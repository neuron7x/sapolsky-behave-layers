# DGC theorem/prior-art authority matrix — 2026-08-22

Purpose: prevent novelty inflation and distinguish external mathematical foundations from DGC-specific engineering composition.

| DGC proposition family | Closest external foundation | Relation | Novelty authority |
|---|---|---|---|
| VOI/VOC and computation selection | Russell & Wefald, *Principles of Metareasoning*, Artificial Intelligence 49 (1991), DOI 10.1016/0004-3702(91)90015-C | foundational / prior art | VOC itself: **NOT NOVEL** |
| Metalevel MDP / nonmyopic computation selection | Hay, Russell, Tolpin, Shimony; rational metareasoning / metalevel selection; subsequent analysis summarized by Lieder et al., *Learning to select computations* (UAI 2018) | foundational / prior art | general metareasoning: **NOT NOVEL** |
| Time-uniform concentration / confidence sequences | Howard, Ramdas, McAuliffe, Sekhon, Annals of Statistics 49(2), 2021, DOI 10.1214/20-AOS1991; Howard et al., Probability Surveys 17, 2020 | theorem foundation | DGC implementation only |
| Adaptive e-process under predictable sampling | nonnegative-supermartingale / time-uniform Chernoff framework of Howard et al. | specialization/composition | no theorem novelty asserted |
| Conformal risk control | Angelopoulos, Bates, Fisch, Lei, Schuster, ICLR 2024, *Conformal Risk Control* | direct foundation | no theorem novelty asserted |
| Covariate-shift conformal weighting | Tibshirani, Barber, Candès, Ramdas, NeurIPS 2019, *Conformal Prediction Under Covariate Shift* | adjacent/direct foundation | no weighted-conformal novelty asserted |
| Weighted conformal risk under shift | Zecchin, Hellström, Park, Shamai, Simeone, ISIT 2025 / arXiv:2501.11413 | adjacent recent foundation | no W-CRC novelty asserted |
| Wasserstein DRO robustness | Gao, Operations Research 71(6), 2023; Le & Malick, ICLR 2025, *Universal generalization guarantees for Wasserstein distributionally robust models* | direct robustness foundation | no WDRO novelty asserted |
| Causal intervention / identifiability | structural causal model / do-calculus literature; DGC currently only checks declared obligations | external foundation | general identification **UNSOLVED IN DGC** |
| Decision-irrelevant compute suffix certificate | elementary decision-stability implication under declared invariance | DGC-specific executable composition | novelty **UNESTABLISHED** pending external review |
| Transition-local meta branch-and-bound | Bellman upper/lower bounding and admissible-heuristic logic applied to metalevel computation | derived engineering specialization | novelty **UNESTABLISHED** |
| Production strict-math authority binding | software governance composition binding statistical certificate digests to runtime VOC | engineering composition | systems novelty **UNESTABLISHED** |

## Source notes

1. Russell & Wefald explicitly derive utility of computations from their ability to change external actions; DGC must not claim invention of VOC.
2. Rational metareasoning literature already distinguishes greedy/myopic and more expensive nonmyopic metalevel control. DGC's executable counterexample therefore establishes an internal correctness boundary, not a new discovery that myopic control can be suboptimal.
3. Howard et al. provide the time-uniform nonasymptotic martingale/concentration foundation used by DGC confidence/e-process contracts.
4. Angelopoulos et al. provide expected monotone-loss conformal risk control; DGC's risk-control primitive is an implementation/specialization.
5. Tibshirani et al. establish weighted conformal prediction under covariate shift when likelihood ratios are known/accurately estimated; DGC's new target-mean Hoeffding bound is different (expectation rather than conformal coverage) and must not be mislabeled weighted conformal prediction.
6. Le & Malick (ICLR 2025) and Gao's finite-sample WDRO work show that Wasserstein robust generalization theory is mature external prior art. DGC's weighted-L1 geometry is an auditable metric specialization, not a new WDRO theory.

## Current review status

`INTERNAL_THEOREM_BY_THEOREM_PRIOR_ART_AUDIT_V1` complete for the listed families. Independent external mathematical review / proof-assistant verification remains absent, so this document does not authorize a novelty claim.
