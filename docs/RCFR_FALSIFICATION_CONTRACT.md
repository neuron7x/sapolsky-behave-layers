# RCFR Falsification Contract — Role-Conditioned Functional Reuse

Status: NORMATIVE. Governs any future work on RCFR (role-plastic modules /
dynamic role-conditioned low-rank modulation) in CWC. Derived from the
owner-supplied RCFR audit (2026-07-16) and DCSA v2.0 discipline. RCFR is
**WP-3+ territory** and is BLOCKED until the WP-2 routing gate resolves; this
document freezes what RCFR would have to prove, not permission to build it.

## 0. What RCFR claims
A shared bank of operators `{E_1..E_N}`; a controller emits `(module i_t,
role r_t, depth d_t)` per input; the role modulates the module via a
low-rank/FiLM/hypernetwork delta:
`E_i^{(r)}(h) = E_i(h; θ_i + Δθ_i(r, M))`, `Δθ(r) = A(r) B(r)^T`.
Claim: one physical module changes functional role by context, not one expert
per function.

## 1. Claim-status ledger (audit, statuses re-verified here)
| Claim | Status | Basis |
|---|---|---|
| Conditional low-rank modulation exists | **VERIFIED PRIOR ART** | HyperNetworks (1609.09106), HyperFormer (2106.04489), HypeLoRA, HyLoVQA, DISeL — a hypernet generating LoRA A,B by task/input is published |
| Dynamic-LoRA generator `r→A(r),B(r)→ΔW(r)` is novel | **FALSE** | direct analogues above; the map is prior art |
| Current code implements *token-level* RCFR | **FALSE** | code carries `A:[B,d_out,rank]` per sequence ⇒ ΔW_{b,1}=…=ΔW_{b,L}; that is sequence-conditioned, not `r_{b,t}`. Token-level needs `A,B ∈ R^{B×L×d×k}` |
| Generator is "almost free" | **FALSE (naive token-level)** | see §2, arithmetic INDEPENDENTLY VERIFIED |
| Frozen base weights remove forgetting | **FALSE** | §3: `A'(r_o)B'(r_o)^T ≠ A(r_o)B(r_o)^T` after W_A,W_B change, even with W frozen |
| Entropy is a reliable executive signal | **FALSE** | NNs miscalibrated (1706.04599); need a calibrated risk estimator |
| XOR/transfer proves functional repurposing | **NOT PROVEN** | confounds: shared encoder, format matching, memorization, extra params/FLOPs, regularization |
| RCFR as a *closed CWC system* is non-novel | **NOT PROVEN** | the integration hypothesis stays open |
| RCFR beats MoE/MoD | **NOT_TESTED** | no compute-matched comparison exists |
| Strongest potential novelty | **joint role–route–depth–memory–budget control** | not the LoRA generator alone |

## 2. Resource budget — INDEPENDENTLY RE-COMPUTED (VERIFIED, `scripts`-free check)
For `d_in=d_out=4096, d_r=128, k=8`:
- Generator params per module `= d_r·k·(d_in+d_out) = 8,388,608` (**8.39M**).
  16 modules ⇒ **134.2M** generator params. NOT free.
- Token-level A,B storage at `B=8, L=2048, fp16 = B·L·k·(d_in+d_out)·2 B =
  2.00 GiB` — transient only, before grads/optimizer/activations.
- Generation FLOPs `= 2·d_r·k·(d_in+d_out) = 16,777,216` per role vector;
  for `8×2048` tokens ⇒ **274.9 GFLOPs = 50% of one full 4096×4096 layer**
  (549.8 GFLOPs). Naive token-level matrix generation can erase the resource
  advantage.
- Static LoRA fuses into W (zero inference latency); **context-dependent RCFR
  cannot pre-fuse** because ΔW(r_t) changes per input.

Consequence: any RCFR proposal MUST state which granularity (sequence vs
token) it implements and pay the corresponding, measured, WP-1-qualified cost.
A "cheap token-level roles" claim is refuted a priori until measured otherwise.

## 3. Forgetting is not solved by freezing W
For an old role `r_o`, output `y_o = W h + A(r_o) B(r_o)^T h`. Training a new
task changes generator weights `W_A→W'_A, W_B→W'_B`, so
`A'(r_o)B'(r_o)^T ≠ A(r_o)B(r_o)^T` even with W frozen. Base weights are
protected; the *functional behavior of the old role* is not. RCFR forgetting
claims require an explicit mechanism (replay, role-anchor regularization,
orthogonal subspaces, consolidation, or freezing verified role primitives) AND
a longitudinal adaptation experiment — never "frozen base ⇒ no forgetting".

## 4. Executive gate must be a calibrated risk estimator
Not entropy. `R_t = P(failure | h_t, route, B_t)`, validated by Expected
Calibration Error, Brier score, risk–coverage curve, selective accuracy, OOD
detection, and disagreement between independent trajectories.

## 5. Mandatory compute-matched baselines (RCFR is supported only vs ALL)
| Baseline | Isolates |
|---|---|
| Base shared module | reuse without roles |
| Static LoRA | ordinary adaptation |
| HyperFormer-style adapter | prior-art conditional generation |
| Input-gated rank basis | dynamic-LoRA baseline |
| Neural Interpreter | dynamic function composition |
| MoD | adaptive compute under a budget |
| **RCFR** | joint module–role–depth control |

## 6. Mandatory causal controls
1. Role permutation (keep module, permute r_t).
2. Module swap (keep role, swap E_i).
3. Random role (same compute, random r_t).
4. Frozen controller (remove learned adaptation).
5. Static adapter (average ΔW(r)).
6. Alternative-path ablation (remove the backup trajectory).
7. Fixed-depth control (equalize total FLOPs).

## 7. RCFR is SUPPORTED only if (all)
Same physical module is used across tasks; changing ONLY the role vector
predictably changes its function; random/swapped/static roles LOSE at equal
compute; effect replicates on ≥5 seeds; transfers to unseen compositions; and
the whole is compute-matched against every §5 baseline including MoE/MoD. Until
then RCFR novelty = the OPEN integration hypothesis (joint
role–route–depth–memory–budget control), not the LoRA generator.

## 8. Ordering
No RCFR experiment begins until WP-2 routing (block, then token) has a verdict.
Current status: WP-2 v1 NOT_SUPPORTED (ROUTER_COLLAPSE); v1.1 (binding budget,
heterogeneous task) in progress. If learned routing cannot beat static even
where adaptivity provably helps, adding role-modulation on top is unjustified —
the audit's "joint control is the only novelty" claim would itself be at risk.
