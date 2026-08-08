# Related Work and Novelty Review

**Status.** Completed targeted review, 2026-07-22. Supersedes the 2026-07-20 working
review, which declared itself `PENDING`. Every reference cited here exists in
[`references.bib`](references.bib) and was resolved against an external authority
(arXiv API, DOI content negotiation, OpenAlex, Open Library); the resolution record is
[`BIBLIOGRAPHY_VERIFICATION.json`](BIBLIOGRAPHY_VERIFICATION.json) and the agreement
between this document, that record and the BibTeX file is enforced by
`scripts/verify_bibliography.py`, which runs inside `make -f Makefile.cwc verify`.

**Scope honesty.** This is a *targeted, anchored* review, **not** a PRISMA-style
exhaustive systematic review. It is anchored on two field surveys — dynamic neural
networks [@han2021dynamicnn] and sparse expert models [@fedus2022sparsereview] — plus
backward chasing from the mechanisms CWC actually implements. A claim of exhaustive
coverage is **not** made and must not be made downstream. What *is* claimed is that the
nearest prior art for every mechanism CWC touches has been identified, read, and either
conceded or distinguished in writing.

---

## 1. Search procedure

| Item | Value |
|---|---|
| Date of this pass | 2026-07-22; §2.5.1 and the RIGOR3 rows amended 2026-08-08 |
| Resolvers of record | arXiv Atom API; doi.org CSL content negotiation; OpenAlex; Open Library |
| Anchor surveys (backward chase) | [@han2021dynamicnn], [@fedus2022sparsereview] |
| Query families | adaptive computation time; conditional computation; dynamic depth / early exit; mixture-of-experts routing; test-time compute scaling; value of information; rational inattention; rate–distortion; nonconcavity in the value of information; marginal value of information at the null; family-wise error; preregistration; mutation testing |
| Inclusion | work that (a) allocates or routes computation conditionally on the input, or (b) supplies a formal object CWC's theory or gates depend on |
| Exclusion | uniform scaling with no conditional mechanism; distillation/quantisation (orthogonal compression axis); anything CWC does not implement or depend on |
| Entries admitted | 70, all machine-resolved, 0 unresolved (65 at the 2026-07-22 pass; +5 in §2.5.1) |
| Known gap | the 2026-07-22 pass missed the economics-of-information nonconcavity line entirely — found by an external audit, not by this procedure; no forward citation chasing on the 2025 entries; no non-English sources; single reviewer (the author) — see [`THREATS_TO_VALIDITY_AND_RED_TEAM.md`](THREATS_TO_VALIDITY_AND_RED_TEAM.md) |

The repository forks nanochat [@karpathy2025nanochat]; the `master`/`baseline` branches
are unmodified upstream history and all CWC work is additive.

---

## 2. Prior art by area, and what CWC does *not* claim against it

### 2.1 Adaptive computation and conditional depth

Learned halting originates with Adaptive Computation Time [@graves2016act] and is
carried into transformers by Universal Transformers [@dehghani2019universal] and
PonderNet [@banino2021pondernet]; spatially adaptive variants [@figurnov2017sact],
early-exit branches [@teerapittayanon2016branchynet], learned layer skipping
[@wang2018skipnet] and block dropping [@wu2018blockdrop] cover the discrete-policy
space, and the general programme is stated in [@bengio2015conditional].

> **CWC claims no novelty anywhere in this paragraph.** Adaptive stopping, adaptive
> depth and learned skipping are solved prior art. CWC's object is one step earlier: on
> a *given* workload, is there anything for such a controller to allocate — i.e. is the
> context×resource interaction large enough to certify and to pay for? That question is
> assumed answered by every work above and is tested by `CWC-L1-identifiability` and
> `CWC-AC1-compute-identifiability`.

At scale the current frontier is Mixture-of-Depths [@raposo2024mod],
Mixture-of-Recursions [@bae2025mor], LayerSkip [@elhoushi2024layerskip] and recurrent
latent depth [@geiping2025recurrentdepth]. **`CWC-L7-pareto` is `NOT_TESTED`**: no
comparison against any of these has been run, none is claimed, and the synthetic Pareto
result `CWC-L7s-synthetic-pareto` is a harness demonstration on CWC's own mechanism, not
a competitive result. [@geiping2025recurrentdepth] and [@dehghani2019universal] are also
the scale-instances of CWC's own weight-tied substrate, which is why WP19's finding —
that WP18's "same best depth in every bucket" was an artefact of weight tying, not a
property of the data — is recorded as narrowing `CWC-RD4-negative-robustness` rather
than as a fact about language.

### 2.2 Sparse experts

Conditional expert selection runs from the original mixture of local experts
[@jacobs1991moe] through sparsely-gated MoE [@shazeer2017moe] to Switch Transformers
[@fedus2022switch], surveyed in [@fedus2022sparsereview]. CWC borrows load-balancing and
anti-collapse discipline for its controllers and makes **no MoE-superiority claim**. The
quantity CWC formalises as the two-way ANOVA interaction `γ[c,a]` is the same
context-conditioned choice value this line has optimised since 1991.

### 2.3 Real-workload adaptive compute — the prior art that *contradicts* CWC's negatives

This subsection exists because omitting it would be the single most dishonest move
available to this document. CWC records three real-data negatives
(`CWC-RD1-real-lm-boundary`, `CWC-RD2-real-lm-contextual`, `CWC-RD3-real-workload-pilot`)
while the literature reports *positive* results for input-adaptive compute on real NLP
workloads: instance-matched model capacity [@schwartz2020righttool], early exiting in
BERT [@xin2020deebert], depth-adaptive sequence generation [@elbayad2020depthadaptive],
and per-token confident early exit in language models [@schuster2022calm].

**Resolution, stated as scope rather than as dispute.** These works report *wall-clock or
FLOP savings at acceptable quality loss under a confidence rule*. CWC's certificate asks
a strictly stronger question: does the per-instance oracle gap exceed the *measured* cost
of making the routing decision, with a bound valid at δ = 0.05? Three differences carry
the whole disagreement, and none of them makes the prior work wrong:

1. **Unit of decision.** [@schwartz2020righttool] and [@xin2020deebert] decide per
   *sequence* in classification; CWC's negatives are per *token* in byte-level
   prediction, where the interaction measured is ≈0.001 nats.
2. **Currency.** Early-exit papers price a decision in saved compute at fixed quality;
   CWC prices it in certified utility net of the physically measured `c_route` = 0.0006
   model-forward equivalents (WP17), and `CWC-RIGOR9-route-cost-charged` shows the
   synthetic positive survives that charge while the real ones do not.
3. **Scale.** CWC's models are ≤1 MB corpora on a 4 GB laptop GPU. [@schuster2022calm]
   operates at a scale CWC has never reached. **The defensible CWC statement is not
   "adaptive compute does not pay on real data" — it is "on the workloads reachable
   here, the interaction is worth less than the decision costs."**

The forward-looking half of the same literature explains *where* the interaction should
be large: chain-of-thought reasoning [@wei2022cot], test-time compute scaling
[@snell2024testtime], latent-space reasoning [@hao2024coconut] — regimes where
per-instance demand varies by orders of magnitude. Speculative decoding
[@leviathan2023speculative] is the deployed proof that an adaptive scheme lives or dies
by the decision being cheaper than the work, which is `CWC-L2b-route-decision-cost`
stated in production terms. `CWC-R1-routability-screen` exists precisely to test such a
candidate workload cheaply *before* spending on it.

### 2.4 Plasticity and continual learning

CWC's plasticity line budgets *where a model is allowed to change*. Importance-weighted
continual learning — EWC [@kirkpatrick2017ewc], synaptic intelligence [@zenke2017si],
memory-aware synapses [@aljundi2018mas] — is the prior art for that framing, and CWC
claims no novelty for importance estimation. The biological source of "capacity to
change is itself allocated" is metaplasticity [@abraham1996metaplasticity]; the layered,
multi-timescale account of behaviour that gives this repository's parent directory its
name is [@sapolsky2017behave], cited as conceptual provenance with **no empirical weight
placed on it**.

### 2.5 Information theory, value of information — the largest concession in this document

CWC's theory documents define the oracle gap `G = V_oracle − V_fixed`, the routability
ceiling `V(Z) ≤ Δu·√(I(C;Z)/2)`, and the rate function
`V*(R) = max{V(Z) : I(C;Z) ≤ R}`, described in-repo as "the exact analogue of Shannon's
rate–distortion function for decisions."

**That analogy is not a metaphor and it is not new.** Stated plainly:

| CWC object | Established name | Source |
|---|---|---|
| oracle gap `G` | expected value of perfect information about the context, relative to a context-blind policy | [@howard1966voi] |
| ceiling via `√(I/2)` | Pinsker-type bound: total variation from divergence | [@kullback1967lower], [@kullback1951], [@cover2006elements] |
| `V*(R)` frontier | decision value under a mutual-information constraint — rational inattention | [@sims2003inattention] |
| soft-routing optimum `V*` exceeds committed-greedy policies | free-energy / information-cost formulation of bounded rationality | [@ortega2013thermo], [@ortega2015bounded] |
| numerical tracing of the frontier | Blahut–Arimoto | [@blahut1972], [@arimoto1972] |
| compression-vs-relevance in a noisy router signal | information bottleneck | [@tishby2000ib] |
| mutual information, rate-function form | [@shannon1948] | |

Consequences that are now written into the record:

- **`CWC-L4b-inferred-context` and `CWC-AC3-inferred-difficulty` are rediscoveries.**
  "The governor abstains as `I(C;Z) → 0`" is rational inattention [@sims2003inattention]
  in a compute-allocation costume. They remain `SUPPORTED` as *measurements on a working
  mechanism*, and their novelty claim is withdrawn to: an empirical demonstration that a
  reward-only learned controller tracks the theoretical boundary to ±0.001.
- **The low-information saturation gap (0.326) is structural, not a defect.** CWC's
  governors commit greedily; the optimum they are measured against is the soft
  information-cost optimum of [@ortega2013thermo]. That the gap widens with more contexts
  is the expected behaviour of a committed policy, and `CWC-L4i-rate-bridge` /
  `CWC-AC4-rate-bridge` should be read as ceiling-respect results, not optimality results.
- **`CWC-L2p-jensen-gap` is claimed conservatively.** The identity
  `adaptive − static = P(m > K)` is an optimal-stopping statement in the lineage of
  sequential analysis [@wald1945sprt]; CWC contributes the exact empirical verification,
  not the identity.

#### 2.5.1 The nonconcavity line — added 2026-08-08 after an independent audit

The 2026-07-22 pass argued `CWC-RIGOR3-pinsker` against Pinsker [@kullback1967lower] and
rational inattention [@sims2003inattention] and stopped there. An independent audit
observed that the *marginal value of the first unit of information* has its own
literature in the economics of information, that none of it was in `references.bib`, and
that the one surviving novelty candidate was therefore argued against the wrong
neighbours. That omission is corrected here rather than defended.

[@radner1984nonconcavity] is the origin: the value of information is not concave, and
under a regularity condition its marginal value **at zero information vanishes**.
Reparameterised from their informativeness index into mutual information, that is the
`Θ(R)` half of CWC's dichotomy. [@chade2002another] sharpens the regularity hypothesis —
unique prior-optimal action with a strict margin — which is precisely the condition CWC
calls REGULAR. [@delara2007tight] gives a tight sufficient condition for a zero marginal
value at the null stated on the information structure alone, independent of preferences,
and is the closest published statement to CWC's regular-case exponent.
[@whitmeyer2024cavity] states the split itself — a regime where the marginal value at
zero is strictly positive against one where it is almost always zero — but without rates
or exponents. [@delara2020payoffs] reaches CWC's indifference manifold from convex
duality: information is worth most exactly where the decision-maker is indifferent,
because a small signal breaks the tie.

**Consequence for the novelty claim.** The dichotomy *as a phenomenon* is prior art and
CWC asserts no priority over it. What a targeted search did not locate is the
quantitative form: the exponents `Θ(R)` versus `Θ(√R)` **in nats of mutual information**,
tied to the tightness of the Pinsker step and with the leading constant `c = std(D)/Δu`
pinned on the indifference manifold. §3 records `CWC-RIGOR3-pinsker` accordingly as a
narrowed candidate, and no stronger statement is licensed.

The biological precedent for per-instance variable processing time — evidence
accumulation to a bound — is [@ratcliff1978] and [@goldshadlen2007]. The energy axis
[@attwell2001energy], [@levy1996energy] names the currency CWC **abandoned**: energy is
recorded `INSTRUMENT_INVALID` on this hardware and no energy claim exists.

### 2.6 Statistical machinery of the certificate

The certificate's deviation terms are Hoeffding bounds [@hoeffding1963]; WP7's corrected
bound `G_lo = Ĝ − b − 2d` union-bounds two of them. Multiplicity is controlled by
Bonferroni and Holm's step-down procedure [@holm1979]; false-discovery-rate control
[@benjamini1995fdr] was deliberately **not** used and the choice is recorded rather than
defaulted, with [@johnson2013revised] as the argument for the stricter setting. Effect
sizes use bootstrap intervals [@efron1986bootstrap].

**Stated limitation.** The bound is fixed-sample. A certificate that may be inspected
repeatedly should be anytime-valid [@ramdas2022anytime]; CWC's is not, and this is
recorded as an upgrade path, not as an implemented property.

### 2.7 Research-integrity machinery

Strict-ancestor preregistration (`CWC-RIGOR7-prereg-integrity`, 19 preregistrations, 0
violations) implements [@nosek2018prereg]; the model it imitates *without an external
reviewer* is Registered Reports [@chambers2013registered], and that missing reviewer is
conceded, not glossed. The clean-room spine (WP16) follows [@munafo2017manifesto] and the
NeurIPS reproducibility programme [@pineau2021reproducibility]; against both it is a
**partial pass** — same operator, same host — which is exactly why
`CWC-L8-replication` remains `NOT_TESTED`. The disclosed grid amendments and the frozen
kill rule exist to remove the researcher degrees of freedom catalogued in [@simmons2011],
and the base-rate argument of [@ioannidis2005] is why a ledger containing 10
`NOT_SUPPORTED` claims is evidence about the method rather than about failure.

### 2.8 Verification of the instrument itself

The measurement substrate is gated by mutation testing — seed a fault, require a test to
notice — originating in [@demillo1978hints], surveyed with its limits (notably equivalent
mutants) in [@jia2011mutation], and empirically connected to real fault detection by
[@just2014mutants]. This is why CWC's 12/12 mutation gate is scoped to an arithmetic core
and is **not** advertised as whole-repository mutation coverage.

Every reward-only controller in the programme is REINFORCE [@williams1992reinforce]. This
attribution carries real weight: `CWC-L4c-credit-collapse` and `CWC-L4d-budget-scaling`
are `NOT_SUPPORTED` because the advantage term scales with reward noise, so they are
statements about *this estimator's* credit assignment, not about adaptivity. Likewise
`CWC-L2c-e2e-straightthrough` is `NOT_SUPPORTED` with the failure attributed to
straight-through estimation [@bengio2013ste] — a known-hard estimator — rather than to
the benchmark. Adaptive network selection with an explicit decision cost
[@bolukbasi2017adaptive] is the nearest prior art that already charges for the decision;
CWC's addition is measuring `c_route` physically and charging it inside the certificate.

---

## 3. Novelty boundary, claim by claim

Verdicts are deliberately conservative. `NOT_NOVEL` means CWC asserts no priority.
`NOVELTY_CANDIDATE` means no prior art was found for the specific construct *and* the
absence of forward citation chasing is acknowledged. `OVERLAP_CONCEDED` means prior art
covers the idea and CWC's contribution is narrower than an earlier draft implied.

| Construct | Claims | Verdict | Basis |
|---|---|---|---|
| Adaptive halting / depth / skipping mechanisms | L1, AC1 | **NOT_NOVEL** | [@graves2016act], [@dehghani2019universal], [@banino2021pondernet], [@figurnov2017sact], [@teerapittayanon2016branchynet], [@wang2018skipnet], [@wu2018blockdrop] |
| Learned routing controllers | L2, L2a, AC2 | **NOT_NOVEL** | [@shazeer2017moe], [@fedus2022switch], [@wang2018skipnet]; estimator is [@williams1992reinforce] |
| Oracle gap as value of adaptivity | L1, AC1 | **OVERLAP_CONCEDED** | equals EVPI [@howard1966voi] |
| Information ceiling on routing value | L4b, AC3 | **OVERLAP_CONCEDED** | rational inattention [@sims2003inattention]; bound is Pinsker-type [@kullback1967lower] |
| `V*(R)` decision rate function | L4i, AC4 | **OVERLAP_CONCEDED** | rate–distortion for decisions; [@ortega2013thermo], [@ortega2015bounded], [@cover2006elements] |
| Halt-gap identity `= P(m>K)` | L2p | **NOT_NOVEL** | optimal stopping [@wald1945sprt]; CWC verifies, does not discover |
| Role-conditioned functional reuse | L3 | **NOT_SUPPORTED / NOT_NOVEL** | ties prior art; recorded as a negative in the ledger |
| Nonconcavity / vanishing marginal value of the first unit of information | RIGOR3 | **OVERLAP_CONCEDED** | [@radner1984nonconcavity], [@chade2002another], [@delara2007tight], [@whitmeyer2024cavity], [@delara2020payoffs] — the phenomenon and the regular/critical split are prior art (§2.5.1) |
| Its quantitative form: exponents `Θ(R)` vs `Θ(√R)` in nats, identified with Pinsker tightness, constant `c=std(D)/Δu` on the manifold | RIGOR3 | **NOVELTY_CANDIDATE (NARROWED 2026-08-08)** | no prior statement of the *rate* located; certified over 60+60 de-curated random instances; narrowed from an unqualified candidate after §2.5.1 |
| Certificate: proof-complete corrected lower bound `Ĝ − b − 2d` with measured `c_route` charged | RIGOR1, RIGOR9 | **NOVELTY_CANDIDATE** | assembled from standard parts [@hoeffding1963]; the *decision instrument* is the contribution, not the inequality |
| Closed-form routability screen `Ĝ > c_route + κ·se` | R1 | **NOVELTY_CANDIDATE** | κ = 4.9007 is design-specific and must not be reported as universal; tested out-of-sample on 7 frozen bundles + a 61-point boundary sweep |
| Three-way frozen real-data negative with positive control in the same run | RD1, RD2, RD3, RD4 | **NOVELTY_CANDIDATE (as evidence)** | negative results of this shape are rarely published; the contribution is the frozen, instrument-sensitivity-tested negative, not a mechanism |
| Compute-equivalent Pareto vs MoD/MoE on real workloads | L7 | **NOT CLAIMED** | `NOT_TESTED`; [@raposo2024mod], [@bae2025mor], [@elhoushi2024layerskip] are the untested baselines |
| Independent replication | L8 | **NOT CLAIMED** | `NOT_TESTED`; standard is [@munafo2017manifesto], [@pineau2021reproducibility] |

**The one-sentence novelty statement licensed by this review.** CWC's defensible
contribution is *not* an adaptive-computation mechanism and *not* the
value-of-information theory — both are prior art — but an **executable, falsification-
tested instrument that decides, before spending, whether a given workload can pay for
adaptivity**, together with the frozen negatives that instrument produced when turned on
its author's own preferred hypothesis.

That sentence survives the 2026-08-08 amendment unchanged: §2.5.1 removes a
theory-side candidate, and the instrument and the negatives were never resting on it.

---

## 4. Enforcement

| Property | Enforced by |
|---|---|
| Every citation machine-resolved against an external authority | `scripts/build_bibliography.py` (build aborts on any unresolved identifier) |
| BibTeX titles identical to resolver output | `scripts/verify_bibliography.py` check B4 |
| Every reference attached to real claim ids | check B5 against `claim_registry.json` |
| Every reference argued; every argued key exists | checks B6, B7 against this document |
| Gate runs in the standard verification | `make -f Makefile.cwc verify` → `doc-gate` |

No novelty statement stronger than §3 may enter a paper, abstract or README without a new
pass of this review recorded here with its own date.
