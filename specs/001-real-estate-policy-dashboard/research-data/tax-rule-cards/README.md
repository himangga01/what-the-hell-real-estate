# 주택 세금 규칙 카드 조사본

**기준일**: 2026-07-10 23:59:59+09:00

**작성 확인일**: 2026-07-17

**공통 상태**: `PENDING_TAX_REVIEW`

**공개 가능**: 아니요

이 폴더는 구현용 세율·공제·비과세·중과·감면·경과규정을 법령 단위로 동결하기 위한
조사본이다. 세금 계산 결과를 일반 사용자에게 제공하는 승인본이 아니며, 세무 담당자의
조문·부칙·사례 검수 전에는 규칙 엔진이나 공개 화면에 탑재하지 않는다.

## 카드 목록

| 세목 | 카드 | 현재 범위 | 남은 핵심 검수 |
|---|---|---|---|
| 취득세 | [acquisition-tax.md](./acquisition-tax.md) | 유상취득 기본세율, 다주택·법인 중과, 생애최초, 일시적 2주택 | 주택 수 제외, 조합원입주권·분양권, 특례·추징 전수 |
| 재산세 | [property-tax.md](./property-tax.md) | 과세기준일, 주택 과세표준, 일반·1주택 특례 세율 | 과세표준상한 산식, 도시지역분·교육세, 지방 조례 |
| 종합부동산세 | [comprehensive-holding-tax.md](./comprehensive-holding-tax.md) | 기본공제, 공정시장가액비율, 세율, 세액공제 | 합산배제·공동명의·법인·농특세 세부 selector |
| 양도소득세 | [capital-gains-tax.md](./capital-gains-tax.md) | 1세대 1주택, 고가주택, 장특공, 다주택 중과·경과 | 주택 수 판정, 거주 예외, 장특공 표, 허가구역 경과 |

## 공통 사용 원칙

1. 거래일·취득일·과세기준일에 실제 시행 중인 법률·시행령·부칙 버전을 선택한다.
2. 보도자료와 국세청 안내는 설명·사례 근거다. 세율과 요건의 법적 효력은 국가법령정보센터
   법령 원문으로 재검증한다.
3. 조정대상지역·투기지역 등 공간 상태는 별도 지정 이력의 해당 날짜 결과를 입력으로 받는다.
4. 하나라도 주택 수, 세대, 용도, 가액, 보유·거주기간 또는 경과요건이 불명확하면 확정 세액을
   만들지 않고 `REQUIRES_TAX_REVIEW`로 종료한다.
5. 원 단위 절사·반올림, 지방교육세·지방소득세·농어촌특별세와 신고세액공제 등 부가 계산은
   검수된 규칙이 없는 한 본세와 분리해 표시한다.
6. 법령 링크가 있어도 원문 바이트 SHA-256과 사람 승인 전에는 `publication_ready: false`다.

## 남은 승인

- [ ] 세무 담당자가 네 카드의 시행 버전과 조문 selector를 확인했다.
- [ ] 경과규정과 계약금·잔금·등기·양도일 경계를 골든 사례로 확인했다.
- [ ] 지방세·국세 부가세목과 절사 규칙을 확인했다.
- [ ] 원문 캡처 해시와 권리 상태를 결합했다.
- [ ] T006 세금 담당 서명·일자가 기록됐다.

---

## English AI Context

```yaml
artifact_kind: tax_rule_card_index
cutoff_at: 2026-07-10T23:59:59+09:00
checked_on: 2026-07-17
review_status: PENDING_TAX_REVIEW
publication_ready: false
cards:
  - acquisition-tax.md
  - property-tax.md
  - comprehensive-holding-tax.md
  - capital-gains-tax.md
fail_closed_status: REQUIRES_TAX_REVIEW
required_human_gate: T006
```
