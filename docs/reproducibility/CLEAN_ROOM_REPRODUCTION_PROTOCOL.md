# Clean-Room Reproduction Protocol

## Conditions
Fresh checkout · fresh container · no author-local paths · no manual edits · no hidden
credentials · source/data hash verification · separate output dir · no overwrite of
canonical artifacts · automatic verdict · automatic checksum verification.

## One command
```bash
make -f Makefile.cwc reproduce-primary
```
which must: verify source → build environment (`uv sync --frozen`) → verify deps →
generate immutable data (seeded generators) → run the primary experiment → collect raw
outputs → analyze → generate verdict → compare to preregistered tolerance → write a
reproduction report → validate SHA256SUMS.

## Containers
Hermetic builds in `containers/` (`Dockerfile.cpu`, `Dockerfile.cuda`, `apptainer.def`).

## Status
`make reproduce-primary` exists and regenerates the WP4 primary result. Full
fresh-container reproduction is `NOT_VALIDATED` until an independent operator runs it on
a clean machine (see `docs/risk/EXTERNAL_REVIEW_AND_INDEPENDENCE_PROTOCOL.md`). This is
the honest current gap.

## Acceptance
fresh-machine PASS · one-command PASS · manual edits 0 · private paths 0 · checksum
failures 0 · primary result within preregistered tolerance.
