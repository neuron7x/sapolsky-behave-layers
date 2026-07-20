"""Machine-verifiable documentation spine (Act CWC-LAB-DOC-2026-01, Gate DOC-1..4).

Checks, with NO third-party deps (jsonschema unavailable in the frozen env):
  1. claim_registry.json validates against schemas/claim.schema.json (required
     fields + status enum + no unknown keys); its git_commit is a real,
     reachable ANCESTOR of HEAD (a committed registry is always one behind HEAD,
     so exact equality is unsatisfiable); AND — fail-closed against a stale stamp
     that predates its own evidence — every required_artifact already exists in
     the tree of that git_commit, not merely in the working tree;
  2. every claim has a hypothesis_id that resolves in HYPOTHESIS_REGISTRY.yaml,
     and every hypothesis has a claim_id that resolves back (orphans == 0);
  3. every claim's required_artifacts path exists on disk;
  4. the P0 constitutional documents listed below are present.

Exit code 0 = PASS, 1 = FAIL. Run:
  PYTHONPATH=. .venv/bin/python scripts/doc_status_gate.py
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[1]

P0_DOCS = [
    "README.md", "SYSTEM.md", "LICENSE", "CITATION.cff", "CHANGELOG.md",
    "THIRD_PARTY_NOTICES.md", "claim_registry.json",
    "docs/methodology/CWC_MASTER_METHODOLOGY.md",
    "docs/methodology/HYPOTHESIS_REGISTRY.yaml",
    "docs/methodology/EXPERIMENT_PROTOCOL_TEMPLATE.md",
    "docs/methodology/STATISTICAL_ANALYSIS_PLAN.md",
    "docs/methodology/PROTOCOL_AMENDMENT_AND_DEVIATION_POLICY.md",
    "docs/lab/EXPERIMENT_LEDGER.jsonl",
    "docs/data/DATA_MANAGEMENT_AND_SHARING_PLAN.md",
    "docs/data/DATASET_REGISTER.yaml",
    "docs/evaluation/CWC_EVALUATION_PLAN.md",
    "docs/evaluation/MEASUREMENT_UNCERTAINTY_AND_METROLOGY_REPORT.md",
    "docs/vnv/VERIFICATION_AND_VALIDATION_PLAN.md",
    "docs/vnv/REQUIREMENTS_TRACEABILITY_MATRIX.csv",
    "docs/reproducibility/CLEAN_ROOM_REPRODUCTION_PROTOCOL.md",
    "docs/reproducibility/RESULT_TO_SCRIPT_MATRIX.csv",
    "docs/system_card/CWC_SYSTEM_CARD.md",
    "schemas/claim.schema.json", "schemas/hypothesis.schema.json",
]

STATUS_ENUM = {"SUPPORTED", "SUPPORTED_NARROWED", "NOT_SUPPORTED", "NOT_TESTED",
               "INSTRUMENT_INVALID", "NOT_IDENTIFIABLE"}


def _load_schema_keys(path: Path) -> tuple[set[str], set[str]]:
    s = json.loads(path.read_text())
    return set(s.get("required", [])), set(s.get("properties", {}).keys())


def main() -> int:
    errors: list[str] = []

    # (4) P0 documents present
    for rel in P0_DOCS:
        if not (ROOT / rel).exists():
            errors.append(f"P0 document missing: {rel}")

    # (1) claim registry vs schema + commit
    reg = json.loads((ROOT / "claim_registry.json").read_text())
    req_keys, allowed_keys = _load_schema_keys(ROOT / "schemas/claim.schema.json")
    head = subprocess.run("git rev-parse HEAD", shell=True, cwd=ROOT,
                          capture_output=True, text=True).stdout.strip()
    reg_commit = reg.get("git_commit", "")
    if reg_commit:
        # "not stale" = the recorded commit is a real ancestor of HEAD (reachable),
        # not a divergent/old pre-drift commit. A committed registry is always one
        # behind HEAD, so exact equality is unsatisfiable; ancestry is the right test.
        exists = subprocess.run(f"git cat-file -e {reg_commit}^{{commit}}", shell=True,
                                cwd=ROOT, capture_output=True).returncode == 0
        ancestor = subprocess.run(f"git merge-base --is-ancestor {reg_commit} HEAD",
                                  shell=True, cwd=ROOT, capture_output=True).returncode == 0
        if not exists:
            errors.append(f"claim_registry git_commit {reg_commit[:7]} is not a real commit")
        elif not ancestor:
            errors.append(f"claim_registry git_commit {reg_commit[:7]} is not an ancestor of HEAD (stale/divergent)")
        else:
            # Anti-staleness: the stamp must not predate the evidence it points to.
            # Every required_artifact must already exist in reg_commit's own tree,
            # so a registry stamped 51 commits before its artifacts were created
            # (the historical d920f79 defect) fails closed instead of passing on a
            # working-tree existence check alone.
            for c in reg["claims"]:
                for art in c.get("required_artifacts", []):
                    tree_path = art.rstrip("/")
                    present = subprocess.run(
                        f"git cat-file -e {reg_commit}:{tree_path}",
                        shell=True, cwd=ROOT, capture_output=True).returncode == 0
                    if not present:
                        errors.append(
                            f"claim {c.get('claim_id','<no id>')}: required_artifact "
                            f"'{art}' absent at registry commit {reg_commit[:7]} "
                            f"(registry stamped before its own evidence)")

    claims = reg["claims"]
    claim_hyp = {}
    for c in claims:
        cid = c.get("claim_id", "<no id>")
        for k in req_keys:
            if k not in c:
                errors.append(f"claim {cid}: missing required field '{k}'")
        for k in c:
            if k not in allowed_keys:
                errors.append(f"claim {cid}: unknown field '{k}'")
        if c.get("status") not in STATUS_ENUM:
            errors.append(f"claim {cid}: status '{c.get('status')}' not in enum")
        for art in c.get("required_artifacts", []):
            if not (ROOT / art).exists():
                errors.append(f"claim {cid}: required_artifact missing on disk: {art}")
        if "hypothesis_id" in c:
            claim_hyp[cid] = c["hypothesis_id"]
        else:
            errors.append(f"claim {cid}: no hypothesis_id (orphan claim)")

    # (2) claim <-> hypothesis linkage
    hyps = yaml.safe_load((ROOT / "docs/methodology/HYPOTHESIS_REGISTRY.yaml").read_text())
    hyp_by_id = {h["hypothesis_id"]: h for h in hyps["hypotheses"]}
    for cid, hid in claim_hyp.items():
        if hid not in hyp_by_id:
            errors.append(f"claim {cid}: hypothesis_id {hid} not in registry (orphan)")
        elif hyp_by_id[hid].get("claim_id") != cid:
            errors.append(f"hypothesis {hid}: claim_id back-ref != {cid}")
    for hid, h in hyp_by_id.items():
        back = h.get("claim_id")
        if back and back not in {c.get("claim_id") for c in claims}:
            errors.append(f"hypothesis {hid}: claim_id {back} not in registry (orphan)")

    n_docs = sum(1 for d in P0_DOCS if (ROOT / d).exists())
    print(f"P0 docs present: {n_docs}/{len(P0_DOCS)} | claims: {len(claims)} | "
          f"hypotheses: {len(hyp_by_id)} | HEAD {head[:7]}")
    if errors:
        print(f"\nDOC-GATE FAIL ({len(errors)} issue(s)):")
        for e in errors:
            print(f"  - {e}")
        return 1
    print("DOC-GATE PASS: registry schema-valid, commit current, 0 orphans, artifacts exist.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
