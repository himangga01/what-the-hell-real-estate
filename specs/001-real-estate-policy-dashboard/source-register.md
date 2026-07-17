# 공식 출처 레지스트리

**확인 기준일**: 2026-07-17

**데이터 컷오프**: 2026-07-10T23:59:59+09:00

**용도**: 구현 전 출처 역할, 신선도, 장애 대응, 수집 한도와 권리 경계를 고정한다.

## 1. 상태와 판정 원칙

- `VERIFIED`: 공식 페이지·조건을 확인했지만, 개별 문서의 법률·세무·공간 내용 승인을 뜻하지 않는다.
- `PARTIAL`: 공식 출처는 확인했으나 정량 SLA, 첨부 권리, 공고번호, 경계 또는 저장 조건이 남았다.
- `PENDING_REVIEW`: 사람의 권리·정책·세무·공간 검토 전에는 수집·게시·RAG 색인을 활성화하지 않는다.
- `NOT_CAPTURED`: 원문 바이트를 보존하지 않았고 SHA-256 값은 비워 둔다는 뜻이다.
- `TEMPORARY_NOT_RETAINED`: 조사 시 응답을 확인했지만 불변 원문을 보존하지 않았다는 뜻이다.
- `IMMUTABLE_CAPTURED`: 원문 바이트와 `sha256:{64 hex}`를 저장하고 매니페스트로 재검증할 수 있다는 뜻이다.
- `LEGAL_EFFECT`와 `BOUNDARY`만 법적 판정의 직접 근거가 될 수 있다. 국가법령정보센터
  화면·API는 센터 안내에 따라 법적 효력이 없는 참고·색인(`STATUS_INDEX`)으로 취급하고,
  관보 또는 발행기관 원문으로 최종 확인한다.
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
| `ROBOTS_POLICY_NOT_CAPTURED` | robots 원문 URL·확인 시각·해시를 아직 보존하지 않아 세부 허용·차단을 주장하지 않음 |
| `ROBOTS_POLICY_NOT_FOUND` | 명시 정책을 찾지 못함. 허용으로 해석하지 않음 |
| `OBSERVED_ALLOWED` | 조사 시 허용 규칙을 관찰했지만 응답 바이트를 보존하지 않아 해시 증거가 없음 |
| `OBSERVED_PATH_RULES` | 허용·차단 경로 규칙을 관찰했으나 대상 URL마다 다시 판정해야 함 |
| `OBSERVED_DEFAULT_DISALLOW_ALLOWLIST` | 기본 차단과 허용 목록을 관찰했으며 허용 목록 밖 접근은 중단함 |
| `OBSERVED_NOT_FOUND` | 404 또는 오류 페이지로 정책 파일을 찾지 못했으며 허용으로 해석하지 않음 |
| `OBSERVED_REDIRECT_LOOP` | 동일 URL 리디렉션 반복으로 정책 파일을 판독하지 못함 |
| `OBSERVED_SOFT_BLOCK` | HTTP 200 응답이었지만 실제 본문은 보안 차단 화면이었음 |
| `OBSERVED_CRAWL_DELAY_30` | 일반 허용과 30초 crawl-delay를 관찰했으나 이용 허락을 뜻하지 않음 |

## 2. 기관·출처 레지스트리

| 안정 키 | 기관·출처 | 기본 역할 | 공식 URL | 프로젝트 재확인 목표 | 공급자 SLA | 정확도·한계 | 장애 시 공식 확인 경로 | 요청·robots 경계 | 권리 운영 상태 | 캡처 |
|---|---|---|---|---:|---|---|---|---|---|---|
| `law.open-api` | 국가법령정보센터 공동활용 API | `STATUS_INDEX` | [공동활용 안내](https://open.law.go.kr/LSO/information/guide.do) · [법적효력·저작권](https://www.law.go.kr/lawPetitionForm.do?menuId=13&subMenuId=79) | 24시간 | 가용성·복구·정량 호출 SLA 미공개; 활용 승인 통상 1~2일은 신청 처리 안내이지 SLA가 아님 | 승인받은 API로 현행·연혁 법령, 행정규칙, 자치법규를 검색한다. 센터 제공 정보 자체에는 법적 효력이 없고 트래픽 부하 시 제한될 수 있다. | 전자관보, 소관 기관의 공포·고시 원문 | 모든 데이터는 신청·승인 뒤 사용. 제한·신청 문의 044-200-6797, 기술 문의 02-2109-6446 | 법령·행정규칙 본문은 출처 표시·위조/변조 금지 조건의 `ALLOWED`; 제3자 권리는 별도 `REVIEW_REQUIRED` | `NOT_CAPTURED` |
| `law.web.attachments` | 국가법령정보센터의 판례·결정례·제3자 첨부 | `DISCOVERY_ONLY` | [국가법령정보센터](https://www.law.go.kr/) | 24시간 | 미공개 | 법령 본문과 별도 권리일 수 있어 직접 판정 근거에서 제외한다. | 소관 부처 원문, 전자관보 | 일반 웹 자동 대량 수집 대신 API를 우선한다. | 문서별 권리 검토 전 `REVIEW_REQUIRED`·링크만 제공 | `NOT_CAPTURED` |
| `gazette` | 대한민국 전자관보 | `LEGAL_EFFECT` | [전자관보](https://www.gwanbo.go.kr/) · [저작권정책](https://www.gwanbo.go.kr/user/info/copyright.do) | 24시간 | 서비스 이용시간 24/7 원칙이나 점검·기술 사유 중단 가능; 가용성·복구·정량 SLA 미공개 | 일자·호수·정정·취소관보의 법적 게재 사실을 확인한다. 공식 API와 전국 첨부 전수 경로는 미확인이다. | 발행 기관 고시·공고, 국가법령정보센터 참고 색인 | robots 증거 미캡처. 검색·첨부를 우회 수집하지 않는다. | 전자관보는 저작권법 제7조 대상으로 별도 이용허락 없이 자유이용 가능한 `ALLOWED`; 출처 표시 필요. 전자관보 외 홈페이지 게시물은 문서별 공공누리 검토 | 투기지역 관보 4건 `IMMUTABLE_CAPTURED`; 나머지 `NOT_CAPTURED` |
| `molit.legal-notices` | 국토교통부 고시·공고 문서군 | `LEGAL_EFFECT` | [국토교통부 고시·공고](https://www.molit.go.kr/USR/I0204/m_45/lst.jsp) · [저작권정책](https://www.molit.go.kr/USR/WPGE0201/m_121/DTL.jsp) | 6시간 | 미공개 | 본문과 공식 붙임을 하나의 문서군으로 버전 관리하고 문서번호·게재일·시행일·정정/취소·붙임 해시를 함께 확인한다. 게시판 목록과 보도자료는 직접 판정 근거가 아니다. | 전자관보, 국가법령정보센터 참고 색인, 담당 부서 | robots 증거 미캡처. 403·CAPTCHA를 우회하지 않는다. | 게시물별 공공누리 표시 확인 전 `REVIEW_REQUIRED` | `NOT_CAPTURED` |
| `molit.boundary-attachments` | 국토교통부 지번표·도면·공간 첨부 | `BOUNDARY` | [국토교통부 고시·공고](https://www.molit.go.kr/USR/I0204/m_45/lst.jsp) | 6시간 | 미공개 | 공고 상세 페이지를 안정 부모 URL로 두고 각 붙임 URL·버전·필지·도면·해시를 별도 기록한다. 일반 다운로드 엔드포인트만 canonical URL로 사용하지 않는다. | 발행 지자체 원문, 토지이음, 전자관보 | robots 증거 미캡처. 첨부 직접 경로의 요청 정책을 문서별 확인한다. | 개별 첨부 권리 확인 전 `REVIEW_REQUIRED`·링크 전용 | `NOT_CAPTURED` |
| `molit.press-releases` | 국토교통부 보도자료 | `EXPLANATION` | [국토교통부 보도자료](https://www.molit.go.kr/USR/NEWS/m_71/lst.jsp) | 24시간 | 미공개 | 변경 발견과 설명에만 사용하고 공고·법령을 대체하지 않는다. | 고시·공고, 국가법령정보센터, 전자관보 | 검색·목록 robots 제한을 준수한다. | 게시물별 공공누리 표시 확인 전 `REVIEW_REQUIRED` | `NOT_CAPTURED` |
| `molit.policy-handbooks` | 국토교통부 주택업무편람 | `STATUS_INDEX` | [2024년 주택업무편람](https://www.molit.go.kr/USR/policyData/m_34681/dtl.jsp?id=4818) | 갱신 시 | 미공개 | 규제지역 지정·해제 연혁의 누락 탐지와 역방향 대조에만 사용한다. 개별 공고를 대체하지 않는다. | 개별 국토교통부 공고, 국가법령정보센터, 전자관보 | 정책자료 검색·첨부 경로의 요청 제한을 준수한다. | 문서별 공공누리·첨부 권리 확인 전 `REVIEW_REQUIRED` | `TEMPORARY_NOT_RETAINED`; 임시 해시만 아래 기록 |
| `mofe.policy-explanations` | 재정경제부·구 기획재정부 정책 설명 | `EXPLANATION` | [재정경제부](https://www.mofe.go.kr/) · [저작권정책](https://www.mofe.go.kr/mn/siteguide/drmp.do?menuNo=2030000) | 24시간 | 미공개 | 세제 정책 설명은 법령·관보 발견에만 사용한다. 과거 문서는 당시 발행 기관명을 보존한다. | 전자관보, 발행 당시 기관 고시·공고 | robots 증거 미캡처 | 항목별 공공누리 조건. 일괄 허용하지 않고 기본 `REVIEW_REQUIRED` | `NOT_CAPTURED` |
| `mofe.legal-notices` | 재정경제부·구 기획재정부 고시·공고 | `LEGAL_EFFECT` | [고시·공고 목록](https://mofe.go.kr/lw/denm/TbDenmList.do?bbsId=MOSFBBS_000000000120&menuNo=7090200) · [저작권정책](https://www.mofe.go.kr/mn/siteguide/drmp.do?menuNo=2030000) | 24시간 | 미공개 | 개별 고시·공고와 관보를 대조하고 정정·취소·시행일·붙임을 함께 확인한다. | 전자관보, 담당 부서 | robots 증거 미캡처 | 문서별 공공누리 확인 전 `REVIEW_REQUIRED` | `NOT_CAPTURED` |
| `mofe.tax-interpretations` | 재정경제부 세법해석 | `STATUS_INDEX` | [세법해석 목록](https://mofe.go.kr/lw/intrprt/TaxLawIntrPrtCaseList.do?bbsId=MOSFBBS_000000000237&menuNo=8120300) | 24시간 | 미공개 | 일반 사례·해석 발견용이며 신청인 특정 사실관계나 법원 판결을 대체하지 않는다. | 관보·법령 원문, 국세상담센터 126, 전문가 | robots 증거 미캡처 | 문서별 권리 확인 전 `REVIEW_REQUIRED` | `NOT_CAPTURED` |
| `nts.guides` | 국세청 세금 안내 | `EXPLANATION` | [국세청](https://www.nts.go.kr/) · [국세법령정보시스템](https://taxlaw.nts.go.kr/qt/USEQTM001M.do) · [저작권정책](https://www.nts.go.kr/nts/cm/cntnts/cntntsView.do?cntntsId=8169&mi=6791) | 24시간 | 미공개 | 참고자료이며 개별 사안에 동일 적용되지 않을 수 있다. 계산 안내·사례는 발견용이고 세율·요건은 관보·법령 원문과 세무 검수로 재확인한다. | 국세상담센터 126, 관보·법령 원문, 세무 전문가 | robots 증거 미캡처. 공개 API·정량 한도 미확인 | 공공누리 표시 자료만 표시 유형에 따라 이용. 미표시·사례 첨부는 `REVIEW_REQUIRED` | `NOT_CAPTURED` |
| `mois.policy-explanations` | 행정안전부 정책 설명 | `EXPLANATION` | [행정안전부](https://www.mois.go.kr/) · [저작권정책](https://www.mois.go.kr/frt/sub/a08/copyrightPolicy/screen.do) | 24시간 | 미공개 | 지방세·주소 제도 설명은 법령·고시 발견에만 사용한다. | 전자관보, 발행기관 법적 문서, 담당 부서 | robots 증거 미캡처 | 문서별 공공누리 확인 전 `REVIEW_REQUIRED` | `NOT_CAPTURED` |
| `mois.legal-instruments` | 행정안전부 훈령·예규·고시 | `LEGAL_EFFECT` | [훈령·예규·고시](https://www.mois.go.kr/frt/bbs/type001/commonSelectBoardList.do?bbsId=BBSMSTR_000000000016) · [저작권정책](https://www.mois.go.kr/frt/sub/a08/copyrightPolicy/screen.do) | 24시간 | 미공개 | 문서번호·시행일·정정/폐지와 관보 게재를 확인한다. | 전자관보, 국가법령정보센터 참고 색인, 담당 부서 | robots 증거 미캡처 | 문서별 공공누리 확인 전 `REVIEW_REQUIRED` | `NOT_CAPTURED` |
| `seoul.city-notices` | 서울특별시 본청 고시·공고 | `LEGAL_EFFECT` | [서울시 고시·공고](https://www.seoul.go.kr/news/news_notice.do) · [저작권정책](https://www.seoul.go.kr/helper/copyright.do) | 6시간 | 미공개 | 누락·번호 검색은 서울시보로 대조한다. 25개 자치구는 이 행에 포함하지 않는다. | 서울시보, 전자관보, 담당 부서 | robots 증거 미캡처 | 문서별 공공누리 0~4·AI 유형 확인 전 `REVIEW_REQUIRED` | `NOT_CAPTURED` |
| `seoul.city-boundary-attachments` | 서울특별시 본청 지번표·도면 | `BOUNDARY` | [서울시 고시·공고](https://www.seoul.go.kr/news/news_notice.do) | 6시간 | 미공개 | 법적 공고와 붙임 지번·도면을 별도 버전·해시로 보존한다. 25개 자치구 첨부는 별도 등록 전 비활성이다. | 서울시보, 해당 자치구 공식 게시판 | robots 증거 미캡처 | 첨부별 공공누리·제3자 권리 확인 전 `REVIEW_REQUIRED` | `NOT_CAPTURED` |
| `gyeonggi.province-notices` | 경기도 본청 도보·고시공고 | `LEGAL_EFFECT` | [경기도보](https://www.gg.go.kr/gg-dobo) · [저작권정책](https://www.gg.go.kr/contents/contents.do?ciIdx=1066&menuId=2772) | 6시간 | 미공개 | 경기도 본청 공고만 포함한다. 31개 시군은 이 행에 포함하지 않는다. | 전자관보, 담당 부서 | robots 증거 미캡처 | 문서별 공공누리 유형 확인 전 `REVIEW_REQUIRED` | `NOT_CAPTURED` |
| `gyeonggi.province-boundary-attachments` | 경기도 본청 지번표·도면 | `BOUNDARY` | [경기도보](https://www.gg.go.kr/gg-dobo) | 6시간 | 미공개 | 공고와 붙임 필지·단지 조서·도면을 별도 버전·해시로 보존한다. 31개 시군 첨부는 별도 등록 전 비활성이다. | 해당 시군 공식 게시판, 토지이음 | robots 증거 미캡처 | 첨부별 공공누리·제3자 권리 확인 전 `REVIEW_REQUIRED` | `NOT_CAPTURED` |

서울 25개 자치구와 경기도 31개 시군 제공자는 stable key·공식 게시판·권리·robots 증거를
각각 등록하기 전 모두 `DISABLED_PENDING_REVIEW`다. 본청 행의 권리나 요청 정책을 상속하지 않는다.

문의 번호와 수동 대체 경로는 운영 설정에서 다시 확인한다. 조사 당시 국가법령정보센터
공동활용 제한·신청 문의는 044-200-6797, 기술 문의는 02-2109-6446, 국세 상담은 126,
행안부 주소 API 문의는 1588-0061로 안내됐다.

### 2.1 robots·권리 페이지 임시 관찰

2026-07-17에 공식 호스트의 robots와 권리 페이지를 직접 확인했다. 응답 바이트와 임시 계산
해시는 저장소에 보존하지 않았고 `source-rights.csv`의 증거 해시 열도 비워 두었다.
404·오류 HTML·소프트 차단 본문은 정상 정책 증거로 등록하지 않는다.

| 호스트 | 공식 robots URL | 관찰 결과 |
|---|---|---|
| 국가법령정보센터 | [robots.txt](https://www.law.go.kr/robots.txt) | 전체 허용 |
| 국가법령정보 공동활용 | [robots.txt](https://open.law.go.kr/robots.txt) | missing HTML로 리디렉션되어 정책 파일 없음 |
| 전자관보 | [robots.txt](https://www.gwanbo.go.kr/robots.txt) | 404 HTML, 허용으로 해석하지 않음 |
| 국토교통부 | [robots.txt](https://www.molit.go.kr/robots.txt) | 동일 URL 307 리디렉션 반복 |
| 재정경제부 | [robots.txt](https://www.mofe.go.kr/robots.txt) | 검색·설문 일부 제한, 관련 `/lw`·`/mn` 경로 허용 |
| 국세청 | [robots.txt](https://www.nts.go.kr/robots.txt) | 전체 허용 |
| 국세법령정보시스템 | [robots.txt](https://taxlaw.nts.go.kr/robots.txt) | `/is` 일부 제한, 관련 `/qt`·`/br` 경로 허용 |
| 행정안전부 | [robots.txt](https://www.mois.go.kr/robots.txt) | 전체 허용 |
| 서울특별시 | [robots.txt](https://www.seoul.go.kr/robots.txt) | 기본 차단, `/news`·`/helper` 등 허용 목록 |
| 경기도 | [robots.txt](https://www.gg.go.kr/robots.txt) | HTTP 200이지만 보안 차단 HTML |
| 주소정보누리집 | [robots.txt](https://business.juso.go.kr/robots.txt) | `/jsi`·`/jsm` 선택 차단 |
| 브이월드 | [robots.txt](https://www.vworld.kr/robots.txt) | 일반 허용, crawl-delay 30 |

권리·이용조건은 robots와 별도로 확인했다. 국가법령정보센터의
[법적효력·저작권](https://www.law.go.kr/lawPetitionForm.do?menuId=13&subMenuId=79),
[공동활용 안내](https://open.law.go.kr/LSO/information/guide.do), 전자관보
[저작권정책](https://www.gwanbo.go.kr/user/info/copyright.do), 재정경제부
[저작권정책](https://www.mofe.go.kr/mn/siteguide/drmp.do?menuNo=2030000), 국세청
[저작권정책](https://www.nts.go.kr/nts/cm/cntnts/cntntsView.do?cntntsId=8169&mi=6791),
행정안전부 [저작권정책](https://www.mois.go.kr/frt/sub/a08/copyrightPolicy/screen.do), 서울시
[저작권정책](https://www.seoul.go.kr/helper/copyright.do), 브이월드
[Geocoder 안내](https://www.vworld.kr/dev/v4dv_geocoderguide2_s001.do)를 확인했다. 개별
공공누리 유형과 제3자 권리는 문서마다 다시 판정한다. 국토교통부는 리디렉션 반복, 경기도는
보안 차단 HTML 때문에 권리 본문을 확보하지 못했고, Juso API 목록은 약관이 아니어서
저장·재배포 허용 범위는 계속 `REVIEW_REQUIRED`다.

## 3. 운영 주소 정규화 후보

| 안정 키 | 후보 | 공식 기능·한도 | 정확도·저장 경계 | 장애 시 경로 | 운영 판단 |
|---|---|---|---|---|---|
| `juso.search-api` | 행안부 주소기반산업지원서비스 검색 API | [현재 API 목록](https://business.juso.go.kr/jst/jstAddressApiList). 정량 제한 없음 안내, 과도 호출 시 IP 차단 가능 | 도로명↔지번·건물관리번호 검색. 좌표를 반환하지 않으며 도로명·지번은 항상 1:1이 아니다. PNU 직접 반환과 결과 저장·재배포 조건은 미확정 | 주소정보누리집 수동 검색, 1588-0061 | 별도 신청 후 sandbox 검증 전 `REVIEW_REQUIRED`; T101 결정 필요 |
| `juso.coordinate-api` | 행안부 좌표제공 API | 검색 API와 별도 신청. [공식 한도 답변](https://business.juso.go.kr/api/jsi/qna-board/126550/126550)에 따라 5초당 10건 | [좌표 설명](https://business.juso.go.kr/api/jsi/qna-board/128137/128137)의 UTM-K(GRS80). [누락 가능성 안내](https://business.juso.go.kr/api/jsi/qna-board/101585/101585)처럼 비공개 시설은 좌표가 없을 수 있고 좌표→PNU·보존 조건은 미확정 | 주소정보누리집, 1588-0061 | `REVIEW_REQUIRED`; 속도 제한·백오프 필수 |
| `vworld.geocoder` | 브이월드 Geocoder | [공식 Geocoder 레퍼런스](https://www.vworld.kr/dev/v4dv_geocoderguide2_s001.do), 일 최대 40,000건 | 주소→좌표, 기본 EPSG:4326과 선택 좌표계 지원. 결과의 별도 저장장치·DB 저장 금지, 정확도 보장·가용성 SLA 미공개 | 브이월드 웹, 02-1661-0115 | 영구 snapshot·RAG·공개는 `BLOCKED`/`NO_PERSISTENT_STORAGE`; 메모리 내 일회성 사용도 T101 별도 승인 전 비활성 |

운영 제공자는 도로명 주소, 지번, 건물관리번호, 좌표와 PNU를 한 API가 모두 보장한다고
가정하지 않는다. 후보 API 실패·모호성 시 확정 판정을 중단하고 원문 주소를 저장하지 않은
채 공식 주소 검색과 토지이음/지자체 확인 경로를 안내한다.

## 4. 문서 권리 기본 규칙

세부 행은 [`research-data/source-rights.csv`](./research-data/source-rights.csv)에 기록한다.

| 유형 | 내부 전문 | 전문 공개 | RAG 색인 | 기본 상태 |
|---|---|---|---|---|
| 국가법령정보 공동활용의 법령·행정규칙 본문 | 출처·버전·무결성 조건으로 가능 | 같은 조건으로 가능 | 가능 | `ALLOWED` |
| 판례·결정례·제3자 첨부 | 검토 | 불가 | 불가 | `REVIEW_REQUIRED` |
| 전자관보 PDF·DB | 출처·진본·버전·무결성 표시 후 가능 | 같은 조건으로 가능 | 같은 조건으로 가능 | `ALLOWED` |
| 공공누리 제1유형 표시 문서 | 출처 표시 후 가능 | 출처 표시 후 가능 | 가능 | 문서별 `ALLOWED` |
| 공공누리 2·3·4유형 또는 미표시 문서 | 검토 | 검토 전 불가 | 검토 전 불가 | `REVIEW_REQUIRED`/`LINK_ONLY` |
| 주소 API 원문 응답 | 기본 무저장 | 불가 | 불가 | Juso `REVIEW_REQUIRED`, VWorld `BLOCKED` |

- robots와 약관·공공누리·저작권은 각각 독립 검사한다.
- 페이지와 첨부파일을 별도 레코드로 관리한다.
- SHA-256은 수집 무결성 증거일 뿐 이용 허락이 아니다.
- 403·로그인·CAPTCHA·챌린지를 우회하지 않는다.
- 권리 검토 전 원문 공개, 임베딩, 생성 모델 전송을 하지 않는다.

## 5. 원문 캡처 증거

2024년 주택업무편람과 2017~2020년 규제지역 공고 HWP 7건은 연혁표·법적 전환·공고번호를
교차검증하기 위해 2026-07-17에 한 번 다운로드했다. 파일은 작업용 임시 디렉터리에서만
사용하고 저장소에는 보존하지 않았으므로, 아래 해시는 조사 당시의 응답을 식별할 뿐 불변 원문
캡처 게이트를 충족하지 않는다.

### 5.1 교차검증용 임시 HWP 추출

2026-07-17에 공식 [`edwardkim/rhwp`](https://github.com/edwardkim/rhwp) `v0.7.18`
Windows x86_64 릴리스를 다음 조건으로 검증했다.

- 공식 archive SHA-256:
  `BD0B3280C0B87580BFC8C86AF337609ACF939C5F8F1DA6AB3EE73955064420FD`
- 압축 해제한 `rhwp.exe` SHA-256:
  `C92492674CD9B2BDEF7B550FD24591554F75FE391F6299F943B01B7AEEF4F859`
- 버전 출력: `rhwp v0.7.18`
- 공식 CLI `gen-table` 임시 HWP: text 18페이지, Markdown 18페이지 추출
- 입력 원문 보존과 매니페스트의 입력·페이지별 출력 SHA-256 재계산: 일치
- 각 리디렉션을 요청 전에 허용 호스트로 검사하고, 입력 전후 SHA-256·폐쇄형 출력 트리·
  소유권 표식 미게시·원자 게시 경쟁 상태를 포함한 단위 테스트 25건: 통과
- 성공 명령의 도구 진단 메시지 기록과 실행 중 생성한 손상 HWP의 fail-closed 통합 경로: 통과
- Windows PowerShell 5.1 단위·로컬 302 기본 경로: 필수 CI, 공식 릴리스 통합: 수동 CI
- 국토교통부공고 제2018-1086호 HWP 임시 재추출: 기존 12,288바이트·SHA-256과 일치,
  text 2페이지·Markdown 2페이지, `국토교통부공고 제2018-1086호`·`광명시`·`하남시` 확인
- 국토교통부공고 제2018-1090호 HWP 신규 임시 추출: 18,944바이트, text 2페이지·
  Markdown 2페이지, 문서번호·구리시·안양시 동안구·광교택지개발지구·공고일부터 효력 확인
- archive·실행 파일·생성 HWP·추출물: 통합검증 후 임시 디렉터리에서 삭제
- 라이선스: MIT, 프로젝트 고지 파일 `THIRD_PARTY_NOTICES.md`에 기록

아래 정부 HWP 7건 중 제2018-1086호와 제2018-1090호 두 건을 새 파이프라인으로 임시
추출·재대조했다. 나머지 5건은 아직 `rhwp` 재대조 전이며, 한 건의 원문·추출물도 불변
보존하지 않았다. 기존 임시 해시와
권리·불변 원문 게이트는 그대로이고 사람의 법적 효력 검수를 대체하지 않는다.

| 문서 | 공식 게시 페이지 | 응답 바이트 | SHA-256 | 보존 상태 | 사용 역할 |
|---|---|---:|---|---|---|
| 2024년 주택업무편람 PDF | [국토교통부 정책정보](https://www.molit.go.kr/USR/policyData/m_34681/dtl.jsp?id=4818) | 7,250,197 | `7ed969eb2eb3d9a64856fd724679a33b45fe23700be2b26af4d66bd3402de767` | `TEMPORARY_NOT_RETAINED` | `STATUS_INDEX`; 지정·해제 누락 탐지 |
| 국토교통부공고 제2017-1305호 HWP | [조정대상지역 예정지 지정](https://www.molit.go.kr/USR/I0204/m_45/dtl.jsp?idx=15151) | 23,040 | `5080ce5d676c8263e4a057e9dce1124f05c937d55471978e659cc9f8dadeb2f3` | `TEMPORARY_NOT_RETAINED` | `LEGAL_EFFECT`; 법률 제14866호 시행 전 예정지 40곳 교차검증 |
| 국토교통부공고 제2018-1086호 HWP | [투기과열지구 지정](https://www.molit.go.kr/USR/I0204/m_45/dtl.jsp?idx=15658) | 12,288 | `fea461b2ce654ac9fde7aef15b487435af59cae86ea46e0bb13800846ea62e9a` | `TEMPORARY_NOT_RETAINED` | `LEGAL_EFFECT` 번호·scope 교차검증 |
| 국토교통부공고 제2018-1088호 HWP | [조정대상지역 지정](https://www.molit.go.kr/USR/I0204/m_45/dtl.jsp?idx=15659) | 14,336 | `ec77c267066adc7c7439549e7355b0d7f35ec24c27ee898cdba4040a30abff66` | `TEMPORARY_NOT_RETAINED` | `LEGAL_EFFECT` 번호·scope 교차검증 |
| 국토교통부공고 제2018-1089호 HWP | [조정대상지역 지정 해제](https://www.molit.go.kr/USR/I0204/m_45/dtl.jsp?idx=15660) | 10,240 | `12ba74533969f4f7e495bbc18967505d40470504d75519aa5e05ee20db9ca7f0` | `TEMPORARY_NOT_RETAINED` | `LEGAL_EFFECT` 번호·scope 교차검증 |
| 국토교통부공고 제2018-1090호 HWP | [조정대상지역 전매행위 제한기간 지정](https://www.molit.go.kr/USR/I0204/m_45/dtl.jsp?idx=15661) | 18,944 | `7f3a3772fd0a634ca74a3a45c90ae34701d366aaeac5bec200c220ea40ed8c08` | `TEMPORARY_NOT_RETAINED` | `LEGAL_EFFECT` 번호·구리·안양 동안·광교 범위·공고일 효력 교차검증 |
| 국토교통부공고 제2019-1540호 HWP | [조정대상지역 조정](https://www.molit.go.kr/USR/I0204/m_45/dtl.jsp?idx=16220) | 11,264 | `465a838dd69a8399da7542bc51e985599cc2a5f90b7ba49b5dc33722d6a66afa` | `TEMPORARY_NOT_RETAINED` | `LEGAL_EFFECT` 번호·해제·유지 scope 교차검증 |
| 국토교통부공고 제2020-877호 HWP | [제2020-828호 정정](https://www.molit.go.kr/USR/I0204/m_45/dtl.jsp?idx=17020) | 19,968 | `b2801068c4eb5b415a6ddddb544ad510e1affbe0d9ceb2efc19923a198b6d173` | `TEMPORARY_NOT_RETAINED` | `LEGAL_EFFECT` 화성 누락·용인/광주 제외 범위 정정 교차검증 |

### 5.2 불변 보존한 전자관보 원문

투기지역 지정·해제의 법적 원문 4건은 2026-07-17에 전자관보 뷰어에서 내려받아 저장소에
보존했다. 각 PDF는 1페이지이며 모든 페이지를 PNG로 렌더링해 공고번호·날짜·대상 범위를
육안 확인했다. 아래 해시는 현재 저장된 바이트의 재현 가능한 식별자이며, 권리 상태는
전자관보 저작권정책에 따라 출처·무결성 표시 조건의 `ALLOWED`다.

| 문서 | 보존 파일 | 바이트 | SHA-256 | 상태 |
|---|---|---:|---|---|
| 기획재정부공고 제2017-114호 | [`2017-114.pdf`](./research-data/captures/gazette/2017-114.pdf) | 377,374 | `sha256:2ff1852bee51dbffa93ad59f174c2dab05fbb2d8b8b35fe17a78ff2511230af9` | `IMMUTABLE_CAPTURED` |
| 기획재정부공고 제2018-151호 | [`2018-151.pdf`](./research-data/captures/gazette/2018-151.pdf) | 641,483 | `sha256:3643c6ae0cbb7fa85441964786c1be020240dcbf25e97a26cc627f6d6af5d908` | `IMMUTABLE_CAPTURED` |
| 기획재정부공고 제2022-189호 | [`2022-189.pdf`](./research-data/captures/gazette/2022-189.pdf) | 58,756 | `sha256:e54ac0bfe1196f2efdc9002e54a67aaedb801d80341d701e8cc417386e330f84` | `IMMUTABLE_CAPTURED` |
| 기획재정부공고 제2023-1호 | [`2023-001.pdf`](./research-data/captures/gazette/2023-001.pdf) | 66,231 | `sha256:fb9934260e5eeea8a662601dab9c8e7ea69d07bcfdcc5ad8625f990b9c1fa475` | `IMMUTABLE_CAPTURED` |

원본 URL·캡처 날짜 정밀도·MIME·검증 메모는
[`research-data/captures/manifest.csv`](./research-data/captures/manifest.csv)를 단일 매니페스트로 쓴다.
초 단위 수집 시각과 응답 헤더는 당시 보존하지 않았으므로 `DATE_ONLY`, `NOT_RETAINED`로
기록하며 T002 완료 증거로 승격하지 않는다.

### 5.3 서울·경기 토지거래허가구역 원문 임시 검증

2026-07-17에 서울시와 경기도의 공식 PDF를 임시 다운로드해 모든 관련 페이지를 렌더링하고
공고번호·효력기간·범위·면적 기준·지정도를 대조했다. 문서별 권리 승인이 끝나지 않았으므로
원문과 렌더링 이미지는 저장소에 보존하지 않았다. 아래 해시는 조사 당시 받은 응답을 식별할
뿐 불변 캡처나 공급자 체크섬이 아니다.

| 문서 | 공식 부모·원문 | 바이트 | 관련 페이지 검수 | 임시 응답 SHA-256 | 보존 상태 |
|---|---|---:|---|---|---|
| 서울특별시 공고 제2025-2774호 | [서울시 지정 현황](https://land.seoul.go.kr/land/other/appointStatusSeoul.do) · [공식 PDF](https://land.seoul.go.kr/land/common/downloadFileNm.do?filePath=%2Fother%2F&fileName=appointStatus_25_18.pdf) | 1,587,323 | 15/15쪽 렌더·육안 확인 | `fd9eb2c5ba1560168cd6ae2ee24736101206fe6fbc4d1fafd251514ffe3c81c8` | `TEMPORARY_NOT_RETAINED` |
| 경기도 공고 제2026-1792호, 경기도보 제8034호 | [경기도보](https://www.gg.go.kr/gg-dobo) · [공식 PDF](https://www.gg.go.kr/uploads/BOARD/2026/06/20260630095414_NG21sBX5thRF.pdf) | 1,652,610 | 전체 96쪽 중 공고 40~42쪽 렌더·육안 확인 | `9145052676ae75f57d24b8c01e8da4b0a87899c989f630f535369edee1c539ac` | `TEMPORARY_NOT_RETAINED` |

서울 공고는 142.22㎢ 아파트 부지의 재지정과 정비사업 후보지 8곳 446,779.3㎡의 신규
지정을 서로 다른 효력 구간으로 분리했다. 경기도 공고는 용인 기흥구·화성 동탄구·구리시
170.50㎢와 도시지역·도시지역 외 면적 기준, 아파트 한정 조건을 확인했다. 경기도보 페이지의
공공누리 제3유형 표시는 확인했지만, 변경금지 조건 아래 원문 보존·전문 공개·RAG 색인을
각각 승인해야 하므로 두 문서 모두 현재 운영 상태는 `REVIEW_REQUIRED`다.

같은 날 공식 현황표를 누락 탐지용으로 대조했다. 서울시 현황표의 지정 묶음행 31개 중 현재
`designations.csv`에 대응하는 행은 제2025-2774호의 두 범위와 국토교통부공고
제2025-1219호 등 3개뿐이어서 최소 28개 묶음행이 남는다. 경기도의 2026-04-02 기준
현황표는 합계·소계를 제외한 지정 수단 25개 중 제2025-1219호 1개만 대응해 최소 24개가
남는다. 이 수치는 공식 현황표의 묶음행 기준 하한이며, 최근 10년 지정·연장·정정·해제의
전국 전수 수량으로 해석하지 않는다.

- 서울시 현황 HTML: 111,729바이트,
  임시 SHA-256 `3c34ea15f37a8b9e5d6017b639fa429a81a4d64ed8dec1e2d5f6d9c157e3f058`
- 경기부동산포털 2026-04-02 현황 HTML: 60,611바이트,
  임시 SHA-256 `4de78b4c57f3bba04a5509d9721f800091dbb4543a3a3fdca56fe738903b6ebd`
- 두 HTML 모두 `TEMPORARY_NOT_RETAINED`; 권리 승인·불변 캡처를 대체하지 않음

이 대조에서 2020-12-18 창원시 의창구는 조정대상지역이 아니라 별도 투기과열지구
공고 제2020-1649호의 범위이고, 같은 날 조정대상지역 공고 제2020-1650호의 창원 범위는
성산구임을 확인해 매니페스트를 정정했다.

또한 2016-11-03·2017-06-19 이력은 당시 주택공급 규칙상 청약 조정대상지역 선행 상태로
분리했다. 법률 제14866호 부칙 제2조와 공고 제2017-1305호에 따라 40개 예정지는 법 시행일인
2017-11-10에 주택법 제63조의2의 법정 조정대상지역으로 지정된 것으로 간주된다.

### 5.4 전국 정책 사건 역대조 보강

국토교통부의 `조정대상지역` 제목 공식 색인 23건을 현재 매니페스트와 역대조했다. 감사 전
없던 전매행위 제한기간 지정 공고 7건을 다음과 같이 추가했다.

| 효력일 | 문서번호 | 공식 상세 | 원문 상태 |
|---|---|---|---|
| 2017-11-10 | 국토교통부공고 제2017-1544호 | [공식 상세](https://www.molit.go.kr/USR/I0204/m_45/dtl.jsp?idx=15360) | HWP 미캡처 |
| 2018-08-28 | 국토교통부공고 제2018-1090호 | [공식 상세](https://www.molit.go.kr/USR/I0204/m_45/dtl.jsp?idx=15661) | `rhwp` 임시 추출, 불변 미보존 |
| 2018-12-31 | 국토교통부공고 제2018-1768호 | [공식 상세](https://www.molit.go.kr/USR/I0204/m_45/dtl.jsp?idx=15911) | HWP 미캡처 |
| 2020-02-21 | 국토교통부공고 제2020-198호 | [공식 상세](https://www.molit.go.kr/USR/I0204/m_45/dtl.jsp?idx=17016) | HWP 미캡처 |
| 2020-06-19 | 국토교통부공고 제2020-829호 | [공식 상세](https://www.molit.go.kr/USR/I0204/m_45/dtl.jsp?idx=17019) | HWP 미캡처 |
| 2020-11-20 | 국토교통부공고 제2020-1522호 | [공식 상세](https://www.molit.go.kr/USR/I0204/m_45/dtl.jsp?idx=17022) | HWP 미캡처 |
| 2020-12-18 | 국토교통부공고 제2020-1651호 | [공식 상세](https://www.molit.go.kr/USR/I0204/m_45/dtl.jsp?idx=17025) | HWP 미캡처 |

또한 2016-11-03과 2017-06-19를 일반적인 효력일로 보던 기존 행을 각각
[국토교통부령 제372호](https://www.law.go.kr/LSW/nwRvsLsInfoR.do?chrIdx=0&lsiSeq=187555&pageIndex=1&sortIdx=0)의
2016-11-15 공포·시행과
[국토교통부령 제432호](https://www.law.go.kr/nwRvsLsInfoR.do?chrIdx=0&lsiSeq=194694&pageIndex=1&sortIdx=0)의
2017-07-03 공포·시행으로 교정했다. 공포와 효력 사건은 별도 행으로 두고 관계 테이블로
연결했다. 이 좁은 공식 색인만으로도 감사 전 누락이 7/23이었고, 전자관보·국토교통부·
재정경제부·행정안전부·국세청의 기간 전체 역방향 열거가 끝나지 않았으므로 T001은 계속
미완료다.

## 6. 초기 사실 카드와 남은 증거

### `FACT.REGULATED_AREAS.2026-07-10`

- 주장: 2026-07-10 현재 조정대상지역·투기과열지구 현황
- 현황 교차검증: 국토부 실거래가 규제지역 안내
- 변경 발견: 2026-06-30 국토부 후속 조치
- 상태: `PARTIAL`
- 남은 증거: 각 지정 공고 번호·효력일·지역 범위·원문/첨부 해시와 공간 검수

### `FACT.LAND_PERMIT.NEW_AREAS.2026-07-05`

- 주장: 구리시·용인시 기흥구·화성시 동탄구 170.50㎢의 아파트 대상 신규
  토지거래허가구역이 2026-07-05부터 2027-12-31까지 적용됨
- 법적 근거: 경기도보 제8034호의 경기도 공고 제2026-1792호 40~42쪽
- 확인 완료: 공고번호·공고일·효력기간·대상·전체 용도지역 면적 기준·지정도
- 상태: `PARTIAL`
- 남은 증거: 불변 원문 보존 권리 승인, 행정구역 코드 정규화, 이용의무 세부기간

### `FACT.LAND_PERMIT.SEOUL.2025-2774`

- 주장 1: 강남구·서초구·송파구·용산구의 공고 대상 동 아파트 부지 142.22㎢를
  2025-10-01부터 2026-12-31까지 재지정
- 주장 2: 신속통합기획 주택재개발 후보지 7곳과 공공재개발 후보지 1곳,
  합계 446,779.3㎡를 2025-09-30부터 2026-08-30까지 신규 지정
- 법적 근거: 서울특별시 공고 제2025-2774호 본문과 붙임 1·2
- 확인 완료: 공고번호·공고일·두 효력기간·대상·면적 기준·15쪽 지정도
- 상태: `PARTIAL`
- 남은 증거: 불변 원문 보존 권리 승인, PNU·행정구역 코드 정규화

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
- 실제 원문 바이트 캡처: 전자관보 PDF 4건 완료, 나머지 출처 미완료
- 주소 운영 제공자: 미선정(T101 승인 필요)
- 전국 지자체 공고·필지·도면: 미완료
- T006 정책·세금·공간·권리 사람 승인: 미완료

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
  government_hwp_temporary_reextraction_count: 2
  immutable_capture_completed: false
  government_hwp_evidence:
    - document: molit_notice_2018_1086
      bytes: 12288
      sha256: fea461b2ce654ac9fde7aef15b487435af59cae86ea46e0bb13800846ea62e9a
      matched_previous_local_observation: true
      text_pages: 2
      markdown_pages: 2
      content_checks: [notice_2018_1086, gwangmyeong, hanam]
      retention: TEMPORARY_NOT_RETAINED
    - document: molit_notice_2018_1090
      bytes: 18944
      sha256: 7f3a3772fd0a634ca74a3a45c90ae34701d366aaeac5bec200c220ea40ed8c08
      text_pages: 2
      markdown_pages: 2
      content_checks: [notice_2018_1090, guri, anyang_dongan, gwanggyo, effective_on_announcement]
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
  - document: molit_notice_2018_1090
    bytes: 18944
    sha256: 7f3a3772fd0a634ca74a3a45c90ae34701d366aaeac5bec200c220ea40ed8c08
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
  - document: seoul_notice_2025_2774
    bytes: 1587323
    pages: 15
    rendered_pages_reviewed: 15
    sha256: fd9eb2c5ba1560168cd6ae2ee24736101206fe6fbc4d1fafd251514ffe3c81c8
    retention: TEMPORARY_NOT_RETAINED
    role: LEGAL_EFFECT_AND_BOUNDARY_CROSSCHECK_ONLY
  - document: gyeonggi_gazette_8034_notice_2026_1792
    bytes: 1652610
    pages: 96
    rendered_notice_pages_reviewed: [40, 41, 42]
    sha256: 9145052676ae75f57d24b8c01e8da4b0a87899c989f630f535369edee1c539ac
    retention: TEMPORARY_NOT_RETAINED
    role: LEGAL_EFFECT_AND_BOUNDARY_CROSSCHECK_ONLY
  - document: seoul_land_permit_status_index
    bytes: 111729
    grouped_rows: 31
    represented_grouped_rows: 3
    missing_grouped_rows_lower_bound: 28
    sha256: 3c34ea15f37a8b9e5d6017b639fa429a81a4d64ed8dec1e2d5f6d9c157e3f058
    retention: TEMPORARY_NOT_RETAINED
    role: STATUS_INDEX_COMPLETENESS_AUDIT_ONLY
  - document: gyeonggi_land_permit_status_2026_04_02
    bytes: 60611
    instrument_rows_excluding_totals: 25
    represented_instrument_rows: 1
    missing_instrument_rows_lower_bound: 24
    sha256: 4de78b4c57f3bba04a5509d9721f800091dbb4543a3a3fdca56fe738903b6ebd
    retention: TEMPORARY_NOT_RETAINED
    role: STATUS_INDEX_COMPLETENESS_AUDIT_ONLY
national_policy_audit:
  policy_event_rows: 105
  policy_event_relation_rows: 42
  molit_adjustment_title_index_rows: 23
  resale_restriction_notices_missing_before_audit: 7
  resale_restriction_notices_added: 7
  corrected_false_effective_dates:
    - {previous: 2016-11-03, corrected_promulgation_and_effective: 2016-11-15, instrument: MOLIT_ORDINANCE_372}
    - {previous: 2017-06-19, corrected_promulgation_and_effective: 2017-07-03, instrument: MOLIT_ORDINANCE_432}
  nationwide_reverse_enumeration_complete: false
  task_T001_complete: false
immutable_gazette_evidence:
  count: 4
  manifest: research-data/captures/manifest.csv
  manifest_sha256: 15ba1f67db608c318c8311de655d1986298bfd3720d6a4a8dee516858a649c95
  page_render_reviewed: true
  status: IMMUTABLE_CAPTURED
  capture_time_precision: DATE_ONLY
  response_headers_status: NOT_RETAINED
  documents: [mofe_2017_114, mofe_2018_151, mofe_2022_189, mofe_2023_1]
source_roles:
  decision_capable: [LEGAL_EFFECT, BOUNDARY]
  supporting_only: [EXPLANATION, STATUS_INDEX, DISCOVERY_ONLY]
  law_center_content: STATUS_INDEX_ONLY_NO_LEGAL_EFFECT
rights:
  robots_is_not_permission: true
  page_and_attachment_are_separate: true
  uncaptured_hash_value: null
  uncaptured_status: NOT_CAPTURED
  unknown_default: REVIEW_REQUIRED
  gazette_content: ALLOWED_WITH_SOURCE_AND_INTEGRITY
  observed_on: 2026-07-17
  observation_retention: TEMPORARY_NOT_RETAINED
  policy_hashes_persisted: false
  robots_observations:
    law_go_kr: {status: OBSERVED_ALLOWED, evidence_hash: null}
    open_law_go_kr: {status: OBSERVED_NOT_FOUND, evidence_hash: null}
    gwanbo_go_kr: {status: OBSERVED_NOT_FOUND, evidence_hash: null}
    molit_go_kr: {status: OBSERVED_REDIRECT_LOOP, evidence_hash: null}
    mofe_go_kr: {status: OBSERVED_PATH_RULES, evidence_hash: null}
    nts_go_kr: {status: OBSERVED_ALLOWED, evidence_hash: null}
    taxlaw_nts_go_kr: {status: OBSERVED_PATH_RULES, evidence_hash: null}
    mois_go_kr: {status: OBSERVED_ALLOWED, evidence_hash: null}
    seoul_go_kr: {status: OBSERVED_DEFAULT_DISALLOW_ALLOWLIST, evidence_hash: null}
    gg_go_kr: {status: OBSERVED_SOFT_BLOCK, evidence_hash: null}
    business_juso_go_kr: {status: OBSERVED_PATH_RULES, evidence_hash: null}
    vworld_kr: {status: OBSERVED_CRAWL_DELAY_30, evidence_hash: null}
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
  - remaining_immutable_byte_capture_and_sha256
  - nationwide_notice_and_boundary_collection
  - address_provider_approval_T101
  - policy_tax_spatial_rights_human_approval_T006
```
