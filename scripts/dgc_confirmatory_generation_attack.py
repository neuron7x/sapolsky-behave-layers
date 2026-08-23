from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from enum import Enum

from cwc.governance.confirmatory_generation import (
    certify_confirmatory_completion,
    freeze_confirmatory_generation,
)


def h(char: str) -> str:
    return char * 64


def task_digest(tasks=("t1", "t2")) -> str:
    return hashlib.sha256(
        json.dumps(tuple(sorted(tasks)), sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


class Stage(Enum):
    SOURCE_VERIFIED = 2
    MATERIALIZED_VERIFIED = 3


@dataclass
class Source:
    family_id: str = "FAM"
    stage: Stage = Stage.MATERIALIZED_VERIFIED
    digest: str = h("a")
    materialized_tree_sha256: str = h("b")
    materialized_task_manifest_sha256: str = task_digest()


@dataclass
class Panel:
    executable_frozen: bool = True
    digest: str = h("c")


@dataclass
class Plan:
    digest: str = h("d")
    per_claim_alpha: float = 0.002
    target_power: float = 0.90


@dataclass
class Sizing:
    required_trials_per_task: int = 2
    per_claim_alpha: float = 0.002
    target_power: float = 0.90


@dataclass
class Harness:
    task_manifest_digest: str = task_digest()
    statistical_plan_digest: str = h("d")
    baseline_panel_digest: str = h("c")
    governance_policy_digest: str = h("3")
    comparison_frame_digest: str = h("e")
    full_digest: str = h("4")


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


def freeze(source=None, panel=None, plan=None, sizing=None, harnesses=None, dist=None):
    source = source or Source()
    panel = panel or Panel()
    plan = plan or Plan()
    sizing = sizing or Sizing()
    dist = dist or Dist()
    harnesses = harnesses or {
        "b0": Harness(governance_policy_digest=h("3"), full_digest=h("4")),
        "dgc": Harness(governance_policy_digest=h("5"), full_digest=h("6")),
    }
    return freeze_confirmatory_generation(
        generation_id="attack-generation",
        repo_commit_oid="a" * 40,
        repo_tree_oid="b" * 40,
        source_authority=source,
        baseline_panel=panel,
        statistical_plan=plan,
        trial_sizing=sizing,
        policy_harnesses=harnesses,
        distributed_spec=dist,
    )


def main() -> int:
    killed = 0

    try:
        freeze(source=Source(stage=Stage.SOURCE_VERIFIED))
    except ValueError:
        killed += 1

    try:
        freeze(panel=Panel(executable_frozen=False))
    except ValueError:
        killed += 1

    try:
        freeze(dist=Dist(replicates=3))
    except ValueError:
        killed += 1

    bad_harnesses = {
        "b0": Harness(governance_policy_digest=h("3"), full_digest=h("4")),
        "dgc": Harness(
            governance_policy_digest=h("5"),
            full_digest=h("6"),
            comparison_frame_digest=h("9"),
        ),
    }
    try:
        freeze(harnesses=bad_harnesses)
    except ValueError:
        killed += 1

    try:
        freeze(dist=Dist(task_ids=("t1", "other")))
    except ValueError:
        killed += 1

    root = freeze()
    try:
        certify_confirmatory_completion(root, Completion(committed_units=7))
    except ValueError:
        killed += 1

    if killed != 6:
        raise AssertionError(f"expected 6/6 attacks killed, got {killed}")
    print("DGC-CONFIRMATORY-GENERATION-ATTACK: PASS killed=6/6")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
