from __future__ import annotations

import hashlib
import json
import math
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Any, Mapping, Sequence

from jsonschema import Draft202012Validator, FormatChecker, ValidationError

from .image_contract import PngContractError, validate_png_bytes
from .model_lock import (
    LockedArtifact,
    ModelLockError,
    revalidate_locked_artifacts,
)
from .runtime import RuntimeInfo
from .strict_json import StrictJsonError, strict_json_loads


SCHEMA_ROOT = Path(__file__).resolve().parents[2] / "schemas"
MANIFEST_SCHEMA_PATH = SCHEMA_ROOT / "manifest.schema.json"
OCR_PAGE_SCHEMA_PATH = SCHEMA_ROOT / "page-ocr.schema.json"
STRUCTURE_PAGE_SCHEMA_PATH = SCHEMA_ROOT / "page-structure.schema.json"
MODEL_COMPONENT_ROLES = {
    "RAPIDOCR": {
        "rapidocr_det",
        "rapidocr_cls",
        "rapidocr_rec",
        "rapidocr_rec_keys",
        "rapidocr_font",
    },
    "DOCLING": {"docling_layout"},
    "TABLEFORMER": {"tableformer"},
}
REQUIRED_MODEL_COMPONENT_ROLES = {
    (component, role)
    for component, roles in MODEL_COMPONENT_ROLES.items()
    for role in roles
}
FORMAT_CHECKER = FormatChecker()
RFC3339_DATETIME = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    r"(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)
MANDATORY_REVIEW_REASONS = frozenset(
    {
        "NOTICE_NUMBER",
        "LEGAL_DATE",
        "AREA",
        "JURISDICTION",
        "TAX_RULE",
        "LEGAL_EFFECT",
        "SPATIAL_BOUNDARY",
        "SOURCE_RIGHTS",
    }
)
REVIEW_REASON_VALUES = MANDATORY_REVIEW_REASONS | {
    "LOW_CONFIDENCE",
    "OCR_TABLE_MISMATCH",
    "MERGED_OR_MULTILEVEL_HEADER",
    "POSSIBLE_CROSS_PAGE_TABLE",
}


def _validate_schema(payload: Mapping[str, Any], schema_path: Path) -> None:
    _reject_nonfinite(payload)
    with schema_path.open(encoding="utf-8") as schema_file:
        schema = json.load(schema_file)
    Draft202012Validator(
        schema,
        format_checker=FORMAT_CHECKER,
    ).validate(payload)


def _reject_nonfinite(value: Any) -> None:
    if isinstance(value, float) and not math.isfinite(value):
        raise ValidationError("JSON numbers must be finite")
    if isinstance(value, Mapping):
        for nested in value.values():
            _reject_nonfinite(nested)
    elif isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        for nested in value:
            _reject_nonfinite(nested)


def _finite_number(value: Any, description: str) -> float:
    if isinstance(value, bool):
        raise ValidationError(f"{description} must be a finite number")
    try:
        normalized = float(value)
    except (TypeError, ValueError, OverflowError) as error:
        raise ValidationError(
            f"{description} must be a finite number"
        ) from error
    if not math.isfinite(normalized):
        raise ValidationError(f"{description} must be a finite number")
    return normalized


def _strict_int(value: Any, description: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValidationError(f"{description} must be a strict integer")
    return value


def _safe_relative_posix_path(value: Any, description: str) -> PurePosixPath:
    if not isinstance(value, str):
        raise ValidationError(
            f"{description} file_name path must be a safe relative POSIX path"
        )
    segments = value.split("/")
    if (
        not value
        or value.startswith("/")
        or "\\" in value
        or "\x00" in value
        or ":" in value
        or any(segment in {"", ".", ".."} for segment in segments)
    ):
        raise ValidationError(
            f"{description} file_name path is unsafe or escapes its root; "
            "a relative POSIX path is required"
        )
    path = PurePosixPath(value)
    if path.is_absolute() or path.as_posix() != value:
        raise ValidationError(
            f"{description} file_name path is unsafe or escapes its root; "
            "a relative POSIX path is required"
        )
    return path


def _width_only_normalize(value: str) -> str:
    return unicodedata.normalize(
        "NFC",
        "".join(
            unicodedata.normalize("NFKC", character)
            if unicodedata.east_asian_width(character) in {"F", "H"}
            else character
            for character in value
        ),
    )


def _comparison_text(value: str) -> str:
    return "".join(
        character
        for character in _width_only_normalize(value)
        if not character.isspace()
    )


def _numeric_whitespace_risk(values: Sequence[str]) -> bool:
    normalized = tuple(_width_only_normalize(value) for value in values)
    for value in normalized:
        for index, character in enumerate(value):
            if not character.isspace():
                continue
            before = value[index - 1] if index else ""
            after = value[index + 1] if index + 1 < len(value) else ""
            if before.isdigit() and after.isdigit():
                return True
    ocr_values = normalized[:-1]
    return any(
        left.rstrip()[-1:].isdigit() and right.lstrip()[:1].isdigit()
        for left, right in zip(ocr_values, ocr_values[1:], strict=False)
    )


def _validate_bbox(
    bbox: Sequence[Any],
    *,
    width: float | None = None,
    height: float | None = None,
) -> None:
    x0, y0, x1, y1 = (
        _finite_number(value, "bbox coordinate")
        for value in bbox
    )
    if x0 < 0 or y0 < 0 or x0 >= x1 or y0 >= y1:
        raise ValidationError("bbox is negative, empty, or reversed")
    if width is not None and (x1 > width or y1 > height):
        raise ValidationError("bbox is outside the page coordinate space")


def validate_ocr_page(payload: Mapping[str, Any]) -> None:
    _validate_schema(payload, OCR_PAGE_SCHEMA_PATH)

    width = _finite_number(payload["coordinate_space"]["width"], "page width")
    height = _finite_number(payload["coordinate_space"]["height"], "page height")
    page_number = payload["page_number"]
    reading_orders: set[int] = set()
    confidences: list[float] = []
    for block in payload["blocks"]:
        reading_order = block["reading_order"]
        if reading_order in reading_orders:
            raise ValidationError("OCR block reading_order values must be unique")
        reading_orders.add(reading_order)
        if block["source_page_number"] != page_number:
            raise ValidationError("OCR block source_page_number does not match page")
        if block["model_name"] != payload["model_name"]:
            raise ValidationError(
                "OCR block model_name does not match page model_name"
            )
        if (
            payload["engine"] == "EMBEDDED_TEXT"
            and block["model_name"] != "embedded-text"
        ):
            raise ValidationError(
                "EMBEDDED_TEXT blocks must use the embedded-text model"
            )
        _validate_bbox(block["bbox"], width=width, height=height)
        confidences.append(
            _finite_number(
                block["recognition_confidence"],
                "recognition_confidence",
            )
        )
        polygon: list[tuple[float, float]] = []
        for point in block["polygon"]:
            x, y = (
                _finite_number(value, "polygon coordinate")
                for value in point
            )
            if x < 0 or y < 0 or x > width or y > height:
                raise ValidationError(
                    "OCR polygon is outside the page coordinate space"
                )
            polygon.append((x, y))
        area = abs(
            sum(
                x0 * y1 - x1 * y0
                for (x0, y0), (x1, y1) in zip(
                    polygon,
                    polygon[1:] + polygon[:1],
                    strict=True,
                )
            )
        ) / 2.0
        if not math.isfinite(area) or area <= 0:
            raise ValidationError("OCR polygon must have positive area")
        polygon_bbox = (
            min(point[0] for point in polygon),
            min(point[1] for point in polygon),
            max(point[0] for point in polygon),
            max(point[1] for point in polygon),
        )
        declared_bbox = tuple(
            _finite_number(value, "bbox coordinate")
            for value in block["bbox"]
        )
        tolerance = 1e-6
        if any(
            not math.isclose(
                declared,
                expected,
                rel_tol=1e-9,
                abs_tol=tolerance,
            )
            for declared, expected in zip(
                declared_bbox,
                polygon_bbox,
                strict=True,
            )
        ):
            raise ValidationError(
                "OCR bbox does not match the polygon min/max envelope"
            )
    minimum_confidence = payload["minimum_confidence"]
    if confidences:
        minimum = _finite_number(minimum_confidence, "minimum_confidence")
        if minimum != min(confidences):
            raise ValidationError(
                "minimum_confidence does not match block minimum"
            )
    elif minimum_confidence is not None:
        raise ValidationError(
            "minimum_confidence must be null when blocks are empty"
        )


def validate_table_topology(table: Mapping[str, Any]) -> None:
    try:
        num_rows = _strict_int(table["num_rows"], "table num_rows")
        num_columns = _strict_int(
            table["num_columns"],
            "table num_columns",
        )
        cells = table["cells"]
        table_bbox = table["bbox"]
    except KeyError as error:
        raise ValidationError("table topology fields are missing or invalid") from error

    if num_rows < 1 or num_columns < 1:
        raise ValidationError("table rows and columns must be positive")
    if not isinstance(cells, Sequence) or isinstance(cells, (str, bytes)) or not cells:
        raise ValidationError("table cells must not be empty")
    _validate_bbox(table_bbox)
    tx0, ty0, tx1, ty1 = (float(value) for value in table_bbox)

    expected = {
        (row, column)
        for row in range(num_rows)
        for column in range(num_columns)
    }
    occupied: set[tuple[int, int]] = set()
    bboxes: list[tuple[float, float, float, float]] = []
    for cell in cells:
        if not isinstance(cell, Mapping):
            raise ValidationError("table cell topology must be an object")
        try:
            start_row = _strict_int(cell["start_row"], "table cell start_row")
            end_row = _strict_int(cell["end_row"], "table cell end_row")
            start_column = _strict_int(
                cell["start_column"],
                "table cell start_column",
            )
            end_column = _strict_int(
                cell["end_column"],
                "table cell end_column",
            )
            row_span = _strict_int(cell["row_span"], "table cell row_span")
            col_span = _strict_int(cell["col_span"], "table cell col_span")
        except KeyError as error:
            raise ValidationError(
                "table cell topology fields are missing"
            ) from error
        if (
            start_row < 0
            or start_column < 0
            or end_row <= start_row
            or end_column <= start_column
            or end_row > num_rows
            or end_column > num_columns
        ):
            raise ValidationError("table cell range is outside the declared grid")
        if row_span != end_row - start_row:
            raise ValidationError("row_span does not match row range")
        if col_span != end_column - start_column:
            raise ValidationError("col_span does not match column range")

        _validate_bbox(cell["bbox"])
        cx0, cy0, cx1, cy1 = (float(value) for value in cell["bbox"])
        if cx0 < tx0 or cy0 < ty0 or cx1 > tx1 or cy1 > ty1:
            raise ValidationError("cell bbox is outside the table bbox")
        for ox0, oy0, ox1, oy1 in bboxes:
            if min(cx1, ox1) > max(cx0, ox0) and min(cy1, oy1) > max(cy0, oy0):
                raise ValidationError(
                    "table cell bboxes overlap geometrically"
                )
        bboxes.append((cx0, cy0, cx1, cy1))

        slots = {
            (row, column)
            for row in range(start_row, end_row)
            for column in range(start_column, end_column)
        }
        if occupied & slots:
            raise ValidationError("table cells overlap")
        occupied.update(slots)
    if occupied != expected:
        raise ValidationError("table cells do not cover the declared grid")


def validate_structure_page(payload: Mapping[str, Any]) -> None:
    _validate_schema(payload, STRUCTURE_PAGE_SCHEMA_PATH)

    width = float(payload["coordinate_space"]["width"])
    height = float(payload["coordinate_space"]["height"])
    for region in payload["regions"]:
        _validate_bbox(region["bbox"], width=width, height=height)

    table_numbers: set[int] = set()
    html_files: set[str] = set()
    for table in payload["tables"]:
        if table["table_number"] in table_numbers:
            raise ValidationError("table_number values must be unique")
        table_numbers.add(table["table_number"])
        if table["html_file"] in html_files:
            raise ValidationError("table html_file values must be unique")
        html_files.add(table["html_file"])
        _validate_bbox(table["bbox"], width=width, height=height)
        for table_cell in table["cells"]:
            _validate_bbox(table_cell["bbox"], width=width, height=height)
        validate_table_topology(table)


def validate_manifest(payload: Mapping[str, Any]) -> None:
    _validate_manifest_model_files(payload)
    _validate_schema(payload, MANIFEST_SCHEMA_PATH)
    if not RFC3339_DATETIME.fullmatch(payload["started_at"]) or not (
        RFC3339_DATETIME.fullmatch(payload["completed_at"])
    ):
        raise ValidationError(
            "started_at and completed_at must be RFC3339 date-time values"
        )
    try:
        started_at = datetime.fromisoformat(
            payload["started_at"].replace("Z", "+00:00")
        )
        completed_at = datetime.fromisoformat(
            payload["completed_at"].replace("Z", "+00:00")
        )
    except ValueError as error:
        raise ValidationError("manifest date-time value is invalid") from error
    if completed_at < started_at:
        raise ValidationError("completed_at must not precede started_at")

    page_count = payload["input"]["page_count"]
    page_numbers = [page["page_number"] for page in payload["pages"]]
    expected_page_numbers = list(range(1, page_count + 1))
    if page_numbers != expected_page_numbers:
        raise ValidationError(
            "page numbers must be continuous, ordered, and match input.page_count"
        )

    file_names: set[str] = set()
    for page in payload["pages"]:
        if page["review"]["status"] != "PENDING_HUMAN_REVIEW":
            raise ValidationError(
                "manifest review status must remain PENDING_HUMAN_REVIEW"
            )
        reasons = set(page["review"]["reasons"])
        if not MANDATORY_REVIEW_REASONS.issubset(reasons):
            raise ValidationError(
                "manifest review reasons are missing mandatory review gates"
            )
        if not reasons.issubset(REVIEW_REASON_VALUES):
            raise ValidationError("manifest review contains an unknown reason")
        records = [page["image"], *page["outputs"]]
        for record in records:
            file_name = record["file_name"]
            _safe_relative_posix_path(file_name, "manifest page artifact")
            if file_name in file_names:
                raise ValidationError("manifest file_name values must be unique")
            file_names.add(file_name)

        kinds = Counter(output["kind"] for output in page["outputs"])
        for required_kind in ("OCR_JSON", "STRUCTURE_JSON", "MARKDOWN"):
            if kinds[required_kind] != 1:
                raise ValidationError(
                    f"page outputs require exactly one {required_kind}"
                )
        if page["route"] == "RAPIDOCR_TABLEFORMER":
            if kinds["TABLE_HTML"] < 1:
                raise ValidationError(
                    "RAPIDOCR_TABLEFORMER requires TABLE_HTML output"
                )
        elif kinds["TABLE_HTML"]:
            raise ValidationError(
                "TABLE_HTML output is only valid for RAPIDOCR_TABLEFORMER"
            )


def _validate_manifest_model_files(payload: Mapping[str, Any]) -> None:
    try:
        model_files = payload["runtime"]["model_files"]
    except (KeyError, TypeError):
        return
    if not isinstance(model_files, Sequence) or isinstance(
        model_files, (str, bytes)
    ):
        return
    if not all(
        isinstance(item, Mapping)
        and isinstance(item.get("component"), str)
        and isinstance(item.get("role"), str)
        for item in model_files
    ):
        return

    combinations = [
        (item["component"], item["role"])
        for item in model_files
    ]
    for component, role in combinations:
        if role not in MODEL_COMPONENT_ROLES.get(component, set()):
            raise ValidationError(
                f"model component/role combination is invalid: {component}/{role}"
            )
    for item in model_files:
        _safe_relative_posix_path(
            item.get("file_name"),
            "manifest model",
        )
    identities = [
        (item["component"], item["role"], item.get("file_name"))
        for item in model_files
    ]
    duplicate_combinations = [
        combination
        for combination, count in Counter(identities).items()
        if count > 1
    ]
    if duplicate_combinations:
        raise ValidationError(
            f"duplicate model component/role/file_name: {duplicate_combinations}"
        )
    missing = REQUIRED_MODEL_COMPONENT_ROLES - set(combinations)
    if missing:
        raise ValidationError(
            f"model files are missing required component/role combinations: "
            f"{sorted(missing)}"
        )


def _strict_json_mapping(data: bytes, description: str) -> Mapping[str, Any]:
    try:
        value = strict_json_loads(data, description=description)
    except StrictJsonError as error:
        raise ValidationError(
            f"{description} must be strict JSON: {error}"
        ) from error
    if not isinstance(value, Mapping):
        raise ValidationError(f"{description} must be a JSON object")
    return value


def _expected_comparison_statuses(
    ocr_payload: Mapping[str, Any],
    structure_payload: Mapping[str, Any],
) -> list[tuple[Mapping[str, Any], str]]:
    blocks = sorted(
        ocr_payload["blocks"],
        key=lambda block: block["reading_order"],
    )
    result: list[tuple[Mapping[str, Any], str]] = []
    for table in structure_payload["tables"]:
        cells = table["cells"]
        for block in blocks:
            x0, y0, x1, y1 = (
                _finite_number(value, "OCR block bbox")
                for value in block["bbox"]
            )
            center_x = (x0 + x1) / 2.0
            center_y = (y0 + y1) / 2.0
            matches = 0
            for cell in cells:
                cx0, cy0, cx1, cy1 = (
                    _finite_number(value, "table cell bbox")
                    for value in cell["bbox"]
                )
                matches += (
                    cx0 <= center_x <= cx1
                    and cy0 <= center_y <= cy1
                )
            if matches > 1:
                raise ValidationError(
                    "OCR token assignment is ambiguous across table cells"
                )
        for cell in cells:
            cx0, cy0, cx1, cy1 = (
                _finite_number(value, "table cell bbox")
                for value in cell["bbox"]
            )
            cell_blocks = []
            for block in blocks:
                x0, y0, x1, y1 = (
                    _finite_number(value, "OCR block bbox")
                    for value in block["bbox"]
                )
                center_x = (x0 + x1) / 2.0
                center_y = (y0 + y1) / 2.0
                if cx0 <= center_x <= cx1 and cy0 <= center_y <= cy1:
                    cell_blocks.append(block)
            raw_values = [block["text"] for block in cell_blocks]
            raw_text = "".join(raw_values)
            normalized_raw = _comparison_text(raw_text)
            normalized_cell = _comparison_text(cell["text"])
            if not normalized_raw and not normalized_cell:
                status = "NOT_COMPARABLE"
            elif (
                normalized_raw == normalized_cell
                and not _numeric_whitespace_risk(
                    (*raw_values, cell["text"])
                )
            ):
                status = "MATCHED"
            else:
                status = "MISMATCH"
            result.append((cell, status))
    return result


def validate_comparison_statuses(
    ocr_payload: Mapping[str, Any],
    structure_payload: Mapping[str, Any],
) -> None:
    for cell, expected in _expected_comparison_statuses(
        ocr_payload,
        structure_payload,
    ):
        if cell["raw_ocr_comparison_status"] != expected:
            raise ValidationError(
                "raw_ocr_comparison_status does not match recomputed OCR/table "
                "comparison"
            )


def _expected_review_reasons(
    ocr_payload: Mapping[str, Any],
    structure_payload: Mapping[str, Any],
) -> set[str]:
    reasons = set(MANDATORY_REVIEW_REASONS)
    minimum_confidence = ocr_payload["minimum_confidence"]
    if minimum_confidence is not None and (
        _finite_number(minimum_confidence, "minimum_confidence") < 0.90
    ):
        reasons.add("LOW_CONFIDENCE")
    if any(
        cell["raw_ocr_comparison_status"] == "MISMATCH"
        for table in structure_payload["tables"]
        for cell in table["cells"]
    ):
        reasons.add("OCR_TABLE_MISMATCH")
    if any(
        cell["row_span"] > 1
        or cell["col_span"] > 1
        or (
            cell["is_column_header"]
            and cell["start_row"] > 0
        )
        for table in structure_payload["tables"]
        for cell in table["cells"]
    ):
        reasons.add("MERGED_OR_MULTILEVEL_HEADER")
    page_height = structure_payload["coordinate_space"]["height"]
    if any(
        table["bbox"][1] <= 24.0
        or page_height - table["bbox"][3] <= 24.0
        for table in structure_payload["tables"]
    ):
        reasons.add("POSSIBLE_CROSS_PAGE_TABLE")
    return reasons


def validate_output_hashes(
    payload: Mapping[str, Any],
    root: Path,
    *,
    locked_rapidocr_model_name: str | None = None,
) -> None:
    resolved_root = root.resolve()
    records: list[Mapping[str, Any]] = []
    for page in payload["pages"]:
        records.append(page["image"])
        records.extend(page["outputs"])

    file_bytes: dict[str, bytes] = {}
    for record in records:
        relative = _safe_relative_posix_path(
            record["file_name"],
            "manifest output",
        )
        path = (resolved_root / Path(*relative.parts)).resolve()
        if resolved_root not in path.parents or not path.is_file():
            raise ValidationError("manifest output path is missing or escapes root")
        try:
            data = path.read_bytes()
        except OSError as error:
            raise ValidationError("manifest output path could not be read") from error
        if len(data) != record["bytes"]:
            raise ValidationError("manifest output size mismatch")
        digest = "sha256:" + hashlib.sha256(data).hexdigest()
        if digest != record["sha256"]:
            raise ValidationError("manifest output SHA-256 mismatch")
        if record["file_name"] in file_bytes:
            raise ValidationError("manifest output file_name is duplicated")
        file_bytes[record["file_name"]] = data

    for page in payload["pages"]:
        page_number = page["page_number"]
        page_stem = f"{page_number:04d}"
        outputs = page["outputs"]
        expected_names = {
            "OCR_JSON": f"pages/{page_stem}.ocr.json",
            "STRUCTURE_JSON": f"pages/{page_stem}.structure.json",
            "MARKDOWN": f"pages/{page_stem}.md",
        }
        image_name = page["image"]["file_name"]
        if image_name != f"pages/{page_stem}.png":
            raise ValidationError("page image does not use the fixed page stem")
        try:
            image_width, image_height = validate_png_bytes(
                file_bytes[image_name]
            )
        except PngContractError as error:
            raise ValidationError(f"page image violates PNG contract: {error}") from error
        for output in outputs:
            expected_name = expected_names.get(output["kind"])
            if expected_name is not None and output["file_name"] != expected_name:
                raise ValidationError(
                    f"{output['kind']} does not use the fixed page stem"
                )
        manifest_table_html_files = [
            output["file_name"]
            for output in outputs
            if output["kind"] == "TABLE_HTML"
        ]
        structure_records = [
            output for output in outputs if output["kind"] == "STRUCTURE_JSON"
        ]
        if len(structure_records) != 1:
            raise ValidationError(
                "page requires exactly one STRUCTURE_JSON output"
            )
        ocr_records = [
            output for output in outputs if output["kind"] == "OCR_JSON"
        ]
        if len(ocr_records) != 1:
            raise ValidationError("page requires exactly one OCR_JSON output")
        ocr_payload = _strict_json_mapping(
            file_bytes[ocr_records[0]["file_name"]],
            "OCR_JSON output",
        )
        structure_payload = _strict_json_mapping(
            file_bytes[structure_records[0]["file_name"]],
            "STRUCTURE_JSON output",
        )
        validate_ocr_page(ocr_payload)
        validate_structure_page(structure_payload)
        if ocr_payload["page_number"] != page_number:
            raise ValidationError("OCR JSON page does not match manifest page")
        if structure_payload["page_number"] != page_number:
            raise ValidationError("structure JSON page does not match manifest page")
        expected_engine = (
            "EMBEDDED_TEXT"
            if page["route"] == "EMBEDDED_TEXT"
            else "RAPIDOCR"
        )
        if ocr_payload["engine"] != expected_engine:
            raise ValidationError("manifest route does not match OCR engine")
        if (
            expected_engine == "RAPIDOCR"
            and locked_rapidocr_model_name is not None
            and ocr_payload["model_name"] != locked_rapidocr_model_name
        ):
            raise ValidationError(
                "RAPIDOCR OCR model_name does not match the locked recognizer"
            )
        if ocr_payload["coordinate_space"] != structure_payload["coordinate_space"]:
            raise ValidationError("OCR and structure coordinate spaces do not match")
        coordinate_space = ocr_payload["coordinate_space"]
        if (
            coordinate_space["width"] != image_width
            or coordinate_space["height"] != image_height
        ):
            raise ValidationError(
                "hashed PNG dimensions do not match JSON coordinate space"
            )
        validate_comparison_statuses(ocr_payload, structure_payload)
        structure_table_html_files = [
            table["html_file"]
            for table in structure_payload["tables"]
        ]
        expected_table_html_files = [
            f"pages/{page_stem}.tables/{table['table_number']:04d}.html"
            for table in structure_payload["tables"]
        ]
        if structure_table_html_files != expected_table_html_files:
            raise ValidationError(
                "TABLE_HTML paths do not use the fixed page/table stem"
            )
        if (
            len(manifest_table_html_files) != len(structure_table_html_files)
            or set(manifest_table_html_files) != set(structure_table_html_files)
        ):
            raise ValidationError(
                "TABLE_HTML paths do not match structure html_file paths"
            )
        from .artifacts import validate_serialized_table_html

        for table in structure_payload["tables"]:
            html_name = table["html_file"]
            try:
                html = file_bytes[html_name].decode("utf-8", errors="strict")
                validate_serialized_table_html(table, html)
            except (UnicodeError, KeyError, ValueError, RuntimeError) as error:
                raise ValidationError(
                    f"hashed TABLE_HTML output is invalid: {error}"
                ) from error
        if "review" in page:
            expected_reasons = _expected_review_reasons(
                ocr_payload,
                structure_payload,
            )
            if set(page["review"]["reasons"]) != expected_reasons:
                raise ValidationError(
                    "manifest review reasons do not match recomputed page gates"
                )


def validate_manifest_against_runtime(
    payload: Mapping[str, Any],
    runtime: RuntimeInfo,
    artifacts: Sequence[LockedArtifact],
) -> None:
    validate_manifest(payload)
    try:
        revalidate_locked_artifacts(artifacts)
    except ModelLockError as error:
        raise ValidationError(f"locked model artifacts are invalid: {error}") from error
    runtime_payload = payload["runtime"]
    version_fields = {
        "rapidocr": "rapidocr_version",
        "onnxruntime": "onnxruntime_version",
        "docling": "docling_version",
        "docling-ibm-models": "docling_ibm_models_version",
    }
    if set(runtime.package_versions) != set(version_fields):
        raise ValidationError("RuntimeInfo package versions are incomplete")
    for package_name, manifest_field in version_fields.items():
        if (
            runtime_payload[manifest_field]
            != runtime.package_versions[package_name]
        ):
            raise ValidationError(
                f"manifest runtime version does not match RuntimeInfo: "
                f"{package_name}"
            )
    if runtime_payload["execution_provider"] != runtime.execution_provider:
        raise ValidationError(
            "manifest execution provider does not match RuntimeInfo"
        )

    fields = (
        "component",
        "role",
        "name",
        "source_url",
        "license",
        "file_name",
        "bytes",
        "sha256",
    )
    expected_records = []
    for artifact in artifacts:
        for locked_file in artifact.files:
            file_name = (
                artifact.root_relative_path / locked_file.relative_path
            ).as_posix()
            _safe_relative_posix_path(file_name, "locked model projection")
            expected_records.append(
                {
                    "component": artifact.component,
                    "role": artifact.role,
                    "name": artifact.name,
                    "source_url": artifact.source_url,
                    "license": artifact.license,
                    "file_name": file_name,
                    "bytes": locked_file.bytes,
                    "sha256": locked_file.sha256,
                }
            )
    expected = Counter(
        tuple(record[field] for field in fields)
        for record in expected_records
    )
    actual = Counter(
        tuple(record[field] for field in fields)
        for record in runtime_payload["model_files"]
    )
    if actual != expected:
        raise ValidationError(
            "manifest model_files do not match the exact locked model projection"
        )


def validate_publication_bundle(
    payload: Mapping[str, Any],
    root: Path,
    runtime: RuntimeInfo,
    artifacts: Sequence[LockedArtifact],
) -> None:
    validate_manifest_against_runtime(payload, runtime, artifacts)
    recognition = [
        artifact
        for artifact in artifacts
        if artifact.role == "rapidocr_rec"
    ]
    if len(recognition) != 1:
        raise ValidationError(
            "publication requires exactly one locked rapidocr_rec artifact"
        )
    validate_output_hashes(
        payload,
        root,
        locked_rapidocr_model_name=recognition[0].name,
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
