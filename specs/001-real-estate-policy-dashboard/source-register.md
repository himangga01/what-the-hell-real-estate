# 공식 출처 레지스트리

**확인 기준일**: 2026-07-17

**데이터 컷오프**: 2026-07-10T23:59:59+09:00

**용도**: 구현 전 출처 역할, 신선도, 장애 대응, 수집 한도와 권리 경계를 고정한다.

## 1. 상태와 판정 원칙

- `VERIFIED`: 공식 페이지·조건을 확인했지만, 개별 문서의 법률·세무·공간 내용 승인을 뜻하지 않는다.
- `PARTIAL`: 공식 출처는 확인했으나 정량 SLA, 첨부 권리, 공고번호, 경계 또는 저장 조건이 남았다.
- `PENDING_REVIEW`: 사람의 권리·정책·세무·공간 검토 전에는 수집·게시·RAG 색인을 활성화하지 않는다.
- `PENDING_CAPTURE`: 이번 작업에서 원문 바이트를 보존하지 않아 SHA-256을 생성하지 않았다는 뜻이다.
- `LEGAL_EFFECT`와 `BOUNDARY`만 법적 판정의 직접 근거가 될 수 있다.
- `EXPLANATION`, `STATUS_INDEX`, `DISCOVERY_ONLY`는 발견과 설명에만 사용하고 공고·법령을 대체하지 않는다.

아래의 “프로젝트 재확인 목표”는 공급자가 보장한 SLA가 아니다. 공개된 공급자 SLA를 찾지
못한 경우 `미공개`로 분리했다. robots 허용도 저작권·약관상 이용 허락을 뜻하지 않는다.

권리 상태는 데이터 모델의 `ALLOWED`, `LINK_ONLY`, `REVIEW_REQUIRED`, `BLOCKED`만
사용한다. `ALLOWED` 행의 출처 표시 같은 부가 조건은 `rights_basis`에 보존한다.
`robots_status`는 아래 조사용 운영 상태이며 권리 상태와 독립적이다.

| robots 상태 | 의미 |
|---|---|
| `ALLOW_GENERAL_PATHS` | 확인한 일반 문서 경로에 명시적 차단을 찾지 못함. 대량 수집 허가는 아님 |
| `DEFAULT_DISALLOW_WITH_ALLOWLIST` | 기본 차단 후 허용 경로만 접근 |
| `MULTIPLE_PATHS_RESTRICTED` | 기관 내 여러 제한 경로가 있어 수집기별 확인 필요 |
| `SEARCH_AND_LIST_PATHS_RESTRICTED` | 검색·목록 자동 접근 제한. 문서 직접 경로도 요청 정책 준수 |
| `LEGACY_SEARCH_RESTRICTED` | 구 사이트 검색 제한과 현 사이트 정책을 별도 확인 |
| `API_APPLICATION_REQUIRED` | API 승인 후 발급 조건과 호출 정책 준수 |
| `API_PATHS_RESTRICTED` | 승인된 API 경로·속도만 사용 |
| `API_KEY_REQUIRED` | 키 발급과 제공기관 이용조건 준수 |
| `ROBOTS_POLICY_NOT_FOUND` | 명시 정책을 찾지 못함. 허용으로 해석하지 않음 |

## 2. 기관·출처 레지스트리

| 안정 키 | 기관·출처 | 기본 역할 | 공식 URL | 프로젝트 재확인 목표 | 공급자 SLA | 정확도·한계 | 장애 시 공식 확인 경로 | 요청·robots 경계 | 권리 운영 상태 | 캡처 |
|---|---|---|---|---:|---|---|---|---|---|---|
| `law.open-api` | 국가법령정보센터 공동활용 API | `LEGAL_EFFECT` | [공동활용 안내](https://open.law.go.kr/LSO/information/guide.do) · [API 가이드](https://open.law.go.kr/LSO/openApi/guideList.do) | 24시간 | 정량 한도 미공개 | 승인받은 API로 현행·연혁 법령, 행정규칙, 자치법규를 조회한다. 과도 호출은 제한될 수 있다. | 국가법령정보센터 웹 원문, 소관 기관, 전자관보 | 활용 신청·승인 필요. 사전 협의 없이 고빈도 호출 금지 | 법령·행정규칙 본문은 출처·버전·무결성 표시 조건의 `ALLOWED`; 판례·제3자 첨부는 별도 `REVIEW_REQUIRED` 행 | `PENDING_CAPTURE` |
| `law.web.attachments` | 국가법령정보센터의 판례·결정례·제3자 첨부 | `DISCOVERY_ONLY` | [국가법령정보센터](https://www.law.go.kr/) | 24시간 | 미공개 | 법령 본문과 별도 권리일 수 있어 직접 판정 근거에서 제외한다. | 소관 부처 원문, 전자관보 | 일반 웹 자동 대량 수집 대신 API를 우선한다. | 문서별 권리 검토 전 `REVIEW_REQUIRED`·링크만 제공 | `PENDING_CAPTURE` |
| `gazette` | 대한민국 전자관보 | `LEGAL_EFFECT` | [전자관보](https://www.gwanbo.go.kr/) | 24시간 | 미공개 | 일자·호수·정정·취소관보의 법적 게재 사실을 확인한다. 공식 API와 전국 첨부 전수 경로는 미확인이다. | 국가법령정보센터, 발행 기관 고시·공고 | robots 명시 파일 미확인. 검색·첨부를 우회 수집하지 않는다. | 약관의 가공·상업·무승인 배포 제한 때문에 PDF·DB는 `REVIEW_REQUIRED`, 검토 전 `LINK_ONLY` | `PENDING_CAPTURE` |
| `molit.legal-notices` | 국토교통부 고시·공고 본문 | `LEGAL_EFFECT` | [국토교통부 고시·공고](https://www.molit.go.kr/USR/I0204/m_45/lst.jsp) · [저작권정책](https://www.molit.go.kr/USR/WPGE0201/m_121/DTL.jsp) | 6시간 | 미공개 | 고시·공고 본문만 법적 효력 판정 후보로 사용한다. | 전자관보, 국가법령정보센터, 담당 부서 | 검색·목록 robots 제한을 준수하고 403·CAPTCHA를 우회하지 않는다. | 게시물별 공공누리 표시 확인 전 `REVIEW_REQUIRED` | `PENDING_CAPTURE` |
| `molit.boundary-attachments` | 국토교통부 지번표·도면·공간 첨부 | `BOUNDARY` | [국토교통부 고시·공고](https://www.molit.go.kr/USR/I0204/m_45/lst.jsp) | 6시간 | 미공개 | 본문과 첨부를 분리하고 필지·도면의 버전과 해시를 확인한다. | 발행 지자체 원문, 토지이음, 전자관보 | 첨부 직접 경로와 게시물별 robots·요청 정책을 확인한다. | 개별 첨부 권리 확인 전 `REVIEW_REQUIRED`·링크 전용 | `PENDING_CAPTURE` |
| `molit.press-releases` | 국토교통부 보도자료 | `EXPLANATION` | [국토교통부 보도자료](https://www.molit.go.kr/USR/NEWS/m_71/lst.jsp) | 24시간 | 미공개 | 변경 발견과 설명에만 사용하고 공고·법령을 대체하지 않는다. | 고시·공고, 국가법령정보센터, 전자관보 | 검색·목록 robots 제한을 준수한다. | 게시물별 공공누리 표시 확인 전 `REVIEW_REQUIRED` | `PENDING_CAPTURE` |
| `molit.policy-handbooks` | 국토교통부 주택업무편람 | `STATUS_INDEX` | [2024년 주택업무편람](https://www.molit.go.kr/USR/policyData/m_34681/dtl.jsp?id=4818) | 갱신 시 | 미공개 | 규제지역 지정·해제 연혁의 누락 탐지와 역방향 대조에만 사용한다. 개별 공고를 대체하지 않는다. | 개별 국토교통부 공고, 국가법령정보센터, 전자관보 | 정책자료 검색·첨부 경로의 요청 제한을 준수한다. | 문서별 공공누리·첨부 권리 확인 전 `REVIEW_REQUIRED` | `PENDING_CAPTURE`; 임시 해시만 아래 기록 |
| `mofe.policy` | 재정경제부 및 구 기획재정부 문서 | `EXPLANATION`, 문서별 `LEGAL_EFFECT` | [재정경제부](https://www.mofe.go.kr/) | 24시간 | 미공개 | 세제 정책 설명은 법령 발견에만 사용하고 법률·시행령 버전으로 재검증한다. 과거 문서는 당시 발행 기관명을 보존한다. | 국가법령정보센터, 전자관보 | 구 사이트 검색 robots 제한을 준수한다. 새 사이트의 통합 정책은 추가 캡처가 필요하다. | 항목별 공공누리 조건. 일괄 허용하지 않고 기본 `REVIEW_REQUIRED` | `PENDING_CAPTURE` |
| `nts.guides` | 국세청 세금 안내 | `EXPLANATION` | [국세청](https://www.nts.go.kr/) · [저작권정책](https://www.nts.go.kr/nts/cm/cntnts/cntntsView.do?cntntsId=8169&mi=6791) | 24시간 | 미공개 | 계산 안내·사례·경과 발견용이다. 세율·요건은 국가법령정보센터 시행 버전으로 재검증한다. | 국세상담센터 126, 국가법령정보센터 | 확인 당시 robots 일반 허용. 공개 API·정량 한도는 미확인 | 공공누리 표시 자료만 표시 유형에 따라 이용. 미표시·사례 첨부는 `REVIEW_REQUIRED` | `PENDING_CAPTURE` |
| `mois.policy` | 행정안전부 | `EXPLANATION`, 문서별 `LEGAL_EFFECT` | [행정안전부](https://www.mois.go.kr/) · [저작권정책](https://www.mois.go.kr/frt/sub/a08/copyrightPolicy/screen.do) | 24시간 | 미공개 | 지방세·주소 제도 설명을 법령·고시와 분리한다. | 국가법령정보센터, 전자관보, 담당 부서 | 확인 당시 일반 경로 robots 허용 | 공공누리 제1유형 표시 자료는 출처 표시 조건, 미표시는 `REVIEW_REQUIRED` | `PENDING_CAPTURE` |
| `seoul.notices` | 서울시·자치구 고시공고 | `LEGAL_EFFECT`, `BOUNDARY` | [서울특별시](https://www.seoul.go.kr/) · [저작권정책](https://www.seoul.go.kr/helper/copyright.do) | 6시간 | 미공개 | 서울시보·시/구 공고와 붙임 지번·도면을 문서별로 확인한다. | 서울시보, 자치구 고시공고, 전자관보 | 기본 차단 뒤 허용 경로를 열거하는 robots 정책. 허용되지 않은 첨부 경로 수집 금지 | 문서·첨부별 공공누리 확인 전 `REVIEW_REQUIRED` | `NOT_CAPTURED_ROBOTS_RESTRICTED` |
| `gyeonggi.local-notices` | 경기도·시군 고시공고 | `LEGAL_EFFECT`, `BOUNDARY` | [경기도](https://www.gg.go.kr/) | 6시간 | 미공개 | 경기도보와 각 시군 공고를 별도 출처로 확장해야 한다. 하나의 “지자체” 권리로 합치지 않는다. | 경기도보, 해당 시군 공식 게시판, 전자관보 | `/site/`, `/down/`, XML 등 확인된 제한 경로를 우회하지 않는다. | 기관·게시판·첨부별 `REVIEW_REQUIRED` | `NOT_CAPTURED_ROBOTS_RESTRICTED` |

문의 번호와 수동 대체 경로는 운영 설정에서 다시 확인한다. 조사 당시 국가법령정보센터
공동활용 문의는 02-2109-6446, 과도 호출 협의는 02-2109-6457, 국세 상담은 126,
행안부 주소 API 문의는 1588-0061로 안내됐다.

## 3. 운영 주소 정규화 후보

| 안정 키 | 후보 | 공식 기능·한도 | 정확도·저장 경계 | 장애 시 경로 | 운영 판단 |
|---|---|---|---|---|---|
| `juso.search-api` | 행안부 주소기반산업지원서비스 검색 API | [API 신청](https://business.juso.go.kr/addrlink/openApi/apiReqst.do). 정량 제한은 공식 Q&A에서 없다고 안내하지만 과도 호출 시 IP 차단 가능 | 도로명↔지번·건물관리번호 검색. PNU 직접 반환과 결과 저장·재배포 조건은 확정하지 못함 | 주소정보누리집 수동 검색, 1588-0061 | 별도 신청 후 sandbox 검증 전 `REVIEW_REQUIRED`; T101 결정 필요 |
| `juso.coordinate-api` | 행안부 좌표제공 API | 검색 API와 별도 신청. [공식 한도 답변](https://business.juso.go.kr/addrlink/qna/qnaDetail.do?bulletinRefSn=126550)에 따라 5초당 10건 | [좌표 설명](https://business.juso.go.kr/addrlink/qna/qnaDetail.do?bulletinRefSn=128137)의 UTM-K(GRS80). 좌표→PNU·보존 조건은 별도 확인 | 주소정보누리집, 1588-0061 | `REVIEW_REQUIRED`; 속도 제한·백오프 필수 |
| `vworld.geocoder` | 브이월드 Geocoder | [공공데이터포털 공식 항목](https://www.data.go.kr/data/15101106/openapi.do), 무료·일 최대 40,000건 | 주소→좌표. 공식 안내상 API 결과의 별도 저장장치·DB 저장 금지 | 브이월드 웹, 02-1661-0115 | 권리 상태는 `BLOCKED`, 제한 사유는 `NO_PERSISTENT_STORAGE`; 메모리 내 사용도 서면 확인 전 비활성 |

운영 제공자는 도로명 주소, 지번, 건물관리번호, 좌표와 PNU를 한 API가 모두 보장한다고
가정하지 않는다. 후보 API 실패·모호성 시 확정 판정을 중단하고 원문 주소를 저장하지 않은
채 공식 주소 검색과 토지이음/지자체 확인 경로를 안내한다.

## 4. 문서 권리 기본 규칙

세부 행은 [`research-data/source-rights.csv`](./research-data/source-rights.csv)에 기록한다.

| 유형 | 내부 전문 | 전문 공개 | RAG 색인 | 기본 상태 |
|---|---|---|---|---|
| 국가법령정보 공동활용의 법령·행정규칙 본문 | 출처·버전·무결성 조건으로 가능 | 같은 조건으로 가능 | 가능 | `ALLOWED` |
| 판례·결정례·제3자 첨부 | 검토 | 불가 | 불가 | `REVIEW_REQUIRED` |
| 전자관보 PDF·DB | 검토 | 불가 | 불가 | `LINK_ONLY` 임시값 |
| 공공누리 제1유형 표시 문서 | 출처 표시 후 가능 | 출처 표시 후 가능 | 가능 | 문서별 `ALLOWED` |
| 공공누리 2·3·4유형 또는 미표시 문서 | 검토 | 검토 전 불가 | 검토 전 불가 | `REVIEW_REQUIRED`/`LINK_ONLY` |
| 주소 API 원문 응답 | 기본 무저장 | 불가 | 불가 | Juso `REVIEW_REQUIRED`, VWorld `BLOCKED` |

- robots와 약관·공공누리·저작권은 각각 독립 검사한다.
- 페이지와 첨부파일을 별도 레코드로 관리한다.
- SHA-256은 수집 무결성 증거일 뿐 이용 허락이 아니다.
- 403·로그인·CAPTCHA·챌린지를 우회하지 않는다.
- 권리 검토 전 원문 공개, 임베딩, 생성 모델 전송을 하지 않는다.

## 5. 교차검증용 임시 캡처 증거

2024년 주택업무편람과 2017~2020년 규제지역 공고 HWP 6건은 연혁표·법적 전환·공고번호를
교차검증하기 위해 2026-07-17에 한 번 다운로드했다. 파일은 작업용 임시 디렉터리에서만
사용하고 저장소에는 보존하지 않았으므로, 아래 해시는 조사 당시의 응답을 식별할 뿐 불변 원문
캡처 게이트를 충족하지 않는다.

### 5.1 HWP 추출 도구 검증

2026-07-17에 공식 [`edwardkim/rhwp`](https://github.com/edwardkim/rhwp) `v0.7.18`
Windows x86_64 릴리스를 다음 조건으로 검증했다.

- 공식 archive SHA-256:
  `BD0B3280C0B87580BFC8C86AF337609ACF939C5F8F1DA6AB3EE73955064420FD`
- 압축 해제한 `rhwp.exe` SHA-256:
  `C92492674CD9B2BDEF7B550FD24591554F75FE391F6299F943B01B7AEEF4F859`
- 버전 출력: `rhwp v0.7.18`
- 공식 CLI `gen-table` 임시 HWP: text 18페이지, Markdown 18페이지 추출
- 입력 원문 보존과 매니페스트의 입력·페이지별 출력 SHA-256 재계산: 일치
- 국토교통부공고 제2018-1086호 HWP 임시 재추출: 기존 12,288바이트·SHA-256과 일치,
  text 2페이지·Markdown 2페이지, `국토교통부공고 제2018-1086호`·`광명시`·`하남시` 확인
- archive·실행 파일·생성 HWP·추출물: 통합검증 후 임시 디렉터리에서 삭제
- 라이선스: MIT, 프로젝트 고지 파일 `THIRD_PARTY_NOTICES.md`에 기록

아래 정부 HWP 6건 중 제2018-1086호 한 건만 새 파이프라인으로 임시 재추출했다. 나머지 5건은
아직 `rhwp` 재대조 전이며, 한 건의 원문·추출물도 불변 보존하지 않았다. 기존 임시 해시와
권리·불변 원문 게이트는 그대로이고 사람의 법적 효력 검수를 대체하지 않는다.

| 문서 | 공식 게시 페이지 | 응답 바이트 | SHA-256 | 보존 상태 | 사용 역할 |
|---|---|---:|---|---|---|
| 2024년 주택업무편람 PDF | [국토교통부 정책정보](https://www.molit.go.kr/USR/policyData/m_34681/dtl.jsp?id=4818) | 7,250,197 | `7ed969eb2eb3d9a64856fd724679a33b45fe23700be2b26af4d66bd3402de767` | `TEMPORARY_NOT_RETAINED` | `STATUS_INDEX`; 지정·해제 누락 탐지 |
| 국토교통부공고 제2017-1305호 HWP | [조정대상지역 예정지 지정](https://www.molit.go.kr/USR/I0204/m_45/dtl.jsp?idx=15151) | 23,040 | `5080ce5d676c8263e4a057e9dce1124f05c937d55471978e659cc9f8dadeb2f3` | `TEMPORARY_NOT_RETAINED` | `LEGAL_EFFECT`; 법률 제14866호 시행 전 예정지 40곳 교차검증 |
| 국토교통부공고 제2018-1086호 HWP | [투기과열지구 지정](https://www.molit.go.kr/USR/I0204/m_45/dtl.jsp?idx=15658) | 12,288 | `fea461b2ce654ac9fde7aef15b487435af59cae86ea46e0bb13800846ea62e9a` | `TEMPORARY_NOT_RETAINED` | `LEGAL_EFFECT` 번호·scope 교차검증 |
| 국토교통부공고 제2018-1088호 HWP | [조정대상지역 지정](https://www.molit.go.kr/USR/I0204/m_45/dtl.jsp?idx=15659) | 14,336 | `ec77c267066adc7c7439549e7355b0d7f35ec24c27ee898cdba4040a30abff66` | `TEMPORARY_NOT_RETAINED` | `LEGAL_EFFECT` 번호·scope 교차검증 |
| 국토교통부공고 제2018-1089호 HWP | [조정대상지역 지정 해제](https://www.molit.go.kr/USR/I0204/m_45/dtl.jsp?idx=15660) | 10,240 | `12ba74533969f4f7e495bbc18967505d40470504d75519aa5e05ee20db9ca7f0` | `TEMPORARY_NOT_RETAINED` | `LEGAL_EFFECT` 번호·scope 교차검증 |
| 국토교통부공고 제2019-1540호 HWP | [조정대상지역 조정](https://www.molit.go.kr/USR/I0204/m_45/dtl.jsp?idx=16220) | 11,264 | `465a838dd69a8399da7542bc51e985599cc2a5f90b7ba49b5dc33722d6a66afa` | `TEMPORARY_NOT_RETAINED` | `LEGAL_EFFECT` 번호·해제·유지 scope 교차검증 |
| 국토교통부공고 제2020-877호 HWP | [제2020-828호 정정](https://www.molit.go.kr/USR/I0204/m_45/dtl.jsp?idx=17020) | 19,968 | `b2801068c4eb5b415a6ddddb544ad510e1affbe0d9ceb2efc19923a198b6d173` | `TEMPORARY_NOT_RETAINED` | `LEGAL_EFFECT` 화성 누락·용인/광주 제외 범위 정정 교차검증 |

이 대조에서 2020-12-18 창원시 의창구는 조정대상지역이 아니라 별도 투기과열지구
공고 제2020-1649호의 범위이고, 같은 날 조정대상지역 공고 제2020-1650호의 창원 범위는
성산구임을 확인해 매니페스트를 정정했다.

또한 2016-11-03·2017-06-19 이력은 당시 주택공급 규칙상 청약 조정대상지역 선행 상태로
분리했다. 법률 제14866호 부칙 제2조와 공고 제2017-1305호에 따라 40개 예정지는 법 시행일인
2017-11-10에 주택법 제63조의2의 법정 조정대상지역으로 지정된 것으로 간주된다.

## 6. 초기 사실 카드와 남은 증거

### `FACT.REGULATED_AREAS.2026-07-10`

- 주장: 2026-07-10 현재 조정대상지역·투기과열지구 현황
- 현황 교차검증: 국토부 실거래가 규제지역 안내
- 변경 발견: 2026-06-30 국토부 후속 조치
- 상태: `PARTIAL`
- 남은 증거: 각 지정 공고 번호·효력일·지역 범위·원문/첨부 해시와 공간 검수

### `FACT.LAND_PERMIT.NEW_AREAS.2026-07-05`

- 주장: 구리시·용인시 기흥구·화성시 동탄구 170.5㎢의 아파트 대상 신규
  토지거래허가구역이 2026-07-05부터 2027-12-31까지 적용된다는 설명
- 설명 근거: 경기도 보도자료 번호 70759
- 상태: `PARTIAL`
- 남은 증거: 경기도 법적 공고번호, 도면·필지/아파트 조서, 전체 용도지역 면적 조건과 이용기간

### `FACT.CGT.SURCHARGE.SUSPENSION.END.2026-05-09`

- 주장: 다주택자 양도소득세 중과 한시 배제 종료 경계
- 설명 근거: 국세청 종료 안내
- 상태: `PARTIAL`
- 남은 증거: 시행령 정확한 버전, 계약금·토지거래허가·4/6개월 경과 조문과 세무 검수

### `FACT.CGT.ONE_HOME.HIGH_VALUE.12E8`

- 주장: 1세대 1주택 12억원 경계와 고가주택 안분
- 상태: `PARTIAL`
- 남은 증거: 기준일 시행 조문 selector, 반올림·공제 관계와 골든 사례 검수

## 7. 현재 게이트 상태

- 게시 가능 출처: 0개(개별 문서 권리·내용·해시·사람 검수가 아직 결합되지 않음)
- 실제 원문 바이트 캡처: 이번 작업 범위에서는 0건
- 주소 운영 제공자: 미선정(T101 승인 필요)
- 전국 지자체 공고·필지·도면: 미완료
- T006 정책·세금·공간 사람 승인: 미완료

---

## English AI Context

```yaml
checked_on: 2026-07-17
snapshot_cutoff: 2026-07-10T23:59:59+09:00
publication_ready_sources: 0
provider_sla_publicly_confirmed: false
freshness_values_are_internal_targets: true
rhwp_extraction:
  version: v0.7.18
  archive_sha256_windows_x86_64: BD0B3280C0B87580BFC8C86AF337609ACF939C5F8F1DA6AB3EE73955064420FD
  executable_sha256_windows_x86_64: C92492674CD9B2BDEF7B550FD24591554F75FE391F6299F943B01B7AEEF4F859
  integration_fixture: rhwp_gen_table_temporary_output
  text_pages: 18
  markdown_pages: 18
  input_and_output_hashes_verified: true
  extraction_retention: TEMPORARY_NOT_RETAINED
  government_hwp_temporary_reextraction_count: 1
  immutable_capture_completed: false
  government_hwp_evidence:
    document: molit_notice_2018_1086
    bytes: 12288
    sha256: fea461b2ce654ac9fde7aef15b487435af59cae86ea46e0bb13800846ea62e9a
    prior_hash_matched: true
    text_pages: 2
    markdown_pages: 2
    content_checks: [notice_2018_1086, gwangmyeong, hanam]
    retention: TEMPORARY_NOT_RETAINED
temporary_research_evidence:
  - document: molit_2024_housing_handbook
    bytes: 7250197
    sha256: 7ed969eb2eb3d9a64856fd724679a33b45fe23700be2b26af4d66bd3402de767
    retention: TEMPORARY_NOT_RETAINED
    role: STATUS_INDEX_ONLY
  - document: molit_notice_2017_1305
    bytes: 23040
    sha256: 5080ce5d676c8263e4a057e9dce1124f05c937d55471978e659cc9f8dadeb2f3
    retention: TEMPORARY_NOT_RETAINED
    role: LEGAL_EFFECT_CROSSCHECK_ONLY
  - document: molit_notice_2018_1086
    bytes: 12288
    sha256: fea461b2ce654ac9fde7aef15b487435af59cae86ea46e0bb13800846ea62e9a
    retention: TEMPORARY_NOT_RETAINED
    role: LEGAL_EFFECT_CROSSCHECK_ONLY
  - document: molit_notice_2018_1088
    bytes: 14336
    sha256: ec77c267066adc7c7439549e7355b0d7f35ec24c27ee898cdba4040a30abff66
    retention: TEMPORARY_NOT_RETAINED
    role: LEGAL_EFFECT_CROSSCHECK_ONLY
  - document: molit_notice_2018_1089
    bytes: 10240
    sha256: 12ba74533969f4f7e495bbc18967505d40470504d75519aa5e05ee20db9ca7f0
    retention: TEMPORARY_NOT_RETAINED
    role: LEGAL_EFFECT_CROSSCHECK_ONLY
  - document: molit_notice_2019_1540
    bytes: 11264
    sha256: 465a838dd69a8399da7542bc51e985599cc2a5f90b7ba49b5dc33722d6a66afa
    retention: TEMPORARY_NOT_RETAINED
    role: LEGAL_EFFECT_CROSSCHECK_ONLY
  - document: molit_notice_2020_877
    bytes: 19968
    sha256: b2801068c4eb5b415a6ddddb544ad510e1affbe0d9ceb2efc19923a198b6d173
    retention: TEMPORARY_NOT_RETAINED
    role: LEGAL_EFFECT_CROSSCHECK_ONLY
source_roles:
  decision_capable: [LEGAL_EFFECT, BOUNDARY]
  supporting_only: [EXPLANATION, STATUS_INDEX, DISCOVERY_ONLY]
rights:
  robots_is_not_permission: true
  page_and_attachment_are_separate: true
  uncaptured_hash_marker: PENDING_CAPTURE
  unknown_default: REVIEW_REQUIRED
address_candidates:
  juso_search: REVIEW_REQUIRED
  juso_coordinate:
    status: REVIEW_REQUIRED
    published_limit: 10_requests_per_5_seconds
  vworld:
    status: BLOCKED
    restriction: NO_PERSISTENT_STORAGE
    published_daily_limit: 40000
remaining_gates:
  - per_document_rights_and_content_review
  - immutable_byte_capture_and_sha256
  - nationwide_notice_and_boundary_collection
  - address_provider_approval_T101
  - policy_tax_spatial_human_approval_T006
```
