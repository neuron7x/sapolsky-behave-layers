# Formal Identifiability Certificate

Status: normative mathematical contract; no empirical claim is created by this document.

## Purpose

CWC already distinguishes factual, predictive, assumption-conditional, and intervention-supported authority. This contract adds a stricter precondition: a mechanism may not receive an identifiability claim unless the declared observation/intervention channel can, in principle, distinguish the admitted alternatives.

The certificate is deliberately narrower than "the model is true". It answers only whether the declared candidate family is distinguishable under the declared channel and tolerance.

## 1. Finite candidate families

Let `M={m_1,...,m_k}` be a finite set of candidate mechanisms, `A` a finite set of interventions, and `P_m(.|do(a))` a discrete outcome law for candidate `m` under intervention `a`.

For a pair `(m_i,m_j)` and action `a`, define total-variation separation

`TV_a(i,j) = 0.5 * sum_y |P_i(y|do(a)) - P_j(y|do(a))|`.

For a chosen action set `D subseteq A`, define pair separation

`delta_D(i,j) = max_{a in D} TV_a(i,j)`

and the family margin

`delta_min(D) = min_{i<j} delta_D(i,j)`.

### Finite identifiability predicate

At numerical tolerance `eps`, the finite family is distinguishable by `D` iff every pair has at least one separating action:

`forall i<j, exists a in D: TV_a(i,j) > eps`.

Equivalently, `delta_min(D) > eps`.

If the predicate fails, the gate MUST return the unresolved model pairs. No estimator, optimizer, larger neural network, or additional training on the same channel can convert those observationally equivalent pairs into an identified mechanism without adding assumptions or a new observation/intervention channel.

This is a finite-family channel property, not a statement that finite data will achieve a desired statistical power.

## 2. Minimum separating intervention design

Given positive intervention costs `c(a)`, find the non-empty subset `D` that separates every candidate pair while minimizing, in order:

1. total intervention cost `sum_{a in D} c(a)`;
2. number of selected interventions;
3. deterministic lexical action order for tie-breaking.

For the small candidate families used as CWC preflight gates, exhaustive subset enumeration is the reference implementation. If no subset separates all pairs, the result is `NOT_IDENTIFIABLE_UNDER_DECLARED_CHANNEL`.

## 3. Local first-order identifiability for continuous parameters

Let a differentiable observable mean map be `mu(theta) in R^q` with parameter vector `theta in R^p`. At a declared operating point `theta_0`, let

`J = d mu(theta) / d theta |_{theta_0}`.

The implementation certifies only **local first-order identifiability**:

`rank(J) = p`.

If `rank(J) < p`, the right null space of `J` contains first-order parameter perturbations that the declared mean channel cannot observe. The certificate MUST return a numerical basis for those null directions.

If a positive-definite observation covariance `Sigma` is declared, the local information matrix is

`F = J^T Sigma^{-1} J`.

The certificate reports its minimum eigenvalue and condition number as conditioning diagnostics. Positive definiteness of `F` is equivalent to full column rank of the whitened Jacobian; it does not establish global nonlinear identifiability or causal validity.

## 4. Fail-closed boundaries

The gate MUST NOT promote causal authority from any of the following:

- full rank alone;
- a positive finite-family separation margin alone;
- numerical conditioning alone;
- an optimizer finding one parameter vector;
- agreement on factual data without a separating intervention;
- a model class whose omitted alternatives are not represented.

The output is therefore one of:

- `FINITE_IDENTIFIABLE_UNDER_DECLARED_CHANNEL`;
- `NOT_IDENTIFIABLE_UNDER_DECLARED_CHANNEL`;
- `LOCAL_FIRST_ORDER_IDENTIFIABLE`;
- `LOCAL_FIRST_ORDER_NOT_IDENTIFIABLE`.

## 5. Mandatory falsification cases

The executable gate must reject or expose:

1. duplicate finite mechanisms;
2. a candidate pair separated only by an omitted intervention;
3. zero/negative intervention costs;
4. malformed probability laws;
5. rank-deficient Jacobians;
6. nearly singular but formally full-rank Jacobians as ill-conditioned rather than rank-deficient;
7. non-positive-definite covariance matrices;
8. row/column relabellings that incorrectly change the semantic verdict.

## 6. Promotion rule

This certificate is a preflight gate. Passing it permits an experiment to proceed; it never upgrades a scientific hypothesis by itself. Empirical authority still requires preregistration, execution, evidence binding, negative controls, replication, and the experiment-specific promotion predicate.

## 7. CWC Boolean counterfactual basis: orthogonal intervention design

The current counterfactual families use distinct multilinear monomials over the five
binary coordinates `(A,C,D,B,context) in {-1,+1}^5`. On the complete 32-state
intervention cube, any two distinct monomials are orthogonal: their product is a
non-constant parity character and sums to zero over the cube. Every monomial has squared
norm 32. Therefore, for every declared CWC basis that is a subset of these distinct
characters,

`X^T X = 32 I`.

This is stronger than full column rank. Under the declared basis it gives exact equal
norms, zero cross-term correlation, and Gram condition number 1. The executable gate
checks this identity for `LINEAR`, `CONTEXT`, and `NONLINEAR` rather than assuming it.

The factual restriction `C=A` destroys the full cube. The same gate requires that this
restricted channel lose rank and return explicit null directions. Thus the repository
contains both a positive structural control (orthogonal full intervention design) and a
negative control (confounded factual slice) for identifiability machinery.
