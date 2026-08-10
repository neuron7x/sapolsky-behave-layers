from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import math
import random
from typing import Mapping, Sequence

import numpy as np

from cwc.counterfactual.model import CANDIDATES, FittedCounterfactualModel, fit_counterfactual_ensemble
from cwc.counterfactual.structural_adequacy import (
    EmpiricalInterventionProbe,
    best_family_audit,
    context_effect_audits,
    graph_structural_sensitivity,
    interventional_divergence_audit,
)

TRAIN_N = 256
EVAL_N = 128
NOISE_SD = 0.15
BOOTSTRAPS_PER_FAMILY = 4
POOL_PER_CELL = 64
REPLICATES_PER_ARM_PER_SPLIT = 4
BUDGETS_PER_CELL = (2, 4, 8, 16, 32)
COVERAGE_FLOOR = 2

CALIBRATION_FAMILIES = (
    "C0_LINEAR",
    "C1_CONTEXT_SIGN",
    "C2_PAIR_INTERACTION",
    "C3_REDUNDANT",
)

CONFIRMATORY_FAMILIES = (
    "M1_SHARED_WRONG_EDGE",
    "M2_MISSING_TRUE_EDGE",
    "M3_SIGN_ERROR",
    "M4_WRONG_COEFFICIENT",
    "M5_LATENT_CONFOUNDER",
    "M6_ZERO_CAUSE",
    "M7_TRIPLE_INTERACTION",
    "M8_CONTEXT_SWITCH",
    "M9_CONTEXT_SIGN_FLIP",
    "M10_COLLINEAR_IDENTIFIABILITY",
)

EXPECTED_STRUCTURAL_ADEQUACY = {
    "C0_LINEAR": True,
    "C1_CONTEXT_SIGN": True,
    "C2_PAIR_INTERACTION": True,
    "C3_REDUNDANT": True,
    "M1_SHARED_WRONG_EDGE": False,
    "M2_MISSING_TRUE_EDGE": False,
    "M3_SIGN_ERROR": False,
    "M4_WRONG_COEFFICIENT": False,
    "M5_LATENT_CONFOUNDER": False,
    "M6_ZERO_CAUSE": False,
    "M7_TRIPLE_INTERACTION": False,
    "M8_CONTEXT_SWITCH": True,
    "M9_CONTEXT_SIGN_FLIP": True,
    "M10_COLLINEAR_IDENTIFIABILITY": False,
}

TRUE_CAUSAL_SETS = {
    "C0_LINEAR": {"A"},
    "C1_CONTEXT_SIGN": {"A"},
    "C2_PAIR_INTERACTION": {"A", "C", "D"},
    "C3_REDUNDANT": {"A", "B"},
    "M1_SHARED_WRONG_EDGE": {"A"},
    "M2_MISSING_TRUE_EDGE": {"A"},
    "M3_SIGN_ERROR": {"A"},
    "M4_WRONG_COEFFICIENT": {"A"},
    "M5_LATENT_CONFOUNDER": {"A"},
    "M6_ZERO_CAUSE": set(),
    "M7_TRIPLE_INTERACTION": {"A", "B", "C"},
    "M8_CONTEXT_SWITCH": {"A", "D"},
    "M9_CONTEXT_SIGN_FLIP": {"A"},
    "M10_COLLINEAR_IDENTIFIABILITY": {"A"},
}

FAULTS = {
    "M1_SHARED_WRONG_EDGE": "SHARED_SPURIOUS_EDGE",
    "M2_MISSING_TRUE_EDGE": "MISSING_TRUE_EDGE",
    "M3_SIGN_ERROR": "SIGN_ERROR",
    "M4_WRONG_COEFFICIENT": "WRONG_COEFFICIENT",
}

CONTEXT_CONDITIONAL_FAMILIES = {"C1_CONTEXT_SIGN", "M8_CONTEXT_SWITCH", "M9_CONTEXT_SIGN_FLIP"}


def stable_seed(*parts: object) -> int:
    digest = hashlib.sha256("|".join(map(str, parts)).encode()).digest()
    return int.from_bytes(digest[:8], "big")


def _binary(rng: random.Random, p: float = 0.5) -> float:
    return 1.0 if rng.random() < p else -1.0


def observed_row(seed: int, family: str, phase: str, index: int) -> dict[str, float]:
    rng = random.Random(stable_seed(seed, family, phase, index, "row"))
    A = _binary(rng)
    U = _binary(rng)
    if family in {"M1_SHARED_WRONG_EDGE", "M10_COLLINEAR_IDENTIFIABILITY"}:
        C = A
    elif family in {"M5_LATENT_CONFOUNDER", "M6_ZERO_CAUSE"}:
        C = U if rng.random() < 0.98 else -U
    else:
        C = _binary(rng)
    B = _binary(rng)
    D = _binary(rng)
    context = _binary(rng)
    return {"A": A, "C": C, "D": D, "B": B, "context": context, "U": U}


def structural_mean(row: Mapping[str, float], family: str) -> float:
    A, C, D, B = (float(row[name]) for name in CANDIDATES)
    ctx = float(row["context"])
    U = float(row.get("U", 0.0))
    if family == "C0_LINEAR":
        return A + 0.15 * ctx
    if family in {"C1_CONTEXT_SIGN", "M9_CONTEXT_SIGN_FLIP"}:
        return ctx * A
    if family == "C2_PAIR_INTERACTION":
        return A * C + 0.25 * D
    if family == "C3_REDUNDANT":
        return A + 0.30 * B
    if family in {"M1_SHARED_WRONG_EDGE", "M2_MISSING_TRUE_EDGE", "M3_SIGN_ERROR", "M4_WRONG_COEFFICIENT", "M10_COLLINEAR_IDENTIFIABILITY"}:
        return A
    if family == "M5_LATENT_CONFOUNDER":
        return A + 1.8 * U
    if family == "M6_ZERO_CAUSE":
        return 1.8 * U
    if family == "M7_TRIPLE_INTERACTION":
        return A * B * C
    if family == "M8_CONTEXT_SWITCH":
        return A if ctx < 0 else D
    raise KeyError(family)


def noisy_outcome(row: Mapping[str, float], family: str, *, seed: int, phase: str, index: int) -> float:
    rng = random.Random(stable_seed(seed, family, phase, index, "y"))
    return structural_mean(row, family) + rng.gauss(0.0, NOISE_SD)


@dataclass(frozen=True, slots=True)
class PreparedCase:
    seed: int
    family: str
    train_rows: tuple[dict[str, float], ...]
    train_y: tuple[float, ...]
    eval_rows: tuple[dict[str, float], ...]
    eval_y: tuple[float, ...]
    models: tuple[FittedCounterfactualModel, ...]
    full_probe_pool: tuple[EmpiricalInterventionProbe, ...]
    expected_adequate: bool
    true_causal_set: tuple[str, ...]
    factual_rmse: float


def _split_effect(seed: int, family: str, candidate: str, context: float, index: int, split: str, true_effect: float) -> float:
    # Each split is a difference of two intervention-arm means divided by 2.
    # Var = sigma^2/(2*r) for r replicates/arm.
    sd = NOISE_SD / math.sqrt(2.0 * REPLICATES_PER_ARM_PER_SPLIT)
    rng = random.Random(stable_seed(seed, family, candidate, context, index, split, "intervention"))
    return true_effect + rng.gauss(0.0, sd)


def _probe_pool(seed: int, family: str) -> tuple[EmpiricalInterventionProbe, ...]:
    probes=[]
    for candidate in CANDIDATES:
        for context in (-1.0, 1.0):
            for index in range(POOL_PER_CELL):
                base=observed_row(seed, family, f"probe-{candidate}-{int(context)}", index)
                base["context"] = context
                plus=dict(base); minus=dict(base)
                plus[candidate]=1.0; minus[candidate]=-1.0
                true_effect=0.5*(structural_mean(plus,family)-structural_mean(minus,family))
                d1=_split_effect(seed,family,candidate,context,index,"a",true_effect)
                d2=_split_effect(seed,family,candidate,context,index,"b",true_effect)
                probes.append(EmpiricalInterventionProbe(candidate,context,base,d1,d2))
    return tuple(probes)


def prepare_case(seed: int, family: str) -> PreparedCase:
    train=tuple(observed_row(seed,family,"train",i) for i in range(TRAIN_N))
    train_y=tuple(noisy_outcome(r,family,seed=seed,phase="train",index=i) for i,r in enumerate(train))
    eval_rows=tuple(observed_row(seed,family,"eval",i) for i in range(EVAL_N))
    eval_y=tuple(noisy_outcome(r,family,seed=seed,phase="eval",index=i) for i,r in enumerate(eval_rows))
    models=fit_counterfactual_ensemble(train,train_y,seed=seed,fault=FAULTS.get(family,"NONE"),bootstraps_per_family=BOOTSTRAPS_PER_FAMILY)
    pred=np.mean(np.asarray([m.predict(eval_rows) for m in models]),axis=0)
    factual_rmse=float(np.sqrt(np.mean((pred-np.asarray(eval_y))**2)))
    return PreparedCase(seed,family,train,train_y,eval_rows,eval_y,models,_probe_pool(seed,family),EXPECTED_STRUCTURAL_ADEQUACY[family],tuple(sorted(TRUE_CAUSAL_SETS[family])),factual_rmse)


def _disagreement(case: PreparedCase, probe: EmpiricalInterventionProbe) -> float:
    vals=[m.intervention_effect(probe.base,probe.candidate) for m in case.models]
    return float(np.std(vals))


def select_probes(case: PreparedCase, budget_per_cell: int, strategy: str) -> tuple[EmpiricalInterventionProbe, ...]:
    if budget_per_cell > POOL_PER_CELL:
        raise ValueError("budget exceeds pool")
    cells={(cand,ctx):[] for cand in CANDIDATES for ctx in (-1.0,1.0)}
    for probe in case.full_probe_pool:
        cells[(probe.candidate,probe.context)].append(probe)
    for key in cells:
        cells[key].sort(key=lambda p: stable_seed(case.seed,case.family,key[0],key[1],p.base["A"],p.base["B"],p.base["C"],p.base["D"],len(cells[key])))

    total=budget_per_cell*len(cells)
    if strategy == "BALANCED":
        return tuple(p for key in sorted(cells) for p in cells[key][:budget_per_cell])
    scored=sorted(case.full_probe_pool,key=lambda p:(-_disagreement(case,p),p.candidate,p.context,stable_seed(case.seed,p.candidate,p.context,p.effect)))
    if strategy == "DISAGREEMENT_ONLY":
        return tuple(scored[:total])
    if strategy == "CREDIT_PRIORITY":
        # Use the model's current highest absolute-credit candidate; intentionally unsafe baseline.
        scores={name:0.0 for name in CANDIDATES}
        for model in case.models:
            abs_credit,_=model.mean_credit(case.eval_rows)
            for name in CANDIDATES:
                scores[name]+=abs_credit[name]/len(case.models)
        top=max(CANDIDATES,key=lambda n:(scores[n],-CANDIDATES.index(n)))
        eligible=[p for p in case.full_probe_pool if p.candidate==top]
        return tuple(eligible[:min(total,len(eligible))])
    if strategy == "COVERAGE_PLUS_DISAGREEMENT":
        floor=min(COVERAGE_FLOOR,budget_per_cell)
        chosen=[]; chosen_ids=set()
        for key in sorted(cells):
            for p in cells[key][:floor]:
                chosen.append(p); chosen_ids.add(id(p))
        for p in scored:
            if len(chosen)>=total:
                break
            if id(p) in chosen_ids:
                continue
            chosen.append(p); chosen_ids.add(id(p))
        return tuple(chosen)
    raise KeyError(strategy)


@dataclass(frozen=True, slots=True)
class CaseAudit:
    seed: int
    family: str
    expected_adequate: bool
    strategy: str
    budget_per_cell: int
    factual_rmse: float
    best_family: str
    best_idr: float
    best_max_cell_idr: float
    all_family_idr: dict[str,float]
    min_cell_support: int
    covered_cells: int
    total_cells: int
    context_conditional: bool
    context_sign_flip_candidates: tuple[str,...]
    gss_top_factual_candidate: str
    gss_top_interventional_candidate: str
    true_causal_set: tuple[str,...]


def audit_case(case: PreparedCase, budget_per_cell: int, strategy: str) -> CaseAudit:
    probes=select_probes(case,budget_per_cell,strategy)
    audits=interventional_divergence_audit(case.models,probes)
    best=best_family_audit(audits)
    supports={}
    for p in probes:
        key=(p.candidate,p.context); supports[key]=supports.get(key,0)+1
    ctx=context_effect_audits(probes)
    flips=tuple(sorted(x.candidate for x in ctx if x.sign_flip and x.standardized_difference>=3.0))
    gss=graph_structural_sensitivity(case.models,case.eval_rows,case.eval_y,probes)
    top_f=max(gss,key=lambda x:(x.factual_delta_mse,-CANDIDATES.index(x.candidate))).candidate
    top_i=max(gss,key=lambda x:(x.intervention_delta_mse,-CANDIDATES.index(x.candidate))).candidate
    return CaseAudit(
        seed=case.seed,family=case.family,expected_adequate=case.expected_adequate,strategy=strategy,budget_per_cell=budget_per_cell,
        factual_rmse=case.factual_rmse,best_family=best.family,best_idr=best.idr,best_max_cell_idr=best.max_cell_idr,
        all_family_idr={x.family:x.max_cell_idr for x in audits},min_cell_support=min(supports.values()) if supports else 0,
        covered_cells=len(supports),total_cells=len(CANDIDATES)*2,context_conditional=case.family in CONTEXT_CONDITIONAL_FAMILIES,
        context_sign_flip_candidates=flips,gss_top_factual_candidate=top_f,gss_top_interventional_candidate=top_i,true_causal_set=case.true_causal_set,
    )


def as_jsonable(obj):
    if hasattr(obj,"__dataclass_fields__"):
        return asdict(obj)
    raise TypeError(type(obj))
