from __future__ import annotations

from cwc.governance.confirmatory_generation import (
    ConfirmatoryCompletionCertificate,
    ConfirmatoryGenerationRoot,
)
from cwc.governance.external_source_authority import (
    ExternalSourceAuthority,
    ExternalSourceStage,
    promote_executed,
)


def promote_executed_from_confirmatory(
    source_authority: ExternalSourceAuthority,
    *,
    root: ConfirmatoryGenerationRoot,
    completion: ConfirmatoryCompletionCertificate,
) -> ExternalSourceAuthority:
    if source_authority.stage is not ExternalSourceStage.MATERIALIZED_VERIFIED:
        raise ValueError("source authority must be MATERIALIZED_VERIFIED before execution promotion")
    if source_authority.family_id != root.family_id:
        raise ValueError("source family does not match confirmatory generation root")
    if source_authority.digest != root.source_authority_digest:
        raise ValueError("source authority digest does not match confirmatory generation root")
    if not completion.complete:
        raise ValueError("confirmatory completion must be complete")
    if completion.generation_root_digest != root.root_digest:
        raise ValueError("completion belongs to a different confirmatory generation root")
    return promote_executed(
        source_authority,
        execution_population_digest=completion.execution_population_digest,
    )
