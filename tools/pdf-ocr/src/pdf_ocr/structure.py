from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence, Set
from dataclasses import asdict
from numbers import Real
from pathlib import Path
from typing import Any

from docling.datamodel.accelerator_options import (
    AcceleratorDevice,
    AcceleratorOptions,
)
from docling.datamodel.base_models import ConversionStatus, InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    RapidOcrOptions,
    TableFormerMode,
    TableStructureOptions,
)
from docling.document_converter import DocumentConverter, ImageFormatOption

from .contracts import validate_table_topology
from .image_contract import PngContractError, validate_png_file
from .model_lock import (
    LockedArtifact,
    docling_artifacts_root,
    revalidate_locked_artifacts,
)
from .ocr import build_rapidocr_params
from .types import (
    BBox,
    LayoutPage,
    LayoutRegion,
    StructurePage,
    TableCell,
    TableData,
)


class DoclingStructureError(RuntimeError):
    pass


_MISSING = object()


def _normalized_error(
    context: str,
    error: Exception,
) -> DoclingStructureError:
    return DoclingStructureError(f"{context}: {error}")


def _field(
    value: Any,
    name: str,
    description: str,
    *,
    default: Any = _MISSING,
) -> Any:
    try:
        if isinstance(value, Mapping):
            if name in value:
                return value[name]
        else:
            return getattr(value, name)
    except AttributeError:
        pass
    except Exception as error:
        raise _normalized_error(
            f"{description} attribute {name} is invalid",
            error,
        ) from error
    if default is not _MISSING:
        return default
    raise DoclingStructureError(
        f"{description} is missing required attribute {name}"
    )


def _ordered(
    value: Any,
    description: str,
) -> list[Any]:
    if isinstance(
        value,
        (str, bytes, bytearray, Mapping, Set),
    ):
        raise DoclingStructureError(
            f"{description} must be an ordered iterable"
        )
    try:
        return list(iter(value))
    except Exception as error:
        raise _normalized_error(
            f"{description} must be an ordered iterable",
            error,
        ) from error


def _positive_int(value: Any, description: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise DoclingStructureError(
            f"{description} must be a positive integer"
        )
    return value


def _grid_index(value: Any, description: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DoclingStructureError(f"{description} must be an integer")
    return value


def _finite_real(value: Any, description: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise DoclingStructureError(f"{description} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise DoclingStructureError(f"{description} must be finite")
    return result


def _origin_value(value: Any) -> str:
    origin = getattr(value, "value", value)
    if not isinstance(origin, str):
        raise DoclingStructureError(
            "Docling coordinate origin is unknown"
        )
    return origin


def _top_left_pixel_bbox(
    *,
    left: float,
    top: float,
    right: float,
    bottom: float,
    origin: str,
    source_width: float,
    source_height: float,
    image_width: int,
    image_height: int,
) -> BBox:
    source_width_value = _finite_real(
        source_width,
        "Docling coordinate space width",
    )
    source_height_value = _finite_real(
        source_height,
        "Docling coordinate space height",
    )
    if source_width_value <= 0 or source_height_value <= 0:
        raise DoclingStructureError(
            "Docling coordinate space is invalid"
        )
    if (
        isinstance(image_width, bool)
        or isinstance(image_height, bool)
        or not isinstance(image_width, int)
        or not isinstance(image_height, int)
        or image_width <= 0
        or image_height <= 0
    ):
        raise DoclingStructureError("Docling page image is invalid")

    left_value = _finite_real(left, "Docling bbox coordinate")
    top_value = _finite_real(top, "Docling bbox coordinate")
    right_value = _finite_real(right, "Docling bbox coordinate")
    bottom_value = _finite_real(bottom, "Docling bbox coordinate")
    normalized_origin = _origin_value(origin)
    if normalized_origin == "BOTTOMLEFT":
        top_value, bottom_value = (
            source_height_value - top_value,
            source_height_value - bottom_value,
        )
    elif normalized_origin != "TOPLEFT":
        raise DoclingStructureError(
            "Docling coordinate origin is unknown"
        )

    bbox = (
        left_value * image_width / source_width_value,
        top_value * image_height / source_height_value,
        right_value * image_width / source_width_value,
        bottom_value * image_height / source_height_value,
    )
    if not all(math.isfinite(coordinate) for coordinate in bbox):
        raise DoclingStructureError(
            "Docling bbox coordinate must be finite"
        )
    x0, y0, x1, y1 = bbox
    if (
        x0 < 0
        or y0 < 0
        or x1 > image_width
        or y1 > image_height
        or x0 >= x1
        or y0 >= y1
    ):
        raise DoclingStructureError(
            "Docling bbox is outside the page image"
        )
    return bbox


def _bbox_values(
    value: Any,
    description: str,
) -> tuple[Any, Any, Any, Any, str]:
    if isinstance(value, Mapping) or all(
        hasattr(value, name)
        for name in ("l", "t", "r", "b")
    ):
        return (
            _field(value, "l", description),
            _field(value, "t", description),
            _field(value, "r", description),
            _field(value, "b", description),
            _origin_value(
                _field(
                    value,
                    "coord_origin",
                    description,
                    default="TOPLEFT",
                )
            ),
        )
    coordinates = _ordered(value, description)
    if len(coordinates) != 4:
        raise DoclingStructureError(
            f"{description} must contain exactly four coordinates"
        )
    return (
        coordinates[0],
        coordinates[1],
        coordinates[2],
        coordinates[3],
        "TOPLEFT",
    )


def _pixel_bbox(
    value: Any,
    *,
    description: str,
    source_width: float,
    source_height: float,
    image_width: int,
    image_height: int,
) -> BBox:
    if value is None:
        raise DoclingStructureError(f"{description} is missing")
    left, top, right, bottom, origin = _bbox_values(
        value,
        description,
    )
    return _top_left_pixel_bbox(
        left=left,
        top=top,
        right=right,
        bottom=bottom,
        origin=origin,
        source_width=source_width,
        source_height=source_height,
        image_width=image_width,
        image_height=image_height,
    )


def _has_complex_layout(
    regions: Sequence[LayoutRegion],
    width: int,
) -> bool:
    text_like = [
        region
        for region in regions
        if region.label
        in {"text", "list_item", "section_header", "caption"}
    ]
    normalized_x_starts = {
        round(region.bbox[0] / max(width, 1), 1)
        for region in text_like
    }
    non_text_structure = any(
        region.label in {"list", "picture", "formula", "code"}
        for region in regions
    )
    return len(normalized_x_starts) >= 2 or non_text_structure


def _cpu_options() -> AcceleratorOptions:
    return AcceleratorOptions(device=AcceleratorDevice.CPU)


def build_layout_pipeline_options(
    artifacts: Sequence[LockedArtifact],
) -> PdfPipelineOptions:
    try:
        revalidate_locked_artifacts(artifacts)
        return PdfPipelineOptions(
            artifacts_path=str(docling_artifacts_root(artifacts)),
            accelerator_options=_cpu_options(),
            do_ocr=False,
            do_table_structure=False,
            enable_remote_services=False,
            allow_external_plugins=False,
        )
    except DoclingStructureError:
        raise
    except Exception as error:
        raise _normalized_error(
            "Docling layout options could not be built",
            error,
        ) from error


def build_table_pipeline_options(
    artifacts: Sequence[LockedArtifact],
) -> PdfPipelineOptions:
    try:
        revalidate_locked_artifacts(artifacts)
        rapidocr_params = build_rapidocr_params(artifacts)
        options = PdfPipelineOptions(
            artifacts_path=str(docling_artifacts_root(artifacts)),
            accelerator_options=_cpu_options(),
            do_ocr=True,
            do_table_structure=True,
            enable_remote_services=False,
            allow_external_plugins=False,
        )
        options.ocr_options = RapidOcrOptions(
            backend="onnxruntime",
            force_full_page_ocr=True,
            text_score=0.0,
            use_det=True,
            use_cls=False,
            use_rec=True,
            det_model_path=rapidocr_params["Det.model_path"],
            cls_model_path=rapidocr_params["Cls.model_path"],
            rec_model_path=rapidocr_params["Rec.model_path"],
            rec_keys_path=rapidocr_params["Rec.rec_keys_path"],
            font_path=rapidocr_params["Global.font_path"],
            print_verbose=False,
            rapidocr_params=rapidocr_params,
        )
        options.table_structure_options = TableStructureOptions(
            do_cell_matching=True,
            mode=TableFormerMode.ACCURATE,
        )
        return options
    except DoclingStructureError:
        raise
    except Exception as error:
        raise _normalized_error(
            "Docling table options could not be built",
            error,
        ) from error


def create_layout_converter(
    artifacts: Sequence[LockedArtifact],
) -> Any:
    try:
        revalidate_locked_artifacts(artifacts)
        converter = DocumentConverter(
            allowed_formats=[InputFormat.IMAGE],
            format_options={
                InputFormat.IMAGE: ImageFormatOption(
                    pipeline_options=build_layout_pipeline_options(
                        artifacts
                    )
                )
            },
        )
        converter.initialize_pipeline(InputFormat.IMAGE)
        return converter
    except DoclingStructureError:
        raise
    except Exception as error:
        raise _normalized_error(
            "Docling layout converter could not be created",
            error,
        ) from error


def create_table_converter(
    artifacts: Sequence[LockedArtifact],
) -> Any:
    try:
        revalidate_locked_artifacts(artifacts)
        converter = DocumentConverter(
            allowed_formats=[InputFormat.IMAGE],
            format_options={
                InputFormat.IMAGE: ImageFormatOption(
                    pipeline_options=build_table_pipeline_options(
                        artifacts
                    )
                )
            },
        )
        converter.initialize_pipeline(InputFormat.IMAGE)
        return converter
    except DoclingStructureError:
        raise
    except Exception as error:
        raise _normalized_error(
            "Docling table converter could not be created",
            error,
        ) from error


def _png_dimensions(image_path: Path) -> tuple[int, int]:
    try:
        return validate_png_file(image_path)
    except PngContractError as error:
        raise _normalized_error(
            "Docling PNG decode or dimension validation failed",
            error,
        ) from error


def _convert_single_png(
    converter: Any,
    image_path: Path,
) -> tuple[Any, Any, int, int]:
    if image_path.suffix.lower() != ".png":
        raise DoclingStructureError(
            "Docling accepts page PNG input only"
        )
    image_width, image_height = _png_dimensions(image_path)
    try:
        result = converter.convert(str(image_path))
    except Exception as error:
        raise _normalized_error(
            "Docling conversion failed",
            error,
        ) from error
    if result is None:
        raise DoclingStructureError(
            "Docling conversion result is missing"
        )
    status = _field(
        result,
        "status",
        "Docling conversion result",
    )
    if status is not ConversionStatus.SUCCESS:
        raise DoclingStructureError(
            f"Docling conversion did not fully succeed: {status}"
        )
    try:
        pages = _ordered(
            _field(result, "pages", "Docling conversion result"),
            "Docling conversion pages",
        )
    except DoclingStructureError as error:
        raise DoclingStructureError(
            f"Docling image conversion must have one page: {error}"
        ) from error
    if len(pages) != 1:
        raise DoclingStructureError(
            "Docling image conversion must have one page"
        )
    return result, pages[0], image_width, image_height


def _page_space(page: Any) -> tuple[int, float, float]:
    page_no = _positive_int(
        _field(page, "page_no", "Docling page"),
        "Docling page number",
    )
    size = _field(page, "size", "Docling page")
    if size is None:
        raise DoclingStructureError("Docling page size is missing")
    source_width = _finite_real(
        _field(size, "width", "Docling page size"),
        "Docling page width",
    )
    source_height = _finite_real(
        _field(size, "height", "Docling page size"),
        "Docling page height",
    )
    if source_width <= 0 or source_height <= 0:
        raise DoclingStructureError(
            "Docling page size must be positive"
        )
    return page_no, source_width, source_height


def _document_items(document: Any) -> list[tuple[Any, int]]:
    iterate_items = _field(
        document,
        "iterate_items",
        "Docling document",
    )
    if not callable(iterate_items):
        raise DoclingStructureError(
            "Docling document iterate_items is invalid"
        )
    try:
        raw_items = iterate_items()
    except Exception as error:
        raise _normalized_error(
            "Docling document items could not be read",
            error,
        ) from error
    entries = _ordered(raw_items, "Docling document items")
    items: list[tuple[Any, int]] = []
    for entry in entries:
        pair = _ordered(entry, "Docling document items entry")
        if len(pair) != 2:
            raise DoclingStructureError(
                "Docling document items entry must contain item and level"
            )
        level = _grid_index(pair[1], "Docling item level")
        if level < 0:
            raise DoclingStructureError(
                "Docling item level must not be negative"
            )
        items.append((pair[0], level))
    return items


def _label(item: Any) -> str:
    raw_label = _field(item, "label", "Docling item")
    label = getattr(raw_label, "value", raw_label)
    if not isinstance(label, str) or not label:
        raise DoclingStructureError("Docling item label is invalid")
    return label


def _item_bbox(
    item: Any,
    *,
    internal_page_no: int,
    source_width: float,
    source_height: float,
    image_width: int,
    image_height: int,
) -> BBox:
    provenance = _ordered(
        _field(item, "prov", "Docling item"),
        "Docling item provenance",
    )
    if len(provenance) != 1:
        raise DoclingStructureError(
            "Docling item provenance must contain exactly one page reference"
        )
    item_provenance = provenance[0]
    provenance_page_no = _positive_int(
        _field(
            item_provenance,
            "page_no",
            "Docling item provenance",
        ),
        "Docling provenance page number",
    )
    if provenance_page_no != internal_page_no:
        raise DoclingStructureError(
            "Docling item provenance references the wrong page"
        )
    return _pixel_bbox(
        _field(
            item_provenance,
            "bbox",
            "Docling item provenance",
        ),
        description="Docling item provenance bbox",
        source_width=source_width,
        source_height=source_height,
        image_width=image_width,
        image_height=image_height,
    )


def _regions_and_items(
    document: Any,
    *,
    internal_page_no: int,
    source_width: float,
    source_height: float,
    image_width: int,
    image_height: int,
) -> tuple[tuple[LayoutRegion, ...], list[tuple[Any, str, BBox]]]:
    regions: list[LayoutRegion] = []
    normalized_items: list[tuple[Any, str, BBox]] = []
    for item, _level in _document_items(document):
        label = _label(item)
        bbox = _item_bbox(
            item,
            internal_page_no=internal_page_no,
            source_width=source_width,
            source_height=source_height,
            image_width=image_width,
            image_height=image_height,
        )
        regions.append(
            LayoutRegion(
                label=label,
                bbox=bbox,
                reading_order=len(regions),
            )
        )
        normalized_items.append((item, label, bbox))
    return tuple(regions), normalized_items


def _cell_field(
    cell: Any,
    name: str,
    *,
    default: Any = _MISSING,
) -> Any:
    return _field(
        cell,
        name,
        "Docling table cell",
        default=default,
    )


def _normalize_cell(
    cell: Any,
    *,
    source_width: float,
    source_height: float,
    image_width: int,
    image_height: int,
) -> TableCell:
    text = _cell_field(cell, "text")
    if not isinstance(text, str):
        raise DoclingStructureError(
            "Docling table cell text is invalid"
        )
    start_row = _grid_index(
        _cell_field(cell, "start_row_offset_idx"),
        "Docling table cell start row",
    )
    end_row = _grid_index(
        _cell_field(cell, "end_row_offset_idx"),
        "Docling table cell end row",
    )
    start_column = _grid_index(
        _cell_field(cell, "start_col_offset_idx"),
        "Docling table cell start column",
    )
    end_column = _grid_index(
        _cell_field(cell, "end_col_offset_idx"),
        "Docling table cell end column",
    )
    row_span = end_row - start_row
    col_span = end_column - start_column

    declared_row_span = _cell_field(
        cell,
        "row_span",
        default=row_span,
    )
    declared_col_span = _cell_field(
        cell,
        "col_span",
        default=col_span,
    )
    if (
        _grid_index(
            declared_row_span,
            "Docling table cell row span",
        )
        != row_span
    ):
        raise DoclingStructureError(
            "Docling table cell row span conflicts with half-open range"
        )
    if (
        _grid_index(
            declared_col_span,
            "Docling table cell column span",
        )
        != col_span
    ):
        raise DoclingStructureError(
            "Docling table cell column span conflicts with half-open range"
        )

    column_header = _cell_field(
        cell,
        "column_header",
        default=False,
    )
    row_header = _cell_field(
        cell,
        "row_header",
    )
    row_section = _cell_field(cell, "row_section")
    if not isinstance(column_header, bool) or not isinstance(
        row_header,
        bool,
    ) or not isinstance(row_section, bool):
        raise DoclingStructureError(
            "Docling table cell header flags are invalid"
        )

    try:
        bbox = _pixel_bbox(
            _cell_field(cell, "bbox"),
            description="Docling table cell bbox",
            source_width=source_width,
            source_height=source_height,
            image_width=image_width,
            image_height=image_height,
        )
    except DoclingStructureError as error:
        raise DoclingStructureError(
            f"Docling table cell bbox is invalid: {error}"
        ) from error
    return TableCell(
        text=text,
        bbox=bbox,
        start_row=start_row,
        end_row=end_row,
        start_column=start_column,
        end_column=end_column,
        row_span=row_span,
        col_span=col_span,
        is_column_header=column_header,
        is_row_header=row_header,
        is_row_section=row_section,
        raw_ocr_comparison_status="NOT_COMPARABLE",
    )


def _validate_normalized_table(
    *,
    bbox: BBox,
    num_rows: int,
    num_columns: int,
    cells: Sequence[TableCell],
) -> None:
    payload = {
        "bbox": bbox,
        "num_rows": num_rows,
        "num_columns": num_columns,
        "cells": [asdict(cell) for cell in cells],
    }
    try:
        validate_table_topology(payload)
    except Exception as error:
        raise _normalized_error(
            "Docling table topology is invalid",
            error,
        ) from error


def _lossless_html(item: Any, document: Any) -> str:
    exporter = _field(
        item,
        "export_to_html",
        "Docling table",
    )
    if not callable(exporter):
        raise DoclingStructureError(
            "Docling table HTML exporter is invalid"
        )
    try:
        html = exporter(doc=document)
    except Exception as error:
        raise _normalized_error(
            "Docling table HTML export failed",
            error,
        ) from error
    if not isinstance(html, str) or not html.strip():
        raise DoclingStructureError(
            "Docling lossless table HTML is empty or invalid"
        )
    return html


def _raw_document(document: Any) -> Mapping[str, Any]:
    exporter = _field(
        document,
        "export_to_dict",
        "Docling document",
    )
    if not callable(exporter):
        raise DoclingStructureError(
            "Docling document raw exporter is invalid"
        )
    try:
        raw = exporter()
    except Exception as error:
        raise _normalized_error(
            "Docling raw export failed",
            error,
        ) from error
    if not isinstance(raw, Mapping):
        raise DoclingStructureError(
            "Docling raw export must be a JSON object"
        )
    try:
        encoded = json.dumps(
            raw,
            ensure_ascii=False,
            allow_nan=False,
        )
        normalized = json.loads(encoded)
    except Exception as error:
        raise _normalized_error(
            "Docling raw export is not JSON compatible",
            error,
        ) from error
    if not isinstance(normalized, Mapping):
        raise DoclingStructureError(
            "Docling raw export must be a JSON object"
        )
    return normalized


class DoclingRunner:
    def __init__(
        self,
        *,
        layout_converter: Any,
        table_converter: Any,
    ) -> None:
        self._layout_converter = layout_converter
        self._table_converter = table_converter

    def detect_layout(
        self,
        image_path: Path,
        *,
        page_number: int,
    ) -> LayoutPage:
        try:
            return self._detect_layout(
                image_path,
                page_number=page_number,
            )
        except DoclingStructureError:
            raise
        except Exception as error:
            raise _normalized_error(
                "Docling layout normalization failed",
                error,
            ) from error

    def _detect_layout(
        self,
        image_path: Path,
        *,
        page_number: int,
    ) -> LayoutPage:
        original_page_number = _positive_int(
            page_number,
            "page_number",
        )
        result, page, width, height = _convert_single_png(
            self._layout_converter,
            image_path,
        )
        internal_page_no, source_width, source_height = _page_space(page)
        document = _field(
            result,
            "document",
            "Docling conversion result",
        )
        regions, _ = _regions_and_items(
            document,
            internal_page_no=internal_page_no,
            source_width=source_width,
            source_height=source_height,
            image_width=width,
            image_height=height,
        )
        return LayoutPage(
            page_number=original_page_number,
            width=width,
            height=height,
            regions=regions,
            has_table=any(
                region.label == "table"
                for region in regions
            ),
            has_complex_layout=_has_complex_layout(regions, width),
        )

    def recognize_tables(
        self,
        image_path: Path,
        *,
        page_number: int,
    ) -> StructurePage:
        try:
            return self._recognize_tables(
                image_path,
                page_number=page_number,
            )
        except DoclingStructureError:
            raise
        except Exception as error:
            raise _normalized_error(
                "Docling table normalization failed",
                error,
            ) from error

    def _recognize_tables(
        self,
        image_path: Path,
        *,
        page_number: int,
    ) -> StructurePage:
        original_page_number = _positive_int(
            page_number,
            "page_number",
        )
        result, page, width, height = _convert_single_png(
            self._table_converter,
            image_path,
        )
        internal_page_no, source_width, source_height = _page_space(page)
        document = _field(
            result,
            "document",
            "Docling conversion result",
        )
        regions, normalized_items = _regions_and_items(
            document,
            internal_page_no=internal_page_no,
            source_width=source_width,
            source_height=source_height,
            image_width=width,
            image_height=height,
        )

        tables: list[TableData] = []
        for item, label, table_bbox in normalized_items:
            if label != "table":
                continue
            data = _field(item, "data", "Docling table data")
            num_rows = _positive_int(
                _field(data, "num_rows", "Docling table data"),
                "Docling table rows",
            )
            num_columns = _positive_int(
                _field(data, "num_cols", "Docling table data"),
                "Docling table columns",
            )
            raw_cells = _ordered(
                _field(
                    data,
                    "table_cells",
                    "Docling table data",
                ),
                "Docling table cells",
            )
            if not raw_cells:
                raise DoclingStructureError(
                    "Docling table cells must not be empty"
                )
            cells = tuple(
                _normalize_cell(
                    cell,
                    source_width=source_width,
                    source_height=source_height,
                    image_width=width,
                    image_height=height,
                )
                for cell in raw_cells
            )
            _validate_normalized_table(
                bbox=table_bbox,
                num_rows=num_rows,
                num_columns=num_columns,
                cells=cells,
            )
            tables.append(
                TableData(
                    table_number=len(tables) + 1,
                    bbox=table_bbox,
                    num_rows=num_rows,
                    num_columns=num_columns,
                    cells=cells,
                    html=_lossless_html(item, document),
                )
            )
        if not tables:
            raise DoclingStructureError(
                "Docling table recognition returned no table"
            )

        return StructurePage(
            page_number=original_page_number,
            width=width,
            height=height,
            regions=regions,
            tables=tuple(tables),
            raw=_raw_document(document),
        )
