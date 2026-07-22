"""Build the CWC bibliography from machine-resolved sources (ONLINE, refresh only).

Every citation CWC makes must be resolvable against an authority that is not this
repository and not a language model:

  * arXiv preprints   -> arXiv Atom API              (export.arxiv.org)
  * journal articles  -> DOI content negotiation     (doi.org -> CSL JSON)
  * DOIs without CSL  -> OpenAlex work record        (api.openalex.org)
  * books             -> Open Library                (openlibrary.org)

The curated list below carries only what a human must supply: the citation key, the
identifier, and the *argument* — why this work is cited and which CWC claim it bounds.
All bibliographic fields (title, authors, year, venue) are taken from the resolver, so
a wrong or invented identifier cannot silently produce a plausible-looking entry: it
fails to resolve and the build aborts.

Outputs (both regenerated, never hand-edited):
  docs/publication/BIBLIOGRAPHY_VERIFICATION.json   resolution record + arguments
  docs/publication/references.bib                   BibTeX derived from that record

Refresh:  PYTHONPATH=. .venv/bin/python scripts/build_bibliography.py
Check:    PYTHONPATH=. .venv/bin/python scripts/verify_bibliography.py   (offline gate)
"""

from __future__ import annotations

import json
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
OUT_JSON = ROOT / "docs/publication/BIBLIOGRAPHY_VERIFICATION.json"
OUT_BIB = ROOT / "docs/publication/references.bib"

UA = {"User-Agent": "cwc-bibliography-builder/1.0 (+https://gitlab.com/neuron7x-group/nanochat-cwc-baseline)"}
ATOM = {"a": "http://www.w3.org/2005/Atom"}
ARXIV_SCHEMA = "{http://arxiv.org/schemas/atom}"

# (key, kind, identifier, area, claims, role, argument)
#   kind     : arxiv | doi | openalex_doi | isbn | url
#   claims   : CWC claim ids this reference bounds, scopes or supplies method for
#   role     : prior-art | foundation | method | integrity | upstream
#   argument : why it is cited; for prior-art, what CWC does NOT claim against it
CURATED: list[tuple[str, str, str, str, list[str], str, str]] = [
    # ---- A. adaptive computation / conditional compute -------------------------
    ("graves2016act", "arxiv", "1603.08983", "adaptive-computation",
     ["CWC-L1-identifiability", "CWC-AC1-compute-identifiability"], "prior-art",
     "Learned halting for recurrent nets is the origin of the adaptive-compute line. CWC claims "
     "no novelty for adaptive stopping; its object is whether such a mechanism is IDENTIFIABLE "
     "on a given workload, which ACT assumes rather than tests."),
    ("dehghani2019universal", "arxiv", "1807.03819", "adaptive-computation",
     ["CWC-AC1-compute-identifiability", "CWC-RD4-negative-robustness"], "prior-art",
     "Weight-tied recurrent depth with ACT halting. CWC's WP5/WP18 substrate is a weight-tied "
     "recurrent block of the same family; WP19 shows the WP18 mechanism finding was a property "
     "of weight tying, so this reference fixes the scope of that narrowing."),
    ("banino2021pondernet", "arxiv", "2107.05407", "adaptive-computation",
     ["CWC-L2p-jensen-gap", "CWC-AC2-compute-controller"], "prior-art",
     "Probabilistic halting with a principled loss. Establishes learned per-instance halting as "
     "solved prior art; CWC's contribution is the certificate that decides when such a controller "
     "can pay for itself, not the controller."),
    ("figurnov2017sact", "arxiv", "1612.02297", "adaptive-computation",
     ["CWC-AC1-compute-identifiability"], "prior-art",
     "Spatially adaptive computation time in residual networks: per-position compute allocation. "
     "Prior art for allocation itself; CWC makes no vision claim."),
    ("teerapittayanon2016branchynet", "arxiv", "1709.01686", "adaptive-computation",
     ["CWC-AC1-compute-identifiability"], "prior-art",
     "Early-exit branches — the cheapest realisation of input-conditional compute. Included so the "
     "novelty boundary explicitly excludes early exit."),
    ("bolukbasi2017adaptive", "arxiv", "1702.07811", "adaptive-computation",
     ["CWC-L2b-route-decision-cost"], "prior-art",
     "Adaptive network selection with an explicit cost/accuracy trade-off; the nearest prior art "
     "that already charges for the decision. CWC's addition is measuring c_route physically (WP17) "
     "and charging it inside the certificate."),
    ("schwartz2020righttool", "arxiv", "2004.07453", "adaptive-computation",
     ["CWC-RD1-real-lm-boundary", "CWC-RD3-real-workload-pilot"], "prior-art",
     "Matches model capacity to instance difficulty on real NLP tasks — the positive-result "
     "counterpart to CWC's real-data negatives. Cited because it is the strongest published "
     "evidence AGAINST CWC's WP18 conclusion and must be confronted, not omitted."),
    ("xin2020deebert", "arxiv", "2004.12993", "adaptive-computation",
     ["CWC-RD1-real-lm-boundary"], "prior-art",
     "Early exiting in BERT: real-workload adaptive compute that reports gains. Same confrontation "
     "role as schwartz2020righttool; scope difference is per-sequence classification vs CWC's "
     "per-token byte prediction."),
    ("elbayad2020depthadaptive", "arxiv", "1910.10073", "adaptive-computation",
     ["CWC-RD1-real-lm-boundary", "CWC-RD3-real-workload-pilot"], "prior-art",
     "Depth-adaptive transformer for sequence generation — the closest published setting to CWC's "
     "per-token compute allocation, and therefore the sharpest external check on the WP6/WP14/WP18 "
     "negatives."),
    ("schuster2022calm", "arxiv", "2207.07061", "adaptive-computation",
     ["CWC-RD2-real-lm-contextual"], "prior-art",
     "Confident adaptive language modelling: per-token early exit with calibrated confidence on "
     "real LMs. The reference most likely to be read as contradicting CWC-RD1/RD2; the resolution "
     "is scale and the fact that CALM prices exit by confidence, not by a certified oracle gap."),
    ("elhoushi2024layerskip", "arxiv", "2404.16710", "adaptive-computation",
     ["CWC-L7-pareto"], "prior-art",
     "Layer skipping with self-speculative decoding at LM scale. Part of the baseline family a real "
     "L7 Pareto test would have to beat; CWC has not run it (NOT_TESTED)."),
    ("raposo2024mod", "arxiv", "2404.02258", "adaptive-computation",
     ["CWC-L7-pareto", "CWC-L7s-synthetic-pareto"], "prior-art",
     "Mixture-of-Depths: the reference adaptive-depth transformer at scale. CWC explicitly does NOT "
     "claim to beat MoD — CWC-L7-pareto is NOT_TESTED and cloud-blocked; the synthetic Pareto result "
     "CWC-L7s is a harness demonstration, not a comparison."),
    ("bae2025mor", "arxiv", "2507.10524", "adaptive-computation",
     ["CWC-L7-pareto"], "prior-art",
     "Mixture-of-Recursions: token-level dynamic recursion depth, the current state of the art in "
     "the exact mechanism family CWC studies. Its existence is why CWC's honest ceiling is an "
     "identifiability instrument rather than an architecture claim."),
    ("geiping2025recurrentdepth", "arxiv", "2502.05171", "adaptive-computation",
     ["CWC-AC1-compute-identifiability", "CWC-RD4-negative-robustness"], "prior-art",
     "Latent reasoning by recurrent depth at scale — the large-model instance of CWC's weight-tied "
     "substrate. Directly relevant to WP19's finding that weight tying, not the data, produced "
     "WP18's uniform best-K."),
    ("han2021dynamicnn", "arxiv", "2102.04906", "adaptive-computation",
     ["CWC-L1-identifiability"], "prior-art",
     "Survey of dynamic neural networks; used as the coverage backbone of the systematic search so "
     "the related-work claim is not built from memory."),
    ("bengio2013ste", "arxiv", "1308.3432", "adaptive-computation",
     ["CWC-L2c-e2e-straightthrough"], "method",
     "Straight-through estimation for stochastic/discrete units — the exact estimator whose failure "
     "CWC-L2c records as NOT_SUPPORTED. Cited so the negative is attributed to a known-hard "
     "estimator, not to the benchmark."),
    ("bengio2015conditional", "arxiv", "1511.06297", "adaptive-computation",
     ["CWC-L1-identifiability"], "prior-art",
     "Conditional computation via learned sparse gating — the programmatic statement of the idea "
     "CWC tests the preconditions of."),
    ("wang2018skipnet", "arxiv", "1711.09485", "adaptive-computation",
     ["CWC-L2-routing-causality"], "prior-art",
     "Layer-skipping policy learned with RL: prior art for reward-only routing controllers of the "
     "kind CWC trains in WP2/AC2."),
    ("wu2018blockdrop", "arxiv", "1711.08393", "adaptive-computation",
     ["CWC-L2-routing-causality"], "prior-art",
     "Learned per-input block dropping; same role as SkipNet in bounding controller novelty."),

    # ---- B. sparse experts ----------------------------------------------------
    ("jacobs1991moe", "doi", "10.1162/neco.1991.3.1.79", "sparse-experts",
     ["CWC-L1-identifiability"], "prior-art",
     "The original mixture of local experts. The context-conditioned choice CWC formalises as the "
     "ANOVA interaction gamma is the same object this line has optimised since 1991."),
    ("shazeer2017moe", "arxiv", "1701.06538", "sparse-experts",
     ["CWC-L7-pareto"], "prior-art",
     "Sparsely-gated MoE with load balancing. CWC borrows anti-collapse/load-balance discipline for "
     "its controllers and makes no MoE-superiority claim."),
    ("fedus2022switch", "arxiv", "2101.03961", "sparse-experts",
     ["CWC-L7-pareto"], "prior-art",
     "Switch Transformer: the scaled MoE baseline family a real L7 test must include. Not run."),
    ("fedus2022sparsereview", "arxiv", "2209.01667", "sparse-experts",
     ["CWC-L7-pareto"], "prior-art",
     "Review of sparse expert models; the second coverage backbone of the systematic search."),

    # ---- C. test-time compute — the prior question WP-R1 screens --------------
    ("wei2022cot", "arxiv", "2201.11903", "test-time-compute",
     ["CWC-R1-routability-screen"], "prior-art",
     "Chain-of-thought: the canonical case where per-instance compute demand varies by orders of "
     "magnitude — precisely the workload property CWC's closing analysis says is required and that "
     "per-token byte prediction lacks."),
    ("snell2024testtime", "arxiv", "2408.03314", "test-time-compute",
     ["CWC-R1-routability-screen", "CWC-L7-pareto"], "prior-art",
     "Optimal test-time compute scaling: shows adaptive allocation paying off when the demand "
     "spread is large. The empirical anchor for WP-R1's screen being worth running before any "
     "cloud spend."),
    ("leviathan2023speculative", "arxiv", "2211.17192", "test-time-compute",
     ["CWC-L2b-route-decision-cost"], "prior-art",
     "Speculative decoding: a deployed adaptive-compute scheme whose entire viability rests on the "
     "decision being cheaper than the work — the deployed analogue of CWC's V = gap - c_route."),
    ("hao2024coconut", "arxiv", "2412.06769", "test-time-compute",
     ["CWC-R1-routability-screen"], "prior-art",
     "Continuous-latent-space reasoning: a candidate workload family with order-of-magnitude "
     "per-instance demand variation, i.e. a legitimate target for the WP-R1 screen."),

    # ---- D. plasticity / continual learning ----------------------------------
    ("kirkpatrick2017ewc", "arxiv", "1612.00796", "plasticity",
     ["CWC-L4-plasticity"], "prior-art",
     "Elastic weight consolidation: per-parameter importance as a plasticity budget. CWC's governor "
     "reuses this framing and claims novelty only for the identifiability certificate over it."),
    ("zenke2017si", "arxiv", "1703.04200", "plasticity",
     ["CWC-L4-plasticity"], "prior-art",
     "Synaptic intelligence: online importance accumulation; same bounding role as EWC."),
    ("aljundi2018mas", "arxiv", "1711.09601", "plasticity",
     ["CWC-L4-plasticity"], "prior-art",
     "Memory-aware synapses: unsupervised importance estimation; completes the importance-based "
     "continual-learning triple CWC's plasticity line sits inside."),
    ("abraham1996metaplasticity", "doi", "10.1016/S0166-2236(96)80018-X", "plasticity",
     ["CWC-L4-plasticity", "CWC-L4h-context-scaling"], "foundation",
     "Metaplasticity — the plasticity of synaptic plasticity. The biological source of the claim "
     "that a system can allocate its own capacity to change, which CWC tests as a budgeted "
     "allocation problem rather than asserting as an analogy."),
    ("sapolsky2017behave", "isbn", "9781594205071", "plasticity",
     ["CWC-L4-plasticity"], "foundation",
     "The layered account of behaviour (seconds to evolution) that names this repository's parent "
     "directory and supplies the multi-timescale framing. Cited as the conceptual source, with no "
     "empirical weight placed on it."),

    # ---- E. information theory / value of information -------------------------
    ("shannon1948", "doi", "10.1002/j.1538-7305.1948.tb00917.x", "information-theory",
     ["CWC-L4i-rate-bridge", "CWC-AC4-rate-bridge"], "foundation",
     "The source of mutual information and of the rate-function form. CWC's V*(R) is stated as the "
     "decision-valued analogue of a rate-distortion function and inherits its shape from here."),
    ("cover2006elements", "doi", "10.1002/047174882X", "information-theory",
     ["CWC-L4i-rate-bridge", "CWC-AC4-rate-bridge", "CWC-RIGOR3-pinsker"], "foundation",
     "Canonical reference for the rate-distortion function, mutual information identities and "
     "Pinsker's inequality as used verbatim in ROUTABILITY_INFORMATION_BOUND and "
     "VALUE_OF_INFORMATION_RATE_FUNCTION."),
    ("kullback1951", "doi", "10.1214/aoms/1177729694", "information-theory",
     ["CWC-RIGOR3-pinsker"], "foundation",
     "On information and sufficiency: the divergence CWC's routability bound is stated in."),
    ("kullback1967lower", "doi", "10.1109/TIT.1967.1053968", "information-theory",
     ["CWC-RIGOR3-pinsker"], "foundation",
     "A lower bound for discrimination information in terms of variation — the Pinsker-type "
     "inequality CWC's ceiling V(Z) <= du*sqrt(I/2) applies. CWC-RIGOR3 tests where that step is "
     "tight (Theta(R)) and where it is loose (Theta(sqrt R)); attribution matters because the "
     "dichotomy is a statement about THIS inequality, not a new one."),
    ("blahut1972", "doi", "10.1109/TIT.1972.1054855", "information-theory",
     ["CWC-L4i-rate-bridge", "CWC-AC4-rate-bridge"], "method",
     "Blahut's algorithm for rate-distortion computation — the numerical method family used to "
     "trace the V*(R) frontier CWC's governors are compared against."),
    ("arimoto1972", "doi", "10.1109/TIT.1972.1054753", "information-theory",
     ["CWC-L4i-rate-bridge", "CWC-AC4-rate-bridge"], "method",
     "Arimoto's companion algorithm; cited jointly as the standard Blahut-Arimoto procedure."),
    ("howard1966voi", "doi", "10.1109/TSSC.1966.300074", "information-theory",
     ["CWC-L1-identifiability", "CWC-L4i-rate-bridge"], "foundation",
     "Information Value Theory. CWC's oracle gap G = V_oracle - V_fixed is the expected value of "
     "perfect information about the context relative to a context-blind policy. This is the single "
     "most important attribution in the programme: the quantity is classical, and CWC's claim is "
     "about MEASURING it with a certificate, not about discovering it."),
    ("sims2003inattention", "doi", "10.1016/S0304-3932(03)00029-1", "information-theory",
     ["CWC-L4b-inferred-context", "CWC-AC3-inferred-difficulty"], "foundation",
     "Rational inattention: optimal behaviour under an explicit mutual-information constraint on "
     "what the decision-maker observes. CWC's inferred-context boundary (governor abstains as "
     "I(C;Z) -> 0) is a rediscovery of this result in a compute-allocation setting; the review "
     "states that overlap rather than claiming the boundary as novel."),
    ("ortega2013thermo", "arxiv", "1204.6481", "information-theory",
     ["CWC-L4i-rate-bridge", "CWC-AC4-rate-bridge"], "foundation",
     "Decision-making with information-processing costs, in free-energy form. The soft-routing "
     "optimum CWC's committed-greedy governors fall short of at low information is exactly this "
     "object, which is why the low-info saturation gap (0.326) is a known structural gap, not an "
     "unexplained defect."),
    ("ortega2015bounded", "arxiv", "1512.06789", "information-theory",
     ["CWC-L4i-rate-bridge"], "foundation",
     "Information-theoretic bounded rationality: the general framework CWC's master inequality "
     "V_realized <= oracle_gap - c_route is a special case of."),
    ("tishby2000ib", "arxiv", "physics/0004057", "information-theory",
     ["CWC-AC3-inferred-difficulty"], "foundation",
     "The information bottleneck: the trade-off between signal compression and task relevance that "
     "governs how much a router can learn from a noisy difficulty observation."),

    # ---- F. optimal stopping / evidence accumulation --------------------------
    ("wald1945sprt", "doi", "10.1214/aoms/1177731118", "decision-theory",
     ["CWC-L2p-jensen-gap"], "foundation",
     "Sequential tests: the classical optimal-stopping result behind 'stop when enough evidence has "
     "accumulated'. CWC's halt-conditioned identity adaptive - static = P(m > K) is an "
     "optimal-stopping identity and is claimed conservatively as a verification, not a discovery."),
    ("ratcliff1978", "doi", "10.1037/0033-295X.85.2.59", "decision-theory",
     ["CWC-AC1-compute-identifiability"], "foundation",
     "The diffusion model of decision: per-instance variable processing time in cognition, the "
     "biological precedent for input-dependent compute."),
    ("goldshadlen2007", "doi", "10.1146/annurev.neuro.29.051605.113038", "decision-theory",
     ["CWC-AC1-compute-identifiability"], "foundation",
     "Neural basis of decision making: evidence accumulation to a bound, i.e. adaptive computation "
     "as implemented by brains. Supplies the biological framing without carrying empirical weight."),

    # ---- G. statistical inference used by the certificate ---------------------
    ("hoeffding1963", "doi", "10.1080/01621459.1963.10500830", "statistics",
     ["CWC-RIGOR1-certificate", "CWC-RIGOR5-independence"], "method",
     "The concentration inequality the identifiability certificate's deviation terms are built "
     "from; WP7's corrected bound G_lo = Ghat - b - 2d union-bounds two such deviations."),
    ("holm1979", "openalex_doi", "10.2307/4615733", "statistics",
     ["CWC-RIGOR2-fwer"], "method",
     "Holm's step-down procedure, applied in WP8 alongside Bonferroni to control family-wise error "
     "over the certificate positives."),
    ("benjamini1995fdr", "doi", "10.1111/j.2517-6161.1995.tb02031.x", "statistics",
     ["CWC-RIGOR2-fwer"], "method",
     "False discovery rate control: the less conservative alternative CWC deliberately did NOT use, "
     "recorded so the choice of family-wise control is a stated decision rather than a default."),
    ("efron1986bootstrap", "doi", "10.1214/ss/1177013815", "statistics",
     ["CWC-RIGOR6-effect-size"], "method",
     "Bootstrap standard errors and confidence intervals — the method behind WP13's 95% CIs on the "
     "certificate positives."),
    ("johnson2013revised", "doi", "10.1073/pnas.1313476110", "statistics",
     ["CWC-RIGOR2-fwer"], "integrity",
     "Revised standards for statistical evidence: the argument that conventional thresholds are too "
     "permissive, supporting CWC's choice of an ultra-conservative all-claims Bonferroni variant."),
    ("ramdas2022anytime", "arxiv", "2210.01948", "statistics",
     ["CWC-RIGOR1-certificate"], "method",
     "Game-theoretic statistics and safe anytime-valid inference: the correct framework for a "
     "certificate that may be evaluated repeatedly. CWC's bound is fixed-sample, so this is cited "
     "as a known limitation and an upgrade path, not as something already implemented."),

    # ---- H. research integrity / reproducibility ------------------------------
    ("nosek2018prereg", "doi", "10.1073/pnas.1708274114", "integrity",
     ["CWC-RIGOR7-prereg-integrity"], "integrity",
     "The preregistration revolution: the methodological source of CWC's strict-ancestor "
     "requirement, where a preregistration must be a git ancestor of its own results."),
    ("chambers2013registered", "doi", "10.1016/j.cortex.2012.12.016", "integrity",
     ["CWC-RIGOR7-prereg-integrity"], "integrity",
     "Registered Reports: peer review of the protocol before results exist — the model CWC's "
     "per-experiment PREREGISTRATION.md files imitate without an external reviewer, a gap the "
     "threats document states openly."),
    ("munafo2017manifesto", "doi", "10.1038/s41562-016-0021", "integrity",
     ["CWC-RIGOR7-prereg-integrity", "CWC-L8-replication"], "integrity",
     "A manifesto for reproducible science: the checklist CWC's clean-room spine (WP16) implements "
     "and, for independent replication, admits it does not satisfy."),
    ("ioannidis2005", "doi", "10.1371/journal.pmed.0020124", "integrity",
     ["CWC-RIGOR2-fwer"], "integrity",
     "Why most published research findings are false: the base-rate argument that makes a "
     "10-negative ledger evidence of method rather than of failure."),
    ("simmons2011", "doi", "10.1177/0956797611417632", "integrity",
     ["CWC-RIGOR7-prereg-integrity"], "integrity",
     "False-positive psychology: researcher degrees of freedom. CWC's disclosed grid amendments and "
     "frozen kill rule exist to remove exactly the flexibility catalogued here."),
    ("pineau2021reproducibility", "arxiv", "2003.12206", "integrity",
     ["CWC-L8-replication"], "integrity",
     "The NeurIPS reproducibility programme report: the community standard against which CWC's "
     "clean-room reproduction is a partial pass (same operator, same host)."),

    # ---- I. software verification underwriting the instrument -----------------
    ("demillo1978hints", "doi", "10.1109/C-M.1978.218136", "software-verification",
     ["CWC-L0-measurement"], "method",
     "The origin of mutation testing: seed a fault, require a test to notice. CWC's 12/12 mutation "
     "gate on the mathematical core is this idea applied to a measurement instrument."),
    ("jia2011mutation", "doi", "10.1109/TSE.2010.62", "software-verification",
     ["CWC-L0-measurement"], "method",
     "Survey of mutation testing: establishes the technique's scope and its known limits, including "
     "equivalent mutants, which is why CWC's probe is scoped to an arithmetic core rather than "
     "advertised as whole-repository mutation coverage."),
    ("just2014mutants", "doi", "10.1145/2635868.2635929", "software-verification",
     ["CWC-L0-measurement"], "method",
     "Evidence that mutant detection correlates with real fault detection — the empirical warrant "
     "for treating the mutation gate as evidence about the instrument rather than as ceremony."),

    # ---- J. energy: why energy is INSTRUMENT_INVALID here ---------------------
    ("attwell2001energy", "doi", "10.1097/00004647-200110000-00001", "energy",
     ["CWC-L0-measurement", "CWC-RIGOR10-timing-metrology"], "foundation",
     "An energy budget for cortical signalling: the biological precedent for costing computation in "
     "energy. CWC records energy as INSTRUMENT_INVALID on its hardware and therefore makes no "
     "energy claim; the citation marks the axis that was deliberately abandoned."),
    ("levy1996energy", "doi", "10.1162/neco.1996.8.3.531", "energy",
     ["CWC-L0-measurement"], "foundation",
     "Energy-efficient neural codes: information per joule as an objective. Same role — the "
     "unmeasurable axis is named, not quietly dropped."),

    # ---- K. method and upstream ----------------------------------------------
    ("williams1992reinforce", "doi", "10.1007/BF00992696", "method",
     ["CWC-L2a-e2e-reinforce", "CWC-AC2-compute-controller", "CWC-L4c-credit-collapse"], "method",
     "REINFORCE. Every reward-only controller in CWC is this estimator; the L4c/L4d negatives are "
     "statements about ITS credit assignment (the advantage term scaling with reward noise), which "
     "is why they are reported as estimator properties, not as facts about adaptivity."),
    ("karpathy2025nanochat", "url", "https://github.com/karpathy/nanochat", "upstream",
     ["CWC-L0-measurement"], "upstream",
     "The upstream baseline this repository forks. The master/baseline branches are unmodified "
     "upstream history; all CWC work is additive."),
]


def _get(url: str, accept: str | None = None, timeout: int = 45) -> str:
    headers = dict(UA)
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 - fixed https authorities
        body: bytes = resp.read()
    return body.decode("utf-8", "replace")


def _retry(fn: Any, attempts: int = 5, wait: float = 10.0) -> Any:
    last: Exception | None = None
    for i in range(attempts):
        try:
            return fn()
        except Exception as exc:  # network flakiness / rate limits
            last = exc
            if i < attempts - 1:
                time.sleep(wait)
    raise RuntimeError(f"unresolved after {attempts} attempts: {last}")


def resolve_arxiv(identifier: str) -> dict[str, Any]:
    def call() -> dict[str, Any]:
        xml = _get(f"https://export.arxiv.org/api/query?id_list={identifier}&max_results=1")
        root = ET.fromstring(xml)
        entry = root.find("a:entry", ATOM)
        if entry is None:
            raise RuntimeError("no entry")
        title_el = entry.find("a:title", ATOM)
        if title_el is None or title_el.text is None:
            raise RuntimeError("no title")
        doi_el = entry.find(f"{ARXIV_SCHEMA}doi")
        jr_el = entry.find(f"{ARXIV_SCHEMA}journal_ref")
        pub_el = entry.find("a:published", ATOM)
        return {
            "resolver": "arxiv-api",
            "resolver_url": f"https://export.arxiv.org/api/query?id_list={identifier}",
            "title": " ".join(title_el.text.split()),
            "authors": [a.findtext("a:name", default="", namespaces=ATOM) for a in entry.findall("a:author", ATOM)],
            "year": int((pub_el.text or "0000")[:4]) if pub_el is not None else None,
            "venue": (jr_el.text if jr_el is not None else None) or "arXiv preprint",
            "doi": doi_el.text if doi_el is not None else None,
            "url": f"https://arxiv.org/abs/{identifier}",
        }

    out: dict[str, Any] = _retry(call)
    time.sleep(4)
    return out


def resolve_doi(identifier: str) -> dict[str, Any]:
    def call() -> dict[str, Any]:
        raw = json.loads(_get("https://doi.org/" + identifier, accept="application/vnd.citationstyles.csl+json"))
        title = raw.get("title")
        container = raw.get("container-title")
        parts = raw.get("issued", {}).get("date-parts", [[None]])
        return {
            "resolver": "doi-content-negotiation",
            "resolver_url": "https://doi.org/" + identifier,
            "title": (title[0] if isinstance(title, list) else title) or "",
            "authors": [
                " ".join(x for x in (a.get("given"), a.get("family")) if x)
                for a in (raw.get("author") or [])
            ],
            "year": (parts[0] or [None])[0],
            "venue": (container if isinstance(container, str) else (container[0] if container else ""))
            or raw.get("publisher", ""),
            "doi": identifier,
            "url": "https://doi.org/" + identifier,
        }

    out: dict[str, Any] = _retry(call, attempts=3, wait=4.0)
    time.sleep(1.5)
    return out


def resolve_openalex_doi(identifier: str) -> dict[str, Any]:
    """For DOIs that are registered but expose no CSL metadata (e.g. JSTOR back-issues)."""

    def call() -> dict[str, Any]:
        raw = json.loads(_get(f"https://api.openalex.org/works/doi:{identifier}?mailto=neuron7x@ukr.net"))
        loc = raw.get("primary_location") or {}
        src = loc.get("source") or {}
        return {
            "resolver": "openalex",
            "resolver_url": f"https://api.openalex.org/works/doi:{identifier}",
            "title": raw.get("title") or "",
            "authors": [a["author"]["display_name"] for a in raw.get("authorships", [])],
            "year": raw.get("publication_year"),
            "venue": src.get("display_name", ""),
            "doi": identifier,
            "url": "https://doi.org/" + identifier,
        }

    out: dict[str, Any] = _retry(call, attempts=3, wait=4.0)
    time.sleep(1.5)
    return out


def resolve_isbn(identifier: str) -> dict[str, Any]:
    def call() -> dict[str, Any]:
        raw = json.loads(
            _get(f"https://openlibrary.org/api/books?bibkeys=ISBN:{identifier}&format=json&jscmd=data")
        )
        rec = raw.get(f"ISBN:{identifier}")
        if not rec:
            raise RuntimeError("isbn not found")
        date = str(rec.get("publish_date", ""))
        year = int(re.findall(r"\b(1[89]\d\d|20\d\d)\b", date)[0]) if re.findall(r"\b(1[89]\d\d|20\d\d)\b", date) else None
        return {
            "resolver": "openlibrary",
            "resolver_url": f"https://openlibrary.org/api/books?bibkeys=ISBN:{identifier}&format=json&jscmd=data",
            "title": rec.get("title", ""),
            "authors": [a["name"] for a in rec.get("authors", [])],
            "year": year,
            "venue": ", ".join(p["name"] for p in rec.get("publishers", [])),
            "doi": None,
            "url": rec.get("url", f"https://openlibrary.org/isbn/{identifier}"),
            "isbn": identifier,
        }

    out: dict[str, Any] = _retry(call, attempts=3, wait=4.0)
    time.sleep(1.0)
    return out


def resolve_url(identifier: str) -> dict[str, Any]:
    def call() -> dict[str, Any]:
        req = urllib.request.Request(identifier, headers=UA, method="HEAD")
        with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 - fixed https authority
            code = resp.status
        if code >= 400:
            raise RuntimeError(f"HTTP {code}")
        return {
            "resolver": "http-head",
            "resolver_url": identifier,
            "title": None,
            "authors": [],
            "year": None,
            "venue": None,
            "doi": None,
            "url": identifier,
            "http_status": code,
        }

    out: dict[str, Any] = _retry(call, attempts=3, wait=4.0)
    time.sleep(1.0)
    return out


RESOLVERS = {
    "arxiv": resolve_arxiv,
    "doi": resolve_doi,
    "openalex_doi": resolve_openalex_doi,
    "isbn": resolve_isbn,
    "url": resolve_url,
}

# Fields a human supplies for entries whose resolver returns no bibliographic metadata.
MANUAL_FIELDS: dict[str, dict[str, Any]] = {
    "karpathy2025nanochat": {
        "title": "nanochat",
        "authors": ["Andrej Karpathy"],
        "year": 2025,
        "venue": "GitHub repository",
    },
}


def bibtex(key: str, rec: dict[str, Any]) -> str:
    meta = rec["resolved"]
    kind = rec["kind"]
    entry = "misc" if kind in {"url", "isbn"} else ("article" if kind != "arxiv" else "misc")
    fields: list[tuple[str, str]] = []
    title = meta.get("title") or ""
    authors = meta.get("authors") or []
    fields.append(("title", "{" + title + "}"))
    if authors:
        fields.append(("author", "{" + " and ".join(authors) + "}"))
    if meta.get("year"):
        fields.append(("year", "{" + str(meta["year"]) + "}"))
    if kind == "arxiv":
        fields.append(("eprint", "{" + rec["identifier"] + "}"))
        fields.append(("archivePrefix", "{arXiv}"))
        if meta.get("venue") and meta["venue"] != "arXiv preprint":
            fields.append(("note", "{" + str(meta["venue"]) + "}"))
    elif meta.get("venue"):
        fields.append(("journal", "{" + str(meta["venue"]) + "}"))
    if meta.get("doi"):
        fields.append(("doi", "{" + str(meta["doi"]) + "}"))
    if meta.get("isbn"):
        fields.append(("isbn", "{" + str(meta["isbn"]) + "}"))
    if meta.get("url"):
        fields.append(("url", "{" + str(meta["url"]) + "}"))
    fields.append(("cwcverified", "{" + f"{meta['resolver']}@{rec['verified_utc']}" + "}"))
    body = ",\n  ".join(f"{k} = {v}" for k, v in fields)
    return f"@{entry}{{{key},\n  {body}\n}}\n"


def main() -> int:
    keys = [c[0] for c in CURATED]
    if len(set(keys)) != len(keys):
        print("FAIL: duplicate citation keys", file=sys.stderr)
        return 1

    registry = json.loads((ROOT / "claim_registry.json").read_text())
    known_claims = {c["claim_id"] for c in registry["claims"]}

    records: dict[str, Any] = {}
    failures: list[str] = []
    for key, kind, identifier, area, claims, role, argument in CURATED:
        unknown = [c for c in claims if c not in known_claims]
        if unknown:
            failures.append(f"{key}: unknown claim ids {unknown}")
            continue
        try:
            resolved = RESOLVERS[kind](identifier)
        except Exception as exc:
            failures.append(f"{key}: {kind}:{identifier} did not resolve ({exc})")
            continue
        for field, value in MANUAL_FIELDS.get(key, {}).items():
            if not resolved.get(field):
                resolved[field] = value
                resolved.setdefault("manual_fields", []).append(field)
        records[key] = {
            "kind": kind,
            "identifier": identifier,
            "area": area,
            "role": role,
            "claims": claims,
            "argument": argument,
            "verified_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "resolved": resolved,
        }
        print(f"  resolved {key:32s} {resolved['resolver']:26s} {str(resolved.get('title'))[:52]}")

    if failures:
        print("\nBIBLIOGRAPHY BUILD FAILED — unresolved or invalid entries:", file=sys.stderr)
        for f in failures:
            print("  " + f, file=sys.stderr)
        return 1

    OUT_JSON.write_text(
        json.dumps(
            {
                "generated_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "policy": (
                    "Every entry's bibliographic fields come from the named external resolver, not "
                    "from the author and not from a language model. An identifier that does not "
                    "resolve aborts the build. Re-check offline with scripts/verify_bibliography.py."
                ),
                "resolvers": sorted({r["resolved"]["resolver"] for r in records.values()}),
                "entry_count": len(records),
                "entries": records,
            },
            indent=1,
            ensure_ascii=False,
            sort_keys=True,
        )
        + "\n"
    )

    header = (
        "% CWC bibliography — MACHINE-GENERATED, do not hand-edit.\n"
        "% Source of truth: docs/publication/BIBLIOGRAPHY_VERIFICATION.json\n"
        "% Regenerate:      PYTHONPATH=. .venv/bin/python scripts/build_bibliography.py   (online)\n"
        "% Check:           PYTHONPATH=. .venv/bin/python scripts/verify_bibliography.py  (offline gate)\n"
        "%\n"
        "% Every entry below was resolved against an external authority (arXiv API, DOI content\n"
        "% negotiation, OpenAlex, Open Library). The cwcverified field records which resolver\n"
        "% answered and when. Argument for each citation: RELATED_WORK_AND_NOVELTY_REVIEW.md.\n\n"
    )
    OUT_BIB.write_text(header + "\n".join(bibtex(k, records[k]) for k in sorted(records)))

    print(f"\nOK: {len(records)} entries -> {OUT_JSON.relative_to(ROOT)} + {OUT_BIB.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
