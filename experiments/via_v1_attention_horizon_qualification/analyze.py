"""Human-readable renderer for the frozen VIA-V1Q verdict."""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ART = ROOT / "artifacts" / "via-v1-attention-horizon-qualification"


def main() -> int:
    verdict = json.loads((ART / "verdict.json").read_text())
    lines = [
        "# VIA-V1Q — Attention-Horizon Qualification Results",
        "",
        f"**Verdict:** `{verdict['verdict']}`",
        "",
        "This is a controlled mechanism qualification with no scientific ascension authority.",
        "",
        "## Exact controlled surface",
        "",
        "| regime | action | quality | compute proxy |",
        "|---|---|---:|---:|",
    ]
    for regime, actions in verdict["regime_action_means"].items():
        for action, values in actions.items():
            lines.append(
                f"| {regime} | {action} | {values['quality']:.6f} | {values['compute_proxy']:.6f} |"
            )
    lines += [
        "",
        f"Max regime opportunity over exact ranking regions: `{verdict['max_regime_gap']:.12f}`",
        f"Max controller-compute allowance (controlled proxy units): `{verdict['max_controller_compute_allowance']:.12f}`",
        f"Critical lambdas: `{verdict['critical_lambdas']}`",
        "",
        "## Interpretation",
        "",
        "The candidate has the minimal cost-sensitive action-ranking reversal required for adaptive value in the",
        "controlled task. This only qualifies attention horizon for a prospective real-workload VIA-V1 pilot.",
        "VIA-V1 remains scientifically blocked and VIA-V2 remains unauthorized.",
    ]
    (ART / "RESULTS.md").write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
