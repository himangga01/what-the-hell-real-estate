from __future__ import annotations

import json
import math
import os
import stat
import unicodedata
from dataclasses import asdict, dataclass, replace
from html.parser import HTMLParser
from numbers import Real
from pathlib import Path
from typing import Any, Mapping

from jsonschema import ValidationError

from pdf_ocr.contracts import (
    sha256,
    validate_comparison_statuses,
    validate_ocr_page,
    validate_structure_page,
    validate_table_topology,
)
from pdf_ocr.image_contract import PngContractError, validate_png_file
from pdf_ocr.router import PageRoute
from pdf_ocr.types import OcrPage, OcrToken, StructurePage, TableCell, TableData


class ArtifactError(RuntimeError):
    pass


@dataclass(frozen=True)
class PageArtifactSet:
    image: dict[str, object]
    ocr: dict[str, object]
    structure: dict[str, object]
    markdown: dict[str, object]
    tables: tuple[dict[str, object], ...]


def _normalized_text(value: str) -> str:
    normalized = unicodedata.normalize(
        "NFC",
        "".join(
            unicodedata.normalize("NFKC", character)
            if unicodedata.east_asian_width(character) in {"F", "H"}
            else character
            for character in value
        ),
    )
    return "".join(
        character
        for character in normalized
        if not character.isspace()
    )


def _numeric_whitespace_risk(
    values: tuple[str, ...],
) -> bool:
    normalized_values = tuple(
        unicodedata.normalize(
            "NFC",
            "".join(
                unicodedata.normalize("NFKC", character)
                if unicodedata.east_asian_width(character) in {"F", "H"}
                else character
                for character in value
            ),
        )
        for value in values
    )
    for value in normalized_values:
        for index, character in enumerate(value):
            if not character.isspace():
                continue
            before = value[index - 1] if index else ""
            after = value[index + 1] if index + 1 < len(value) else ""
            if before.isdigit() and after.isdigit():
                return True
    ocr_values = normalized_values[:-1]
    return any(
        left.rstrip()[-1:].isdigit() and right.lstrip()[:1].isdigit()
        for left, right in zip(
            ocr_values,
            ocr_values[1:],
            strict=False,
        )
    )


def _positive_page_number(value: Any, description: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        raise ArtifactError(f"{description} must be a positive integer")
    return value


def _finite_bbox(
    bbox: Any,
    *,
    description: str,
) -> tuple[float, float, float, float]:
    if (
        not isinstance(bbox, (tuple, list))
        or len(bbox) != 4
        or any(
            isinstance(value, bool)
            or not isinstance(value, Real)
            or not math.isfinite(float(value))
            for value in bbox
        )
    ):
        raise ArtifactError(f"{description} is invalid")
    x0, y0, x1, y1 = (float(value) for value in bbox)
    if x0 < 0 or y0 < 0 or x0 >= x1 or y0 >= y1:
        raise ArtifactError(f"{description} is invalid")
    return x0, y0, x1, y1


def _token_center_inside(token: OcrToken, cell: TableCell) -> bool:
    x0, y0, x1, y1 = _finite_bbox(
        token.bbox,
        description="OCR token bbox",
    )
    center_x = (x0 + x1) / 2.0
    center_y = (y0 + y1) / 2.0
    cx0, cy0, cx1, cy1 = _finite_bbox(
        cell.bbox,
        description="table cell bbox",
    )
    return cx0 <= center_x <= cx1 and cy0 <= center_y <= cy1


def _validate_comparison_pages(
    ocr_page: OcrPage,
    structure_page: StructurePage,
) -> None:
    ocr_page_number = _positive_page_number(
        ocr_page.page_number,
        "OCR page number",
    )
    structure_page_number = _positive_page_number(
        structure_page.page_number,
        "structure page number",
    )
    if ocr_page_number != structure_page_number:
        raise ArtifactError("OCR and structure page numbers do not match")

    reading_orders: set[int] = set()
    for token in ocr_page.tokens:
        token_page_number = _positive_page_number(
            token.source_page_number,
            "OCR token source page",
        )
        if token_page_number != ocr_page_number:
            raise ArtifactError(
                "OCR token source page does not match the compared page"
            )
        if (
            isinstance(token.reading_order, bool)
            or not isinstance(token.reading_order, int)
            or token.reading_order < 0
            or token.reading_order in reading_orders
        ):
            raise ArtifactError("OCR token reading_order is invalid or duplicate")
        reading_orders.add(token.reading_order)
        if not isinstance(token.text, str):
            raise ArtifactError("OCR token text is invalid")

    for table in structure_page.tables:
        for cell in table.cells:
            if not isinstance(cell.text, str):
                raise ArtifactError("table cell text is invalid")


def _compare_table_cells(
    ocr_page: OcrPage,
    structure_page: StructurePage,
) -> StructurePage:
    _validate_comparison_pages(ocr_page, structure_page)
    compared_tables: list[TableData] = []
    for table in structure_page.tables:
        for token in ocr_page.tokens:
            matches = sum(
                _token_center_inside(token, cell)
                for cell in table.cells
            )
            if matches > 1:
                raise ArtifactError(
                    "OCR token assignment is ambiguous across multiple cells"
                )
        compared_cells: list[TableCell] = []
        for cell in table.cells:
            tokens = sorted(
                (
                    token
                    for token in ocr_page.tokens
                    if _token_center_inside(token, cell)
                ),
                key=lambda token: token.reading_order,
            )
            raw_text = "".join(token.text for token in tokens)
            normalized_raw = _normalized_text(raw_text)
            normalized_cell = _normalized_text(cell.text)
            if not normalized_raw and not normalized_cell:
                status = "NOT_COMPARABLE"
            elif (
                normalized_raw == normalized_cell
                and not _numeric_whitespace_risk(
                    tuple(token.text for token in tokens) + (cell.text,)
                )
            ):
                status = "MATCHED"
            else:
                status = "MISMATCH"
            compared_cells.append(
                replace(cell, raw_ocr_comparison_status=status)
            )
        compared_tables.append(
            replace(table, cells=tuple(compared_cells))
        )
    return replace(structure_page, tables=tuple(compared_tables))


def compare_table_cells(
    ocr_page: OcrPage,
    structure_page: StructurePage,
) -> StructurePage:
    try:
        return _compare_table_cells(ocr_page, structure_page)
    except ArtifactError:
        raise
    except Exception as error:
        raise ArtifactError(
            f"table cell comparison failed: {error}"
        ) from error


@dataclass
class _HtmlCell:
    row_span: int
    col_span: int
    tag: str
    text_parts: list[str]


class _TableHtmlParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.table_depth = 0
        self.table_count = 0
        self.completed_table_count = 0
        self.rows: list[list[_HtmlCell]] = []
        self.current_row: list[_HtmlCell] | None = None
        self.current_cell: _HtmlCell | None = None
        self.in_caption_element = False
        self.in_caption_div = False
        self.caption_div_count = 0
        self.caption_seen = False
        self.body_started = False
        self.in_tbody = False

    @staticmethod
    def _attributes(
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> dict[str, str | None]:
        allowed: set[str] = set()
        if tag in {"td", "th"}:
            allowed |= {"rowspan", "colspan", "dir"}
        elif tag == "div":
            allowed |= {"class", "dir"}
        values: dict[str, str | None] = {}
        for name, value in attrs:
            lower_name = name.lower()
            if lower_name in values:
                raise ArtifactError(
                    f"table HTML has duplicate {lower_name} attribute"
                )
            if lower_name not in allowed:
                raise ArtifactError(
                    f"table HTML attribute is not allowed: {lower_name}"
                )
            if lower_name == "dir" and value != "rtl":
                raise ArtifactError("table HTML dir must be rtl")
            values[lower_name] = value
        if tag == "div" and values.get("class") != "caption":
            raise ArtifactError(
                "table HTML div must have exactly class=\"caption\""
            )
        return values

    def handle_starttag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        lower_tag = tag.lower()
        if lower_tag not in {
            "table",
            "caption",
            "div",
            "tbody",
            "tr",
            "td",
            "th",
        }:
            raise ArtifactError(f"table HTML tag is not allowed: {lower_tag}")
        values = self._attributes(lower_tag, attrs)
        if lower_tag == "table":
            if (
                self.table_depth
                or self.in_caption_element
                or self.in_caption_div
            ):
                raise ArtifactError("table HTML contains a nested table")
            self.table_depth = 1
            self.table_count += 1
            self.caption_div_count = 0
            self.caption_seen = False
            self.body_started = False
            return
        if lower_tag == "caption":
            if (
                self.table_depth != 1
                or self.in_caption_element
                or self.in_caption_div
                or self.current_row is not None
                or self.in_tbody
                or self.body_started
                or self.caption_seen
            ):
                raise ArtifactError(
                    "table HTML caption element nesting is invalid"
                )
            self.in_caption_element = True
            self.caption_div_count = 0
            self.caption_seen = True
            return
        if lower_tag == "div":
            if (
                self.table_depth != 1
                or not self.in_caption_element
                or self.in_caption_div
                or self.current_row is not None
                or self.in_tbody
            ):
                raise ArtifactError("table HTML caption div nesting is invalid")
            self.in_caption_div = True
            self.caption_div_count += 1
            return
        if lower_tag == "tbody":
            if (
                self.table_depth != 1
                or self.in_tbody
                or self.current_row is not None
                or self.in_caption_element
                or self.in_caption_div
            ):
                raise ArtifactError("table HTML tbody nesting is invalid")
            self.in_tbody = True
            self.body_started = True
            return
        if lower_tag == "tr":
            if (
                self.table_depth != 1
                or self.current_row is not None
                or self.in_caption_element
                or self.in_caption_div
            ):
                raise ArtifactError("table HTML row nesting is invalid")
            self.current_row = []
            self.body_started = True
            return
        if lower_tag not in {"td", "th"}:
            return
        if (
            self.table_depth != 1
            or self.current_row is None
            or self.current_cell is not None
        ):
            raise ArtifactError("table HTML cell placement is invalid")

        html_cell = _HtmlCell(
            row_span=self._span(values.get("rowspan"), "rowspan"),
            col_span=self._span(values.get("colspan"), "colspan"),
            tag=lower_tag,
            text_parts=[],
        )
        self.current_row.append(html_cell)
        self.current_cell = html_cell

    def handle_endtag(self, tag: str) -> None:
        lower_tag = tag.lower()
        if lower_tag not in {
            "table",
            "caption",
            "div",
            "tbody",
            "tr",
            "td",
            "th",
        }:
            raise ArtifactError(
                f"table HTML end tag is not allowed: {lower_tag}"
            )
        if lower_tag in {"td", "th"}:
            if self.current_cell is None or self.current_cell.tag != lower_tag:
                raise ArtifactError("table HTML cell nesting is invalid")
            self.current_cell = None
            return
        if lower_tag == "div":
            if not self.in_caption_div or not self.in_caption_element:
                raise ArtifactError("table HTML caption div nesting is invalid")
            self.in_caption_div = False
            return
        if lower_tag == "caption":
            if (
                not self.in_caption_element
                or self.in_caption_div
                or self.caption_div_count < 1
            ):
                raise ArtifactError(
                    "table HTML caption element nesting is invalid"
                )
            self.in_caption_element = False
            return
        if lower_tag == "tbody":
            if not self.in_tbody or self.current_row is not None:
                raise ArtifactError("table HTML tbody nesting is invalid")
            self.in_tbody = False
            return
        if lower_tag == "tr":
            if (
                self.table_depth != 1
                or self.current_row is None
                or self.current_cell is not None
            ):
                raise ArtifactError("table HTML row is incomplete")
            self.rows.append(self.current_row)
            self.current_row = None
            return
        if (
            self.table_depth != 1
            or self.current_row is not None
            or self.current_cell is not None
            or self.in_caption_element
            or self.in_caption_div
            or self.in_tbody
        ):
            raise ArtifactError("table HTML has an unmatched table end tag")
        self.table_depth = 0
        self.completed_table_count += 1

    def handle_startendtag(
        self,
        tag: str,
        attrs: list[tuple[str, str | None]],
    ) -> None:
        raise ArtifactError("table HTML self-closing syntax is not allowed")

    def handle_comment(self, data: str) -> None:
        raise ArtifactError("table HTML comments are not allowed")

    def handle_decl(self, decl: str) -> None:
        raise ArtifactError("table HTML declarations are not allowed")

    def handle_pi(self, data: str) -> None:
        raise ArtifactError("table HTML processing instructions are not allowed")

    def unknown_decl(self, data: str) -> None:
        raise ArtifactError("table HTML unknown declarations are not allowed")

    def handle_data(self, data: str) -> None:
        if self.current_cell is not None:
            self.current_cell.text_parts.append(data)
            return
        if self.in_caption_div or not data.strip():
            return
        if self.in_caption_element:
            raise ArtifactError(
                "table HTML caption text must be inside caption div"
            )
        raise ArtifactError("table HTML contains text outside a cell")

    @staticmethod
    def _span(value: str | None, attribute: str) -> int:
        if value is None:
            return 1
        try:
            span = int(value)
        except (TypeError, ValueError) as error:
            raise ArtifactError(
                f"table HTML {attribute} is not a positive integer"
            ) from error
        if span < 1 or str(span) != value.strip():
            raise ArtifactError(
                f"table HTML {attribute} is not an exact positive integer"
            )
        return span


def _html_grid_ranges(
    rows: list[list[_HtmlCell]],
    *,
    num_rows: int,
    num_columns: int,
) -> tuple[tuple[tuple[int, int, int, int], _HtmlCell], ...]:
    if len(rows) != num_rows:
        raise ArtifactError(
            "table HTML row count does not match structure"
        )
    occupied: set[tuple[int, int]] = set()
    ranges: list[tuple[tuple[int, int, int, int], _HtmlCell]] = []
    for row_index, row in enumerate(rows):
        column_index = 0
        for html_cell in row:
            row_span = html_cell.row_span
            col_span = html_cell.col_span
            while (
                column_index < num_columns
                and (row_index, column_index) in occupied
            ):
                column_index += 1
            end_row = row_index + row_span
            end_column = column_index + col_span
            if (
                column_index >= num_columns
                or end_row > num_rows
                or end_column > num_columns
            ):
                raise ArtifactError(
                    "table HTML cell range is outside the structure grid"
                )
            slots = {
                (row, column)
                for row in range(row_index, end_row)
                for column in range(column_index, end_column)
            }
            if occupied & slots:
                raise ArtifactError("table HTML cells overlap")
            occupied.update(slots)
            ranges.append(
                ((
                    row_index,
                    end_row,
                    column_index,
                    end_column,
                ), html_cell)
            )
            column_index = end_column

    expected_slots = {
        (row, column)
        for row in range(num_rows)
        for column in range(num_columns)
    }
    if occupied != expected_slots:
        raise ArtifactError(
            "table HTML cells do not cover the structure grid"
        )
    return tuple(ranges)


def _validate_table_html(table: TableData) -> None:
    if not isinstance(table.html, str) or not table.html.strip():
        raise ArtifactError("table HTML is empty or invalid")
    parser = _TableHtmlParser()
    try:
        parser.feed(table.html)
        parser.close()
    except ArtifactError:
        raise
    except Exception as error:
        raise ArtifactError(f"table HTML parsing failed: {error}") from error

    if (
        parser.table_count != 1
        or parser.completed_table_count != 1
        or parser.table_depth != 0
        or parser.current_row is not None
        or parser.current_cell is not None
        or parser.in_caption_element
        or parser.in_caption_div
    ):
        raise ArtifactError(
            "table HTML must contain exactly one complete table element"
        )
    actual_ranges = _html_grid_ranges(
        parser.rows,
        num_rows=table.num_rows,
        num_columns=table.num_columns,
    )
    expected_cells = {
        (
            cell.start_row,
            cell.end_row,
            cell.start_column,
            cell.end_column,
        ): cell
        for cell in table.cells
    }
    actual_cells = dict(actual_ranges)
    if len(actual_cells) != len(expected_cells) or set(actual_cells) != set(expected_cells):
        raise ArtifactError(
            "table HTML cell grid ranges do not match structure"
        )
    for grid_range, html_cell in actual_cells.items():
        cell = expected_cells[grid_range]
        expected_tag = (
            "th"
            if (
                cell.is_column_header
                or cell.is_row_header
                or cell.is_row_section
            )
            else "td"
        )
        html_text = " ".join(
            unicodedata.normalize(
                "NFC",
                "".join(html_cell.text_parts),
            ).split()
        )
        structure_text = " ".join(
            unicodedata.normalize("NFC", cell.text).split()
        )
        if html_cell.tag != expected_tag or html_text != structure_text:
            raise ArtifactError(
                "table HTML cell tag or text does not match structure"
            )


def validate_serialized_table_html(
    table_payload: Mapping[str, Any],
    html: str,
) -> None:
    try:
        cells = tuple(
            TableCell(
                text=cell["text"],
                bbox=tuple(cell["bbox"]),
                start_row=cell["start_row"],
                end_row=cell["end_row"],
                start_column=cell["start_column"],
                end_column=cell["end_column"],
                row_span=cell["row_span"],
                col_span=cell["col_span"],
                is_column_header=cell["is_column_header"],
                is_row_header=cell["is_row_header"],
                is_row_section=cell["is_row_section"],
                raw_ocr_comparison_status=cell[
                    "raw_ocr_comparison_status"
                ],
            )
            for cell in table_payload["cells"]
        )
        table = TableData(
            table_number=table_payload["table_number"],
            bbox=tuple(table_payload["bbox"]),
            num_rows=table_payload["num_rows"],
            num_columns=table_payload["num_columns"],
            cells=cells,
            html=html,
        )
        _validate_table_html(table)
    except ArtifactError:
        raise
    except Exception as error:
        raise ArtifactError(
            f"serialized table HTML validation failed: {error}"
        ) from error


def _strict_json_text(
    payload: Mapping[str, Any],
    *,
    description: str,
) -> str:
    try:
        return (
            json.dumps(
                payload,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
            + "\n"
        )
    except Exception as error:
        raise ArtifactError(
            f"{description} JSON serialization failed: {error}"
        ) from error


def _is_link_or_reparse(path: Path) -> bool:
    if path.is_symlink():
        return True
    is_junction = getattr(path, "is_junction", None)
    if callable(is_junction) and is_junction():
        return True
    try:
        attributes = getattr(path.lstat(), "st_file_attributes", 0)
    except FileNotFoundError:
        return False
    return bool(
        attributes
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    )


def _root_and_relative_file(
    path: Path,
    root: Path,
) -> tuple[Path, Path, Path]:
    root_path = Path(root)
    file_path = Path(path)
    root_absolute = Path(os.path.abspath(root_path))
    file_absolute = Path(os.path.abspath(file_path))

    if _is_link_or_reparse(root_absolute):
        raise ArtifactError("artifact root is a link or reparse point")
    if not root_absolute.exists() or not root_absolute.is_dir():
        raise ArtifactError("artifact root is missing or is not a directory")
    try:
        relative = file_absolute.relative_to(root_absolute)
    except ValueError as error:
        raise ArtifactError("artifact file escapes root") from error
    if not relative.parts:
        raise ArtifactError("artifact path must identify a file inside root")

    current = root_absolute
    for part in relative.parts:
        current = current / part
        if _is_link_or_reparse(current):
            raise ArtifactError(
                "artifact path crosses a link or reparse boundary"
            )
    if not file_absolute.exists():
        raise ArtifactError("artifact file is missing")
    if not file_absolute.is_file():
        raise ArtifactError("artifact path is not a regular file")

    try:
        resolved_root = root_absolute.resolve(strict=True)
        resolved_file = file_absolute.resolve(strict=True)
        resolved_file.relative_to(resolved_root)
    except (OSError, ValueError) as error:
        raise ArtifactError("artifact file escapes root") from error
    return root_absolute, file_absolute, relative


def _preflight_output_paths(
    root: Path,
    planned_paths: tuple[Path, ...],
) -> tuple[Path, ...]:
    root_absolute = Path(os.path.abspath(root))
    if _is_link_or_reparse(root_absolute):
        raise ArtifactError("artifact root is a link or reparse point")
    if not root_absolute.exists() or not root_absolute.is_dir():
        raise ArtifactError("artifact root is missing or is not a directory")
    resolved_root = root_absolute.resolve(strict=True)

    normalized_names: set[str] = set()
    directories_to_create: set[Path] = set()
    for planned_path in planned_paths:
        target = Path(os.path.abspath(planned_path))
        try:
            relative = target.relative_to(root_absolute)
        except ValueError as error:
            raise ArtifactError("planned output path escapes root") from error
        if not relative.parts:
            raise ArtifactError("planned output path must be inside root")

        normalized_name = os.path.normcase(str(target))
        if normalized_name in normalized_names:
            raise ArtifactError("planned output paths must be unique")
        normalized_names.add(normalized_name)

        current = root_absolute
        for index, part in enumerate(relative.parts):
            current = current / part
            is_target = index == len(relative.parts) - 1
            if _is_link_or_reparse(current):
                raise ArtifactError(
                    "planned output path crosses a link or reparse boundary"
                )
            if current.exists():
                try:
                    current.resolve(strict=True).relative_to(resolved_root)
                except (OSError, ValueError) as error:
                    raise ArtifactError(
                        "planned output path escapes root"
                    ) from error
                if is_target:
                    raise ArtifactError(
                        "planned output target already exists; fresh staging "
                        "is required"
                    )
                if not current.is_dir():
                    raise ArtifactError(
                        "planned output parent is not a directory"
                    )
            elif not is_target:
                directories_to_create.add(current)

    return tuple(
        sorted(
            directories_to_create,
            key=lambda path: (len(path.parts), os.path.normcase(str(path))),
        )
    )


def _file_record(path: Path, root: Path) -> dict[str, object]:
    _, file_path, relative = _root_and_relative_file(path, root)
    byte_count = file_path.stat().st_size
    digest = sha256(file_path)
    if (
        isinstance(byte_count, bool)
        or not isinstance(byte_count, int)
        or byte_count < 0
        or len(digest) != 64
        or digest != digest.lower()
    ):
        raise ArtifactError("artifact file record is invalid")
    return {
        "file_name": relative.as_posix(),
        "bytes": byte_count,
        "sha256": f"sha256:{digest}",
    }


def file_record(path: Path, root: Path) -> dict[str, object]:
    try:
        return _file_record(path, root)
    except ArtifactError:
        raise
    except Exception as error:
        raise ArtifactError(f"artifact file record failed: {error}") from error


def _coordinate_space(structure_page: StructurePage) -> dict[str, object]:
    return {
        "unit": "pixel",
        "width": structure_page.width,
        "height": structure_page.height,
        "render_dpi": 300,
        "pdf_points_per_pixel": 0.24,
    }


def _png_dimensions(image_path: Path) -> tuple[int, int]:
    try:
        return validate_png_file(image_path)
    except PngContractError as error:
        raise ArtifactError(
            f"page PNG dimension validation failed: {error}"
        ) from error


def _ocr_payload(
    ocr_page: OcrPage,
    structure_page: StructurePage,
) -> dict[str, object]:
    minimum_confidence = (
        min(token.recognition_confidence for token in ocr_page.tokens)
        if ocr_page.tokens
        else None
    )
    return {
        "schema_version": "2.0.0",
        "page_number": ocr_page.page_number,
        "engine": ocr_page.engine,
        "model_name": ocr_page.model_name,
        "coordinate_space": _coordinate_space(structure_page),
        "blocks": [asdict(token) for token in ocr_page.tokens],
        "minimum_confidence": minimum_confidence,
        "raw": ocr_page.raw,
    }


def _structure_payload(
    structure_page: StructurePage,
) -> dict[str, object]:
    page_stem = f"{structure_page.page_number:04d}"
    return {
        "schema_version": "2.0.0",
        "page_number": structure_page.page_number,
        "coordinate_space": _coordinate_space(structure_page),
        "regions": [asdict(region) for region in structure_page.regions],
        "tables": [
            {
                "table_number": table.table_number,
                "bbox": table.bbox,
                "num_rows": table.num_rows,
                "num_columns": table.num_columns,
                "cells": [asdict(cell) for cell in table.cells],
                "html_file": (
                    f"pages/{page_stem}.tables/{table.table_number:04d}.html"
                ),
            }
            for table in structure_page.tables
        ],
        "raw": structure_page.raw,
    }


def _validate_route(
    route: PageRoute,
    ocr_page: OcrPage,
    structure_page: StructurePage,
) -> None:
    if not isinstance(route, PageRoute):
        raise ArtifactError("page route is invalid")
    expected_engine = (
        "EMBEDDED_TEXT"
        if route is PageRoute.EMBEDDED_TEXT
        else "RAPIDOCR"
    )
    if ocr_page.engine != expected_engine:
        raise ArtifactError("page route does not match OCR engine")
    if route is PageRoute.RAPIDOCR_TABLEFORMER:
        if not structure_page.tables:
            raise ArtifactError(
                "RAPIDOCR_TABLEFORMER requires at least one table"
            )
    elif structure_page.tables:
        raise ArtifactError(
            "table artifacts require RAPIDOCR_TABLEFORMER route"
        )


def _validate_page_contracts(
    *,
    root: Path,
    image_path: Path,
    route: PageRoute,
    ocr_page: OcrPage,
    structure_page: StructurePage,
) -> tuple[
    dict[str, object],
    dict[str, object],
    str,
    str,
    tuple[str, ...],
]:
    _validate_comparison_pages(ocr_page, structure_page)
    page_number = _positive_page_number(
        ocr_page.page_number,
        "page number",
    )
    _validate_route(route, ocr_page, structure_page)
    if not isinstance(ocr_page.markdown, str) or not ocr_page.markdown.strip():
        raise ArtifactError("page Markdown is empty or invalid")

    page_stem = f"{page_number:04d}"
    image_record = _file_record(image_path, root)
    expected_image_name = f"pages/{page_stem}.png"
    if image_record["file_name"] != expected_image_name:
        raise ArtifactError(
            f"page image must use fixed name {expected_image_name}"
        )
    image_width, image_height = _png_dimensions(image_path)
    if (
        image_width != structure_page.width
        or image_height != structure_page.height
    ):
        raise ArtifactError(
            "page PNG dimensions do not match structure coordinate space"
        )

    expected_table_numbers = list(range(1, len(structure_page.tables) + 1))
    actual_table_numbers = [
        table.table_number
        for table in structure_page.tables
    ]
    if actual_table_numbers != expected_table_numbers:
        raise ArtifactError(
            "table_number values must be continuous, ordered, and unique"
        )

    html_texts: list[str] = []
    for table in structure_page.tables:
        _validate_table_html(table)
        html_texts.append(table.html)

    ocr_payload = _ocr_payload(ocr_page, structure_page)
    structure_payload = _structure_payload(structure_page)
    ocr_text = _strict_json_text(
        ocr_payload,
        description="OCR page",
    )
    structure_text = _strict_json_text(
        structure_payload,
        description="structure page",
    )
    normalized_ocr_payload = json.loads(ocr_text)
    normalized_structure_payload = json.loads(structure_text)
    try:
        validate_ocr_page(normalized_ocr_payload)
        validate_structure_page(normalized_structure_payload)
        validate_comparison_statuses(
            normalized_ocr_payload,
            normalized_structure_payload,
        )
        for table_payload in normalized_structure_payload["tables"]:
            validate_table_topology(table_payload)
    except ValidationError as error:
        raise ArtifactError(f"page artifact schema validation failed: {error}") from error
    except Exception as error:
        raise ArtifactError(f"page artifact validation failed: {error}") from error

    return (
        image_record,
        normalized_ocr_payload,
        ocr_text,
        structure_text,
        tuple(html_texts),
    )


def _output_record(
    path: Path,
    root: Path,
    kind: str,
) -> dict[str, object]:
    return {
        **_file_record(path, root),
        "kind": kind,
    }


def _exclusive_write_all(
    entries: tuple[tuple[Path, bytes], ...],
) -> None:
    opened: list[tuple[Path, Any]] = []
    succeeded = False
    try:
        for path, _ in entries:
            opened.append((path, path.open("xb")))
        for (path, output_file), (_, data) in zip(
            opened,
            entries,
            strict=True,
        ):
            output_file.write(data)
            output_file.flush()
        succeeded = True
    except FileExistsError as error:
        raise ArtifactError(
            "planned output target already exists; exclusive fresh staging "
            "is required"
        ) from error
    except OSError as error:
        raise ArtifactError(f"exclusive artifact write failed: {error}") from error
    finally:
        for _, output_file in opened:
            output_file.close()
        if not succeeded:
            for path, _ in opened:
                try:
                    path.unlink()
                except OSError:
                    pass


def _write_page_artifacts(
    *,
    root: Path,
    image_path: Path,
    route: PageRoute,
    ocr_page: OcrPage,
    structure_page: StructurePage,
) -> PageArtifactSet:
    (
        image_record,
        _,
        ocr_text,
        structure_text,
        html_texts,
    ) = _validate_page_contracts(
        root=root,
        image_path=image_path,
        route=route,
        ocr_page=ocr_page,
        structure_page=structure_page,
    )

    root_path = Path(os.path.abspath(root))
    page_stem = f"{ocr_page.page_number:04d}"
    pages = root_path / "pages"
    ocr_path = pages / f"{page_stem}.ocr.json"
    structure_path = pages / f"{page_stem}.structure.json"
    markdown_path = pages / f"{page_stem}.md"
    table_root = pages / f"{page_stem}.tables"
    table_paths = tuple(
        table_root / f"{table.table_number:04d}.html"
        for table in structure_page.tables
    )
    planned_paths = (
        ocr_path,
        structure_path,
        markdown_path,
        *table_paths,
    )
    directories_to_create = _preflight_output_paths(
        root_path,
        planned_paths,
    )

    for directory in directories_to_create:
        directory.mkdir()
    _exclusive_write_all(
        (
            (ocr_path, ocr_text.encode("utf-8")),
            (structure_path, structure_text.encode("utf-8")),
            (markdown_path, ocr_page.markdown.encode("utf-8")),
            *(
                (table_path, html.encode("utf-8"))
                for table_path, html in zip(
                    table_paths,
                    html_texts,
                    strict=True,
                )
            ),
        )
    )

    return PageArtifactSet(
        image=image_record,
        ocr=_output_record(ocr_path, root_path, "OCR_JSON"),
        structure=_output_record(
            structure_path,
            root_path,
            "STRUCTURE_JSON",
        ),
        markdown=_output_record(markdown_path, root_path, "MARKDOWN"),
        tables=tuple(
            _output_record(table_path, root_path, "TABLE_HTML")
            for table_path in table_paths
        ),
    )


def write_page_artifacts(
    root: Path,
    image_path: Path,
    route: PageRoute,
    ocr_page: OcrPage,
    structure_page: StructurePage,
) -> PageArtifactSet:
    try:
        return _write_page_artifacts(
            root=root,
            image_path=image_path,
            route=route,
            ocr_page=ocr_page,
            structure_page=structure_page,
        )
    except ArtifactError:
        raise
    except Exception as error:
        raise ArtifactError(
            f"page artifact writing failed: {error}"
        ) from error
