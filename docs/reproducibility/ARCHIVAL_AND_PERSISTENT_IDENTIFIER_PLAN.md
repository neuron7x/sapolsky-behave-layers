# Archival and Persistent-Identifier Plan

## Current state
- **Local immutability:** every evidence bundle carries `SHA256SUMS`; frozen negatives
  live in `artifacts/history/`. Full backup at `~/CWC_CONSOLIDATION_BACKUP_2026-07-16/`
  and a clean substrate zip in `~/Downloads/CWC-FULL-SUBSTRATE-*.zip`.
- **Public archival: PENDING.** The GitHub organization is currently suspended (see
  `SYSTEM.md`), so no public repository or DOI exists yet.

## Plan (on public-release unblock)
1. Push the frozen release (git bundle + `make-release` archives with `RELEASE_MANIFEST.json`).
2. Mint a DOI via Zenodo (or an institutional archive) against the tagged release commit.
3. Record the DOI in `CITATION.cff` and `ARTIFACT_README.md`.
4. Deposit the source + evidence archives (not `.venv`) so the artifact is
   reconstructible via `uv sync --frozen` + `make reproduce-primary`.

Until then, the persistent identifier is the git commit hash + archive SHA-256.
