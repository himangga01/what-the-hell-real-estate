# 로컬 개발·검증 빠른 시작

**현재 상태**: 의존성 잠금·품질 설정·로컬 DB 정의·CI까지의 설정 골격은 구현됐다.
아래 서버·마이그레이션·fixture·테스트 명령은 해당 구현 작업이 완료된 뒤의 목표
실행 절차이며, 지금 저장소에 애플리케이션 코드가 이미 있다는 뜻이 아니다.

## 1. 도구 준비

권장 도구:

- Git
- Python 3.14
- uv
- Node.js 24 LTS와 npm
- Docker Desktop 또는 PostgreSQL 18 + PostGIS + pgvector
- Spec Kit CLI 0.12.9(문서 workflow를 실행할 때만 선택적으로 필요)

버전 확인:

```powershell
python --version
uv --version
node --version
npm --version
docker --version
specify --version
```

## 2. 환경 변수

현재 제공되는 `.env.example`을 `.env`로 복사하고 로컬 값만 채운다.

```powershell
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env
```

백엔드 기본값:

```dotenv
APP_ENV=development
DATABASE_URL=postgresql+psycopg://app:app@localhost:5432/real_estate
PUBLIC_WEB_ORIGIN=http://localhost:5173
SOURCE_USER_AGENT=what-the-hell-real-estate/0.1 contact@example.invalid
ADDRESS_PROVIDER=fixture
EMBEDDING_PROVIDER=disabled
GENERATION_PROVIDER=disabled
```

프런트엔드 공개 설정:

```dotenv
VITE_API_BASE_URL=http://localhost:8000
```

API 키·토큰은 저장소에 커밋하지 않는다. fixture 모드에서는 외부 주소·생성 모델
호출 없이 검증할 수 있어야 한다. `VITE_*` 값은 브라우저에 공개되므로 비밀값을
넣지 않는다.

## 3. 의존성과 DB

현재 실행 가능한 잠금 설치와 DB 기동 명령:

```powershell
uv sync --project backend --locked --all-groups --python 3.14 --no-python-downloads
npm --prefix frontend ci --ignore-scripts --no-audit --no-fund
docker compose --file infra/docker-compose.yml up --detach --build --wait db
```

T019 이후 마이그레이션 목표 명령:

```powershell
uv run --project backend --locked --no-sync alembic upgrade head
```

DB에는 `postgis`, `vector` 확장이 필요하다. 마이그레이션이 확장을 만들 수 없는
운영 환경에서는 DBA가 먼저 활성화하고 애플리케이션은 시작 시 버전을 확인한다.

## 4. 검수 fixture 적재

운영 데이터를 인터넷에서 즉시 가져와 공개하지 않는다. 로컬에서는 해시와 기대값이
고정된 fixture를 적재한다.

```powershell
uv run --project backend --locked --no-sync python -m app.jobs.seed `
  --manifest scripts/seed/verified-fixtures/manifest.json
```

매니페스트는 다음을 포함해야 한다.

- 데이터 기준일과 컷오프 시각
- 원문·경계 fixture 해시
- 규칙 번들 해시
- 검수자와 골든 테스트 결과
- 알려진 데이터 공백

## 5. 개발 서버

각 터미널에서 실행한다.

```powershell
uv run --project backend --locked --no-sync uvicorn app.main:app --reload --port 8000
```

```powershell
npm run dev --prefix frontend
```

예상 주소:

- 웹: `http://localhost:5173`
- API: `http://localhost:8000`
- OpenAPI: `http://localhost:8000/docs`

## 6. 자동 검증

```powershell
uv run --project backend --locked --no-sync pytest
uv run --project backend --locked --no-sync ruff check .
uv run --project backend --locked --no-sync pyright
npm --prefix frontend run test:unit
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend run typecheck
npm --prefix frontend run test:e2e
```

규칙 검증:

```powershell
uv run --project backend --locked --no-sync python -m app.domains.rules.cli validate backend/rulesets
uv run --project backend --locked --no-sync python -m app.domains.rules.cli golden backend/rulesets
uv run --project backend --locked --no-sync python -m app.domains.rules.cli compile `
  backend/rulesets --dry-run
```

## 7. 독립 인수 시나리오

### 현재 정책

1. 기준일이 2026-07-10인 fixture에서 게시·시행 중 정책만 표시한다.
2. 발표됐지만 미시행인 항목과 종료 항목이 현재 카드에 없는지 확인한다.
3. 신선도 SLA를 넘긴 출처는 정책을 숨기지 않고 마지막 확인 시각과 경고를 표시한다.

### 주소 규제

1. 서울 검증 주소에서 조정대상지역·투기과열지구·투기지역·토허제를 각각 반환한다.
2. 구리·용인 기흥·화성 동탄의 2026-06-30, 07-01, 07-04, 07-05 결과를 비교한다.
3. 필지·공식 도면이 없는 토허제 주소는 `REQUIRES_OFFICIAL_CHECK`를 반환한다.
4. 거래주체·유형·면적이 부족한 토허제는 `CONDITIONAL` 또는 `NEEDS_INPUT`이다.

### 개인 세금 시나리오

1. 검수된 1세대 1주택 fixture에서 비과세 후보, 12억원 경계, 보유·거주 요건을 분리한다.
2. 다주택 중과 경계는 2026-05-09 전후와 계약금 증빙·경과기한을 각각 검사한다.
3. 취득세·양도세·종부세의 주택 수가 별도 파생 사실인지 확인한다.
4. 세대원별 소유지분·소유기간·과거 처분 이력을 바꾸면 관련 세목의 주택 수만 근거와 함께 달라지는지 확인한다.
5. 금액 결과가 본세·부가세목·공제·반올림·미포함 항목으로 분리되는지 확인한다.
6. 공동명의·신탁·입주권 등 미지원 fixture가 임의 계산되지 않고 `UNSUPPORTED`인지 확인한다.

### 근거와 RAG

1. 모든 핵심 주장에 게시된 문서의 조문·페이지·문단 인용이 있는지 확인한다.
2. 과거 문서는 종료 상태를 표시하고 현재 정책으로 답하지 않는지 확인한다.
3. 인용 가능한 근거가 없으면 `INSUFFICIENT_EVIDENCE`인지 확인한다.
4. 개인 적용 여부나 세액 질문은 답을 생성하지 않고 `ANALYSIS_REQUIRED`를 반환하는지 확인한다.
5. 생성 모델을 끈 상태에서도 규칙 판정 API가 같은 결과를 반환하는지 확인한다.

### 관리자 검수

1. 같은 URL의 원문 해시 변경이 기존 스냅샷을 덮지 않는지 확인한다.
2. 미검수 규칙과 근거가 공개 분석·RAG에 포함되지 않는지 확인한다.
3. 규칙 충돌, 근거 누락 또는 골든 실패 시 게시가 409로 거부되는지 확인한다.
4. 승인자·시각·이유·이전 번들 해시가 감사 기록에 남는지 확인한다.

### 개인정보

1. 주민등록번호·세대원 이름 같은 미정의 필드를 API가 거부하는지 확인한다.
2. 주소·금액 fixture가 애플리케이션·오류·브라우저 저장소에 남지 않는지 검사한다.
3. 생성 모델 요청에 개인 시나리오가 포함되지 않는지 검사한다.

## 8. P1 MVP 완료 조건

- `/api/v1/policies/current`와 `/api/v1/areas/resolve` 계약 테스트 통과
- 현재·예정·종료 필터와 4종 규제의 날짜·공간 골든 테스트 통과
- 공개 정책 카드 100%에 기관·원문·시행일·확인일 표시
- 불완전한 경계가 확정값으로 노출되지 않음
- 모바일·키보드·스크린리더 핵심 흐름 검사 통과
- 원시 주소와 시나리오가 서버 영구 저장·로그에 남지 않음

---

## AI Context (English)

```yaml
document_state: setup_scaffold_implemented_application_commands_are_future_targets
install_policy: lockfiles_only
local_ports:
  frontend: 5173
  backend: 8000
default_external_services: disabled
seed_mode: verified_hash_pinned_fixtures
validation_order:
  - unit_and_property_tests
  - contract_tests
  - golden_tests
  - integration_tests
  - e2e_and_accessibility
p1_gate:
  endpoints: [GET_/api/v1/policies/current, POST_/api/v1/areas/resolve]
  no_unverified_boolean_geo_decisions: true
  no_raw_scenario_persistence: true
```
