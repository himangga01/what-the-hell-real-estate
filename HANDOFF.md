# 다른 PC 작업 인수인계

- **재검토일**: 2026-08-21
- **작업 브랜치·푸시 대상**: `main` / `origin/main`
- **인수인계 문서 작성 전 기준 커밋**: `78db17269261c347d4440699736c4eccfbaf8be6`
- **최신 작업 기준**: 이 파일이 포함된 `origin/main`의 최신 커밋

이 문서는 다른 Windows PC에서 현재 작업을 그대로 이어가기 위한 기준이다. 현재 원격의
기본 브랜치 포인터는 오래된 `origin/codex/real-estate-dashboard`를 가리키므로, 복제할 때
반드시 `main`을 명시해야 한다. 기본 브랜치 설정 자체는 이번 작업에서 변경하지 않았다.

## 1. 저장소 가져오기

```powershell
git clone --branch main https://github.com/himangga01/what-the-hell-real-estate.git
Set-Location .\what-the-hell-real-estate
git pull --ff-only origin main
git branch --show-current
git rev-parse HEAD
```

`git branch --show-current` 결과는 `main`이어야 한다. 위에 적은 `78db172...`는 이 문서를
작성하기 직전의 상태 기준이며, 실제 재개 지점은 인수인계 문서가 포함된
`origin/main`의 최신 커밋이다.

## 2. 현재 프로젝트 상태

- 전체 작업 112개 중 12개 완료, 100개 미완료다.
- Phase 2 프로젝트 설정은 완료됐다.
- Phase 1 조사는 일부 완료됐고 HWP 및 PDF 조사 추출 도구가 구현됐다.
- PDF 도구는 RapidOCR·ONNX Runtime·Docling TableFormer 기반이며, 표 구조 보존을
  포함한 사람 검수 게이트가 남아 있다.
- 애플리케이션 본체, Alembic 마이그레이션, API 엔트리 포인트, 프런트
  `index.html`·`src`, 검수 fixture·seed, 제품 테스트는 아직 없다.
- 따라서 대시보드·API·프런트 개발 서버를 지금 실행할 수 있는 상태가 아니다.

상세 진행률과 근거는
[`progress.md`](specs/001-real-estate-policy-dashboard/progress.md), 실제 작업 체크박스는
[`tasks.md`](specs/001-real-estate-policy-dashboard/tasks.md)를 기준으로 한다.

## 3. 새 PC 필수 도구

| 용도 | 요구사항 |
| --- | --- |
| 공통 | Git, Windows PowerShell 5.1 이상 또는 호환 PowerShell, uv |
| 제품 백엔드 | Python `>=3.14,<3.15` |
| PDF 조사 도구 | 별도 Python `>=3.12,<3.13` |
| 프런트엔드 | Node.js `>=24,<25`, npm `>=11` |
| 로컬 DB | Docker Compose v2 또는 별도로 승인된 Compose 호환 런타임 |
| HWP 조사 | `rhwp v0.7.18`; 미지정 시 공식 릴리스를 검증 후 임시 사용 |
| 네트워크 | 최초 의존성 설치, 컨테이너 이미지, `rhwp` 임시 다운로드에 필요 |

제품 백엔드와 PDF 조사 도구는 Python 버전이 다르다. 한 가상환경을 공유하지 말고
각 프로젝트의 uv 환경을 사용한다.

## 4. 잠금 기반 의존성 준비

저장소 루트에서 다음 명령만 사용한다. 일반 `uv sync`나 `npm install`로 잠금 파일을
임의 갱신하지 않는다.

```powershell
uv sync --project backend --locked --all-groups --python 3.14 --no-python-downloads
npm --prefix frontend ci --ignore-scripts --no-audit --no-fund
uv sync --project tools/pdf-ocr --frozen --group dev --python 3.12 --no-python-downloads
```

로컬 환경 파일은 예시를 복사해 만든다. 생성된 `.env`는 Git에 커밋하지 않는다.

```powershell
Copy-Item backend/.env.example backend/.env
Copy-Item frontend/.env.example frontend/.env
```

## 5. Git에 포함되지 않는 로컬 자산

| 항목 | Git 상태 | 새 PC에서 할 일 |
| --- | --- | --- |
| 코드·문서·의존성 잠금 파일 | 추적됨 | `origin/main`에서 받는다. |
| `tools/pdf-ocr/models.lock.json` | 추적됨 | 모델 파일 검증 계약으로 사용한다. |
| PDF OCR 실제 모델 파일 | 추적 안 됨 | 기존 PC에서 모델 홈을 복사하거나 승인된 방식으로 별도 준비한다. |
| `.env`, `.venv`, `node_modules`, 각종 캐시 | 추적 안 됨 | 새 PC에서 다시 생성한다. |
| `temp/` OCR 출력 | 현재 미추적 임시·미승인 산출물 | 이어받을 근거로 사용하지 말고 필요 시 다시 생성한다. |
| `rhwp` 실행 파일 | 저장소에 포함되지 않음 | 스크립트의 검증된 임시 다운로드 또는 `-RhwpPath`를 사용한다. |
| Docker·WSL·컨테이너 런타임 | 저장소 밖 | 새 PC 환경에 맞게 별도 설치한다. WSL 자체는 저장소 필수 조건이 아니다. |

현재 PDF 모델 잠금은 7개 artifact, 11개 파일, 총 413,788,439바이트를 요구한다.
저장소에는 모델 자동 프로비저닝 스크립트가 없으며 모델 바이너리를 재배포하지 않는다.

## 6. PDF 모델 홈 이전과 확인

기존 PC의 `PDF_OCR_MODEL_HOME` 디렉터리 전체를 새 PC의 접근 가능한 경로로 복사한다.
그 후 새 경로를 절대 경로로 지정한다. 모델 잠금 파일은 이미 Git에 있으므로 새 PC에서
`models.lock.json`을 다시 생성하지 않는다.

2026-08-21에 현재 PC에서 존재를 확인한 복사 원본 경로는 다음과 같다.

```text
C:\Users\HOONJAE\AppData\Local\what-the-hell-real-estate\pdf-ocr-models
```

```powershell
$env:PDF_OCR_MODEL_HOME = (Resolve-Path 'D:\path\to\pdf-ocr-models').Path
$env:HF_HUB_OFFLINE = '1'
$env:TRANSFORMERS_OFFLINE = '1'
$env:UV_OFFLINE = '1'
$env:DOCLING_ARTIFACTS_PATH = $env:PDF_OCR_MODEL_HOME
uv run --project tools/pdf-ocr --frozen python -c "import os; from pathlib import Path; from pdf_ocr.runtime import collect_runtime_info; from pdf_ocr.model_lock import load_model_lock; info=collect_runtime_info(Path('tools/pdf-ocr/uv.lock')); artifacts=load_model_lock(Path('tools/pdf-ocr/models.lock.json'), Path(os.environ['PDF_OCR_MODEL_HOME']), info.package_versions); print(info); print(f'verified_artifacts={len(artifacts)}')"
```

마지막 출력의 `verified_artifacts`는 `7`이어야 한다. 실제 PDF 추출은 입력 파일,
기존 모델 홈, 아직 존재하지 않는 새 출력 디렉터리를 지정한다. 래퍼가 네트워크 기반
모델 다운로드를 차단하고 잠금·해시 불일치 시 실패하도록 되어 있다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/research/extract-pdf.ps1 `
  -InputPath <공식-PDF-파일경로> `
  -OutputDirectory <아직-존재하지-않는-출력-경로> `
  -ModelLockPath .\tools\pdf-ocr\models.lock.json `
  -ModelHome $env:PDF_OCR_MODEL_HOME
```

## 7. HWP 조사 추출

입력은 `.hwp`만 지원하며 `.hwpx`는 현재 지원하지 않는다. 출력 디렉터리는 실행 전에
존재하면 안 된다. `-RhwpPath`를 생략하면 스크립트가 `rhwp v0.7.18` 공식 릴리스와
체크섬을 확인한 뒤 임시로 사용하고 삭제한다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/research/extract-hwp.ps1 `
  -InputPath <공식-HWP-파일경로> `
  -OutputDirectory <아직-존재하지-않는-출력-경로> `
  -Format both
```

## 8. 이어서 할 작업

1. T001 최근 10년 정책 전수 목록을 마무리한다.
2. T002 공식 정부 출처·원문 해시를 마무리한다.
3. T003 규제지역·토지거래허가구역 지정 이력을 마무리한다.
4. T112 관보 4건 사람 검수, 원문 권리 확인, 실제 표가 있는 PDF 표 구조 인수를
   완료한다.
5. 정책·세금·공간·권리 담당자의 T006 최종 승인을 받는다.
6. 위 Phase 1 게이트가 모두 닫힌 뒤 Phase 3 T014~T028 구현을 시작한다.

현재 조사 승인 상태는 `PENDING_HUMAN_APPROVAL`이다. 정책·세금·공간·권리 검수가
모두 대기 중이며, 미승인·부분 수집·임시 출력은 공개 fixture, 규칙 판정 또는 RAG
근거로 승격하면 안 된다. 조사 게이트 기록은 2026-07-17 감사 기준이므로 최신 Git
상태와 혼동하지 않는다.

## 9. 현재 실행 대상으로 보면 안 되는 명령

다음 항목은 구현 후 목표일 뿐 현재 성공이 보장되지 않는다.

- Alembic 마이그레이션과 API 서버 실행
- fixture·seed 적재와 제품 백엔드 테스트
- 프런트 개발 서버, 단위·E2E 테스트, production 빌드
- 규칙 DSL 검증·골든·컴파일 CLI

구체적인 미래 명령은 [`README.md`](README.md)의 "구현 후 목표 명령"과
[`quickstart.md`](specs/001-real-estate-policy-dashboard/quickstart.md)를 참고한다.

## 10. 기준 문서

- 프로젝트 입구와 현재 실행 경계: [`README.md`](README.md)
- 작업 현황과 우선순위: [`progress.md`](specs/001-real-estate-policy-dashboard/progress.md)
- 실제 작업 체크박스: [`tasks.md`](specs/001-real-estate-policy-dashboard/tasks.md)
- 조사 승인 게이트: [`research-readiness.md`](specs/001-real-estate-policy-dashboard/checklists/research-readiness.md)
- 조사 데이터 범위: [`research-data/README.md`](specs/001-real-estate-policy-dashboard/research-data/README.md)
- 로컬 개발 목표 절차: [`quickstart.md`](specs/001-real-estate-policy-dashboard/quickstart.md)
- PDF 모델·라이선스 고지: [`THIRD_PARTY_NOTICES.md`](THIRD_PARTY_NOTICES.md)

---

## English AI Context

```yaml
document: cross_pc_handoff
reviewed_on: 2026-08-21
repository: https://github.com/himangga01/what-the-hell-real-estate.git
continuation_ref: origin/main
pre_handoff_parent_commit: 78db17269261c347d4440699736c4eccfbaf8be6
clone_requirement:
  command: git clone --branch main https://github.com/himangga01/what-the-hell-real-estate.git
  reason: origin/HEAD still points to origin/codex/real-estate-dashboard

project_state:
  application_runnable: false
  tasks: {total: 112, completed: 12, pending: 100}
  completed: [phase_2_setup, rhwp_research_pipeline, pdf_ocr_research_pipeline]
  blocking_tasks: [T001, T002, T003, T112, T006]
  human_gate: PENDING_HUMAN_APPROVAL
  phase_3_allowed_before_gate: false

runtimes:
  backend_python: ">=3.14,<3.15"
  pdf_ocr_python: ">=3.12,<3.13"
  node: ">=24,<25"
  npm: ">=11"
  rhwp: v0.7.18

local_only_assets:
  - environment_files
  - virtual_environments_and_dependency_caches
  - pdf_ocr_model_home
  - temp_ocr_outputs
  - rhwp_runtime_binary
  - container_runtime

pdf_model_contract:
  lock: tools/pdf-ocr/models.lock.json
  source_pc_model_home: 'C:\Users\HOONJAE\AppData\Local\what-the-hell-real-estate\pdf-ocr-models'
  artifacts: 7
  files: 11
  bytes: 413788439
  runtime_downloads: forbidden
  regenerate_lock_on_new_pc: false

next_order:
  - complete_T001_T002_T003
  - complete_T112_human_rights_and_real_table_acceptance
  - obtain_T006_policy_tax_spatial_rights_approvals
  - implement_phase_3_T014_T028

documentation_review:
  tests_rerun: false
  reason: user_instruction_requires_separate_approval
  excluded_from_commit: temp/
```
