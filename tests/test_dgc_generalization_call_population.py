from __future__ import annotations

import dataclasses
import json
from pathlib import Path

import pytest

import cwc.governance.generalization_dual_authority as dual_module
import cwc.governance.generalization_execution_authority as exec_module
from cwc.governance.generalization_dual_authority import (
    GeneralizationDualError,
    _verify_axis_randomness,
    build_generalization_axis_dual_authority,
)
from cwc.governance.generalization_execution_authority import (
    AXIS_EXECUTION_SCHEMA,
    REPLICATE_RULE,
    GeneralizationExecutionError,
    VerifiedGeneralizationAxisBundle,
    verify_generalization_axis_bundle,
)
from cwc.governance.generalization_registry import (
    AXIS_SCHEMA,
    DGC_ROLE,
    REQUIRED_BASELINE_ROLES,
    GeneralizationAxis,
)
from cwc.governance.materialization_transaction import canonical_json_bytes, sha256_bytes, sha256_file
from cwc.governance.paired_randomness_protocol import INDEPENDENCE_ASSUMPTION, PROTOCOL, paired_seed
from cwc.governance.physical_cost_evidence import (
    PRODUCT_COST_COMPONENTS,
    CostAuthority,
    CostComponentEvidence,
    certify_physical_trial_cost,
)

# No producer in the repository writes G1-G5 AXIS_EXECUTION.json bundles and no
# earlier test called verify_generalization_axis_bundle or
# build_generalization_axis_dual_authority. These falsifiers build the bundle
# by hand, with every digest resealed, so only the check under test can reject.

AXIS = GeneralizationAxis.UNSEEN_TASKS
TASKS = ("task-1", "task-2")
REPLICATES = 2
ROLES = (*REQUIRED_BASELINE_ROLES, DGC_ROLE)
POLICIES = {role: f"policy-{index}" for index, role in enumerate(ROLES)}
REGISTRY_DIGEST = "1" * 64
DGC_POLICY_DIGEST = "2" * 64
SIZING_DIGEST = "3" * 64


def _write(path: Path, payload: object) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return path


def _task_digest() -> str:
    return sha256_bytes(canonical_json_bytes(tuple(sorted(TASKS))))


def _schedule_root(evaluation_digest: str) -> str:
    return sha256_bytes(canonical_json_bytes({
        "axis": AXIS.value,
        "registry_digest": REGISTRY_DIGEST,
        "evaluation_manifest_digest": evaluation_digest,
        "protocol": PROTOCOL,
    }))


def _record_digest(row: dict, *, omit: tuple[str, ...] = ()) -> str:
    # Mirrors the authenticated record_payload of verify_generalization_axis_bundle.
    payload = {
        "task_id": row["task_id"],
        "policy_id": row["policy_id"],
        "replicate": row["replicate"],
        "randomness_protocol": PROTOCOL,
        "replicate_seed": row["replicate_seed"],
        "quality": row["quality"],
        "catastrophic_regret": row["catastrophic_regret"],
        "covered": row["covered"],
        "metric_evidence_path": row["metric_evidence_path"],
        "metric_evidence_sha256": row["metric_evidence_sha256"],
        "live_source_ids": sorted(row["live_source_ids"]),
        "physical_cost_components": sorted(row["physical_cost_components"], key=lambda c: c["component"]),
        "physical_cost_certificate_digest": row["physical_cost_certificate_digest"],
    }
    return sha256_bytes(canonical_json_bytes({k: v for k, v in payload.items() if k not in omit}))


def _seal(root: Path, manifest: dict, *, reseal_records: bool = True) -> None:
    rows = manifest["results"]
    if reseal_records:
        for row in rows:
            row["record_digest"] = _record_digest(row)
    ordered = sorted(rows, key=lambda r: (r["task_id"], r["policy_id"], r["replicate"]))
    metric = sha256_bytes(canonical_json_bytes([
        (r["task_id"], r["policy_id"], r["replicate"], r["quality"], r["catastrophic_regret"], r["covered"],
         r["metric_evidence_sha256"])
        for r in ordered
    ]))
    cost = sha256_bytes(canonical_json_bytes([
        (r["task_id"], r["policy_id"], r["replicate"], r["_cost"], r["physical_cost_certificate_digest"])
        for r in ordered
    ]))
    payload = {
        "axis": AXIS.value,
        "registry_digest": REGISTRY_DIGEST,
        "evaluation_manifest_digest": manifest["evaluation_manifest_digest"],
        "task_population_digest": _task_digest(),
        "frozen_dgc_policy_digest": DGC_POLICY_DIGEST,
        "trial_sizing_authority_digest": SIZING_DIGEST,
        "replicates": REPLICATES,
        "max_physical_cost_usd_per_unit": 1.0,
        "metric_population_digest": metric,
        "physical_cost_population_digest": cost,
        "result_record_digests": [r["record_digest"] for r in ordered],
    }
    manifest["bundle_digest"] = sha256_bytes(canonical_json_bytes(payload))
    on_disk = {
        **manifest,
        "results": [{k: v for k, v in r.items() if k != "_cost"} for r in rows],
    }
    _write(root / "AXIS_EXECUTION.json", on_disk)


class Fixture:
    def __init__(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        self.repo = tmp_path / "repo"
        self.root = tmp_path / "bundle"
        self.registry_path = tmp_path / "registry.json"
        self.sizing_path = tmp_path / "sizing.json"
        axis_semantic = {
            "axis": AXIS.value,
            "replicate_rule": REPLICATE_RULE,
            "max_physical_cost_usd_per_unit": 1.0,
            "randomness_protocol": PROTOCOL,
            "randomness_independence_assumption": INDEPENDENCE_ASSUMPTION,
        }
        self.evaluation_digest = sha256_bytes(canonical_json_bytes(axis_semantic))
        axis_manifest = _write(self.repo / "manifests" / "g1.json", {
            "schema": AXIS_SCHEMA,
            **axis_semantic,
            "evaluation_manifest_digest": self.evaluation_digest,
            "outcomes_observed": False,
            "policy_retuning_allowed": False,
        })
        registry = {
            "registry_digest": REGISTRY_DIGEST,
            "frozen_dgc_policy_digest": DGC_POLICY_DIGEST,
            "generalization_familywise_alpha": 0.05,
            "per_claim_alpha": (0.05 / len(GeneralizationAxis)) / (len(REQUIRED_BASELINE_ROLES) * 3),
            "policy_role_bindings": [[role, POLICIES[role]] for role in ROLES],
            "axes": [{
                "axis": AXIS.value,
                "manifest_path": "manifests/g1.json",
                "manifest_sha256": sha256_file(axis_manifest),
                "evaluation_manifest_digest": self.evaluation_digest,
                "task_population_digest": _task_digest(),
                "quality_noninferiority_margin": 0.05,
                "catastrophic_noninferiority_margin": 0.05,
            }],
        }
        sizing = {"authority_digest": SIZING_DIGEST, "required_trials_per_task": REPLICATES}
        for module in (exec_module, dual_module):
            monkeypatch.setattr(module, "verify_generalization_registry_document", lambda _: registry)
        monkeypatch.setattr(exec_module, "verify_trial_sizing_authority_document", lambda _: sizing)
        _write(self.root / "costs" / "meter.json", {"meter": "fixture"})
        self.manifest: dict = {
            "schema": AXIS_EXECUTION_SCHEMA,
            "axis": AXIS.value,
            "registry_digest": REGISTRY_DIGEST,
            "evaluation_manifest_digest": self.evaluation_digest,
            "task_population_digest": _task_digest(),
            "frozen_dgc_policy_digest": DGC_POLICY_DIGEST,
            "trial_sizing_authority_digest": SIZING_DIGEST,
            "replicates": REPLICATES,
            "policy_retuned": False,
            "product_promotion_authorized": False,
            "results": [],
        }
        counter = 0
        for task in TASKS:
            for role in ROLES:
                for replicate in range(REPLICATES):
                    counter += 1
                    self.manifest["results"].append(
                        self._row(task, role, replicate, source=f"provider:req-{counter}")
                    )
        _seal(self.root, self.manifest)

    def _row(self, task: str, role: str, replicate: int, *, source: str) -> dict:
        policy = POLICIES[role]
        is_dgc = role == DGC_ROLE
        model_usd = 0.1 if is_dgc else 0.3 + 0.01 * replicate
        meter_rel = "costs/meter.json"
        meter_digest = sha256_file(self.root / meter_rel)
        evidence = {
            component: CostComponentEvidence(
                component=component,
                value_usd=model_usd if component == "model_usd" else 0.0,
                authority=CostAuthority.PROVIDER_METER if component == "model_usd" else CostAuthority.ZERO_BY_CONTRACT,
                source_digest=meter_digest,
            )
            for component in PRODUCT_COST_COMPONENTS
        }
        certificate = certify_physical_trial_cost(
            trial_id=f"{AXIS.value}:{task}:{policy}:{replicate}", evidence=evidence
        )
        metric_rel = f"metrics/{task}-{policy}-{replicate}.json"
        metric = _write(self.root / metric_rel, {"task": task, "policy": policy, "replicate": replicate})
        return {
            "task_id": task,
            "policy_id": policy,
            "replicate": replicate,
            "randomness_protocol": PROTOCOL,
            "replicate_seed": paired_seed(
                root_digest=_schedule_root(self.evaluation_digest), task_id=task, replicate=replicate
            ),
            "quality": 0.9 if is_dgc else 0.6,
            "catastrophic_regret": 0.01 if is_dgc else 0.05,
            "covered": True,
            "metric_evidence_path": metric_rel,
            "metric_evidence_sha256": sha256_file(metric),
            "live_source_ids": [source],
            "physical_cost_components": [
                {
                    "component": row.component,
                    "value_usd": row.value_usd,
                    "authority": row.authority.value,
                    "source_path": meter_rel,
                    "source_digest": row.source_digest,
                }
                for row in certificate.component_evidence
            ],
            "physical_cost_certificate_digest": certificate.digest,
            "_cost": certificate.cost.total_operational_usd,
        }

    def verify(self) -> VerifiedGeneralizationAxisBundle:
        return verify_generalization_axis_bundle(
            self.root,
            repository_root=self.repo,
            registry_path=self.registry_path,
            trial_sizing_authority_path=self.sizing_path,
        )

    def build_dual(self):
        return build_generalization_axis_dual_authority(
            self.root,
            repository_root=self.repo,
            registry_path=self.registry_path,
            trial_sizing_authority_path=self.sizing_path,
        )

    def reseal(self, **kwargs: bool) -> None:
        _seal(self.root, self.manifest, **kwargs)


@pytest.fixture
def fx(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Fixture:
    return Fixture(tmp_path, monkeypatch)


# --- base verifier: authenticated record_payload --------------------------------


def test_complete_axis_bundle_binds_seed_and_live_sources_into_results(fx: Fixture):
    bundle = fx.verify()
    assert len(bundle.results) == len(TASKS) * len(ROLES) * REPLICATES
    schedule_root = _schedule_root(fx.evaluation_digest)
    for row in bundle.results:
        assert row.replicate_seed == paired_seed(
            root_digest=schedule_root, task_id=row.task_id, replicate=row.replicate
        )
        assert len(row.live_source_ids) == 1 and row.live_source_ids[0].startswith("provider:")
    authority = fx.build_dual()
    assert authority.randomness_protocol == PROTOCOL
    assert authority.paired_observations_per_baseline == len(TASKS) * REPLICATES


def test_missing_randomness_protocol_is_rejected(fx: Fixture):
    del fx.manifest["results"][0]["randomness_protocol"]
    fx.reseal()
    with pytest.raises(GeneralizationExecutionError, match="lacks frozen paired randomness protocol"):
        fx.verify()


def test_resealed_off_schedule_seed_is_rejected(fx: Fixture):
    fx.manifest["results"][0]["replicate_seed"] += 1
    fx.reseal()
    with pytest.raises(GeneralizationExecutionError, match="replicate_seed differs from frozen paired schedule"):
        fx.verify()


@pytest.mark.parametrize("seed", ["123", 1.0, True, None])
def test_non_integer_seed_is_rejected(fx: Fixture, seed: object):
    fx.manifest["results"][0]["replicate_seed"] = seed
    fx.reseal()
    with pytest.raises(GeneralizationExecutionError, match="replicate_seed must be an integer"):
        fx.verify()


def test_live_source_reused_across_units_is_rejected(fx: Fixture):
    rows = fx.manifest["results"]
    rows[1]["live_source_ids"] = list(rows[0]["live_source_ids"])
    fx.reseal()
    with pytest.raises(GeneralizationExecutionError, match="live source identity reused across work units"):
        fx.verify()


@pytest.mark.parametrize("value", [None, [], "provider:req-1"])
def test_missing_live_source_population_is_rejected(fx: Fixture, value: object):
    if value is None:
        del fx.manifest["results"][0]["live_source_ids"]
    else:
        fx.manifest["results"][0]["live_source_ids"] = value
    fx.reseal(reseal_records=False)
    with pytest.raises(GeneralizationExecutionError, match="live_source_ids must be a non-empty list"):
        fx.verify()


@pytest.mark.parametrize(
    "source",
    [
        "provider:",
        "provider: ",
        " provider:req-x",
        "runtime:call-1:" + "z" * 64,
        "runtime::" + "a" * 64,
        "runtime:call-1",
        "trace:req-x",
        "req-x",
        7,
    ],
)
def test_untyped_live_source_identity_is_rejected(fx: Fixture, source: object):
    fx.manifest["results"][0]["live_source_ids"] = [source]
    fx.reseal(reseal_records=False)
    with pytest.raises(GeneralizationExecutionError, match="live source identity must be"):
        fx.verify()


def test_runtime_typed_live_source_identity_is_accepted(fx: Fixture):
    fx.manifest["results"][0]["live_source_ids"] = ["runtime:harbor:session-1:" + "a" * 64]
    fx.reseal()
    bundle = fx.verify()
    assert any(row.live_source_ids == ("runtime:harbor:session-1:" + "a" * 64,) for row in bundle.results)


def test_duplicate_live_source_within_unit_is_rejected(fx: Fixture):
    row = fx.manifest["results"][0]
    row["live_source_ids"] = [row["live_source_ids"][0], row["live_source_ids"][0]]
    fx.reseal(reseal_records=False)
    with pytest.raises(GeneralizationExecutionError, match="duplicate live source identity within work unit"):
        fx.verify()


@pytest.mark.parametrize(
    "omitted",
    [("live_source_ids",), ("randomness_protocol", "replicate_seed")],
)
def test_record_digest_must_authenticate_call_population_and_randomness(
    fx: Fixture, omitted: tuple[str, ...]
):
    # The fields stay on disk unchanged; every record digest (and the bundle
    # digest over them) is resealed over a payload that omits them. A verifier
    # whose record_payload does not cover these fields would accept this bundle.
    for row in fx.manifest["results"]:
        row["record_digest"] = _record_digest(row, omit=omitted)
    fx.reseal(reseal_records=False)
    with pytest.raises(GeneralizationExecutionError, match="generalization result record digest mismatch"):
        fx.verify()


# --- dual authority consumes verified results -----------------------------------


def _replace_first(bundle: VerifiedGeneralizationAxisBundle, **changes: object) -> VerifiedGeneralizationAxisBundle:
    first = dataclasses.replace(bundle.results[0], **changes)
    return dataclasses.replace(bundle, results=(first, *bundle.results[1:]))


def _replay(bundle: VerifiedGeneralizationAxisBundle) -> tuple[str, int]:
    return _verify_axis_randomness(
        bundle,
        axis=AXIS,
        task_ids=TASKS,
        policy_ids=tuple(sorted(POLICIES.values())),
    )


def test_dual_replay_counts_verified_sources(fx: Fixture):
    _, sources = _replay(fx.verify())
    assert sources == len(TASKS) * len(ROLES) * REPLICATES


def test_dual_rejects_verified_seed_off_schedule(fx: Fixture):
    bundle = _replace_first(fx.verify(), replicate_seed=fx.verify().results[0].replicate_seed + 1)
    with pytest.raises(GeneralizationDualError, match="verified replicate seed differs"):
        _replay(bundle)


def test_dual_rejects_empty_verified_source_population(fx: Fixture):
    with pytest.raises(GeneralizationDualError, match="verified live source population missing"):
        _replay(_replace_first(fx.verify(), live_source_ids=()))


def test_dual_rejects_verified_source_reuse(fx: Fixture):
    bundle = fx.verify()
    with pytest.raises(GeneralizationDualError, match="live source identity reused across G1-G5 work units"):
        _replay(_replace_first(bundle, live_source_ids=bundle.results[1].live_source_ids))


def test_dual_authority_uses_verified_results_not_raw_axis_execution(
    fx: Fixture, monkeypatch: pytest.MonkeyPatch
):
    # AXIS_EXECUTION.json on disk stays valid; only the verified object handed to
    # the dual authority carries an off-schedule seed. A dual authority that
    # re-reads the raw file would accept it.
    verified = fx.verify()
    tampered = _replace_first(verified, replicate_seed=verified.results[0].replicate_seed + 1)
    monkeypatch.setattr(dual_module, "verify_generalization_axis_bundle", lambda *_, **__: tampered)
    with pytest.raises(GeneralizationDualError, match="verified replicate seed differs"):
        fx.build_dual()
