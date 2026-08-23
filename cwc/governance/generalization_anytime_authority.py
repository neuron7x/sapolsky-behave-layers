from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.average_conditional_mean_cs import (
    ASSUMPTION_BOUNDARY,
    CLAIM_TARGET,
    METHOD,
    SEQUENCE_ORDER_RULE,
    certify_multi_baseline_anytime_valid,
)
from cwc.governance.exact_finite_panel_pareto import (
    certificate_digest as exact_certificate_digest,
    certify_exact_finite_panel,
)
from cwc.governance.generalization_execution_authority import (
    build_generalization_axis_authority,
    verify_generalization_axis_bundle,
)
from cwc.governance.generalization_registry import (
    DGC_ROLE,
    GeneralizationAxis,
    REQUIRED_AXES,
    REQUIRED_BASELINE_ROLES,
    verify_generalization_registry_document,
)
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
from cwc.governance.p9_scientific_authority_v3 import verify_p9_scientific_authority_v3_document
from cwc.governance.pareto import PairedBaselineEvidence

AXIS_SCHEMA = "DGC_GENERALIZATION_AXIS_ANYTIME_AUTHORITY_V4"
FINAL_SCHEMA = "DGC_GENERALIZATION_ANYTIME_AUTHORITY_V5"
CLAIM_SCOPE = "EXACT_G1_G5_PLUS_ANYTIME_VALID_AVERAGE_CONDITIONAL_MEAN_V2"


class GeneralizationAnytimeError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise GeneralizationAnytimeError(f"{name} must be lowercase SHA-256")
    return text


def _role_map(registry: Mapping[str, object]) -> dict[str, str]:
    rows = registry.get("policy_role_bindings")
    if not isinstance(rows, list) or not all(isinstance(row, list) and len(row) == 2 for row in rows):
        raise GeneralizationAnytimeError("generalization policy-role mapping malformed")
    result = {str(row[0]): str(row[1]) for row in rows}
    expected = set(REQUIRED_BASELINE_ROLES) | {DGC_ROLE}
    if set(result) != expected or len(set(result.values())) != len(expected):
        raise GeneralizationAnytimeError("generalization policy-role population mismatch")
    return result


def _axis_row(registry: Mapping[str, object], axis: GeneralizationAxis) -> Mapping[str, object]:
    rows = registry.get("axes")
    if not isinstance(rows, list):
        raise GeneralizationAnytimeError("generalization registry axes missing")
    matches = [row for row in rows if isinstance(row, Mapping) and row.get("axis") == axis.value]
    if len(matches) != 1:
        raise GeneralizationAnytimeError("generalization axis missing or duplicated")
    return matches[0]


def _paired_evidence(bundle, *, roles: Mapping[str, str], axis: GeneralizationAxis) -> tuple[PairedBaselineEvidence, ...]:
    by_unit = {(row.task_id, row.policy_id, row.replicate): row for row in bundle.results}
    tasks = tuple(sorted({row.task_id for row in bundle.results}))
    dgc_policy = roles[DGC_ROLE]
    paired_digest = sha256_bytes(canonical_json_bytes({
        "axis": axis.value,
        "task_population_digest": bundle.task_population_digest,
        "execution_bundle_digest": bundle.bundle_digest,
        "replicates": bundle.replicates,
        "sequence_order_rule": SEQUENCE_ORDER_RULE,
        "claim_target": CLAIM_TARGET,
    }))
    cap = float(bundle.max_physical_cost_usd_per_unit)
    evidence: list[PairedBaselineEvidence] = []
    for baseline_role in REQUIRED_BASELINE_ROLES:
        baseline_policy = roles[baseline_role]
        cost_gain: list[float] = []
        quality_gain: list[float] = []
        regret_gain: list[float] = []
        coverage = True
        for task_id in tasks:
            for replicate in range(bundle.replicates):
                baseline = by_unit[(task_id, baseline_policy, replicate)]
                dgc = by_unit[(task_id, dgc_policy, replicate)]
                cost_gain.append(float(baseline.physical_cost_usd) - float(dgc.physical_cost_usd))
                quality_gain.append(float(dgc.quality) - float(baseline.quality))
                regret_gain.append(float(baseline.catastrophic_regret) - float(dgc.catastrophic_regret))
                coverage = coverage and bool(baseline.covered) and bool(dgc.covered)
        evidence.append(PairedBaselineEvidence(
            baseline_id=baseline_role,
            paired_task_digest=paired_digest,
            coverage=1.0 if coverage else 0.0,
            baseline_minus_dgc_cost=tuple(cost_gain),
            dgc_minus_baseline_quality=tuple(quality_gain),
            baseline_minus_dgc_catastrophic_regret=tuple(regret_gain),
            cost_gain_support=(-cap, cap),
            quality_gain_support=(-1.0, 1.0),
            catastrophic_gain_support=(-1.0, 1.0),
        ))
    return tuple(evidence)


@dataclass(frozen=True, slots=True)
class GeneralizationAxisAnytimeAuthority:
    axis: str
    registry_digest: str
    evaluation_manifest_digest: str
    task_population_digest: str
    execution_bundle_digest: str
    metric_population_digest: str
    physical_cost_population_digest: str
    replicates: int
    paired_observations_per_baseline: int
    lineage_v1_axis_authority_digest: str
    exact_panel_certificate: dict[str, object]
    exact_panel_certificate_digest: str
    exact_panel_supported: bool
    anytime_certificate: dict[str, object]
    anytime_certificate_digest: str
    anytime_average_conditional_mean_supported: bool
    anytime_method: str
    anytime_claim_target: str
    anytime_assumption_boundary: str
    sequence_order_rule: str
    legacy_task_aggregated_hoeffding_certificate_digest: str | None
    legacy_task_aggregated_hoeffding_supported: bool
    axis_supported_without_iid_assumption: bool
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": AXIS_SCHEMA,
            **asdict(self),
            "iid_assumption_required": False,
            "provider_request_independence_required": False,
            "legacy_statistics_promotion_authorized": False,
            "policy_retuned": False,
            "product_promotion_authorized": False,
        }


def build_generalization_axis_anytime_authority(
    bundle_root: Path,
    *,
    repository_root: Path,
    registry_path: Path,
    trial_sizing_authority_path: Path,
) -> GeneralizationAxisAnytimeAuthority:
    registry = verify_generalization_registry_document(Path(registry_path))
    bundle = verify_generalization_axis_bundle(
        Path(bundle_root),
        repository_root=Path(repository_root),
        registry_path=Path(registry_path),
        trial_sizing_authority_path=Path(trial_sizing_authority_path),
    )
    try:
        axis = GeneralizationAxis(bundle.axis)
    except ValueError as exc:
        raise GeneralizationAnytimeError("unknown generalization axis") from exc

    lineage = build_generalization_axis_authority(
        Path(bundle_root),
        repository_root=Path(repository_root),
        registry_path=Path(registry_path),
        trial_sizing_authority_path=Path(trial_sizing_authority_path),
    )
    if lineage.execution_bundle_digest != bundle.bundle_digest:
        raise GeneralizationAnytimeError("legacy lineage verifier and V4 axis execution subject differ")

    row = _axis_row(registry, axis)
    roles = _role_map(registry)
    paired = _paired_evidence(bundle, roles=roles, axis=axis)
    qmargin = float(row["quality_noninferiority_margin"])
    cmargin = float(row["catastrophic_noninferiority_margin"])
    exact = certify_exact_finite_panel(
        paired,
        quality_noninferiority_margin=qmargin,
        catastrophic_noninferiority_margin=cmargin,
    )
    alpha_axis = float(registry["generalization_familywise_alpha"]) / len(REQUIRED_AXES)
    anytime = certify_multi_baseline_anytime_valid(
        paired,
        alpha=alpha_axis,
        quality_noninferiority_margin=qmargin,
        catastrophic_noninferiority_margin=cmargin,
    )
    if not math.isclose(anytime.per_metric_alpha, float(registry["per_claim_alpha"]), rel_tol=0.0, abs_tol=1e-15):
        raise GeneralizationAnytimeError("G1-G5 anytime-valid multiplicity differs from preregistration")

    exact_doc = asdict(exact)
    anytime_doc = asdict(anytime)
    anytime_digest = sha256_bytes(canonical_json_bytes(anytime_doc))
    exact_supported = bool(exact.all_baselines_observed)
    anytime_supported = bool(anytime.all_baselines_certified)
    supported = exact_supported and anytime_supported
    payload = {
        "axis": axis.value,
        "registry_digest": bundle.registry_digest,
        "evaluation_manifest_digest": bundle.evaluation_manifest_digest,
        "task_population_digest": bundle.task_population_digest,
        "execution_bundle_digest": bundle.bundle_digest,
        "metric_population_digest": bundle.metric_population_digest,
        "physical_cost_population_digest": bundle.physical_cost_population_digest,
        "replicates": bundle.replicates,
        "paired_observations_per_baseline": len({item.task_id for item in bundle.results}) * bundle.replicates,
        "lineage_v1_axis_authority_digest": lineage.authority_digest,
        "exact_panel_certificate": exact_doc,
        "exact_panel_certificate_digest": exact_certificate_digest(exact),
        "exact_panel_supported": exact_supported,
        "anytime_certificate": anytime_doc,
        "anytime_certificate_digest": anytime_digest,
        "anytime_average_conditional_mean_supported": anytime_supported,
        "anytime_method": METHOD,
        "anytime_claim_target": CLAIM_TARGET,
        "anytime_assumption_boundary": ASSUMPTION_BOUNDARY,
        "sequence_order_rule": SEQUENCE_ORDER_RULE,
        "legacy_task_aggregated_hoeffding_certificate_digest": lineage.certificate_digest,
        "legacy_task_aggregated_hoeffding_supported": bool(lineage.supported),
        "axis_supported_without_iid_assumption": supported,
    }
    return GeneralizationAxisAnytimeAuthority(
        **payload,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_generalization_axis_anytime_authority_document(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise GeneralizationAnytimeError("G1-G5 anytime authority must be a regular file")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GeneralizationAnytimeError("invalid G1-G5 anytime authority JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != AXIS_SCHEMA:
        raise GeneralizationAnytimeError("unexpected G1-G5 anytime authority schema")
    if doc.get("iid_assumption_required") is not False or doc.get("provider_request_independence_required") is not False:
        raise GeneralizationAnytimeError("G1-G5 anytime authority incorrectly requires iid/independence")
    if doc.get("legacy_statistics_promotion_authorized") is not False:
        raise GeneralizationAnytimeError("legacy statistics cannot authorize V4 axis promotion")
    if doc.get("policy_retuned") is not False or doc.get("product_promotion_authorized") is not False:
        raise GeneralizationAnytimeError("G1-G5 anytime promotion boundary malformed")
    keys = (
        "axis", "registry_digest", "evaluation_manifest_digest", "task_population_digest",
        "execution_bundle_digest", "metric_population_digest", "physical_cost_population_digest",
        "replicates", "paired_observations_per_baseline", "lineage_v1_axis_authority_digest",
        "exact_panel_certificate", "exact_panel_certificate_digest", "exact_panel_supported",
        "anytime_certificate", "anytime_certificate_digest", "anytime_average_conditional_mean_supported",
        "anytime_method", "anytime_claim_target", "anytime_assumption_boundary", "sequence_order_rule",
        "legacy_task_aggregated_hoeffding_certificate_digest", "legacy_task_aggregated_hoeffding_supported",
        "axis_supported_without_iid_assumption",
    )
    try:
        payload = {key: doc[key] for key in keys}
    except KeyError as exc:
        raise GeneralizationAnytimeError("G1-G5 anytime payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise GeneralizationAnytimeError("G1-G5 anytime authority digest mismatch")
    exact = doc.get("exact_panel_certificate")
    anytime = doc.get("anytime_certificate")
    if not isinstance(exact, dict) or not isinstance(anytime, dict):
        raise GeneralizationAnytimeError("G1-G5 exact/anytime certificates missing")
    if sha256_bytes(canonical_json_bytes(exact)) != _sha(
        "exact_panel_certificate_digest", doc.get("exact_panel_certificate_digest")
    ):
        raise GeneralizationAnytimeError("G1-G5 exact certificate digest mismatch")
    if sha256_bytes(canonical_json_bytes(anytime)) != _sha(
        "anytime_certificate_digest", doc.get("anytime_certificate_digest")
    ):
        raise GeneralizationAnytimeError("G1-G5 anytime certificate digest mismatch")
    if doc.get("anytime_method") != METHOD or doc.get("anytime_claim_target") != CLAIM_TARGET:
        raise GeneralizationAnytimeError("G1-G5 anytime theorem identity mismatch")
    if doc.get("anytime_assumption_boundary") != ASSUMPTION_BOUNDARY or doc.get("sequence_order_rule") != SEQUENCE_ORDER_RULE:
        raise GeneralizationAnytimeError("G1-G5 anytime assumption/order mismatch")
    derived_exact = exact.get("all_baselines_observed") is True
    derived_anytime = anytime.get("all_baselines_certified") is True
    if doc.get("exact_panel_supported") is not derived_exact:
        raise GeneralizationAnytimeError("G1-G5 exact support flag is not certificate-derived")
    if doc.get("anytime_average_conditional_mean_supported") is not derived_anytime:
        raise GeneralizationAnytimeError("G1-G5 anytime support flag is not certificate-derived")
    derived = derived_exact and derived_anytime
    if doc.get("axis_supported_without_iid_assumption") is not derived:
        raise GeneralizationAnytimeError("G1-G5 axis support must derive from exact + anytime-valid evidence")
    if int(doc.get("paired_observations_per_baseline", 0)) <= 0:
        raise GeneralizationAnytimeError("G1-G5 paired observation population must be non-empty")
    for field in (
        "registry_digest", "evaluation_manifest_digest", "task_population_digest", "execution_bundle_digest",
        "metric_population_digest", "physical_cost_population_digest", "lineage_v1_axis_authority_digest",
        "exact_panel_certificate_digest",
    ):
        _sha(field, doc.get(field))
    legacy_digest = doc.get("legacy_task_aggregated_hoeffding_certificate_digest")
    if legacy_digest is not None:
        _sha("legacy_task_aggregated_hoeffding_certificate_digest", legacy_digest)
    return doc


@dataclass(frozen=True, slots=True)
class GeneralizationAnytimeAuthority:
    registry_digest: str
    p9_scientific_v3_authority_digest: str
    frozen_dgc_policy_digest: str
    axis_authority_digests: tuple[tuple[str, str], ...]
    exact_g1_g5_supported: bool
    anytime_g1_g5_supported: bool
    generalization_supported_without_iid_assumption: bool
    independent_replication_evaluation_authorized: bool
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": FINAL_SCHEMA,
            **asdict(self),
            "claim_scope": CLAIM_SCOPE,
            "iid_assumption_required": False,
            "provider_request_independence_required": False,
            "product_promotion_authorized": False,
        }


def build_generalization_anytime_authority(
    *,
    registry_path: Path,
    p9_scientific_v3_authority_path: Path,
    axis_authority_paths: Mapping[GeneralizationAxis, Path],
) -> GeneralizationAnytimeAuthority:
    registry = verify_generalization_registry_document(Path(registry_path))
    p9 = verify_p9_scientific_authority_v3_document(Path(p9_scientific_v3_authority_path))
    if p9.get("generalization_evaluation_authorized") is not True:
        raise GeneralizationAnytimeError("primary P9 scientific V3 does not authorize G1-G5 evaluation")
    if set(axis_authority_paths) != set(REQUIRED_AXES):
        raise GeneralizationAnytimeError("final generalization authority requires exact G1-G5")
    rows: list[dict[str, object]] = []
    for axis in REQUIRED_AXES:
        doc = verify_generalization_axis_anytime_authority_document(Path(axis_authority_paths[axis]))
        if doc.get("axis") != axis.value or doc.get("registry_digest") != registry.get("registry_digest"):
            raise GeneralizationAnytimeError("G1-G5 anytime authority lineage mismatch")
        registry_row = _axis_row(registry, axis)
        if doc.get("evaluation_manifest_digest") != registry_row.get("evaluation_manifest_digest"):
            raise GeneralizationAnytimeError("G1-G5 anytime evaluation identity differs from registry")
        if doc.get("task_population_digest") != registry_row.get("task_population_digest"):
            raise GeneralizationAnytimeError("G1-G5 anytime task identity differs from registry")
        rows.append(doc)
    exact = all(row.get("exact_panel_supported") is True for row in rows)
    anytime = all(row.get("anytime_average_conditional_mean_supported") is True for row in rows)
    supported = exact and anytime
    axis_digests = tuple(sorted(
        (str(row["axis"]), _sha("axis authority_digest", row.get("authority_digest"))) for row in rows
    ))
    payload = {
        "registry_digest": _sha("registry_digest", registry.get("registry_digest")),
        "p9_scientific_v3_authority_digest": _sha("P9 scientific V3 authority_digest", p9.get("authority_digest")),
        "frozen_dgc_policy_digest": _sha("frozen_dgc_policy_digest", registry.get("frozen_dgc_policy_digest")),
        "axis_authority_digests": [list(row) for row in axis_digests],
        "exact_g1_g5_supported": exact,
        "anytime_g1_g5_supported": anytime,
        "generalization_supported_without_iid_assumption": supported,
        "independent_replication_evaluation_authorized": supported,
    }
    return GeneralizationAnytimeAuthority(
        registry_digest=payload["registry_digest"],
        p9_scientific_v3_authority_digest=payload["p9_scientific_v3_authority_digest"],
        frozen_dgc_policy_digest=payload["frozen_dgc_policy_digest"],
        axis_authority_digests=axis_digests,
        exact_g1_g5_supported=exact,
        anytime_g1_g5_supported=anytime,
        generalization_supported_without_iid_assumption=supported,
        independent_replication_evaluation_authorized=supported,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_generalization_anytime_authority_document(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise GeneralizationAnytimeError("final G1-G5 anytime authority must be a regular file")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GeneralizationAnytimeError("invalid final G1-G5 anytime authority JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != FINAL_SCHEMA:
        raise GeneralizationAnytimeError("unexpected final G1-G5 anytime schema")
    if doc.get("claim_scope") != CLAIM_SCOPE:
        raise GeneralizationAnytimeError("final G1-G5 anytime claim scope mismatch")
    if doc.get("iid_assumption_required") is not False or doc.get("provider_request_independence_required") is not False:
        raise GeneralizationAnytimeError("final G1-G5 anytime authority incorrectly requires iid/independence")
    if doc.get("product_promotion_authorized") is not False:
        raise GeneralizationAnytimeError("final G1-G5 anytime authority cannot authorize product promotion")
    keys = (
        "registry_digest", "p9_scientific_v3_authority_digest", "frozen_dgc_policy_digest",
        "axis_authority_digests", "exact_g1_g5_supported", "anytime_g1_g5_supported",
        "generalization_supported_without_iid_assumption", "independent_replication_evaluation_authorized",
    )
    try:
        payload = {key: doc[key] for key in keys}
    except KeyError as exc:
        raise GeneralizationAnytimeError("final G1-G5 anytime payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise GeneralizationAnytimeError("final G1-G5 anytime authority digest mismatch")
    derived = doc.get("exact_g1_g5_supported") is True and doc.get("anytime_g1_g5_supported") is True
    if doc.get("generalization_supported_without_iid_assumption") is not derived:
        raise GeneralizationAnytimeError("generalization support must derive from exact + anytime G1-G5")
    if doc.get("independent_replication_evaluation_authorized") is not derived:
        raise GeneralizationAnytimeError("replication evaluation requires exact + anytime G1-G5")
    for field in ("registry_digest", "p9_scientific_v3_authority_digest", "frozen_dgc_policy_digest"):
        _sha(field, doc.get(field))
    return doc