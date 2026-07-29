from dataclasses import dataclass
from typing import Any, Mapping


Point = tuple[float, float]
BBox = tuple[float, float, float, float]


@dataclass(frozen=True)
class OcrToken:
    text: str
    recognition_confidence: float
    polygon: tuple[Point, ...]
    bbox: BBox
    reading_order: int
    model_name: str
    source_page_number: int


@dataclass(frozen=True)
class OcrPage:
    page_number: int
    engine: str
    model_name: str
    markdown: str
    tokens: tuple[OcrToken, ...]
    raw: Mapping[str, Any]


@dataclass(frozen=True)
class LayoutRegion:
    label: str
    bbox: BBox
    reading_order: int


@dataclass(frozen=True)
class LayoutPage:
    page_number: int
    width: int
    height: int
    regions: tuple[LayoutRegion, ...]
    has_table: bool
    has_complex_layout: bool


@dataclass(frozen=True)
class TableCell:
    text: str
    bbox: BBox
    start_row: int
    end_row: int
    start_column: int
    end_column: int
    row_span: int
    col_span: int
    is_column_header: bool
    is_row_header: bool
    is_row_section: bool
    raw_ocr_comparison_status: str


@dataclass(frozen=True)
class TableData:
    table_number: int
    bbox: BBox
    num_rows: int
    num_columns: int
    cells: tuple[TableCell, ...]
    html: str


@dataclass(frozen=True)
class StructurePage:
    page_number: int
    width: int
    height: int
    regions: tuple[LayoutRegion, ...]
    tables: tuple[TableData, ...]
    raw: Mapping[str, Any]
