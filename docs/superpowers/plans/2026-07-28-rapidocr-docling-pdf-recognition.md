# RapidOCR·Docling PDF 인식 파이프라인 구현 계획

**현재 실행 상태**: Task 1~9 구현·자동 회귀·실제 관보 4건 처리를 완료했고,
Task 10 문서 동기화를 진행했다. 네 관보는 실제 표가 없는 1쪽 문서이며 AI 시각
사전대조만 완료됐으므로 T112 사람 검수 게이트는 `PENDING_USER_HUMAN_REVIEW`다.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Windows CPU에서 PaddleOCR·PaddlePaddle 실행 패키지 없이 정부 PDF의 한국어 원문과 표 구조를 인식하고, 페이지·모델·산출물 해시와 사람 검수 상태를 보존하는 T112 조사 파이프라인을 완성한다.

**Architecture:** pypdf가 PDF 유효성·암호화·내장 텍스트 경계를 유지하고 PyMuPDF가 모든 페이지를 300 DPI PNG로 렌더링한다. 모든 PNG는 먼저 OCR·표 구조 기능을 끈 Docling 레이아웃 탐지를 거치며, 라우팅 결과에 따라 내장 텍스트 또는 별도 RapidOCR 감사 실행을 사용하고 표 페이지에만 Docling 내부 RapidOCR와 TableFormer `accurate` 구조 복원을 추가한다. 모든 페이지 산출물과 매니페스트를 staging에서 검증한 뒤 전체 성공일 때만 원자적으로 게시한다.

**Tech Stack:** Windows, Python 3.12, RapidOCR, ONNX Runtime CPU, Docling, docling-ibm-models, TableFormer `accurate`, pypdf, PyMuPDF, JSON Schema Draft 2020-12, SHA-256, pytest, uv, PowerShell

## Global Constraints

- 구현 기준 설계는 `docs/superpowers/specs/2026-07-28-rapidocr-docling-pdf-recognition-design.md`이며 기존 PaddleOCR 설계·계획은 결정 이력으로만 보존한다.
- 실행 플랫폼은 Windows CPU이고 격리 런타임은 Python `>=3.12,<3.13`이다.
- `paddleocr`와 `paddlepaddle` 실행 패키지는 제거하며, Paddle 계열에서 학습된 한국어 ONNX 모델은 RapidOCR·ONNX Runtime으로만 실행한다.
- pypdf의 PDF 유효성·암호화·페이지 수·내장 텍스트 검사와 PyMuPDF의 300 DPI PNG 렌더링은 유지한다.
- Docling에는 원본 PDF가 아니라 `pages/NNNN.png`만 전달한다.
- 모든 페이지에서 Docling 레이아웃 전용 1차 패스를 실행하고, 이 패스는 `do_ocr=False`, `do_table_structure=False`여야 한다.
- 표 페이지의 2차 패스만 Docling 내부 RapidOCR와 TableFormer `accurate`를 사용한다.
- 직접 RapidOCR 감사 실행의 원시 보존 임계값은 `0.0`, 사람 검수 임계값은 `0.90`이다.
- 런타임 중 모델 자동 다운로드와 원격 서비스 호출은 금지한다. 모든 모델 경로는 잠금 파일로 검증된 로컬 절대 경로여야 한다.
- 매니페스트와 페이지 계약 버전은 `2.0.0`이다.
- 처리 경로는 `EMBEDDED_TEXT`, `RAPIDOCR`, `RAPIDOCR_TABLEFORMER` 세 개만 허용한다.
- OCR 또는 표 구조 결과만으로 정책·세금·공간 사실을 `VERIFIED`로 승격하거나 공개 fixture·RAG 입력으로 사용하지 않는다.
- 실제 승인 표본은 `2017-114.pdf`, `2018-151.pdf`, `2022-189.pdf`, `2023-001.pdf` 네 건이다.
- 관련 없는 전체 프로젝트 테스트는 실행하지 않는다.
- 아래의 설치·모델 다운로드·코드 변경·테스트 실행·Git 명령은 후속 실행 절차일 뿐이다. 이 계획서 작성 승인은 실행 승인이 아니며 각 범위는 사용자의 별도 승인을 받은 뒤에만 수행한다.
- 특히 각 Task의 `Run`과 `Commit` 단계는 사용자가 테스트 또는 Git 작업을 명시적으로 승인하기 전에는 실행하지 않는다.

---

## 1. 구현 후 산출물 구조

페이지 `0001`은 다음 구조를 갖는다.

```text
<output>/
├── pdf-ocr-manifest.json
└── pages/
    ├── 0001.png
    ├── 0001.ocr.json
    ├── 0001.structure.json
    ├── 0001.md
    └── 0001.tables/
        ├── 0001.html
        └── 0002.html
```

- `0001.ocr.json`: 내장 텍스트 또는 직접 RapidOCR 감사 결과의 텍스트·신뢰도·polygon·bbox·읽기 순서
- `0001.structure.json`: Docling 레이아웃 결과와 TableFormer 표의 행·열·셀·병합 범위
- `0001.md`: 사람이 읽는 페이지 텍스트. 병합셀 구조의 권위 있는 근거가 아니다.
- `0001.tables/TTTT.html`: 표별 `rowspan`·`colspan`을 보존한 사람 대조용 HTML
- `pdf-ocr-manifest.json`: 입력·런타임·모델·페이지·출력·검수 상태와 모든 SHA-256 연결

## 2. 파일 책임 지도

### 새로 생성할 파일

| 경로 | 단일 책임 |
|---|---|
| `tools/pdf-ocr/src/pdf_ocr/types.py` | OCR·레이아웃·표 구조의 내부 불변 데이터 타입 |
| `tools/pdf-ocr/src/pdf_ocr/runtime.py` | uv 잠금 버전·설치 버전·ONNX CPU provider 일치 검사 |
| `tools/pdf-ocr/src/pdf_ocr/model_lock.py` | 모델 잠금 스키마, 로컬 경로·크기·SHA-256 검증 |
| `tools/pdf-ocr/src/pdf_ocr/ocr.py` | 직접 RapidOCR 엔진 생성, 결과 정규화, 감사 토큰 생성 |
| `tools/pdf-ocr/src/pdf_ocr/structure.py` | Docling 레이아웃 전용 패스와 TableFormer 표 패스, 구조 정규화 |
| `tools/pdf-ocr/src/pdf_ocr/artifacts.py` | 페이지 JSON·Markdown·표 HTML 직렬화와 파일 레코드 생성 |
| `tools/pdf-ocr/schemas/model-lock.schema.json` | 패키지·모델 잠금 계약 `2.0.0` |
| `tools/pdf-ocr/schemas/source-receipt.schema.json` | provisioning 출처·라이선스·상대 경로 입력 계약 |
| `tools/pdf-ocr/schemas/page-ocr.schema.json` | 페이지 OCR 감사 산출물 계약 `2.0.0` |
| `tools/pdf-ocr/schemas/page-structure.schema.json` | 레이아웃·표 구조 산출물 계약 `2.0.0` |
| `tools/pdf-ocr/tests/test_runtime.py` | 패키지 잠금과 CPU provider 계약 |
| `tools/pdf-ocr/tests/test_model_lock.py` | 누락·크기·해시·역할 불일치 fail-closed 계약 |
| `tools/pdf-ocr/tests/test_rapidocr_runner.py` | RapidOCR 결과·좌표·신뢰도 정규화 계약 |
| `tools/pdf-ocr/tests/test_docling_structure.py` | 레이아웃 전용 설정과 행·열·병합셀 구조 계약 |
| `tools/pdf-ocr/tests/test_artifacts.py` | JSON·HTML·Markdown·해시 산출물 계약 |
| `specs/001-real-estate-policy-dashboard/research-data/pdf-ocr-acceptance.md` | 실제 관보 네 건의 한국어 사람 대조 기록과 영문 AI context |

### 수정할 파일

| 경로 | 변경 책임 |
|---|---|
| `tools/pdf-ocr/pyproject.toml` | Paddle 런타임 제거, 호환성이 확인된 RapidOCR·ONNX·Docling 직접 의존성 선언 |
| `tools/pdf-ocr/uv.lock` | Windows Python 3.12에서 확인된 정확한 패키지 버전 고정 |
| `tools/pdf-ocr/models.lock.json` | RapidOCR·Docling·TableFormer 모델 파일별 출처·크기·SHA-256·라이선스 고정 |
| `tools/pdf-ocr/scripts/generate_model_lock.py` | 명시적 로컬 모델 루트와 출처 영수증에서 잠금 파일 생성 |
| `tools/pdf-ocr/schemas/manifest.schema.json` | 런타임·모델·페이지 산출물 계약을 `2.0.0`으로 교체 |
| `tools/pdf-ocr/src/pdf_ocr/contracts.py` | 세 페이지/매니페스트 스키마, 표 topology, 해시 연쇄 검증 |
| `tools/pdf-ocr/src/pdf_ocr/router.py` | 신규 경로와 표 우선 라우팅 |
| `tools/pdf-ocr/src/pdf_ocr/pipeline.py` | PDF 경계·페이지 흐름·원자 게시만 조정하는 오케스트레이터로 축소 |
| `tools/pdf-ocr/src/pdf_ocr/cli.py` | 신규 런타임·모델 잠금 경로를 파이프라인에 전달 |
| `tools/pdf-ocr/Dockerfile` | Paddle 환경 제거, 오프라인 모델·frozen lock·비루트 실행 |
| `tools/pdf-ocr/tests/test_router.py` | 신규 경로와 표 우선순위 |
| `tools/pdf-ocr/tests/test_manifest_schema.py` | 매니페스트 `2.0.0`과 출력 종류 |
| `tools/pdf-ocr/tests/test_pipeline_integration.py` | 레이아웃→라우팅→OCR/표 2차 패스 흐름 |
| `tools/pdf-ocr/tests/test_pipeline_fail_closed.py` | OCR·표·모델·좌표·빈 출력·원자 게시 실패 경계 |
| `tools/pdf-ocr/tests/test_research_samples.py` | PowerShell wrapper와 native child crash 정리 |
| `scripts/research/extract-pdf.ps1` | `uv run --frozen`, 오프라인 환경, 모델 잠금 전달 |
| `THIRD_PARTY_NOTICES.md` | RapidOCR·ONNX Runtime·Docling·모델 artifact별 고지 |
| `specs/001-real-estate-policy-dashboard/spec.md` | 승인된 PDF 인식 파이프라인 명칭 교체 |
| `specs/001-real-estate-policy-dashboard/plan.md` | 조사 기술·처리 흐름·게이트 교체 |
| `specs/001-real-estate-policy-dashboard/research.md` | Paddle 실패 이력과 채택 조합·근거 기록 |
| `specs/001-real-estate-policy-dashboard/tasks.md` | T112 설명·상태·AI context 갱신 |
| `specs/001-real-estate-policy-dashboard/source-register.md` | 도구·모델·테스트·실제 대조 증거 갱신 |
| `specs/001-real-estate-policy-dashboard/research-data/README.md` | 산출물·보존·검수 경계 갱신 |
| `specs/001-real-estate-policy-dashboard/checklists/research-readiness.md` | T112 조사 게이트 증거 갱신 |
| `specs/001-real-estate-policy-dashboard/research-data/cutoff-manifest.csv` | 최종 승인 문서의 변경 후 SHA-256 갱신 |
| `docs/superpowers/specs/2026-07-28-rapidocr-docling-pdf-recognition-design.md` | 문서 상태를 승인 완료로 갱신 |
| 기존 PaddleOCR 설계·계획 | 삭제하지 않고 `SUPERSEDED`와 후속 문서 경로만 기록 |

## 3. 고정 내부 인터페이스

후속 Task는 아래 이름과 의미를 바꾸지 않는다.

```python
# tools/pdf-ocr/src/pdf_ocr/types.py
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

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
```

행·열 인덱스는 0부터 시작하고 `start_*`는 포함, `end_*`는 제외한다.
따라서 `row_span == end_row - start_row`,
`col_span == end_column - start_column`이어야 한다.

---

### Task 1: Windows Python 3.12 호환 조합과 런타임 잠금

**Files:**

- Create: `tools/pdf-ocr/src/pdf_ocr/runtime.py`
- Create: `tools/pdf-ocr/tests/test_runtime.py`
- Modify: `tools/pdf-ocr/pyproject.toml:1-28`
- Modify: `tools/pdf-ocr/uv.lock`

**Interfaces:**

- Consumes: `tools/pdf-ocr/uv.lock`
- Produces: `locked_runtime_versions(lock_path: Path) -> dict[str, str]`
- Produces: `collect_runtime_info(lock_path: Path) -> RuntimeInfo`
- Produces: `require_cpu_execution_provider(providers: Sequence[str]) -> str`

- [ ] **Step 1: 잠금·설치·CPU provider 불일치의 실패 테스트 작성**

```python
from pathlib import Path

import pytest

from pdf_ocr.runtime import (
    RuntimeContractError,
    require_cpu_execution_provider,
)


def test_missing_cpu_execution_provider_is_rejected() -> None:
    with pytest.raises(RuntimeContractError, match="CPUExecutionProvider"):
        require_cpu_execution_provider(["CUDAExecutionProvider"])


def test_cpu_execution_provider_is_selected_explicitly() -> None:
    assert require_cpu_execution_provider(
        ["AzureExecutionProvider", "CPUExecutionProvider"]
    ) == "CPUExecutionProvider"
```

`test_runtime.py`에는 임시 `uv.lock`의 `rapidocr`, `onnxruntime`, `docling`,
`docling-ibm-models` 버전과 monkeypatch한 `importlib.metadata.version()` 값이 하나라도
다르면 `RuntimeContractError`가 발생하는 사례도 함께 작성한다.

- [ ] **Step 2: 실패 확인**

Run:

```powershell
uv run --project tools/pdf-ocr pytest tools/pdf-ocr/tests/test_runtime.py -q
```

Expected: `pdf_ocr.runtime` 모듈이 없어 collection 단계에서 실패한다.

- [ ] **Step 3: 최소 런타임 계약 구현**

```python
from __future__ import annotations

import importlib.metadata
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

LOCKED_DISTRIBUTIONS = (
    "rapidocr",
    "onnxruntime",
    "docling",
    "docling-ibm-models",
)


class RuntimeContractError(RuntimeError):
    pass


@dataclass(frozen=True)
class RuntimeInfo:
    package_versions: dict[str, str]
    execution_provider: str


def locked_runtime_versions(lock_path: Path) -> dict[str, str]:
    payload = tomllib.loads(lock_path.read_text(encoding="utf-8"))
    versions = {
        str(item["name"]): str(item["version"])
        for item in payload.get("package", [])
    }
    missing = [name for name in LOCKED_DISTRIBUTIONS if name not in versions]
    if missing:
        raise RuntimeContractError(
            f"uv.lock is missing runtime packages: {', '.join(missing)}"
        )
    return {name: versions[name] for name in LOCKED_DISTRIBUTIONS}


def require_cpu_execution_provider(providers: Sequence[str]) -> str:
    if "CPUExecutionProvider" not in providers:
        raise RuntimeContractError("ONNX CPUExecutionProvider is unavailable")
    return "CPUExecutionProvider"


def collect_runtime_info(lock_path: Path) -> RuntimeInfo:
    import onnxruntime

    locked = locked_runtime_versions(lock_path)
    installed = {
        name: importlib.metadata.version(name)
        for name in LOCKED_DISTRIBUTIONS
    }
    mismatches = {
        name: (locked[name], installed[name])
        for name in LOCKED_DISTRIBUTIONS
        if locked[name] != installed[name]
    }
    if mismatches:
        raise RuntimeContractError(
            f"installed packages do not match uv.lock: {mismatches}"
        )
    provider = require_cpu_execution_provider(
        onnxruntime.get_available_providers()
    )
    return RuntimeInfo(
        package_versions=installed,
        execution_provider=provider,
    )
```

`collect_runtime_info()`는 위와 같이 `locked_runtime_versions()` 결과와
`importlib.metadata.version()`을 정확히 비교하고, `onnxruntime.get_available_providers()`
중 `CPUExecutionProvider`를 명시적으로 선택해 반환한다.

- [ ] **Step 4: 호환 후보를 정확한 잠금 버전으로 해석**

`pyproject.toml`에서 `paddleocr[doc-parser]`와 `paddlepaddle`을 제거하고 다음 직접
의존성 범위를 선언한다. project description도
`Fail-closed RapidOCR and Docling research pipeline for Korean government PDFs`로
교체한다.

```toml
dependencies = [
    "docling>=2.115,<3",
    "docling-ibm-models>=3.13,<4",
    "jsonschema>=4.25,<5",
    "onnxruntime>=1.22,<2",
    "pymupdf>=1.26,<2",
    "pypdf>=6,<7",
    "rapidocr>=3.9.1,<4",
]
```

Run:

```powershell
uv lock --project tools/pdf-ocr --python 3.12 --resolution highest
uv sync --project tools/pdf-ocr --frozen --group dev
uv run --project tools/pdf-ocr python -c "from importlib.metadata import version; import onnxruntime as ort; print({n: version(n) for n in ('rapidocr','onnxruntime','docling','docling-ibm-models')}); print(ort.get_available_providers())"
```

Expected:

- 해결된 정확한 버전이 `uv.lock`에 기록된다.
- 네 직접 패키지가 Python 3.12에서 동시에 import된다.
- 출력 provider 목록에 `CPUExecutionProvider`가 있다.
- `paddleocr`와 `paddlepaddle`은 `uv.lock`에 존재하지 않는다.
- 하나라도 충족하지 않으면 다음 Task로 진행하지 않고 호환 범위 변경 승인을 요청한다.

- [ ] **Step 5: 런타임 계약 통과 확인**

Run:

```powershell
uv run --project tools/pdf-ocr pytest tools/pdf-ocr/tests/test_runtime.py -q
```

Expected: 모든 `test_runtime.py` 사례가 통과한다.

- [ ] **Step 6: 승인된 경우에만 Task 단위 커밋**

```powershell
git add tools/pdf-ocr/pyproject.toml tools/pdf-ocr/uv.lock tools/pdf-ocr/src/pdf_ocr/runtime.py tools/pdf-ocr/tests/test_runtime.py
git commit -m "build(pdf-ocr): lock RapidOCR Docling runtime"
```

---

### Task 2: 경로·페이지·매니페스트 계약 `2.0.0`

**Files:**

- Create: `tools/pdf-ocr/src/pdf_ocr/types.py`
- Create: `tools/pdf-ocr/schemas/page-ocr.schema.json`
- Create: `tools/pdf-ocr/schemas/page-structure.schema.json`
- Modify: `tools/pdf-ocr/schemas/manifest.schema.json:1-279`
- Modify: `tools/pdf-ocr/src/pdf_ocr/contracts.py:1-26`
- Modify: `tools/pdf-ocr/src/pdf_ocr/router.py:1-33`
- Modify: `tools/pdf-ocr/tests/test_router.py:1-25`
- Modify: `tools/pdf-ocr/tests/test_manifest_schema.py:1-131`
- Create: `tools/pdf-ocr/tests/test_artifacts.py`

**Interfaces:**

- Produces: 고정 타입 `OcrToken`, `OcrPage`, `LayoutRegion`, `LayoutPage`, `TableCell`, `TableData`, `StructurePage`
- Produces: `select_page_route(text: str, *, has_table: bool, has_complex_layout: bool) -> PageRoute`
- Produces: `validate_ocr_page(payload: Mapping[str, Any]) -> None`
- Produces: `validate_structure_page(payload: Mapping[str, Any]) -> None`
- Produces: `validate_manifest(payload: Mapping[str, Any]) -> None`
- Produces: `validate_table_topology(table: Mapping[str, Any]) -> None`
- Produces: `validate_output_hashes(payload: Mapping[str, Any], root: Path) -> None`
- Produces: `sha256(path: Path) -> str`

- [ ] **Step 1: 신규 경로 우선순위 실패 테스트 작성**

```python
from pdf_ocr.router import PageRoute, select_page_route


def test_table_always_uses_rapidocr_tableformer() -> None:
    text = "서울특별시 고시 제2026-1호 " * 4
    assert select_page_route(
        text,
        has_table=True,
        has_complex_layout=False,
    ) is PageRoute.RAPIDOCR_TABLEFORMER


def test_clean_simple_text_keeps_embedded_text() -> None:
    text = "서울특별시 고시 제2026-1호 " * 4
    assert select_page_route(
        text,
        has_table=False,
        has_complex_layout=False,
    ) is PageRoute.EMBEDDED_TEXT


def test_complex_non_table_page_uses_rapidocr() -> None:
    text = "서울특별시 고시 제2026-1호 " * 4
    assert select_page_route(
        text,
        has_table=False,
        has_complex_layout=True,
    ) is PageRoute.RAPIDOCR
```

- [ ] **Step 2: 신규 스키마와 topology 실패 테스트 작성**

`test_manifest_schema.py`의 유효 fixture는 `schema_version: "2.0.0"`과 다음 runtime
필드를 모두 포함한다.

```python
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
        {
            "component": "RAPIDOCR",
            "role": "rapidocr_rec",
            "name": "korean_PP-OCRv5_mobile_rec",
            "source_url": "https://www.modelscope.cn/",
            "license": "UPSTREAM_MODEL_NOTICE_RECORDED",
            "bytes": 1,
            "sha256": "sha256:" + ("0" * 64),
        }
    ],
}
```

버전 문자열은 예시 fixture이며 실제 런타임 값은 Task 1의 `uv.lock`에서 읽는다.
스키마는 특정 예시 버전을 `const`로 고정하지 않고 비어 있지 않은 문자열로 검증한다.

`test_artifacts.py`에는 다음 겹침 실패 사례를 작성한다.

```python
def test_overlapping_table_cells_are_rejected() -> None:
    table = {
        "table_number": 1,
        "bbox": [0, 0, 200, 100],
        "num_rows": 1,
        "num_columns": 1,
        "cells": [
            cell(start_row=0, end_row=1, start_column=0, end_column=1),
            cell(start_row=0, end_row=1, start_column=0, end_column=1),
        ],
    }
    with pytest.raises(ValidationError, match="overlap"):
        validate_table_topology(table)
```

경계 밖 인덱스, `row_span`·`col_span` 불일치, 빈 cell 목록, grid 미포함 영역,
음수 또는 페이지 크기 밖 bbox도 각각 실패 사례로 고정한다.

- [ ] **Step 3: 실패 확인**

Run:

```powershell
uv run --project tools/pdf-ocr pytest tools/pdf-ocr/tests/test_router.py tools/pdf-ocr/tests/test_manifest_schema.py tools/pdf-ocr/tests/test_artifacts.py -q
```

Expected: 신규 enum·스키마·검증 함수가 없어 실패한다.

- [ ] **Step 4: 타입과 라우터 최소 구현**

`types.py`는 이 문서의 “고정 내부 인터페이스”를 그대로 구현한다.
`router.py`는 다음 우선순위를 사용한다.

```python
class PageRoute(str, Enum):
    EMBEDDED_TEXT = "EMBEDDED_TEXT"
    RAPIDOCR = "RAPIDOCR"
    RAPIDOCR_TABLEFORMER = "RAPIDOCR_TABLEFORMER"


def select_page_route(
    text: str,
    *,
    has_table: bool,
    has_complex_layout: bool,
) -> PageRoute:
    if has_table:
        return PageRoute.RAPIDOCR_TABLEFORMER
    if has_complex_layout:
        return PageRoute.RAPIDOCR

    non_whitespace_chars, invalid_character_ratio = embedded_text_quality(text)
    if non_whitespace_chars < 30 or invalid_character_ratio > 0.05:
        return PageRoute.RAPIDOCR
    return PageRoute.EMBEDDED_TEXT
```

- [ ] **Step 5: 페이지 스키마의 정확한 필드 계약 구현**

`page-ocr.schema.json`은 다음 필드를 강제한다.

```json
{
  "schema_version": "2.0.0",
  "page_number": 1,
  "engine": "RAPIDOCR",
  "model_name": "korean_PP-OCRv5_mobile_rec",
  "coordinate_space": {
    "unit": "pixel",
    "width": 2480,
    "height": 3508,
    "render_dpi": 300,
    "pdf_points_per_pixel": 0.24
  },
  "blocks": [],
  "minimum_confidence": null,
  "raw": {}
}
```

- `engine`은 `EMBEDDED_TEXT` 또는 `RAPIDOCR`이다.
- `blocks[*]`는 `text`, `recognition_confidence`, `polygon`, `bbox`,
  `reading_order`, `model_name`, `source_page_number`를 모두 가진다.
- `recognition_confidence`는 `0.0..1.0`, `polygon`은 4개 이상의 `[x, y]`,
  `bbox`는 `[x0, y0, x1, y1]`, 읽기 순서는 0 이상의 고유 정수다.
- `RAPIDOCR` 경로는 blocks가 한 개 이상이어야 하며 `minimum_confidence`가 숫자여야 한다.
- `EMBEDDED_TEXT` 경로는 RapidOCR 결과로 위장하지 않고
  `model_name: "embedded-text"`를 사용한다.

`page-structure.schema.json`은 `page_number`, `coordinate_space`, `regions`,
`tables`, `raw`를 강제하고 표에는 `table_number`, `bbox`, `num_rows`,
`num_columns`, `cells`, `html_file`을 강제한다. 각 cell은 고정 내부 인터페이스의 필드
전부를 가지며 비교 상태는 `MATCHED`, `MISMATCH`, `NOT_COMPARABLE` 중 하나다.

- [ ] **Step 6: 매니페스트와 추가 불변조건 구현**

`manifest.schema.json`을 `2.0.0`으로 교체하고 페이지별 출력 종류를
`OCR_JSON`, `STRUCTURE_JSON`, `MARKDOWN`, `TABLE_HTML`로 제한한다.
`contracts.py`는 스키마 검증 후 다음을 추가로 검사한다.

```python
def validate_table_topology(table: Mapping[str, Any]) -> None:
    expected = {
        (row, column)
        for row in range(table["num_rows"])
        for column in range(table["num_columns"])
    }
    occupied: set[tuple[int, int]] = set()
    for cell in table["cells"]:
        if cell["row_span"] != cell["end_row"] - cell["start_row"]:
            raise ValidationError("row_span does not match row range")
        if cell["col_span"] != cell["end_column"] - cell["start_column"]:
            raise ValidationError("col_span does not match column range")
        slots = {
            (row, column)
            for row in range(cell["start_row"], cell["end_row"])
            for column in range(cell["start_column"], cell["end_column"])
        }
        if occupied & slots:
            raise ValidationError("table cells overlap")
        occupied.update(slots)
    if occupied != expected:
        raise ValidationError("table cells do not cover the declared grid")


def validate_output_hashes(
    payload: Mapping[str, Any],
    root: Path,
) -> None:
    records = []
    for page in payload["pages"]:
        records.append(page["image"])
        records.extend(page["outputs"])
    for record in records:
        path = (root / record["file_name"]).resolve()
        if root.resolve() not in path.parents or not path.is_file():
            raise ValidationError("manifest output path is missing or escapes root")
        if path.stat().st_size != record["bytes"]:
            raise ValidationError("manifest output size mismatch")
        if f"sha256:{sha256(path)}" != record["sha256"]:
            raise ValidationError("manifest output SHA-256 mismatch")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as input_file:
        for chunk in iter(lambda: input_file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()
```

또한 page number가 1부터 `input.page_count`까지 연속인지, 표 route의
`TABLE_HTML` 수가 `structure.json`의 표 수와 같은지, 모든 파일 레코드가
`sha256:<64 lowercase hex>`인지 검사한다.

- [ ] **Step 7: 계약 테스트 통과 확인**

Run:

```powershell
uv run --project tools/pdf-ocr pytest tools/pdf-ocr/tests/test_router.py tools/pdf-ocr/tests/test_manifest_schema.py tools/pdf-ocr/tests/test_artifacts.py -q
```

Expected: 신규 경로·스키마·topology 사례가 모두 통과한다.

- [ ] **Step 8: 승인된 경우에만 Task 단위 커밋**

```powershell
git add tools/pdf-ocr/src/pdf_ocr/types.py tools/pdf-ocr/src/pdf_ocr/router.py tools/pdf-ocr/src/pdf_ocr/contracts.py tools/pdf-ocr/schemas tools/pdf-ocr/tests/test_router.py tools/pdf-ocr/tests/test_manifest_schema.py tools/pdf-ocr/tests/test_artifacts.py
git commit -m "feat(pdf-ocr): define version 2 page contracts"
```

---

### Task 3: 모델 artifact 잠금과 오프라인 실행 경계

**Files:**

- Create: `tools/pdf-ocr/src/pdf_ocr/model_lock.py`
- Create: `tools/pdf-ocr/schemas/model-lock.schema.json`
- Create: `tools/pdf-ocr/schemas/source-receipt.schema.json`
- Create: `tools/pdf-ocr/tests/test_model_lock.py`
- Modify: `tools/pdf-ocr/scripts/generate_model_lock.py:1-126`
- Modify: `tools/pdf-ocr/models.lock.json`

**Interfaces:**

- Consumes: 환경변수 `PDF_OCR_MODEL_HOME`
- Produces: `LockedFile`, `LockedArtifact`
- Produces: `load_model_lock(lock_path: Path, model_home: Path, runtime_versions: Mapping[str, str]) -> tuple[LockedArtifact, ...]`
- Produces: `artifact_path(artifacts: Sequence[LockedArtifact], role: str) -> Path`
- Produces: `optional_artifact_path(artifacts: Sequence[LockedArtifact], role: str) -> Path | None`
- Produces: `docling_artifacts_root(artifacts: Sequence[LockedArtifact]) -> Path`
- Produces: `build_lock(model_home: Path, receipt_path: Path) -> dict[str, object]`

- [ ] **Step 1: 모델 잠금 실패 테스트 작성**

```python
def test_model_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    model_home = tmp_path / "models"
    model_home.mkdir()
    model_root = model_home / "rapidocr-rec"
    model_root.mkdir()
    model = model_root / "korean-rec.onnx"
    model.write_bytes(b"changed")
    lock = write_lock(
        tmp_path,
        root="rapidocr-rec",
        entrypoint="korean-rec.onnx",
        file_path="korean-rec.onnx",
        byte_count=7,
        digest="sha256:" + ("0" * 64),
    )

    with pytest.raises(ModelLockError, match="SHA-256"):
        load_model_lock(lock, model_home, RUNTIME_VERSIONS)


def test_absolute_or_parent_escape_path_is_rejected(tmp_path: Path) -> None:
    lock = write_lock(
        tmp_path,
        root="../outside",
        entrypoint="model.onnx",
        file_path="model.onnx",
    )
    with pytest.raises(ModelLockError, match="model home"):
        load_model_lock(lock, tmp_path / "models", RUNTIME_VERSIONS)
```

다음 실패 사례도 각각 작성한다.

- `rapidocr`, `onnxruntime`, `docling`, `docling-ibm-models` 잠금 버전과 설치 버전 불일치
- 필수 역할 `rapidocr_det`, `rapidocr_rec`, `rapidocr_rec_keys`, `rapidocr_font`,
  `docling_layout`, `tableformer` 중 하나 누락
- 중복 역할, 0바이트 파일, 비 HTTPS 출처, 비어 있는 라이선스
- `PDF_OCR_MODEL_HOME` 밖으로 나가는 상대 경로와 symlink
- 잠금 파일에 기록되지 않은 파일을 factory에 요청

- [ ] **Step 2: 실패 확인**

Run:

```powershell
uv run --project tools/pdf-ocr pytest tools/pdf-ocr/tests/test_model_lock.py -q
```

Expected: `pdf_ocr.model_lock`과 `model-lock.schema.json`이 없어 실패한다.

- [ ] **Step 3: 모델 잠금 스키마 구현**

`model-lock.schema.json`의 최상위와 artifact 1개 형태를 보여주는 발췌는 다음과 같다.
유효 fixture는 필수 역할 여섯 개를 모두 포함한다.

```json
{
  "schema_version": "2.0.0",
  "generated_at": "2026-07-28T00:00:00+09:00",
  "cache_environment_variable": "PDF_OCR_MODEL_HOME",
  "packages": [
    {"name": "rapidocr", "version": "3.9.1"}
  ],
  "artifacts": [
    {
      "component": "RAPIDOCR",
      "role": "rapidocr_rec",
      "name": "korean_PP-OCRv5_mobile_rec",
      "source_url": "https://www.modelscope.cn/",
      "license": "UPSTREAM_MODEL_NOTICE_RECORDED",
      "root": "rapidocr/korean-rec",
      "entrypoint": "korean_PP-OCRv5_mobile_rec.onnx",
      "files": [
        {
          "path": "korean_PP-OCRv5_mobile_rec.onnx",
          "bytes": 1,
          "sha256": "sha256:0000000000000000000000000000000000000000000000000000000000000000"
        }
      ]
    }
  ]
}
```

위 값은 스키마 형태를 설명하는 테스트 fixture다. 저장소의 실제
`models.lock.json`에는 승인된 모델 준비 단계에서 계산한 실제 URL·크기·해시만
기록한다. `component`는 `RAPIDOCR`, `DOCLING`, `TABLEFORMER`,
`role`은 `rapidocr_det`, `rapidocr_cls`, `rapidocr_rec`,
`rapidocr_rec_keys`, `rapidocr_font`, `docling_layout`, `tableformer`만 허용한다.
각 artifact의 `files`는 한 개 이상이어야 하고 file `path`는 artifact root 기준의
고유 상대 POSIX 경로여야 한다.
분류기를 사용하지 않으면 `rapidocr_cls`를 생략하고 런타임에서 `use_cls=False`를
강제한다.

- [ ] **Step 4: 잠금 로더의 경로·해시 검증 구현**

```python
import os
from typing import Sequence


@dataclass(frozen=True)
class LockedFile:
    path: Path
    bytes: int
    sha256: str


@dataclass(frozen=True)
class LockedArtifact:
    component: str
    role: str
    name: str
    source_url: str
    license: str
    path: Path
    files: tuple[LockedFile, ...]


def _resolve_inside_model_home(
    model_home: Path,
    root_value: str,
    entrypoint_value: str,
) -> tuple[Path, Path]:
    if Path(root_value).is_absolute() or Path(entrypoint_value).is_absolute():
        raise ModelLockError("model path must be relative to model home")
    root = model_home.resolve()
    artifact_root = (root / root_value).resolve()
    entrypoint = (artifact_root / entrypoint_value).resolve()
    if root not in artifact_root.parents or artifact_root not in {
        entrypoint, *entrypoint.parents
    }:
        raise ModelLockError("model path escapes model home")
    return artifact_root, entrypoint


def optional_artifact_path(
    artifacts: Sequence[LockedArtifact],
    role: str,
) -> Path | None:
    matches = [artifact.path for artifact in artifacts if artifact.role == role]
    if len(matches) > 1:
        raise ModelLockError(f"duplicate model role: {role}")
    return matches[0] if matches else None


def artifact_path(
    artifacts: Sequence[LockedArtifact],
    role: str,
) -> Path:
    value = optional_artifact_path(artifacts, role)
    if value is None:
        raise ModelLockError(f"missing model role: {role}")
    return value


def docling_artifacts_root(
    artifacts: Sequence[LockedArtifact],
) -> Path:
    paths = [
        artifact.path
        for artifact in artifacts
        if artifact.role in {"docling_layout", "tableformer"}
    ]
    if len(paths) != 2:
        raise ModelLockError("Docling layout and TableFormer roots are required")
    roots = [path if path.is_dir() else path.parent for path in paths]
    common = Path(os.path.commonpath([str(path) for path in roots]))
    if not common.is_dir():
        raise ModelLockError("Docling artifacts root is missing")
    return common
```

`load_model_lock()`은 JSON Schema를 먼저 검증하고, Task 1의 정확한 runtime 버전과
`packages`를 비교한 뒤 각 bundle의 `files` 목록과 실제 root 아래 일반 파일 목록이
정확히 같은지 검사하고 파일 크기와 SHA-256을 스트리밍 계산한다. entrypoint도 잠긴
파일 또는 잠긴 디렉터리여야 한다. 모든 검증이 끝난 후에만 `LockedArtifact` tuple을
반환한다.

```python
REQUIRED_ROLES = {
    "rapidocr_det",
    "rapidocr_rec",
    "rapidocr_rec_keys",
    "rapidocr_font",
    "docling_layout",
    "tableformer",
}


def load_model_lock(
    lock_path: Path,
    model_home: Path,
    runtime_versions: Mapping[str, str],
) -> tuple[LockedArtifact, ...]:
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    schema = json.loads(MODEL_LOCK_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator(schema).validate(payload)

    locked_versions = {
        item["name"]: item["version"]
        for item in payload["packages"]
    }
    if locked_versions != dict(runtime_versions):
        raise ModelLockError("model lock package versions do not match runtime")

    artifacts = []
    seen_roles = set()
    for item in payload["artifacts"]:
        role = item["role"]
        if role in seen_roles:
            raise ModelLockError(f"duplicate model role: {role}")
        seen_roles.add(role)
        artifact_root, entrypoint = _resolve_inside_model_home(
            model_home,
            item["root"],
            item["entrypoint"],
        )
        if not artifact_root.is_dir() or not entrypoint.exists():
            raise ModelLockError(f"model artifact is missing: {role}")

        descendants = list(artifact_root.rglob("*"))
        if any(path.is_symlink() for path in descendants):
            raise ModelLockError(f"model artifact contains symlink: {role}")
        actual_paths = {
            path.relative_to(artifact_root).as_posix(): path
            for path in descendants
            if path.is_file()
        }
        expected_files = {
            record["path"]: record for record in item["files"]
        }
        if set(actual_paths) != set(expected_files):
            raise ModelLockError(f"model file list does not match lock: {role}")

        locked_files = []
        for relative_path, record in expected_files.items():
            path = actual_paths[relative_path]
            if path.stat().st_size != record["bytes"]:
                raise ModelLockError(f"model file size mismatch: {path}")
            if f"sha256:{sha256(path)}" != record["sha256"]:
                raise ModelLockError(f"model file SHA-256 mismatch: {path}")
            locked_files.append(
                LockedFile(
                    path=path,
                    bytes=record["bytes"],
                    sha256=record["sha256"],
                )
            )
        artifacts.append(
            LockedArtifact(
                component=item["component"],
                role=role,
                name=item["name"],
                source_url=item["source_url"],
                license=item["license"],
                path=entrypoint,
                files=tuple(locked_files),
            )
        )

    missing = REQUIRED_ROLES - seen_roles
    if missing:
        raise ModelLockError(
            f"model lock is missing roles: {', '.join(sorted(missing))}"
        )
    return tuple(artifacts)
```

- [ ] **Step 5: 잠금 생성기를 출처 영수증 기반으로 교체**

모델 준비 단계는 네트워크가 허용된 별도 provisioning 실행이며, 런타임 실행과
분리한다. `generate_model_lock.py`는
`source-receipt.schema.json`을 통과한 `source-receipt.json`과 모델 루트를 입력받는다.
영수증 스키마의 핵심 계약은 다음과 같다.

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "type": "object",
  "additionalProperties": false,
  "required": ["schema_version", "artifacts"],
  "properties": {
    "schema_version": {"const": "1.0.0"},
    "artifacts": {
      "type": "array",
      "minItems": 6,
      "items": {
        "type": "object",
        "additionalProperties": false,
        "required": [
          "component", "role", "name", "source_url", "license",
          "root", "entrypoint"
        ],
        "properties": {
          "component": {
            "enum": ["RAPIDOCR", "DOCLING", "TABLEFORMER"]
          },
          "role": {
            "enum": [
              "rapidocr_det", "rapidocr_cls", "rapidocr_rec",
              "rapidocr_rec_keys", "rapidocr_font",
              "docling_layout", "tableformer"
            ]
          },
          "name": {"type": "string", "minLength": 1},
          "source_url": {
            "type": "string", "format": "uri", "pattern": "^https://"
          },
          "license": {"type": "string", "minLength": 1},
          "root": {"type": "string", "minLength": 1},
          "entrypoint": {"type": "string", "minLength": 1}
        }
      }
    }
  }
}
```

생성기는 `uv.lock`의 네 버전을 직접 읽어 최종 잠금의 `packages`에 쓰므로 사람이
버전을 재입력하지 않는다. `load_model_lock()`이 실행 시 설치 버전과 이를 대조한다.
영수증의 URL·라이선스·상대 `root`·`entrypoint`는 승인된 provisioning 명령의
출력과 upstream model card에서 그대로 기록한다. 생성기는 각 artifact root를
재귀 순회해 모든 일반 파일의 상대 `path`, `bytes`, `sha256`을 계산한다. symlink,
빈 디렉터리, 0바이트 파일, root 밖으로 나가는 entrypoint는 거부하며 영수증에
`files`, `bytes`, `sha256`이 들어오면 거부한다.

Run:

```powershell
uv run --project tools/pdf-ocr python tools/pdf-ocr/scripts/generate_model_lock.py --model-home $env:PDF_OCR_MODEL_HOME --receipt $env:PDF_OCR_MODEL_HOME\source-receipt.json --uv-lock tools/pdf-ocr/uv.lock --output tools/pdf-ocr/models.lock.json
```

Expected: 필수 역할, 출처, 라이선스, 파일 크기와 실제 SHA-256이 있는
`schema_version: "2.0.0"` 잠금이 생성된다. 모델 준비·다운로드 자체는 별도 사용자
승인 전에는 실행하지 않는다.

- [ ] **Step 6: 모델 잠금 테스트 통과 확인**

Run:

```powershell
uv run --project tools/pdf-ocr pytest tools/pdf-ocr/tests/test_model_lock.py -q
```

Expected: 누락·경로 탈출·크기·해시·버전·역할 실패 사례가 모두 통과한다.

- [ ] **Step 7: 승인된 경우에만 Task 단위 커밋**

```powershell
git add tools/pdf-ocr/src/pdf_ocr/model_lock.py tools/pdf-ocr/schemas/model-lock.schema.json tools/pdf-ocr/schemas/source-receipt.schema.json tools/pdf-ocr/tests/test_model_lock.py tools/pdf-ocr/scripts/generate_model_lock.py tools/pdf-ocr/models.lock.json
git commit -m "feat(pdf-ocr): enforce offline model artifact lock"
```

---

### Task 4: 직접 RapidOCR 감사 실행기

**Files:**

- Create: `tools/pdf-ocr/src/pdf_ocr/ocr.py`
- Create: `tools/pdf-ocr/tests/test_rapidocr_runner.py`

**Interfaces:**

- Consumes: `artifact_path(..., "rapidocr_det")`, `artifact_path(..., "rapidocr_rec")`,
  `artifact_path(..., "rapidocr_rec_keys")`, `artifact_path(..., "rapidocr_font")`
- Produces: `RapidOcrError`
- Produces: `build_rapidocr_params(artifacts: Sequence[LockedArtifact]) -> dict[str, Any]`
- Produces: `create_rapidocr_engine(artifacts: Sequence[LockedArtifact]) -> Any`
- Produces: `RapidOcrRunner.recognize(image_path: Path, *, page_number: int) -> OcrPage`

- [ ] **Step 1: 결과 정규화 실패 테스트 작성**

```python
class FakeRapidResult:
    boxes = [
        [[10.0, 20.0], [110.0, 20.0], [110.0, 50.0], [10.0, 50.0]]
    ]
    txts = ["서울특별시 고시 제2026-1호"]
    scores = [0.87]


def test_runner_preserves_polygon_bbox_confidence_and_page(tmp_path: Path) -> None:
    image = write_png(tmp_path / "0003.png", width=300, height=200)
    runner = RapidOcrRunner(
        engine=lambda _: FakeRapidResult(),
        model_name="korean_PP-OCRv5_mobile_rec",
    )

    result = runner.recognize(image, page_number=3)

    assert result.tokens[0].recognition_confidence == 0.87
    assert result.tokens[0].polygon == (
        (10.0, 20.0), (110.0, 20.0), (110.0, 50.0), (10.0, 50.0)
    )
    assert result.tokens[0].bbox == (10.0, 20.0, 110.0, 50.0)
    assert result.tokens[0].reading_order == 0
    assert result.tokens[0].source_page_number == 3
```

빈 결과, `boxes/txts/scores` 길이 불일치, NaN·범위 밖 confidence, 4점 미만 polygon,
이미지 경계 밖 좌표, `.png`가 아닌 입력을 각각 `RapidOcrError`로 고정한다.

- [ ] **Step 2: 실패 확인**

Run:

```powershell
uv run --project tools/pdf-ocr pytest tools/pdf-ocr/tests/test_rapidocr_runner.py -q
```

Expected: `pdf_ocr.ocr`이 없어 실패한다.

- [ ] **Step 3: 다운로드를 유발하지 않는 RapidOCR parameter 구현**

RapidOCR 공식 `params` 계약을 사용하고 경로를 모두 잠금 artifact에서 주입한다.

```python
import math
from dataclasses import replace

import fitz


class RapidOcrError(RuntimeError):
    pass


def build_rapidocr_params(
    artifacts: Sequence[LockedArtifact],
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "Global.text_score": 0.0,
        "Global.use_det": True,
        "Global.use_cls": False,
        "Global.use_rec": True,
        "Global.font_path": str(artifact_path(artifacts, "rapidocr_font")),
        "Global.log_level": "warning",
        "EngineConfig.onnxruntime.use_cuda": False,
        "EngineConfig.onnxruntime.use_dml": False,
        "Det.engine_type": "onnxruntime",
        "Det.lang_type": "ch",
        "Det.model_type": "mobile",
        "Det.ocr_version": "PP-OCRv5",
        "Det.model_path": str(artifact_path(artifacts, "rapidocr_det")),
        "Rec.engine_type": "onnxruntime",
        "Rec.lang_type": "korean",
        "Rec.model_type": "mobile",
        "Rec.ocr_version": "PP-OCRv5",
        "Rec.model_path": str(artifact_path(artifacts, "rapidocr_rec")),
        "Rec.rec_keys_path": str(
            artifact_path(artifacts, "rapidocr_rec_keys")
        ),
    }
    return params


def create_rapidocr_engine(artifacts: Sequence[LockedArtifact]) -> Any:
    from rapidocr import RapidOCR

    return RapidOCR(params=build_rapidocr_params(artifacts))
```

Task 1에서 잠긴 RapidOCR 버전의 공개 API가 위 key를 받지 않으면 임의로 우회하지
않고 실행을 중단한다. 해당 버전의 `rapidocr config` 출력과 공식 문서를 근거로 key
이름만 수정하는 별도 변경 승인을 받는다.

- [ ] **Step 4: 결과 정규화와 읽기 순서 구현**

```python
def _bbox(polygon: tuple[Point, ...]) -> BBox:
    xs = [point[0] for point in polygon]
    ys = [point[1] for point in polygon]
    return min(xs), min(ys), max(xs), max(ys)


def _reading_order_key(token: OcrToken) -> tuple[float, float]:
    return (round(token.bbox[1] / 10.0) * 10.0, token.bbox[0])


class RapidOcrRunner:
    def __init__(self, engine: Any, model_name: str) -> None:
        self._engine = engine
        self._model_name = model_name

    def recognize(
        self,
        image_path: Path,
        *,
        page_number: int,
    ) -> OcrPage:
        if image_path.suffix.lower() != ".png":
            raise RapidOcrError("RapidOCR accepts page PNG input only")
        pixmap = fitz.Pixmap(str(image_path))
        width, height = pixmap.width, pixmap.height
        result = self._engine(str(image_path))
        boxes = list(result.boxes or [])
        texts = list(result.txts or [])
        scores = list(result.scores or [])
        if not (len(boxes) == len(texts) == len(scores)):
            raise RapidOcrError("RapidOCR result lengths do not match")

        tokens = []
        for box, text, score in zip(boxes, texts, scores, strict=True):
            if not isinstance(text, str) or not text.strip():
                continue
            confidence = float(score)
            if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
                raise RapidOcrError("RapidOCR confidence is invalid")
            polygon = tuple((float(point[0]), float(point[1])) for point in box)
            if len(polygon) < 4:
                raise RapidOcrError("RapidOCR polygon has fewer than four points")
            bbox = _bbox(polygon)
            if (
                bbox[0] < 0
                or bbox[1] < 0
                or bbox[2] > width
                or bbox[3] > height
                or bbox[0] >= bbox[2]
                or bbox[1] >= bbox[3]
            ):
                raise RapidOcrError("RapidOCR coordinates are outside the page")
            tokens.append(
                OcrToken(
                    text=text.strip(),
                    recognition_confidence=confidence,
                    polygon=polygon,
                    bbox=bbox,
                    reading_order=0,
                    model_name=self._model_name,
                    source_page_number=page_number,
                )
            )
        if not tokens:
            raise RapidOcrError("RapidOCR returned no text")

        ordered = tuple(
            replace(token, reading_order=index)
            for index, token in enumerate(
                sorted(tokens, key=_reading_order_key)
            )
        )
        return OcrPage(
            page_number=page_number,
            engine="RAPIDOCR",
            model_name=self._model_name,
            markdown="\n".join(token.text for token in ordered),
            tokens=ordered,
            raw={
                "boxes": [
                    [[float(point[0]), float(point[1])] for point in box]
                    for box in boxes
                ],
                "txts": texts,
                "scores": [float(score) for score in scores],
            },
        )
```

engine 결과의 `boxes`, `txts`, `scores`를 길이 대조한 뒤 텍스트가 비어 있지 않은
모든 항목을 `OcrToken`으로 만든다. 읽기 순서는 위 y-band·x 정렬 후 0부터 다시
부여한다. `OcrPage.engine`은 `RAPIDOCR`, `model_name`은 잠금된 한국어 인식 모델명,
`markdown`은 정렬된 token text를 줄바꿈으로 연결한 값이다. 원본 engine 결과는
JSON 호환 형태로 `OcrPage.raw`에 보존한다.

- [ ] **Step 5: RapidOCR 단위 테스트 통과 확인**

Run:

```powershell
uv run --project tools/pdf-ocr pytest tools/pdf-ocr/tests/test_rapidocr_runner.py -q
```

Expected: 정상 결과와 모든 fail-closed 사례가 통과한다.

- [ ] **Step 6: 승인된 로컬 모델 1장 smoke 확인**

Run:

```powershell
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
uv run --project tools/pdf-ocr python -m pdf_ocr.cli --help
```

Expected: 네트워크 요청 없이 CLI import와 RapidOCR factory 사전조건 검사가 성공한다.
실제 OCR 모델 초기화와 이미지 인식은 모델 다운로드·테스트 실행 승인을 함께 받은
경우에만 수행한다.

- [ ] **Step 7: 승인된 경우에만 Task 단위 커밋**

```powershell
git add tools/pdf-ocr/src/pdf_ocr/ocr.py tools/pdf-ocr/tests/test_rapidocr_runner.py
git commit -m "feat(pdf-ocr): add RapidOCR audit runner"
```

---

### Task 5: Docling 레이아웃 패스와 TableFormer 구조 패스

**Files:**

- Create: `tools/pdf-ocr/src/pdf_ocr/structure.py`
- Create: `tools/pdf-ocr/tests/test_docling_structure.py`

**Interfaces:**

- Consumes: 잠금된 Docling artifact root와 RapidOCR det/rec 경로
- Produces: `DoclingStructureError`
- Produces: `create_layout_converter(artifacts: Sequence[LockedArtifact]) -> Any`
- Produces: `create_table_converter(artifacts: Sequence[LockedArtifact]) -> Any`
- Produces: `DoclingRunner.detect_layout(image_path: Path, *, page_number: int) -> LayoutPage`
- Produces: `DoclingRunner.recognize_tables(image_path: Path, *, page_number: int) -> StructurePage`

- [ ] **Step 1: 두 패스 설정의 실패 테스트 작성**

```python
def test_layout_pass_disables_ocr_and_tableformer(locked_artifacts) -> None:
    options = build_layout_pipeline_options(locked_artifacts)
    assert options.do_ocr is False
    assert options.do_table_structure is False
    assert options.enable_remote_services is False
    assert options.artifacts_path is not None


def test_table_pass_uses_rapidocr_and_accurate_tableformer(
    locked_artifacts,
) -> None:
    options = build_table_pipeline_options(locked_artifacts)
    assert options.do_ocr is True
    assert options.do_table_structure is True
    assert options.ocr_options.backend == "onnxruntime"
    assert options.ocr_options.text_score == 0.0
    assert options.table_structure_options.mode.value == "accurate"
```

두 converter가 `InputFormat.IMAGE`와 `ImageFormatOption`만 등록하는지, `.pdf` 입력을
거부하는지, partial/failed conversion을 성공으로 취급하지 않는지도 테스트한다.

- [ ] **Step 2: 병합셀 정규화 실패 테스트 작성**

Docling test double은 다음 원시 셀을 반환한다.

```python
raw_cells = [
    {
        "text": "구분",
        "bbox": [0, 0, 100, 40],
        "start_row_offset_idx": 0,
        "end_row_offset_idx": 2,
        "start_col_offset_idx": 0,
        "end_col_offset_idx": 1,
        "column_header": True,
        "row_header": False,
    },
    {
        "text": "면적",
        "bbox": [100, 0, 200, 20],
        "start_row_offset_idx": 0,
        "end_row_offset_idx": 1,
        "start_col_offset_idx": 1,
        "end_col_offset_idx": 2,
        "column_header": True,
        "row_header": False,
    },
    {
        "text": "㎡",
        "bbox": [100, 20, 200, 40],
        "start_row_offset_idx": 1,
        "end_row_offset_idx": 2,
        "start_col_offset_idx": 1,
        "end_col_offset_idx": 2,
        "column_header": True,
        "row_header": False,
    },
]
```

첫 셀의 `row_span == 2`, HTML의 `rowspan="2"`, `num_rows == 2`,
`num_columns == 2`를 단언한다.

- [ ] **Step 3: 실패 확인**

Run:

```powershell
uv run --project tools/pdf-ocr pytest tools/pdf-ocr/tests/test_docling_structure.py -q
```

Expected: `pdf_ocr.structure`가 없어 실패한다.

- [ ] **Step 4: 레이아웃 전용 옵션 구현**

```python
from docling.datamodel.base_models import ConversionStatus, InputFormat
from docling.datamodel.pipeline_options import (
    PdfPipelineOptions,
    RapidOcrOptions,
    TableFormerMode,
    TableStructureOptions,
)
from docling.document_converter import DocumentConverter, ImageFormatOption


def build_layout_pipeline_options(
    artifacts: Sequence[LockedArtifact],
) -> PdfPipelineOptions:
    options = PdfPipelineOptions(
        artifacts_path=str(docling_artifacts_root(artifacts)),
        do_ocr=False,
        do_table_structure=False,
        enable_remote_services=False,
        allow_external_plugins=False,
    )
    return options
```

converter는 다음 경계로 만든다.

```python
DocumentConverter(
    allowed_formats=[InputFormat.IMAGE],
    format_options={
        InputFormat.IMAGE: ImageFormatOption(
            pipeline_options=build_layout_pipeline_options(artifacts)
        )
    },
)
```

- [ ] **Step 5: 표 전용 옵션 구현**

```python
def build_table_pipeline_options(
    artifacts: Sequence[LockedArtifact],
) -> PdfPipelineOptions:
    options = PdfPipelineOptions(
        artifacts_path=str(docling_artifacts_root(artifacts)),
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
        det_model_path=str(artifact_path(artifacts, "rapidocr_det")),
        rec_model_path=str(artifact_path(artifacts, "rapidocr_rec")),
        rec_keys_path=str(artifact_path(artifacts, "rapidocr_rec_keys")),
        font_path=str(artifact_path(artifacts, "rapidocr_font")),
        print_verbose=False,
    )
    options.table_structure_options = TableStructureOptions(
        do_cell_matching=True,
        mode=TableFormerMode.ACCURATE,
    )
    return options
```

Docling의 `artifacts_path`는 사전 다운로드된 로컬 디렉터리만 가리키며
`enable_remote_services=False`를 유지한다.

- [ ] **Step 6: Docling 결과를 내부 타입으로 정규화**

`detect_layout()`은 Docling item의 label·bbox·reading order를 `LayoutRegion`으로
바꾸고 table label 존재 여부를 `has_table`로 기록한다. 복합 레이아웃은 다음 고정
함수로 판정한다.

```python
class DoclingStructureError(RuntimeError):
    pass


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
    if source_width <= 0 or source_height <= 0:
        raise DoclingStructureError("Docling coordinate space is invalid")
    if origin == "BOTTOMLEFT":
        top, bottom = source_height - bottom, source_height - top
    elif origin != "TOPLEFT":
        raise DoclingStructureError("Docling coordinate origin is unknown")
    bbox = (
        left * image_width / source_width,
        top * image_height / source_height,
        right * image_width / source_width,
        bottom * image_height / source_height,
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
        raise DoclingStructureError("Docling bbox is outside the page image")
    return bbox


def _has_complex_layout(
    regions: Sequence[LayoutRegion],
    width: int,
) -> bool:
    text_like = [
        region
        for region in regions
        if region.label in {"text", "list_item", "section_header", "caption"}
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
```

표는 `has_table`이 별도 우선 경로를 결정하므로 위 함수의 `non_text_structure`에
포함하지 않는다.

두 public method는 먼저 다음 공통 경계를 통과한다.

```python
def _convert_single_png(converter: Any, image_path: Path) -> Any:
    if image_path.suffix.lower() != ".png":
        raise DoclingStructureError("Docling accepts page PNG input only")
    result = converter.convert(str(image_path))
    if result.status is not ConversionStatus.SUCCESS:
        raise DoclingStructureError(
            f"Docling conversion did not fully succeed: {result.status}"
        )
    if len(result.pages) != 1:
        raise DoclingStructureError("Docling image conversion must have one page")
    return result
```

`result.document.iterate_items()`의 각 `(item, level)`에서 `item.prov[0].bbox`와
label을 읽고, Docling page size와 실제 PNG size를 위
`_top_left_pixel_bbox()`에 전달한다. provenance가 없거나 여러 원본 page를 가리키면
실패한다. 원본 PDF page number는 Docling 내부 page number를 사용하지 않고 method
인자 `page_number`를 모든 내부 타입에 다시 결합한다.

`recognize_tables()`는 table item의 `data.num_rows`, `data.num_cols`,
`table_cells`를 `TableData`와 `TableCell`로 변환한다. Docling export JSON 원본은
`StructurePage.raw`에 JSON 호환 형태로 보존하고, HTML은 Docling의 lossless table
export를 사용한다. Task 6 대조 전 모든 cell의
`raw_ocr_comparison_status`는 `NOT_COMPARABLE`이다. table label은 탐지됐지만
rows·columns·cells가 하나라도 비면 `DoclingStructureError`를 발생시킨다.

- [ ] **Step 7: Docling 구조 테스트 통과 확인**

Run:

```powershell
uv run --project tools/pdf-ocr pytest tools/pdf-ocr/tests/test_docling_structure.py -q
```

Expected: 패스 설정·이미지 전용 입력·병합셀·partial result 실패 사례가 모두 통과한다.

- [ ] **Step 8: 승인된 경우에만 Task 단위 커밋**

```powershell
git add tools/pdf-ocr/src/pdf_ocr/structure.py tools/pdf-ocr/tests/test_docling_structure.py
git commit -m "feat(pdf-ocr): add Docling TableFormer structure runner"
```

---

### Task 6: OCR·표 대조와 페이지 산출물 직렬화

**Files:**

- Create: `tools/pdf-ocr/src/pdf_ocr/artifacts.py`
- Modify: `tools/pdf-ocr/tests/test_artifacts.py`

**Interfaces:**

- Consumes: `OcrPage`, `LayoutPage`, `StructurePage`, `PageRoute`
- Produces: `compare_table_cells(ocr_page: OcrPage, structure_page: StructurePage) -> StructurePage`
- Produces: `write_page_artifacts(root: Path, image_path: Path, route: PageRoute, ocr_page: OcrPage, structure_page: StructurePage) -> PageArtifactSet`
- Produces: `file_record(path: Path, root: Path) -> dict[str, object]`

- [ ] **Step 1: OCR와 표 셀 대조의 실패 테스트 작성**

```python
def test_table_cell_mismatch_is_preserved_for_human_review() -> None:
    ocr_page = ocr_fixture(text="면적 120㎡", bbox=(100, 20, 190, 40))
    structure_page = structure_fixture(
        cell_text="면적 12㎡",
        cell_bbox=(90, 10, 200, 50),
    )

    compared = compare_table_cells(ocr_page, structure_page)

    assert (
        compared.tables[0].cells[0].raw_ocr_comparison_status
        == "MISMATCH"
    )
```

추가 사례는 다음과 같다.

- NFKC 정규화와 공백 제거 후 같은 문자열은 `MATCHED`
- 셀 bbox 안에 중심점이 있는 OCR token만 비교
- OCR과 셀 텍스트가 모두 비면 `NOT_COMPARABLE`
- 한쪽만 비거나 정규화 문자열이 다르면 `MISMATCH`
- 교차 페이지 표를 자동으로 합치지 않고 각 페이지 표를 독립 보존

- [ ] **Step 2: 산출물 원자성·파일명·해시 실패 테스트 작성**

```python
def test_page_artifacts_use_fixed_names_and_hashes(tmp_path: Path) -> None:
    artifact_set = write_page_artifacts(
        root=tmp_path,
        image_path=write_png(tmp_path / "pages" / "0001.png"),
        route=PageRoute.RAPIDOCR_TABLEFORMER,
        ocr_page=ocr_fixture(page_number=1),
        structure_page=structure_fixture(page_number=1),
    )

    assert artifact_set.ocr["file_name"] == "pages/0001.ocr.json"
    assert artifact_set.structure["file_name"] == "pages/0001.structure.json"
    assert artifact_set.markdown["file_name"] == "pages/0001.md"
    assert artifact_set.tables[0]["file_name"] == (
        "pages/0001.tables/0001.html"
    )
    assert artifact_set.ocr["sha256"].startswith("sha256:")
```

빈 Markdown, 빈 HTML, 빈 JSON, page number 불일치, 표 수와 HTML 수 불일치는 게시 전에
`ArtifactError`가 발생해야 한다. `row_span > 1` 또는 `col_span > 1`인 cell이 있는데
HTML에 같은 값의 `rowspan` 또는 `colspan`이 없을 때도 실패해야 한다.

- [ ] **Step 3: 실패 확인**

Run:

```powershell
uv run --project tools/pdf-ocr pytest tools/pdf-ocr/tests/test_artifacts.py -q
```

Expected: 대조·직렬화 함수가 없어 실패한다.

- [ ] **Step 4: 보수적 셀 대조 구현**

```python
from dataclasses import replace


def _normalized_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value)
    return "".join(character for character in normalized if not character.isspace())


def _token_center_inside(token: OcrToken, cell: TableCell) -> bool:
    x0, y0, x1, y1 = token.bbox
    center_x = (x0 + x1) / 2.0
    center_y = (y0 + y1) / 2.0
    cx0, cy0, cx1, cy1 = cell.bbox
    return cx0 <= center_x <= cx1 and cy0 <= center_y <= cy1


def compare_table_cells(
    ocr_page: OcrPage,
    structure_page: StructurePage,
) -> StructurePage:
    compared_tables = []
    for table in structure_page.tables:
        compared_cells = []
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
            elif normalized_raw == normalized_cell:
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
```

셀마다 포함된 token을 `reading_order`로 정렬해 연결한다. 두 정규화 문자열이 정확히
같을 때만 `MATCHED`로 두며 유사도 기반 자동 일치는 사용하지 않는다.

- [ ] **Step 5: 페이지 JSON·Markdown·HTML writer 구현**

```python
@dataclass(frozen=True)
class PageArtifactSet:
    image: dict[str, object]
    ocr: dict[str, object]
    structure: dict[str, object]
    markdown: dict[str, object]
    tables: tuple[dict[str, object], ...]
```

`write_page_artifacts()`는 먼저 메모리 payload를 만들고
`validate_ocr_page()`·`validate_structure_page()`·`validate_table_topology()`를
통과시킨 다음 파일을 쓴다. JSON은 UTF-8, `ensure_ascii=False`, 2칸 들여쓰기,
마지막 newline을 사용한다. Markdown은 `OcrPage.markdown`, 표 HTML은
`TableData.html`을 수정하지 않고 UTF-8로 저장한다.

`minimum_confidence`는 token confidence 최솟값이며 직접 RapidOCR가 필요한 경로에서
token이 없으면 쓰기 전에 실패한다. 모든 파일 기록은 상대 POSIX 경로, byte 수,
`sha256:` 접두어가 있는 소문자 SHA-256을 갖는다.

표 HTML은 저장 전에 다음 불변조건을 검사한다.

```python
def validate_table_html(table: TableData) -> None:
    if "<table" not in table.html.lower() or "</table>" not in table.html.lower():
        raise ArtifactError("table HTML has no table element")
    for cell in table.cells:
        if cell.row_span > 1 and f'rowspan="{cell.row_span}"' not in table.html:
            raise ArtifactError("table HTML lost rowspan")
        if cell.col_span > 1 and f'colspan="{cell.col_span}"' not in table.html:
            raise ArtifactError("table HTML lost colspan")
```

- [ ] **Step 6: 산출물 테스트 통과 확인**

Run:

```powershell
uv run --project tools/pdf-ocr pytest tools/pdf-ocr/tests/test_artifacts.py -q
```

Expected: 대조 상태, 파일명, JSON·HTML·Markdown, 해시와 빈 출력 실패 사례가 모두
통과한다.

- [ ] **Step 7: 승인된 경우에만 Task 단위 커밋**

```powershell
git add tools/pdf-ocr/src/pdf_ocr/artifacts.py tools/pdf-ocr/tests/test_artifacts.py
git commit -m "feat(pdf-ocr): serialize auditable page artifacts"
```

---

### Task 7: 페이지 오케스트레이션과 원자 게시

**Files:**

- Modify: `tools/pdf-ocr/src/pdf_ocr/pipeline.py:1-571`
- Modify: `tools/pdf-ocr/tests/test_pipeline_integration.py:1-278`
- Modify: `tools/pdf-ocr/tests/test_pipeline_fail_closed.py:1-169`

**Interfaces:**

- Consumes: `collect_runtime_info`, `load_model_lock`, `DoclingRunner`, `RapidOcrRunner`, `select_page_route`, `write_page_artifacts`
- Produces: `extract_pdf(input_path: Path, output_dir: Path, *, ocr_runner: OcrRunner | None = None, structure_runner: StructureRunner | None = None, model_lock_path: Path | None = None, model_home: Path | None = None, uv_lock_path: Path | None = None) -> Path`
- Produces: `OcrRunner`와 `StructureRunner` Protocol
- Produces: `embedded_text_page(page: fitz.Page, text: str, page_number: int) -> OcrPage`
- Produces: `structure_from_layout(layout: LayoutPage) -> StructurePage`
- Produces: `any_cell_status(page: StructurePage, status: str) -> bool`
- Produces: `has_merged_or_multilevel_header(page: StructurePage) -> bool`
- Produces: `has_possible_cross_page_table(page: StructurePage) -> bool`
- Preserves: `PdfOcrError`, `OutputExistsError`, `.pdf-ocr-staging-owner`

- [ ] **Step 1: 모든 페이지 레이아웃 1차 패스 테스트 작성**

```python
def test_every_page_runs_layout_before_route_selection(tmp_path: Path) -> None:
    pdf = write_two_page_pdf(
        tmp_path / "notice.pdf",
        first_text="서울특별시 고시 제2026-1호 " * 4,
        second_text="",
    )
    structure = RecordingStructureRunner(
        layouts=[
            layout_page(page_number=1, has_table=False),
            layout_page(page_number=2, has_table=False),
        ]
    )
    ocr = RecordingRapidOcrRunner()

    extract_pdf(
        pdf,
        tmp_path / "result",
        ocr_runner=ocr,
        structure_runner=structure,
        model_lock_path=fixture_model_lock(tmp_path),
        model_home=tmp_path / "models",
        uv_lock_path=fixture_uv_lock(tmp_path),
    )

    assert structure.layout_pages == [1, 2]
    assert structure.table_pages == []
    assert ocr.pages == [2]
```

- [ ] **Step 2: 표 페이지의 이중 OCR·TableFormer 테스트 작성**

```python
def test_table_page_runs_audit_ocr_and_tableformer(tmp_path: Path) -> None:
    structure = RecordingStructureRunner(
        layouts=[layout_page(page_number=1, has_table=True)],
        tables=[structure_page(page_number=1)],
    )
    ocr = RecordingRapidOcrRunner()

    manifest = run_fixture_pipeline(tmp_path, ocr=ocr, structure=structure)

    assert ocr.pages == [1]
    assert structure.table_pages == [1]
    assert manifest["pages"][0]["route"] == "RAPIDOCR_TABLEFORMER"
    assert {
        item["kind"] for item in manifest["pages"][0]["outputs"]
    } == {"OCR_JSON", "STRUCTURE_JSON", "MARKDOWN", "TABLE_HTML"}
```

내장 텍스트가 충분해도 표가 탐지되면 표 경로가 우선하는 사례와, 표가 없는 복합 페이지는
직접 RapidOCR만 실행하고 TableFormer를 실행하지 않는 사례도 작성한다.

- [ ] **Step 3: fail-closed 통합 사례 작성**

`test_pipeline_fail_closed.py`에 다음 각 실패가 최종 출력 디렉터리를 만들지 않고 소유권
표식이 있는 해당 실행의 staging만 정리하는지 확인한다.

- 레이아웃 패스 예외 또는 partial result
- 직접 RapidOCR 빈 결과
- table label이 있으나 rows·columns·cells 중 하나가 비어 있음
- 겹치거나 범위를 벗어난 셀
- page number 불일치 또는 페이지 누락
- PDF↔PNG 좌표 변환 불가능
- 페이지 JSON·HTML·Markdown 중 하나가 비어 있음
- 스키마 또는 출력 SHA-256 불일치
- 처리 중 입력 PDF SHA-256 변경
- 동일 이름의 최종 출력이 처리 도중 생성됨
- native child 비정상 종료 후 wrapper가 소유한 staging 정리

- [ ] **Step 4: 실패 확인**

Run:

```powershell
uv run --project tools/pdf-ocr pytest tools/pdf-ocr/tests/test_pipeline_integration.py tools/pdf-ocr/tests/test_pipeline_fail_closed.py -q
```

Expected: 기존 Paddle 전용 runner signature와 신규 구조 runner 부재로 실패한다.

- [ ] **Step 5: PDF 경계를 유지하고 오케스트레이터 축소**

`extract_pdf()`는 기존 pypdf·PyMuPDF 검사, 입력 전후 SHA-256, 300 DPI PNG,
staging owner marker, 최종 rename을 유지한다. 페이지 처리 순서는 정확히 다음이다.

```python
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


layout = structure_runner.detect_layout(
    image_path,
    page_number=page_number,
)
route = select_page_route(
    embedded_text,
    has_table=layout.has_table,
    has_complex_layout=layout.has_complex_layout,
)

if route is PageRoute.EMBEDDED_TEXT:
    ocr_page = embedded_text_page(fitz_page, embedded_text, page_number)
    structure_page = structure_from_layout(layout)
elif route is PageRoute.RAPIDOCR:
    ocr_page = ocr_runner.recognize(image_path, page_number=page_number)
    structure_page = structure_from_layout(layout)
else:
    ocr_page = ocr_runner.recognize(image_path, page_number=page_number)
    structure_page = structure_runner.recognize_tables(
        image_path,
        page_number=page_number,
    )
    structure_page = compare_table_cells(ocr_page, structure_page)
```

factory는 주입된 test double이 없을 때에만 실제 RapidOCR·Docling runner를 생성한다.
Docling에는 `image_path`만 전달하고 `input_path`는 전달하지 않는다.
`embedded_text_page()`는 PyMuPDF block 좌표를 pixel 좌표로 `300 / 72`배 변환하고
confidence `1.0`, model name `embedded-text`를 기록한다.
`structure_from_layout()`은 같은 page·width·height·regions와 빈 `tables`를 가진
`StructurePage`를 반환한다.

```python
def embedded_text_page(
    page: fitz.Page,
    text: str,
    page_number: int,
) -> OcrPage:
    scale = 300.0 / 72.0
    tokens = []
    for order, block in enumerate(page.get_text("blocks")):
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
                bbox=bbox,
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
```

- [ ] **Step 6: 좌표와 검수 상태를 매니페스트에 기록**

PNG pixel에서 PDF point로의 배율은 `72 / 300 == 0.24`로 기록한다.
매니페스트 page의 review reason은 다음 규칙으로 계산한다.

매니페스트 runtime의 `model_files`는 잠금 bundle을 파일 단위로 펼친 다음
`component`, `role`, `name`, `source_url`, `license`, 모델 root 상대 `file_name`,
`bytes`, `sha256`을 기록한다. 절대 로컬 모델 경로는 기록하지 않는다.
`rapidocr_version`, `onnxruntime_version`, `docling_version`,
`docling_ibm_models_version`은 `RuntimeInfo.package_versions`에서,
`execution_provider`는 `RuntimeInfo.execution_provider`에서 가져온다.

```python
reasons = {
    "NOTICE_NUMBER",
    "LEGAL_DATE",
    "AREA",
    "JURISDICTION",
    "TAX_RULE",
    "LEGAL_EFFECT",
    "SPATIAL_BOUNDARY",
    "SOURCE_RIGHTS",
}
if minimum_confidence is not None and minimum_confidence < 0.90:
    reasons.add("LOW_CONFIDENCE")
if any_cell_status(structure_page, "MISMATCH"):
    reasons.add("OCR_TABLE_MISMATCH")
if has_merged_or_multilevel_header(structure_page):
    reasons.add("MERGED_OR_MULTILEVEL_HEADER")
if has_possible_cross_page_table(structure_page):
    reasons.add("POSSIBLE_CROSS_PAGE_TABLE")
```

helper는 다음과 같이 고정한다.

```python
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
```

모든 page의 review status는 실제 사람 검수 완료 전
`PENDING_HUMAN_REVIEW`로 쓴다. 매니페스트 retention은
`TEMPORARY_NOT_RETAINED`, source rights는 `PENDING_REVIEW`를 유지한다.

- [ ] **Step 7: 게시 직전 전체 계약·해시 연쇄 검증**

모든 페이지가 끝난 뒤 `validate_manifest()`와
`validate_output_hashes(manifest, staging_dir)`를 실행한다. 입력 PDF 해시도 다시
계산한다. 하나라도 실패하면 staging을 정리하고 최종 디렉터리를 만들지 않는다.
모두 성공한 뒤에만 owner marker를 지우고 `staging_dir.rename(output_dir)`을 수행한다.

- [ ] **Step 8: 통합·fail-closed 테스트 통과 확인**

Run:

```powershell
uv run --project tools/pdf-ocr pytest tools/pdf-ocr/tests/test_pipeline_integration.py tools/pdf-ocr/tests/test_pipeline_fail_closed.py -q
```

Expected: 신규 3경로, 모든 페이지 레이아웃, 표 이중 처리, 좌표·검수·원자 게시 사례가
통과한다.

- [ ] **Step 9: 승인된 경우에만 Task 단위 커밋**

```powershell
git add tools/pdf-ocr/src/pdf_ocr/pipeline.py tools/pdf-ocr/tests/test_pipeline_integration.py tools/pdf-ocr/tests/test_pipeline_fail_closed.py
git commit -m "feat(pdf-ocr): orchestrate RapidOCR and TableFormer pages"
```

---

### Task 8: CLI·PowerShell·컨테이너 오프라인 실행

**Files:**

- Modify: `tools/pdf-ocr/src/pdf_ocr/cli.py:1-60`
- Modify: `scripts/research/extract-pdf.ps1:1-100`
- Modify: `tools/pdf-ocr/Dockerfile:1-31`
- Modify: `tools/pdf-ocr/tests/test_research_samples.py:1-164`

**Interfaces:**

- Produces: `python -m pdf_ocr.cli --input PDF --output DIR --model-lock LOCK --model-home DIR --uv-lock LOCK`
- Produces: `extract-pdf.ps1 -InputPath PDF -OutputDirectory DIR -ModelLockPath LOCK -ModelHome DIR`
- Requires: `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`, `DOCLING_ARTIFACTS_PATH`, `PDF_OCR_MODEL_HOME`

- [ ] **Step 1: CLI 인자와 wrapper 환경 실패 테스트 작성**

```python
def test_cli_requires_existing_model_home(tmp_path: Path) -> None:
    parser = build_parser()
    args = parser.parse_args(
        [
            "--input", str(tmp_path / "a.pdf"),
            "--output", str(tmp_path / "out"),
            "--model-lock", str(tmp_path / "models.lock.json"),
            "--model-home", str(tmp_path / "missing-models"),
            "--uv-lock", str(tmp_path / "uv.lock"),
        ]
    )
    with pytest.raises(PdfOcrError, match="model home"):
        validate_cli_paths(args)
```

`test_research_samples.py`의 가짜 `uv` 실행기는 전달된 인자에 `--frozen`이 있고,
자식 환경에 `HF_HUB_OFFLINE=1`, `TRANSFORMERS_OFFLINE=1`,
`PDF_OCR_MODEL_HOME=<승인 경로>`가 있는지 기록한다. 하나라도 없으면 wrapper 테스트가
실패하게 한다.

- [ ] **Step 2: 실패 확인**

Run:

```powershell
uv run --project tools/pdf-ocr pytest tools/pdf-ocr/tests/test_research_samples.py -q
```

Expected: 신규 인자와 offline 환경이 없어 실패한다.

- [ ] **Step 3: CLI 경로 전달 구현**

```python
parser.add_argument("--model-lock", type=Path, required=True)
parser.add_argument("--model-home", type=Path, required=True)
parser.add_argument("--uv-lock", type=Path, required=True)
```

세 경로를 resolve하고 각각 file/directory 여부를 확인한 뒤 `extract_pdf()`에 전달한다.
실패 응답은 기존처럼 UTF-8 JSON과 종료 코드 1을 사용하며 부분 성공 상태는 만들지 않는다.

- [ ] **Step 4: PowerShell wrapper를 frozen·offline으로 변경**

```powershell
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
$env:PDF_OCR_MODEL_HOME = $absoluteModelHome
$env:DOCLING_ARTIFACTS_PATH = $absoluteModelHome

& uv run `
    --frozen `
    --project "tools/pdf-ocr" `
    python -m pdf_ocr.cli `
    --input $absoluteInputPath `
    --output $absoluteOutputDirectory `
    --model-lock $absoluteModelLockPath `
    --model-home $absoluteModelHome `
    --uv-lock (Join-Path $repositoryRoot "tools\pdf-ocr\uv.lock")
```

wrapper는 기존 owner marker 값 `pdf-ocr-owned-staging-v1`과 같은 parent/prefix 검사 후
자신의 staging만 정리하는 로직을 유지한다.

- [ ] **Step 5: Dockerfile을 Paddle-free runtime으로 교체**

```dockerfile
FROM python:3.12.13-slim-bookworm

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    HF_HUB_OFFLINE=1 \
    TRANSFORMERS_OFFLINE=1 \
    PDF_OCR_MODEL_HOME=/models \
    DOCLING_ARTIFACTS_PATH=/models
```

`uv sync --frozen --no-dev`와 비루트 `pdfocr` 사용자는 유지한다. 빌드 중 factory를
초기화하거나 모델을 다운로드하는 기존 `RUN create_ocr_pipeline()` 단계는 삭제한다.
모델은 런타임에 읽기 전용 `/models` volume으로 제공하고 모델 잠금 검증 실패 시
entrypoint가 종료 코드 1로 끝난다.

- [ ] **Step 6: wrapper 회귀 테스트 통과 확인**

Run:

```powershell
uv run --project tools/pdf-ocr pytest tools/pdf-ocr/tests/test_research_samples.py -q
```

Expected: 성공 JSON, 덮어쓰기 거부, native child crash staging 정리, frozen/offline
환경 사례가 모두 통과한다.

- [ ] **Step 7: 승인된 경우에만 Task 단위 커밋**

```powershell
git add tools/pdf-ocr/src/pdf_ocr/cli.py scripts/research/extract-pdf.ps1 tools/pdf-ocr/Dockerfile tools/pdf-ocr/tests/test_research_samples.py
git commit -m "build(pdf-ocr): enforce frozen offline execution"
```

---

### Task 9: T112 한정 회귀와 실제 관보 네 건 사람 검수

**Files:**

- Test: `tools/pdf-ocr/tests/test_runtime.py`
- Test: `tools/pdf-ocr/tests/test_model_lock.py`
- Test: `tools/pdf-ocr/tests/test_router.py`
- Test: `tools/pdf-ocr/tests/test_manifest_schema.py`
- Test: `tools/pdf-ocr/tests/test_rapidocr_runner.py`
- Test: `tools/pdf-ocr/tests/test_docling_structure.py`
- Test: `tools/pdf-ocr/tests/test_artifacts.py`
- Test: `tools/pdf-ocr/tests/test_pipeline_integration.py`
- Test: `tools/pdf-ocr/tests/test_pipeline_fail_closed.py`
- Test: `tools/pdf-ocr/tests/test_research_samples.py`
- Create: `specs/001-real-estate-policy-dashboard/research-data/pdf-ocr-acceptance.md`

**Interfaces:**

- Consumes: 실제 모델 잠금과 네 승인 PDF
- Produces: 네 출력 디렉터리의 `pdf-ocr-manifest.json`
- Produces: 사람 대조 기록 `pdf-ocr-acceptance.md`

- [ ] **Step 1: T112 전용 자동 회귀만 실행**

Run:

```powershell
uv run --project tools/pdf-ocr pytest tools/pdf-ocr/tests -q
```

Expected: T112 전용 테스트만 모두 통과한다. 다른 프로젝트 디렉터리의 테스트는 실행하지
않는다.

- [ ] **Step 2: 실제 모델 파일·잠금·CPU provider 사전검사**

Run:

```powershell
$env:PDF_OCR_MODEL_HOME = (Resolve-Path $env:PDF_OCR_MODEL_HOME).Path
$env:HF_HUB_OFFLINE = "1"
$env:TRANSFORMERS_OFFLINE = "1"
uv run --project tools/pdf-ocr --frozen python -c "from pathlib import Path; from pdf_ocr.runtime import collect_runtime_info; from pdf_ocr.model_lock import load_model_lock; info=collect_runtime_info(Path('tools/pdf-ocr/uv.lock')); artifacts=load_model_lock(Path('tools/pdf-ocr/models.lock.json'), Path(r'$env:PDF_OCR_MODEL_HOME'), info.package_versions); print(info); print(len(artifacts))"
```

Expected: 잠금 패키지 버전이 일치하고 `CPUExecutionProvider`가 선택되며 모든 모델
파일의 크기·SHA-256 검증이 끝난다. 모델 다운로드 로그나 네트워크 요청이 없어야 한다.

- [ ] **Step 3: 네 승인 PDF를 각각 독립 출력으로 처리**

Run:

```powershell
$samples = @('2017-114', '2018-151', '2022-189', '2023-001')
foreach ($sample in $samples) {
    powershell -NoProfile -ExecutionPolicy Bypass `
        -File scripts/research/extract-pdf.ps1 `
        -InputPath "specs/001-real-estate-policy-dashboard/research-data/captures/gazette/$sample.pdf" `
        -OutputDirectory "temp/pdf-ocr-acceptance/$sample" `
        -ModelLockPath "tools/pdf-ocr/models.lock.json" `
        -ModelHome $env:PDF_OCR_MODEL_HOME
    if ($LASTEXITCODE -ne 0) {
        throw "PDF recognition failed: $sample"
    }
}
```

Expected: 네 건 모두 종료 코드 0이며 각 출력에 page gap 없는
`pdf-ocr-manifest.json`이 있다. 하나라도 실패하면 T112를 완료 처리하지 않는다.

- [ ] **Step 4: 표와 핵심 법적 필드를 모든 페이지에서 사람 대조**

`pdf-ocr-acceptance.md`는 한국어 섹션을 먼저 만들고 PDF별로 다음 값을 빠짐없이
기록한다.

```markdown
## 2017-114.pdf

- 원본 SHA-256:
- 매니페스트 SHA-256:
- 전체 페이지 수:
- 처리된 페이지 수:
- 페이지 누락:
- 탐지된 표 수:

| 페이지 | 표 번호 | 원문 행×열 | 결과 행×열 | 병합셀 원문 | 병합셀 결과 | 판정 |
|---:|---:|---:|---:|---|---|---|

| 핵심 필드 | 원문 값 | OCR/표 값 | 페이지 | 판정 | 검수자 | 검수 시각 |
|---|---|---|---:|---|---|---|
| 공고번호 |  |  |  |  |  |  |
| 법적 날짜 |  |  |  |  |  |  |
| 면적 |  |  |  |  |  |  |
| 지역·관할 |  |  |  |  |  |  |
| 세금 규칙 |  |  |  |  |  |  |
| 법적 효력 |  |  |  |  |  |  |
| 공간 경계 |  |  |  |  |  |  |
| 원문 이용권한 |  |  |  |  |  |  |
```

빈 칸을 남긴 보고서는 완료 증거가 아니다. 표가 없는 PDF·페이지는 원문 육안 확인 후
“표 없음”과 확인 페이지를 기록한다. 교차 페이지 표, 다단 헤더, 병합셀은 각각 원문
페이지와 JSON의 0-based half-open range를 함께 기록한다. 문서에 해당하지 않는
핵심 필드는 빈 칸 대신 `NOT_APPLICABLE`과 원문 근거를 기록한다.

- [ ] **Step 5: 불변 매니페스트와 별도 사람 검수 판정을 연결**

파이프라인이 원자적으로 게시한 매니페스트는 수정하지 않고 page review status
`PENDING_HUMAN_REVIEW`를 유지한다. `pdf-ocr-acceptance.md`에서 각 page를
`HUMAN_REVIEWED` 또는 `REJECTED`로 판정하고 해당 입력 PDF SHA-256,
매니페스트 SHA-256, page number를 연결한다. 필수 항목과 모든 표 topology가 원문과
일치한 경우에만 보고서의 page 판정을 `HUMAN_REVIEWED`로 기록한다. 불일치·빈 칸이
하나라도 있으면 `REJECTED`로 기록하고 T112를 미완료로 둔다.

- [ ] **Step 6: 영문 AI context를 같은 보고서 뒤에 추가**

```yaml
acceptance_id: T112_RAPIDOCR_DOCLING_GAZETTE
samples:
  - 2017-114.pdf
  - 2018-151.pdf
  - 2022-189.pdf
  - 2023-001.pdf
required_status: HUMAN_REVIEWED
checks:
  - all_pages_processed
  - no_page_gaps
  - table_count
  - row_column_count
  - merged_cell_ranges
  - critical_legal_fields
  - complete_sha256_chain
publication_authorized: false
rag_authorized: false
```

- [ ] **Step 7: 승인된 경우에만 검수 증거 커밋**

실제 OCR 출력은 기본 보존 상태가 `TEMPORARY_NOT_RETAINED`이므로 저장소에
`temp/pdf-ocr-acceptance/`를 추가하지 않는다. 사람 대조 보고서만 별도 승인된 경우
커밋한다.

```powershell
git add specs/001-real-estate-policy-dashboard/research-data/pdf-ocr-acceptance.md
git commit -m "docs(research): record T112 PDF acceptance"
```

---

### Task 10: 고지·Spec Kit 조사 문서·T112 게이트 갱신

**Files:**

- Modify: `THIRD_PARTY_NOTICES.md`
- Modify: `specs/001-real-estate-policy-dashboard/spec.md:203`
- Modify: `specs/001-real-estate-policy-dashboard/plan.md:32,117-118,367-371`
- Modify: `specs/001-real-estate-policy-dashboard/research.md:174-208,318-328,373-378`
- Modify: `specs/001-real-estate-policy-dashboard/tasks.md:34,51-56,363`
- Modify: `specs/001-real-estate-policy-dashboard/source-register.md:271-307,373-393`
- Modify: `specs/001-real-estate-policy-dashboard/research-data/README.md:122-168`
- Modify: `specs/001-real-estate-policy-dashboard/checklists/research-readiness.md:108-135,198`
- Modify: `specs/001-real-estate-policy-dashboard/research-data/cutoff-manifest.csv`
- Modify: `docs/superpowers/specs/2026-07-28-rapidocr-docling-pdf-recognition-design.md:1-12,379-544`
- Modify: `docs/superpowers/specs/2026-07-28-paddleocr-pdf-recognition-design.md:1-12`
- Modify: `docs/superpowers/plans/2026-07-28-paddleocr-pdf-recognition.md:1-20`
- Include: `docs/superpowers/plans/2026-07-28-rapidocr-docling-pdf-recognition.md`

**Interfaces:**

- Consumes: Task 1의 실제 패키지 버전, Task 3의 실제 모델 출처·라이선스·해시, Task 9의 사람 검수 결과
- Produces: 한국어 우선 조사 문서와 뒤쪽 `English AI Context`

- [ ] **Step 1: 제3자 고지를 실제 잠금과 일치시켜 작성**

`THIRD_PARTY_NOTICES.md`의 한국어 앞부분에 다음을 artifact별로 기록한다.

- RapidOCR 코드: 정확한 잠금 버전, Apache-2.0, 공식 저장소
- ONNX Runtime: 정확한 잠금 버전, MIT, 공식 저장소
- Docling와 docling-ibm-models 코드: 정확한 잠금 버전, MIT, 공식 저장소
- RapidOCR det·Korean rec·선택적 keys artifact: 모델명, 원문 URL, 잠금 SHA-256, upstream model notice
- Docling layout·TableFormer artifact: 모델명, 원문 URL, 잠금 SHA-256, artifact별 확인된 라이선스

확인되지 않은 artifact 라이선스를 추정해 하나로 합치지 않는다. 확인되지 않은 항목은
배포·공개가 승인된 것으로 쓰지 않고 `PENDING_REVIEW`로 기록한다. PaddleOCR·PaddlePaddle
항목은 “실행 중단된 과거 결정 이력”으로 이동하며 현재 의존성으로 표시하지 않는다.

- [ ] **Step 2: Spec Kit 문서의 엔진과 처리 계약 교체**

`spec.md`, `plan.md`, `research.md`, `source-register.md`,
`research-data/README.md`의 현행 기술 설명을 다음 문장 의미로 통일한다.

```markdown
PDF는 pypdf 내장 텍스트를 우선하고 PyMuPDF로 모든 페이지를 300 DPI PNG로
렌더링한다. 모든 PNG에 Docling 레이아웃 전용 패스를 먼저 적용하며, 스캔·저텍스트·
복합 페이지는 RapidOCR·ONNX Runtime CPU로 인식하고 표 페이지는 Docling 내부
RapidOCR와 TableFormer accurate로 행·열·병합셀 구조를 복원한다.
```

Paddle `phi.dll` 접근 위반은 대체 이유와 실패 증거로 보존하되 현재 실행 구성으로
남기지 않는다.

- [ ] **Step 3: T112 상태를 실제 승인 결과에 맞춰 갱신**

Task 9의 네 PDF가 모두 `HUMAN_REVIEWED`인 경우에만 `tasks.md`의 T112를 `[x]`로
바꾸고 `research-readiness.md`의 실제 관보 대조 항목도 `[x]`로 바꾼다.
하나라도 실패·미검수이면 T112와 조사 게이트를 `[ ]`로 유지하고 정확한 실패 표본·페이지·
이유를 기록한다.

`tasks.md` T112 설명은 다음 범위를 포함해야 한다.

- Python 3.12, RapidOCR, ONNX Runtime CPU, Docling, TableFormer `accurate`
- 원본·페이지·모델·OCR JSON·구조 JSON·표 HTML·Markdown SHA-256
- polygon·bbox·confidence·행·열·병합셀·사람 검수
- runtime auto-download 금지와 fail-closed 원자 게시

- [ ] **Step 4: 설계·계획 상태와 대체 관계 갱신**

RapidOCR·Docling 설계의 한국어 상태를 `사용자 문서 승인 완료`로, AI context status를
`APPROVED_FOR_IMPLEMENTATION`으로 바꾼다. 기존 Paddle 설계·계획의 상단에는 삭제 대신
다음 대체 안내를 추가한다.

```markdown
> **상태: SUPERSEDED**
> Windows PaddlePaddle 접근 위반으로 이 문서는 실행 기준이 아니다.
> 후속 기준: `docs/superpowers/specs/2026-07-28-rapidocr-docling-pdf-recognition-design.md`
> 후속 계획: `docs/superpowers/plans/2026-07-28-rapidocr-docling-pdf-recognition.md`
```

- [ ] **Step 5: 컷오프 매니페스트 해시 갱신**

위 문서 내용이 확정된 뒤 `cutoff-manifest.csv`에 이미 등록된 변경 문서만 실제 byte
수와 SHA-256으로 갱신한다. 새 승인 보고서를 컷오프 범위에 포함하려면 별도 행으로
경로·byte·SHA-256·검수 상태를 기록한다. 해시 계산 뒤 문서를 다시 수정하지 않는다.

- [ ] **Step 6: 문서 자체 정합성 확인**

Run:

```powershell
rg -n "현재 실행|현행 구성|pdf_tool:|pdf_pipeline:" THIRD_PARTY_NOTICES.md specs/001-real-estate-policy-dashboard -g "*.md"
rg -n "PaddleOCR|PaddlePaddle|PP-StructureV3" THIRD_PARTY_NOTICES.md specs/001-real-estate-policy-dashboard -g "*.md"
```

Expected: 첫 검색의 현행 구성은 RapidOCR·ONNX Runtime·Docling/TableFormer만
가리킨다. 두 번째 검색의 Paddle 항목은 과거 실패·대체 이력 또는 모델 계보 설명에만
남아 있다.

- [ ] **Step 7: 승인된 경우에만 문서 Task 커밋**

```powershell
git add THIRD_PARTY_NOTICES.md specs/001-real-estate-policy-dashboard docs/superpowers/specs/2026-07-28-paddleocr-pdf-recognition-design.md docs/superpowers/specs/2026-07-28-rapidocr-docling-pdf-recognition-design.md docs/superpowers/plans/2026-07-28-paddleocr-pdf-recognition.md docs/superpowers/plans/2026-07-28-rapidocr-docling-pdf-recognition.md
git commit -m "docs(research): adopt RapidOCR Docling T112 evidence"
```

---

### Task 11: 승인된 범위만 최종 통합

**Files:**

- Review: `git status --short`
- Review: `git diff --stat`
- Review: `git diff --check`

**Interfaces:**

- Consumes: Task 1~10 중 사용자가 승인하고 완료한 커밋
- Produces: 승인된 브랜치 또는 `main`의 일관된 T112 변경 이력

- [ ] **Step 1: 작업 범위 대조**

Run:

```powershell
git status --short
git diff --stat
git diff --check
```

Expected: 사용자의 기존 변경을 제외하고 이 계획의 파일 지도에 있는 파일만 T112
변경으로 식별되며 whitespace 오류가 없다.

- [ ] **Step 2: 완료 주장 전 승인된 T112 증거 확인**

다음 세 조건을 모두 충족한 경우에만 “T112 완료”라고 보고한다.

1. Task 9의 T112 전용 자동 회귀가 통과했다.
2. 실제 관보 네 건의 모든 페이지·표·핵심 필드 사람 대조가 완료됐다.
3. Task 10 문서와 컷오프 해시가 실제 결과와 일치한다.

조건을 충족하지 않으면 구현 완료와 조사 게이트 완료를 구분해 남은 차단 사유를
보고한다.

- [ ] **Step 3: Git 통합은 별도 명시 승인 후 수행**

현재 브랜치와 `main` 관계를 확인한 뒤 사용자가 요청한 방식으로만 통합한다.
이미 `main`이면 추가 merge를 만들지 않는다. 기능 브랜치이면 사용자의 merge 승인을
받은 뒤 `superpowers:finishing-a-development-branch` 지침으로 통합한다. 강제 push,
`git reset --hard`, 사용자 변경 폐기는 수행하지 않는다.

---

## 4. Task 의존성

```text
Task 1 runtime lock
  ├── Task 2 contracts and routes
  └── Task 3 model artifact lock
        ├── Task 4 RapidOCR runner
        └── Task 5 Docling/TableFormer runner
Task 2 + Task 4 + Task 5
  └── Task 6 artifact serialization
Task 1..6
  └── Task 7 pipeline orchestration
        └── Task 8 CLI/wrapper/container
              └── Task 9 automated and real-sample acceptance
                    └── Task 10 documentation and T112 gate
                          └── Task 11 approved Git integration
```

Task 4와 Task 5는 Task 3의 잠금 인터페이스가 확정된 뒤 서로 병렬로 구현할 수 있다.
Task 9의 실제 PDF 실행은 패키지 설치·모델 준비·테스트에 대한 사용자의 별도 승인을
받은 경우에만 진행한다.

## 5. 공식 구현 근거

- [RapidOCR 사용법과 `params` 구성](https://rapidai.github.io/RapidOCRDocs/latest/install_usage/rapidocr/usage/)
- [RapidOCR 모델·ONNX Runtime parameter](https://rapidai.github.io/RapidOCRDocs/latest/install_usage/rapidocr/parameters/)
- [Docling pipeline options와 offline `artifacts_path`](https://docling-project.github.io/docling/reference/pipeline_options/)
- [Docling serialization](https://docling-project.github.io/docling/concepts/serialization/)
- [Docling 모델 카탈로그](https://docling-project.github.io/docling/usage/model_catalog/)
- [ONNX Runtime 설치](https://onnxruntime.ai/docs/install/)

---

## English AI Context

```yaml
plan_id: RAPIDOCR_DOCLING_PDF_RECOGNITION
planned_on: 2026-07-28
document_language_order:
  - korean_user_context
  - english_ai_context
design:
  path: docs/superpowers/specs/2026-07-28-rapidocr-docling-pdf-recognition-design.md
  user_document_status: APPROVED
  status: APPROVED_FOR_IMPLEMENTATION
supersedes:
  - docs/superpowers/plans/2026-07-28-paddleocr-pdf-recognition.md
task: T112

execution:
  current_status: TASK_1_TO_9_COMPLETE_TASK_10_DOCUMENTATION_IN_PROGRESS
  automated_acceptance: PASS_508_PASSED_1_SKIPPED
  real_sample_execution: PASS_4_OF_4
  human_acceptance: PENDING_USER_HUMAN_REVIEW
  real_table_acceptance_coverage: MISSING_NO_TABLES_IN_APPROVED_SAMPLES
  package_install_requires_separate_approval: true
  model_download_requires_separate_approval: true
  code_change_requires_separate_approval: true
  test_execution_requires_separate_approval: true
  git_actions_require_separate_approval: true
  unrelated_project_tests_forbidden: true

runtime_contract:
  platform: windows_cpu
  python: ">=3.12,<3.13"
  exact_versions_source: tools/pdf-ocr/uv.lock
  required_distributions:
    - rapidocr
    - onnxruntime
    - docling
    - docling-ibm-models
  forbidden_distributions:
    - paddleocr
    - paddlepaddle
  execution_provider: CPUExecutionProvider
  model_home_env: PDF_OCR_MODEL_HOME
  network_download_during_run: forbidden

page_pipeline:
  - pypdf_validate_and_extract_embedded_text
  - pymupdf_render_every_page_300_dpi_png
  - docling_layout_only_on_every_png
  - route_page
  - direct_rapidocr_audit_when_required
  - docling_rapidocr_tableformer_accurate_on_table_pages
  - compare_raw_ocr_to_table_cells
  - validate_page_schemas_and_table_topology
  - validate_manifest_hash_chain
  - atomic_publish

routes:
  - EMBEDDED_TEXT
  - RAPIDOCR
  - RAPIDOCR_TABLEFORMER

contracts:
  schema_version: "2.0.0"
  raw_ocr_threshold: 0.0
  human_review_threshold: 0.90
  row_column_indexing: zero_based_half_open
  table_authority:
    - structure_json
    - table_html
  markdown_authoritative_for_merged_cells: false

implementation_tasks:
  - id: 1
    output: exact_runtime_lock_and_cpu_provider_contract
  - id: 2
    output: v2_routes_page_schemas_manifest_and_topology
  - id: 3
    output: offline_model_artifact_lock
  - id: 4
    output: direct_rapidocr_audit_runner
  - id: 5
    output: docling_layout_and_tableformer_runner
  - id: 6
    output: ocr_table_comparison_and_artifact_writer
  - id: 7
    output: fail_closed_atomic_pipeline
  - id: 8
    output: frozen_offline_cli_wrapper_container
  - id: 9
    output: t112_regression_and_four_sample_human_acceptance
  - id: 10
    output: notices_speckit_docs_and_t112_gate
  - id: 11
    output: separately_approved_git_integration

acceptance_samples:
  - specs/001-real-estate-policy-dashboard/research-data/captures/gazette/2017-114.pdf
  - specs/001-real-estate-policy-dashboard/research-data/captures/gazette/2018-151.pdf
  - specs/001-real-estate-policy-dashboard/research-data/captures/gazette/2022-189.pdf
  - specs/001-real-estate-policy-dashboard/research-data/captures/gazette/2023-001.pdf

completion_gate:
  - all_t112_tests_pass
  - all_four_pdfs_process_all_pages
  - table_counts_rows_columns_and_spans_match_source
  - critical_legal_fields_human_reviewed
  - complete_sha256_chain
  - documentation_matches_evidence
  - no_publication_or_rag_elevation_from_ocr_alone
```
