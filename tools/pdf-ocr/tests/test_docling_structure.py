from __future__ import annotations

import json
import hashlib
import math
from collections.abc import Mapping
from pathlib import Path
from pathlib import PurePosixPath
from types import SimpleNamespace
from typing import Any

import fitz
import pytest
from docling.datamodel.accelerator_options import AcceleratorDevice
from docling.datamodel.base_models import ConversionStatus, InputFormat
from docling.datamodel.pipeline_options import (
    RapidOcrOptions,
    TableFormerMode,
)
from docling.document_converter import (
    DocumentConverter,
    ImageFormatOption,
)
from docling_core.types.doc.base import CoordOrigin

from pdf_ocr.model_lock import (
    LockedArtifact,
    LockedFile,
    docling_artifacts_root,
)
from pdf_ocr.ocr import build_rapidocr_params
from pdf_ocr.structure import (
    DoclingRunner,
    DoclingStructureError,
    _top_left_pixel_bbox,
    build_layout_pipeline_options,
    build_table_pipeline_options,
    create_layout_converter,
    create_table_converter,
)


def _artifact(path: Path, role: str, model_home: Path) -> LockedArtifact:
    root = path if path.is_dir() else path.parent
    entrypoint = PurePosixPath(".") if path.is_dir() else PurePosixPath(path.name)
    if path.is_dir():
        sentinel = path / "model.bin"
        sentinel.write_bytes(role.encode("utf-8"))
    files = []
    for file_path in sorted(item for item in root.rglob("*") if item.is_file()):
        data = file_path.read_bytes()
        files.append(
            LockedFile(
                path=file_path.resolve(),
                bytes=len(data),
                sha256=f"sha256:{hashlib.sha256(data).hexdigest()}",
                relative_path=PurePosixPath(
                    file_path.relative_to(root).as_posix()
                ),
            )
        )
    return LockedArtifact(
        component=(
            "RAPIDOCR"
            if role.startswith("rapidocr_")
            else "DOCLING"
            if role == "docling_layout"
            else "TABLEFORMER"
        ),
        role=role,
        name=role,
        source_url="https://example.invalid/model",
        license="TEST-ONLY",
        model_home=model_home.resolve(),
        root_relative_path=PurePosixPath(
            root.relative_to(model_home).as_posix()
        ),
        entrypoint_relative_path=entrypoint,
        root=root.resolve(),
        path=path.resolve(),
        files=tuple(files),
    )


@pytest.fixture
def locked_artifacts(tmp_path: Path) -> tuple[LockedArtifact, ...]:
    model_home = tmp_path / "models"
    docling_root = model_home / "docling-artifacts"
    layout = docling_root / "layout"
    tableformer = docling_root / "tableformer"
    layout.mkdir(parents=True)
    tableformer.mkdir()

    paths: dict[str, Path] = {}
    for role in (
        "rapidocr_det",
        "rapidocr_cls",
        "rapidocr_rec",
        "rapidocr_rec_keys",
        "rapidocr_font",
    ):
        path = model_home / role / f"{role}.bin"
        path.parent.mkdir(parents=True)
        path.write_bytes(role.encode("utf-8"))
        paths[role] = path

    return (
        _artifact(layout, "docling_layout", model_home),
        _artifact(tableformer, "tableformer", model_home),
        *(
            _artifact(paths[role], role, model_home)
            for role in (
                "rapidocr_det",
                "rapidocr_cls",
                "rapidocr_rec",
                "rapidocr_rec_keys",
                "rapidocr_font",
            )
        ),
    )


@pytest.fixture
def png_path(tmp_path: Path) -> Path:
    path = tmp_path / "0007.png"
    pixmap = fitz.Pixmap(fitz.csRGB, fitz.IRect(0, 0, 200, 100))
    pixmap.clear_with(255)
    pixmap.save(path)
    return path


def _bbox(
    left: float = 0,
    top: float = 0,
    right: float = 100,
    bottom: float = 50,
    *,
    origin: CoordOrigin = CoordOrigin.TOPLEFT,
) -> SimpleNamespace:
    return SimpleNamespace(
        l=left,
        t=top,
        r=right,
        b=bottom,
        coord_origin=origin,
    )


def _prov(
    *,
    page_no: int = 1,
    bbox: Any | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        page_no=page_no,
        bbox=_bbox() if bbox is None else bbox,
    )


class FakeItem:
    def __init__(
        self,
        label: Any,
        *,
        bbox: Any | None = None,
        prov: Any | None = None,
        data: Any | None = None,
        html: Any = "<table></table>",
        export_error: BaseException | None = None,
    ) -> None:
        self.label = label
        self.prov = [_prov(bbox=bbox)] if prov is None else prov
        if data is not None:
            self.data = data
        self._html = html
        self._export_error = export_error

    def export_to_html(self, *, doc: Any) -> Any:
        if self._export_error is not None:
            raise self._export_error
        return self._html


class FakeDocument:
    def __init__(
        self,
        items: Any,
        *,
        raw: Any | None = None,
        iterate_error: BaseException | None = None,
        export_error: BaseException | None = None,
    ) -> None:
        self._items = items
        self._raw = {"name": "lossless", "unicode": "면적㎡"} if raw is None else raw
        self._iterate_error = iterate_error
        self._export_error = export_error

    def iterate_items(self) -> Any:
        if self._iterate_error is not None:
            raise self._iterate_error
        return self._items

    def export_to_dict(self) -> Any:
        if self._export_error is not None:
            raise self._export_error
        return self._raw


def _result(
    items: Any,
    *,
    status: Any = ConversionStatus.SUCCESS,
    pages: Any | None = None,
    raw: Any | None = None,
    document: Any | None = None,
) -> SimpleNamespace:
    if pages is None:
        pages = [
            SimpleNamespace(
                page_no=1,
                size=SimpleNamespace(width=100, height=50),
            )
        ]
    if document is None:
        document = FakeDocument(items, raw=raw)
    return SimpleNamespace(
        status=status,
        pages=pages,
        document=document,
    )


class FakeConverter:
    def __init__(
        self,
        result: Any = None,
        *,
        error: BaseException | None = None,
    ) -> None:
        self.result = result
        self.error = error
        self.calls: list[str] = []

    def convert(self, source: str) -> Any:
        self.calls.append(source)
        if self.error is not None:
            raise self.error
        return self.result


def _runner(result: Any) -> tuple[DoclingRunner, FakeConverter]:
    converter = FakeConverter(result)
    return (
        DoclingRunner(
            layout_converter=converter,
            table_converter=converter,
        ),
        converter,
    )


def _valid_cells() -> list[dict[str, Any]]:
    return [
        {
            "text": "구분",
            "bbox": [0, 0, 50, 50],
            "start_row_offset_idx": 0,
            "end_row_offset_idx": 2,
            "start_col_offset_idx": 0,
            "end_col_offset_idx": 1,
            "column_header": True,
            "row_header": False,
            "row_section": False,
        },
        {
            "text": "면적",
            "bbox": [50, 0, 100, 25],
            "start_row_offset_idx": 0,
            "end_row_offset_idx": 1,
            "start_col_offset_idx": 1,
            "end_col_offset_idx": 2,
            "column_header": True,
            "row_header": False,
            "row_section": False,
        },
        {
            "text": "㎡",
            "bbox": [50, 25, 100, 50],
            "start_row_offset_idx": 1,
            "end_row_offset_idx": 2,
            "start_col_offset_idx": 1,
            "end_col_offset_idx": 2,
            "column_header": True,
            "row_header": False,
            "row_section": False,
        },
    ]


def _table_item(
    *,
    cells: Any | None = None,
    num_rows: Any = 2,
    num_cols: Any = 2,
    bbox: Any | None = None,
    html: Any = (
        '<table><tr><th rowspan="2">구분</th><th>면적</th></tr>'
        "<tr><th>㎡</th></tr></table>"
    ),
) -> FakeItem:
    return FakeItem(
        "table",
        bbox=_bbox() if bbox is None else bbox,
        data=SimpleNamespace(
            num_rows=num_rows,
            num_cols=num_cols,
            table_cells=_valid_cells() if cells is None else cells,
        ),
        html=html,
    )


def test_layout_pass_disables_ocr_tableformer_remote_and_plugins(
    locked_artifacts: tuple[LockedArtifact, ...],
) -> None:
    options = build_layout_pipeline_options(locked_artifacts)

    assert options.do_ocr is False
    assert options.do_table_structure is False
    assert options.enable_remote_services is False
    assert options.allow_external_plugins is False
    assert Path(options.artifacts_path) == docling_artifacts_root(locked_artifacts)
    assert options.accelerator_options.device == AcceleratorDevice.CPU


def test_table_pass_reuses_task4_rapidocr_params_and_accurate_tableformer(
    locked_artifacts: tuple[LockedArtifact, ...],
) -> None:
    options = build_table_pipeline_options(locked_artifacts)

    assert options.do_ocr is True
    assert options.do_table_structure is True
    assert options.enable_remote_services is False
    assert options.allow_external_plugins is False
    assert Path(options.artifacts_path) == docling_artifacts_root(locked_artifacts)
    assert options.accelerator_options.device == AcceleratorDevice.CPU
    assert isinstance(options.ocr_options, RapidOcrOptions)
    assert options.ocr_options.backend == "onnxruntime"
    assert options.ocr_options.force_full_page_ocr is True
    assert options.ocr_options.text_score == 0.0
    assert options.ocr_options.use_det is True
    assert options.ocr_options.use_cls is False
    assert options.ocr_options.use_rec is True
    assert options.ocr_options.cls_model_path == str(
        next(
            item.path
            for item in locked_artifacts
            if item.role == "rapidocr_cls"
        ).resolve()
    )
    assert options.ocr_options.rapidocr_params == build_rapidocr_params(
        locked_artifacts
    )
    assert options.ocr_options.rapidocr_params[
        "EngineConfig.onnxruntime.use_cuda"
    ] is False
    assert options.ocr_options.rapidocr_params[
        "EngineConfig.onnxruntime.use_dml"
    ] is False
    assert options.ocr_options.rapidocr_params["Cls.model_path"] == str(
        next(
            item.path
            for item in locked_artifacts
            if item.role == "rapidocr_cls"
        ).resolve()
    )
    assert options.table_structure_options.do_cell_matching is True
    assert options.table_structure_options.mode is TableFormerMode.ACCURATE


@pytest.mark.parametrize(
    "factory",
    [create_layout_converter, create_table_converter],
)
def test_converter_is_image_only_and_uses_image_format_option(
    factory: Any,
    locked_artifacts: tuple[LockedArtifact, ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    events: list[object] = []

    class FakeDocumentConverter:
        def __init__(self, **kwargs: Any) -> None:
            self.kwargs = kwargs
            events.append("constructed")

        def initialize_pipeline(self, value: Any) -> None:
            events.append(("initialized", value))

    monkeypatch.setattr(
        "pdf_ocr.structure.DocumentConverter",
        FakeDocumentConverter,
    )
    converter = factory(locked_artifacts)

    assert isinstance(converter, FakeDocumentConverter)
    assert converter.kwargs["allowed_formats"] == [InputFormat.IMAGE]
    assert set(converter.kwargs["format_options"]) == {InputFormat.IMAGE}
    assert isinstance(
        converter.kwargs["format_options"][InputFormat.IMAGE],
        ImageFormatOption,
    )
    assert events == ["constructed", ("initialized", InputFormat.IMAGE)]


@pytest.mark.parametrize(
    "builder",
    [build_layout_pipeline_options, build_table_pipeline_options],
)
def test_pipeline_options_revalidate_locked_files_before_consuming_paths(
    builder: Any,
    locked_artifacts: tuple[LockedArtifact, ...],
) -> None:
    locked_artifacts[0].files[0].path.write_bytes(b"tampered")

    with pytest.raises(DoclingStructureError, match="model|size|SHA|locked"):
        builder(locked_artifacts)


def test_docling_rejects_jpeg_bytes_renamed_png_before_converter(
    tmp_path: Path,
) -> None:
    from PIL import Image

    image_path = tmp_path / "renamed.png"
    Image.new("RGB", (20, 10), "white").save(image_path, format="JPEG")
    runner, converter = _runner(None)

    with pytest.raises(DoclingStructureError, match="PNG"):
        runner.detect_layout(image_path, page_number=1)

    assert converter.calls == []


def test_non_png_is_rejected_before_converter_is_called(tmp_path: Path) -> None:
    runner, converter = _runner(None)

    with pytest.raises(DoclingStructureError, match="PNG input only"):
        runner.detect_layout(tmp_path / "page.pdf", page_number=1)

    assert converter.calls == []


@pytest.mark.parametrize(
    "status",
    [
        ConversionStatus.PARTIAL_SUCCESS,
        ConversionStatus.FAILURE,
        ConversionStatus.SKIPPED,
        "success",
    ],
)
def test_non_success_conversion_status_is_rejected(
    png_path: Path,
    status: Any,
) -> None:
    runner, _ = _runner(_result([], status=status))

    with pytest.raises(DoclingStructureError, match="fully succeed"):
        runner.detect_layout(png_path, page_number=1)


@pytest.mark.parametrize(
    "pages",
    [
        [],
        [
            SimpleNamespace(
                page_no=1,
                size=SimpleNamespace(width=100, height=50),
            ),
            SimpleNamespace(
                page_no=2,
                size=SimpleNamespace(width=100, height=50),
            ),
        ],
        "one-page",
        {"page": 1},
    ],
)
def test_conversion_requires_one_ordered_page(
    png_path: Path,
    pages: Any,
) -> None:
    runner, _ = _runner(_result([], pages=pages))

    with pytest.raises(DoclingStructureError, match="one page"):
        runner.detect_layout(png_path, page_number=1)


def test_missing_result_status_is_normalized(png_path: Path) -> None:
    runner, _ = _runner(SimpleNamespace(pages=[], document=FakeDocument([])))

    with pytest.raises(DoclingStructureError, match="conversion result"):
        runner.detect_layout(png_path, page_number=1)


def test_converter_exception_is_normalized(png_path: Path) -> None:
    converter = FakeConverter(error=ValueError("broken converter"))
    runner = DoclingRunner(
        layout_converter=converter,
        table_converter=converter,
    )

    with pytest.raises(
        DoclingStructureError,
        match="Docling conversion failed: broken converter",
    ):
        runner.detect_layout(png_path, page_number=1)


def test_converter_baseexception_is_not_caught(png_path: Path) -> None:
    converter = FakeConverter(error=KeyboardInterrupt())
    runner = DoclingRunner(
        layout_converter=converter,
        table_converter=converter,
    )

    with pytest.raises(KeyboardInterrupt):
        runner.detect_layout(png_path, page_number=1)


def test_top_left_coordinates_are_scaled_to_png_pixels() -> None:
    assert _top_left_pixel_bbox(
        left=10,
        top=5,
        right=30,
        bottom=15,
        origin="TOPLEFT",
        source_width=100,
        source_height=50,
        image_width=200,
        image_height=100,
    ) == (20.0, 10.0, 60.0, 30.0)


def test_bottom_left_coordinates_use_docling_origin_semantics() -> None:
    assert _top_left_pixel_bbox(
        left=10,
        top=40,
        right=30,
        bottom=20,
        origin="BOTTOMLEFT",
        source_width=100,
        source_height=50,
        image_width=200,
        image_height=100,
    ) == (20.0, 20.0, 60.0, 60.0)


@pytest.mark.parametrize(
    "overrides, message",
    [
        ({"origin": "CENTER"}, "origin"),
        ({"source_width": 0}, "coordinate space"),
        ({"source_height": math.nan}, "coordinate space"),
        ({"image_width": 0}, "page image"),
        ({"left": -1}, "outside"),
        ({"right": 101}, "outside"),
        ({"left": 20, "right": 20}, "outside"),
        ({"top": 30, "bottom": 20}, "outside"),
        ({"left": math.nan}, "finite"),
        ({"bottom": math.inf}, "finite"),
        ({"left": True}, "numeric"),
    ],
)
def test_coordinate_transform_rejects_invalid_values(
    overrides: dict[str, Any],
    message: str,
) -> None:
    values: dict[str, Any] = {
        "left": 10,
        "top": 5,
        "right": 30,
        "bottom": 15,
        "origin": "TOPLEFT",
        "source_width": 100,
        "source_height": 50,
        "image_width": 200,
        "image_height": 100,
    }
    values.update(overrides)

    with pytest.raises(DoclingStructureError, match=message):
        _top_left_pixel_bbox(**values)


def test_layout_rebinds_original_page_number_and_detects_table(
    png_path: Path,
) -> None:
    items = [
        (FakeItem("text", bbox=_bbox(5, 5, 45, 15)), 1),
        (FakeItem("table", bbox=_bbox(5, 20, 95, 45)), 1),
    ]
    runner, converter = _runner(_result(items))

    page = runner.detect_layout(png_path, page_number=7)

    assert page.page_number == 7
    assert (page.width, page.height) == (200, 100)
    assert page.has_table is True
    assert page.has_complex_layout is False
    assert [region.label for region in page.regions] == ["text", "table"]
    assert [region.reading_order for region in page.regions] == [0, 1]
    assert page.regions[0].bbox == (10.0, 10.0, 90.0, 30.0)
    assert converter.calls == [str(png_path)]


@pytest.mark.parametrize(
    "items, expected",
    [
        (
            [
                (FakeItem("text", bbox=_bbox(0, 0, 40, 10)), 1),
                (FakeItem("text", bbox=_bbox(50, 20, 90, 30)), 1),
            ],
            True,
        ),
        ([(FakeItem("picture"), 1)], True),
        ([(FakeItem("formula"), 1)], True),
        ([(FakeItem("code"), 1)], True),
        ([(FakeItem("list"), 1)], True),
        ([(FakeItem("table"), 1)], False),
        ([(FakeItem("text"), 1)], False),
    ],
)
def test_complex_layout_rule_is_fixed(
    png_path: Path,
    items: list[tuple[FakeItem, int]],
    expected: bool,
) -> None:
    runner, _ = _runner(_result(items))

    assert (
        runner.detect_layout(png_path, page_number=1).has_complex_layout
        is expected
    )


@pytest.mark.parametrize(
    "items",
    [
        "not-items",
        {"item": 1},
        {(1, 2)},
        [FakeItem("text")],
        [(FakeItem("text"), 1, "extra")],
    ],
)
def test_malformed_item_container_is_rejected(
    png_path: Path,
    items: Any,
) -> None:
    runner, _ = _runner(_result(items))

    with pytest.raises(DoclingStructureError, match="items"):
        runner.detect_layout(png_path, page_number=1)


@pytest.mark.parametrize(
    "item",
    [
        SimpleNamespace(prov=[_prov()]),
        SimpleNamespace(label="text"),
        FakeItem("text", prov=[]),
        FakeItem("text", prov=[_prov(), _prov()]),
        FakeItem("text", prov=[_prov(page_no=2)]),
        FakeItem("text", prov=[SimpleNamespace(page_no=1)]),
        FakeItem(
            "text",
            prov=[SimpleNamespace(page_no=1, bbox=SimpleNamespace())],
        ),
    ],
)
def test_malformed_or_wrong_provenance_is_rejected(
    png_path: Path,
    item: Any,
) -> None:
    runner, _ = _runner(_result([(item, 1)]))

    with pytest.raises(DoclingStructureError, match="item|provenance|bbox"):
        runner.detect_layout(png_path, page_number=1)


@pytest.mark.parametrize(
    "page",
    [
        SimpleNamespace(page_no=1),
        SimpleNamespace(page_no=1, size=None),
        SimpleNamespace(
            page_no=1,
            size=SimpleNamespace(width=0, height=50),
        ),
        SimpleNamespace(
            page_no=1,
            size=SimpleNamespace(width=100, height=math.inf),
        ),
        SimpleNamespace(
            page_no=True,
            size=SimpleNamespace(width=100, height=50),
        ),
    ],
)
def test_malformed_docling_page_attributes_are_rejected(
    png_path: Path,
    page: Any,
) -> None:
    runner, _ = _runner(_result([], pages=[page]))

    with pytest.raises(DoclingStructureError, match="page"):
        runner.detect_layout(png_path, page_number=1)


def test_invalid_original_page_number_is_rejected(png_path: Path) -> None:
    runner, _ = _runner(_result([]))

    with pytest.raises(DoclingStructureError, match="page_number"):
        runner.detect_layout(png_path, page_number=0)


def test_iteration_exception_is_normalized(png_path: Path) -> None:
    document = FakeDocument([], iterate_error=ValueError("bad tree"))
    runner, _ = _runner(_result([], document=document))

    with pytest.raises(DoclingStructureError, match="bad tree"):
        runner.detect_layout(png_path, page_number=1)


def test_merged_cells_use_half_open_spans_and_lossless_html(
    png_path: Path,
) -> None:
    expected_html = (
        '<table><tr><th rowspan="2">구분</th><th>면적</th></tr>'
        "<tr><th>㎡</th></tr></table>"
    )
    table = _table_item(html=expected_html)
    raw = {
        "schema_name": "DoclingDocument",
        "tables": [{"text": "구분/면적/㎡", "merged": True}],
    }
    runner, _ = _runner(_result([(table, 1)], raw=raw))

    page = runner.recognize_tables(png_path, page_number=7)

    assert page.page_number == 7
    assert (page.width, page.height) == (200, 100)
    assert page.raw == raw
    assert json.loads(json.dumps(page.raw, ensure_ascii=False)) == raw
    assert len(page.tables) == 1
    normalized = page.tables[0]
    assert normalized.table_number == 1
    assert normalized.num_rows == 2
    assert normalized.num_columns == 2
    assert normalized.html == expected_html
    assert normalized.bbox == (0.0, 0.0, 200.0, 100.0)
    assert normalized.cells[0].start_row == 0
    assert normalized.cells[0].end_row == 2
    assert normalized.cells[0].row_span == 2
    assert normalized.cells[0].start_column == 0
    assert normalized.cells[0].end_column == 1
    assert normalized.cells[0].col_span == 1
    assert normalized.cells[0].is_column_header is True
    assert normalized.cells[0].is_row_header is False
    assert normalized.cells[0].is_row_section is False
    assert all(
        cell.raw_ocr_comparison_status == "NOT_COMPARABLE"
        for cell in normalized.cells
    )


def test_table_cells_accept_public_docling_attribute_models(
    png_path: Path,
) -> None:
    cells = [
        SimpleNamespace(
            text=cell["text"],
            bbox=_bbox(
                cell["bbox"][0],
                cell["bbox"][1],
                cell["bbox"][2],
                cell["bbox"][3],
            ),
            start_row_offset_idx=cell["start_row_offset_idx"],
            end_row_offset_idx=cell["end_row_offset_idx"],
            start_col_offset_idx=cell["start_col_offset_idx"],
            end_col_offset_idx=cell["end_col_offset_idx"],
            row_span=(
                cell["end_row_offset_idx"]
                - cell["start_row_offset_idx"]
            ),
            col_span=(
                cell["end_col_offset_idx"]
                - cell["start_col_offset_idx"]
            ),
            column_header=cell["column_header"],
            row_header=cell["row_header"],
            row_section=cell["row_section"],
        )
        for cell in _valid_cells()
    ]
    runner, _ = _runner(_result([(_table_item(cells=cells), 1)]))

    page = runner.recognize_tables(png_path, page_number=1)

    assert [cell.text for cell in page.tables[0].cells] == [
        "구분",
        "면적",
        "㎡",
    ]


def test_docling_row_section_is_preserved_as_header_semantics(
    png_path: Path,
) -> None:
    cells = _valid_cells()
    cells[2]["row_section"] = True
    runner, _ = _runner(_result([(_table_item(cells=cells), 1)]))

    page = runner.recognize_tables(png_path, page_number=1)

    assert page.tables[0].cells[2].is_row_section is True


@pytest.mark.parametrize(
    "num_rows, num_cols, cells",
    [
        (0, 2, _valid_cells()),
        (2, 0, _valid_cells()),
        (2, 2, []),
        (2, 2, "cells"),
        (2, 2, {"cell": 1}),
        (True, 2, _valid_cells()),
    ],
)
def test_empty_or_malformed_table_data_is_rejected(
    png_path: Path,
    num_rows: Any,
    num_cols: Any,
    cells: Any,
) -> None:
    runner, _ = _runner(
        _result(
            [
                (
                    _table_item(
                        num_rows=num_rows,
                        num_cols=num_cols,
                        cells=cells,
                    ),
                    1,
                )
            ]
        )
    )

    with pytest.raises(DoclingStructureError, match="table"):
        runner.recognize_tables(png_path, page_number=1)


@pytest.mark.parametrize(
    "mutate",
    [
        lambda cells: cells[0].update(end_row_offset_idx=3),
        lambda cells: cells[0].update(start_row_offset_idx=-1),
        lambda cells: cells[1].update(start_col_offset_idx=2),
        lambda cells: cells[1].update(start_row_offset_idx=1),
        lambda cells: cells.pop(),
        lambda cells: cells[0].update(bbox=[-1, 0, 50, 50]),
        lambda cells: cells[0].update(bbox=[0, 0, 101, 50]),
        lambda cells: cells[0].update(row_span=1),
        lambda cells: cells[0].update(col_span=2),
    ],
)
def test_table_topology_conflicts_are_rejected(
    png_path: Path,
    mutate: Any,
) -> None:
    cells = _valid_cells()
    mutate(cells)
    runner, _ = _runner(_result([(_table_item(cells=cells), 1)]))

    with pytest.raises(DoclingStructureError, match="table|cell"):
        runner.recognize_tables(png_path, page_number=1)


@pytest.mark.parametrize(
    "cell",
    [
        {"text": "missing everything"},
        {
            **_valid_cells()[0],
            "text": 123,
        },
        {
            **_valid_cells()[0],
            "column_header": "yes",
        },
        {
            **_valid_cells()[0],
            "bbox": None,
        },
        {
            **_valid_cells()[0],
            "bbox": [0, 0, math.nan, 50],
        },
    ],
)
def test_malformed_table_cell_attributes_are_rejected(
    png_path: Path,
    cell: Mapping[str, Any],
) -> None:
    cells = [cell, *_valid_cells()[1:]]
    runner, _ = _runner(_result([(_table_item(cells=cells), 1)]))

    with pytest.raises(DoclingStructureError, match="cell|bbox|finite"):
        runner.recognize_tables(png_path, page_number=1)


def test_table_label_without_data_is_rejected(png_path: Path) -> None:
    runner, _ = _runner(_result([(FakeItem("table"), 1)]))

    with pytest.raises(DoclingStructureError, match="table data"):
        runner.recognize_tables(png_path, page_number=1)


def test_no_table_item_is_rejected(png_path: Path) -> None:
    runner, _ = _runner(_result([(FakeItem("text"), 1)]))

    with pytest.raises(DoclingStructureError, match="no table"):
        runner.recognize_tables(png_path, page_number=1)


@pytest.mark.parametrize("html", ["", "   ", None, 123])
def test_lossless_html_must_be_nonempty_text(
    png_path: Path,
    html: Any,
) -> None:
    runner, _ = _runner(_result([(_table_item(html=html), 1)]))

    with pytest.raises(DoclingStructureError, match="HTML"):
        runner.recognize_tables(png_path, page_number=1)


def test_html_export_exception_is_normalized(png_path: Path) -> None:
    table = _table_item()
    table._export_error = ValueError("serializer failed")
    runner, _ = _runner(_result([(table, 1)]))

    with pytest.raises(DoclingStructureError, match="serializer failed"):
        runner.recognize_tables(png_path, page_number=1)


@pytest.mark.parametrize(
    "raw",
    [
        [],
        "json",
        {"bad": {1, 2}},
        {"bad": math.nan},
    ],
)
def test_raw_export_must_be_json_compatible_mapping(
    png_path: Path,
    raw: Any,
) -> None:
    runner, _ = _runner(_result([(_table_item(), 1)], raw=raw))

    with pytest.raises(DoclingStructureError, match="raw|JSON"):
        runner.recognize_tables(png_path, page_number=1)


def test_raw_export_exception_is_normalized(png_path: Path) -> None:
    document = FakeDocument(
        [(_table_item(), 1)],
        export_error=ValueError("raw export failed"),
    )
    runner, _ = _runner(
        _result(
            [(_table_item(), 1)],
            document=document,
        )
    )

    with pytest.raises(DoclingStructureError, match="raw export failed"):
        runner.recognize_tables(png_path, page_number=1)


def test_multiple_tables_are_numbered_in_reading_order(
    png_path: Path,
) -> None:
    first = _table_item()
    second = _table_item()
    runner, _ = _runner(_result([(first, 1), (second, 1)]))

    page = runner.recognize_tables(png_path, page_number=1)

    assert [table.table_number for table in page.tables] == [1, 2]


def test_public_methods_normalize_unexpected_exceptions(
    png_path: Path,
) -> None:
    malformed = _result([])
    malformed.document = property(lambda self: None)
    runner, _ = _runner(malformed)

    with pytest.raises(DoclingStructureError):
        runner.recognize_tables(png_path, page_number=1)
