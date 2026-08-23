# DGC Mathematics v2 — Evidence and Prior-Art Boundary

This file records external mathematical authorities used to constrain DGC claims. DGC-specific propositions are either direct specializations/compositions or internally derived finite-case results; no novelty claim is made.

## Safe anytime-valid inference / e-processes

- Ramdas, Grünwald, Vovk, Shafer, *Game-Theoretic Statistics and Safe Anytime-Valid Inference*, Statistical Science 38(4), 2023. DOI: https://doi.org/10.1214/23-STS894
- Cook, Mishler, Ramdas, *Semiparametric Efficient Inference in Adaptive Experiments*, CLeaR/PMLR 236, 2024. https://proceedings.mlr.press/v236/cook24a.html
- Neopane, Ramdas, Singh, *Optimistic Algorithms for Adaptive Estimation of the Average Treatment Effect*, ICML/PMLR 267, 2025. https://proceedings.mlr.press/v267/neopane25a.html

Boundary: DGC v2 implements only a bounded importance-weighted Hoeffding e-process under predictable propensities and a fixed target mean. It does not inherit the full semiparametric efficiency or general adaptive-inference results of these papers.

## Conformal calibration / risk control

- Angelopoulos, Bates, Fisch, Lei, Schuster, *Conformal Risk Control*, ICLR 2024. https://proceedings.iclr.cc/paper_files/paper/2024/file/f3549ef9b5ff520a7e41ff3cc306ab2b-Paper-Conference.pdf
- Bao, Huo, Ren, Zou, *CAP: A General Algorithm for Online Selective Conformal Prediction with FCR Control*, JMLR 26, 2025. https://jmlr.org/papers/volume26/24-0452/24-0452.pdf
- Bai, Jin, *Conformal Selective Prediction with General Risk Control*, 2026 preprint. https://arxiv.org/abs/2603.24704

Boundary: v2 implements a finite-grid monotone specialization of conformal expected-risk control and a basic one-sided split-conformal lower prediction bound. It does not claim online FCR or SCoRE guarantees.

## Value of information / perfect information

- Berkeley CS188, *The Value of Perfect Information*. https://inst.eecs.berkeley.edu/~cs188/textbook/vpis/vpi.html
- Avriel, Williams, *The Value of Information and Stochastic Programming*, Operations Research 18(5), 1970. https://doi.org/10.1287/opre.18.5.947
- Boncompte Pons, Guerrero Manzano, *The value of perfect information for the problem: a sensitivity analysis*, Environment Systems and Decisions 44, 2024. https://doi.org/10.1007/s10669-024-09986-7

Boundary: DGC uses perfect revelation only as an upper bound for **pure information** operations. The certificate is invalid for computations that causally alter the world, utility or action set.

## Ambiguous experiments / robust decisions

- Wang, *Informativeness orders over ambiguous experiments*, Journal of Economic Theory 222, 2024, 105937. https://doi.org/10.1016/j.jet.2024.105937
- Micheli, Balta, Tsiamis, Lygeros, *Wasserstein Distributionally Robust Bayesian Optimization with Continuous Context*, AISTATS/PMLR 258, 2025. https://proceedings.mlr.press/v258/micheli25a.html

Boundary: DGC does not claim a new ambiguity/informativeness theory. Its finite credal LP, TV bound and Wasserstein-Lipschitz penalty are conservative engineering specializations.

## Multiobjective / Pareto reporting

DGC's paired Pareto certificate is an internal simultaneous-inference contract: paired cost and quality differences receive bounded fixed-n confidence intervals with Bonferroni familywise control. It is not a new multiobjective optimization algorithm.
