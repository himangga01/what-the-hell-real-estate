# rhwp 기반 HWP 조사 파이프라인 설계

**설계 승인일**: 2026-07-17

**승인 상태**: 승인됨

**적용 범위**: 조사 단계의 HWP 원문 구조·텍스트 추출 및 HWPX 호환성 검증
**선택 도구**: [`edwardkim/rhwp`](https://github.com/edwardkim/rhwp) `v0.7.18`

## 1. 목적

정부기관이 게시한 HWP/HWPX 첨부를 조사할 때 파서와 실행 버전이 달라져 결과가 흔들리지
않도록 공식 `rhwp` 릴리스 CLI를 고정해 사용한다. 원문 해시, 도구 해시, 추출 결과와 실행
시각을 함께 기록하여 같은 입력을 같은 도구로 다시 검증할 수 있게 한다.

이 도구는 정책·세금·공간 판정을 승인하지 않는다. 추출 성공은 문서 내용을 읽었다는 뜻일
뿐이며, 법적 효력·권리·공간 경계·세무 규칙의 사람 검수를 대체하지 않는다.

## 2. 범위와 제외 범위

### 포함

- HWP 5.0 입력과 `v0.7.18` CLI의 HWPX 실제 호환성 확인
- `rhwp export-text`를 이용한 페이지별 일반 텍스트 추출
- `rhwp export-markdown`을 이용한 표·문단 구조 보존용 Markdown 추출
- 입력 원문, 릴리스 압축파일, 실행 파일과 출력물의 SHA-256 기록
- 고정 버전 설치·검증·실행을 담당하는 PowerShell 래퍼
- 손상·빈 출력·체크섬 불일치 시 fail-closed 처리

### 제외

- 공개 서비스에서 HWP 뷰어 또는 편집기 제공
- HWP 원문이나 추출 전문의 자동 게시·RAG 색인
- 권리 검토 전 원문을 저장소 fixture로 영구 보존
- `rhwp` 소스 포크 또는 자체 파서 개발
- 추출 결과만으로 정책·세금·공간 상태를 `VERIFIED`로 승격

## 3. 선택 근거와 대안

### 채택: 공식 릴리스 CLI 고정

`v0.7.18`의 운영체제별 공식 릴리스 자산과 `SHA256SUMS.txt`를 사용한다. 소스 빌드가
필요하지 않아 조사 환경을 단순하게 유지하면서도 배포물 무결성을 확인할 수 있다.

### 미채택: 소스 직접 빌드

커밋 단위 감사에는 유리하지만 Rust 도구 체인과 빌드 시간이 추가된다. 파서를 수정하지 않는
현재 범위에는 비용이 크므로 비상 대체 경로로만 둔다.

### 미채택: `@rhwp/core` WASM 직접 연동

브라우저·Node 애플리케이션에 적합하지만 조사 CLI보다 의존성과 실행 표면이 넓다. 제품에서
HWP 렌더링이 필요해질 때 별도 설계로 검토한다.

## 4. 구성 요소

### 4.1 도구 부트스트랩

`scripts/research/rhwp-tool.ps1`이 다음 책임만 가진다.

1. 기본 버전 `v0.7.18`과 현재 운영체제의 릴리스 자산명을 결정한다.
2. `github.com/edwardkim/rhwp/releases/download/v0.7.18/`에서 압축파일과
   `SHA256SUMS.txt`를 HTTPS로 받는다.
3. 압축파일 SHA-256이 공식 목록과 일치하지 않으면 압축 해제나 실행을 하지 않는다.
4. 임시 도구 디렉터리에만 압축을 풀고 `rhwp` 실행 파일 SHA-256을 별도로 계산한다.
5. 호출이 끝나면 다운로드 압축파일과 임시 도구 디렉터리를 삭제한다.

네트워크가 없거나 공식 체크섬을 확인할 수 없으면 자동으로 다른 버전이나 비공식 미러를
사용하지 않는다. 검증된 로컬 실행 파일을 쓰는 경우에도 버전 출력과 실행 파일 SHA-256을
실행 매니페스트에 기록해야 한다.

### 4.2 HWP 추출 래퍼

`scripts/research/extract-hwp.ps1`은 다음 입력을 받는다.

- `InputPath`: 읽을 `.hwp` 파일. `.hwpx`는 고정 버전 호환성 테스트가 통과한 뒤에만 허용
- `OutputDirectory`: 추출물을 둘 명시적 임시 디렉터리
- `Format`: `text`, `markdown`, `both` 중 하나. 기본값은 `both`
- `RhwpPath`: 선택적 로컬 `rhwp` 실행 파일 경로

실행 흐름은 다음과 같다.

1. 입력 확장자·파일 존재·크기와 SHA-256을 확인한다. 검증 전 `.hwpx` 입력은 네트워크
   접근 전에 fail-closed로 거부한다.
2. 도구 부트스트랩 또는 검증된 `RhwpPath`에서 실행 파일을 얻는다.
3. 텍스트는 `rhwp export-text`, 구조 보존본은 `rhwp export-markdown`으로 추출한다.
4. 명령 종료 코드뿐 아니라 예상 출력 파일 존재, 비어 있지 않은 출력과 오류 메시지를 검사한다.
5. 성공한 경우에만 `rhwp-extraction-manifest.json`을 원자적으로 생성한다.
6. 호출자가 후속 검증을 마치면 출력 디렉터리를 삭제한다. 래퍼는 사용자 입력 원문을 삭제하지 않는다.

### 4.3 실행 매니페스트

매니페스트에는 다음 필드를 기록한다.

- 스키마 버전과 실행 시각
- `rhwp` 태그·실행 파일 SHA-256·공식 릴리스 URL
- 입력 파일명·바이트 수·SHA-256
- 실행한 하위 명령과 출력 형식
- 생성된 파일별 바이트 수·SHA-256
- `TEMPORARY_NOT_RETAINED`, `RETAINED_APPROVED` 중 보존 상태
- 경고, 파싱 오류와 수동 검수 필요 여부

원문 권리 승인이 없으면 기본 보존 상태는 `TEMPORARY_NOT_RETAINED`다. 이 상태의 해시는
조사 당시 응답을 식별하지만 불변 원문 보존 게이트를 충족하지 않는다.

## 5. 오류 처리와 안전 경계

- 릴리스 체크섬 불일치: 즉시 실패하고 실행 금지
- 지원하지 않는 확장자: 네트워크 접근 전에 실패
- 손상된 HWP 및 호환성이 확인되지 않은 HWPX: `PENDING_REVIEW`로 종료하고 부분 출력을
  근거로 사용하지 않음
- 출력 0바이트 또는 예상 페이지 누락: 성공 매니페스트 생성 금지
- 표·도형 내용 누락 의심: Markdown과 일반 텍스트를 비교하고 공식 게시 페이지를 병행 확인
- 원문 권리 미승인: 전문 공개·RAG·저장소 커밋 금지
- 임시 삭제 실패: 경로를 출력하고 성공으로 보고하지 않음

최초 다운로드 URL은 고정된 GitHub 저장소와 태그만 허용한다. 리디렉션은 GitHub 릴리스가
사용하는 `github.com`, `objects.githubusercontent.com`, `release-assets.githubusercontent.com`
호스트만 허용하며, 그 밖의 최종 호스트로 이동하면 중단한다.

## 6. 테스트 전략

구현은 테스트 우선으로 진행한다.

1. 지원하지 않는 확장자가 네트워크 접근 전에 거부되는 테스트
2. 변조된 릴리스 압축파일이 체크섬 검사에서 거부되는 테스트
3. 고정된 테스트 HWP에서 알려진 문구를 `export-text`로 추출하는 통합 테스트
4. 표가 있는 테스트 HWP에서 `export-markdown` 결과가 비어 있지 않은지 확인하는 테스트
5. 출력 일부가 누락되면 성공 매니페스트가 생성되지 않는 테스트
6. 성공 매니페스트의 입력·도구·출력 SHA-256을 재계산해 일치시키는 테스트
7. 작업 종료 후 입력 원문은 유지되고 래퍼가 만든 임시 도구 파일만 삭제되는 테스트
8. HWPX 샘플의 고정 버전 통합 테스트가 통과하기 전에는 `.hwpx` 입력을 거부하는 테스트

권리 검토 전 정부 원문은 테스트 fixture로 커밋하지 않는다. 통합 테스트는 MIT 라이선스가
확인된 `rhwp` 테스트 샘플을 고정 커밋과 해시로 사용하거나, 권리가 승인된 내부 fixture를
사용한다.

## 7. 문서와 운영 반영

구현 시 다음 문서를 함께 갱신한다.

- `specs/001-real-estate-policy-dashboard/source-register.md`
- `specs/001-real-estate-policy-dashboard/research-data/README.md`
- `specs/001-real-estate-policy-dashboard/checklists/research-readiness.md`
- 프로젝트의 제3자 라이선스 고지 파일

기존 조사에서 다른 추출기를 사용해 얻은 사실은 원문 URL·원문 해시가 같더라도 `rhwp`로
재추출해 번호·본문·표 결과를 다시 대조한다. 대조 전까지 기존 사실 상태는 승격하지 않는다.

## 8. 완료 기준

- 고정 버전과 공식 체크섬 검증이 자동화됐다.
- 텍스트·Markdown 추출과 매니페스트 생성 테스트가 통과한다.
- 체크섬 불일치·손상·빈 출력이 모두 fail-closed로 끝난다.
- 공식 HWP 샘플 한 건 이상을 `rhwp`로 재추출해 기존 조사 결과와 대조했다.
- 임시 원문·도구·출력의 삭제 여부가 검증됐다.
- 출처 레지스트리와 연구 게이트에 `rhwp` 도구·버전·해시가 기록됐다.

---

## English AI Context

```yaml
design_id: RHWP_RESEARCH_PIPELINE
approved_on: 2026-07-17
status: APPROVED_FOR_PLANNING
scope: research_only_hwp_extraction_with_hwpx_capability_gate
tool:
  repository: https://github.com/edwardkim/rhwp
  version: v0.7.18
  license: MIT
  acquisition: official_github_release
  checksum_source: SHA256SUMS.txt
commands:
  text: rhwp export-text
  markdown: rhwp export-markdown
components:
  - scripts/research/rhwp-tool.ps1
  - scripts/research/extract-hwp.ps1
  - extraction_manifest
security:
  fixed_release_only: true
  checksum_required: true
  unofficial_mirror_allowed: false
  delete_user_input: false
  default_retention: TEMPORARY_NOT_RETAINED
compatibility_gates:
  hwpx:
    default_enabled: false
    enable_after: pinned_version_integration_test_passes
fail_closed_on:
  - checksum_mismatch
  - unsupported_extension
  - parser_error
  - empty_output
  - incomplete_page_output
human_review_required:
  - legal_effect
  - tax_rule
  - spatial_boundary
  - source_rights
out_of_scope:
  - public_hwp_viewer
  - application_editor
  - automatic_rag_publication
  - parser_fork
```
