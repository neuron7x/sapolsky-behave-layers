# NeurIPS 2026 Submission Checklist (self-assessment)

| Item | Answer | Evidence |
|---|---|---|
| Claims match theory & experiments | Yes | claim_registry.json ⟷ VALIDATION_RECORD |
| Limitations discussed | Yes | LIMITATIONS_BROADER_IMPACTS_AND_ENVIRONMENT.md |
| Theory: assumptions & proofs | Yes | docs/IDENTIFIABILITY_THEORY.md |
| Reproducibility: code released | Yes | full repo + `make reproduce-primary` |
| Data: synthetic generators disclosed | Yes | DATASET_REGISTER.yaml, DATA_MANAGEMENT_AND_SHARING_PLAN.md |
| Experimental detail | Yes | PREREGISTRATION*.md per experiment |
| Error bars / statistical significance | Yes | STATISTICAL_ANALYSIS_PLAN; bootstrap CIs in analyzers |
| Compute resources reported | Yes | EXPECTED_RUNTIME_HARDWARE_AND_COST.md |
| Broader impacts | Yes | LIMITATIONS_BROADER_IMPACTS_AND_ENVIRONMENT.md |
| Safeguards / high-risk release | N/A | LOCAL_RESEARCH_ONLY, no dual-use surface |
| Existing assets credited | Yes | THIRD_PARTY_NOTICES.md, CITATION.cff |
| Systematic related-work search | **PENDING** | RELATED_WORK_AND_NOVELTY_REVIEW.md (must complete before submission) |
| Independent replication | **No** | CWC-L8 = NOT_TESTED |

**Not submission-ready** until the related-work search is completed and (for any
architectural claim) the compute-equivalent Pareto experiment is run.
