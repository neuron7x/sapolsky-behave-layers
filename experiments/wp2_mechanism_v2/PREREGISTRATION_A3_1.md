# A3.1 — Anti-collapse re-run (preregistered before analysis)

Named as the next decisive step in `artifacts/wp2-mechanism-v2/FINAL_REPORT.md`.
A3 failed claim-tier reliability (2-3/8 seeds hit a straight-through collapse
attractor). Fix: Switch-style load-balance auxiliary loss
`L_aux = coef * 2 * sum_i f_i * P_i` (f = batch fraction dispatched to block i,
P = mean gate prob), which penalizes constant-policy collapse.

Coefficient FROZEN at lb_coef=0.01 (chosen on Stage-A seeds 0,3,7 — the three
that previously collapsed — all three converged to route~T=1.0). Now applied
UNCHANGED to all 8 seeds, both stages.

Hypothesis: >=80% of seeds converge to adaptive routing (acc>0.9, route~T>0.9)
with interventions still confirming causality. If met, A3 PASSES -> routing
causality supported -> maturity cap lifts from 59 to 86 -> A4 (RCFR) unblocks.
Controls (random/frozen/fixed/oracle) are unchanged from v2; reused for parity.
No threshold changed after seeing the 8-seed result.
