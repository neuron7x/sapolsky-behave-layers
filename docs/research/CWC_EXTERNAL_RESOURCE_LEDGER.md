# External resource admission ledger

No external data or package is vendored by this PR. Links below identify sources or candidates, not downloaded/inspected artifacts. Install nothing into the canonical runtime until version, license, platform compatibility and integrity are checked. Never infer H's calibration from a prepared signal.

## Data: staged read-only acquisition

| Priority | Source identity | Use and limitation |
|---|---|---|
| P0 | Harkin et al., *Patch-clamp recordings from dorsal raphe neurons*, [Dryad DOI 10.5061/dryad.66t1g1k2w](https://doi.org/10.5061/dryad.66t1g1k2w); updated 2023-02-22; [paper DOI 10.7554/eLife.72951](https://doi.org/10.7554/eLife.72951) | Verified landing page lists 970.56 MB version with README, checksums and mostly ABF recordings. DRN 5-HT, DRN GABA and mPFC L5 pyramidal neurons. Inspect metadata and README before downloading 970 MB archive. Gating / pharmacology voltage-clamp and current-step/noise records serve different analyses. Not an independently calibrated NMDA-gain/time reference dataset. |
| P1 | [Allen Cell Types SDK documentation](https://allensdk.readthedocs.io/en/latest/cell_types.html); [database](https://celltypes.brain-map.org/) | Verified SDK describes current-clamp NWB files and sweep metadata. Use for current-clamp model residuals and cell-level transfer; do not reinterpret as H voltage-clamp observations. Specimen 324257146 is an SDK example, not selected evaluation data. |
| P2 | [DANDI Archive](https://dandiarchive.org/), [NWB schema](https://nwb-schema.readthedocs.io/), [G-Node GIN](https://gin.g-node.org/) | Candidate catalogues: search for actual synaptic voltage-clamp recordings, receptor-isolated traces, baseline and instrument metadata, independent cell groups. No accession admitted yet. |

Metadata record required per file: URL/DOI, accession/version, fetched_at UTC, license/terms, file SHA-256, byte count, parser and version, protocol, cell/preparation/animal keys when released, units and scaling, timebase and sampling frequency, raw-vs-processed status, known filtering/ADC range/quantization, clipping, series/access resistance and compensation metadata, clamp holding command, temperature, bath/internal solution, receptor isolation, reference records and their provenance. Unknown fields remain null with reason; no guessing from file extension or histogram. Verify supplied checksums using their declared algorithm and independently compute SHA-256. Use metadata/license first and download a bounded appropriate subset or documented archive with storage approval. Do not republish raw data unless license permits.

H measurement requirements: total reference error 2^-20 pA for the electronic references, 2^-20 ms (0.953674 ns) for timing, analog error <=1/1024 pA, current grid 2^-30 pA, independent gamma/tau measurements of specified accuracy, no clipping, bounded residual jitter, and linear drift through 240 ms. These are synthetic assumptions, not instrument specifications. Ordinary sampling intervals do not establish timestamp jitter or calibration accuracy. Noise residuals can falsify a proposed bound but finite sample agreement cannot prove a universal bounded-noise law. Series resistance, imperfect clamp, filtering, capacitance, offsets and leak must be modeled or explicitly excluded; inability to identify an artifact becomes an uncertainty or blocker. H's voltage clamp model cannot be validated by an unrelated current-clamp trace. Harkin dataset is dorsal raphe, not pineal tissue as the source report incorrectly stated.

## Tool selection

| Tier | Tool / official location | Reason and admission |
|---|---|---|
| 0 | Python 3.12.16 stdlib Fraction, itertools, unittest, hashlib | Exact finite oracle and deterministic proof replay; zero external runtime dependency. Existing repo interval arithmetic for continuous proofs; validate scope and coefficient bounds. |
| 1 | [Lean 4](https://github.com/leanprover/lean4) + [mathlib](https://github.com/leanprover-community/mathlib4) | Candidate for mechanizing finite theorem and covering lemmas; pin compatible toolchain and mathlib revision; separate proof CI, no use of admitted axioms to masquerade as completed proof. |
| 1 | [Z3](https://github.com/Z3Prover/z3), [cvc5](https://github.com/cvc5/cvc5) | Candidate exact linear/rational feasibility or discrete search cross-check; proof obligations independently replayed; unsupported transcendental operations or unknown cannot certify. No need to install for DS01. |
| 2 | [HiGHS](https://github.com/ERGO-Code/HiGHS), [SciPy](https://scipy.org/), [Pyomo](https://www.pyomo.org/) | Candidate numeric LP/MILP and baselines; floating solver output is only a proposal unless checked by an exact certificate. Prefer open solver before proprietary requirements. |
| 2 | [Neo](https://github.com/NeuralEnsemble/python-neo), [PyNWB](https://github.com/NeurodataWithoutBorders/pynwb), [AllenSDK](https://github.com/AllenInstitute/AllenSDK) | Candidate data readers; separate environment, lock versions after compatibility test; use correct protocol and units. |

Official links are pointers; exact dependency versions/licenses are NOT_ADMITTED until pinned and verified. No external source packages downloaded in this intake.

## Baselines: do not mix incompatible tasks

Finite information-acquisition baselines: no acquisition, fixed full or fixed static optimal acquisition, greedy one-step worst-regret gain/cost, exact worst-case DP oracle, decision-region hyperedge method (Javdani 2014; implement its declared Bayesian premise separately), current COG-INFO/PLAN. Same initial record, test catalogue, prices, action labels, epsilon, maximum horizon and seed/cohort. Report certified coverage, violation count, worst regret, abstention and conditional acquisition cost; report wall clock, peak memory, verification overhead and oracle gap. Do not report low cost from failing/abstaining as efficiency. Separate expected-cost and worst-case objectives.

Model-compute baselines only after model task, matching backbone and evaluation contract are frozen: fixed depth; actual [Switch Transformer paper](https://arxiv.org/abs/2101.03961); actual [Mixture-of-Depths paper](https://arxiv.org/abs/2404.02258); adaptive/early exit baseline; existing CWC. Paper IDs are source leads, not executed baselines. Match training tokens, hardware, precision, inference FLOPs, router/control cost, wall latency and memory; GPU benchmarking requires separately available compute. Retain previous learned routing failure.

## External reproducibility checklist

- Immutable Git commit and tree IDs, repository license, exact Python/solver environments, source archive SHA-256, frozen protocol, code and data manifests.
- No stale or mixed attempts. Record exact head/base/checkout, run ID and attempt, all job statuses, artifact archive SHA-256 and payload SHA-256 separately.
- Rerun DS01 with `python -m unittest discover -s tests -p test_cwc_decision_sufficiency.py -v` and `python -m experiments.cwc_decision_sufficiency.oracle`. Compare canonical bytes on native profiles. Independently verify proof tree and recompute numerical quantities.
- Review original G/H/I evidence and proofs at their pinned commits; distinguish same-project independent code reconstruction from external replication. Preserve failures and UNKNOWN.
- Independent reviewer checks all three distinct decision concepts, obstruction cover, exact feasibility vs outer cover, budgets, model updates, leakage and authority. Require evidence of independent custody for blind review.
- Scope-specific claim table; no statement of real calibration, control or global scientific priority without evidence. Archive negative results. Obtain DOI only via an actual authorized deposit; no fictional DOI. [World Bank reproducible research guidance](https://worldbank.github.io/wb-reproducible-research-repository/guidance_note_wb.html) is a packaging reference from the supplied report.
