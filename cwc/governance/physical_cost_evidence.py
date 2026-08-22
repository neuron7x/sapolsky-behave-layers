from __future__ import annotations

import hashlib
import json
import math
from dataclasses import dataclass
from enum import Enum
from typing import Mapping

from cwc.governance.product_economics import ProductTrialCost


class CostAuthority(str, Enum):
    PROVIDER_METER = "PROVIDER_METER"
    TOOL_METER = "TOOL_METER"
    INFRA_METER = "INFRA_METER"
    HUMAN_TIME_LOG = "HUMAN_TIME_LOG"
    FAILURE_LEDGER = "FAILURE_LEDGER"
    ZERO_BY_CONTRACT = "ZERO_BY_CONTRACT"


PRODUCT_COST_COMPONENTS = (
    "model_usd",
    "router_usd",
    "countermodel_usd",
    "retrieval_usd",
    "tools_usd",
    "verification_usd",
    "human_review_usd",
    "infra_usd",
    "retry_usd",
    "failure_loss_usd",
)


@dataclass(frozen=True, slots=True)
class CostComponentEvidence:
    component: str
    value_usd: float
    authority: CostAuthority
    source_digest: str

    def __post_init__(self) -> None:
        if self.component not in PRODUCT_COST_COMPONENTS:
            raise ValueError("unknown product cost component")
        value = float(self.value_usd)
        if not math.isfinite(value) or value < 0.0:
            raise ValueError("value_usd must be finite and >=0")
        object.__setattr__(self, "value_usd", value)
        if not self.source_digest.strip():
            raise ValueError("source_digest required")
        if value > 0.0 and self.authority is CostAuthority.ZERO_BY_CONTRACT:
            raise ValueError("nonzero cost cannot use ZERO_BY_CONTRACT authority")


@dataclass(frozen=True, slots=True)
class PhysicalCostCertificate:
    trial_id: str
    cost: ProductTrialCost
    component_evidence: tuple[CostComponentEvidence, ...]
    digest: str


def certify_physical_trial_cost(
    *, trial_id: str, evidence: Mapping[str, CostComponentEvidence]
) -> PhysicalCostCertificate:
    trial = str(trial_id).strip()
    if not trial:
        raise ValueError("trial_id required")
    if set(evidence) != set(PRODUCT_COST_COMPONENTS):
        missing = sorted(set(PRODUCT_COST_COMPONENTS) - set(evidence))
        extra = sorted(set(evidence) - set(PRODUCT_COST_COMPONENTS))
        raise ValueError(f"complete cost authority required; missing={missing}; extra={extra}")
    rows: list[CostComponentEvidence] = []
    values: dict[str, float] = {}
    for component in PRODUCT_COST_COMPONENTS:
        item = evidence[component]
        if item.component != component:
            raise ValueError("cost evidence key/component mismatch")
        rows.append(item)
        values[component] = item.value_usd
    cost = ProductTrialCost(**values)
    payload = {
        "trial_id": trial,
        "components": [
            (row.component, row.value_usd, row.authority.value, row.source_digest)
            for row in rows
        ],
        "total_operational_usd": cost.total_operational_usd,
    }
    digest = hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return PhysicalCostCertificate(trial, cost, tuple(rows), digest)
