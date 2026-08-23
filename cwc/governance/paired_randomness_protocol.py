from __future__ import annotations

import hashlib
from dataclasses import dataclass
from typing import Mapping

from cwc.governance.execution_evidence_bundle import VerifiedExecutionBundle
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes

PROTOCOL = "DGC_PAIRED_COMMON_RANDOM_NUMBERS_V1"
INDEPENDENCE_ASSUMPTION = "CROSS_TASK_REPLICATE_PROVIDER_REQUESTS_CONDITIONALLY_INDEPENDENT"


class RandomnessProtocolError(RuntimeError):
    pass


def paired_seed(*, root_digest: str, task_id: str, replicate: int) -> int:
    if replicate < 0 or not task_id.strip():
        raise ValueError("valid task_id and nonnegative replicate required")
    material = f"{PROTOCOL}|{root_digest}|{task_id}|{replicate}".encode("utf-8")
    return int.from_bytes(hashlib.sha256(material).digest()[:8], "big") & ((1 << 63) - 1)


@dataclass(frozen=True, slots=True)
class RandomnessProtocolAuthority:
    root_digest: str
    execution_bundle_digest: str
    protocol: str
    independence_assumption: str
    task_replicate_pairs: int
    provider_requests: int
    schedule_digest: str
    authority_digest: str
    assumption_verified: bool = False


def verify_paired_randomness_protocol(
    bundle: VerifiedExecutionBundle,
    *,
    root_digest: str,
) -> RandomnessProtocolAuthority:
    request_ids: set[str] = set()
    schedule_rows: list[tuple[str, int, int, tuple[str, ...]]] = []
    by_pair: dict[tuple[str, int], list] = {}
    for result in bundle.results:
        payload = result.result_payload
        if payload.get("randomness_protocol") != PROTOCOL:
            raise RandomnessProtocolError("execution result lacks frozen paired randomness protocol")
        try:
            seed = int(payload["replicate_seed"])
        except (KeyError, TypeError, ValueError) as exc:
            raise RandomnessProtocolError("execution result replicate_seed missing or malformed") from exc
        expected = paired_seed(
            root_digest=root_digest,
            task_id=result.unit.task_id,
            replicate=result.unit.replicate,
        )
        if seed != expected:
            raise RandomnessProtocolError("execution result seed differs from precommitted paired schedule")
        request_id = str(payload.get("provider_request_id", "")).strip()
        if not request_id:
            raise RandomnessProtocolError("provider_request_id required for randomness protocol")
        if request_id in request_ids:
            raise RandomnessProtocolError("provider_request_id reused across execution units")
        request_ids.add(request_id)
        by_pair.setdefault((result.unit.task_id, result.unit.replicate), []).append(result)

    for (task_id, replicate), rows in sorted(by_pair.items()):
        policies = tuple(sorted(row.unit.policy_id for row in rows))
        if len(policies) != len(set(policies)):
            raise RandomnessProtocolError("duplicate policy within paired task/replicate")
        expected_seed = paired_seed(root_digest=root_digest, task_id=task_id, replicate=replicate)
        if any(int(row.result_payload["replicate_seed"]) != expected_seed for row in rows):
            raise RandomnessProtocolError("policies within a pair do not share the precommitted seed")
        schedule_rows.append((task_id, replicate, expected_seed, policies))

    schedule_digest = sha256_bytes(canonical_json_bytes(schedule_rows))
    payload: Mapping[str, object] = {
        "root_digest": root_digest,
        "execution_bundle_digest": bundle.bundle_digest,
        "protocol": PROTOCOL,
        "independence_assumption": INDEPENDENCE_ASSUMPTION,
        "task_replicate_pairs": len(schedule_rows),
        "provider_requests": len(request_ids),
        "schedule_digest": schedule_digest,
        "assumption_verified": False,
    }
    return RandomnessProtocolAuthority(
        root_digest=root_digest,
        execution_bundle_digest=bundle.bundle_digest,
        protocol=PROTOCOL,
        independence_assumption=INDEPENDENCE_ASSUMPTION,
        task_replicate_pairs=len(schedule_rows),
        provider_requests=len(request_ids),
        schedule_digest=schedule_digest,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
        assumption_verified=False,
    )
