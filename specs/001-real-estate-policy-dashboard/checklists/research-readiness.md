# 조사 완료 검수 게이트

**데이터 컷오프**: 2026-07-10T23:59:59+09:00

**체크리스트 작성일**: 2026-07-17

**게이트 상태**: `PENDING_HUMAN_APPROVAL`

**구현·게시 승인**: 보류

이 문서는 T006의 사람 검수 기록이다. 자동 검증 통과는 자료 구조가 읽을 수 있다는 뜻일 뿐,
정책·세금·공간 판정의 정확성이나 게시 승인을 뜻하지 않는다. 아래 세 담당자의 이름·날짜·서명
또는 승인 커밋이 모두 기록되기 전에는 T006을 완료 처리하지 않는다.

## 1. 산출물 존재·구조 확인

- [x] `policy-events.csv`에 조사 기간, 공식 URL, 검증 상태, 캡처 상태와 알려진 공백 열이 있다.
- [x] `source-register.md`에 출처 역할, 재확인 목표, 장애 시 경로, robots·권리 경계가 있다.
- [x] `designations.csv`에 4종 규제의 구분 열과 경계·조건·공백 열이 있다.
- [x] 취득세·재산세·종부세·양도소득세 카드와 색인 문서가 있다.
- [x] `source-rights.csv`에 내부 전문·공개·RAG·링크 전용·권리 상태가 분리돼 있다.
- [ ] 원문 바이트 캡처와 SHA-256이 완료됐다.
- [ ] 전국 지자체 필지·도면 자료가 전수 정규화됐다.

## 2. 정책 이력 담당 검수

자동 조사·대조 기록:

- [x] 국토교통부 2024 주택업무편람의 투기과열지구·조정대상지역 연혁표를 현재 매니페스트와 대조했다.
- [x] 2016·2017·2018·2019·2021 누락 규제 instrument를 `PARTIAL` 또는 `VERIFIED` 상태로 추가했다.
- [x] 2016-11-03·2017-06-19 청약 조정대상지역 선행 상태와 2017-11-10 법정 조정대상지역 전환을 분리했다.
- [x] 2018-08-28 공식 HWP에서 제2018-1086호·제2018-1088호·제2018-1089호와 적용 범위를 교차검증했다.
- [x] 2019-11-08 제2019-1540호의 고양·남양주 유지 범위와 부산 3개 구 해제를 교차검증했다.
- [x] 2020-06-19 제827호·제828호를 분리하고 2020-06-29 제877호 정정 사건을 추가했다.
- [x] 2020-12-18 창원 의창구/성산구 규제 수단 혼합 오류를 제2020-1649호·제2020-1650호로 분리 정정했다.
- [x] 2018-08-28과 2021-08-30의 서로 다른 규제 수단을 별도 정책 사건으로 분리했다.

- [ ] 2016-07-10~2026-07-10의 전국 정책 목록을 기관별로 역방향 대조했다.
- [ ] 발표·공포·시행·유예·연장·정정·해제·종료 사건을 중복 없이 분리했다.
- [ ] `VERIFIED` 사건의 공고번호·시행일·공식 URL·selector를 원문과 대조했다.
- [ ] 투기지역의 지정·해제 공고 공백을 해소했다.
- [ ] `PARTIAL`과 `PENDING_CAPTURE` 행을 승인 대상에서 제외했다.
- [ ] 2026-07-10 컷오프 이후 변경을 초기 스냅샷에서 제외했다.

**검수자 이름/역할**: 미지정

**검수일**: 미지정

**승인 서명 또는 커밋**: 미지정

**결정**: `PENDING_POLICY_REVIEW`

## 3. 세금 담당 검수

- [ ] 네 세금 카드의 기준일 시행 법률·시행령·부칙 selector를 확인했다.
- [ ] 세율·공제·비과세·중과·감면·추징과 주택 수 예외를 전수 대조했다.
- [ ] 취득세 계약금 경과와 양도세 2026년 4개월·6개월·허가구역 경과를 확인했다.
- [ ] 재산세 과세표준상한과 종전 주택 세부담상한 미적용을 확인했다.
- [ ] 지방교육세·지방소득세·농어촌특별세·절사 순서를 확인했다.
- [ ] 골든 사례와 수기 계산의 경계값이 일치한다.

**검수자 이름/역할**: 미지정

**검수일**: 미지정

**승인 서명 또는 커밋**: 미지정

**결정**: `PENDING_TAX_REVIEW`

## 4. 공간·규제 담당 검수

- [ ] 조정대상지역·투기과열지구·투기지역·토지거래허가구역을 서로 다른 수단으로 검수했다.
- [ ] 각 지정·해제·연장 instrument의 `[valid_from, valid_to)` 구간을 확인했다.
- [ ] 행정구역 코드, 읍면동 제외, 필지·아파트 조서와 동일 단지 조건을 확인했다.
- [ ] 경기도 2026-07-05 토지거래허가구역의 공고번호·도면·조건을 확보했다.
- [ ] 경계 충돌·도면 누락 시 `REQUIRES_OFFICIAL_CHECK`로 종료하는 것을 승인했다.
- [ ] 주소 제공자 저장·권리 조건을 검토하고 운영 제공자를 승인했다.

**검수자 이름/역할**: 미지정

**검수일**: 미지정

**승인 서명 또는 커밋**: 미지정

**결정**: `PENDING_SPATIAL_REVIEW`

## 5. 원문 권리·무결성 확인

- [x] `rhwp v0.7.18` 공식 archive를 `SHA256SUMS.txt`로 검증하고 실행 파일 SHA-256을 기록했다.
- [x] 공식 CLI 생성 임시 HWP 18페이지를 text·Markdown으로 추출하고 입력·출력 해시를 재계산했다.
- [x] 제2018-1086호 HWP의 기존 SHA-256을 재확인하고 공고번호·광명시·하남시를 `rhwp`로 대조했다.
- [x] 통합검증 후 도구·생성 HWP·추출물이 임시 디렉터리에서 삭제되고 입력 보존 동작을 확인했다.
- [ ] 법령 본문과 판례·첨부를 별도 권리 행으로 검수했다.
- [ ] 공공누리 표시는 문서·첨부별로 확인했다.
- [ ] `REVIEW_REQUIRED`, `LINK_ONLY`, `BLOCKED` 자료의 전문 공개·RAG가 비활성이다.
- [ ] robots 상태와 저작권·약관 허용을 독립적으로 기록했다.
- [ ] 캡처 시각·응답 헤더·원문 SHA-256과 변경 이력이 불변 저장된다.

**검수자 이름/역할**: 미지정

**검수일**: 미지정

**승인 서명 또는 커밋**: 미지정

**결정**: `PENDING_RIGHTS_REVIEW`

## 6. 현재 차단 사유

1. 최근 10년 전국 정책·투기지역·지자체 공고의 전수 대조가 끝나지 않았다.
2. 원문 바이트 캡처와 SHA-256이 모두 `PENDING_CAPTURE`다.
3. 토지거래허가구역의 필지·도면·조건과 일부 공고번호가 남았다.
4. 세금 카드는 조사본이며 세무 담당자의 조문·부칙 검수가 없다.
5. 정책·세금·공간·권리 담당자의 실명 승인이 없다.

## 7. 최종 게이트

- [ ] 위 차단 사유가 모두 해소됐다.
- [ ] 정책 담당 승인 완료
- [ ] 세금 담당 승인 완료
- [ ] 공간 담당 승인 완료
- [ ] 권리 담당 승인 완료
- [ ] 컷오프 매니페스트 파일 해시와 승인 커밋을 기록했다.
- [ ] T006을 완료 처리해도 된다는 명시적 사람 승인을 받았다.

**최종 승인자**: 미지정

**최종 승인일**: 미지정

**승인 커밋/문서 해시**: 미지정

**최종 결정**: `PENDING_HUMAN_APPROVAL`

---

## English AI Context

```yaml
checklist_id: T006_RESEARCH_READINESS
cutoff_at: 2026-07-10T23:59:59+09:00
created_on: 2026-07-17
gate_status: PENDING_HUMAN_APPROVAL
implementation_approved: false
publication_approved: false
required_approvals:
  policy: PENDING_POLICY_REVIEW
  tax: PENDING_TAX_REVIEW
  spatial: PENDING_SPATIAL_REVIEW
  rights: PENDING_RIGHTS_REVIEW
blocking_gaps:
  - nationwide_policy_exhaustiveness
  - speculation_area_history
  - immutable_source_capture_and_sha256
  - parcel_and_boundary_coverage
  - tax_statute_and_transition_review
completion_rule: all_required_human_approvals_and_hashes_present
automated_research_progress:
  molit_2024_handbook_crosscheck: complete
  confirmed_2018_notice_numbers: [2018-1086, 2018-1088, 2018-1089]
  separated_predecessor_and_statutory_adjustment_area: true
  corrected_mixed_instrument_2020_12_18: true
  policy_event_rows: 68
  designation_instrument_rows: 40
  rhwp_version: v0.7.18
  rhwp_archive_sha256: BD0B3280C0B87580BFC8C86AF337609ACF939C5F8F1DA6AB3EE73955064420FD
  rhwp_executable_sha256: C92492674CD9B2BDEF7B550FD24591554F75FE391F6299F943B01B7AEEF4F859
  rhwp_generated_fixture_text_pages: 18
  rhwp_generated_fixture_markdown_pages: 18
  rhwp_manifest_hashes_verified: true
  rhwp_extraction_retention: TEMPORARY_NOT_RETAINED
  rhwp_government_hwp_reextraction:
    document: molit_notice_2018_1086
    prior_hash_matched: true
    text_pages: 2
    markdown_pages: 2
    retained: false
```
