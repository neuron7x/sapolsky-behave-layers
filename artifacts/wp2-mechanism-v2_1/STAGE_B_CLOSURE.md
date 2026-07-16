# Stage B (inferred-label) collapse — diagnosis & closure

The named next step after A3.1 was to fix Stage B collapse (unsupervised
routing when the task type must be inferred from content, 6/8 seeds with
lb=0.01). Three interventions tested, all preregistered as anti-collapse
attempts:

| Intervention | Result |
|---|---|
| Load-balance coef tuning (0.01 → 0.03 → 0.10) | **Trade-off, not a fix** — each coef rescues some collapsed seeds while collapsing others; no value gets ≥7/8. |
| Router-logit exploration noise (σ=0.5, 1.0) | **Harmful** — enough noise to escape collapse also destroys the routing signal; ALL seeds collapse. |
| Decaying route-supervision (diagnostic, Act §11) | **8/8 converge** (6 perfect, s3=0.955, s6=0.854). |

## Conclusion (diagnostic)
The route-supervision diagnostic — a weak CE(route_logits, true_label) term
that decays to zero by mid-training — makes **all 8 Stage-B seeds converge to
correct inferred routing**. Per Act §11 this is a SEPARATE diagnostic run,
reported apart from the unsupervised causal run; it does not count toward the
claim.

What it proves: the Stage-B failure is an **optimization / initialization**
problem (a constant-policy collapse attractor in unsupervised straight-through
top-1), **NOT** a capacity or mechanism deficit. The controller can represent
and execute perfect content-inferred routing; it simply does not reliably
*find* that solution from a cold start without a marker.

## Honest status
- Stage A (observable marker): A3 ROUTING_CAUSALITY_SUPPORTED, 8/8 (claim tier).
- Stage B (inferred), **unsupervised**: 6/8 — remains NOT_SUPPORTED at claim
  tier; simple anti-collapse tricks do not reliably fix it.
- Stage B, **route-supervised diagnostic**: 8/8 — mechanism & capacity proven;
  failure is optimization only.

Full A3 (both stages unsupervised) is therefore NOT passed; maturity cap 59
stands. The remaining work is a better unsupervised optimizer for the inference
regime (e.g. importance-weighted router warm-up, or a controller architecture
with a stronger inductive bias for content-based gating) — not more capacity.
The `ROUTER_NOISE` knob is retained in the model (default 0.0) but documented
here as ineffective for this collapse.
