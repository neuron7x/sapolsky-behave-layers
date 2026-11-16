"""Replay finite-world plans without accepting memory or information authority."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from cwc.memory.epistemic_store import EpistemicMemoryLedger
from cwc.planning.proof_carrying import WorldBranch, plan_counterfactual


def replay_memory_free_plan(
    *,
    plan_id: str,
    context_scope: Sequence[str],
    worlds: Sequence[tuple[str, Mapping[str, float], str]],
    robust_margin: float,
) -> tuple[dict[str, object], str, str | None]:
    """Return detached certificate data and the native decision from a fresh ledger.

    Inputs carry finite-world data only. No ledger, memory record, information
    action or executor can cross this boundary; admission remains the caller's
    responsibility.
    """
    result = plan_counterfactual(
        ledger=EpistemicMemoryLedger(),
        plan_id=plan_id,
        context_scope=context_scope,
        required_memories=(),
        worlds=[WorldBranch(world_id, utilities, provenance) for world_id, utilities, provenance in worlds],
        robust_margin=robust_margin,
        information_actions=(),
    )
    certificate = {**result.certificate.payload(), "certificate_digest": result.certificate.certificate_digest}
    return certificate, result.state.value, result.selected_action
