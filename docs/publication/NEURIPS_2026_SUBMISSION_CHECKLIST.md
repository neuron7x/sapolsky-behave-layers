# NeurIPS 2026 Main Track documentation crosswalk

Internal, prospective assessment against the [official paper checklist](https://neurips.cc/public/guides/PaperChecklist)
and [2026 handbook](https://neurips.cc/Conferences/2026/MainTrackHandbook). The sixteen
rows below preserve the official question order. The selected submission and its
paper determine final answers. This repository records no submission or venue decision.

| # | Obligation | Evidence and status |
| --- | --- | --- |
| 1 | Scope the paper's claims | INCOMPLETE. [Programme charter](../../CWC_CLOSURE.md) and [claim registry](../../claim_registry.json) provide scoped claims. Align a final paper with its actual evidence. |
| 2 | Expose assumptions and limitations | INCOMPLETE. [Threats and limitations](THREATS_TO_VALIDITY_AND_RED_TEAM.md) and [formal model](../architecture/FORMAL_MODEL.md). Bind the exact paper and artifact. |
| 3 | Supply assumptions and proofs for theoretical results | INCOMPLETE. [Proof obligations](../architecture/FORMAL_MODEL.md) and the [frozen JOINT-LP protocol](../../experiments/cneh_joint_lp/PROTOCOL.md) cover a scoped body of results. Check final theorem roster and derivations. |
| 4 | Provide an avenue for result reproduction | INCOMPLETE. [CI and replay](../vnv/CWC_TEST_AND_CI_REFERENCE.md) binds historic receipts. Provide a working reproduction route for the submitted contribution. |
| 5 | Document access to code, data and instructions | INCOMPLETE. [Data plan](../data/DATA_MANAGEMENT_AND_SHARING_PLAN.md) and [artifact guide](../reproducibility/ARTIFACT_README.md) identify access boundaries and artifact gaps. |
| 6 | Describe settings, sampling and selection | INCOMPLETE. [Frozen external protocol](../../experiments/real_transfer_01/PREREGISTRATION.md) sets rules. Only report settings for actual runs. |
| 7 | Justify statistical comparisons | INCOMPLETE. [SAP](../methodology/STATISTICAL_ANALYSIS_PLAN.md) and per-experiment rules distinguish descriptive intervals and acceptance thresholds. |
| 8 | Disclose computational resources | INCOMPLETE. [Hardware and cost guide](../reproducibility/EXPECTED_RUNTIME_HARDWARE_AND_COST.md) is historical. Record actual environment, time and resource use per result and in aggregate, including preliminary work where applicable. |
| 9 | Assess venue ethics | INCOMPLETE. Apply the [venue code](https://neurips.cc/public/EthicsGuidelines) to the selected contribution and record author review and any deviations. |
| 10 | Discuss societal effects | INCOMPLETE. [Broader impacts](LIMITATIONS_BROADER_IMPACTS_AND_ENVIRONMENT.md) exists. Review actual data, claims and intended use in the paper. |
| 11 | Address release safeguards where applicable | INCOMPLETE. [Research risks and acceptance](../assurance/RESEARCH_RISK_AND_ACCEPTANCE.md) records boundaries. Reassess the release contents and misuse risks before distribution. |
| 12 | Credit and respect reused assets | INCOMPLETE. [Third-party notices](../../THIRD_PARTY_NOTICES.md) and [external terms review](../../experiments/cwc_manifest_candidate/TERMS_AND_COMPUTE_REVIEW.md) precede source admission. |
| 13 | Document new assets | INCOMPLETE. [Artifact guide](../reproducibility/ARTIFACT_README.md) and [data dictionary](../data/DATA_DICTIONARY.md) support existing assets. Re-evaluate the license, consent basis where applicable, documentation and anonymized access for each included asset. |
| 14 | Report participant and crowdsourcing work when used | INCOMPLETE. Scope each submission to actual collection and processing. The audited external stage reconstructs existing sources. |
| 15 | Address human-subject approvals where required | INCOMPLETE. Determine actual activities, jurisdiction and review authority. Record the applicable formal review or documented equivalent process under the venue's guidance. |
| 16 | Describe qualifying LLM roles in the method | INCOMPLETE. [AI-assistance disclosure](AUTHOR_FUNDING_COI_AND_AI_ASSISTANCE_DISCLOSURE.md) records known historical and documentation activities. The final paper must review method-specific involvement. |

The [targeted related-work review](RELATED_WORK_AND_NOVELTY_REVIEW.md) states its search
limits. [Independent reproduction](../risk/EXTERNAL_REVIEW_AND_INDEPENDENCE_PROTOCOL.md)
is a separate CWC obligation. Submission requirements must be rechecked for the next
selected venue, track and deadline.
