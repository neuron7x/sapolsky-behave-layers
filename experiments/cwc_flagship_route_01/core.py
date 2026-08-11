from __future__ import annotations

import hashlib
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

from cwc.instrumentation.flops import (
    FlopLedger,
    attention_core_flops,
    full_causal_pairs,
    lm_head_flops,
)
from experiments.wp18_real_workload_pilot.src.runner import Block

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "artifacts/wp18-real-workload-pilot"
OUT = ROOT / "artifacts/cwc-flagship-route-01"

EXPERIMENT_ID = "CWC-FLAGSHIP-ROUTE-01"
VOCAB = 256
SEQ_LEN = 64
D_MODEL = 64
N_HEAD = 4
TRAIN_STEPS = 400
BATCH = 16
LR = 3e-3
WEIGHT_DECAY = 0.01
RIDGE_ALPHA = 1e-3
WINDOWS_PER_FILE = 64

SEEDS = {
    "CALIBRATION": (74101,),
    "PRIMARY": (74201, 74202, 74203),
    "REPLICATION": (74301, 74302, 74303),
}

FILES = {
    "PROSE": {
        "train": ("corpus_prose_train.txt",),
        "CALIBRATION": ("corpus_prose_eval1.txt", "corpus_prose_eval2.txt"),
        "PRIMARY": ("corpus_prose_eval3.txt", "corpus_prose_eval4.txt"),
        "REPLICATION": ("corpus_prose_eval5.txt",),
    },
    "CODE": {
        "train": ("corpus_code_train.txt",),
        "CALIBRATION": ("corpus_code_eval1.txt", "corpus_code_eval2.txt"),
        "PRIMARY": ("corpus_code_eval3.txt", "corpus_code_eval4.txt"),
        "REPLICATION": ("corpus_code_eval5.txt",),
    },
}

EXPECTED_SHA256 = {
    "corpus_prose_train.txt": "c8908856e76dcaf9821388d027fb4ce4219bad01a92f9efcd4ae6a5242283d09",
    "corpus_prose_eval1.txt": "bc36bae46dd0611600691c5beeda4e7b75d0af90821ff3054005c9baf7664fbb",
    "corpus_prose_eval2.txt": "1d9839f79c24d8508d9341db8733fd459a5a75ff872a9332c4419a94efefc571",
    "corpus_prose_eval3.txt": "bf71b8544096e317f1557a932f4b299aa019cd8f1a414b94da88c3a63a108172",
    "corpus_prose_eval4.txt": "322caad772d06b92ec1b0af31f4f2798a4238032609c14c7378549e99d2e176f",
    "corpus_prose_eval5.txt": "9216ab79a57cb3d49cbbe06cfee9dfe3dd14145fa964a24128f52ee9a709d99f",
    "corpus_code_train.txt": "1378a6448e492cb20ea9ec755cf7bab8cfe39bb782de83b37619c17e87898ca1",
    "corpus_code_eval1.txt": "5904959a4ba16dbed66d9aad4761aea52b51fd79874a59f3706c74d5794f50be",
    "corpus_code_eval2.txt": "30b083fe083da170761564210cc7c522dada9bed947a9ac936ae8d14f55024e3",
    "corpus_code_eval3.txt": "685749478c837bab57b1c1547d1f3efe54237c96e44aa2ec675ee5d16d3cdd5a",
    "corpus_code_eval4.txt": "74826093a986246141fe9b2ad19770573a394991ea6a919ff12628d912d03e8d",
    "corpus_code_eval5.txt": "1bd8b76723710d6115e9d381b9f4b01168e02212f22462efbef7f464bcfd5da0",
}


class ProtocolViolation(RuntimeError):
    pass


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def verify_data_hashes() -> dict[str, str]:
    actual: dict[str, str] = {}
    for name, expected in EXPECTED_SHA256.items():
        path = DATA / name
        if not path.is_file():
            raise ProtocolViolation(f"missing frozen corpus: {name}")
        got = sha256_file(path)
        actual[name] = got
        if got != expected:
            raise ProtocolViolation(f"corpus SHA mismatch {name}: {got} != {expected}")
    return actual


def validate_seed_contract() -> None:
    if SEEDS != {
        "CALIBRATION": (74101,),
        "PRIMARY": (74201, 74202, 74203),
        "REPLICATION": (74301, 74302, 74303),
    }:
        raise ProtocolViolation("frozen model seed contract drifted")
    if set(SEEDS["PRIMARY"]) & set(SEEDS["REPLICATION"]):
        raise ProtocolViolation("PRIMARY/REPLICATION seed overlap")


@dataclass(frozen=True, slots=True)
class FlopContract:
    block: int
    head: int
    route: int
    fixed_depth1: int
    fixed_depth2: int


def flop_contract() -> FlopContract:
    tokens = SEQ_LEN
    led = FlopLedger()
    led.add_dense_linear("qkv", tokens=tokens, d_in=D_MODEL, d_out=3 * D_MODEL)
    led.add_dense_linear("proj", tokens=tokens, d_in=D_MODEL, d_out=D_MODEL)
    led.add_dense_linear("fc", tokens=tokens, d_in=D_MODEL, d_out=4 * D_MODEL)
    led.add_dense_linear("fout", tokens=tokens, d_in=4 * D_MODEL, d_out=D_MODEL)
    led.add(
        "attn",
        "attention_core",
        attention_core_flops(
            batch=1,
            d_model=D_MODEL,
            valid_attention_pairs=full_causal_pairs(SEQ_LEN),
        ),
    )
    block = led.total_logical_flops
    head = lm_head_flops(tokens=tokens, d_model=D_MODEL, vocab_size=VOCAB)
    # Mean pooling: (T-1)*D additions + D divisions. Ridge score 65 MACs = 130 FLOPs.
    # One scalar comparison is charged as one operation.
    route = (SEQ_LEN - 1) * D_MODEL + D_MODEL + 2 * (D_MODEL + 1) + 1
    return FlopContract(block, head, route, block + head, 2 * block + head)


def dynamic_compute(continue_count: int, n_cases: int) -> float:
    if n_cases <= 0 or not (0 <= continue_count <= n_cases):
        raise ProtocolViolation("invalid continuation count")
    f = flop_contract()
    return float(f.fixed_depth1 + f.route + (continue_count / n_cases) * f.block)


def fixed_frontier_loss(loss1: float, loss2: float, budget: float) -> float:
    """Best fixed/randomized depth1/depth2 loss using compute <= budget."""
    f = flop_contract()
    if budget < f.fixed_depth1 - 1e-9:
        raise ProtocolViolation("budget below fixed depth-1")
    if budget > f.fixed_depth2 + 1e-9:
        raise ProtocolViolation("OUTSIDE_FIXED_FRONTIER")
    if loss2 >= loss1:
        return float(loss1)  # extra compute is dominated; baseline may leave budget unused.
    q = min(1.0, max(0.0, (budget - f.fixed_depth1) / (f.fixed_depth2 - f.fixed_depth1)))
    return float(loss1 + q * (loss2 - loss1))


@dataclass(frozen=True, slots=True)
class WindowCase:
    case_id: str
    family: str
    cohort: str
    file_name: str
    offset: int
    x: tuple[int, ...]
    y: tuple[int, ...]


def _window_offsets(path: Path, *, cohort: str, family: str) -> list[int]:
    raw = path.read_bytes()
    valid = len(raw) - SEQ_LEN - 1
    if valid <= WINDOWS_PER_FILE:
        raise ProtocolViolation(f"insufficient window positions: {path}")
    file_hash = sha256_file(path)
    used: set[int] = set()
    out: list[int] = []
    for i in range(WINDOWS_PER_FILE):
        key = f"{EXPERIMENT_ID}|{cohort}|{family}|{file_hash}|{i}".encode()
        offset = int.from_bytes(hashlib.sha256(key).digest()[:8], "big") % valid
        while offset in used:
            offset = (offset + 1) % valid
        used.add(offset)
        out.append(offset)
    return out


def window_cases(family: str, cohort: str) -> list[WindowCase]:
    if family not in ("PROSE", "CODE") or cohort not in ("CALIBRATION", "PRIMARY", "REPLICATION"):
        raise ProtocolViolation("invalid family/cohort")
    out: list[WindowCase] = []
    for name in FILES[family][cohort]:
        path = DATA / name
        raw = path.read_bytes()
        file_hash = sha256_file(path)
        for i, offset in enumerate(_window_offsets(path, cohort=cohort, family=family)):
            x = tuple(raw[offset : offset + SEQ_LEN])
            y = tuple(raw[offset + 1 : offset + SEQ_LEN + 1])
            if len(x) != SEQ_LEN or len(y) != SEQ_LEN:
                raise ProtocolViolation("window length drift")
            case_id = hashlib.sha256(
                f"{EXPERIMENT_ID}|{cohort}|{family}|{file_hash}|{i}|{offset}".encode()
            ).hexdigest()
            out.append(WindowCase(case_id, family, cohort, name, offset, x, y))
    if len({c.case_id for c in out}) != len(out):
        raise ProtocolViolation("duplicate case id")
    return out


class DualExitLM(nn.Module):
    def __init__(self) -> None:
        super().__init__()
        self.emb = nn.Embedding(VOCAB, D_MODEL)
        self.pos = nn.Embedding(SEQ_LEN, D_MODEL)
        self.blocks = nn.ModuleList([Block(D_MODEL, N_HEAD), Block(D_MODEL, N_HEAD)])
        self.head = nn.Linear(D_MODEL, VOCAB, bias=False)

    def first_hidden(self, x: torch.Tensor) -> torch.Tensor:
        t = x.shape[1]
        h = self.emb(x) + self.pos(torch.arange(t, device=x.device)).unsqueeze(0)
        return self.blocks[0](h)

    def second_hidden(self, h1: torch.Tensor) -> torch.Tensor:
        return self.blocks[1](h1)

    def logits(self, h: torch.Tensor) -> torch.Tensor:
        return self.head(h)

    def forward_exits(self, x: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        h1 = self.first_hidden(x)
        l1 = self.logits(h1)
        h2 = self.second_hidden(h1)
        l2 = self.logits(h2)
        return l1, l2, h1


def _training_bytes() -> dict[str, torch.Tensor]:
    return {
        "PROSE": torch.tensor(list((DATA / FILES["PROSE"]["train"][0]).read_bytes()), dtype=torch.long),
        "CODE": torch.tensor(list((DATA / FILES["CODE"]["train"][0]).read_bytes()), dtype=torch.long),
    }


def train_model(seed: int, checkpoint: Path) -> dict[str, Any]:
    validate_seed_contract()
    if seed not in set(sum((list(v) for v in SEEDS.values()), [])):
        raise ProtocolViolation(f"unregistered seed: {seed}")
    torch.manual_seed(seed)
    torch.use_deterministic_algorithms(True)
    model = DualExitLM()
    model.train()
    opt = torch.optim.AdamW(model.parameters(), lr=LR, weight_decay=WEIGHT_DECAY)
    data = _training_bytes()
    gen = torch.Generator().manual_seed(seed + 17)
    first_loss = last_loss = None
    for step in range(TRAIN_STEPS):
        family = "PROSE" if step % 2 == 0 else "CODE"
        src = data[family]
        ix = torch.randint(0, len(src) - SEQ_LEN - 1, (BATCH,), generator=gen)
        x = torch.stack([src[i : i + SEQ_LEN] for i in ix])
        y = torch.stack([src[i + 1 : i + SEQ_LEN + 1] for i in ix])
        l1, l2, _ = model.forward_exits(x)
        ce1 = F.cross_entropy(l1.reshape(-1, VOCAB), y.reshape(-1))
        ce2 = F.cross_entropy(l2.reshape(-1, VOCAB), y.reshape(-1))
        loss = 0.5 * (ce1 + ce2)
        opt.zero_grad(set_to_none=True)
        loss.backward()
        opt.step()
        if first_loss is None:
            first_loss = float(loss.detach())
        last_loss = float(loss.detach())
    model.eval()
    checkpoint.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "experiment": EXPERIMENT_ID,
        "seed": seed,
        "architecture": {"vocab": VOCAB, "seq_len": SEQ_LEN, "d_model": D_MODEL, "n_head": N_HEAD, "n_layer": 2},
        "training": {"steps": TRAIN_STEPS, "batch": BATCH, "lr": LR, "weight_decay": WEIGHT_DECAY,
                     "first_loss": first_loss, "final_loss": last_loss},
        "data_sha256": verify_data_hashes(),
        "state_dict": model.state_dict(),
    }
    torch.save(payload, checkpoint)
    try:
        checkpoint_ref = checkpoint.resolve().relative_to(ROOT.resolve()).as_posix()
    except ValueError as exc:
        raise ProtocolViolation("checkpoint must remain repository-relative") from exc
    return {"seed": seed, "checkpoint": checkpoint_ref, "sha256": sha256_file(checkpoint), **payload["training"]}


def load_model(checkpoint: Path) -> DualExitLM:
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    if payload.get("experiment") != EXPERIMENT_ID:
        raise ProtocolViolation("checkpoint experiment mismatch")
    model = DualExitLM()
    model.load_state_dict(payload["state_dict"])
    model.eval()
    return model


@dataclass(frozen=True, slots=True)
class EvalRow:
    case_id: str
    family: str
    cohort: str
    loss1: float
    loss2: float
    feature: tuple[float, ...]  # 65-dimensional pre-target route representation

    @property
    def gain(self) -> float:
        return self.loss1 - self.loss2


def evaluate_rows(model: DualExitLM, family: str, cohort: str) -> list[EvalRow]:
    cases = window_cases(family, cohort)
    x = torch.tensor([c.x for c in cases], dtype=torch.long)
    y = torch.tensor([c.y for c in cases], dtype=torch.long)
    with torch.no_grad():
        l1, l2, h1 = model.forward_exits(x)
        p1 = F.cross_entropy(l1.transpose(1, 2), y, reduction="none").mean(dim=1)
        p2 = F.cross_entropy(l2.transpose(1, 2), y, reduction="none").mean(dim=1)
        z = h1.mean(dim=1).float()
        fam = torch.zeros((len(cases), 1), dtype=z.dtype) if family == "PROSE" else torch.ones((len(cases), 1), dtype=z.dtype)
        feat = torch.cat([z, fam], dim=1)
    return [
        EvalRow(c.case_id, family, cohort, float(p1[i]), float(p2[i]), tuple(float(v) for v in feat[i]))
        for i, c in enumerate(cases)
    ]


@dataclass(frozen=True, slots=True)
class RidgeModel:
    mean: tuple[float, ...]
    scale: tuple[float, ...]
    intercept: float
    coef: tuple[float, ...]
    alpha: float = RIDGE_ALPHA

    def predict(self, x: np.ndarray) -> np.ndarray:
        mean = np.asarray(self.mean)
        scale = np.asarray(self.scale)
        coef = np.asarray(self.coef)
        return ((x - mean) / scale) @ coef + self.intercept

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "RidgeModel":
        return cls(tuple(raw["mean"]), tuple(raw["scale"]), float(raw["intercept"]), tuple(raw["coef"]), float(raw["alpha"]))


def fit_ridge(x: np.ndarray, y: np.ndarray, *, cohort: str) -> RidgeModel:
    if cohort != "CALIBRATION":
        raise ProtocolViolation("ridge fitting is CALIBRATION-only")
    if x.ndim != 2 or x.shape[1] != D_MODEL + 1 or y.shape != (x.shape[0],):
        raise ProtocolViolation("ridge shape mismatch")
    mean = x.mean(axis=0)
    scale = x.std(axis=0)
    scale = np.where(scale < 1e-12, 1.0, scale)
    xs = (x - mean) / scale
    xa = np.concatenate([np.ones((len(xs), 1)), xs], axis=1)
    reg = np.eye(xa.shape[1]) * RIDGE_ALPHA
    reg[0, 0] = 0.0
    beta = np.linalg.solve(xa.T @ xa + reg, xa.T @ y)
    return RidgeModel(tuple(mean.tolist()), tuple(scale.tolist()), float(beta[0]), tuple(beta[1:].tolist()))


def rows_to_xy(rows: Iterable[EvalRow]) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    rs = list(rows)
    x = np.asarray([r.feature for r in rs], dtype=float)
    gain = np.asarray([r.gain for r in rs], dtype=float)
    loss1 = np.asarray([r.loss1 for r in rs], dtype=float)
    return x, gain, loss1


def frontier_slope(rows: Iterable[EvalRow]) -> dict[str, float]:
    rs = list(rows)
    l1 = float(np.mean([r.loss1 for r in rs]))
    l2 = float(np.mean([r.loss2 for r in rs]))
    f = flop_contract()
    slope = max(0.0, (l1 - l2) / (f.fixed_depth2 - f.fixed_depth1))
    return {"loss1": l1, "loss2": l2, "gain_per_flop": slope}


def make_calibration_policy(rows_by_family: dict[str, list[EvalRow]], checkpoint_meta: dict[str, Any]) -> dict[str, Any]:
    pooled = rows_by_family["PROSE"] + rows_by_family["CODE"]
    x, gain, loss1 = rows_to_xy(pooled)
    gain_model = fit_ridge(x, gain, cohort="CALIBRATION")
    difficulty_model = fit_ridge(x, loss1, cohort="CALIBRATION")
    return {
        "experiment": EXPERIMENT_ID,
        "status": "CALIBRATION_FROZEN",
        "checkpoint": checkpoint_meta,
        "ridge_alpha": RIDGE_ALPHA,
        "gain_model": gain_model.to_dict(),
        "difficulty_model": difficulty_model.to_dict(),
        "frontier": {fam: frontier_slope(rows) for fam, rows in rows_by_family.items()},
        "flops": asdict(flop_contract()),
        "data_sha256": verify_data_hashes(),
        "seed_contract": {k: list(v) for k, v in SEEDS.items()},
    }


def _select_top(scores: np.ndarray, n: int, case_ids: list[str], *, largest: bool = True) -> np.ndarray:
    if not 0 <= n <= len(scores):
        raise ProtocolViolation("invalid selection count")
    # Stable, deterministic tie-break by case hash.
    order = sorted(range(len(scores)), key=lambda i: ((-scores[i] if largest else scores[i]), case_ids[i]))
    mask = np.zeros(len(scores), dtype=bool)
    for i in order[:n]:
        mask[i] = True
    return mask


def _random_matched(case_ids: list[str], n: int) -> np.ndarray:
    score = np.asarray([int(hashlib.sha256((EXPERIMENT_ID + "|RANDOM|" + c).encode()).hexdigest(), 16) for c in case_ids], dtype=object)
    order = sorted(range(len(case_ids)), key=lambda i: (score[i], case_ids[i]))
    mask = np.zeros(len(case_ids), dtype=bool)
    for i in order[:n]:
        mask[i] = True
    return mask


def _policy_loss(loss1: np.ndarray, loss2: np.ndarray, mask: np.ndarray) -> float:
    return float(np.mean(np.where(mask, loss2, loss1)))


def evaluate_cell(rows: list[EvalRow], policy: dict[str, Any]) -> dict[str, Any]:
    if not rows:
        raise ProtocolViolation("empty evaluation cell")
    family = rows[0].family
    cohort = rows[0].cohort
    if any(r.family != family or r.cohort != cohort for r in rows):
        raise ProtocolViolation("mixed cell")
    if cohort not in ("PRIMARY", "REPLICATION"):
        raise ProtocolViolation("scientific cell must be PRIMARY/REPLICATION")
    x, gain, loss1 = rows_to_xy(rows)
    loss2 = np.asarray([r.loss2 for r in rows], dtype=float)
    ids = [r.case_id for r in rows]
    gm = RidgeModel.from_dict(policy["gain_model"])
    dm = RidgeModel.from_dict(policy["difficulty_model"])
    pred_gain = gm.predict(x)
    pred_diff = dm.predict(x)
    f = flop_contract()
    slope = float(policy["frontier"][family]["gain_per_flop"])
    candidate = pred_gain > slope * f.block
    n_cont = int(candidate.sum())
    q = n_cont / len(rows)
    compute = dynamic_compute(n_cont, len(rows))
    outside = compute > f.fixed_depth2 + 1e-9

    hidden_norm_score = np.linalg.norm(x[:, :D_MODEL], axis=1)
    masks = {
        "DECISION_RELEVANT": candidate,
        "RANDOM_MATCHED": _random_matched(ids, n_cont),
        "HIDDEN_NORM_MATCHED": _select_top(hidden_norm_score, n_cont, ids, largest=True),
        "DIFFICULTY_MATCHED": _select_top(pred_diff, n_cont, ids, largest=True),
        "ORACLE_MATCHED": _select_top(gain, n_cont, ids, largest=True),
    }
    if any(int(m.sum()) != n_cont for m in masks.values()):
        raise ProtocolViolation("matched continuation count drift")
    losses = {name: _policy_loss(loss1, loss2, mask) for name, mask in masks.items()}
    l1 = float(loss1.mean())
    l2 = float(loss2.mean())
    frontier = None if outside else fixed_frontier_loss(l1, l2, compute)
    eps = 1e-12
    endpoints = {
        "within_fixed_frontier": not outside,
        "beats_fixed_frontier": (not outside and losses["DECISION_RELEVANT"] < float(frontier) - eps),
        "beats_random_matched": losses["DECISION_RELEVANT"] < losses["RANDOM_MATCHED"] - eps,
        "no_worse_hidden_norm": losses["DECISION_RELEVANT"] <= losses["HIDDEN_NORM_MATCHED"] + eps,
        "beats_difficulty_matched": losses["DECISION_RELEVANT"] < losses["DIFFICULTY_MATCHED"] - eps,
        "oracle_sanity": losses["ORACLE_MATCHED"] <= losses["DECISION_RELEVANT"] + eps,
        "matched_counts": all(int(m.sum()) == n_cont for m in masks.values()),
    }
    decisions = [
        {
            "case_id": ids[i],
            "loss1": float(loss1[i]),
            "loss2": float(loss2[i]),
            "gain": float(gain[i]),
            "predicted_gain": float(pred_gain[i]),
            "predicted_difficulty": float(pred_diff[i]),
            "candidate_continue": bool(candidate[i]),
            "random_continue": bool(masks["RANDOM_MATCHED"][i]),
            "hidden_norm_continue": bool(masks["HIDDEN_NORM_MATCHED"][i]),
            "difficulty_continue": bool(masks["DIFFICULTY_MATCHED"][i]),
            "oracle_continue": bool(masks["ORACLE_MATCHED"][i]),
        }
        for i in range(len(rows))
    ]
    advantage = None if outside else float(frontier) - losses["DECISION_RELEVANT"]
    return {
        "family": family,
        "cohort": cohort,
        "n_cases": len(rows),
        "n_continue": n_cont,
        "continue_rate": q,
        "logical_flops_per_window": compute,
        "fixed_depth1_flops": f.fixed_depth1,
        "fixed_depth2_flops": f.fixed_depth2,
        "fixed_depth1_loss": l1,
        "fixed_depth2_loss": l2,
        "fixed_frontier_loss": frontier,
        "losses": losses,
        "candidate_advantage_vs_fixed_frontier": advantage,
        "endpoints": endpoints,
        "passed": all(endpoints.values()),
        "decisions": decisions,
    }


def cohort_gate(cells: list[dict[str, Any]], cohort: str) -> dict[str, Any]:
    expected_seeds = set(SEEDS[cohort])
    if cohort not in ("PRIMARY", "REPLICATION"):
        raise ProtocolViolation("invalid scientific cohort")
    got = {(int(c["seed"]), c["family"]) for c in cells}
    expected = {(s, f) for s in expected_seeds for f in ("PROSE", "CODE")}
    if got != expected:
        raise ProtocolViolation(f"cell set mismatch: {got ^ expected}")
    med: dict[str, float | None] = {}
    for fam in ("PROSE", "CODE"):
        vals = [c["candidate_advantage_vs_fixed_frontier"] for c in cells if c["family"] == fam]
        med[fam] = None if any(v is None for v in vals) else float(np.median(np.asarray(vals, dtype=float)))
    med_positive = all(v is not None and v > 0.0 for v in med.values())
    passed = all(c["passed"] for c in cells) and med_positive
    return {"cohort": cohort, "passed": passed, "median_advantage_vs_fixed_frontier": med,
            "all_cells_pass": all(c["passed"] for c in cells), "median_positive_both_families": med_positive}


def final_verdict(primary: dict[str, Any], replication: dict[str, Any], *, void: bool = False) -> str:
    if void:
        return "CWC_FLAGSHIP_ROUTE_01_VOID"
    if not primary["passed"]:
        return "CWC_FLAGSHIP_ROUTE_01_NOT_SUPPORTED"
    if not replication["passed"]:
        return "CWC_FLAGSHIP_ROUTE_01_PRIMARY_PASS_REPLICATION_FAIL"
    return "CWC_FLAGSHIP_ROUTE_01_SUPPORTED_NARROW"


def canonical_json_hash(value: Any) -> str:
    raw = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()
