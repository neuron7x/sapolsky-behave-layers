# Research risk and acceptance record

Scope: public research repository, frozen synthetic qualification and source-custody
work on external workloads. [The programme charter](../../CWC_CLOSURE.md) governs
scientific closure. [The DGC pointer](../../artifacts/dgc-product-v1/PRODUCT_QUALIFICATION_POINTER_V3.json)
records current production authority. Ratings below are qualitative engineering
assessments of consequence. No incident rates or occurrence probabilities are inferred.

| Failure mode | Effect and control | Residual state and responsibility |
| --- | --- | --- |
| Wrong evidence identity or altered package | A reader can reproduce different bytes. Require exact commits, complete package roster, blob and mode comparison, archive hashes and a restored replay. | OPEN. The package owner must supply a clean restore and independent verifier before artifact acceptance. |
| Incomplete input or source terms | A logically coherent manifest can bind the wrong cohort or authorize inappropriate processing. Reconstruct frozen source and cohort identities, audit held-out exposure and review actual use and terms. | OPEN. Source custodian and competent approval role required before any external execution authorization. |
| Evaluator accepts invalid accounting or misaligned gold | A result can satisfy a metric with invalid input. Test gold identity, admissible action domains, resource counters and comparator eligibility before outcomes are observed. | OPEN. Research owner must accept protocol-faithful runner-bound validation before the first held-out run. |
| Publication converts conditional engineering evidence into scientific authority | A real-world conclusion can exceed the synthetic model and tested domain. Bind every claim to scope, protocol, falsifier and exact receipt. Verify reported identity and conduct external replay when claimed. | OPEN. Author and external reviewer have separate acceptance obligations. |
| Replay loses raw results or original negatives | An artifact can cease to be resolvable, or contrary evidence can disappear. Keep immutable historic Git objects and preserve hosted metadata and allowed payloads before expiry. | OPEN. Verify a clean restoration from the proposed persistent deposit and preserve the receipt. |

## Failure tree

The top event is an unsupported acceptance. Sufficient branches include the
admission of invalid source or model identity, acceptance of a verdict with
invalid inputs, acceptance of a mismatched package, or promotion above the
receipt's stated authority. Each branch closes only when a negative control
detects its failure and the relevant evidence is bound to the accepted identity.
The existence of this tree records an analysis, with no quantitative risk claim.

## Correction, recovery and acceptance

Register observed defects in [FINDINGS](FINDINGS.json) with original blob and a
specific disposition. A proposed correction needs independent review and an exact
post-change receipt before closure. For package recovery, reconstruct from a clean
full-history candidate and compare the published byte roster before rerunning the
scoped result. Preserve failures and do not overwrite frozen outputs. The clean
restore remains an open acceptance condition.

The audit inventory and acceptance command are described in
[the audit record](DOCUMENTATION_AUDIT.md). Responsible source, release and external
review roles must be assigned by the owner. No signature, regulator approval,
operational commissioning, badge or independent completion is recorded here.
