"""CLI for the content-addressed evidence intake firewall."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, TextIO

from cwc.evidence.intake import audit_tree


def _write_record(stream: TextIO, item: dict[str, Any]) -> None:
    stream.write(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--require-complete", action="store_true")
    parser.add_argument("--progress-every", type=int, default=10_000)
    args = parser.parse_args()
    if args.progress_every < 1:
        parser.error("--progress-every must be positive")

    args.summary.parent.mkdir(parents=True, exist_ok=True)
    manifest_stream = None
    try:
        if args.manifest is not None:
            args.manifest.parent.mkdir(parents=True, exist_ok=True)
            manifest_stream = args.manifest.open("w", encoding="utf-8")
        summary = audit_tree(
            args.root,
            record=(lambda item: _write_record(manifest_stream, item)) if manifest_stream else None,
            progress=lambda files, size: print(f"DATA-INTAKE: {files} files, {size} bytes hashed"),
            progress_every=args.progress_every,
        )
    finally:
        if manifest_stream is not None:
            manifest_stream.close()
    args.summary.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(
        f"DATA-INTAKE: {'PASS' if summary['complete'] else 'INCOMPLETE'} "
        f"({summary['hashed_file_count']}/{summary['file_count']} files, "
        f"{summary['byte_count']} bytes, root={summary['corpus_sha256']})"
    )
    return 1 if args.require_complete and not summary["complete"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
