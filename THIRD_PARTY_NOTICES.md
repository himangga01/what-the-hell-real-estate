# 제3자 소프트웨어 고지

## 현재 실행 구성

### `edwardkim/rhwp`

- 사용 버전: `v0.7.18`
- 저작권: Copyright (c) 2025-2026 Edward Kim
- 라이선스: MIT License
- 공식 저장소: <https://github.com/edwardkim/rhwp>
- 공식 릴리스: <https://github.com/edwardkim/rhwp/releases/tag/v0.7.18>
- 공식 라이선스: <https://github.com/edwardkim/rhwp/blob/v0.7.18/LICENSE>
- 사용 범위: 조사 단계의 HWP 텍스트·Markdown 임시 추출과 입력·도구·출력 SHA-256 기록

이 저장소는 `rhwp` 실행 파일을 재배포하지 않는다. 실행 시 공식 GitHub 릴리스의 고정
버전을 임시 다운로드하고 `SHA256SUMS.txt`로 archive를 검증한 뒤 삭제한다.

### PDF 조사 런타임

PDF 조사 도구는 제품 백엔드와 분리된 Python 3.12 환경에서 다음 패키지를 실행한다.
정확한 실행 버전은 `tools/pdf-ocr/uv.lock`과 런타임 사전검사로 고정한다.

| 구성요소 | 고정 버전 | 라이선스 | 공식 저장소 | 사용 범위 |
|---|---:|---|---|---|
| RapidOCR | `3.9.2` | Apache-2.0 | <https://github.com/RapidAI/RapidOCR> | 한국어 OCR, polygon·bbox·confidence 생성 |
| ONNX Runtime | `1.28.0` | MIT | <https://github.com/microsoft/onnxruntime> | `CPUExecutionProvider` 모델 추론 |
| Docling | `2.115.0` | MIT | <https://github.com/docling-project/docling> | 모든 페이지 PNG의 레이아웃 분석과 표 sidecar 실행 |
| docling-ibm-models | `3.13.3` | MIT | <https://github.com/docling-project/docling-ibm-models> | Docling 레이아웃·TableFormer 추론 코드 |

현재 PDF 처리 순서는 pypdf 내장 텍스트 우선, PyMuPDF 전체 페이지 300 DPI PNG 렌더링,
모든 PNG의 Docling 레이아웃 전용 패스, 스캔·저텍스트·복합 페이지의 RapidOCR·
ONNX Runtime CPU 인식, 표 페이지의 Docling 내부 RapidOCR와 TableFormer `accurate`
행·열·병합셀 복원이다. 런타임 자동 다운로드와 원격 추론은 금지한다.

### 고정 모델·데이터 artifact

다음 artifact는 `tools/pdf-ocr/models.lock.json`에 출처 URL, 바이트와 SHA-256을
파일별로 고정한다. 모델 파일은 로컬 모델 홈에만 준비하며 이 저장소에서 재배포하지 않는다.

| 역할·모델 | 확인된 라이선스 | 잠금 파일 SHA-256 |
|---|---|---|
| RapidOCR `ch_PP-OCRv5_det_mobile` | Apache-2.0 | `4d97c44a20d30a81aad087d6a396b08f786c4635742afc391f6621f5c6ae78ae` |
| RapidOCR `ch_ppocr_mobile_v2.0_cls_mobile` | Apache-2.0 | `e47acedf663230f8863ff1ab0e64dd2d82b838fceb5957146dab185a89d6215c` |
| RapidOCR `korean_PP-OCRv5_rec_mobile` | Apache-2.0 | `cd6e2ea50f6943ca7271eb8c56a877a5a90720b7047fe9c41a2e541a25773c9b` |
| RapidOCR `ppocrv5_korean_dict` | Apache-2.0 | `a88071c68c01707489baa79ebe0405b7beb5cca229f4fc94cc3ef992328802d7` |
| `Noto Sans KR` 글꼴·OFL 고지 | OFL-1.1 | 글꼴 `194018e6b2b293a7964f037b25c0249ce1418bc9ab3c971060a03aa57861e252`, 고지 `1c05c68c34f9708415aada51f17e1b0092d2cea709bf4a94cd38114f9e73d7d9` |
| Docling `docling-layout-heron` | Apache-2.0 | config `fdea30805ce2f5666b147fca941dcdd27ad468e27d6ed21902207d3da056a97d`, model `00333a43451945aaf89db8ca9c0a17e75d1537c17db60fdb91aa95f4c7929e0c`, preprocessor `cd38cd59999e7a95d68e487fbe5132df3d4e5c32a0836add57e6126ba0c4eaf1` |
| `TableFormer accurate` | CDLA-Permissive-2.0(모델 artifact), MIT(추론 코드) | model `2a7d6c924b3cd12fb99a09280ca9c33a89c5d60b93253617d2e088c1a40374d9`, config `984e122ceb8ccf84d84c9d2882f6f2302a44b4f1e577babd6289892c36f3cffd` |

각 원문 URL은 잠금 파일에 기록되어 있다. 잠금 전체는 7개 artifact, 11개 파일,
413,788,439바이트다.

### 중단된 과거 결정 이력

PaddleOCR `3.7.0`, PaddlePaddle `3.2.2`, PP-StructureV3 실행 구성은 Windows CPU
`phi.dll` 접근 위반 때문에 중단되고 RapidOCR·ONNX Runtime·Docling 구성으로 대체됐다.
PaddleOCR·PaddlePaddle 패키지는 현재 실행 의존성도 재배포 대상도 아니다. Paddle 계열에서
학습된 ONNX 모델의 계보 설명만 현재 기록에 남는다.

### 법률·권리 경계

HWP 또는 PDF 추출 성공은 정부 원문의 법적 효력, 이용권한, 세무 규칙 또는 공간 경계를
승인하지 않는다. 공고번호·날짜·면적·관할 등 핵심 필드는 사람이 원문과 대조해야 하며
미승인 파생물은 공개 fixture나 RAG에 넣지 않는다. 기본 보존 상태는
`TEMPORARY_NOT_RETAINED`다.

---

## English License Notice

### rhwp MIT License

MIT License

Copyright (c) 2025-2026 Edward Kim

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and
associated documentation files (the "Software"), to deal in the Software without restriction,
including without limitation the rights to use, copy, modify, merge, publish, distribute,
sublicense, and/or sell copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or
substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT
NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND
NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT
OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

### Current PDF runtime notices

RapidOCR 3.9.2 is used under Apache-2.0, ONNX Runtime 1.28.0 under MIT, Docling 2.115.0
under MIT, and docling-ibm-models 3.13.3 under MIT. Model artifact licenses remain
artifact-specific as recorded above and in `tools/pdf-ocr/models.lock.json`. No package or model
binary is committed or redistributed by this repository.

## English AI Context

```yaml
current_dependencies:
  rhwp:
    version: v0.7.18
    license: MIT
    source: https://github.com/edwardkim/rhwp
    binary_redistributed: false
  pdf_runtime:
    python: "3.12"
    packages:
      rapidocr:
        version: 3.9.2
        license: Apache-2.0
        source: https://github.com/RapidAI/RapidOCR
      onnxruntime:
        version: 1.28.0
        license: MIT
        source: https://github.com/microsoft/onnxruntime
      docling:
        version: 2.115.0
        license: MIT
        source: https://github.com/docling-project/docling
      docling_ibm_models:
        version: 3.13.3
        license: MIT
        source: https://github.com/docling-project/docling-ibm-models
    execution_provider: CPUExecutionProvider
    auto_download_at_runtime: forbidden
    package_or_model_redistributed: false
model_lock:
  file: tools/pdf-ocr/models.lock.json
  artifacts: 7
  files: 11
  bytes: 413788439
  artifact_licenses:
    rapidocr_models_and_dictionary: Apache-2.0
    noto_sans_kr: OFL-1.1
    docling_layout_heron: Apache-2.0
    tableformer_model_artifacts: CDLA-Permissive-2.0
    tableformer_inference_code: MIT
historical_superseded_runtime:
  packages: [PaddleOCR, PaddlePaddle]
  reason: WINDOWS_CPU_PHI_DLL_ACCESS_VIOLATION
  current_dependency: false
publication_boundary:
  human_review_required: true
  unapproved_derivatives_for_public_fixture_or_rag: forbidden
```
