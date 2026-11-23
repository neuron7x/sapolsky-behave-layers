# CNEH-04-DC — Budgeted Collective Causal Identification and Dual Control

**Status:** formal research hypothesis; mathematical lemmas proven only under explicitly stated assumptions; collective neurocognitive emergence **not established**.

**Replaces:** the unqualified claims of `CNEH-03-DC`. **Domain:** partially observed, nonstationary, controlled stochastic systems with interacting inference modules. **Goal:** test whether interaction creates a causally attributable advantage in safe identification and goal reachability beyond resource-matched alternatives.

## 0. Epistemic contract

- `THEOREM`: mathematical result whose assumptions are stated and whose proof is supplied.
- `DERIVED`: consequence valid only in the specified model.
- `HYPOTHESIS`: pre-registered experimentally refutable claim.
- `NOT_ESTABLISHED`: no promotion to global cognitive or biological laws.
- “Emergence” here is **operational and relative to a fixed comparator class and resource envelope**. An unrestricted simulator with the same physical interfaces cannot in general be outperformed on expressivity alone.

## I. Formal objects and causal architecture

Let `\mathcal X\subseteq\mathbb R^d` denote the physical state, `\Theta\subseteq\mathbb R^p` a frozen admissible parameter family, and `\tau_\star` an unobserved change time. A two-subsystem experiment consists of the *same* physical world and hardware interfaces under all randomized conditions:

\[
 dx_t=f_{\theta_t}(x_t,u_t)\,dt+D_w\,dW_t,\qquad
 dY_{i,t}=h_i(x_t)\,dt+R_i^{1/2}\,dV_{i,t},\quad i\in\{A,B\},
\]

where `\theta_t=\theta_0` before `\tau_\star` and `\theta_t=\theta_1` afterward; the shift class is pre-registered. The Wiener processes are independent across the measurement channels for the additive-information theorem; correlated channels require the full joint noise covariance. `R_i\succ0` denotes an observation-noise *spectral density*, avoiding the invalid continuous-time formula `y(t)=Cx(t)+\text{white noise value}`.

For each module, `b_{i,t}` is its causal belief, `z_{i,t}` its recurrent state, `\Pi_{i,t}` an estimated precision, and `m_{i\to j,t}` a message. An explicit computational-neurodynamics **ansatz**, not an established brain equation, is

\[
\tau_i\dot z_i=-z_i+\sigma_i\!\left(W_i z_i+B_i^{\rm sens}\widehat o_i+G_i\Pi_i\epsilon_i+K_{ji}C_{ji}m_{j\to i}(t-\delta_{ji})\right)+\xi_i,
\]

where the innovation is defined rigorously in stochastic continuous time by `dI_{i,t}=dY_{i,t}-\widehat h_{i,t}\,dt`; its precision-weighted increment is `R_i^{-1}dI_{i,t}`. Any use of a derivative of `dI` is shorthand for a filtered, bandwidth-limited observable. The message/decision process is an adapted (non-anticipative) policy

\[
m_{i\to j,t}=g_i(z_{i,[0,t]},b_{i,t}),\qquad
u_t=\pi_A(b_{A,t},m_{B\to A})+\pi_B(b_{B,t},m_{A\to B}),\qquad
u_t\mapsto u_t\in\mathcal U_{\rm admissible}.
\]

`K` governs *communication/interaction* in the controller; it does **not** magically change fixed physical sensor matrices or physical actuator placements. If an experiment allows `K` to change the plant, this becomes a separate, explicitly modeled manipulation. The complete physical/computational budget is the **vector**

\[
\mathbf B=(B_{u^2},B_{\rm FLOPs},B_{\rm memory},B_{\rm bytes},B_{\rm latency},B_{\rm training}),
\qquad \mathbf C(\pi)\preceq \mathbf B.
\]

For repeated tasks, training is included as `C_{\rm train}/N_{\rm episodes}` and the amortization horizon must be frozen before evaluation. Control effort `\int\|u\|^2dt` is an input-energy proxy, **not necessarily thermodynamic joules**.

## II. Three different operators (no conflation)

Fix a nominal linearized *physical* plant in a local regime

\[
\dot x=A_\theta x+Bu,\quad y_i=C_i x+\eta_i,\quad
A_\theta=A_0+\sum_{j=1}^p\theta_jE_j.
\]

Its finite-horizon matrices for `T>0` are

\[
W_o^{(i)}(T)=\int_0^T e^{A_\theta^\top s}C_i^\top R_i^{-1}C_i e^{A_\theta s}\,ds,\qquad
W_c(T)=\int_0^T e^{A_\theta s}BB^\top e^{A_\theta^\top s}\,ds.
\]

`W_o`: initial-state observability sensitivity in the locally linearized observation model (not in general the exact posterior Fisher matrix if process noise is present). `W_c`: unconstrained deterministic minimum-energy state reachability. Neither describes the experimental *parameter* identification problem by itself. For that define `\mathcal I_\theta(\pi)` from the likelihood of observations conditioned on the actual intervention policy.

### Theorem 1 — complementarity of observation channels

Assume the same finite-dimensional LTI `A_\theta`, `T>0`, and independent sensors with `R_i\succ0`. Let `\mathcal N_i=\bigcap_{k=0}^{d-1}\ker(C_iA_\theta^k)`. Then

\[
\boxed{\ker(W_o^{(A)}+W_o^{(B)})=\mathcal N_A\cap\mathcal N_B.}
\]

**Proof.** For any `v`,

\[
v^\top(W_o^{(A)}+W_o^{(B)})v
=\int_0^T\!\sum_{i=A,B}\|R_i^{-1/2}C_ie^{A_\theta s}v\|^2ds.
\]

The integral vanishes precisely when both analytic functions `C_ie^{A_\theta s}v` vanish on the interval. Their derivatives at zero and Cayley–Hamilton yield `C_iA_\theta^kv=0` for `k=0,\ldots,d-1`. **QED.**

Consequently, the joint system can be locally observable while both channels are individually rank-deficient. This establishes **sensory complementarity**, not an advantage over a centralized controller receiving the same two channels.

### Theorem 2 — exact minimum-input-effort identity

For an unconstrained deterministic LTI system and target displacement `\delta x=x_T-e^{A_\theta T}x_0`:

\[
\boxed{E_{\min}(\delta x)=
\begin{cases}
\delta x^\top W_c(T)^\dagger\delta x,&\delta x\in\operatorname{Im}W_c(T),\\
+\infty,&\text{otherwise}.
\end{cases}}
\]

The minimizing input is `u^*(s)=B^\top e^{A_\theta^\top(T-s)}W_c^\dagger\delta x`. **Proof:** the end-point map `L:L^2[0,T]\to\mathbb R^d` satisfies `LL^*=W_c`; the displayed input is the minimum-norm solution to `Lu=\delta x`, orthogonal to `\ker L`. Additional state/input safety constraints can only raise the minimum effort or make the target infeasible.

### Operationally relevant jointly effective modes

For a stable local linearization with compatible time horizon, define the *diagnostic* Hankel singular values

\[
\sigma_k^{H}(T)=\sqrt{\lambda_k(W_c(T)W_o(T))}.
\]

These are **classical** control quantities, not a newly discovered `W_o\cap W_c`. Their numerical use requires pinned state/input/output units, a defined observation channel, and explicit handling of nonlinear, delayed or regime-switching approximations. They are *secondary* mechanistic diagnostics, not the definition of intelligence.

## III. Robust stabilization and stochastic safety: corrected statement

Let the locally linearized changed plant obey

\[
dx_t=[A_\theta x_t+B(-F\hat x_t+v_t)]dt+D_wdW_t,\quad e_t=x_t-\hat x_t,
\]

so `dx=[(A_\theta-BF)x+BF e+Bv]dt+D_wdW`. Assume a single `P_s\succ0` and `q>0` satisfy the **verified robust LMI**

\[
(A_\theta-BF)^\top P_s+P_s(A_\theta-BF)\preceq-qP_s
\quad\forall\theta\in\Theta_{\rm admitted}.
\]

Let `d_t=BF e_t+Bv_t`. On the explicitly specified high-confidence event where `\|P_s^{1/2}d_t\|\le d_{\max}` for all `t\in[0,T]`, the infinitesimal generator of `V=x^\top P_sx` obeys

\[
\boxed{\mathcal LV\le -\tfrac q2V+c,\qquad
c=\tfrac{2d_{\max}^2}{q}+\operatorname{tr}(P_sD_wD_w^\top).}
\]

**Proof.** Use the robust LMI and Young's inequality `2x^\top P_sd\le(q/2)x^\top P_sx+(2/q)d^\top P_sd` in Itô's formula. **QED.**

For global bounded disturbances or before the first violation of the bounded-estimation-error event, this gives

\[
\mathbb E[V_t]\le e^{-qt/2}V_0+\frac{2c}{q}(1-e^{-qt/2}).
\]

With `\tau_R=\inf\{t:V_t\ge R\}`, a conservative finite-horizon *exit-probability* bound under the globally applicable drift inequality is

\[
\boxed{\Pr(\tau_R\le T)\le \min\big\{1,(V_0+cT)/R\big\}.}
\]

This follows from optional stopping of `V_{t\wedge\tau_R}` and `\mathcal LV\le c`. If the estimation-error bound fails with probability `\delta_e`, run the stopping argument only until the first estimation-bound violation and add `\delta_e` to the failure probability. With full-support Gaussian diffusion, **almost-sure positive invariance of a bounded ellipsoid must not be claimed**. `\mathcal LV\le0` on a boundary is not a pathwise safety certificate.

The original finite-horizon inverse-Gramian feedback may be examined as a candidate `F`; it is *not* a general robust-safety theorem. Robust LMI feasibility and estimation error must be independently demonstrated.

## IV. Dual control: parameter information, not structural-observability magic

Under the parameterization `A_\theta=A_0+\sum_{j=1}^p\theta_jE_j`, controlled data `D_t` induce a likelihood `p_\theta(D_t\mid\pi)` and score `s_\theta(D_t)=\nabla_\theta\log p_\theta(D_t\mid\pi)`. Define

\[
\boxed{\mathcal I_\theta(\pi;t)=\mathbb E_\theta[s_\theta(D_t)s_\theta(D_t)^\top].}
\]

For *independent Gaussian measurements with a fixed covariance and a differentiable conditional prediction mean* `\mu_t(\theta,\pi)`, a corresponding simplified sensitivity form is

\[
\mathcal I_\theta(\pi;t)=\sum_{k\le t}\mathbb E\!\left[S_k^\top R_k^{-1}S_k\right],
\qquad S_k=\partial_\theta\mu_k.
\]

If the innovation covariance depends on `\theta`, its score term must also be included. State-estimation/filter sensitivity, action feedback, latent confounders and sensor correlations must not be silently dropped. `\lambda_{\min}(\mathcal I_\theta)>0` is a **local sensitivity condition**, not alone a finite-sample guarantee.

### Theorem 3 — valid finite-sample estimation bound in a restricted linear experiment

Assume an independently frozen, nonadaptive Gaussian regression experiment `r_k=H_k\theta+\varepsilon_k` with fixed `H_k`, independent `\varepsilon_k\sim\mathcal N(0,R_k)`, `R_k\succ0`, and `F_n=\sum H_k^\top R_k^{-1}H_k\succ0`. Then generalized least squares gives

\[
\hat\theta-\theta\sim\mathcal N(0,F_n^{-1}),
\]

and for `0<\delta<1`, with probability `\ge1-\delta`,

\[
\boxed{\|\hat\theta-\theta\|_2^2\le
\frac{p+2\sqrt{p\ln(1/\delta)}+2\ln(1/\delta)}{\lambda_{\min}(F_n)}.}
\]

**Proof:** whiten the Gaussian vector and apply a chi-squared upper-tail inequality. **QED.**

This is not a theorem for arbitrary closed-loop adaptive sensing, regularized estimators, latent Kalman innovations or stopping times selected from observed data. Those require model-specific self-normalized/time-uniform confidence bounds, bias control, and independently verified assumptions. **Cramér–Rao provides a lower, not an upper, covariance bound**; it cannot justify the earlier `T_id` claim.

### Probe design

Define a feasible, non-anticipative control family `\mathcal U_{\rm safe}(b_t)` using current confidence sets and verified actuator limits. A candidate harmonic input is

\[
v_t=\sum_{j=1}^{q}a_j\sin(\omega_jt+\varphi_j),
\quad v_t\in\mathcal U_{\rm safe}(b_t).
\]

Distinct harmonics, or `q\ge\lceil d/2\rceil`, **do not imply** identification of `p` unknown parameters. The actual qualification is a *verified* persistent excitation or likelihood information condition (with correct closed-loop score):

\[
\inf_{\theta\in\Theta_{\rm holdout}}
\lambda_{\min}(\mathcal I_\theta(\pi;T))\ge\alpha_T>0.
\]

A permissible objective is `max_\pi\inf_{\theta\in\Theta}\lambda_{\min}(\mathcal I_\theta(\pi;T))` subject to chance safety, information bandwidth, and total compute. Harmonic probing is merely one candidate policy, not a universal proof of `\alpha_T>0`.

Define the empirical reidentification time `\tau_{\rm id}` as the first time a pre-registered **valid confidence set** for `\theta` has diameter at most `\varepsilon_\theta`; define `\tau_{\rm unsafe}` as the first safety violation. Their conjunction is evaluated through

\[
\boxed{P(\tau_{\rm id}\le T,\ \tau_{\rm unsafe}>T)\ge 1-\delta.}
\]

There is no universal necessary identity `T_id<T_escape`: safe operation without full parameter recovery can be possible, and stochastic exit times are random.

## V. Information decomposition is orthogonal to identification

For a **frozen, explicitly named PID convention** and target variable `S` (e.g. future outcome conditional on the action regime or latent change category), the four-atom decomposition is

\[
I(S;Z_A,Z_B)=U_A+U_B+R+\mathrm{Syn}_{\rm PID}.
\]

`\mathrm{Syn}_{\rm PID}>0` is a property of the chosen distribution/target/redundancy axiom, **not** automatically causal interaction, full-rank Fisher information, or goal-directed intelligence. Equal network weights do not imply equal realized stochastic representations; different weights are not logically necessary for positive synergy. A PID result is labeled `CORRELATIONAL` until a controlled content-preserving ablation links it to policy performance.

For optional *guesswork-only* analysis, the correct Arimoto–Rényi conditional entropy at order `1/2` is

\[
\boxed{H_{1/2}^{A}(S\mid Z)=\log_2\sum_z P(z)
\left(\sum_s\sqrt{P(s\mid z)}\right)^2.}
\]

For finite `\mathcal S` and optimal ranking-based guessing, Arıkan-type bounds give

\[
\frac{2^{H_{1/2}^{A}(S\mid Z)}}{1+\ln|\mathcal S|}
\le\mathbb E[G^*(S\mid Z)]\le
2^{H_{1/2}^{A}(S\mid Z)}.
\]

The previously proposed **extra prefactor 2** in the definition of `H_{1/2}^{A}` was wrong. Neither PID nor these bounds imply a general polynomial-time causal planner, and finite-sample ratios of guesswork need not be exactly `2^{\Delta H}`.

## VI. Impossibility boundary for unrestricted monolithic simulation

### Proposition 4 — simulation dominance

Suppose a centralized architecture has the same physically available observations/actions, can represent both local algorithms, has the same admissible randomization, and can simulate their communications within the same (or smaller) measured compute/latency budget. Then every admissible coupled policy is also a centralized policy:

\[
\boxed{\Pi_{AB}(\mathbf B)\subseteq\Pi_{\rm mono}(\mathbf B),\quad
\sup_{\pi\in\Pi_{AB}}V(\pi)\le\sup_{\pi\in\Pi_{\rm mono}}V(\pi).}
\]

**Proof:** simulate both modules, message order and random states step-by-step under matched physical interfaces. **QED.**

Therefore, **absolute computational irreducibility** does not follow from networking. A positive collective advantage can only be asserted **relative to an explicit, finite, physically budgeted comparator class**. If an unrestricted resource-matched monolith really can simulate the interaction, a strict advantage against that class is impossible by construction.

## VII. Operational CNEH hypothesis and falsifier

Let `\mathcal G_{\rm OOD}` be a preregistered family of new targets/changes. Let success be reaching target `g` **and** avoiding unsafe exit before horizon `T`. For architecture `a` define

\[
V_a=\mathbb E_{g,\theta,\text{world seed}}\left[
\mathbf1\{x_T\in g,\ \tau_{\rm unsafe}>T\}
\right],\qquad \mathbf C(\pi_a)\preceq\mathbf B.
\]

Declare the controls **before** collecting results:

- `A_ONLY`, `B_ONLY`, `PARALLEL_NO_MESSAGES`;
- `STATIC_FUSION`, `ONE_WAY`, `HOMOGENEOUS_DUPLICATES`;
- `SCRAMBLED_MATCHED_TRAFFIC`, `CENTRALIZED_MATCHED`;
- `FULL_INFORMATION_ORACLE` (an upper reference, not a fair baseline).

`SCRAMBLED_MATCHED_TRAFFIC` preserves message envelope, bytes, delivery delays, sampling rate and approximate traffic distributions, but destroys cross-episode *semantic matching*. It **cannot** be assumed to preserve the entire message/world joint distribution while destroying conditional information; report exactly which distributions remain matched.

Define primary contrasts

\[
\Delta_{\rm central}=V_{AB}-V_{\rm centralized},\quad
\Delta_{\rm static}=V_{AB}-V_{\rm static},\quad
\Delta_{\rm scramble}=V_{AB}-V_{\rm scrambled}.
\]

A narrow operational collective advantage is supported only if, for frozen meaningful effect `\delta_V>0`, the multiplicity-adjusted lower confidence limits satisfy

\[
\boxed{
\mathrm{LCB}(\Delta_{\rm central})>\delta_V,\quad
\mathrm{LCB}(\Delta_{\rm static})>\delta_V,\quad
\mathrm{LCB}(\Delta_{\rm scramble})>\delta_V
}
\]

*and* (i) the total-budget and safety gates pass, (ii) blind OOD confirmation replicates, and (iii) the independent evaluator has ground-truth access not available to training policies. If the centralized class satisfies Proposition 4, the first inequality is not an achievable target; instead label the comparator claim `STRUCTURALLY_UNTESTABLE_UNDER_SIMULATION_DOMINANCE` and report the comparison, not a fictitious win.

Mechanistic evidence is **separate**:

\[
\begin{aligned}
&\Delta \lambda_{\min}(\mathcal I_\theta)>0\quad\text{(parameter identification, conditioned on a valid estimator)},\\
&\Delta V_{\rm target}>0\quad\text{(safe goal reachability)},\\
&\Delta\mathrm{Syn}_{\rm PID}>0\quad\text{(descriptive information synergy)},\\
&\Delta V_{\rm ablation}>0\quad\text{(causal effect of meaningful communication)}.
\end{aligned}
\]

These indicators should **not** be collapsed into one score. Mediation by PID is a separate hypothesis requiring an intervention that changes synergy without changing other relevant causal mechanisms; otherwise it remains `UNIDENTIFIED`.

### Criticality claim (independent)

If a critical phase transition is asserted, measure a separate order parameter with finite-size scaling, susceptibility, control-parameter sweep, and alternative noncritical slow-memory nulls. A peak in PID, phase-locking or `V` near one tuned coupling is not by itself a phase-transition proof. Criticality is **not necessary** for the operational CNEH hypothesis.

### Fail-closed verdict space

`SUPPORTED_NARROW` — preregistered comparator-qualified advantage and valid replication. `FALSIFIED_IN_SCOPE` — primary contrast fails under an adequately powered design. `INCONCLUSIVE` — interval includes the material-effect boundary or required coverage is absent. `UNIDENTIFIABLE` — interventions cannot separate models under declared sensors and budget. `SAFETY_UNQUALIFIED` — no validated risk guarantee. `NOT_TESTED` — experiment not executed. These are **claims about the defined regime**, not declarations about general intelligence.

## VIII. Research implementation map (not an assertion of executed integration)

- `neuron7x/sapolsky-behave-layers`: CWC experiment runner, observability and structural adequacy, active policies, preregistration.
- `neuron7x/bnsyn-phase-controlled-emergent-dynamics`: seeded AdEx/STDP/criticality substrate with frozen simulator adapters; no substitution of criticality readouts for cognitive utility.
- `neuron7xLab/neuron7x-agents`: optional DNCA competitive-regime architecture; keep source and dependency pinning separate.
- `neuron7xLab/time-rupture-inference`: hidden-change and active-intervention benchmark with negative controls.
- `neuron7x/neosynaptex`: separate null and external-diagnostic track; no promotion from the prior failed gamma-specificity claim.
- `neuron7xLab/proof-of-state`, `neuron7xLab/measured-honesty`: independent re-execution and epistemic-level checks.

**Required experiment artifact:** `protocol.json`, `preregistration.md`, `frozen_sources.lock`, `seeds.json`, `environment_truth_sealed.json`, `primary.csv`, `replication.csv`, `ablation.csv`, `budget.json`, `safety.json`, `negative_controls.json`, `verdict.json`, `SHA256SUMS`. No historical negative verdict files may be overwritten.

## IX. Source-level theoretical anchors

- Arıkan, E. (1996), *An inequality on guessing and its application to sequential decoding*, IEEE Transactions on Information Theory.
- Kalman, R. E. (1960), *On the general theory of control systems*; classical linear reachability/observability.
- Cramér–Rao information inequality: lower covariance limit under regularity and unbiasedness, **not** an upper bound.
- Classical stochastic Lyapunov drift and stopped-process estimates: bounded expected energy and finite-horizon exit probability, **not** pathwise invariance with full-support process noise.
- PID/\(\Phi\)ID: **estimator and target definition must be frozen**; descriptive synergy does not self-certify causal mediation.

**Publication ceiling:** no scientific claim of collective cognitive emergence without executable, independent, preregistered evidence. Mathematical correctness of the conditional lemmas must be audited independently before promotion as formal proof.
