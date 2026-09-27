from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping

from cwc.governance.materialization_transaction import (
    canonical_json_bytes,
    sha256_bytes,
)

SCHEMA = "DGC_RUNTIME_COST_CONTRACT_V1"
ALLOCATION_POLICY = "ALL_LOCAL_COMPUTE_TO_INFRA_V1"
ZERO_COMPONENTS = (
    "router_usd",
    "countermodel_usd",
    "retrieval_usd",
    "tools_usd",
    "verification_usd",
    "human_review_usd",
    "retry_usd",
    "failure_loss_usd",
)


class RuntimeCostContractError(RuntimeError):
    pass


def _required(name: str, value: object) -> str:
    text = str(value).strip()
    if not text:
        raise RuntimeCostContractError(f"{name} required")
    return text


def _positive(name: str, value: object) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise RuntimeCostContractError(f"{name} must be numeric") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise RuntimeCostContractError(f"{name} must be finite and > 0")
    return parsed


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise RuntimeCostContractError(f"{name} must be lowercase SHA-256")
    return text


@dataclass(frozen=True, slots=True)
class RuntimeCostContract:
    host_profile_id: str
    infra_usd_per_second: float
    infra_rate_source_uri: str
    infra_rate_captured_at: str
    zero_by_contract: tuple[tuple[str, str], ...]

    def clause(self, component: str) -> str:
        rows = dict(self.zero_by_contract)
        if component not in rows:
            raise RuntimeCostContractError(
                f"runtime cost clause missing for {component}"
            )
        return rows[component]


def parse_runtime_cost_contract(value: object) -> RuntimeCostContract:
    if not isinstance(value, Mapping):
        raise RuntimeCostContractError("runtime_cost_contract must be an object")
    if value.get("schema") != SCHEMA:
        raise RuntimeCostContractError("runtime cost contract schema mismatch")
    if value.get("allocation_policy") != ALLOCATION_POLICY:
        raise RuntimeCostContractError("runtime cost allocation policy mismatch")
    for field in (
        "billable_external_tools_allowed",
        "paid_retrieval_allowed",
        "human_review_allowed",
        "automatic_retries_allowed",
    ):
        if value.get(field) is not False:
            raise RuntimeCostContractError(
                f"runtime cost contract requires {field}=false"
            )
    raw_clauses = value.get("zero_by_contract")
    if not isinstance(raw_clauses, Mapping):
        raise RuntimeCostContractError("zero_by_contract must be an object")
    if set(str(key) for key in raw_clauses) != set(ZERO_COMPONENTS):
        raise RuntimeCostContractError(
            "runtime zero-by-contract component population mismatch"
        )
    clauses: list[tuple[str, str]] = []
    for component in ZERO_COMPONENTS:
        clauses.append(
            (component, _required(f"{component} clause_id", raw_clauses[component]))
        )
    return RuntimeCostContract(
        host_profile_id=_required("host_profile_id", value.get("host_profile_id")),
        infra_usd_per_second=_positive(
            "infra_usd_per_second", value.get("infra_usd_per_second")
        ),
        infra_rate_source_uri=_required(
            "infra_rate_source_uri", value.get("infra_rate_source_uri")
        ),
        infra_rate_captured_at=_required(
            "infra_rate_captured_at", value.get("infra_rate_captured_at")
        ),
        zero_by_contract=tuple(clauses),
    )


def runtime_physical_cost_evidence(
    *,
    contract: RuntimeCostContract,
    budget_manifest_sha256: str,
    elapsed_ns: int,
) -> tuple[dict[str, object], dict[str, object], float]:
    budget_sha = _sha("budget_manifest_sha256", budget_manifest_sha256)
    if isinstance(elapsed_ns, bool):
        raise RuntimeCostContractError("elapsed_ns must be an integer")
    try:
        elapsed = int(elapsed_ns)
    except (TypeError, ValueError) as exc:
        raise RuntimeCostContractError("elapsed_ns must be an integer") from exc
    if elapsed <= 0:
        raise RuntimeCostContractError("elapsed_ns must be > 0")
    elapsed_seconds = elapsed / 1_000_000_000.0
    infra_usd = elapsed_seconds * contract.infra_usd_per_second
    measurement = {
        "schema": "DGC_RUNTIME_COST_MEASUREMENT_V1",
        "budget_manifest_sha256": budget_sha,
        "host_profile_id": contract.host_profile_id,
        "infra_rate_source_uri": contract.infra_rate_source_uri,
        "infra_rate_captured_at": contract.infra_rate_captured_at,
        "infra_usd_per_second": contract.infra_usd_per_second,
        "elapsed_ns": elapsed,
        "elapsed_seconds": elapsed_seconds,
        "infra_usd": infra_usd,
        "clock": "time.monotonic_ns",
    }
    evidence: dict[str, object] = {}
    for component in ZERO_COMPONENTS:
        evidence[component] = {
            "value_usd": 0.0,
            "authority": "ZERO_BY_CONTRACT",
            "source_digest": sha256_bytes(
                canonical_json_bytes({
                    "budget_manifest_sha256": budget_sha,
                    "component": component,
                    "clause_id": contract.clause(component),
                })
            ),
        }
    evidence["infra_usd"] = {
        "value_usd": infra_usd,
        "authority": "INFRA_METER",
        "source_digest": sha256_bytes(canonical_json_bytes(measurement)),
    }
    return evidence, measurement, infra_usd
