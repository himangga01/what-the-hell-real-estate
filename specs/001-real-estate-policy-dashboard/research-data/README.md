# 조사 데이터 매니페스트

**기준 컷오프**: 2026-07-10T23:59:59+09:00

**마지막 구조 확인**: 2026-07-17

**현재 구조화 수량**: 정책 사건 68건, 규제 instrument 40건, 출처 권리 행 15건,
세금 규칙 카드 4건

이 폴더는 구현 전에 동결할 정책 사건, 규제 지정, 세금 규칙, 원문 이용권한의 조사
매니페스트다. `VERIFIED`는 공식 페이지에서 해당 핵심 필드를 확인했다는 뜻이며 법률·세무·공간
담당자의 최종 승인이나 원문 캡처 완료를 뜻하지 않는다.

## 파일과 상태

| 파일 | 목적 | 현재 상태 | 완료로 보기 위한 남은 조건 |
|---|---|---|---|
| `policy-events.csv` | 최근 10년 발표·시행·해제 등 정책 사건 | 부분 완료 | 전국 기관 역방향 전수 대조, 원문 캡처·해시 |
| `designations.csv` | 4종 규제 지정·해제·경계 조건 | 부분 완료 | 투기지역 이력, 전국 필지·도면, 누락 공고번호·연장 공고 |
| `source-rights.csv` | 전문 보존·공개·RAG·링크 정책 | 구조 완료·사람 검수 대기 | 문서별 권리 승인과 원문 캡처 |
| `tax-rule-cards/` | 4대 주택 세목의 구현 전 규칙 카드 | 조사본 완료·세무 검수 대기 | 조문·부칙·경계 골든 승인 |

## 공통 상태

- `VERIFIED`: 공식 출처에서 기록한 사실을 확인했으나 원문 해시·사람 승인은 별도다.
- `PARTIAL`: 공고번호, scope, selector, 조건 또는 권리 검토가 남았다.
- `PENDING_REVIEW`: 담당자 승인 전 수집·게시·계산·RAG를 활성화하지 않는다.
- `PENDING_CAPTURE`: 원문 바이트를 보존하지 않아 SHA-256이 없다.
- `NOT_CAPTURED_ROBOTS_RESTRICTED`: 자동 수집이 허용되지 않은 경로를 우회하지 않았다.

## fail-closed 원칙

알려진 공백이 있는 행을 현재 정책·공간·세금 확정 판정에 사용하지 않는다. 날짜별 유효 구간,
원문 selector, 권리 상태와 해시 중 하나라도 없으면 `REQUIRES_OFFICIAL_CHECK` 또는
`REQUIRES_TAX_REVIEW`를 반환한다.

## HWP 임시 추출

HWP 첨부는 공식 [`edwardkim/rhwp`](https://github.com/edwardkim/rhwp) `v0.7.18` CLI로
추출한다. 출력 경로는 존재하지 않는 새 임시 디렉터리여야 한다.

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File scripts/research/extract-hwp.ps1 `
  -InputPath <공식-원문.hwp> `
  -OutputDirectory <새-임시-출력-경로> `
  -Format both
```

- 공식 archive는 `SHA256SUMS.txt`와 일치해야 실행된다.
- `rhwp-extraction-manifest.json`에 입력·실행 파일·archive·페이지별 출력 SHA-256을 기록한다.
- 기본 보존 상태 `TEMPORARY_NOT_RETAINED`는 해시만 조사 응답을 식별하고 원문·추출물은
  불변 보존하지 않았다는 뜻이다.
- HWPX 텍스트 추출은 고정 버전 호환성 테스트 전까지 fail-closed로 비활성이다.
- 추출 성공만으로 정책·세금·공간·권리 상태를 `VERIFIED` 또는 승인 상태로 바꾸지 않는다.
- 정부기관 원문과 추출 전문은 권리 승인 전 저장소 fixture나 RAG에 넣지 않는다.

---

## English AI Context

```yaml
manifest_cutoff: 2026-07-10T23:59:59+09:00
checked_on: 2026-07-17
row_counts:
  policy_events: 68
  designation_instruments: 40
  source_rights: 15
  tax_rule_cards: 4
files:
  policy-events.csv: PARTIAL
  designations.csv: PARTIAL
  source-rights.csv: STRUCTURE_COMPLETE_REVIEW_PENDING
  tax-rule-cards: DRAFT_COMPLETE_TAX_REVIEW_PENDING
fail_closed: true
pending_human_gate: T006
rhwp:
  version: v0.7.18
  archive_sha256_windows_x86_64: BD0B3280C0B87580BFC8C86AF337609ACF939C5F8F1DA6AB3EE73955064420FD
  executable_sha256_windows_x86_64: C92492674CD9B2BDEF7B550FD24591554F75FE391F6299F943B01B7AEEF4F859
  extraction_retention: TEMPORARY_NOT_RETAINED
  hwpx_extraction_enabled: false
  government_fixture_commit_allowed: false
```
