"""Generate docs/vnv/DOCUMENT_STATUS_REGISTER.csv (Act CWC-LAB-DOC-2026-01 §15) from
REAL file existence. States: EXISTS / MISSING / TRIGGER_NOT_REACHED / N_A. Never
hand-maintained -> never drifts. Run:
  PYTHONPATH=. .venv/bin/python scripts/build_document_register.py
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/vnv/DOCUMENT_STATUS_REGISTER.csv"

# (id, priority, path, note). Priority P2 risk docs are TRIGGER_NOT_REACHED by design.
DOCS = [
    ("DOC-001", "P0", "README.md", ""),
    ("DOC-002", "P0", "SYSTEM.md", ""),
    ("DOC-003", "P0", "docs/methodology/CWC_MASTER_METHODOLOGY.md", ""),
    ("DOC-004", "P0", "docs/methodology/HYPOTHESIS_REGISTRY.yaml", ""),
    ("DOC-005", "P0", "claim_registry.json", ""),
    ("DOC-006", "P0", "docs/methodology/EXPERIMENT_PROTOCOL_TEMPLATE.md", ""),
    ("DOC-007", "P0", "experiments/wp2_routing_v2/PREREGISTRATION.md", "per-experiment preregs"),
    ("DOC-008", "P0", "docs/methodology/PROTOCOL_AMENDMENT_AND_DEVIATION_POLICY.md", ""),
    ("DOC-009", "P0", "docs/methodology/STATISTICAL_ANALYSIS_PLAN.md", ""),
    ("DOC-010", "P0", "docs/methodology/POWER_AND_SAMPLE_SIZE_PLAN.md", ""),
    ("DOC-011", "P0", "docs/lab/EXPERIMENT_LEDGER.jsonl", ""),
    ("DOC-012", "P1", "docs/lab/LAB_NOTEBOOK.md", ""),
    ("DOC-013", "P1", "docs/adr", "ADR dir"),
    ("DOC-014", "P1", "docs/methodology/NEGATIVE_RESULTS_REGISTER.json", ""),
    ("DOC-015", "P0", "docs/data/DATA_MANAGEMENT_AND_SHARING_PLAN.md", ""),
    ("DOC-016", "P0", "docs/data/DATASET_REGISTER.yaml", ""),
    ("DOC-017", "P0", "docs/data/cards/benchmarks/semantic-route.md", "dataset/benchmark cards"),
    ("DOC-018", "P0", "docs/data/cards/benchmarks/surface-matched-duplicate.md", ""),
    ("DOC-019", "P0", "docs/data/DATA_DICTIONARY.md", ""),
    ("DOC-020", "P0", "THIRD_PARTY_NOTICES.md", "provenance/license"),
    ("DOC-021", "P0", "docs/data/SPLIT_CONTAMINATION_AND_TEST_ACCESS_POLICY.md", ""),
    ("DOC-022", "P1", "docs/data/DATA_MANAGEMENT_AND_SHARING_PLAN.md", "retention covered in DMP"),
    ("DOC-023", "P0", "docs/evaluation/CWC_EVALUATION_PLAN.md", ""),
    ("DOC-024", "P0", "docs/evaluation/BASELINE_SELECTION_AND_COMPUTE_PARITY_POLICY.md", ""),
    ("DOC-025", "P0", "docs/evaluation/MEASUREMENT_UNCERTAINTY_AND_METROLOGY_REPORT.md", ""),
    ("DOC-026", "P0", "experiments/common/metrics.py", "metric defs + tests"),
    ("DOC-027", "P0", "docs/vnv/VERIFICATION_AND_VALIDATION_PLAN.md", ""),
    ("DOC-028", "P0", "docs/vnv/REQUIREMENTS_TRACEABILITY_MATRIX.csv", ""),
    ("DOC-029", "P0", "docs/vnv/VERIFICATION_RECORD.md", ""),
    ("DOC-030", "P0", "docs/vnv/VALIDATION_RECORD.md", ""),
    ("DOC-031", "P1", "docs/vnv/EXPERIMENT_CLOSEOUT_TEMPLATE.md", ""),
    ("DOC-032", "P0", "docs/reproducibility/ARTIFACT_README.md", ""),
    ("DOC-033", "P0", "docs/reproducibility/RESULT_TO_SCRIPT_MATRIX.csv", ""),
    ("DOC-034", "P0", "docs/reproducibility/EXPECTED_RUNTIME_HARDWARE_AND_COST.md", ""),
    ("DOC-035", "P0", "docs/reproducibility/CLEAN_ROOM_REPRODUCTION_PROTOCOL.md", ""),
    ("DOC-036", "P0", "RELEASE_MANIFEST.json", ""),
    ("DOC-037", "P0", "scripts/make_release.py", "release builder"),
    ("DOC-038", "P0", "containers/Dockerfile.cpu", "hermetic containers"),
    ("DOC-039", "P0", "CITATION.cff", ""),
    ("DOC-040", "P1", "docs/reproducibility/ARCHIVAL_AND_PERSISTENT_IDENTIFIER_PLAN.md", ""),
    ("DOC-041", "P1", "CHANGELOG.md", ""),
    ("DOC-042", "P1", "THIRD_PARTY_NOTICES.md", ""),
    ("DOC-043", "P2", "SBOM.spdx.json", ""),
    ("DOC-044", "P1", "docs/publication/CWC_TECHNICAL_REPORT.md", ""),
    ("DOC-045", "P1", "docs/publication/RELATED_WORK_AND_NOVELTY_REVIEW.md", ""),
    ("DOC-046", "P1", "docs/publication/references.bib", ""),
    ("DOC-047", "P1", "docs/publication/NEURIPS_2026_SUBMISSION_CHECKLIST.md", ""),
    ("DOC-048", "P1", "docs/publication/ACM_ARTIFACT_EVALUATION_CHECKLIST.md", ""),
    ("DOC-049", "P1", "docs/publication/AUTHOR_FUNDING_COI_AND_AI_ASSISTANCE_DISCLOSURE.md", ""),
    ("DOC-050", "P1", "docs/publication/LIMITATIONS_BROADER_IMPACTS_AND_ENVIRONMENT.md", ""),
    ("DOC-051", "P1", "docs/system_card/CWC_SYSTEM_CARD.md", ""),
    ("DOC-052", "P2", "docs/risk/NIST_AI_RMF_CURRENT_TARGET_PROFILE.md", "TRIGGER_NOT_REACHED"),
    ("DOC-053", "P2", "docs/risk/RISK_REGISTER.csv", "TRIGGER_NOT_REACHED (TR-1)"),
    ("DOC-054", "P2", "docs/risk/THREAT_MODEL.md", "TRIGGER_NOT_REACHED (TR-1)"),
    ("DOC-055", "P2", "docs/risk/CAPABILITY_ASSESSMENT_AND_TRIGGER_LEVELS.md", ""),
    ("DOC-056", "P2", "docs/risk/SAFETY_CASE.md", "TRIGGER_NOT_REACHED (TR-4)"),
    ("DOC-057", "P2", "docs/risk/RED_TEAM_REPORT.md", "TRIGGER_NOT_REACHED (TR-2)"),
    ("DOC-058", "P2", "docs/risk/SECURITY.md", "TRIGGER_NOT_REACHED (TR-1)"),
    ("DOC-059", "P2", "docs/risk/INCIDENT_RESPONSE_AND_ROLLBACK_PLAN.md", "TRIGGER_NOT_REACHED (TR-1)"),
    ("DOC-060", "P2", "docs/risk/PRIVACY_PII_AND_DATA_RETENTION_POLICY.md", "TRIGGER_NOT_REACHED (TR-2)"),
    ("DOC-061", "P2", "docs/risk/DEPLOYMENT_MONITORING_DEPRECATION_AND_CHANGE_CONTROL.md", "TRIGGER_NOT_REACHED"),
    ("DOC-062", "P2", "docs/risk/EXTERNAL_REVIEW_AND_INDEPENDENCE_PROTOCOL.md", ""),
    ("DOC-063", "P2", "docs/risk/NONCOMPLIANCE_CORRECTIVE_AND_PREVENTIVE_ACTION.md", "TRIGGER_NOT_REACHED"),
]


def main() -> None:
    rows = ["doc_id,priority,state,path,note"]
    counts: dict[str, int] = {}
    for did, prio, path, note in DOCS:
        exists = (ROOT / path).exists()
        if exists:
            state = "EXISTS"
        elif "TRIGGER_NOT_REACHED" in note:
            state = "TRIGGER_NOT_REACHED"
        else:
            state = "MISSING"
        counts[state] = counts.get(state, 0) + 1
        rows.append(f"{did},{prio},{state},{path},{note}")
    OUT.write_text("\n".join(rows) + "\n")
    print(f"register -> {OUT.relative_to(ROOT)} ({len(DOCS)} docs)")
    for k, v in sorted(counts.items()):
        print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
