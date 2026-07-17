# 기술·도메인 조사 기록

**기준일**: 2026-07-10  
**범위**: 최근 10년 정책 원문 수집 체계, 현행 규제·세금 스냅샷, 기술 스택,
규칙 엔진, 시공간 모델, RAG, 개인정보와 참고 사이트 IA

## 조사 상태 요약

이 문서는 제품 구현 전에 확인한 설계 근거와 아직 전수 검수가 필요한 범위를
구분한다. 현행 규제지역과 핵심 세금 경계 일부는 정부 원문으로 확인했지만,
2016-07-10 이후 모든 정책 사건의 문서·공고·시행일 전수 목록은 아직 큐레이션
작업 대상이다. 따라서 이 문서는 `조사 체계와 초기 검증 스냅샷`이며 완성된
법률 데이터베이스라고 주장하지 않는다.

2026-07-17 감사에서는 정책 사건을 89건, 규제 지정 수단(공고)을 44건, 출처 권리 행을
21건으로 정규화했다. 기획재정부 투기지역 전자관보 4건은 원문 PDF·SHA-256을 불변
보존하고 모든 페이지를 렌더링해 확인했다. 그 밖의 정책·지정 원문과 전국 경계 자료는
아직 부분 상태이므로 T001~T003과 T006은 완료 처리하지 않는다.

## 1. 확인된 현행 스냅샷

### 1.1 규제지역과 토지거래허가구역

- 국토교통부 실거래가 공개시스템의 규제지역 안내를 기준으로 2026-07-10 현재
  조정대상지역과 투기과열지구는 서울 25개 구와 경기 15개 지역으로 확인한다.
- 국토교통부의 2026-06-30 발표에 따라 구리시, 용인시 기흥구, 화성시 동탄구의
  조정대상지역·투기과열지구 지정은 2026-07-01 효력이 시작되고, 해당 신규
  토지거래허가구역은 2026-07-05 효력이 시작된다.
- 보도자료는 발견·설명 근거이고 실제 주소 판정은 지정 공고, 필지 조서와
  공식 도면을 법적 효력 근거로 연결해야 한다.
- 투기지역은 조정대상지역·투기과열지구와 독립된 제도다. 다른 규제지역의
  확대를 투기지역 확대라고 추론하지 않는다.

검증 원문:

- [국토교통부 실거래가 공개시스템 규제지역 안내](https://rt.molit.go.kr/pt/gis/gis.do)
- [2026-06-30 국토교통부 주택시장 안정화 방안 후속 조치](https://www.molit.go.kr/USR/NEWS/m_72/dtl.jsp?id=95092167)

### 1.2 양도소득세 핵심 경계

- 다주택자 양도소득세 중과 일반 한시 배제는 2026-05-09가 마지막 적용일이고
  2026-05-10부터 일반 배제 종료 상태다. 계약일·양도일과 경과규정의 날짜 경계를 분리해 평가한다.
- 1세대 1주택 비과세는 보유·거주·주택 수·취득 당시 규제상태 등 사실관계가
  함께 필요하며, 고가주택 기준을 넘는 양도차익은 별도 계산이 필요하다.
- 고가주택 기준 금액 12억원을 단순 비과세 불가 불리언으로 표현하지 않고
  과세 대상 양도차익 산식의 입력 경계로 모델링한다.

검증 원문:

- [국세청 다주택자 양도소득세 중과 한시 배제 종료 안내](https://www.nts.go.kr/nts/na/ntt/selectNttInfo.do?bbsId=1028&mi=2201&nttSn=1349339)
- [국가법령정보센터 1세대 1주택 비과세 관련 법령 연결](https://www.law.go.kr/LSW/lumLsLinkPop.do?ancYnChk=0&chrClsCd=010202&lspttninfSeq=126513)
- [국세청 고가주택 양도차익 계산 안내](https://d.nts.go.kr/nts/cm/cntnts/cntntsView.do?cntntsId=8799&mi=12271)

주의: 위 세 항목은 세금 규칙 전체가 아니다. 취득세, 재산세, 종합부동산세,
양도소득세, 지방소득세의 전체 세율·공제·특례·경과규정은 규칙별 검수 카드와
골든 사례가 완성된 뒤 게시한다.

## 2. 최근 10년 정책 조사 방법

### 결정

연도별 기사 목록을 만드는 대신 `정책 사건 → 법적 수단 → 규칙·지정 버전 → 근거`
의 네 단계로 조사한다.

### 사건 분류

- 정책 발표
- 법령 공포·시행
- 조정대상지역·투기과열지구·투기지역 지정·해제
- 토지거래허가구역 지정·연장·해제·정정
- 세율·공제·비과세·중과·감면 변경
- 유예·경과규정 시작·종료
- 대출·거래 신고·실거주 의무 변경

### 출처 우선순위

1. 전자관보와 국토교통부·기획재정부·행정안전부·국세청·지자체 발행 원문
2. 국가법령정보센터의 현행·연혁 상태 색인과 공식 API
3. 공공데이터 포털과 공식 현황 API
4. 설명·발견용 정부 보도자료
5. 기사·블로그·경쟁 서비스는 검색 키워드 발견과 UX 참고에만 사용

국가법령정보센터는 [공식 Open API 안내](https://open.law.go.kr/LSO/openApi/openApiManual.do)를
제공하지만 센터 정보 자체에는 법적 효력이 없다고 안내한다. 따라서 현행·연혁 탐색에는
`STATUS_INDEX`로 사용하고 법적 효력은 전자관보 또는 발행기관 원문으로 확인한다. API
이용조건과 호출량을 출처 레지스트리에 기록하고, 원문 변경 시 이전 응답을 덮어쓰지 않는다.

### 조사 매니페스트

각 조사 배치는 다음을 기록한다.

```yaml
snapshot_cutoff: 2026-07-10T23:59:59+09:00
history_from: 2016-07-10T00:00:00+09:00
source_id: official-source-id
source_role: LEGAL_EFFECT | BOUNDARY | EXPLANATION | STATUS_INDEX | DISCOVERY_ONLY
retrieved_at: timestamp | null
content_sha256: sha256:{64 hex} | null
capture_status: NOT_CAPTURED | TEMPORARY_NOT_RETAINED | IMMUTABLE_CAPTURED
rights_status: ALLOWED | LINK_ONLY | REVIEW_REQUIRED | BLOCKED
verification_status: VERIFIED | PARTIAL | PENDING_REVIEW
cutoff_manifest:
  path: research-data/cutoff-manifest.csv
  artifact_rows: 12
  sha256: 6c074fd5affaf5c6b4bc4ad0e36c86b6ef3e1225b7283979c12ec901826a34ee
  approval_status: PENDING_T006
known_gaps:
  - id: stable-gap-id
    status: PARTIAL
    statement: machine-readable gap statement
```

현재 투기지역 이력에는 다음 공백을 명시한다.

```yaml
- id: GAP-SPECULATION-AREA-NATIONAL-COMPLETENESS
  status: PARTIAL
  period: 2016-07-10/2026-07-10
  statement: 전자관보 키워드 검색은 개별 공고의 발견·검증 근거일 뿐 전국 지정·해제 이력의 완전성 열거기가 아니다. 공식 상태 인덱스 또는 전수 목록 확보 전까지 전국 완전성을 주장하지 않는다.
```

### 필수 역사 경계 회귀 사례

- 2023-01-05 당시 강남·서초·송파·용산만 남은 규제지역 상태
- 2025-10-16 규제지역 시행과 2025-10-20 토지거래허가구역 시행의 분리
- 2026-06-30/07-01/07-05 구리·용인 기흥·화성 동탄의 단계적 변경
- 지정 만료 직전 연장 공고와 정정 공고가 기존 버전을 덮지 않는지 확인
- 과거 행정구역 코드가 현재와 다른 주소를 당시 경계로 재현

## 3. 참고 사이트 조사와 독자적 IA

참고한 공개 사이트는 [부동산계산기.com](https://xn--989a00af8jnslv3dba.com/)이다.
공개 메뉴 구조만 읽기 전용으로 참고했다. 확인한 `robots.txt`는 `/api`를 차단하며,
홈과 사이트맵의 Cloudflare 챌린지는 자동 접근 제한 신호이므로 내부 API 분석이나
우회를 하지 않는다.

관찰한 유용한 패턴:

- 법 조문보다 `취득·보유·양도·임대차·금융` 같은 사용자 사건으로 분류한다.
- 기본 질문과 복잡한 예외·고급 입력을 분리한다.
- 결과에서 기준표·도움말·공식 출처로 이동할 수 있다.
- 하나의 도구를 관련 업무 흐름에서 다시 찾을 수 있다.

독자 서비스의 결정:

- 고정 계산기 카탈로그를 복제하지 않고 `현재 정책 → 주소 규제 → 내 시나리오 →
  정책 이력·근거`의 의사결정 흐름을 쓴다.
- 참고 사이트의 문구, 표, 계산식, 메뉴 배열, 로고, 뉴스, 전문가 검수 표현과
  내부 API를 복제하거나 골든 데이터로 사용하지 않는다.
- 정부 원문에서 규칙과 검증 사례를 직접 구축한다.

## 4. 기술 선택 연구

### Python 3.14와 FastAPI

**결정**: Python 3.14, FastAPI, Pydantic 2를 쓴다.

**이유**:

- 정책 수집·문서 파싱·공간·검색 라이브러리 생태계와 잘 맞는다.
- 타입 힌트 기반 요청 검증과 OpenAPI 생성을 한 모델에서 관리할 수 있다.
- 규칙 평가와 수집 작업을 같은 언어로 구현해 검증 도구를 공유할 수 있다.

**대안**: Django는 내장 관리자 기능이 좋지만 API 중심 모듈형 구조에 더 많은
프레임워크 결합이 생긴다. Node 전용 백엔드는 프런트 언어를 통일할 수 있으나
문서·공간·데이터 처리의 Python 생태계 이점을 잃는다.

공식 근거: [Python 3.14 릴리스](https://www.python.org/downloads/release/python-3140/),
[FastAPI 공식 문서](https://fastapi.tiangolo.com/)

### React 19.2, Vite 8.1, Tailwind CSS 4.3

**결정**: React와 TypeScript로 접근 가능한 SPA를 구성하고 Vite와 Tailwind를 쓴다.

**이유**:

- 주소·기준일·단계형 시나리오 상태와 표·카드·타임라인 상호작용을 컴포넌트로 분리한다.
- Tailwind 토큰을 사용해 Figma 디자인 토큰과 코드 간 간격·색상·타이포를 맞춘다.
- 서버 렌더링이 필요한 검색 유입은 MVP 성과 측정 후 별도 결정한다.

공식 근거: [React 19.2](https://react.dev/blog/2025/10/01/react-19-2),
[Vite 8.1](https://vite.dev/blog/announcing-vite8-1),
[Tailwind CSS 4.3](https://tailwindcss.com/blog/tailwindcss-v4-3)

### PostgreSQL 18, PostGIS와 pgvector

**결정**: 정형 정책 데이터, 시간 구간, 공간 경계, 전문 검색과 벡터를 한
PostgreSQL 클러스터에서 관리한다.

**이유**:

- PostGIS는 행정구역·필지·도면 폴리곤의 포함·교차 판정과 공간 인덱스를 제공한다.
- pgvector는 검수 문서 조각을 정형 필터·전문 검색과 함께 조회할 수 있다.
- 별도 검색·벡터 서비스를 도입하지 않아 게시 트랜잭션, 백업과 삭제 정책을 단순화한다.

**대안**: Elasticsearch와 별도 벡터 DB는 대규모 검색에서 유리할 수 있지만 초기
데이터량과 운영 인력에 비해 복잡하다. SQLite는 로컬 데모에는 좋지만 다중 사용자,
공간 버전과 벡터 운영의 기준 저장소로 부족하다.

공식 근거: [PostgreSQL 18 발표](https://www.postgresql.org/about/news/postgresql-18-released-3142/),
[PostGIS 공식 문서](https://postgis.net/documentation/manual/),
[pgvector 공식 저장소](https://github.com/pgvector/pgvector)

## 5. 시공간 데이터 결정

### 결정

법적 효력이 있는 사실은 이중시간과 버전된 공간 객체로 저장한다.

- `valid_time`: 실제 효력 구간
- `system_time`: 시스템이 해당 버전을 게시 상태로 알고 있던 구간
- `published_at`: 기관 발표 시각
- `promulgated_at`: 공포 시각
- `observed_at`: 특정 수집·검증 작업이 관찰한 시각

기간은 한국 표준시 `[start, end)`로 통일한다. `end = null`은 무기한을 뜻하며
추정 종료일을 만들지 않는다. 정책 발표와 법적 지정 공고를 서로 다른 엔터티로
만들고 연결한다.

### 공간 객체

- 행정구역·법정동
- 필지·PNU
- 정비사업·개발사업 구역
- 공식 도면 폴리곤
- 포함·제외 필지 목록

토지거래허가구역은 주소 포함만으로 판정하지 않는다. 거래주체, 주택·토지 유형,
용도지역, 면적 문턱, 동일 단지 조건, 이용 의무와 허가권자를 함께 평가한다.

## 6. 규칙 엔진과 RAG 경계

### 결정론적 규칙 DSL

- 규칙은 사람이 검토 가능한 YAML과 제한된 JSON Schema를 쓴다.
- 실행 가능한 임의 코드, 템플릿 주입과 `eval`은 허용하지 않는다.
- 각 규칙은 ID, 버전, 우선순위, 적용·예외 조건, 결과, 유효기간, 근거, 골든 사례를 가진다.
- 규칙 충돌은 최신 날짜로 자동 해결하지 않고 게시를 막는다.
- 동일 입력·기준일·게시 스냅샷은 동일한 결과와 근거 순서를 반환한다.

### RAG

- 게시·검수·권리 확인이 끝난 원문 조각만 색인한다.
- 기준일, 기관, 문서 역할, 정책 유형과 규칙 근거를 먼저 필터링하고 전문 검색과
  벡터 유사도를 결합한다.
- 생성 모델은 판정 결과를 바꾸거나 새 세율을 만들 수 없다.
- 인용 가능한 근거가 없으면 `INSUFFICIENT_EVIDENCE`로 답변을 중단한다.

## 7. 개인정보와 안전

- 주민등록번호, 등기번호와 세대원 실명을 입력받지 않는다.
- 주소·가격·보유현황은 분석 요청 메모리에서만 사용하고 기본 영구 저장하지 않는다.
- 명시적 저장 동의 기능을 나중에 추가하더라도 TTL, 삭제, 내보내기와 감사 정책을 먼저 만든다.
- 원문 주소와 금액을 애플리케이션·오류·분석 로그에서 마스킹한다.
- 결과는 `적용 가능성`, `조건부`, `추가 정보 필요`, `공식 확인 필요`로 표현하고
  `확정`, `신고액`, `안전` 같은 오해 표현을 피한다.
- 결과에는 계산 기준일, 규칙 버전, 지원하지 않는 예외와 공식 문의 기관을 표시한다.

## 8. 출처별 수집·신선도 정책

| 출처군 | 기본 점검 주기 | 실패 처리 | 판정 역할 |
|---|---:|---|---|
| 법령·전자관보 | 매일 | 마지막 성공 시각 경고, 자동 비대상 금지 | 법적 효력 |
| 부처 고시·공고 | 6시간 | 변경 탐지 대기, 관리자 알림 | 법적 효력·경계 |
| 부처 보도자료 | 6시간 | 발견 지연 경고 | 설명·발견 |
| 지자체 공고 | 6시간 | 해당 지역 공식 확인 필요 표시 | 법적 효력·경계 |
| 현황 안내 페이지 | 매일 | 오래됨 표시, 공고보다 우선 금지 | 상태 교차검증 |
| 경쟁 서비스 | 자동 수집 안 함 | 해당 없음 | UX 참고만 |

실제 주기는 출처 이용조건과 호출 제한에 맞춰 출처 레지스트리에서 조정한다.

## 9. 해결된 질문과 남은 조사

### 해결된 결정

- 현재 정책과 과거 이력은 별도 기본 경로로 제공한다.
- 규칙 엔진과 RAG의 책임을 분리한다.
- 시공간 데이터는 이중시간과 버전 경계를 쓴다.
- PostgreSQL 하나에 정형·공간·검색 데이터를 통합한다.
- MVP에서 Redis, Celery와 별도 벡터 DB를 도입하지 않는다.

### 구현 전 반드시 완료할 데이터 조사

- 2016-07-10 이후 정책 사건 전수 매니페스트와 중복·누락 검증
- 현행 조정대상지역·투기과열지구·투기지역의 법적 공고 원문과 경계 파일 확보
- 전국 토지거래허가구역의 지자체별 필지 조서·도면·조건 정규화
- 취득세·재산세·종합부동산세·양도소득세의 현행 규칙 카드와 골든 사례
- 공공누리·저작권·robots·API 약관별 원문 보존 및 RAG 색인 허용 여부
- 주소 API의 이용조건, PNU·좌표 정확도와 장애 시 수동 확인 경로

---

## AI Context (English)

```yaml
research_date: 2026-07-10
audit_updated_on: 2026-07-17
row_counts:
  policy_events: 89
  policy_event_relations: 29
  designation_instruments: 44
  designation_evidence_links: 7
  source_rights: 21
  tax_rule_cards: 4
immutable_captures:
  gazette_pdfs: 4
  manifest: research-data/captures/manifest.csv
  manifest_sha256: 15ba1f67db608c318c8311de655d1986298bfd3720d6a4a8dee516858a649c95
  all_pages_render_reviewed: true
verified_now:
  - current_regulated_area_index
  - 2026_07_01_new_regulated_areas
  - 2026_07_05_new_land_transaction_permit_effective_date
  - 2026_05_09_multi_home_capital_gains_transition
  - one_house_exemption_and_krw_1_2b_high_value_boundary
not_yet_complete:
  - exhaustive_2016_2026_policy_event_manifest
  - nationwide_speculation_area_completeness
  - remaining_immutable_source_capture
  - nationwide_parcel_level_land_permit_boundaries
  - fully_reviewed_tax_rule_catalog
  - robots_and_terms_evidence_hashes
decisions:
  source_strategy: official_primary_source_first
  storage: postgresql_postgis_pgvector
  application: react_spa_plus_fastapi
  temporal_model: bitemporal_half_open_intervals_kst
  rule_engine: deterministic_safe_dsl
  rag: citation_only_over_published_evidence
  competitor_site: ia_reference_only_no_api_or_content_copy
```
