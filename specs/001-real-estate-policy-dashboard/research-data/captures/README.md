# 전자관보 원문 캡처

이 디렉터리는 최근 10년 투기지역 이력을 검증하는 데 필요한 전자관보 원문 PDF와
SHA-256 매니페스트를 보존한다. 2026-07-17에 전자관보 공식 뷰어에서 내려받았으며,
각 PDF를 PNG로 렌더링해 공고번호·공고일·대상 지역·시행 문구가 읽히는지 육안 확인했다.

## 보존·이용 원칙

- 전자관보 저작권정책은 전자관보를 저작권법 제7조에 따른 자유이용 대상으로 안내한다.
- 원문은 수정하지 않고 [`manifest.csv`](./manifest.csv)의 바이트 수와 SHA-256으로 검증한다.
- 응답 헤더와 초 단위 수집 시각은 당시 보존하지 않았으므로 매니페스트에
  `captured_at_precision=DATE_ONLY`, `response_headers_status=NOT_RETAINED`로 명시한다.
- 화면·API에서 추출한 텍스트보다 보존 PDF와 관보 공고문을 우선한다.
- 이 네 건의 캡처는 투기지역 이력만 보강한다. 다른 정책·세금·공간 문서의
  `NOT_CAPTURED` 또는 `TEMPORARY_NOT_RETAINED` 상태를 해소하지 않는다.
- 게시·RAG 활성화에는 T006 정책·세금·공간·권리 담당자 승인과 출처 표시가 별도로 필요하다.

## 확인된 연결

| 관보 공고                   | 확인된 효력 범위                            |
| --------------------------- | ------------------------------------------- |
| 기획재정부공고 제2017-114호 | 서울 11개 구와 세종특별자치시 지정          |
| 기획재정부공고 제2018-151호 | 서울 종로·중·동대문·동작구 추가 지정        |
| 기획재정부공고 제2022-189호 | 세종특별자치시 해제                         |
| 기획재정부공고 제2023-1호   | 서울 11개 구 해제, 강남·서초·송파·용산 유지 |

---

## English AI Context

```yaml
capture_set: speculation_area_gazette_evidence
captured_on: 2026-07-17
source_key: gazette.speculation-area-captures
rights_status: ALLOWED
documents: 4
manifest: manifest.csv
manifest_sha256: 15ba1f67db608c318c8311de655d1986298bfd3720d6a4a8dee516858a649c95
capture_time_precision: DATE_ONLY
response_headers_status: NOT_RETAINED
integrity: SHA256_AND_BYTE_LENGTH
visual_validation: PDF_RENDERED_AND_VISUALLY_VERIFIED
scope_limit: SPECULATION_AREA_HISTORY_ONLY
human_gate: T006_PENDING
```
