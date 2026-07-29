from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
from dataclasses import replace
from pathlib import Path
from pathlib import PurePosixPath
from types import ModuleType

import pytest
from jsonschema import ValidationError

from pdf_ocr import model_lock as model_lock_module
from pdf_ocr.model_lock import (
    LockedArtifact,
    LockedFile,
    ModelLockError,
    artifact_path,
    docling_artifacts_root,
    load_model_lock,
    optional_artifact_path,
    revalidate_locked_artifacts,
)


RUNTIME_VERSIONS = {
    "rapidocr": "3.9.2",
    "onnxruntime": "1.28.0",
    "docling": "2.115.0",
    "docling-ibm-models": "3.13.3",
}
ROLE_COMPONENTS = {
    "rapidocr_det": "RAPIDOCR",
    "rapidocr_cls": "RAPIDOCR",
    "rapidocr_rec": "RAPIDOCR",
    "rapidocr_rec_keys": "RAPIDOCR",
    "rapidocr_font": "RAPIDOCR",
    "docling_layout": "DOCLING",
    "tableformer": "TABLEFORMER",
}


def _digest(data: bytes) -> str:
    return f"sha256:{hashlib.sha256(data).hexdigest()}"


def _write_valid_lock(tmp_path: Path) -> tuple[Path, Path, dict[str, object]]:
    model_home = tmp_path / "models"
    model_home.mkdir()
    artifacts: list[dict[str, object]] = []
    for role, component in ROLE_COMPONENTS.items():
        root = f"docling/{role}" if role in {"docling_layout", "tableformer"} else role
        artifact_root = model_home / root
        artifact_root.mkdir(parents=True)
        filename = f"{role}.bin"
        data = role.encode("utf-8")
        (artifact_root / filename).write_bytes(data)
        artifacts.append(
            {
                "component": component,
                "role": role,
                "name": f"{role}-model",
                "source_url": f"https://models.example.test/{role}",
                "license": "UPSTREAM-LICENSE",
                "root": root,
                "entrypoint": filename,
                "files": [
                    {
                        "path": filename,
                        "bytes": len(data),
                        "sha256": _digest(data),
                    }
                ],
            }
        )
    payload: dict[str, object] = {
        "schema_version": "2.0.0",
        "generated_at": "2026-07-28T00:00:00+09:00",
        "cache_environment_variable": "PDF_OCR_MODEL_HOME",
        "packages": [
            {"name": name, "version": version}
            for name, version in RUNTIME_VERSIONS.items()
        ],
        "artifacts": artifacts,
    }
    lock_path = tmp_path / "models.lock.json"
    lock_path.write_text(json.dumps(payload), encoding="utf-8")
    return lock_path, model_home, payload


def _rewrite_lock(lock_path: Path, payload: dict[str, object]) -> None:
    lock_path.write_text(json.dumps(payload), encoding="utf-8")


def _artifact(payload: dict[str, object], role: str) -> dict[str, object]:
    return next(
        item
        for item in payload["artifacts"]  # type: ignore[index, union-attr]
        if item["role"] == role
    )


def _load_generator() -> ModuleType:
    script = Path(__file__).parents[1] / "scripts" / "generate_model_lock.py"
    spec = importlib.util.spec_from_file_location("generate_model_lock", script)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _write_receipt_from_lock(
    tmp_path: Path,
    lock_payload: dict[str, object],
) -> Path:
    artifacts = [
        {key: value for key, value in artifact.items() if key != "files"}
        for artifact in lock_payload["artifacts"]
    ]
    receipt_path = tmp_path / "source-receipt.json"
    receipt_path.write_text(
        json.dumps({"schema_version": "1.0.0", "artifacts": artifacts}),
        encoding="utf-8",
    )
    return receipt_path


def _directory_link(link: Path, target: Path) -> None:
    try:
        link.symlink_to(target, target_is_directory=True)
        return
    except OSError:
        if os.name != "nt":
            raise
    result = subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(link), str(target)],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise OSError(result.stderr or result.stdout)


def test_valid_lock_returns_only_verified_artifacts(tmp_path: Path) -> None:
    lock_path, model_home, _ = _write_valid_lock(tmp_path)

    artifacts = load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)

    assert {artifact.role for artifact in artifacts} == set(ROLE_COMPONENTS)
    assert artifact_path(artifacts, "rapidocr_rec").read_bytes() == b"rapidocr_rec"
    assert optional_artifact_path(artifacts, "rapidocr_cls") is not None
    assert docling_artifacts_root(artifacts) == (model_home / "docling").resolve()
    rec = next(item for item in artifacts if item.role == "rapidocr_rec")
    assert rec.model_home == model_home.resolve()
    assert rec.root_relative_path == PurePosixPath("rapidocr_rec")
    assert rec.entrypoint_relative_path == PurePosixPath("rapidocr_rec.bin")
    assert rec.root == (model_home / "rapidocr_rec").resolve()
    assert rec.files[0].relative_path.as_posix() == "rapidocr_rec.bin"


def test_component_must_match_locked_role(tmp_path: Path) -> None:
    lock_path, model_home, payload = _write_valid_lock(tmp_path)
    _artifact(payload, "rapidocr_det")["component"] = "DOCLING"
    _rewrite_lock(lock_path, payload)

    with pytest.raises(ModelLockError, match="component/role"):
        load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)


def test_model_home_itself_must_not_be_a_link_or_reparse_point(
    tmp_path: Path,
) -> None:
    lock_path, model_home, _ = _write_valid_lock(tmp_path)
    linked_home = tmp_path / "linked-models"
    try:
        _directory_link(linked_home, model_home)
    except OSError as error:
        pytest.skip(f"directory links unavailable: {error}")

    with pytest.raises(ModelLockError, match="model home.*link|reparse"):
        load_model_lock(lock_path, linked_home, RUNTIME_VERSIONS)


def test_regular_model_file_hardlinks_are_rejected(tmp_path: Path) -> None:
    lock_path, model_home, _ = _write_valid_lock(tmp_path)
    source = model_home / "rapidocr_rec" / "rapidocr_rec.bin"
    os.link(source, tmp_path / "alias.bin")

    with pytest.raises(ModelLockError, match="hardlink"):
        load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)


def test_revalidation_detects_bytes_changed_after_lock_load(
    tmp_path: Path,
) -> None:
    lock_path, model_home, _ = _write_valid_lock(tmp_path)
    artifacts = load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)
    artifact_path(artifacts, "rapidocr_rec").write_bytes(b"tampered")

    with pytest.raises(ModelLockError, match="size|SHA-256"):
        model_lock_module.revalidate_locked_artifacts(artifacts)


def test_schema_is_validated_before_filesystem_access(tmp_path: Path) -> None:
    lock_path = tmp_path / "models.lock.json"
    lock_path.write_text('{"schema_version": "wrong"}', encoding="utf-8")

    with pytest.raises(ValidationError):
        load_model_lock(lock_path, tmp_path / "missing-model-home", RUNTIME_VERSIONS)


def test_model_lock_rejects_malformed_https_uri(tmp_path: Path) -> None:
    lock_path, model_home, payload = _write_valid_lock(tmp_path)
    _artifact(payload, "rapidocr_det")["source_url"] = "https://[invalid"
    _rewrite_lock(lock_path, payload)

    with pytest.raises(ValidationError):
        load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)


@pytest.mark.parametrize(
    "invalid_uri",
    (
        "https://example.test/%ZZ",
        "https://example.test:99999/model.bin",
        "https://예시.테스트/model.bin",
        "https://example.test/path[bad]",
        "https://user@@example.test/model",
    ),
)
def test_model_lock_rejects_non_rfc3986_https_uri(
    tmp_path: Path,
    invalid_uri: str,
) -> None:
    lock_path, model_home, payload = _write_valid_lock(tmp_path)
    _artifact(payload, "rapidocr_det")["source_url"] = invalid_uri
    _rewrite_lock(lock_path, payload)

    with pytest.raises(ValidationError):
        load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)


@pytest.mark.parametrize(
    "source_url",
    (
        "https://www.modelscope.cn/models/RapidAI/RapidOCR/resolve/v3.9.2/"
        "onnx/PP-OCRv5/det/ch_PP-OCRv5_det_mobile.onnx",
        "https://github.com/google/fonts/tree/"
        "7ff85c87f93ea6cca5f41c69f2e4edcb90240f26/ofl/notosanskr",
        "https://raw.githubusercontent.com/google/fonts/"
        "7ff85c87f93ea6cca5f41c69f2e4edcb90240f26/ofl/notosanskr/"
        "NotoSansKR%5Bwght%5D.ttf",
        "https://huggingface.co/docling-project/docling-models/tree/"
        "fc0f2d45e2218ea24bce5045f58a389aed16dc23/"
        "model_artifacts/tableformer/accurate",
    ),
)
def test_model_lock_accepts_official_provenance_https_subset(
    tmp_path: Path,
    source_url: str,
) -> None:
    lock_path, model_home, payload = _write_valid_lock(tmp_path)
    _artifact(payload, "rapidocr_det")["source_url"] = source_url
    _rewrite_lock(lock_path, payload)

    artifacts = load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)

    assert artifact_path(artifacts, "rapidocr_det").is_file()


def test_model_lock_rejects_malformed_generated_at(tmp_path: Path) -> None:
    lock_path, model_home, payload = _write_valid_lock(tmp_path)
    payload["generated_at"] = "not-a-date-time"
    _rewrite_lock(lock_path, payload)

    with pytest.raises(ValidationError):
        load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)


def test_model_lock_rejects_basic_iso_generated_at(tmp_path: Path) -> None:
    lock_path, model_home, payload = _write_valid_lock(tmp_path)
    payload["generated_at"] = "20260728T000000+09:00"
    _rewrite_lock(lock_path, payload)

    with pytest.raises(ValidationError):
        load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)


@pytest.mark.parametrize(
    "required_field",
    (
        "schema_version",
        "generated_at",
        "cache_environment_variable",
        "packages",
        "artifacts",
    ),
)
def test_model_lock_rejects_missing_top_level_required_field(
    tmp_path: Path,
    required_field: str,
) -> None:
    lock_path, model_home, payload = _write_valid_lock(tmp_path)
    payload.pop(required_field)
    _rewrite_lock(lock_path, payload)

    with pytest.raises(ValidationError):
        load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)


def test_model_lock_rejects_top_level_additional_property(tmp_path: Path) -> None:
    lock_path, model_home, payload = _write_valid_lock(tmp_path)
    payload["unexpected"] = True
    _rewrite_lock(lock_path, payload)

    with pytest.raises(ValidationError):
        load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)


@pytest.mark.parametrize(
    "required_field",
    (
        "component",
        "role",
        "name",
        "source_url",
        "license",
        "root",
        "entrypoint",
        "files",
    ),
)
def test_model_lock_rejects_missing_artifact_required_field(
    tmp_path: Path,
    required_field: str,
) -> None:
    lock_path, model_home, payload = _write_valid_lock(tmp_path)
    _artifact(payload, "rapidocr_det").pop(required_field)
    _rewrite_lock(lock_path, payload)

    with pytest.raises(ValidationError):
        load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)


def test_model_lock_rejects_artifact_additional_property(tmp_path: Path) -> None:
    lock_path, model_home, payload = _write_valid_lock(tmp_path)
    _artifact(payload, "rapidocr_det")["unexpected"] = True
    _rewrite_lock(lock_path, payload)

    with pytest.raises(ValidationError):
        load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)


@pytest.mark.parametrize("required_field", ("path", "bytes", "sha256"))
def test_model_lock_rejects_missing_file_required_field(
    tmp_path: Path,
    required_field: str,
) -> None:
    lock_path, model_home, payload = _write_valid_lock(tmp_path)
    _artifact(payload, "rapidocr_det")["files"][0].pop(required_field)
    _rewrite_lock(lock_path, payload)

    with pytest.raises(ValidationError):
        load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)


def test_model_lock_rejects_file_additional_property(tmp_path: Path) -> None:
    lock_path, model_home, payload = _write_valid_lock(tmp_path)
    _artifact(payload, "rapidocr_det")["files"][0]["unexpected"] = True
    _rewrite_lock(lock_path, payload)

    with pytest.raises(ValidationError):
        load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)


@pytest.mark.parametrize(
    ("field", "value"),
    (("component", "PADDLEOCR"), ("role", "unknown_role")),
)
def test_model_lock_rejects_unknown_component_or_role(
    tmp_path: Path,
    field: str,
    value: str,
) -> None:
    lock_path, model_home, payload = _write_valid_lock(tmp_path)
    _artifact(payload, "rapidocr_det")[field] = value
    _rewrite_lock(lock_path, payload)

    with pytest.raises(ValidationError):
        load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)


@pytest.mark.parametrize(
    "invalid_path",
    (
        "/absolute.bin",
        "C:/absolute.bin",
        "../escape.bin",
        "nested/../escape.bin",
        "nested\\file.bin",
        "./file.bin",
        "nested/./file.bin",
        ".",
    ),
)
def test_model_lock_rejects_non_relative_posix_file_path(
    tmp_path: Path,
    invalid_path: str,
) -> None:
    lock_path, model_home, payload = _write_valid_lock(tmp_path)
    _artifact(payload, "rapidocr_det")["files"][0]["path"] = invalid_path
    _rewrite_lock(lock_path, payload)

    with pytest.raises(ValidationError):
        load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)


@pytest.mark.parametrize(
    "invalid_digest",
    (
        "0" * 64,
        "sha256:abc",
        "sha256:" + ("G" * 64),
        "SHA256:" + ("0" * 64),
    ),
)
def test_model_lock_rejects_malformed_sha256(
    tmp_path: Path,
    invalid_digest: str,
) -> None:
    lock_path, model_home, payload = _write_valid_lock(tmp_path)
    _artifact(payload, "rapidocr_det")["files"][0]["sha256"] = invalid_digest
    _rewrite_lock(lock_path, payload)

    with pytest.raises(ValidationError):
        load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)


@pytest.mark.parametrize("package_name", tuple(RUNTIME_VERSIONS))
def test_each_runtime_package_version_mismatch_is_rejected(
    tmp_path: Path, package_name: str
) -> None:
    lock_path, model_home, payload = _write_valid_lock(tmp_path)
    package = next(
        item for item in payload["packages"] if item["name"] == package_name  # type: ignore[index, union-attr]
    )
    package["version"] = "0.0.0"
    _rewrite_lock(lock_path, payload)

    with pytest.raises(ModelLockError, match="package versions"):
        load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)


def test_missing_required_role_is_rejected(tmp_path: Path) -> None:
    lock_path, model_home, payload = _write_valid_lock(tmp_path)
    payload["artifacts"].remove(_artifact(payload, "rapidocr_font"))  # type: ignore[union-attr]
    _rewrite_lock(lock_path, payload)

    with pytest.raises(ModelLockError, match="missing roles.*rapidocr_font"):
        load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)


def test_duplicate_role_is_rejected(tmp_path: Path) -> None:
    lock_path, model_home, payload = _write_valid_lock(tmp_path)
    duplicate = dict(_artifact(payload, "rapidocr_rec"))
    duplicate["name"] = "duplicate-recognizer"
    payload["artifacts"].append(duplicate)  # type: ignore[union-attr]
    _rewrite_lock(lock_path, payload)

    with pytest.raises(ModelLockError, match="duplicate model role"):
        load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)


@pytest.mark.parametrize(
    ("field", "value"),
    (("source_url", "http://models.example.test/model"), ("license", "")),
)
def test_untrusted_source_metadata_is_rejected(
    tmp_path: Path, field: str, value: str
) -> None:
    lock_path, model_home, payload = _write_valid_lock(tmp_path)
    _artifact(payload, "rapidocr_det")[field] = value
    _rewrite_lock(lock_path, payload)

    with pytest.raises(ValidationError):
        load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)


def test_zero_byte_file_is_rejected_by_schema(tmp_path: Path) -> None:
    lock_path, model_home, payload = _write_valid_lock(tmp_path)
    record = _artifact(payload, "rapidocr_det")["files"][0]
    record["bytes"] = 0
    _rewrite_lock(lock_path, payload)

    with pytest.raises(ValidationError):
        load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)


@pytest.mark.parametrize(
    ("field", "value"),
    (
        ("root", "../outside"),
        ("root", "C:/outside"),
        ("entrypoint", "../outside.bin"),
        ("entrypoint", "C:/outside.bin"),
    ),
)
def test_absolute_or_parent_escape_path_is_rejected(
    tmp_path: Path, field: str, value: str
) -> None:
    lock_path, model_home, payload = _write_valid_lock(tmp_path)
    _artifact(payload, "rapidocr_rec")[field] = value
    _rewrite_lock(lock_path, payload)

    with pytest.raises((ValidationError, ModelLockError)):
        load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)


def test_symlink_inside_artifact_is_rejected(tmp_path: Path) -> None:
    lock_path, model_home, _ = _write_valid_lock(tmp_path)
    external = tmp_path / "external"
    external.mkdir()
    (external / "external.bin").write_bytes(b"external")
    link = model_home / "rapidocr_det" / "linked"
    _directory_link(link, external)

    with pytest.raises(ModelLockError, match="symlink"):
        load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)


def test_symlink_in_artifact_root_components_is_rejected(tmp_path: Path) -> None:
    lock_path, model_home, payload = _write_valid_lock(tmp_path)
    linked_parent = model_home / "linked-parent"
    _directory_link(linked_parent, model_home)
    _artifact(payload, "rapidocr_det")["root"] = "linked-parent/rapidocr_det"
    _rewrite_lock(lock_path, payload)

    with pytest.raises(ModelLockError, match="symlink"):
        load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)


def test_unlocked_or_missing_file_is_rejected(tmp_path: Path) -> None:
    lock_path, model_home, _ = _write_valid_lock(tmp_path)
    (model_home / "rapidocr_det" / "unlocked.bin").write_bytes(b"unlocked")

    with pytest.raises(ModelLockError, match="file list"):
        load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)


def test_model_file_size_mismatch_is_rejected(tmp_path: Path) -> None:
    lock_path, model_home, payload = _write_valid_lock(tmp_path)
    _artifact(payload, "rapidocr_rec")["files"][0]["bytes"] += 1
    _rewrite_lock(lock_path, payload)

    with pytest.raises(ModelLockError, match="size"):
        load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)


def test_model_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    lock_path, model_home, payload = _write_valid_lock(tmp_path)
    _artifact(payload, "rapidocr_rec")["files"][0]["sha256"] = (
        "sha256:" + ("0" * 64)
    )
    _rewrite_lock(lock_path, payload)

    with pytest.raises(ModelLockError, match="SHA-256"):
        load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)


def test_entrypoint_must_be_locked(tmp_path: Path) -> None:
    lock_path, model_home, payload = _write_valid_lock(tmp_path)
    artifact = _artifact(payload, "rapidocr_rec")
    artifact["entrypoint"] = "factory.onnx"
    factory = model_home / artifact["root"] / "factory.onnx"
    factory.write_bytes(b"factory")
    _rewrite_lock(lock_path, payload)

    with pytest.raises(ModelLockError, match="entrypoint"):
        load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)


def test_factory_cannot_request_unlocked_role(tmp_path: Path) -> None:
    lock_path, model_home, _ = _write_valid_lock(tmp_path)
    artifacts = load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)

    with pytest.raises(ModelLockError, match="missing model role"):
        artifact_path(artifacts, "unknown_role")


def test_directory_entrypoint_is_allowed_when_all_descendants_are_locked(
    tmp_path: Path,
) -> None:
    lock_path, model_home, payload = _write_valid_lock(tmp_path)
    artifact = _artifact(payload, "docling_layout")
    artifact["entrypoint"] = "."
    _rewrite_lock(lock_path, payload)

    artifacts = load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)

    assert artifact_path(artifacts, "docling_layout").is_dir()


def test_build_lock_uses_receipt_and_uv_lock_metadata(tmp_path: Path) -> None:
    _, model_home, lock_payload = _write_valid_lock(tmp_path)
    receipt = {
        "schema_version": "1.0.0",
        "artifacts": [
            {key: value for key, value in artifact.items() if key != "files"}
            for artifact in lock_payload["artifacts"]
        ],
    }
    receipt_path = tmp_path / "source-receipt.json"
    receipt_path.write_text(json.dumps(receipt), encoding="utf-8")
    uv_lock = tmp_path / "uv.lock"
    uv_lock.write_text(
        "\n".join(
            f'[[package]]\nname = "{name}"\nversion = "{version}"'
            for name, version in RUNTIME_VERSIONS.items()
        ),
        encoding="utf-8",
    )

    payload = _load_generator().build_lock(model_home, receipt_path, uv_lock)

    assert payload["schema_version"] == "2.0.0"
    assert payload["cache_environment_variable"] == "PDF_OCR_MODEL_HOME"
    assert {
        item["name"]: item["version"] for item in payload["packages"]
    } == RUNTIME_VERSIONS
    generated_rec = next(
        item for item in payload["artifacts"] if item["role"] == "rapidocr_rec"
    )
    assert generated_rec["source_url"] == "https://models.example.test/rapidocr_rec"
    assert generated_rec["license"] == "UPSTREAM-LICENSE"
    assert generated_rec["files"] == [
        {
            "path": "rapidocr_rec.bin",
            "bytes": len(b"rapidocr_rec"),
            "sha256": _digest(b"rapidocr_rec"),
        }
    ]


def test_build_lock_sorts_recursive_files_and_calculates_metadata(
    tmp_path: Path,
) -> None:
    _, model_home, lock_payload = _write_valid_lock(tmp_path)
    artifact_root = model_home / "rapidocr_det"
    (artifact_root / "a.bin").write_bytes(b"a")
    nested = artifact_root / "nested"
    nested.mkdir()
    (nested / "b.bin").write_bytes(b"nested-b")
    receipt_path = _write_receipt_from_lock(tmp_path, lock_payload)

    payload = _load_generator().build_lock(
        model_home,
        receipt_path,
        Path(__file__).parents[1] / "uv.lock",
    )

    generated = next(
        item for item in payload["artifacts"] if item["role"] == "rapidocr_det"
    )
    assert generated["files"] == [
        {"path": "a.bin", "bytes": 1, "sha256": _digest(b"a")},
        {
            "path": "nested/b.bin",
            "bytes": len(b"nested-b"),
            "sha256": _digest(b"nested-b"),
        },
        {
            "path": "rapidocr_det.bin",
            "bytes": len(b"rapidocr_det"),
            "sha256": _digest(b"rapidocr_det"),
        },
    ]


def test_build_lock_rejects_link_or_windows_reparse_point(
    tmp_path: Path,
) -> None:
    _, model_home, lock_payload = _write_valid_lock(tmp_path)
    external = tmp_path / "external"
    external.mkdir()
    (external / "external.bin").write_bytes(b"external")
    _directory_link(model_home / "rapidocr_det" / "linked", external)
    receipt_path = _write_receipt_from_lock(tmp_path, lock_payload)

    with pytest.raises(ModelLockError, match="symlink"):
        _load_generator().build_lock(
            model_home,
            receipt_path,
            Path(__file__).parents[1] / "uv.lock",
        )


def test_build_lock_rejects_empty_artifact(tmp_path: Path) -> None:
    _, model_home, lock_payload = _write_valid_lock(tmp_path)
    (model_home / "rapidocr_det" / "rapidocr_det.bin").unlink()
    receipt_path = _write_receipt_from_lock(tmp_path, lock_payload)

    with pytest.raises(ModelLockError, match="empty"):
        _load_generator().build_lock(
            model_home,
            receipt_path,
            Path(__file__).parents[1] / "uv.lock",
        )


def test_build_lock_rejects_empty_nested_directory(tmp_path: Path) -> None:
    _, model_home, lock_payload = _write_valid_lock(tmp_path)
    (model_home / "rapidocr_det" / "empty").mkdir()
    receipt_path = _write_receipt_from_lock(tmp_path, lock_payload)

    with pytest.raises(ModelLockError, match="empty directory"):
        _load_generator().build_lock(
            model_home,
            receipt_path,
            Path(__file__).parents[1] / "uv.lock",
        )


def test_build_lock_rejects_actual_zero_byte_file(tmp_path: Path) -> None:
    _, model_home, lock_payload = _write_valid_lock(tmp_path)
    (model_home / "rapidocr_det" / "zero.bin").write_bytes(b"")
    receipt_path = _write_receipt_from_lock(tmp_path, lock_payload)

    with pytest.raises(ModelLockError, match="zero-byte"):
        _load_generator().build_lock(
            model_home,
            receipt_path,
            Path(__file__).parents[1] / "uv.lock",
        )


@pytest.mark.parametrize("root", ("../outside", "C:/outside"))
def test_build_lock_rejects_root_escape(tmp_path: Path, root: str) -> None:
    _, model_home, lock_payload = _write_valid_lock(tmp_path)
    _artifact(lock_payload, "rapidocr_det")["root"] = root
    receipt_path = _write_receipt_from_lock(tmp_path, lock_payload)

    with pytest.raises(ValidationError):
        _load_generator().build_lock(
            model_home,
            receipt_path,
            Path(__file__).parents[1] / "uv.lock",
        )


@pytest.mark.parametrize("entrypoint", ("../outside.bin", "C:/outside.bin"))
def test_build_lock_rejects_entrypoint_escape(
    tmp_path: Path,
    entrypoint: str,
) -> None:
    _, model_home, lock_payload = _write_valid_lock(tmp_path)
    _artifact(lock_payload, "rapidocr_det")["entrypoint"] = entrypoint
    receipt_path = _write_receipt_from_lock(tmp_path, lock_payload)

    with pytest.raises(ValidationError):
        _load_generator().build_lock(
            model_home,
            receipt_path,
            Path(__file__).parents[1] / "uv.lock",
        )


def test_build_lock_rejects_missing_entrypoint(tmp_path: Path) -> None:
    _, model_home, lock_payload = _write_valid_lock(tmp_path)
    _artifact(lock_payload, "rapidocr_det")["entrypoint"] = "missing.bin"
    receipt_path = _write_receipt_from_lock(tmp_path, lock_payload)

    with pytest.raises(ModelLockError, match="entrypoint is missing"):
        _load_generator().build_lock(
            model_home,
            receipt_path,
            Path(__file__).parents[1] / "uv.lock",
        )


def test_build_lock_rejects_entrypoint_directory_without_locked_files(
    tmp_path: Path,
) -> None:
    _, model_home, lock_payload = _write_valid_lock(tmp_path)
    empty_entrypoint = model_home / "rapidocr_det" / "empty-entrypoint"
    empty_entrypoint.mkdir()
    _artifact(lock_payload, "rapidocr_det")["entrypoint"] = "empty-entrypoint"
    receipt_path = _write_receipt_from_lock(tmp_path, lock_payload)

    with pytest.raises(ModelLockError, match="entrypoint"):
        _load_generator().build_lock(
            model_home,
            receipt_path,
            Path(__file__).parents[1] / "uv.lock",
        )


def test_build_lock_rejects_malformed_receipt_https_uri(tmp_path: Path) -> None:
    _, model_home, lock_payload = _write_valid_lock(tmp_path)
    artifacts = [
        {key: value for key, value in artifact.items() if key != "files"}
        for artifact in lock_payload["artifacts"]
    ]
    artifacts[0]["source_url"] = "https://[invalid"
    receipt_path = tmp_path / "source-receipt.json"
    receipt_path.write_text(
        json.dumps({"schema_version": "1.0.0", "artifacts": artifacts}),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        _load_generator().build_lock(
            model_home,
            receipt_path,
            Path(__file__).parents[1] / "uv.lock",
        )


def test_build_lock_rejects_malformed_percent_escape_in_receipt_uri(
    tmp_path: Path,
) -> None:
    _, model_home, lock_payload = _write_valid_lock(tmp_path)
    artifacts = [
        {key: value for key, value in artifact.items() if key != "files"}
        for artifact in lock_payload["artifacts"]
    ]
    artifacts[0]["source_url"] = "https://example.test/%ZZ"
    receipt_path = tmp_path / "source-receipt.json"
    receipt_path.write_text(
        json.dumps({"schema_version": "1.0.0", "artifacts": artifacts}),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        _load_generator().build_lock(
            model_home,
            receipt_path,
            Path(__file__).parents[1] / "uv.lock",
        )


@pytest.mark.parametrize(
    "invalid_uri",
    (
        "https://example.test/path[bad]",
        "https://user@@example.test/model",
    ),
)
def test_build_lock_rejects_unsafe_provenance_receipt_uri(
    tmp_path: Path,
    invalid_uri: str,
) -> None:
    _, model_home, lock_payload = _write_valid_lock(tmp_path)
    artifacts = [
        {key: value for key, value in artifact.items() if key != "files"}
        for artifact in lock_payload["artifacts"]
    ]
    artifacts[0]["source_url"] = invalid_uri
    receipt_path = tmp_path / "source-receipt.json"
    receipt_path.write_text(
        json.dumps({"schema_version": "1.0.0", "artifacts": artifacts}),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        _load_generator().build_lock(
            model_home,
            receipt_path,
            Path(__file__).parents[1] / "uv.lock",
        )


@pytest.mark.parametrize("forbidden_field", ("files", "bytes", "sha256"))
def test_build_lock_rejects_generated_metadata_in_receipt(
    tmp_path: Path, forbidden_field: str
) -> None:
    _, model_home, lock_payload = _write_valid_lock(tmp_path)
    artifacts = [
        {key: value for key, value in artifact.items() if key != "files"}
        for artifact in lock_payload["artifacts"]
    ]
    artifacts[0][forbidden_field] = [] if forbidden_field == "files" else "forged"
    receipt_path = tmp_path / "source-receipt.json"
    receipt_path.write_text(
        json.dumps({"schema_version": "1.0.0", "artifacts": artifacts}),
        encoding="utf-8",
    )
    uv_lock = Path(__file__).parents[1] / "uv.lock"

    with pytest.raises(ValidationError):
        _load_generator().build_lock(model_home, receipt_path, uv_lock)


def test_artifact_factory_rejects_duplicate_role_objects(tmp_path: Path) -> None:
    model_home = tmp_path / "models"
    root = model_home / "duplicate"
    root.mkdir(parents=True)
    duplicate_path = root / "duplicate.bin"
    duplicate_path.write_bytes(b"x")
    locked_file = LockedFile(
        path=duplicate_path,
        bytes=1,
        sha256=_digest(b"x"),
        relative_path=PurePosixPath("duplicate.bin"),
    )
    duplicate = LockedArtifact(
        component="RAPIDOCR",
        role="rapidocr_rec",
        name="duplicate",
        source_url="https://models.example.test/duplicate",
        license="UPSTREAM-LICENSE",
        model_home=model_home,
        root_relative_path=PurePosixPath("duplicate"),
        entrypoint_relative_path=PurePosixPath("duplicate.bin"),
        root=root,
        path=duplicate_path,
        files=(locked_file,),
    )

    with pytest.raises(ModelLockError, match="duplicate model role"):
        optional_artifact_path((duplicate, duplicate), "rapidocr_rec")


def test_docling_artifacts_root_normalizes_different_drive_error() -> None:
    artifacts = (
        LockedArtifact(
            component="DOCLING",
            role="docling_layout",
            name="layout",
            source_url="https://models.example.test/layout",
            license="Apache-2.0",
            model_home=Path("C:/models"),
            root_relative_path=PurePosixPath("layout"),
            entrypoint_relative_path=PurePosixPath("model.bin"),
            root=Path("C:/models/layout"),
            path=Path("C:/models/layout/model.bin"),
            files=(
                LockedFile(
                    path=Path("C:/models/layout/model.bin"),
                    bytes=1,
                    sha256=_digest(b"x"),
                    relative_path=PurePosixPath("model.bin"),
                ),
            ),
        ),
        LockedArtifact(
            component="TABLEFORMER",
            role="tableformer",
            name="tableformer",
            source_url="https://models.example.test/tableformer",
            license="CDLA-Permissive-2.0",
            model_home=Path("D:/models"),
            root_relative_path=PurePosixPath("tableformer"),
            entrypoint_relative_path=PurePosixPath("model.bin"),
            root=Path("D:/models/tableformer"),
            path=Path("D:/models/tableformer/model.bin"),
            files=(
                LockedFile(
                    path=Path("D:/models/tableformer/model.bin"),
                    bytes=1,
                    sha256=_digest(b"x"),
                    relative_path=PurePosixPath("model.bin"),
                ),
            ),
        ),
    )

    with pytest.raises(ModelLockError, match="common"):
        docling_artifacts_root(artifacts)


def test_model_lock_rejects_duplicate_json_object_keys(tmp_path: Path) -> None:
    lock_path, model_home, payload = _write_valid_lock(tmp_path)
    encoded = json.dumps(payload)
    lock_path.write_text(
        encoded.replace(
            '"schema_version": "2.0.0"',
            '"schema_version": "2.0.0", "schema_version": "2.0.0"',
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises((ModelLockError, ValueError), match="duplicate"):
        load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)


def test_source_receipt_rejects_duplicate_json_object_keys(tmp_path: Path) -> None:
    _, model_home, lock_payload = _write_valid_lock(tmp_path)
    receipt_path = _write_receipt_from_lock(tmp_path, lock_payload)
    encoded = receipt_path.read_text(encoding="utf-8")
    receipt_path.write_text(
        encoded.replace(
            '"schema_version": "1.0.0"',
            '"schema_version": "1.0.0", "schema_version": "1.0.0"',
            1,
        ),
        encoding="utf-8",
    )

    with pytest.raises((ModelLockError, ValueError), match="duplicate"):
        _load_generator().build_lock(
            model_home,
            receipt_path,
            Path(__file__).parents[1] / "uv.lock",
        )


@pytest.mark.parametrize(
    "mutator",
    (
        lambda artifact: replace(artifact, files=()),
        lambda artifact: replace(
            artifact,
            model_home=artifact.model_home.parent,
        ),
        lambda artifact: replace(
            artifact,
            root_relative_path=PurePosixPath("forged-root"),
        ),
        lambda artifact: replace(
            artifact,
            entrypoint_relative_path=PurePosixPath("forged.bin"),
        ),
        lambda artifact: replace(
            artifact,
            path=artifact.root / "forged.bin",
        ),
    ),
)
def test_revalidation_rejects_forged_provenance_dto(
    tmp_path: Path,
    mutator: object,
) -> None:
    lock_path, model_home, _ = _write_valid_lock(tmp_path)
    artifacts = list(load_model_lock(lock_path, model_home, RUNTIME_VERSIONS))
    index = next(
        index
        for index, artifact in enumerate(artifacts)
        if artifact.role == "rapidocr_rec"
    )
    artifacts[index] = mutator(artifacts[index])  # type: ignore[operator]

    with pytest.raises(ModelLockError):
        revalidate_locked_artifacts(tuple(artifacts))


def test_revalidation_rejects_forged_locked_file_binding(tmp_path: Path) -> None:
    lock_path, model_home, _ = _write_valid_lock(tmp_path)
    artifacts = list(load_model_lock(lock_path, model_home, RUNTIME_VERSIONS))
    index = next(
        index
        for index, artifact in enumerate(artifacts)
        if artifact.role == "rapidocr_rec"
    )
    artifact = artifacts[index]
    forged_file = replace(
        artifact.files[0],
        relative_path=PurePosixPath("forged.bin"),
    )
    artifacts[index] = replace(artifact, files=(forged_file,))

    with pytest.raises(ModelLockError):
        revalidate_locked_artifacts(tuple(artifacts))


def test_revalidation_rejects_unlocked_descendant_added_after_load(
    tmp_path: Path,
) -> None:
    lock_path, model_home, _ = _write_valid_lock(tmp_path)
    artifacts = load_model_lock(lock_path, model_home, RUNTIME_VERSIONS)
    rec = next(artifact for artifact in artifacts if artifact.role == "rapidocr_rec")
    (rec.root / "unlocked.bin").write_bytes(b"unlocked")

    with pytest.raises(ModelLockError, match="file list|descendant"):
        revalidate_locked_artifacts(artifacts)
