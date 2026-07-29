# T112 RapidOCR·Docling 실제 관보 인식 검수 기록

## 한국어 검수 기록

### 1. 검수 범위와 현재 판정

- 실행일: `2026-07-29`
- AI 시각 사전대조 시각: `2026-07-29T10:31:15+09:00`
- 실행 환경: Windows, Python 3.12.13, `CPUExecutionProvider`
- 런타임 잠금:
  RapidOCR 3.9.2, ONNX Runtime 1.28.0, Docling 2.115.0,
  docling-ibm-models 3.13.3
- 모델 잠금 검증:
  7 artifacts, 11 files, 413,788,439 bytes, 크기·SHA-256 일치
- 최종 자동 회귀:
  `508 passed, 1 skipped in 28.73s`
- 건너뜀:
  Windows 심볼릭 링크 생성 권한 부족(`WinError 1314`) 1건.
  같은 fail-closed 분기의 권한 독립 회귀는 통과했다.
- 실제 처리:
  승인된 PDF 4건 모두 종료 코드 0, 1/1 page 처리, page gap 없음.
- 산출물 해시 연쇄:
  원본 PDF와 매니페스트의 입력 크기·SHA-256, PNG·OCR JSON·구조 JSON·
  Markdown의 크기·SHA-256이 4건 모두 일치했다.
- 매니페스트 page 상태:
  원자 게시된 원본 그대로 `PENDING_HUMAN_REVIEW`.
- 이 보고서의 현재 최종 상태:
  `PENDING_USER_HUMAN_REVIEW`.
- 게시 승인: `false`
- RAG 투입 승인: `false`

Codex는 원본에서 생성된 300 DPI PNG와 Markdown·JSON을 시각적으로 대조했지만
사람 검수자가 아니다. 따라서 아래 `AI_VISUAL_MATCH`는 사전대조 결과이며
`HUMAN_REVIEWED`를 대신하지 않는다.

### 2. 실제 표 검수 제한

네 승인 PDF의 모든 페이지를 시각 확인한 결과 실제 행·열 표가 없었다.
페이지 테두리, 제목 구분선, 번호 목록은 표로 계산하지 않았다. 구조 결과의 표 수
0개는 네 원본과 일치한다.

자동 회귀는 행·열 수, 0-based half-open range, 병합셀, 다단 헤더,
교차 페이지 가능성, OCR-cell 비교와 TableFormer accurate 경로를 검증한다.
그러나 이번 네 실제 표본에는 실제 표가 없으므로, 이 보고서만으로 실표 인식 품질을
사람 검수 완료했다고 주장할 수 없다.

---

## 2017-114.pdf

- 최종 출력: `temp/pdf-ocr-acceptance/2017-114-final`
- 원본 SHA-256:
  `2ff1852bee51dbffa93ad59f174c2dab05fbb2d8b8b35fe17a78ff2511230af9`
- 매니페스트 SHA-256:
  `25c315bd7f97efd82ed87b220fba0e00b6974fd2ab01f63a8985c703cbe15f7e`
- 전체 페이지 수: 1
- 처리된 페이지 수: 1
- 페이지 누락: 없음
- route: `EMBEDDED_TEXT`
- 탐지된 표 수: 0
- page 최종 사람 판정: `PENDING_USER_HUMAN_REVIEW`

| 페이지 | 표 번호 | 원문 행×열 | 결과 행×열 | 병합셀 원문 | 병합셀 결과 | 판정 |
|---:|---:|---:|---:|---|---|---|
| 1 | NOT_APPLICABLE | 표 없음 | 0개 | NOT_APPLICABLE | NOT_APPLICABLE | AI_VISUAL_MATCH / HUMAN_PENDING |

| 핵심 필드 | 원문 값 | OCR/표 값 | 페이지 | 판정 | 검수자 | 검수 시각 |
|---|---|---|---:|---|---|---|
| 공고번호 | 기획재정부공고 제2017-114호 | 기획재정부공고제2017-114호 | 1 | AI_VISUAL_MATCH / HUMAN_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |
| 법적 날짜 | 2017년 8월 3일 | 2017년8월3일 | 1 | AI_VISUAL_MATCH / HUMAN_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |
| 면적 | NOT_APPLICABLE — 수치 면적 없음 | NOT_APPLICABLE — 수치 면적 없음 | 1 | AI_VISUAL_MATCH / HUMAN_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |
| 지역·관할 | 서울특별시 용산구·성동구·노원구·마포구·양천구·강서구·영등포구·서초구·강남구·송파구·강동구 및 세종특별자치시 | 동일 지역 문자열 추출 | 1 | AI_VISUAL_MATCH / HUMAN_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |
| 세금 규칙 | 소득세법 제104조의2 및 소득세법 시행령 제168조의3에 따른 부동산 지정지역 | 동일 법 조문과 지정 규칙 추출 | 1 | AI_VISUAL_MATCH / HUMAN_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |
| 법적 효력 | 2017년 8월 3일부터 지정해제일 전일까지 지정, 공고한 날부터 시행 | 동일 기간·부칙 추출 | 1 | AI_VISUAL_MATCH / HUMAN_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |
| 공간 경계 | 위 서울 11개 구 및 세종특별자치시 행정중심복합도시 건설예정지역 | 동일 경계 문구 추출 | 1 | AI_VISUAL_MATCH / HUMAN_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |
| 원문 이용권한 | PDF 본문에는 없음. source register: `ALLOWED`, `PDF_RENDERED_AND_VISUALLY_VERIFIED`; response headers `NOT_RETAINED` | 매니페스트 `PENDING_REVIEW`; OCR로 권한을 승격하지 않음 | 1 | NOT_APPLICABLE_TO_OCR / HUMAN_RIGHTS_REVIEW_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |

---

## 2018-151.pdf

- 최종 출력: `temp/pdf-ocr-acceptance/2018-151-final`
- 원본 SHA-256:
  `3643c6ae0cbb7fa85441964786c1be020240dcbf25e97a26cc627f6d6af5d908`
- 매니페스트 SHA-256:
  `50d21c8faf8d6df145605bd03237155cb8cfbd016bf95bec47b0e9ea1ad4e766`
- 전체 페이지 수: 1
- 처리된 페이지 수: 1
- 페이지 누락: 없음
- route: `EMBEDDED_TEXT`
- 탐지된 표 수: 0
- page 최종 사람 판정: `PENDING_USER_HUMAN_REVIEW`

| 페이지 | 표 번호 | 원문 행×열 | 결과 행×열 | 병합셀 원문 | 병합셀 결과 | 판정 |
|---:|---:|---:|---:|---|---|---|
| 1 | NOT_APPLICABLE | 표 없음 | 0개 | NOT_APPLICABLE | NOT_APPLICABLE | AI_VISUAL_MATCH / HUMAN_PENDING |

| 핵심 필드 | 원문 값 | OCR/표 값 | 페이지 | 판정 | 검수자 | 검수 시각 |
|---|---|---|---:|---|---|---|
| 공고번호 | 기획재정부공고 제2018-151호 | 기획재정부공고제2018-151호 | 1 | AI_VISUAL_MATCH / HUMAN_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |
| 법적 날짜 | 2018년 8월 28일 | 2018년 8월 28일 | 1 | AI_VISUAL_MATCH / HUMAN_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |
| 면적 | NOT_APPLICABLE — 수치 면적 없음 | NOT_APPLICABLE — 수치 면적 없음 | 1 | AI_VISUAL_MATCH / HUMAN_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |
| 지역·관할 | 서울특별시 종로구·중구·동대문구·동작구 | 동일 지역 문자열 추출 | 1 | AI_VISUAL_MATCH / HUMAN_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |
| 세금 규칙 | 소득세법 제104조의2 및 소득세법 시행령 제168조의3에 따른 부동산 지정지역 | 동일 법 조문과 지정 규칙 추출 | 1 | AI_VISUAL_MATCH / HUMAN_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |
| 법적 효력 | 2018년 8월 28일부터 지정해제일 전일까지 지정, 공고한 날부터 시행 | 동일 기간·부칙 추출 | 1 | AI_VISUAL_MATCH / HUMAN_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |
| 공간 경계 | 서울특별시 종로구·중구·동대문구·동작구 | 동일 경계 문구 추출 | 1 | AI_VISUAL_MATCH / HUMAN_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |
| 원문 이용권한 | PDF 본문에는 없음. source register: `ALLOWED`, `PDF_RENDERED_AND_VISUALLY_VERIFIED`; response headers `NOT_RETAINED` | 매니페스트 `PENDING_REVIEW`; OCR로 권한을 승격하지 않음 | 1 | NOT_APPLICABLE_TO_OCR / HUMAN_RIGHTS_REVIEW_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |

---

## 2022-189.pdf

- 최종 출력: `temp/pdf-ocr-acceptance/2022-189-final`
- 원본 SHA-256:
  `e54ac0bfe1196f2efdc9002e54a67aaedb801d80341d701e8cc417386e330f84`
- 매니페스트 SHA-256:
  `8b644b59db1c06af65cb9bf2ba761b47252c44ac4753ec76f483b775bda2689d`
- 전체 페이지 수: 1
- 처리된 페이지 수: 1
- 페이지 누락: 없음
- route: `EMBEDDED_TEXT`
- 탐지된 표 수: 0
- page 최종 사람 판정: `PENDING_USER_HUMAN_REVIEW`

| 페이지 | 표 번호 | 원문 행×열 | 결과 행×열 | 병합셀 원문 | 병합셀 결과 | 판정 |
|---:|---:|---:|---:|---|---|---|
| 1 | NOT_APPLICABLE | 표 없음 | 0개 | NOT_APPLICABLE | NOT_APPLICABLE | AI_VISUAL_MATCH / HUMAN_PENDING |

| 핵심 필드 | 원문 값 | OCR/표 값 | 페이지 | 판정 | 검수자 | 검수 시각 |
|---|---|---|---:|---|---|---|
| 공고번호 | 기획재정부공고 제2022-189호 | 기획재정부공고 제2022-189호 | 1 | AI_VISUAL_MATCH / HUMAN_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |
| 법적 날짜 | 2022년 9월 26일 | 2022년 09월 26일 | 1 | AI_VISUAL_MATCH / HUMAN_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |
| 면적 | NOT_APPLICABLE — 수치 면적 없음 | NOT_APPLICABLE — 수치 면적 없음 | 1 | AI_VISUAL_MATCH / HUMAN_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |
| 지역·관할 | 세종특별자치시 행정중심복합도시 건설 예정지역 | 동일 지역 문자열 추출 | 1 | AI_VISUAL_MATCH / HUMAN_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |
| 세금 규칙 | 소득세법 제104조의2 및 같은 법 시행령 제168조의3에 따른 부동산 지정지역 해제 | 동일 법 조문과 해제 규칙 추출 | 1 | AI_VISUAL_MATCH / HUMAN_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |
| 법적 효력 | 지정지역 해제, 공고한 날부터 시행 | 동일 해제·부칙 추출 | 1 | AI_VISUAL_MATCH / HUMAN_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |
| 공간 경계 | 건설교통부고시 제2006-418호의 세종 행정중심복합도시 건설 예정지역이며 특별법 제15조제1호에 따라 해제된 지역 포함 | 동일 경계·포함 문구 추출 | 1 | AI_VISUAL_MATCH / HUMAN_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |
| 원문 이용권한 | PDF 본문에는 없음. source register: `ALLOWED`, `PDF_RENDERED_AND_VISUALLY_VERIFIED`; response headers `NOT_RETAINED` | 매니페스트 `PENDING_REVIEW`; OCR로 권한을 승격하지 않음 | 1 | NOT_APPLICABLE_TO_OCR / HUMAN_RIGHTS_REVIEW_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |

---

## 2023-001.pdf

- 최종 출력: `temp/pdf-ocr-acceptance/2023-001-final`
- 원본 SHA-256:
  `fb9934260e5eeea8a662601dab9c8e7ea69d07bcfdcc5ad8625f990b9c1fa475`
- 매니페스트 SHA-256:
  `36936c5ab7a9ff5b3b5587cd65ed2af712d49fccffdee65d7e1cf9069455b42e`
- 전체 페이지 수: 1
- 처리된 페이지 수: 1
- 페이지 누락: 없음
- route: `EMBEDDED_TEXT`
- 탐지된 표 수: 0
- page 최종 사람 판정: `PENDING_USER_HUMAN_REVIEW`

| 페이지 | 표 번호 | 원문 행×열 | 결과 행×열 | 병합셀 원문 | 병합셀 결과 | 판정 |
|---:|---:|---:|---:|---|---|---|
| 1 | NOT_APPLICABLE | 표 없음 | 0개 | NOT_APPLICABLE | NOT_APPLICABLE | AI_VISUAL_MATCH / HUMAN_PENDING |

| 핵심 필드 | 원문 값 | OCR/표 값 | 페이지 | 판정 | 검수자 | 검수 시각 |
|---|---|---|---:|---|---|---|
| 공고번호 | 기획재정부공고 제2023-1호 | 기획재정부공고 제2023-1호 | 1 | AI_VISUAL_MATCH / HUMAN_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |
| 법적 날짜 | 2023년 1월 5일 | 2023년 01월 05일 | 1 | AI_VISUAL_MATCH / HUMAN_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |
| 면적 | NOT_APPLICABLE — 수치 면적 없음 | NOT_APPLICABLE — 수치 면적 없음 | 1 | AI_VISUAL_MATCH / HUMAN_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |
| 지역·관할 | 서울특별시 성동구·노원구·마포구·양천구·강서구·영등포구·강동구·종로구·중구·동대문구·동작구 | 동일 지역 문자열 추출 | 1 | AI_VISUAL_MATCH / HUMAN_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |
| 세금 규칙 | 소득세법 제104조의2 및 같은 법 시행령 제168조의3에 따른 부동산 지정지역 해제 | 동일 법 조문과 해제 규칙 추출 | 1 | AI_VISUAL_MATCH / HUMAN_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |
| 법적 효력 | 지정지역 해제, 공고한 날부터 시행 | 동일 해제·부칙 추출 | 1 | AI_VISUAL_MATCH / HUMAN_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |
| 공간 경계 | 위 서울특별시 11개 구 | 동일 경계 문구 추출 | 1 | AI_VISUAL_MATCH / HUMAN_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |
| 원문 이용권한 | PDF 본문에는 없음. source register: `ALLOWED`, `PDF_RENDERED_AND_VISUALLY_VERIFIED`; response headers `NOT_RETAINED` | 매니페스트 `PENDING_REVIEW`; OCR로 권한을 승격하지 않음 | 1 | NOT_APPLICABLE_TO_OCR / HUMAN_RIGHTS_REVIEW_PENDING | Codex AI 사전대조 | 2026-07-29T10:31:15+09:00 |

---

## 3. 완료 게이트

| 게이트 | 결과 | 근거 |
|---|---|---|
| T112 전용 자동 회귀 | PASS | 508 passed, 1 privilege-dependent skipped |
| 고정 런타임·CPU provider | PASS | 잠금 버전 일치, `CPUExecutionProvider` |
| 모델 파일 크기·SHA-256 | PASS | 7 artifacts, 11 files, 413,788,439 bytes |
| 네 PDF 전체 페이지 처리 | PASS | 각 1/1 page, page gap 없음 |
| 원본·산출물 해시 연쇄 | PASS | 네 출력 모두 독립 재계산 일치 |
| 실제 표 topology 대조 | NOT_APPLICABLE_TO_THESE_SAMPLES | 네 원본 모두 실제 표 없음 |
| 핵심 법적 필드 AI 사전대조 | PASS_WITH_HUMAN_PENDING | 원본 PNG와 Markdown 값 일치 |
| 원문 이용권한 사람 검수 | PENDING | register는 ALLOWED이나 response headers 미보존 gap 존재 |
| 사람 최종 판정 | PENDING | 사용자의 명시적 검수 승인 필요 |
| T112 완료 | NOT_COMPLETE | `HUMAN_REVIEWED` 조건 미충족 |

---

## English AI Context

```yaml
acceptance_id: T112_RAPIDOCR_DOCLING_GAZETTE
recorded_at: 2026-07-29T10:31:15+09:00
document_language_order:
  - korean_user_record
  - english_ai_context

runtime:
  python: 3.12.13
  rapidocr: 3.9.2
  onnxruntime: 1.28.0
  docling: 2.115.0
  docling_ibm_models: 3.13.3
  execution_provider: CPUExecutionProvider
  network_mode: offline

model_lock:
  artifacts: 7
  files: 11
  bytes: 413788439
  size_and_sha256: PASS

automated_tests:
  result: 508_passed_1_skipped
  skipped_reason: windows_symlink_creation_privilege_winerror_1314
  privilege_independent_fallback: PASS

samples:
  - file: 2017-114.pdf
    input_sha256: 2ff1852bee51dbffa93ad59f174c2dab05fbb2d8b8b35fe17a78ff2511230af9
    manifest_sha256: 25c315bd7f97efd82ed87b220fba0e00b6974fd2ab01f63a8985c703cbe15f7e
    pages: 1
    processed_pages: 1
    route: EMBEDDED_TEXT
    tables_in_source: 0
    tables_in_result: 0
    hash_chain: PASS
    ai_visual_precheck: MATCH
    human_status: PENDING_USER_HUMAN_REVIEW
  - file: 2018-151.pdf
    input_sha256: 3643c6ae0cbb7fa85441964786c1be020240dcbf25e97a26cc627f6d6af5d908
    manifest_sha256: 50d21c8faf8d6df145605bd03237155cb8cfbd016bf95bec47b0e9ea1ad4e766
    pages: 1
    processed_pages: 1
    route: EMBEDDED_TEXT
    tables_in_source: 0
    tables_in_result: 0
    hash_chain: PASS
    ai_visual_precheck: MATCH
    human_status: PENDING_USER_HUMAN_REVIEW
  - file: 2022-189.pdf
    input_sha256: e54ac0bfe1196f2efdc9002e54a67aaedb801d80341d701e8cc417386e330f84
    manifest_sha256: 8b644b59db1c06af65cb9bf2ba761b47252c44ac4753ec76f483b775bda2689d
    pages: 1
    processed_pages: 1
    route: EMBEDDED_TEXT
    tables_in_source: 0
    tables_in_result: 0
    hash_chain: PASS
    ai_visual_precheck: MATCH
    human_status: PENDING_USER_HUMAN_REVIEW
  - file: 2023-001.pdf
    input_sha256: fb9934260e5eeea8a662601dab9c8e7ea69d07bcfdcc5ad8625f990b9c1fa475
    manifest_sha256: 36936c5ab7a9ff5b3b5587cd65ed2af712d49fccffdee65d7e1cf9069455b42e
    pages: 1
    processed_pages: 1
    route: EMBEDDED_TEXT
    tables_in_source: 0
    tables_in_result: 0
    hash_chain: PASS
    ai_visual_precheck: MATCH
    human_status: PENDING_USER_HUMAN_REVIEW

required_status: HUMAN_REVIEWED
current_status: PENDING_USER_HUMAN_REVIEW
real_table_sample_coverage: NONE_IN_APPROVED_FOUR_SAMPLES
source_rights:
  register_status: ALLOWED
  evidence_status: PDF_RENDERED_AND_VISUALLY_VERIFIED
  response_headers: NOT_RETAINED
  human_review: PENDING
checks:
  all_pages_processed: PASS
  no_page_gaps: PASS
  table_count: PASS_FOR_ZERO_TABLE_SOURCES
  row_column_count: NOT_APPLICABLE
  merged_cell_ranges: NOT_APPLICABLE
  critical_legal_fields_ai_precheck: PASS
  critical_legal_fields_human_review: PENDING
  complete_sha256_chain: PASS
publication_authorized: false
rag_authorized: false
t112_complete: false
```
