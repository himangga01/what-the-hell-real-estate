# 조사 데이터 매니페스트

**기준 컷오프**: 2026-07-10T23:59:59+09:00

**마지막 구조 확인**: 2026-07-17

**현재 구조화 수량**: 정책 사건 105건, 정책 사건 관계 42건, 규제 지정 수단(공고) 45건,
지정-원문 증거 연결 7건, 출처 권리 행 21건, 세금 규칙 카드 4건,
불변 보존 전자관보 PDF 4건

이 폴더는 구현 전에 동결할 정책 사건, 규제 지정, 세금 규칙, 원문 이용권한의 조사
매니페스트다. `VERIFIED`는 공식 페이지에서 해당 핵심 필드를 확인했다는 뜻이며 법률·세무·공간
담당자의 최종 승인이나 원문 캡처 완료를 뜻하지 않는다.

## 파일과 상태

| 파일 | 목적 | 현재 상태 | 완료로 보기 위한 남은 조건 |
|---|---|---|---|
| `policy-events.csv` | 최근 10년 발표·시행·해제 등 정책 사건 | 부분 완료 | 전국 기관 역방향 전수 대조, 남은 원문 캡처·해시 |
| `policy-event-relations.csv` | 발표→효력·정정·연장·해제 등 사건 간 관계 | 부분 완료 | 전국 사건 관계와 scope 전수 대조 |
| `designations.csv` | 4종 규제 지정·해제·경계 조건 | 부분 완료 | 전국 투기지역 완전성 확인, 전국 필지·도면, 누락 공고번호·연장 공고 |
| `designation-evidence.csv` | 지정 scope와 불변 원문 캡처의 기계 판독 조인 | 투기지역 7행 완료 | 나머지 지정 수단의 원문 캡처·연결 |
| `source-rights.csv` | 전문 보존·공개·RAG·링크 정책 | 구조 완료·사람 검수 대기 | robots·약관 증거 해시, 하위 지자체 등록, 문서별 권리 승인과 남은 원문 캡처 |
| `tax-rule-cards/` | 4대 주택 세목의 구현 전 규칙 카드 | 조사본 완료·세무 검수 대기 | 조문·부칙·경계 골든 승인 |
| `captures/` | 불변 보존한 공식 원문과 SHA-256 매니페스트 | 부분 완료 | 나머지 정책·지정·권리 근거 원문 캡처 |
| `cutoff-manifest.csv` | 조사 산출물별 컷오프·해시·승인 상태 | 12개 항목 해시 고정·승인 대기 | 네 담당자 승인과 승인 커밋 기록 |

컷오프 매니페스트의 텍스트 SHA-256은 UTF-8·LF 바이트를 기준으로 한다. 루트
`.gitattributes`가 매니페스트 대상 CSV·세금 카드·출처 레지스트리를 `eol=lf`로 고정하고,
전자관보 PDF는 바이너리로 취급해 운영체제별 체크아웃에서 해시가 바뀌지 않게 한다.

## 공통 상태

- `VERIFIED`: 공식 출처에서 기록한 사실을 확인했으나 원문 해시·사람 승인은 별도다.
- `PARTIAL`: 공고번호, scope, selector, 조건 또는 권리 검토가 남았다.
- `PENDING_REVIEW`: 담당자 승인 전 수집·게시·계산·RAG를 활성화하지 않는다.
- `NOT_CAPTURED`: 원문 바이트를 보존하지 않았고 SHA-256 필드는 비어 있다.
- `TEMPORARY_NOT_RETAINED`: 조사 중 응답을 확인했지만 불변 원문은 보존하지 않았다.
- `IMMUTABLE_CAPTURED`: 원문 바이트와 `sha256:{64 hex}`를 저장하고 매니페스트로 검증한다.

## 이번 감사에서 확인한 범위와 남은 공백

- 기획재정부공고 제2017-114호·제2018-151호·제2022-189호·제2023-1호 전자관보 PDF를
  불변 보존하고 모든 페이지를 렌더링해 육안 확인했다. 파일·크기·해시는
  [`captures/manifest.csv`](./captures/manifest.csv)에 기록했다.
- 투기지역은 서울 범위와 세종 범위를 효력 구간별로 분리했다. 다만 전자관보 키워드 검색은
  전국 이력 전수 열거기가 아니므로 2016-07-10~2026-07-10 전국 완전성을 주장하지 않는다.
- 정책 사건은 발표·공포·시행·유예·연장·정정·해제·종료를 분리해 105건으로 정규화했다.
  2016-11-03과 2017-06-19를 일반 시행일로 보던 행을 실제 부령 공포·시행일인
  2016-11-15와 2017-07-03으로 교정하고, 공포 사건과 효력 사건을 분리했다.
- 국토교통부의 `조정대상지역` 제목 공식 색인 23건을 역대조해 기존에 없던 전매행위
  제한기간 지정 공고 7건을 추가했다. 제2018-1090호는 공식 HWP를 `rhwp v0.7.18`로
  2쪽 추출해 문서번호·구리시·안양시 동안구·광교 범위·공고일부터 효력을 확인했다.
  이 색인 하나에서 기존 누락이 7/23이었으므로 전국 전수성을 계속 주장하지 않는다.
- 정책 사건 105건 중 불변 원문 캡처는 4건뿐이다. `NOT_CAPTURED` 97건과
  `TEMPORARY_NOT_RETAINED` 4건을 합친 101/105(96.2%)는 불변 원문이 없으며 기관별
  역방향 전수 대조도 끝나지 않았다.
- `policy-events.csv.event_at`은 조사 staging의 한국 표준시 민사 날짜(`YYYY-MM-DD`)다.
  구현 적재 시 `T00:00:00+09:00`으로 정규화하고 날짜 정밀도가 낮다는 메타데이터를 보존한다.
- 사건의 인과·추가·정정·연장·해제 관계는 `supersedes_event_id`에 섞지 않고
  `policy-event-relations.csv`의 관계 유형으로 분리했다.
- 2020년 제1650호의 지정과 해제는 별도 행으로 분리했다. 다만 최근 10년 지정 연장 공고의
  전국 전수 목록은 아직 없어 T003은 미완료다.
- 서울특별시 공고 제2025-2774호는 아파트 부지 142.22㎢ 재지정과 정비사업 후보지 8곳
  446,779.3㎡ 신규 지정을 별도 효력 구간으로 분리했다. 공식 PDF 15쪽 전부를 렌더링해
  확인했지만 권리 승인 전 원문은 보존하지 않았다.
- 경기도보 제8034호의 경기도 공고 제2026-1792호 40~42쪽에서 용인 기흥구·화성 동탄구·
  구리시 170.50㎢의 공고번호·기간·아파트 한정·전체 면적 기준·지정도를 확인했다. 역시
  권리 승인 전 원문은 보존하지 않았다.
- 전수성 하한 감사에서 서울 공식 현황표 묶음행 31개 중 3개만 대응해 최소 28개가 남았고,
  경기도 2026-04-02 공식 현황표 지정 수단 25개 중 1개만 대응해 최소 24개가 남았다.
  현황표는 누락 탐지용 색인이므로 이 수치를 최근 10년 전국 전수 수량으로 보지 않는다.
- 출처 권리는 역할이 섞인 기관·본문·첨부를 분리했다. 2026-07-17에 12개 공식 호스트의
  robots와 주요 권리 페이지를 임시 관찰하고 API 신청 조건과 robots 상태를 구분했다.
  응답 바이트를 보존하지 않아 정책·약관 해시 열은 비워 두었으며, 서울 25개 자치구·경기
  31개 시군의 개별 등록도 남았다.

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
- GitHub 리디렉션은 자동 추종하지 않고 허용 호스트를 각 요청 전에 검사한다.
- 입력 크기·SHA-256은 추출 전후가 같아야 하며, 예상 밖 출력은 게시하지 않는다.
- 내부 임시 소유권 표식은 최종 출력에 포함하지 않고 출력 디렉터리를 원자적으로 게시한다.
- `rhwp-extraction-manifest.json`에 입력·실행 파일·archive·페이지별 출력 SHA-256을 기록한다.
- 매니페스트의 명령 레코드에는 `rhwp` 진단 메시지를 함께 기록한다.
- 기본 보존 상태 `TEMPORARY_NOT_RETAINED`는 해시만 조사 응답을 식별하고 원문·추출물은
  불변 보존하지 않았다는 뜻이다.
- HWPX 텍스트 추출은 고정 버전 호환성 테스트 전까지 fail-closed로 비활성이다.
- 추출 성공만으로 정책·세금·공간·권리 상태를 `VERIFIED` 또는 승인 상태로 바꾸지 않는다.
- 정부기관 원문과 추출 전문은 권리 승인 전 저장소 fixture나 RAG에 넣지 않는다.
- Windows PowerShell 5.1의 단위 테스트와 로컬 리디렉션 스모크 테스트는 필수 CI에서
  실행하며, 공식 릴리스 다운로드 통합 테스트는 수동 CI로 다시 실행할 수 있다.

---

## English AI Context

```yaml
manifest_cutoff: 2026-07-10T23:59:59+09:00
checked_on: 2026-07-17
row_counts:
  policy_events: 105
  policy_event_relations: 42
  designation_instruments: 45
  designation_evidence_links: 7
  source_rights: 21
  tax_rule_cards: 4
  immutable_gazette_captures: 4
  immutable_gazette_manifest_sha256: 15ba1f67db608c318c8311de655d1986298bfd3720d6a4a8dee516858a649c95
  cutoff_manifest_artifacts: 12
  cutoff_manifest_sha256: 6ae43212e983072dd98587699a2aee6d680b83e3fd903cde400b84d5a16821ef
  cutoff_hash_byte_policy: UTF8_LF_TEXT_AND_RAW_PDF_BYTES
files:
  policy-events.csv: PARTIAL
  policy-event-relations.csv: PARTIAL
  designations.csv: PARTIAL
  designation-evidence.csv: VERIFIED_FOR_7_SPECULATION_AREA_SCOPE_ROWS
  source-rights.csv: STRUCTURE_COMPLETE_REVIEW_PENDING
  tax-rule-cards: DRAFT_COMPLETE_TAX_REVIEW_PENDING
  captures/manifest.csv: PARTIAL_4_IMMUTABLE_GAZETTE_PDFS
  cutoff-manifest.csv: HASHED_12_ARTIFACTS_APPROVAL_PENDING
known_gaps:
  - id: GAP-SPECULATION-AREA-NATIONAL-COMPLETENESS
    status: PARTIAL
    period: 2016-07-10/2026-07-10
    statement: gazette_keyword_search_is_verification_not_exhaustive_enumerator
  - id: GAP-NATIONWIDE-POLICY-REVERSE-ENUMERATION
    status: PARTIAL
    statement: official_agency_reverse_enumeration_not_complete_molit_title_index_had_7_of_23_missing_before_this_audit
  - id: GAP-REMAINING-IMMUTABLE-SOURCE-CAPTURE
    status: PARTIAL
    statement: 101_of_105_policy_events_not_immutably_captured
  - id: GAP-NATIONWIDE-PARCEL-BOUNDARY-NORMALIZATION
    status: PARTIAL
    statement: parcel_drawing_and_admin_code_normalization_not_complete
  - id: GAP-DESIGNATION-EXTENSION-ENUMERATION
    status: PARTIAL
    statement: seoul_status_missing_grouped_rows_at_least_28_and_gyeonggi_2026_04_02_status_missing_instruments_at_least_24_nationwide_history_not_enumerated
  - id: GAP-ROBOTS-TERMS-EVIDENCE
    status: PARTIAL
    statement: robots_and_terms_body_hashes_not_captured
  - id: GAP-CAPTURE-TIMESTAMP-HEADERS
    status: PARTIAL
    statement: gazette_capture_time_is_date_only_and_response_headers_not_retained
event_at_staging_semantics:
  type: KST_CIVIL_DATE
  format: YYYY-MM-DD
  load_normalization: append_T00_00_00_plus_09_00
  precision_metadata_required: true
fail_closed: true
pending_human_gate: T006
rhwp:
  version: v0.7.18
  archive_sha256_windows_x86_64: BD0B3280C0B87580BFC8C86AF337609ACF939C5F8F1DA6AB3EE73955064420FD
  executable_sha256_windows_x86_64: C92492674CD9B2BDEF7B550FD24591554F75FE391F6299F943B01B7AEEF4F859
  extraction_retention: TEMPORARY_NOT_RETAINED
  hwpx_extraction_enabled: false
  government_fixture_commit_allowed: false
  redirect_validation: BEFORE_EACH_REQUEST
  input_integrity_check: PRE_AND_POST_SHA256
  output_tree_policy: EXPECTED_PAGES_ONLY
  unit_tests_passed: 25
  integration_pages: {text: 18, markdown: 18}
  government_hwp_temporary_reextractions:
    - {document: molit_notice_2018_1086, bytes: 12288, text_pages: 2, markdown_pages: 2}
    - {document: molit_notice_2018_1090, bytes: 18944, text_pages: 2, markdown_pages: 2}
  corrupt_hwp_failed_closed: true
  required_ci: WINDOWS_POWERSHELL_5_1_UNIT_AND_LOCAL_REDIRECT
  official_integration_ci: MANUAL_NON_BLOCKING
```
