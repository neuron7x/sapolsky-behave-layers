from __future__ import annotations

import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from cwc.governance import confirmatory_root_authority as product
from cwc.governance.product_statistical_plan import ProductStatisticalPlan
from scripts import dgc_freeze_task_partition as partition


@pytest.mark.parametrize("family", ["SWE_BENCH_VERIFIED", "TERMINAL_BENCH_2_1"])
def test_retired_product_family_rejected_at_mint_and_replay(tmp_path, monkeypatch, family):
    monkeypatch.setattr(
        product, "verify_execution_manifest_freeze_document", lambda _: {"family_id": family}
    )
    document = tmp_path / "root.json"
    document.write_text(json.dumps({"schema": product.SCHEMA, "family_id": family}))
    with pytest.raises(product.ConfirmatoryRootAuthorityError, match="retired under issue #17"):
        product.build_confirmatory_root_authority(
            execution_manifest_freeze_path=document,
            harness_freeze_path=document,
            trial_sizing_authority_path=document,
            task_partition_path=document,
            materialization_reference_path=document,
            source_registry_path=document,
            root_input_path=document,
        )
    with pytest.raises(product.ConfirmatoryRootAuthorityError, match="retired under issue #17"):
        product.verify_confirmatory_root_authority_document(document)


@pytest.mark.parametrize("mechanism", [False, True])
def test_partition_cli_dispatches_freeze_and_preserves_lineage(tmp_path, monkeypatch, mechanism):
    plan = ProductStatisticalPlan()
    execution = {
        "statistical_plan": {},
        "statistical_plan_digest": plan.digest,
        "materialization_reference_path": "eval_bundle/reference.json",
        "materialization_reference_digest": "a" * 64,
        "task_manifest_digest": "b" * 64,
        "family_id": "TERMINAL_BENCH_2_1",
    }
    freeze_flag = "--mechanism-execution-freeze" if mechanism else "--execution-freeze"
    called = []

    def verifier(kind):
        def verify(path):
            called.append((kind, path))
            return execution
        return verify

    def freeze(**kwargs):
        assert kwargs["family_id"] == execution["family_id"]
        assert kwargs["statistical_plan"].digest == plan.digest
        assert kwargs["materialization_reference_path"] == tmp_path / "eval_bundle/reference.json"
        return SimpleNamespace(
            statistical_plan_digest=plan.digest,
            materialization_reference_digest="a" * 64,
            task_manifest_digest="b" * 64,
            family_id=execution["family_id"],
            calibration_task_ids=("a",),
            confirmatory_task_ids=("b",),
            receipt_digest="c" * 64,
            document={"outcomes_observed": False},
        )

    monkeypatch.setattr(partition, "ROOT", tmp_path)
    monkeypatch.setattr(partition, "RUNTIME_ROOT", tmp_path / "eval_bundle")
    monkeypatch.setattr(partition, "verify_execution_manifest_freeze_document", verifier(False))
    monkeypatch.setattr(partition, "verify_mechanism_execution_freeze_document", verifier(True))
    monkeypatch.setattr(partition, "freeze_task_partition", freeze)
    monkeypatch.setattr(sys, "argv", [
        "dgc_freeze_task_partition", "--generation-root", str(tmp_path),
        freeze_flag, "eval_bundle/freeze.json", "--output", "eval_bundle/partition.json",
    ])
    assert partition.main() == 0
    assert called == [(mechanism, Path(tmp_path / "eval_bundle/freeze.json"))]
    assert json.loads((tmp_path / "eval_bundle/partition.json").read_text()) == {"outcomes_observed": False}
