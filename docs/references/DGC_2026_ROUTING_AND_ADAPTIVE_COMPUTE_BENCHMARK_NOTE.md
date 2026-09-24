# DGC 2026 Routing / Adaptive-Compute Benchmark Note

Status: related-work constraint, not novelty or superiority evidence.

## LLMRouterBench (2026)

`LLMRouterBench: A Massive Benchmark and Unified Framework for LLM Routing` (arXiv:2601.07206) reports a benchmark with over 400K instances, 21 datasets, 33 models and 10 routing baselines. Under unified evaluation, multiple routing methods have similar performance and several recent/commercial routers do not reliably beat a simple baseline; a substantial Oracle gap remains.

Source: `https://arxiv.org/abs/2601.07206`

Repository consequence: DGC financial experiments MUST compare against strong, matched-quality routing baselines and MUST NOT claim superiority from comparison with only a naive always-expensive policy.

## Adaptive Test-Time Compute Allocation (2026)

`Adaptive Test-Time Compute Allocation for Reasoning LLMs via Constrained Policy Optimization` (arXiv:2604.14853) formalizes per-instance test-time compute allocation under an average compute constraint and reports experiments on MATH/GSM8K across multiple models, including up to 12.8% relative accuracy improvement on MATH at matched budget in the reported setting.

Source: `https://arxiv.org/abs/2604.14853`

Repository consequence: decision-aware compute allocation is an active frontier research class, not unique to DGC. DGC must establish any incremental value from counterfactual decision regret, VOC stopping, falsification and proof-carrying governance under matched cost/quality evaluation.
