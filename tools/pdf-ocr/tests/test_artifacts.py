from __future__ import annotations

import json
from copy import deepcopy
from dataclasses import replace
from pathlib import Path

import fitz
import pytest
from jsonschema import ValidationError

from pdf_ocr import artifacts as artifact_module
from pdf_ocr.artifacts import (
    ArtifactError,
    compare_table_cells,
    file_record,
    write_page_artifacts,
)
from pdf_ocr.contracts import (
    sha256,
    validate_ocr_page,
    validate_output_hashes,
    validate_structure_page,
    validate_table_topology,
)
from pdf_ocr.router import PageRoute
from pdf_ocr.types import (
    LayoutRegion,
    OcrPage,
    OcrToken,
    StructurePage,
    TableCell,
    TableData,
)


def coordinate_space() -> dict[str, object]:
    return {
        "unit": "pixel",
        "width": 200,
        "height": 100,
        "render_dpi": 300,
        "pdf_points_per_pixel": 0.24,
    }


def ocr_block(
    *,
    reading_order: int = 0,
    bbox: list[float] | None = None,
) -> dict[str, object]:
    return {
        "text": "서울특별시 고시",
        "recognition_confidence": 0.91,
        "polygon": [[10, 10], [190, 10], [190, 40], [10, 40]],
        "bbox": bbox or [10, 10, 190, 40],
        "reading_order": reading_order,
        "model_name": "korean_PP-OCRv5_mobile_rec",
        "source_page_number": 1,
    }


def valid_ocr_page() -> dict[str, object]:
    return {
        "schema_version": "2.0.0",
        "page_number": 1,
        "engine": "RAPIDOCR",
        "model_name": "korean_PP-OCRv5_mobile_rec",
        "coordinate_space": coordinate_space(),
        "blocks": [ocr_block()],
        "minimum_confidence": 0.91,
        "raw": {},
    }


def cell(
    *,
    text: str = "구분",
    bbox: list[float] | None = None,
    start_row: int = 0,
    end_row: int = 1,
    start_column: int = 0,
    end_column: int = 1,
    row_span: int | None = None,
    col_span: int | None = None,
) -> dict[str, object]:
    return {
        "text": text,
        "bbox": bbox or [0, 0, 200, 100],
        "start_row": start_row,
        "end_row": end_row,
        "start_column": start_column,
        "end_column": end_column,
        "row_span": (
            end_row - start_row if row_span is None else row_span
        ),
        "col_span": (
            end_column - start_column if col_span is None else col_span
        ),
        "is_column_header": True,
        "is_row_header": False,
        "is_row_section": False,
        "raw_ocr_comparison_status": "MATCHED",
    }


def table(
    *,
    num_rows: int = 1,
    num_columns: int = 1,
    cells: list[dict[str, object]] | None = None,
    bbox: list[float] | None = None,
) -> dict[str, object]:
    return {
        "table_number": 1,
        "bbox": bbox or [0, 0, 200, 100],
        "num_rows": num_rows,
        "num_columns": num_columns,
        "cells": [cell()] if cells is None else cells,
        "html_file": "pages/0001.tables/0001.html",
    }


def valid_structure_page() -> dict[str, object]:
    return {
        "schema_version": "2.0.0",
        "page_number": 1,
        "coordinate_space": coordinate_space(),
        "regions": [
            {
                "label": "table",
                "bbox": [0, 0, 200, 100],
                "reading_order": 0,
            }
        ],
        "tables": [table()],
        "raw": {},
    }


def test_valid_page_artifact_contracts_are_accepted() -> None:
    validate_ocr_page(valid_ocr_page())
    validate_structure_page(valid_structure_page())


def test_rapidocr_page_requires_at_least_one_block() -> None:
    payload = valid_ocr_page()
    payload["blocks"] = []
    payload["minimum_confidence"] = None

    with pytest.raises(ValidationError):
        validate_ocr_page(payload)


def test_embedded_text_cannot_claim_a_rapidocr_model() -> None:
    payload = valid_ocr_page()
    payload["engine"] = "EMBEDDED_TEXT"
    payload["model_name"] = "korean_PP-OCRv5_mobile_rec"

    with pytest.raises(ValidationError):
        validate_ocr_page(payload)


def test_ocr_reading_order_must_be_unique() -> None:
    payload = valid_ocr_page()
    payload["blocks"] = [ocr_block(), ocr_block()]

    with pytest.raises(ValidationError, match="reading_order"):
        validate_ocr_page(payload)


@pytest.mark.parametrize(
    "bbox",
    (
        [-1, 0, 20, 20],
        [0, 0, 201, 20],
    ),
)
def test_ocr_bbox_must_stay_inside_page(bbox: list[float]) -> None:
    payload = valid_ocr_page()
    payload["blocks"] = [ocr_block(bbox=bbox)]

    with pytest.raises(ValidationError, match="bbox"):
        validate_ocr_page(payload)


def test_structure_bbox_must_stay_inside_page() -> None:
    payload = valid_structure_page()
    payload["tables"][0]["bbox"] = [0, 0, 201, 100]  # type: ignore[index]

    with pytest.raises(ValidationError, match="bbox"):
        validate_structure_page(payload)


def test_overlapping_table_cells_are_rejected() -> None:
    payload = table(
        cells=[
            cell(start_row=0, end_row=1, start_column=0, end_column=1),
            cell(start_row=0, end_row=1, start_column=0, end_column=1),
        ]
    )

    with pytest.raises(ValidationError, match="overlap"):
        validate_table_topology(payload)


def test_out_of_bounds_table_cell_range_is_rejected() -> None:
    payload = table(
        cells=[
            cell(start_row=0, end_row=2, start_column=0, end_column=1),
        ]
    )

    with pytest.raises(ValidationError, match="range"):
        validate_table_topology(payload)


@pytest.mark.parametrize(
    ("span_name", "span_value", "message"),
    (
        ("row_span", 2, "row_span"),
        ("col_span", 2, "col_span"),
    ),
)
def test_cell_span_must_match_half_open_range(
    span_name: str,
    span_value: int,
    message: str,
) -> None:
    kwargs = {span_name: span_value}
    payload = table(cells=[cell(**kwargs)])  # type: ignore[arg-type]

    with pytest.raises(ValidationError, match=message):
        validate_table_topology(payload)


def test_empty_table_cell_list_is_rejected() -> None:
    with pytest.raises(ValidationError, match="cells"):
        validate_table_topology(table(cells=[]))


def test_table_cells_must_cover_the_declared_grid() -> None:
    payload = table(
        num_rows=1,
        num_columns=2,
        cells=[
            cell(start_row=0, end_row=1, start_column=0, end_column=1),
        ],
    )

    with pytest.raises(ValidationError, match="cover"):
        validate_table_topology(payload)


def test_negative_table_bbox_is_rejected() -> None:
    with pytest.raises(ValidationError, match="bbox"):
        validate_table_topology(table(bbox=[-1, 0, 200, 100]))


def write_page_outputs(root: Path, *, table_count: int = 1) -> dict[str, object]:
    pages = root / "pages"
    pages.mkdir()
    image = pages / "0001.png"
    ocr = pages / "0001.ocr.json"
    structure = pages / "0001.structure.json"
    markdown = pages / "0001.md"
    table_html = pages / "0001.tables" / "0001.html"
    table_html.parent.mkdir()
    write_real_png(image)
    ocr_payload = valid_ocr_page()
    ocr.write_text(
        json.dumps(ocr_payload, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    structure_payload = valid_structure_page()
    structure_payload["tables"] = [
        {
            **table(),
            "table_number": table_number,
            "html_file": f"pages/0001.tables/{table_number:04d}.html",
        }
        for table_number in range(1, table_count + 1)
    ]
    comparison_text = ocr_payload["blocks"][0]["text"]
    for table_payload in structure_payload["tables"]:
        table_payload["cells"][0]["text"] = comparison_text
        table_payload["cells"][0]["raw_ocr_comparison_status"] = "MATCHED"
    structure.write_text(
        json.dumps(structure_payload, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    markdown.write_text("서울특별시 고시\n", encoding="utf-8")
    table_html.write_text(
        f"<table><tbody><tr><th>{comparison_text}</th></tr></tbody></table>\n",
        encoding="utf-8",
    )

    def record(path: Path, kind: str | None = None) -> dict[str, object]:
        result: dict[str, object] = {
            "file_name": path.relative_to(root).as_posix(),
            "bytes": path.stat().st_size,
            "sha256": f"sha256:{sha256(path)}",
        }
        if kind is not None:
            result["kind"] = kind
        return result

    return {
        "pages": [
            {
                "page_number": 1,
                "route": "RAPIDOCR_TABLEFORMER",
                "image": record(image),
                "outputs": [
                    record(ocr, "OCR_JSON"),
                    record(structure, "STRUCTURE_JSON"),
                    record(markdown, "MARKDOWN"),
                    record(table_html, "TABLE_HTML"),
                ],
            }
        ]
    }


def test_output_hash_chain_is_accepted(tmp_path: Path) -> None:
    validate_output_hashes(write_page_outputs(tmp_path), tmp_path)


def test_missing_output_file_is_rejected(tmp_path: Path) -> None:
    payload = write_page_outputs(tmp_path)
    (tmp_path / "pages" / "0001.md").unlink()

    with pytest.raises(ValidationError, match="missing"):
        validate_output_hashes(payload, tmp_path)


def test_output_path_escape_is_rejected(tmp_path: Path) -> None:
    payload = write_page_outputs(tmp_path)
    outside = tmp_path.parent / "outside.md"
    outside.write_text("outside", encoding="utf-8")
    output = payload["pages"][0]["outputs"][2]  # type: ignore[index]
    output["file_name"] = "../outside.md"
    output["bytes"] = outside.stat().st_size
    output["sha256"] = f"sha256:{sha256(outside)}"

    with pytest.raises(ValidationError, match="escapes"):
        validate_output_hashes(payload, tmp_path)


def test_output_size_mismatch_is_rejected(tmp_path: Path) -> None:
    payload = write_page_outputs(tmp_path)
    payload["pages"][0]["image"]["bytes"] = 999  # type: ignore[index]

    with pytest.raises(ValidationError, match="size"):
        validate_output_hashes(payload, tmp_path)


def test_output_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    payload = write_page_outputs(tmp_path)
    payload["pages"][0]["image"]["sha256"] = "sha256:" + ("0" * 64)  # type: ignore[index]

    with pytest.raises(ValidationError, match="SHA-256"):
        validate_output_hashes(payload, tmp_path)


def test_table_html_count_must_match_structure_table_count(
    tmp_path: Path,
) -> None:
    payload = write_page_outputs(tmp_path, table_count=2)

    with pytest.raises(ValidationError, match="TABLE_HTML"):
        validate_output_hashes(payload, tmp_path)


def test_table_html_paths_must_match_structure_html_files(
    tmp_path: Path,
) -> None:
    payload = write_page_outputs(tmp_path)
    structure_path = tmp_path / "pages" / "0001.structure.json"
    structure_payload = json.loads(structure_path.read_text(encoding="utf-8"))
    structure_payload["tables"][0]["html_file"] = (
        "pages/0001.tables/0002.html"
    )
    structure_path.write_text(
        json.dumps(structure_payload) + "\n",
        encoding="utf-8",
    )
    structure_record = payload["pages"][0]["outputs"][1]  # type: ignore[index]
    structure_record["bytes"] = structure_path.stat().st_size
    structure_record["sha256"] = f"sha256:{sha256(structure_path)}"

    with pytest.raises(ValidationError, match="TABLE_HTML paths"):
        validate_output_hashes(payload, tmp_path)


def test_output_json_page_route_engine_and_fixed_stem_are_cross_bound(
    tmp_path: Path,
) -> None:
    payload = write_page_outputs(tmp_path)
    ocr_path = tmp_path / "pages" / "0001.ocr.json"
    ocr_payload = json.loads(ocr_path.read_text(encoding="utf-8"))
    ocr_payload["page_number"] = 2
    for block in ocr_payload["blocks"]:
        block["source_page_number"] = 2
    ocr_path.write_text(json.dumps(ocr_payload) + "\n", encoding="utf-8")
    record = payload["pages"][0]["outputs"][0]  # type: ignore[index]
    record["bytes"] = ocr_path.stat().st_size
    record["sha256"] = f"sha256:{sha256(ocr_path)}"

    with pytest.raises(ValidationError, match="page"):
        validate_output_hashes(payload, tmp_path)


def test_output_json_coordinate_spaces_must_match(tmp_path: Path) -> None:
    payload = write_page_outputs(tmp_path)
    structure_path = tmp_path / "pages" / "0001.structure.json"
    structure_payload = json.loads(structure_path.read_text(encoding="utf-8"))
    structure_payload["coordinate_space"]["width"] = 201
    structure_path.write_text(json.dumps(structure_payload) + "\n", encoding="utf-8")
    record = payload["pages"][0]["outputs"][1]  # type: ignore[index]
    record["bytes"] = structure_path.stat().st_size
    record["sha256"] = f"sha256:{sha256(structure_path)}"

    with pytest.raises(ValidationError, match="coordinate"):
        validate_output_hashes(payload, tmp_path)


def test_table_html_must_use_the_fixed_page_and_table_stem(
    tmp_path: Path,
) -> None:
    payload = write_page_outputs(tmp_path)
    original = tmp_path / "pages" / "0001.tables" / "0001.html"
    wrong = tmp_path / "pages" / "0001.tables" / "9999.html"
    original.replace(wrong)
    structure_path = tmp_path / "pages" / "0001.structure.json"
    structure_payload = json.loads(structure_path.read_text(encoding="utf-8"))
    structure_payload["tables"][0]["html_file"] = (
        "pages/0001.tables/9999.html"
    )
    structure_path.write_text(json.dumps(structure_payload) + "\n", encoding="utf-8")
    structure_record = payload["pages"][0]["outputs"][1]  # type: ignore[index]
    structure_record["bytes"] = structure_path.stat().st_size
    structure_record["sha256"] = f"sha256:{sha256(structure_path)}"
    html_record = payload["pages"][0]["outputs"][3]  # type: ignore[index]
    html_record["file_name"] = "pages/0001.tables/9999.html"
    html_record["bytes"] = wrong.stat().st_size
    html_record["sha256"] = f"sha256:{sha256(wrong)}"

    with pytest.raises(ValidationError, match="stem|TABLE_HTML"):
        validate_output_hashes(payload, tmp_path)


def test_contract_rejects_nonfinite_numbers_nested_in_raw_json() -> None:
    payload = valid_ocr_page()
    payload["raw"] = {"nested": [float("nan")]}

    with pytest.raises(ValidationError, match="finite"):
        validate_ocr_page(payload)


def ocr_token_fixture(
    *,
    text: str = "면적",
    bbox: tuple[float, float, float, float] = (10.0, 10.0, 90.0, 40.0),
    reading_order: int = 0,
    page_number: int = 1,
    confidence: float = 0.91,
) -> OcrToken:
    x0, y0, x1, y1 = bbox
    return OcrToken(
        text=text,
        recognition_confidence=confidence,
        polygon=((x0, y0), (x1, y0), (x1, y1), (x0, y1)),
        bbox=bbox,
        reading_order=reading_order,
        model_name="korean_PP-OCRv5_rec_mobile",
        source_page_number=page_number,
    )


def ocr_page_fixture(
    *,
    page_number: int = 1,
    engine: str = "RAPIDOCR",
    model_name: str = "korean_PP-OCRv5_rec_mobile",
    markdown: str = "면적\n",
    tokens: tuple[OcrToken, ...] | None = None,
    raw: dict[str, object] | None = None,
) -> OcrPage:
    return OcrPage(
        page_number=page_number,
        engine=engine,
        model_name=model_name,
        markdown=markdown,
        tokens=(
            (ocr_token_fixture(page_number=page_number),)
            if tokens is None
            else tokens
        ),
        raw={"원문": "보존"} if raw is None else raw,
    )


def table_cell_fixture(
    *,
    text: str = "면적",
    bbox: tuple[float, float, float, float] = (0.0, 0.0, 100.0, 50.0),
    start_row: int = 0,
    end_row: int = 1,
    start_column: int = 0,
    end_column: int = 1,
    status: str = "MATCHED",
    is_column_header: bool = True,
    is_row_header: bool = False,
    is_row_section: bool = False,
) -> TableCell:
    return TableCell(
        text=text,
        bbox=bbox,
        start_row=start_row,
        end_row=end_row,
        start_column=start_column,
        end_column=end_column,
        row_span=end_row - start_row,
        col_span=end_column - start_column,
        is_column_header=is_column_header,
        is_row_header=is_row_header,
        is_row_section=is_row_section,
        raw_ocr_comparison_status=status,
    )


def structure_page_fixture(
    *,
    page_number: int = 1,
    cells: tuple[TableCell, ...] | None = None,
    table_number: int = 1,
    html: str = "<table><tr><th>면적</th></tr></table>",
    tables: tuple[TableData, ...] | None = None,
    raw: dict[str, object] | None = None,
) -> StructurePage:
    if tables is None:
        fixture_cells = (
            (table_cell_fixture(),)
            if cells is None
            else cells
        )
        tables = (
            TableData(
                table_number=table_number,
                bbox=(0.0, 0.0, 200.0, 100.0),
                num_rows=max(cell.end_row for cell in fixture_cells),
                num_columns=max(cell.end_column for cell in fixture_cells),
                cells=fixture_cells,
                html=html,
            ),
        )
    return StructurePage(
        page_number=page_number,
        width=200,
        height=100,
        regions=(
            LayoutRegion(
                label="table",
                bbox=(0.0, 0.0, 200.0, 100.0),
                reading_order=0,
            ),
        ),
        tables=tables,
        raw={"원문": "구조"} if raw is None else raw,
    )


def write_real_png(
    path: Path,
    *,
    width: int = 200,
    height: int = 100,
) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    pixmap = fitz.Pixmap(
        fitz.csRGB,
        fitz.IRect(0, 0, width, height),
        False,
    )
    pixmap.save(str(path))
    return path


def test_table_cell_comparison_uses_nfkc_all_whitespace_and_reading_order() -> None:
    tokens = (
        ocr_token_fixture(
            text="Ｂ",
            bbox=(50.0, 10.0, 70.0, 30.0),
            reading_order=1,
        ),
        ocr_token_fixture(
            text="Ａ\u2003",
            bbox=(10.0, 10.0, 30.0, 30.0),
            reading_order=0,
        ),
        ocr_token_fixture(
            text="무시",
            bbox=(100.0, 10.0, 120.0, 30.0),
            reading_order=2,
        ),
    )
    structure = structure_page_fixture(
        cells=(
            table_cell_fixture(
                text="A B",
                status="MISMATCH",
            ),
        ),
    )

    compared = compare_table_cells(
        ocr_page_fixture(tokens=tokens),
        structure,
    )

    assert compared.tables[0].cells[0].raw_ocr_comparison_status == "MATCHED"
    assert structure.tables[0].cells[0].raw_ocr_comparison_status == "MISMATCH"
    assert compared is not structure


def test_table_cell_comparison_includes_token_center_on_bbox_boundary() -> None:
    token = ocr_token_fixture(
        text="경계",
        bbox=(0.0, 10.0, 20.0, 30.0),
    )
    structure = structure_page_fixture(
        cells=(
            table_cell_fixture(
                text="경계",
                bbox=(10.0, 0.0, 100.0, 50.0),
            ),
        ),
    )

    compared = compare_table_cells(
        ocr_page_fixture(tokens=(token,)),
        structure,
    )

    assert compared.tables[0].cells[0].raw_ocr_comparison_status == "MATCHED"


@pytest.mark.parametrize(
    ("ocr_text", "cell_text", "expected"),
    (
        (" \n\t", "\u2003", "NOT_COMPARABLE"),
        ("", "면적", "MISMATCH"),
        ("면적", "", "MISMATCH"),
        ("면적 120", "면적 12", "MISMATCH"),
    ),
)
def test_table_cell_comparison_status_is_exact(
    ocr_text: str,
    cell_text: str,
    expected: str,
) -> None:
    compared = compare_table_cells(
        ocr_page_fixture(
            tokens=(ocr_token_fixture(text=ocr_text),),
        ),
        structure_page_fixture(
            cells=(table_cell_fixture(text=cell_text),),
        ),
    )

    assert compared.tables[0].cells[0].raw_ocr_comparison_status == expected


def test_table_cell_comparison_excludes_token_center_outside_cell() -> None:
    compared = compare_table_cells(
        ocr_page_fixture(
            tokens=(
                ocr_token_fixture(
                    text="면적",
                    bbox=(99.0, 10.0, 103.0, 30.0),
                ),
            ),
        ),
        structure_page_fixture(
            cells=(table_cell_fixture(text=""),),
        ),
    )

    assert (
        compared.tables[0].cells[0].raw_ocr_comparison_status
        == "NOT_COMPARABLE"
    )


@pytest.mark.parametrize(
    ("ocr_page_number", "structure_page_number", "token_page_number"),
    (
        (1, 2, 1),
        (1, 1, 2),
    ),
)
def test_table_cell_comparison_rejects_cross_page_inputs(
    ocr_page_number: int,
    structure_page_number: int,
    token_page_number: int,
) -> None:
    with pytest.raises(ArtifactError, match="page"):
        compare_table_cells(
            ocr_page_fixture(
                page_number=ocr_page_number,
                tokens=(
                    ocr_token_fixture(page_number=token_page_number),
                ),
            ),
            structure_page_fixture(page_number=structure_page_number),
        )


@pytest.mark.parametrize("token_page_number", (True, 1.0, 0, -1))
def test_table_cell_comparison_rejects_noninteger_or_nonpositive_token_page(
    token_page_number: object,
) -> None:
    with pytest.raises(ArtifactError, match="page"):
        compare_table_cells(
            ocr_page_fixture(
                tokens=(
                    replace(
                        ocr_token_fixture(),
                        source_page_number=token_page_number,
                    ),
                ),
            ),
            structure_page_fixture(),
        )


def test_page_artifacts_use_fixed_names_hashes_and_lossless_text(
    tmp_path: Path,
) -> None:
    image = write_real_png(tmp_path / "pages" / "0001.png")
    markdown = "한글  원문\n둘째 줄"
    html = "<table><tr><th>면적</th></tr></table>"

    artifact_set = write_page_artifacts(
        root=tmp_path,
        image_path=image,
        route=PageRoute.RAPIDOCR_TABLEFORMER,
        ocr_page=ocr_page_fixture(markdown=markdown),
        structure_page=structure_page_fixture(html=html),
    )

    assert artifact_set.image["file_name"] == "pages/0001.png"
    assert artifact_set.ocr["file_name"] == "pages/0001.ocr.json"
    assert artifact_set.ocr["kind"] == "OCR_JSON"
    assert artifact_set.structure["file_name"] == "pages/0001.structure.json"
    assert artifact_set.markdown["file_name"] == "pages/0001.md"
    assert artifact_set.tables[0]["file_name"] == (
        "pages/0001.tables/0001.html"
    )
    assert artifact_set.tables[0]["kind"] == "TABLE_HTML"
    assert (tmp_path / "pages" / "0001.md").read_text(
        encoding="utf-8"
    ) == markdown
    assert (tmp_path / "pages" / "0001.tables" / "0001.html").read_text(
        encoding="utf-8"
    ) == html
    ocr_bytes = (tmp_path / "pages" / "0001.ocr.json").read_bytes()
    assert ocr_bytes.endswith(b"\n")
    assert b"\\u" not in ocr_bytes
    assert b"\r\n" not in ocr_bytes
    ocr_payload = json.loads(ocr_bytes)
    structure_payload = json.loads(
        (tmp_path / "pages" / "0001.structure.json").read_bytes()
    )
    assert ocr_payload["minimum_confidence"] == 0.91
    assert structure_payload["tables"][0]["html_file"] == (
        "pages/0001.tables/0001.html"
    )
    for record in (
        artifact_set.image,
        artifact_set.ocr,
        artifact_set.structure,
        artifact_set.markdown,
        *artifact_set.tables,
    ):
        assert record["bytes"] > 0
        assert isinstance(record["sha256"], str)
        assert record["sha256"].startswith("sha256:")
        assert record["sha256"] == record["sha256"].lower()


def test_embedded_page_artifacts_match_embedded_schema_contract(
    tmp_path: Path,
) -> None:
    image = write_real_png(tmp_path / "pages" / "0001.png")
    embedded = ocr_page_fixture(
        engine="EMBEDDED_TEXT",
        model_name="embedded-text",
        markdown="내장 텍스트",
        tokens=(
            replace(
                ocr_token_fixture(confidence=1.0),
                model_name="embedded-text",
            ),
        ),
    )
    empty_structure = structure_page_fixture(tables=())

    artifact_set = write_page_artifacts(
        root=tmp_path,
        image_path=image,
        route=PageRoute.EMBEDDED_TEXT,
        ocr_page=embedded,
        structure_page=empty_structure,
    )

    payload = json.loads(
        (tmp_path / artifact_set.ocr["file_name"]).read_text(encoding="utf-8")
    )
    assert payload["engine"] == "EMBEDDED_TEXT"
    assert payload["model_name"] == "embedded-text"
    assert payload["minimum_confidence"] == 1.0
    assert artifact_set.tables == ()


@pytest.mark.parametrize(
    ("route", "engine", "tables", "message"),
    (
        (PageRoute.RAPIDOCR, "EMBEDDED_TEXT", (), "route"),
        (PageRoute.EMBEDDED_TEXT, "RAPIDOCR", (), "route"),
        (PageRoute.RAPIDOCR_TABLEFORMER, "RAPIDOCR", (), "table"),
        (
            PageRoute.RAPIDOCR,
            "RAPIDOCR",
            structure_page_fixture().tables,
            "table",
        ),
    ),
)
def test_page_route_and_table_count_are_validated_before_writes(
    tmp_path: Path,
    route: PageRoute,
    engine: str,
    tables: tuple[TableData, ...],
    message: str,
) -> None:
    image = write_real_png(tmp_path / "pages" / "0001.png")
    before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}
    model_name = "embedded-text" if engine == "EMBEDDED_TEXT" else (
        "korean_PP-OCRv5_rec_mobile"
    )
    tokens = (
        (
            replace(
                ocr_token_fixture(),
                model_name="embedded-text",
            ),
        )
        if engine == "EMBEDDED_TEXT"
        else (ocr_token_fixture(),)
    )

    with pytest.raises(ArtifactError, match=message):
        write_page_artifacts(
            root=tmp_path,
            image_path=image,
            route=route,
            ocr_page=ocr_page_fixture(
                engine=engine,
                model_name=model_name,
                tokens=tokens,
            ),
            structure_page=structure_page_fixture(tables=tables),
        )

    assert {path.relative_to(tmp_path) for path in tmp_path.rglob("*")} == before


def test_noncontinuous_table_numbers_are_rejected_before_writes(
    tmp_path: Path,
) -> None:
    image = write_real_png(tmp_path / "pages" / "0001.png")
    invalid_structure = structure_page_fixture(table_number=2)
    before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}

    with pytest.raises(ArtifactError, match="table_number"):
        write_page_artifacts(
            root=tmp_path,
            image_path=image,
            route=PageRoute.RAPIDOCR_TABLEFORMER,
            ocr_page=ocr_page_fixture(),
            structure_page=invalid_structure,
        )

    assert {path.relative_to(tmp_path) for path in tmp_path.rglob("*")} == before


@pytest.mark.parametrize(
    ("markdown", "html", "message"),
    (
        (" \n\t", "<table><tr><th>면적</th></tr></table>", "Markdown"),
        ("면적", " \n\t", "HTML"),
    ),
)
def test_empty_human_artifacts_are_rejected_before_writes(
    tmp_path: Path,
    markdown: str,
    html: str,
    message: str,
) -> None:
    image = write_real_png(tmp_path / "pages" / "0001.png")
    before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}

    with pytest.raises(ArtifactError, match=message):
        write_page_artifacts(
            root=tmp_path,
            image_path=image,
            route=PageRoute.RAPIDOCR_TABLEFORMER,
            ocr_page=ocr_page_fixture(markdown=markdown),
            structure_page=structure_page_fixture(html=html),
        )

    assert {path.relative_to(tmp_path) for path in tmp_path.rglob("*")} == before


@pytest.mark.parametrize(
    "html",
    (
        '<div data-markup="<table></table>"></div>',
        '<table><tr><th data-rowspan="2">구분</th><th>값</th></tr>'
        "<tr><td>면적</td></tr></table>",
        '<table><tr><th rowspan="3">구분</th><th>값</th></tr>'
        "<tr><td>면적</td></tr></table>",
    ),
)
def test_table_html_requires_real_exact_merged_cell_attributes(
    tmp_path: Path,
    html: str,
) -> None:
    image = write_real_png(tmp_path / "pages" / "0001.png")
    cells = (
        table_cell_fixture(
            text="구분",
            bbox=(0.0, 0.0, 100.0, 100.0),
            start_row=0,
            end_row=2,
            start_column=0,
            end_column=1,
        ),
        table_cell_fixture(
            text="값",
            bbox=(100.0, 0.0, 200.0, 50.0),
            start_row=0,
            end_row=1,
            start_column=1,
            end_column=2,
        ),
        table_cell_fixture(
            text="면적",
            bbox=(100.0, 50.0, 200.0, 100.0),
            start_row=1,
            end_row=2,
            start_column=1,
            end_column=2,
        ),
    )
    before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}

    with pytest.raises(ArtifactError, match="HTML"):
        write_page_artifacts(
            root=tmp_path,
            image_path=image,
            route=PageRoute.RAPIDOCR_TABLEFORMER,
            ocr_page=ocr_page_fixture(),
            structure_page=structure_page_fixture(cells=cells, html=html),
        )

    assert {path.relative_to(tmp_path) for path in tmp_path.rglob("*")} == before


def test_table_html_rejects_merged_span_moved_to_another_grid_position(
    tmp_path: Path,
) -> None:
    image = write_real_png(tmp_path / "pages" / "0001.png")
    cells = (
        table_cell_fixture(
            text="A",
            bbox=(0.0, 0.0, 100.0, 100.0),
            start_row=0,
            end_row=2,
            start_column=0,
            end_column=1,
        ),
        table_cell_fixture(
            text="B",
            bbox=(100.0, 0.0, 200.0, 50.0),
            start_row=0,
            end_row=1,
            start_column=1,
            end_column=2,
        ),
        table_cell_fixture(
            text="C",
            bbox=(100.0, 50.0, 200.0, 100.0),
            start_row=1,
            end_row=2,
            start_column=1,
            end_column=2,
        ),
    )
    moved_span_html = (
        '<table><tr><th>B</th><th rowspan="2">A</th></tr>'
        "<tr><td>C</td></tr></table>"
    )

    with pytest.raises(ArtifactError, match="HTML"):
        write_page_artifacts(
            root=tmp_path,
            image_path=image,
            route=PageRoute.RAPIDOCR_TABLEFORMER,
            ocr_page=ocr_page_fixture(),
            structure_page=structure_page_fixture(
                cells=cells,
                html=moved_span_html,
            ),
        )

    assert not (tmp_path / "pages" / "0001.ocr.json").exists()
    assert not (tmp_path / "pages" / "0001.tables").exists()


@pytest.mark.parametrize(
    "html",
    (
        "<table><tr><td>A<table><tr><td>B</td></tr></table></td></tr></table>",
        '<table><tr><td rowspan="2">A</td><td>B</td></tr>'
        '<tr><td colspan="2">C</td></tr></table>',
        '<table><tr><td colspan="3">A</td></tr><tr><td>B</td></tr></table>',
        "<table><tr><td>A</td><td>B</td></tr><tr></tr></table>",
    ),
)
def test_table_html_grid_is_fail_closed(
    tmp_path: Path,
    html: str,
) -> None:
    image = write_real_png(tmp_path / "pages" / "0001.png")
    cells = (
        table_cell_fixture(
            text="A",
            bbox=(0.0, 0.0, 100.0, 50.0),
            start_row=0,
            end_row=1,
            start_column=0,
            end_column=1,
        ),
        table_cell_fixture(
            text="B",
            bbox=(100.0, 0.0, 200.0, 50.0),
            start_row=0,
            end_row=1,
            start_column=1,
            end_column=2,
        ),
        table_cell_fixture(
            text="C",
            bbox=(0.0, 50.0, 100.0, 100.0),
            start_row=1,
            end_row=2,
            start_column=0,
            end_column=1,
        ),
        table_cell_fixture(
            text="D",
            bbox=(100.0, 50.0, 200.0, 100.0),
            start_row=1,
            end_row=2,
            start_column=1,
            end_column=2,
        ),
    )

    with pytest.raises(ArtifactError, match="HTML"):
        write_page_artifacts(
            root=tmp_path,
            image_path=image,
            route=PageRoute.RAPIDOCR_TABLEFORMER,
            ocr_page=ocr_page_fixture(),
            structure_page=structure_page_fixture(cells=cells, html=html),
        )


def test_all_merged_cell_spans_are_preserved_in_html(tmp_path: Path) -> None:
    image = write_real_png(tmp_path / "pages" / "0001.png")
    cells = (
        table_cell_fixture(
            text="A",
            bbox=(0.0, 0.0, 100.0, 100.0),
            start_row=0,
            end_row=2,
            start_column=0,
            end_column=1,
        ),
        table_cell_fixture(
            text="B",
            bbox=(100.0, 0.0, 200.0, 50.0),
            start_row=0,
            end_row=1,
            start_column=1,
            end_column=2,
        ),
        table_cell_fixture(
            text="C",
            bbox=(100.0, 50.0, 200.0, 100.0),
            start_row=1,
            end_row=2,
            start_column=1,
            end_column=2,
        ),
    )
    html = (
        '<table><tr><th rowspan="2">A</th><th>B</th></tr>'
        "<tr><th>C</th></tr></table>"
    )

    ocr_page = ocr_page_fixture()
    compared_structure = compare_table_cells(
        ocr_page,
        structure_page_fixture(cells=cells, html=html),
    )
    artifact_set = write_page_artifacts(
        root=tmp_path,
        image_path=image,
        route=PageRoute.RAPIDOCR_TABLEFORMER,
        ocr_page=ocr_page,
        structure_page=compared_structure,
    )

    assert len(artifact_set.tables) == 1


def test_nonfinite_json_is_rejected_without_outputs(tmp_path: Path) -> None:
    image = write_real_png(tmp_path / "pages" / "0001.png")
    before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}

    with pytest.raises(ArtifactError, match="JSON"):
        write_page_artifacts(
            root=tmp_path,
            image_path=image,
            route=PageRoute.RAPIDOCR_TABLEFORMER,
            ocr_page=ocr_page_fixture(raw={"bad": float("nan")}),
            structure_page=structure_page_fixture(),
        )

    assert {path.relative_to(tmp_path) for path in tmp_path.rglob("*")} == before


def test_page_and_image_fixed_name_are_validated_before_outputs(
    tmp_path: Path,
) -> None:
    image = write_real_png(tmp_path / "pages" / "wrong.png")
    before = {path.relative_to(tmp_path) for path in tmp_path.rglob("*")}

    with pytest.raises(ArtifactError, match="image"):
        write_page_artifacts(
            root=tmp_path,
            image_path=image,
            route=PageRoute.RAPIDOCR_TABLEFORMER,
            ocr_page=ocr_page_fixture(),
            structure_page=structure_page_fixture(),
        )

    assert {path.relative_to(tmp_path) for path in tmp_path.rglob("*")} == before


def test_file_record_rejects_missing_directory_and_escape(
    tmp_path: Path,
) -> None:
    outside = tmp_path.parent / f"{tmp_path.name}-outside.txt"
    outside.write_text("outside", encoding="utf-8")
    directory = tmp_path / "directory"
    directory.mkdir()

    with pytest.raises(ArtifactError, match="missing"):
        file_record(tmp_path / "missing.txt", tmp_path)
    with pytest.raises(ArtifactError, match="file"):
        file_record(directory, tmp_path)
    with pytest.raises(ArtifactError, match="root"):
        file_record(outside, tmp_path)


def test_file_record_uses_relative_posix_path_bytes_and_lowercase_hash(
    tmp_path: Path,
) -> None:
    path = tmp_path / "pages" / "0001.md"
    path.parent.mkdir()
    path.write_text("한글", encoding="utf-8")

    record = file_record(path, tmp_path)

    assert record == {
        "file_name": "pages/0001.md",
        "bytes": len("한글".encode("utf-8")),
        "sha256": f"sha256:{sha256(path)}",
    }


@pytest.mark.parametrize(
    "unsafe_relative",
    (
        ".",
        "pages",
        "pages/0001.ocr.json",
        "pages/0001.tables",
    ),
)
def test_planned_output_link_or_reparse_is_rejected_before_any_mutation(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    unsafe_relative: str,
) -> None:
    image = write_real_png(tmp_path / "pages" / "0001.png")
    image_before = image.read_bytes()
    outside = tmp_path.parent / f"{tmp_path.name}-outside-sentinel.txt"
    outside.write_text("outside-sentinel", encoding="utf-8")
    unsafe_path = (
        tmp_path
        if unsafe_relative == "."
        else tmp_path / Path(unsafe_relative)
    )
    detector_calls: list[Path] = []
    mutation_calls: list[tuple[str, Path]] = []

    def fake_link_or_reparse(path: Path) -> bool:
        normalized = Path(path)
        detector_calls.append(normalized)
        return normalized == unsafe_path

    def forbidden_mkdir(path: Path, *args: object, **kwargs: object) -> None:
        mutation_calls.append(("mkdir", Path(path)))
        raise AssertionError("mkdir must not be called")

    def forbidden_write(path: Path, data: bytes) -> int:
        mutation_calls.append(("write", Path(path)))
        raise AssertionError("write_bytes must not be called")

    monkeypatch.setattr(
        artifact_module,
        "_is_link_or_reparse",
        fake_link_or_reparse,
        raising=False,
    )
    monkeypatch.setattr(Path, "mkdir", forbidden_mkdir)
    monkeypatch.setattr(Path, "write_bytes", forbidden_write)

    with pytest.raises(ArtifactError, match="link|reparse|unsafe"):
        write_page_artifacts(
            root=tmp_path,
            image_path=image,
            route=PageRoute.RAPIDOCR_TABLEFORMER,
            ocr_page=ocr_page_fixture(),
            structure_page=structure_page_fixture(),
        )

    assert unsafe_path in detector_calls
    assert mutation_calls == []
    assert outside.read_text(encoding="utf-8") == "outside-sentinel"
    assert image.read_bytes() == image_before
    assert not (tmp_path / "pages" / "0001.ocr.json").exists()
    assert not (tmp_path / "pages" / "0001.structure.json").exists()
    assert not (tmp_path / "pages" / "0001.md").exists()
    assert not (tmp_path / "pages" / "0001.tables").exists()


def test_existing_output_target_is_rejected_without_mutation(
    tmp_path: Path,
) -> None:
    image = write_real_png(tmp_path / "pages" / "0001.png")
    existing = tmp_path / "pages" / "0001.ocr.json"
    existing.write_text("sentinel", encoding="utf-8")

    with pytest.raises(ArtifactError, match="exists|fresh"):
        write_page_artifacts(
            root=tmp_path,
            image_path=image,
            route=PageRoute.RAPIDOCR_TABLEFORMER,
            ocr_page=ocr_page_fixture(),
            structure_page=structure_page_fixture(),
        )

    assert existing.read_text(encoding="utf-8") == "sentinel"
    assert not (tmp_path / "pages" / "0001.structure.json").exists()
    assert not (tmp_path / "pages" / "0001.md").exists()
    assert not (tmp_path / "pages" / "0001.tables").exists()


def test_ordinary_exceptions_are_normalized_but_baseexceptions_propagate(
    tmp_path: Path,
) -> None:
    class BrokenPath:
        def __fspath__(self) -> str:
            raise ValueError("broken")

    class StopPath:
        def __fspath__(self) -> str:
            raise KeyboardInterrupt

    with pytest.raises(ArtifactError, match="broken"):
        file_record(BrokenPath(), tmp_path)  # type: ignore[arg-type]
    with pytest.raises(KeyboardInterrupt):
        file_record(StopPath(), tmp_path)  # type: ignore[arg-type]


def test_compare_table_cells_normalizes_exception_and_propagates_baseexception() -> None:
    class BrokenOcrPage:
        @property
        def page_number(self) -> int:
            raise ValueError("compare broken")

    class StoppedOcrPage:
        @property
        def page_number(self) -> int:
            raise KeyboardInterrupt

    with pytest.raises(ArtifactError, match="compare broken"):
        compare_table_cells(  # type: ignore[arg-type]
            BrokenOcrPage(),
            structure_page_fixture(),
        )
    with pytest.raises(KeyboardInterrupt):
        compare_table_cells(  # type: ignore[arg-type]
            StoppedOcrPage(),
            structure_page_fixture(),
        )


def test_write_page_artifacts_normalizes_exception_and_propagates_baseexception(
    tmp_path: Path,
) -> None:
    class BrokenPath:
        def __fspath__(self) -> str:
            raise ValueError("write broken")

    class StoppedPath:
        def __fspath__(self) -> str:
            raise KeyboardInterrupt

    with pytest.raises(ArtifactError, match="write broken"):
        write_page_artifacts(
            root=BrokenPath(),  # type: ignore[arg-type]
            image_path=tmp_path / "pages" / "0001.png",
            route=PageRoute.RAPIDOCR_TABLEFORMER,
            ocr_page=ocr_page_fixture(),
            structure_page=structure_page_fixture(),
        )
    with pytest.raises(KeyboardInterrupt):
        write_page_artifacts(
            root=StoppedPath(),  # type: ignore[arg-type]
            image_path=tmp_path / "pages" / "0001.png",
            route=PageRoute.RAPIDOCR_TABLEFORMER,
            ocr_page=ocr_page_fixture(),
            structure_page=structure_page_fixture(),
        )


@pytest.mark.parametrize("invalid", (True, float("nan"), float("inf")))
def test_contracts_reject_boolean_and_nonfinite_numeric_values(
    invalid: object,
) -> None:
    payload = valid_ocr_page()
    payload["blocks"][0]["recognition_confidence"] = invalid  # type: ignore[index]
    with pytest.raises(ValidationError):
        validate_ocr_page(payload)

    structure = valid_structure_page()
    structure["tables"][0]["bbox"][0] = invalid  # type: ignore[index]
    with pytest.raises(ValidationError):
        validate_structure_page(structure)


def test_ocr_page_model_and_minimum_confidence_are_cross_checked() -> None:
    payload = valid_ocr_page()
    payload["blocks"][0]["model_name"] = "different-model"  # type: ignore[index]
    with pytest.raises(ValidationError, match="model_name"):
        validate_ocr_page(payload)

    payload = valid_ocr_page()
    payload["minimum_confidence"] = 0.5
    with pytest.raises(ValidationError, match="minimum_confidence"):
        validate_ocr_page(payload)


def test_table_cells_reject_identical_or_geometrically_overlapping_bboxes() -> None:
    first = cell(
        text="A",
        bbox=[0, 0, 100, 100],
        start_column=0,
        end_column=1,
    )
    second = cell(
        text="B",
        bbox=[50, 0, 150, 100],
        start_column=1,
        end_column=2,
    )
    payload = table(num_columns=2, cells=[first, second])

    with pytest.raises(ValidationError, match="bbox|geometric"):
        validate_table_topology(payload)


def test_token_cannot_be_assigned_to_two_table_cells() -> None:
    token = ocr_token_fixture(bbox=(40.0, 10.0, 60.0, 30.0))
    structure = structure_page_fixture(
        cells=(
            table_cell_fixture(
                text="A",
                bbox=(0.0, 0.0, 60.0, 50.0),
                start_column=0,
                end_column=1,
            ),
            table_cell_fixture(
                text="B",
                bbox=(40.0, 0.0, 100.0, 50.0),
                start_column=1,
                end_column=2,
            ),
        )
    )

    with pytest.raises(ArtifactError, match="two|multiple|ambiguous"):
        compare_table_cells(ocr_page_fixture(tokens=(token,)), structure)


def test_numeric_whitespace_cannot_create_a_false_match() -> None:
    compared = compare_table_cells(
        ocr_page_fixture(tokens=(ocr_token_fixture(text="12 34"),)),
        structure_page_fixture(cells=(table_cell_fixture(text="1234"),)),
    )

    assert compared.tables[0].cells[0].raw_ocr_comparison_status == "MISMATCH"


@pytest.mark.parametrize(
    "html",
    (
        "<script></script><table><tr><th>면적</th></tr></table>",
        '<table onclick="x"><tr><th>면적</th></tr></table>',
        '<table><tbody><tr><th><a href="https://example.test">면적</a></th></tr></tbody></table>',
        "<table><tr><td>면적</td></tr></table>trailing",
    ),
)
def test_table_html_rejects_active_unknown_or_outside_content(
    tmp_path: Path,
    html: str,
) -> None:
    image = write_real_png(tmp_path / "pages" / "0001.png")
    with pytest.raises(ArtifactError, match="HTML"):
        write_page_artifacts(
            root=tmp_path,
            image_path=image,
            route=PageRoute.RAPIDOCR_TABLEFORMER,
            ocr_page=ocr_page_fixture(),
            structure_page=structure_page_fixture(
                cells=(table_cell_fixture(text="면적"),),
                html=html,
            ),
        )


def test_table_html_cell_text_and_header_tag_match_structure(
    tmp_path: Path,
) -> None:
    image = write_real_png(tmp_path / "pages" / "0001.png")
    with pytest.raises(ArtifactError, match="HTML"):
        write_page_artifacts(
            root=tmp_path,
            image_path=image,
            route=PageRoute.RAPIDOCR_TABLEFORMER,
            ocr_page=ocr_page_fixture(),
            structure_page=structure_page_fixture(
                cells=(table_cell_fixture(text="면적"),),
                html="<table><tr><td>다름</td></tr></table>",
            ),
        )


def test_png_dimensions_must_match_structure_coordinate_space(
    tmp_path: Path,
) -> None:
    image = write_real_png(
        tmp_path / "pages" / "0001.png",
        width=201,
        height=100,
    )
    with pytest.raises(ArtifactError, match="dimension|coordinate"):
        write_page_artifacts(
            root=tmp_path,
            image_path=image,
            route=PageRoute.RAPIDOCR_TABLEFORMER,
            ocr_page=ocr_page_fixture(),
            structure_page=structure_page_fixture(),
        )


@pytest.mark.parametrize(
    "field",
    (
        "num_rows",
        "num_columns",
        "start_row",
        "end_row",
        "start_column",
        "end_column",
        "row_span",
        "col_span",
    ),
)
@pytest.mark.parametrize("invalid", (True, 1.0, "1"))
def test_table_topology_grid_fields_require_strict_integers(
    field: str,
    invalid: object,
) -> None:
    payload = table()
    if field in {"num_rows", "num_columns"}:
        payload[field] = invalid
    else:
        payload["cells"][0][field] = invalid  # type: ignore[index]

    with pytest.raises(ValidationError, match="integer|topology"):
        validate_table_topology(payload)


def test_ocr_polygon_requires_positive_area() -> None:
    payload = valid_ocr_page()
    payload["blocks"][0]["polygon"] = [  # type: ignore[index]
        [10, 10],
        [20, 10],
        [30, 10],
        [40, 10],
    ]
    payload["blocks"][0]["bbox"] = [10, 10, 40, 20]  # type: ignore[index]

    with pytest.raises(ValidationError, match="polygon|area"):
        validate_ocr_page(payload)


def test_ocr_bbox_must_match_polygon_envelope() -> None:
    payload = valid_ocr_page()
    payload["blocks"][0]["bbox"] = [10, 10, 189, 40]  # type: ignore[index]

    with pytest.raises(ValidationError, match="polygon|bbox|envelope"):
        validate_ocr_page(payload)


def test_table_comparison_does_not_fold_non_width_compatibility_symbols() -> None:
    compared = compare_table_cells(
        ocr_page_fixture(tokens=(ocr_token_fixture(text="①"),)),
        structure_page_fixture(
            cells=(table_cell_fixture(text="1", status="MATCHED"),),
            html="<table><tr><th>1</th></tr></table>",
        ),
    )

    assert (
        compared.tables[0].cells[0].raw_ocr_comparison_status
        == "MISMATCH"
    )


def test_writer_rejects_claimed_comparison_status_not_recomputed_from_ocr(
    tmp_path: Path,
) -> None:
    image = write_real_png(tmp_path / "pages" / "0001.png")
    with pytest.raises(ArtifactError, match="comparison|MATCHED|status"):
        write_page_artifacts(
            root=tmp_path,
            image_path=image,
            route=PageRoute.RAPIDOCR_TABLEFORMER,
            ocr_page=ocr_page_fixture(
                tokens=(ocr_token_fixture(text="different"),)
            ),
            structure_page=structure_page_fixture(
                cells=(
                    table_cell_fixture(
                        text="expected",
                        status="MATCHED",
                    ),
                ),
                html="<table><tr><th>expected</th></tr></table>",
            ),
        )


def test_row_section_requires_th_and_is_serialized(tmp_path: Path) -> None:
    image = write_real_png(tmp_path / "pages" / "0001.png")
    text = table_cell_fixture().text
    result = write_page_artifacts(
        root=tmp_path,
        image_path=image,
        route=PageRoute.RAPIDOCR_TABLEFORMER,
        ocr_page=ocr_page_fixture(),
        structure_page=structure_page_fixture(
            cells=(
                table_cell_fixture(
                    is_column_header=False,
                    is_row_section=True,
                ),
            ),
            html=f"<table><tr><th>{text}</th></tr></table>",
        ),
    )

    payload = json.loads(
        (tmp_path / result.structure["file_name"]).read_text(encoding="utf-8")
    )
    assert payload["tables"][0]["cells"][0]["is_row_section"] is True


def test_docling_caption_div_is_allowed_but_general_div_is_rejected(
    tmp_path: Path,
) -> None:
    image = write_real_png(tmp_path / "pages" / "0001.png")
    text = table_cell_fixture().text
    write_page_artifacts(
        root=tmp_path,
        image_path=image,
        route=PageRoute.RAPIDOCR_TABLEFORMER,
        ocr_page=ocr_page_fixture(),
        structure_page=structure_page_fixture(
            html=(
                '<table><caption><div class="caption" dir="rtl">'
                "제목</div></caption>"
                f"<tbody><tr><th>{text}</th></tr></tbody></table>"
            ),
        ),
    )


@pytest.mark.parametrize(
    "invalid_html",
    (
        (
            '<table><div class="caption">제목</div>'
            "<tr><th>{text}</th></tr></table>"
        ),
        (
            "<table><caption><div>제목</div></caption>"
            "<tr><th>{text}</th></tr></table>"
        ),
        (
            '<table><caption><div class="other">제목</div></caption>'
            "<tr><th>{text}</th></tr></table>"
        ),
        (
            '<table><caption><caption><div class="caption">제목</div>'
            "</caption></caption><tr><th>{text}</th></tr></table>"
        ),
        (
            '<caption><div class="caption">제목</div></caption>'
            "<table><tr><th>{text}</th></tr></table>"
        ),
        (
            "<table><tr><th>{text}</th></tr>"
            '<caption><div class="caption">제목</div></caption></table>'
        ),
    ),
    ids=(
        "direct-div-without-caption",
        "general-div",
        "wrong-caption-class",
        "nested-caption",
        "caption-outside-table",
        "caption-after-row",
    ),
)
def test_table_html_rejects_invalid_caption_nesting(
    tmp_path: Path,
    invalid_html: str,
) -> None:
    image = write_real_png(tmp_path / "pages" / "0001.png")
    text = table_cell_fixture().text
    with pytest.raises(ArtifactError, match="HTML"):
        write_page_artifacts(
            root=tmp_path,
            image_path=image,
            route=PageRoute.RAPIDOCR_TABLEFORMER,
            ocr_page=ocr_page_fixture(),
            structure_page=structure_page_fixture(
                html=invalid_html.format(text=text),
            ),
        )


@pytest.mark.parametrize(
    "prefix",
    (
        "<!--comment-->",
        "<!DOCTYPE html>",
        "<?target data?>",
        "<![CDATA[data]]>",
        "</unknown>",
    ),
)
def test_table_html_rejects_special_or_unknown_syntax(
    tmp_path: Path,
    prefix: str,
) -> None:
    image = write_real_png(tmp_path / "pages" / "0001.png")
    with pytest.raises(ArtifactError, match="HTML"):
        write_page_artifacts(
            root=tmp_path,
            image_path=image,
            route=PageRoute.RAPIDOCR_TABLEFORMER,
            ocr_page=ocr_page_fixture(),
            structure_page=structure_page_fixture(
                html=prefix + "<table><tr><th>硫댁쟻</th></tr></table>",
            ),
        )


def test_table_html_uses_nfc_not_nfkc_for_text_identity(
    tmp_path: Path,
) -> None:
    image = write_real_png(tmp_path / "pages" / "0001.png")
    with pytest.raises(ArtifactError, match="HTML"):
        write_page_artifacts(
            root=tmp_path,
            image_path=image,
            route=PageRoute.RAPIDOCR_TABLEFORMER,
            ocr_page=ocr_page_fixture(tokens=(ocr_token_fixture(text="1"),)),
            structure_page=structure_page_fixture(
                cells=(table_cell_fixture(text="1"),),
                html="<table><tr><th>①</th></tr></table>",
            ),
        )


def _refresh_output_record(
    payload: dict[str, object],
    root: Path,
    *,
    kind: str | None = None,
    image: bool = False,
) -> None:
    page = payload["pages"][0]  # type: ignore[index]
    if image:
        record = page["image"]
    else:
        record = next(
            item for item in page["outputs"] if item["kind"] == kind
        )
    path = root / record["file_name"]
    record["bytes"] = path.stat().st_size
    record["sha256"] = f"sha256:{sha256(path)}"


def test_final_verifier_rejects_duplicate_json_keys(tmp_path: Path) -> None:
    payload = write_page_outputs(tmp_path)
    path = tmp_path / "pages" / "0001.ocr.json"
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace(
            '"schema_version": "2.0.0"',
            '"schema_version": "2.0.0", "schema_version": "2.0.0"',
            1,
        ),
        encoding="utf-8",
    )
    _refresh_output_record(payload, tmp_path, kind="OCR_JSON")

    with pytest.raises(ValidationError, match="duplicate|strict JSON"):
        validate_output_hashes(payload, tmp_path)


def test_final_verifier_rejects_jpeg_bytes_named_png(tmp_path: Path) -> None:
    from PIL import Image

    payload = write_page_outputs(tmp_path)
    path = tmp_path / "pages" / "0001.png"
    Image.new("RGB", (200, 100), "white").save(path, format="JPEG")
    _refresh_output_record(payload, tmp_path, image=True)

    with pytest.raises(ValidationError, match="PNG"):
        validate_output_hashes(payload, tmp_path)


def test_final_verifier_binds_png_dimensions_to_json_coordinate_space(
    tmp_path: Path,
) -> None:
    payload = write_page_outputs(tmp_path)
    for kind in ("OCR_JSON", "STRUCTURE_JSON"):
        path = tmp_path / "pages" / (
            "0001.ocr.json" if kind == "OCR_JSON" else "0001.structure.json"
        )
        item = json.loads(path.read_text(encoding="utf-8"))
        item["coordinate_space"]["width"] = 201
        path.write_text(json.dumps(item) + "\n", encoding="utf-8")
        _refresh_output_record(payload, tmp_path, kind=kind)

    with pytest.raises(ValidationError, match="PNG|coordinate|dimension"):
        validate_output_hashes(payload, tmp_path)


def test_final_verifier_revalidates_hashed_table_html_semantics(
    tmp_path: Path,
) -> None:
    payload = write_page_outputs(tmp_path)
    path = tmp_path / "pages" / "0001.tables" / "0001.html"
    path.write_text(
        "<table><tbody><tr><th>wrong</th></tr></tbody></table>",
        encoding="utf-8",
    )
    _refresh_output_record(payload, tmp_path, kind="TABLE_HTML")

    with pytest.raises(ValidationError, match="HTML"):
        validate_output_hashes(payload, tmp_path)


def test_output_target_inserted_after_preflight_is_not_followed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    image = write_real_png(tmp_path / "pages" / "0001.png")
    target = tmp_path / "pages" / "0001.ocr.json"
    original_preflight = artifact_module._preflight_output_paths

    def insert_target(root: Path, paths: tuple[Path, ...]) -> tuple[Path, ...]:
        directories = original_preflight(root, paths)
        target.write_text("sentinel", encoding="utf-8")
        return directories

    monkeypatch.setattr(
        artifact_module,
        "_preflight_output_paths",
        insert_target,
    )
    with pytest.raises(ArtifactError, match="exists|exclusive|fresh"):
        write_page_artifacts(
            root=tmp_path,
            image_path=image,
            route=PageRoute.RAPIDOCR_TABLEFORMER,
            ocr_page=ocr_page_fixture(),
            structure_page=structure_page_fixture(),
        )
    assert target.read_text(encoding="utf-8") == "sentinel"
