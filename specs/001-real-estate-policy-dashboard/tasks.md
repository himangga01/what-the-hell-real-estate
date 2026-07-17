---
description: "대한민국 부동산 정책·세금 분석 대시보드 구현 작업"
---

# 구현 작업: 대한민국 부동산 정책·세금 분석 대시보드

**입력 문서**: [spec.md](./spec.md), [plan.md](./plan.md), [research.md](./research.md),
[data-model.md](./data-model.md), [rule-engine.md](./rule-engine.md),
[tax-support-matrix.md](./tax-support-matrix.md), [source-register.md](./source-register.md),
[contracts/](./contracts/)

**테스트 원칙**: 헌장에 따라 각 규칙·기능의 실패하는 테스트를 구현보다 먼저
작성한다. 특히 날짜, 금액, 세율과 면적은 `경계-1/경계/경계+1`, 시행일은
`전일/당일/익일`을 검사한다.

**작업 형식**: `[ID] [P?] [US?] 설명과 정확한 파일 경로`

- `[P]`: 다른 파일을 다루며 선행 의존성이 없어 병렬 진행 가능
- `[US1]`~`[US4]`: 기능 명세의 사용자 스토리 추적 태그
- 연구 완료와 기반 단계가 끝나기 전에는 공개 사용자 스토리를 구현하지 않는다.

## Phase 1: 심층 조사 완료 게이트

**목적**: 기사 요약이 아니라 정부 원문·공고·경계·세금 규칙을 게시 가능한
데이터로 전환하기 위한 조사 산출물을 먼저 완성한다.

- [ ] T001 [P] 2016-07-10~2026-07-10 정책 사건의 발표·공포·시행·유예·해제·종료와 공식 URL을 `specs/001-real-estate-policy-dashboard/research-data/policy-events.csv`에 전수 정리한다.
- [ ] T002 [P] 국가법령정보센터·전자관보·국토교통부·기획재정부·국세청·행정안전부·지자체와 운영 주소 정규화 후보 API의 출처 역할, SLA, 정확도, 장애 시 공식 확인 경로, robots·약관·권리와 캡처 해시를 `specs/001-real-estate-policy-dashboard/source-register.md`에 보강한다.
- [ ] T003 [P] 4종 규제의 지정·해제·연장 공고, 시행 구간, 행정구역·필지·도면과 조건을 `specs/001-real-estate-policy-dashboard/research-data/designations.csv`에 정규화한다.
- [x] T004 [P] 취득세·재산세·종부세·양도소득세의 세율·공제·비과세·중과·감면·경과규정 원문 카드를 `specs/001-real-estate-policy-dashboard/research-data/tax-rule-cards/`에 작성한다.
- [x] T005 [P] 원문별 전문 보존·공개·RAG 색인 허용 여부와 링크 전용 정책을 `specs/001-real-estate-policy-dashboard/research-data/source-rights.csv`에 기록한다.
- [ ] T006 정책·세금·공간·권리 담당자가 알려진 공백, 충돌 문서와 초기 컷오프 매니페스트를 검수하고 `specs/001-real-estate-policy-dashboard/checklists/research-readiness.md`를 승인한다.
- [x] T111 [P] HWP 첨부를 공식 `edwardkim/rhwp` `v0.7.18`과 `SHA256SUMS.txt`로 검증해 임시 text·Markdown과 입력·도구·출력 SHA-256 매니페스트를 생성하는 fail-closed 파이프라인을 `scripts/research/`에 구현하고 `THIRD_PARTY_NOTICES.md`, `specs/001-real-estate-policy-dashboard/source-register.md`와 조사 게이트에 증거를 기록한다.

**2026-07-17 진행 기록**:

- T001: 정책 사건 105건·사건 관계 42건으로 재정규화했다. 국토교통부 제목 색인 23건에서
  누락됐던 전매행위 제한 공고 7건을 추가하고, 2016-11-03·2017-06-19를 일반 효력일로
  보던 행을 실제 부령 공포·시행일로 교정했다. 전국 기관별 전수 역대조와 불변 원문이 없는
  101건의 캡처가 남아 미완료다.
- T002: 출처 권리 21행으로 기관·본문·첨부 역할을 분리하고 전자관보 권리, 법령정보센터의
  `STATUS_INDEX`, 주소 API 한계를 정정했다. 12개 공식 호스트의 robots와 주요 권리 페이지를
  임시 관찰했지만 응답 바이트·증거 해시를 보존하지 않았고 하위 지자체 등록도 남아 미완료다.
- T003: 규제 지정 수단(공고) 45건으로 정규화하고 투기지역 관보 4건을 불변 캡처·해시·렌더링
  검증했다. 서울 현황표에서 최소 28개 묶음행, 경기 현황표에서 최소 24개 지정 수단이 현재
  데이터에 대응하지 않아 전국 완전성 열거, 연장 공고, 필지·도면·행정구역 코드가 남아 미완료다.
- T006: 조사 산출물 12개를 `cutoff-manifest.csv`에 고정했고 매니페스트 SHA-256은
  `fc180839e67b367e73f9ae65bcc1dc8e87303987c6332dc1f32c376b9cf3e8d4`다. 자동 구조 검증과
  해시 생성은 정책·세금·공간·권리 담당자의 실명 승인 및 승인 커밋을 대체하지 않는다.

**게이트**: T001~T006이 모두 완료되고 정책·세금·공간·권리 담당자의 승인과 컷오프
매니페스트 해시가 기록돼야 Phase 3을 시작한다. `PARTIAL`, `NOT_CAPTURED`,
`TEMPORARY_NOT_RETAINED`, `PENDING_REVIEW` 자료는 공개 fixture·판정·RAG에 적재하지 않는다.

---

## Phase 2: 프로젝트 설정

**목적**: Python API, React 앱, DB와 자동 검증의 최소 골격을 만든다.

- [x] T007 `backend/pyproject.toml`에 Python 3.14, FastAPI, Pydantic, SQLAlchemy, Alembic, psycopg와 pytest 개발 의존성을 고정한다.
- [x] T008 [P] `frontend/package.json`과 `frontend/vite.config.ts`에 React 19.2, TypeScript, Vite 8.1, Tailwind CSS 4.3, Vitest와 Playwright를 구성한다.
- [x] T009 [P] PostgreSQL 18, PostGIS와 pgvector를 포함한 로컬 DB를 `infra/docker-compose.yml`과 `infra/db/init/001-extensions.sql`에 정의한다.
- [x] T010 [P] 비밀값 없이 설정 계약과 fixture 기본값을 `backend/.env.example`과 `frontend/.env.example`에 작성한다.
- [x] T011 [P] Ruff·Pyright·ESLint·Prettier 설정을 `backend/pyproject.toml`, `frontend/eslint.config.js`, `frontend/tsconfig.json`에 구성한다.
- [x] T012 [P] 잠금 파일 기반 설치, Ruff·Pyright·ESLint·타입 검사·빌드·백엔드·프런트·계약·골든 테스트와 공식 OpenAPI·JSON Schema 2020-12 검증을 실행하는 CI를 `.github/workflows/ci.yml`에 추가한다.
- [x] T013 Docker 또는 승인된 호환 런타임을 포함한 사전 요구사항, 개발·테스트·fixture 적재 명령과 현재 지원 범위를 `README.md`에 한국어 우선, English AI Context 순서로 기록한다.

---

## Phase 3: 공통 기반

**목적**: 모든 사용자 스토리가 공유하는 저장·규칙·감사·오류 기반을 만든다.

**중요**: 이 단계가 끝나기 전에는 US1~US4 구현을 시작하지 않는다.

### 실패 테스트 우선

- [ ] T014 [P] OpenAPI와 규칙 JSON Schema가 예제·금지 필드를 검증하는 계약 테스트를 `backend/tests/contract/test_design_contracts.py`에 작성한다.
- [ ] T015 [P] Asia/Seoul 반개구간, Decimal 원화, 반올림과 전일·당일·익일 속성 테스트를 `backend/tests/property/test_temporal_money_semantics.py`에 작성한다.
- [ ] T016 [P] 알 수 없는 연산자, 임의 코드, 과도한 AST, 규칙 겹침·순환·인용 누락의 컴파일 실패와 동일 번들 재현성 테스트를 `backend/tests/unit/rules/test_compiler_rejections.py`, `backend/tests/unit/rules/test_bundle_reproducibility.py`에 먼저 작성한다.
- [ ] T017 [P] 주소·금액·보유내역·토큰이 validation·500·timeout 로그에 없는지 `backend/tests/security/test_log_redaction.py`에 작성한다.

### 기반 구현

- [ ] T018 DB 연결, 트랜잭션과 설정 검증을 `backend/app/core/config.py`, `backend/app/db/session.py`에 구현한다.
- [ ] T019 PostGIS·pgvector 버전 확인과 기초 타입을 `backend/alembic/versions/0001_enable_extensions.py`에 마이그레이션한다.
- [ ] T020 [P] 출처·스냅샷·근거·검증 작업 모델을 `backend/app/domains/sources/models.py`와 `backend/alembic/versions/0002_sources.py`에 구현한다.
- [ ] T021 [P] 정책 사건·공간 버전·지정 수단·범위 모델을 `backend/app/domains/policies/models.py`, `backend/app/domains/geography/models.py`, `backend/alembic/versions/0003_policy_geography.py`에 구현한다.
- [ ] T022 [P] 규칙·경과규정·번들·골든 사례·검수 모델을 `backend/app/domains/rules/models.py`, `backend/app/domains/reviews/models.py`, `backend/alembic/versions/0004_rules_reviews.py`에 구현한다.
- [ ] T023 제한된 DSL AST, 연산자별 타입 스키마와 버전 고정 파생 사실 함수 레지스트리를 `backend/app/domains/rules/ast.py`, `backend/app/domains/rules/schema.py`, `backend/app/domains/rules/functions.py`에 구현한다.
- [ ] T024 정규 JSON·함수 구현 해시·의존성·충돌 검사를 `backend/app/domains/rules/compiler.py`에 구현해 T016을 통과시킨다.
- [ ] T025 3값 조건 평가, Decimal 계산, 컬렉션·기간 파생 함수와 사실 추적을 `backend/app/domains/rules/evaluator.py`, `backend/app/domains/rules/trace.py`에 구현한다.
- [ ] T026 불변 RuleBundle 빌드·고정·검증을 `backend/app/domains/rules/bundles.py`에 구현해 T016의 재현성 테스트를 통과시킨다.
- [ ] T027 RFC 9457 오류 응답, 요청 ID와 허용 목록 로깅을 `backend/app/core/errors.py`, `backend/app/core/logging.py`, `backend/app/main.py`에 구현해 T017을 통과시킨다.
- [ ] T028 검수 fixture 매니페스트의 해시·컷오프·알려진 공백을 검증하는 로더를 `backend/app/jobs/seed.py`, `scripts/seed/verified-fixtures/manifest.schema.json`에 구현한다.

**체크포인트**: 스키마·컴파일러·3값 평가·번들 재현·로그 비식별 테스트가 모두 통과한다.

---

## Phase 4: 사용자 스토리 1 — 현재 정책과 주소 규제 확인 (P1) 🎯 MVP

**목표**: 기준일에 시행 중인 정책만 보여주고 주소별 4종 규제를 독립적으로 판정한다.

**독립 테스트**: 고정된 정책·경계 fixture와 주소 제공자 stub만으로 현재 카드,
날짜 경계, 공간 중첩과 불확실성 상태를 검증한다. 세금·RAG·관리자 UI는 필요 없다.

### 실패 테스트 우선

- [ ] T029 [P] [US1] `GET /api/v1/policies/current`의 예정·종료 제외와 권위 역할·비어 있지 않은 해시·정확한 selector를 가진 decision source 계약을 `backend/tests/contract/test_current_policies_api.py`에 작성한다.
- [ ] T030 [P] [US1] `POST /api/v1/areas/resolve`의 4종 결과·조건부·공식 확인 계약을 `backend/tests/contract/test_area_resolve_api.py`에 작성한다.
- [ ] T031 [P] [US1] 발표일과 시행일이 다른 정책의 current-only 통합 테스트를 `backend/tests/integration/test_current_policy_projection.py`에 작성한다.
- [ ] T032 [P] [US1] 최소 5개 기준일을 포함해 2023-01-05, 2025-10-16/20, 2026-06-30/07-01/04/05 규제 경계 골든 사례를 `backend/tests/golden/test_designation_timeline.py`와 `backend/tests/fixtures/designations/`에 작성한다.
- [ ] T033 [P] [US1] 최소 30개 검증 주소로 필지 내부·외부·경계·중첩·도면 충돌과 과거 행정코드 공간 테스트를 `backend/tests/golden/test_geospatial_designations.py`에 작성한다.
- [ ] T034 [P] [US1] 기준일, 신선도, 텍스트 판정 상태와 키보드 흐름의 실패 E2E를 `frontend/tests/e2e/current-and-address.spec.ts`에 작성한다.

### 구현

- [ ] T035 [P] [US1] 기준일·게시 상태·유효구간과 검수된 `LEGAL_EFFECT/BOUNDARY` decision source로 현재 정책을 투영하는 조회 서비스를 `backend/app/domains/policies/current_service.py`에 구현한다.
- [ ] T036 [P] [US1] 외부 호출 없는 fixture 주소 정규화 어댑터를 `backend/app/domains/geography/providers/fixture.py`에 구현한다.
- [ ] T037 [US1] PNU·좌표와 기준일의 공간 버전을 연결하는 해석기를 `backend/app/domains/geography/resolver.py`에 구현한다.
- [ ] T038 [US1] 거래주체·유형·면적·동일 단지 조건과 불확실성을 평가하는 지정 서비스를 `backend/app/domains/geography/designation_service.py`에 구현한다.
- [ ] T039 [P] [US1] 현재 정책 전용 라우터를 `backend/app/api/v1/policies.py`에 구현해 T029와 T031을 통과시키고, 이력 endpoint 구현은 T071에 남긴다.
- [ ] T040 [US1] 주소 규제 라우터를 `backend/app/api/v1/areas.py`에 구현해 T030·T032·T033을 통과시킨다.
- [ ] T041 [P] [US1] 공통 레이아웃, 디자인 토큰, 기준일·신선도·근거 컴포넌트를 `frontend/src/app/`, `frontend/src/components/policy/`에 구현한다.
- [ ] T042 [US1] 현재 정책 대시보드를 `frontend/src/features/current-dashboard/`에 구현한다.
- [ ] T043 [US1] 주소 입력·정규화 확인·4종 규제 카드·공식 확인 CTA를 `frontend/src/features/address-analysis/`에 구현한다.
- [ ] T044 [US1] 모바일·키보드·스크린리더 회귀를 수정하고 `frontend/tests/e2e/current-and-address.spec.ts`를 통과시킨다.

**체크포인트**: US1만 배포해도 현재 정책과 주소 규제를 독립적으로 확인할 수 있다.

---

## Phase 5: 사용자 스토리 2 — 취득·보유·양도 시나리오 분석 (P2)

**목표**: 지원 행렬 안의 표준 사례를 결정론적으로 분석하고 그 밖에서는 명시적으로 멈춘다.

**독립 테스트**: 검수 규칙 fixture와 주소 stub만으로 분석한다. 생성 모델과
정책 타임라인 UI는 필요 없다.

### 실패 테스트 우선

- [ ] T045 [P] [US2] `POST /api/v1/analyses`의 무저장 입력·결과 상태·추적 계약을 `backend/tests/contract/test_analyses_api.py`에 작성한다.
- [ ] T046 [P] [US2] TRUE/FALSE/UNKNOWN 전파와 영향도별 누락 질문 테스트를 `backend/tests/unit/rules/test_three_valued_analysis.py`에 작성한다.
- [ ] T047 [P] [US2] 세대원별 소유지분·소유기간·당시 세대 귀속과 과거 처분 이력으로 취득세·양도세·종부세별 주택 수가 독립 파생되는지 `backend/tests/golden/test_tax_specific_home_counts.py`에 작성한다.
- [ ] T048 [P] [US2] 일반 주택 취득·중과·일시적 2주택·생애최초 감면 골든 사례를 `backend/tests/golden/tax/test_acquisition_pack.py`에 작성한다.
- [ ] T049 [P] [US2] 6월 1일·공시가격·주택 과세표준 상한·공제 경계 골든 사례를 `backend/tests/golden/tax/test_holding_pack.py`에 작성한다.
- [ ] T050 [P] [US2] 1세대 1주택·12억원·보유/거주·일시적 2주택·장기보유공제 골든 사례를 `backend/tests/golden/tax/test_disposal_pack.py`에 작성한다.
- [ ] T051 [P] [US2] 2026-05-09 전후, 계약금 증빙, 지역별 기한과 토허 여부 경과 테스트를 `backend/tests/golden/tax/test_2026_surcharge_transition.py`에 작성한다.
- [ ] T052 [P] [US2] 상속·증여 부분지원 안내, 공동명의·신탁·입주권·비거주자 미지원 종료와 개인정보 금지 필드를 `backend/tests/contract/test_analysis_safety_boundaries.py`에 작성한다.
- [ ] T053 [P] [US2] 단계형 입력, 누락 재질문, 결과 구성, 미지원 종료와 시나리오가 URL·localStorage·sessionStorage에 남지 않는 실패 E2E를 `frontend/tests/e2e/scenario-analysis.spec.ts`에 작성한다.

### 구현

- [ ] T054 [P] [US2] 세대원 유효기간, 구성원별 소유지분·소유기간, 과거 처분 이력, 소득·공시가격·직전 세부담을 표현하는 분석 DTO를 `backend/app/domains/analyses/schemas.py`에 구현하되 공통 주택 수와 사용자 제공 세법상 사건일 필드를 만들지 않는다.
- [ ] T055 [US2] 세법상 사건일, 세목별 주택 수, 보유·거주기간 파생 팩을 `backend/app/domains/analyses/facts.py`, `backend/rulesets/kr/common/`에 구현한다.
- [ ] T056 [P] [US2] 검수 완료된 취득 규칙팩을 `backend/rulesets/kr/acquisition/`과 `backend/app/domains/analyses/packs/acquisition.py`에 구현해 T048을 통과시킨다.
- [ ] T057 [P] [US2] 검수 완료된 보유 규칙팩을 `backend/rulesets/kr/holding/`과 `backend/app/domains/analyses/packs/holding.py`에 구현해 T049를 통과시킨다.
- [ ] T058 [P] [US2] 검수 완료된 양도·2026 경과 규칙팩을 `backend/rulesets/kr/disposal/`과 `backend/app/domains/analyses/packs/disposal.py`에 구현해 T050·T051을 통과시킨다.
- [ ] T059 [US2] 한 번 고정한 번들로 파생 사실·적용/제외/억제 규칙·계산 줄·누락·인용을 합치는 서비스를 `backend/app/domains/analyses/service.py`에 구현한다.
- [ ] T060 [US2] 분석 라우터와 무저장·로그 차단을 `backend/app/api/v1/analyses.py`에 구현해 T045·T052를 통과시킨다.
- [ ] T061 [US2] 취득·보유·양도별 필수 입력과 고급 예외를 분리한 위저드를 `frontend/src/features/scenario-analysis/ScenarioWizard.tsx`에 구현한다.
- [ ] T062 [US2] 입력 요약, 파생 주택 수, 적용·제외 규칙, 계산 줄, 누락·공식 확인·미지원 결과를 `frontend/src/features/scenario-analysis/AnalysisResult.tsx`에 구현한다.
- [ ] T063 [US2] 색상 외 텍스트·아이콘과 전문가 확인 경로를 보강하고 `frontend/tests/e2e/scenario-analysis.spec.ts`를 통과시킨다.

**체크포인트**: US2는 지원 범위 안에서 재현 가능한 결과를 내고, 지원 밖에서는
`UNSUPPORTED` 또는 `REQUIRES_OFFICIAL_CHECK`로 끝난다.

---

## Phase 6: 사용자 스토리 3 — 최근 10년 이력과 근거 RAG (P3)

**목표**: 현재 정책과 과거 이력을 분리해 탐색하고 검수된 원문만 인용해 설명한다.

**독립 테스트**: 게시 근거 fixture와 생성 모델 stub으로 검색·인용·거부를 검증한다.

### 실패 테스트 우선

- [ ] T064 [P] [US3] 정책 이력·근거 상세와 함께 `ANSWERED`의 주장별 인용, 근거 부족 무답변, 개인 판정 질문의 분석 라우팅 API 계약을 `backend/tests/contract/test_history_evidence_questions_api.py`에 작성한다.
- [ ] T065 [P] [US3] 게시·권리·기준일 필터, 전문+벡터 결합, 근거 부족 거부와 개인 사실이 모델 입력에서 제거되는지 `backend/tests/integration/test_hybrid_evidence_retrieval.py`에 작성한다.
- [ ] T066 [P] [US3] 대표 정책 최소 20개에서 연장·정정·종료·대체가 버전별로 보이는 이력 테스트를 `backend/tests/golden/test_policy_history.py`에 작성한다.
- [ ] T067 [P] [US3] 과거 문서 현재 오인 방지, 주장별 인용과 근거 부족 UX의 실패 E2E를 `frontend/tests/e2e/history-and-evidence.spec.ts`에 작성한다.

### 구현

- [ ] T068 [P] [US3] 조문·페이지·표·문단 경계를 보존하는 추출·청킹을 `backend/app/domains/rag/chunking.py`에 구현한다.
- [ ] T069 [US3] 기관·역할·기준일 정형 필터 후 전문 검색과 pgvector 점수를 합치는 검색기를 `backend/app/domains/rag/retrieval.py`에 구현한다.
- [ ] T070 [US3] 주장마다 게시 인용을 강제하고 근거 부족·개인 적용·세액 판정 질문을 차단하거나 분석 API로 안내하는 생성 어댑터를 `backend/app/domains/rag/generation.py`에 구현한다.
- [ ] T071 [P] [US3] 정책 사건·버전·변경 차이 조회를 `backend/app/domains/policies/history_service.py`, `backend/app/api/v1/policies.py`에 구현한다.
- [ ] T072 [US3] 근거 상세와 일반 정책 질문 라우터를 `backend/app/api/v1/evidence.py`에 구현해 T064·T065를 통과시킨다.
- [ ] T073 [P] [US3] 기관·지역·세목·상태 필터와 버전 연결 타임라인을 `frontend/src/features/timeline/`에 구현한다.
- [ ] T074 [US3] 주장별 원문 인용과 근거 부족 상태를 `frontend/src/features/evidence/`에 구현해 T067을 통과시킨다.

**체크포인트**: 생성 모델을 끄면 규칙 판정은 그대로 동작하고, 모델을 켜도 게시
근거 없는 주장은 생성되지 않는다.

---

## Phase 7: 사용자 스토리 4 — 원문 수집·검수·게시 (P4)

**목표**: 변경된 정부 원문을 불변 스냅샷으로 수집하고 사람 승인과 골든 테스트를
거친 규칙만 게시한다.

**독립 테스트**: 로컬 HTTP fixture와 관리자 계정으로 수집·변경·검수·게시 상태를 검증한다.

### 실패 테스트 우선

- [ ] T075 [P] [US4] JWT 역할별 401·403, 일반화된 문서·정책·지정·규칙·근거 검수 상세·결정과 낙관적 해시 계약을 `backend/tests/contract/test_admin_api.py`에 작성한다.
- [ ] T076 [P] [US4] 같은 URL의 해시 변경이 기존 스냅샷을 보존하고 검수 대기가 탐지 후 24시간 이내 생성되는지 clock fixture로 `backend/tests/integration/test_immutable_ingestion.py`에 작성한다.
- [ ] T077 [P] [US4] 미검수 근거·규칙 충돌·골든 실패가 게시를 막는지 `backend/tests/integration/test_publication_gates.py`에 작성한다.
- [ ] T078 [P] [US4] robots 차단·403·로그인·CAPTCHA·챌린지를 우회하지 않는지 `backend/tests/security/test_source_policy_boundaries.py`에 작성한다.

### 구현

- [ ] T079 [P] [US4] 국가법령정보센터·전자관보·국토부·국세청용 출처 어댑터 인터페이스와 fixture 구현을 `backend/app/domains/sources/adapters/`에 추가한다.
- [ ] T080 [US4] 조건부 요청·속도 제한·백오프·권리 확인·불변 스냅샷 저장과 24시간 검수 대기 SLA를 `backend/app/domains/sources/ingestion.py`에 구현해 T076·T078을 통과시킨다.
- [ ] T081 [US4] 원문 메타데이터·텍스트·표·경계 추출과 이전 버전 diff를 `backend/app/domains/sources/extraction.py`, `backend/app/domains/sources/diff.py`에 구현한다.
- [ ] T082 [US4] 원문·추출·규칙·근거·골든 결과를 승인·반려하는 서비스를 `backend/app/domains/reviews/service.py`에 구현한다.
- [ ] T083 [US4] 검수 규칙만 정규화·컴파일·게시하고 이전 번들을 대체하는 서비스를 `backend/app/domains/reviews/publication.py`에 구현해 T077을 통과시킨다.
- [ ] T084 [US4] 수집·검수 상세·일반 승인/반려·게시 관리자 API와 JWT role claim 검사를 `backend/app/api/v1/admin.py`, `backend/app/core/auth.py`에 구현해 T075를 통과시킨다.
- [ ] T085 [P] [US4] 수집 대기열·원문 변경·신선도 경고를 `frontend/src/features/admin-review/ReviewQueue.tsx`에 구현한다.
- [ ] T086 [US4] 원문·이전 diff·추출값·규칙·근거·골든 영향을 함께 보는 검수 작업대를 `frontend/src/features/admin-review/ReviewWorkspace.tsx`에 구현한다.
- [ ] T087 [US4] 출처별 예약 수집과 신선도 확인 CLI를 `backend/app/jobs/ingest.py`, `backend/app/jobs/verify_freshness.py`에 구현한다.

**체크포인트**: 미검수 데이터가 공개 경로로 들어갈 수 없고 모든 게시 결정이 재현된다.

---

## Phase 8: 품질·운영 마무리

**목적**: 성능, 접근성, 보안, 복구와 문서 증거를 전체 흐름에서 검증한다.

- [ ] T088 [P] 순수 규칙 p95 300ms, 현재 정책 p95 300ms, 주소 p95 1.5s, 분석 p95 2s, 근거 검색 p95 4s 목표와 초기 동시 사용자 100명 부하를 `backend/tests/performance/test_service_budgets.py`에 측정한다.
- [ ] T089 [P] 출처 신선도·수집 실패·게시 번들·규칙 평가·근거 검색 지연의 메트릭과 알림을 `backend/app/core/metrics.py`, `infra/observability/alerts.yml`에 구현한다.
- [ ] T090 [P] WCAG 핵심 흐름, 모바일 뷰포트와 색상 외 상태 표기를 `frontend/tests/e2e/accessibility.spec.ts`에 검증한다.
- [ ] T091 [P] 종속성·비밀 스캔, 관리자 권한, SSRF·프롬프트 주입·DSL 자원 제한과 개인 시나리오가 생성 모델·오류 수집기로 전송되지 않는 검사를 `backend/tests/security/`, `frontend/tests/security/`에 보강한다.
- [ ] T092 PostgreSQL·원문 객체·규칙 번들의 백업·복구 훈련을 `infra/runbooks/backup-restore.md`에 한국어 우선과 English AI Context로 문서화하고 실제 복구 해시를 검증한다.
- [ ] T093 API·규칙·데이터 모델과 현재 지원·미지원 범위를 `docs/operations.md`, `docs/rule-authoring.md`, `docs/data-curation.md`에 한국어 우선과 English AI Context로 문서화한다.
- [ ] T094 [P] 개인정보·로그 정책의 금지 패턴과 30일 삭제 작업을 `backend/app/jobs/purge_logs.py`, `backend/tests/security/test_retention.py`에 구현한다.
- [ ] T095 [P] 경쟁 사이트 DOM·API·계산 결과가 코드·fixture·문서에 복제되지 않았는지 `scripts/audit/reference-boundaries.ps1`로 검사한다.
- [ ] T096 [P] P1 데이터 컷오프의 원문·공고·경계·규칙·골든 해시를 `scripts/seed/verified-fixtures/manifest.json`에 고정하고 두 명의 검수 승인을 기록한다.
- [ ] T097 [quickstart.md](./quickstart.md)의 설치·마이그레이션·fixture·테스트·P1 인수 시나리오를 깨끗한 환경에서 실행하고 T110의 `specs/001-real-estate-policy-dashboard/checklists/p1-release-scope.md` 각 항목을 검증해 `specs/001-real-estate-policy-dashboard/checklists/release-readiness.md`에 명령·결과·증거 해시를 기록한다.

---

## 실행 시점별 보완 작업

**목적**: 기존 ID를 보존하면서 분석에서 발견한 공백을 닫는다. 다음 작업은 뒤에 실행하는 새 Phase가 아니라 각 제목에 표시한 기존 Phase에 병합한다.

### 프로젝트 설정 보완 — Phase 2

- [x] T098 프로젝트 설정 명령을 실행하기 전에 비밀값·가상환경·캐시·테스트·빌드 산출물을 제외하는 루트 `.gitignore`와 금지 파일 검사를 `scripts/verify/repository-hygiene.ps1`에 추가한다. (plan: repository hygiene, missing)
- [x] T099 T007·T008 이후 Python과 Node 의존성을 `backend/uv.lock`, `frontend/package-lock.json`에 고정하고 잠금 파일만으로 깨끗한 설치를 재현하는 검사를 `scripts/verify/reproducible-install.ps1`에 추가한다. (plan: reproducible setup, missing)

---

### 사용자 스토리 1 보완 — Phase 4 운영 주소와 사용성

**목표**: fixture 전용 주소 판정을 실제 사용자 주소에 안전하게 연결하고 P1 사용성 성공 기준을 측정한다.

- [ ] T100 [US1] 승인된 주소 제공자의 도로명주소→지번·PNU·좌표 정규화, 다중 후보, timeout·장애·약관 차단과 원문 주소 로그 비노출 계약 테스트를 `backend/tests/contract/test_address_provider_contract.py`에 먼저 작성한다. (FR-004~006, partial)
- [ ] T101 [US1] T002·T005의 이용조건 검수와 T100 통과를 전제로 운영용 주소 제공자 어댑터와 fixture 대체 구성을 `backend/app/domains/geography/providers/official.py`, `backend/app/core/config.py`에 구현하고 장애 시 `REQUIRES_OFFICIAL_CHECK`로 종료한다. (FR-004~006, partial)
- [ ] T102 [US1] 제품과 과제를 미리 보지 않은 대상 사용자 최소 30명을 한 번씩 검증하고 시작자 전원과 중도 이탈을 분모에 포함해 도움 없이 180초 안에 유효한 주소 규제 결과를 확인한 비율이 90% 이상인지 측정하며, 참여 조건·실패·재시도 금지와 원자료 비식별 요약을 `specs/001-real-estate-policy-dashboard/checklists/p1-usability-readiness.md`에 한국어 우선, English AI Context 순서로 기록한다. (SC-003, partial)

---

### 사용자 스토리 4 보완 — Phase 7 추가 공식 출처

**목표**: 계획에 포함된 정부·지자체 출처 전체가 동일한 권리·차단·수집 계약을 통과하게 한다.

- [ ] T103 [US4] 기획재정부·행정안전부·지자체 출처의 조건부 요청, 속도 제한, 권리 상태, 첨부·도면과 차단 응답을 공통 인터페이스로 검증하는 fixture 계약 테스트를 `backend/tests/contract/test_additional_source_adapters.py`에 먼저 작성한다. (plan: source adapters, missing)
- [ ] T104 [US4] T079의 공통 인터페이스와 T103을 통과하는 기획재정부·행정안전부·지자체 출처 어댑터를 `backend/app/domains/sources/adapters/moef.py`, `backend/app/domains/sources/adapters/mois.py`, `backend/app/domains/sources/adapters/local_government.py`에 구현한다. (plan: source adapters, missing)

---

### 전달·배포 보완 — Phase 8 및 릴리스

**목적**: 선택한 사용자 스토리를 재현 가능한 이미지로 승격하고 복구할 수 있는 전달 게이트를 만든다.

- [ ] T105 `GET /api/v1/health/live` liveness, `GET /api/v1/health/ready` DB·게시 스냅샷 readiness 계약과 정적 웹 `/healthz` probe를 `specs/001-real-estate-policy-dashboard/contracts/openapi.yaml`, `backend/app/api/v1/health.py`, `backend/tests/contract/test_health_readiness_api.py`, `frontend/nginx.conf`에 구현한다. (plan: health and readiness, missing)
- [ ] T106 백엔드 API와 정적 프런트의 최소 권한·다단계 프로덕션 이미지를 `backend/Dockerfile`, `frontend/Dockerfile`에 정의하고 T105의 health·readiness·비루트 실행 smoke test를 `scripts/release/container-smoke.ps1`에 작성한다. (plan: container delivery, missing)
- [ ] T107 컨테이너 API·정적 웹·PostgreSQL을 지원하는 staging·production 호스팅 대상, 리전·도메인·비밀 주입·객체 저장소·네트워크·비용 한도와 환경별 책임을 제품 책임자·보안·운영 담당자가 승인하고 그 결정과 승인자를 `infra/deployment/target.md`, `infra/deployment/environments.example.yaml`에 한국어 우선, English AI Context 순서로 고정한다. (plan: deployment target, missing)
- [ ] T108 T012·T106·T107 이후 잠금 파일 해시로 이미지를 한 번만 빌드하고 staging에서 검증한 동일 digest를 재빌드 없이 production으로 승격하며, DB migration gate·health 검증·사람 승인과 환경별 digest 동일성 검사를 `.github/workflows/deploy.yml`에 구현하고 비밀값은 저장소 밖에서 주입한다. (plan: deployment pipeline, missing)
- [ ] T109 이미지 버전과 이전 호환 DB migration을 기준으로 애플리케이션·DB 롤백을 훈련하고 `infra/runbooks/deployment-rollback.md`, `scripts/release/rollback-smoke.ps1`에 한국어 우선, English AI Context 순서로 절차와 증거를 기록한다. (plan: rollback, missing)
- [ ] T110 P1 배포에 필요한 T088~T097의 세부 검사와 T098~T102·T105~T109 선행 여부, 실행 명령과 합격 증거를 `specs/001-real-estate-policy-dashboard/checklists/p1-release-scope.md`에 한국어 우선, English AI Context 순서로 고정하고 T097이 모든 항목을 검증하게 한다. (plan: P1 release gate, partial)

## 의존성과 실행 순서

### 단계 의존성

- Phase 1의 T001~T006 완료는 Phase 3 공통 기반 시작과 모든 공개 데이터 작업을 막는 게이트다.
- T111은 Phase 1 HWP 증거 추출을 지원하지만 원문 권리·불변 캡처·T006 사람 승인을 완료 처리하지 않는다.
- Phase 2 설정은 조사와 병렬 가능하지만 검증되지 않은 규칙·경계를 fixture로 만들지 않는다.
- Phase 3 공통 기반은 T001~T006 완료 뒤에만 시작하며 모든 사용자 스토리의 선행 조건이다.
- US1~US4는 공통 기반 후 코드 수준에서 병렬 가능하지만, 공개 전달은 US1 → US2 → US3 → US4 순이다.
- Phase 8은 선택한 사용자 스토리 완료 후 실행한다.
- T098은 다른 프로젝트 설정 명령보다 먼저 시작하고, T099는 T007·T008 뒤이자 T012 전에 완료한다.
- T100은 T030과 병렬 작성할 수 있고, T101은 T002·T005·T036·T100 뒤이자 T037·T040·T043 전에 완료한다.
- T102는 T043·T044·T090 뒤, P1 배포 전에 완료한다.
- T103은 T020 뒤에 작성하고 T104는 T079·T103 뒤이자 T080·T087 전에 완료한다.
- T105는 T027·T041 뒤, T106은 T105 뒤, T107은 CD 구현 전에 완료한다. T108은 T012·T106·T107 뒤, T109는 T108의 staging 배포 뒤에 완료한다.
- T110은 T097 전에 완료한다. P1 배포에는 T110이 정의한 T088~T097의 P1 세부 검사와 T098~T102·T105~T109가 모두 필요하다.

### 사용자 스토리 의존성

- **US1/P1**: 공통 기반만 필요하며 독립 MVP다.
- **US2/P2**: 공통 규칙 엔진과 US1의 주소 지정 서비스를 재사용하지만 독립 fixture로 검증한다.
- **US3/P3**: 출처·근거 모델을 재사용하되 규칙 판정 없이 독립 검색·거부 테스트가 가능하다.
- **US4/P4**: 공통 출처·규칙 모델을 재사용하며 공개 분석과 분리된 관리자 경계로 검증한다.

### 각 스토리 안의 순서

1. 계약·골든·보안·E2E 테스트 작성
2. 테스트가 기대 이유로 실패하는지 확인
3. 모델·서비스·API 구현
4. UI 구현
5. 독립 체크포인트 실행
6. 규칙·근거 변경 시 골든 테스트와 검수 게이트 재실행

## 병렬 실행 예시

US1의 T029~T034와 T100은 서로 다른 계약·골든·E2E 파일이므로 함께 작성할 수 있다.
이후 T035 정책 조회, T036 fixture 주소 어댑터와 T041 공통 UI를 병렬로 진행하고, T100 실패 확인 뒤 T101 운영 주소 어댑터를 연결한다.

US2의 세금팩은 공통 사실 모델 T055 이후 T056~T058을 병렬로 구현할 수 있다.
각 담당자는 다른 규칙 디렉터리와 골든 세트를 사용하며 규칙 번들 테스트에서 합친다.

## 전달 전략

### P1 우선

1. 조사 게이트에서 현행 정책·4종 규제 원문과 경계를 검수한다.
2. 설정과 공통 기반을 완성한다.
3. US1의 실패 테스트와 구현을 끝낸다.
4. T110에서 고정한 T088~T097의 P1 세부 검사와 T098~T102·T105~T109를 실행한다.
5. 현재 정책·주소 규제만 독립 배포하고 데이터 신선도를 관찰한다.

### 점진 확장

- US2는 세목별 지원 카드가 승인될 때마다 규칙팩 단위로 공개한다.
- US3는 근거 권리 검토가 끝난 문서 조각만 색인한다.
- US4는 자동 게시가 아니라 수집·초안·사람 검수·게시 순서를 유지한다.
- 조사 공백이 발견되면 기능을 추정 확장하지 않고 해당 지역·세목을 조건부 또는 미지원으로 표시한다.

---

## AI Context (English)

```yaml
task_count: 111
blocking_order:
  - T098_repository_hygiene
  - T111_rhwp_research_extraction
  - T099_dependency_locks_before_T012_CI
  - phase2_setup_may_run_in_parallel_with_deep_research
  - T001_T006_deep_research_gate
  - shared_foundation_after_T001_T006
  - user_stories
  - quality_and_release
story_tasks:
  US1: [T029-T044, T100-T102]
  US2: [T045-T063]
  US3: [T064-T074]
  US4: [T075-T087, T103-T104]
cross_cutting_supplements: [T098-T099, T105-T110, T111]
supplemental_work_packages:
  setup: T098-T099
  research: T111
  US1: T100-T102
  US4: T103-T104
  delivery: T105-T110
supplemental_execution: merge_into_declared_existing_phase_not_after_phase8
tdd_required: true
publication_rules:
  - no_unverified_source_or_boundary_in_public_fixtures
  - no_rule_without_official_citation_and_golden_cases
  - no_publication_when_conflicts_or_tests_fail
  - no_personal_scenario_persistence
mvp: US1
```
