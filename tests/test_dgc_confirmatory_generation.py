from dataclasses import dataclass
from enum import Enum

import pytest

from cwc.governance.confirmatory_generation import (
    certify_confirmatory_completion,
    freeze_confirmatory_generation,
)


def h(char: str) -> str:
    return char * 64


class Stage(Enum):
    MATERIALIZED_VERIFIED = 3
    SOURCE_VERIFIED = 2


@dataclass
class Source:
    family_id: str = "FAM"
    stage: Stage = Stage.MATERIALIZED_VERIFIED
    digest: str = h("a")
    materialized_tree_sha256: str = h("b")
    materialized_task_manifest_sha256: str = ""


@dataclass
class Panel:
    executable_frozen: bool = True
    digest: str = h("c")


@dataclass
class Plan:
    digest: str = h("d")
    per_claim_alpha: float = 0.002
    target_power: float = 0.9


@dataclass
class Sizing:
    required_trials_per_task: int = 2
    per_claim_alpha: float = 0.002
    target_power: float = 0.9


@dataclass
class Harness:
    task_manifest_digest: str
    statistical_plan_digest: str = h("d")
    baseline_panel_digest: str = h("c")
    governance_policy_digest: str = ""
    comparison_frame_digest: str = h("e")
    full_digest: str = ""


@dataclass
class Dist:
    task_ids: tuple[str, ...] = ("t1", "t2")
    policy_ids: tuple[str, ...] = ("b0", "dgc")
    replicates: int = 2
    harness_digest: str = h("e")
    statistical_plan_digest: str = h("d")
    digest: str = h("f")


@dataclass
class Completion:
    spec_digest: str = h("f")
    expected_units: int = 8
    committed_units: int = 8
    total_cost_usd: float = 1.0
    audit_root_digest: str = h("1")
    result_population_digest: str = h("2")
    complete: bool = True


def task_digest(tasks=("t1", "t2")):
    import hashlib
    import json

    return hashlib.sha256(
        json.dumps(tuple(sorted(tasks)), sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


def fixture():
    source = Source(materialized_task_manifest_sha256=task_digest())
    harnesses = {
        "b0": Harness(
            task_manifest_digest=source.materialized_task_manifest_sha256,
            governance_policy_digest=h("3"),
            full_digest=h("4"),
        ),
        "dgc": Harness(
            task_manifest_digest=source.materialized_task_manifest_sha256,
            governance_policy_digest=h("5"),
            full_digest=h("6"),
        ),
    }
    return source, Panel(), Plan(), Sizing(), harnesses, Dist()


def freeze():
    source, panel, plan, sizing, harnesses, dist = fixture()
    return freeze_confirmatory_generation(
        generation_id="g1",
        repo_commit_oid="a" * 40,
        repo_tree_oid="b" * 40,
        source_authority=source,
        baseline_panel=panel,
        statistical_plan=plan,
        trial_sizing=sizing,
        policy_harnesses=harnesses,
        distributed_spec=dist,
    )


def test_good_generation_and_completion():
    root = freeze()
    assert root.expected_work_units == 8
    assert len(root.root_digest) == 64
    cert = certify_confirmatory_completion(root, Completion())
    assert cert.complete and len(cert.execution_population_digest) == 64


def test_source_must_be_materialized():
    source, panel, plan, sizing, harnesses, dist = fixture()
    source.stage = Stage.SOURCE_VERIFIED
    with pytest.raises(ValueError, match="MATERIALIZED_VERIFIED"):
        freeze_confirmatory_generation(
            generation_id="g",
            repo_commit_oid="a" * 40,
            repo_tree_oid="b" * 40,
            source_authority=source,
            baseline_panel=panel,
            statistical_plan=plan,
            trial_sizing=sizing,
            policy_harnesses=harnesses,
            distributed_spec=dist,
        )


def test_task_population_is_bound():
    source, panel, plan, sizing, harnesses, dist = fixture()
    dist.task_ids = ("t1", "other")
    with pytest.raises(ValueError, match="task population"):
        freeze_confirmatory_generation(
            generation_id="g",
            repo_commit_oid="a" * 40,
            repo_tree_oid="b" * 40,
            source_authority=source,
            baseline_panel=panel,
            statistical_plan=plan,
            trial_sizing=sizing,
            policy_harnesses=harnesses,
            distributed_spec=dist,
        )


def test_baseline_panel_must_be_executable_frozen():
    source, panel, plan, sizing, harnesses, dist = fixture()
    panel.executable_frozen = False
    with pytest.raises(ValueError, match="executable-frozen"):
        freeze_confirmatory_generation(
            generation_id="g",
            repo_commit_oid="a" * 40,
            repo_tree_oid="b" * 40,
            source_authority=source,
            baseline_panel=panel,
            statistical_plan=plan,
            trial_sizing=sizing,
            policy_harnesses=harnesses,
            distributed_spec=dist,
        )


def test_replicates_must_match_cluster_aware_sizing():
    source, panel, plan, sizing, harnesses, dist = fixture()
    dist.replicates = 3
    with pytest.raises(ValueError, match="replicate count"):
        freeze_confirmatory_generation(
            generation_id="g",
            repo_commit_oid="a" * 40,
            repo_tree_oid="b" * 40,
            source_authority=source,
            baseline_panel=panel,
            statistical_plan=plan,
            trial_sizing=sizing,
            policy_harnesses=harnesses,
            distributed_spec=dist,
        )


def test_policy_population_and_harness_frame_are_bound():
    source, panel, plan, sizing, harnesses, dist = fixture()
    harnesses["dgc"].comparison_frame_digest = h("9")
    with pytest.raises(ValueError, match="controlled-comparison frame"):
        freeze_confirmatory_generation(
            generation_id="g",
            repo_commit_oid="a" * 40,
            repo_tree_oid="b" * 40,
            source_authority=source,
            baseline_panel=panel,
            statistical_plan=plan,
            trial_sizing=sizing,
            policy_harnesses=harnesses,
            distributed_spec=dist,
        )


def test_dist_spec_must_bind_comparison_frame():
    source, panel, plan, sizing, harnesses, dist = fixture()
    dist.harness_digest = h("9")
    with pytest.raises(ValueError, match="comparison frame"):
        freeze_confirmatory_generation(
            generation_id="g",
            repo_commit_oid="a" * 40,
            repo_tree_oid="b" * 40,
            source_authority=source,
            baseline_panel=panel,
            statistical_plan=plan,
            trial_sizing=sizing,
            policy_harnesses=harnesses,
            distributed_spec=dist,
        )


def test_completion_cannot_be_partial_or_foreign():
    root = freeze()
    with pytest.raises(ValueError, match="different distributed spec"):
        certify_confirmatory_completion(root, Completion(spec_digest=h("9")))
    with pytest.raises(ValueError, match="full frozen work population"):
        certify_confirmatory_completion(root, Completion(committed_units=7))
