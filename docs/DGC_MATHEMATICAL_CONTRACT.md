# DGC Mathematical Contract v1

Status: **normative engineering mathematics; no empirical superiority claim**.

## 1. Decision object

Let `A` be a finite legal action set, `W` an admitted set of worlds/countermodels, and `U(w,a)` a finite utility/loss-transformed utility fixed independently of the governor. Let `a0` be the currently authorized action.

For perturbation/world `w_i'` define

\[
a_i^* \in \arg\max_{a\in A} U(w_i',a),\qquad
R_i = U(w_i',a_i^*) - U(w_i',a_0).
\]

The implementation uses deterministic lexicographic tie breaking for replay, but the regret statement is tie-invariant.

### Proposition P1 — non-negative regret

For every admitted perturbation, `R_i >= 0`.

**Proof.** `a_i*` maximizes `U(w_i',a)` over `A`; therefore `U(w_i',a_i*) >= U(w_i',a0)`. Subtraction gives the result. QED.

### Proposition P2 — action invariance kills decision regret

If `a0` is optimal in every admitted perturbation, then `R_i = 0` for every `i`, hence every non-negative weighted average of these regrets is zero.

This is the exact mathematical statement behind “uncertainty can be high while additional decision-directed compute has zero value.” It does **not** state that all information is worthless; only that information whose sole purpose is changing the current action has zero immediate action value under the declared world set and utility.

## 2. DGC sensitivity functional

For declared non-negative scenario weights `q_i`, not assumed probabilistic unless separately calibrated,

\[
\widehat G_D = \frac{\sum_i q_iR_i}{\sum_i q_i},\qquad \sum_i q_i>0.
\]

This is a weighted counterfactual decision-regret sensitivity functional. It is **not** a differential gradient without a perturbation geometry, direction and normalization.

The runtime additionally retains

\[
R_{max}=\max_i R_i,
\]

because an expectation-like scalar can hide a low-weight/high-loss reversal.

## 3. One-step value of computation

Let a candidate computation `c` produce an observation `Y` and permit a post-computation policy `a(Y)`. Under a declared probabilistic model,

\[
VOC(c\mid s)=
\mathbb E[U(W,a(Y))\mid s,c]
- \max_a\mathbb E[U(W,a)\mid s]
- Cost(c).
\]

### Proposition P3 — exact perfect-diagnostic rule

In DGC-01 the diagnostic perfectly reveals the hidden world and has fixed scalar cost `k`. Therefore

\[
VOC = EVPI-k
= \mathbb E[R(W;a_0)]-k.
\]

Among the two meta-actions `{STOP, BUY_DIAGNOSTIC}`, buying is Bayes-optimal iff `VOC>0`, assuming the declared prior, utility and cost are correct.

This is a theorem of the **synthetic decision model**, not evidence that an estimated real-world VOC is correct.

## 4. Conservative compute admission

The runtime admits an operation only when

\[
LCB(VOC)>m_{risk}\ge0
\]

and the hard resource budget permits the operation. The code rejects a scalar-cost mismatch between the operation contract and its VOC estimate. Therefore a caller cannot increase estimated VOC merely by reporting a lower cost inside the estimator.

### Proposition P4 — admission safety invariant

Given `ComputeGovernor.select`, every returned non-STOP operation satisfies all of:

1. an estimate exists for the same operation id;
2. `estimate.total_cost == operation.estimated_cost` within the frozen numeric tolerance;
3. every hard resource dimension admits the spend;
4. the conservative VOC lower bound exceeds the applicable margin.

This is a program invariant covered by unit tests; it is not a claim that the supplied lower bound itself is statistically valid.

## 5. Anytime-valid sequential inference

The first executable sequential contract supports only a frozen i.i.d. bounded draw process. Let `X_n in [L,H]` and choose total error probability `delta`. Spend

\[
\delta_n=\frac{6\delta}{\pi^2n^2}.
\]

At each fixed `n`, Hoeffding gives a two-sided interval with failure probability at most `delta_n` and half-width

\[
r_n=(H-L)\sqrt{\frac{\log(2/\delta_n)}{2n}}.
\]

Because

\[
\sum_{n=1}^{\infty}\delta_n=\delta,
\]

a union bound yields

\[
\Pr\left(\forall n\ge1:\mu\in CI_n\right)\ge1-\delta.
\]

### Proposition P5 — optional stopping validity under the contract

For any stopping time `tau` measurable with respect to the observed i.i.d. sequence,

\[
\Pr(\mu\in CI_\tau)\ge1-\delta.
\]

This follows immediately from simultaneous coverage over all `n`. The implementation refuses `SamplingMode.ADAPTIVE`; adaptive perturbation selection requires a separately justified e-process/martingale construction.

The stitched Hoeffding CS is intentionally conservative. It is selected for auditability, not statistical efficiency.

## 6. Hard-budget monotonicity

For each resource dimension `r`, let hard limit `B_r` and accumulated spend `S_r`. `BudgetLedger.spend` can only return a successor with

\[
S'_r=S_r+c_r,\quad c_r\ge0,\quad S'_r\le B_r.
\]

No method mutates `B_r`; the dataclass is frozen. Therefore internal spending is monotone and self-escalation through the ledger API is impossible.

## 7. Bounded scheduling

The serving boundary implements two independent constraints:

- `in_flight <= max_concurrency`;
- token-bucket consumption cannot exceed the externally declared refill process.

A retry does not bypass either state variable. Scheduler admission is not cognition-value evidence; it is only a serving constraint.

## 8. Proof-carrying action

External action certificates bind by SHA-256:

- decision id and selected action;
- decision-gradient digest;
- world-set and utility digests;
- governor digest;
- budget before/after digests;
- evidence ids;
- metered compute spent;
- terminal reason.

Telemetry uses a previous-event digest chain. These mechanisms detect mutation relative to the detached recorded digest; they do not prove semantic truth of the underlying evidence.

## 9. Conditions that kill DGC claims

Any of the following invalidates a broad “DGC is rational/optimal” claim:

1. misspecified or strategically mutable utility;
2. perturbation/world set omits an action-reversing world;
3. scenario weights are treated as probabilities without calibration/provenance;
4. VOC estimator is biased or its confidence bound is invalid under the sampling policy;
5. compute cost is incomplete or moved into an unmetered subsystem;
6. diagnostic changes the world rather than merely informing the decision and this causal effect is omitted;
7. non-stationarity invalidates the frozen model before action;
8. abstention/coverage changes are not priced;
9. tail loss matters but only mean regret is optimized;
10. meta-computation itself consumes enough resource to erase the estimated gain.

DGC therefore remains an engineering hypothesis about **compute admission under explicit contracts**, not a universal theory of cognition.
