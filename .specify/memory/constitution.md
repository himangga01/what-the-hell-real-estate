<!--
Sync Impact Report
- Version change: template -> 1.0.0
- Added principles: official-source evidence, temporal/geospatial correctness,
  deterministic rules, user safety/privacy, test-first auditability
- Added sections: product constraints, development and review workflow,
  AI-readable English context
- Templates reviewed: .specify/templates/spec-template.md,
  .specify/templates/plan-template.md, .specify/templates/tasks-template.md
- Template changes required: none; bilingual ordering is enforced in generated artifacts
- Deferred items: none
-->

# 대한민국 부동산 정책 분석 서비스 헌장

## 핵심 원칙

### I. 정부 원문과 추적 가능한 근거가 최우선이다

모든 정책, 규제지역, 세금 규칙과 사용자 판정은 법령, 고시, 공고,
정부 보도자료 또는 공공데이터 원문에 연결되어야 한다. 각 근거에는 발행기관,
문서명, 원문 URL, 발표일, 공포일, 시행일, 확인일과 원문 해시를 기록한다.
언론, 블로그, 경쟁 서비스는 탐색과 UX 참고에만 사용하며 판정 근거로 사용하지 않는다.

### II. 시점과 공간을 분리해 정확하게 판정한다

정책의 발표 여부와 실제 시행 여부를 분리하고, 모든 규칙과 지역 지정은
`valid_from`, `valid_to`, `published_at`, `checked_at`을 갖는다. 조정대상지역,
투기과열지구, 투기지역, 토지거래허가구역은 서로 다른 제도로 저장하고
주소, 법정동, 행정구역 또는 필지 폴리곤 중 원문이 지정한 최소 단위로 판정한다.
공간 경계가 불완전하면 추정하지 않고 확인 필요 상태를 반환한다.

### III. 규칙 엔진이 판정하고 RAG는 설명한다

세금, 비과세, 중과, 규제지역 적용 여부는 버전이 고정된 결정 규칙이 계산한다.
생성형 AI는 근거 검색, 쉬운 설명과 관련 조문 탐색에만 사용한다. AI 답변은
공개·검수 완료된 근거만 검색하며 모든 실질 주장에 인용을 포함한다. 근거가
부족하거나 규칙이 충돌하면 단정하지 않고 불확실성과 추가 확인 항목을 제시한다.

### IV. 사용자 안전과 개인정보 최소화는 기능보다 우선한다

MVP 결과는 법률·세무 신고를 대체하지 않는 참고용 판정과 개략 추정이다.
결과에는 적용 전제, 제외 조건, 기준일, 규칙 버전과 전문가 확인 필요 여부를
명확히 표시한다. 주민등록번호, 등기번호와 불필요한 식별정보는 수집하지 않는다.
사용자 입력은 기본적으로 브라우저 세션에서만 유지하고, 저장은 명시적 동의가
있을 때만 허용한다.

### V. 테스트 우선, 재현성, 감사 가능성은 타협하지 않는다

모든 규칙 변경은 실패하는 경계일·지역·세금 골든 테스트를 먼저 추가한 뒤
구현한다. 수집, 정규화, 검수, 게시, 분석 단계는 구조화 로그와 실행 식별자를
남긴다. 동일한 입력, 기준일, 규칙 버전은 동일한 결과와 근거 묶음을 반환해야 한다.
검수되지 않은 규칙은 운영 판정에 절대 사용하지 않는다.

## 제품 및 기술 제약

- 사용자 문서는 한국어를 먼저 제공하고, 같은 파일 아래에 AI가 해석하기 쉬운
  영문 구조를 둔다.
- 제품은 대한민국 부동산만 다루며, 최초 정책 이력 범위는
  2016-07-10부터 2026-07-10까지다.
- 현재 정책 화면은 기준일에 실제 유효한 항목만 보여주고, 예정·종료·폐기 정책은
  별도 이력 화면에서만 보여준다.
- Python API, React 웹 앱과 Tailwind CSS를 기본 기술 방향으로 유지한다.
- 출처 이용조건, robots.txt, 공공누리 유형과 API 호출 제한을 준수한다.
- 근거 변경이 탐지되면 기존 결과를 조용히 덮어쓰지 않고 새 규칙 버전을 만든다.

## 개발 및 검수 절차

1. 정부 원문을 수집하고 원본과 메타데이터를 변경 불가능한 형태로 보존한다.
2. 추출된 문장, 표, 지역 경계와 시행일을 정규화한다.
3. 규칙 초안과 원문 인용 범위를 생성하고 자동 검증을 실행한다.
4. 세금 또는 지역 판정에 영향을 주는 변경은 사람 검수 후 게시한다.
5. 테스트는 단위, 계약, 통합, 시점 경계, 공간 경계와 골든 사례를 포함한다.
6. 배포 전 현재 정책만 노출되는지, 모든 결과에 근거와 기준일이 있는지 확인한다.

## 거버넌스

이 헌장은 다른 프로젝트 지침보다 우선한다. 변경은 이유, 영향 받는 명세와
마이그레이션 계획을 문서화하고 검토받아야 한다. 원칙 삭제 또는 의미 변경은
주 버전, 새 원칙이나 필수 절차 추가는 부 버전, 표현 보정은 패치 버전을 올린다.
모든 명세, 계획, 작업 목록과 코드 리뷰는 헌장 준수를 확인해야 하며, 예외는
기간과 종료 조건이 있는 서면 기록 없이는 허용하지 않는다.

**버전**: 1.0.0 | **제정일**: 2026-07-10 | **최종 개정일**: 2026-07-10

---

## AI Context (English)

### Normative Principles

1. `SOURCE_FIRST`: Every policy, designation, tax rule, and analysis outcome
   MUST cite an official primary source with dates, URL, authority, and hash.
2. `BITEMPORAL_GEOSPATIAL`: Rules and designations MUST model publication,
   validity, observation time, and the smallest official geographic unit.
3. `RULES_DECIDE_RAG_EXPLAINS`: Deterministic, versioned rules produce legal
   and tax applicability. RAG only retrieves and explains published evidence.
4. `SAFETY_PRIVACY`: MVP outputs are advisory estimates. Collect no national
   identifier and retain scenario input only with explicit user consent.
5. `TEST_AUDIT`: Rule changes require failing boundary and golden tests first.
   Unreviewed rules MUST NOT enter production analysis.

### Governance Metadata

- Constitution version: `1.0.0`
- Ratified: `2026-07-10`
- Initial policy history window: `2016-07-10/2026-07-10`
- Canonical user language: Korean
- Required AI companion language: English, after the Korean section

