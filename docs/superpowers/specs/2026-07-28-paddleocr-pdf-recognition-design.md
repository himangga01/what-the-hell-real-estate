# PaddleOCR 기반 PDF 인식 파이프라인 설계

> **상태: SUPERSEDED**
> Windows PaddlePaddle 접근 위반으로 이 문서는 실행 기준이 아니다.
> 후속 기준: `docs/superpowers/specs/2026-07-28-rapidocr-docling-pdf-recognition-design.md`
> 후속 계획: `docs/superpowers/plans/2026-07-28-rapidocr-docling-pdf-recognition.md`

**설계 승인일**: 2026-07-28

**승인 상태**: 과거 승인 이력, 현재 실행 기준 아님

**적용 범위**: 조사 단계의 정부·지자체 PDF 텍스트·표·문서 구조 인식

**선택 도구**: [`PaddlePaddle/PaddleOCR`](https://github.com/PaddlePaddle/PaddleOCR)
`v3.7.0`

## 1. 목적

정부 PDF에서 공고번호, 날짜, 대상 지역, 면적, 표와 문단 구조를 읽을 때 PaddleOCR를
표준 인식 도구로 사용한다. 원본 PDF와 페이지별 파생 결과를 연결하고 입력·모델·출력의
SHA-256을 기록하여 어떤 도구와 설정으로 어떤 문자열을 얻었는지 추적할 수 있게 한다.

OCR은 원문을 대신하지 않는다. 인식 결과는 조사 보조 자료이며, 법적 효력·세금 규칙·공간
경계와 원문 이용권한의 사람 검수를 통과하기 전에는 `VERIFIED` 근거나 공개 RAG 자료로
사용하지 않는다.

## 2. 처리 범위

### 포함

- PDF에 신뢰 가능한 텍스트 레이어가 있으면 원문 텍스트를 우선 추출
- 텍스트가 없거나 품질 기준을 충족하지 못한 페이지는 PaddleOCR로 인식
- 표·다단·제목·문단의 읽기 순서가 필요한 페이지는 `PP-StructureV3`로 구조화
- 한국어·영문·숫자는 `PP-OCRv5`의 `korean_PP-OCRv5_mobile_rec`로 인식
- 원본 PDF, 렌더링 페이지, JSON·Markdown 결과와 실행 설정의 SHA-256 기록
- 공고번호·날짜·면적·법령명·지역명에 대한 사람 검수 대기 상태 기록
- 손상·빈 출력·페이지 누락·모델 불일치 시 fail-closed 처리

### 제외

- OCR 결과만으로 정책·규제·세금 사실을 자동 승인
- 이용권한 검토 전 원문 또는 OCR 전문을 공개·RAG 색인
- PaddleOCR의 온라인 API 또는 외부 호스팅 OCR로 정부 문서 전송
- 백엔드 Python 3.14 프로세스에 OCR 런타임 직접 설치
- 손글씨, 지도 경계와 도면 좌표의 자동 법적 판정
- PaddleOCR 모델 학습·미세조정

## 3. 선택한 접근

### 채택: 텍스트 우선 + 선택적 PaddleOCR

페이지의 내장 텍스트를 먼저 확인하고, 공백 제거 후 30자 미만이거나 제어·대체문자 비율이
5%를 초과하면 OCR 대상으로 보낸다. 내장 텍스트가 기준을 통과하더라도 표·다단 구조가
핵심인 페이지는 `PP-StructureV3` 결과를 추가 생성해 원문 텍스트와 대조한다.

이 방식은 모든 페이지를 무조건 OCR하는 방식보다 오인식과 실행 비용을 줄이면서 스캔 PDF를
놓치지 않는다.

### 격리 런타임

제품 백엔드는 Python 3.14를 유지한다. OCR은 `tools/pdf-ocr/`의 Python 3.12 컨테이너에서
실행하며 파일 입력과 JSON 매니페스트 출력만 공유한다. 계획 기준 의존성은
`paddleocr==3.7.0`, `paddlepaddle==3.2.2`로 고정하고 잠금 파일로 재현한다.

2026-07-28 실제 Windows CPU 실행에서 PaddlePaddle 3.3.0의 PIR·oneDNN 회귀가 확인돼
사용자 승인으로 3.2.2로 하향 고정했다. 3.2.2도 현재 Windows의 `phi.dll`에서 접근 위반이
발생하므로 실제 관보 승인 실행은 Linux 컨테이너 런타임에서 완료해야 한다.

### 한국어 모델

일반 한국어 텍스트 인식은 `PP-OCRv5`와 `korean_PP-OCRv5_mobile_rec`를 명시한다.
`PP-OCRv6` 기본 모델로 자동 전환하지 않는다. 표·문단 구조는 `PP-StructureV3`가 담당하되
텍스트 인식 모델은 같은 한국어 모델을 사용한다.

## 4. 데이터 흐름

1. 원본 PDF의 바이트 수와 SHA-256을 기록한다.
2. 페이지 수를 확인하고 각 페이지를 300 DPI PNG로 렌더링한다.
3. 내장 텍스트를 추출해 페이지별 품질 기준을 계산한다.
4. 기준 미달 페이지와 구조 분석 대상 페이지를 PaddleOCR로 처리한다.
5. 페이지별 JSON·Markdown, 좌표, 신뢰도와 이미지 SHA-256을 기록한다.
6. 전체 페이지 수와 출력 페이지 번호의 연속성을 확인한다.
7. 공고번호·날짜·면적·지역명과 낮은 신뢰도 문자열을 사람 검수 대상으로 표시한다.
8. 성공한 경우에만 실행 매니페스트를 게시한다.

## 5. 실행 매니페스트

매니페스트에는 다음 필드를 기록한다.

- 스키마 버전과 실행 시각
- 입력 PDF 파일명·MIME·바이트 수·SHA-256·페이지 수
- PaddleOCR·PaddlePaddle·Python 버전
- 파이프라인명, 한국어 모델명, 모델 파일별 SHA-256
- 렌더링 DPI와 페이지 이미지 SHA-256
- 페이지별 처리 경로: `EMBEDDED_TEXT`, `PADDLEOCR`, `PADDLEOCR_STRUCTURE`
- 페이지별 JSON·Markdown 파일명·바이트 수·SHA-256
- 인식 좌표와 신뢰도
- 낮은 신뢰도와 핵심 필드 사람 검수 상태
- 원문·파생물 보존 상태와 이용권한 상태
- 경고·오류와 성공 여부

## 6. 실패 및 검수 경계

- 입력 PDF 손상 또는 암호화: 성공 결과 생성 금지
- 페이지 수 불일치 또는 페이지 번호 누락: 성공 매니페스트 생성 금지
- 고정 패키지·모델명 불일치: 실행 금지
- 모델 파일 해시 불일치: 실행 금지
- OCR 출력 0바이트 또는 빈 페이지: 해당 문서를 완료 처리하지 않음
- 신뢰도 기준 미달: `PENDING_HUMAN_REVIEW`
- 공고번호·날짜·면적·지역명: 신뢰도와 무관하게 사람 대조 필수
- 권리 미승인: 기본 보존 상태 `TEMPORARY_NOT_RETAINED`
- OCR 결과와 원문 텍스트 충돌: 최신값을 자동 선택하지 않고 검수 대기

## 7. 완료 기준

- 격리된 Python 3.12 OCR 환경과 잠금 파일이 존재한다.
- 고정 PaddleOCR·PaddlePaddle 버전과 한국어 모델이 매니페스트에 기록된다.
- 텍스트 PDF와 스캔 PDF를 구분해 정해진 처리 경로로 보낸다.
- 페이지별 JSON·Markdown·좌표·신뢰도·SHA-256이 생성된다.
- 손상·빈 출력·페이지 누락·모델 불일치가 fail-closed로 끝난다.
- 기존 전자관보 PDF와 구조가 복잡한 공식 PDF를 승인 샘플로 처리한다.
- 핵심 필드 사람 검수와 원문 이용권한 게이트가 유지된다.

---

## English AI Context

```yaml
design_id: PADDLEOCR_PDF_RESEARCH_PIPELINE
approved_on: 2026-07-28
status: APPROVED_NOT_IMPLEMENTED
scope: research_only_government_pdf_recognition
tool:
  repository: https://github.com/PaddlePaddle/PaddleOCR
  paddleocr_version: 3.7.0
  paddlepaddle_version: 3.2.2
  license: Apache-2.0
runtime:
  application_python: "3.14"
  isolated_ocr_python: "3.12"
  boundary: file_input_json_manifest_output
pipeline:
  embedded_text_first: true
  embedded_text_min_non_whitespace_chars: 30
  embedded_text_max_invalid_character_ratio: 0.05
  structured_pdf_pipeline: PP-StructureV3
  ocr_version: PP-OCRv5
  text_recognition_model: korean_PP-OCRv5_mobile_rec
  render_dpi: 300
artifacts:
  - original_pdf_sha256
  - rendered_page_sha256
  - model_file_sha256
  - page_json_sha256
  - page_markdown_sha256
  - extraction_manifest
fail_closed_on:
  - corrupt_or_encrypted_pdf
  - package_or_model_mismatch
  - model_hash_mismatch
  - empty_output
  - page_count_mismatch
  - page_gap
human_review_required:
  - notice_number
  - legal_dates
  - area_values
  - jurisdiction_names
  - legal_effect
  - tax_rule
  - spatial_boundary
  - source_rights
default_retention: TEMPORARY_NOT_RETAINED
out_of_scope:
  - automatic_legal_verification
  - public_ocr_service
  - model_training
  - handwriting
  - map_boundary_adjudication
```
