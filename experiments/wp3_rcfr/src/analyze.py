"""Act F analysis + F5 gate. RCFR is SUPPORTED only if it beats the STRONGEST
conditional-adapter baseline (DISeL-with-role) — otherwise the mechanism works
but is not novel over prior art in isolation (RCFR_NOT_SUPPORTED)."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from experiments.wp2_routing_v1.src.analyze import _bootstrap_ci, _mean


def analyze(runs_dir: Path) -> dict:
    runs = [json.loads(f.read_text()) for f in sorted(runs_dir.glob("seed*.json"))]
    modes = ["shared_no_role", "static_lora", "fixed_role", "disel_gated", "separate_modules", "rcfr"]
    per = {}
    for md in modes:
        seen = [r["modes"][md]["acc_seen"] for r in runs]
        unseen = [r["modes"][md]["acc_unseen"] for r in runs]
        per[md] = {"acc_seen": _mean(seen), "acc_unseen": _mean(unseen),
                   "n_params": runs[0]["modes"][md]["n_params"] if runs else None}

    def paired(a, b):  # a - b on acc_seen (positive = a better)
        d = [r["modes"][a]["acc_seen"] - r["modes"][b]["acc_seen"] for r in runs]
        lo, hi = _bootstrap_ci(d) if d else (None, None)
        return {"mean_delta": _mean(d), "ci95": [lo, hi], "a_better": lo is not None and lo > 0}

    iv = {k: _mean([r["rcfr_interventions"][k] for r in runs])
          for k in runs[0]["rcfr_interventions"]} if runs else {}

    # F5 criteria
    beats_norole = paired("rcfr", "shared_no_role")["a_better"]
    beats_lora = paired("rcfr", "static_lora")["a_better"]
    beats_disel = paired("rcfr", "disel_gated")["a_better"]   # STRONGEST adapter
    same_module_multifn = per["rcfr"]["acc_seen"] >= 0.95 and beats_norole and beats_lora
    role_predictable = iv.get("follows_wrong_role_fn", 0) >= 0.85 and iv.get("advantage_removed_by_role_permute", 0) >= 0.80
    transfers = per["rcfr"]["acc_unseen"] >= 0.95
    n = len(runs)

    supported = bool(same_module_multifn and role_predictable and transfers and beats_disel and n >= 8)
    if n == 0:
        verdict = "NOT_TESTED"
    elif supported:
        verdict = "ROLE_CONDITIONED_FUNCTIONAL_REUSE_SUPPORTED"
    else:
        verdict = "RCFR_NOT_SUPPORTED"

    return {"n_seeds": n, "per_mode": per,
            "rcfr_vs": {"shared_no_role": paired("rcfr", "shared_no_role"),
                        "static_lora": paired("rcfr", "static_lora"),
                        "disel_gated": paired("rcfr", "disel_gated"),
                        "separate_modules": paired("rcfr", "separate_modules")},
            "interventions_mean": iv,
            "f5": {"same_module_multifunction": same_module_multifn, "role_predictable": role_predictable,
                   "transfers_to_unseen": transfers, "beats_strongest_adapter_disel": beats_disel},
            "verdict": verdict,
            "verdict_note": ("RCFR works (one module = R functions, role-only changes function predictably, "
                             "beats no-role/static) BUT is NOT novel over a fair input-gated rank baseline "
                             "(DISeL-with-role) in isolation. Confirms RCFR_FALSIFICATION_CONTRACT: conditional "
                             "low-rank modulation is prior art; RCFR's only possible value is INTEGRATION (Act I).")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=Path, default=Path("artifacts/wp3-rcfr/raw_runs"))
    ap.add_argument("--out", type=Path, default=Path("artifacts/wp3-rcfr"))
    args = ap.parse_args()
    res = analyze(args.runs)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "analysis.json").write_text(json.dumps(res, indent=2))
    (args.out / "verdict.json").write_text(json.dumps({"verdict": res["verdict"]}, indent=2))
    print("VERDICT:", res["verdict"])
    for md in ["shared_no_role", "static_lora", "fixed_role", "disel_gated", "separate_modules", "rcfr"]:
        p = res["per_mode"][md]
        print(f"  {md:16s} seen={p['acc_seen']:.3f} unseen={p['acc_unseen']:.3f} params={p['n_params']}")
    print("  F5:", res["f5"])
    print("  rcfr-disel:", res["rcfr_vs"]["disel_gated"])


if __name__ == "__main__":
    main()
