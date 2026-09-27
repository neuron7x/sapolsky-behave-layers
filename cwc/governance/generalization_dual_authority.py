from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.empirical_bernstein_pareto import certify_multi_baseline_empirical_bernstein
from cwc.governance.exact_finite_panel_pareto import certificate_digest as exact_certificate_digest, certify_exact_finite_panel
from cwc.governance.generalization_execution_authority import verify_generalization_axis_bundle
from cwc.governance.generalization_registry import (
    DGC_ROLE,
    GeneralizationAxis,
    REQUIRED_AXES,
    REQUIRED_BASELINE_ROLES,
    verify_generalization_registry_document,
)
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes
from cwc.governance.p9_scientific_authority_v2 import verify_p9_scientific_authority_v2_document
from cwc.governance.paired_randomness_protocol import INDEPENDENCE_ASSUMPTION, PROTOCOL, paired_seed
from cwc.governance.pareto import PairedBaselineEvidence

AXIS_SCHEMA = "DGC_GENERALIZATION_AXIS_DUAL_AUTHORITY_V2"
FINAL_SCHEMA = "DGC_GENERALIZATION_DUAL_AUTHORITY_V2"
AXIS_ESTIMAND = "FROZEN_GENERALIZATION_AXIS_EQUAL_TASK_EQUAL_REPLICATE_WEIGHT_V1"


class GeneralizationDualError(RuntimeError):
    pass


def _sha(name: str, value: object) -> str:
    text = str(value).strip().lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise GeneralizationDualError(f"{name} must be lowercase SHA-256")
    return text


def _role_map(registry: Mapping[str, object]) -> dict[str, str]:
    rows = registry.get("policy_role_bindings")
    if not isinstance(rows, list) or not all(isinstance(row, list) and len(row) == 2 for row in rows):
        raise GeneralizationDualError("generalization policy-role mapping malformed")
    result = {str(row[0]): str(row[1]) for row in rows}
    expected = set(REQUIRED_BASELINE_ROLES) | {DGC_ROLE}
    if set(result) != expected or len(set(result.values())) != len(expected):
        raise GeneralizationDualError("generalization policy-role population mismatch")
    return result


def _axis_registry_row(registry: Mapping[str, object], axis: GeneralizationAxis) -> Mapping[str, object]:
    rows = registry.get("axes")
    if not isinstance(rows, list):
        raise GeneralizationDualError("generalization registry axes missing")
    matches = [row for row in rows if isinstance(row, Mapping) and row.get("axis") == axis.value]
    if len(matches) != 1:
        raise GeneralizationDualError("generalization axis missing or duplicated")
    return matches[0]


def _axis_manifest(repository_root: Path, row: Mapping[str, object]) -> Mapping[str, object]:
    rel = Path(str(row.get("manifest_path", "")))
    if rel.is_absolute() or ".." in rel.parts or not rel.parts:
        raise GeneralizationDualError("axis manifest path unsafe")
    path = repository_root / rel
    if path.is_symlink() or not path.is_file():
        raise GeneralizationDualError("axis manifest missing")
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GeneralizationDualError("axis manifest invalid JSON") from exc
    if not isinstance(doc, Mapping) or doc.get("schema") != "DGC_GENERALIZATION_AXIS_MANIFEST_V1":
        raise GeneralizationDualError("axis manifest schema mismatch")
    if doc.get("randomness_protocol") != PROTOCOL:
        raise GeneralizationDualError("axis manifest must preregister paired randomness protocol")
    if doc.get("randomness_independence_assumption") != INDEPENDENCE_ASSUMPTION:
        raise GeneralizationDualError("axis manifest randomness assumption mismatch")
    return doc


def _flat_evidence(bundle, roles: Mapping[str, str], paired_panel_digest: str) -> tuple[PairedBaselineEvidence, ...]:
    by_unit = {(row.task_id, row.policy_id, row.replicate): row for row in bundle.results}
    tasks = tuple(sorted({row.task_id for row in bundle.results}))
    dgc = roles[DGC_ROLE]
    result: list[PairedBaselineEvidence] = []
    cap = float(bundle.max_physical_cost_usd_per_unit)
    for baseline_role in REQUIRED_BASELINE_ROLES:
        baseline = roles[baseline_role]
        cost_gain: list[float] = []
        quality_gain: list[float] = []
        catastrophic_gain: list[float] = []
        coverage = True
        for task in tasks:
            for replicate in range(bundle.replicates):
                b = by_unit[(task, baseline, replicate)]
                d = by_unit[(task, dgc, replicate)]
                cost_gain.append(b.physical_cost_usd - d.physical_cost_usd)
                quality_gain.append(d.quality - b.quality)
                catastrophic_gain.append(b.catastrophic_regret - d.catastrophic_regret)
                coverage = coverage and b.covered and d.covered
        result.append(PairedBaselineEvidence(
            baseline_id=baseline_role,
            paired_task_digest=paired_panel_digest,
            coverage=1.0 if coverage else 0.0,
            baseline_minus_dgc_cost=tuple(cost_gain),
            dgc_minus_baseline_quality=tuple(quality_gain),
            baseline_minus_dgc_catastrophic_regret=tuple(catastrophic_gain),
            cost_gain_support=(-cap, cap),
            quality_gain_support=(-1.0, 1.0),
            catastrophic_gain_support=(-1.0, 1.0),
        ))
    return tuple(result)


def _verify_axis_randomness(
    bundle_root: Path,
    *,
    axis: GeneralizationAxis,
    registry_digest: str,
    evaluation_manifest_digest: str,
    task_ids: tuple[str, ...],
    policy_ids: tuple[str, ...],
    replicates: int,
) -> tuple[str, int]:
    path = Path(bundle_root) / "AXIS_EXECUTION.json"
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GeneralizationDualError("axis execution JSON unavailable for randomness replay") from exc
    rows = doc.get("results") if isinstance(doc, Mapping) else None
    if not isinstance(rows, list):
        raise GeneralizationDualError("axis execution result population missing")
    schedule_root = sha256_bytes(canonical_json_bytes({
        "axis": axis.value,
        "registry_digest": registry_digest,
        "evaluation_manifest_digest": evaluation_manifest_digest,
        "protocol": PROTOCOL,
    }))
    seen_requests: set[str] = set()
    schedule: list[tuple[str, int, int, tuple[str, ...]]] = []
    indexed: dict[tuple[str, int], list[Mapping[str, object]]] = {}
    for raw in rows:
        if not isinstance(raw, Mapping):
            raise GeneralizationDualError("malformed axis result during randomness replay")
        if raw.get("randomness_protocol") != PROTOCOL:
            raise GeneralizationDualError("axis result lacks preregistered randomness protocol")
        task = str(raw.get("task_id", ""))
        policy = str(raw.get("policy_id", ""))
        replicate = int(raw.get("replicate", -1))
        expected_seed = paired_seed(root_digest=schedule_root, task_id=task, replicate=replicate)
        if int(raw.get("replicate_seed", -1)) != expected_seed:
            raise GeneralizationDualError("axis result seed differs from frozen paired schedule")
        request_id = str(raw.get("provider_request_id", "")).strip()
        if not request_id or request_id in seen_requests:
            raise GeneralizationDualError("provider_request_id must be non-empty and unique per work unit")
        seen_requests.add(request_id)
        indexed.setdefault((task, replicate), []).append(raw)
    expected_pairs = {(task, rep) for task in task_ids for rep in range(replicates)}
    if set(indexed) != expected_pairs:
        raise GeneralizationDualError("axis randomness schedule pair population mismatch")
    for pair in sorted(expected_pairs):
        task, replicate = pair
        rows_for_pair = indexed[pair]
        policies = tuple(sorted(str(row.get("policy_id", "")) for row in rows_for_pair))
        if policies != tuple(sorted(policy_ids)):
            raise GeneralizationDualError("axis paired randomness policy population mismatch")
        seed = paired_seed(root_digest=schedule_root, task_id=task, replicate=replicate)
        if any(int(row.get("replicate_seed", -1)) != seed for row in rows_for_pair):
            raise GeneralizationDualError("axis policies do not share paired seed")
        schedule.append((task, replicate, seed, policies))
    return sha256_bytes(canonical_json_bytes(schedule)), len(seen_requests)


@dataclass(frozen=True, slots=True)
class GeneralizationAxisDualAuthority:
    axis: str
    registry_digest: str
    evaluation_manifest_digest: str
    task_population_digest: str
    execution_bundle_digest: str
    metric_population_digest: str
    physical_cost_population_digest: str
    replicates: int
    paired_observations_per_baseline: int
    paired_panel_digest: str
    exact_panel_certificate: dict[str, object]
    exact_panel_certificate_digest: str
    exact_panel_supported: bool
    expected_effect_certificate: dict[str, object]
    expected_effect_certificate_digest: str
    expected_effect_supported_under_independence_assumption: bool
    randomness_protocol: str
    randomness_schedule_digest: str
    randomness_independence_assumption: str
    randomness_assumption_verified: bool
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": AXIS_SCHEMA,
            **asdict(self),
            "estimand": AXIS_ESTIMAND,
            "policy_retuned": False,
            "product_promotion_authorized": False,
        }


def build_generalization_axis_dual_authority(
    bundle_root: Path,
    *,
    repository_root: Path,
    registry_path: Path,
    trial_sizing_authority_path: Path,
) -> GeneralizationAxisDualAuthority:
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
        raise GeneralizationDualError("unknown generalization axis") from exc
    row = _axis_registry_row(registry, axis)
    manifest = _axis_manifest(Path(repository_root), row)
    roles = _role_map(registry)
    tasks = tuple(sorted({item.task_id for item in bundle.results}))
    policy_ids = tuple(sorted(set(roles.values())))
    schedule_digest, _ = _verify_axis_randomness(
        Path(bundle_root),
        axis=axis,
        registry_digest=bundle.registry_digest,
        evaluation_manifest_digest=bundle.evaluation_manifest_digest,
        task_ids=tasks,
        policy_ids=policy_ids,
        replicates=bundle.replicates,
    )
    paired_panel_digest = sha256_bytes(canonical_json_bytes({
        "axis": axis.value,
        "task_population_digest": bundle.task_population_digest,
        "replicates": bundle.replicates,
        "randomness_protocol": PROTOCOL,
        "randomness_schedule_digest": schedule_digest,
        "estimand": AXIS_ESTIMAND,
    }))
    paired = _flat_evidence(bundle, roles, paired_panel_digest)
    qmargin = float(row["quality_noninferiority_margin"])
    cmargin = float(row["catastrophic_noninferiority_margin"])
    exact = certify_exact_finite_panel(
        paired,
        quality_noninferiority_margin=qmargin,
        catastrophic_noninferiority_margin=cmargin,
    )
    exact_doc = asdict(exact)
    alpha_axis = float(registry["generalization_familywise_alpha"]) / len(REQUIRED_AXES)
    expected = certify_multi_baseline_empirical_bernstein(
        paired,
        alpha=alpha_axis,
        quality_noninferiority_margin=qmargin,
        catastrophic_noninferiority_margin=cmargin,
    )
    if not math.isclose(expected.per_metric_delta, float(registry["per_claim_alpha"]), rel_tol=0.0, abs_tol=1e-15):
        raise GeneralizationDualError("G1-G5 empirical-Bernstein multiplicity differs from preregistration")
    expected_doc = asdict(expected)
    expected_digest = sha256_bytes(canonical_json_bytes(expected_doc))
    payload = {
        "axis": axis.value,
        "registry_digest": bundle.registry_digest,
        "evaluation_manifest_digest": bundle.evaluation_manifest_digest,
        "task_population_digest": bundle.task_population_digest,
        "execution_bundle_digest": bundle.bundle_digest,
        "metric_population_digest": bundle.metric_population_digest,
        "physical_cost_population_digest": bundle.physical_cost_population_digest,
        "replicates": bundle.replicates,
        "paired_observations_per_baseline": len(tasks) * bundle.replicates,
        "paired_panel_digest": paired_panel_digest,
        "exact_panel_certificate": exact_doc,
        "exact_panel_certificate_digest": exact_certificate_digest(exact),
        "exact_panel_supported": exact.all_baselines_observed,
        "expected_effect_certificate": expected_doc,
        "expected_effect_certificate_digest": expected_digest,
        "expected_effect_supported_under_independence_assumption": expected.all_baselines_certified,
        "randomness_protocol": PROTOCOL,
        "randomness_schedule_digest": schedule_digest,
        "randomness_independence_assumption": INDEPENDENCE_ASSUMPTION,
        "randomness_assumption_verified": False,
    }
    return GeneralizationAxisDualAuthority(
        **payload,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_generalization_axis_dual_authority_document(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise GeneralizationDualError("G1-G5 dual authority must be a regular file")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GeneralizationDualError("invalid G1-G5 dual authority JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != AXIS_SCHEMA:
        raise GeneralizationDualError("unexpected G1-G5 dual authority schema")
    if doc.get("estimand") != AXIS_ESTIMAND or doc.get("policy_retuned") is not False:
        raise GeneralizationDualError("G1-G5 dual authority claim boundary malformed")
    if doc.get("product_promotion_authorized") is not False:
        raise GeneralizationDualError("G1-G5 dual authority cannot authorize product promotion")
    keys = (
        "axis", "registry_digest", "evaluation_manifest_digest", "task_population_digest",
        "execution_bundle_digest", "metric_population_digest", "physical_cost_population_digest",
        "replicates", "paired_observations_per_baseline", "paired_panel_digest",
        "exact_panel_certificate", "exact_panel_certificate_digest", "exact_panel_supported",
        "expected_effect_certificate", "expected_effect_certificate_digest",
        "expected_effect_supported_under_independence_assumption", "randomness_protocol",
        "randomness_schedule_digest", "randomness_independence_assumption", "randomness_assumption_verified",
    )
    try:
        payload = {key: doc[key] for key in keys}
    except KeyError as exc:
        raise GeneralizationDualError("G1-G5 dual authority payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise GeneralizationDualError("G1-G5 dual authority digest mismatch")
    exact = doc.get("exact_panel_certificate")
    expected = doc.get("expected_effect_certificate")
    if not isinstance(exact, Mapping) or not isinstance(expected, Mapping):
        raise GeneralizationDualError("G1-G5 dual certificates missing")
    if sha256_bytes(canonical_json_bytes(dict(exact))) != _sha(
        "exact_panel_certificate_digest", doc.get("exact_panel_certificate_digest")
    ):
        raise GeneralizationDualError("G1-G5 exact certificate digest mismatch")
    if sha256_bytes(canonical_json_bytes(dict(expected))) != _sha(
        "expected_effect_certificate_digest", doc.get("expected_effect_certificate_digest")
    ):
        raise GeneralizationDualError("G1-G5 conditional certificate digest mismatch")
    if doc.get("exact_panel_supported") is not (exact.get("all_baselines_observed") is True):
        raise GeneralizationDualError("G1-G5 exact support flag not derived from certificate")
    if doc.get("expected_effect_supported_under_independence_assumption") is not (
        expected.get("all_baselines_certified") is True
    ):
        raise GeneralizationDualError("G1-G5 conditional support flag not derived from certificate")
    return doc


@dataclass(frozen=True, slots=True)
class GeneralizationDualAuthority:
    registry_digest: str
    p9_scientific_v2_authority_digest: str
    frozen_dgc_policy_digest: str
    axis_authority_digests: tuple[tuple[str, str], ...]
    exact_g1_g5_supported: bool
    expected_g1_g5_supported_under_independence_assumption: bool
    authority_digest: str

    @property
    def document(self) -> dict[str, object]:
        return {
            "schema": FINAL_SCHEMA,
            **asdict(self),
            "claim_scope": "EXACT_FROZEN_G1_G5_PANELS_PLUS_CONDITIONAL_EXPECTATIONS_V1",
            "independent_replication_authorized": self.exact_g1_g5_supported,
            "product_promotion_authorized": False,
        }


def build_generalization_dual_authority(
    *,
    registry_path: Path,
    p9_scientific_v2_authority_path: Path,
    axis_authority_paths: Mapping[GeneralizationAxis, Path],
) -> GeneralizationDualAuthority:
    registry = verify_generalization_registry_document(Path(registry_path))
    p9 = verify_p9_scientific_authority_v2_document(Path(p9_scientific_v2_authority_path))
    if p9.get("generalization_evaluation_authorized") is not True:
        raise GeneralizationDualError("primary exact P9 + CCF does not authorize G1-G5 evaluation")
    if set(axis_authority_paths) != set(REQUIRED_AXES):
        raise GeneralizationDualError("final generalization authority requires exact G1-G5")
    rows: list[dict[str, object]] = []
    for axis in REQUIRED_AXES:
        doc = verify_generalization_axis_dual_authority_document(Path(axis_authority_paths[axis]))
        if doc.get("axis") != axis.value or doc.get("registry_digest") != registry.get("registry_digest"):
            raise GeneralizationDualError("G1-G5 authority lineage mismatch")
        registry_row = _axis_registry_row(registry, axis)
        if doc.get("evaluation_manifest_digest") != registry_row.get("evaluation_manifest_digest"):
            raise GeneralizationDualError("G1-G5 authority evaluation identity differs from registry")
        rows.append(doc)
    exact = all(row.get("exact_panel_supported") is True for row in rows)
    conditional = all(
        row.get("expected_effect_supported_under_independence_assumption") is True for row in rows
    )
    axis_digests = tuple(sorted(
        (str(row["axis"]), _sha("axis authority_digest", row.get("authority_digest"))) for row in rows
    ))
    payload = {
        "registry_digest": _sha("registry_digest", registry.get("registry_digest")),
        "p9_scientific_v2_authority_digest": _sha("P9 scientific V2 authority_digest", p9.get("authority_digest")),
        "frozen_dgc_policy_digest": _sha("frozen_dgc_policy_digest", registry.get("frozen_dgc_policy_digest")),
        "axis_authority_digests": [list(row) for row in axis_digests],
        "exact_g1_g5_supported": exact,
        "expected_g1_g5_supported_under_independence_assumption": conditional,
    }
    return GeneralizationDualAuthority(
        registry_digest=payload["registry_digest"],
        p9_scientific_v2_authority_digest=payload["p9_scientific_v2_authority_digest"],
        frozen_dgc_policy_digest=payload["frozen_dgc_policy_digest"],
        axis_authority_digests=axis_digests,
        exact_g1_g5_supported=exact,
        expected_g1_g5_supported_under_independence_assumption=conditional,
        authority_digest=sha256_bytes(canonical_json_bytes(payload)),
    )


def verify_generalization_dual_authority_document(path: Path) -> dict[str, object]:
    candidate = Path(path)
    if candidate.is_symlink() or not candidate.is_file():
        raise GeneralizationDualError("final G1-G5 dual authority must be a regular file")
    try:
        doc = json.loads(candidate.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GeneralizationDualError("invalid final G1-G5 dual authority JSON") from exc
    if not isinstance(doc, dict) or doc.get("schema") != FINAL_SCHEMA:
        raise GeneralizationDualError("unexpected final G1-G5 dual authority schema")
    if doc.get("claim_scope") != "EXACT_FROZEN_G1_G5_PANELS_PLUS_CONDITIONAL_EXPECTATIONS_V1":
        raise GeneralizationDualError("final G1-G5 claim scope mismatch")
    if doc.get("product_promotion_authorized") is not False:
        raise GeneralizationDualError("final G1-G5 authority cannot authorize product promotion")
    keys = (
        "registry_digest", "p9_scientific_v2_authority_digest", "frozen_dgc_policy_digest",
        "axis_authority_digests", "exact_g1_g5_supported",
        "expected_g1_g5_supported_under_independence_assumption",
    )
    try:
        payload = {key: doc[key] for key in keys}
    except KeyError as exc:
        raise GeneralizationDualError("final G1-G5 authority payload incomplete") from exc
    if sha256_bytes(canonical_json_bytes(payload)) != _sha("authority_digest", doc.get("authority_digest")):
        raise GeneralizationDualError("final G1-G5 authority digest mismatch")
    if doc.get("independent_replication_authorized") is not (doc.get("exact_g1_g5_supported") is True):
        raise GeneralizationDualError("replication authority must derive only from exact G1-G5 support")
    return doc
