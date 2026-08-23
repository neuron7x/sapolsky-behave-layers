# DGC Related Work and Novelty Review

**Status:** living pre-claim review. Novelty is `UNKNOWN` until a systematic literature search is completed and frozen before any novelty claim.

## Established foundations

1. **Metareasoning / bounded rationality.** Russell & Wefald formalize limited rational agents as constrained optimization over computation itself. This supports treating computation as an action with cost, but does not establish DGC.
2. **Value of information.** Stanford decision-analysis materials define information value by the improvement available when decisions can condition on additional information. This supports the decision-relevance distinction: uncertainty can be high while information value is zero if the action is invariant.
3. **Structural causal counterfactuals.** Pearl's UCLA structural-model semantics distinguish causal counterfactuals from unconstrained textual alternatives. DGC therefore requires provenance and structural semantics whenever it claims causal interpretation.
4. **Adaptive computation / routing.** Existing adaptive-depth, early-exit, routing and model-selection work already allocates compute conditionally. RouteLLM is a strong cost/quality routing baseline and defeats any novelty claim of "adaptive compute" in general.
5. **Sequential inference.** Confidence sequences provide time-uniform coverage under optional stopping. DGC's sequential stopping must use an anytime-valid method under its actual sampling/adaptation assumptions; a fixed-n confidence interval is not sufficient after repeated peeking.
6. **Serving systems.** vLLM/PagedAttention demonstrates that serving scheduling and memory management are separate systems questions from model quality. DGC compute admission and provider/runtime scheduling must remain separate authorities.
7. **Holistic evaluation.** Stanford HELM supports multi-metric evaluation rather than single-score accuracy optimization.
8. **Evaluation budget accounting.** OpenAI's 2026 guidance on third-party evaluations explicitly requires reporting harness, tokens/cost/time and, where repeated attempts apply, expected cost per successful solve. DGC therefore meters all inference resources.
9. **Automated adversarial auditing.** Anthropic Petri is evidence that agentic audit loops can systematically search for concerning behaviors; it motivates but does not validate DGC self-falsification.
10. **Monitorability.** OpenAI's monitorability work treats monitoring capability/compute as a distinct resource; DGC likewise assigns a budget to monitors and logs decision metadata rather than private hidden reasoning.

## Existing CWC overlap — boundary that MUST be preserved

CWC already contains `ADAPTIVE_COMPUTATION_VALUE_THEORY.md` and `ADAPTIVE_COMPUTATION_ADMISSIBILITY_SPEC.md`. Those answer a **programme-level / pilot-level** question: whether context-adaptive computation has positive net value on a workload and should be admitted to a larger experiment/deployment stage.

DGC answers a different **online state-level** question:

> Given the current decision state, which next cognition/compute operation, if any, has positive conservative value before paying its cost?

If DGC merely reimplements the existing admissibility gate per request, the novelty claim collapses into duplication.

## Potentially defensible narrow contribution

> Compute admission based on estimated counterfactual decision regret under provenance-bound perturbations, combined with sequential value-of-computation stopping, hard resource budgets, and proof-carrying decision certificates.

This is a **candidate contribution**, not a novelty conclusion.

## Primary sources

- Russell, S.; Wefald, E. *Principles of Metareasoning*. CMU archive copy: https://iiif.library.cmu.edu/file/Newell_box00014_fld01011_doc0001/Newell_box00014_fld01011_doc0001.pdf
- Stanford CS29N, *Good Decision, Bad Outcome* (Value of Perfect Information): https://web.stanford.edu/class/cs29n/slides/Lec8.pdf
- Shachter, R. *Efficient Value of Information Computation*: https://web.stanford.edu/~shachter/pubs/valinfo.pdf
- Pearl, J. *The Mathematics of Cause and Effect* / structural-model semantics: https://bayes.cs.ucla.edu/mathematics.htm
- UC Berkeley STAT 158, *Sequential Testing for Experimental Design* (2026): https://stat158.berkeley.edu/spring-2026/27-sequential-analysis/slides.html
- UC Berkeley Sky Computing Lab, RouteLLM: https://sky.cs.berkeley.edu/project/routellm/
- Kwon et al., *Efficient Memory Management for Large Language Model Serving with PagedAttention*: https://arxiv.org/abs/2309.06180
- Stanford CRFM, HELM: https://crfm.stanford.edu/2022/11/17/helm.html
- OpenAI, *A shared playbook for trustworthy third party evaluations* (2026): https://openai.com/index/trustworthy-third-party-evaluations-foundations/
- OpenAI, *Evaluating chain-of-thought monitorability*: https://openai.com/index/evaluating-chain-of-thought-monitorability/
- Anthropic, *Petri: An open-source auditing tool to accelerate AI safety research*: https://www.anthropic.com/research/petri-open-source-auditing
- Anthropic, *Donating our open-source alignment tool* (Petri 3.0, 2026): https://www.anthropic.com/research/donating-open-source-petri
