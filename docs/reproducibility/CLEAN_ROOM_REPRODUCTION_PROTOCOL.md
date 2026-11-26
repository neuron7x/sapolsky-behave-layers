# Clean-Room Reproduction Protocol

## Conditions
Fresh checkout · fresh container · no author-local paths · no manual edits · no hidden
credentials · source/data hash verification · separate output dir · no overwrite of
canonical artifacts · automatic verdict · automatic checksum verification.

## Commands and scope

Use a fresh checkout with full Git history and record its commit and tree. Install
runtime and development dependencies using the [test and CI reference](../vnv/CWC_TEST_AND_CI_REFERENCE.md).

```bash
make -f Makefile.cwc verify-evidence
make -f Makefile.cwc reproduce-primary
```

The first target verifies the history guard and archives with discovered manifests.
The second checks the frozen WP4 manifest and listed bytes, regenerates eight
seeded WP4 runs in temporary storage, and checks the synthetic verdict and tolerance. Retain the command log as a receipt.
Use `verify-full` to include both operations in the wider test suite.

## Containers
The recipes in `containers/` retain their historical scope. The CPU recipe can fall
back after a failed frozen sync. Container build, restore and clean-room evidence
remain open. The [hosted expert workflow](../../.github/workflows/cwc-full-pr-gate.yml)
records its locked CPU checkout separately.

## Status
`make reproduce-primary` exists and regenerates the WP4 primary result. Full
fresh-container reproduction is `NOT_VALIDATED` until an independent operator runs it on
a clean machine (see `docs/risk/EXTERNAL_REVIEW_AND_INDEPENDENCE_PROTOCOL.md`). This is
the honest current gap.

## Acceptance
Record the exact checkout and runtime, exit codes for archive verification and
replay, manual edits, and the regenerated verdict and tolerance check. An external
reproduction receipt identifies its operator and environment.
