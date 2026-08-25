from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.ccf_quantizer import RawCounterfactualOption, quantize_counterfactual_option
from cwc.governance.ccf_spec_authority import (
    load_and_verify_ccf_spec,
    verify_ccf_spec_authority_document,
)
from cwc.governance.confirmatory_execution_authority import verify_confirmatory_execution_authority_document
from cwc.governance.confirmatory_root_authority import verify_confirmatory_root_authority_document
from cwc.governance.counterfactual_frontier import PolicyOracleAudit, audit_policy_against_counterfactual_oracle
from cwc.governance.counterfactual_oracle_spec import parse_counterfactual_oracle_spec
from cwc.governance.distributed_eval_control import DistributedEvalSpec, WorkUnitId
from cwc.governance.execution_evidence_bundle import VerifiedExecutionBundle, verify_execution_bundle
from cwc.governance.harness_freeze import DGC_ROLE, verify_harness_freeze_document
from cwc.governance.materialization_transaction import canonical_json_bytes, file_manifest, sha256_bytes, sha256_file
from cwc.governance.physical_execution_cost_bundle import (
    VerifiedPhysicalExecutionCostBundle,
    verify_physical_execution_cost_bundle,
)

BUNDLE_SCHEMA = "DGC_CCF_ORACLE_EVIDENCE_BUNDLE_V1"
AUTHORITY_SCHEMA = "DGC_CCF_ORACLE_AUDIT_AUTHORITY_V1"


class CCFOracleAuditError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise CCFOracleAuditError(f"{name} must be lowercase SHA-256")
    return text


def _finite(name: str, value: object, *, lower: float | None = None, upper: float | None = None) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise CCFOracleAuditError(f"{name} must be numeric") from exc
    if not math.isfinite(result):
        raise CCFOracleAuditError(f"{name} must be finite")
    if lower is not None and result < lower:
        raise CCFOracleAuditError(f"{name} below lower bound")
    if upper is not None and result > upper:
        raise CCFOracleAuditError(f"{name} above upper bound")
    return result


def _json(path: Path, *, schema: str) -> dict[str, object]:
    if path.is_symlink() or not path.is_file():
        raise CCFOracleAuditError("CCF JSON subject must be a regular file")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise CCFOracleAuditError("invalid CCF JSON subject") from exc
    if not isinstance(doc, dict) or doc.get("schema") != schema:
        raise CCFOracleAuditError(f"unexpected CCF schema; expected {schema}")
    return doc


def _bundle_file(root: Path, value: object) -> tuple[Path, str]:
    rel = Path(str(value))
    if not str(value) or rel.is_absolute() or ".." in rel.parts:
        raise CCFOracleAuditError("CCF evidence path must be relative and non-traversing")
    candidate = root / rel
    if candidate.is_symlink():
        raise CCFOracleAuditError("CCF evidence symlink rejected")
    path = candidate.resolve()
    try:
        path.relative_to(root.resolve())
    except ValueError as exc:
        raise CCFOracleAuditError("CCF evidence path escapes bundle") from exc
    if not path.is_file() or path.stat().st_size <= 0:
        raise CCFOracleAuditError("CCF evidence path must be a non-empty regular file")
    return path, rel.as_posix()


def _policy_roles(harness: Mapping[str, object]) -> dict[str, str]:
    rows = harness.get("policy_role_bindings")
    if not isinstance(rows, list) or not all(isinstance(row, Mapping) for row in rows):
        raise CCFOracleAuditError("harness policy role bindings missing")
    result = {str(row.get("role")): str(row.get("policy_id")) for row in rows}
    if DGC_ROLE not in result or not result[DGC_ROLE]:
        raise CCFOracleAuditError("DGC policy role missing")
    return result


def _load_frozen_spec(
    repository_root: Path,
    ccf_authority: Mapping[str, object],
):
    root = Path(repository_root).resolve()
    spec_path = root / str(ccf_authority.get("ccf_spec_path", ""))
    quantizer_path = root / str(ccf_authority.get("quantizer_source_path", ""))
    spec_doc, spec_sha, spec_digest = load_and_verify_ccf_spec(spec_path)
    if spec_sha != ccf_authority.get("ccf_spec_sha256") or spec_digest != ccf_authority.get("ccf_spec_digest"):
        raise CCFOracleAuditError("CCF spec bytes differ from preregistered authority")
    if sha256_file(quantizer_path) != ccf_authority.get("quantizer_source_sha256"):
        raise CCFOracleAuditError("CCF quantizer bytes differ from preregistered authority")
    try:
        return parse_counterfactual_oracle_spec(spec_doc)
    except ValueError as exc:
        raise CCFOracleAuditError("CCF spec cannot be reconstructed") from exc


def _execution_index(bundle: VerifiedExecutionBundle) -> dict[WorkUnitId, object]:
    return {row.unit: row for row in bundle.results}


@dataclass(frozen=True, slots=True)
class ReplicateHeadroomAudit:
    replicate: int
    value_regret_units: int
    avoidable_cost_units: int
    policy_cost_units: int
    policy_value_units: int
    oracle_cost_units: int
    oracle_value_units: int
    certificate_digest: str


@dataclass(frozen=True, slots=True)
class CCFOracleAuditAuthority:
    family_id: str
    ccf_spec_authority_digest: str
    ccf_spec_digest: str
    execution_authority_digest: str
    execution_population_digest: str
    execution_bundle_digest: str
    physical_cost_bundle_digest: str
    physical_cost_population_digest: str
    harness_freeze_digest: str
    ccf_evidence_bundle_digest: str
    ccf_evidence_population_digest: str
    dgc_policy_id: str
    confirmatory_task_manifest_digest: str
    replicate_audits: tuple[ReplicateHeadroomAudit, ...]
    total_value_regret_units: int
    total_avoidable_cost_units: int
    max_value_regret_units: int
    max_avoidable_cost_units: int
    headroom_audit_complete: bool
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": AUTHORITY_SCHEMA,
            "family_id": self.family_id,
            "ccf_spec_authority_digest": self.ccf_spec_authority_digest,
            "ccf_spec_digest": self.ccf_spec_digest,
            "execution_authority_digest": self.execution_authority_digest,
            "execution_population_digest": self.execution_population_digest,
            "execution_bundle_digest": self.execution_bundle_digest,
            "physical_cost_bundle_digest": self.physical_cost_bundle_digest,
            "physical_cost_population_digest": self.physical_cost_population_digest,
            "harness_freeze_digest": self.harness_freeze_digest,
            "ccf_evidence_bundle_digest": self.ccf_evidence_bundle_digest,
            "ccf_evidence_population_digest": self.ccf_evidence_population_digest,
            "dgc_policy_id": self.dgc_policy_id,
            "confirmatory_task_manifest_digest": self.confirmatory_task_manifest_digest,
            "replicate_audits": [asdict(row) for row in self.replicate_audits],
            "total_value_regret_units": self.total_value_regret_units,
            "total_avoidable_cost_units": self.total_avoidable_cost_units,
            "max_value_regret_units": self.max_value_regret_units,
            "max_avoidable_cost_units": self.max_avoidable_cost_units,
            "headroom_audit_complete": self.headroom_audit_complete,
            "authority_digest": self.authority_digest,
            "product_promotion_authorized": False,
        }


def build_ccf_oracle_audit_authority(
    *,
    repository_root: Path,
    ccf_spec_authority_path: Path,
    ccf_evidence_bundle_root: Path,
    confirmatory_execution_authority_path: Path,
    execution_bundle_root: Path,
    physical_cost_bundle_root: Path,
    confirmatory_root_authority_path: Path,
    harness_freeze_path: Path,
) -> CCFOracleAuditAuthority:
    repository_root = Path(repository_root).resolve()
    ccf_authority = verify_ccf_spec_authority_document(Path(ccf_spec_authority_path))
    spec = _load_frozen_spec(repository_root, ccf_authority)
    execution_authority = verify_confirmatory_execution_authority_document(
        Path(confirmatory_execution_authority_path)
    )
    root_authority = verify_confirmatory_root_authority_document(Path(confirmatory_root_authority_path))
    harness = verify_harness_freeze_document(Path(harness_freeze_path))
    execution_bundle = verify_execution_bundle(
        Path(execution_bundle_root),
        confirmatory_root_authority_path=Path(confirmatory_root_authority_path),
    )
    physical_bundle: VerifiedPhysicalExecutionCostBundle = verify_physical_execution_cost_bundle(
        Path(physical_cost_bundle_root),
        confirmatory_execution_authority_path=Path(confirmatory_execution_authority_path),
        execution_bundle_root=Path(execution_bundle_root),
        confirmatory_root_authority_path=Path(confirmatory_root_authority_path),
    )
    if ccf_authority.get("family_id") != execution_authority.get("family_id") or harness.get("family_id") != execution_authority.get("family_id"):
        raise CCFOracleAuditError("CCF family lineage mismatch")
    if harness.get("ccf_spec_authority_digest") != ccf_authority.get("authority_digest"):
        raise CCFOracleAuditError("harness is bound to a different CCF preregistration")
    if harness.get("ccf_spec_digest") != ccf_authority.get("ccf_spec_digest"):
        raise CCFOracleAuditError("harness CCF spec digest mismatch")
    if execution_bundle.bundle_digest != execution_authority.get("execution_bundle_digest"):
        raise CCFOracleAuditError("CCF execution subject differs from EXECUTED authority")
    if physical_bundle.execution_population_digest != execution_authority.get("execution_population_digest"):
        raise CCFOracleAuditError("CCF physical costs belong to a different execution population")

    spec_doc = root_authority.get("distributed_spec")
    if not isinstance(spec_doc, Mapping):
        raise CCFOracleAuditError("distributed spec missing")
    try:
        distributed = DistributedEvalSpec(**dict(spec_doc))
    except (TypeError, ValueError) as exc:
        raise CCFOracleAuditError("distributed spec cannot be reconstructed") from exc
    if distributed.digest != root_authority.get("distributed_spec_digest"):
        raise CCFOracleAuditError("distributed spec digest mismatch")
    roles = _policy_roles(harness)
    dgc_policy = roles[DGC_ROLE]
    dgc_units = {
        unit.stable_id: unit for unit in distributed.units() if unit.policy_id == dgc_policy
    }
    if not dgc_units:
        raise CCFOracleAuditError("frozen distributed population contains no DGC work units")
    execution_index = _execution_index(execution_bundle)
    physical_index = physical_bundle.cost_by_unit()

    supplied_root = Path(ccf_evidence_bundle_root)
    if supplied_root.is_symlink() or not supplied_root.is_dir():
        raise CCFOracleAuditError("CCF evidence bundle root must be a real directory")
    bundle_root = supplied_root.resolve()
    manifest = _json(bundle_root / "CCF_EVIDENCE_BUNDLE.json", schema=BUNDLE_SCHEMA)
    if manifest.get("ccf_spec_authority_digest") != ccf_authority.get("authority_digest"):
        raise CCFOracleAuditError("CCF evidence bundle preregistration mismatch")
    if manifest.get("execution_authority_digest") != execution_authority.get("authority_digest"):
        raise CCFOracleAuditError("CCF evidence bundle execution authority mismatch")
    if manifest.get("execution_population_digest") != execution_authority.get("execution_population_digest"):
        raise CCFOracleAuditError("CCF evidence bundle execution population mismatch")
    if manifest.get("physical_cost_population_digest") != physical_bundle.physical_cost_population_digest:
        raise CCFOracleAuditError("CCF evidence bundle physical-cost population mismatch")
    if manifest.get("product_promotion_authorized") is not False:
        raise CCFOracleAuditError("CCF evidence bundle cannot authorize product promotion")
    payload_rows = file_manifest(bundle_root, excluded_names=frozenset({"CCF_EVIDENCE_BUNDLE.json"}))
    payload_digest = sha256_bytes(canonical_json_bytes(payload_rows))
    if manifest.get("payload_manifest_sha256") != payload_digest:
        raise CCFOracleAuditError("CCF evidence payload manifest mismatch")

    rows = manifest.get("rows")
    if not isinstance(rows, list) or len(rows) != len(dgc_units):
        raise CCFOracleAuditError("CCF evidence requires exactly one row per DGC work unit")
    seen: set[str] = set()
    options_by_rep_task: dict[tuple[int, str], tuple] = {}
    selections_by_rep: dict[int, dict[str, str]] = {}
    evidence_population_rows = []
    for row in rows:
        if not isinstance(row, Mapping):
            raise CCFOracleAuditError("invalid CCF work-unit row")
        unit_id = str(row.get("unit_id", ""))
        if not unit_id or unit_id in seen or unit_id not in dgc_units:
            raise CCFOracleAuditError("CCF work-unit population contains duplicate/unknown unit")
        seen.add(unit_id)
        unit = dgc_units[unit_id]
        execution_row = execution_index.get(unit)
        if execution_row is None:
            raise CCFOracleAuditError("CCF work unit missing from executed result population")
        selected = str(row.get("selected_option_id", "")).strip()
        result_selected = str(execution_row.result_payload.get("selected_option_id", "")).strip()
        if not selected or selected != result_selected:
            raise CCFOracleAuditError("CCF selected option differs from executed DGC result")
        result_latency = _finite("executed latency_ms", execution_row.result_payload.get("latency_ms"), lower=0.0)

        raw_options = row.get("options")
        if not isinstance(raw_options, list) or not raw_options:
            raise CCFOracleAuditError("CCF work-unit row requires non-empty option population")
        option_ids: set[str] = set()
        quantized = []
        option_evidence_rows = []
        selected_raw = None
        for option in raw_options:
            if not isinstance(option, Mapping):
                raise CCFOracleAuditError("invalid CCF option row")
            option_id = str(option.get("option_id", "")).strip()
            if not option_id or option_id in option_ids:
                raise CCFOracleAuditError("CCF option ids must be non-empty and unique per work unit")
            option_ids.add(option_id)
            cost = _finite("CCF option cost_usd", option.get("cost_usd"), lower=0.0)
            quality = _finite("CCF option quality", option.get("quality"), lower=0.0, upper=1.0)
            latency = _finite("CCF option latency_ms", option.get("latency_ms"), lower=0.0)
            regret = _finite("CCF option catastrophic_regret", option.get("catastrophic_regret"), lower=0.0, upper=1.0)
            evidence_path, evidence_rel = _bundle_file(bundle_root, option.get("evidence_path"))
            evidence_sha = sha256_file(evidence_path)
            if option.get("evidence_sha256") != evidence_sha:
                raise CCFOracleAuditError("CCF option evidence digest mismatch")
            raw = RawCounterfactualOption(
                task_id=unit.task_id,
                option_id=option_id,
                cost_usd=cost,
                quality=quality,
                latency_ms=latency,
                catastrophic_regret=regret,
            )
            quantized.append(quantize_counterfactual_option(raw, spec=spec))
            option_evidence_rows.append((option_id, cost, quality, latency, regret, evidence_rel, evidence_sha))
            if option_id == selected:
                selected_raw = raw
        if selected_raw is None:
            raise CCFOracleAuditError("executed DGC option absent from counterfactual option population")
        if not math.isclose(selected_raw.cost_usd, physical_index[unit], rel_tol=0.0, abs_tol=1e-12):
            raise CCFOracleAuditError("selected CCF option cost differs from physical execution cost")
        if not math.isclose(selected_raw.quality, execution_row.quality, rel_tol=0.0, abs_tol=1e-12):
            raise CCFOracleAuditError("selected CCF option quality differs from executed result")
        if not math.isclose(selected_raw.catastrophic_regret, execution_row.catastrophic_regret, rel_tol=0.0, abs_tol=1e-12):
            raise CCFOracleAuditError("selected CCF option regret differs from executed result")
        if not math.isclose(selected_raw.latency_ms, result_latency, rel_tol=0.0, abs_tol=1e-9):
            raise CCFOracleAuditError("selected CCF option latency differs from executed result")
        options_by_rep_task[(unit.replicate, unit.task_id)] = tuple(quantized)
        selections_by_rep.setdefault(unit.replicate, {})[unit.task_id] = selected
        evidence_population_rows.append((unit_id, selected, sorted(option_evidence_rows)))
    if seen != set(dgc_units):
        raise CCFOracleAuditError("CCF evidence population does not equal exact DGC execution population")

    task_count = len(distributed.task_ids)
    audits: list[ReplicateHeadroomAudit] = []
    for replicate in range(distributed.replicates):
        options = []
        for task in distributed.task_ids:
            try:
                options.extend(options_by_rep_task[(replicate, task)])
            except KeyError as exc:
                raise CCFOracleAuditError("CCF option population missing task/replicate cell") from exc
        selections = selections_by_rep.get(replicate, {})
        if set(selections) != set(distributed.task_ids):
            raise CCFOracleAuditError("CCF DGC selection population incomplete for replicate")
        try:
            audit: PolicyOracleAudit = audit_policy_against_counterfactual_oracle(
                options,
                policy_selections=selections,
                max_cost_units=spec.max_cost_units_per_task * task_count,
                max_latency_units=spec.max_latency_units_per_task * task_count,
                max_risk_units=spec.max_risk_units_per_task * task_count,
            )
        except (TypeError, ValueError, RuntimeError) as exc:
            raise CCFOracleAuditError("counterfactual oracle audit failed") from exc
        audits.append(ReplicateHeadroomAudit(
            replicate=replicate,
            value_regret_units=audit.value_regret_units,
            avoidable_cost_units=audit.avoidable_cost_units,
            policy_cost_units=audit.policy_cost_units,
            policy_value_units=audit.policy_value_units,
            oracle_cost_units=audit.oracle_cost_units,
            oracle_value_units=audit.oracle_value_units,
            certificate_digest=audit.certificate_digest,
        ))

    evidence_population_rows.sort()
    evidence_population_digest = sha256_bytes(canonical_json_bytes(evidence_population_rows))
    if manifest.get("ccf_evidence_population_digest") != evidence_population_digest:
        raise CCFOracleAuditError("CCF evidence population digest mismatch")
    manifest_payload = {
        "family_id": str(execution_authority["family_id"]),
        "ccf_spec_authority_digest": str(ccf_authority["authority_digest"]),
        "execution_authority_digest": str(execution_authority["authority_digest"]),
        "execution_population_digest": str(execution_authority["execution_population_digest"]),
        "physical_cost_population_digest": physical_bundle.physical_cost_population_digest,
        "payload_manifest_sha256": payload_digest,
        "rows": rows,
        "ccf_evidence_population_digest": evidence_population_digest,
        "product_promotion_authorized": False,
    }
    ccf_bundle_digest = sha256_bytes(canonical_json_bytes(manifest_payload))
    if manifest.get("bundle_digest") != ccf_bundle_digest:
        raise CCFOracleAuditError("CCF evidence bundle digest mismatch")

    audits_tuple = tuple(audits)
    total_regret = sum(row.value_regret_units for row in audits_tuple)
    total_avoidable = sum(row.avoidable_cost_units for row in audits_tuple)
    max_regret = max(row.value_regret_units for row in audits_tuple)
    max_avoidable = max(row.avoidable_cost_units for row in audits_tuple)
    payload = {
        "family_id": str(execution_authority["family_id"]),
        "ccf_spec_authority_digest": str(ccf_authority["authority_digest"]),
        "ccf_spec_digest": str(ccf_authority["ccf_spec_digest"]),
        "execution_authority_digest": str(execution_authority["authority_digest"]),
        "execution_population_digest": str(execution_authority["execution_population_digest"]),
        "execution_bundle_digest": execution_bundle.bundle_digest,
        "physical_cost_bundle_digest": physical_bundle.bundle_digest,
        "physical_cost_population_digest": physical_bundle.physical_cost_population_digest,
        "harness_freeze_digest": str(harness["harness_freeze_digest"]),
        "ccf_evidence_bundle_digest": ccf_bundle_digest,
        "ccf_evidence_population_digest": evidence_population_digest,
        "dgc_policy_id": dgc_policy,
        "confirmatory_task_manifest_digest": str(harness["confirmatory_task_manifest_digest"]),
        "replicate_audits": [asdict(row) for row in audits_tuple],
        "total_value_regret_units": total_regret,
        "total_avoidable_cost_units": total_avoidable,
        "max_value_regret_units": max_regret,
        "max_avoidable_cost_units": max_avoidable,
        "headroom_audit_complete": True,
    }
    return CCFOracleAuditAuthority(
        family_id=payload["family_id"],
        ccf_spec_authority_digest=payload["ccf_spec_authority_digest"],
        ccf_spec_digest=payload["ccf_spec_digest"],
        execution_authority_digest=payload["execution_authority_digest"],
        execution_population_digest=payload["execution_population_digest"],
        execution_bundle_digest=payload["execution_bundle_digest"],
        physical_cost_bundle_digest=payload["physical_cost_bundle_digest"],
        physical_cost_population_digest=payload["physical_cost_population_digest"],
        harness_freeze_digest=payload["harness_freeze_digest"],
        ccf_evidence_bundle_digest=payload["ccf_evidence_bundle_digest"],
        ccf_evidence_population_digest=payload["ccf_evidence_population_digest"],
        dgc_policy_id=dgc_policy,
        confirmatory_task_manifest_digest=payload["confirmatory_task_manifest_digest"],
        replicate_audits=audits_tuple,
        total_value_regret_units=total_regret,
        total_avoidable_cost_units=total_avoidable,
        max_value_regret_units=max_regret,
        max_avoidable_cost_units=max_avoidable,
        headroom_audit_complete=True,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_ccf_oracle_audit_authority_document(path: Path) -> dict[str, object]:
    doc = _json(Path(path), schema=AUTHORITY_SCHEMA)
    if doc.get("headroom_audit_complete") is not True:
        raise CCFOracleAuditError("CCF oracle headroom audit is incomplete")
    if doc.get("product_promotion_authorized") is not False:
        raise CCFOracleAuditError("CCF oracle audit cannot authorize product promotion")
    keys = (
        "family_id", "ccf_spec_authority_digest", "ccf_spec_digest", "execution_authority_digest",
        "execution_population_digest", "execution_bundle_digest", "physical_cost_bundle_digest",
        "physical_cost_population_digest", "harness_freeze_digest", "ccf_evidence_bundle_digest",
        "ccf_evidence_population_digest", "dgc_policy_id", "confirmatory_task_manifest_digest",
        "replicate_audits", "total_value_regret_units", "total_avoidable_cost_units",
        "max_value_regret_units", "max_avoidable_cost_units", "headroom_audit_complete",
    )
    try:
        payload = {key: doc[key] for key in keys}
    except KeyError as exc:
        raise CCFOracleAuditError("CCF oracle audit authority payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise CCFOracleAuditError("CCF oracle audit authority digest mismatch")
    for name in (
        "ccf_spec_authority_digest", "ccf_spec_digest", "execution_authority_digest",
        "execution_population_digest", "execution_bundle_digest", "physical_cost_bundle_digest",
        "physical_cost_population_digest", "harness_freeze_digest", "ccf_evidence_bundle_digest",
        "ccf_evidence_population_digest", "confirmatory_task_manifest_digest",
    ):
        _sha(name, doc.get(name))
    audits = doc.get("replicate_audits")
    if not isinstance(audits, list) or not audits:
        raise CCFOracleAuditError("CCF oracle audit authority requires replicate audits")
    if sum(int(row["value_regret_units"]) for row in audits) != int(doc["total_value_regret_units"]):
        raise CCFOracleAuditError("CCF total value regret mismatch")
    if sum(int(row["avoidable_cost_units"]) for row in audits) != int(doc["total_avoidable_cost_units"]):
        raise CCFOracleAuditError("CCF total avoidable cost mismatch")
    if max(int(row["value_regret_units"]) for row in audits) != int(doc["max_value_regret_units"]):
        raise CCFOracleAuditError("CCF max value regret mismatch")
    if max(int(row["avoidable_cost_units"]) for row in audits) != int(doc["max_avoidable_cost_units"]):
        raise CCFOracleAuditError("CCF max avoidable cost mismatch")
    return doc
