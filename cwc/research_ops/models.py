from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Literal

PublicationStatus = Literal[
    "PEER_REVIEWED",
    "CONFERENCE",
    "WORKSHOP",
    "PREPRINT",
    "DATASET",
    "CODE",
    "UNKNOWN",
]
SourceGateStatus = Literal["SOURCE_VERIFIED", "QUARANTINED", "NEW_REVISION"]


@dataclass(frozen=True, slots=True)
class SourceSpan:
    source_id: str
    source_path: str
    start_line: int
    end_line: int
    section: str = "UNKNOWN"
    span_quality: str = "EXACT"

    def validate(self) -> None:
        if not self.source_id:
            raise ValueError("source_id is required")
        if not self.source_path:
            raise ValueError("source_path is required")
        if self.start_line < 1 or self.end_line < self.start_line:
            raise ValueError("invalid source line range")


@dataclass(frozen=True, slots=True)
class ClaimRecord:
    claim_id: str
    source_id: str
    source_span: SourceSpan
    claim_text: str
    claim_type: str
    relation: str
    variables: tuple[str, ...] = ()
    intervention: str = ""
    comparison: str = ""
    outcome: str = ""
    metric: str = ""
    result: str = ""
    authors_interpretation: str = ""
    automatic_flags: tuple[str, ...] = ()
    status: str = "UNVERIFIED_EXTRACTION"

    def validate(self) -> None:
        if not self.claim_id or not self.source_id or not self.claim_text:
            raise ValueError("claim identity and text are required")
        self.source_span.validate()
        if self.source_span.source_id != self.source_id:
            raise ValueError("claim source_id does not match source span")


@dataclass(frozen=True, slots=True)
class HypothesisCard:
    hypothesis_id: str
    source_claims: tuple[str, ...]
    mechanism: str
    formalization: str
    causal_graph: str
    prediction: str
    intervention: str
    null_model: str
    negative_control: str
    baseline: str
    ood_condition: str
    metric: str
    failure_predicate: str
    replication_protocol: str
    integration_target: str

    def validate(self) -> None:
        required = asdict(self)
        missing = [name for name, value in required.items() if not value]
        if missing:
            raise ValueError(f"hypothesis missing required fields: {', '.join(missing)}")


@dataclass(frozen=True, slots=True)
class RunTelemetry:
    run_id: str
    git_commit: str
    dataset_hash: str
    seed: int | str
    device: str
    wall_seconds: float
    gpu_seconds: float | None
    peak_vram_bytes: int | None
    peak_ram_bytes: int | None
    exit_code: int
    metric_output: dict[str, Any] = field(default_factory=dict)
    artifact_hashes: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ExperimentResult:
    experiment_id: str
    hypothesis_id: str
    preregistration_sha256: str
    code_commit: str
    dataset_hash: str
    primary_metric: str
    observed: Any
    null_results: dict[str, Any]
    ood_result: Any
    replication_result: Any
    verdict: str
    architecture_promotion_authority: bool = False
