# Bibliography and proof obligations

Each row states what a source establishes, where CWC uses it and what remains to be tested. A claim about CWC needs evidence from CWC.

## Citation coverage

| Bibliography | Verification scope |
| --- | --- |
| [Central BibTeX](references.bib), [resolver record](BIBLIOGRAPHY_VERIFICATION.json), [related-work review](RELATED_WORK_AND_NOVELTY_REVIEW.md) | The offline gate reads stored resolver records. It checks entry rosters, metadata, titles subject to documented exceptions, claim IDs and coverage in the targeted related-work review. [Gate](https://github.com/neuron7x/sapolsky-behave-layers/blob/861718751198deeeda54a23efacb2227a819b49f/scripts/verify_bibliography.py#L29-L33) · [checks](https://github.com/neuron7x/sapolsky-behave-layers/blob/861718751198deeeda54a23efacb2227a819b49f/scripts/verify_bibliography.py#L53-L123). |
| [CNEH-JOINT-LP source audit, M01–M09](../../experiments/cneh_joint_lp/BIBLIOGRAPHY.md) | Separate targeted source-to-obligation review with primary links, fit and limitations. Its Markdown citations are outside the central BibTeX gate. |
| [Terminal convergence bibliography](../../experiments/cwc_closure/BIBLIOGRAPHY.md) | Sources for decision-region comparators, risk accounting, model provenance and frozen datasets. Read this dated bibliography together with the current source admission and frozen external protocol. |

## From source to obligation

| Source of record | CWC obligation and limit |
| --- | --- |
| Howard, *Information Value Theory* (1966), `howard1966voi` | The oracle gap bounds policy gain before routing cost. Measure the policy's own gain and the incremental cost of routing. [Derivation](../architecture/FORMAL_MODEL.md#adaptive-computation-and-information-cost). |
| Sims, *Implications of Rational Inattention* (2003), `sims2003inattention`, and Kullback, `kullback1967lower` | Credit antecedents for information-constrained choice and information bounds. A bound under a stated distribution or loss supplies no empirical performance claim. [Theory](../VALUE_OF_INFORMATION_RATE_FUNCTION.md) · [routability bound](../ROUTABILITY_INFORMATION_BOUND.md). |
| Boyd and Vandenberghe (2004), M01, and Applegate et al. (2007), M02 | First prove outer inclusion. For rows `Ax ≤ b`, the checker requires `λ ≥ 0` and `Aᵀλ = q` for objective `q`. An infeasibility certificate requires `q = 0` and `bᵀλ < 0`. The certificate covers the declared rational system and objective. [Checker](https://github.com/neuron7x/sapolsky-behave-layers/blob/861718751198deeeda54a23efacb2227a819b49f/experiments/cneh_joint_lp/kernel.py#L91-L125). |
| Necula and Lee (1996), and Necula (1997), M07 | The proposer searches. A separate Python checker verifies the certificate against the bound system and objective. Replay covers the exercised cases. [Implementation](https://github.com/neuron7x/sapolsky-behave-layers/blob/861718751198deeeda54a23efacb2227a819b49f/experiments/cneh_joint_lp/run.py#L136-L198). |
| Javdani et al. (2014), M04/C01, and Golovin and Krause (2011), M05 | Credit decision-region acquisition and conditional greedy guarantees as prior art. CWC's finite worst-case recursion and XOR obstruction have their own assumptions. Bayesian HEC comparison and generic greedy guarantees remain separate obligations. [DS01](../../experiments/cwc_decision_sufficiency/PROTOCOL.md). |
| Gao et al. (2012), Kong et al. (2018), M03, and de Moura and Ullrich (2021), M08 | Nonlinear completion and proof-assistant mechanization are prospective. A δ-SAT result establishes satisfiability of the weakened formula. An exact witness requires a separate check. The current checker is Python with exact rational arithmetic. [Scope and future obligations](../../experiments/cneh_joint_lp/BIBLIOGRAPHY.md#remaining-mathematics). |
| Angelopoulos et al. and Gibbs and Candès, M06/C02, and the original AVeriTeC/HybridQA papers, C04/C05 | Statistical risk and exact per-instance proof concern different objects. Use the frozen workload releases, cohort identities, metrics and amendments. Substituting a calibration method would require a prospectively qualified protocol. [Preregistration](../../experiments/real_transfer_01/PREREGISTRATION.md) · [dataset and source contract](../../experiments/real_transfer_01/INTAKE_CONTRACT.md). |

For a new citation, record author, title, version, stable identifier, resolver evidence, the exact theorem or fact used, its assumptions, the linked CWC claim or protocol and the experiment or proof that exercises it. Preserve contrary findings and distinguish a prospective comparison from a measured result. Cite an exact repository commit for software or evidence and record the run and digest when citing a measured output. [Software authorship](../../CITATION.cff) · [artifact identity](../vnv/CWC_TEST_AND_CI_REFERENCE.md#hosted-selection-and-identity).
