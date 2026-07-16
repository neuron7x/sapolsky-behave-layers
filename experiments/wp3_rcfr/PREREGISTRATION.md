# WP-3 RCFR — Role-Conditioned Functional Reuse — PREREGISTRATION (Act F)

Registered 2026-07-16 before the 8-seed confirmatory analysis. Authority: CWC
Evidence Act v3.0 Act F. Unblocked by Gate D (routing causality SUPPORTED).
Governed by `docs/RCFR_FALSIFICATION_CONTRACT.md`.

## Claim under test
The SAME physical module performs R distinct functions under learned role
conditioning via a FIXED low-rank primitive bank
`ΔW(r) = Σ_m c_m(r) U_m V_mᵀ` (controller emits only c(r)), and this beats the
strongest conditional-adapter baseline at equal compute.

## Task
R=8 fixed random permutations of S=16 symbols; input [role, x0..x7], target =
apply the role's permutation element-wise. The operator module is LINEAR (no
nonlinearity) so a single fixed weight CANNOT be R permutations — role-weight
modulation is the mechanism under test. Test = novel sequence arrangements of
trained (role, symbol) pairs (compositional generalization for an element-wise
operator).

## Modes (equal compute except separate_modules param count)
shared_no_role (role in input, fixed W), static_lora (one fixed low-rank delta),
fixed_role (ΔW at a constant role), disel_gated (FAIR STRONG baseline: input+
role gated rank bank — prior-art conditional adaptation), separate_modules (one
W per role, R× params, capacity ceiling), rcfr (role→coeffs→ΔW).

## F5 gate — RCFR SUPPORTED iff ALL (8 seeds)
1. same module ≥2 functions: rcfr acc_seen ≥ 0.95 AND beats shared_no_role AND
   static_lora (paired bootstrap CI > 0);
2. role-only changes function predictably: forced-wrong-role output follows the
   wrong role's function ≥ 0.85 AND role permutation removes ≥ 80% of advantage;
3. transfers to unseen compositions: rcfr acc_unseen ≥ 0.95;
4. **beats the strongest conditional-adapter baseline (disel_gated), paired CI > 0.**
Else RCFR_NOT_SUPPORTED.

## Prior expectation (from RCFR contract, honest)
Conditional low-rank modulation is VERIFIED PRIOR ART (HyperNetworks/HyperFormer/
DISeL). If a fair input+role-gated rank baseline matches RCFR, criterion 4 fails
and the verdict is RCFR_NOT_SUPPORTED — RCFR's only possible value is INTEGRATION
(Act I joint control), NOT isolated novelty. A NULL here is a valid, expected
completion and must not be hidden.

## Causal interventions (RCFR)
force wrong role, module swap (corrupt ΔW), random role, plus the follows-wrong
and advantage-removed measures. No threshold changed after seeing results.
