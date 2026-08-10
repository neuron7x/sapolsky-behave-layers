# CSCA-04-SA — Post-primary Integrity Note 001

Primary and independent replication used only the preregistered `BALANCED` selector; that selector never reads intervention outcomes during allocation.

Before running the predeclared **secondary** allocation-strategy comparison, an integrity audit found that the `DISAGREEMENT_ONLY` sort used `probe.effect` only as a deterministic tie-break key. Although it did not affect the authoritative BALANCED cohorts, any outcome-dependent tie-break is invalid for a prospective intervention scheduler.

The secondary selector is corrected to tie-break only on immutable pre-intervention base variables. PRIMARY and replication artifacts remain unchanged and are not rerun or rescued by this change.
