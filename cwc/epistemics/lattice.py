from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import hashlib
import json
import re
from pathlib import Path
from typing import Iterable, Sequence


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MINT_SEAL = object()
_CAPABILITY_SEAL = object()


class EpistemicError(RuntimeError):
    """Base class for fail-closed epistemic transition failures."""


class IllegalTransition(EpistemicError):
    """Raised when a transition is not licensed by the current state/capability."""


class CapabilityBindingError(EpistemicError):
    """Raised when a capability is replayed across claim/parent/scope boundaries."""


class EvidenceClassError(EpistemicError):
    """Raised when evidence cannot license the requested epistemic operation."""


class EpistemicState(str, Enum):
    OBSERVED = "OBSERVED"
    PREDICTIVE = "PREDICTIVE"
    ASSUMPTION_CONDITIONAL = "ASSUMPTION_CONDITIONAL"
    INTERVENTION_SUPPORTED = "INTERVENTION_SUPPORTED"
    UNIDENTIFIED = "UNIDENTIFIED"
    FALSIFIED = "FALSIFIED"
    OOD = "OOD"
    ABSTAIN = "ABSTAIN"


POSITIVE_CHAIN: tuple[EpistemicState, ...] = (
    EpistemicState.OBSERVED,
    EpistemicState.PREDICTIVE,
    EpistemicState.ASSUMPTION_CONDITIONAL,
    EpistemicState.INTERVENTION_SUPPORTED,
)
TERMINAL_STATES: frozenset[EpistemicState] = frozenset(
    {
        EpistemicState.UNIDENTIFIED,
        EpistemicState.FALSIFIED,
        EpistemicState.OOD,
        EpistemicState.ABSTAIN,
    }
)


class EvidenceKind(str, Enum):
    FACTUAL_OBSERVATION = "FACTUAL_OBSERVATION"
    PREDICTIVE_VALIDATION = "PREDICTIVE_VALIDATION"
    IDENTIFYING_ASSUMPTION = "IDENTIFYING_ASSUMPTION"
    DIRECT_INTERVENTION = "DIRECT_INTERVENTION"
    SURROGATE_COUNTERFACTUAL = "SURROGATE_COUNTERFACTUAL"
    COUNTERMODEL = "COUNTERMODEL"
    FALSIFICATION = "FALSIFICATION"
    OOD_DIAGNOSTIC = "OOD_DIAGNOSTIC"
    ABSTENTION_REASON = "ABSTENTION_REASON"


class EvidenceSource(str, Enum):
    FACTUAL_CHANNEL = "FACTUAL_CHANNEL"
    HELD_OUT_PREDICTION = "HELD_OUT_PREDICTION"
    ASSUMPTION_CONTRACT = "ASSUMPTION_CONTRACT"
    DIRECT_SYSTEM_REEXECUTION = "DIRECT_SYSTEM_REEXECUTION"
    EXTERNAL_ENV_INTERVENTION = "EXTERNAL_ENV_INTERVENTION"
    SURROGATE_MODEL = "SURROGATE_MODEL"
    REPLAY_GENERATED = "REPLAY_GENERATED"
    COUNTERMODEL_SEARCH = "COUNTERMODEL_SEARCH"
    DIAGNOSTIC = "DIAGNOSTIC"
    HUMAN_PROVENANCE = "HUMAN_PROVENANCE"


class CapabilityType(str, Enum):
    PREDICTIVE_PROMOTION = "PREDICTIVE_PROMOTION"
    ASSUMPTION_PROMOTION = "ASSUMPTION_PROMOTION"
    INTERVENTION_PROMOTION = "INTERVENTION_PROMOTION"
    TERMINAL_DEGRADE = "TERMINAL_DEGRADE"


_DIRECT_INTERVENTION_SOURCES = frozenset(
    {
        EvidenceSource.DIRECT_SYSTEM_REEXECUTION,
        EvidenceSource.EXTERNAL_ENV_INTERVENTION,
    }
)


def _normalize_strings(values: Iterable[str], *, field: str, allow_empty: bool = False) -> tuple[str, ...]:
    normalized = tuple(sorted({str(v).strip() for v in values if str(v).strip()}))
    if not allow_empty and not normalized:
        raise ValueError(f"{field} must be non-empty")
    return normalized


def _canonical_sha(payload: object) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True, slots=True)
class EvidenceRef:
    ref: str
    sha256: str
    kind: EvidenceKind
    source: EvidenceSource
    context_scope: tuple[str, ...]
    provenance: str

    def __post_init__(self) -> None:
        if not self.ref.strip():
            raise ValueError("evidence ref must be non-empty")
        if not _SHA256_RE.fullmatch(self.sha256):
            raise ValueError("evidence sha256 must be 64 lowercase hex characters")
        if not self.provenance.strip():
            raise ValueError("evidence provenance must be non-empty")
        object.__setattr__(self, "context_scope", _normalize_strings(self.context_scope, field="context_scope"))

    @property
    def digest(self) -> str:
        return _canonical_sha(self.as_dict())

    def as_dict(self) -> dict[str, object]:
        return {
            "ref": self.ref,
            "sha256": self.sha256,
            "kind": self.kind.value,
            "source": self.source.value,
            "context_scope": list(self.context_scope),
            "provenance": self.provenance,
        }

    @classmethod
    def from_file(
        cls,
        path: str | Path,
        *,
        kind: EvidenceKind,
        source: EvidenceSource,
        context_scope: Sequence[str],
        provenance: str,
        ref: str | None = None,
    ) -> "EvidenceRef":
        p = Path(path)
        return cls(
            ref=ref or str(p),
            sha256=hashlib.sha256(p.read_bytes()).hexdigest(),
            kind=kind,
            source=source,
            context_scope=tuple(context_scope),
            provenance=provenance,
        )


@dataclass(frozen=True, slots=True, init=False)
class EpistemicCapability:
    capability_type: CapabilityType
    target_state: EpistemicState
    claim_id: str
    parent_digest: str
    context_scope: tuple[str, ...]
    evidence: tuple[EvidenceRef, ...]
    assumption_ids: tuple[str, ...]
    operator_id: str | None
    reason: str
    capability_digest: str

    def __new__(cls, *args: object, **kwargs: object) -> "EpistemicCapability":
        raise TypeError("EpistemicCapability tokens can only be minted by EpistemicMachine")

    @classmethod
    def _mint(
        cls,
        *,
        capability_type: CapabilityType,
        target_state: EpistemicState,
        claim_id: str,
        parent_digest: str,
        context_scope: Sequence[str],
        evidence: Sequence[EvidenceRef],
        assumption_ids: Sequence[str] = (),
        operator_id: str | None = None,
        reason: str = "",
        _seal: object,
    ) -> "EpistemicCapability":
        if _seal is not _CAPABILITY_SEAL:
            raise TypeError("invalid capability mint seal")
        scope = _normalize_strings(context_scope, field="context_scope")
        assumptions = _normalize_strings(assumption_ids, field="assumption_ids", allow_empty=True)
        ev = tuple(sorted(evidence, key=lambda x: (x.ref, x.digest)))
        if not ev:
            raise EvidenceClassError("capability requires at least one evidence reference")
        payload = {
            "capability_type": capability_type.value,
            "target_state": target_state.value,
            "claim_id": claim_id,
            "parent_digest": parent_digest,
            "context_scope": list(scope),
            "evidence_digests": [e.digest for e in ev],
            "assumption_ids": list(assumptions),
            "operator_id": operator_id,
            "reason": reason,
        }
        obj = object.__new__(cls)
        object.__setattr__(obj, "capability_type", capability_type)
        object.__setattr__(obj, "target_state", target_state)
        object.__setattr__(obj, "claim_id", claim_id)
        object.__setattr__(obj, "parent_digest", parent_digest)
        object.__setattr__(obj, "context_scope", scope)
        object.__setattr__(obj, "evidence", ev)
        object.__setattr__(obj, "assumption_ids", assumptions)
        object.__setattr__(obj, "operator_id", operator_id)
        object.__setattr__(obj, "reason", reason)
        object.__setattr__(obj, "capability_digest", _canonical_sha(payload))
        return obj


@dataclass(frozen=True, slots=True, init=False)
class EpistemicRecord:
    state: EpistemicState
    claim_id: str
    context_scope: tuple[str, ...]
    assumption_ids: tuple[str, ...]
    operator_id: str | None
    evidence: tuple[EvidenceRef, ...]
    parent_digest: str | None
    transition_capability_digest: str | None
    lineage_depth: int
    reason: str
    record_digest: str

    def __new__(cls, *args: object, **kwargs: object) -> "EpistemicRecord":
        raise TypeError("EpistemicRecord can only be constructed by EpistemicMachine")

    @classmethod
    def _mint(
        cls,
        *,
        state: EpistemicState,
        claim_id: str,
        context_scope: Sequence[str],
        assumption_ids: Sequence[str],
        operator_id: str | None,
        evidence: Sequence[EvidenceRef],
        parent_digest: str | None,
        transition_capability_digest: str | None,
        lineage_depth: int,
        reason: str,
        _seal: object,
    ) -> "EpistemicRecord":
        if _seal is not _MINT_SEAL:
            raise TypeError("invalid epistemic record mint seal")
        if not claim_id.strip():
            raise ValueError("claim_id must be non-empty")
        scope = _normalize_strings(context_scope, field="context_scope")
        assumptions = _normalize_strings(assumption_ids, field="assumption_ids", allow_empty=True)
        ev = tuple(sorted(evidence, key=lambda x: (x.ref, x.digest)))
        payload = {
            "state": state.value,
            "claim_id": claim_id,
            "context_scope": list(scope),
            "assumption_ids": list(assumptions),
            "operator_id": operator_id,
            "evidence_digests": [e.digest for e in ev],
            "parent_digest": parent_digest,
            "transition_capability_digest": transition_capability_digest,
            "lineage_depth": lineage_depth,
            "reason": reason,
        }
        obj = object.__new__(cls)
        object.__setattr__(obj, "state", state)
        object.__setattr__(obj, "claim_id", claim_id)
        object.__setattr__(obj, "context_scope", scope)
        object.__setattr__(obj, "assumption_ids", assumptions)
        object.__setattr__(obj, "operator_id", operator_id)
        object.__setattr__(obj, "evidence", ev)
        object.__setattr__(obj, "parent_digest", parent_digest)
        object.__setattr__(obj, "transition_capability_digest", transition_capability_digest)
        object.__setattr__(obj, "lineage_depth", int(lineage_depth))
        object.__setattr__(obj, "reason", reason)
        object.__setattr__(obj, "record_digest", _canonical_sha(payload))
        return obj

    @property
    def is_terminal(self) -> bool:
        return self.state in TERMINAL_STATES

    @property
    def positive_rank(self) -> int | None:
        try:
            return POSITIVE_CHAIN.index(self.state)
        except ValueError:
            return None

    @property
    def unconditional_causal_authority(self) -> bool:
        # CWC intentionally has no unconditional-causal-truth state.
        return False

    def as_dict(self) -> dict[str, object]:
        return {
            "state": self.state.value,
            "claim_id": self.claim_id,
            "context_scope": list(self.context_scope),
            "assumption_ids": list(self.assumption_ids),
            "operator_id": self.operator_id,
            "evidence": [e.as_dict() for e in self.evidence],
            "parent_digest": self.parent_digest,
            "transition_capability_digest": self.transition_capability_digest,
            "lineage_depth": self.lineage_depth,
            "reason": self.reason,
            "record_digest": self.record_digest,
            "unconditional_causal_authority": False,
        }


class EpistemicMachine:
    """Fail-closed runtime authority state machine.

    The machine does not infer causal truth. It enforces which evidence class is
    required to *represent* a stronger epistemic state. Historical string verdicts
    remain immutable and can be adapted into this runtime layer without rewriting
    frozen experiment artifacts.
    """

    def observe(
        self,
        *,
        claim_id: str,
        context_scope: Sequence[str],
        evidence: Sequence[EvidenceRef],
        reason: str = "factual observation registered",
    ) -> EpistemicRecord:
        ev = self._require_evidence(
            evidence,
            kinds={EvidenceKind.FACTUAL_OBSERVATION},
            sources={EvidenceSource.FACTUAL_CHANNEL},
            context_scope=context_scope,
        )
        return EpistemicRecord._mint(
            state=EpistemicState.OBSERVED,
            claim_id=claim_id,
            context_scope=context_scope,
            assumption_ids=(),
            operator_id=None,
            evidence=ev,
            parent_digest=None,
            transition_capability_digest=None,
            lineage_depth=0,
            reason=reason,
            _seal=_MINT_SEAL,
        )

    def issue_predictive_capability(
        self,
        record: EpistemicRecord,
        *,
        evidence: Sequence[EvidenceRef],
        context_scope: Sequence[str] | None = None,
        reason: str = "held-out predictive validation",
    ) -> EpistemicCapability:
        self._require_state(record, EpistemicState.OBSERVED)
        scope = self._resolve_scope(record, context_scope)
        ev = self._require_evidence(
            evidence,
            kinds={EvidenceKind.PREDICTIVE_VALIDATION},
            sources={EvidenceSource.HELD_OUT_PREDICTION},
            context_scope=scope,
        )
        return self._mint_capability(
            record,
            CapabilityType.PREDICTIVE_PROMOTION,
            EpistemicState.PREDICTIVE,
            scope,
            ev,
            reason=reason,
        )

    def issue_assumption_capability(
        self,
        record: EpistemicRecord,
        *,
        assumption_ids: Sequence[str],
        evidence: Sequence[EvidenceRef],
        context_scope: Sequence[str] | None = None,
        reason: str = "explicit identifying assumptions bound",
    ) -> EpistemicCapability:
        self._require_state(record, EpistemicState.PREDICTIVE)
        assumptions = _normalize_strings(assumption_ids, field="assumption_ids")
        scope = self._resolve_scope(record, context_scope)
        ev = self._require_evidence(
            evidence,
            kinds={EvidenceKind.IDENTIFYING_ASSUMPTION},
            sources={EvidenceSource.ASSUMPTION_CONTRACT, EvidenceSource.HUMAN_PROVENANCE},
            context_scope=scope,
        )
        return self._mint_capability(
            record,
            CapabilityType.ASSUMPTION_PROMOTION,
            EpistemicState.ASSUMPTION_CONDITIONAL,
            scope,
            ev,
            assumption_ids=assumptions,
            reason=reason,
        )

    def issue_intervention_capability(
        self,
        record: EpistemicRecord,
        *,
        operator_id: str,
        evidence: Sequence[EvidenceRef],
        context_scope: Sequence[str] | None = None,
        reason: str = "direct intervention evidence bound",
    ) -> EpistemicCapability:
        self._require_state(record, EpistemicState.ASSUMPTION_CONDITIONAL)
        if not operator_id.strip():
            raise ValueError("operator_id must be non-empty")
        scope = self._resolve_scope(record, context_scope)
        ev = self._require_evidence(
            evidence,
            kinds={EvidenceKind.DIRECT_INTERVENTION},
            sources=set(_DIRECT_INTERVENTION_SOURCES),
            context_scope=scope,
        )
        return self._mint_capability(
            record,
            CapabilityType.INTERVENTION_PROMOTION,
            EpistemicState.INTERVENTION_SUPPORTED,
            scope,
            ev,
            assumption_ids=record.assumption_ids,
            operator_id=operator_id,
            reason=reason,
        )

    def issue_terminal_capability(
        self,
        record: EpistemicRecord,
        *,
        target_state: EpistemicState,
        evidence: Sequence[EvidenceRef],
        reason: str,
    ) -> EpistemicCapability:
        if record.is_terminal:
            raise IllegalTransition(f"terminal state {record.state.value} cannot transition in-place")
        required: dict[EpistemicState, tuple[set[EvidenceKind], set[EvidenceSource]]] = {
            EpistemicState.UNIDENTIFIED: (
                {EvidenceKind.COUNTERMODEL, EvidenceKind.IDENTIFYING_ASSUMPTION},
                {EvidenceSource.COUNTERMODEL_SEARCH, EvidenceSource.ASSUMPTION_CONTRACT, EvidenceSource.DIAGNOSTIC},
            ),
            EpistemicState.FALSIFIED: (
                {EvidenceKind.FALSIFICATION},
                {EvidenceSource.DIAGNOSTIC, EvidenceSource.DIRECT_SYSTEM_REEXECUTION, EvidenceSource.EXTERNAL_ENV_INTERVENTION},
            ),
            EpistemicState.OOD: (
                {EvidenceKind.OOD_DIAGNOSTIC},
                {EvidenceSource.DIAGNOSTIC},
            ),
            EpistemicState.ABSTAIN: (
                {EvidenceKind.ABSTENTION_REASON},
                {EvidenceSource.DIAGNOSTIC},
            ),
        }
        if target_state not in required:
            raise IllegalTransition(f"{target_state.value} is not a terminal fail-closed target")
        kinds, sources = required[target_state]
        ev = self._require_evidence(evidence, kinds=kinds, sources=sources, context_scope=record.context_scope)
        return self._mint_capability(
            record,
            CapabilityType.TERMINAL_DEGRADE,
            target_state,
            record.context_scope,
            ev,
            assumption_ids=record.assumption_ids,
            operator_id=record.operator_id,
            reason=reason,
        )

    def transition(self, record: EpistemicRecord, capability: EpistemicCapability) -> EpistemicRecord:
        if record.is_terminal:
            raise IllegalTransition(f"terminal state {record.state.value} is absorbing")
        self._validate_binding(record, capability)
        expected = {
            (EpistemicState.OBSERVED, CapabilityType.PREDICTIVE_PROMOTION): EpistemicState.PREDICTIVE,
            (EpistemicState.PREDICTIVE, CapabilityType.ASSUMPTION_PROMOTION): EpistemicState.ASSUMPTION_CONDITIONAL,
            (EpistemicState.ASSUMPTION_CONDITIONAL, CapabilityType.INTERVENTION_PROMOTION): EpistemicState.INTERVENTION_SUPPORTED,
        }
        if capability.capability_type is CapabilityType.TERMINAL_DEGRADE:
            if capability.target_state not in TERMINAL_STATES:
                raise IllegalTransition("terminal capability has non-terminal target")
            target = capability.target_state
        else:
            target = expected.get((record.state, capability.capability_type))
            if target is None or target is not capability.target_state:
                raise IllegalTransition(
                    f"{record.state.value} cannot consume {capability.capability_type.value} -> {capability.target_state.value}"
                )

        evidence = tuple(record.evidence) + tuple(capability.evidence)
        assumption_ids = record.assumption_ids
        operator_id = record.operator_id
        if target is EpistemicState.ASSUMPTION_CONDITIONAL:
            if not capability.assumption_ids:
                raise EvidenceClassError("assumption-conditional state requires explicit assumption ids")
            assumption_ids = capability.assumption_ids
        elif target is EpistemicState.INTERVENTION_SUPPORTED:
            if not capability.operator_id:
                raise EvidenceClassError("intervention-supported state requires an operator id")
            if not capability.assumption_ids:
                raise EvidenceClassError("intervention promotion must preserve the assumption lineage")
            assumption_ids = capability.assumption_ids
            operator_id = capability.operator_id

        return EpistemicRecord._mint(
            state=target,
            claim_id=record.claim_id,
            context_scope=capability.context_scope,
            assumption_ids=assumption_ids,
            operator_id=operator_id,
            evidence=evidence,
            parent_digest=record.record_digest,
            transition_capability_digest=capability.capability_digest,
            lineage_depth=record.lineage_depth + 1,
            reason=capability.reason,
            _seal=_MINT_SEAL,
        )

    def _mint_capability(
        self,
        record: EpistemicRecord,
        capability_type: CapabilityType,
        target_state: EpistemicState,
        context_scope: Sequence[str],
        evidence: Sequence[EvidenceRef],
        *,
        assumption_ids: Sequence[str] = (),
        operator_id: str | None = None,
        reason: str,
    ) -> EpistemicCapability:
        return EpistemicCapability._mint(
            capability_type=capability_type,
            target_state=target_state,
            claim_id=record.claim_id,
            parent_digest=record.record_digest,
            context_scope=context_scope,
            evidence=evidence,
            assumption_ids=assumption_ids,
            operator_id=operator_id,
            reason=reason,
            _seal=_CAPABILITY_SEAL,
        )

    @staticmethod
    def _require_state(record: EpistemicRecord, expected: EpistemicState) -> None:
        if record.state is not expected:
            raise IllegalTransition(f"expected {expected.value}, got {record.state.value}")

    @staticmethod
    def _resolve_scope(record: EpistemicRecord, requested: Sequence[str] | None) -> tuple[str, ...]:
        scope = record.context_scope if requested is None else _normalize_strings(requested, field="context_scope")
        if tuple(scope) != tuple(record.context_scope):
            raise CapabilityBindingError("scope escalation/narrowing requires a new record lineage; exact scope binding enforced")
        return tuple(scope)

    @staticmethod
    def _require_evidence(
        evidence: Sequence[EvidenceRef],
        *,
        kinds: set[EvidenceKind],
        sources: set[EvidenceSource],
        context_scope: Sequence[str],
    ) -> tuple[EvidenceRef, ...]:
        ev = tuple(evidence)
        if not ev:
            raise EvidenceClassError("at least one evidence reference is required")
        scope = _normalize_strings(context_scope, field="context_scope")
        for item in ev:
            if item.kind not in kinds:
                raise EvidenceClassError(f"evidence kind {item.kind.value} cannot license this operation")
            if item.source not in sources:
                raise EvidenceClassError(f"evidence source {item.source.value} cannot license this operation")
            if item.context_scope != scope:
                raise CapabilityBindingError("evidence context scope does not match record scope")
        return tuple(sorted(ev, key=lambda x: (x.ref, x.digest)))

    @staticmethod
    def _validate_binding(record: EpistemicRecord, capability: EpistemicCapability) -> None:
        if capability.claim_id != record.claim_id:
            raise CapabilityBindingError("capability claim id does not match record")
        if capability.parent_digest != record.record_digest:
            raise CapabilityBindingError("capability parent digest is stale or belongs to another record")
        if capability.context_scope != record.context_scope:
            raise CapabilityBindingError("capability scope does not match record scope")


def positive_state_dominates(a: EpistemicState, b: EpistemicState) -> bool:
    """Return whether positive authority state `a` is at least as strong as `b`.

    Terminal dispositions are intentionally incomparable to positive support levels.
    """
    if a not in POSITIVE_CHAIN or b not in POSITIVE_CHAIN:
        raise ValueError("dominance is defined only on the positive authority chain")
    return POSITIVE_CHAIN.index(a) >= POSITIVE_CHAIN.index(b)
