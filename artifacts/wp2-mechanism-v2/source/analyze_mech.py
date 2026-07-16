"""A2/A3 analysis + gates. Reads raw_runs/<stage>/<config>/seed*.json and emits
the oracle-gap gate (A2) and the routing-causality gate (A3) per stage.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.wp2_routing_v1.src.analyze import _bootstrap_ci, _mean

CONFIGS = ["dense", "random", "frozen", "fixed", "oracle", "learned"]
STAGES = ["A_marker", "B_inferred"]


def _load(runs: Path, stage: str):
    out = {}
    for c in CONFIGS:
        d = runs / stage / c
        out[c] = sorted((json.loads(f.read_text()) for f in d.glob("seed*.json")),
                        key=lambda r: r["seed"]) if d.exists() else []
    return out


def analyze_stage(runs: Path, stage: str) -> dict:
    data = _load(runs, stage)

    def ces(c):
        return [r["eval"]["answer_ce"] for r in data[c]]

    def accs(c):
        return [r["eval"]["acc"] for r in data[c]]

    per = {c: {"n": len(data[c]), "mean_ce": _mean(ces(c)), "mean_acc": _mean(accs(c)),
               "mean_acc_local": _mean([r["eval"]["acc_local"] for r in data[c]]),
               "mean_acc_far": _mean([r["eval"]["acc_far"] for r in data[c]])}
           for c in CONFIGS}

    # ---- A2 oracle-gap gate (loss-based), per seed: best-fixed = min(fixed, best static) ----
    # fixed here = always E_A; the true best-fixed is min over {E_A-only, E_B-only}.
    # E_B-only is captured by frozen's collapse OR we approximate best-fixed by the
    # better of fixed(E_A) and frozen(E_B-collapsed). Use the explicit fixed run and
    # the frozen run (which collapses to one block) as the two fixed candidates.
    oracle_ce = {r["seed"]: r["eval"]["answer_ce"] for r in data["oracle"]}
    fixedA_ce = {r["seed"]: r["eval"]["answer_ce"] for r in data["fixed"]}
    frozen_ce = {r["seed"]: r["eval"]["answer_ce"] for r in data["frozen"]}
    seeds = sorted(set(oracle_ce) & set(fixedA_ce) & set(frozen_ce))
    gains = []
    for s in seeds:
        best_fixed = min(fixedA_ce[s], frozen_ce[s])
        gains.append((best_fixed - oracle_ce[s]) / best_fixed if best_fixed > 0 else 0.0)
    g_lo, g_hi = _bootstrap_ci(gains) if gains else (None, None)
    oracle_acc = per["oracle"]["mean_acc"]
    best_fixed_acc = max(per["fixed"]["mean_acc"], per["frozen"]["mean_acc"])
    a2_pass = bool(gains and _mean(gains) >= 0.10 and g_lo is not None and g_lo > 0.05
                   and per["oracle"]["mean_acc_local"] > 0.9 and per["oracle"]["mean_acc_far"] > 0.9)

    # ---- A3 routing-causality (learned vs random/frozen/fixed) ----
    def paired(a, b):
        ra = {r["seed"]: r["eval"]["answer_ce"] for r in data[a]}
        rb = {r["seed"]: r["eval"]["answer_ce"] for r in data[b]}
        ss = sorted(set(ra) & set(rb))
        d = [ra[s] - rb[s] for s in ss]
        lo, hi = _bootstrap_ci(d) if d else (None, None)
        return {"mean_delta": _mean(d), "ci95": [lo, hi], "learned_better": hi is not None and hi < 0,
                "n": len(d)}

    comps = {f"learned_vs_{c}": paired("learned", c) for c in ["random", "frozen", "fixed", "oracle"]}
    inorm = [r["eval"].get("mi_i_norm", 0.0) for r in data["learned"]]
    inorm_lo, inorm_hi = _bootstrap_ci(inorm) if inorm else (None, None)
    perm_ps = [r.get("permutation_p", 1.0) for r in data["learned"]]
    agree = [r["eval"].get("route_label_agreement", 0.0) for r in data["learned"]]

    # interventions (mean over learned seeds)
    iv = [r["interventions"] for r in data["learned"] if "interventions" in r]
    iv_mean = {k: _mean([x[k] for x in iv]) for k in iv[0]} if iv else {}

    beats = all(comps[f"learned_vs_{c}"]["learned_better"] for c in ["random", "frozen", "fixed"])
    mi_ok = _mean(inorm) >= 0.25 and inorm_lo is not None and inorm_lo >= 0.15 and max(perm_ps) <= 0.01
    # intervention checks: force-incorrect >> force-correct; permute destroys advantage
    iv_ok = bool(iv_mean and iv_mean.get("incorrect_over_correct_ratio", 0) >= 1.5)
    n = per["learned"]["n"]
    if n == 0:
        a3 = "NOT_TESTED"
    elif beats and mi_ok and iv_ok and n >= 8:
        a3 = "ROUTING_CAUSALITY_SUPPORTED"
    elif beats and mi_ok:
        a3 = "SUPPORTED_WEAK" + ("" if n >= 8 else "_PILOT")
    else:
        a3 = "NOT_SUPPORTED"

    return {"stage": stage, "per_config": per,
            "A2_oracle_gap": {"mean_relative_gain": _mean(gains), "ci95": [g_lo, g_hi],
                              "oracle_acc": oracle_acc, "best_fixed_acc": best_fixed_acc,
                              "acc_gap_pp": (oracle_acc - best_fixed_acc) * 100 if oracle_acc and best_fixed_acc else None,
                              "PASS": a2_pass},
            "A3_routing_causality": {"comparisons": comps,
                                     "mean_i_norm": _mean(inorm), "i_norm_ci95": [inorm_lo, inorm_hi],
                                     "max_permutation_p": max(perm_ps) if perm_ps else None,
                                     "mean_route_label_agreement": _mean(agree),
                                     "interventions_mean": iv_mean,
                                     "beats_all_static": beats, "mi_gate": mi_ok, "intervention_gate": iv_ok,
                                     "n_seeds": n, "VERDICT": a3}}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=Path, default=Path("artifacts/wp2-mechanism-v2/raw_runs"))
    ap.add_argument("--out", type=Path, default=Path("artifacts/wp2-mechanism-v2/statistics"))
    args = ap.parse_args()
    res = {s: analyze_stage(args.runs, s) for s in STAGES}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "analysis.json").write_text(json.dumps(res, indent=2))
    for s in STAGES:
        r = res[s]
        print(f"=== {s} ===")
        print(f"  A2 oracle-gap: gain={r['A2_oracle_gap']['mean_relative_gain']:.3f} "
              f"ci={r['A2_oracle_gap']['ci95']} acc_gap_pp={r['A2_oracle_gap']['acc_gap_pp']} PASS={r['A2_oracle_gap']['PASS']}")
        a3 = r["A3_routing_causality"]
        print(f"  A3 verdict: {a3['VERDICT']}  beats_static={a3['beats_all_static']} "
              f"i_norm={a3['mean_i_norm']:.3f} route~T={a3['mean_route_label_agreement']:.3f} "
              f"max_perm_p={a3['max_permutation_p']}")
        for c in CONFIGS:
            p = r["per_config"][c]
            print(f"    {c:8s} n={p['n']} ce={p['mean_ce']:.3f} acc={p['mean_acc']:.3f} (L={p['mean_acc_local']:.2f} F={p['mean_acc_far']:.2f})")


if __name__ == "__main__":
    main()
