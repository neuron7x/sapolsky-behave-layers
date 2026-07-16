# COGNITIVE SEMIOTIC AUDIT REPORT (LEVEL: PRINCIPAL-RESEARCH)

> **SUPERSEDED 2026-07-16 by `DCSA_PROTOCOL_V2.md` + `DCSA_AUDIT_0002.md`.** Kept for provenance; v2 restates "grounding ratio UNDEFINED" as NOT_TESTED and adds claim-level bounds.
## SYSTEM METADATA & MATHEMATICAL CORES
*   Target Architecture: `nanochat-cwc-baseline` = unmodified dense GPT (karpathy/nanochat, fixed depth, no conditional computation) + verified WP-1 instrumentation substrate (15 modules). All six CWC capability terms are tier **ABSENT** (see `CWC_SEMANTIC_CONTRACT.md`).
*   Mathematical Bounds Applied: information-theoretic channel capacity (routing), categorical existence analysis (grounding functor 𝔾), measurement-theoretic admissibility. Riemannian curvature / FIM / IB objectives are **procedure-defined only**: they require a trained checkpoint, which does not exist in this environment. Provenance rule (project-wide): a numeric value may appear in this report only with a runnable procedure and evidence artifact; otherwise the field carries `NOT_MEASURED(unlock condition)` or `UNDEFINED`. This rule is itself the audit's primary finding-preventer: any DCSA report printing curvature/FIM/RSI numbers for this system today would be fabrication.

---

## I. SEMIOTIC LANDSCAPE ANALYSIS (SYNTAX/SIGN FLOW)
*   **Syntactic Entropy**: $H(S)$ = `NOT_MEASURED`. Procedure (preregistered): token-level cross-entropy rate of the frozen baseline on a fixed, SHA256-hashed corpus, seeds in manifest. Unlock: trained checkpoint present.
*   **Graph Transition Density**: derivable **exactly, without a checkpoint** — the computational graph is static; every token traverses the identical dense path (all blocks, all heads, all MLPs). The path-transition matrix $\mathbf{T}$ is a point mass, hence the routing-channel entropy is exactly
    $$H_{route} = 0 \text{ bits/token.}$$
    The `cwc/instrumentation/routing.py` counters confirm this structurally: there exist no conditional-computation events to record. This is the formal restatement of "the CWC mechanism is absent": the sign-flow has zero decision capacity.
*   **Path Congruence**: trivially perfect (single path). Congruence without selection carries no semantic information; a 0-bit channel cannot ground anything.

---

## II. SEMASIOLOGICAL GROUNDING VERDICT (MEANING/INVARIANTS)
*   **Grounding Ratio**: $I(\mathcal{C}_{Sign}; \mathcal{M}_{sem}) / H(\mathcal{C}_{Sign})$ = **UNDEFINED** — not 0 (0 would be a measurement). The grounding functor 𝔾 is not implemented; $\mathcal{C}_{Sem}$ has no objects (no concept lattice, no world-model states, no target variable $Y$). There is no instrument to point at the quantity.
*   **Functorial Commutativity Analysis**: vacuously non-testable — no diagram exists to commute. The first non-vacuous commutativity test becomes available when the `task utility` gate (contract §5) instantiates $Y$ and a preregistered task suite fixes $\mathcal{C}_{Sem}$.
*   **Representation Drift**: `NOT_MEASURED`. Procedure: RSI under meaning-preserving syntactic perturbation (paraphrase set, hashed) on a frozen checkpoint; $\epsilon$ preregistered before the first run, with a positive control (a deliberately scrambled encoder must fail the RSI floor).

---

## III. COMPUTE-EQUIVALENT ABLATION BASELINE
*   **Control Configuration**: preregistered now — (a) dense baseline at equal FLOPs; (b) uniform-random router at equal FLOPs; (c) frozen-at-init router (contract §1); (d) utility-blind structural edits of equal budget (contract §4); (e) memory-zeroed variant (contract §2).
*   **Ablation FLOPs Equivalence**: this is the one section the current system already serves with full honesty — compute parity is **certified, not asserted**, by the verified FLOP ledger + energy meter (99.46% coverage, 12/12 mutation kill). Parity artifact: per-run ledger dumps under the same manifest schema.
*   **Performance Delta**: `NOT_MEASURED` — this is precisely the `Pareto advantage` gate (contract §6). By the semantic contract, the term may not be used in denoting mode until the delta exists as a bootstrap-CI artifact whose interval excludes 0.

---

## IV. ADVERSARIAL DISRUPTION VECTOR (SEMANTIC COLLAPSE CASE)
*   **Perturbation Equation**: $\delta$ is **NOT_SYNTHESIZABLE** at tier ABSENT — the objective $\max_{\|\delta\|\le\eta} D_{KL}(p(Y|\mathbb{G}(x)) \,\|\, p(Y|\mathbb{G}(x+\delta)))$ requires both 𝔾 and $p(Y|\cdot)$, neither of which exists.
*   **Failure Mode** (preregistered probe for the future router): minimal-pair prompts — semantic intent held constant, surface form perturbed — maximizing KL of the *routing distribution*. A router whose decisions track surface form rather than intent is the canonical semasiological fault: signs routed without invariant grounding. This probe doubles as the falsification arm of contract §1.
*   **Mitigation Strategy**: adopted as future training-time constraints — (i) RSI floor as an invariant-regularization gate; (ii) mandatory positive controls per contract; (iii) routing-entropy corridor: $H_{route} = 0$ (dead router) and degenerate collapse to a single expert are both RED states — the gate must reject *both* tails.

---

## VERDICT
The system today is a **pure interpretant-instrument**: measurement channel verified; sign-flow degenerate ($H_{route} = 0$ bits/token, exact); grounding functor nonexistent (UNDEFINED, not zero). Every DCSA quantity is classified into exactly one of: derived-exactly, UNDEFINED (no instrument), or NOT_MEASURED (procedure preregistered, unlock condition named). Each unlock condition coincides with a tier transition in `CWC_SEMANTIC_CONTRACT.md` — the DCSA stages are hereby bound as the formal layer those gates must instantiate. Next executable transition: `dynamic depth` ABSENT→SPECIFIED (cheapest by dependencies: the FLOP ledger already measures it per-token).
