# 대한민국 부동산 정책·세금 분석 대시보드

대한민국의 부동산 정책, 주소별 규제, 취득·보유·양도 시나리오와 그 근거를
기준일에 맞춰 설명하는 대시보드 프로젝트다. 정책·공간 경계·세금 규칙은
검수된 출처와 버전으로 관리하고, 결과가 불확실하거나 지원 범위 밖이면 추정하지
않고 공식 확인이 필요하다고 알리는 것을 목표로 한다.

## 현재 상태

현재 저장소는 **Phase 2 설정 완료·Phase 1 조사 진행 단계**다. 다음 항목은 구현되어 있다.

- Python·Node 의존성 정의와 잠금 파일
- Ruff·Pyright·ESLint·TypeScript·Prettier 설정
- PostgreSQL 18.x, PostGIS 3.6.x, pgvector 0.8.2용 Compose 정의
- 비밀값이 없는 백엔드·프런트 환경 변수 예시
- OpenAPI·규칙 JSON Schema 설계 계약과 Spec Kit 구현 문서
- 저장소 위생·재현 설치 검증 스크립트와 GitHub Actions CI
- 조사 데이터 구조와 일부 정책·세금·권리 조사 기록
- `rhwp v0.7.18` 기반 HWP 추출 도구
- RapidOCR·ONNX Runtime·Docling TableFormer 기반 PDF·표 추출 도구

아직 애플리케이션 소스, Alembic 설정·마이그레이션, API 엔트리 포인트,
프런트 `index.html`·`src`, 검수 fixture와 seed 모듈, 테스트 모음은 구현되지
않았다. 따라서 현재는 대시보드나 API를 실행할 수 없고, 아래의 "구현 후 목표
명령"도 아직 실행하면 안 된다. Spec Kit CLI는 앱 실행 필수 도구가 아니라
명세·계획·작업 문서를 선택적으로 관리하는 개발 workflow 도구다.

다른 PC에서 이어서 작업할 때는 원격 기본 브랜치가 아니라 `main`을 명시해서
복제해야 한다. 필요한 로컬 자산과 정확한 재개 절차는 [`HANDOFF.md`](HANDOFF.md)를
먼저 따른다.

## 지원 범위와 안전 경계

계획된 사용자 스토리는 다음과 같다.

| 우선순위 | 구현 목표 |
| --- | --- |
| P1 | 현재 정책 대시보드와 운영 주소 정규화, 주소별 4종 규제 판정 |
| P2 | 결정론적인 취득·보유·양도 시나리오 분석과 참고용 세금 범위 |
| P3 | 최근 10년 정책 이력과 검수된 근거만 인용하는 설명 |
| P4 | 원문 수집, 사람 검수, 게시와 대체 이력을 관리하는 관리자 흐름 |

이 기능들은 현재 목표이며 아직 사용자에게 제공되지 않는다. v1의 세금 결과는
일반적인 정보와 개략 추정일 뿐 확정 신고액, 세금 신고서, 법률 또는 세무 자문이
아니다. 공동명의·신탁·입주권·비거주자 등 지원 행렬 밖의 사례나 공식 근거가
부족한 사례는 임의로 계산하지 않고 `UNSUPPORTED` 또는
`REQUIRES_OFFICIAL_CHECK`로 종료하는 것이 제품 경계다. 실제 계약·신고·의사결정
전에는 관계 기관 또는 자격 있는 전문가에게 확인해야 한다.

## 사전 요구사항

저장소 루트에서 명령을 실행한다.

| 도구·자원 | 요구사항 |
| --- | --- |
| Git | 저장소 가져오기와 변경 추적 |
| PowerShell | 검증 스크립트 실행. Windows PowerShell 5.1 또는 호환 PowerShell |
| 제품 백엔드 Python | 3.14.x (`>=3.14,<3.15`) |
| PDF 조사 도구 Python | 3.12.x (`>=3.12,<3.13`), 백엔드와 별도 uv 환경 |
| uv | Python 잠금 설치와 명령 실행 |
| Node.js | 24.x (`>=24,<25`) |
| npm | 11 이상 |
| 컨테이너 런타임 | Docker Compose v2 또는 프로젝트가 별도로 승인한 Compose 호환 런타임 |
| 네트워크 | 최초 의존성 설치, DB 이미지 빌드, 원격 공식 스키마 검증에 필요 |
| 로컬 포트 | DB `5432`, 향후 API `8000`, 향후 프런트 개발 서버 `5173` |

포트가 사용 중이면 실행 전에 충돌을 해결해야 한다. DB 바인드 주소와 포트는
`POSTGRES_BIND_ADDRESS`, `POSTGRES_PORT`로 재정의할 수 있다.

> **현재 컨테이너 검증 공백:** 이 README를 작성한 Windows 호스트에는
> Docker, Podman, nerdctl이 설치되어 있지 않다. 따라서 Compose 파일의 정적
> 정의는 검토했지만 DB 이미지 빌드, 컨테이너 기동, healthcheck와 확장 버전
> 조회는 이 호스트에서 실제 실행 검증되지 않았다. 컨테이너 런타임이 있는
> 환경과 CI에서 반드시 확인해야 한다.

## 잠금 기반 설치

의존성 버전을 임의로 다시 해석하지 않는다. 백엔드는 `uv sync --locked`,
프런트는 `npm ci`만 사용한다. 일반 `uv sync`, `npm install`, 잠금 파일 재생성은
의존성 갱신 작업이 명시적으로 승인된 경우에만 수행한다.

```powershell
uv sync --project backend --locked --all-groups --python 3.14 --no-python-downloads
npm --prefix frontend ci --ignore-scripts --no-audit --no-fund
```

`--no-python-downloads`를 사용하므로 Python 3.14.x가 먼저 설치되어 있어야 한다.
프런트 설치는 lifecycle script를 실행하지 않는 CI와 동일한 정책이다.

## 로컬 환경 설정

예시 파일을 복사한다. 생성되는 `.env` 파일은 커밋하지 않는다.

```powershell
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env
```

백엔드의 현재 개발 기본값은 다음과 같다.

- `DATABASE_URL=postgresql+psycopg://app:app@localhost:5432/real_estate`
- `ADDRESS_PROVIDER=fixture`
- `EMBEDDING_PROVIDER=disabled`
- `GENERATION_PROVIDER=disabled`

`app/app`은 로컬 fixture 개발 전용 DB 자격증명이다. 공유·staging·production
환경에서 사용하거나 저장소에 실제 비밀값을 넣으면 안 된다. 운영 환경은 비밀
저장소로 모든 자격증명을 주입해야 한다. `SOURCE_USER_AGENT`의
`contact@example.invalid`도 실제 운영 연락처로 교체해야 한다.

프런트의 `VITE_API_BASE_URL=http://localhost:8000`은 브라우저 번들에 포함된다.
이름이 `VITE_`로 시작하는 모든 값은 공개 정보로 취급하고 토큰, 암호, 개인 정보,
내부 전용 주소를 넣지 않는다. fixture/disabled 공급자 기본값은 외부 서비스를
호출하지 않는 개발 안전값이며 운영 준비 완료를 뜻하지 않는다.

## 로컬 DB 명령

다음 명령은 Docker Compose v2와 기본 DB 값
`app/app@localhost:5432/real_estate`를 가정한다. 이 저장소에는 명령에 필요한
정의가 있지만, 위에 적은 컨테이너 검증 공백 때문에 현재 작성 호스트에서는
실행하지 못했다.

구성을 정적으로 확인하고 DB를 빌드·기동한다.

```powershell
docker compose --file infra/docker-compose.yml config --quiet
docker compose --file infra/docker-compose.yml up --detach --build --wait db
```

상태와 로그를 확인한다.

```powershell
docker compose --file infra/docker-compose.yml ps db
docker compose --file infra/docker-compose.yml logs db
```

PostgreSQL, PostGIS, pgvector 버전을 조회한다. 예상 결과는 각각 18.x, 3.6.x,
0.8.2다.

```powershell
docker compose --file infra/docker-compose.yml exec --no-TTY db psql --username app --dbname real_estate --command "SELECT current_setting('server_version') AS postgresql, postgis_lib_version() AS postgis, (SELECT extversion FROM pg_catalog.pg_extension WHERE extname = 'vector') AS pgvector;"
```

컨테이너를 종료한다. 이 명령은 이름 있는 DB 볼륨을 삭제하지 않는다.

```powershell
docker compose --file infra/docker-compose.yml down
```

## 현재 실행 가능한 검증

먼저 잠금 파일이 의존성 정의와 일치하는지 확인한다.

```powershell
uv lock --project backend --check --python 3.14 --no-python-downloads
npm --prefix frontend ls --depth=0
```

백엔드 린트, 형식, 타입 검사를 실행한다. 아직 앱 디렉터리가 없으므로 현재는
설정과 존재하는 Python 범위만 검사한다.

```powershell
Push-Location backend
uv run --locked --no-sync ruff check .
uv run --locked --no-sync ruff format --check .
uv run --locked --no-sync pyright
Pop-Location
```

프런트 린트, 형식, 타입 검사를 실행한다. 아직 `index.html`과 `src`가 없어 빌드는
현재 검증에 포함하지 않는다.

```powershell
npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend run typecheck
```

저장소 위생과 깨끗한 임시 디렉터리에서의 잠금 설치 재현성을 검증한다. 재현 설치는
네트워크와 시간이 필요하며 원본 잠금 파일의 해시가 바뀌지 않았는지도 확인한다.

```powershell
& ./scripts/verify/repository-hygiene.ps1
& ./scripts/verify/reproducible-install.ps1
```

설계 계약과 CI workflow 스키마를 검사한다. OpenAPI 공식 스키마 검증은 네트워크가
필요하다.

```powershell
uv run --project backend --locked --no-sync check-jsonschema --no-cache --schemafile https://spec.openapis.org/oas/3.1/schema-base/2025-11-23 specs/001-real-estate-policy-dashboard/contracts/openapi.yaml
uv run --project backend --locked --no-sync check-jsonschema --check-metaschema specs/001-real-estate-policy-dashboard/contracts/rule-definition.schema.json
uv run --project backend --locked --no-sync check-jsonschema --builtin-schema vendor.github-workflows .github/workflows/ci.yml
uv run --project backend --locked --no-sync check-jsonschema --builtin-schema custom.github-workflows-require-timeout .github/workflows/ci.yml
```

GitHub Actions의 `.github/workflows/ci.yml`은 push, pull request,
수동 `workflow_dispatch`에서 실행된다. 현재 없는 앱·테스트 파일은 CI가 명시적으로
탐지해 보류하고, 해당 디렉터리나 엔트리 포인트가 추가된 뒤에는 빌드와 테스트를
필수로 실행한다.

## 구현 후 목표 명령 — 현재 실행 금지

아래는 담당 작업이 완료된 뒤 활성화할 목표 명령이다. 현재 저장소에는 필요한
파일이 없으므로 성공을 보장하지 않는다.

| 구현 후 목표 | 활성화 담당 작업 | 목표 명령 |
| --- | --- | --- |
| DB 마이그레이션 | T018~T022 | `uv run --locked --no-sync alembic upgrade head` (`backend`에서 실행) |
| API 개발 서버 | T027 및 필요한 API 라우터 | `uv run --locked --no-sync uvicorn app.main:app --reload --port 8000` (`backend`에서 실행) |
| 검수 fixture 적재 | T028, T096 | `uv run --locked --no-sync python -m app.jobs.seed` (`backend`에서 실행) |
| 백엔드 테스트 | T014~T017 및 사용자 스토리별 테스트 | `uv run --locked --no-sync pytest tests` (`backend`에서 실행) |
| 프런트 개발 서버 | T041~T043 | `npm --prefix frontend run dev` |
| 프런트 단위 테스트 | 프런트 단위 테스트 파일 구현 후 | `npm --prefix frontend run test:unit` |
| 프런트 E2E 테스트 | T034, T044, T053, T067, T090 | `npm --prefix frontend run test:e2e` |
| 프런트 production 빌드 | T041 이후 `index.html`·`src` 구현 후 | `npm --prefix frontend run build` |

fixture seed의 최종 CLI 계약은 T028에서 확정된다. 위 명령은 계획된 모듈 경로를
보여 주는 목표이며 구현 결과에 따라 README와 함께 갱신해야 한다. 프런트 테스트는
정의된 `test:unit`, `test:e2e` 스크립트만 사용한다.

## 관련 문서

- 다른 PC 인수인계: [`HANDOFF.md`](HANDOFF.md)
- 현재 진행률·남은 작업: [`specs/001-real-estate-policy-dashboard/progress.md`](specs/001-real-estate-policy-dashboard/progress.md)
- 기능 범위: `specs/001-real-estate-policy-dashboard/spec.md`
- 구현 설계: `specs/001-real-estate-policy-dashboard/plan.md`
- 실행 작업: `specs/001-real-estate-policy-dashboard/tasks.md`
- 세금 지원 행렬: `specs/001-real-estate-policy-dashboard/tax-support-matrix.md`
- 단계별 상세 안내: `specs/001-real-estate-policy-dashboard/quickstart.md`

## English AI Context

### Purpose and current state

This repository targets a versioned, evidence-backed Korean real-estate policy and
tax-analysis dashboard. **Phase 2 setup is complete and Phase 1 research is in progress**;
it is not a runnable application. Dependency manifests and locks, quality configuration,
environment examples, a PostgreSQL/PostGIS/pgvector Compose definition, design contracts,
repository verification scripts, CI, partial research records, a pinned rhwp HWP pipeline,
and a RapidOCR/ONNX Runtime/Docling TableFormer PDF and table pipeline exist. Application
source, Alembic configuration and migrations, the API entry point, frontend entry files,
verified fixtures, seed code, and product test suites do not exist yet.

Cross-PC continuation must explicitly use `main` because the remote default branch pointer
still targets an older branch. Follow `HANDOFF.md` for clone commands and local-only assets.

Spec Kit is an optional documentation workflow tool. It is not an application runtime
dependency.

### Support boundary

The planned stories are P1 current-policy and address designation resolution, P2
deterministic acquisition/holding/disposal analysis, P3 ten-year history and citation-only
explanations, and P4 curator ingestion/review/publication. None is currently available to
end users. v1 output is informational and approximate; it is neither a filed tax amount
nor legal/tax advice and does not submit returns. Unsupported or insufficiently verified
cases must terminate as `UNSUPPORTED` or `REQUIRES_OFFICIAL_CHECK`.

### Prerequisites and locked installation

- Git and Windows PowerShell 5.1 or compatible PowerShell
- Python `>=3.14,<3.15` for the backend and a separate Python `>=3.12,<3.13`
  environment for the PDF research tool, plus uv
- Node.js `>=24,<25` and npm `>=11`
- Docker Compose v2 or a separately approved Compose-compatible runtime
- Network access for dependency installation, image builds, and remote schema validation
- Free local ports: database `5432`, future API `8000`, future frontend `5173`

Only locked installation is allowed:

```powershell
uv sync --project backend --locked --all-groups --python 3.14 --no-python-downloads
npm --prefix frontend ci --ignore-scripts --no-audit --no-fund
```

Copy `backend/.env.example` to `backend/.env` and `frontend/.env.example` to
`frontend/.env`. `VITE_*` values are public browser-bundle data and must never contain
secrets or personal information. `ADDRESS_PROVIDER=fixture`,
`EMBEDDING_PROVIDER=disabled`, and `GENERATION_PROVIDER=disabled` are safe development
defaults. `app/app@localhost:5432/real_estate` is a local-only credential and must be
replaced outside local fixture development.

### Container verification gap

Docker, Podman, and nerdctl are absent from the authoring host. The database image build,
startup, healthcheck, and extension-version queries have therefore **not been locally
executed**. A container-enabled environment and CI must verify them. The expected versions
are PostgreSQL 18.x, PostGIS 3.6.x, and pgvector 0.8.2.

```powershell
docker compose --file infra/docker-compose.yml config --quiet
docker compose --file infra/docker-compose.yml up --detach --build --wait db
docker compose --file infra/docker-compose.yml ps db
docker compose --file infra/docker-compose.yml logs db
docker compose --file infra/docker-compose.yml exec --no-TTY db psql --username app --dbname real_estate --command "SELECT current_setting('server_version') AS postgresql, postgis_lib_version() AS postgis, (SELECT extversion FROM pg_catalog.pg_extension WHERE extname = 'vector') AS pgvector;"
docker compose --file infra/docker-compose.yml down
```

### Currently executable verification

```powershell
uv lock --project backend --check --python 3.14 --no-python-downloads
npm --prefix frontend ls --depth=0

Push-Location backend
uv run --locked --no-sync ruff check .
uv run --locked --no-sync ruff format --check .
uv run --locked --no-sync pyright
Pop-Location

npm --prefix frontend run lint
npm --prefix frontend run format:check
npm --prefix frontend run typecheck

& ./scripts/verify/repository-hygiene.ps1
& ./scripts/verify/reproducible-install.ps1

uv run --project backend --locked --no-sync check-jsonschema --no-cache --schemafile https://spec.openapis.org/oas/3.1/schema-base/2025-11-23 specs/001-real-estate-policy-dashboard/contracts/openapi.yaml
uv run --project backend --locked --no-sync check-jsonschema --check-metaschema specs/001-real-estate-policy-dashboard/contracts/rule-definition.schema.json
uv run --project backend --locked --no-sync check-jsonschema --builtin-schema vendor.github-workflows .github/workflows/ci.yml
uv run --project backend --locked --no-sync check-jsonschema --builtin-schema custom.github-workflows-require-timeout .github/workflows/ci.yml
```

### Future commands after implementation

These are targets and must not be treated as currently runnable:

- T018~T022: run `uv run --locked --no-sync alembic upgrade head` from `backend`.
- T027 plus API routers: run `uv run --locked --no-sync uvicorn app.main:app --reload --port 8000` from `backend`.
- T028 and T096: target `uv run --locked --no-sync python -m app.jobs.seed` from `backend`; T028 must finalize the CLI contract.
- T014~T017 and story tests: run `uv run --locked --no-sync pytest tests` from `backend`.
- T041~T043: run `npm --prefix frontend run dev`.
- After unit tests exist: run `npm --prefix frontend run test:unit`.
- T034/T044/T053/T067/T090: run `npm --prefix frontend run test:e2e`.
- After T041 provides `index.html` and `src`: run `npm --prefix frontend run build`.

Use only the defined `test:unit` and `test:e2e` frontend test scripts. Keep this README
synchronized whenever those target files or CLI contracts are implemented.
