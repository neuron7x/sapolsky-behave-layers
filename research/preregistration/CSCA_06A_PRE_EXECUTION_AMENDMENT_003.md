# CSCA-06A Pre-execution Amendment 003

The first attempted direct script invocation terminated before any experiment data were generated because Python did not place the repository root on `sys.path`. This is an execution-hermeticity defect, not a scientific result.

Repair: the runner now resolves and prepends its repository root before importing `cwc`. No protocol parameter, seed, family, threshold, metric, or budget changed. The failed invocation produced no authoritative artifact.
