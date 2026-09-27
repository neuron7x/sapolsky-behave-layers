# DGC Mathematical Hardening v2b — Drift and Myopic Error Bounds

Status: **narrow mathematical closure; not a general nonstationary or optimal-metareasoning solution**.

## P17 — bounded-drift current-mean lower confidence bound

Let independent observations `X_i in [L,H]` have possibly different means `mu_i`. Let `mu_*` be the current target mean and suppose an external drift contract certifies

\[
|\mu_i-\mu_*|\le d_i.
\]

Hoeffding concentration for independent bounded variables (identical distributions are not required) gives with probability at least `1-delta`

\[
\frac1n\sum_i \mu_i \ge \bar X-(H-L)\sqrt{\frac{\log(1/\delta)}{2n}}.
\]

Since `mu_* >= n^{-1} sum_i mu_i - n^{-1} sum_i d_i`, DGC obtains

\[
\boxed{\mu_* \ge \bar X-(H-L)\sqrt{\frac{\log(1/\delta)}{2n}}-\bar d}.
\]

The drift envelope must be independently justified. Estimating a convenient `d_i` from the same outcomes is unauthorized. Dependence, unknown change points and adversarial drift outside the envelope remain open.

Implementation: `cwc/governance/nonstationary.py`.

## P18 — perfect-information upper bound on myopic metareasoning error

For finite **pure-information** compute sequences with non-negative compute costs, let `V_1(s)` be the one-step/myopic metalevel value and `V_PI(s)` an authoritative upper bound on object-level value after perfect revelation of the latent world. Any finite-horizon metapolicy satisfies

\[
V_h(s)\le V_{PI}(s),
\]

and therefore

\[
\boxed{0\le V_h(s)-V_1(s)\le \max(0,V_{PI}(s)-V_1(s)).}
\]

This is intentionally loose: it bounds myopic error but does not solve the meta-MDP. It is invalid for compute that causally changes the world, utility, or legal action set.

Implementation: `cwc/governance/metareasoning_bounds.py`.

## Prior-art boundary

Value-of-computation and rational metareasoning substantially predate DGC: Russell & Wefald, *Principles of Metareasoning* (Artificial Intelligence, 1991), and Hay, Russell, Tolpin & Shimony, *Selecting Computations: Theory and Applications* (UAI 2012 / arXiv:1207.5879) are direct foundational references. DGC claims no novelty for VOC itself.
