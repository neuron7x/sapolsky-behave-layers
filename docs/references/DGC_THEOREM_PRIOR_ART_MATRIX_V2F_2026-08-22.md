# DGC theorem / prior-art matrix — v2f

Date: 2026-08-22

Purpose: prevent theorem-family novelty inflation. `DGC-specific` means the repository's executable composition or restricted certificate, not invention of the underlying mathematics.

| DGC proposition / mechanism | External foundation | DGC-specific authority | Novelty authority |
|---|---|---|---|
| one-step VOC / rational compute selection | Russell & Wefald; Hay, Russell, Tolpin & Shimony, *Selecting Computations: Theory and Applications* (UAI 2012; arXiv:1207.5879) | executable fail-closed admission contract and counterexample retention | **NO novelty claim for VOC/metareasoning** |
| time-uniform / anytime-valid bounded inference | Howard, Ramdas, McAuliffe & Sekhon, *Time-uniform, nonparametric, nonasymptotic confidence sequences* (arXiv:1810.08240; Annals of Statistics) | restricted predictable-propensity and drift guards | **NO novelty claim for confidence sequences/e-processes** |
| conformal expected-risk control | Angelopoulos, Bates, Fisch, Lei, Schuster, *Conformal Risk Control*, ICLR 2024 | DGC calibration/risk-control authority binding | **NO novelty claim for CRC** |
| covariate-shift weighting | Tibshirani, Barber, Candes, Ramdas, *Conformal Prediction Under Covariate Shift* (2019); later weighted risk-control literature | bounded target-mean LCB with explicit ratio-error authority | **NO novelty claim for importance weighting** |
| unbounded/estimated ratio risk | Wang & Goel, *Weight Clipping for Robust Conformal Inference under Unbounded Covariate Shifts* (arXiv:2605.02072, 2026) | DGC rejects impossible `W<1` and keeps bounded-ratio/error-budget scope explicit | boundary hardening only |
| Wasserstein ambiguity / DRO | Mohajerin Esfahani & Kuhn, *Data-driven distributionally robust optimization using the Wasserstein metric*, Math. Programming 171 (2018) | audited weighted-L1 geometry + externally authoritative radius/Lipschitz budget | **NO novelty claim for Wasserstein DRO** |
| causal selection diagrams / transportability | Bareinboim & Pearl, 2012/2013; complete transportability algorithms | exact d-separation + restricted S-admissible transport certificate | **NO novelty claim for transportability/do-calculus** |
| counterfactual transportability | Correa, Lee & Bareinboim, ICML 2022 | currently **not implemented generally** | OPEN / prohibited |
| bounded finite-horizon metalevel planning | Bellman dynamic programming + metalevel MDP literature | interval branch-and-bound with explicit admissible-upper provenance and exact-rational model check | composition claim only |

## Authority boundary

The repository may claim implementation/falsification of the listed restricted DGC contracts. It may not claim invention of the external theorem families. Broader causal transport, arbitrary adaptive inference, unbounded-shift guarantees, or global metareasoning optimality remain outside current authority unless separately proved and validated.
