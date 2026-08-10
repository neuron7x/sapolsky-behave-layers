# CSCA-04-SA — Pre-primary Amendment 003

The first full PRIMARY invocation exceeded the execution window before producing any result artifact. No PRIMARY summary or case record was written.

`Graph Structural Sensitivity` is preregistered as a **secondary diagnostic with no authority**. It was unnecessarily recomputed inside every primary case and dominated runtime. The confirmatory runner now skips GSS computation while leaving every primary decision variable unchanged: intervention probes, IDR, frozen thresholds, context test, coverage, and decision states are identical. GSS is executed later as its own diagnostic on frozen cases.

This is an execution-cost refactor only; it cannot change the primary verdict.
