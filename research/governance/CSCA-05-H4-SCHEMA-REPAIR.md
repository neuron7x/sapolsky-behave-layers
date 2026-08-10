# CSCA-05 H4 schema repair

Date: 2026-08-10
Status: POST-EXECUTION METADATA REPAIR — NO SCIENTIFIC AUTHORITY

`H4-CSCA-05.json` was frozen before authoritative CSCA-05 execution, but it used an ad-hoc field layout rather than the repository canonical `HumanDecision` schema. The scientific design fields were already frozen and are preserved in Git history at commit `1992c58`.

This repair adds only the canonical governance metadata required by `cwc.research_ops.governance.HumanDecision`: `decision_id`, `subject_id`, `reviewer`, `reviewer_role`, `decision`, `rationale`, `evidence_refs`, `created_at`, and `architecture_authority=false`.

It does **not** change the pre-execution primary metric, negative controls, failure predicate, intervention definition, budget calibration rule, or architecture-promotion boundary. It therefore repairs machine validation without retroactively changing the experiment.
