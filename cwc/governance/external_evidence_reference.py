from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping

from cwc.governance.external_materialization import (
    parse_terminal_dataset_manifest,
    verify_swe_parquet,
)
from cwc.governance.external_source_authority import (
    ExternalSourceAuthority,
    ExternalSourceStage,
    promote_materialized_verified,
)
from cwc.governance.git_tree_reconstruction import (
    GitTreeReconstructionError,
    git_blob_oid_path,
    reconstruct_git_tree,
)
from cwc.governance.materialization_transaction import (
    AtomicEvidenceGeneration,
    canonical_json_bytes,
    file_manifest,
    sha256_bytes,
    sha256_file,
)
from cwc.governance.workload_seal import WorkloadSeal, seal_materialized_workload

REFERENCE_SCHEMA = "DGC_EXTERNAL_EVIDENCE_REFERENCE_V2"
GENERATION_MANIFEST_SCHEMA = "DGC_EVIDENCE_GENERATION_MANIFEST_V2"
MATERIALIZATION_RECEIPT_SCHEMA = "DGC_EXTERNAL_MATERIALIZATION_RECEIPT_V2"
MATERIALIZATION_PROVENANCE_SCHEMA = "DGC_MATERIALIZATION_PROVENANCE_V1"
SOURCE_REGISTRY_SCHEMA = "DGC_EXTERNAL_SOURCE_AUTHORITY_REGISTRY_V1"
_REQUIRED_FAMILIES = frozenset({"SWE_BENCH_VERIFIED", "TERMINAL_BENCH_2_1"})


class ExternalEvidenceError(RuntimeError):
    """Raised when an external evidence generation cannot be imported safely."""


def _sha(name: str, value: object) -> str:
    text = str(value).lower()
    if len(text) != 64 or any(ch not in "0123456789abcdef" for ch in text):
        raise ExternalEvidenceError(f"{name} must be lowercase SHA-256")
    return text


def _git_oid(name: str, value: object) -> str:
    text = str(value).lower()
    if len(text) != 40 or any(ch not in "0123456789abcdef" for ch in text):
        raise ExternalEvidenceError(f"{name} must be lowercase 40-char Git object id")
    return text


def _read_json(path: Path, *, expected_schema: str) -> dict[str, object]:
    if not path.is_file() or path.is_symlink():
        raise ExternalEvidenceError(f"missing regular control file: {path.name}")
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ExternalEvidenceError(f"invalid JSON control file: {path.name}") from exc
    if not isinstance(value, dict) or value.get("schema") != expected_schema:
        raise ExternalEvidenceError(f"unexpected schema for {path.name}")
    return value


def _manifest_rows(rows: object) -> tuple[tuple[str, str, int, int, str], ...]:
    if not isinstance(rows, list):
        raise ExternalEvidenceError("generation manifest files must be a list")
    normalized: list[tuple[str, str, int, int, str]] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            raise ExternalEvidenceError("generation manifest file row must be an object")
        path = str(row.get("path", ""))
        object_type = str(row.get("type", ""))
        try:
            mode = int(row.get("mode"))
            size = int(row.get("bytes"))
        except (TypeError, ValueError) as exc:
            raise ExternalEvidenceError("generation manifest mode/bytes must be integers") from exc
        digest = _sha("generation file sha256", row.get("sha256"))
        if not path or Path(path).is_absolute() or ".." in Path(path).parts:
            raise ExternalEvidenceError("generation manifest path must be relative")
        if path in seen:
            raise ExternalEvidenceError(f"duplicate generation manifest path: {path}")
        if object_type not in {"file", "symlink"}:
            raise ExternalEvidenceError(f"unsupported generation object type: {object_type}")
        if mode < 0 or mode > 0o7777 or size < 0:
            raise ExternalEvidenceError("generation manifest mode/bytes out of range")
        seen.add(path)
        normalized.append((path, object_type, mode, size, digest))
    return tuple(sorted(normalized))


def _source_authority(row: Mapping[str, object]) -> ExternalSourceAuthority:
    verification = row.get("verification")
    if not isinstance(verification, Mapping):
        raise ExternalEvidenceError("source registry verification object missing")
    try:
        authority = ExternalSourceAuthority(
            family_id=str(row["family_id"]),
            stage=ExternalSourceStage.SOURCE_VERIFIED,
            upstream_revision=str(row["upstream_revision"]),
            upstream_identity_digest=str(row["upstream_identity_digest"]),
            source_verification_method=str(verification["verification_method"]),
            source_verification_evidence_digest=str(row["source_verification_evidence_digest"]),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ExternalEvidenceError("source registry authority record is malformed") from exc
    if authority.digest != _sha("registry authority_digest", row.get("authority_digest")):
        raise ExternalEvidenceError(f"source authority digest mismatch for {authority.family_id}")
    return authority


def _require_safe_relative(name: str, value: object) -> Path:
    path = Path(str(value))
    if not str(value) or path.is_absolute() or ".." in path.parts:
        raise ExternalEvidenceError(f"{name} must be a safe relative path")
    return path


def _assert_declared_seal(receipt_row: Mapping[str, object], observed: WorkloadSeal) -> None:
    declared = receipt_row.get("workload_seal")
    if not isinstance(declared, Mapping) or dict(declared) != asdict(observed):
        raise ExternalEvidenceError(f"{observed.family_id}: declared workload seal does not match published payload")


@dataclass(frozen=True, slots=True)
class FamilyMaterializationBinding:
    family_id: str
    source_authority_digest: str
    materialized_authority_digest: str
    materialized_tree_sha256: str
    materialized_task_manifest_sha256: str
    expected_task_count: int
    semantic_verification_digest: str

    def __post_init__(self) -> None:
        family = str(self.family_id).strip()
        if family not in _REQUIRED_FAMILIES:
            raise ExternalEvidenceError("unknown family in materialization binding")
        object.__setattr__(self, "family_id", family)
        for name in (
            "source_authority_digest",
            "materialized_authority_digest",
            "materialized_tree_sha256",
            "materialized_task_manifest_sha256",
            "semantic_verification_digest",
        ):
            object.__setattr__(self, name, _sha(name, getattr(self, name)))
        if self.expected_task_count <= 0:
            raise ExternalEvidenceError("expected_task_count must be > 0")


@dataclass(frozen=True, slots=True)
class ExternalEvidenceReference:
    subject_type: str
    publication_manifest_sha256: str
    payload_manifest_sha256: str
    materialization_receipt_sha256: str
    materialization_provenance_sha256: str
    source_registry_sha256: str
    materializer_sha256: str
    repository_commit: str
    repository_tree: str
    family_bindings: tuple[FamilyMaterializationBinding, ...]
    file_count: int

    def __post_init__(self) -> None:
        if self.subject_type != "DGC_EXTERNAL_MATERIALIZATION_GENERATION_V2":
            raise ExternalEvidenceError("unsupported external evidence subject type")
        for name in (
            "publication_manifest_sha256",
            "payload_manifest_sha256",
            "materialization_receipt_sha256",
            "materialization_provenance_sha256",
            "source_registry_sha256",
            "materializer_sha256",
        ):
            object.__setattr__(self, name, _sha(name, getattr(self, name)))
        object.__setattr__(self, "repository_commit", _git_oid("repository_commit", self.repository_commit))
        object.__setattr__(self, "repository_tree", _git_oid("repository_tree", self.repository_tree))
        if self.file_count < 1:
            raise ExternalEvidenceError("file_count must be >= 1")
        families = [binding.family_id for binding in self.family_bindings]
        if set(families) != _REQUIRED_FAMILIES or len(families) != len(_REQUIRED_FAMILIES):
            raise ExternalEvidenceError("reference must bind exactly the two frozen workload families")
        if families != sorted(families):
            raise ExternalEvidenceError("family bindings must use deterministic sorted order")

    @property
    def payload(self) -> dict[str, object]:
        return {"schema": REFERENCE_SCHEMA, **asdict(self)}

    @property
    def digest(self) -> str:
        return sha256_bytes(canonical_json_bytes(self.payload))

    def binding(self, family_id: str) -> FamilyMaterializationBinding:
        for binding in self.family_bindings:
            if binding.family_id == family_id:
                return binding
        raise ExternalEvidenceError(f"family binding missing: {family_id}")


def reference_document(reference: ExternalEvidenceReference) -> dict[str, object]:
    return {**reference.payload, "reference_digest": reference.digest}


def reference_bytes(reference: ExternalEvidenceReference) -> bytes:
    return json.dumps(reference_document(reference), indent=2, sort_keys=True).encode("utf-8") + b"\n"


def _verify_swe_family(
    *,
    root: Path,
    registry_row: Mapping[str, object],
    receipt_row: Mapping[str, object],
    source: ExternalSourceAuthority,
) -> FamilyMaterializationBinding:
    identity = registry_row.get("identity")
    if not isinstance(identity, Mapping):
        raise ExternalEvidenceError("SWE source identity missing")
    parquet_rel = _require_safe_relative("SWE parquet path", identity.get("parquet_path"))
    parquet = root / "SWE_BENCH_VERIFIED" / parquet_rel
    try:
        verified = verify_swe_parquet(
            parquet,
            expected_sha256=_sha("SWE parquet_sha256", identity.get("parquet_sha256")),
            expected_bytes=None,
            expected_count=int(identity.get("expected_task_count")),
        )
        seal = seal_materialized_workload(
            family_id="SWE_BENCH_VERIFIED",
            root=root / "SWE_BENCH_VERIFIED",
            task_ids=verified.instance_ids,
            expected_task_count=int(identity.get("expected_task_count")),
        )
    except (OSError, TypeError, ValueError, RuntimeError) as exc:
        raise ExternalEvidenceError("SWE payload semantic verification failed") from exc
    if verified.task_manifest_sha256 != seal.task_manifest_sha256:
        raise ExternalEvidenceError("SWE task manifest algorithms disagree")
    parquet_declared = receipt_row.get("parquet")
    expected_parquet = {
        "bytes_size": verified.bytes_size,
        "sha256": verified.sha256,
        "row_count": verified.row_count,
        "instance_id_manifest_sha256": verified.task_manifest_sha256,
    }
    if not isinstance(parquet_declared, Mapping) or dict(parquet_declared) != expected_parquet:
        raise ExternalEvidenceError("SWE receipt parquet evidence does not match published payload")
    _assert_declared_seal(receipt_row, seal)
    materialized = promote_materialized_verified(
        source,
        materialized_tree_sha256=seal.file_tree_sha256,
        materialized_task_manifest_sha256=seal.task_manifest_sha256,
    )
    declared_materialized = _sha("SWE materialized authority", receipt_row.get("authority_digest"))
    if materialized.digest != declared_materialized:
        raise ExternalEvidenceError("SWE materialized authority cannot be reconstructed from canonical source + payload")
    semantic = sha256_bytes(canonical_json_bytes({
        "family_id": "SWE_BENCH_VERIFIED",
        "parquet_sha256": verified.sha256,
        "row_count": verified.row_count,
        "task_manifest_sha256": seal.task_manifest_sha256,
        "workload_tree_sha256": seal.file_tree_sha256,
    }))
    return FamilyMaterializationBinding(
        family_id="SWE_BENCH_VERIFIED",
        source_authority_digest=source.digest,
        materialized_authority_digest=materialized.digest,
        materialized_tree_sha256=seal.file_tree_sha256,
        materialized_task_manifest_sha256=seal.task_manifest_sha256,
        expected_task_count=seal.expected_task_count,
        semantic_verification_digest=semantic,
    )


def _verify_terminal_family(
    *,
    root: Path,
    registry_row: Mapping[str, object],
    receipt_row: Mapping[str, object],
    source: ExternalSourceAuthority,
) -> FamilyMaterializationBinding:
    identity = registry_row.get("identity")
    if not isinstance(identity, Mapping):
        raise ExternalEvidenceError("Terminal source identity missing")
    repo = root / "TERMINAL_BENCH_2_1" / "repo"
    tasks = repo / "tasks"
    dataset = tasks / "dataset.toml"
    try:
        repo_tree = reconstruct_git_tree(repo).root_tree_oid
        tasks_tree = reconstruct_git_tree(tasks).root_tree_oid
        dataset_blob = git_blob_oid_path(dataset)
    except (OSError, GitTreeReconstructionError) as exc:
        raise ExternalEvidenceError("Terminal payload Git reconstruction failed") from exc
    expected_repo_tree = _git_oid("Terminal repository tree", identity.get("tree"))
    expected_tasks_tree = _git_oid("Terminal tasks tree", identity.get("tasks_tree"))
    expected_dataset_blob = _git_oid("Terminal dataset manifest blob", identity.get("dataset_manifest_blob"))
    if repo_tree != expected_repo_tree or tasks_tree != expected_tasks_tree or dataset_blob != expected_dataset_blob:
        raise ExternalEvidenceError("Terminal published bytes do not reconstruct the frozen upstream Git object chain")
    try:
        manifest = parse_terminal_dataset_manifest(
            dataset.read_text(encoding="utf-8"),
            expected_count=int(identity.get("expected_task_count")),
        )
        task_ids = tuple(name for name, _ in manifest.tasks)
        seal = seal_materialized_workload(
            family_id="TERMINAL_BENCH_2_1",
            root=tasks,
            task_ids=task_ids,
            expected_task_count=int(identity.get("expected_task_count")),
        )
    except (OSError, UnicodeError, TypeError, ValueError, RuntimeError) as exc:
        raise ExternalEvidenceError("Terminal task semantic verification failed") from exc
    git_declared = receipt_row.get("git_identity")
    expected_git = {
        "commit": str(identity.get("commit")),
        "repository_tree": expected_repo_tree,
        "tasks_tree": expected_tasks_tree,
        "dataset_manifest_blob": expected_dataset_blob,
    }
    if not isinstance(git_declared, Mapping) or dict(git_declared) != expected_git:
        raise ExternalEvidenceError("Terminal receipt Git identity disagrees with canonical registry")
    dataset_declared = receipt_row.get("dataset_manifest")
    expected_dataset = {
        "dataset_name": manifest.dataset_name,
        "task_count": manifest.task_count,
        "task_name_digest_manifest_sha256": manifest.canonical_task_digest,
    }
    if not isinstance(dataset_declared, Mapping) or dict(dataset_declared) != expected_dataset:
        raise ExternalEvidenceError("Terminal receipt dataset manifest disagrees with published payload")
    _assert_declared_seal(receipt_row, seal)
    materialized = promote_materialized_verified(
        source,
        materialized_tree_sha256=seal.file_tree_sha256,
        materialized_task_manifest_sha256=seal.task_manifest_sha256,
    )
    declared_materialized = _sha("Terminal materialized authority", receipt_row.get("authority_digest"))
    if materialized.digest != declared_materialized:
        raise ExternalEvidenceError("Terminal materialized authority cannot be reconstructed from canonical source + payload")
    semantic = sha256_bytes(canonical_json_bytes({
        "family_id": "TERMINAL_BENCH_2_1",
        "repository_tree_oid": repo_tree,
        "tasks_tree_oid": tasks_tree,
        "dataset_manifest_blob_oid": dataset_blob,
        "dataset_task_digest": manifest.canonical_task_digest,
        "task_manifest_sha256": seal.task_manifest_sha256,
        "workload_tree_sha256": seal.file_tree_sha256,
    }))
    return FamilyMaterializationBinding(
        family_id="TERMINAL_BENCH_2_1",
        source_authority_digest=source.digest,
        materialized_authority_digest=materialized.digest,
        materialized_tree_sha256=seal.file_tree_sha256,
        materialized_task_manifest_sha256=seal.task_manifest_sha256,
        expected_task_count=seal.expected_task_count,
        semantic_verification_digest=semantic,
    )


def verify_materialization_generation(
    generation_root: Path,
    *,
    expected_repository_commit: str,
    expected_repository_tree: str,
    source_registry_path: Path,
) -> ExternalEvidenceReference:
    supplied_root = Path(generation_root)
    if supplied_root.is_symlink():
        raise ExternalEvidenceError("generation_root symlink is not accepted")
    root = supplied_root.resolve()
    if not root.is_dir():
        raise ExternalEvidenceError("generation_root must be a real directory")

    registry_path = Path(source_registry_path)
    registry = _read_json(registry_path, expected_schema=SOURCE_REGISTRY_SCHEMA)
    registry_sha = sha256_file(registry_path)
    registry_families = registry.get("families")
    if not isinstance(registry_families, list):
        raise ExternalEvidenceError("source registry family list missing")
    registry_rows = {
        str(row.get("family_id")): row
        for row in registry_families
        if isinstance(row, Mapping)
    }
    if set(registry_rows) != _REQUIRED_FAMILIES or len(registry_rows) != len(_REQUIRED_FAMILIES):
        raise ExternalEvidenceError("canonical source registry must contain exactly both frozen workload families")

    manifest_path = root / AtomicEvidenceGeneration.MANIFEST_NAME
    receipt_path = root / AtomicEvidenceGeneration.RECEIPT_NAME
    provenance_path = root / AtomicEvidenceGeneration.PROVENANCE_NAME
    manifest = _read_json(manifest_path, expected_schema=GENERATION_MANIFEST_SCHEMA)
    receipt = _read_json(receipt_path, expected_schema=MATERIALIZATION_RECEIPT_SCHEMA)
    provenance = _read_json(provenance_path, expected_schema=MATERIALIZATION_PROVENANCE_SCHEMA)

    observed_publication_rows = file_manifest(root, excluded_names=frozenset({AtomicEvidenceGeneration.MANIFEST_NAME}))
    declared_publication_rows = _manifest_rows(manifest.get("files"))
    if observed_publication_rows != declared_publication_rows:
        raise ExternalEvidenceError("generation publication file manifest mismatch")
    observed_publication_digest = sha256_bytes(canonical_json_bytes(observed_publication_rows))
    if observed_publication_digest != _sha("publication_manifest_sha256", manifest.get("publication_manifest_sha256")):
        raise ExternalEvidenceError("generation publication digest mismatch")

    observed_payload_rows = file_manifest(root, excluded_names=AtomicEvidenceGeneration._CONTROL_FILES)
    observed_payload_digest = sha256_bytes(canonical_json_bytes(observed_payload_rows))
    if observed_payload_digest != _sha("payload_manifest_sha256", manifest.get("payload_manifest_sha256")):
        raise ExternalEvidenceError("generation payload digest mismatch")
    for name, control in (("receipt", receipt), ("provenance", provenance)):
        if _sha(f"{name}.payload_manifest_sha256", control.get("payload_manifest_sha256")) != observed_payload_digest:
            raise ExternalEvidenceError(f"{name} payload binding mismatch")

    expected_commit = _git_oid("expected_repository_commit", expected_repository_commit)
    expected_tree = _git_oid("expected_repository_tree", expected_repository_tree)
    receipt_commit = _git_oid("receipt.repository_commit", receipt.get("repository_commit"))
    receipt_tree = _git_oid("receipt.repository_tree", receipt.get("repository_tree"))
    repository = provenance.get("repository")
    if not isinstance(repository, Mapping):
        raise ExternalEvidenceError("materialization provenance repository binding missing")
    provenance_commit = _git_oid("provenance.repository.git_commit", repository.get("git_commit"))
    provenance_tree = _git_oid("provenance.repository.git_tree", repository.get("git_tree"))
    if {receipt_commit, provenance_commit} != {expected_commit} or {receipt_tree, provenance_tree} != {expected_tree}:
        raise ExternalEvidenceError("materialization repository identity mismatch")

    if receipt.get("execution_authorized") is not False or receipt.get("product_promotion_authorized") is not False:
        raise ExternalEvidenceError("materialization receipt illegally grants downstream authority")
    if provenance.get("execution_authorized") is not False or provenance.get("product_promotion_authorized") is not False:
        raise ExternalEvidenceError("materialization provenance illegally grants downstream authority")
    if provenance.get("claim") != "VERIFIED_MATERIALIZATION_ONLY":
        raise ExternalEvidenceError("materialization provenance claim boundary mismatch")
    if provenance.get("slsa_conformance_claim") is not False:
        raise ExternalEvidenceError("unverified SLSA conformance claim rejected")

    source_registry_sha = _sha("source_registry_sha256", receipt.get("source_registry_sha256"))
    if source_registry_sha != registry_sha:
        raise ExternalEvidenceError("materialization generation was not produced from the supplied canonical source registry")
    materials = provenance.get("materials")
    if not isinstance(materials, Mapping):
        raise ExternalEvidenceError("materialization provenance materials missing")
    if _sha("provenance source registry", materials.get("external_source_registry_sha256")) != source_registry_sha:
        raise ExternalEvidenceError("source registry provenance mismatch")
    materializer_sha = _sha("receipt.materializer_sha256", receipt.get("materializer_sha256"))
    if _sha("provenance.materializer_sha256", materials.get("materializer_sha256")) != materializer_sha:
        raise ExternalEvidenceError("materializer provenance mismatch")

    families = receipt.get("families")
    if not isinstance(families, list):
        raise ExternalEvidenceError("materialization families missing")
    receipt_rows = {
        str(row.get("family_id")): row
        for row in families
        if isinstance(row, Mapping)
    }
    if set(receipt_rows) != _REQUIRED_FAMILIES or len(receipt_rows) != len(_REQUIRED_FAMILIES):
        raise ExternalEvidenceError("materialization receipt must contain exactly both frozen workload families")

    bindings: list[FamilyMaterializationBinding] = []
    for family_id in sorted(_REQUIRED_FAMILIES):
        registry_row = registry_rows[family_id]
        receipt_row = receipt_rows[family_id]
        if registry_row.get("stage") != "SOURCE_VERIFIED" or receipt_row.get("stage") != "MATERIALIZED_VERIFIED":
            raise ExternalEvidenceError(f"invalid authority stage for {family_id}")
        source = _source_authority(registry_row)
        if _sha(f"receipt source authority for {family_id}", receipt_row.get("source_authority_digest")) != source.digest:
            raise ExternalEvidenceError(f"receipt source authority does not match canonical registry for {family_id}")
        if family_id == "SWE_BENCH_VERIFIED":
            binding = _verify_swe_family(root=root, registry_row=registry_row, receipt_row=receipt_row, source=source)
        else:
            binding = _verify_terminal_family(root=root, registry_row=registry_row, receipt_row=receipt_row, source=source)
        bindings.append(binding)

    declared_authorities = materials.get("source_authority_digests")
    if not isinstance(declared_authorities, list) or sorted(str(x).lower() for x in declared_authorities) != sorted(
        binding.source_authority_digest for binding in bindings
    ):
        raise ExternalEvidenceError("source authority provenance mismatch")

    return ExternalEvidenceReference(
        subject_type="DGC_EXTERNAL_MATERIALIZATION_GENERATION_V2",
        publication_manifest_sha256=observed_publication_digest,
        payload_manifest_sha256=observed_payload_digest,
        materialization_receipt_sha256=sha256_file(receipt_path),
        materialization_provenance_sha256=sha256_file(provenance_path),
        source_registry_sha256=source_registry_sha,
        materializer_sha256=materializer_sha,
        repository_commit=expected_commit,
        repository_tree=expected_tree,
        family_bindings=tuple(bindings),
        file_count=len(observed_publication_rows),
    )
