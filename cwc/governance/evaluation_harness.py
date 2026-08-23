from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def canonical_manifest_digest(payload: object) -> str:
    """Canonical content digest for structured frozen-harness manifests."""
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def _digest_field(name: str, value: str) -> str:
    value = str(value).strip()
    if _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be lowercase SHA-256, not a semantic label")
    return value


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
            object.__setattr__(self, name, _digest_field(name, getattr(self, name)))

    @property
    def comparison_frame_digest(self) -> str:
        """Digest of everything that must remain identical across policies."""
        return canonical_manifest_digest({
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
        return canonical_manifest_digest({
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
