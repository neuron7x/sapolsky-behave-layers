from __future__ import annotations

import tempfile
from pathlib import Path

from make_dgc_release import build_release, sha256_file

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="dgc-release-a-") as a, tempfile.TemporaryDirectory(prefix="dgc-release-b-") as b:
        first = build_release(ROOT, Path(a), require_clean=True, require_product_qualified=False)
        second = build_release(ROOT, Path(b), require_clean=True, require_product_qualified=False)
        if first != second:
            raise AssertionError("release manifests differ across clean rebuilds")
        names_a = sorted(path.name for path in Path(a).iterdir())
        names_b = sorted(path.name for path in Path(b).iterdir())
        if names_a != names_b:
            raise AssertionError("release file sets differ across clean rebuilds")
        for name in names_a:
            if sha256_file(Path(a) / name) != sha256_file(Path(b) / name):
                raise AssertionError(f"non-reproducible release artifact: {name}")
        print(
            "DGC-RELEASE-REPRO: PASS "
            f"commit={first['git_commit']} tree={first['git_tree']} files={len(names_a)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
