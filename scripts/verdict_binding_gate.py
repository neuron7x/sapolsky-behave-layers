"""Bind every registered claim status to the sealed verdict it is supposed to rest on.

WHY THIS GATE EXISTS
--------------------
An independent audit (2026-08-08) flipped three registry statuses by hand —
``CWC-L3-rcfr`` and ``CWC-L2c-e2e-straightthrough`` from ``NOT_SUPPORTED`` and
``CWC-L7-pareto`` from ``NOT_TESTED``, all to ``SUPPORTED`` — and ``make -f Makefile.cwc
pr-fast`` still reported ALL GATES PASSED. The reason was structural, not accidental:

  * ``doc_status_gate.py`` validates the registry's *shape* (schema, orphans, artifact
    paths, ancestor commit) and never reads a verdict;
  * ``validate_evidence.py`` validates that bundle JSON is finite and complete and never
    compares a number to the claim it supports;
  * ``coherence_audit.audit_ladder`` reproduces the master certificate on its OWN
    hard-coded six-row ``_LADDER`` whose ids ("wp3-rcfr (ties DISeL-with-role)") do not
    exist in ``claim_registry.json`` at all.

So the guard read past the thing it guarded. This module closes that: a status in the
registry is now a *derived* quantity, checked against a value that lives inside a
checksummed evidence bundle.

THE CHAIN (each link is independently falsifiable)
--------------------------------------------------
  1. every claim MUST carry ``verdict_binding`` (fail-closed: a new claim without one
     fails the gate); ``verdict_binding == null`` is legal ONLY for ``NOT_TESTED``;
  2. ``binding.file`` exists in the working tree AND in the tree of the registry's own
     ``git_commit`` (a status may not rest on evidence added after it was stamped);
  3. the value at ``binding.pointer`` inside that file equals ``binding.expected``
     (``pointer == null`` means: the file must contain ``expected`` verbatim);
  4. ``expected`` is present in ``VERDICT_POLARITY`` below — a table that lives in THIS
     source file, not in the registry, so editing the registry cannot redefine what a
     verdict means. An unknown verdict string fails rather than defaults;
  5. the polarity implied by the verdict equals the polarity implied by ``status``;
  6. the file's SHA-256 matches its entry in the bundle's ``SHA256SUMS`` where one
     exists, so the numbers behind the verdict cannot be edited without detection —
     this is what pulls the ``verify-evidence`` checksum guarantee into the every-run
     ``verify`` target instead of leaving it to ``verify-full``;
  7. ``SUPPORTED_NARROWED`` requires a non-empty ``limitations`` list — "narrowed" must
     name what it was narrowed to;
  8. every ``_LADDER`` row in ``coherence_audit`` resolves to a real ``claim_id`` and
     declares the registry status it expects; a divergence fails. This is what ties
     Theorem C to the 43-claim ledger instead of to its own copy.

HONEST LIMIT. This gate detects *drift and inconsistency*. It cannot detect a
coordinated forgery in which the verdict file, its SHA256SUMS line and the registry are
all rewritten together — that is a git-history and review problem, not a checksum
problem, and it is stated here rather than glossed.

Exit code 0 = PASS, 1 = FAIL. Self-test (a gate that cannot fail is not a gate):
    PYTHONPATH=. .venv/bin/python scripts/verdict_binding_gate.py --self-test
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
REGISTRY = ROOT / "claim_registry.json"

POSITIVE = "POSITIVE"
NEGATIVE = "NEGATIVE"
UNTESTED = "UNTESTED"

STATUS_POLARITY = {
    "SUPPORTED": POSITIVE,
    "SUPPORTED_NARROWED": POSITIVE,
    "NOT_SUPPORTED": NEGATIVE,
    "NOT_IDENTIFIABLE": NEGATIVE,
    "INSTRUMENT_INVALID": NEGATIVE,
    "NOT_TESTED": UNTESTED,
}

# What each sealed verdict string MEANS for the claim that rests on it. Kept in code,
# deliberately: the registry must not be able to redefine its own semantics. Note
# `NEGATIVE_IS_MECHANISM_SPECIFIC` -> POSITIVE: the claim is that the negative is robust,
# so a naive substring classifier on "NEGATIVE" would get it backwards.
VERDICT_POLARITY: dict[Any, str] = {
    "## Baseline integrity (Act A2) — PASS": POSITIVE,
    "ROUTING_CAUSALITY_SUPPORTED_UNDER_COUNTERFACTUAL_VALUE_DISTILLATION_"
    "ON_A_SYNTHETIC_MECHANISM_SEPARABLE_BENCHMARK": POSITIVE,
    "ROUTING_END_TO_END_SUPPORTED_UNDER_BINDING_BUDGET": POSITIVE,
    "ROUTE_DECISION_IS_THE_COMPUTATION": POSITIVE,
    "ADAPTIVE_COMPUTE_JENSEN_GAP_CONFIRMED": POSITIVE,
    "ROUTING_END_TO_END_NOT_SUPPORTED": NEGATIVE,
    "SUPPORTED_END_TO_END_INTERNAL": POSITIVE,
    "RCFR_NOT_SUPPORTED": NEGATIVE,
    "L4A_SUPPORTED": POSITIVE,
    "L4B_BOUNDARY_MAPPED": POSITIVE,
    "L4C_SCALING_VIOLATED": NEGATIVE,
    "L4D_BUDGET_SCALING_VIOLATED": NEGATIVE,
    "L4E_MECHANISM_INCOMPLETE": NEGATIVE,
    "L4F_ARM_SCALING_MAPPED": POSITIVE,
    "L4G_ROBUST": POSITIVE,
    "L4H_GENERALIZES": POSITIVE,
    "L4I_BRIDGE_CONFIRMED": POSITIVE,
    "L4J_CONSISTENT": POSITIVE,
    "L4K_LINE_SURVIVES": POSITIVE,
    "NOT_SUPPORTED": NEGATIVE,
    "AC1_IDENTIFIABLE": POSITIVE,
    "AC2_CONTROLLER_RECOVERS": POSITIVE,
    "AC3_BOUNDARY_MAPPED": POSITIVE,
    "AC4_RATE_BRIDGE_CONFIRMED": POSITIVE,
    "WP6_REAL_LM_NOT_IDENTIFIABLE": NEGATIVE,
    "WP7_GAP_CLOSED_POSITIVES_ROBUST": POSITIVE,
    "WP8_FWER_CONTROLLED": POSITIVE,
    "PINSKER_DICHOTOMY_CERTIFIED": POSITIVE,
    "COHERENCE_DECIRCULARIZED_0_CONTRADICTIONS": POSITIVE,
    "INDEPENDENCE_ROBUST": POSITIVE,
    "EFFECT_SIZES_CI_POSITIVE": POSITIVE,
    "PREREG_INTEGRITY_CLEAN": POSITIVE,
    "WP14_REAL_LM_NOT_IDENTIFIABLE_ROBUST": NEGATIVE,
    "SYNTHETIC_COMPUTE_PARETO_DOMINATES": POSITIVE,
    "PARETO_SURVIVES_PHYSICAL_ROUTE_COST": POSITIVE,
    "WP18_KILL_RULE_TRIGGERED_NO_REAL_IDENTIFIABILITY": NEGATIVE,
    "NEGATIVE_IS_MECHANISM_SPECIFIC": POSITIVE,
    "SPEC_PREDICTS_CERTIFICATE": POSITIVE,
    "CAUSAL_DEBT_CONTROL_NOT_QUALIFIED": NEGATIVE,
    "CAUSAL_DEBT_V2_CONTROL_QUALIFIED": POSITIVE,
    "CAUSAL_DEBT_V2_CONTROL_NOT_QUALIFIED": NEGATIVE,
    True: POSITIVE,
    False: NEGATIVE,
}


def _resolve(doc: Any, pointer: str) -> Any:
    """Walk a dotted pointer; integer segments index into lists."""
    cur = doc
    for seg in pointer.split("."):
        if isinstance(cur, list):
            cur = cur[int(seg)]
        elif isinstance(cur, dict):
            if seg not in cur:
                raise KeyError(seg)
            cur = cur[seg]
        else:
            raise KeyError(seg)
    return cur


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(path.read_bytes())
    return h.hexdigest()


def _checksum_error(path: Path) -> str | None:
    """Compare ``path`` against whichever SHA256SUMS covers it; None == OK/absent."""
    for parent in list(path.parents)[:4]:
        for name in ("SHA256SUMS", "WP1_SHA256SUMS"):
            sums = parent / name
            if not sums.exists():
                continue
            want = None
            for line in sums.read_text(errors="replace").splitlines():
                parts = line.split(None, 1)
                if len(parts) != 2:
                    continue
                digest, rel = parts[0], parts[1].strip().lstrip("*")
                if (parent / rel).resolve() == path.resolve():
                    want = digest
                    break
            if want is None:
                continue
            got = _sha256(path)
            if got != want:
                return f"checksum mismatch vs {sums.relative_to(ROOT)}: {got[:12]} != {want[:12]}"
            return None
    return None


def _tracked_at(commit: str, rel: str) -> bool:
    r = subprocess.run(["git", "-C", str(ROOT), "cat-file", "-e", f"{commit}:{rel}"],
                       capture_output=True)
    return r.returncode == 0


def audit(registry: dict[str, Any], *, check_commit: bool = True) -> list[str]:
    """Return the list of violations; empty == coherent."""
    errors: list[str] = []
    commit = registry.get("git_commit", "")
    for claim in registry["claims"]:
        cid = claim["claim_id"]
        status = claim["status"]
        if "verdict_binding" not in claim:
            errors.append(f"{cid}: no verdict_binding (fail-closed: every claim must bind)")
            continue
        binding = claim["verdict_binding"]
        want_polarity = STATUS_POLARITY.get(status)
        if want_polarity is None:
            errors.append(f"{cid}: unknown status {status!r}")
            continue
        if status == "SUPPORTED_NARROWED" and not claim.get("limitations"):
            errors.append(f"{cid}: SUPPORTED_NARROWED with empty limitations")
        if binding is None:
            if want_polarity != UNTESTED:
                errors.append(f"{cid}: status {status} but no verdict bound")
            continue
        if want_polarity == UNTESTED:
            errors.append(f"{cid}: NOT_TESTED must not bind a verdict")
            continue

        rel = binding["file"]
        path = ROOT / rel
        if not path.is_file():
            errors.append(f"{cid}: verdict file missing: {rel}")
            continue
        if check_commit and commit and not _tracked_at(commit, rel):
            errors.append(f"{cid}: {rel} absent from registry commit {commit[:8]}")

        expected = binding["expected"]
        pointer = binding["pointer"]
        if pointer is None:
            if expected not in path.read_text(errors="replace"):
                errors.append(f"{cid}: {rel} does not contain {expected!r}")
                continue
            actual: Any = expected
        else:
            try:
                actual = _resolve(json.loads(path.read_text()), pointer)
            except (KeyError, IndexError, ValueError) as exc:
                errors.append(f"{cid}: cannot resolve {pointer!r} in {rel}: {exc}")
                continue
            if actual != expected:
                errors.append(f"{cid}: {rel}:{pointer} is {actual!r}, registry expects {expected!r}")
                continue

        key = actual if isinstance(actual, bool) else str(actual)
        if key not in VERDICT_POLARITY:
            errors.append(f"{cid}: verdict {key!r} has no declared polarity in this gate")
            continue
        got_polarity = VERDICT_POLARITY[key]
        if got_polarity != want_polarity:
            errors.append(
                f"{cid}: status {status} implies {want_polarity} but sealed verdict "
                f"{key!r} is {got_polarity}"
            )
        err = _checksum_error(path)
        if err:
            errors.append(f"{cid}: {rel} {err}")
    return errors


def audit_ladder_binding(registry: dict[str, Any]) -> list[str]:
    """Every coherence-ladder row must name a real claim and its expected status."""
    from experiments.common.coherence_audit import _LADDER

    by_id = {c["claim_id"]: c for c in registry["claims"]}
    errors: list[str] = []
    for entry in _LADDER:
        cid = entry.get("registry_claim_id")
        if not cid:
            errors.append(f"ladder row {entry['claim_id']!r}: no registry_claim_id")
            continue
        claim = by_id.get(str(cid))
        if claim is None:
            errors.append(f"ladder row {entry['claim_id']!r}: unknown claim {cid!r}")
            continue
        want = entry.get("registry_status")
        if claim["status"] != want:
            errors.append(
                f"ladder row {entry['claim_id']!r}: expects {cid} == {want}, "
                f"registry says {claim['status']}"
            )
    return errors


def self_test() -> list[str]:
    """A gate that cannot fail is not a gate: inject each defect, require detection."""
    registry = json.loads(REGISTRY.read_text())
    failures: list[str] = []

    def probe(name: str, mutate: Callable[[dict[str, Any]], None]) -> None:
        forged = json.loads(json.dumps(registry))
        mutate(forged)
        if not audit(forged, check_commit=False):
            failures.append(f"self-test {name}: gate did not detect the injected defect")

    def flip_negative(reg: dict[str, Any]) -> None:
        for c in reg["claims"]:
            if c["status"] == "NOT_SUPPORTED":
                c["status"] = "SUPPORTED"
                return
        raise AssertionError("no NOT_SUPPORTED claim to flip")

    def promote_untested(reg: dict[str, Any]) -> None:
        for c in reg["claims"]:
            if c["status"] == "NOT_TESTED":
                c["status"] = "SUPPORTED"
                return
        raise AssertionError("no NOT_TESTED claim to promote")

    def drop_binding(reg: dict[str, Any]) -> None:
        reg["claims"][0].pop("verdict_binding", None)

    def retarget_expected(reg: dict[str, Any]) -> None:
        for c in reg["claims"]:
            if c.get("verdict_binding") and c["verdict_binding"]["pointer"]:
                c["verdict_binding"]["expected"] = "TOTALLY_DIFFERENT_VERDICT"
                return
        raise AssertionError("no pointer binding to retarget")

    probe("flip NOT_SUPPORTED -> SUPPORTED", flip_negative)
    probe("promote NOT_TESTED -> SUPPORTED", promote_untested)
    probe("remove verdict_binding", drop_binding)
    probe("retarget expected verdict", retarget_expected)

    # Positive control: the unmutated registry must pass, or the probes prove nothing.
    if audit(registry, check_commit=False):
        failures.append("self-test positive control: the real registry does not pass")
    return failures


def main(argv: list[str]) -> int:
    registry = json.loads(REGISTRY.read_text())
    if "--self-test" in argv:
        failures = self_test()
        for f in failures:
            print(f"SELF-TEST FAIL: {f}")
        if failures:
            return 1
        print("VERDICT-BINDING SELF-TEST PASS: 4 injected defects detected, control clean")
        return 0

    errors = audit(registry) + audit_ladder_binding(registry)
    for e in errors:
        print(f"VERDICT-BINDING FAIL: {e}")
    if errors:
        return 1
    bound = sum(1 for c in registry["claims"] if c.get("verdict_binding"))
    untested = sum(1 for c in registry["claims"] if c["status"] == "NOT_TESTED")
    print(
        f"VERDICT-BINDING PASS: {bound} claims bound to sealed verdicts, "
        f"{untested} NOT_TESTED unbound by design, ladder rows resolve to the registry."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
