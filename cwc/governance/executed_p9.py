from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import Sequence

from cwc.governance.baseline_panel import REQUIRED_BASELINES
from cwc.governance.external_source_authority import ExternalSourceAuthority, ExternalSourceStage
from cwc.governance.pareto import (
    MultiBaselineParetoCertificate,
    PairedBaselineEvidence,
    certify_multi_baseline_pareto_improvement,
)

_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _sha(name: str, value: str) -> str:
    value = str(value).strip()
    if _SHA256_RE.fullmatch(value) is None:
        raise ValueError(f"{name} must be lowercase SHA-256")
    return value


def _digest(payload: object) -> str:
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class ExecutedPairedBaselineEvidence:
    execution_population_digest: str
    evidence: PairedBaselineEvidence

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "execution_population_digest",
            _sha("execution_population_digest", self.execution_population_digest),
        )
        _sha("paired_task_digest", self.evidence.paired_task_digest)

    @property
    def digest(self) -> str:
        evidence = self.evidence
        return _digest(
            {
                "execution_population_digest": self.execution_population_digest,
                "baseline_id": evidence.baseline_id,
                "paired_task_digest": evidence.paired_task_digest,
                "coverage": evidence.coverage,
                "baseline_minus_dgc_cost": evidence.baseline_minus_dgc_cost,
                "dgc_minus_baseline_quality": evidence.dgc_minus_baseline_quality,
                "baseline_minus_dgc_catastrophic_regret": evidence.baseline_minus_dgc_catastrophic_regret,
                "cost_gain_support": evidence.cost_gain_support,
                "quality_gain_support": evidence.quality_gain_support,
                "catastrophic_gain_support": evidence.catastrophic_gain_support,
            }
        )


@dataclass(frozen=True, slots=True)
class ExecutedP9Certificate:
    family_id: str
    source_authority_digest: str
    execution_population_digest: str
    evidence_population_digest: str
    pareto: MultiBaselineParetoCertificate
    certificate_digest: str


def certify_executed_p9(
    authority: ExternalSourceAuthority,
    evidence: Sequence[ExecutedPairedBaselineEvidence],
    *,
    alpha: float = 0.05,
    quality_noninferiority_margin: float = 0.0,
    catastrophic_noninferiority_margin: float = 0.0,
) -> ExecutedP9Certificate:
    if authority.stage is not ExternalSourceStage.EXECUTED:
        raise ValueError("P9 requires EXECUTED source authority")
    execution = _sha(
        "authority.execution_population_digest", authority.execution_population_digest or ""
    )
    rows = tuple(evidence)
    if not rows:
        raise ValueError("non-empty executed P9 evidence required")
    if any(row.execution_population_digest != execution for row in rows):
        raise ValueError("P9 evidence belongs to a different execution population")

    expected = {kind.value for kind in REQUIRED_BASELINES}
    observed = {row.evidence.baseline_id for row in rows}
    if observed != expected or len(rows) != len(expected):
        raise ValueError("P9 requires exactly the frozen B0-B3 baseline set")

    paired = tuple(row.evidence for row in rows)
    certificate = certify_multi_baseline_pareto_improvement(
        paired,
        alpha=alpha,
        quality_noninferiority_margin=quality_noninferiority_margin,
        catastrophic_noninferiority_margin=catastrophic_noninferiority_margin,
    )
    evidence_digest = _digest(
        [
            (row.evidence.baseline_id, row.digest)
            for row in sorted(rows, key=lambda item: item.evidence.baseline_id)
        ]
    )
    payload = {
        "family_id": authority.family_id,
        "source_authority_digest": authority.digest,
        "execution_population_digest": execution,
        "evidence_population_digest": evidence_digest,
        "paired_task_digest": certificate.paired_task_digest,
        "all_baselines_certified": certificate.all_baselines_certified,
        "familywise_alpha": certificate.familywise_alpha,
        "quality_noninferiority_margin": certificate.quality_noninferiority_margin,
        "catastrophic_noninferiority_margin": certificate.catastrophic_noninferiority_margin,
    }
    return ExecutedP9Certificate(
        family_id=authority.family_id,
        source_authority_digest=authority.digest,
        execution_population_digest=execution,
        evidence_population_digest=evidence_digest,
        pareto=certificate,
        certificate_digest=_digest(payload),
    )
