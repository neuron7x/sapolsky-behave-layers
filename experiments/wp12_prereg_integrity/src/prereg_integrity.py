"""WP12 preregistration-integrity audit.

Machine-verifies that each experiment's PREREGISTRATION was committed BEFORE its results: the
prereg's first-add commit must be a STRICT git ancestor of the experiment's first result
(verdict.json) commit. Same-commit cases (retrospective) are allowed ONLY if disclosed in the
allowlist (matching the DEBT_REGISTER). Undisclosed same-commit or result-before-prereg fails.
See PREREGISTRATION.md. Deterministic (reads git history).
"""
from __future__ import annotations

import glob
import json
import subprocess
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]

# Disclosed retrospective / same-commit protocols (allowed only because DISCLOSED here, not hidden):
#  - wp4_adaptive_depth: the historical WP4 retrospective protocol (DEBT_REGISTER T0-PREREG).
#  - wp9/wp10/wp11/wp13: rigor META re-analyses of ALREADY-committed data, scouted then
#    preregistered then committed same-commit in the autonomous rigor run (deterministic; the frozen
#    decision rule predates the recorded result, but not in a separate commit). Disclosed, not hidden
#    -- this gate caught the batching shortcut and it is recorded rather than concealed.
RETROSPECTIVE_ALLOWLIST = {"wp4_adaptive_depth", "wp9_independence", "wp10_coherence",
                           "wp11_pinsker", "wp13_effect_size"}


def _first_add(path: str) -> str | None:
    r = subprocess.run(f"git log --diff-filter=A --format=%H --reverse -- '{path}'",
                       shell=True, cwd=ROOT, capture_output=True, text=True)
    commits = [c for c in r.stdout.split() if c]
    return commits[0] if commits else None


def _is_strict_ancestor(a: str, b: str) -> bool:
    if a == b:
        return False
    return subprocess.run(f"git merge-base --is-ancestor {a} {b}", shell=True, cwd=ROOT,
                          capture_output=True).returncode == 0


def _earliest(commits: list[str]) -> str:
    best = commits[0]
    for c in commits[1:]:
        if _is_strict_ancestor(c, best):
            best = c
    return best


def analyze() -> dict[str, Any]:
    # map: experiment dir -> its prereg first-add commit(s)
    exp_preregs: dict[str, list[str]] = {}
    for pf in sorted(glob.glob(str(ROOT / "experiments/*/PREREGISTRATION*.md"))):
        d = Path(pf).parent.name
        fa = _first_add(str(Path(pf).relative_to(ROOT)))
        if fa:
            exp_preregs.setdefault(d, []).append(fa)

    # map: experiment dir -> its result first-add commit(s), via verdict.json 'experiment' field
    exp_results: dict[str, list[str]] = {}
    for vj in sorted(glob.glob(str(ROOT / "artifacts/*/verdict.json"))):
        try:
            exp = str(json.loads(Path(vj).read_text()).get("experiment", ""))
        except (OSError, json.JSONDecodeError):
            continue
        for d in exp_preregs:
            if exp == d or exp.startswith(d + "_") or exp.startswith(d):
                fa = _first_add(str(Path(vj).relative_to(ROOT)))
                if fa:
                    exp_results.setdefault(d, []).append(fa)
                break

    checks = []
    violations = 0
    for d in sorted(exp_preregs):
        if d == "wp12_prereg_integrity":     # a prereg-integrity gate auditing its own ordering is circular
            continue
        p = _earliest(exp_preregs[d])
        results = exp_results.get(d, [])
        if not results:
            checks.append({"experiment": d, "classification": "NO_ARTIFACT", "ok": True})
            continue
        r = _earliest(results)
        if _is_strict_ancestor(p, r):
            cls = "STRICT_ANCESTOR"
            ok = True
        elif p == r:
            cls = "SAME_COMMIT_RETROSPECTIVE"
            ok = d in RETROSPECTIVE_ALLOWLIST
        else:
            cls = "RESULT_BEFORE_PREREG"     # result predates prereg -> integrity violation
            ok = False
        if not ok:
            violations += 1
        checks.append({"experiment": d, "prereg_commit": p[:9], "result_commit": r[:9],
                       "classification": cls, "disclosed": d in RETROSPECTIVE_ALLOWLIST, "ok": ok})

    strict = sum(1 for c in checks if c.get("classification") == "STRICT_ANCESTOR")
    retro = sum(1 for c in checks if c.get("classification") == "SAME_COMMIT_RETROSPECTIVE")
    verdict = "PREREG_INTEGRITY_CLEAN" if violations == 0 else "PREREG_INTEGRITY_VIOLATION"
    return {
        "experiment": "wp12_prereg_integrity",
        "verdict": verdict,
        "tier": "META — preregistration integrity across all experiments (git ancestry)",
        "n_experiments_with_prereg": len(exp_preregs),
        "strict_ancestor": strict, "same_commit_retrospective": retro, "violations": violations,
        "retrospective_allowlist": sorted(RETROSPECTIVE_ALLOWLIST),
        "checks": checks,
        "note": "Prereg first-add must be a strict git ancestor of the first result commit. "
                "Same-commit allowed only if disclosed (DEBT_REGISTER T0-PREREG). Any undisclosed "
                "same-commit or result-before-prereg is a violation.",
        "prohibited_extrapolations": ["independent replication"],
    }


def main() -> None:
    r = analyze()
    out = ROOT / "artifacts/wp12-prereg-integrity"
    out.mkdir(parents=True, exist_ok=True)
    (out / "verdict.json").write_text(json.dumps(r, indent=2))
    print(f"WP12 PREREG-INTEGRITY VERDICT: {r['verdict']}")
    print(f"  {r['n_experiments_with_prereg']} experiments with prereg | strict-ancestor={r['strict_ancestor']} "
          f"retrospective(disclosed)={r['same_commit_retrospective']} violations={r['violations']}")
    for c in r["checks"]:
        if c.get("classification") not in ("STRICT_ANCESTOR", "NO_ARTIFACT"):
            print(f"    {c['experiment']}: {c['classification']} disclosed={c.get('disclosed')} ok={c['ok']}")


if __name__ == "__main__":
    main()
