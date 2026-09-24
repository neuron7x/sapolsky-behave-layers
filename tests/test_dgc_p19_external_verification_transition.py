from __future__ import annotations

from types import SimpleNamespace

import pytest

from cwc.governance.p19_external_verification_plan import CANONICAL_PLAN_PATH
from cwc.governance.p19_external_verification_transition import (
    ACTIVATED_PLAN_DEFAULT_PATH,
    P19ExternalVerificationTransitionError,
    verify_inactive_to_activated_transition,
)


def _plan(*, active: bool, entry_sha: str = "a" * 64, deps: str = "b" * 64, method: str = "m"):
    return SimpleNamespace(
        activation_authorized=active,
        verifier_entrypoint_path="scripts/dgc_external_p19_verifier.py",
        verifier_entrypoint_sha256=entry_sha,
        verifier_dependency_manifest_digest=deps,
        check_contracts=({"check_id": "REPOSITORY_IDENTITY", "method_id": method},),
        all_check_implementations_complete=True,
        product_qualification_authorized=False,
    )


def test_inactive_contract_and_activated_composition_are_distinct_and_compatible():
    transition = verify_inactive_to_activated_transition(
        inactive=_plan(active=False),
        activated=_plan(active=True),
    )
    assert transition.admissible is True
    assert transition.inactive_contract_path == CANONICAL_PLAN_PATH
    assert transition.activated_plan_path == ACTIVATED_PLAN_DEFAULT_PATH
    assert transition.inactive_contract_path != transition.activated_plan_path


def test_activation_cannot_overwrite_immutable_inactive_contract():
    with pytest.raises(P19ExternalVerificationTransitionError, match="must not overwrite"):
        verify_inactive_to_activated_transition(
            inactive=_plan(active=False),
            activated=_plan(active=True),
            activated_plan_path=CANONICAL_PLAN_PATH,
        )


@pytest.mark.parametrize(
    "activated",
    [
        _plan(active=True, entry_sha="c" * 64),
        _plan(active=True, deps="d" * 64),
        _plan(active=True, method="different-method"),
    ],
)
def test_activation_cannot_refreeze_changed_verifier_contract(activated):
    with pytest.raises(P19ExternalVerificationTransitionError, match="not an activation-only composition"):
        verify_inactive_to_activated_transition(
            inactive=_plan(active=False),
            activated=activated,
        )


def test_activation_cannot_smuggle_product_qualification():
    activated = _plan(active=True)
    activated.product_qualification_authorized = True
    with pytest.raises(P19ExternalVerificationTransitionError, match="not an activation-only composition"):
        verify_inactive_to_activated_transition(
            inactive=_plan(active=False),
            activated=activated,
        )
