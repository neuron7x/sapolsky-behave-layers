# Data Management and Sharing Plan (DMP)

## Nature of CWC data
CWC's confirmatory experiments use **synthetic, procedurally-generated data**, not
collected corpora. The "datasets" are deterministic **generators** in the codebase,
seeded explicitly; there is no PII, no scraped content, and no licensing encumbrance on
the generated examples.

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

## Real-workload data (future, NOT_TESTED)
When real workloads are introduced (RQ-pareto), each must gain a full dataset card,
license record, contamination check, and split policy **before** any confirmatory run.
