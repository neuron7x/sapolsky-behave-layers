# CSCA-08A/B pre-execution repair

The first attempt to start the confirmatory runner failed before loading the experiment because direct script execution did not place the repository root on `sys.path`. No cohort data were generated or inspected. The runner was repaired to insert the resolved repository root exactly as the already-sealed CSCA-07 runner does. No scientific threshold, seed, family, metric, or pass predicate changed. This repair commit remains an ancestor of the first data-bearing execution.
