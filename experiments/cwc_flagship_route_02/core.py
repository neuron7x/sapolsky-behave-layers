from __future__ import annotations

import hashlib
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any, Iterable

import numpy as np
import torch
import torch.nn.functional as F

from experiments.cwc_flagship_route_01 import core as r1

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "artifacts/wp18-real-workload-pilot"
OUT = ROOT / "artifacts/cwc-flagship-route-02"
EXPERIMENT_ID = "CWC-FLAGSHIP-ROUTE-02"

VOCAB = r1.VOCAB
SEQ_LEN = r1.SEQ_LEN
D_MODEL = r1.D_MODEL
N_HEAD = r1.N_HEAD
TRAIN_STEPS = r1.TRAIN_STEPS
BATCH = r1.BATCH
LR = r1.LR
WEIGHT_DECAY = r1.WEIGHT_DECAY
RIDGE_ALPHA = r1.RIDGE_ALPHA
WINDOWS_PER_FILE = r1.WINDOWS_PER_FILE
FILES = r1.FILES
EXPECTED_SHA256 = r1.EXPECTED_SHA256
ProtocolViolation = r1.ProtocolViolation
DualExitLM = r1.DualExitLM
EvalRow = r1.EvalRow
RidgeModel = r1.RidgeModel
sha256_file = r1.sha256_file
verify_data_hashes = r1.verify_data_hashes
flop_contract = r1.flop_contract
dynamic_compute = r1.dynamic_compute
fixed_frontier_loss = r1.fixed_frontier_loss
fit_ridge = r1.fit_ridge
rows_to_xy = r1.rows_to_xy
frontier_slope = r1.frontier_slope

SEEDS = {
    "PRIMARY": (74401, 74402, 74403),
    "REPLICATION": (74501, 74502, 74503),
}


def validate_seed_contract() -> None:
    if SEEDS != {
        "PRIMARY": (74401, 74402, 74403),
        "REPLICATION": (74501, 74502, 74503),
    }:
        raise ProtocolViolation("R2 seed contract drifted")
    if set(SEEDS["PRIMARY"]) & set(SEEDS["REPLICATION"]):
        raise ProtocolViolation("PRIMARY/REPLICATION seed overlap")


def _r1_offsets(path: Path, *, cohort: str, family: str) -> set[int]:
    return set(r1._window_offsets(path, cohort=cohort, family=family))


def _window_offsets(path: Path, *, cohort: str, family: str) -> list[int]:
    if cohort not in ("CALIBRATION", "PRIMARY", "REPLICATION"):
        raise ProtocolViolation("invalid cohort")
    raw = path.read_bytes()
    valid = len(raw) - SEQ_LEN - 1
    if valid <= WINDOWS_PER_FILE:
        raise ProtocolViolation(f"insufficient window positions: {path}")
    file_hash = sha256_file(path)
    forbidden = _r1_offsets(path, cohort=cohort, family=family)
    used: set[int] = set()
    out: list[int] = []
    for i in range(WINDOWS_PER_FILE):
        key = f"{EXPERIMENT_ID}|{cohort}|{family}|{file_hash}|{i}".encode()
        offset = int.from_bytes(hashlib.sha256(key).digest()[:8], "big") % valid
        probes = 0
        while offset in used or offset in forbidden:
            offset = (offset + 1) % valid
            probes += 1
            if probes > valid:
                raise ProtocolViolation("unable to construct non-overlapping R2 cohort")
        used.add(offset)
        out.append(offset)
    if set(out) & forbidden:
        raise ProtocolViolation("R2/R1 offset overlap")
    return out


def window_cases(family: str, cohort: str) -> list[r1.WindowCase]:
    if family not in ("PROSE", "CODE") or cohort not in ("CALIBRATION", "PRIMARY", "REPLICATION"):
        raise ProtocolViolation("invalid family/cohort")
    out: list[r1.WindowCase] = []
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
            out.append(r1.WindowCase(case_id, family, cohort, name, offset, x, y))
    if len({c.case_id for c in out}) != len(out):
        raise ProtocolViolation("duplicate case id")
    return out


def assert_no_r1_overlap() -> dict[str, int]:
    checked = 0
    for family in ("PROSE", "CODE"):
        for cohort in ("CALIBRATION", "PRIMARY", "REPLICATION"):
            for name in FILES[family][cohort]:
                path = DATA / name
                a = set(_window_offsets(path, cohort=cohort, family=family))
                b = _r1_offsets(path, cohort=cohort, family=family)
                if a & b:
                    raise ProtocolViolation(f"R2/R1 overlap: {family}/{cohort}/{name}")
                checked += len(a)
    return {"r2_offsets_checked": checked, "overlaps": 0}


def _training_bytes() -> dict[str, torch.Tensor]:
    return {
        "PROSE": torch.tensor(list((DATA / FILES["PROSE"]["train"][0]).read_bytes()), dtype=torch.long),
        "CODE": torch.tensor(list((DATA / FILES["CODE"]["train"][0]).read_bytes()), dtype=torch.long),
    }


def train_model(seed: int, checkpoint: Path) -> dict[str, Any]:
    validate_seed_contract(); verify_data_hashes()
    if seed not in set(SEEDS["PRIMARY"] + SEEDS["REPLICATION"]):
        raise ProtocolViolation(f"unregistered R2 seed: {seed}")
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
        opt.zero_grad(set_to_none=True); loss.backward(); opt.step()
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
    ref = checkpoint.resolve().relative_to(ROOT.resolve()).as_posix()
    return {"seed": seed, "checkpoint": ref, "sha256": sha256_file(checkpoint), **payload["training"]}


def load_model(checkpoint: Path, *, expected_seed: int) -> DualExitLM:
    payload = torch.load(checkpoint, map_location="cpu", weights_only=False)
    if payload.get("experiment") != EXPERIMENT_ID or int(payload.get("seed", -1)) != expected_seed:
        raise ProtocolViolation("R2 checkpoint identity mismatch")
    model = DualExitLM(); model.load_state_dict(payload["state_dict"]); model.eval()
    return model


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


def make_seed_policy(seed: int, rows_by_family: dict[str, list[EvalRow]], checkpoint_meta: dict[str, Any]) -> dict[str, Any]:
    if int(checkpoint_meta.get("seed", -1)) != seed:
        raise ProtocolViolation("policy/checkpoint seed mismatch")
    pooled = rows_by_family["PROSE"] + rows_by_family["CODE"]
    x, gain, loss1 = rows_to_xy(pooled)
    gain_model = fit_ridge(x, gain, cohort="CALIBRATION")
    difficulty_model = fit_ridge(x, loss1, cohort="CALIBRATION")
    return {
        "experiment": EXPERIMENT_ID,
        "status": "PER_MODEL_CALIBRATION_FROZEN",
        "seed": seed,
        "checkpoint": checkpoint_meta,
        "ridge_alpha": RIDGE_ALPHA,
        "gain_model": gain_model.to_dict(),
        "difficulty_model": difficulty_model.to_dict(),
        "frontier": {fam: frontier_slope(rows) for fam, rows in rows_by_family.items()},
        "flops": asdict(flop_contract()),
        "data_sha256": verify_data_hashes(),
        "anti_reuse": assert_no_r1_overlap(),
    }


def _select_top(scores: np.ndarray, n: int, case_ids: list[str], *, largest: bool = True) -> np.ndarray:
    return r1._select_top(scores, n, case_ids, largest=largest)


def _random_matched(case_ids: list[str], n: int) -> np.ndarray:
    score = np.asarray([int(hashlib.sha256((EXPERIMENT_ID + "|RANDOM|" + c).encode()).hexdigest(), 16) for c in case_ids], dtype=object)
    order = sorted(range(len(case_ids)), key=lambda i: (score[i], case_ids[i]))
    mask = np.zeros(len(case_ids), dtype=bool)
    for i in order[:n]: mask[i] = True
    return mask


def _policy_loss(loss1: np.ndarray, loss2: np.ndarray, mask: np.ndarray) -> float:
    return float(np.mean(np.where(mask, loss2, loss1)))


def evaluate_cell(rows: list[EvalRow], policy: dict[str, Any], *, expected_seed: int) -> dict[str, Any]:
    if int(policy.get("seed", -1)) != expected_seed:
        raise ProtocolViolation("wrong per-model policy")
    if policy.get("experiment") != EXPERIMENT_ID:
        raise ProtocolViolation("wrong R2 policy experiment")
    if not rows:
        raise ProtocolViolation("empty evaluation cell")
    family, cohort = rows[0].family, rows[0].cohort
    if cohort not in ("PRIMARY", "REPLICATION") or any(r.family != family or r.cohort != cohort for r in rows):
        raise ProtocolViolation("invalid/mixed scientific cell")
    x, gain, loss1 = rows_to_xy(rows)
    loss2 = np.asarray([r.loss2 for r in rows], dtype=float)
    ids = [r.case_id for r in rows]
    gm = RidgeModel.from_dict(policy["gain_model"])
    dm = RidgeModel.from_dict(policy["difficulty_model"])
    pred_gain, pred_diff = gm.predict(x), dm.predict(x)
    f = flop_contract()
    slope = float(policy["frontier"][family]["gain_per_flop"])
    candidate = pred_gain > slope * f.block
    n_cont = int(candidate.sum())
    q = n_cont / len(rows)
    compute = dynamic_compute(n_cont, len(rows))
    outside = compute > f.fixed_depth2 + 1e-9
    hidden_norm = np.linalg.norm(x[:, :D_MODEL], axis=1)
    masks = {
        "DECISION_RELEVANT": candidate,
        "RANDOM_MATCHED": _random_matched(ids, n_cont),
        "HIDDEN_NORM_MATCHED": _select_top(hidden_norm, n_cont, ids, largest=True),
        "DIFFICULTY_MATCHED": _select_top(pred_diff, n_cont, ids, largest=True),
        "ORACLE_MATCHED": _select_top(gain, n_cont, ids, largest=True),
    }
    if any(int(m.sum()) != n_cont for m in masks.values()):
        raise ProtocolViolation("matched continuation count drift")
    losses = {name: _policy_loss(loss1, loss2, m) for name, m in masks.items()}
    l1, l2 = float(loss1.mean()), float(loss2.mean())
    frontier = None if outside else fixed_frontier_loss(l1, l2, compute)
    eps = 1e-12
    endpoints = {
        "within_fixed_frontier": not outside,
        "beats_fixed_frontier": frontier is not None and losses["DECISION_RELEVANT"] < frontier - eps,
        "beats_random_matched": losses["DECISION_RELEVANT"] < losses["RANDOM_MATCHED"] - eps,
        "no_worse_hidden_norm": losses["DECISION_RELEVANT"] <= losses["HIDDEN_NORM_MATCHED"] + eps,
        "beats_difficulty_matched": losses["DECISION_RELEVANT"] < losses["DIFFICULTY_MATCHED"] - eps,
        "oracle_sanity": losses["ORACLE_MATCHED"] <= losses["DECISION_RELEVANT"] + eps,
        "matched_counts": all(int(m.sum()) == n_cont for m in masks.values()),
        "anti_reuse": assert_no_r1_overlap()["overlaps"] == 0,
    }
    advantage = None if frontier is None else float(frontier - losses["DECISION_RELEVANT"])
    return {
        "experiment": EXPERIMENT_ID, "cohort": cohort, "family": family, "seed": expected_seed,
        "n_cases": len(rows), "continue_count": n_cont, "continue_rate": q,
        "logical_flops_per_window": compute, "fixed_frontier_loss": frontier,
        "candidate_advantage_vs_fixed_frontier": advantage, "loss1": l1, "loss2": l2,
        "losses": losses, "endpoints": endpoints, "passed": all(endpoints.values()),
    }


def cohort_gate(cells: list[dict[str, Any]], cohort: str) -> dict[str, Any]:
    expected_seeds = SEEDS[cohort]
    expected = {(s, f) for s in expected_seeds for f in ("PROSE", "CODE")}
    got = {(int(c["seed"]), c["family"]) for c in cells}
    if got != expected:
        raise ProtocolViolation(f"{cohort} cell coverage mismatch")
    medians: dict[str, float | None] = {}
    for fam in ("PROSE", "CODE"):
        vals = [c["candidate_advantage_vs_fixed_frontier"] for c in cells if c["family"] == fam]
        medians[fam] = None if any(v is None for v in vals) else float(np.median(np.asarray(vals, dtype=float)))
    passed = all(c["passed"] for c in cells) and all(v is not None and v > 0 for v in medians.values())
    return {"cohort": cohort, "passed": passed, "cell_pass_count": sum(bool(c["passed"]) for c in cells),
            "cell_count": len(cells), "median_advantage_by_family": medians}


def final_verdict(primary: dict[str, Any], replication: dict[str, Any]) -> str:
    if not primary["passed"]:
        return "CWC_FLAGSHIP_ROUTE_02_NOT_SUPPORTED"
    if not replication["passed"]:
        return "CWC_FLAGSHIP_ROUTE_02_NOT_SUPPORTED_REPLICATION"
    return "CWC_FLAGSHIP_ROUTE_02_SUPPORTED_NARROW"
