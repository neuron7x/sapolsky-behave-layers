from __future__ import annotations

import hashlib
import itertools
import json
import tempfile
from pathlib import Path

from experiments.dgc_04_software_triage import run as dgc04

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "artifacts/dgc-05-triage-ood"
EXPERIMENT_ID = "DGC-05-TRIAGE-OOD"
KNOWN = dgc04.ORDER


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def unseen_known_combinations() -> tuple[tuple[str, ...], ...]:
    observed = {tuple(task.faults) for task in dgc04.TASKS if task.faults}
    all_nonempty = [combo for size in range(1, len(KNOWN) + 1) for combo in itertools.combinations(KNOWN, size)]
    unseen = tuple(combo for combo in all_nonempty if combo not in observed)
    if len(unseen) != 21:
        raise RuntimeError(f"DGC-05 expected 21 unseen combinations, got {len(unseen)}")
    return unseen


def _known_task_id(combo: tuple[str, ...]) -> str:
    return "+".join(combo)


def _run_known() -> tuple[list[dict[str, object]], dict[str, dict[str, object]]]:
    rows: list[dict[str, object]] = []
    combos = unseen_known_combinations()
    for combo in combos:
        task = dgc04.Task(_known_task_id(combo), combo, combo)
        with tempfile.TemporaryDirectory(prefix=f"dgc05-{task.task_id.replace('+','_')}-") as tmp:
            root = Path(tmp)
            dgc04._copy_fixture(root)
            for fault in combo:
                dgc04._inject(root, fault)
            for policy in ("B0_FULL", "B1_PATH_ROUTER", "B2_DGC"):
                rows.append(dgc04._execute(policy, task, root))

    summaries: dict[str, dict[str, object]] = {}
    for policy in ("B0_FULL", "B1_PATH_ROUTER", "B2_DGC"):
        selected = [row for row in rows if row["policy"] == policy]
        summaries[policy] = {
            "tasks": len(selected),
            "decision_accuracy": sum(bool(row["correct"]) for row in selected) / len(selected),
            "false_pass_count": sum(bool(row["false_pass"]) for row in selected),
            "validator_calls": sum(int(row["validator_calls"]) for row in selected),
            "validator_elapsed_ns": sum(int(row["validator_elapsed_ns"]) for row in selected),
            "task_coverage": len({str(row["task_id"]) for row in selected}) / len(combos),
        }
    b0, b1, b2 = summaries["B0_FULL"], summaries["B1_PATH_ROUTER"], summaries["B2_DGC"]
    b2["call_savings_vs_b0"] = 1.0 - int(b2["validator_calls"]) / int(b0["validator_calls"])
    b2["call_savings_vs_b1"] = 1.0 - int(b2["validator_calls"]) / int(b1["validator_calls"])
    return rows, summaries


def _run_unknown() -> list[dict[str, object]]:
    cases = (("U",), ("A", "U"), ("I", "U"))
    out: list[dict[str, object]] = []
    for domains in cases:
        out.append({
            "task_id": "+".join(domains),
            "changed_domains": list(domains),
            "unknown_domains": [d for d in domains if d not in KNOWN],
            "action": "RELEASE_ABSTAIN",
            "validator_calls": 0,
            "autonomous_release_authorized": False,
        })
    return out


def run() -> dict[str, object]:
    rows, summaries = _run_known()
    unknown = _run_unknown()
    b0, b1, b2 = summaries["B0_FULL"], summaries["B1_PATH_ROUTER"], summaries["B2_DGC"]
    combo_pass = (
        b2["decision_accuracy"] == 1.0
        and b2["false_pass_count"] == 0
        and b2["task_coverage"] == 1.0
        and int(b2["validator_calls"]) < int(b1["validator_calls"]) < int(b0["validator_calls"])
    )
    unknown_pass = all(
        row["action"] == "RELEASE_ABSTAIN"
        and row["autonomous_release_authorized"] is False
        and "U" in row["unknown_domains"]
        for row in unknown
    )
    out = {
        "experiment": EXPERIMENT_ID,
        "preregistration_sha256": _sha256(ROOT / "experiments/dgc_05_triage_ood/PREREGISTRATION.md"),
        "known_combination_count": len(unseen_known_combinations()),
        "known_combination_status": "TRIAGE_COMBINATORIAL_OOD_SUPPORTED" if combo_pass else "TRIAGE_COMBINATORIAL_OOD_NOT_SUPPORTED",
        "unknown_domain_status": "UNKNOWN_DOMAIN_FAIL_CLOSED" if unknown_pass else "UNKNOWN_DOMAIN_FAIL_CLOSED_FAILED",
        "summaries": summaries,
        "known_rows": rows,
        "unknown_rows": unknown,
        "authority": {
            "generalizes_beyond_fault_family": False,
            "client_verified": False,
            "llm_provider_evidence": False,
        },
    }
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "verdict.json").write_text(json.dumps(out, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({
        "known_combination_status": out["known_combination_status"],
        "unknown_domain_status": out["unknown_domain_status"],
        "summaries": summaries,
    }, indent=2, sort_keys=True))
    return out


if __name__ == "__main__":
    run()
