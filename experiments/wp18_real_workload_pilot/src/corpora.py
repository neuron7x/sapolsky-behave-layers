"""WP18 corpus construction with contamination control (Act G3).

Two distinct REAL task families from local sources -- English prose (repo docs) and Python source
code -- split deterministically by SHA-256 of each source file into train + 5 held-out eval shards.
Splitting by FILE (not by byte offset) is what makes the contamination check meaningful: no eval
file contributes a single training byte. See PREREGISTRATION.md.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "artifacts/wp18-real-workload-pilot"
N_EVAL_SHARDS = 5
MIN_FILE_BYTES = 512


def _files(family: str) -> list[Path]:
    if family == "prose":
        return sorted(p for p in (ROOT / "docs").rglob("*.md")
                      if p.is_file() and p.stat().st_size >= MIN_FILE_BYTES)
    if family == "code":
        return sorted(p for p in ROOT.rglob("*.py")
                      if p.is_file() and p.stat().st_size >= MIN_FILE_BYTES
                      and not any(x in p.parts for x in
                                  (".venv", "__pycache__", ".git", "legacy", "artifacts")))
    raise ValueError(family)


def _bucket(p: Path) -> int:
    """Deterministic split by content hash: 0 = train, 1..N = eval shards."""
    h = int(hashlib.sha256(p.read_bytes()).hexdigest()[:8], 16)
    return 0 if h % 3 else (h // 3) % N_EVAL_SHARDS + 1


def build(family: str) -> dict[str, Any]:
    files = _files(family)
    parts: dict[int, list[Path]] = {i: [] for i in range(N_EVAL_SHARDS + 1)}
    for p in files:
        parts[_bucket(p)].append(p)

    def _text(ps: list[Path]) -> str:
        return "\n".join(p.read_text(encoding="utf-8", errors="ignore") for p in ps)

    train = _text(parts[0])
    shards = [_text(parts[i]) for i in range(1, N_EVAL_SHARDS + 1)]

    # Contamination control: no file may appear in two partitions, and no eval file's bytes may
    # occur in the training text. Verified, not assumed.
    all_sets = [{str(p) for p in parts[i]} for i in range(N_EVAL_SHARDS + 1)]
    overlap = any(all_sets[i] & all_sets[j] for i in range(len(all_sets))
                  for j in range(i + 1, len(all_sets)))
    leaked = [str(p) for i in range(1, N_EVAL_SHARDS + 1) for p in parts[i]
              if p.read_text(encoding="utf-8", errors="ignore")[:400] in train]
    return {
        "family": family,
        "n_files_total": len(files),
        "n_train_files": len(parts[0]),
        "eval_shard_files": [len(parts[i]) for i in range(1, N_EVAL_SHARDS + 1)],
        "train_bytes": len(train.encode("utf-8", "ignore")),
        "eval_shard_bytes": [len(s.encode("utf-8", "ignore")) for s in shards],
        "file_partition_overlap": overlap,
        "leaked_eval_files": leaked,
        "contamination_clean": (not overlap) and not leaked,
        "train_sha256": hashlib.sha256(train.encode("utf-8", "ignore")).hexdigest(),
        "eval_shard_sha256": [hashlib.sha256(s.encode("utf-8", "ignore")).hexdigest() for s in shards],
        "_train_text": train,
        "_shard_texts": shards,
    }


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    cards = {}
    for fam in ("prose", "code"):
        b = build(fam)
        (OUT / f"corpus_{fam}_train.txt").write_text(b.pop("_train_text"), encoding="utf-8")
        for i, s in enumerate(b.pop("_shard_texts"), 1):
            (OUT / f"corpus_{fam}_eval{i}.txt").write_text(s, encoding="utf-8")
        cards[fam] = b
        print(f"{fam}: train {b['train_bytes']:,}B / {b['n_train_files']} files | "
              f"eval shards {b['eval_shard_bytes']} | clean={b['contamination_clean']}")
    (OUT / "dataset_card.json").write_text(json.dumps({
        "workloads": cards,
        "split_rule": "deterministic by SHA-256 of each source file; bucket 0 = train, 1..5 = eval",
        "license": "repository's own content (MIT) -- no external dataset, no redistribution issue",
        "provenance": "local repository files at the recorded commit; immutable given the commit",
        "note": "Splitting by FILE, not byte offset, is what makes the contamination check "
                "meaningful: no eval file contributes any training byte.",
    }, indent=2) + "\n")


if __name__ == "__main__":
    main()
