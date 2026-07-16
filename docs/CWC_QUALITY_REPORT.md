# CWC WP-1 Instrumentation — Reference-Quality Report

Quality state of the `cwc/instrumentation` subsystem after the reference-grade
hardening pass. Every number below was produced by running the tool on the
exact-pinned environment (`.venv`, `torch==2.9.1+cu128`, Python 3.10.20), not
asserted from memory. Reproduce with `make -f Makefile.cwc verify`.

## Headline

| Dimension | Result | Gate |
|---|---|---|
| Type safety | `mypy --strict` clean, 16 source files | `mypy.ini`, 0 errors |
| Lint | `ruff` clean (E/F/I/UP/B/SIM/C4/PIE/RET/RUF) | `ruff.toml` |
| Line+branch coverage | **99.46%** (13 of 15 modules at 100%) | floor 95% (`--cov-fail-under`) |
| Mutation kill rate | **12/12 = 100%** over the mathematical cores | `scripts/mutation_probe.py` |
| Behavioral tests | 209 tests (+ 12 mutants), 254 across the fork | all pass, pynvml-only skips |
| Property-based tests | 25 invariants (Hypothesis) | `test_instrumentation_properties.py` |
| Determinism | byte-identical deterministic layers | `test_instrumentation_determinism.py` |

Source: 1,821 LOC across 15 modules. Tests: 2,382 LOC — a test:source ratio > 1.3.

## What each gate actually proves

**Type strictness.** `mypy --strict` over the whole package: no implicit `Any`,
no untyped defs, no missing return types. The only untyped external surfaces
(`torch.cuda.Event/record/elapsed_time`, `pynvml`) are optional-import-guarded
and confined via scoped config, never blanket-`# type: ignore`'d.

**Coverage.** 99.46% line+branch on the CUDA host (97% on a CPU-only runner,
where the `@pytest.mark.cuda` tests skip). The residual is 2 lines + 4 partial
branches, each documented: `energy.py:28` (`import pynvml` success flag —
uncoverable without installing the optional pynvml), `energy.py:228->230` (a
defensive facade fallthrough), and 3 `audit.py` profiler branches needing a
specific torch-profiler op. None is a real logic gap.

**Property-based testing.** 25 Hypothesis properties assert invariants over
*all* inputs, not examples: 2-MAC FLOP identity and monotonicity,
`causal ≤ noncausal`, `sliding ≤ full`, `window≥n ⟹ full`, `w=1 ⟹ diagonal`,
percentile bounds/monotonicity/endpoint-exactness, bootstrap-CI
ordering/range/constant-exactness, trapezoidal `P·T` identity and
non-negativity, routing sum/min/max and histogram conservation, event-pool
conservation.

**Mutation testing** is the real proof the suite catches bugs. 12 curated,
semantically-real defects injected into the mathematical cores; each must make
the suite fail. It earned its keep: on first run it found **two genuinely weak
tests** (percentile upper-index off-by-one, and a bootstrap two-sided-tail test
that passed for the wrong reason) — both strengthened to exact-value
assertions, taking the kill rate 10/12 → 12/12.

**Determinism.** The deterministic reduction layers produce byte-identical
output across repeated runs with identical inputs (FLOP ledger JSON, routing
snapshot, seeded bootstrap CI, writer summary + SHA256SUMS, manifest
deterministic fields). This is the property that makes an evidence bundle
auditable.

## Two real hazards found and fixed during hardening

1. **Constant-input precision (Hypothesis).** The original `percentile` /
   `bootstrap_ci` (duplicated across 3 scripts) lost a ULP on constant inputs
   (`lo*(1-w)+hi*w` and `fmean`). Fixed by extracting a single canonical
   `cwc/instrumentation/stats.py` that is constant-exact (endpoint short-circuit
   + `statistics.mean`). DRY *and* correct.

2. **Stale-`.pyc` mutation poisoning.** Mutating a source file and restoring it
   within the same mtime-second let Python trust a stale mutated `.pyc` on the
   next import — silently corrupting later results. Fixed: the probe runs its
   inner pytest with `PYTHONDONTWRITEBYTECODE=1` and purges each mutated file's
   bytecode in the restore `finally` block.

## Scope and honesty

This report covers *code and test quality* of the measurement layer. It does
**not** re-open the WP-1 verdict: the overhead gate remains
`BLOCKED_BY_MEASUREMENT_OVERHEAD` at the one model scale this 4 GiB GPU can run
(see `docs/WP1_INSTRUMENTATION.md`), and `infer_bench.py` integration is still
code-complete-but-not-runtime-verified (no trained checkpoint in this
environment). Quality hardening does not change either of those honest limits —
it makes the measurement instrument itself trustworthy, which is the
precondition for any future claim built on it.

## Reproduce

```bash
make -f Makefile.cwc install-dev     # ruff/mypy/hypothesis/coverage/mutmut into .venv
make -f Makefile.cwc verify          # lint -> typecheck -> test -> coverage(95) -> mutation(100%)
make -f Makefile.cwc determinism     # byte-identical-output gate
make -f Makefile.cwc properties      # Hypothesis property suite
```
