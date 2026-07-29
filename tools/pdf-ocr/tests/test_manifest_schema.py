from copy import deepcopy
import hashlib
from pathlib import Path, PurePosixPath

import pytest
from jsonschema import ValidationError

from pdf_ocr.contracts import (
    validate_manifest,
    validate_manifest_against_runtime,
)
from pdf_ocr.model_lock import LockedArtifact, LockedFile
from pdf_ocr.runtime import RuntimeInfo


MANDATORY_REASONS = [
    "NOTICE_NUMBER",
    "LEGAL_DATE",
    "AREA",
    "JURISDICTION",
    "TAX_RULE",
    "LEGAL_EFFECT",
    "SPATIAL_BOUNDARY",
    "SOURCE_RIGHTS",
]


def file_record(
    file_name: str,
    *,
    digest_character: str = "a",
) -> dict[str, object]:
    return {
        "file_name": file_name,
        "bytes": 1,
        "sha256": "sha256:" + (digest_character * 64),
    }


def output_record(
    kind: str,
    file_name: str,
    *,
    digest_character: str = "a",
) -> dict[str, object]:
    return {
        "kind": kind,
        **file_record(file_name, digest_character=digest_character),
    }


def model_file(
    component: str,
    role: str,
    name: str,
    *,
    digest_character: str,
    file_name: str | None = None,
) -> dict[str, object]:
    return {
        "component": component,
        "role": role,
        "name": name,
        "source_url": "https://www.modelscope.cn/",
        "license": "UPSTREAM_MODEL_NOTICE_RECORDED",
        "file_name": file_name or f"{role}/{name}.bin",
        "bytes": 1,
        "sha256": "sha256:" + (digest_character * 64),
    }


def valid_manifest() -> dict[str, object]:
    return {
        "schema_version": "2.0.0",
        "status": "SUCCEEDED",
        "started_at": "2026-07-28T10:00:00+09:00",
        "completed_at": "2026-07-28T10:00:05+09:00",
        "input": {
            "file_name": "notice.pdf",
            "mime_type": "application/pdf",
            "bytes": 1234,
            "sha256": "sha256:" + ("a" * 64),
            "page_count": 2,
        },
        "runtime": {
            "python_version": "3.12.13",
            "rapidocr_version": "3.9.1",
            "onnxruntime_version": "1.22.1",
            "execution_provider": "CPUExecutionProvider",
            "docling_version": "2.115.0",
            "docling_ibm_models_version": "3.13.3",
            "table_mode": "accurate",
            "render_dpi": 300,
            "raw_ocr_threshold": 0.0,
            "human_review_threshold": 0.90,
            "model_files": [
                model_file(
                    "RAPIDOCR",
                    "rapidocr_det",
                    "ch_PP-OCRv5_det_mobile",
                    digest_character="0",
                ),
                model_file(
                    "RAPIDOCR",
                    "rapidocr_cls",
                    "ch_ppocr_mobile_v2.0_cls_mobile",
                    digest_character="1",
                ),
                model_file(
                    "RAPIDOCR",
                    "rapidocr_rec",
                    "korean_PP-OCRv5_mobile_rec",
                    digest_character="2",
                ),
                model_file(
                    "RAPIDOCR",
                    "rapidocr_rec_keys",
                    "ppocrv5_korean_dict",
                    digest_character="3",
                ),
                model_file(
                    "RAPIDOCR",
                    "rapidocr_font",
                    "Noto Sans KR",
                    digest_character="4",
                ),
                model_file(
                    "DOCLING",
                    "docling_layout",
                    "docling-layout",
                    digest_character="5",
                ),
                model_file(
                    "TABLEFORMER",
                    "tableformer",
                    "tableformer-accurate",
                    digest_character="6",
                ),
            ],
        },
        "pages": [
            {
                "page_number": 1,
                "route": "EMBEDDED_TEXT",
                "image": file_record("pages/0001.png"),
                "embedded_text_quality": {
                    "non_whitespace_chars": 80,
                    "invalid_character_ratio": 0.0,
                },
                "outputs": [
                    output_record("OCR_JSON", "pages/0001.ocr.json"),
                    output_record(
                        "STRUCTURE_JSON",
                        "pages/0001.structure.json",
                        digest_character="b",
                    ),
                    output_record(
                        "MARKDOWN",
                        "pages/0001.md",
                        digest_character="c",
                    ),
                ],
                "review": {
                    "status": "PENDING_HUMAN_REVIEW",
                    "reasons": [*MANDATORY_REASONS],
                },
                "warnings": [],
            },
            {
                "page_number": 2,
                "route": "RAPIDOCR_TABLEFORMER",
                "image": file_record(
                    "pages/0002.png",
                    digest_character="b",
                ),
                "embedded_text_quality": {
                    "non_whitespace_chars": 0,
                    "invalid_character_ratio": 0.0,
                },
                "outputs": [
                    output_record("OCR_JSON", "pages/0002.ocr.json"),
                    output_record(
                        "STRUCTURE_JSON",
                        "pages/0002.structure.json",
                        digest_character="b",
                    ),
                    output_record(
                        "MARKDOWN",
                        "pages/0002.md",
                        digest_character="c",
                    ),
                    output_record(
                        "TABLE_HTML",
                        "pages/0002.tables/0001.html",
                        digest_character="d",
                    ),
                ],
                "review": {
                    "status": "PENDING_HUMAN_REVIEW",
                    "reasons": [
                        *MANDATORY_REASONS,
                        "OCR_TABLE_MISMATCH",
                    ],
                },
                "warnings": [],
            },
        ],
        "retention": {
            "status": "TEMPORARY_NOT_RETAINED",
            "source_rights_status": "PENDING_REVIEW",
        },
        "warnings": [],
    }


def test_complete_manifest_is_accepted() -> None:
    validate_manifest(valid_manifest())


def test_runtime_versions_are_non_empty_not_fixture_constants() -> None:
    manifest = valid_manifest()
    runtime = manifest["runtime"]
    assert isinstance(runtime, dict)
    runtime["rapidocr_version"] = "9.9.9-local"
    runtime["docling_version"] = "8.8.8-local"

    validate_manifest(manifest)


def test_non_sha256_value_is_rejected() -> None:
    manifest = valid_manifest()
    manifest["input"]["sha256"] = "not-a-hash"  # type: ignore[index]

    with pytest.raises(ValidationError):
        validate_manifest(manifest)


def test_uppercase_sha256_is_rejected() -> None:
    manifest = valid_manifest()
    manifest["pages"][0]["image"]["sha256"] = (  # type: ignore[index]
        "sha256:" + ("A" * 64)
    )

    with pytest.raises(ValidationError):
        validate_manifest(manifest)


def test_page_number_gap_is_rejected() -> None:
    manifest = deepcopy(valid_manifest())
    manifest["pages"][1]["page_number"] = 3  # type: ignore[index]

    with pytest.raises(ValidationError, match="continuous"):
        validate_manifest(manifest)


def test_table_route_requires_a_table_html_output() -> None:
    manifest = valid_manifest()
    manifest["pages"][1]["outputs"].pop()  # type: ignore[index]

    with pytest.raises(ValidationError, match="TABLE_HTML"):
        validate_manifest(manifest)


def test_non_table_route_rejects_table_html_output() -> None:
    manifest = valid_manifest()
    manifest["pages"][0]["outputs"].append(  # type: ignore[index]
        output_record("TABLE_HTML", "pages/0001.tables/0001.html")
    )

    with pytest.raises(ValidationError, match="TABLE_HTML"):
        validate_manifest(manifest)


def test_duplicate_required_page_output_is_rejected() -> None:
    manifest = valid_manifest()
    manifest["pages"][0]["outputs"].append(  # type: ignore[index]
        output_record("OCR_JSON", "pages/0001.copy.ocr.json")
    )

    with pytest.raises(ValidationError, match="exactly one"):
        validate_manifest(manifest)


def test_cpu_execution_provider_is_required() -> None:
    manifest = valid_manifest()
    manifest["runtime"]["execution_provider"] = "CUDAExecutionProvider"  # type: ignore[index]

    with pytest.raises(ValidationError):
        validate_manifest(manifest)


@pytest.mark.parametrize(
    ("component", "role"),
    (
        ("RAPIDOCR", "rapidocr_det"),
        ("RAPIDOCR", "rapidocr_cls"),
        ("RAPIDOCR", "rapidocr_rec"),
        ("RAPIDOCR", "rapidocr_rec_keys"),
        ("RAPIDOCR", "rapidocr_font"),
        ("DOCLING", "docling_layout"),
        ("TABLEFORMER", "tableformer"),
    ),
)
def test_required_model_component_role_is_not_optional(
    component: str,
    role: str,
) -> None:
    manifest = valid_manifest()
    model_files = manifest["runtime"]["model_files"]  # type: ignore[index]
    manifest["runtime"]["model_files"] = [  # type: ignore[index]
        item
        for item in model_files
        if (item["component"], item["role"]) != (component, role)
    ]

    with pytest.raises(ValidationError, match="model"):
        validate_manifest(manifest)


def test_model_component_and_role_must_form_an_approved_pair() -> None:
    manifest = valid_manifest()
    tableformer = manifest["runtime"]["model_files"][-1]  # type: ignore[index]
    tableformer["component"] = "DOCLING"

    with pytest.raises(ValidationError, match="model"):
        validate_manifest(manifest)


def test_multiple_files_for_same_model_role_are_allowed_when_names_differ() -> None:
    manifest = valid_manifest()
    duplicate = model_file(
        "RAPIDOCR",
        "rapidocr_rec",
        "duplicate-recognition-model",
        digest_character="3",
        file_name="rapidocr_rec/extra.bin",
    )
    manifest["runtime"]["model_files"].append(duplicate)  # type: ignore[index]

    validate_manifest(manifest)


def test_duplicate_model_component_role_and_file_name_is_rejected() -> None:
    manifest = valid_manifest()
    duplicate = deepcopy(manifest["runtime"]["model_files"][2])  # type: ignore[index]
    manifest["runtime"]["model_files"].append(duplicate)  # type: ignore[index]

    with pytest.raises(ValidationError, match="duplicate model"):
        validate_manifest(manifest)


@pytest.mark.parametrize(
    ("started_at", "completed_at"),
    (
        ("2026-07-28 10:00:00", "2026-07-28T10:00:05+09:00"),
        ("2026-07-28T10:00:00+09:00", "not-a-date"),
    ),
)
def test_manifest_timestamps_are_rfc3339(
    started_at: str,
    completed_at: str,
) -> None:
    manifest = valid_manifest()
    manifest["started_at"] = started_at
    manifest["completed_at"] = completed_at

    with pytest.raises(ValidationError):
        validate_manifest(manifest)


def test_manifest_completion_cannot_precede_start() -> None:
    manifest = valid_manifest()
    manifest["completed_at"] = "2026-07-28T09:59:59+09:00"

    with pytest.raises(ValidationError, match="completed_at"):
        validate_manifest(manifest)


@pytest.mark.parametrize(
    "file_name",
    (
        "/absolute.png",
        "C:/absolute.png",
        "//server/share.png",
        "pages\\0001.png",
        "pages/./0001.png",
        "pages/../0001.png",
        "pages//0001.png",
        "pages/0001:stream.png",
        "pages/\x00.png",
    ),
)
def test_manifest_page_paths_must_be_safe_relative_posix(
    file_name: str,
) -> None:
    manifest = valid_manifest()
    manifest["pages"][0]["image"]["file_name"] = file_name  # type: ignore[index]

    with pytest.raises(ValidationError, match="POSIX|path|file_name"):
        validate_manifest(manifest)


@pytest.mark.parametrize("status", ("HUMAN_REVIEWED", "REJECTED"))
def test_manifest_review_status_remains_pending_until_acceptance_file(
    status: str,
) -> None:
    manifest = valid_manifest()
    manifest["pages"][0]["review"]["status"] = status  # type: ignore[index]

    with pytest.raises(ValidationError):
        validate_manifest(manifest)


def test_manifest_requires_all_eight_mandatory_review_reasons() -> None:
    manifest = valid_manifest()
    manifest["pages"][0]["review"]["reasons"].remove("LEGAL_EFFECT")  # type: ignore[index]

    with pytest.raises(ValidationError, match="review"):
        validate_manifest(manifest)


def test_manifest_rejects_unknown_review_reason() -> None:
    manifest = valid_manifest()
    manifest["pages"][0]["review"]["reasons"].append("ARBITRARY")  # type: ignore[index]

    with pytest.raises(ValidationError):
        validate_manifest(manifest)


def _runtime_artifacts(tmp_path: Path) -> tuple[LockedArtifact, ...]:
    model_home = (tmp_path / "models").resolve()
    result = []
    roles = (
        ("RAPIDOCR", "rapidocr_det"),
        ("RAPIDOCR", "rapidocr_cls"),
        ("RAPIDOCR", "rapidocr_rec"),
        ("RAPIDOCR", "rapidocr_rec_keys"),
        ("RAPIDOCR", "rapidocr_font"),
        ("DOCLING", "docling_layout"),
        ("TABLEFORMER", "tableformer"),
    )
    for component, role in roles:
        root = model_home / role
        root.mkdir(parents=True)
        path = root / f"{role}.bin"
        data = role.encode("ascii")
        path.write_bytes(data)
        result.append(
            LockedArtifact(
                component=component,
                role=role,
                name=f"{role}-model",
                source_url="https://models.example.test/model",
                license="TEST",
                model_home=model_home,
                root_relative_path=PurePosixPath(role),
                entrypoint_relative_path=PurePosixPath(path.name),
                root=root,
                path=path,
                files=(
                    LockedFile(
                        path=path,
                        bytes=len(data),
                        sha256=(
                            "sha256:" + hashlib.sha256(data).hexdigest()
                        ),
                        relative_path=PurePosixPath(path.name),
                    ),
                ),
            )
        )
    return tuple(result)


def test_high_level_manifest_validator_binds_runtime_and_lock_projection(
    tmp_path: Path,
) -> None:
    manifest = valid_manifest()
    artifacts = _runtime_artifacts(tmp_path)
    manifest["runtime"]["rapidocr_version"] = "3.9.2"  # type: ignore[index]
    manifest["runtime"]["onnxruntime_version"] = "1.28.0"  # type: ignore[index]
    manifest["runtime"]["model_files"] = [  # type: ignore[index]
        {
            "component": artifact.component,
            "role": artifact.role,
            "name": artifact.name,
            "source_url": artifact.source_url,
            "license": artifact.license,
            "file_name": (
                artifact.root_relative_path / locked_file.relative_path
            ).as_posix(),
            "bytes": locked_file.bytes,
            "sha256": locked_file.sha256,
        }
        for artifact in artifacts
        for locked_file in artifact.files
    ]
    runtime = RuntimeInfo(
        package_versions={
            "rapidocr": "3.9.2",
            "onnxruntime": "1.28.0",
            "docling": "2.115.0",
            "docling-ibm-models": "3.13.3",
        },
        execution_provider="CPUExecutionProvider",
    )

    validate_manifest_against_runtime(manifest, runtime, artifacts)

    manifest["runtime"]["model_files"][0]["sha256"] = "sha256:" + ("f" * 64)  # type: ignore[index]
    with pytest.raises(ValidationError, match="model"):
        validate_manifest_against_runtime(manifest, runtime, artifacts)
