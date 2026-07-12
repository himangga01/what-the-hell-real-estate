# 공식 출처 레지스트리 초안

**수동 확인일**: 2026-07-10  
**용도**: 구현 전 출처 어댑터, 신선도, 권리와 원문 캡처 대상을 고정한다.

## 상태 의미

- `수동 확인`: 사람이 공개 페이지 내용을 확인했다.
- `캡처 대기`: 수집기가 원문 바이트·응답 메타데이터·SHA-256을 아직 저장하지 않았다.
- `공고 보강 필요`: 보도자료·현황 페이지는 확인했으나 법적 공고·경계 원문 연결이 더 필요하다.
- `게시 가능`: 원문·권리·근거 범위·해시·사람 검수가 모두 끝난 상태다.

현재 아래 항목은 모두 초기 설계 근거이며 `게시 가능` 상태가 아니다.

## 초기 출처 목록

| ID | 기관·출처 | 역할 | URL | 수동 확인 | 다음 작업 |
|---|---|---|---|---|---|
| `law.openapi` | 국가법령정보센터 Open API | 법적 효력·조문 | [공식 API](https://open.law.go.kr/LSO/openApi/openApiManual.do) | 예 | 이용조건·호출한도 등록, 원문 버전 캡처 |
| `law.one-home` | 국가법령정보센터 | 1세대 1주택 법령 연결 | [원문](https://www.law.go.kr/LSW/lumLsLinkPop.do?ancYnChk=0&chrClsCd=010202&lspttninfSeq=126513) | 예 | 정확한 조문·시행 버전·해시 확정 |
| `molit.regulated-index` | 국토교통부 실거래가 공개시스템 | 현황 교차검증 | [규제지역 안내](https://rt.molit.go.kr/pt/gis/gis.do) | 예 | 법적 공고별 연결, 신선도 SLA 설정 |
| `molit.2026-06-30` | 국토교통부 | 설명·발견 | [후속 조치](https://www.molit.go.kr/USR/NEWS/m_72/dtl.jsp?id=95092167) | 예 | 첨부 공고·경계·시행일 원문 캡처 |
| `nts.cgt-transition-2026` | 국세청 | 세금 설명·경과 발견 | [중과 한시 배제 종료 안내](https://www.nts.go.kr/nts/na/ntt/selectNttInfo.do?bbsId=1028&mi=2201&nttSn=1349339) | 예 | 소득세법·시행령 조문과 증빙 요건 연결 |
| `nts.high-value-home` | 국세청 | 계산 설명 | [고가주택 양도차익 안내](https://d.nts.go.kr/nts/cm/cntnts/cntntsView.do?cntntsId=8799&mi=12271) | 예 | 공식 산식·예제·반올림 골든 사례 캡처 |
| `local.designations` | 서울시·경기도·시군구 공고 | 법적 효력·경계 | 기관별 등록 예정 | 부분 | 전국 지자체 레지스트리와 필지·도면 수집 허용 검토 |
| `gazette` | 대한민국 전자관보 | 법적 효력 | 기관 어댑터 등록 예정 | 대기 | 검색·첨부·권리 정책 확인 |

## 초기 사실 카드

### `FACT.REGULATED_AREAS.2026-07-10`

- 주장: 2026-07-10 현재 조정대상지역·투기과열지구의 현황
- 현황 근거: `molit.regulated-index`
- 변경 발견 근거: `molit.2026-06-30`
- 상태: `공고 보강 필요`
- 필수 보강: 각 지정 공고 번호, 법적 효력일, 행정구역·필지 범위, 원문 해시

### `FACT.LAND_PERMIT.NEW_AREAS.2026-07-05`

- 주장: 구리시·용인시 기흥구·화성시 동탄구 신규 토지거래허가구역 시행일
- 발견 근거: `molit.2026-06-30`
- 상태: `공고 보강 필요`
- 필수 보강: 지정권자 공고, 도면·필지 조서, 거래주체·부동산 유형·면적 조건

### `FACT.CGT.SURCHARGE.SUSPENSION.END.2026-05-09`

- 주장: 다주택자 양도소득세 중과 한시 배제 종료 경계
- 설명 근거: `nts.cgt-transition-2026`
- 상태: `공고 보강 필요`
- 필수 보강: 시행령 개정 버전, 계약금 증빙과 양도기한 경과규정의 정확한 조문

### `FACT.CGT.ONE_HOME.HIGH_VALUE.12E8`

- 주장: 1세대 1주택 고가주택 12억원 경계와 부분 과세 산식
- 법령 발견 근거: `law.one-home`
- 계산 설명: `nts.high-value-home`
- 상태: `공고 보강 필요`
- 필수 보강: 기준일 시행 조문, 산식·공제 관계와 골든 사례

## 출처 운영 규칙

- `LEGAL_EFFECT`와 `BOUNDARY`만 법적 판정의 직접 근거가 될 수 있다.
- `EXPLANATION`, `STATUS_INDEX`, `DISCOVERY_ONLY`는 법적 공고를 대체할 수 없다.
- 같은 URL에서 해시가 바뀌면 이전 스냅샷을 덮지 않고 검수 대기를 만든다.
- 403·로그인·CAPTCHA·챌린지는 우회하지 않는다.
- 권리 상태가 `LINK_ONLY`나 `REVIEW_REQUIRED`면 전문 공개와 RAG 색인을 보류한다.
- 현황 페이지가 오래됐다고 자동 해제하지 않고 이후 공고를 찾는다.

## 참고 사이트 경계

[부동산계산기.com](https://xn--989a00af8jnslv3dba.com/)은 `DISCOVERY_ONLY`보다도
좁은 `UX_REFERENCE_ONLY`로 취급한다. 자동 수집 출처 레지스트리에 넣지 않는다.
공개 메뉴의 업무 분류만 참고하고, `/api` 차단 경로·내부 API·계산 결과·문구·표·
뉴스·계산식·브랜드 자산을 수집하거나 복제하지 않는다.

---

## AI Context (English)

```yaml
manual_check_date: 2026-07-10
publication_ready_sources: 0
source_roles:
  decision_capable: [LEGAL_EFFECT, BOUNDARY]
  supporting_only: [EXPLANATION, STATUS_INDEX, DISCOVERY_ONLY]
current_seed_facts:
  - regulated_areas_as_of_2026_07_10
  - new_land_permit_effective_2026_07_05
  - cgt_surcharge_suspension_end_2026_05_09
  - one_home_high_value_krw_1_2b_boundary
required_before_publication:
  - immutable_source_snapshot
  - sha256
  - exact_legal_selector
  - rights_review
  - human_review
  - passing_golden_cases
competitor_site_policy: UX_REFERENCE_ONLY_NO_AUTOMATED_INGESTION
```
