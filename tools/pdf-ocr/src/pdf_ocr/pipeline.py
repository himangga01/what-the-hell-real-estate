from __future__ import annotations

import ctypes
import errno
import hashlib
import json
import os
import platform
import re
import shutil
import stat
import sys
import tempfile
import uuid
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any, Protocol

import fitz
from pypdf import PdfReader
from pypdf.errors import PdfReadError

from pdf_ocr.artifacts import (
    PageArtifactSet,
    compare_table_cells,
    write_page_artifacts,
)
from pdf_ocr.contracts import (
    MANDATORY_REVIEW_REASONS,
    validate_publication_bundle,
)
from pdf_ocr.image_contract import validate_png_file
from pdf_ocr.model_lock import LockedArtifact, load_model_lock
from pdf_ocr.ocr import create_rapidocr_runner
from pdf_ocr.router import PageRoute, embedded_text_quality, select_page_route
from pdf_ocr.runtime import RuntimeInfo, collect_runtime_info
from pdf_ocr.strict_json import strict_json_loads
from pdf_ocr.structure import (
    DoclingRunner,
    _has_complex_layout as calculate_complex_layout,
    create_layout_converter,
    create_table_converter,
)
from pdf_ocr.types import (
    LayoutPage,
    OcrPage,
    OcrToken,
    StructurePage,
)


RENDER_DPI = 300
STAGING_OWNER_MARKER = ".pdf-ocr-staging-owner"
RECOVERY_TOKEN_ENV = "PDF_OCR_RECOVERY_TOKEN"
STAGING_NONCE_ENV = "PDF_OCR_STAGING_NONCE"
STAGING_PATH_ENV = "PDF_OCR_STAGING_PATH"
RECOVERY_RECEIPT_ENV = "PDF_OCR_RECOVERY_RECEIPT"
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODEL_LOCK_PATH = PACKAGE_ROOT / "models.lock.json"
DEFAULT_UV_LOCK_PATH = PACKAGE_ROOT / "uv.lock"
MANIFEST_FILE_NAME = "pdf-ocr-manifest.json"
WARNING = (
    "OCR output cannot independently mark legal, tax, spatial, or source-rights "
    "facts as verified."
)


class PdfOcrError(RuntimeError):
    pass


class OutputExistsError(PdfOcrError):
    pass


class _WindowsRenameSharingError(PdfOcrError):
    pass


class OcrRunner(Protocol):
    def recognize(
        self,
        image_path: Path,
        *,
        page_number: int,
    ) -> OcrPage: ...


class StructureRunner(Protocol):
    def detect_layout(
        self,
        image_path: Path,
        *,
        page_number: int,
    ) -> LayoutPage: ...

    def recognize_tables(
        self,
        image_path: Path,
        *,
        page_number: int,
    ) -> StructurePage: ...


@dataclass(frozen=True)
class _PathIdentity:
    device: int
    inode: int


@dataclass(frozen=True)
class _FileIdentity:
    device: int
    inode: int
    size: int
    modified_ns: int
    changed_ns: int


@dataclass
class _DirectoryGuard:
    path: Path
    identity: _PathIdentity
    windows_handle: int | None = None
    windows_volume: int | None = None
    windows_file_id: int | None = None

    def close(self) -> None:
        if self.windows_handle is None:
            return
        handle = self.windows_handle
        self.windows_handle = None
        _windows_close_handle(handle)


@dataclass(frozen=True)
class _InputSnapshot:
    data: bytes
    sha256: str
    size: int
    source_identity: _PathIdentity


@dataclass(frozen=True)
class _RecoveryHandshake:
    token: str
    nonce: str
    staging_path: Path
    receipt_path: Path


@dataclass
class _FinalReadGuard:
    path: Path
    relative_name: str
    expected_size: int
    expected_sha256: str
    initial_state: tuple[int, int, int, int, int]
    handle: int | None
    expected_exact_bytes: bytes | None = None

    def close(self) -> None:
        if self.handle is None:
            return
        handle = self.handle
        self.handle = None
        _windows_close_handle(handle)


@dataclass(frozen=True)
class _RenderedPage:
    page_number: int
    image_path: Path
    embedded_text: str
    layout: LayoutPage


def embedded_text_page(
    page: fitz.Page,
    text: str,
    page_number: int,
) -> OcrPage:
    scale = RENDER_DPI / 72.0
    tokens: list[OcrToken] = []
    for block in page.get_text("blocks"):
        block_text = str(block[4]).strip()
        if not block_text:
            continue
        bbox = tuple(float(block[index]) * scale for index in range(4))
        x0, y0, x1, y1 = bbox
        tokens.append(
            OcrToken(
                text=block_text,
                recognition_confidence=1.0,
                polygon=((x0, y0), (x1, y0), (x1, y1), (x0, y1)),
                bbox=(x0, y0, x1, y1),
                reading_order=len(tokens),
                model_name="embedded-text",
                source_page_number=page_number,
            )
        )
    return OcrPage(
        page_number=page_number,
        engine="EMBEDDED_TEXT",
        model_name="embedded-text",
        markdown=text.strip(),
        tokens=tuple(tokens),
        raw={"source": "pypdf_embedded_text"},
    )


def structure_from_layout(layout: LayoutPage) -> StructurePage:
    return StructurePage(
        page_number=layout.page_number,
        width=layout.width,
        height=layout.height,
        regions=layout.regions,
        tables=(),
        raw={"source": "docling_layout_only"},
    )


def any_cell_status(page: StructurePage, status: str) -> bool:
    return any(
        cell.raw_ocr_comparison_status == status
        for table in page.tables
        for cell in table.cells
    )


def has_merged_or_multilevel_header(page: StructurePage) -> bool:
    return any(
        cell.row_span > 1
        or cell.col_span > 1
        or (cell.is_column_header and cell.start_row > 0)
        for table in page.tables
        for cell in table.cells
    )


def has_possible_cross_page_table(page: StructurePage) -> bool:
    edge_margin = 24.0
    return any(
        table.bbox[1] <= edge_margin
        or page.height - table.bbox[3] <= edge_margin
        for table in page.tables
    )


def extract_pdf(
    input_path: Path,
    output_dir: Path,
    *,
    ocr_runner: OcrRunner | None = None,
    structure_runner: StructureRunner | None = None,
    model_lock_path: Path | None = None,
    model_home: Path | None = None,
    uv_lock_path: Path | None = None,
) -> Path:
    input_file = _validated_input_path(input_path, output_dir)
    output = _prepare_output_path(output_dir)

    parent = output.parent
    parent_guard: _DirectoryGuard | None = None
    staging: Path | None = None
    staging_guard: _DirectoryGuard | None = None
    owner_token: str | None = None
    try:
        parent_guard = _open_directory_guard(parent, parent_target=True)
        staging, staging_guard, owner_token = _create_private_staging(
            output,
            parent_guard,
        )
        started_at = _timestamp()
        snapshot = _snapshot_input(input_file)
        embedded_texts = _read_embedded_texts(snapshot.data)
        lock_path = _absolute_path(
            model_lock_path or DEFAULT_MODEL_LOCK_PATH
        )
        runtime_lock_path = _absolute_path(
            uv_lock_path or DEFAULT_UV_LOCK_PATH
        )
        resolved_model_home = _model_home(model_home)
        try:
            runtime = collect_runtime_info(runtime_lock_path)
            locked_artifacts = load_model_lock(
                lock_path,
                resolved_model_home,
                runtime.package_versions,
            )
        except Exception as error:
            raise PdfOcrError(
                f"runtime or model lock validation failed: {error}"
            ) from error

        if structure_runner is None:
            try:
                structure_runner = DoclingRunner(
                    layout_converter=create_layout_converter(
                        locked_artifacts
                    ),
                    table_converter=create_table_converter(
                        locked_artifacts
                    ),
                )
            except Exception as error:
                raise PdfOcrError(
                    f"Docling structure runner creation failed: {error}"
                ) from error
        pages = _process_pages(
            input_bytes=snapshot.data,
            embedded_texts=embedded_texts,
            staging_dir=staging,
            ocr_runner=ocr_runner,
            structure_runner=structure_runner,
            locked_artifacts=locked_artifacts,
        )
        _require_input_unchanged(input_file, snapshot)
        completed_at = _timestamp()
        manifest = _manifest(
            input_path=input_file,
            input_hash=snapshot.sha256,
            input_size=snapshot.size,
            page_count=len(embedded_texts),
            runtime=runtime,
            locked_artifacts=locked_artifacts,
            pages=pages,
            started_at=started_at,
            completed_at=completed_at,
        )

        _require_owned_staging(
            staging,
            staging_guard,
            parent_guard,
            owner_token,
        )
        _reject_unreferenced_staging_files(
            staging,
            manifest,
            include_owner=True,
            include_manifest=False,
        )
        file_identities = _capture_staging_file_identities(staging)
        validate_publication_bundle(
            manifest,
            staging,
            runtime,
            locked_artifacts,
        )
        _require_input_unchanged(input_file, snapshot)
        _revalidate_staging_file_identities(staging, file_identities)
        _reject_unreferenced_staging_files(
            staging,
            manifest,
            include_owner=True,
            include_manifest=False,
        )
        manifest_path = staging / MANIFEST_FILE_NAME
        manifest_bytes, manifest_identity = _write_manifest_exclusive(
            manifest_path,
            manifest,
        )
        file_identities[MANIFEST_FILE_NAME] = manifest_identity
        _verify_disk_manifest(
            manifest_path,
            manifest_bytes,
            manifest,
            manifest_identity,
        )
        validate_publication_bundle(
            manifest,
            staging,
            runtime,
            locked_artifacts,
        )
        _verify_disk_manifest(
            manifest_path,
            manifest_bytes,
            manifest,
            manifest_identity,
        )
        _require_input_unchanged(input_file, snapshot)
        _revalidate_staging_file_identities(staging, file_identities)
        _require_owned_staging(
            staging,
            staging_guard,
            parent_guard,
            owner_token,
        )
        _reject_unreferenced_staging_files(
            staging,
            manifest,
            include_owner=True,
            include_manifest=True,
        )
        if _path_exists_even_if_broken(output):
            raise OutputExistsError(
                f"output appeared during processing: {output}"
            )

        marker = staging / STAGING_OWNER_MARKER
        _require_regular_file_identity(
            marker,
            file_identities[STAGING_OWNER_MARKER],
        )
        marker.unlink()
        del file_identities[STAGING_OWNER_MARKER]
        try:
            _require_guard_path_identity(staging_guard, "staging")
            _require_guard_path_identity(parent_guard, "output parent")
            _reject_unreferenced_staging_files(
                staging,
                manifest,
                include_owner=False,
                include_manifest=True,
            )
            _revalidate_staging_file_identities(staging, file_identities)
            final_read_guards = _open_windows_final_read_guards(
                staging,
                manifest,
                manifest_bytes,
            )
            try:
                _atomic_publish_no_replace(
                    staging,
                    output,
                    staging_guard=staging_guard,
                    parent_guard=parent_guard,
                    final_read_guards=final_read_guards,
                )
            finally:
                _close_final_read_guards(final_read_guards)
        except BaseException:
            _restore_owner_marker(
                staging,
                staging_guard,
                parent_guard,
                owner_token,
            )
            raise
        return output / MANIFEST_FILE_NAME
    except BaseException as error:
        if (
            staging is not None
            and staging_guard is not None
            and owner_token is not None
            and parent_guard is not None
        ):
            _cleanup_owned_staging(
                staging,
                staging_guard,
                parent_guard,
                owner_token,
            )
        if isinstance(error, PdfOcrError):
            raise
        if isinstance(error, Exception):
            raise PdfOcrError(f"PDF recognition failed: {error}") from error
        raise
    finally:
        if staging_guard is not None:
            staging_guard.close()
        if parent_guard is not None:
            parent_guard.close()


def _validated_input_path(input_path: Path, output_dir: Path) -> Path:
    output_candidate = _absolute_path(output_dir)
    if _path_exists_even_if_broken(output_candidate):
        raise OutputExistsError(f"output already exists: {output_candidate}")
    candidate = Path(input_path)
    if candidate.suffix.lower() != ".pdf":
        raise PdfOcrError(f"input must have a .pdf extension: {candidate}")
    try:
        resolved = candidate.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise PdfOcrError(f"input PDF does not exist: {candidate}") from error
    if not resolved.is_file():
        raise PdfOcrError(f"input PDF is not a fixed regular file: {resolved}")
    return resolved


def _prepare_output_path(output_dir: Path) -> Path:
    candidate = _absolute_path(output_dir)
    if _path_exists_even_if_broken(candidate):
        raise OutputExistsError(f"output already exists: {candidate}")
    try:
        candidate.parent.mkdir(parents=True, exist_ok=True)
        parent = candidate.parent.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise PdfOcrError(f"output parent cannot be created: {candidate.parent}") from error
    output = parent / candidate.name
    if _path_exists_even_if_broken(output):
        raise OutputExistsError(f"output already exists: {output}")
    if _is_link_or_reparse(parent) or not parent.is_dir():
        raise PdfOcrError("output parent must be a real directory")
    return output


def _read_embedded_texts(input_bytes: bytes) -> list[str]:
    try:
        reader = PdfReader(BytesIO(input_bytes), strict=True)
        if reader.is_encrypted:
            raise PdfOcrError("encrypted PDFs are not accepted")
        result = [page.extract_text() or "" for page in reader.pages]
    except PdfOcrError:
        raise
    except (PdfReadError, OSError, ValueError) as error:
        raise PdfOcrError("invalid or unreadable PDF snapshot") from error
    except Exception as error:
        raise PdfOcrError("invalid or unreadable PDF snapshot") from error
    if not result:
        raise PdfOcrError("PDF must contain at least one page")
    return result


def _snapshot_input(
    input_path: Path,
) -> _InputSnapshot:
    if os.name == "nt":
        return _snapshot_windows_input(input_path)
    try:
        with input_path.open("rb") as source:
            source_before = os.fstat(source.fileno())
            path_before = input_path.stat(follow_symlinks=False)
            if (
                not stat.S_ISREG(source_before.st_mode)
                or not stat.S_ISREG(path_before.st_mode)
                or (source_before.st_dev, source_before.st_ino)
                != (path_before.st_dev, path_before.st_ino)
            ):
                raise PdfOcrError(
                    "input path is not bound to the opened regular file"
                )
            data = source.read()
            source_after = os.fstat(source.fileno())
            path_after = input_path.stat(follow_symlinks=False)
        stable_fields_before = (
            source_before.st_dev,
            source_before.st_ino,
            source_before.st_size,
            source_before.st_mtime_ns,
            source_before.st_ctime_ns,
        )
        stable_fields_after = (
            source_after.st_dev,
            source_after.st_ino,
            source_after.st_size,
            source_after.st_mtime_ns,
            source_after.st_ctime_ns,
        )
        if (
            stable_fields_before != stable_fields_after
            or len(data) != source_before.st_size
            or (path_after.st_dev, path_after.st_ino)
            != (source_after.st_dev, source_after.st_ino)
        ):
            raise PdfOcrError("input PDF changed while snapshotting")
        return _InputSnapshot(
            data=data,
            sha256=hashlib.sha256(data).hexdigest(),
            size=len(data),
            source_identity=_PathIdentity(
                source_before.st_dev,
                source_before.st_ino,
            ),
        )
    except PdfOcrError:
        raise
    except OSError as error:
        raise PdfOcrError(
            f"input PDF snapshot failed: {error}"
        ) from error


def _process_pages(
    *,
    input_bytes: bytes,
    embedded_texts: Sequence[str],
    staging_dir: Path,
    ocr_runner: OcrRunner | None,
    structure_runner: StructureRunner,
    locked_artifacts: Sequence[LockedArtifact],
) -> list[dict[str, Any]]:
    pages_dir = staging_dir / "pages"
    pages_dir.mkdir()
    rendered_pages: list[_RenderedPage] = []
    runner = ocr_runner
    try:
        document = _open_fitz_snapshot(input_bytes)
    except (fitz.FileDataError, RuntimeError) as error:
        raise PdfOcrError("invalid or unreadable PDF snapshot") from error

    try:
        if document.page_count != len(embedded_texts):
            raise PdfOcrError("PDF readers disagree on page count")

        for page_index in range(document.page_count):
            page_number = page_index + 1
            page = document.load_page(page_index)
            image_path = pages_dir / f"{page_number:04d}.png"
            try:
                pixmap = page.get_pixmap(dpi=RENDER_DPI, alpha=False)
                png = pixmap.tobytes("png")
                with image_path.open("xb") as output:
                    output.write(png)
                image_width, image_height = validate_png_file(image_path)
            except Exception as error:
                raise PdfOcrError(
                    f"page {page_number} PNG rendering failed: {error}"
                ) from error
            try:
                layout = structure_runner.detect_layout(
                    image_path,
                    page_number=page_number,
                )
                _validate_layout(
                    layout,
                    page_number=page_number,
                    width=image_width,
                    height=image_height,
                )
            except PdfOcrError:
                raise
            except Exception as error:
                raise PdfOcrError(
                    f"layout failed on page {page_number}: {error}"
                ) from error
            rendered_pages.append(
                _RenderedPage(
                    page_number=page_number,
                    image_path=image_path,
                    embedded_text=embedded_texts[page_index],
                    layout=layout,
                )
            )

        manifest_pages: list[dict[str, Any]] = []
        for rendered in rendered_pages:
            page_number = rendered.page_number
            route = select_page_route(
                rendered.embedded_text,
                has_table=rendered.layout.has_table,
                has_complex_layout=rendered.layout.has_complex_layout,
            )
            try:
                if route is PageRoute.EMBEDDED_TEXT:
                    ocr_page = embedded_text_page(
                        document.load_page(page_number - 1),
                        rendered.embedded_text,
                        page_number,
                    )
                    structure_page = structure_from_layout(rendered.layout)
                else:
                    if runner is None:
                        runner = create_rapidocr_runner(locked_artifacts)
                    ocr_page = runner.recognize(
                        rendered.image_path,
                        page_number=page_number,
                    )
                    _validate_ocr_page_binding(ocr_page, page_number)
                    if route is PageRoute.RAPIDOCR_TABLEFORMER:
                        structure_page = structure_runner.recognize_tables(
                            rendered.image_path,
                            page_number=page_number,
                        )
                        _validate_structure_page_binding(
                            structure_page,
                            rendered.layout,
                            page_number,
                        )
                        structure_page = compare_table_cells(
                            ocr_page,
                            structure_page,
                        )
                    else:
                        structure_page = structure_from_layout(rendered.layout)
                _validate_ocr_page_binding(ocr_page, page_number)
                _validate_structure_page_binding(
                    structure_page,
                    rendered.layout,
                    page_number,
                )
                artifact_set = write_page_artifacts(
                    staging_dir,
                    rendered.image_path,
                    route,
                    ocr_page,
                    structure_page,
                )
            except PdfOcrError:
                raise
            except Exception as error:
                raise PdfOcrError(
                    f"page {page_number} recognition or artifact failure: {error}"
                ) from error
            manifest_pages.append(
                _manifest_page(
                    page_number=page_number,
                    route=route,
                    embedded_text=rendered.embedded_text,
                    ocr_page=ocr_page,
                    structure_page=structure_page,
                    artifacts=artifact_set,
                )
            )
        return manifest_pages
    finally:
        document.close()


def _open_fitz_snapshot(input_bytes: bytes) -> fitz.Document:
    return fitz.open(stream=input_bytes, filetype="pdf")


def _validate_layout(
    layout: Any,
    *,
    page_number: int,
    width: int,
    height: int,
) -> None:
    if not isinstance(layout, LayoutPage):
        raise PdfOcrError("layout result is missing or partial")
    if layout.page_number != page_number:
        raise PdfOcrError("layout page number does not match request")
    if layout.width != width or layout.height != height:
        raise PdfOcrError("layout coordinate space does not match rendered PNG")
    if type(layout.has_table) is not bool or type(layout.has_complex_layout) is not bool:
        raise PdfOcrError("layout route flags must be booleans")
    expected_table = any(region.label == "table" for region in layout.regions)
    if layout.has_table is not expected_table:
        raise PdfOcrError(
            "layout has_table flag does not match normalized regions"
        )
    expected_complex = calculate_complex_layout(layout.regions, layout.width)
    if layout.has_complex_layout is not expected_complex:
        raise PdfOcrError(
            "layout has_complex_layout flag does not match normalized regions"
        )


def _validate_ocr_page_binding(page: Any, page_number: int) -> None:
    if not isinstance(page, OcrPage):
        raise PdfOcrError("OCR result is missing or partial")
    if page.page_number != page_number:
        raise PdfOcrError("OCR page number does not match request")
    for token in page.tokens:
        if token.source_page_number != page_number:
            raise PdfOcrError("OCR token page number does not match request")


def _validate_structure_page_binding(
    page: Any,
    layout: LayoutPage,
    page_number: int,
) -> None:
    if not isinstance(page, StructurePage):
        raise PdfOcrError("structure result is missing or partial")
    if page.page_number != page_number:
        raise PdfOcrError("structure page number does not match request")
    if page.width != layout.width or page.height != layout.height:
        raise PdfOcrError(
            "structure coordinate space does not match rendered PNG"
        )


def _manifest_page(
    *,
    page_number: int,
    route: PageRoute,
    embedded_text: str,
    ocr_page: OcrPage,
    structure_page: StructurePage,
    artifacts: PageArtifactSet,
) -> dict[str, Any]:
    reasons = set(MANDATORY_REVIEW_REASONS)
    minimum_confidence = (
        min(token.recognition_confidence for token in ocr_page.tokens)
        if ocr_page.tokens
        else None
    )
    if minimum_confidence is not None and minimum_confidence < 0.90:
        reasons.add("LOW_CONFIDENCE")
    if any_cell_status(structure_page, "MISMATCH"):
        reasons.add("OCR_TABLE_MISMATCH")
    if has_merged_or_multilevel_header(structure_page):
        reasons.add("MERGED_OR_MULTILEVEL_HEADER")
    if has_possible_cross_page_table(structure_page):
        reasons.add("POSSIBLE_CROSS_PAGE_TABLE")
    non_whitespace, invalid_ratio = embedded_text_quality(embedded_text)
    return {
        "page_number": page_number,
        "route": route.value,
        "image": artifacts.image,
        "embedded_text_quality": {
            "non_whitespace_chars": non_whitespace,
            "invalid_character_ratio": invalid_ratio,
        },
        "outputs": [
            artifacts.ocr,
            artifacts.structure,
            artifacts.markdown,
            *artifacts.tables,
        ],
        "review": {
            "status": "PENDING_HUMAN_REVIEW",
            "reasons": sorted(reasons),
        },
        "warnings": [],
    }


def _manifest(
    *,
    input_path: Path,
    input_hash: str,
    input_size: int,
    page_count: int,
    runtime: RuntimeInfo,
    locked_artifacts: Sequence[LockedArtifact],
    pages: list[dict[str, Any]],
    started_at: str,
    completed_at: str,
) -> dict[str, Any]:
    versions = runtime.package_versions
    return {
        "schema_version": "2.0.0",
        "status": "SUCCEEDED",
        "started_at": started_at,
        "completed_at": completed_at,
        "input": {
            "file_name": input_path.name,
            "mime_type": "application/pdf",
            "bytes": input_size,
            "sha256": f"sha256:{input_hash}",
            "page_count": page_count,
        },
        "runtime": {
            "python_version": platform.python_version(),
            "rapidocr_version": versions["rapidocr"],
            "onnxruntime_version": versions["onnxruntime"],
            "execution_provider": runtime.execution_provider,
            "docling_version": versions["docling"],
            "docling_ibm_models_version": versions["docling-ibm-models"],
            "table_mode": "accurate",
            "render_dpi": RENDER_DPI,
            "raw_ocr_threshold": 0.0,
            "human_review_threshold": 0.9,
            "model_files": _model_file_projection(locked_artifacts),
        },
        "pages": pages,
        "retention": {
            "status": "TEMPORARY_NOT_RETAINED",
            "source_rights_status": "PENDING_REVIEW",
        },
        "warnings": [WARNING],
    }


def _model_file_projection(
    artifacts: Sequence[LockedArtifact],
) -> list[dict[str, Any]]:
    return [
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


def _load_recovery_handshake(
    output: Path,
) -> _RecoveryHandshake | None:
    values = {
        RECOVERY_TOKEN_ENV: os.environ.get(RECOVERY_TOKEN_ENV),
        STAGING_NONCE_ENV: os.environ.get(STAGING_NONCE_ENV),
        STAGING_PATH_ENV: os.environ.get(STAGING_PATH_ENV),
        RECOVERY_RECEIPT_ENV: os.environ.get(RECOVERY_RECEIPT_ENV),
    }
    if all(value is None for value in values.values()):
        return None
    if any(value is None or value == "" for value in values.values()):
        raise PdfOcrError("recovery handshake environment is incomplete")

    token = values[RECOVERY_TOKEN_ENV]
    nonce = values[STAGING_NONCE_ENV]
    staging_value = values[STAGING_PATH_ENV]
    receipt_value = values[RECOVERY_RECEIPT_ENV]
    assert token is not None
    assert nonce is not None
    assert staging_value is not None
    assert receipt_value is not None
    if re.fullmatch(r"[0-9a-f]{64}", token) is None:
        raise PdfOcrError("recovery token must be 64 lowercase hex characters")
    if re.fullmatch(r"[0-9a-f]{32}", nonce) is None:
        raise PdfOcrError("staging nonce must be 32 lowercase hex characters")

    expected_staging = output.parent / f".{output.name}.tmp-{nonce}"
    expected_receipt = output.parent / f".{output.name}.recovery-{nonce}"
    supplied_staging = Path(staging_value)
    supplied_receipt = Path(receipt_value)
    if not supplied_staging.is_absolute() or not supplied_receipt.is_absolute():
        raise PdfOcrError("recovery handshake paths must be absolute")
    try:
        staging_path = supplied_staging.resolve(strict=False)
        receipt_path = supplied_receipt.resolve(strict=True)
    except (OSError, RuntimeError) as error:
        raise PdfOcrError("recovery handshake paths cannot be resolved") from error
    if staging_path != expected_staging or receipt_path != expected_receipt:
        raise PdfOcrError(
            "recovery handshake paths must be exact direct children "
            "of the output parent"
        )

    recovery = _RecoveryHandshake(
        token=token,
        nonce=nonce,
        staging_path=staging_path,
        receipt_path=receipt_path,
    )
    _require_recovery_receipt(recovery)
    return recovery


def _require_recovery_receipt(recovery: _RecoveryHandshake) -> None:
    try:
        identity = _regular_file_identity(recovery.receipt_path)
        actual = recovery.receipt_path.read_text(encoding="utf-8")
        _require_regular_file_identity(recovery.receipt_path, identity)
    except (OSError, UnicodeError) as error:
        raise PdfOcrError("recovery receipt is unreadable") from error
    if actual != recovery.token:
        raise PdfOcrError("recovery receipt token does not match exactly")


def _create_private_staging(
    output: Path,
    parent_guard: _DirectoryGuard,
) -> tuple[Path, _DirectoryGuard, str]:
    _require_guard_path_identity(parent_guard, "output parent")
    recovery = _load_recovery_handshake(output)
    staging: Path | None = None
    staging_guard: _DirectoryGuard | None = None
    fallback_identity: _PathIdentity | None = None
    owner_token = recovery.token if recovery is not None else uuid.uuid4().hex
    try:
        if os.name == "nt":
            if recovery is not None:
                if _windows_create_restricted_directory(
                    recovery.staging_path
                ):
                    staging = recovery.staging_path
            else:
                prefix = f".{output.name}.tmp-"
                for _ in range(32):
                    candidate = output.parent / f"{prefix}{uuid.uuid4().hex}"
                    if _windows_create_restricted_directory(candidate):
                        staging = candidate
                        break
            if staging is None:
                raise PdfOcrError(
                    "private staging name allocation was exhausted"
                )
            fallback_identity = _path_identity(staging)
            staging_guard = _open_directory_guard(
                staging,
                rename_source=True,
            )
            fallback_identity = staging_guard.identity
            _require_bound_windows_directory_dacl(
                staging_guard,
                "private staging",
            )
        else:
            staging, fallback_identity = _create_posix_private_staging(
                output,
                exact_path=(
                    recovery.staging_path
                    if recovery is not None
                    else None
                ),
            )
        if staging_guard is None:
            staging_guard = _open_directory_guard(
                staging,
                rename_source=True,
            )
        _require_guard_path_identity(parent_guard, "output parent")
        _write_owner_marker_exclusive(
            staging / STAGING_OWNER_MARKER,
            owner_token,
        )
        if recovery is not None:
            _require_recovery_receipt(recovery)
        return staging, staging_guard, owner_token
    except BaseException as error:
        if staging is not None:
            _cleanup_initializing_staging(
                staging,
                staging_guard,
                fallback_identity,
            )
        if staging_guard is not None:
            staging_guard.close()
        if isinstance(error, Exception):
            if isinstance(error, PdfOcrError):
                raise
            raise PdfOcrError(
                f"private staging creation failed: {error}"
            ) from error
        raise


def _create_posix_private_staging(
    output: Path,
    *,
    exact_path: Path | None = None,
) -> tuple[Path, _PathIdentity]:
    if exact_path is None:
        staging = Path(
            tempfile.mkdtemp(
                prefix=f".{output.name}.tmp-",
                dir=output.parent,
            )
        )
    else:
        staging = exact_path
        try:
            os.mkdir(staging, mode=stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR)
        except OSError as error:
            raise PdfOcrError(
                f"exact private staging cannot be created: {staging}"
            ) from error
    identity = _path_identity(staging)
    try:
        os.chmod(
            staging,
            stat.S_IRUSR | stat.S_IWUSR | stat.S_IXUSR,
        )
        return staging, identity
    except BaseException as error:
        try:
            _require_directory_identity(
                staging,
                identity,
                "initializing POSIX staging",
            )
            _remove_owned_tree_no_follow(staging)
        except Exception:
            pass
        if isinstance(error, Exception):
            raise PdfOcrError(
                f"private staging permission setup failed: {error}"
            ) from error
        raise


def _write_owner_marker_exclusive(path: Path, owner_token: str) -> None:
    with path.open("x", encoding="utf-8", newline="\n") as output_file:
        output_file.write(owner_token)
        output_file.flush()
        os.fsync(output_file.fileno())


def _cleanup_initializing_staging(
    staging: Path,
    guard: _DirectoryGuard | None,
    fallback_identity: _PathIdentity | None,
) -> None:
    try:
        if guard is not None:
            _require_guard_path_identity(guard, "initializing staging")
            guard.close()
            _require_directory_identity(
                staging,
                guard.identity,
                "initializing staging",
            )
        elif fallback_identity is not None:
            _require_directory_identity(
                staging,
                fallback_identity,
                "initializing staging",
            )
        else:
            return
        _remove_owned_tree_no_follow(staging)
    except Exception:
        return


def _require_owned_staging(
    staging: Path,
    staging_guard: _DirectoryGuard,
    parent_guard: _DirectoryGuard,
    owner_token: str,
) -> None:
    _require_guard_path_identity(parent_guard, "output parent")
    _require_guard_path_identity(staging_guard, "staging")
    if os.name == "nt":
        _require_bound_windows_directory_dacl(
            staging_guard,
            "staging",
        )
    marker = staging / STAGING_OWNER_MARKER
    if _is_link_or_reparse(marker) or not marker.is_file():
        raise PdfOcrError("staging ownership marker is missing or linked")
    try:
        actual = marker.read_text(encoding="utf-8")
    except OSError as error:
        raise PdfOcrError("staging ownership marker is unreadable") from error
    if actual != owner_token:
        raise PdfOcrError("staging ownership changed during processing")


def _restore_owner_marker(
    staging: Path,
    staging_guard: _DirectoryGuard,
    parent_guard: _DirectoryGuard,
    owner_token: str,
) -> None:
    try:
        _require_guard_path_identity(parent_guard, "output parent")
        _require_guard_path_identity(staging_guard, "staging")
        marker = staging / STAGING_OWNER_MARKER
        if _path_exists_even_if_broken(marker):
            return
        _write_owner_marker_exclusive(marker, owner_token)
    except Exception:
        return


def _cleanup_owned_staging(
    staging: Path,
    staging_guard: _DirectoryGuard,
    parent_guard: _DirectoryGuard,
    owner_token: str,
) -> None:
    try:
        _require_owned_staging(
            staging,
            staging_guard,
            parent_guard,
            owner_token,
        )
        staging_guard.close()
        _require_directory_identity(
            staging,
            staging_guard.identity,
            "owned staging cleanup",
        )
        _remove_owned_tree_no_follow(staging)
    except Exception:
        return


def _remove_owned_tree_no_follow(root: Path) -> None:
    if os.name == "nt":
        try:
            shutil.rmtree(root)
        except OSError:
            pass
        return
    try:
        entries = list(os.scandir(root))
    except OSError:
        return
    for entry in entries:
        path = Path(entry.path)
        try:
            if _is_link_or_reparse(path):
                is_junction = getattr(path, "is_junction", None)
                if callable(is_junction) and is_junction():
                    os.rmdir(path)
                else:
                    path.unlink()
            elif entry.is_dir(follow_symlinks=False):
                _remove_owned_tree_no_follow(path)
            else:
                path.unlink()
        except OSError:
            continue
    try:
        os.rmdir(root)
    except OSError:
        return


def _reject_unreferenced_staging_files(
    staging: Path,
    manifest: Mapping[str, Any],
    *,
    include_owner: bool,
    include_manifest: bool,
) -> None:
    expected_files = {
        record["file_name"]
        for page in manifest["pages"]
        for record in (page["image"], *page["outputs"])
    }
    if include_owner:
        expected_files.add(STAGING_OWNER_MARKER)
    if include_manifest:
        expected_files.add(MANIFEST_FILE_NAME)
    expected_directories = {
        parent.as_posix()
        for value in expected_files
        for parent in Path(value).parents
        if parent != Path(".")
    }
    actual_files: set[str] = set()
    actual_directories: set[str] = set()
    for root, directories, files in os.walk(staging, followlinks=False):
        root_path = Path(root)
        for directory in directories:
            path = root_path / directory
            if _is_link_or_reparse(path):
                raise PdfOcrError(
                    "staging contains a linked or reparse directory"
                )
            actual_directories.add(path.relative_to(staging).as_posix())
        for file_name in files:
            path = root_path / file_name
            if _is_link_or_reparse(path) or not path.is_file():
                raise PdfOcrError("staging contains a linked or irregular file")
            actual_files.add(path.relative_to(staging).as_posix())
    if actual_files != expected_files or actual_directories != expected_directories:
        raise PdfOcrError("staging contains unreferenced or missing artifacts")


def _write_manifest_exclusive(
    path: Path,
    manifest: Mapping[str, Any],
) -> tuple[bytes, _FileIdentity]:
    try:
        data = (
            json.dumps(
                manifest,
                ensure_ascii=False,
                indent=2,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
        with path.open("xb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        return data, _regular_file_identity(path)
    except Exception as error:
        raise PdfOcrError(f"manifest exclusive write failed: {error}") from error


def _verify_disk_manifest(
    path: Path,
    expected_bytes: bytes,
    expected_payload: Mapping[str, Any],
    expected_identity: _FileIdentity,
) -> None:
    _require_regular_file_identity(path, expected_identity)
    try:
        actual_bytes = path.read_bytes()
        actual_payload = strict_json_loads(
            actual_bytes,
            description="published manifest",
        )
    except Exception as error:
        raise PdfOcrError(f"disk manifest verification failed: {error}") from error
    if actual_bytes != expected_bytes or actual_payload != expected_payload:
        raise PdfOcrError(
            "disk manifest differs from the validated in-memory payload"
        )


def _capture_staging_file_identities(
    staging: Path,
) -> dict[str, _FileIdentity]:
    result: dict[str, _FileIdentity] = {}
    for root, directories, files in os.walk(staging, followlinks=False):
        root_path = Path(root)
        for directory in directories:
            path = root_path / directory
            if _is_link_or_reparse(path):
                raise PdfOcrError(
                    "staging contains a linked or reparse directory"
                )
        for file_name in files:
            path = root_path / file_name
            relative = path.relative_to(staging).as_posix()
            result[relative] = _regular_file_identity(path)
    return result


def _revalidate_staging_file_identities(
    staging: Path,
    expected: Mapping[str, _FileIdentity],
) -> None:
    actual = _capture_staging_file_identities(staging)
    if actual != dict(expected):
        raise PdfOcrError(
            "staging file identity, metadata, or link count changed"
        )


def _regular_file_identity(path: Path) -> _FileIdentity:
    try:
        metadata = path.stat(follow_symlinks=False)
    except OSError as error:
        raise PdfOcrError(f"regular file identity cannot be read: {path}") from error
    if (
        _is_link_or_reparse(path)
        or not stat.S_ISREG(metadata.st_mode)
        or metadata.st_nlink != 1
    ):
        raise PdfOcrError(
            f"staging regular file is linked, missing, or irregular: {path}"
        )
    return _FileIdentity(
        device=metadata.st_dev,
        inode=metadata.st_ino,
        size=metadata.st_size,
        modified_ns=metadata.st_mtime_ns,
        changed_ns=metadata.st_ctime_ns,
    )


def _require_regular_file_identity(
    path: Path,
    expected: _FileIdentity,
) -> None:
    if _regular_file_identity(path) != expected:
        raise PdfOcrError(f"regular file identity changed: {path}")


def _open_windows_final_read_guards(
    staging: Path,
    manifest: Mapping[str, Any],
    manifest_bytes: bytes,
) -> list[_FinalReadGuard]:
    if os.name != "nt":
        return []
    records = [
        record
        for page in manifest["pages"]
        for record in (page["image"], *page["outputs"])
    ]
    specifications: list[tuple[str, int, str, bytes | None]] = [
        (
            str(record["file_name"]),
            int(record["bytes"]),
            str(record["sha256"]).removeprefix("sha256:"),
            None,
        )
        for record in records
    ]
    specifications.append(
        (
            MANIFEST_FILE_NAME,
            len(manifest_bytes),
            hashlib.sha256(manifest_bytes).hexdigest(),
            manifest_bytes,
        )
    )
    guards: list[_FinalReadGuard] = []
    try:
        for relative_name, size, digest, exact_bytes in specifications:
            path = staging / Path(relative_name)
            handle = _windows_open_regular_file_handle(
                path,
                desired_access=0x80000000,
                share_mode=0x00000001,
                sequential=True,
            )
            guard = _FinalReadGuard(
                path=path,
                relative_name=relative_name,
                expected_size=size,
                expected_sha256=digest,
                initial_state=_windows_handle_file_state(handle),
                handle=handle,
                expected_exact_bytes=exact_bytes,
            )
            guards.append(guard)
            _verify_windows_final_read_guard(guard)
        return guards
    except BaseException:
        _close_final_read_guards(guards)
        raise


def _verify_windows_final_read_guard(
    guard: _FinalReadGuard,
) -> None:
    if guard.handle is None:
        raise PdfOcrError(
            f"final artifact read guard is closed: {guard.relative_name}"
        )
    before = _windows_require_path_matches_file_handle(
        guard.path,
        guard.handle,
    )
    if (
        before != guard.initial_state
        or before[2] & 0x00000400
        or before[2] & 0x00000010
        or before[4] != 1
    ):
        raise PdfOcrError(
            f"final artifact handle identity is invalid: {guard.relative_name}"
        )
    actual = _windows_read_handle_bytes(guard.handle)
    after = _windows_require_path_matches_file_handle(
        guard.path,
        guard.handle,
    )
    if before != after:
        raise PdfOcrError(
            f"final artifact changed while reading: {guard.relative_name}"
        )
    if (
        len(actual) != guard.expected_size
        or hashlib.sha256(actual).hexdigest()
        != guard.expected_sha256
    ):
        raise PdfOcrError(
            f"final artifact bytes differ from manifest: {guard.relative_name}"
        )
    if (
        guard.expected_exact_bytes is not None
        and actual != guard.expected_exact_bytes
    ):
        raise PdfOcrError(
            "final manifest bytes differ from the validated payload"
        )


def _close_final_read_guards(
    guards: Sequence[_FinalReadGuard],
) -> None:
    for guard in guards:
        guard.close()


def _atomic_publish_no_replace(
    staging: Path,
    output: Path,
    *,
    staging_guard: _DirectoryGuard,
    parent_guard: _DirectoryGuard,
    final_read_guards: Sequence[_FinalReadGuard] = (),
) -> None:
    if _path_exists_even_if_broken(output):
        raise OutputExistsError(f"output appeared during processing: {output}")
    if os.name == "nt":
        for guard in final_read_guards:
            _verify_windows_final_read_guard(guard)
        _close_final_read_guards(final_read_guards)
        _windows_rename_directory_handle_no_replace(
            staging_guard,
            parent_guard,
            output.name,
            output,
        )
        expected_identity = staging_guard.identity
        staging_guard.path = output
        try:
            _require_guard_path_identity(
                staging_guard,
                "published output",
            )
            _require_bound_windows_directory_dacl(
                staging_guard,
                "published output",
            )
        except BaseException:
            staging_guard.close()
            _close_final_read_guards(final_read_guards)
            _cleanup_published_after_failed_verification(
                output,
                expected_identity,
            )
            raise
        staging_guard.close()
        return
    if sys.platform.startswith("linux"):
        _linux_rename_no_replace(staging, output)
        return
    raise PdfOcrError(
        "atomic no-replace directory publication is unsupported on this platform"
    )


def _cleanup_published_after_failed_verification(
    output: Path,
    expected_identity: _PathIdentity,
) -> None:
    try:
        _require_directory_identity(
            output,
            expected_identity,
            "failed published output",
        )
        _remove_owned_tree_no_follow(output)
    except Exception:
        return


def _linux_rename_no_replace(staging: Path, output: Path) -> None:
    rename_no_replace = 1
    at_fdcwd = -100
    libc = ctypes.CDLL(None, use_errno=True)
    renameat2 = getattr(libc, "renameat2", None)
    if renameat2 is None:
        raise PdfOcrError("renameat2 is required for no-replace publication")
    renameat2.argtypes = [
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_int,
        ctypes.c_char_p,
        ctypes.c_uint,
    ]
    renameat2.restype = ctypes.c_int
    result = renameat2(
        at_fdcwd,
        os.fsencode(staging),
        at_fdcwd,
        os.fsencode(output),
        rename_no_replace,
    )
    if result == 0:
        return
    error_number = ctypes.get_errno()
    if error_number in {errno.EEXIST, errno.ENOTEMPTY}:
        raise OutputExistsError(f"output appeared during processing: {output}")
    raise PdfOcrError(
        f"atomic output publish failed: {os.strerror(error_number)}"
    )


def _require_input_unchanged(
    input_path: Path,
    snapshot: _InputSnapshot,
) -> None:
    try:
        metadata = input_path.stat(follow_symlinks=False)
        current_size = metadata.st_size
        current_hash = _sha256(input_path)
    except OSError as error:
        raise PdfOcrError("input PDF became unavailable during processing") from error
    if (
        (metadata.st_dev, metadata.st_ino)
        != (snapshot.source_identity.device, snapshot.source_identity.inode)
        or current_size != snapshot.size
        or current_hash != snapshot.sha256
    ):
        raise PdfOcrError("input PDF changed while it was being processed")


def _model_home(explicit: Path | None) -> Path:
    value: Path | str | None = explicit
    if value is None:
        value = os.environ.get("PDF_OCR_MODEL_HOME")
    if value is None or not str(value).strip():
        raise PdfOcrError(
            "model home is required via model_home or PDF_OCR_MODEL_HOME"
        )
    path = _absolute_path(Path(value))
    if not path.is_dir():
        raise PdfOcrError(f"model home does not exist: {path}")
    return path


def _open_directory_guard(
    path: Path,
    *,
    rename_source: bool = False,
    parent_target: bool = False,
) -> _DirectoryGuard:
    identity = _path_identity(path)
    if os.name != "nt":
        return _DirectoryGuard(path=path, identity=identity)
    handle = _windows_open_directory_handle(
        path,
        rename_source=rename_source,
        parent_target=parent_target,
    )
    try:
        volume, file_id, attributes = _windows_handle_identity(handle)
        if attributes & 0x00000400:
            raise PdfOcrError("directory handle names a reparse point")
        if not attributes & 0x00000010:
            raise PdfOcrError("directory handle does not name a directory")
        return _DirectoryGuard(
            path=path,
            identity=identity,
            windows_handle=handle,
            windows_volume=volume,
            windows_file_id=file_id,
        )
    except BaseException:
        _windows_close_handle(handle)
        raise


def _require_guard_path_identity(
    guard: _DirectoryGuard,
    description: str,
) -> None:
    _require_directory_identity(guard.path, guard.identity, description)
    if os.name != "nt":
        return
    if guard.windows_handle is None:
        raise PdfOcrError(f"{description} stable directory handle is closed")
    volume, file_id, attributes = _windows_handle_identity(
        guard.windows_handle
    )
    if (
        attributes & 0x00000400
        or volume != guard.windows_volume
        or file_id != guard.windows_file_id
    ):
        raise PdfOcrError(
            f"{description} stable directory handle identity changed"
        )
    current_handle = _windows_open_directory_handle(
        guard.path,
        verification=True,
    )
    try:
        current_volume, current_file_id, current_attributes = (
            _windows_handle_identity(current_handle)
        )
        if (
            current_attributes & 0x00000400
            or current_volume != guard.windows_volume
            or current_file_id != guard.windows_file_id
        ):
            raise PdfOcrError(
                f"{description} path no longer names the held directory"
            )
    finally:
        _windows_close_handle(current_handle)


def _require_bound_windows_directory_dacl(
    guard: _DirectoryGuard,
    description: str,
) -> None:
    if os.name != "nt":
        return
    _require_guard_path_identity(guard, description)
    if not _windows_directory_dacl_is_restricted(guard.path):
        raise PdfOcrError(
            f"{description} DACL is not protected and restricted"
        )
    _require_guard_path_identity(guard, description)


def _windows_open_directory_handle(
    path: Path,
    *,
    rename_source: bool = False,
    parent_target: bool = False,
    verification: bool = False,
) -> int:
    if os.name != "nt":
        raise PdfOcrError("Windows directory handles are unavailable")
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    desired_access = 0x00000080 | 0x00020000 | 0x00100000
    if rename_source:
        desired_access |= 0x00010000
    if parent_target:
        desired_access |= 0x00000001 | 0x00000002 | 0x00000004
    handle = create_file(
        str(path),
        desired_access,
        (
            0x00000001
            | 0x00000002
            | (0x00000004 if verification else 0)
        ),
        None,
        3,
        0x02000000 | 0x00200000,
        None,
    )
    handle_value = (
        handle
        if isinstance(handle, int)
        else ctypes.cast(handle, ctypes.c_void_p).value
    )
    if handle_value == ctypes.c_void_p(-1).value:
        raise PdfOcrError(
            f"Windows directory handle open failed: {ctypes.WinError(ctypes.get_last_error())}"
        )
    if handle_value is None:
        raise PdfOcrError("Windows directory handle open returned null")
    return int(handle_value)


def _windows_close_handle(handle: int) -> None:
    if os.name != "nt":
        return
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    close_handle(wintypes.HANDLE(handle))


def _windows_handle_identity(handle: int) -> tuple[int, int, int]:
    volume, file_id, attributes, _, _ = _windows_handle_file_state(handle)
    return volume, file_id, attributes


def _windows_handle_file_state(
    handle: int,
) -> tuple[int, int, int, int, int]:
    if os.name != "nt":
        raise PdfOcrError("Windows handle identity is unavailable")
    from ctypes import wintypes

    class ByHandleFileInformation(ctypes.Structure):
        _fields_ = [
            ("dwFileAttributes", wintypes.DWORD),
            ("ftCreationTime", wintypes.FILETIME),
            ("ftLastAccessTime", wintypes.FILETIME),
            ("ftLastWriteTime", wintypes.FILETIME),
            ("dwVolumeSerialNumber", wintypes.DWORD),
            ("nFileSizeHigh", wintypes.DWORD),
            ("nFileSizeLow", wintypes.DWORD),
            ("nNumberOfLinks", wintypes.DWORD),
            ("nFileIndexHigh", wintypes.DWORD),
            ("nFileIndexLow", wintypes.DWORD),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    get_information = kernel32.GetFileInformationByHandle
    get_information.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(ByHandleFileInformation),
    ]
    get_information.restype = wintypes.BOOL
    information = ByHandleFileInformation()
    if not get_information(
        wintypes.HANDLE(handle),
        ctypes.byref(information),
    ):
        raise PdfOcrError(
            f"Windows handle identity read failed: {ctypes.WinError(ctypes.get_last_error())}"
        )
    file_id = (
        int(information.nFileIndexHigh) << 32
    ) | int(information.nFileIndexLow)
    file_size = (
        int(information.nFileSizeHigh) << 32
    ) | int(information.nFileSizeLow)
    return (
        int(information.dwVolumeSerialNumber),
        file_id,
        int(information.dwFileAttributes),
        file_size,
        int(information.nNumberOfLinks),
    )


def _windows_open_regular_file_handle(
    path: Path,
    *,
    desired_access: int,
    share_mode: int,
    sequential: bool = False,
) -> int:
    if os.name != "nt":
        raise PdfOcrError("Windows regular-file handles are unavailable")
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    flags = 0x00200000
    if sequential:
        flags |= 0x08000000
    handle = create_file(
        str(path),
        desired_access,
        share_mode,
        None,
        3,
        flags,
        None,
    )
    handle_value = (
        handle
        if isinstance(handle, int)
        else ctypes.cast(handle, ctypes.c_void_p).value
    )
    if handle_value == ctypes.c_void_p(-1).value:
        raise PdfOcrError(
            f"Windows file handle open failed: {ctypes.WinError(ctypes.get_last_error())}"
        )
    if handle_value is None:
        raise PdfOcrError("Windows file handle open returned null")
    return int(handle_value)


def _windows_read_handle_bytes(handle: int) -> bytes:
    if os.name != "nt":
        raise PdfOcrError("Windows handle reads are unavailable")
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    set_pointer = kernel32.SetFilePointerEx
    set_pointer.argtypes = [
        wintypes.HANDLE,
        ctypes.c_longlong,
        ctypes.POINTER(ctypes.c_longlong),
        wintypes.DWORD,
    ]
    set_pointer.restype = wintypes.BOOL
    if not set_pointer(
        wintypes.HANDLE(handle),
        0,
        None,
        0,
    ):
        raise PdfOcrError(
            f"Windows handle rewind failed: {ctypes.WinError(ctypes.get_last_error())}"
        )
    read_file = kernel32.ReadFile
    read_file.argtypes = [
        wintypes.HANDLE,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
        wintypes.LPVOID,
    ]
    read_file.restype = wintypes.BOOL
    chunks: list[bytes] = []
    buffer = ctypes.create_string_buffer(1024 * 1024)
    while True:
        read_count = wintypes.DWORD()
        if not read_file(
            wintypes.HANDLE(handle),
            buffer,
            len(buffer),
            ctypes.byref(read_count),
            None,
        ):
            raise PdfOcrError(
                f"Windows handle read failed: {ctypes.WinError(ctypes.get_last_error())}"
            )
        if read_count.value == 0:
            break
        chunks.append(buffer.raw[: read_count.value])
    return b"".join(chunks)


def _windows_require_path_matches_file_handle(
    path: Path,
    handle: int,
) -> tuple[int, int, int, int, int]:
    held = _windows_handle_file_state(handle)
    verification_handle = _windows_open_regular_file_handle(
        path,
        desired_access=0x00000080,
        share_mode=0x00000001,
    )
    try:
        current = _windows_handle_file_state(verification_handle)
    finally:
        _windows_close_handle(verification_handle)
    if current[:3] != held[:3]:
        raise PdfOcrError("input path no longer names the held source file")
    return held


def _snapshot_windows_input(input_path: Path) -> _InputSnapshot:
    handle = _windows_open_regular_file_handle(
        input_path,
        desired_access=0x80000000,
        share_mode=0x00000001,
        sequential=True,
    )
    try:
        before = _windows_require_path_matches_file_handle(
            input_path,
            handle,
        )
        if before[2] & 0x00000400 or before[2] & 0x00000010:
            raise PdfOcrError(
                "input source handle is a reparse point or directory"
            )
        metadata = input_path.stat(follow_symlinks=False)
        if (
            not stat.S_ISREG(metadata.st_mode)
            or metadata.st_ino != before[1]
        ):
            raise PdfOcrError(
                "input path identity does not match the stable source handle"
            )
        data = _windows_read_handle_bytes(handle)
        after = _windows_require_path_matches_file_handle(
            input_path,
            handle,
        )
        if before != after or len(data) != before[3]:
            raise PdfOcrError("input PDF changed while snapshotting")
        return _InputSnapshot(
            data=data,
            sha256=hashlib.sha256(data).hexdigest(),
            size=len(data),
            source_identity=_PathIdentity(
                metadata.st_dev,
                metadata.st_ino,
            ),
        )
    except PdfOcrError:
        raise
    except (OSError, RuntimeError) as error:
        raise PdfOcrError(
            f"input PDF snapshot failed: {error}"
        ) from error
    finally:
        _windows_close_handle(handle)


def _windows_current_user_sid_string() -> str:
    if os.name != "nt":
        raise PdfOcrError("Windows current-user SID is unavailable")
    from ctypes import wintypes

    class SidAndAttributes(ctypes.Structure):
        _fields_ = [
            ("Sid", wintypes.LPVOID),
            ("Attributes", wintypes.DWORD),
        ]

    class TokenUser(ctypes.Structure):
        _fields_ = [("User", SidAndAttributes)]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    open_token = advapi32.OpenProcessToken
    open_token.argtypes = [
        wintypes.HANDLE,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.HANDLE),
    ]
    open_token.restype = wintypes.BOOL
    get_token_information = advapi32.GetTokenInformation
    get_token_information.argtypes = [
        wintypes.HANDLE,
        ctypes.c_int,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.DWORD),
    ]
    get_token_information.restype = wintypes.BOOL
    convert_sid = advapi32.ConvertSidToStringSidW
    convert_sid.argtypes = [
        wintypes.LPVOID,
        ctypes.POINTER(wintypes.LPWSTR),
    ]
    convert_sid.restype = wintypes.BOOL
    token = wintypes.HANDLE()
    kernel32.GetCurrentProcess.argtypes = []
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    kernel32.LocalFree.argtypes = [wintypes.HANDLE]
    kernel32.LocalFree.restype = wintypes.HANDLE
    if not open_token(
        kernel32.GetCurrentProcess(),
        0x0008,
        ctypes.byref(token),
    ):
        raise PdfOcrError(
            f"current-user token open failed: {ctypes.WinError(ctypes.get_last_error())}"
        )
    try:
        required = wintypes.DWORD()
        get_token_information(
            token,
            1,
            None,
            0,
            ctypes.byref(required),
        )
        if ctypes.get_last_error() != 122 or required.value == 0:
            raise PdfOcrError("current-user token size query failed")
        buffer = ctypes.create_string_buffer(required.value)
        if not get_token_information(
            token,
            1,
            buffer,
            required.value,
            ctypes.byref(required),
        ):
            raise PdfOcrError(
                f"current-user SID query failed: {ctypes.WinError(ctypes.get_last_error())}"
            )
        token_user = ctypes.cast(
            buffer,
            ctypes.POINTER(TokenUser),
        ).contents
        sid_text = wintypes.LPWSTR()
        if not convert_sid(token_user.User.Sid, ctypes.byref(sid_text)):
            raise PdfOcrError(
                f"current-user SID conversion failed: {ctypes.WinError(ctypes.get_last_error())}"
            )
        try:
            return str(sid_text.value)
        finally:
            kernel32.LocalFree(
                ctypes.cast(sid_text, wintypes.HANDLE)
            )
    finally:
        token_value = (
            token.value
            if hasattr(token, "value")
            else ctypes.cast(token, ctypes.c_void_p).value
        )
        if token_value is not None:
            _windows_close_handle(int(token_value))


def _windows_create_restricted_directory(path: Path) -> bool:
    if os.name != "nt":
        raise PdfOcrError("Windows protected directory creation is unavailable")
    from ctypes import wintypes

    class SecurityAttributes(ctypes.Structure):
        _fields_ = [
            ("nLength", wintypes.DWORD),
            ("lpSecurityDescriptor", wintypes.LPVOID),
            ("bInheritHandle", wintypes.BOOL),
        ]

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    convert = advapi32.ConvertStringSecurityDescriptorToSecurityDescriptorW
    convert.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPVOID),
        ctypes.POINTER(wintypes.DWORD),
    ]
    convert.restype = wintypes.BOOL
    create_directory = kernel32.CreateDirectoryW
    create_directory.argtypes = [
        wintypes.LPCWSTR,
        ctypes.POINTER(SecurityAttributes),
    ]
    create_directory.restype = wintypes.BOOL
    kernel32.LocalFree.argtypes = [wintypes.HANDLE]
    kernel32.LocalFree.restype = wintypes.HANDLE
    sid = _windows_current_user_sid_string()
    sddl = f"D:P(A;OICI;FA;;;SY)(A;OICI;FA;;;{sid})"
    security_descriptor = wintypes.LPVOID()
    size = wintypes.DWORD()
    if not convert(
        sddl,
        1,
        ctypes.byref(security_descriptor),
        ctypes.byref(size),
    ):
        raise PdfOcrError(
            f"protected DACL construction failed: {ctypes.WinError(ctypes.get_last_error())}"
        )
    try:
        attributes = SecurityAttributes(
            ctypes.sizeof(SecurityAttributes),
            security_descriptor,
            False,
        )
        if create_directory(str(path), ctypes.byref(attributes)):
            return True
        error_number = ctypes.get_last_error()
        if error_number in {80, 183}:
            return False
        raise PdfOcrError(
            f"protected staging creation failed: {ctypes.WinError(error_number)}"
        )
    finally:
        kernel32.LocalFree(
            ctypes.cast(security_descriptor, wintypes.HANDLE)
        )


def _windows_directory_dacl_is_restricted(path: Path) -> bool:
    if os.name != "nt":
        return False
    try:
        from ctypes import wintypes

        advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
        get_file_security = advapi32.GetFileSecurityW
        get_file_security.argtypes = [
            wintypes.LPCWSTR,
            wintypes.DWORD,
            wintypes.LPVOID,
            wintypes.DWORD,
            ctypes.POINTER(wintypes.DWORD),
        ]
        get_file_security.restype = wintypes.BOOL
        required = wintypes.DWORD()
        get_file_security(
            str(path),
            0x00000004,
            None,
            0,
            ctypes.byref(required),
        )
        if ctypes.get_last_error() != 122 or required.value == 0:
            return False
        descriptor = ctypes.create_string_buffer(required.value)
        if not get_file_security(
            str(path),
            0x00000004,
            descriptor,
            required.value,
            ctypes.byref(required),
        ):
            return False
        return _windows_security_descriptor_dacl_is_restricted(
            descriptor
        )
    except Exception:
        return False


def _windows_security_descriptor_dacl_is_restricted(
    descriptor: Any,
) -> bool:
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    advapi32 = ctypes.WinDLL("advapi32", use_last_error=True)
    get_control = advapi32.GetSecurityDescriptorControl
    get_control.argtypes = [
        wintypes.LPVOID,
        ctypes.POINTER(wintypes.WORD),
        ctypes.POINTER(wintypes.DWORD),
    ]
    get_control.restype = wintypes.BOOL
    control = wintypes.WORD()
    revision = wintypes.DWORD()
    if not get_control(
        descriptor,
        ctypes.byref(control),
        ctypes.byref(revision),
    ):
        return False
    if not control.value & 0x1000:
        return False
    convert = (
        advapi32.ConvertSecurityDescriptorToStringSecurityDescriptorW
    )
    convert.argtypes = [
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(wintypes.DWORD),
    ]
    convert.restype = wintypes.BOOL
    sddl_pointer = wintypes.LPWSTR()
    length = wintypes.DWORD()
    if not convert(
        descriptor,
        1,
        0x00000004,
        ctypes.byref(sddl_pointer),
        ctypes.byref(length),
    ):
        return False
    kernel32.LocalFree.argtypes = [wintypes.HANDLE]
    kernel32.LocalFree.restype = wintypes.HANDLE
    try:
        sddl = str(sddl_pointer.value)
    finally:
        kernel32.LocalFree(
            ctypes.cast(sddl_pointer, wintypes.HANDLE)
        )
    if not sddl.startswith("D:P"):
        return False
    aces = re.findall(r"\(([^()]*)\)", sddl)
    if len(aces) != 2:
        return False
    current_sid = _windows_current_user_sid_string()
    trustees: set[str] = set()
    for ace in aces:
        fields = ace.split(";")
        if len(fields) != 6 or fields[0] != "A":
            return False
        if "OI" not in fields[1] or "CI" not in fields[1]:
            return False
        if fields[2] not in {"FA", "0x1f01ff"}:
            return False
        trustees.add(fields[5])
    return trustees == {"SY", current_sid} or trustees == {
        "S-1-5-18",
        current_sid,
    }


def _windows_rename_directory_handle_no_replace(
    staging_guard: _DirectoryGuard,
    parent_guard: _DirectoryGuard,
    output_name: str,
    output_path: Path,
) -> None:
    if os.name != "nt":
        raise PdfOcrError("Windows handle-bound rename is unavailable")
    if (
        staging_guard.windows_handle is None
        or parent_guard.windows_handle is None
    ):
        raise PdfOcrError("Windows rename requires live directory handles")
    if (
        not output_name
        or Path(output_name).name != output_name
        or "/" in output_name
        or "\\" in output_name
    ):
        raise PdfOcrError("Windows rename target must be a simple name")
    _windows_set_relative_rename_information(
        staging_guard.windows_handle,
        parent_guard.windows_handle,
        output_name,
    )


def _windows_set_relative_rename_information(
    source_handle: int,
    parent_handle: int,
    output_name: str,
) -> None:
    from ctypes import wintypes

    class FileRenameInfo(ctypes.Structure):
        _fields_ = [
            ("ReplaceIfExistsOrFlags", wintypes.DWORD),
            ("RootDirectory", wintypes.HANDLE),
            ("FileNameLength", wintypes.DWORD),
            ("FileName", wintypes.WCHAR * 1),
        ]

    class IoStatusValue(ctypes.Union):
        _fields_ = [
            ("Status", ctypes.c_long),
            ("Pointer", wintypes.LPVOID),
        ]

    class IoStatusBlock(ctypes.Structure):
        _fields_ = [
            ("Value", IoStatusValue),
            ("Information", ctypes.c_size_t),
        ]

    encoded_name = output_name.encode("utf-16-le")
    buffer_size = (
        FileRenameInfo.FileName.offset
        + len(encoded_name)
        + ctypes.sizeof(wintypes.WCHAR)
    )
    buffer = ctypes.create_string_buffer(buffer_size)
    information = ctypes.cast(
        buffer,
        ctypes.POINTER(FileRenameInfo),
    ).contents
    information.ReplaceIfExistsOrFlags = 0
    information.RootDirectory = wintypes.HANDLE(parent_handle)
    information.FileNameLength = len(encoded_name)
    ctypes.memmove(
        ctypes.addressof(buffer) + FileRenameInfo.FileName.offset,
        encoded_name,
        len(encoded_name),
    )
    ntdll = ctypes.WinDLL("ntdll")
    rename = ntdll.NtSetInformationFile
    rename.argtypes = [
        wintypes.HANDLE,
        ctypes.POINTER(IoStatusBlock),
        wintypes.LPVOID,
        wintypes.ULONG,
        ctypes.c_int,
    ]
    rename.restype = ctypes.c_long
    io_status = IoStatusBlock()
    status = int(
        rename(
            wintypes.HANDLE(source_handle),
            ctypes.byref(io_status),
            buffer,
            buffer_size,
            10,
        )
    )
    if status >= 0:
        return
    rtl_status_to_error = ntdll.RtlNtStatusToDosError
    rtl_status_to_error.argtypes = [wintypes.ULONG]
    rtl_status_to_error.restype = wintypes.ULONG
    error_number = int(
        rtl_status_to_error(status & 0xFFFFFFFF)
    )
    if error_number in {80, 183}:
        raise OutputExistsError(
            f"output appeared during processing: {output_name}"
        )
    if error_number == 32:
        raise _WindowsRenameSharingError(
            "handle-relative directory rename was blocked by final read guards"
        )
    raise PdfOcrError(
        f"handle-relative atomic output publish failed: {ctypes.WinError(error_number)}"
    )


def _path_identity(path: Path) -> _PathIdentity:
    try:
        metadata = path.stat(follow_symlinks=False)
    except OSError as error:
        raise PdfOcrError(f"path identity cannot be read: {path}") from error
    if _is_link_or_reparse(path) or not path.is_dir():
        raise PdfOcrError(f"path identity is not a real directory: {path}")
    return _PathIdentity(metadata.st_dev, metadata.st_ino)


def _require_directory_identity(
    path: Path,
    expected: _PathIdentity,
    description: str,
) -> None:
    if _path_identity(path) != expected:
        raise PdfOcrError(f"{description} identity changed during processing")


def _is_link_or_reparse(path: Path) -> bool:
    try:
        if path.is_symlink():
            return True
        is_junction = getattr(path, "is_junction", None)
        if callable(is_junction) and is_junction():
            return True
        attributes = getattr(path.stat(follow_symlinks=False), "st_file_attributes", 0)
        return bool(
            attributes
            & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
        )
    except OSError:
        return False


def _path_exists_even_if_broken(path: Path) -> bool:
    return os.path.lexists(path)


def _absolute_path(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _timestamp() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")
