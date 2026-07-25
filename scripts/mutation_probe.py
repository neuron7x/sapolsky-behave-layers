"""CWC WP-1 mutation probe: proves the test suite actually catches bugs, not
just that it runs. For each mutation it applies one small, semantically-real
defect to a source file, runs the targeted test subset, and asserts the suite
FAILS (the mutant is killed). A surviving mutant is a genuine test-suite gap.

This is deliberately a small, hand-curated, deterministic set focused on the
mathematical cores (where a silent wrong answer is most dangerous), not a
blanket AST mutator — every mutation here is one a real bug could plausibly be.

Safety: each source file is backed up and restored in a finally block, so an
interrupted run never leaves a mutated source on disk. Run from repo root:

    python scripts/mutation_probe.py
"""
from __future__ import annotations

import dataclasses
import os
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PY = sys.executable

# Fast, targeted test subset — the suites that exercise the mutated logic.
# (Excludes CUDA/slow tests so each mutant runs in a couple of seconds.)
TEST_TARGETS = [
    "tests/test_instrumentation_stats.py",
    "tests/test_instrumentation_properties.py",
    "tests/test_instrumentation_flops.py",
    "tests/test_instrumentation_energy.py",
    "tests/test_instrumentation_energy_nvml.py",
    "tests/test_instrumentation_routing.py",
]


@dataclasses.dataclass(frozen=True)
class Mutation:
    file: str
    original: str
    mutated: str
    description: str


MUTATIONS: list[Mutation] = [
    # --- stats.py: percentile / bootstrap -----------------------------------
    Mutation(
        "cwc/instrumentation/stats.py",
        "return low_value * (1.0 - weight) + high_value * weight",
        "return low_value * (1.0 + weight) + high_value * weight",
        "percentile interpolation weight sign flip",
    ),
    Mutation(
        "cwc/instrumentation/stats.py",
        "upper = min(lower + 1, len(ordered) - 1)",
        "upper = min(lower + 2, len(ordered) - 1)",
        "percentile upper index off-by-one",
    ),
    Mutation(
        "cwc/instrumentation/stats.py",
        "tail = (1.0 - confidence) / 2.0",
        "tail = (1.0 - confidence) / 1.0",
        "bootstrap CI tail probability wrong (one-sided)",
    ),
    # --- flops.py: formulas -------------------------------------------------
    Mutation(
        "cwc/instrumentation/flops.py",
        "return 2 * tokens * d_in * d_out",
        "return 1 * tokens * d_in * d_out",
        "dense linear FLOPs drops the 2-MAC factor",
    ),
    Mutation(
        "cwc/instrumentation/flops.py",
        "return seq_len * (seq_len + 1) // 2",
        "return seq_len * (seq_len - 1) // 2",
        "causal pair count off (n-1 instead of n+1)",
    ),
    Mutation(
        "cwc/instrumentation/flops.py",
        "return 4 * batch * valid_attention_pairs * d_model",
        "return 2 * batch * valid_attention_pairs * d_model",
        "attention-core QK+AV factor halved",
    ),
    Mutation(
        "cwc/instrumentation/flops.py",
        "return 2 * tokens * d_model * d_ff + 2 * tokens * d_ff * d_model",
        "return 2 * tokens * d_model * d_ff",
        "MLP FLOPs missing the down-projection term",
    ),
    Mutation(
        "cwc/instrumentation/flops.py",
        "total += i - left + 1",
        "total += i - left",
        "sliding-window pair count off-by-one per query",
    ),
    # --- energy.py: trapezoidal integration ---------------------------------
    Mutation(
        "cwc/instrumentation/energy.py",
        "total += 0.5 * (w0 + w1) * dt",
        "total += 1.0 * (w0 + w1) * dt",
        "trapezoidal rule drops the 0.5 factor",
    ),
    Mutation(
        "cwc/instrumentation/energy.py",
        "joules = max(0, end_mj - self._start_mj) / 1000.0",
        "joules = (end_mj - self._start_mj) / 1000.0",
        "total-energy delta loses the negative clamp",
    ),
    # --- routing.py: aggregation --------------------------------------------
    Mutation(
        "cwc/instrumentation/routing.py",
        "return value if current is None else min(current, value)",
        "return value if current is None else max(current, value)",
        "routing running-min computes max instead",
    ),
    Mutation(
        "cwc/instrumentation/routing.py",
        "self._active_tokens_sum += active_tokens",
        "self._active_tokens_sum += active_blocks",
        "routing token-sum accumulates the wrong field",
    ),
]


def _purge_bytecode(source_path: Path) -> None:
    """Remove any compiled bytecode for a mutated source file so the next
    import always recompiles from the (restored) source, never a stale .pyc."""
    cache_dir = source_path.parent / "__pycache__"
    if cache_dir.is_dir():
        for pyc in cache_dir.glob(f"{source_path.stem}.*.pyc"):
            pyc.unlink(missing_ok=True)


def _run_targets() -> subprocess.CompletedProcess[str]:
    """Run the mutation targets and preserve enough evidence to classify failure.

    PYTHONDONTWRITEBYTECODE guarantees each run imports the freshly-mutated
    source, never a stale .pyc — without it a cached bytecode of the original
    can mask a mutation and produce a false 'killed'/'survived'.
    """
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1"}
    return subprocess.run(
        [PY, "-m", "pytest", "-x", "-q", "-p", "no:cacheprovider", *TEST_TARGETS],
        cwd=REPO,
        capture_output=True,
        text=True,
        env=env,
    )


def _is_assertion_kill(result: subprocess.CompletedProcess[str]) -> bool:
    """Only an actual test failure kills a mutant.

    Import errors, collection errors, crashes, interrupts and infrastructure
    failures used to be counted as successful kills. That produced a green
    mutation score while the probe itself was broken.
    """
    output = f"{result.stdout}\n{result.stderr}"
    has_failed_test = re.search(r"^FAILED\s+", output, re.MULTILINE) is not None
    has_test_error = re.search(r"^ERROR\s+", output, re.MULTILINE) is not None
    return result.returncode == 1 and has_failed_test and not has_test_error


def main() -> int:
    # Sanity: baseline must be green before mutating anything.
    baseline = _run_targets()
    if baseline.returncode != 0:
        print("BASELINE FAILED — refusing to run mutation probe on a red suite")
        print(baseline.stdout)
        print(baseline.stderr)
        return 2

    killed = 0
    survived: list[Mutation] = []
    for i, mut in enumerate(MUTATIONS, start=1):
        path = REPO / mut.file
        source = path.read_text(encoding="utf-8")
        if mut.original not in source:
            print(f"[{i:02d}/{len(MUTATIONS)}] SKIP (anchor not found): {mut.description}")
            survived.append(mut)  # a missing anchor is a probe defect worth surfacing
            continue
        backup = source
        try:
            path.write_text(source.replace(mut.original, mut.mutated, 1), encoding="utf-8")
            result = _run_targets()
        finally:
            path.write_text(backup, encoding="utf-8")
            # Purge the mutated file's bytecode so a same-second mtime cannot
            # let a subsequent import trust a stale mutated .pyc (this is the
            # documented mutation-probe poisoning gotcha).
            _purge_bytecode(path)
        if result.returncode == 0:
            survived.append(mut)
            print(f"[{i:02d}/{len(MUTATIONS)}] SURVIVED  ✗  {mut.description}")
        elif not _is_assertion_kill(result):
            survived.append(mut)
            print(
                f"[{i:02d}/{len(MUTATIONS)}] INVALID   ✗  "
                f"{mut.description} (non-assertion test failure)"
            )
        else:
            killed += 1
            print(f"[{i:02d}/{len(MUTATIONS)}] killed    ✓  {mut.description}")

    total = len(MUTATIONS)
    rate = 100.0 * killed / total if total else 0.0
    print(f"\nMUTATION KILL RATE: {killed}/{total} = {rate:.1f}%")
    if survived:
        print("SURVIVORS (test-suite gaps):")
        for mut in survived:
            print(f"  - {mut.file}: {mut.description}")
        return 1
    print("ALL MUTANTS KILLED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
