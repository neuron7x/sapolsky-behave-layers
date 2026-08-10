# ACT-R&D-02 — EXECUTION, COMPUTE & GOVERNANCE CONTROL

**CLASS:** NeuroAI Research Operations / Evidence-to-Executable-Mechanism
**MODE:** FAIL-CLOSED · PRIMARY-SOURCE FIRST · REPRODUCIBLE · HUMAN-GATED · COMPUTE-AWARE
**PRECONDITION:** `ACT-R&D-01` accepted
**OBJECTIVE:** перетворити research-ingestion pipeline на виконувану R&D систему, де джерело → claim → mechanism → experiment → falsification → integration має повний provenance.

> **Boundary:** внутрішні методи SSI/Sutskever не публічні. Цей акт не приписує їм конкретний pipeline; він реалізує frontier-level принципи: generalization-first, experiment-before-scale, expensive compute only after cheap falsification, separation of discovery and verification.

---

# 1. INTENT

Побудувати три операційні контури:

```
A. EVIDENCE INGESTION
source → immutable record → structured claims → evidence graph

B. COMPUTE GOVERNOR
hypothesis → cheap falsification → pilot → scale decision → expensive run

C. HUMAN GOVERNANCE
machine extraction → human causal judgment → independent verification → integration

```

Головний системний інваріант:

```
NO_EXPENSIVE_COMPUTE_WITHOUT_CHEAP_KILL_TEST
NO_ARCHITECTURE_CHANGE_WITHOUT_CAUSAL_GATE
NO_CLAIM_WITHOUT_SOURCE_PROVENANCE

```

---

# 2. VERIFIED STATE

Автоматизація придатна для:

```
source discovery
metadata acquisition
PDF/text normalization
citation extraction
claim candidate extraction
equation extraction
dataset/code discovery
duplicate detection
experiment-result parsing
metric computation
reproduction execution
null execution
artifact hashing
registry generation

```

Автоматизація **не є достатньою** для:

```
causal interpretation
claim-strength classification
biological mechanism equivalence
confound identification
validity of intervention
architecture promotion
resolution of contradictory evidence

```

Ці операції залишаються human-gated.

---

# 3. SYSTEM TOPOLOGY

```
                    ┌─────────────────────┐
                    │   SOURCE WATCHER    │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │ SOURCE IMMUTABILITY │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │ DOCUMENT NORMALIZER │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │ CLAIM EXTRACTOR     │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │ EVIDENCE GRAPH      │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │ HUMAN CAUSAL GATE   │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │ EXPERIMENT BUILDER  │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │ COMPUTE GOVERNOR    │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │ NULL / REPRO / OOD  │
                    └──────────┬──────────┘
                               ↓
                    ┌─────────────────────┐
                    │ INTEGRATION COUNCIL │
                    └─────────────────────┘

```

---

# 4. WORKSTREAM A — AUTOMATED INGESTION

## A1. SOURCE CONNECTORS

Підтримувати окремі adapters:

```
ArxivAdapter
CrossrefAdapter
PubMedAdapter
OpenReviewAdapter
SemanticScholarMetadataAdapter
OfficialRepoAdapter
DatasetRepositoryAdapter

```

Core evidence завжди завантажувати з primary source.

Search engine або secondary index дозволений тільки для discovery.

---

# 5. SOURCE FETCH CONTRACT

Кожний ingestion event повинен створювати:

```
source_id:
canonical_title:
authors:
publication_date:
venue:
doi:
arxiv_id:
arxiv_version:
source_url:
publication_status:
retrieved_at:
content_sha256:
metadata_sha256:
license:
code_url:
dataset_url:
parent_source:

```

`content_sha256` є обов'язковим.

Якщо hash змінився:

```
NEW_REVISION

```

а не silent overwrite.

---

# 6. IMMUTABLE RAW LAYER

Структура:

```
research/raw/
├── arxiv/
├── journals/
├── openreview/
├── code/
├── datasets/
└── metadata/

```

Raw-файли ніколи не редагуються.

Derived data зберігається окремо:

```
research/derived/

```

---

# 7. DOCUMENT NORMALIZATION

Pipeline:

```
PDF/HTML
→ structured text
→ sections
→ equations
→ tables
→ figures metadata
→ references
→ appendix

```

Обов'язково зберігати mapping:

```
normalized_span
→ original_page
→ original_section
→ original_source

```

Щоб будь-який extracted claim можна було повернути до первинного тексту.

---

# 8. CLAIM EXTRACTION ENGINE

LLM дозволено використовувати лише як:

```
CANDIDATE GENERATOR

```

не як verifier.

Для кожного paper генерувати:

```
claim_id:
source_id:
source_span:
page:
section:
claim_text:
claim_type:
variables:
population:
intervention:
comparison:
outcome:
metric:
result:
authors_interpretation:

```

Після extraction автоматично:

```
STATUS = UNVERIFIED_EXTRACTION

```

---

# 9. CLAIM NORMALIZATION

Claims приводити до мінімальної структури:

```
UNDER CONDITIONS C
INTERVENTION / DIFFERENCE X
CAUSES / PREDICTS / CORRELATES WITH
OUTCOME Y
MEASURED BY M

```

Приклад:

```
X predicts Y

```

не можна автоматично переписувати як:

```
X causes Y

```

---

# 10. AUTOMATED CLAIM ATTACK

Перед human review система сама перевіряє:

```
Does experiment contain intervention?
Is temporal order established?
Was randomization used?
Are alternative baselines present?
Does reported metric support stated direction?
Is there an ablation?
Is claim stronger than experiment?
Is sample/domain restricted?

```

Результат:

```
automatic_flags:
  causal_overreach:
  missing_control:
  no_ablation:
  observational_only:
  narrow_domain:
  unavailable_code:
  unavailable_data:

```

Це не verdict.

---

# 11. EVIDENCE GRAPH

Замість списку papers будувати graph:

```
CLAIM
├── SUPPORTED_BY
├── CONTRADICTED_BY
├── REPLICATED_BY
├── DEPENDS_ON
├── GENERALIZES
├── FAILS_UNDER
└── IMPLEMENTED_BY

```

Nodes:

```
Paper
Claim
Mechanism
Metric
Dataset
Experiment
CodeCommit
Hypothesis
NullModel
Result

```

---

# 12. INGESTION QUEUES

Три незалежні черги:

```
Q_DISCOVERY
Q_VERIFICATION
Q_REPRODUCTION

```

Заборонено виконувати reproduction без завершеного verification record.

---

# 13. DISCOVERY PRIORITY FUNCTION

Не використовувати citation count як основний score.

Priority визначається:

```
P(source) =
mechanistic_relevance
× falsifiability
× executable_transfer
× evidence_strength
÷ reproduction_cost

```

Це **ranking heuristic**, не scientific metric.

Усі компоненти зберігати окремо.

---

# 14. INGESTION ACCEPTANCE GATE

Source переходить у `SOURCE_VERIFIED`, якщо:

```
PRIMARY_SOURCE_RESOLVED
CONTENT_HASHED
VERSION_IDENTIFIED
PUBLICATION_STATUS_IDENTIFIED
CLAIMS_TRACEABLE_TO_SOURCE
NO_UNRESOLVED_METADATA_CONFLICT

```

Інакше:

```
QUARANTINED

```

---

# 15. WORKSTREAM B — COMPUTE ALLOCATION

Головний принцип:

> **Compute не використовується для компенсації слабкої гіпотези.**

Масштабування починається тільки після локальної фальсифікації.

---

# 16. FOUR-STAGE COMPUTE LADDER

## C0 — ANALYTIC KILL

GPU не використовувати.

Виконати:

```
dimensional consistency
identifiability check
information leakage analysis
toy counterexample
synthetic adversarial case
baseline comparison

```

Якщо гіпотеза падає тут:

```
KILL

```

---

## C1 — CPU / SMALL MODEL PILOT

Мета:

```
verify code path
verify metric
verify null
detect trivial leakage
estimate runtime
measure memory

```

Використовувати мінімальний dataset/model, здатний спростувати claim.

---

## C2 — SINGLE-GPU REPRODUCTION

Дозволено тільки після:

```
C0 PASS
C1 PASS

```

Вимірювати:

```
wall_time
GPU_time
peak_VRAM
CPU_RAM
disk_IO
energy_if_available
random_seed
software_commit
dataset_hash

```

---

## C3 — MULTI-GPU / FRONTIER SCALE

Дозволено лише коли:

```
MECHANISM_SURVIVED_NULLS
SIGNAL_REPLICATED_ACROSS_SEEDS
OOD_TEST_JUSTIFIES_SCALE
SCALING_QUESTION_IS_EXPLICIT

```

Не запускати великий training лише для отримання «кращого benchmark».

---

# 17. COMPUTE REQUEST OBJECT

Кожний дорогий запуск повинен мати:

```
compute_request_id:
hypothesis_id:
experiment_id:
scientific_question:
kill_condition:
why_small_scale_is_insufficient:
baseline_completed:
nulls_completed:
expected_information_gain:
hardware:
estimated_runtime:
estimated_vram:
seeds:
checkpoint_policy:
stop_condition:
owner:
approved_by:

```

Без `kill_condition` request відхиляється.

---

# 18. COMPUTE OBJECTIVE

Оптимізується не:

```
maximum benchmark

```

а:

```
INFORMATION_GAIN / COMPUTE_COST

```

Практичне правило:

> наступний compute unit купується лише тоді, коли він може змінити integration decision.

---

# 19. EARLY STOP POLICY

Experiment негайно зупиняється, якщо:

```
data leakage detected
null model matches target model
metric implementation invalid
training diverges irrecoverably
causal variable unavailable
result cannot change decision

```

Sunk-cost reasoning заборонений.

---

# 20. REPLICATION POLICY

Порядок:

```
R0 exact reproduction
R1 independent seed replication
R2 implementation perturbation
R3 dataset perturbation
R4 OOD context
R5 adversarial null

```

Architecture promotion заборонений після одного успішного run.

---

# 21. COMPUTE TELEMETRY

Для кожного run автоматично:

```
{
  "run_id": "",
  "git_commit": "",
  "dataset_hash": "",
  "seed": 0,
  "device": "",
  "wall_seconds": 0,
  "gpu_seconds": 0,
  "peak_vram_bytes": 0,
  "peak_ram_bytes": 0,
  "exit_code": 0,
  "metric_output": {},
  "artifact_hashes": {}
}

```

Числа заповнюються лише runtime instrumentation.

Ніяких estimated performance values у result ledger.

---

# 22. COMPUTE SCHEDULER PRIORITY

Порядок виконання:

```
P0 falsification
P1 exact reproduction
P2 null models
P3 OOD replication
P4 ablations
P5 architecture comparison
P6 scaling

```

Scale — останній, не перший.

---

# 23. WORKSTREAM C — HUMAN-IN-THE-LOOP

Людина використовується не для ручної роботи, яку може виконати машина, а для операцій, де помилка є **онтологічною**, а не синтаксичною.

---

# 24. HUMAN GATE H0 — SOURCE IDENTITY

Автоматизувати максимально.

Людина втручається тільки при:

```
conflicting versions
unclear publication status
paper/repository mismatch
ambiguous dataset provenance

```

---

# 25. HUMAN GATE H1 — CLAIM INTERPRETATION

Обов'язкова людина.

Перевірити:

```
What exactly was measured?
What does the result NOT establish?
Is interpretation stronger than evidence?
What variables are latent/unobserved?
What confounds remain?

```

Output:

```
CLAIM_ACCEPTED
CLAIM_DOWNGRADED
CLAIM_REJECTED

```

---

# 26. HUMAN GATE H2 — CAUSALITY

Не делегувати LLM фінальний verdict.

Reviewer повинен відповісти:

```
What is intervention?
What changes under do(X)?
What is held constant?
What alternate causal graph explains result?
Can temporal correlation explain it?
Can selection bias explain it?

```

---

# 27. HUMAN GATE H3 — BRAIN↔AI TRANSFER

Критичний gate.

Для кожного transfer:

```
Functionally similar?
Computationally homologous?
Mechanistically supported?

```

Default:

```
FUNCTIONAL_ANALOGY_ONLY

```

Поки немає stronger evidence.

---

# 28. HUMAN GATE H4 — EXPERIMENT DESIGN

Людина затверджує:

```
hypothesis
primary metric
null
negative control
failure predicate
OOD condition

```

до запуску.

Після результату змінювати primary metric заборонено без нового experiment ID.

---

# 29. HUMAN GATE H5 — ARCHITECTURE INTEGRATION

Інтеграція дозволена тільки якщо reviewer може сформулювати:

```
WHAT mechanism does
WHY mechanism is needed
WHAT evidence supports it
WHAT test can still kill it
WHAT simpler mechanism was rejected

```

Якщо останнє питання не має відповіді:

```
NO INTEGRATION

```

---

# 30. TWO-PERSON LOGIC WITHOUT TWO PEOPLE

Для solo-R&D ролі мають бути логічно розділені:

```
ROLE_A = BUILDER
ROLE_B = ADVERSARIAL REVIEWER

```

Навіть якщо це одна фізична людина.

Процедура:

```
Builder writes preregistration
↓
freeze
↓
Experiment executes
↓
Reviewer receives result + preregistration
↓
Reviewer attacks without modifying experiment

```

LLM можна використовувати в обох ролях, але з окремими context bundles.

---

# 31. LLM AUTHORITY BOUNDARY

LLM дозволено:

```
search
extract
normalize
summarize
generate hypotheses
generate nulls
write experiment code
run tests
compare outputs
find contradictions

```

LLM заборонено самостійно визначати:

```
scientific truth
causal validity
biological equivalence
final integration

```

Це governance invariant.

---

# 32. FULL EXECUTION LOOP

```
DISCOVER SOURCE
↓
HASH + REGISTER
↓
NORMALIZE
↓
EXTRACT CLAIMS
↓
AUTOMATED ATTACK
↓
HUMAN CLAIM GATE
↓
HUMAN CAUSAL GATE
↓
BUILD EXECUTABLE HYPOTHESIS
↓
PREREGISTER
↓
C0 ANALYTIC KILL
↓
C1 CHEAP PILOT
↓
C2 REPRODUCTION
↓
NULL ATTACKS
↓
OOD
↓
REPLICATION
↓
HUMAN INTEGRATION GATE
↓
RETAIN / MODIFY / KILL
↓
STORE RUIN

```

---

# 33. FIRST EXECUTION TARGET

Першим запускати:

```
Counterfactual Shapley Credit Assignment

```

Причина:

```
closest match to causal-debt hypothesis
formal object exists
synthetic environments possible
counterfactual claims directly testable
does not require biological dataset
cheap falsification available

```

Це дозволяє протестувати сам causal-credit kernel до переходу до fMRI/ECoG.

---

# 34. EXPERIMENT ACT — CSCA-01

## Hypothesis

Counterfactual credit краще відділяє delayed causal actions від temporal distractors, ніж:

```
recency
TD-error
uniform credit
random credit

```

---

# 35. SYNTHETIC ENVIRONMENT

Створити deterministic simulator з:

```
true_cause
delayed_outcome
correlated_distractor
random_distractor
context_variable
stochastic_noise

```

Ground-truth causal graph відомий генератору.

Evaluator не отримує graph.

---

# 36. PRIMARY METRIC

Не використовувати загальний reward як єдину метрику.

Використовувати:

```
causal_rank_accuracy

```

тобто чи отримує true cause вищий credit за non-causes.

Додатково:

```
false_credit_rate
OOD_causal_rank_accuracy
credit_calibration

```

---

# 37. NULLS

```
NULL-01 shuffle action timing
NULL-02 destroy causal link
NULL-03 preserve correlation only
NULL-04 remove delayed cause
NULL-05 increase noise
NULL-06 context inversion

```

Якщо method продовжує давати високий causal credit після `destroy causal link`:

```
FAIL

```

---

# 38. SECOND EXECUTION TARGET

Після causal-credit kernel:

```
Semantic Abstraction

```

Побудувати:

```
SemanticStateEncoder

```

і перевірити:

```
paraphrase invariance
context inversion
negation sensitivity
lexical distractor resistance

```

---

# 39. THIRD EXECUTION TARGET

Після цього:

```
LatentStateWorldModel

```

із:

```
z(t+1) = F(z(t), semantic_event(t))

```

і causal rollout.

Лише після цих трьох компонентів дозволити їх об'єднання в `Semantic Causal Leverage`.

---

# 40. INTEGRATION ORDER

```
1. CausalCredit
2. SemanticState
3. LatentDynamics
4. CounterfactualRollout
5. Replay
6. CrossContextInvariant
7. SemanticCausalLeverage

```

Не будувати SCL монолітом.

Кожний модуль має вижити незалежно.

---

# 41. REQUIRED REPOSITORY STRUCTURE

```
src/
├── ingestion/
├── registry/
├── evidence_graph/
├── claim_extraction/
├── causal_review/
├── experiments/
├── nulls/
├── compute_governor/
└── integration/

research/
├── raw/
├── derived/
├── preregistration/
├── results/
├── ruins/
└── reports/

tests/
├── ingestion/
├── provenance/
├── claims/
├── causal/
├── experiments/
└── reproducibility/

```

---

# 42. CI GATES

CI повинен падати, якщо:

```
source missing hash
claim missing source span
experiment missing null
experiment missing seed
result missing commit
metric undefined
integration missing evidence reference
killed hypothesis deleted

```

---

# 43. SSOT

Єдиний machine-readable source of truth:

```
research/registry/

```

Markdown звіти — derived artifacts.

Не навпаки.

---

# 44. MINIMAL DEPLOYABLE SYSTEM

Перша реально корисна версія системи повинна вміти:

```
ingest arXiv paper
freeze source
extract claims
link claims to exact source spans
mark causal weaknesses
create hypothesis card
generate preregistration
execute synthetic experiment
execute nulls
store result
produce integration verdict

```

Nature/PubMed/OpenReview adapters додаються після стабілізації arXiv path.

---

# 45. BOTTLENECKS

## B1 — Claim extraction hallucination

Mitigation:

```
source spans mandatory
no uncited extracted claim
human spot verification

```

## B2 — Causal language inflation

Mitigation:

```
predicts != causes
association-only flag
human H2 gate

```

## B3 — Compute escalation

Mitigation:

```
C0 → C1 → C2 → C3

```

без bypass.

## B4 — Research confirmation bias

Mitigation:

```
contradiction search mandatory
nulls before scaling
ruins retained

```

## B5 — Architecture accretion

Mitigation:

```
new module must beat simpler baseline

```

---

# 46. EXECUTION PRIORITY

```
P0 implement registry + immutable ingestion
P0 implement claim/source traceability
P0 implement compute governor
P0 implement human decision records

P1 reproduce Counterfactual Shapley
P1 build synthetic causal environment
P1 null attack suite

P2 semantic abstraction experiments
P2 latent-state world model

P3 replay
P3 SCL integration

```

---

# 47. DEFINITION OF DONE

ACT-R&D-02 завершується тільки коли система фізично може виконати:

```
SOURCE
→ CLAIM
→ HYPOTHESIS
→ PREREGISTRATION
→ RUN
→ NULL
→ RESULT
→ VERDICT

```

без ручного перенесення доказових даних між етапами.

---

# 48. EVAL GATE

**PASS** якщо:

```
ingestion reproducible
sources immutable
claims traceable
causal review human-gated
compute escalation controlled
cheap falsification precedes scaling
runs reproducible by commit+seed+data hash
nulls mandatory
OOD separated from IID
failed hypotheses preserved
architecture integration requires explicit evidence

```

**FAIL** якщо:

```
LLM summary becomes evidence
GPU scaling precedes falsification
claim lacks primary source span
causality inferred from correlation
brain/AI analogy promoted without gate
metric changes after observing result
negative result is deleted
architecture accepts mechanism without simpler baseline

```

---

# FINAL EXECUTION ORDER

```
ACT-R&D-02/PHASE-1
Build evidence substrate.

ACT-R&D-02/PHASE-2
Build compute governor.

ACT-R&D-02/PHASE-3
Reproduce causal-credit mechanism.

ACT-R&D-02/PHASE-4
Attack with nulls and OOD contexts.

ACT-R&D-02/PHASE-5
Only surviving mechanism proceeds to SemanticState integration.

```

**STATUS:** `READY_FOR_IMPLEMENTATION`

**NEXT HARD GATE:** `CSCA-01 — Counterfactual Credit Kernel Reproduction & Falsification`.