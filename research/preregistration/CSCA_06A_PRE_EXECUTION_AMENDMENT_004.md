# CSCA-06A Pre-execution Amendment 004 — burned confirmatory cohorts

After Amendment 003 repaired the import path, an accidental `--help` invocation executed the runner because it has no CLI parser. This occurred before the repair commit. The generated 61000/71000 outputs are sealed as `INSTRUMENT_PROVENANCE_INVALID_PRECOMMIT_EXECUTION`, excluded from analysis, and their scientific values are not used.

To preserve prospective separation, the 61000/71000 cohorts are permanently burned. Authoritative PRIMARY now starts at 81000 and REPLICATION at 91000. No family, alpha, metric, threshold, budget, nuisance envelope, test density, or qualification predicate changed.
