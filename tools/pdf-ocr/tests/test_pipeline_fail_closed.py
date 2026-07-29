from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import replace
from pathlib import Path
from typing import Callable

import pytest
from pypdf import PdfWriter

from pdf_ocr import pipeline as pipeline_module
from pdf_ocr.artifacts import PageArtifactSet
from pdf_ocr.pipeline import (
    OutputExistsError,
    PdfOcrError,
    STAGING_OWNER_MARKER,
)
from pdf_ocr.types import LayoutPage, OcrPage, StructurePage, TableCell, TableData
from test_pipeline_integration import (
    FixtureEnvironment,
    RecordingOcrRunner,
    RecordingStructureRunner,
    fixture_environment,
    run_extract,
    sha256,
    standard_ocr_page,
    standard_structure_page,
    write_pdf,
)


def assert_not_published(tmp_path: Path, output_name: str = "result") -> None:
    assert not (tmp_path / output_name).exists()
    assert list(tmp_path.glob(f".{output_name}.tmp-*")) == []


def test_corrupt_and_encrypted_pdfs_are_rejected_without_output(
    tmp_path: Path,
) -> None:
    corrupt = tmp_path / "corrupt.pdf"
    corrupt.write_bytes(b"%PDF-1.7\nincomplete")
    with pytest.raises(PdfOcrError):
        pipeline_module.extract_pdf(corrupt, tmp_path / "corrupt-result")
    assert_not_published(tmp_path, "corrupt-result")

    encrypted = tmp_path / "encrypted.pdf"
    writer = PdfWriter()
    writer.add_blank_page(width=612, height=792)
    writer.encrypt("secret")
    with encrypted.open("wb") as output:
        writer.write(output)
    with pytest.raises(PdfOcrError, match="encrypted"):
        pipeline_module.extract_pdf(encrypted, tmp_path / "encrypted-result")
    assert_not_published(tmp_path, "encrypted-result")


def test_existing_output_is_never_overwritten(tmp_path: Path) -> None:
    pdf = write_pdf(tmp_path / "notice.pdf", ["notice text " * 5])
    output = tmp_path / "result"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("preserve", encoding="utf-8")

    with pytest.raises(OutputExistsError):
        pipeline_module.extract_pdf(pdf, output)

    assert sentinel.read_text(encoding="utf-8") == "preserve"


class ExplodingStructureRunner(RecordingStructureRunner):
    def detect_layout(
        self,
        image_path: Path,
        *,
        page_number: int,
    ) -> LayoutPage:
        raise RuntimeError("simulated layout failure")


def test_layout_failure_cleans_only_owned_staging(tmp_path: Path) -> None:
    environment = fixture_environment(tmp_path)
    pdf = write_pdf(tmp_path / "scan.pdf", [""])

    with pytest.raises(PdfOcrError, match="page 1"):
        run_extract(
            pdf,
            tmp_path / "result",
            environment,
            ocr=RecordingOcrRunner(),
            structure=ExplodingStructureRunner({1: (False, False)}),
        )

    assert_not_published(tmp_path)


def test_partial_or_mismatched_layout_is_rejected(tmp_path: Path) -> None:
    environment = fixture_environment(tmp_path)
    pdf = write_pdf(tmp_path / "scan.pdf", [""])

    class PartialLayoutRunner(RecordingStructureRunner):
        def detect_layout(
            self,
            image_path: Path,
            *,
            page_number: int,
        ) -> LayoutPage:
            layout = super().detect_layout(
                image_path,
                page_number=page_number,
            )
            return replace(layout, page_number=2, width=layout.width + 1)

    with pytest.raises(PdfOcrError, match="layout"):
        run_extract(
            pdf,
            tmp_path / "result",
            environment,
            ocr=RecordingOcrRunner(),
            structure=PartialLayoutRunner({1: (False, False)}),
        )

    assert_not_published(tmp_path)


def test_empty_or_wrong_page_rapidocr_result_is_rejected(
    tmp_path: Path,
) -> None:
    environment = fixture_environment(tmp_path)
    pdf = write_pdf(tmp_path / "scan.pdf", [""])

    def empty_page(image_path: Path, page_number: int) -> OcrPage:
        valid = standard_ocr_page(image_path, page_number)
        return replace(valid, markdown="", tokens=())

    with pytest.raises(PdfOcrError):
        run_extract(
            pdf,
            tmp_path / "empty-result",
            environment,
            ocr=RecordingOcrRunner(factory=empty_page),
            structure=RecordingStructureRunner({1: (False, False)}),
        )
    assert_not_published(tmp_path, "empty-result")

    def wrong_page(image_path: Path, page_number: int) -> OcrPage:
        valid = standard_ocr_page(image_path, page_number)
        token = replace(valid.tokens[0], source_page_number=page_number + 1)
        return replace(valid, page_number=page_number + 1, tokens=(token,))

    with pytest.raises(PdfOcrError, match="page"):
        run_extract(
            pdf,
            tmp_path / "wrong-result",
            environment,
            ocr=RecordingOcrRunner(factory=wrong_page),
            structure=RecordingStructureRunner({1: (False, False)}),
        )
    assert_not_published(tmp_path, "wrong-result")


@pytest.mark.parametrize(
    "invalid_kind",
    ["empty", "zero_rows", "zero_columns", "overlap", "outside"],
)
def test_invalid_table_topology_is_rejected(
    tmp_path: Path,
    invalid_kind: str,
) -> None:
    environment = fixture_environment(tmp_path)
    pdf = write_pdf(tmp_path / f"{invalid_kind}.pdf", [""])

    def invalid_table(image_path: Path, page_number: int) -> StructurePage:
        page = standard_structure_page(image_path, page_number)
        table = page.tables[0]
        if invalid_kind == "empty":
            table = replace(table, cells=())
        elif invalid_kind == "zero_rows":
            table = replace(table, num_rows=0)
        elif invalid_kind == "zero_columns":
            table = replace(table, num_columns=0)
        elif invalid_kind == "outside":
            cell = replace(
                table.cells[0],
                start_row=1,
                end_row=2,
            )
            table = replace(table, cells=(cell,))
        else:
            first = replace(
                table.cells[0],
                end_column=1,
                col_span=1,
                bbox=(100.0, 100.0, 400.0, 220.0),
            )
            second = replace(
                first,
                start_column=1,
                end_column=2,
                bbox=(300.0, 100.0, 600.0, 220.0),
            )
            table = replace(
                table,
                num_columns=2,
                cells=(first, second),
            )
        return replace(page, tables=(table,))

    with pytest.raises(PdfOcrError):
        run_extract(
            pdf,
            tmp_path / "result",
            environment,
            ocr=RecordingOcrRunner(),
            structure=RecordingStructureRunner(
                {1: (True, True)},
                table_factory=invalid_table,
            ),
        )

    assert_not_published(tmp_path)


@pytest.mark.parametrize(
    "artifact_kind",
    ["OCR_JSON", "STRUCTURE_JSON", "MARKDOWN", "TABLE_HTML"],
)
def test_empty_serialized_artifact_fails_final_publication_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    artifact_kind: str,
) -> None:
    environment = fixture_environment(tmp_path)
    pdf = write_pdf(tmp_path / "table.pdf", [""])
    original = pipeline_module.write_page_artifacts

    def corrupting_writer(*args: object, **kwargs: object) -> PageArtifactSet:
        result = original(*args, **kwargs)
        records = [
            result.ocr,
            result.structure,
            result.markdown,
            *result.tables,
        ]
        record = next(item for item in records if item["kind"] == artifact_kind)
        root = Path(args[0]) if args else Path(kwargs["root"])
        (root / str(record["file_name"])).write_bytes(b"")
        return result

    monkeypatch.setattr(
        pipeline_module,
        "write_page_artifacts",
        corrupting_writer,
    )
    with pytest.raises(PdfOcrError):
        run_extract(
            pdf,
            tmp_path / "result",
            environment,
            ocr=RecordingOcrRunner(),
            structure=RecordingStructureRunner({1: (True, True)}),
        )

    assert_not_published(tmp_path)


def test_schema_corruption_with_matching_hash_is_still_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = fixture_environment(tmp_path)
    pdf = write_pdf(tmp_path / "scan.pdf", [""])
    original = pipeline_module.write_page_artifacts

    def schema_corrupting_writer(
        *args: object,
        **kwargs: object,
    ) -> PageArtifactSet:
        result = original(*args, **kwargs)
        root = Path(args[0]) if args else Path(kwargs["root"])
        path = root / str(result.ocr["file_name"])
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["page_number"] = 99
        data = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        path.write_bytes(data)
        result.ocr["bytes"] = len(data)
        result.ocr["sha256"] = "sha256:" + hashlib.sha256(data).hexdigest()
        return result

    monkeypatch.setattr(
        pipeline_module,
        "write_page_artifacts",
        schema_corrupting_writer,
    )
    with pytest.raises(PdfOcrError):
        run_extract(
            pdf,
            tmp_path / "result",
            environment,
            ocr=RecordingOcrRunner(),
            structure=RecordingStructureRunner({1: (False, False)}),
        )

    assert_not_published(tmp_path)


def test_input_mutation_is_detected_before_publish(tmp_path: Path) -> None:
    environment = fixture_environment(tmp_path)
    pdf = write_pdf(tmp_path / "scan.pdf", [""])

    def mutating_ocr(image_path: Path, page_number: int) -> OcrPage:
        result = standard_ocr_page(image_path, page_number)
        with pdf.open("ab") as output:
            output.write(b"\n% changed during OCR")
        return result

    with pytest.raises(PdfOcrError, match="changed"):
        run_extract(
            pdf,
            tmp_path / "result",
            environment,
            ocr=RecordingOcrRunner(factory=mutating_ocr),
            structure=RecordingStructureRunner({1: (False, False)}),
        )

    assert_not_published(tmp_path)


def test_output_appearing_during_processing_is_preserved(tmp_path: Path) -> None:
    environment = fixture_environment(tmp_path)
    pdf = write_pdf(tmp_path / "scan.pdf", [""])
    output_dir = tmp_path / "result"

    def racing_ocr(image_path: Path, page_number: int) -> OcrPage:
        result = standard_ocr_page(image_path, page_number)
        output_dir.mkdir()
        (output_dir / "winner.txt").write_text("other run", encoding="utf-8")
        return result

    with pytest.raises(OutputExistsError):
        run_extract(
            pdf,
            output_dir,
            environment,
            ocr=RecordingOcrRunner(factory=racing_ocr),
            structure=RecordingStructureRunner({1: (False, False)}),
        )

    assert (output_dir / "winner.txt").read_text(encoding="utf-8") == "other run"
    assert list(tmp_path.glob(".result.tmp-*")) == []


def test_foreign_owner_marker_prevents_cleanup(tmp_path: Path) -> None:
    environment = fixture_environment(tmp_path)
    pdf = write_pdf(tmp_path / "scan.pdf", [""])

    def steal_marker(image_path: Path, page_number: int) -> OcrPage:
        staging = next(tmp_path.glob(".result.tmp-*"))
        (staging / STAGING_OWNER_MARKER).write_text(
            "foreign-owner",
            encoding="utf-8",
        )
        raise RuntimeError("simulated ownership loss")

    with pytest.raises(PdfOcrError):
        run_extract(
            pdf,
            tmp_path / "result",
            environment,
            ocr=RecordingOcrRunner(factory=steal_marker),
            structure=RecordingStructureRunner({1: (False, False)}),
        )

    staging = list(tmp_path.glob(".result.tmp-*"))
    assert len(staging) == 1
    assert (staging[0] / STAGING_OWNER_MARKER).read_text(
        encoding="utf-8"
    ) == "foreign-owner"
    assert not (tmp_path / "result").exists()


def test_baseexception_still_cleans_owned_staging(tmp_path: Path) -> None:
    environment = fixture_environment(tmp_path)
    pdf = write_pdf(tmp_path / "scan.pdf", [""])

    def abnormal_exit(image_path: Path, page_number: int) -> OcrPage:
        raise SystemExit(77)

    with pytest.raises(SystemExit) as caught:
        run_extract(
            pdf,
            tmp_path / "result",
            environment,
            ocr=RecordingOcrRunner(factory=abnormal_exit),
            structure=RecordingStructureRunner({1: (False, False)}),
        )

    assert caught.value.code == 77
    assert_not_published(tmp_path)


def test_staging_initialization_baseexception_leaves_no_orphan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = fixture_environment(tmp_path)
    pdf = write_pdf(tmp_path / "scan.pdf", [""])

    def fail_marker(*args: object, **kwargs: object) -> None:
        raise SystemExit(78)

    monkeypatch.setattr(
        pipeline_module,
        "_write_owner_marker_exclusive",
        fail_marker,
        raising=False,
    )
    with pytest.raises(SystemExit) as caught:
        run_extract(
            pdf,
            tmp_path / "result",
            environment,
            ocr=RecordingOcrRunner(),
            structure=RecordingStructureRunner({1: (False, False)}),
        )

    assert caught.value.code == 78
    assert_not_published(tmp_path)


def test_windows_staging_guard_open_failure_leaves_no_orphan(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.name != "nt":
        pytest.skip("Windows protected staging regression")
    environment = fixture_environment(tmp_path)
    pdf = write_pdf(tmp_path / "scan.pdf", [""])
    original = pipeline_module._open_directory_guard

    def fail_staging_guard(
        path: Path,
        *,
        rename_source: bool = False,
        parent_target: bool = False,
    ) -> object:
        if rename_source:
            raise OSError("simulated staging guard open failure")
        return original(
            path,
            rename_source=rename_source,
            parent_target=parent_target,
        )

    monkeypatch.setattr(
        pipeline_module,
        "_open_directory_guard",
        fail_staging_guard,
    )
    with pytest.raises(PdfOcrError, match="staging|guard|creation"):
        run_extract(
            pdf,
            tmp_path / "result",
            environment,
            ocr=RecordingOcrRunner(),
            structure=RecordingStructureRunner({1: (False, False)}),
        )

    assert_not_published(tmp_path)


def test_external_hardlink_to_staging_artifact_fails_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = fixture_environment(tmp_path)
    pdf = write_pdf(tmp_path / "scan.pdf", [""])
    external_link = tmp_path / "external-ocr-link.json"
    original = pipeline_module.write_page_artifacts

    def hardlinking_writer(*args: object, **kwargs: object) -> PageArtifactSet:
        result = original(*args, **kwargs)
        root = Path(args[0]) if args else Path(kwargs["root"])
        os.link(root / str(result.ocr["file_name"]), external_link)
        return result

    monkeypatch.setattr(
        pipeline_module,
        "write_page_artifacts",
        hardlinking_writer,
    )
    with pytest.raises(PdfOcrError, match="link|identity|staging"):
        run_extract(
            pdf,
            tmp_path / "result",
            environment,
            ocr=RecordingOcrRunner(),
            structure=RecordingStructureRunner({1: (False, False)}),
        )

    assert external_link.is_file()
    assert_not_published(tmp_path)


def test_manifest_tamper_after_write_is_caught_by_final_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = fixture_environment(tmp_path)
    pdf = write_pdf(tmp_path / "scan.pdf", [""])
    original = pipeline_module.validate_publication_bundle
    calls = 0

    def tampering_validator(
        payload: object,
        root: Path,
        runtime: object,
        artifacts: object,
    ) -> None:
        nonlocal calls
        calls += 1
        original(payload, root, runtime, artifacts)
        if calls == 2:
            manifest = root / "pdf-ocr-manifest.json"
            manifest.write_bytes(manifest.read_bytes() + b" ")

    monkeypatch.setattr(
        pipeline_module,
        "validate_publication_bundle",
        tampering_validator,
    )
    with pytest.raises(PdfOcrError, match="manifest|identity|staging"):
        run_extract(
            pdf,
            tmp_path / "result",
            environment,
            ocr=RecordingOcrRunner(),
            structure=RecordingStructureRunner({1: (False, False)}),
        )

    assert calls == 2
    assert_not_published(tmp_path)


def test_input_a_to_b_to_a_uses_one_stable_snapshot(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    environment = fixture_environment(tmp_path)
    original_pdf = write_pdf(
        tmp_path / "notice.pdf",
        ["ALPHA stable source notice content. " * 4],
    )
    alternate_pdf = write_pdf(
        tmp_path / "alternate.pdf",
        ["BRAVO swapped source notice content. " * 4],
    )
    alpha_bytes = original_pdf.read_bytes()
    bravo_bytes = alternate_pdf.read_bytes()
    original_reader = pipeline_module._read_embedded_texts

    def read_then_swap(snapshot: object) -> list[str]:
        result = original_reader(snapshot)
        original_pdf.write_bytes(bravo_bytes)
        return result

    original_writer = pipeline_module.write_page_artifacts

    def restore_before_write(*args: object, **kwargs: object) -> PageArtifactSet:
        original_pdf.write_bytes(alpha_bytes)
        return original_writer(*args, **kwargs)

    monkeypatch.setattr(
        pipeline_module,
        "_read_embedded_texts",
        read_then_swap,
    )
    monkeypatch.setattr(
        pipeline_module,
        "write_page_artifacts",
        restore_before_write,
    )
    manifest_path = run_extract(
        original_pdf,
        tmp_path / "result",
        environment,
        ocr=RecordingOcrRunner(),
        structure=RecordingStructureRunner({1: (False, False)}),
    )

    payload = json.loads(
        (manifest_path.parent / "pages/0001.ocr.json").read_text(
            encoding="utf-8"
        )
    )
    assert "ALPHA" in payload["blocks"][0]["text"]
    assert "BRAVO" not in payload["blocks"][0]["text"]


@pytest.mark.parametrize(
    ("has_table", "has_complex", "region_label"),
    [
        (True, False, "text"),
        (False, False, "table"),
        (False, True, "text"),
        (False, False, "picture"),
    ],
)
def test_inconsistent_layout_flags_fail_closed(
    tmp_path: Path,
    has_table: bool,
    has_complex: bool,
    region_label: str,
) -> None:
    environment = fixture_environment(tmp_path)
    pdf = write_pdf(tmp_path / "notice.pdf", ["notice content " * 5])

    class InconsistentLayoutRunner(RecordingStructureRunner):
        def detect_layout(
            self,
            image_path: Path,
            *,
            page_number: int,
        ) -> LayoutPage:
            layout = super().detect_layout(
                image_path,
                page_number=page_number,
            )
            region = replace(layout.regions[0], label=region_label)
            return replace(
                layout,
                regions=(region,),
                has_table=has_table,
                has_complex_layout=has_complex,
            )

    with pytest.raises(PdfOcrError, match="layout"):
        run_extract(
            pdf,
            tmp_path / "result",
            environment,
            ocr=RecordingOcrRunner(),
            structure=InconsistentLayoutRunner(
                {1: (has_table, has_complex)}
            ),
        )

    assert_not_published(tmp_path)


def test_broken_link_final_output_is_treated_as_occupied(
    tmp_path: Path,
) -> None:
    pdf = write_pdf(tmp_path / "notice.pdf", ["notice content " * 5])
    output = tmp_path / "result"
    try:
        output.symlink_to(tmp_path / "missing-output-target", target_is_directory=True)
    except OSError as error:
        pytest.skip(f"directory symlink creation is unavailable: {error}")

    with pytest.raises(OutputExistsError):
        pipeline_module.extract_pdf(pdf, output)

    assert output.is_symlink()


def test_broken_link_lexists_branch_is_permission_independent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pdf = write_pdf(tmp_path / "notice.pdf", ["notice content " * 5])
    output = tmp_path / "result"
    original = pipeline_module._path_exists_even_if_broken

    def fake_lexists(path: Path) -> bool:
        if Path(path) == output:
            return True
        return original(path)

    monkeypatch.setattr(
        pipeline_module,
        "_path_exists_even_if_broken",
        fake_lexists,
    )
    with pytest.raises(OutputExistsError):
        pipeline_module.extract_pdf(pdf, output)


def test_posix_chmod_failure_removes_new_staging(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output = tmp_path / "result"

    def fail_chmod(*args: object, **kwargs: object) -> None:
        raise OSError("simulated chmod failure")

    monkeypatch.setattr(pipeline_module.os, "chmod", fail_chmod)
    with pytest.raises(PdfOcrError, match="staging|permission|chmod"):
        pipeline_module._create_posix_private_staging(output)

    assert list(tmp_path.glob(".result.tmp-*")) == []


def test_input_resolve_runtimeerror_is_normalized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = Path.resolve

    def loop_error(path: Path, *args: object, **kwargs: object) -> Path:
        if path.name == "loop.pdf":
            raise RuntimeError("simulated symlink loop")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", loop_error)
    with pytest.raises(PdfOcrError, match="input"):
        pipeline_module._validated_input_path(
            tmp_path / "loop.pdf",
            tmp_path / "result",
        )


def test_output_parent_resolve_runtimeerror_is_normalized(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    parent = tmp_path / "loop-parent"
    original = Path.resolve

    def loop_error(path: Path, *args: object, **kwargs: object) -> Path:
        if path == parent:
            raise RuntimeError("simulated parent symlink loop")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "resolve", loop_error)
    with pytest.raises(PdfOcrError, match="output parent"):
        pipeline_module._prepare_output_path(parent / "result")


def test_cleanup_removes_junction_object_without_touching_external_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    if os.name != "nt":
        pytest.skip("junction regression is Windows-specific")
    environment = fixture_environment(tmp_path)
    pdf = write_pdf(tmp_path / "scan.pdf", [""])
    external = tmp_path / "external-target"
    external.mkdir()
    sentinel = external / "sentinel.txt"
    sentinel.write_text("preserve", encoding="utf-8")
    original = pipeline_module.write_page_artifacts

    def junction_writer(*args: object, **kwargs: object) -> PageArtifactSet:
        result = original(*args, **kwargs)
        root = Path(args[0]) if args else Path(kwargs["root"])
        junction = root / "untrusted-junction"
        completed = subprocess.run(
            [
                "cmd",
                "/c",
                "mklink",
                "/J",
                str(junction),
                str(external),
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        if completed.returncode != 0:
            pytest.skip(
                f"junction creation is unavailable: {completed.stderr}"
            )
        raise RuntimeError("force owned cleanup")

    monkeypatch.setattr(
        pipeline_module,
        "write_page_artifacts",
        junction_writer,
    )
    with pytest.raises(PdfOcrError):
        run_extract(
            pdf,
            tmp_path / "result",
            environment,
            ocr=RecordingOcrRunner(),
            structure=RecordingStructureRunner({1: (False, False)}),
        )

    assert sentinel.read_text(encoding="utf-8") == "preserve"
    assert_not_published(tmp_path)
