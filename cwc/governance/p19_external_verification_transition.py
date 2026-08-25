from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from cwc.governance.p19_external_verification_plan import CANONICAL_PLAN_PATH

ACTIVATED_PLAN_DEFAULT_PATH = (
    "artifacts/dgc-product-v1/generated/verifier-activation/"
    "P19_EXTERNAL_VERIFICATION_PLAN_V4_ACTIVE.json"
)


class P19ExternalVerificationTransitionError(RuntimeError):
    pass


class PlanView(Protocol):
    activation_authorized: bool
    verifier_entrypoint_path: str
    verifier_entrypoint_sha256: str
    verifier_dependency_manifest_digest: str
    check_contracts: tuple[dict[str, object], ...]
    all_check_implementations_complete: bool
    product_qualification_authorized: bool


@dataclass(frozen=True, slots=True)
class P19ExternalVerificationTransition:
    inactive_contract_path: str
    activated_plan_path: str
    same_entrypoint_identity: bool
    same_runtime_dependency_identity: bool
    same_check_contract_identity: bool
    inactive_contract_remains_inactive: bool
    activated_plan_is_active: bool
    product_qualification_authorized: bool

    @property
    def admissible(self) -> bool:
        return all((
            self.same_entrypoint_identity,
            self.same_runtime_dependency_identity,
            self.same_check_contract_identity,
            self.inactive_contract_remains_inactive,
            self.activated_plan_is_active,
            not self.product_qualification_authorized,
        ))


def verify_inactive_to_activated_transition(
    *,
    inactive: PlanView,
    activated: PlanView,
    inactive_contract_path: str = CANONICAL_PLAN_PATH,
    activated_plan_path: str = ACTIVATED_PLAN_DEFAULT_PATH,
) -> P19ExternalVerificationTransition:
    if Path(inactive_contract_path).as_posix() == Path(activated_plan_path).as_posix():
        raise P19ExternalVerificationTransitionError(
            "activated verifier plan must not overwrite immutable inactive contract"
        )
    transition = P19ExternalVerificationTransition(
        inactive_contract_path=Path(inactive_contract_path).as_posix(),
        activated_plan_path=Path(activated_plan_path).as_posix(),
        same_entrypoint_identity=(
            inactive.verifier_entrypoint_path == activated.verifier_entrypoint_path
            and inactive.verifier_entrypoint_sha256 == activated.verifier_entrypoint_sha256
        ),
        same_runtime_dependency_identity=(
            inactive.verifier_dependency_manifest_digest == activated.verifier_dependency_manifest_digest
        ),
        same_check_contract_identity=(inactive.check_contracts == activated.check_contracts),
        inactive_contract_remains_inactive=(inactive.activation_authorized is False),
        activated_plan_is_active=(activated.activation_authorized is True),
        product_qualification_authorized=(
            inactive.product_qualification_authorized or activated.product_qualification_authorized
        ),
    )
    if not transition.admissible:
        raise P19ExternalVerificationTransitionError(
            "activated verifier plan is not an activation-only composition of the frozen inactive contract"
        )
    if not inactive.all_check_implementations_complete or not activated.all_check_implementations_complete:
        raise P19ExternalVerificationTransitionError("verifier check implementation population is incomplete")
    return transition
