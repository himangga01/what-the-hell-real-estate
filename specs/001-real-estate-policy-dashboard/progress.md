# 프로젝트 작업 현황 및 남은 작업

- **작성 기준일**: 2026-08-21
- **기준 브랜치**: `main`
- **기준 커밋**: `bf5c9e7` (`feat(research): add RapidOCR Docling PDF pipeline`)
- **기준 작업표**: [`tasks.md`](./tasks.md)

이 문서는 지금까지 실제로 저장소에 반영된 작업과 앞으로 진행해야 할 작업을 구분한다.
체크박스 상태와 조사 게이트를 우선하며, 코드 구현·자동 검증·사람 승인을 서로 다른
완료 조건으로 취급한다.

## 1. 현재 상태 요약

- 전체 작업: 112개
- 완료: 12개
- 미완료: 100개
- 현재 제품 상태: 프로젝트 설정, 조사 데이터 구조, HWP·PDF 조사 도구까지 구현됨
- 아직 제공할 수 없는 범위: 사용자용 대시보드, API, 주소 판정, 세금 분석, RAG,
  관리자 검수·게시, 배포
- 최우선 병목: T001·T002·T003·T112를 완료하고 T006 사람 승인 게이트를 통과하는 것

| 단계 | 완료 | 미완료 | 현재 판단 |
|---|---:|---:|---|
| Phase 1 심층 조사 | 3/8 | 5 | T004·T005·T111 완료, T001·T002·T003·T006·T112 미완료 |
| Phase 2 프로젝트 설정 | 7/7 | 0 | 설정 작업 완료 |
| Phase 3 공통 기반 | 0/15 | 15 | Phase 1 게이트 때문에 착수 대기 |
| Phase 4 US1/P1 MVP | 0/16 | 16 | 공통 기반 이후 진행 |
| Phase 5 US2/P2 | 0/19 | 19 | US1·세금 검수 기반 필요 |
| Phase 6 US3/P3 | 0/11 | 11 | 게시·권리 검토가 끝난 근거 필요 |
| Phase 7 US4/P4 | 0/13 | 13 | 공통 출처·검수 모델 이후 진행 |
| Phase 8 품질·운영 | 2/23 | 21 | T098·T099 완료, 나머지는 기능 구현 뒤 진행 |

Phase 2가 완료됐어도 애플리케이션 본체가 완성된 것은 아니다. 현재 저장소에는 제품용
API 엔트리 포인트, Alembic 마이그레이션, 프런트 `index.html`·`src`, 검수 fixture·seed와
제품 기능 테스트가 아직 없어 대시보드와 API를 실행할 수 없다.

## 2. 지금까지 완료한 작업

### 2.1 명세·저장소·재현 가능한 설정 기반

- Spec Kit 기반 `spec.md`, `plan.md`, `research.md`, `tasks.md`, 데이터 모델과 API·규칙
  계약을 작성했다.
- Python 3.14 백엔드와 React 19.2/Vite 8.1 프런트 의존성, PostgreSQL 18·PostGIS·
  pgvector 구성을 정의했다.
- 백엔드 `uv.lock`, 프런트 `package-lock.json`, Ruff·Pyright·ESLint·TypeScript·Prettier,
  저장소 위생·재현 설치 검사와 GitHub Actions CI를 추가했다.
- 작업표 기준 T007~T013, T098, T099가 완료 상태다.

주요 경로:

- [`README.md`](../../README.md)
- [`plan.md`](./plan.md)
- [`tasks.md`](./tasks.md)
- [`contracts/`](./contracts/)
- [`.github/workflows/ci.yml`](../../.github/workflows/ci.yml)

### 2.2 심층 조사 데이터 구조와 초기 스냅샷

- 정책 사건 105건과 사건 관계 42건을 정규화했다.
- 규제 지정 수단 45건과 투기지역 증거 연결 7건을 정리했다.
- 출처 권리 21행과 취득세·재산세·종합부동산세·양도소득세 카드 4종을 작성했다.
- 전자관보 PDF 4건을 불변 캡처하고 원본 SHA-256 매니페스트를 기록했다.
- PDF 인식 검수 기록을 포함한 조사 산출물 13개의 byte 수·SHA-256을
  `cutoff-manifest.csv`에 고정했다.
- 작업표 기준 T004와 T005가 완료 상태다.

이 수치는 현재 저장된 조사 산출물의 규모다. 전국 정책·규제 이력의 완전성을 증명하거나
정책·세금·공간·권리 담당자의 승인을 대체하지 않는다.

주요 경로:

- [`research-data/README.md`](./research-data/README.md)
- [`source-register.md`](./source-register.md)
- [`research-data/cutoff-manifest.csv`](./research-data/cutoff-manifest.csv)
- [`checklists/research-readiness.md`](./checklists/research-readiness.md)

### 2.3 `rhwp` 기반 HWP 조사 추출

- 공식 `edwardkim/rhwp` `v0.7.18` archive와 실행 파일을 SHA-256으로 검증하는
  fail-closed 임시 추출 파이프라인을 구현했다.
- 입력 변경, 리디렉션, 예상 밖 출력, 손상 파일과 부분 게시를 차단하고 입력·도구·출력
  해시 매니페스트를 기록한다.
- 작업표 기준 T111은 완료 상태다.
- 저장소에 기록된 과거 실행 증거는 단위 테스트 25건 통과와 text·Markdown 각 18페이지
  통합 추출이다. 이번 현황 문서 작성 과정에서 해당 테스트를 다시 실행하지 않았다.
- HWPX 텍스트 추출은 고정 버전 호환성 검증 전까지 비활성이다.

주요 경로:

- [`scripts/research/RhwpPipeline.psm1`](../../scripts/research/RhwpPipeline.psm1)
- [`scripts/research/extract-hwp.ps1`](../../scripts/research/extract-hwp.ps1)
- [`docs/superpowers/specs/2026-07-17-rhwp-research-pipeline-design.md`](../../docs/superpowers/specs/2026-07-17-rhwp-research-pipeline-design.md)

### 2.4 RapidOCR·Docling PDF 조사 추출

- pypdf 내장 텍스트 우선, PyMuPDF 전체 페이지 300 DPI 렌더링, Docling 레이아웃 분석,
  RapidOCR·ONNX Runtime CPU 인식, TableFormer `accurate` 표 구조 복원 파이프라인을
  구현했다.
- 모델 7개 artifact·11개 파일의 출처·라이선스·크기·SHA-256을 잠그고 런타임 자동
  다운로드를 금지했다.
- 원본·페이지·OCR JSON·구조 JSON·표 HTML·Markdown 해시, polygon·bbox·confidence와
  표 topology를 기록하고 실패 시 부분 결과를 게시하지 않는다.
- 저장소에 기록된 과거 자동 회귀 증거는 `508 passed, 1 skipped`다.
- 전자관보 4건은 각각 1/1쪽을 실제 처리했고 입력·산출물 해시 연쇄가 일치했다.
- 기존 PaddleOCR·PaddlePaddle 실행 구성은 Windows `phi.dll` 접근 위반 때문에
  중단하고 현재 구성으로 대체했다.

T112는 아직 완료가 아니다. 위 4건은 AI 시각 사전대조만 끝났으며 사람 최종 검수와
원문 권리 검토가 남아 있다. 또한 네 문서 모두 실제 행·열 표가 없어 TableFormer의
실제 표 인수 근거가 없다.

주요 경로:

- [`tools/pdf-ocr/`](../../tools/pdf-ocr/)
- [`scripts/research/extract-pdf.ps1`](../../scripts/research/extract-pdf.ps1)
- [`research-data/pdf-ocr-acceptance.md`](./research-data/pdf-ocr-acceptance.md)
- [`docs/superpowers/specs/2026-07-28-rapidocr-docling-pdf-recognition-design.md`](../../docs/superpowers/specs/2026-07-28-rapidocr-docling-pdf-recognition-design.md)

## 3. 최우선 남은 작업: Phase 1 조사 게이트

| 작업 | 현재까지 확보한 내용 | 남은 작업 | 완료 기준 |
|---|---|---|---|
| T001 정책 사건 전수 조사 | 사건 105건, 관계 42건 | 전국 기관별 역방향 열거, 중복·누락 대조, 불변 원문이 없는 101건 캡처 | 발표·공포·시행·유예·연장·정정·해제·종료를 분리하고 각 검증 사건에 공식 URL·공고번호·시행일·selector·해시 기록 |
| T002 출처·권리 조사 | 출처 권리 21행, 공식 호스트 12곳 임시 관찰 | robots·약관·권리 응답 바이트와 해시 보존, 하위 지자체 등록, 주소 API 이용조건·장애 정책 승인 | 출처별 역할·SLA·정확도·권리·장애 시 공식 확인 경로와 증거 해시 확정 |
| T003 4종 규제·경계 | 지정 수단 45건, 관보 4건 캡처 | 서울 최소 28개 묶음행·경기 최소 24개 지정 수단 대응, 전국 지정·해제·연장, 필지·도면·조건·행정코드 정규화 | 4종 규제의 공고와 `[valid_from, valid_to)` 구간 및 공간 경계 근거 전수 대조 |
| T112 PDF 인수 | 코드·자동 회귀·관보 4건 실제 처리 | 4건 핵심 필드 사람 대조, 원문 권리 검토, 실제 표가 있는 권리 허용 PDF의 행·열·병합셀 검수 | 4건 모두 `HUMAN_REVIEWED`, 권리 검토 완료, 실제 표 인수 근거 기록 |
| T006 최종 조사 승인 | 13개 산출물 컷오프·해시 기록 | 정책·세금·공간·권리 담당 실명 검수와 승인 커밋 | 모든 차단 사유 해소, 4개 역할 승인, T006 완료 명시 승인 |

T004 세금 카드 작성과 T005 권리 정책 기록은 완료됐지만, 내용의 사람 검수와 T006 최종
승인을 대신하지 않는다. Phase 1 게이트를 통과하기 전에는 `PARTIAL`, `NOT_CAPTURED`,
`TEMPORARY_NOT_RETAINED`, `PENDING_REVIEW` 자료를 공개 fixture·판정·RAG에 넣지 않는다.

## 4. 조사 게이트 이후 구현 순서

### 4.1 Phase 3 공통 기반 — T014~T028

1. 계약·시간·금액·규칙 컴파일·로그 비식별 실패 테스트를 먼저 작성한다.
2. DB 연결과 출처·정책·공간·규칙·검수 모델 및 Alembic 마이그레이션을 구현한다.
3. 제한된 규칙 DSL, 컴파일러, 3값 평가기, 불변 번들과 검수 fixture 로더를 구현한다.

### 4.2 Phase 4 US1/P1 MVP — T029~T044, T100~T102

- 현재 정책 조회와 주소별 4종 규제 판정 API·서비스·UI를 구현한다.
- 이용조건이 승인된 주소 제공자를 선택하고 운영 어댑터를 구현한다.
- 대상 사용자 30명의 단회 사용성 검증에서 180초 이내 성공률 90% 이상을 기록한다.

### 4.3 Phase 5 US2/P2 — T045~T063

- 취득·보유·양도 분석 계약, 세목별 주택 수와 3값 규칙 평가를 구현한다.
- 사람 검수가 끝난 취득·보유·양도 규칙팩과 골든 사례를 구현한다.
- 무저장 시나리오 위저드와 근거·누락·미지원 상태가 포함된 결과 UI를 구현한다.

### 4.4 Phase 6 US3/P3 — T064~T074

- 게시·권리 검토가 끝난 근거만 청킹·검색한다.
- 정책 이력, 하이브리드 검색과 주장별 인용을 구현한다.
- 근거 부족이나 개인 적용·세액 질문에는 답을 추정하지 않고 거부하거나 분석 API로 안내한다.

### 4.5 Phase 7 US4/P4 — T075~T087, T103~T104

- 공식 출처 어댑터, 조건부 요청·속도 제한·불변 수집·diff를 구현한다.
- 원문·추출·규칙·근거·골든 사례의 검수·승인·반려·게시 서비스를 구현한다.
- 역할 기반 관리자 API·검수 작업대와 예약 수집·신선도 CLI를 구현한다.

### 4.6 Phase 8 품질·운영·배포 — T088~T097, T105~T110

- 성능, 접근성, 보안, 개인정보 보존, 백업·복구, 운영 문서와 참조 경계 검사를 완료한다.
- health/readiness, 비루트 컨테이너, staging·production 대상, build-once CD와 롤백을 구현한다.
- P1 fixture와 릴리스 범위를 고정하고 깨끗한 환경에서 최종 인수 절차를 수행한다.

## 5. 외부 결정과 사람 승인이 필요한 항목

- 정책·세금·공간·권리 담당자의 T006 실명 승인
- 전자관보 4건과 실제 표 PDF에 대한 T112 사람 검수
- 운영 주소 제공자의 약관·정확도·개인정보·장애 정책 승인
- 30명 P1 사용성 검증 참여와 결과 승인
- staging·production 호스팅 대상, 리전, 도메인, 비밀 주입, 객체 저장소, 네트워크,
  비용 한도와 운영 책임 승인
- production 승격과 롤백 훈련의 사람 승인

## 6. 다음 실행 권장 순서

1. T001·T002·T003을 병렬로 마무리한다.
2. T112의 관보 4건 사람 검수와 실제 표 PDF 인수를 완료한다.
3. 정책·세금·공간·권리 담당자가 T006을 승인한다.
4. Phase 3 T014~T028을 테스트 우선으로 구현한다.
5. US1/P1을 독립 MVP로 완성한다.
6. US2 → US3 → US4 순으로 기능을 확장한다.
7. 품질·운영·배포 게이트를 완료한다.

## 7. 검증 및 Git 기록 범위

- 이 문서는 Git 이력, 현재 `tasks.md`, 조사 체크리스트와 인수 보고서를 읽기 전용으로
  대조해 작성했다.
- 기존 테스트 수치는 당시 저장소에 기록된 과거 실행 증거다. 사용자 지침에 따라 이번
  문서 작성에서는 테스트를 새로 실행하지 않았다.
- 기존 `temp/` OCR 실행 산출물은 임시·미승인 파생물이므로 이 문서 커밋에서 제외한다.
- 게시 대상은 `origin/main`이며, 문서 작성 당시 원격 기본 브랜치는
  `origin/codex/real-estate-dashboard`였다. 기본 브랜치 변경이나 PR 생성은 이 작업 범위가 아니다.

---

## English AI Context

```yaml
document: project_progress_and_remaining_work
status_date: 2026-08-21
baseline:
  branch: main
  commit: bf5c9e7
  remote: origin
  push_target: origin/main
  remote_default_at_write_time: origin/codex/real-estate-dashboard

task_summary:
  total: 112
  completed: 12
  pending: 100
  phase_status:
    phase_1_research: {completed: 3, total: 8}
    phase_2_setup: {completed: 7, total: 7}
    phase_3_foundation: {completed: 0, total: 15}
    phase_4_us1: {completed: 0, total: 16}
    phase_5_us2: {completed: 0, total: 19}
    phase_6_us3: {completed: 0, total: 11}
    phase_7_us4: {completed: 0, total: 13}
    phase_8_quality_delivery: {completed: 2, total: 23}

completed_scope:
  - speckit_spec_plan_tasks_and_contracts
  - reproducible_backend_frontend_database_setup
  - dependency_locks_repository_hygiene_and_ci
  - partial_research_dataset_and_cutoff_manifest
  - rhwp_v0_7_18_fail_closed_research_extraction
  - rapidocr_onnx_docling_tableformer_pdf_research_pipeline

historical_evidence_not_rerun_for_this_document:
  rhwp:
    unit_tests: 25_passed
    integration_pages: {text: 18, markdown: 18}
  pdf_ocr:
    automated_regression: 508_passed_1_skipped
    actual_gazette_documents_processed: 4
    human_reviewed_outputs: 0
    actual_table_samples: 0

blocking_gate:
  tasks: [T001, T002, T003, T006, T112]
  phase_3_start_requires: [T001, T002, T003, T004, T005, T006, T112]
  human_roles: [policy, tax, spatial, rights]
  publication_or_rag_elevation_before_gate: forbidden

ordered_remaining_work:
  - complete_T001_T002_T003
  - complete_T112_human_and_real_table_acceptance
  - obtain_T006_human_approvals
  - implement_phase_3_T014_T028
  - implement_US1_T029_T044_T100_T102
  - implement_US2_T045_T063
  - implement_US3_T064_T074
  - implement_US4_T075_T087_T103_T104
  - complete_quality_operations_delivery_T088_T097_T105_T110

verification_scope:
  documentation_cross_check: performed
  tests_rerun: false
  reason_tests_not_rerun: user_instruction_requires_separate_approval
  excluded_from_commit: temp/
```
