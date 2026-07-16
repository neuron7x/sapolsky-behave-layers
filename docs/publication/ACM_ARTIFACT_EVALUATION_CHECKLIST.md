# ACM Artifact Evaluation Checklist (self-assessment)

## Gate A — Functional
| Criterion | Status | Evidence |
|---|---|---|
| Documented | Yes | ARTIFACT_README.md, SYSTEM.md |
| Consistent | Yes | claims ⟷ artifacts ⟷ verdicts (doc-gate) |
| Complete | Yes | all shipped results have bundles + SHA256SUMS |
| Exercisable | Yes | `make experiment-tests` (69), `make verify-evidence` (11) |
| Verified | Yes | VERIFICATION_RECORD.md |
| Validated | Yes | VALIDATION_RECORD.md |

## Gate B — Reusable
| Criterion | Status |
|---|---|
| Modular structure | Yes (cwc/ experiments/ scripts/ schemas/) |
| Stable interfaces | Partial (experiment runners are research-grade) |
| Data dictionary + schemas | Yes |
| Examples + extension points | Partial |
| Versioning | Yes (CHANGELOG, CITATION) |
| Test suite | Yes |

## Gate C — Available
| Criterion | Status |
|---|---|
| Persistent public repository | **PENDING** (GitHub org suspended — see SYSTEM.md) |
| Immutable version | Yes (commit + release archive) |
| DOI / identifier | **PENDING** (ARCHIVAL_AND_PERSISTENT_IDENTIFIER_PLAN.md) |
| License | Yes (MIT) |

## Gate D — Results Reproduced
**NOT claimable** — requires an independent operator (CWC-L8 = NOT_TESTED).
