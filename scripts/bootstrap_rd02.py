from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from cwc.research_ops.claim_attack import attack_claim
from cwc.research_ops.compute_governor import ComputeGovernor, ComputeRequest
from cwc.research_ops.evidence_graph import EvidenceGraph
from cwc.research_ops.governance import HumanDecision, write_human_decision
from cwc.research_ops.models import ClaimRecord, HypothesisCard, SourceSpan
from cwc.research_ops.provenance import freeze_local_source, sha256_file

ROOT = Path(__file__).resolve().parents[1]
REG = ROOT / "research/registry"
RAW = ROOT / "research/raw/arxiv"
GOV = ROOT / "research/governance"
DERIVED = ROOT / "research/derived"


def load_jsonish(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    REG.mkdir(parents=True, exist_ok=True)
    DERIVED.mkdir(parents=True, exist_ok=True)

    sources = load_jsonish(ROOT / "research/registry/01_SOURCE_REGISTRY.yaml")
    s01 = next(item for item in sources if item["source_id"] == "S01")
    snapshot = ROOT / s01["snapshot_path"]
    frozen = freeze_local_source(
        source_path=snapshot,
        raw_root=RAW,
        metadata={
            "source_id": "S01",
            "canonical_title": s01["title"],
            "publication_status": s01["publication_status"],
            "version": s01["version"],
            "retrieved_at": s01["retrieved_at"],
            "primary_source": True,
            "arxiv_id": s01["arxiv_id"],
        },
        primary_source_bytes=False,
        path_base=ROOT,
    )
    (REG / "rd02_sources.json").write_text(json.dumps([frozen.to_dict()], indent=2, sort_keys=True) + "\n", encoding="utf-8")

    extraction = load_jsonish(ROOT / "research/extractions/S01.yaml")
    claims: list[dict[str, object]] = []
    graph = EvidenceGraph()
    graph.add_node("S01", "Paper", title=s01["title"], gate_status=frozen.gate_status)
    for claim in extraction["claims"]:
        relation = "CAUSES" if claim.get("intervention") not in {"", "N/A", None} else "PREDICTS"
        record = ClaimRecord(
            claim_id=claim["claim_id"],
            source_id="S01",
            source_span=SourceSpan(
                source_id="S01",
                source_path=s01["snapshot_path"],
                start_line=1,
                end_line=1,
                section=str(claim.get("evidence_location", "UNKNOWN")),
                span_quality="COARSE_SNAPSHOT_ONLY",
            ),
            claim_text=claim["claim"],
            claim_type=claim["claim_type"],
            relation=relation,
            intervention=str(claim.get("intervention", "")),
            comparison=str(claim.get("comparison", "")),
            outcome=str(claim.get("effect_direction", "")),
            metric=str(claim.get("metric", "")),
            result=str(claim.get("status", "")),
            authors_interpretation=str(claim.get("authors_interpretation", "")),
        )
        flags = attack_claim(record)
        payload = asdict(record)
        payload["automatic_flags"] = list(flags)
        claims.append(payload)
        graph.add_node(record.claim_id, "Claim", text=record.claim_text, status=record.status, automatic_flags=list(flags))
        graph.add_edge("S01", "SUPPORTED_BY", record.claim_id)
    (REG / "rd02_claims.json").write_text(json.dumps(claims, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    hypothesis = HypothesisCard(
        hypothesis_id="H-CSCA-01",
        source_claims=("S01-C01", "S01-C03"),
        mechanism="Counterfactual coalition credit separates a delayed manipulable cause from temporal, correlated and stochastic non-causes.",
        formalization="phi_i = Shapley_i[v(S)], v(S)=Y_obs-E[Y_do(S)]",
        causal_graph="U->C; U->Y; A->Y; A~B observationally; D independent; C/B/D not structural parents of Y",
        prediction="A receives unique highest structural credit under IID and OOD context shifts; non-causes receive zero exact credit.",
        intervention="Resample selected candidate actions from an explicit {-1,+1} baseline while reusing admissible exogenous row evidence.",
        null_model="Destroy A->Y; latent-correlation-only; pure-noise; high-noise; OOD sign inversion.",
        negative_control="Uniform, random, recency, observational association and delayed-error eligibility proxy.",
        baseline="Exact Shapley reference plus finite-budget MC approximation and simple non-causal credit baselines.",
        ood_condition="Weak confounder and sign-inverted confounder contexts on independent frozen seeds.",
        metric="causal_rank_accuracy; false_credit_mass; Shapley efficiency; structural evaluations; wall time.",
        failure_predicate="Any exact primary predicate in experiments/csca_01/PREREGISTRATION.md fails.",
        replication_protocol="PRIMARY 12000..12031 then unchanged-code REPLICATION 22000..22031.",
        integration_target="cwc/replay candidate credit estimator; architecture integration explicitly withheld.",
    )
    hypothesis.validate()
    (REG / "rd02_hypotheses.json").write_text(json.dumps([asdict(hypothesis)], indent=2, sort_keys=True) + "\n", encoding="utf-8")
    graph.add_node(hypothesis.hypothesis_id, "Hypothesis", mechanism=hypothesis.mechanism)
    for claim_id in hypothesis.source_claims:
        graph.add_edge(claim_id, "DEPENDS_ON", hypothesis.hypothesis_id)
    graph.write_json(REG / "rd02_evidence_graph.json")

    h4 = HumanDecision(
        decision_id="H4-CSCA-01-AUTHOR-DIRECTIVE",
        gate="H4_EXPERIMENT_DESIGN",
        subject_id="CSCA-01",
        reviewer="AUTHOR_DIRECTIVE",
        reviewer_role="HUMAN_RESEARCH_OWNER",
        decision="APPROVE_EXECUTION",
        rationale="The uploaded ACT-R&D-02 explicitly fixes the CSCA-01 hypothesis, primary metric, null family and failure principle before execution. Architecture integration is not authorized.",
        evidence_refs=("docs/acts/ACT_RD_02.md", "experiments/csca_01/PREREGISTRATION.md"),
        created_at="2026-08-10",
        architecture_authority=False,
    )
    h4_path = write_human_decision(h4, GOV)

    c0 = ComputeRequest(
        compute_request_id="CR-CSCA-01-C0",
        hypothesis_id="H-CSCA-01",
        experiment_id="CSCA-01",
        stage="C0",
        scientific_question="Can the formalized counterfactual credit operator distinguish a structural cause from non-causes in an analytically known SCM?",
        kill_condition="Exact Shapley assigns non-zero structural credit to a candidate absent from the structural outcome equation or violates efficiency.",
        why_small_scale_is_insufficient="C0 is the small-scale analytic stage itself.",
        expected_information_gain=1.0,
        estimated_cost_units=1.0,
        stop_condition="Kill on formal counterexample or implementation identity failure.",
        owner="CWC_R&D",
        approved_by="AUTHOR_DIRECTIVE",
    )
    c0_decision = ComputeGovernor.evaluate(c0)
    c1 = ComputeRequest(
        compute_request_id="CR-CSCA-01-C1",
        hypothesis_id="H-CSCA-01",
        experiment_id="CSCA-01",
        stage="C1",
        scientific_question="Does the kernel survive replicated synthetic OOD and null attacks under measured CPU compute?",
        kill_condition="Any frozen exact primary predicate fails; approximation is separately qualified or rejected.",
        why_small_scale_is_insufficient="Analytic identities cannot establish finite-sample ranking, null behavior, approximation variance or OOD replication.",
        expected_information_gain=1.0,
        estimated_cost_units=8.0,
        baseline_completed=True,
        c0_pass=c0_decision.approved,
        stop_condition="Stop before any GPU scale if C1 fails or cannot alter the integration decision.",
        owner="CWC_R&D",
        approved_by="AUTHOR_DIRECTIVE",
    )
    c1_decision = ComputeGovernor.evaluate(c1)
    compute_payload = [
        {"request": asdict(c0), "decision": asdict(c0_decision)},
        {"request": asdict(c1), "decision": asdict(c1_decision)},
    ]
    (REG / "rd02_compute_requests.json").write_text(json.dumps(compute_payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    state = {
        "act": "ACT-R&D-02",
        "status": "PHASE_1_2_READY",
        "source_gate": frozen.gate_status,
        "paper_reproduction_authority": False,
        "mechanism_test_authority": bool(c0_decision.approved and c1_decision.approved),
        "architecture_promotion_authority": False,
        "h4_record": str(h4_path.relative_to(ROOT)),
        "preregistration_sha256": sha256_file(ROOT / "experiments/csca_01/PREREGISTRATION.md"),
        "next": "EXECUTE_CSCA_01_PRIMARY_THEN_REPLICATION_AND_NULLS",
    }
    (REG / "rd02_pipeline_state.json").write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(state, indent=2, sort_keys=True))
    return 0 if state["mechanism_test_authority"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
