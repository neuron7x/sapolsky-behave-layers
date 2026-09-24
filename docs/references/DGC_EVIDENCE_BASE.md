# DGC Evidence Base — Claim-to-Source Map

This file records the external theoretical/engineering support used by the DGC programme. Sources support components; none independently establishes DGC superiority or novelty.

## E1 — Value of information / decision relevance

- Ross D. Shachter, Stanford University, *Efficient Value of Information Computation*. VOI is framed as the change in decision value obtained when uncertainties become observable. https://web.stanford.edu/~shachter/pubs/valinfo.pdf
- Stanford MS&E 152, *Introduction to Decision Analysis*, explicitly includes value of information and experimentation within structured decision analysis. https://bulletin.stanford.edu/courses/1045271
- Athey & Levin, Stanford GSB, *The Value of Information in Monotone Decision Problems*, Research in Economics 72(1), 2018. https://www.gsb.stanford.edu/faculty-research/publications/value-information-monotone-decision-problems

**DGC use:** information/compute is evaluated by effect on decision value, not uncertainty magnitude alone.

## E2 — Rational metareasoning / value of computation

- De Sabbata, Sumers & Griffiths, *Rational Metareasoning for Large Language Models*, 2024. Formulates inference-time reasoning as a cost-performance tradeoff using Value of Computation. https://arxiv.org/abs/2410.05563
- Horvitz & Breese, *Ideal Partition of Resources for Metareasoning*. Studies the resource split between metareasoning/control and base-level execution. https://arxiv.org/abs/2110.09624

**DGC use:** cognition itself is a costly action and the governor's own cost must be included.

## E3 — Structural causal semantics

- Judea Pearl, UCLA Cognitive Systems Laboratory, *Causality*, 2nd ed. (2009), including structural-equation/intervention semantics. https://bayes.cs.ucla.edu/BOOK-2K/
- Pearl, *The Mathematics of Cause and Effect*: structural-model semantics use functional/counterfactual relationships as building blocks. https://bayes.cs.ucla.edu/mathematics.htm

**DGC use:** textual alternatives are not automatically causal countermodels. `CAUSAL_INTERVENTION` requires a structural-model digest and dependencies.

## E4 — Anytime-valid sequential inference

- Howard, Ramdas, McAuliffe & Sekhon, *Time-uniform, nonparametric, nonasymptotic confidence sequences*, Annals of Statistics 49(2), 2021, DOI 10.1214/20-AOS1991. https://arxiv.org/abs/1810.08240
- Aaditya Ramdas, CMU Statistics/Data Science publication record. https://stat.cmu.edu/~aramdas/

**DGC use:** sequential peeking/stopping requires time-uniform validity. The initial implementation uses a simpler stitched Hoeffding union-bound construction under frozen i.i.d. bounded sampling; adaptive sampling fails closed.

## E5 — Strong routing baselines

- Ong et al., UC Berkeley/Anyscale/Canva, *RouteLLM: Learning to Route LLMs with Preference Data*, ICLR 2025. https://openreview.net/pdf?id=8sSqNntaMr

**DGC use:** DGC must be compared against cost/quality routing, not a naive fixed LLM strawman.

## E6 — Serving/scheduling separation

- UC Berkeley EECS, *vLLM: An Efficient Inference Engine for Large Language Models* (2025 thesis/report). Discusses PagedAttention, scheduling and systems-level serving optimization. https://www2.eecs.berkeley.edu/Pubs/TechRpts/2025/EECS-2025-192.html

**DGC use:** compute-value governance and serving throughput/rate-limit scheduling are distinct authorities.

## E7 — Budget-aware evaluation

- OpenAI, *A shared playbook for trustworthy third party evaluations* (2026). Reports that test-time budget can materially change elicited capability and recommends reporting turns/tokens/retries/wall time/inference cost and expected cost per successful solve. https://openai.com/index/trustworthy-third-party-evaluations-foundations/

**DGC use:** no capability/efficiency claim without the exact inference harness and resource budget.

## E8 — Monitorability is itself resource-dependent

- OpenAI, *Evaluating chain-of-thought monitorability* (2025), including the explicit distinction between agent compute and monitor compute and the “monitorability tax”. https://openai.com/index/evaluating-chain-of-thought-monitorability/

**DGC use:** monitor/auditor compute is separately metered; DGC telemetry stores decision metadata rather than treating private reasoning text as the governance certificate.

## Evidence boundary

The sources above anchor VOI, metareasoning, causal semantics, sequential inference, routing baselines, serving separation, budget-aware evaluation and monitorability. They do **not** establish:

- that `CWC-DGC-H1` is true;
- that the DGC estimator is calibrated on real tasks;
- that DGC is novel;
- that DGC is safe or production-ready;
- that the synthetic one-step theorem transfers to open-ended LLM cognition.
