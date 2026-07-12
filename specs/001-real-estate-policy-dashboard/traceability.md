# 요구사항 추적성 매트릭스

**기준 명세**: [spec.md](./spec.md)  
**목적**: 요구사항이 데이터 모델, API 계약, 실패 테스트와 구현 작업까지 이어지는지 확인한다.

## 기능 요구사항

| 요구사항 | 설계·계약 | 실패 테스트·구현 작업 | 완료 증거 |
|---|---|---|---|
| FR-001~003 현재 정책과 권위 원문 | `PolicyCard.decision_sources`, `DataSnapshot`, [source-register.md](./source-register.md) | T029, T031, T035, T039, T042 | 기준일 current-only 계약과 해시·selector가 있는 `LEGAL_EFFECT/BOUNDARY` 원문 |
| FR-004~006 4종 규제·공간 불확실성 | `DesignationSet`, `GeoFeatureVersion`, `DesignationScope` | T002, T030, T032~T033, T036~T040, T043~T044, T100~T101 | 유형별 고정 결과, 전일/당일, 내부/외부/경계/충돌 골든과 운영 주소 제공자 장애·비식별 계약 |
| FR-007~009 단계·입력·세목별 주택 수 | `AnalysisRequest`, `HouseholdFacts`, `OwnershipInterest`, 파생 사실 함수 | T045~T047, T053~T055, T061 | 세대원·소유기간·과거 처분 이력으로 세목별 주택 수 재현 |
| FR-010 취득 분석 | [tax-support-matrix.md](./tax-support-matrix.md), 취득 규칙팩 | T048, T056 | 취득·중과·일시적 2주택·생애최초 골든 |
| FR-011 보유 분석 | 연도별 공시가격·직전 과세표준·세부담 입력, 보유 규칙팩 | T049, T057 | 6월 1일·공시가격·상한·공제 골든 |
| FR-012 양도 분석 | 원시 사건일과 파생 세법상 사건일, 경과규정 | T050~T051, T055, T058 | 1세대 1주택·12억원·중과·2026 경과 골든 |
| FR-013 상속·증여 부분 지원 | `AnalysisStatus`, 지원 행렬 | T052, T060, T062 | 확정 세액 없이 원칙·필요 입력·공식 확인 경로 |
| FR-014~016 개략값·결정 규칙·AI 경계 | `CalculationLine`, `RuleEvaluation`, `RuleBundle` | T015~T016, T023~T026, T045 | Decimal·반올림·재현 해시, 모델 없이 동일 판정 |
| FR-017 근거 RAG | `QuestionResponse.claims`, `Citation`, 게시 근거 필터 | T064~T065, T068~T070, T072, T074 | `ANSWERED`의 모든 주장에 인용, 근거 부족 시 무답변 |
| FR-018~019 10년 이력 분리 | `PolicyEvent`, `/policies/history` cursor API | T001, T066, T071, T073 | 발표·시행·연장·정정·해제·종료 버전 이력 |
| FR-020~021 불변 수집·변경 | `SourceSnapshot`, `VerificationRun` | T002, T005, T020, T076, T079~T081, T103~T104 | 동일 URL 해시 변경 시 이전 스냅샷 보존과 모든 계획 출처의 공통 수집 계약 통과 |
| FR-022~023 규칙 상태·미검수 차단 | `RuleVersion`, `ReviewDecision`, 게시 번들 게이트 | T016, T022~T026, T077, T082~T084 | 미검수·충돌·골든 실패 시 409, 공개·RAG 제외 |
| FR-024 결과 추적 | `AnalysisResult`, 파생 사실·규칙 평가·인용 묶음 | T045, T059~T062 | 입력 요약, 적용·제외·억제, 누락, 기준일과 해시 |
| FR-025~026 식별자 금지·기본 무저장 | [privacy-log-policy.md](./privacy-log-policy.md), OpenAPI `x-privacy` | T017, T052~T053, T060, T091, T094 | 금지 필드 422, 로그·URL·브라우저 저장소·모델 요청 무잔존 |
| FR-027 신선도 | `DataSnapshot`, `VerificationRun`, 출처 SLA | T002, T080, T087, T089 | 마지막 확인 시각·오래됨·출처 장애 경고 |
| FR-028 골든 연결 | `GoldenCase`, RuleBundle 게시 조건 | T016, T026, T032~T033, T047~T051, T077 | 변경 규칙별 경계 테스트와 결과 해시 |
| FR-029 관리자 게시 권한 | JWT `roles`, 일반 검수 상세·결정, 게시 API | T075, T082~T086, T091 | 401/403 분리, 승인자·이유·대체 번들 감사 |
| FR-030 공식·전문가 확인 | `OfficialCheck`, 지원 행렬 | T030, T052, T059, T062~T063 | 이유 코드, 기관, 행동과 원문 경로 |
| FR-031 미지원 종료 | `UNSUPPORTED`, `REQUIRES_OFFICIAL_CHECK` | T052, T059~T063 | 지원 밖 fixture의 임의 계산 0건 |
| FR-032 계산 구성요소 | `CalculationLine`, `excluded_components` | T048~T051, T059, T062 | 본세·부가세목·공제·반올림·미포함 분리 |
| FR-033~034 RAG 판정 차단·주장별 인용 | `ANALYSIS_REQUIRED`, 조건부 `QuestionResponse` | T064~T065, T070, T072, T091 | 개인 판정 질문 무답변·분석 안내, 무인용 `ANSWERED` 거부 |

## UX 요구사항

| 요구사항 | 컴포넌트·작업 | 검증 |
|---|---|---|
| UX-001 기준일 | 공통 레이아웃 T041 | T034·T053·T067 E2E |
| UX-002 색상 외 상태 | 정책·주소·분석 결과 T041~T044, T062~T063 | T090 접근성 |
| UX-003 원문 메타데이터 | 정책 카드·근거 T041~T042, T074 | T029·T064 계약 |
| UX-004 필수/고급 입력 | 시나리오 위저드 T061 | T053 E2E |
| UX-005 영향 중심 오류 | 공통 오류 T027, 위저드 T061 | T045·T053 |
| UX-006 무저장 | 프런트·API T053, T060 | T017·T091·T094 |
| UX-007 모바일 결과 우선 | 주소·분석 T043, T062~T063 | T090 |
| UX-008 신선도 경고 | T041~T042, T085, T087~T089 | T031·T076 |
| UX-009 현재/이력 분리 | T042, T071, T073 | T031·T066~T067 |
| UX-010 관리자 상태 구분 | T085~T086 | T075·T077 |

## 성공 기준

| 성공 기준 | 주요 증거 |
|---|---|
| SC-001 정책 카드 근거 100% | T029 계약과 P1 매니페스트 T096 |
| SC-002 검증 주소·기준일 오류 0건 | T032~T033 골든 세트 |
| SC-003 3분 이내 주소 결과 | T034 자동 흐름과 T102 첫 방문 사용자 사용성 검증 |
| SC-004 분석 결과 근거·불확실성 100% | T045·T059 계약·통합 |
| SC-005 변경 후 24시간 내 검수 대기 | clock fixture T076과 수집 SLA T080 |
| SC-006 게시 규칙 골든 연결 100% | 게시 게이트 T077·T083 |
| SC-007 근거 없는 주장 0% | T064~T065·T070 |
| SC-008 무동의 시나리오 영구 저장 0건 | T017·T053·T060·T091·T094 |

## 운영·전달 계획 추적

| 계획 의무 | 작업 | 완료 증거 |
|---|---|---|
| 재현 가능한 설치와 저장소 비밀 보호 | T012, T098~T099 | `.gitignore` 금지 패턴과 잠금 파일 해시 기반 CI 설치 검사 |
| 운영 주소 정규화와 안전한 실패 | T100~T101 | 제공자 계약·비식별·장애 테스트와 `REQUIRES_OFFICIAL_CHECK` fallback |
| 전체 계획 출처 어댑터 | T079, T103~T104 | 7개 기관군의 조건부 요청·권리·차단 fixture 계약 통과 |
| RAG 성능과 관측 | T088~T089 | 근거 검색 p95 4초와 지연 메트릭·알림 증거 |
| health·readiness 계약 | T105 | API liveness, DB·게시 스냅샷 readiness와 정적 웹 probe 계약 통과 |
| 프로덕션 이미지·호스팅 계약과 승격 | T106~T108 | 비루트 smoke test, 승인된 환경 계약, staging 검증과 동일 digest 무재빌드 승격 |
| 롤백과 P1 릴리스 범위 | T109~T110, T097 | 롤백 훈련 증거와 P1 세부 게이트의 명령·결과·해시가 연결된 release checklist |

## 리뷰 게이트 해결 기록

| 리뷰 문제 | 반영 |
|---|---|
| 비권위·무해시 현재 정책 근거 허용 | `decision_sources`를 권위 역할·해시·selector·검수 완료로 제한 |
| RAG 무인용·개인 판정 허용 | 조건부 응답과 `ANALYSIS_REQUIRED` 추가 |
| 세대원과 소유 이력 연결 부재 | `OwnershipInterest`와 당시 세대 귀속·과거 보유 이력 추가 |
| 공간 system time 누락 | 경계·지정 범위에 recorded time·verification run 추가 |
| 사용자 입력 사건일과 파생 사건일 충돌 | `tax_event_date` 입력 제거, 원시 사건일에서 파생 |
| 관리자 bearer scope 오용 | JWT role claim과 401/403, 일반 검수 endpoint로 수정 |
| fixture 주소만 있어 실제 사용자 주소 처리 부재 | 운영 주소 제공자 계약·어댑터 T100~T101 추가 |
| SC-003을 자동 E2E만으로 측정 | 첫 방문 사용자 검증과 비식별 결과 기록 T102 추가 |
| 기획재정부·행정안전부·지자체 어댑터 누락 | 공통 계약과 추가 어댑터 T103~T104 추가 |
| health·readiness 구현 소유 작업 부재 | API·정적 웹 probe 계약과 구현 T105 추가 |
| 컨테이너 배포·승격·롤백 작업 부재 | 프로덕션 이미지·호스팅 계약·CD·롤백 T106~T109 추가 |
| P1 관련 품질 작업 범위 모호 | P1 릴리스 범위와 T097 검증 연결 T110 추가 |

---

## AI Context (English)

```yaml
functional_requirements: 34
ux_requirements: 10
implementation_tasks: 110
traceability_axes:
  - requirement_to_contract
  - requirement_to_data_model
  - requirement_to_failing_test
  - requirement_to_implementation_task
public_api_blockers_resolved_in_design:
  - authoritative_hashed_decision_sources
  - citation_conditioned_rag_response
  - household_member_ownership_timeline
  - bitemporal_geospatial_versions
  - derived_tax_event_date
  - explicit_jwt_role_contract
  - production_address_provider_with_safe_fallback
  - measurable_first_visit_usability_gate
  - complete_planned_source_adapter_coverage
  - reproducible_delivery_and_rollback
  - explicit_p1_release_scope
```
