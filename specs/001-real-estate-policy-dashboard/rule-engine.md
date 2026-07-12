# 규칙 엔진·날짜 의미론 설계

**결정 상태**: 채택  
**결정**: 제한된 선언형 DSL + Python 인터프리터 + 불변 게시 번들

## 선택 이유

| 선택지 | 평가 |
|---|---|
| Python 함수 레지스트리 | 빠르지만 비개발자 검수, 정규 해시, 변경 비교와 안전한 제한이 어렵다. |
| 제한된 선언형 DSL | 조건·효과·근거를 비교·검수·해시하고 동일 인터프리터로 재현하기 좋다. 채택한다. |
| OPA·Drools 등 범용 엔진 | 날짜·금액·3값 논리·근거 추적 확장이 커 MVP에 과하다. |

YAML은 작성 형식일 뿐이다. 게시할 때 JSON Schema를 검증하고 키 순서와 숫자 표현을
정규화한 JSON으로 컴파일한 뒤 SHA-256을 계산한다.

## 실행 의미론

### 3값 논리

조건 값은 `TRUE`, `FALSE`, `UNKNOWN` 중 하나다. 누락을 `FALSE`로 바꾸지 않는다.

| 연산 | 규칙 |
|---|---|
| `all` | 하나라도 FALSE면 FALSE, 모두 TRUE면 TRUE, 나머지는 UNKNOWN |
| `any` | 하나라도 TRUE면 TRUE, 모두 FALSE면 FALSE, 나머지는 UNKNOWN |
| `not` | TRUE↔FALSE, UNKNOWN은 UNKNOWN |

`UNKNOWN`이 결과에 영향을 주면 `NEEDS_INPUT` 또는 `REQUIRES_OFFICIAL_CHECK`를
반환한다. 지원 행렬 밖이면 `UNSUPPORTED`다.

### 날짜

- 법령·지정의 효력은 `Asia/Seoul`의 `[from, to)`로 처리한다.
- 날짜만 적힌 시행일은 해당일 `00:00:00+09:00`부터로 정규화한다.
- 발표일, 공포일, 시행일과 시스템 확인일을 같은 필드로 합치지 않는다.
- 취득일·양도일은 세법상 판정 규칙으로 파생하고 계약일·잔금일·등기일을 보존한다.
- 경과규정은 계약일뿐 아니라 계약금 지급 증빙, 잔금·등기, 허가 여부와 기간을
  독립 조건으로 평가한다.

### 숫자

- 원화는 정수 `Decimal`, 세율은 정수 basis point 또는 정밀 Decimal이다.
- 나눗셈, 누진공제, 세액공제, 부가세목, 반올림 순서를 계산 AST에 명시한다.
- 규칙마다 통화, 반올림 방식과 단위를 선언한다.

### 버전 고정 파생 사실 함수

컬렉션 필터·집계, 기간 계산과 누진세율표는 임의 수식 문자열로 표현하지 않는다.
대신 타입이 고정된 순수 함수 레지스트리를 사용한다.

- 초기 허용 함수: 세목별 주택 수, 세법상 사건일, 소유지분 합계, 보유·거주기간,
  구간표 조회, 누진세액 계산
- 각 함수는 ID, 입력·출력 스키마, 버전, 구현 해시와 속성 테스트를 가진다.
- 규칙은 허용 목록의 함수 ID와 버전만 참조하며 파일·네트워크·시계에 접근할 수 없다.
- RuleBundle은 사용된 함수 ID·버전·구현 해시를 포함한다.
- 함수 레지스트리 버전이 달라지면 같은 규칙 YAML이어도 새 번들을 만든다.

비교·집합·존재·기간·지역 연산자는 연산자별 JSON Schema를 갖는다. 예를 들어
`exists`는 값 인수를 받을 수 없고, `between`은 정확히 두 값, `in`은 비어 있지 않은
목록을 요구한다. 알 수 없는 연산자나 타입이 맞지 않는 인수는 컴파일 전에 거부한다.

### 충돌

- 숫자 우선순위로 덮어쓰지 않는다.
- `overrides`, `excludes`, `suppresses`, `supersedes`, `requires`를 명시한다.
- 동일한 대상·기간의 규칙이 겹치고 해결 관계가 없으면 컴파일을 실패시킨다.
- 의존 순환, 없는 규칙 참조와 서로 모순된 효과도 컴파일 오류다.

## DSL 예시

```yaml
rule_id: KR.CGT.MULTI_HOME.SURCHARGE
version: 2026-05-10.1
scope:
  stage: DISPOSAL
  tax_type: CAPITAL_GAINS
legal_validity:
  from: "2026-05-10"
  to: null
recording_validity:
  from: "2026-07-10T09:00:00+09:00"
  to: null
derived_fact_calls:
  - output: home_count.capital_gains
    function_id: count_capital_gains_homes
    function_version: 1.0.0
    args:
      - fact: household.property_ownership_history
      - fact: transaction.transfer_date
when:
  all:
    - fact: property.designations.adjustment_area
      at: transfer_date
      op: eq
      value: true
    - derived_fact: home_count.capital_gains
      at: transfer_date
      op: gte
      value: 2
then:
  emit:
    classification: SURCHARGED
unknown:
  outcome: NEEDS_INPUT
  required_facts:
    - holdings_at_transfer
    - property.region_at_transfer
citations:
  - source_document_id: official-document-id
    selector:
      type: article
      value: "검수 시 정확한 조문 입력"
```

예시의 조문과 세율은 자리표시자이므로 게시 번들에 넣을 수 없다. 근거 문서 ID와
검수된 정확한 selector가 채워지고 테스트가 통과해야 한다.

## 경과규정

경과규정은 규칙의 `valid_from`을 비틀지 않고 별도 일급 객체로 둔다.

```yaml
transition_id: KR.CGT.SURCHARGE.SUSPENSION.EXIT.2026
affects_rule: KR.CGT.MULTI_HOME.SURCHARGE
when:
  all:
    - fact: contract_date
      op: lte
      value: "2026-05-09"
    - fact: deposit_payment_proven
      op: eq
      value: true
    - derived_fact: transfer_within_transition_window
      op: eq
      value: true
effect:
  suppress_rule: KR.CGT.MULTI_HOME.SURCHARGE
unknown:
  outcome: NEEDS_INPUT
  required_facts: [deposit_payment_proven, transfer_date, regional_window]
```

위 예시는 구조 설명용이다. 실제 4·6개월 범위와 토지거래허가 조건은 국세청·법령
원문을 규칙 카드에서 검수한 값으로 대체한다.

## 입력 사실과 파생 사실

입력 사실은 사용자가 알 수 있는 사건과 자료다. 파생 사실은 규칙 엔진이 만든다.

- 입력: 계약·잔금·등기일, 주소, 면적, 가격, 보유 이력, 세대 관계, 거주기간, 증빙 여부
- 파생: 세법상 취득·양도시기, 세목별 주택 수, 당시 규제지역, 보유·거주 연수,
  일시적 2주택 기한, 과세표준, 공제 한도

파생 사실에는 값을 만든 규칙, 입력 사실, 기준일과 계산 추적 해시를 붙인다.

## 평가 흐름

```text
요청 검증
→ 주소·시점 정규화
→ 기준일에 게시된 RuleBundle 고정
→ 파생 사실 계산
→ 적용·예외·경과규정 3값 평가
→ 계산 AST 실행
→ 누락·공식 확인·미지원 상태 병합
→ 규칙 평가 트리와 근거 묶음 반환
```

외부 정부 API와 생성 모델은 이 요청 경로에서 호출하지 않는다. 주소 제공자 장애 시
캐시·수동 PNU 입력·공식 확인 상태로 끝낸다. 설명 모델 장애 시에도 규칙 결과는 반환한다.

## 게시 번들

번들은 다음을 포함한다.

- 정규화 규칙과 경과규정의 해시
- 포함 규칙 ID·버전·유효구간
- 공식 근거 조각과 원문 해시
- 컴파일러·인터프리터 버전
- 골든 사례 목록과 결과 해시
- 승인자·승인 시각·사유

한 요청은 시작부터 끝까지 하나의 번들만 사용한다. 분석 중 새 번들이 게시돼도
진행 중 결과는 바뀌지 않는다.

## 테스트 전략

구현보다 실패하는 테스트를 먼저 작성한다.

- 날짜: 전일·당일·익일
- 금액·세율·면적: 경계-1·경계·경계+1
- 공간: 내부·외부·경계·중첩·불완전 도면
- 3값: 각 필수 입력 누락과 UNKNOWN 전파
- 변형: 보유 목록 순서·무관 입력 추가에도 결과 동일
- 충돌: 겹침·순환·인용 누락 시 컴파일 실패
- 재현: 동일 입력·번들로 결과와 추적 해시 동일
- 안전: 문자열 실행·알 수 없는 연산자·과도한 AST 깊이 거부
- 게시: 골든 실패 또는 미검수 근거가 있으면 번들 생성 실패

## 성능·보안 제한

- 순수 규칙 평가는 p95 300ms 목표다.
- AST 최대 깊이, 노드 수와 계산량을 제한한다.
- DSL은 파일·네트워크·환경변수에 접근할 수 없다.
- 입력과 규칙 모두 스키마 검증 후 실행한다.
- 오류 로그에는 원시 주소, 금액, 보유 목록과 문서 본문을 남기지 않는다.

---

## AI Context (English)

```yaml
decision: restricted_declarative_dsl_with_python_interpreter
authoring_format: yaml
published_format: canonical_json
logic: three_valued
money: decimal_integer_krw
interval: half_open_asia_seoul
arbitrary_code_execution: forbidden
conflict_resolution: explicit_relations_only
transition_rules: first_class_objects
derived_fact_functions: typed_pure_versioned_and_bundle_hashed
request_bundle: immutable_and_pinned
test_order: failing_tests_before_implementation
```
