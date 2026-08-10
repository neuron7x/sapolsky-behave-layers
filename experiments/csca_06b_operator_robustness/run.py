from __future__ import annotations

import hashlib
import json
from pathlib import Path
import statistics
import time
from typing import FrozenSet, Mapping

import numpy as np
import torch
import torch.nn.functional as F

from cwc.credit.ablation_shapley import exact_ablation_shapley, ranked_by_absolute_credit
from experiments.csca_05_shadow_pilot.direct_credit import (
    PLAYERS,
    PromptInterventionSpec,
    candidate_spans,
    top_gap,
)
from experiments.csca_05_shadow_pilot.runtime_model import (
    CODE_MARKER,
    PROSE_MARKER,
    load_checkpoint,
    state_dict_sha256,
)
from experiments.csca_05_shadow_pilot.run import CONTEXT_FILES, _checkpoint_path

ROOT = Path(__file__).resolve().parents[2]
PROTOCOL = json.loads((ROOT / "experiments/csca_06b_operator_robustness/protocol.json").read_text())
ART = ROOT / "artifacts/csca-06b-operator-robustness"
RESULT = ROOT / "research/results/CSCA-06B-OP"
MARKER = {"PROSE": PROSE_MARKER, "CODE": CODE_MARKER}


def _json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _read(paths: list[Path]) -> bytes:
    return b"\n".join(p.read_bytes() for p in paths)


def _old_prompt_hashes() -> set[str]:
    out: set[str] = set()
    cal = ROOT / "artifacts/csca-05-runtime/calibration/raw_records.json"
    if cal.is_file():
        out.update(str(x["prompt_hash"]) for x in json.loads(cal.read_text()))
    for cohort in ("primary", "replication"):
        for path in (ROOT / f"artifacts/csca-05-runtime/{cohort}/traces").glob("*.json"):
            out.add(str(json.loads(path.read_text())["prompt_hash"]))
    diag = ROOT / "artifacts/csca-05-runtime/diagnostics/intervention_semantics/rows.json"
    if diag.is_file():
        out.update(str(x["prompt_hash"]) for x in json.loads(diag.read_text()))
    return out


def _source_bytes(context: str, cohort: str) -> bytes:
    return _read(CONTEXT_FILES[context][cohort])


def fresh_specs(context: str, cohort: str) -> list[PromptInterventionSpec]:
    raw = _source_bytes(context, cohort)
    content = int(PROTOCOL["prompt_content_bytes"])
    n = int(PROTOCOL["prompts_per_context"])
    old = _old_prompt_hashes()
    used_offsets: set[int] = set()
    specs: list[PromptInterventionSpec] = []
    for i in range(n):
        digest = hashlib.sha256(f"CSCA06B:PROMPT:{cohort}:{context}:{i}".encode()).digest()
        offset = int.from_bytes(digest[:8], "big") % (len(raw) - content)
        attempts = 0
        while True:
            tokens = (MARKER[context], *raw[offset : offset + content])
            spec = PromptInterventionSpec(tuple(int(x) for x in tokens), context, candidate_spans(len(tokens)))
            if offset not in used_offsets and spec.prompt_hash not in old and all(spec.prompt_hash != x.prompt_hash for x in specs):
                break
            offset = (offset + 1) % (len(raw) - content)
            attempts += 1
            if attempts > len(raw):
                raise RuntimeError("unable to allocate fresh prompt")
        used_offsets.add(offset)
        specs.append(spec)
    return specs


def _donor_pool(context: str, cohort: str, kernel: str) -> bytes:
    if kernel == "K_TRAIN_CONTIG8":
        return CONTEXT_FILES[context]["train"].read_bytes()
    if kernel == "K_COHORT_CONTIG8":
        return _source_bytes(context, cohort)
    raise ValueError(kernel)


def donor_assignments(spec: PromptInterventionSpec, *, cohort: str, kernel: str) -> tuple[dict[str, tuple[int, ...]], ...]:
    pool = _donor_pool(spec.context, cohort, kernel)
    width = 4
    n = int(PROTOCOL["donor_assignments_per_kernel"])
    out: list[dict[str, tuple[int, ...]]] = []
    for draw in range(n):
        row: dict[str, tuple[int, ...]] = {}
        for player in PLAYERS:
            start, end = spec.spans[player]
            original = tuple(spec.prompt_tokens[start:end])
            digest = hashlib.sha256(
                f"CSCA06B:DONOR:{cohort}:{spec.context}:{kernel}:{spec.prompt_hash}:{player}:{draw}".encode()
            ).digest()
            offset = int.from_bytes(digest[:8], "big") % (len(pool) - width)
            attempts = 0
            replacement = tuple(int(x) for x in pool[offset : offset + width])
            while replacement == original:
                offset = (offset + 1) % (len(pool) - width)
                replacement = tuple(int(x) for x in pool[offset : offset + width])
                attempts += 1
                if attempts > len(pool):
                    raise RuntimeError("donor pool cannot produce a non-identical intervention")
            row[player] = replacement
        out.append(row)
    return tuple(out)


@torch.inference_mode()
def _target_log_prob(model, prompt: list[int], target: int) -> float:
    ids = torch.tensor([prompt], dtype=torch.long, device=model.get_device())
    lp = F.log_softmax(model(ids)[:, -1, :], dim=-1)[0]
    return float(lp[target].item())


class FiniteSoftInterventionOracle:
    """Exact expectation over a frozen finite stochastic intervention kernel."""

    def __init__(self, model, spec: PromptInterventionSpec, assignments: tuple[dict[str, tuple[int, ...]], ...]):
        self.model = model
        self.spec = spec
        self.assignments = assignments
        factual = list(spec.prompt_tokens)
        ids = torch.tensor([factual], dtype=torch.long, device=model.get_device())
        with torch.inference_mode():
            lp = F.log_softmax(model(ids)[:, -1, :], dim=-1)[0]
        self.target = int(torch.argmax(lp).item())
        self.forward_calls = 1

    def __call__(self, keep: FrozenSet[str]) -> float:
        vals = []
        for assignment in self.assignments:
            prompt = list(self.spec.prompt_tokens)
            for player, (start, end) in self.spec.spans.items():
                if player not in keep:
                    prompt[start:end] = assignment[player]
            vals.append(_target_log_prob(self.model, prompt, self.target))
            self.forward_calls += 1
        return float(sum(vals) / len(vals))


class SpaceOracle:
    def __init__(self, model, spec: PromptInterventionSpec):
        self.model=model; self.spec=spec; self.forward_calls=1
        ids=torch.tensor([list(spec.prompt_tokens)],dtype=torch.long,device=model.get_device())
        with torch.inference_mode(): lp=F.log_softmax(model(ids)[:,-1,:],dim=-1)[0]
        self.target=int(torch.argmax(lp).item())
    def __call__(self, keep: FrozenSet[str]) -> float:
        prompt=list(self.spec.prompt_tokens)
        for player,(start,end) in self.spec.spans.items():
            if player not in keep: prompt[start:end]=[32]*(end-start)
        self.forward_calls+=1
        return _target_log_prob(self.model,prompt,self.target)


def sign(x: float) -> int:
    return 1 if x > 0 else (-1 if x < 0 else 0)


def l1(a: Mapping[str,float], b: Mapping[str,float]) -> float:
    return float(sum(abs(float(a[k])-float(b[k])) for k in PLAYERS)/len(PLAYERS))


def score_pair(train: Mapping[str,float], cohort: Mapping[str,float], *, delta: float) -> dict:
    ttop=ranked_by_absolute_credit(train)[0]; ctop=ranked_by_absolute_credit(cohort)[0]
    top_same=ttop==ctop
    ts=sign(float(train[ttop])); cs=sign(float(cohort[ctop]))
    sign_same=bool(top_same and ts==cs and ts!=0)
    train_gap=top_gap(train); cohort_gap=top_gap(cohort)
    magnitude=min(abs(float(train[ttop])),abs(float(cohort[ctop]))) if top_same else 0.0
    robust=bool(top_same and sign_same and train_gap>delta and cohort_gap>delta and magnitude>delta)
    return {
        "train_top":ttop,"cohort_top":ctop,"top_same":top_same,"train_top_sign":ts,"cohort_top_sign":cs,
        "sign_same":sign_same,"train_gap":train_gap,"cohort_gap":cohort_gap,"min_top_magnitude":magnitude,
        "robust_authority":robust,"candidate":ttop if robust else None,"sign":ts if robust else 0,
        "state":"OPERATOR_FAMILY_ROBUST_CONTEXT_ONLY" if robust else ("ABSTAIN_OPERATOR_DEPENDENT" if not top_same or not sign_same else "ABSTAIN_UNRESOLVED_CREDIT"),
        "credit_l1_between_kernels":l1(train,cohort),
    }


def _evaluate_prompt(model, spec: PromptInterventionSpec, *, cohort: str, include_space: bool) -> dict:
    credits={}; forward_calls={}; walls={}
    for kernel in PROTOCOL["admissible_kernels"]:
        assignments=donor_assignments(spec,cohort=cohort,kernel=kernel)
        oracle=FiniteSoftInterventionOracle(model,spec,assignments)
        t=time.perf_counter(); est=exact_ablation_shapley(PLAYERS,oracle); walls[kernel]=time.perf_counter()-t
        credits[kernel]=est.credits; forward_calls[kernel]=oracle.forward_calls
    space=None
    if include_space:
        oracle=SpaceOracle(model,spec); t=time.perf_counter(); est=exact_ablation_shapley(PLAYERS,oracle)
        space={"credits":est.credits,"top":ranked_by_absolute_credit(est.credits)[0],"wall_seconds":time.perf_counter()-t,"forward_calls":oracle.forward_calls}
    return {"credits":credits,"forward_calls":forward_calls,"wall_seconds":walls,"space":space}


def _metrics(rows: list[dict]) -> dict:
    n=len(rows)
    return {
        "n":n,
        "top_agreement_rate":sum(r["score"]["top_same"] for r in rows)/max(n,1),
        "sign_agreement_rate":sum(r["score"]["sign_same"] for r in rows)/max(n,1),
        "robust_authority_count":sum(r["score"]["robust_authority"] for r in rows),
        "robust_authority_coverage":sum(r["score"]["robust_authority"] for r in rows)/max(n,1),
        "robust_recent_count":sum(r["score"]["robust_authority"] and r["score"]["candidate"]=="A_RECENT" for r in rows),
        "robust_nonrecent_count":sum(r["score"]["robust_authority"] and r["score"]["candidate"]!="A_RECENT" for r in rows),
        "median_credit_l1_between_kernels":float(statistics.median(r["score"]["credit_l1_between_kernels"] for r in rows)),
        "legacy_space_agreement_on_robust": (
            sum(r["score"]["robust_authority"] and r["space_top"]==r["score"]["candidate"] for r in rows)
            / max(sum(r["score"]["robust_authority"] for r in rows),1)
        ),
    }


def run_calibration() -> dict:
    model=load_checkpoint(_checkpoint_path("calibration")); before=state_dict_sha256(model)
    rows=[]; min_gaps=[]
    for context in PROTOCOL["contexts"]:
        for idx,spec in enumerate(fresh_specs(context,"calibration")):
            ev=_evaluate_prompt(model,spec,cohort="calibration",include_space=False)
            a=ev["credits"]["K_TRAIN_CONTIG8"]; b=ev["credits"]["K_COHORT_CONTIG8"]
            min_gaps.append(min(top_gap(a),top_gap(b)))
            rows.append({"context":context,"index":idx,"prompt_hash":spec.prompt_hash,"credits":ev["credits"]})
    q10=float(np.quantile(np.asarray(min_gaps,dtype=float),.10,method="linear")); delta=float(min(.25,max(1e-6,.25*q10)))
    after=state_dict_sha256(model)
    payload={"experiment_id":"CSCA-06B-OP","cohort":"CALIBRATION","n":len(rows),"q10_min_gap":q10,"delta":delta,"model_state_mutated":before!=after,"prompt_overlap_with_csca05":sum(r["prompt_hash"] in _old_prompt_hashes() for r in rows)}
    _json(ART/"calibration/rows.json",rows); _json(ART/"calibration/frozen_policy.json",payload)
    return payload


def run_confirmatory(cohort: str) -> dict:
    if cohort not in {"primary","replication"}: raise ValueError(cohort)
    policy=json.loads((ART/"calibration/frozen_policy.json").read_text()); delta=float(policy["delta"])
    model=load_checkpoint(_checkpoint_path(cohort)); before=state_dict_sha256(model)
    rows=[]; start=time.perf_counter(); old=_old_prompt_hashes()
    for context in PROTOCOL["contexts"]:
        for idx,spec in enumerate(fresh_specs(context,cohort)):
            ev=_evaluate_prompt(model,spec,cohort=cohort,include_space=True)
            a=ev["credits"]["K_TRAIN_CONTIG8"]; b=ev["credits"]["K_COHORT_CONTIG8"]
            score=score_pair(a,b,delta=delta)
            rows.append({
                "context":context,"index":idx,"prompt_hash":spec.prompt_hash,"score":score,"credits":ev["credits"],
                "space_top":ev["space"]["top"],"space_credits":ev["space"]["credits"],
                "forward_calls":ev["forward_calls"],"space_forward_calls":ev["space"]["forward_calls"],"wall_seconds":ev["wall_seconds"],
            })
    wall=time.perf_counter()-start; after=state_dict_sha256(model)
    strata={"pooled":_metrics(rows)}
    for c in PROTOCOL["contexts"]: strata[c]=_metrics([r for r in rows if r["context"]==c])
    threshold_checks={}
    passed=True
    for name,m in strata.items():
        checks={
            "top_agreement":m["top_agreement_rate"]>=float(PROTOCOL["min_top_agreement"]),
            "sign_agreement":m["sign_agreement_rate"]>=float(PROTOCOL["min_sign_agreement"]),
            "robust_coverage":m["robust_authority_coverage"]>=float(PROTOCOL["min_robust_coverage"]),
        }
        threshold_checks[name]=checks; passed=passed and all(checks.values())
    overlap=sum(r["prompt_hash"] in old for r in rows); mutation=before!=after
    passed=bool(passed and overlap==0 and not mutation)
    payload={
        "experiment_id":"CSCA-06B-OP","cohort":cohort.upper(),"delta":delta,"metrics":strata,"threshold_checks":threshold_checks,
        "prompt_overlap_with_csca05":overlap,"model_state_mutated":mutation,"wall_seconds":wall,
        "physical_forward_calls":sum(sum(r["forward_calls"].values())+r["space_forward_calls"] for r in rows),
        "cohort_pass":passed,"authority":"DIRECT_INTERVENTION_OPERATOR_FAMILY_ROBUST_SHADOW_MEASUREMENT" if passed else "RESEARCH_ONLY",
        "semantic_causality_authorized":False,"amortized_student_authorized":False,"replay_authorized":False,"active_control":False,
    }
    _json(ART/f"{cohort}/rows.json",rows); _json(ART/f"{cohort}/result.json",payload)
    return payload


def main() -> None:
    import argparse
    ap=argparse.ArgumentParser(); ap.add_argument('phase',choices=['calibration','primary','replication']); args=ap.parse_args()
    if args.phase=='calibration': p=run_calibration()
    else:p=run_confirmatory(args.phase)
    print(json.dumps(p,indent=2,sort_keys=True))

if __name__=='__main__': main()
