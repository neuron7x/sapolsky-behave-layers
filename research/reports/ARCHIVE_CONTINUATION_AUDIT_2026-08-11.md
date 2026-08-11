# CWC / nanochat — Archive Continuation Audit and Execution Record

Date: 2026-08-11  
Source archive: `nanochat-cwc-cog-info02-flagship-key-full.zip`  
Source SHA-256: `ccfaf1446f73841165b1a48e3af28b343efed8b2a390e1ea5399cc9afad1ab9e`  
Source Git HEAD: `a849b63f225483822cc7f3270a92e41b18506882`  
Audited implementation/governance HEAD: `d0ad43f` (`governance: enforce current preregistration ancestry`)  
Scope note: any later commit in the delivered archive only adds this audit report / packaging metadata unless stated otherwise.

## 1. INTENT

Resume the causal/cognitive R&D chain from the archived repository state, treat the repository and sealed artifacts as the executable source of truth, attack the current claims before extending them, execute the next logically downstream tasks, preserve every negative, and leave a downloadable full repository with Git history.

No production, real-world causal-superiority, semantic-causality, frontier-capability, or independent-replication claim is authorized by this work.

## 2. SOURCE ARCHIVE VERIFIED STATE

Archive central-directory inspection:

- `[ANCHORED | procedure: ZIP central-directory count]` 8,151 entries.
- `[ANCHORED | procedure: sum ZipInfo.file_size]` 129,603,268 uncompressed bytes.
- `[ANCHORED | procedure: sum ZipInfo.compress_size]` 72,877,493 compressed bytes.
- `[ANCHORED | procedure: read archived .git/HEAD and branch ref]` source branch `agent/cog-info-02-decision-relevant`, HEAD `a849b63f225483822cc7f3270a92e41b18506882`.
- `.git`, `cwc/`, `tests/`, `experiments/`, `research/`, `runs/`, `artifacts/`, schemas, CI workflows, SBOM material and release/reproducibility material are present.

Initial test discovery before the continuation work found 490 tests. After CAB-01, COG-SELF-01, the evidence repair and the current preregistration gate, current discovery is:

- `[ANCHORED | procedure: python -m pytest --collect-only -q]` 518 tests.
- `[ANCHORED | procedure: pytest collect with -m 'not slow and not mutation']` 517/518 selected; 1 deselected by marker.

A monolithic full-suite invocation did not finish inside the execution window and is therefore **UNKNOWN**, not PASS. Tests were subsequently executed in smaller partitions; no assertion failure was observed in the completed partitions. The long `CSCA-03R` current-tree and semantic self-attack commands were executed directly and both passed.

## 3. CAB-01 — CAUSAL AUTHORITY BENCHMARK QUALIFICATION

### 3.1 Prospective execution registration

Created `research/preregistration/CAB_01_QUALIFICATION_EXECUTION.md` and committed it before implementation/result generation:

- prereg commit: `f55fde0f7eee54f88f6f0443d3de48dbbb582afe`
- implementation commit: `a8ed935f1140eb5dba2e971dcf20229831fd1e12`

Frozen design included 12 task families (`F0..F11`), independent construction/runtime label paths, eight baselines, deterministic replay, leakage controls, paired surface triads, PRIMARY/REPLICATION cohorts and a no-promotion boundary.

### 3.2 Q1 negative preserved

Authoritative Q1 result: `CAB01_Q1_NOT_QUALIFIED`.

Per cohort:

- `[ANCHORED | verdict.json]` 1,792 cases.
- `[ANCHORED | verdict.json]` 0 label-path disagreements.
- `[ANCHORED | verdict.json]` F11 paired triads passed.
- `[ANCHORED | verdict.json]` surface-only held-out accuracy = 0.28690807799442897.
- `[ANCHORED | verdict.json]` preregistered full-cohort-majority null = 0.2857142857142857.
- Because `0.28690807799442897 > 0.2857142857142857`, both cohorts failed the frozen leakage gate.

The negative was checksum-bound and committed unchanged as evidence:

- evidence commit: `2d3bec65972a213dcdb0f24ef53a4edf4b3f0ec2`
- gate self-attack: `[ANCHORED | scripts/cab01_q1_gate.py --self-test]` 7/7 injected semantic mutations detected.

Interpretation: the Q1 benchmark was **not qualified**. The result is not reinterpreted as a positive merely because the observed excess was caused by held-out class-prior drift under a single surface signature.

### 3.3 R1 repair preregistered before execution

The repair changed only the leakage null reference: compare the held-out classifier to the majority rate on the **same held-out fold**, plus require exactly one structural surface signature. Generator semantics, task families and scientific policies remained frozen. Fresh seed namespaces were mandatory.

- R1 prereg commit: `fdd89e4c6ef578647e8522035a6bbbb62185c33f`
- R1 evaluation implementation commit: `66f04a33993b910d9d035b0722d2aeb4682a34cc`
- fresh seed bases: `[ANCHORED | prereg/verdict]` PRIMARY_R1 510811, REPLICATION_R1 610811.

Authoritative result: `CAB01_Q1_R1_BENCHMARK_QUALIFIED_SYNTHETIC`.

Per fresh cohort:

- `[ANCHORED | verdict.json]` 1,792 cases.
- `[ANCHORED | verdict.json]` 0 label-path disagreements.
- `[ANCHORED | verdict.json]` F11 triads PASS.
- `[ANCHORED | verdict.json]` unique surface signatures = 1.
- `[ANCHORED | verdict.json]` held-out n = 359.
- `[ANCHORED | verdict.json]` surface classifier accuracy = 0.28690807799442897.
- `[ANCHORED | verdict.json]` same-fold held-out majority = 0.28690807799442897.
- leakage and structural-surface null predicates PASS.

Evidence commit: `c529099cc9d8c57d812a517753c4e810aa9115c9`.  
Gate self-attack: `[ANCHORED]` 8/8 mutations detected.

**Boundary:** CAB-01 R1 qualifies the internal synthetic benchmark mechanics only. It does not establish CWC superiority, real-model transfer, semantic causal truth, or external validity. Novelty remains `UNKNOWN_OVERLAP_CONCEDED`.

## 4. COG-SELF-01 — AUTONOMOUS FALSIFICATION GOVERNOR

### 4.1 Frozen criterion before implementation

Preregistration commit: `ee99a9e732e3b4fc408f80a9a3ce71d3178717d6`.

The governor is allowed to spend falsification compute only on certified, load-bearing attacks against admitted worlds that can change the current action. Same-decision ambiguity cannot justify spend. A test outcome may retract/invalidate bound authority, but `SURVIVED`/`INCONCLUSIVE` cannot mint or promote authority.

Implementation commit: `a77927568c246f91c04bd0b239b7ca625f851a74`.

### 4.2 Confirmatory result

Verdict: `AUTONOMOUS_DECISION_RELEVANT_FALSIFICATION_GOVERNOR_QUALIFIED_SYNTHETIC_NARROWED`.

Each PRIMARY and REPLICATION cohort contained:

- `[ANCHORED | verdict.json]` 12 families × 128 = 1,536 cases.
- `[ANCHORED | verdict.json]` every S0-S11 family passed 128/128.
- `[ANCHORED | verdict.json]` runtime errors = 0.
- false spend = 0.
- irrelevant attack selections = 0.
- uncertified attack selections = 0.
- stale-plan acceptances = 0.
- permutation disagreements = 0.
- survival promotions = 0.
- negative target violations = 0.
- stale/unbound outcome acceptances = 0.
- `[ANCHORED | verdict.json]` negative dependency propagation = 256/256.

Gate self-attack: `[ANCHORED]` 8/8 mutations detected.  
Evidence commit: `d48e715283e8098fc0d852a70d82280038c9e6fe`.  
Registry/document integration: `d4db9e27417519bf1e19232d51a69fc6bba39fcf`.

**Boundary:** this is a synthetic runtime safety/selection primitive. It does not establish that the selected attack is scientifically correct on real models, nor that survival is causal confirmation.

## 5. NULL-ATTACKS THAT FOUND REAL REPOSITORY DEFECTS

### 5.1 Frozen negative bundle was semantically incomplete

`make ... validate-evidence` initially failed:

`artifacts/history/cog-epistemic-01-initial-negative: missing CLAIM_BOUNDARY.json`.

Repair:

- added only governance metadata derived from the existing frozen negative verdict/report;
- raw `verdict.json` and `transition_matrix.csv` were not rewritten;
- preserved `SHA256SUMS.original`;
- extended current SHA256SUMS to bind the added boundary;
- evidence validator and checksum verification then passed.

Commit: `2b5f262` (`fix: restore frozen negative claim boundary`).

### 5.2 COG-SELF introduced a circular import that targeted tests missed

Repo-level causal-debt collection exposed:

`memory.epistemic_store -> epistemics.__init__ -> self_falsification -> memory.epistemic_store`.

The repair removed eager package-level re-export of `self_falsification`; callers already import the explicit module. Algorithm/evidence semantics were unchanged.

Commit: `5d5fb7d` (`fix: break epistemics memory import cycle`).

Post-fix:

- `[ANCHORED | pytest tests/causal_debt]` 20/20 PASS.
- `COG-SELF-01` semantic gate remains PASS.

This is the key integration lesson from the continuation: targeted confirmatory tests were insufficient to establish repository integration safety.

### 5.3 Reproduction documentation overstated current-head reproducibility

Reviewer-facing docs contained stale bibliography count, stale PyTorch/hardware claims and a reproduction sequence that did not install the exact-pinned verification toolchain. They also transferred the historical sealed WP16 clean-room PASS to a later HEAD.

Repair commit: `e7908b3` (`docs: repair current-head reproduction claims`).

Current documented sequence explicitly separates:

1. `uv sync --frozen --extra cpu` — runtime lock;
2. `make -f Makefile.cwc install-dev` — exact-pinned verification tooling;
3. current-tree verify/reproduction commands.

Historical WP16 evidence is now explicitly historical, not automatically inherited by later HEADs.

## 6. CURRENT-TREE PREREGISTRATION TEMPORAL INTEGRITY

The historical WP12 gate did not cover later `research/preregistration/` protocols. A registry-wide ancestry audit also exposed a wrong path for `H-COG-INFO-02`: the hypothesis registry pointed to an experiment-local file first added with the result, while the actual preconfirmatory preregistration is `research/preregistration/COG_INFO_02_DECISION_RELEVANT.md`, commit `87dbd88...`, a strict ancestor of result commit `7522765...`.

Implemented `scripts/current_prereg_integrity_gate.py`, wired into `doc-gate`, with a fail-closed rule:

- strict ancestor => PASS;
- same-commit => PASS only if already explicitly disclosed as retrospective;
- historical negative without independent prereg => may remain negative only;
- `RESULT_BEFORE_PREREG`, new undisclosed same-commit, missing tested verdict or unresolved prereg => FAIL;
- the historical WP12 self-audit cannot certify its own temporal ordering.

Current result:

- `[ANCHORED | current-prereg-gate]` hypotheses = 68.
- strict ancestor = 56.
- explicitly disclosed same-commit retrospective = 8.
- historical self-audit same-commit exclusion = 1.
- historical negative without independent prereg = 1.
- `NOT_TESTED` = 2.
- failures = 0.
- self-test = `[ANCHORED]` 8/8 decision mutations detected.

Commit: `d0ad43f` (`governance: enforce current preregistration ancestry`).

## 7. CURRENT ENGINEERING / EVIDENCE VERIFICATION

Completed post-change checks:

- `[ANCHORED | scripts/truth_gate.py]` PASS: >=91 test files, >=609 static tests, no unapproved skips/xfails/vacuous asserts, immutable CI image refs.
- `[ANCHORED | pytest collect]` 518 tests discovered on current tree.
- `[ANCHORED | scripts/validate_evidence.py]` PASS.
- `[ANCHORED | find artifacts -name SHA256SUMS + sha256sum -c]` 87 evidence bundles; all checksum manifests verified.
- `[ANCHORED | verdict_binding_gate]` 66 claims bound to sealed verdicts; 2 NOT_TESTED intentionally unbound; self-test 4/4 defects detected.
- `[ANCHORED | doc_status_gate]` 24/24 P0 docs, 68 claims, 68 hypotheses, 0 orphans.
- `[ANCHORED | bibliography gate]` 70 references, all machine-resolved; 12 areas; every entry claim-attached and argued.
- `[ANCHORED | architecture gate]` PASS.
- `[ANCHORED | hermeticity gate]` PASS for canonical evidence scripts.
- `[ANCHORED | complexity gate]` PASS.
- `[ANCHORED | SBOM gate]` 108 frozen components, PASS.
- `[ANCHORED | inference-integrity gate]` PASS.
- `[ANCHORED | assurance attack]` 5/5 injected engineering attacks killed.
- `[ANCHORED | assurance-report]` PASS.
- `[ANCHORED | git fsck --full]` return code 0; 6 dangling/unreachable objects reported. These are not object corruption, but should be garbage-collected only deliberately because one is an unreachable commit.
- `[ANCHORED | uv lock --check --python /opt/pyvenv/bin/python --no-python-downloads]` lock consistency PASS; 109 packages resolved from the existing lock metadata.

Selected execution suites that completed:

- Make `test`: 169 passed, 20 skipped.
- inference-integrity tests: 28 passed.
- data-intake: 9 passed.
- readiness: 17 passed.
- technical-quality tests: 4 passed.
- causal-debt: 20 passed after import-cycle repair.
- research-ingestion: 2 passed.
- research-execution: 3 passed.
- research-ops: 44 passed.
- current-prereg gate unit tests: 4 passed.
- verdict-binding tests: 9 passed.
- multiple broader test-file partitions completed without assertion failures; the monolithic 517-test non-slow/non-mutation command did not complete inside the tool execution window and therefore remains `UNKNOWN` as a single-command run.

## 8. ADMISSION GAPS — DO NOT PROMOTE TO PASS

### 8.1 `pr-fast`

Current sandbox result: **NOT EXECUTED TO COMPLETION**.

`truth-gate` passes, then lint stops because the host Python does not have `ruff` installed. The repository now documents the required exact-pinned `install-dev` step, but DNS restrictions prevented installing the clean verification environment here.

Status: `[UNKNOWN | procedure blocked by missing verification dependency, not by a lint finding]`.

### 8.2 `pr-security`

Current sandbox result: **NOT EXECUTED TO COMPLETION**.

The target requires Docker-pinned actionlint and gitleaks images. Docker is absent in this execution environment, so workflow-lint stops before gitleaks.

Status: `[UNKNOWN | external execution capability absent]`.

### 8.3 dependency audit

`uv export --frozen --extra cpu` succeeds, but `uvx pip-audit==2.10.1` cannot be fetched because sandbox DNS/network access is unavailable.

Status: `[UNKNOWN | vulnerability DB/tool acquisition unavailable]`.

### 8.4 canonical primary reproduction

`reproduce-primary` was attempted but did not complete inside the available execution window. Canonical evidence itself remains checksum-valid; that is not equivalent to current-head independent reproduction.

Status: `[UNKNOWN]`.

Therefore neither `pr-full` nor current-head clean-room reproduction is authorized as PASS by this audit.

## 9. SCIENTIFIC POSITION AFTER THIS CONTINUATION

What is now supported inside the repository:

1. CAB-01 R1 is a qualified **synthetic benchmark harness** for ACT / QUERY / ABSTAIN / REJECT_MODEL causal-authority decisions under its frozen constructed families.
2. COG-SELF-01 is a qualified **synthetic narrowed runtime primitive** for deciding when a falsification attack is decision-relevant and for enforcing monotone-negative outcome authority.
3. Current temporal-preregistration integrity is machine-checked against the live hypothesis/claim registries rather than inferred from an old meta-result.
4. Several negative records remain first-class and checksum-bound; no failed primary was deleted or silently converted to a success.

What is not supported:

- real-model generalization of CAB-01;
- independent authorship/contamination resistance for benchmark instances;
- third-party replication;
- causal truth recovery from passive equivalence classes;
- semantic/content-level causal attribution beyond existing narrowed operators;
- production autonomy;
- current-head full security admission;
- current-head clean-room `verify-full` reproduction;
- novelty as a broad theoretical mechanism.

## 10. NEXT HARD GATE

The next scientifically useful task is **not another synthetic family**. It is a matched-compute real-model transfer of the CAB/COG-SELF decision boundary with at least two externally grounded task families, independently authored or externally sourced instances, contamination controls, frozen ACT/QUERY/ABSTAIN/REJECT labels, strong constant/maximin/uncertainty baselines, and an independent replication path.

The kill criterion should remain: if the decision-relevant governor does not improve irreversible-action safety / necessary-query behavior at matched information/compute cost without collapsing into abstention, then no architecture promotion follows.

## 11. EVAL GATE

`PASS_WITH_CAVEATS`

Passed: internal synthetic scientific gates added in this continuation, checksum/evidence integrity, registry/verdict coherence, current-tree prereg temporal gate, core engineering assurance, targeted and partitioned integration tests.

Unclosed: exact clean dev environment, canonical `pr-fast`, Docker security gate, live dependency vulnerability audit, monolithic full-suite completion, canonical current-head primary reproduction, external/real-model CAB transfer, independent replication.
