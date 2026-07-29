from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

import fitz

from pdf_ocr.image_contract import validate_png_file
from pdf_ocr.pipeline import (
    any_cell_status,
    extract_pdf,
    has_merged_or_multilevel_header,
    has_possible_cross_page_table,
)
from pdf_ocr.types import (
    LayoutPage,
    LayoutRegion,
    OcrPage,
    OcrToken,
    StructurePage,
    TableCell,
    TableData,
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
LOCKED_RECOGNIZER_NAME = "rapidocr_rec-model"
OCR_TEXT = "서울특별시 고시 제2026-1호"
MANDATORY_REASONS = {
    "NOTICE_NUMBER",
    "LEGAL_DATE",
    "AREA",
    "JURISDICTION",
    "TAX_RULE",
    "LEGAL_EFFECT",
    "SPATIAL_BOUNDARY",
    "SOURCE_RIGHTS",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_pdf(path: Path, texts: list[str]) -> Path:
    document = fitz.open()
    for text in texts:
        page = document.new_page()
        if text:
            page.insert_textbox(
                fitz.Rect(72, 72, 520, 720),
                text,
            )
    document.save(path)
    document.close()
    return path


@dataclass(frozen=True)
class FixtureEnvironment:
    model_lock: Path
    model_home: Path
    uv_lock: Path


def fixture_environment(tmp_path: Path) -> FixtureEnvironment:
    model_home = tmp_path / "models"
    model_home.mkdir()
    artifacts: list[dict[str, object]] = []
    for role, component in ROLE_COMPONENTS.items():
        root = (
            f"docling/{role}"
            if role in {"docling_layout", "tableformer"}
            else role
        )
        artifact_root = model_home / root
        artifact_root.mkdir(parents=True)
        file_name = f"{role}.bin"
        data = role.encode("ascii")
        (artifact_root / file_name).write_bytes(data)
        artifacts.append(
            {
                "component": component,
                "role": role,
                "name": f"{role}-model",
                "source_url": f"https://models.example.test/{role}",
                "license": "TEST-LICENSE",
                "root": root,
                "entrypoint": file_name,
                "files": [
                    {
                        "path": file_name,
                        "bytes": len(data),
                        "sha256": (
                            "sha256:" + hashlib.sha256(data).hexdigest()
                        ),
                    }
                ],
            }
        )
    lock_path = tmp_path / "models.lock.json"
    lock_path.write_text(
        json.dumps(
            {
                "schema_version": "2.0.0",
                "generated_at": "2026-07-28T00:00:00+09:00",
                "cache_environment_variable": "PDF_OCR_MODEL_HOME",
                "packages": [
                    {"name": name, "version": version}
                    for name, version in RUNTIME_VERSIONS.items()
                ],
                "artifacts": artifacts,
            }
        ),
        encoding="utf-8",
    )
    uv_lock = tmp_path / "uv.lock"
    uv_lock.write_text(
        "\n".join(
            [
                "version = 1",
                *[
                    (
                        f'[[package]]\nname = "{name}"\n'
                        f'version = "{version}"'
                    )
                    for name, version in RUNTIME_VERSIONS.items()
                ],
                "",
            ]
        ),
        encoding="utf-8",
    )
    return FixtureEnvironment(lock_path, model_home, uv_lock)


def standard_ocr_page(
    image_path: Path,
    page_number: int,
    *,
    confidence: float = 0.95,
    text: str = OCR_TEXT,
) -> OcrPage:
    width, height = validate_png_file(image_path)
    x0, y0 = 120.0, 120.0
    x1, y1 = min(580.0, width - 20.0), min(180.0, height - 20.0)
    polygon = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    return OcrPage(
        page_number=page_number,
        engine="RAPIDOCR",
        model_name=LOCKED_RECOGNIZER_NAME,
        markdown=text,
        tokens=(
            OcrToken(
                text=text,
                recognition_confidence=confidence,
                polygon=polygon,
                bbox=(x0, y0, x1, y1),
                reading_order=0,
                model_name=LOCKED_RECOGNIZER_NAME,
                source_page_number=page_number,
            ),
        ),
        raw={"source": "injected-test-double"},
    )


def standard_structure_page(
    image_path: Path,
    page_number: int,
    *,
    text: str = OCR_TEXT,
) -> StructurePage:
    width, height = validate_png_file(image_path)
    table_bbox = (100.0, 100.0, min(600.0, width - 10.0), 220.0)
    cell_bbox = (100.0, 100.0, min(600.0, width - 10.0), 220.0)
    cell = TableCell(
        text=text,
        bbox=cell_bbox,
        start_row=0,
        end_row=1,
        start_column=0,
        end_column=1,
        row_span=1,
        col_span=1,
        is_column_header=False,
        is_row_header=False,
        is_row_section=False,
        raw_ocr_comparison_status="NOT_COMPARABLE",
    )
    return StructurePage(
        page_number=page_number,
        width=width,
        height=height,
        regions=(
            LayoutRegion(label="table", bbox=table_bbox, reading_order=0),
        ),
        tables=(
            TableData(
                table_number=1,
                bbox=table_bbox,
                num_rows=1,
                num_columns=1,
                cells=(cell,),
                html=f"<table><tbody><tr><td>{text}</td></tr></tbody></table>",
            ),
        ),
        raw={"source": "injected-table-test-double"},
    )


class RecordingOcrRunner:
    def __init__(
        self,
        *,
        events: list[str] | None = None,
        factory: Callable[[Path, int], OcrPage] | None = None,
    ) -> None:
        self.pages: list[int] = []
        self.events = events
        self.factory = factory or standard_ocr_page

    def recognize(self, image_path: Path, *, page_number: int) -> OcrPage:
        self.pages.append(page_number)
        if self.events is not None:
            self.events.append(f"ocr:{page_number}")
        return self.factory(image_path, page_number)


class RecordingStructureRunner:
    def __init__(
        self,
        flags: dict[int, tuple[bool, bool]],
        *,
        events: list[str] | None = None,
        table_factory: Callable[[Path, int], StructurePage] | None = None,
    ) -> None:
        self.flags = flags
        self.events = events
        self.layout_pages: list[int] = []
        self.table_pages: list[int] = []
        self.table_factory = table_factory or standard_structure_page

    def detect_layout(
        self,
        image_path: Path,
        *,
        page_number: int,
    ) -> LayoutPage:
        self.layout_pages.append(page_number)
        if self.events is not None:
            self.events.append(f"layout:{page_number}")
        has_table, has_complex = self.flags[page_number]
        width, height = validate_png_file(image_path)
        label = "table" if has_table else "text"
        regions = [
            LayoutRegion(
                label=label,
                bbox=(10.0, 10.0, min(300.0, width - 1.0), 80.0),
                reading_order=0,
            )
        ]
        if has_complex:
            regions.append(
                LayoutRegion(
                    label="picture",
                    bbox=(10.0, 100.0, min(300.0, width - 1.0), 180.0),
                    reading_order=1,
                )
            )
        return LayoutPage(
            page_number=page_number,
            width=width,
            height=height,
            regions=tuple(regions),
            has_table=has_table,
            has_complex_layout=has_complex,
        )

    def recognize_tables(
        self,
        image_path: Path,
        *,
        page_number: int,
    ) -> StructurePage:
        self.table_pages.append(page_number)
        if self.events is not None:
            self.events.append(f"table:{page_number}")
        return self.table_factory(image_path, page_number)


def run_extract(
    pdf: Path,
    output_dir: Path,
    environment: FixtureEnvironment,
    *,
    ocr: object,
    structure: object,
) -> Path:
    return extract_pdf(
        pdf,
        output_dir,
        ocr_runner=ocr,
        structure_runner=structure,
        model_lock_path=environment.model_lock,
        model_home=environment.model_home,
        uv_lock_path=environment.uv_lock,
    )


def test_every_page_runs_layout_first_and_routes_embedded_and_scanned_pages(
    tmp_path: Path,
) -> None:
    environment = fixture_environment(tmp_path)
    pdf = write_pdf(
        tmp_path / "notice.pdf",
        [
            "Seoul public notice 2026-1 takes effect immediately. " * 3,
            "",
        ],
    )
    events: list[str] = []
    ocr = RecordingOcrRunner(events=events)
    structure = RecordingStructureRunner(
        {1: (False, False), 2: (False, False)},
        events=events,
    )

    manifest_path = run_extract(
        pdf,
        tmp_path / "result",
        environment,
        ocr=ocr,
        structure=structure,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert events[:2] == ["layout:1", "layout:2"]
    assert structure.layout_pages == [1, 2]
    assert structure.table_pages == []
    assert ocr.pages == [2]
    assert [page["route"] for page in manifest["pages"]] == [
        "EMBEDDED_TEXT",
        "RAPIDOCR",
    ]
    embedded_payload = json.loads(
        (tmp_path / "result/pages/0001.ocr.json").read_text(encoding="utf-8")
    )
    assert embedded_payload["engine"] == "EMBEDDED_TEXT"
    assert embedded_payload["blocks"][0]["recognition_confidence"] == 1.0
    assert embedded_payload["blocks"][0]["bbox"][0] > 72.0
    assert embedded_payload["coordinate_space"]["pdf_points_per_pixel"] == 0.24


def test_table_route_precedes_embedded_text_and_writes_dual_outputs(
    tmp_path: Path,
) -> None:
    environment = fixture_environment(tmp_path)
    pdf = write_pdf(
        tmp_path / "table.pdf",
        ["Seoul public notice with a detected table. " * 3],
    )
    ocr = RecordingOcrRunner()
    structure = RecordingStructureRunner({1: (True, True)})

    manifest_path = run_extract(
        pdf,
        tmp_path / "result",
        environment,
        ocr=ocr,
        structure=structure,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    page = manifest["pages"][0]
    assert ocr.pages == [1]
    assert structure.table_pages == [1]
    assert page["route"] == "RAPIDOCR_TABLEFORMER"
    assert {item["kind"] for item in page["outputs"]} == {
        "OCR_JSON",
        "STRUCTURE_JSON",
        "MARKDOWN",
        "TABLE_HTML",
    }
    assert set(page["review"]["reasons"]) == MANDATORY_REASONS


def test_complex_page_without_table_uses_rapidocr_only(tmp_path: Path) -> None:
    environment = fixture_environment(tmp_path)
    pdf = write_pdf(
        tmp_path / "complex.pdf",
        ["Seoul public notice in a complex multi-column layout. " * 3],
    )
    ocr = RecordingOcrRunner()
    structure = RecordingStructureRunner({1: (False, True)})

    manifest_path = run_extract(
        pdf,
        tmp_path / "result",
        environment,
        ocr=ocr,
        structure=structure,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["pages"][0]["route"] == "RAPIDOCR"
    assert ocr.pages == [1]
    assert structure.table_pages == []
    assert {
        item["kind"] for item in manifest["pages"][0]["outputs"]
    } == {"OCR_JSON", "STRUCTURE_JSON", "MARKDOWN"}


def test_manifest_projects_runtime_models_hashes_and_review_gate(
    tmp_path: Path,
) -> None:
    environment = fixture_environment(tmp_path)
    pdf = write_pdf(tmp_path / "scan.pdf", [""])
    ocr = RecordingOcrRunner(
        factory=lambda path, page: standard_ocr_page(
            path,
            page,
            confidence=0.82,
        )
    )
    structure = RecordingStructureRunner({1: (False, False)})

    manifest_path = run_extract(
        pdf,
        tmp_path / "result",
        environment,
        ocr=ocr,
        structure=structure,
    )

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == "2.0.0"
    assert manifest["runtime"]["execution_provider"] == "CPUExecutionProvider"
    assert manifest["runtime"]["rapidocr_version"] == "3.9.2"
    assert len(manifest["runtime"]["model_files"]) == 7
    assert {
        item["file_name"] for item in manifest["runtime"]["model_files"]
    } == {
        f"{role}/{role}.bin"
        if role not in {"docling_layout", "tableformer"}
        else f"docling/{role}/{role}.bin"
        for role in ROLE_COMPONENTS
    }
    page = manifest["pages"][0]
    assert set(page["review"]["reasons"]) == MANDATORY_REASONS | {
        "LOW_CONFIDENCE"
    }
    assert manifest["retention"] == {
        "status": "TEMPORARY_NOT_RETAINED",
        "source_rights_status": "PENDING_REVIEW",
    }
    assert manifest["input"]["sha256"] == f"sha256:{sha256(pdf)}"
    for record in [page["image"], *page["outputs"]]:
        artifact = tmp_path / "result" / record["file_name"]
        assert record["sha256"] == f"sha256:{sha256(artifact)}"


def test_review_helpers_detect_table_risks(tmp_path: Path) -> None:
    pdf = write_pdf(tmp_path / "page.pdf", [""])
    document = fitz.open(pdf)
    pixmap = document[0].get_pixmap(dpi=300, alpha=False)
    image = tmp_path / "page.png"
    image.write_bytes(pixmap.tobytes("png"))
    document.close()
    page = standard_structure_page(image, 1)
    risky_cell = replace(
        page.tables[0].cells[0],
        row_span=2,
        end_row=2,
        is_column_header=True,
        raw_ocr_comparison_status="MISMATCH",
    )
    risky_table = replace(
        page.tables[0],
        bbox=(100.0, 10.0, 600.0, 220.0),
        num_rows=2,
        cells=(risky_cell,),
    )
    risky_page = replace(page, tables=(risky_table,))

    assert any_cell_status(risky_page, "MISMATCH")
    assert has_merged_or_multilevel_header(risky_page)
    assert has_possible_cross_page_table(risky_page)


def test_windows_published_directory_keeps_restricted_protected_dacl(
    tmp_path: Path,
) -> None:
    if os.name != "nt":
        return
    from pdf_ocr import pipeline as pipeline_module

    environment = fixture_environment(tmp_path)
    pdf = write_pdf(tmp_path / "scan.pdf", [""])
    run_extract(
        pdf,
        tmp_path / "result",
        environment,
        ocr=RecordingOcrRunner(),
        structure=RecordingStructureRunner({1: (False, False)}),
    )

    assert pipeline_module._windows_directory_dacl_is_restricted(
        tmp_path / "result"
    )


def test_windows_rename_wrapper_receives_live_parent_handle_and_simple_name(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    if os.name != "nt":
        return
    from pdf_ocr import pipeline as pipeline_module

    environment = fixture_environment(tmp_path)
    pdf = write_pdf(tmp_path / "scan.pdf", [""])
    original = getattr(
        pipeline_module,
        "_windows_set_relative_rename_information",
        None,
    )
    captured: list[tuple[int, int, str]] = []

    def recording_rename(
        source_handle: int,
        parent_handle: int,
        output_name: str,
    ) -> None:
        captured.append((source_handle, parent_handle, output_name))
        assert callable(original)
        original(source_handle, parent_handle, output_name)

    monkeypatch.setattr(
        pipeline_module,
        "_windows_set_relative_rename_information",
        recording_rename,
        raising=False,
    )
    run_extract(
        pdf,
        tmp_path / "result",
        environment,
        ocr=RecordingOcrRunner(),
        structure=RecordingStructureRunner({1: (False, False)}),
    )

    assert len(captured) == 1
    source_handle, parent_handle, output_name = captured[0]
    assert source_handle not in {0, -1}
    assert parent_handle not in {0, -1}
    assert output_name == "result"


def test_both_pdf_parsers_receive_the_same_immutable_bytes_snapshot(
    tmp_path: Path,
    monkeypatch: object,
) -> None:
    from pdf_ocr import pipeline as pipeline_module

    environment = fixture_environment(tmp_path)
    pdf = write_pdf(
        tmp_path / "notice.pdf",
        ["immutable source notice content. " * 4],
    )
    original_reader = pipeline_module._read_embedded_texts
    original_fitz_open = getattr(
        pipeline_module,
        "_open_fitz_snapshot",
        None,
    )
    parser_inputs: list[tuple[str, int, bool]] = []

    def recording_reader(data: object) -> list[str]:
        parser_inputs.append(("pypdf", id(data), isinstance(data, bytes)))
        return original_reader(data)

    def recording_fitz_open(data: object) -> object:
        parser_inputs.append(("fitz", id(data), isinstance(data, bytes)))
        assert callable(original_fitz_open)
        return original_fitz_open(data)

    monkeypatch.setattr(
        pipeline_module,
        "_read_embedded_texts",
        recording_reader,
    )
    monkeypatch.setattr(
        pipeline_module,
        "_open_fitz_snapshot",
        recording_fitz_open,
        raising=False,
    )
    run_extract(
        pdf,
        tmp_path / "result",
        environment,
        ocr=RecordingOcrRunner(),
        structure=RecordingStructureRunner({1: (False, False)}),
    )

    assert parser_inputs == [
        ("pypdf", parser_inputs[0][1], True),
        ("fitz", parser_inputs[0][1], True),
    ]
