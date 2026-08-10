#!/usr/bin/env python3
"""Fail-closed validator for ACT-R&D-01 research-ingestion artifacts.

The registry files use JSON syntax in .yaml containers (valid YAML 1.2 subset) so the
validator has no optional YAML dependency. This gate checks provenance fields,
promotion order, executable hypothesis completeness, and architecture-promotion bans.
"""
from __future__ import annotations

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
RESEARCH = ROOT / "research"

REQUIRED_SOURCE = {
    "source_id", "title", "authors", "year", "venue", "doi", "arxiv_id",
    "version", "publication_status", "primary_source", "code_available",
    "data_available", "independent_replication", "retraction_or_correction",
    "retrieved_at", "source_sha256", "snapshot_sha256", "snapshot_path",
}
REQUIRED_HYPOTHESIS = {
    "hypothesis_id", "source_claims", "mechanism", "formal_object", "expected_effect",
    "intervention", "control", "null_model", "dataset", "metric", "decision_rule",
    "failure_condition", "integration_target", "promotion_status",
}
PROMOTION_ORDER = [
    "DISCOVERED", "SOURCE_VERIFIED", "CLAIM_EXTRACTED", "REPRODUCED",
    "NULL_ATTACKED", "OOD_REPLICATED", "MECHANISM_SUPPORTED", "ARCHITECTURE_CANDIDATE",
]
ALLOWED_EVIDENCE = {"ANCHORED", "REPLICATED", "EXTRAPOLATED", "SPECULATIVE", "UNKNOWN", "FALSIFIED"}
ALLOWED_PUBLICATION = {"PEER_REVIEWED", "CONFERENCE", "WORKSHOP", "PREPRINT", "DATASET", "CODE"}


def load_json_yaml(rel: str):
    return json.loads((RESEARCH / rel).read_text(encoding="utf-8"))


def fail(msg: str) -> None:
    print(f"RESEARCH-INGESTION-GATE: FAIL — {msg}")
    raise SystemExit(1)


def main() -> int:
    required = [
        "01_SOURCE_REGISTRY.yaml", "02_EVIDENCE_MATRIX.csv", "03_CLAIM_LEDGER.yaml",
        "04_MECHANISM_GRAPH.graphml", "05_CONTRADICTION_MATRIX.csv",
        "06_EXECUTABLE_HYPOTHESES.yaml", "07_NULL_ATTACK_REGISTRY.yaml",
        "08_REPRODUCTION_QUEUE.yaml", "09_KILLED_HYPOTHESES.yaml",
        "10_INTEGRATION_DECISIONS.md",
    ]
    missing = [name for name in required if not (RESEARCH / name).is_file()]
    if missing:
        fail(f"missing required artifacts: {missing}")

    sources = load_json_yaml("01_SOURCE_REGISTRY.yaml")
    claims = load_json_yaml("03_CLAIM_LEDGER.yaml")
    hypotheses = load_json_yaml("06_EXECUTABLE_HYPOTHESES.yaml")
    queue = load_json_yaml("08_REPRODUCTION_QUEUE.yaml")

    if not sources:
        fail("source registry is empty")
    source_ids: set[str] = set()
    for source in sources:
        absent = REQUIRED_SOURCE - set(source)
        if absent:
            fail(f"source {source.get('source_id')} missing fields {sorted(absent)}")
        if source["source_id"] in source_ids:
            fail(f"duplicate source_id {source['source_id']}")
        source_ids.add(source["source_id"])
        if not source["primary_source"]:
            fail(f"core source {source['source_id']} is not primary")
        if source["publication_status"] not in ALLOWED_PUBLICATION:
            fail(f"invalid publication status for {source['source_id']}")
        snapshot = ROOT / source["snapshot_path"]
        if not snapshot.is_file():
            fail(f"missing immutable extraction snapshot for {source['source_id']}")

    claim_ids: set[str] = set()
    for claim in claims:
        cid = claim.get("claim_id")
        if not cid or cid in claim_ids:
            fail(f"invalid/duplicate claim_id {cid}")
        claim_ids.add(cid)
        if claim.get("source_id") not in source_ids:
            fail(f"claim {cid} has unknown source")
        if claim.get("status") not in ALLOWED_EVIDENCE:
            fail(f"claim {cid} uses invalid evidence status {claim.get('status')}")

    for hyp in hypotheses:
        absent = REQUIRED_HYPOTHESIS - set(hyp)
        if absent:
            fail(f"hypothesis {hyp.get('hypothesis_id')} missing fields {sorted(absent)}")
        unknown = set(hyp["source_claims"]) - claim_ids
        if unknown:
            fail(f"hypothesis {hyp['hypothesis_id']} references unknown claims {sorted(unknown)}")
        status = hyp["promotion_status"]
        if status not in PROMOTION_ORDER:
            fail(f"hypothesis {hyp['hypothesis_id']} invalid promotion status {status}")
        # First pass must never skip reproduction/null/OOD and jump to architecture.
        if PROMOTION_ORDER.index(status) > PROMOTION_ORDER.index("CLAIM_EXTRACTED"):
            fail(f"hypothesis {hyp['hypothesis_id']} illegally promoted beyond CLAIM_EXTRACTED")
        if not str(hyp["failure_condition"]).strip():
            fail(f"hypothesis {hyp['hypothesis_id']} has no failure condition")
        if not str(hyp["null_model"]).strip():
            fail(f"hypothesis {hyp['hypothesis_id']} has no null model")

    if not queue:
        fail("reproduction queue is empty")
    if not any(item.get("priority") == "P0" for item in queue):
        fail("no P0 reproduction target")

    decisions = (RESEARCH / "10_INTEGRATION_DECISIONS.md").read_text(encoding="utf-8")
    if "None is `REPRODUCED`" not in decisions:
        fail("integration report does not preserve no-reproduction boundary")

    print(
        "RESEARCH-INGESTION-GATE: PASS — "
        f"{len(sources)} sources, {len(claims)} claims, {len(hypotheses)} executable hypotheses; "
        "no architecture promotion"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
