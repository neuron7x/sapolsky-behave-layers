# WP18 Route-Cost Dimensional Correction — 2026-08-11

Status: CURRENT EPISTEMIC CORRECTION. Historical artifacts remain immutable.

## Defect

WP17 reports `rho_flops_encoder_router = router_flops / model_K1_flops`, a dimensionless ratio of routing FLOPs to one `K=1` model forward (`0.0005896226415094339`).

WP18 defines per-action utility inside `_cert` as:

`U = -loss - lambda * K / Kmax`.

`G_lo` is therefore in this utility/loss scale. `experiments/wp18_real_workload_pilot/src/analyze.py` then sets `C_ROUTE = 0.0006` and directly tests `G_lo > C_ROUTE`.

That direct comparison is not dimensionally established. A measured FLOP ratio is not automatically an additive loss/utility penalty. Under the specific normalized-compute utility already used by WP18, treating `rho` as an additional `K=1`-equivalent compute fraction would contribute `lambda * rho / Kmax`, not raw `rho`; at `lambda=0` that utility penalty is zero.

## Consequence

The historical preregistered WP18 programme stop decision remains an immutable historical decision. Its negative `G_lo` values also remain evidence that WP18 did not certify a positive adaptive advantage under its conservative lower-bound procedure.

The stronger historical wording "the interaction is worth less than measured routing cost" is not established by WP18 because the cost-to-utility bridge was not unit-consistent. `G_lo <= 0` is failure to certify a positive gap, not proof that the true gap is non-positive.

## Repair

`CWC-FLAGSHIP-ROUTE-01` removes this bridge. It compares candidate cross-entropy directly against the best fixed depth-1/depth-2 Pareto envelope at the candidate's exact logical-FLOP budget and charges router FLOPs explicitly. Its frozen PRIMARY result is `0/6` cell PASS and its verdict is `CWC_FLAGSHIP_ROUTE_01_NOT_SUPPORTED`.

This correction narrows the interpretation of WP18/WP19; it does not rewrite their frozen artifacts or retroactively change their recorded historical verdicts.
