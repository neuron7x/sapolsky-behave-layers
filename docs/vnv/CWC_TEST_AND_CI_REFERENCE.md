# CWC test and GitHub Actions reference

Commands and triggers describe [`8617187`](https://github.com/neuron7x/sapolsky-behave-layers/commit/861718751198deeeda54a23efacb2227a819b49f). Historical receipts below identify the actual tested checkout.

## Entry points and coverage

| Entry point | Scope and failure semantics |
| --- | --- |
| `make -f Makefile.cwc test` | Selected instrumentation and evidence-validation pytest suites. The Make target filters `slow` and `mutation`. Read the collection, skip and deselection counts. [Recipe](https://github.com/neuron7x/sapolsky-behave-layers/blob/861718751198deeeda54a23efacb2227a819b49f/Makefile.cwc#L182-L188). |
| `make -f Makefile.cwc coverage` | Branch coverage over instrumentation, plasticity, evidence and assurance. Default floor 95%, canonical CPU full PR floor 91%. The dedicated quality workflow instead measures instrumentation at 85%. The dual-sided verifier has a separate 100% scoped gate. [Recipes](https://github.com/neuron7x/sapolsky-behave-layers/blob/861718751198deeeda54a23efacb2227a819b49f/Makefile.cwc#L200-L214) · [verifier gate](https://github.com/neuron7x/sapolsky-behave-layers/blob/861718751198deeeda54a23efacb2227a819b49f/Makefile.cwc#L10-L18) · [quality](https://github.com/neuron7x/sapolsky-behave-layers/blob/861718751198deeeda54a23efacb2227a819b49f/.github/workflows/cwc-quality.yml#L56-L78). |
| `make -f Makefile.cwc mutation` | The registered mathematical-core mutants must be killed. The count covers the injected roster. [Probe](../../scripts/mutation_probe.py). |
| `make -f Makefile.cwc experiment-tests` | Discovers nested `experiments/**/tests` and excludes the separately isolated fractal project and caches. Top-level proof tests need a dedicated target or workflow. [Discovery](https://github.com/neuron7x/sapolsky-behave-layers/blob/861718751198deeeda54a23efacb2227a819b49f/Makefile.cwc#L219-L226) · [proof targets](https://github.com/neuron7x/sapolsky-behave-layers/blob/861718751198deeeda54a23efacb2227a819b49f/Makefile.cwc#L334-L346). |
| `make -f Makefile.cwc verify` | Selected static, behavioral, coverage, mutation, experiment, claim and history-sensitive document gates. `verify-full` adds historical evidence checksums and the WP4 replay. `pr-full` adds `pr-security`. [Target graph](https://github.com/neuron7x/sapolsky-behave-layers/blob/861718751198deeeda54a23efacb2227a819b49f/Makefile.cwc#L20-L42). |
| `make -f Makefile.cwc verify-evidence` | Runs the CNEH history guard and checks discovered `SHA256SUMS` bundles. Recursion starts from manifests that exist. Completeness and missing-manifest rejection require an explicit roster or another gate. [Checksum recipe](https://github.com/neuron7x/sapolsky-behave-layers/blob/861718751198deeeda54a23efacb2227a819b49f/Makefile.cwc#L231-L242) · [history guard](../../scripts/cneh_history_guard.py). |
| `make -f Makefile.cwc reproduce-primary` | Regenerates eight WP4 seeds in temporary storage, analyzes the run and checks the synthetic verdict and tolerance. Archive verification is performed by `verify-evidence` separately. [Replay script](https://github.com/neuron7x/sapolsky-behave-layers/blob/861718751198deeeda54a23efacb2227a819b49f/scripts/reproduce_primary.py#L25-L51). |
| `make -f Makefile.cwc doc-gate` | Bibliography, temporal preregistration and documentation status checks. `docs-regen` updates the machine-generated ledger and document register. Hosted doc gates additionally compare regenerated files and run evidence checks. [Make targets](https://github.com/neuron7x/sapolsky-behave-layers/blob/861718751198deeeda54a23efacb2227a819b49f/Makefile.cwc#L120-L175) · [workflow](https://github.com/neuron7x/sapolsky-behave-layers/blob/861718751198deeeda54a23efacb2227a819b49f/.github/workflows/cwc-doc-gates.yml#L30-L43). |

In an isolated CPU checkout with full history, the expert workflow installs the frozen runtime and hash-pinned development tools, then runs:

```bash
uv sync --frozen --extra cpu
uv pip install --python .venv/bin/python --require-hashes --only-binary :all: --default-index https://pypi.org/simple -r requirements/cwc-dev.lock
make -f Makefile.cwc pr-full COVERAGE_FAIL_UNDER=91
```

The security target invokes pinned Docker tooling and current dependency advisories. Record interpreter, dependency lock, hardware profile and external advisory availability with the result. [Expert workflow](https://github.com/neuron7x/sapolsky-behave-layers/blob/861718751198deeeda54a23efacb2227a819b49f/.github/workflows/cwc-full-pr-gate.yml#L75-L120) · [security targets](https://github.com/neuron7x/sapolsky-behave-layers/blob/861718751198deeeda54a23efacb2227a819b49f/Makefile.cwc#L38-L77).

## Hosted selection and identity

- **All-PR expert workflow.** `cwc-full-pr-gate` runs for PRs and manual dispatch. Separate jobs exercise CNEH promotion, bounded adversarial seeds and the isolated fractal project. Its full verification job runs `pr-full`.
- **General sweeps.** `cwc-doc-gates` runs on branch pushes and PRs. `cwc-quality` is path-filtered. `pr-audit` and CodeQL have their own event and path selectors. Read every relevant job and step, including explicit skips.
- **Experiment qualification.** JOINT-LP, source intake and other specialized workflows have separate path and proof contracts. A documentation-only diff may leave an experiment workflow untriggered. A code carryover check can establish identical scoped bytes. Full-tree equivalence requires equal Git tree OIDs.

For a PR receipt record PR head, base, tested checkout, tree, run ID, attempt, job and artifact SHA-256. Use `PASS` after the required steps completed successfully for that identity. Preserve `FAIL`, `SKIPPED`, `NOT_RUN` and unresolved outcomes as distinct states. Record scientific authority separately. [JOINT-LP workflow](https://github.com/neuron7x/sapolsky-behave-layers/blob/861718751198deeeda54a23efacb2227a819b49f/.github/workflows/cneh-joint-lp.yml#L20-L115) · [scientific admission](../../scripts/cneh_promotion_gate.py).

## Worked provenance example

| Observation | Exact identity and boundary |
| --- | --- |
| Integrated main push | `861718751198deeeda54a23efacb2227a819b49f`, tree `1386cbc5cb9f1c93f38665671b21745cf3a7b0f1`. Four workflows completed successfully. The quality job recorded 179 passed, 9 skipped, 4 deselected, 86% scoped branch coverage and 12/12 selected mutants killed. [Quality run](https://github.com/neuron7x/sapolsky-behave-layers/actions/runs/45665330496) · [doc run](https://github.com/neuron7x/sapolsky-behave-layers/actions/runs/45665330403) · [audit run](https://github.com/neuron7x/sapolsky-behave-layers/actions/runs/45665330487) · [CodeQL run](https://github.com/neuron7x/sapolsky-behave-layers/actions/runs/45665330493). |
| PR #89 full gate and JOINT-LP | PR head `4607b88792dc8dd1bb01130c841e512ecee15fbc`, base `bdc3d736692aeb1362c12918afc022fa11c7ca2c`, tested checkout `1d343eb0a289c773553aa8ea4166243523c42fc2`, tree `fb62831f6605a62fe07f5f595fd5a5e3cb93ad91`. Its whole tree differs from the integrated push. [Full gate](https://github.com/neuron7x/sapolsky-behave-layers/actions/runs/45593809216/job/139134523674) · [aggregate](https://github.com/neuron7x/sapolsky-behave-layers/actions/runs/45593809355/job/139134865855). |
| JOINT-LP attempt 1 | CPython 3.12.16 on x86_64 and aarch64. Four process receipts and a fresh reconstruction agree on payload SHA-256 `f67215d0de14f0e8c98106ebf055e516e9b6ecc8a7f38985206c8b6ee5ca836f`. The unique panel contains 64 toy target checks, 32 compatible records, 8 certified exclusions and 18 rejected mutations. Architecture totals repeat the same panel. Scientific promotion is blocked. [Aggregate receipt](https://github.com/neuron7x/sapolsky-behave-layers/actions/runs/45593809355/job/139134865855). |
| REAL-TRANSFER-01 source stage | Three frozen source payloads and six cohorts were reconstructed. Later custody and inert manifest candidate work retain nonadmission. Model execution and independent scientific replication are `NOT_TESTED`. [Source-intake job](https://github.com/neuron7x/sapolsky-behave-layers/actions/runs/45575157643/job/139071160509) · [manifest scope](../../experiments/cwc_manifest_candidate/PROTOCOL.md). |

[Verification plan](VERIFICATION_AND_VALIDATION_PLAN.md) · [artifact reproduction](../reproducibility/CLEAN_ROOM_REPRODUCTION_PROTOCOL.md) · [architecture](../architecture/CWC_ARCHITECTURE.md).
