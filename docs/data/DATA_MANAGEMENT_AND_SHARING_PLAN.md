# Data Management and Sharing Plan (DMP)

## Synthetic generator experiments
The entries below describe the historical controlled generator experiments. These
procedurally generated examples use source and seeds. External sources follow the
separate rules below.

| Field | Value |
|---|---|
| Data types | synthetic token sequences + structural labels |
| Sources / generators | `experiments/*/src/task_*.py` (e.g. `task_semantic_route.py`, `task_hops.py`, `surface_matched_task.py`) |
| Formats | in-memory torch tensors; artifacts as JSON/JSONL |
| Schema | per-generator; see `DATASET_REGISTER.yaml` and `DATA_DICTIONARY.md` |
| Volume | generated on demand; nothing persisted beyond artifacts |
| Storage | local repo `artifacts/`; full backup `~/CWC_CONSOLIDATION_BACKUP_2026-07-16/` |
| Provenance | generator commit + seed fully determine every example |
| Encryption | not required (non-sensitive synthetic data) |
| Retention | evidence bundles retained immutably (SHA256SUMS); negatives frozen in `artifacts/history/` |
| Backup / recovery | repo + backup dir + release archives |
| Access control | local; no credentials embedded |
| Sharing | code + generators are MIT; regenerating any dataset needs only the commit + seed |
| Deletion | frozen negatives are never deleted |
| Licensing | MIT (generated data), upstream nanochat separately |

## External workload custody and access

REAL-TRANSFER-01 has reconstructed AVeriTeC and HybridQA source bytes and fixed cohort
identities. The manifest candidate is inert. Model execution and scientific transfer
remain open. Source custody controls record pinned source identity, published license notices and
attribution candidates, the actual cohort assignment, and the audited tree. Recheck
admission after tree or source changes.

Controlled source bytes stay in the permitted acquisition environment. Share only
metadata, checksums and artifacts when terms permit. Do not assume the repository's
MIT license applies to third-party data, upstream models or linked text. Record the
actual use purpose, applicable terms and exceptions, personal data handling, access,
retention and disposition before authorizing use or redistribution. A repository
literal-collision check has a scoped corpus and cannot establish training provenance.

[Source contract](../../experiments/real_transfer_01/INTAKE_CONTRACT.md) ·
[candidate policy](../../experiments/cwc_manifest_candidate/PROTOCOL.md) ·
[terms and compute review](../../experiments/cwc_manifest_candidate/TERMS_AND_COMPUTE_REVIEW.md).
