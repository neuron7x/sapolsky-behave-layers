from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass


def _req(name: str, value: str) -> str:
    value = str(value).strip()
    if not value:
        raise ValueError(f"{name} required")
    return value


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class FrozenEvaluationHarness:
    model_manifest_digest: str
    prompt_policy_digest: str
    tool_manifest_digest: str
    task_manifest_digest: str
    environment_digest: str
    budget_digest: str
    pricing_snapshot_digest: str
    scorer_digest: str
    statistical_plan_digest: str
    baseline_panel_digest: str
    governance_policy_digest: str

    def __post_init__(self) -> None:
        for name in (
            "model_manifest_digest", "prompt_policy_digest", "tool_manifest_digest",
            "task_manifest_digest", "environment_digest", "budget_digest",
            "pricing_snapshot_digest", "scorer_digest", "statistical_plan_digest",
            "baseline_panel_digest", "governance_policy_digest",
        ):
            object.__setattr__(self, name, _req(name, getattr(self, name)))

    @property
    def comparison_frame_digest(self) -> str:
        """Digest of everything that must remain identical across policies."""
        return _digest({
            "model_manifest_digest": self.model_manifest_digest,
            "prompt_policy_digest": self.prompt_policy_digest,
            "tool_manifest_digest": self.tool_manifest_digest,
            "task_manifest_digest": self.task_manifest_digest,
            "environment_digest": self.environment_digest,
            "budget_digest": self.budget_digest,
            "pricing_snapshot_digest": self.pricing_snapshot_digest,
            "scorer_digest": self.scorer_digest,
            "statistical_plan_digest": self.statistical_plan_digest,
            "baseline_panel_digest": self.baseline_panel_digest,
        })

    @property
    def full_digest(self) -> str:
        return _digest({
            "comparison_frame_digest": self.comparison_frame_digest,
            "governance_policy_digest": self.governance_policy_digest,
        })


def certify_controlled_comparison(
    reference: FrozenEvaluationHarness, candidate: FrozenEvaluationHarness
) -> str:
    if reference.comparison_frame_digest != candidate.comparison_frame_digest:
        raise ValueError(
            "controlled comparison invalid: tasks/models/tools/environment/budget/pricing/scorer/statistical plan/baseline panel differ"
        )
    if reference.governance_policy_digest == candidate.governance_policy_digest:
        raise ValueError("comparison requires distinct governance policies")
    return reference.comparison_frame_digest
