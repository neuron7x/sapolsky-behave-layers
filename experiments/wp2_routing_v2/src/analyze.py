"""§9 + §12 gates and verdict. Reads oracle-gap and final raw runs, emits
verdict.json with exactly one of the allowed values."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.wp2_routing_v1.src.analyze import _bootstrap_ci, _mean


def _load(d: Path):
    return [json.loads(f.read_text()) for f in sorted(d.glob("seed*.json"))]


def analyze_oracle(oracle_dir: Path) -> dict:
    runs = _load(oracle_dir / "raw_runs")
    if not runs:
        return {"present": False}
    # per-seed oracle vs best-fixed (min CE over DIRECT_ONLY, RANDOM, FROZEN)
    gains, hard_gaps = [], []
    for r in runs:
        m = r["modes"]
        best_fixed_ce = min(m["DIRECT_ONLY"]["canonical_ce"], m["RANDOM"]["canonical_ce"], m["FROZEN"]["canonical_ce"])
        oce = m["ORACLE"]["canonical_ce"]
        gains.append((best_fixed_ce - oce) / best_fixed_ce if best_fixed_ce > 0 else 0.0)
        best_fixed_hard = max(m["DIRECT_ONLY"]["hard_exact"], m["RANDOM"]["hard_exact"], m["FROZEN"]["hard_exact"])
        hard_gaps.append(m["ORACLE"]["hard_exact"] - best_fixed_hard)
    g_lo, g_hi = _bootstrap_ci(gains)
    iso = {k: _mean([r["isolation"][k] for r in runs]) for k in runs[0]["isolation"]}
    oracle_hard = _mean([r["modes"]["ORACLE"]["hard_exact"] for r in runs])
    oracle_easy = _mean([r["modes"]["ORACLE"]["easy_exact"] for r in runs])
    viol = sum(r["modes"]["ORACLE"]["budget_violations"] for r in runs)
    identifiable = bool(
        g_lo is not None and g_lo > 0 and _mean(gains) >= 0.10 and _mean(hard_gaps) >= 0.10
        and viol == 0 and oracle_easy >= 0.95 and oracle_hard >= 0.999
    )
    isolation_pass = bool(
        iso["parser_subject"] >= 0.99 and iso["parser_relation"] >= 0.99 and iso["parser_object"] >= 0.99
        and iso["parser_polarity"] >= 0.99 and iso["parser_tuple"] >= 0.97 and iso["renderer_exact"] >= 0.99
        and iso["direct_easy_exact"] >= 0.99 and iso["direct_hard_exact"] <= 0.70
    )
    return {"present": True, "mean_oracle_gain": _mean(gains), "gain_ci95": [g_lo, g_hi],
            "mean_hard_gap": _mean(hard_gaps), "oracle_hard_exact": oracle_hard,
            "oracle_easy_exact": oracle_easy, "oracle_budget_violations": viol,
            "isolation": iso, "IDENTIFIABLE": identifiable, "ISOLATION_PASS": isolation_pass}


def analyze_final(final_dir: Path) -> dict:
    runs = _load(final_dir / "raw_runs")
    if not runs:
        return {"present": False}
    c = [r["causality"] for r in runs]

    def col(k):
        return [x[k] for x in c]

    bal = col("route_balanced_acc")
    nmi = col("route_nmi")
    auroc = col("route_auroc")
    cre = col("cre")
    sl = col("shuffling_loss_ratio")
    d_lr = [x["learned_loss"] - x["random_loss"] for x in c]
    d_lf = [x["learned_loss"] - x["shuffled_loss"] for x in c]
    nmi_lo, _ = _bootstrap_ci(nmi)
    cre_lo, _ = _bootstrap_ci([x - 1.0 for x in cre])   # CRE-1 > 0
    sl_lo, _ = _bootstrap_ci([x - 1.0 for x in sl])
    lr_lo, lr_hi = _bootstrap_ci(d_lr)
    lf_lo, lf_hi = _bootstrap_ci(d_lf)
    viol = sum(x["budget_violation"] for x in c)
    supported = bool(
        _mean(bal) >= 0.85 and _mean(auroc) >= 0.90 and nmi_lo is not None and nmi_lo >= 0.25
        and cre_lo is not None and cre_lo > 0 and sl_lo is not None and sl_lo > 0
        and lr_hi is not None and lr_hi < 0 and lf_hi is not None and lf_hi < 0 and viol == 0
    )
    # lesions (mean over seeds)
    les_keys = [k for k in runs[0]["lesions"] if not k.startswith("_")]
    lesions = {k: {mk: _mean([r["lesions"][k][mk] for r in runs]) for mk in runs[0]["lesions"][k]} for k in les_keys}
    intact = _mean([r["lesions"]["_intact_exact"] for r in runs])
    return {"present": True, "n_seeds": len(runs),
            "route_balanced_acc": _mean(bal), "route_nmi": _mean(nmi), "nmi_ci_lo": nmi_lo,
            "route_auroc": _mean(auroc), "cre": _mean(cre), "cre_minus1_ci_lo": cre_lo,
            "shuffling_loss_ratio": _mean(sl), "sl_minus1_ci_lo": sl_lo,
            "learned_minus_random_ci": [lr_lo, lr_hi], "learned_minus_shuffled_ci": [lf_lo, lf_hi],
            "budget_violations": viol, "intact_exact": intact, "lesions": lesions,
            "ROUTING_CAUSALITY_SUPPORTED": supported}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--oracle", type=Path, default=Path("artifacts/wp2-routing-v2/oracle-gap"))
    ap.add_argument("--final", type=Path, default=Path("artifacts/wp2-routing-v2/final"))
    ap.add_argument("--out", type=Path, default=Path("artifacts/wp2-routing-v2"))
    args = ap.parse_args()
    orc = analyze_oracle(args.oracle)
    fin = analyze_final(args.final)
    (args.oracle).mkdir(parents=True, exist_ok=True)
    (args.oracle / "analysis.json").write_text(json.dumps(orc, indent=2))
    if not orc.get("present") or not orc["IDENTIFIABLE"]:
        verdict = "BENCHMARK_NOT_IDENTIFIABLE"
    elif not fin.get("present"):
        verdict = "BENCHMARK_NOT_IDENTIFIABLE"  # oracle passed but no final run yet
    elif fin["budget_violations"] > 0:
        verdict = "COMPUTE_MISMATCH"
    elif fin["ROUTING_CAUSALITY_SUPPORTED"]:
        verdict = "ROUTING_CAUSALITY_SUPPORTED"
    else:
        verdict = "ROUTING_CAUSALITY_NOT_SUPPORTED"
    verdict_obj = {"verdict": verdict, "oracle_identifiable": orc.get("IDENTIFIABLE"),
                   "isolation_pass": orc.get("ISOLATION_PASS")}
    (args.oracle / "verdict.json").write_text(json.dumps(verdict_obj, indent=2))
    if fin.get("present"):
        args.final.mkdir(parents=True, exist_ok=True)
        (args.final / "analysis.json").write_text(json.dumps(fin, indent=2))
        (args.final / "verdict.json").write_text(json.dumps({"verdict": verdict}, indent=2))
    print("ORACLE identifiable:", orc.get("IDENTIFIABLE"), "isolation:", orc.get("ISOLATION_PASS"))
    if fin.get("present"):
        print(f"FINAL causality: {fin['ROUTING_CAUSALITY_SUPPORTED']} "
              f"bal={fin['route_balanced_acc']:.3f} nmi={fin['route_nmi']:.3f} "
              f"auroc={fin['route_auroc']:.3f} cre={fin['cre']:.0f} sl={fin['shuffling_loss_ratio']:.1f}")
    print("VERDICT:", verdict)


if __name__ == "__main__":
    main()
