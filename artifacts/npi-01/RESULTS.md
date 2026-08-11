# NPI-01 Results — First-Order Nullspace Inhibition

Verdict: `NPI_01_FIRST_ORDER_CERTIFICATE_NOT_SUPPORTED`

## Frozen construction

Observation: `y(u,v)=u`; invisible direction: `v`; action-value difference: `Delta_K=1-Kv^2`.

At `theta0=(0,0)` every family member has the same first-order certificate: positive margin `1`, `J=[1,0]`, nullspace `span(e_v)`, zero action-value gradient, and zero projected score.

For each frozen radius `r`, the preregistered construction uses `K=8/r^2` and `theta_prime=(0,r/2)`, which is observationally identical and strictly inside the radius, yet gives `Delta(theta_prime)=-1` exactly.

## Exact execution

| radius | K | distance | observation equal | score zero | action reversed |
|---:|---:|---:|:---:|:---:|:---:|
| 1/1 | 8/1 | 1/2 | True | True | True |
| 1/10 | 800/1 | 1/20 | True | True | True |
| 1/100 | 80000/1 | 1/200 | True | True | True |
| 1/10000 | 800000000/1 | 1/20000 | True | True | True |
| 1/100000000 | 80000000000000000/1 | 1/200000000 | True | True | True |

All 5/5 radii satisfy the counterexample.

Preregistered semantic mutations killed: `6/6`.

## Interpretation

The strong first-order certificate is false. The failure is higher-order: local first-order action sensitivity can be exactly zero while curvature along an observationally invisible causal direction reverses the optimal action arbitrarily close to the reference point. Therefore first-order nullspace projection cannot by itself authorize action with a universal positive safety radius.

## Boundary

This does **not** refute identifiability-aware inhibitory control. A successor must carry a curvature/Hessian bound or solve a set-valued robust decision problem over the observational equivalence class.
