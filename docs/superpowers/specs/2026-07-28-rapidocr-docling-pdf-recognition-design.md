# RapidOCR·Docling 기반 PDF 인식 파이프라인 설계

**설계일**: 2026-07-28
**설계 상태**: 사용자 문서 승인 완료
**적용 작업**: T112 정부 PDF 조사 추출
**대체 대상**: PaddleOCR·PaddlePaddle 실행 패키지
**유지 대상**: pypdf, PyMuPDF, 기존 원자적 게시·해시·사람 검수 경계
**선택 구성**: RapidOCR + ONNX Runtime + Docling/TableFormer

이 문서는 기존
`docs/superpowers/specs/2026-07-28-paddleocr-pdf-recognition-design.md`를
대체하는 후속 설계다. 기존 문서는 Windows `phi.dll` 접근 위반이 발생한 결정 이력으로
보존하고, 신규 구현의 기준은 이 문서로 전환한다.

## 1. 결정 요약

PaddleOCR와 PaddlePaddle 실행 패키지는 제거한다. 한국어 인식은 RapidOCR가
ONNX Runtime으로 실행하는 `PP-OCRv5` 한국어 mobile 모델을 사용한다. 이 모델은
Paddle 계열에서 학습됐지만 PaddlePaddle 런타임을 사용하지 않는다. 사용자는 이 모델
계보의 사용을 승인했다.

표와 복합 레이아웃은 Docling의 레이아웃 분석과 TableFormer `accurate` 모드로
처리한다. Docling은 원본 PDF를 직접 열지 않고 PyMuPDF가 만든 페이지 PNG를
페이지별 sidecar 입력으로만 받는다. 따라서 기존 pypdf·PyMuPDF PDF 경계는 유지한다.

RapidOCR 원시 텍스트·좌표·신뢰도와 Docling 표 구조 결과는 서로 다른 감사 산출물로
보존한다. 표가 있는 페이지에서는 Docling 내부 OCR과 별도로 RapidOCR 감사용 원시
출력을 생성하므로 OCR이 중복 실행될 수 있다. 이 중복은 원시 신뢰도 보존과 결과 대조를
위한 승인된 비용이다.

## 2. 배경과 문제

기존 구현은 PaddleOCR `3.7.0`, PaddlePaddle `3.2.2`,
`PP-StructureV3`, `korean_PP-OCRv5_mobile_rec`을 사용했다. 계약·회귀 테스트는
통과했지만 실제 Windows CPU 실행에서 PaddlePaddle의 `phi.dll`이
`0xc0000005` 접근 위반으로 종료됐다. PaddlePaddle `3.3.0`과 `3.2.2`에서 모두
재현됐으며 PDF 내용을 읽기 전 모델 초기화 단계에서 충돌했다.

T112는 Windows에서 실제 전자관보 PDF 네 건을 처리하고, 표 구조와 법적 핵심 필드를
사람이 대조해야 완료된다. Linux·WSL·Docker 설치 대신 Windows에서 실행 가능한
오픈소스 조합으로 PaddleOCR만 교체한다.

## 3. 범위

### 3.1 포함

- 기존 PDF 유효성·암호화·페이지 수 검사 유지
- 모든 페이지 300 DPI PNG 렌더링 유지
- 내장 텍스트 우선 경로 유지
- 모든 페이지의 레이아웃·표 존재 여부 탐지
- 저신뢰·스캔·표·복합 페이지의 RapidOCR 한국어 인식
- 표의 행·열·셀·헤더·병합셀 구조 복원
- 원시 OCR 다각형 좌표·축 정렬 경계·인식 신뢰도 보존
- 표 셀 좌표·행/열 인덱스·병합 범위 보존
- JSON·HTML·Markdown·입력·모델·출력 SHA-256 기록
- 실패 시 출력 미게시와 소유권 표식이 있는 staging 정리
- 공고번호·날짜·면적·지역·세금·법적 효력 사람 검수

### 3.2 제외

- pypdf 또는 PyMuPDF 교체
- Docling이 원본 PDF를 직접 파싱하는 경로
- OCR 결과만으로 정책·세금·공간 사실을 `VERIFIED`로 승격
- OCR 결과 또는 표 구조의 자동 RAG 공개 승인
- PaddleOCR·PaddlePaddle 실행 패키지 유지
- 모델 학습·미세조정
- 손글씨·지도 경계의 법적 판정
- 관련 없는 전체 프로젝트 테스트

## 4. 검토한 접근법

### 4.1 채택: RapidOCR + Docling/TableFormer

RapidOCR는 Windows CPU에서 ONNX Runtime으로 한국어 PP-OCRv5 mobile 모델을
실행하고 텍스트·다각형 좌표·인식 신뢰도를 반환한다. Docling/TableFormer는
페이지 레이아웃과 표의 행·열·셀·병합 구조를 복원한다.

장점은 표 구조를 일급 데이터로 보존하고, Docling의 lossless JSON과 HTML에서
병합셀 정보를 유지할 수 있다는 점이다. 단점은 모델 의존성이 무겁고, Docling의 표준
문서 JSON만으로 RapidOCR의 토큰별 원시 신뢰도를 모두 보존할 수 없어 별도 감사용
RapidOCR 실행이 필요하다는 점이다.

### 4.2 보류: RapidOCR + img2table

img2table은 OpenCV 기반으로 CPU 부담이 작고 RapidOCR 연동, 병합셀, 테두리 없는 표,
셀 좌표, DataFrame·HTML 출력을 지원한다. 그러나 공식 문서도 복잡한 표에서 OpenCV
탐지 한계를 명시한다. 관보의 다단 헤더와 불규칙 표를 주 구조 엔진으로 맡기기에는
보수적인 조사 게이트 요구와 맞지 않아 보조 후보로 보류한다.

### 4.3 제외: RapidOCR + Microsoft Table Transformer 직접 통합

Microsoft Table Transformer는 행·열·헤더·spanning cell 객체를 세밀하게 예측한다.
그러나 표 탐지, crop 좌표 변환, OCR 토큰 셀 배치, 병합셀 후처리를 직접 구현해야 하며
공식 upstream이 2023년 이후 사실상 정체돼 있다. 현재 T112 범위에 비해 통합 비용과
유지보수 위험이 크므로 제외한다.

## 5. 구성요소

### 5.1 PDF 경계

기존 pypdf 경계는 다음을 담당한다.

- 입력 확장자·파일 존재 여부 검사
- 암호화·손상 여부 검사
- 페이지 수 확인
- 페이지별 내장 텍스트 추출
- 처리 전후 원본 SHA-256 비교

Docling은 이 경계를 대체하지 않는다.

### 5.2 페이지 렌더러

기존 PyMuPDF 렌더러가 모든 페이지를 300 DPI, 알파 없는 PNG로 생성한다. 이미지와
PDF 좌표 변환은 다음 고정식으로 기록한다.

`pdf_point = image_pixel × 72 / 300`

회전·기울기 보정을 적용하면 원본 좌표 변환 행렬을 별도로 기록해야 한다. 좌표 변환을
재현할 수 없으면 해당 페이지를 성공 처리하지 않는다.

### 5.3 RapidOCR 감사 실행기

RapidOCR 실행기는 다음 계약을 가진다.

- 실행 엔진: ONNX Runtime CPU
- 인식 모델: PP-OCRv5 Korean mobile
- 자동 모델 다운로드: 금지
- 원시 결과 필터: `0.0`으로 설정해 저신뢰 결과도 보존
- 사람 검수 임계값: 인식 신뢰도 `0.90` 미만
- 결과 단위: 텍스트 행
- 좌표: 원본 4점 다각형과 계산된 축 정렬 bbox를 모두 보존
- 신뢰도: 모델 인식 점수이며 보정된 확률로 해석하지 않음

각 OCR 블록에는 다음 필드를 기록한다.

- `text`
- `recognition_confidence`
- `polygon`
- `bbox`
- `reading_order`
- `model_name`
- `source_page_number`

### 5.4 Docling 레이아웃·TableFormer sidecar

모든 페이지 PNG를 Docling 이미지 입력으로 처리한다. 원본 PDF를 Docling에 넘기지
않는다. 첫 번째 패스는 OCR과 TableFormer를 끈 레이아웃 탐지 전용으로 모든 페이지에
실행한다. 두 번째 패스는 표가 탐지된 페이지에만 RapidOCR와 TableFormer를 켜서
실행한다.

- 장치: Windows CPU
- OCR backend: RapidOCR ONNX
- 표 구조 모드: TableFormer `accurate`
- 셀 매칭: 활성화
- 표 구조 원본: lossless JSON
- 사람 열람용 표: HTML
- Markdown: 파생 출력이며 병합셀의 권위 있는 원본이 아님

Docling 결과는 페이지별로 원본 PDF 페이지 번호와 다시 결합한다. 페이지 PNG 입력에서
생성되는 Docling 내부 페이지 번호만으로 원본 페이지를 식별하지 않는다.

### 5.5 계약·게시 계층

계약 계층은 RapidOCR 원본과 Docling 구조를 검증하고, 모든 파일의 SHA-256을 계산한
뒤 매니페스트를 생성한다. 전체 검증을 통과한 경우에만 staging 디렉터리를 최종 출력
경로로 원자적으로 바꾼다.

## 6. 페이지 처리 흐름

1. 입력 PDF SHA-256을 계산한다.
2. pypdf로 유효성·암호화·페이지 수·내장 텍스트를 검사한다.
3. PyMuPDF로 모든 페이지를 300 DPI PNG로 렌더링한다.
4. 모든 페이지에 OCR·TableFormer를 끈 Docling 레이아웃 탐지를 실행한다.
5. 표가 없고 내장 텍스트 품질이 충분한 페이지는 `EMBEDDED_TEXT`로 처리한다.
6. 내장 텍스트 품질이 낮거나 표·복합 레이아웃이 있으면 RapidOCR 감사 실행을 수행한다.
7. 표가 탐지된 페이지는 Docling 내부 RapidOCR와 TableFormer `accurate`로 구조를
   생성한다.
8. RapidOCR 원시 텍스트와 TableFormer 셀 텍스트를 대조한다.
9. 페이지별 JSON·HTML·Markdown을 생성한다.
10. 페이지 수, 페이지 번호 연속성, 표 구조, 파일 크기, 스키마와 해시를 검증한다.
11. 처리 후 입력 PDF SHA-256이 동일한지 확인한다.
12. 매니페스트 검증 후에만 결과를 게시한다.

## 7. 처리 경로

기존 경로 열거형을 다음과 같이 교체한다.

| 기존 | 신규 | 의미 |
|---|---|---|
| `EMBEDDED_TEXT` | `EMBEDDED_TEXT` | 품질이 충분한 내장 텍스트 |
| `PADDLEOCR` | `RAPIDOCR` | RapidOCR 원시 텍스트 인식 |
| `PADDLEOCR_STRUCTURE` | `RAPIDOCR_TABLEFORMER` | RapidOCR 감사 출력과 TableFormer 구조 처리 |

표가 탐지된 페이지는 내장 텍스트가 충분해도 `RAPIDOCR_TABLEFORMER`를 사용한다.
내장 텍스트는 비교 근거로 함께 보존할 수 있지만 구조 처리 경로를 생략하지 않는다.

## 8. 산출물 계약

페이지 `0001`의 기본 산출물은 다음과 같다.

- `pages/0001.png`: 300 DPI 페이지 이미지
- `pages/0001.ocr.json`: RapidOCR 원시 텍스트·좌표·신뢰도
- `pages/0001.structure.json`: Docling 레이아웃·표 구조
- `pages/0001.md`: 사람이 읽는 페이지 결과
- `pages/0001.tables/0001.html`: 첫 번째 표의 병합셀 보존 HTML
- 필요한 경우 `pages/0001.tables/0002.html` 이후 파일

`0001.structure.json`의 표는 다음 필드를 포함한다.

- 표 번호와 페이지 bbox
- 행 수·열 수
- 셀 텍스트와 bbox
- 시작·종료 행/열 인덱스
- `row_span`·`col_span`
- 열 헤더·행 헤더 여부
- RapidOCR 원본 대조 상태

대조 상태는 다음으로 한정한다.

- `MATCHED`
- `MISMATCH`
- `NOT_COMPARABLE`

Markdown은 병합셀을 완전하게 표현할 수 없으므로 표의 권위 있는 구조 근거로 사용하지
않는다. 표 구조 감사에는 JSON과 HTML을 사용한다.

## 9. 매니페스트와 재현성

출력 계약 변경은 비호환 변경이므로 매니페스트 스키마를 `2.0.0`으로 올린다.
런타임에는 다음을 기록한다.

- Python 버전
- RapidOCR 버전
- ONNX Runtime 버전과 execution provider
- Docling 버전
- docling-ibm-models 버전
- RapidOCR 한국어 인식 모델 이름·출처·바이트·SHA-256
- Docling 레이아웃 모델 이름·출처·바이트·SHA-256
- TableFormer 모델 이름·모드·출처·바이트·SHA-256
- 렌더링 DPI
- OCR 원시 보존 임계값
- 사람 검수 신뢰도 임계값

정확한 패키지 버전은 구현 계획에서 현재 Windows Python 3.12와 설치 가능한 조합을
선정한 뒤 lock 파일에 고정한다. 구현은 범위 연산자에 의존하지 않고 확정된 정확한
버전을 사용한다.

모델은 구현 전에 지정된 로컬 경로에 내려받아 SHA-256을 잠근다. 실행 중 네트워크
다운로드가 발생하면 실패 처리한다.

## 10. 실패 처리

다음 조건에서는 최종 출력 경로를 만들지 않는다.

- 입력 PDF 손상·암호화·페이지 없음
- 입력 PDF가 처리 중 변경됨
- 패키지 버전·모델 이름·모델 SHA-256 불일치
- 자동 모델 다운로드 시도
- ONNX Runtime CPU provider 사용 불가
- RapidOCR 대상 페이지의 텍스트 결과 0건
- 표가 탐지됐지만 행·열·셀 결과가 없음
- 셀의 행·열 범위가 음수·역전·범위 초과
- 서로 모순되는 셀 범위 또는 해석할 수 없는 페이지 좌표
- 페이지 수 불일치·페이지 번호 누락
- 빈 JSON·HTML·Markdown
- 스키마 검증 실패
- 파일 해시 검증 실패
- 자식 프로세스 네이티브 충돌·비정상 종료

실패 시 소유권 표식이 정확히 일치하는 staging 디렉터리만 정리한다. 같은 접두사의
사용자 디렉터리는 삭제하지 않는다.

## 11. 사람 검수 경계

다음 조건은 `PENDING_HUMAN_REVIEW`를 강제한다.

- RapidOCR 인식 신뢰도 `0.90` 미만
- RapidOCR 원시 텍스트와 TableFormer 셀 텍스트 불일치
- 병합셀 또는 다단 헤더 존재
- 페이지를 넘어 이어지는 표
- 공고번호
- 법적 날짜
- 면적
- 지역·관할명
- 세금 규칙
- 법적 효력
- 공간 경계
- 원문 이용권한

OCR와 표 구조 결과만으로 정책·세금·공간 사실을 `VERIFIED`로 변경하지 않는다.
승인되지 않은 파생물을 공개 fixture, 판정 또는 RAG에 넣지 않는다.

## 12. 검증 설계

검증 실행은 별도 사용자 승인 후에만 수행한다.

### 12.1 계약·회귀 범위

- RapidOCR 결과 어댑터
- 다각형·bbox 좌표 변환
- 신뢰도 보존과 검수 상태
- 신규 경로 열거형
- 매니페스트 `2.0.0` 스키마
- 행·열·셀·병합셀 구조
- JSON·HTML·Markdown·해시 기록
- 모델 잠금과 자동 다운로드 금지
- 빈 OCR·빈 표·불일치·페이지 누락 fail-closed
- 네이티브 자식 충돌 staging 정리
- 기존 T112 전용 계약·회귀 테스트의 신규 엔진 전환

### 12.2 실제 관보 승인 표본

다음 원본 네 건을 사용한다.

1. `2017-114.pdf`
2. `2018-151.pdf`
3. `2022-189.pdf`
4. `2023-001.pdf`

네 건 모두 다음을 충족해야 한다.

- 모든 페이지 처리
- 페이지 번호 누락 없음
- 예상 표 전부 탐지
- 표 행·열 수 원문과 일치
- 병합셀 범위 원문과 일치
- 공고번호·날짜·면적·지역명 핵심 셀 누락 없음
- JSON·HTML에서 표 구조 재현 가능
- 원본·페이지·모델·출력 SHA-256 기록
- 사람 대조 기록 완료

네 건 중 하나라도 실패하면 T112를 완료 처리하지 않는다. 관련 없는 전체 프로젝트
테스트는 실행하지 않는다.

## 13. 라이선스와 고지

- RapidOCR 엔지니어링 코드: Apache-2.0
- ONNX Runtime: MIT
- Docling·docling-core·docling-ibm-models 추론 코드: MIT
- PP-OCR 계열 모델: 모델 저작권·출처 고지 필요
- Docling 모델 저장소: artifact별 CDLA-Permissive-2.0 또는 Apache-2.0 매핑 확인 필요

구현 계획에서 실제로 고정하는 패키지와 모델별 라이선스를
`THIRD_PARTY_NOTICES.md`에 기록한다. 모델 저장소가 선언한 복수 라이선스를 하나로
추정하지 않고 artifact별 근거가 확인되지 않으면 배포 상태를 `PENDING_REVIEW`로 둔다.

## 14. 승인 경계

2026-07-28에 다음 설계가 사용자에게 승인됐다.

- PaddleOCR만 교체하고 pypdf·PyMuPDF 유지
- Windows 외부 오픈소스 실행 구성 허용
- 표·테이블 구조 인식 필수
- Paddle 계열 모델을 ONNX로 실행하는 RapidOCR 허용
- RapidOCR + Docling/TableFormer 아키텍처
- 페이지별 데이터 흐름과 산출물 계약
- fail-closed 실패 처리와 사람 검수 기준

이 문서 승인 후 별도의 구현 계획을 작성한다. 패키지 설치, 코드 변경, 모델 다운로드,
테스트 실행은 구현 계획과 실행 범위를 사용자에게 다시 승인받은 뒤 수행한다.

## 15. 공식 근거

- [RapidOCR 저장소](https://github.com/RapidAI/RapidOCR)
- [RapidOCR 모델 목록](https://rapidai.github.io/RapidOCRDocs/main/model_list/)
- [RapidOCR 사용법](https://rapidai.github.io/RapidOCRDocs/main/install_usage/rapidocr/usage/)
- [ONNX Runtime 설치 문서](https://onnxruntime.ai/docs/install/)
- [Docling 저장소](https://github.com/docling-project/docling)
- [Docling 모델 카탈로그](https://docling-project.github.io/docling/usage/model_catalog/)
- [Docling 지원 입력·출력](https://docling-project.github.io/docling/usage/supported_formats/)
- [Docling 직렬화와 병합셀](https://docling-project.github.io/docling/concepts/serialization/)
- [Docling pipeline options](https://docling-project.github.io/docling/reference/pipeline_options/)
- [docling-ibm-models 저장소](https://github.com/docling-project/docling-ibm-models)
- [img2table 저장소](https://github.com/xavctn/img2table)
- [Microsoft Table Transformer 저장소](https://github.com/microsoft/table-transformer)

---

## English AI Context

```yaml
design_id: RAPIDOCR_DOCLING_PDF_RESEARCH_PIPELINE
designed_on: 2026-07-28
status: APPROVED_FOR_IMPLEMENTATION
supersedes:
  - docs/superpowers/specs/2026-07-28-paddleocr-pdf-recognition-design.md
task: T112
scope: research_only_government_pdf_recognition

approved_decisions:
  replace_only:
    - paddleocr_runtime
    - paddlepaddle_runtime
  retain:
    - pypdf_pdf_validation
    - pymupdf_300_dpi_rendering
    - atomic_publish
    - sha256_audit
    - human_review_gate
  allow_paddle_trained_onnx_model: true
  table_structure_required: true

runtime:
  platform: windows_cpu
  isolated_python: "3.12"
  ocr_engine: RapidOCR
  inference_engine: ONNX_Runtime_CPU
  recognition_model:
    family: PP-OCRv5
    language: korean
    size_class: mobile
  layout_engine: Docling
  table_engine: TableFormer
  table_mode: accurate
  docling_input: per_page_300_dpi_png_only
  docling_must_not_parse_original_pdf: true
  network_model_download_during_run: forbidden
  raw_ocr_retention_threshold: 0.0
  exact_package_versions: select_compatible_then_pin_in_implementation_plan

page_flow:
  - validate_pdf_with_pypdf
  - render_every_page_with_pymupdf_300_dpi
  - run_docling_layout_only_detection_on_every_page
  - select_embedded_text_or_rapidocr
  - run_rapidocr_audit_pass_on_low_text_table_or_complex_pages
  - run_docling_tableformer_on_table_pages
  - compare_rapidocr_raw_text_with_table_cell_text
  - validate_schema_page_continuity_hashes_and_table_topology
  - atomically_publish_only_after_full_success

routes:
  - EMBEDDED_TEXT
  - RAPIDOCR
  - RAPIDOCR_TABLEFORMER

manifest:
  schema_version: "2.0.0"
  record:
    - input_pdf_sha256
    - page_png_sha256
    - package_versions
    - execution_provider
    - model_names_sources_sizes_sha256
    - render_dpi
    - raw_ocr_threshold
    - human_review_threshold
    - output_file_sha256
    - page_routes
    - review_status

page_artifacts:
  image: pages/NNNN.png
  raw_ocr: pages/NNNN.ocr.json
  structure: pages/NNNN.structure.json
  human_markdown: pages/NNNN.md
  table_html: pages/PPPP.tables/TTTT.html

raw_ocr_block:
  fields:
    - text
    - recognition_confidence
    - polygon
    - bbox
    - reading_order
    - model_name
    - source_page_number

table_structure:
  authoritative_formats:
    - JSON
    - HTML
  non_authoritative_human_format:
    - Markdown
  fields:
    - table_number
    - table_bbox
    - num_rows
    - num_columns
    - cell_text
    - cell_bbox
    - row_offsets
    - column_offsets
    - row_span
    - col_span
    - header_flags
    - raw_ocr_comparison_status
  comparison_status:
    - MATCHED
    - MISMATCH
    - NOT_COMPARABLE

fail_closed_on:
  - corrupt_encrypted_or_empty_pdf
  - input_changed_during_processing
  - package_model_or_hash_mismatch
  - runtime_model_download_attempt
  - missing_cpu_execution_provider
  - empty_required_ocr
  - detected_table_without_rows_columns_or_cells
  - invalid_or_conflicting_cell_topology
  - untraceable_coordinate_transform
  - page_count_mismatch_or_page_gap
  - empty_output
  - schema_or_hash_validation_failure
  - native_child_crash

human_review_required:
  confidence_below: 0.90
  conditions:
    - raw_ocr_table_cell_mismatch
    - merged_or_multilevel_header
    - cross_page_table
    - notice_number
    - legal_date
    - area
    - jurisdiction
    - tax_rule
    - legal_effect
    - spatial_boundary
    - source_rights

acceptance_samples:
  - 2017-114.pdf
  - 2018-151.pdf
  - 2022-189.pdf
  - 2023-001.pdf
acceptance_requires:
  - all_pages_processed
  - no_page_gaps
  - all_expected_tables_detected
  - row_and_column_counts_match_source
  - merged_cell_ranges_match_source
  - no_missing_critical_legal_cells
  - reproducible_json_and_html_structure
  - complete_sha256_chain
  - recorded_human_comparison

publication_boundary:
  default_retention: TEMPORARY_NOT_RETAINED
  ocr_alone_cannot_mark_fact_verified: true
  unapproved_derivatives_for_public_fixture_or_rag: forbidden

execution_boundary:
  design_document: USER_DOCUMENT_APPROVED
  implementation: COMPLETED
  automated_acceptance: PASS
  real_sample_execution: PASS
  human_acceptance: PENDING_USER_HUMAN_REVIEW
```
