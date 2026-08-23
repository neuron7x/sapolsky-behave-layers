from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from cwc.governance.evidence_closure import EvidenceClosureLedger
from cwc.governance.p19_evidence_root import build_family_p19_evidence_root


def _write_immutable(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o644)
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
    except BaseException:
        path.unlink(missing_ok=True)
        raise


def _subject_roots(values: list[str]) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--subject-root must be LABEL=PATH")
        label, path = value.split("=", 1)
        label = label.strip()
        path = path.strip()
        if not label or not path or label in result:
            raise ValueError("subject-root label/path must be non-empty and unique")
        result[label] = Path(path)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Build one family-scoped P19 evidence root from the pre-P19 ledger and raw subjects.")
    parser.add_argument("--repository-root", default=".")
    parser.add_argument("--ledger", required=True)
    parser.add_argument("--generation-id", required=True)
    parser.add_argument("--repo-commit", required=True)
    parser.add_argument("--repo-tree", required=True)
    parser.add_argument("--primary-anytime-p9", required=True)
    parser.add_argument("--primary-ccf-audit", required=True)
    parser.add_argument("--subject-root", action="append", default=[], help="repeat LABEL=PATH for exact P19 root population")
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    root = Path(args.repository_root)
    ledger = EvidenceClosureLedger(
        repository_root=root,
        ledger_path=Path(args.ledger),
        generation_id=args.generation_id,
        repo_commit=args.repo_commit,
        repo_tree=args.repo_tree,
    )
    authority = build_family_p19_evidence_root(
        ledger=ledger,
        primary_anytime_p9_authority_path=Path(args.primary_anytime_p9),
        primary_ccf_oracle_audit_authority_path=Path(args.primary_ccf_audit),
        subject_roots=_subject_roots(args.subject_root),
    )
    output = Path(args.output)
    _write_immutable(output, json.dumps(authority.document, indent=2, sort_keys=True).encode("utf-8") + b"\n")
    print(json.dumps({
        "status": "PASS" if authority.family_evidence_complete else "FAIL_P19",
        "authority": str(output),
        "family_id": authority.family_id,
        "p19_digest": authority.p19_digest,
        "family_qualification_ready": authority.family_evidence_complete,
        "global_product_qualification_authorized": False,
        "peer_family_p19_required": True,
    }, sort_keys=True))
    return 0 if authority.family_evidence_complete else 60


if __name__ == "__main__":
    raise SystemExit(main())