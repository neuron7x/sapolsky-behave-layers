"""Fixture-bounded qualification; rejecting everything is not a passing verifier."""

from __future__ import annotations

import hashlib
import json
from collections.abc import Callable, Sequence
from dataclasses import asdict, dataclass
from typing import Literal

ArtifactQuality = Literal["PASS", "FAIL", "UNKNOWN"]
Action = Literal["SUBMIT", "STOP", "ESCALATE", "UNRESOLVED"]
Category = Literal["CANONICAL_VALID", "VALID_VARIANT", "INVALID", "BOUNDARY", "ATTACK", "CONTRADICTION", "UNKNOWN"]
REQUIRED_CATEGORIES = frozenset(
    {"CANONICAL_VALID", "VALID_VARIANT", "INVALID", "BOUNDARY", "ATTACK", "CONTRADICTION", "UNKNOWN"}
)


def canonical_bytes(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


@dataclass(frozen=True, slots=True)
class VerificationDecision:
    artifact_quality: ArtifactQuality
    action: Action
    selected_action: str | None = None

    def __post_init__(self) -> None:
        if self.artifact_quality not in {"PASS", "FAIL", "UNKNOWN"}:
            raise ValueError("unknown artifact quality")
        if self.action not in {"SUBMIT", "STOP", "ESCALATE", "UNRESOLVED"}:
            raise ValueError("unknown executable action")
        if self.action == "SUBMIT":
            if (
                self.artifact_quality != "PASS"
                or not isinstance(self.selected_action, str)
                or not self.selected_action.strip()
            ):
                raise ValueError("SUBMIT requires a passing artifact and a bound selected action")
        elif self.selected_action is not None:
            raise ValueError("non-SUBMIT decisions cannot carry executable content")


@dataclass(frozen=True, slots=True)
class VerifierFixture:
    fixture_id: str
    category: Category
    payload: bytes
    expected: VerificationDecision


def qualify_verifier(
    verifier: Callable[[bytes], VerificationDecision],
    critic: Callable[[bytes], VerificationDecision],
    fixtures: Sequence[VerifierFixture],
) -> dict[str, object]:
    """Never pass labels, case IDs or categories to either implementation.

    Exceptions, truthy non-decisions and empty/incomplete suites fail, even when
    the affected input was expected to be rejected. This is not a sandbox for
    malicious Python, a proof of semantic completeness, or product authority.
    """
    errors: list[str] = []
    ids = [f.fixture_id for f in fixtures]
    hashes = [digest(f.payload) for f in fixtures]
    categories = {f.category for f in fixtures}
    if not fixtures or any(not name.strip() for name in ids) or len(ids) != len(set(ids)):
        errors.append("EMPTY_OR_DUPLICATE_FIXTURE_IDS")
    if len(hashes) != len(set(hashes)):
        errors.append("DUPLICATE_INPUT_BYTES")
    if categories != REQUIRED_CATEGORIES:
        errors.append("MISSING_OR_UNKNOWN_CATEGORY")
    canonical = [f for f in fixtures if f.category == "CANONICAL_VALID"]
    variants = [f for f in fixtures if f.category == "VALID_VARIANT"]
    if len(canonical) != 1 or len(variants) < 3:
        errors.append("CANONICAL_PLUS_THREE_VARIANTS_REQUIRED")
    positives = [*canonical, *variants]
    if any(f.expected.artifact_quality != "PASS" or f.expected.action != "SUBMIT" for f in positives):
        errors.append("POSITIVE_FIXTURE_NOT_EXECUTABLE")
    if canonical and any(f.expected != canonical[0].expected for f in variants):
        errors.append("VARIANT_EXPECTATION_DIFFERS_FROM_CANONICAL")
    for category in ("INVALID", "ATTACK"):
        if any(
            f.expected.artifact_quality != "FAIL" or f.expected.action != "STOP"
            for f in fixtures
            if f.category == category
        ):
            errors.append(f"{category}_MUST_REJECT_AND_STOP")
    if any(f.expected.action not in {"STOP", "ESCALATE"} for f in fixtures if f.category == "CONTRADICTION"):
        errors.append("CONTRADICTION_MUST_STOP_OR_ESCALATE")
    if any(
        f.expected.artifact_quality != "UNKNOWN" or f.expected.action != "UNRESOLVED"
        for f in fixtures
        if f.category == "UNKNOWN"
    ):
        errors.append("UNKNOWN_MUST_REMAIN_UNRESOLVED")
    if {f.expected.action == "SUBMIT" for f in fixtures if f.category == "BOUNDARY"} != {True, False}:
        errors.append("BOTH_SIDES_OF_BOUNDARY_REQUIRED")

    rows: list[dict[str, object]] = []
    artifact_ok = True
    decision_ok = True
    execution_ok = True
    for fixture in fixtures:
        observed: list[VerificationDecision | None] = []
        failures: list[str] = []
        for label, implementation in (("verifier", verifier), ("critic", critic)):
            try:
                result = implementation(fixture.payload)
                if type(result) is not VerificationDecision:
                    raise TypeError("implementation must return a VerificationDecision, not a truthy value")
                observed.append(result)
            except Exception as exc:
                observed.append(None)
                failures.append(f"{label}:{type(exc).__name__}")
        artifact_match = all(
            r is not None and r.artifact_quality == fixture.expected.artifact_quality for r in observed
        )
        decision_match = all(
            r is not None
            and (r.action, r.selected_action) == (fixture.expected.action, fixture.expected.selected_action)
            for r in observed
        )
        artifact_ok &= artifact_match
        decision_ok &= decision_match
        execution_ok &= not failures
        rows.append(
            {
                "fixture_id": fixture.fixture_id,
                "category": fixture.category,
                "input_sha256": digest(fixture.payload),
                "expected": asdict(fixture.expected),
                "verifier": asdict(observed[0]) if observed[0] is not None else None,
                "critic": asdict(observed[1]) if observed[1] is not None else None,
                "artifact_match": artifact_match,
                "decision_match": decision_match,
                "errors": failures,
            }
        )
    payload: dict[str, object] = {
        "schema": "CWC_DUAL_SIDED_VERIFIER_QUALIFICATION_V1",
        "scope": "FIXTURE_BOUNDED_NOT_PRODUCT_QUALIFICATION",
        "suite_sha256": digest(
            canonical_bytes(
                [
                    {
                        "id": f.fixture_id,
                        "category": f.category,
                        "input_sha256": digest(f.payload),
                        "expected": asdict(f.expected),
                    }
                    for f in fixtures
                ]
            )
        ),
        "coverage": {
            "complete": not errors,
            "errors": errors,
            "fixture_count": len(fixtures),
            "valid_variants": len(variants),
        },
        "artifact_quality": "PASS" if artifact_ok and fixtures else "FAIL",
        "decision_correctness": "PASS" if decision_ok and fixtures else "FAIL",
        "execution_integrity": "PASS" if execution_ok else "FAIL",
        "verdict": "PASS" if artifact_ok and decision_ok and execution_ok and not errors else "FAIL",
        "product_qualified": False,
        "rows": rows,
    }
    return {**payload, "evidence_sha256": digest(canonical_bytes(payload))}
