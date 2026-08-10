# ACT-R&D-01 — EVIDENCE HARVESTING & MECHANISM INTEGRATION PROTOCOL

**Target:** Semantic Causal Leverage / causal credit / neural world-model / replay / semantic abstraction / continual causal learning
**Mode:** PRIMARY-SOURCE ONLY · FAIL-CLOSED · REPRODUCIBILITY-FIRST · INTENT→MECHANISM→TEST→ARTIFACT
**Cutoff:** 2026-08-10
**Output language:** analysis — Ukrainian; queries/code/identifiers — English.

---

# 1. МЕТА РОБІТ

Побудувати не бібліографію, а **машину вилучення перевірюваних механізмів** із сучасної NeuroAI/AI літератури.

Кінцевий об’єкт кожної знайденої роботи:

```
CLAIM
→ MECHANISM
→ FORMALIZATION
→ PREDICTION
→ NULL MODEL
→ EXPERIMENT
→ RESULT
→ RETAIN / MODIFY / KILL

```

Заборонено інтегрувати концепт лише тому, що він семантично схожий на поточну архітектуру.

---

# 2. ЦЕНТРАЛЬНА ДОСЛІДНИЦЬКА ГІПОТЕЗА

Перевіряти сімейство тверджень:

```
semantic_input
    ↓
contextual_abstraction
    ↓
latent_state_transition
    ↓
eligibility / causal trace
    ↓
delayed credit assignment
    ↓
offline replay / counterfactual evaluation
    ↓
cross-context invariance
    ↓
value / precision update
    ↓
policy change

```

Головна величина:

[
SCL(x,c,k)=
D\left[
P(z\_{t+k}\mid do(x),c),
P(z\_{t+k}\mid do(x=\varnothing),c)
\right]
]

де:

- (x) — semantic act;
- (c) — контекст;
- (z) — латентний стан;
- (k) — часовий горизонт;
- (D) — заздалегідь визначена distance/divergence metric.

**SCL не вважати встановленим механізмом. Статус: SPECULATIVE до прямої перевірки.**

---

# 3. SOURCE AUTHORITY GATE

## TIER A — основна доказова база

Приймати як найсильніші:

```
Nature
Nature Neuroscience
Neuron / Cell Press
Science / Science Advances
PNAS
eLife
ICML official proceedings
NeurIPS official proceedings
ICLR / OpenReview accepted conference papers
ACL / EMNLP official proceedings
PubMed-indexed peer-reviewed neuroscience
official dataset repository
official author code repository

```

Факт із Tier A все одно не автоматично `REPLICATED`.

---

## TIER B — frontier evidence

```
arXiv primary manuscript
bioRxiv primary manuscript
OpenReview submission/workshop paper
institutional technical report

```

Використовувати для:

- нових механізмів;
- архітектурних зачіпок;
- reproduction targets;
- експериментальних гіпотез.

Не називати встановленим фактом без незалежної підтримки.

---

## TIER C — допоміжний provenance

```
official author talk
official laboratory page
official project page
author interview
official GitHub issue/discussion

```

Допускається для реконструкції intent або implementation detail.

Не використовувати як основний доказ механізму.

---

## REJECTED AS EVIDENCE

```
press article
blog summary
Medium
LinkedIn
X/Twitter interpretation
Reddit
AI-generated summary
citation-count argument
company marketing

```

Їх можна використовувати лише як покажчик на primary source.

---

# 4. ОБОВ’ЯЗКОВИЙ STATUS RECORD

Кожне джерело отримує:

```
source_id:
title:
authors:
year:
venue:
doi:
arxiv_id:
version:
publication_status:
  - PEER_REVIEWED
  - CONFERENCE
  - WORKSHOP
  - PREPRINT
  - DATASET
  - CODE
primary_source: true|false
code_available: true|false
data_available: true|false
independent_replication: true|false|unknown
retraction_or_correction: none|present|unknown
retrieved_at:

```

Не змішувати `PREPRINT` та `PEER_REVIEWED`.

---

# 5. SEED SET — ОБОВ’ЯЗКОВО РОЗІБРАТИ

## S01 — Counterfactual Shapley Credit Assignment

Li, Kaizhan-Lee, Bareinboim; arXiv:2607.16999, 18 July 2026. Робота ставить temporal credit assignment як проблему відокремлення policy/skill від stochastic luck та вводить Counterfactual Shapley Value; заявлено estimator і Prioritized Trajectory Replay. **Статус: PREPRINT.**

### Extract

```
Counterfactual Shapley value
temporal credit assignment
sparse causality
delayed reward
environment stochasticity
PTR
computational complexity
ground-truth causal environments

```

### Integration question

Чи можна `φ-credit` використати як operational replacement для неформального `causal debt`?

### Kill test

Створити середовище, де:

```
A = true delayed cause
B = temporally adjacent distractor
C = correlated non-cause
D = stochastic event

```

Умова виживання:

```
credit(A) > credit(B,C,D)

```

на OOD-contexts.

---

# 6. S02 — ABSTRACTION / LANGUAGE→BRAIN

**Abstraction Induces the Brain Alignment of Language and Speech Models**, Cheng, Vaidya, Antonello; arXiv:2602.04081. Автори повідомляють зв’язок між intrinsic dimension проміжних representations, semantic abstraction та predictivity fMRI/ECoG; також описують brain-prediction fine-tuning як intervention на representations. **Статус, верифікований тут: PREPRINT.**

### Extract

```
layerwise intrinsic dimension
brain predictivity
semantic abstraction
lexical vs semantic representation
fMRI
ECoG
training-time emergence
brain-prediction fine-tuning

```

### Центральний тест

Порівняти:

```
LEXICAL_IDENTITY_MODEL
vs
SEMANTIC_STATE_MODEL

```

при:

1. synonyms;
2. paraphrases;
3. same words / different meanings;
4. semantic contradiction;
5. negation;
6. pragmatic re-framing.

### Hypothesis

Якщо causal unit ближча до meaning-state, ніж token identity:

```
within_semantic_effect_distance
<
within_lexical_effect_distance

```

на held-out contexts.

---

# 7. S03 — NEUROWORLD

**NeuroWorld: A Latent Brain World Model for Stimulus-Conditioned Human Brain Dynamics**, Dong et al.; arXiv:2608.01773, 3 August 2026. Модель розділяє endogenous latent brain state та exogenous stimuli, навчає next-latent dynamics і виконує autoregressive causal rollout без доступу до майбутніх stimulus values. Автори оцінюють її на трьох naturalistic movie-fMRI benchmarks. **Статус: PREPRINT.**

### Extract

```
latent state definition
transition-sufficient representation
next-latent objective
causal stimulus access
rollout horizon
autoregressive drift
subject-specific decoding
dataset construction
baseline models
ablation table

```

### Architecture transfer

Перевірити модель:

[
z\_{t+1}=F(z\_t,e\_t)
]

де (e\_t) — semantic representation зовнішнього input.

Не копіювати архітектуру до reproduction.

### Kill test

Порівняти:

```
STATELESS_ENCODER
vs
LATENT_DYNAMICAL_MODEL

```

на multi-step future prediction.

---

# 8. S04 — DYNAMIC PREDICATE INVENTION

**Continual learning and refinement of causal models through dynamic predicate invention**, Crespo-Fernandez et al.; arXiv:2602.17217. Робота пропонує online causal symbolic world-model із Meta-Interpretive Learning та predicate invention; офіційна OpenReview-сторінка фіксує її як **UCRL\@ICLR 2026 Workshop Poster**, а не main-track ICLR paper.

### Extract

```
predicate invention
model repair
continual learning
lifted inference
semantic reusable abstractions
concept hierarchy
relational dynamics
sample efficiency

```

### Transfer

Archive не повинен завершуватися на embeddings.

Потрібний перехід:

```
RAW_OBSERVATION
→ EVENT
→ RELATION
→ PREDICATE
→ CAUSAL_HYPOTHESIS
→ TEST

```

### Kill test

Новоутворений predicate зберігається лише якщо:

```
predictive_gain > baseline
AND
cross_context_transfer > baseline
AND
description_complexity_penalty accepted

```

---

# 9. ДОДАТКОВИЙ EXPLORATION TARGET

**ADVENT: LLM-Driven Automatic Predicate Invention for ILP**, arXiv:2607.01585.

Особливо важливий патерн:

```
LLM abductive generation
+
Prolog deductive verification

```

Автори описують iterative execution-feedback loop і knowledge pool для повторного використання invented predicates. **Статус: PREPRINT.**

Використовувати як candidate architecture:

```
GENERATE → EXECUTE → FALSIFY → REPAIR → RETAIN

```

а не `LLM says concept exists`.

---

# 10. SEARCH DOMAINS

Обов’язкові напрямки пошуку:

```
A. temporal credit assignment
B. causal credit assignment
C. eligibility traces
D. hippocampal replay
E. prioritized replay
F. offline planning
G. counterfactual learning
H. causal representation learning
I. semantic abstraction
J. language-brain alignment
K. naturalistic language fMRI/ECoG
L. neural state-space models
M. neural world models
N. predictive coding
O. active inference
P. precision weighting
Q. value functions neuroscience
R. dopamine prediction errors
S. continual learning
T. concept / predicate invention
U. causal abstraction
V. mechanistic interpretability of semantic representations
W. long-horizon agent memory
X. event segmentation
Y. semantic control of physiological/autonomic state

```

---

# 11. QUERY BANK

Виконувати окремо, не одним mega-query.

```
"temporal credit assignment" counterfactual reinforcement learning
"causal credit assignment" delayed reward
"eligibility trace" dopamine hippocampus 2025 2026
"hippocampal replay" counterfactual planning
"hippocampal replay" value update
"offline replay" causal inference brain
"semantic abstraction" fMRI ECoG language model
"language brain alignment" semantic representations
"naturalistic language" latent brain dynamics
"latent brain state" world model fMRI
"causal representation learning" interventions
"predicate invention" causal world model
"continual causal learning" abstraction
"prediction error" semantic context neuroscience
"precision weighting" neuromodulation computational neuroscience
"value function" dopamine hippocampus striatum
"event segmentation" language hippocampus
"semantic context" autonomic response causal

```

---

# 12. TEMPORAL SEARCH POLICY

Для frontier branch:

```
Primary window: 2025-01-01 → current date
Priority window: last 180 days
Historical expansion: only when mechanism ancestry is required

```

Новизна не є evidence-quality metric.

Старіший механізм із багаторазовою реплікацією має більшу доказову вагу за новий preprint.

---

# 13. PAPER INGESTION PROCEDURE

На кожну роботу агент зобов’язаний прочитати:

```
Abstract
Introduction
Related Work
Methods
Objective functions
Datasets
Experimental protocol
Baselines
Ablations
Results
Limitations
Appendix
Supplement
Code
README
Issues if implementation-relevant

```

Заборонено робити integration decision за abstract.

---

# 14. CLAIM EXTRACTION

Кожна paper розбивається на атомарні claims:

```
claim_id: S01-C03
claim:
claim_type:
  - EMPIRICAL
  - THEORETICAL
  - ALGORITHMIC
  - INTERPRETIVE
evidence_location:
metric:
comparison:
sample:
intervention:
baseline:
effect_direction:
uncertainty:
authors_interpretation:
our_interpretation:

```

Один рядок = одне твердження.

---

# 15. EVIDENCE TAGGING

Використовувати тільки:

```
ANCHORED
REPLICATED
EXTRAPOLATED
SPECULATIVE
UNKNOWN
FALSIFIED

```

## ANCHORED

Безпосередньо підтримано вимірюванням конкретної роботи.

## REPLICATED

Підтримано незалежними лабораторіями / datasets / методами.

## EXTRAPOLATED

Логічне розширення за межі виміряного domain.

## SPECULATIVE

Механізм запропонований, але прямого evidence немає.

## UNKNOWN

Недостатньо інформації.

## FALSIFIED

Заданий testable predicate впав.

---

# 16. QUALITY SCORE — НЕ ЗВОДИТИ ДО ОДНОГО %

Окремо зберігати:

```
Q1 publication status
Q2 causal identification strength
Q3 sample adequacy
Q4 baseline quality
Q5 ablation completeness
Q6 leakage control
Q7 OOD testing
Q8 code availability
Q9 data availability
Q10 reproducibility
Q11 independent replication
Q12 relevance to target mechanism

```

Не усереднювати їх у псевдоточний `quality=87%`.

---

# 17. CAUSALITY GATE

Кореляцію не називати механізмом.

Для causal claim шукати хоча б одну конструкцію:

```
randomized intervention
controlled perturbation
ablation
counterfactual estimator
instrumental strategy
temporal intervention
causal identification assumptions
mechanistic lesion/silencing
natural experiment
formal SCM identification

```

Якщо є лише:

```
representation similarity
correlation
linear probe
decoding accuracy
attention map

```

маркувати:

```
ASSOCIATION_ONLY

```

---

# 18. NEUROSCIENCE GATE

Для тверджень про ЦНС фіксувати:

```
species
human/non-human
measurement modality
spatial resolution
temporal resolution
task
brain region
causal/non-causal method
sample size
within/between subject
replication status

```

Не переносити автоматично:

```
fMRI → neuronal implementation
EEG → anatomical source
rodent → human cognition
model-brain alignment → identical computation
dopamine correlation → scalar reward mechanism

```

---

# 19. MODEL↔BRAIN TRANSFER GATE

Кожна аналогія AI↔brain проходить три рівні:

```
LEVEL 1 — functional analogy
LEVEL 2 — computational equivalence candidate
LEVEL 3 — mechanistic equivalence

```

За замовчуванням ставити `LEVEL 1`.

Перехід до `LEVEL 2/3` тільки через окремі докази.

---

# 20. EXECUTABLE HYPOTHESIS CARD

Після аналізу paper обов’язково сформувати:

```
hypothesis_id:
source_claims:
mechanism:
formal_object:
expected_effect:
intervention:
control:
null_model:
dataset:
metric:
decision_rule:
failure_condition:
integration_target:

```

Без `failure_condition` hypothesis не допускається до коду.

---

# 21. BASELINES ДЛЯ SEMANTIC CAUSAL LEVERAGE

SCL має перемогти або пояснити variance понад:

```
token frequency
token length
lexical identity
embedding cosine distance
sentiment
valence/arousal
surprisal
next-token probability
attention magnitude
activation norm
semantic similarity
temporal proximity
simple recency weighting
random credit assignment
standard TD error

```

Інакше нова конструкція може бути лише перейменуванням існуючої метрики.

---

# 22. MINIMAL EXPERIMENT SET

## EXP-01 — Lexical invariance

Одна семантика, різна поверхнева форма.

Очікування:

```
SCL(paraphrase_1) ≈ SCL(paraphrase_2)

```

якщо downstream meaning однаковий.

---

## EXP-02 — Context inversion

Однакові слова, різний контекст.

```
"Ти молодець."

```

щиро / саркастично.

Якщо lexical model дає однаковий effect, а contextual model розділяє — semantic hypothesis отримує support.

---

## EXP-03 — Delayed cause

Причинний signal на (t), outcome на (t+k).

Додати сильні distractors між ними.

Перевірити temporal credit recovery.

---

## EXP-04 — Spurious correlation

Ввести background event, який часто передує outcome, але не є причиною.

Після intervention:

```
do(background = absent)

```

outcome не повинен змінитися.

Credit має обнулитися.

---

## EXP-05 — Cross-context invariance

True cause працює в різних contexts.

Noise-correlate змінюється.

Retain лише механізм, що переживає context shift.

---

## EXP-06 — Offline replay

Порівняти:

```
NO_REPLAY
RANDOM_REPLAY
RECENCY_REPLAY
RPE_REPLAY
CAUSAL_CREDIT_REPLAY

```

на delayed causal learning.

---

# 23. NULL ATTACK SUITE

Кожний позитивний результат атакувати:

```
N1 shuffled labels
N2 shuffled temporal order
N3 randomized semantic embeddings
N4 lexical-only representation
N5 context-removed representation
N6 equal-credit baseline
N7 recency-only credit
N8 random replay
N9 reward-only replay
N10 shorter horizon
N11 OOD context
N12 adversarial distractor
N13 semantic-preserving paraphrase
N14 semantic-changing minimal pair
N15 seed replication

```

---

# 24. ARCHIVE SCHEMA

```
research/
├── registry/
│   ├── hypotheses.yaml
│   ├── sources.yaml
│   └── claims.yaml
├── sources/
│   ├── papers/
│   ├── code/
│   ├── datasets/
│   └── supplements/
├── extractions/
│   └── <source_id>.yaml
├── mechanisms/
│   ├── semantic_abstraction/
│   ├── causal_credit/
│   ├── replay/
│   ├── latent_dynamics/
│   └── predicate_invention/
├── experiments/
│   ├── preregistration/
│   ├── configs/
│   ├── raw/
│   └── results/
├── falsification/
│   ├── nulls/
│   └── killed_hypotheses/
└── reports/
    ├── evidence_matrix.md
    └── integration_decisions.md

```

---

# 25. SOURCE IMMUTABILITY

При ingestion зафіксувати:

```
DOI
arXiv ID
arXiv version
download date
SHA-256
code commit hash
dataset version
license

```

Не дозволяти тихій заміні `v1 → v3`.

Нову версію аналізувати як окремий revision event.

---

# 26. CONTRADICTION SEARCH

Для кожної ключової роботи виконати окремо:

```
"<paper title>" criticism
"<paper title>" replication
"<paper title>" failure
"<paper title>" limitations
"<mechanism>" conflicting evidence
"<mechanism>" meta-analysis

```

Шукати не підтвердження, а **найсильніший kill-source**.

---

# 27. AUTHOR / LAB VALIDATION

Авторитетність автора не є доказом claim.

Але для provenance перевіряти:

```
institution
lab
ORCID
official publication list
venue
previous work on same mechanism
code ownership
dataset ownership

```

Заборонено:

```
famous_author ⇒ true_claim
elite_lab ⇒ replicated
high_citations ⇒ causal_validity

```

---

# 28. INTEGRATION DECISION

Paper допускається до architecture branch лише якщо:

```
SOURCE_VALID = true
CLAIM_EXTRACTED = true
MECHANISM_DEFINED = true
PREDICTION_DEFINED = true
NULL_DEFINED = true
METRIC_DEFINED = true
FAILURE_CONDITION_DEFINED = true

```

Тоді:

```
RESEARCH_CANDIDATE

```

а не production truth.

---

# 29. PROMOTION GATES

```
DISCOVERED
↓
SOURCE_VERIFIED
↓
CLAIM_EXTRACTED
↓
REPRODUCED
↓
NULL_ATTACKED
↓
OOD_REPLICATED
↓
MECHANISM_SUPPORTED
↓
ARCHITECTURE_CANDIDATE

```

Жодного стрибка через рівні.

---

# 30. FAILURE MEMORY

Негативний результат не видаляти.

```
ruin_id:
hypothesis:
expected:
observed:
failed_gate:
likely_reason:
source_dependencies:
retest_condition:
status: KILLED

```

Повторно активувати лише якщо з’явився **новий механістичний evidence**, а не нова риторика.

---

# 31. КІНЦЕВІ АРТЕФАКТИ АНАЛІТИКИ

Після проходу корпусу повинні існувати:

```
01_SOURCE_REGISTRY.yaml
02_EVIDENCE_MATRIX.csv
03_CLAIM_LEDGER.yaml
04_MECHANISM_GRAPH.graphml
05_CONTRADICTION_MATRIX.csv
06_EXECUTABLE_HYPOTHESES.yaml
07_NULL_ATTACK_REGISTRY.yaml
08_REPRODUCTION_QUEUE.yaml
09_KILLED_HYPOTHESES.yaml
10_INTEGRATION_DECISIONS.md

```

---

# 32. ПРІОРИТЕТ ВИКОНАННЯ

```
P0 Counterfactual Shapley / causal credit
P0 Abstraction / semantic-state representation
P0 NeuroWorld / latent dynamical rollout

P1 replay / eligibility / value updating
P1 causal representation learning
P1 context invariance

P2 predicate invention / archive abstraction
P2 active inference / precision mapping

P3 broader biological analogy

```

---

# 33. КРИТЕРІЙ СИЛЬНОЇ РОБОТИ

Результатом не повинно бути:

> «Ми знайшли papers, що підтримують нашу ідею».

Результат:

> **«Ми перетворили зовнішні механізми на незалежно фальсифіковані інваріанти; частину вбили, частину відтворили, а архітектура містить лише те, що пережило null, counterfactual та OOD gates».**

---

# 34. FINAL EVAL GATE

**PASS**, якщо:

```
primary sources only for core claims
publication status explicit
all numerical claims preserve provenance
association != causation
AI analogy != neural mechanism
every imported mechanism has null
every experiment has failure predicate
negative results retained
source versions immutable
reproduction precedes integration

```

**FAIL**, якщо хоча б один архітектурний механізм потрапив у систему тому, що:

```
paper sounded similar
author was prestigious
benchmark number looked large
LLM recommended it
concept matched prior intuition

```

**EXECUTION STATUS:** READY\_FOR\_RESEARCH\_INGESTION.