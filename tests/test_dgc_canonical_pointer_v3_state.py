from pathlib import Path

from cwc.governance.product_qualification_pointer import (
    CANONICAL_POINTER_PATH,
    SCHEMA,
    load_product_qualification_pointer,
)


ROOT = Path(__file__).resolve().parents[1]


def test_canonical_pointer_v3_is_digest_valid_and_fail_closed_pre_outcome():
    path = ROOT / CANONICAL_POINTER_PATH
    doc = load_product_qualification_pointer(path)
    assert doc["schema"] == SCHEMA
    assert doc["activation_authorized"] is False
    assert doc["product_qualified_claimed"] is False
    assert doc["production_control_authorized"] is False
    assert doc["generation_id"] == "UNCONFIGURED"
    assert doc["repo_commit"] == "0" * 40
    assert doc["repo_tree"] == "0" * 40
    assert doc["global_v5_authority_path"] == "UNCONFIGURED"
    assert doc["global_v5_authority_digest"] == "0" * 64
