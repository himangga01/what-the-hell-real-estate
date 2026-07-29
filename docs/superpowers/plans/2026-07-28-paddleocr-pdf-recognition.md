# PaddleOCR PDF 인식 파이프라인 구현 계획

> **상태: SUPERSEDED**
> Windows PaddlePaddle 접근 위반으로 이 문서는 실행 기준이 아니다.
> 후속 기준: `docs/superpowers/specs/2026-07-28-rapidocr-docling-pdf-recognition-design.md`
> 후속 계획: `docs/superpowers/plans/2026-07-28-rapidocr-docling-pdf-recognition.md`

> **에이전트 작업자용:** 이 계획을 구현할 때
> `superpowers:subagent-driven-development` 또는 `superpowers:executing-plans`를 사용한다.
> 각 단계는 체크박스로 추적한다.

**목표:** 정부 PDF를 텍스트 우선으로 처리하고 스캔·저신뢰·구조 문서는 고정된
PaddleOCR 한국어 파이프라인으로 인식하여 원본·모델·페이지·출력 해시가 있는 조사
매니페스트를 생성한다.

**아키텍처:** 제품 백엔드 Python 3.14와 분리된 `tools/pdf-ocr/` Python 3.12
컨테이너가 파일 입력과 JSON 매니페스트 출력만 담당한다. 내장 텍스트가 품질 기준을
통과하면 이를 우선하고, 나머지 페이지와 표·다단 페이지는 `PP-StructureV3`와
`korean_PP-OCRv5_mobile_rec`로 처리한다.

**기술 스택:** Python 3.12, `paddleocr==3.7.0`, `paddlepaddle==3.2.2`,
PP-StructureV3, PP-OCRv5 Korean, pypdf, PyMuPDF, JSON Schema, SHA-256, pytest

## 전역 제약

- PaddleOCR 버전은 `3.7.0`, PaddlePaddle 버전은 `3.2.2`로 고정한다.
- OCR 실행 Python은 `3.12`이며 제품 백엔드 Python 3.14 환경에 설치하지 않는다.
- 한국어 모델은 `korean_PP-OCRv5_mobile_rec`를 명시하고 기본 모델 자동 전환을 금지한다.
- 원본 PDF는 도구가 변경하거나 삭제하지 않는다.
- 페이지 렌더링은 300 DPI PNG를 사용한다.
- 공백 제거 내장 텍스트가 30자 미만이거나 제어·대체문자 비율이 5%를 초과하면 OCR한다.
- 공고번호·날짜·면적·지역명은 OCR 신뢰도와 무관하게 사람 검수 대상으로 표시한다.
- 권리 승인 전 원문과 파생물 보존 상태는 `TEMPORARY_NOT_RETAINED`다.
- OCR 결과만으로 정책·세금·공간 사실을 `VERIFIED`로 승격하지 않는다.
- 생성하는 Markdown은 한국어 설명 뒤에 `English AI Context`를 둔다.
- 구현·테스트·커밋 실행은 사용자의 별도 실행 승인을 받은 뒤 진행한다.

## 파일 구조

| 경로 | 책임 |
|---|---|
| `tools/pdf-ocr/pyproject.toml` | Python 3.12과 고정 OCR 의존성 |
| `tools/pdf-ocr/uv.lock` | 재현 가능한 OCR 환경 잠금 |
| `tools/pdf-ocr/Dockerfile` | 백엔드와 분리된 CPU OCR 컨테이너 |
| `tools/pdf-ocr/src/pdf_ocr/contracts.py` | 요청·페이지·매니페스트 타입 |
| `tools/pdf-ocr/src/pdf_ocr/router.py` | 내장 텍스트 품질 판정과 처리 경로 선택 |
| `tools/pdf-ocr/src/pdf_ocr/pipeline.py` | 렌더링, PaddleOCR 호출, 원자 게시 |
| `tools/pdf-ocr/src/pdf_ocr/cli.py` | 파일 기반 CLI 진입점 |
| `tools/pdf-ocr/schemas/manifest.schema.json` | OCR 매니페스트 계약 |
| `tools/pdf-ocr/models.lock.json` | 모델명·출처·파일별 SHA-256 |
| `tools/pdf-ocr/tests/` | 계약·라우팅·실패·통합 테스트 |
| `scripts/research/extract-pdf.ps1` | 조사자가 호출하는 PowerShell 래퍼 |
| `THIRD_PARTY_NOTICES.md` | PaddleOCR 버전·Apache-2.0·사용 범위 고지 |

---

### Task 1: 격리 런타임과 고정 의존성

**Files:**

- Create: `tools/pdf-ocr/pyproject.toml`
- Create: `tools/pdf-ocr/uv.lock`
- Create: `tools/pdf-ocr/Dockerfile`
- Create: `tools/pdf-ocr/src/pdf_ocr/__init__.py`

**Interfaces:**

- Produces: Python 3.12 CPU-only OCR runtime
- Produces: `python -m pdf_ocr.cli --help`

- [ ] **Step 1: 패키지 계약 작성**

`pyproject.toml`에 Python `>=3.12,<3.13`, `paddleocr==3.7.0`,
`paddlepaddle==3.2.2`, `pypdf`, `PyMuPDF`, `jsonschema`와 pytest 개발 의존성을
정의한다.

- [ ] **Step 2: 잠금 파일 생성**

Run: `uv lock --project tools/pdf-ocr --python 3.12`

Expected: `tools/pdf-ocr/uv.lock`이 생성되고 PaddleOCR와 PaddlePaddle 버전이 고정된다.

- [ ] **Step 3: CPU 컨테이너 작성**

`Dockerfile`은 Python 3.12 slim 이미지를 사용하고 비루트 사용자로
`python -m pdf_ocr.cli`를 실행한다. 입력과 출력 디렉터리만 볼륨으로 받으며 백엔드
환경을 복사하지 않는다.

- [ ] **Step 4: 환경 확인**

Run: `uv run --project tools/pdf-ocr python -c "import paddleocr; import paddle"`

Expected: 종료 코드 0과 고정된 두 패키지 버전이 출력된다.

---

### Task 2: 매니페스트 계약과 페이지 라우팅

**Files:**

- Create: `tools/pdf-ocr/src/pdf_ocr/contracts.py`
- Create: `tools/pdf-ocr/src/pdf_ocr/router.py`
- Create: `tools/pdf-ocr/schemas/manifest.schema.json`
- Test: `tools/pdf-ocr/tests/test_router.py`
- Test: `tools/pdf-ocr/tests/test_manifest_schema.py`

**Interfaces:**

- Produces: `class PageRoute(str, Enum)`
- Produces: `select_page_route(text: str, has_complex_layout: bool) -> PageRoute`
- Produces: `validate_manifest(payload: dict[str, object]) -> None`

- [ ] **Step 1: 실패하는 라우팅 테스트 작성**

```python
def test_low_text_page_requires_paddleocr() -> None:
    assert select_page_route("공고", False) is PageRoute.PADDLEOCR


def test_clean_text_page_uses_embedded_text() -> None:
    text = "서울특별시 공고 제2025-2774호 " * 3
    assert select_page_route(text, False) is PageRoute.EMBEDDED_TEXT


def test_complex_layout_uses_structure_pipeline() -> None:
    text = "서울특별시 공고 제2025-2774호 " * 3
    assert select_page_route(text, True) is PageRoute.PADDLEOCR_STRUCTURE
```

- [ ] **Step 2: 테스트 실패 확인**

Run: `uv run --project tools/pdf-ocr pytest tools/pdf-ocr/tests/test_router.py -q`

Expected: `PageRoute`와 `select_page_route`가 없어 실패한다.

- [ ] **Step 3: 최소 라우터 구현**

`EMBEDDED_TEXT`, `PADDLEOCR`, `PADDLEOCR_STRUCTURE` 열거형과 30자·5% 기준을
구현한다. `has_complex_layout=True`는 텍스트 품질과 무관하게 구조 파이프라인을
선택한다.

- [ ] **Step 4: 매니페스트 스키마 테스트와 계약 작성**

입력 PDF, 도구·모델, 페이지, 출력, 보존, 검수와 오류 필드를 필수로 하는 JSON Schema
2020-12 계약을 작성한다. 해시는 `^sha256:[0-9a-f]{64}$`, 페이지 번호는 1부터 시작하는
연속 정수로 제한한다.

- [ ] **Step 5: 계약 테스트 통과 확인**

Run: `uv run --project tools/pdf-ocr pytest tools/pdf-ocr/tests/test_router.py tools/pdf-ocr/tests/test_manifest_schema.py -q`

Expected: 모든 라우팅과 스키마 테스트가 통과한다.

---

### Task 3: PDF 렌더링과 PaddleOCR 파이프라인

**Files:**

- Create: `tools/pdf-ocr/src/pdf_ocr/pipeline.py`
- Create: `tools/pdf-ocr/src/pdf_ocr/cli.py`
- Create: `tools/pdf-ocr/models.lock.json`
- Test: `tools/pdf-ocr/tests/test_pipeline_fail_closed.py`
- Test: `tools/pdf-ocr/tests/test_pipeline_integration.py`

**Interfaces:**

- Produces: `extract_pdf(input_path: Path, output_dir: Path) -> Path`
- Produces: `create_ocr_pipeline() -> PPStructureV3`
- Produces: `models.lock.json`

- [ ] **Step 1: 실패 경계 테스트 작성**

손상 PDF, 암호화 PDF, 빈 출력, 페이지 누락, 입력 변경, 모델 해시 불일치와 기존 출력
경로가 있을 때 성공 매니페스트를 만들지 않는 테스트를 작성한다.

- [ ] **Step 2: 실패 확인**

Run: `uv run --project tools/pdf-ocr pytest tools/pdf-ocr/tests/test_pipeline_fail_closed.py -q`

Expected: 파이프라인 구현이 없어 실패한다.

- [ ] **Step 3: 모델 잠금 생성**

공식 모델을 통제된 캐시에 내려받아 `korean_PP-OCRv5_mobile_rec`와
PP-StructureV3 구성 모델의 실제 파일명·공식 출처 URL·바이트 수·SHA-256을
`models.lock.json`에 기록한다. 이후 실행은 잠금에 없는 모델 파일을 거부한다.

- [ ] **Step 4: 최소 파이프라인 구현**

PyMuPDF로 300 DPI 페이지 PNG를 만들고 pypdf 내장 텍스트를 라우터에 전달한다.
OCR 경로는 다음 구성으로 초기화한다.

```python
from paddleocr import PPStructureV3


def create_ocr_pipeline() -> PPStructureV3:
    return PPStructureV3(
        text_recognition_model_name="korean_PP-OCRv5_mobile_rec",
        use_doc_orientation_classify=True,
        use_doc_unwarping=False,
    )
```

출력은 임시 디렉터리에서 완성한 후 같은 파일시스템의 원자 이동으로 게시한다.

- [ ] **Step 5: 페이지 결과와 검수 상태 작성**

각 페이지에 처리 경로, 텍스트·좌표·신뢰도, 이미지와 JSON·Markdown 해시를 기록한다.
공고번호·날짜·면적·지역명은 `PENDING_HUMAN_REVIEW`로 표시한다.

- [ ] **Step 6: 통합 테스트 통과 확인**

Run: `uv run --project tools/pdf-ocr pytest tools/pdf-ocr/tests -q`

Expected: 텍스트 fixture와 스캔 fixture의 페이지 수·라우팅·해시·오류 경계 테스트가
모두 통과한다.

---

### Task 4: 조사 래퍼와 승인 샘플

**Files:**

- Create: `scripts/research/extract-pdf.ps1`
- Test: `tools/pdf-ocr/tests/test_research_samples.py`
- Modify: `THIRD_PARTY_NOTICES.md`
- Modify: `specs/001-real-estate-policy-dashboard/source-register.md`
- Modify: `specs/001-real-estate-policy-dashboard/research-data/README.md`
- Modify: `specs/001-real-estate-policy-dashboard/checklists/research-readiness.md`

**Interfaces:**

- Produces: `extract-pdf.ps1 -InputPath <pdf> -OutputDirectory <dir>`
- Consumes: `python -m pdf_ocr.cli`
- Produces: `pdf-ocr-manifest.json`

- [ ] **Step 1: PowerShell 래퍼 작성**

입력·출력 절대 경로만 허용하고 컨테이너 또는 고정된 로컬 Python 3.12 환경을 호출한다.
사용자 원본은 삭제하지 않으며 실패 시 부분 출력 경로를 성공으로 보고하지 않는다.

- [ ] **Step 2: 승인 샘플 처리**

저장소의 전자관보 PDF 4건과 권리가 허용된 표·다단 공식 PDF 샘플을 처리한다. 원본
공고번호·날짜·대상 지역·면적을 OCR 결과와 사람이 대조하고 검수자·시각·결정을 기록한다.

- [ ] **Step 3: 조사 문서 갱신**

제3자 고지, 출처 레지스트리, 연구 데이터 안내와 조사 체크리스트에 버전·모델·해시·보존
상태·사람 검수 경계를 기록한다. 컷오프 산출물에 새 매니페스트를 포함할 때 기존
컷오프 매니페스트와 참조 해시도 함께 갱신한다.

- [ ] **Step 4: 전체 파이프라인 확인**

Run: `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/research/extract-pdf.ps1 -InputPath specs/001-real-estate-policy-dashboard/research-data/captures/gazette/2017-114.pdf -OutputDirectory temp/pdf-ocr-acceptance`

Expected: 원본은 유지되고 페이지 결과와 `pdf-ocr-manifest.json`이 생성되며 핵심 필드는
사람 검수 대기로 표시된다.

- [ ] **Step 5: 구현 커밋**

구현 시점에 사용자가 Git 커밋을 별도로 승인한 경우에만 OCR 코드·잠금·테스트·문서를
의도적으로 스테이징하고 커밋한다.

---

## English AI Context

```yaml
plan_id: PADDLEOCR_PDF_RECOGNITION
approved_on: 2026-07-28
execution_status: IMPLEMENTED_TESTED_WINDOWS_RUNTIME_BLOCKED
runtime_blocker: PADDLE_PHI_DLL_ACCESS_VIOLATION_REQUIRES_LINUX_ACCEPTANCE
required_execution_skill:
  - superpowers:subagent-driven-development
  - or: superpowers:executing-plans
tasks:
  - isolated_runtime_and_dependency_lock
  - manifest_contract_and_page_router
  - fail_closed_paddleocr_pipeline
  - research_wrapper_and_approved_samples
implementation_requires_separate_user_approval: true
git_actions_require_separate_user_approval: true
```
