from __future__ import annotations

import argparse
from pathlib import Path

from cwc_fractal.protocol import validate_protocol


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "protocol",
        type=Path,
        default=Path("experiments/cwc_fractal_protocol_v1.yaml"),
        nargs="?",
    )
    parser.add_argument("--schema", type=Path, default=Path("schemas/fractal_protocol.schema.json"))
    args = parser.parse_args()
    errors = validate_protocol(args.protocol, args.schema)
    if errors:
        print("\n".join(errors))
        raise SystemExit(1)
    print("FRACTAL_PROTOCOL_PASS")


if __name__ == "__main__":
    main()
