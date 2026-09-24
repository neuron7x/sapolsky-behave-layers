from __future__ import annotations

import argparse
import json
from pathlib import Path

from cwc.governance.p19_external_verifier_freeze_readiness import (
    build_p19_external_verifier_freeze_readiness,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Check whether the current external P19 verifier source/test/method surface is Git-tracked, "
            "clean, content-addressed and ready for one-time inactive Plan V4 freeze."
        )
    )
    parser.add_argument("--repository-root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()

    authority = build_p19_external_verifier_freeze_readiness(
        repository_root=args.repository_root,
    )
    print(json.dumps(authority.document, sort_keys=True))
    return 0 if authority.ready_to_freeze else 2


if __name__ == "__main__":
    raise SystemExit(main())
