from __future__ import annotations

import json
from pathlib import Path

import pytest

from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
from cwc.governance.p9_scientific_authority_v2 import (
    build_p9_scientific_authority_v2,
    verify_p9_scientific_authority_v2_document,
)


def h(char: str) -> str:
    return char * 64


def write(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def dual_doc(path: Path, *, exact: bool, conditional: bool) -> Path:
    exact_certificate = {
        "paired_panel_digest": h("1"),
        "results": [],
        "quality_noninferiority_margin": 0.02,
        "catastrophic_noninferiority_margin": 0.01,
        "all_baselines_observed": exact,
        "evidence_manifest_digest": h("2"),
        "method": "EXACT_FROZEN_FINITE_PANEL_PARETO_V1",
    }
    exact_digest = sha256_bytes(canonical_json_bytes(exact_certificate))
    payload = {
        "family_id": "SWE_BENCH_VERIFIED",
        "finite_panel_v3_authority_digest": h("3"),
        "execution_authority_digest": h("4"),
        "execution_population_digest": h("5"),
        "execution_bundle_digest": h("6"),
        "physical_cost_bundle_digest": h("7"),
        "physical_cost_population_digest": h("8"),
        "harness_freeze_digest": h("9"),
        "confirmatory_task_manifest_digest": h("a"),
        "statistical_plan_digest": h("b"),
        "paired_panel_digest": h("1"),
        "exact_panel_certificate": exact_certificate,
        "exact_panel_certificate_digest": exact_digest,
        "exact_panel_supported": exact,
        "expected_effect_certificate_digest": h("c"),
        "expected_effect_supported_under_independence_assumption": conditional,
        "randomness_protocol": "DGC_PAIRED_COMMON_RANDOM_NUMBERS_V1",
        "randomness_schedule_digest": h("d"),
        "randomness_independence_assumption": "CROSS_TASK_REPLICATE_PROVIDER_REQUESTS_CONDITIONALLY_INDEPENDENT",
        "randomness_assumption_verified": False,
        "claim_scope": "EXACT_FROZEN_PANEL_UNCONDITIONAL_PLUS_EXPECTATION_CONDITIONAL_V1",
        "generalization_evaluation_authorized": exact,
    }
    return write(path, {
        "schema": "DGC_EXECUTED_P9_DUAL_AUTHORITY_V4",
        **payload,
        "authority_digest": sha256_bytes(canonical_json_bytes(payload)),
        "physical_cost_accounting_verified": True,
        "product_promotion_authorized": False,
    })


def ccf_doc(path: Path, *, complete: bool = True) -> Path:
    audits = [{
        "replicate": 0,
        "value_regret_units": 2,
        "avoidable_cost_units": 3,
        "policy_cost_units": 10,
        "policy_value_units": 20,
        "oracle_cost_units": 7,
        "oracle_value_units": 22,
        "certificate_digest": h("e"),
    }]
    payload = {
        "family_id": "SWE_BENCH_VERIFIED",
        "ccf_spec_authority_digest": h("f"),
        "ccf_spec_digest": h("0"),
        "execution_authority_digest": h("4"),
        "execution_population_digest": h("5"),
        "execution_bundle_digest": h("6"),
        "physical_cost_bundle_digest": h("7"),
        "physical_cost_population_digest": h("8"),
        "harness_freeze_digest": h("9"),
        "ccf_evidence_bundle_digest": h("1"),
        "ccf_evidence_population_digest": h("2"),
        "dgc_policy_id": "DGC",
        "confirmatory_task_manifest_digest": h("a"),
        "replicate_audits": audits,
        "total_value_regret_units": 2,
        "total_avoidable_cost_units": 3,
        "max_value_regret_units": 2,
        "max_avoidable_cost_units": 3,
        "headroom_audit_complete": complete,
    }
    return write(path, {
        "schema": "DGC_CCF_ORACLE_AUDIT_AUTHORITY_V1",
        **payload,
        "authority_digest": sha256_bytes(canonical_json_bytes(payload)),
        "product_promotion_authorized": False,
    })


def test_exact_pass_conditional_fail_still_authorizes_only_generalization_evaluation(tmp_path: Path):
    dual = dual_doc(tmp_path / "dual.json", exact=True, conditional=False)
    ccf = ccf_doc(tmp_path / "ccf.json")
    authority = build_p9_scientific_authority_v2(
        dual_p9_authority_path=dual,
        ccf_oracle_audit_authority_path=ccf,
    )
    assert authority.exact_panel_supported is True
    assert authority.expected_effect_supported_under_independence_assumption is False
    assert authority.randomness_assumption_verified is False
    assert authority.generalization_evaluation_authorized is True
    out = write(tmp_path / "science.json", authority.document)
    verified = verify_p9_scientific_authority_v2_document(out)
    assert verified["generalization_evaluation_authorized"] is True
    assert verified["product_promotion_authorized"] is False


def test_exact_fail_cannot_be_rescued_by_conditional_pass(tmp_path: Path):
    dual = dual_doc(tmp_path / "dual.json", exact=False, conditional=True)
    ccf = ccf_doc(tmp_path / "ccf.json")
    authority = build_p9_scientific_authority_v2(
        dual_p9_authority_path=dual,
        ccf_oracle_audit_authority_path=ccf,
    )
    assert authority.expected_effect_supported_under_independence_assumption is True
    assert authority.exact_panel_supported is False
    assert authority.generalization_evaluation_authorized is False


def test_ccf_incomplete_is_rejected_before_scientific_composition(tmp_path: Path):
    dual = dual_doc(tmp_path / "dual.json", exact=True, conditional=True)
    ccf = ccf_doc(tmp_path / "ccf.json", complete=False)
    with pytest.raises(RuntimeError, match="headroom audit is incomplete"):
        build_p9_scientific_authority_v2(
            dual_p9_authority_path=dual,
            ccf_oracle_audit_authority_path=ccf,
        )


def test_forged_exact_flag_breaks_dual_authority_digest(tmp_path: Path):
    dual = dual_doc(tmp_path / "dual.json", exact=True, conditional=False)
    doc = json.loads(dual.read_text())
    doc["exact_panel_supported"] = False
    write(dual, doc)
    with pytest.raises(RuntimeError, match="authority digest mismatch"):
        build_p9_scientific_authority_v2(
            dual_p9_authority_path=dual,
            ccf_oracle_audit_authority_path=ccf_doc(tmp_path / "ccf.json"),
        )
