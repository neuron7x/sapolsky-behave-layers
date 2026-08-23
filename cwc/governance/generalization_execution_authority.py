from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from statistics import fmean
from typing import Mapping, Sequence

from cwc.governance.generalization_registry import (
    AXIS_SCHEMA,
    DGC_ROLE,
    GeneralizationAxis,
    REQUIRED_AXES,
    REQUIRED_BASELINE_ROLES,
    verify_generalization_registry_document,
)
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.pareto import PairedBaselineEvidence, MultiBaselineParetoCertificate, certify_multi_baseline_pareto_improvement
from cwc.governance.physical_cost_evidence import (
    CostAuthority,
    CostComponentEvidence,
    PRODUCT_COST_COMPONENTS,
    certify_physical_trial_cost,
)
from cwc.governance.p9_scientific_authority import verify_p9_scientific_authority_document
from cwc.governance.trial_sizing_authority import verify_trial_sizing_authority_document

AXIS_EXECUTION_SCHEMA = "DGC_GENERALIZATION_AXIS_EXECUTION_V1"
AXIS_AUTHORITY_SCHEMA = "DGC_GENERALIZATION_AXIS_AUTHORITY_V1"
GENERALIZATION_AUTHORITY_SCHEMA = "DGC_GENERALIZATION_AUTHORITY_V1"
REPLICATE_RULE = "USE_PRIMARY_TRIAL_SIZING"


class GeneralizationExecutionError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise GeneralizationExecutionError(f"{name} must be lowercase SHA-256")
    return text


def _req(name: str, value: object) -> str:
    text = str(value).strip()
    if not text:
        raise GeneralizationExecutionError(f"{name} required")
    return text


def _finite(name: str, value: object, *, lower: float | None = None, upper: float | None = None) -> float:
    try:
        result = float(value)
    except (TypeError, ValueError) as exc:
        raise GeneralizationExecutionError(f"{name} must be numeric") from exc
    if not math.isfinite(result):
        raise GeneralizationExecutionError(f"{name} must be finite")
    if lower is not None and result < lower:
        raise GeneralizationExecutionError(f"{name} below lower bound")
    if upper is not None and result > upper:
        raise GeneralizationExecutionError(f"{name} above upper bound")
    return result


def _json(path: Path, *, schema: str) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise GeneralizationExecutionError(f"missing regular JSON file: {candidate}")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GeneralizationExecutionError(f"invalid JSON file: {candidate}") from exc
    if not isinstance(doc, dict) or doc.get("schema") != schema:
        raise GeneralizationExecutionError(f"unexpected schema for {candidate}")
    return doc


def _safe_file(root: Path, value: object) -> tuple[Path, str]:
    rel = Path(str(value))
    if not str(value) or rel.is_absolute() or ".." in rel.parts:
        raise GeneralizationExecutionError("evidence path must be relative and non-traversing")
    candidate = root / rel
    if candidate.is_symlink():
        raise GeneralizationExecutionError("evidence symlink rejected")
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise GeneralizationExecutionError("evidence path escapes bundle root") from exc
    if not resolved.is_file() or resolved.stat().st_size <= 0:
        raise GeneralizationExecutionError("non-empty regular evidence file required")
    return resolved, rel.as_posix()


def _axis_row(registry: Mapping[str, object], axis: GeneralizationAxis) -> Mapping[str, object]:
    rows = registry.get("axes")
    if not isinstance(rows, list):
        raise GeneralizationExecutionError("generalization registry axes missing")
    matches = [row for row in rows if isinstance(row, Mapping) and row.get("axis") == axis.value]
    if len(matches) != 1:
        raise GeneralizationExecutionError("generalization axis missing or duplicated in registry")
    return matches[0]


def _role_map(registry: Mapping[str, object]) -> dict[str, str]:
    rows = registry.get("policy_role_bindings")
    if not isinstance(rows, list) or not all(isinstance(row, list) and len(row) == 2 for row in rows):
        raise GeneralizationExecutionError("generalization policy-role bindings malformed")
    mapping = {str(row[0]): str(row[1]) for row in rows}
    expected = set(REQUIRED_BASELINE_ROLES) | {DGC_ROLE}
    if set(mapping) != expected or len(set(mapping.values())) != len(expected):
        raise GeneralizationExecutionError("generalization policy-role population mismatch")
    return mapping


def _task_digest(task_ids: Sequence[str]) -> str:
    tasks = tuple(sorted({_req("task_id", value) for value in task_ids}))
    if len(tasks) != len(task_ids):
        raise GeneralizationExecutionError("task population contains duplicates")
    return sha256_bytes(canonical_json_bytes(tasks))


def _axis_manifest(root: Path, row: Mapping[str, object]) -> dict[str, object]:
    path = root / str(row.get("manifest_path", ""))
    doc = _json(path, schema=AXIS_SCHEMA)
    if sha256_file(path) != _sha("axis manifest_sha256", row.get("manifest_sha256")):
        raise GeneralizationExecutionError("axis manifest bytes changed after preregistration")
    if doc.get("axis") != row.get("axis"):
        raise GeneralizationExecutionError("axis manifest identity differs from registry")
    if doc.get("outcomes_observed") is not False or doc.get("policy_retuning_allowed") is not False:
        raise GeneralizationExecutionError("axis manifest is not a pre-outcome no-retuning preregistration")
    if doc.get("replicate_rule") != REPLICATE_RULE:
        raise GeneralizationExecutionError("axis manifest must preregister USE_PRIMARY_TRIAL_SIZING")
    cap = _finite("max_physical_cost_usd_per_unit", doc.get("max_physical_cost_usd_per_unit"), lower=0.0)
    if cap <= 0.0:
        raise GeneralizationExecutionError("axis manifest physical cost cap must be > 0")
    semantic = {
        key: value
        for key, value in doc.items()
        if key not in {"schema", "evaluation_manifest_digest", "outcomes_observed", "policy_retuning_allowed"}
    }
    if sha256_bytes(canonical_json_bytes(semantic)) != _sha(
        "evaluation_manifest_digest", doc.get("evaluation_manifest_digest")
    ):
        raise GeneralizationExecutionError("axis evaluation manifest digest is not derivable from frozen semantics")
    if doc.get("evaluation_manifest_digest") != row.get("evaluation_manifest_digest"):
        raise GeneralizationExecutionError("axis evaluation identity differs from registry")
    return doc


def _verify_cost_components(
    *,
    bundle_root: Path,
    axis: GeneralizationAxis,
    task_id: str,
    policy_id: str,
    replicate: int,
    raw: object,
    cost_cap: float,
) -> tuple[float, str, tuple[dict[str, object], ...]]:
    if not isinstance(raw, list) or len(raw) != len(PRODUCT_COST_COMPONENTS):
        raise GeneralizationExecutionError("each unit requires the complete ten-component physical cost population")
    observed: dict[str, CostComponentEvidence] = {}
    normalized: list[dict[str, object]] = []
    for item in raw:
        if not isinstance(item, Mapping):
            raise GeneralizationExecutionError("malformed physical cost component")
        component = _req("cost.component", item.get("component"))
        if component in observed:
            raise GeneralizationExecutionError("duplicate physical cost component")
        source_path, source_rel = _safe_file(bundle_root, item.get("source_path"))
        source_digest = sha256_file(source_path)
        if source_digest != _sha("cost.source_digest", item.get("source_digest")):
            raise GeneralizationExecutionError("physical cost source bytes do not match declared digest")
        try:
            authority = CostAuthority(str(item.get("authority")))
            evidence = CostComponentEvidence(
                component=component,
                value_usd=float(item.get("value_usd")),
                authority=authority,
                source_digest=source_digest,
            )
        except (TypeError, ValueError) as exc:
            raise GeneralizationExecutionError("invalid physical cost component semantics") from exc
        observed[component] = evidence
        normalized.append({
            "component": component,
            "value_usd": evidence.value_usd,
            "authority": evidence.authority.value,
            "source_path": source_rel,
            "source_digest": source_digest,
        })
    if set(observed) != set(PRODUCT_COST_COMPONENTS):
        raise GeneralizationExecutionError("physical cost component set is incomplete")
    trial_id = f"{axis.value}:{task_id}:{policy_id}:{replicate}"
    try:
        certificate = certify_physical_trial_cost(trial_id=trial_id, evidence=observed)
    except (TypeError, ValueError) as exc:
        raise GeneralizationExecutionError("physical cost certificate cannot be reconstructed") from exc
    if certificate.cost.total_operational_usd > cost_cap:
        raise GeneralizationExecutionError("physical cost exceeds preregistered per-unit support cap")
    normalized_sorted = tuple(sorted(normalized, key=lambda row: str(row["component"])))
    return certificate.cost.total_operational_usd, certificate.digest, normalized_sorted


@dataclass(frozen=True, slots=True)
class VerifiedGeneralizationResult:
    task_id: str
    policy_id: str
    replicate: int
    quality: float
    catastrophic_regret: float
    covered: bool
    physical_cost_usd: float
    physical_cost_certificate_digest: str
    metric_evidence_path: str
    metric_evidence_digest: str
    record_digest: str


@dataclass(frozen=True, slots=True)
class VerifiedGeneralizationAxisBundle:
    axis: str
    registry_digest: str
    evaluation_manifest_digest: str
    task_population_digest: str
    frozen_dgc_policy_digest: str
    trial_sizing_authority_digest: str
    replicates: int
    max_physical_cost_usd_per_unit: float
    results: tuple[VerifiedGeneralizationResult, ...]
    metric_population_digest: str
    physical_cost_population_digest: str
    bundle_digest: str


def verify_generalization_axis_bundle(
    bundle_root: Path,
    *,
    repository_root: Path,
    registry_path: Path,
    trial_sizing_authority_path: Path,
) -> VerifiedGeneralizationAxisBundle:
    supplied = Path(bundle_root)
    if supplied.is_symlink() or not supplied.is_dir():
        raise GeneralizationExecutionError("generalization axis bundle root must be a real directory")
    root = supplied.resolve()
    repo = Path(repository_root).resolve()
    registry = verify_generalization_registry_document(Path(registry_path))
    sizing = verify_trial_sizing_authority_document(Path(trial_sizing_authority_path))
    manifest = _json(root / "AXIS_EXECUTION.json", schema=AXIS_EXECUTION_SCHEMA)
    try:
        axis = GeneralizationAxis(str(manifest.get("axis")))
    except ValueError as exc:
        raise GeneralizationExecutionError("unknown generalization axis") from exc
    registry_digest = _sha("registry_digest", registry.get("registry_digest"))
    if manifest.get("registry_digest") != registry_digest:
        raise GeneralizationExecutionError("axis execution belongs to a different generalization registry")
    row = _axis_row(registry, axis)
    axis_manifest = _axis_manifest(repo, row)
    evaluation_digest = _sha("evaluation_manifest_digest", row.get("evaluation_manifest_digest"))
    if manifest.get("evaluation_manifest_digest") != evaluation_digest:
        raise GeneralizationExecutionError("axis execution uses a different evaluation manifest")
    if manifest.get("task_population_digest") != row.get("task_population_digest"):
        raise GeneralizationExecutionError("axis execution uses a different preregistered task population")
    if manifest.get("frozen_dgc_policy_digest") != registry.get("frozen_dgc_policy_digest"):
        raise GeneralizationExecutionError("axis execution uses a different DGC policy")
    sizing_digest = _sha("trial sizing authority_digest", sizing.get("authority_digest"))
    if manifest.get("trial_sizing_authority_digest") != sizing_digest:
        raise GeneralizationExecutionError("axis execution uses a different trial-sizing authority")
    replicates = int(sizing.get("required_trials_per_task", 0))
    if replicates <= 0 or int(manifest.get("replicates", -1)) != replicates:
        raise GeneralizationExecutionError("axis execution replicate count differs from frozen primary trial sizing")
    if manifest.get("policy_retuned") is not False or manifest.get("product_promotion_authorized") is not False:
        raise GeneralizationExecutionError("axis execution must preserve frozen policy and cannot authorize product promotion")
    cost_cap = _finite(
        "max_physical_cost_usd_per_unit",
        axis_manifest.get("max_physical_cost_usd_per_unit"),
        lower=0.0,
    )
    roles = _role_map(registry)
    expected_policies = set(roles.values())

    raw_rows = manifest.get("results")
    if not isinstance(raw_rows, list) or not raw_rows:
        raise GeneralizationExecutionError("axis execution requires a non-empty result population")
    results: list[VerifiedGeneralizationResult] = []
    seen_units: set[tuple[str, str, int]] = set()
    for raw in raw_rows:
        if not isinstance(raw, Mapping):
            raise GeneralizationExecutionError("malformed generalization result row")
        task_id = _req("task_id", raw.get("task_id"))
        policy_id = _req("policy_id", raw.get("policy_id"))
        try:
            replicate = int(raw.get("replicate"))
        except (TypeError, ValueError) as exc:
            raise GeneralizationExecutionError("replicate must be an integer") from exc
        if replicate < 0 or replicate >= replicates:
            raise GeneralizationExecutionError("replicate outside frozen range")
        if policy_id not in expected_policies:
            raise GeneralizationExecutionError("result policy outside frozen five-arm population")
        unit = (task_id, policy_id, replicate)
        if unit in seen_units:
            raise GeneralizationExecutionError("duplicate generalization work unit")
        seen_units.add(unit)
        quality = _finite("quality", raw.get("quality"), lower=0.0, upper=1.0)
        regret = _finite("catastrophic_regret", raw.get("catastrophic_regret"), lower=0.0, upper=1.0)
        covered = raw.get("covered") is True
        evidence_path, evidence_rel = _safe_file(root, raw.get("metric_evidence_path"))
        evidence_digest = sha256_file(evidence_path)
        if evidence_digest != _sha("metric_evidence_sha256", raw.get("metric_evidence_sha256")):
            raise GeneralizationExecutionError("metric evidence bytes changed")
        cost, cost_certificate_digest, normalized_components = _verify_cost_components(
            bundle_root=root,
            axis=axis,
            task_id=task_id,
            policy_id=policy_id,
            replicate=replicate,
            raw=raw.get("physical_cost_components"),
            cost_cap=cost_cap,
        )
        if raw.get("physical_cost_certificate_digest") != cost_certificate_digest:
            raise GeneralizationExecutionError("physical cost certificate digest mismatch")
        record_payload = {
            "task_id": task_id,
            "policy_id": policy_id,
            "replicate": replicate,
            "quality": quality,
            "catastrophic_regret": regret,
            "covered": covered,
            "metric_evidence_path": evidence_rel,
            "metric_evidence_sha256": evidence_digest,
            "physical_cost_components": list(normalized_components),
            "physical_cost_certificate_digest": cost_certificate_digest,
        }
        record_digest = sha256_bytes(canonical_json_bytes(record_payload))
        if raw.get("record_digest") != record_digest:
            raise GeneralizationExecutionError("generalization result record digest mismatch")
        results.append(VerifiedGeneralizationResult(
            task_id=task_id,
            policy_id=policy_id,
            replicate=replicate,
            quality=quality,
            catastrophic_regret=regret,
            covered=covered,
            physical_cost_usd=cost,
            physical_cost_certificate_digest=cost_certificate_digest,
            metric_evidence_path=evidence_rel,
            metric_evidence_digest=evidence_digest,
            record_digest=record_digest,
        ))

    task_ids = tuple(sorted({row.task_id for row in results}))
    if _task_digest(task_ids) != _sha("task_population_digest", row.get("task_population_digest")):
        raise GeneralizationExecutionError("observed task set differs from preregistered task population")
    expected_units = {
        (task, policy, replicate)
        for task in task_ids
        for policy in expected_policies
        for replicate in range(replicates)
    }
    if seen_units != expected_units:
        raise GeneralizationExecutionError("axis execution population is incomplete or contains extra units")

    ordered = sorted(results, key=lambda item: (item.task_id, item.policy_id, item.replicate))
    metric_population_digest = sha256_bytes(canonical_json_bytes([
        (item.task_id, item.policy_id, item.replicate, item.quality, item.catastrophic_regret, item.covered, item.metric_evidence_digest)
        for item in ordered
    ]))
    physical_cost_population_digest = sha256_bytes(canonical_json_bytes([
        (item.task_id, item.policy_id, item.replicate, item.physical_cost_usd, item.physical_cost_certificate_digest)
        for item in ordered
    ]))
    payload = {
        "axis": axis.value,
        "registry_digest": registry_digest,
        "evaluation_manifest_digest": evaluation_digest,
        "task_population_digest": row["task_population_digest"],
        "frozen_dgc_policy_digest": registry["frozen_dgc_policy_digest"],
        "trial_sizing_authority_digest": sizing_digest,
        "replicates": replicates,
        "max_physical_cost_usd_per_unit": cost_cap,
        "metric_population_digest": metric_population_digest,
        "physical_cost_population_digest": physical_cost_population_digest,
        "result_record_digests": [item.record_digest for item in ordered],
    }
    bundle_digest = sha256_bytes(canonical_json_bytes(payload))
    if manifest.get("bundle_digest") != bundle_digest:
        raise GeneralizationExecutionError("axis execution bundle digest mismatch")
    return VerifiedGeneralizationAxisBundle(
        axis=axis.value,
        registry_digest=registry_digest,
        evaluation_manifest_digest=evaluation_digest,
        task_population_digest=str(row["task_population_digest"]),
        frozen_dgc_policy_digest=str(registry["frozen_dgc_policy_digest"]),
        trial_sizing_authority_digest=sizing_digest,
        replicates=replicates,
        max_physical_cost_usd_per_unit=cost_cap,
        results=tuple(ordered),
        metric_population_digest=metric_population_digest,
        physical_cost_population_digest=physical_cost_population_digest,
        bundle_digest=bundle_digest,
    )


def _paired_evidence(
    bundle: VerifiedGeneralizationAxisBundle,
    *,
    role_map: Mapping[str, str],
) -> tuple[PairedBaselineEvidence, ...]:
    by_task_policy: dict[tuple[str, str], list[VerifiedGeneralizationResult]] = {}
    for result in bundle.results:
        by_task_policy.setdefault((result.task_id, result.policy_id), []).append(result)
    tasks = tuple(sorted({row.task_id for row in bundle.results}))
    means: dict[tuple[str, str], tuple[float, float, float, bool]] = {}
    for task in tasks:
        for policy in sorted(set(role_map.values())):
            rows = sorted(by_task_policy[(task, policy)], key=lambda item: item.replicate)
            means[(task, policy)] = (
                fmean(item.physical_cost_usd for item in rows),
                fmean(item.quality for item in rows),
                fmean(item.catastrophic_regret for item in rows),
                all(item.covered for item in rows),
            )
    dgc = role_map[DGC_ROLE]
    result: list[PairedBaselineEvidence] = []
    for baseline_role in REQUIRED_BASELINE_ROLES:
        baseline = role_map[baseline_role]
        cost_gain: list[float] = []
        quality_gain: list[float] = []
        regret_gain: list[float] = []
        coverage_ok = True
        for task in tasks:
            bc, bq, br, bcovered = means[(task, baseline)]
            dc, dq, dr, dcovered = means[(task, dgc)]
            cost_gain.append(bc - dc)
            quality_gain.append(dq - bq)
            regret_gain.append(br - dr)
            coverage_ok = coverage_ok and bcovered and dcovered
        result.append(PairedBaselineEvidence(
            baseline_id=baseline_role,
            paired_task_digest=bundle.task_population_digest,
            coverage=1.0 if coverage_ok else 0.0,
            baseline_minus_dgc_cost=tuple(cost_gain),
            dgc_minus_baseline_quality=tuple(quality_gain),
            baseline_minus_dgc_catastrophic_regret=tuple(regret_gain),
            cost_gain_support=(-bundle.max_physical_cost_usd_per_unit, bundle.max_physical_cost_usd_per_unit),
            quality_gain_support=(-1.0, 1.0),
            catastrophic_gain_support=(-1.0, 1.0),
        ))
    return tuple(result)


@dataclass(frozen=True, slots=True)
class GeneralizationAxisAuthority:
    axis: str
    registry_digest: str
    evaluation_manifest_digest: str
    task_population_digest: str
    frozen_dgc_policy_digest: str
    trial_sizing_authority_digest: str
    execution_bundle_digest: str
    metric_population_digest: str
    physical_cost_population_digest: str
    replicates: int
    certificate: dict[str, object] | None
    certificate_digest: str | None
    supported: bool
    reason_code: str
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": AXIS_AUTHORITY_SCHEMA,
            **asdict(self),
            "policy_retuned": False,
            "product_promotion_authorized": False,
        }


def build_generalization_axis_authority(
    bundle_root: Path,
    *,
    repository_root: Path,
    registry_path: Path,
    trial_sizing_authority_path: Path,
) -> GeneralizationAxisAuthority:
    registry = verify_generalization_registry_document(Path(registry_path))
    bundle = verify_generalization_axis_bundle(
        Path(bundle_root),
        repository_root=Path(repository_root),
        registry_path=Path(registry_path),
        trial_sizing_authority_path=Path(trial_sizing_authority_path),
    )
    role_map = _role_map(registry)
    paired = _paired_evidence(bundle, role_map=role_map)
    certificate: MultiBaselineParetoCertificate | None = None
    reason = "SUPPORTED"
    supported = False
    if any(not math.isclose(row.coverage, 1.0, rel_tol=0.0, abs_tol=1e-12) for row in paired):
        reason = "INCOMPLETE_COVERAGE"
    else:
        axis_row = _axis_row(registry, GeneralizationAxis(bundle.axis))
        try:
            certificate = certify_multi_baseline_pareto_improvement(
                paired,
                alpha=float(registry["generalization_familywise_alpha"]) / len(REQUIRED_AXES),
                quality_noninferiority_margin=float(axis_row["quality_noninferiority_margin"]),
                catastrophic_noninferiority_margin=float(axis_row["catastrophic_noninferiority_margin"]),
            )
        except (TypeError, ValueError) as exc:
            raise GeneralizationExecutionError("generalization paired statistics cannot be certified") from exc
        if not math.isclose(
            certificate.per_metric_delta,
            float(registry["per_claim_alpha"]),
            rel_tol=0.0,
            abs_tol=1e-15,
        ):
            raise GeneralizationExecutionError("generalization multiplicity allocation differs from preregistration")
        supported = certificate.all_baselines_certified
        if not supported:
            reason = "PARETO_OR_NONINFERIORITY_GATE_FAILED"
    certificate_doc = None if certificate is None else asdict(certificate)
    certificate_digest = None if certificate_doc is None else sha256_bytes(canonical_json_bytes(certificate_doc))
    payload = {
        "axis": bundle.axis,
        "registry_digest": bundle.registry_digest,
        "evaluation_manifest_digest": bundle.evaluation_manifest_digest,
        "task_population_digest": bundle.task_population_digest,
        "frozen_dgc_policy_digest": bundle.frozen_dgc_policy_digest,
        "trial_sizing_authority_digest": bundle.trial_sizing_authority_digest,
        "execution_bundle_digest": bundle.bundle_digest,
        "metric_population_digest": bundle.metric_population_digest,
        "physical_cost_population_digest": bundle.physical_cost_population_digest,
        "replicates": bundle.replicates,
        "certificate": certificate_doc,
        "certificate_digest": certificate_digest,
        "supported": supported,
        "reason_code": reason,
    }
    return GeneralizationAxisAuthority(
        **payload,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_generalization_axis_authority_document(path: Path) -> dict[str, object]:
    doc = _json(Path(path), schema=AXIS_AUTHORITY_SCHEMA)
    if doc.get("policy_retuned") is not False or doc.get("product_promotion_authorized") is not False:
        raise GeneralizationExecutionError("axis authority cannot retune policy or authorize product promotion")
    keys = (
        "axis", "registry_digest", "evaluation_manifest_digest", "task_population_digest",
        "frozen_dgc_policy_digest", "trial_sizing_authority_digest", "execution_bundle_digest",
        "metric_population_digest", "physical_cost_population_digest", "replicates",
        "certificate", "certificate_digest", "supported", "reason_code",
    )
    try:
        payload = {key: doc[key] for key in keys}
    except KeyError as exc:
        raise GeneralizationExecutionError("axis authority payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise GeneralizationExecutionError("axis authority digest mismatch")
    GeneralizationAxis(str(doc.get("axis")))
    for name in (
        "registry_digest", "evaluation_manifest_digest", "task_population_digest",
        "frozen_dgc_policy_digest", "trial_sizing_authority_digest", "execution_bundle_digest",
        "metric_population_digest", "physical_cost_population_digest",
    ):
        _sha(name, doc.get(name))
    if int(doc.get("replicates", 0)) <= 0:
        raise GeneralizationExecutionError("axis authority replicate count must be > 0")
    if doc.get("supported") is True:
        cert = doc.get("certificate")
        if not isinstance(cert, Mapping) or not doc.get("certificate_digest"):
            raise GeneralizationExecutionError("supported axis requires a statistical certificate")
        if sha256_bytes(canonical_json_bytes(dict(cert))) != _sha("certificate_digest", doc.get("certificate_digest")):
            raise GeneralizationExecutionError("axis statistical certificate digest mismatch")
        if cert.get("all_baselines_certified") is not True:
            raise GeneralizationExecutionError("axis supported flag does not derive from certificate")
    return doc


@dataclass(frozen=True, slots=True)
class GeneralizationAuthority:
    registry_digest: str
    p9_scientific_authority_digest: str
    frozen_dgc_policy_digest: str
    axis_authority_digests: tuple[tuple[str, str], ...]
    axis_execution_bundle_digests: tuple[tuple[str, str], ...]
    generalization_supported: bool
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": GENERALIZATION_AUTHORITY_SCHEMA,
            "registry_digest": self.registry_digest,
            "p9_scientific_authority_digest": self.p9_scientific_authority_digest,
            "frozen_dgc_policy_digest": self.frozen_dgc_policy_digest,
            "axis_authority_digests": [list(row) for row in self.axis_authority_digests],
            "axis_execution_bundle_digests": [list(row) for row in self.axis_execution_bundle_digests],
            "generalization_supported": self.generalization_supported,
            "authority_digest": self.authority_digest,
            "independent_replication_authorized": self.generalization_supported,
            "product_promotion_authorized": False,
        }


def build_generalization_authority(
    *,
    registry_path: Path,
    p9_scientific_authority_path: Path,
    axis_authority_paths: Mapping[GeneralizationAxis, Path],
) -> GeneralizationAuthority:
    registry = verify_generalization_registry_document(Path(registry_path))
    p9 = verify_p9_scientific_authority_document(Path(p9_scientific_authority_path))
    if p9.get("generalization_authorized") is not True:
        raise GeneralizationExecutionError("primary P9 scientific authority does not authorize generalization evaluation")
    if set(axis_authority_paths) != set(REQUIRED_AXES):
        raise GeneralizationExecutionError("final generalization authority requires exactly G1-G5")
    registry_digest = _sha("registry_digest", registry.get("registry_digest"))
    dgc_digest = _sha("frozen_dgc_policy_digest", registry.get("frozen_dgc_policy_digest"))
    axis_rows: list[dict[str, object]] = []
    for axis in REQUIRED_AXES:
        authority = verify_generalization_axis_authority_document(Path(axis_authority_paths[axis]))
        if authority.get("axis") != axis.value:
            raise GeneralizationExecutionError("axis authority path/identity mismatch")
        if authority.get("registry_digest") != registry_digest:
            raise GeneralizationExecutionError("axis authority belongs to a different registry")
        if authority.get("frozen_dgc_policy_digest") != dgc_digest:
            raise GeneralizationExecutionError("axis authority uses a different frozen DGC policy")
        registry_axis = _axis_row(registry, axis)
        if authority.get("evaluation_manifest_digest") != registry_axis.get("evaluation_manifest_digest"):
            raise GeneralizationExecutionError("axis authority evaluation identity differs from registry")
        if authority.get("task_population_digest") != registry_axis.get("task_population_digest"):
            raise GeneralizationExecutionError("axis authority task identity differs from registry")
        axis_rows.append(authority)
    supported = all(row.get("supported") is True for row in axis_rows)
    axis_authority_digests = tuple(
        sorted((str(row["axis"]), _sha("axis authority_digest", row.get("authority_digest"))) for row in axis_rows)
    )
    bundle_digests = tuple(
        sorted((str(row["axis"]), _sha("execution_bundle_digest", row.get("execution_bundle_digest"))) for row in axis_rows)
    )
    payload = {
        "registry_digest": registry_digest,
        "p9_scientific_authority_digest": _sha("P9 scientific authority_digest", p9.get("authority_digest")),
        "frozen_dgc_policy_digest": dgc_digest,
        "axis_authority_digests": [list(row) for row in axis_authority_digests],
        "axis_execution_bundle_digests": [list(row) for row in bundle_digests],
        "generalization_supported": supported,
    }
    return GeneralizationAuthority(
        registry_digest=registry_digest,
        p9_scientific_authority_digest=payload["p9_scientific_authority_digest"],
        frozen_dgc_policy_digest=dgc_digest,
        axis_authority_digests=axis_authority_digests,
        axis_execution_bundle_digests=bundle_digests,
        generalization_supported=supported,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_generalization_authority_document(path: Path) -> dict[str, object]:
    doc = _json(Path(path), schema=GENERALIZATION_AUTHORITY_SCHEMA)
    if doc.get("product_promotion_authorized") is not False:
        raise GeneralizationExecutionError("generalization authority cannot authorize product promotion")
    keys = (
        "registry_digest", "p9_scientific_authority_digest", "frozen_dgc_policy_digest",
        "axis_authority_digests", "axis_execution_bundle_digests", "generalization_supported",
    )
    try:
        payload = {key: doc[key] for key in keys}
    except KeyError as exc:
        raise GeneralizationExecutionError("generalization authority payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise GeneralizationExecutionError("generalization authority digest mismatch")
    for name in ("registry_digest", "p9_scientific_authority_digest", "frozen_dgc_policy_digest"):
        _sha(name, doc.get(name))
    axis_rows = doc.get("axis_authority_digests")
    bundle_rows = doc.get("axis_execution_bundle_digests")
    if not isinstance(axis_rows, list) or not isinstance(bundle_rows, list):
        raise GeneralizationExecutionError("generalization authority axis populations missing")
    expected = {axis.value for axis in REQUIRED_AXES}
    if {str(row[0]) for row in axis_rows} != expected or {str(row[0]) for row in bundle_rows} != expected:
        raise GeneralizationExecutionError("generalization authority must contain exact G1-G5 populations")
    derived = doc.get("generalization_supported") is True
    if doc.get("independent_replication_authorized") is not derived:
        raise GeneralizationExecutionError("replication authority must derive from generalization support")
    return doc
