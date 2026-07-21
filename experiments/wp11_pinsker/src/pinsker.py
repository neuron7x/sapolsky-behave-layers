"""WP11 Pinsker small-rate dichotomy — certified over a random sample (de-curated).

The audit flagged the dichotomy (regular V*=Theta(R) exponent ~1; critical V*=Theta(sqrt R)
exponent ~0.5) as 'sketch + curated numerics on ~4 instances'. This certifies it over a RANDOM
sample of regular instances and a constructed family of critical instances -- addressing the
'curated' critique with a proper sample. See PREREGISTRATION.md. Deterministic.
"""
from __future__ import annotations

import statistics
from math import isnan
from typing import Any

from experiments.common.identifiability_inference import _Rng
from experiments.common.value_of_information_rate import is_critical, small_rate_exponent

N_REGULAR = 60
N_CRITICAL = 60
PRIOR = [0.5, 0.5]
REG_BAND = (0.85, 1.15)     # regular exponent ~1
CRIT_BAND = (0.40, 0.65)    # critical exponent ~0.5
REG_FRAC_FLOOR = 0.80
CRIT_FRAC_FLOOR = 0.90


def _regular_exponents() -> list[float]:
    rng = _Rng(11)
    out: list[float] = []
    tries = 0
    while len(out) < N_REGULAR and tries < 20 * N_REGULAR:
        tries += 1
        n_a = 2 + (tries % 2)                       # 2 or 3 actions
        u = [[rng.gauss() for _ in range(n_a)] for _ in range(2)]
        if is_critical(u, PRIOR):                   # generic random is regular; skip ties
            continue
        e = small_rate_exponent(u, PRIOR)
        if not isnan(e):
            out.append(e)
    return out


def _critical_exponents() -> list[float]:
    rng = _Rng(4242)
    out: list[float] = []
    tries = 0
    while len(out) < N_CRITICAL and tries < 20 * N_CRITICAL:
        tries += 1
        x, y = rng.gauss(), rng.gauss()
        u = [[x, y], [y, x]]                         # symmetric -> tied columns -> critical
        if is_critical(u, PRIOR):
            e = small_rate_exponent(u, PRIOR)
            if not isnan(e):
                out.append(e)
    return out


def analyze() -> dict[str, Any]:
    reg = _regular_exponents()
    cri = _critical_exponents()

    def _stats(xs, band):
        frac = sum(1 for e in xs if band[0] <= e <= band[1]) / len(xs) if xs else 0.0
        return {"n": len(xs), "mean": statistics.mean(xs), "sd": statistics.pstdev(xs),
                "frac_in_band": frac, "band": list(band)}

    rs, cs = _stats(reg, REG_BAND), _stats(cri, CRIT_BAND)
    reg_ok = REG_BAND[0] <= rs["mean"] <= REG_BAND[1] and rs["frac_in_band"] >= REG_FRAC_FLOOR
    crit_ok = CRIT_BAND[0] <= cs["mean"] <= CRIT_BAND[1] and cs["frac_in_band"] >= CRIT_FRAC_FLOOR
    verdict = "PINSKER_DICHOTOMY_CERTIFIED" if (reg_ok and crit_ok) else "PINSKER_DICHOTOMY_NOT_CERTIFIED"

    return {
        "experiment": "wp11_pinsker",
        "verdict": verdict,
        "tier": "META — Pinsker small-rate dichotomy certified over a random sample (de-curated)",
        "regular": rs, "critical": cs,
        "regular_regime_ok": reg_ok, "critical_regime_ok": crit_ok,
        "note": "Regular random instances -> exponent ~1 (Theta(R)); constructed critical -> ~0.5 "
                "(Theta(sqrt R)). Addresses the 'curated numerics' critique with a random sample. "
                "Analytic note: for regular problems beta(0+)=sigma<inf follows from concavity + a "
                "strictly positive prior-optimal gap; the finiteness on the measure-zero critical "
                "manifold is where the sqrt law takes over. Still a numerical certification, not a "
                "closed proof of the general dichotomy.",
        "prohibited_extrapolations": ["a closed proof of the general dichotomy", "independent replication"],
    }


def main() -> None:
    r = analyze()
    from pathlib import Path
    out = Path(__file__).resolve().parents[3] / "artifacts/wp11-pinsker"
    out.mkdir(parents=True, exist_ok=True)
    import json
    (out / "verdict.json").write_text(json.dumps(r, indent=2))
    print(f"WP11 PINSKER VERDICT: {r['verdict']}")
    print(f"  regular : n={r['regular']['n']}  exp mean={r['regular']['mean']:.3f} sd={r['regular']['sd']:.3f}  "
          f"in-band={r['regular']['frac_in_band']:.2f}  (predict ~1)")
    print(f"  critical: n={r['critical']['n']}  exp mean={r['critical']['mean']:.3f} sd={r['critical']['sd']:.3f}  "
          f"in-band={r['critical']['frac_in_band']:.2f}  (predict ~0.5)")


if __name__ == "__main__":
    main()
