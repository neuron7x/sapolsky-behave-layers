# CSCA-01A — Exploratory Counterfactual-Model Adequacy Diagnostic

Date: 2026-08-10

## Governance status

`EXPLORATORY_DIAGNOSTIC_NO_H4_PROMOTION_AUTHORITY`.

This diagnostic was preregistered and committed before execution, but it was generated after
CSCA-01 and did not receive a separate experiment-specific human H4 approval. Under ACT-R&D-02 it
therefore cannot create an architecture claim or promotion. It is retained as a mechanistic
boundary and candidate for a later human-approved confirmatory test.

## Result

For the misspecified linear counterfactual model

`Y_hat = beta_hat*A + alpha*C`,

with symmetric intervention baseline, exhaustive evaluation matched the analytic identities to
maximum error `8.33e-17`:

- `|phi_A| = |beta_hat|`;
- `|phi_C| = |alpha|`;
- false-credit mass = `|alpha|/(|beta_hat|+|alpha|)`;
- the spurious candidate `C` outranks the true candidate `A` whenever `|alpha|>|beta_hat|`.

Examples:

- `beta_hat=1.0, alpha=0.25` -> false-credit mass `0.20`;
- `beta_hat=1.0, alpha=1.0` -> tie / false-credit mass `0.50`;
- `beta_hat=0.5, alpha=1.25` -> spurious `C>A` / false-credit mass `0.7143`.

## Meaning

This does not show that Shapley is defective. It shows the precise opposite: exact Shapley
faithfully attributes the **counterfactual model it is given**. Therefore a structurally wrong
counterfactual simulator produces structurally wrong causal credit.

The next claim-bearing experiment must estimate or bound counterfactual-model error and test
whether uncertainty-aware credit abstention prevents false consolidation under model
misspecification.
