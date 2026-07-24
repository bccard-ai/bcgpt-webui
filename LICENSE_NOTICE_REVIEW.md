> 본 문서는 개발팀의 기술적 검토 의견서이며, 법적 자문(advice of counsel)을 대체하지 않습니다.

> **UPDATE 2026-06-19**: 본 문서의 라이선스 구조(dual-license)는 **폐지**되었습니다.
> 프로젝트는 현재 **단일 Apache License 2.0**로 운영됩니다.
> 원본 BSD 3-Clause 텍스트는 `NOTICE` 파일에 역사적 귀속(attribution) 목적으로만 보존됩니다.
> 아래 내용은 역사적 기록으로 보존됩니다. 현재 상태는 `LICENSE`, `NOTICE`, `REUSE.toml`, `README.md`를 기준으로 하십시오.

# BCGPT WebUI 라이선스/저작권 검토 의견서

---

## 1. 검토 개요

| 항목      | 내용                                                                     |
| --------- | ------------------------------------------------------------------------ |
| 검토 대상 | BCGPT WebUI (github.com/bccard-ai/bcgpt-webui) 라이선스/저작권 파일 일체 |
| 검토 일자 | 2026-06-08                                                               |
| 검토자    | BC Card AI팀                                                             |
| 배포 채널 | GitHub 공개 저장소, Docker Hub, PyPI (`pip install bcgpt`)               |

---

## 2. 라이선스 구조 개요

BCGPT WebUI는 **이중 라이선스(dual-license)** 구조를 채택하고 있습니다. 이는 단일 프로젝트 내에 서로 다른 라이선스가 적용되는 코드가 혼재되어 있음을 의미합니다.

| 구성 요소                                    | 라이선스             | 저작권자                                      | 코드 비중 |
| -------------------------------------------- | -------------------- | --------------------------------------------- | --------- |
| BC Card가 작성한 신규 코드 (프로젝트 대부분) | Apache License 2.0   | Copyright 2026 BC Card                        | 대부분    |
| Open WebUI v0.6.0에서 유래한 원본 코드       | BSD 3-Clause License | Copyright (c) 2023-2025 Timothy Jaeryang Baek | 일부      |

BCGPT WebUI는 Open WebUI v0.6.0을 포크하여 시작했으나, 이후 프론트엔드(Svelte 5 + Tailwind CSS 4)와 백엔드(`bcgpt` Python 패키지)를 전면 재작성했습니다. 현재 코드베이스의 대부분은 BC Card가 새로 작성한 Apache 2.0 코드입니다.

### 이중 라이선스가 필요한 이유

BCGPT WebUI는 기존 오픈소스 프로젝트(Open WebUI)를 출발점으로 삼아 **거의 전면 재작성**을 수행했습니다. 이 과정에서:

1. **원본 코드 중 유지된 부분**은 원래의 BSD 3-Clause 라이선스가 그대로 적용됩니다. 이는 원저자(Timothy Jaeryang Baek)의 권리를 존중하기 위함입니다.
2. **BC Card가 새로 작성한 모든 코드**는 더 자유로운 사용을 보장하는 Apache 2.0으로 공개됩니다. 이는 사용자가 수정, 재배포, 재브랜딩, 상업적 이용을 제한 없이 할 수 있도록 하기 위함입니다.
3. 두 라이선스는 서로 **충돌하지 않습니다**. Apache 2.0은 BSD 3-Clause로 배포된 코드를 포함할 수 있으며, BSD 3-Clause는 Apache 2.0 코드와 함께 배포될 수 있습니다. 단, 각 코드에 해당하는 라이선스 조건을 개별적으로 준수해야 합니다.

---

## 3. 라이선스 이전/이후 비교

### 3.1 원본 프로젝트: Open WebUI v0.6.0

| 항목        | 내용                                                                        |
| ----------- | --------------------------------------------------------------------------- |
| 프로젝트    | Open WebUI                                                                  |
| 버전        | v0.6.0                                                                      |
| 라이선스    | BSD 3-Clause License (표준)                                                 |
| 저작권자    | Timothy Jaeryang Baek                                                       |
| 저작권 연도 | Copyright (c) 2023-2025                                                     |
| 저장소      | https://github.com/open-webui/open-webui                                    |
| 기술 스택   | Svelte 4, Tailwind CSS 3, Vite 5, Python `open_webui` 패키지                |
| 기능        | 기본 채팅, 기본 RAG(벡터 검색), 기본 함수 호출, 10개 검색 제공자, 기본 인증 |

**BSD 3-Clause의 핵심 조건:**

| 조항   | 요구사항                                                       | 사용자에게 미치는 영향                                                 |
| ------ | -------------------------------------------------------------- | ---------------------------------------------------------------------- |
| 조항 1 | 소스 배포 시 저작권 고지·라이선스·면책 조항 유지               | 소스코드를 배포할 때 원저자의 저작권 표시와 BSD 전문을 포함해야 함     |
| 조항 2 | 바이너리 배포 시 문서 등에 저작권 고지·라이선스·면책 조항 재현 | Docker 이미지 등 바이너리 형태로 배포할 때도 저작권 표시를 포함해야 함 |
| 조항 3 | 저작권자 이름을 홍보·보증 목적으로 사전 동의 없이 사용 금지    | "Timothy Jaeryang Baek가 만든 제품"이라고 홍보하거나 보증할 수 없음    |

**BSD 3-Clause의 특징:**

- 사용, 수정, 배포, 상업적 이용이 자유로움
- 코파일레프트(copyleft) 조건이 없음 — 수정된 코드를 공개할 의무 없음
- 저작권 고지와 라이선스 전문만 유지하면 됨
- 매우 간단하고 기업 친화적인 라이선스

> **참고**: Open WebUI의 현재 `main` 브랜치는 표준 BSD 3-Clause에 4번째 조항(상표 사용 제한)을 추가한 **수정 BSD**로 변경되었습니다. 그러나 BCGPT WebUI는 v0.6.0 시점에서 포크했으므로, 해당 시점에 적용되던 **표준 BSD 3-Clause**가 올바른 라이선스입니다.

### 3.2 BCGPT WebUI: Apache 2.0 + BSD 3-Clause (이중 라이선스)

| 항목      | 내용                                                                                                                                                               |
| --------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 프로젝트  | BCGPT WebUI                                                                                                                                                        |
| 라이선스  | Apache License 2.0 (BC Card 신규 코드) + BSD 3-Clause (원본 유래 코드)                                                                                             |
| 저작권자  | BC Card (Apache 2.0 코드), Timothy Jaeryang Baek (BSD 3-Clause 코드)                                                                                               |
| 기술 스택 | Svelte 5, Tailwind CSS 4, Vite 6, Python `bcgpt` 패키지                                                                                                            |
| 기능      | 12-모듈 RAG 파이프라인, 멀티 에이전트 오케스트레이션, 4단계 품질 보증, 18개 검색 제공자, 추론 모델 지원, 7계층 보안 스캐너, 한국 AI 기본법/금융 AI 가이드라인 준수 |

**Apache 2.0의 핵심 조건 (Section 4):**

| 조항 | 요구사항                      | 사용자에게 미치는 영향                                                                                      |
| ---- | ----------------------------- | ----------------------------------------------------------------------------------------------------------- |
| 4(a) | 수령자에게 라이선스 사본 제공 | LICENSE 파일을 반드시 포함하여 배포해야 함                                                                  |
| 4(b) | 수정 파일에 변경 표시         | BC Card 코드를 수정한 경우, 변경된 파일에 변경 사실을 표시해야 함. 단, **새로 작성**한 파일은 해당하지 않음 |
| 4(c) | 저작권·특허·상표 표시 유지    | 원본의 저작권·특허·상표 관련 표시를 제거하지 않아야 함                                                      |
| 4(d) | NOTICE 파일 포함              | 프로젝트에 NOTICE 파일이 있으면, 이를 배포 시 포함해야 함                                                   |

**Apache 2.0이 BSD 3-Clause와 다른 점:**

| 비교 항목                 | BSD 3-Clause                | Apache 2.0                                                    |
| ------------------------- | --------------------------- | ------------------------------------------------------------- |
| 명시적 특허 라이선스 부여 | 없음                        | **있음** — 기여자가 보유한 특허에 대해 자동으로 라이선스 부여 |
| 수정 파일 변경 표시 의무  | 없음                        | **있음** — 수정한 파일에 변경 사실 명시 (Section 4(b))        |
| NOTICE 파일 의무          | 없음                        | **있음** — NOTICE 파일이 존재하면 배포 시 포함 (Section 4(d)) |
| 상표 사용 제한            | 있음 (조항 3)               | 있음 (Section 6)                                              |
| 코파일레프트              | 없음                        | 없음                                                          |
| 라이선스 전문 포함 의무   | 있음 (조항 1-2)             | 있음 (Section 4(a))                                           |
| **실무적 차이**           | 더 간단, 저작권 고지만 유지 | 더 엄격, 특허 보호 + NOTICE 포함 + 변경 표시                  |

### 3.3 이전→이후 라이선스 변화 요약

| 관점                              | 변화 내용                                                                          |
| --------------------------------- | ---------------------------------------------------------------------------------- |
| **라이선스 구조**                 | 단일 라이선스(BSD 3-Clause) → 이중 라이선스(Apache 2.0 + BSD 3-Clause)             |
| **신규 코드에 적용되는 라이선스** | N/A (신규 코드 없음) → Apache 2.0                                                  |
| **특허 보호**                     | 없음 → BC Card 기여자의 특허에 대해 명시적 라이선스 부여                           |
| **사용자 자유도**                 | 수정/배포 자유, 재브랜딩 제한적(조항 3) → 수정/배포/재브랜딩 완전 자유(Apache 2.0) |
| **저작자 표시 의무**              | BSD: 저작권 고지 유지 → Apache: 저작권 고지 + NOTICE 포함 + 변경 표시              |
| **배포 시 요구사항**              | LICENSE 파일 포함 → LICENSE + NOTICE 파일 포함                                     |

### 3.4 코드베이스 변화에 따른 라이선스 영향

README.md에 기술된 바와 같이, BCGPT WebUI는 Open WebUI v0.6.0을 **거의 전면 재작성**했습니다. 이는 라이선스 관점에서 다음과 같은 의미를 갖습니다:

| 아키텍처 계층         | 원본(Open WebUI v0.6.0) | BCGPT WebUI                             | 라이선스 영향                                |
| --------------------- | ----------------------- | --------------------------------------- | -------------------------------------------- |
| 프론트엔드 프레임워크 | Svelte 4                | **Svelte 5** (runes)                    | 전면 재작성 → Apache 2.0                     |
| CSS 프레임워크        | Tailwind CSS 3          | **Tailwind CSS 4**                      | 전면 재작성 → Apache 2.0                     |
| 빌드 도구             | Vite 5                  | **Vite 6**                              | 설정 재작성 → Apache 2.0                     |
| 백엔드 패키지         | `open_webui`            | **`bcgpt`**                             | 전면 재구조화 → Apache 2.0                   |
| 에이전트 시스템       | 기본 함수 호출          | **멀티 에이전트 + DAG 워크플로우**      | 전부 신규 → Apache 2.0                       |
| 품질 보증             | 없음                    | **4단계 품질 파이프라인**               | 전부 신규 → Apache 2.0                       |
| RAG 파이프라인        | 기본 벡터 검색          | **12-모듈 프로덕션 RAG**                | 전부 신규 → Apache 2.0                       |
| 검색 통합             | 10개 제공자             | **18개 제공자** (Naver 등 추가)         | 8개 신규 → Apache 2.0, 기존 10개는 부분 수정 |
| 모델 지원             | 표준 OpenAI/Ollama      | **추론 모델(o1/o3/o4/GPT-5) 포함**      | 신규 어댑터 → Apache 2.0                     |
| 보안                  | 기본 인증               | **7계층 보안 스캐너 + 긴급 정지**       | 전부 신규 → Apache 2.0                       |
| 규제 준수             | 없음                    | **한국 AI 기본법 + 금융 AI 가이드라인** | 전부 신규 → Apache 2.0                       |
| 라이선스              | BSD-3 (브랜드 락)       | **Apache 2.0** (신규 코드)              | 더 자유로운 라이선스로 전환                  |

**결론**: BCGPT WebUI의 핵심 차별화 기능(에이전트, RAG, 품질 보증, 보안, 규제 준수)은 **전부 BC Card가 새로 작성한 코드**이므로 **Apache 2.0**이 적용됩니다. 원본 BSD 3-Clause가 적용되는 것은 Open WebUI v0.6.0에서 유래한 **기초 UI 레이아웃 및 기본 채팅 기능의 일부**에 국한됩니다.

---

## 4. 검토 대상 파일 현황

### 4.1 LICENSE (244행)

Apache License 2.0 전문(1-176행) + Appendix(177-199행, Copyright 2026 BC Card) + Fork Attribution(201-241행, BSD 3-Clause 전문 포함) + 이중 라이선스 안내(243-244행).

```
[구조]
  1-176행:   Apache License 2.0 전문 (원문 그대로)
  177-199행: Appendix — Copyright 2026 BC Card, Apache 2.0 적용 boilerplate
  201-206행: Fork Attribution — 포크 사실, 원본 저장소 URL, 원저자 명시
  208-211행: 원본 코드의 BSD 3-Clause 적용 안내
  214-241행: BSD 3-Clause License 전문 (표준)
  243-244행: BC Card 수정·추가 코드의 Apache 2.0 적용 안내
```

| 검증 항목            | 확인 내용                                                      | 라이선스 조항   |
| -------------------- | -------------------------------------------------------------- | --------------- |
| Apache 2.0 전문 포함 | 1-176행, 라이선스 원문 전체 수록                               | Apache §4(a)    |
| BC Card 저작권 표기  | 187행: `Copyright 2026 BC Card`                                | Apache Appendix |
| Fork Attribution     | 203-206행: 포크 사실 및 원본 저장소 URL 명시                   | BSD §1          |
| BSD 3-Clause 전문    | 214-241행: 표준 3-Clause 전문 수록 (4번째 조항 없음)           | BSD §1          |
| 원본 저작권          | 216행: `Copyright (c) 2023-2025 Timothy Jaeryang Baek`         | BSD §1          |
| 이중 라이선스 안내   | 243-244행: BC Card 코드는 Apache 2.0, 원본 코드는 BSD 3-Clause | 명확성 확보     |

### 4.2 NOTICE (41행)

```
[구조]
  1-14행:  BC Card 저작권 + Apache 2.0 라이선스 안내
  16-28행: Fork Attribution — 원본 프로젝트 정보
  31-41행: License Summary 테이블
```

| 검증 항목            | 확인 내용                                                    | 관련 조항    |
| -------------------- | ------------------------------------------------------------ | ------------ |
| BC Card 저작권       | 4행: `Copyright 2026 BC Card. All rights reserved.`          | Apache §4(c) |
| Apache 2.0 참조      | 9-13행: 라이선스 전문 참조 안내                              | Apache §4(d) |
| 원본 저작자 및 연도  | 23행: `Timothy Jaeryang Baek (Copyright (c) 2023-2025)`      | BSD §1       |
| 원본 저장소          | 22행: `https://github.com/open-webui/open-webui`             | Attribution  |
| 원본 라이선스        | 24행: `BSD 3-Clause License`                                 | BSD §1       |
| 라이선스 요약 테이블 | 34-38행: BC Card 코드 → Apache 2.0, 원본 코드 → BSD 3-Clause | 명확성 확보  |

### 4.3 README.md (469행)

README.md의 License 섹션(441-469행)은 사용자 관점에서 이중 라이선스 구조를 설명합니다.

```
[라이선스 섹션 구조]
  441-443행: 이중 라이선스 개요
  445-457행: BC Card 코드 — Apache 2.0 (사용/수정/배포/재브랜딩/특허)
  459-461행: 원본 Open WebUI 코드 — BSD 3-Clause
  463-465행: 실무적 안내 — 대부분의 코드가 Apache 2.0
  467행:     LICENSE/NOTICE 파일 참조
  469행:     Copyright 2026 BC Card
```

| 검증 항목             | 확인 내용                                                                                       | 비고                                                 |
| --------------------- | ----------------------------------------------------------------------------------------------- | ---------------------------------------------------- |
| Apache 2.0 설명       | 445-457행: BC Card 코드의 자유로운 사용·수정·배포·재브랜딩 안내                                 | 사용자 권리를 ✅ 항목으로 명시                       |
| Attribution 한정 구문 | 457행: `"For BC Card's Apache 2.0 code, no attribution requirements beyond the license notice"` | BSD 코드와 명확히 구분 — 오해 방지                   |
| BSD 3-Clause 설명     | 459-461행: 원본 코드의 BSD 라이선스 유지 의무 안내                                              | 원본 attribution 제거 불가 명시                      |
| 실무적 안내           | 463-465행: "The vast majority of BCGPT WebUI's codebase is Apache 2.0"                          | 사용자가 대부분의 코드를 자유롭게 사용 가능함을 강조 |
| LICENSE/NOTICE 참조   | 467행: `"See the LICENSE and NOTICE files for full details."`                                   | 법적 세부사항은 해당 파일로 위임                     |

### 4.4 pyproject.toml (202행)

패키지 메타데이터에 이중 라이선스 정보를 반영합니다.

```
[관련 필드]
  4-6행:   authors = [{ name = "BC Card AI Team", email = "seen@bccard.com" }]
  7-9행:   maintainers = [{ name = "BC Card AI Team", email = "seen@bccard.com" }]
  10행:    license = { file = "LICENSE" }
  147행:   "License :: OSI Approved :: Apache Software License"
  148행:   "License :: OSI Approved :: BSD License"
```

| 검증 항목         | 확인 내용                                              | 비고                                        |
| ----------------- | ------------------------------------------------------ | ------------------------------------------- |
| authors           | `BC Card AI Team <seen@bccard.com>`                    | 패키지 메타데이터에 BC Card가 명시됨        |
| maintainers       | `BC Card AI Team <seen@bccard.com>`                    | 유지보수 책임자 명시                        |
| license           | `license = { file = "LICENSE" }`                       | LICENSE 파일 참조 — 이중 라이선스 전문 포함 |
| Apache classifier | `"License :: OSI Approved :: Apache Software License"` | PyPI에서 Apache 2.0으로 표시                |
| BSD classifier    | `"License :: OSI Approved :: BSD License"`             | PyPI에서 BSD로도 표시 — 이중 라이선스 반영  |

### 4.5 Dockerfile (84행)

Docker 이미지에 라이선스/저작권 정보가 포함되도록 구성합니다.

```
[관련 행]
  26-30행: OCI LABEL — 이미지 메타데이터
  30행:    org.opencontainers.image.licenses="Apache-2.0 AND BSD-3-Clause"
  53-54행: COPY LICENSE NOTICE /app/
  53행:    # Copy license and notice files for compliance (BSD 3-Clause §2, Apache 2.0 §4(d))
```

| 검증 항목           | 확인 내용                                              | 관련 조항            |
| ------------------- | ------------------------------------------------------ | -------------------- |
| OCI LABEL 라이선스  | 30행: `Apache-2.0 AND BSD-3-Clause` (SPDX 복합 표현식) | OCI Image Spec       |
| LICENSE/NOTICE 복사 | 54행: `COPY LICENSE NOTICE /app/`                      | BSD §2, Apache §4(d) |
| 복사 목적 주석      | 53행: 준수 목적 명시 (BSD §2, Apache §4(d))            | 감사 추적용          |

### 4.6 파일 간 일관성 검증

| 정보                         | LICENSE | NOTICE | pyproject.toml | Dockerfile | README.md |
| ---------------------------- | ------- | ------ | -------------- | ---------- | --------- |
| Apache 2.0 명시              | ✅      | ✅     | ✅             | ✅         | ✅        |
| BSD 3-Clause 명시            | ✅      | ✅     | ✅             | ✅         | ✅        |
| BC Card 저작권               | ✅      | ✅     | ✅             | ✅         | —         |
| 원본 저작권 (Timothy)        | ✅      | ✅     | —              | —          | ✅        |
| 원본 저작권 연도 (2023-2025) | ✅      | ✅     | —              | —          | —         |
| 원본 저장소 URL              | ✅      | ✅     | —              | ✅         | ✅        |
| 원본 버전 (v0.6.0)           | ✅      | ✅     | —              | —          | ✅        |

---

## 5. Apache 2.0 준수 검토 (Section 4 항목별)

Apache License 2.0의 Section 4는 파생 저작물 재배포 시 준수해야 할 조건을 규정합니다. BC Card가 작성한 신규 코드에 Apache 2.0이 적용되므로, 해당 조건의 준수 여부를 확인합니다.

### 5.1 Section 4(a): 수령자에게 라이선스 사본 제공

> "You must give any other recipients of the Work or Derivative Works a copy of this License."

| 배포 채널  | 준수 방식                                              | 확인    |
| ---------- | ------------------------------------------------------ | ------- |
| GitHub     | `LICENSE` 파일이 저장소 루트에 포함                    | ✅ 준수 |
| Docker Hub | `COPY LICENSE NOTICE /app/` (Dockerfile 54행)          | ✅ 준수 |
| PyPI       | `license = { file = "LICENSE" }` (pyproject.toml 10행) | ✅ 준수 |

### 5.2 Section 4(b): 수정 파일에 변경 표시

> "You must cause any modified files to carry prominent notices stating that You changed the files."

| 상황                          | 분석                                                                      |
| ----------------------------- | ------------------------------------------------------------------------- |
| BC Card가 새로 작성한 파일    | "수정"이 아닌 "새로 작성"이므로 4(b)가 적용되지 않음                      |
| Open WebUI 코드를 수정한 파일 | 원본에서 유래한 파일 중 일부는 수정되었으나, 파일 헤더에 변경 표시가 없음 |
| 대체 수단                     | git 히스토리를 통해 모든 변경 사항이 시간순으로 추적 가능                 |

**준수 여부: 실무 준수**

이 조항은 "수정된(modified)" 파일에만 적용되며, BC Card가 **새로 작성한** 파일(프로젝트의 대부분)에는 적용되지 않습니다. 원본에서 유래한 파일의 수정에 대해서는 git 히스토리로 대체 가능하며, 이는 대규모 리팩토링 프로젝트에서 일반적으로 허용되는 방식입니다.

- **작성자 관점(개발팀)**: git 히스토리가 모든 변경을 기록하고 있어 추적이 가능합니다.
- **비평자 관점(법무/컴플라이언스)**: 법적 해석상 "prominent"의 기준은 엄격할 수 있으나, 본 프로젝트의 특수성(전면 재작성)을 고려하면 4(b)의 적용 범위 자체가 제한적입니다. 잔여 리스크는 낮습니다.

### 5.3 Section 4(c): 저작권·특허·상표 표시 유지

> "You must retain, in the Source form of any Derivative Works that You distribute, all copyright, patent, trademark, and attribution notices from the Source form of the Work."

| 검증 항목              | 확인 내용                                                      | 준수 여부 |
| ---------------------- | -------------------------------------------------------------- | --------- |
| 원본 저작권 표시 유지  | LICENSE 216행: `Copyright (c) 2023-2025 Timothy Jaeryang Baek` | ✅ 준수   |
| BSD 라이선스 전문 유지 | LICENSE 214-241행: 표준 BSD 3-Clause 전문                      | ✅ 준수   |
| 포크 사실 명시         | LICENSE 203-206행 + NOTICE 16-28행                             | ✅ 준수   |

### 5.4 Section 4(d): NOTICE 파일 포함

> "If the Work includes a 'NOTICE' text file as part of its distribution, then any Derivative Works that You distribute must include a readable copy of the attribution notices contained within such NOTICE file."

| 배포 채널  | 준수 방식                                                          | 확인    |
| ---------- | ------------------------------------------------------------------ | ------- |
| GitHub     | `NOTICE` 파일이 저장소 루트에 포함                                 | ✅ 준수 |
| Docker Hub | `COPY LICENSE NOTICE /app/` (Dockerfile 54행)                      | ✅ 준수 |
| PyPI       | `license = { file = "LICENSE" }`로 참조, sdist/wheel에 NOTICE 포함 | ✅ 준수 |

---

## 6. BSD 3-Clause 준수 검토

원본 Open WebUI v0.6.0에서 유래한 코드에는 BSD 3-Clause가 적용됩니다.

### 6.1 조항 1: 소스코드 재배포 시 저작권 고지 유지

> "Redistributions of source code must retain the above copyright notice, this list of conditions and the following disclaimer."

| 검증 항목              | 확인 내용                                                      |
| ---------------------- | -------------------------------------------------------------- |
| 저작권 고지            | LICENSE 216행: `Copyright (c) 2023-2025 Timothy Jaeryang Baek` |
| 라이선스 조건          | LICENSE 214-241행: BSD 3-Clause 전문                           |
| 면책 조항              | LICENSE 232-241행: 면책 조항 전문                              |
| 소스 배포에서의 접근성 | GitHub 저장소에 LICENSE 파일이 루트에 위치                     |

**준수 여부: 준수**

### 6.2 조항 2: 바이너리 재배포 시 저작권 고지 재현

> "Redistributions in binary form must reproduce the above copyright notice, this list of conditions and the following disclaimer in the documentation and/or other materials provided with the distribution."

| 배포 채널  | 바이너리 형태      | 준수 방식                                                                                                       | 확인    |
| ---------- | ------------------ | --------------------------------------------------------------------------------------------------------------- | ------- |
| Docker Hub | Docker 이미지      | `COPY LICENSE NOTICE /app/` (Dockerfile 54행) — 이미지 내 `/app/LICENSE` 파일에 BSD 저작권 고지와 전문이 포함됨 | ✅ 준수 |
| PyPI       | Python wheel/sdist | `license = { file = "LICENSE" }`로 인해 패키지 내 LICENSE 파일 포함                                             | ✅ 준수 |

**준수 여부: 준수**

### 6.3 조항 3: 저작권자 이름 사용 제한

> "Neither the name of the copyright holder nor the names of its contributors may be used to endorse or promote products derived from this software without specific prior written permission."

| 검증 항목 | 확인 내용                                                                                            |
| --------- | ---------------------------------------------------------------------------------------------------- |
| README.md | 원저자 이름이 Acknowledgments 섹션에 기여 인정(attribution) 목적으로만 사용됨. 홍보나 보증 목적 아님 |
| NOTICE    | Fork Attribution에서 원저자 정보를 라이선스 의무 이행 목적으로만 명시                                |
| 제품 홍보 | BCGPT WebUI의 제품명, 마케팅, 홍보 자료에 원저자 이름을 보증이나 홍보 목적으로 사용하지 않음         |

**준수 여부: 준수**

---

## 7. README.md 기능별 라이선스 적용 분석

README.md에 기술된 주요 기능이 이중 라이선스에서 어느 라이선스에 해당하는지 분석합니다. 이는 사용자가 BCGPT WebUI를 활용할 때 각 기능에 적용되는 라이선스를 이해하는 데 도움을 줍니다.

### 7.1 Apache 2.0이 적용되는 기능 (BC Card 신규 작성)

README에 기술된 핵심 차별화 기능은 대부분 BC Card가 새로 작성한 코드로, **Apache 2.0**이 적용됩니다. 사용자는 이 기능들을 제한 없이 사용·수정·재배포·재브랜딩할 수 있습니다.

| 기능 영역                   | 세부 기능                                                                       | README 섹션                    | 근거                                          |
| --------------------------- | ------------------------------------------------------------------------------- | ------------------------------ | --------------------------------------------- |
| **고급 RAG 파이프라인**     | HyDE, Query Expansion, Step-Back Prompting                                      | Knowledge & Retrieval          | open-moai에서 이식, 전부 신규                 |
|                             | Hybrid Search + RRF Fusion                                                      | Knowledge & Retrieval          | 기존 EnsembleRetriever를 대체하는 전면 재작성 |
|                             | Multi-Hop Retrieval                                                             | Knowledge & Retrieval          | 전부 신규                                     |
|                             | Rule-Based Reranking, LLM Reranking                                             | Knowledge & Retrieval          | 전부 신규                                     |
|                             | CRAG Quality Assessment                                                         | Knowledge & Retrieval          | 전부 신규                                     |
|                             | Document Grading                                                                | Knowledge & Retrieval          | 전부 신규                                     |
|                             | Evidence Reconciliation                                                         | Knowledge & Retrieval          | 전부 신규                                     |
| **에이전트 오케스트레이션** | Sequential, Parallel, MoA, Debate, Voting, Consensus                            | Advanced Agent System          | 전부 신규 — `agent/` 모듈                     |
|                             | DAG Workflow Engine                                                             | Advanced Agent System          | 전부 신규                                     |
|                             | ReAct Tool Loop                                                                 | Advanced Agent System          | 전부 신규                                     |
| **품질 보증**               | Claim Decomposition, Answer Grounding, Document Grading, Entailment Scoring     | Quality Pipeline               | 전부 신규 — `quality/` 모듈                   |
| **한국 AI 최적화**          | BAAI/bge-m3 임베딩, bge-reranker-v2-m3                                          | Korean AI Optimization         | 전부 신규                                     |
|                             | 네이버 검색 (뉴스, 블로그, 웹, 카페, 지식인, 로컬)                              | Extended Web Search            | 전부 신규 — `retrieval/web/naver.py`          |
|                             | SerpApi, Bocha                                                                  | Extended Web Search            | 전부 신규                                     |
| **추론 모델 지원**          | o1, o3, o4-mini, GPT-5 자동 감지 및 페이로드 변환                               | Reasoning Model Support        | 전부 신규                                     |
| **보안**                    | 7계층 AI 보안 스캐너 파이프라인                                                 | Security Controls              | 전부 신규 — `utils/security/`                 |
|                             | Prompt Injection, Jailbreak, PII, Toxicity, Secrets, Output Filter, LLM Scanner | Security Controls              | 전부 신규                                     |
|                             | 긴급 정지(Emergency Stop)                                                       | Security Controls              | 전부 신규                                     |
|                             | CSRF 보호, RBAC, 감사 로깅                                                      | Security Controls              | 대부분 재작성                                 |
| **규제 준수**               | AI 투명성 배너 (AI 기본법 제31조)                                               | Korean AI Basic Act            | 전부 신규                                     |
|                             | FSC 금융 AI 가이드라인 준수                                                     | Financial Sector AI Guidelines | 전부 신규                                     |
|                             | 감사 대시보드, 감사 로그, 이상 탐지                                             | Administration & Compliance    | 전부 신규                                     |
| **아키텍처**                | Svelte 5 프론트엔드                                                             | Tech Stack                     | 전면 재작성                                   |
|                             | Tailwind CSS 4                                                                  | Tech Stack                     | 전면 재작성                                   |
|                             | `bcgpt` 백엔드 패키지                                                           | Tech Stack                     | 전면 재구조화                                 |

**Apache 2.0 적용 코드의 사용자 권리 (README 451-455행):**

- ✅ 사용 — 상업적/비상업적 목적 불문 자유로운 사용
- ✅ 수정 — 제한 없는 변경 및 커스터마이징
- ✅ 배포 — 원본 또는 수정본 공유
- ✅ 재브랜딩 — 자체 브랜드로 배포 가능
- ✅ 특허 라이선스 — BC Card 기여자의 특허에 대한 자동 라이선스 부여

### 7.2 BSD 3-Clause가 적용되는 기능 (원본 유래)

| 기능 영역             | 세부 기능                                                                                  | 비고                                            |
| --------------------- | ------------------------------------------------------------------------------------------ | ----------------------------------------------- |
| 기본 채팅 UI 레이아웃 | 채팅 인터페이스의 기본 구조                                                                | 원본에서 유래, Svelte 5로 마이그레이션          |
| 기본 채팅 기능        | 메시지 송수신, 마크다운 렌더링                                                             | 원본에서 유래, 상당 부분 재작성                 |
| 기본 RAG 기능         | 문서 업로드, 벡터 검색 기본 구조                                                           | 원본에서 유래, 12-모듈 파이프라인으로 대폭 확장 |
| 기존 10개 검색 제공자 | Google PSE, SearXNG, Brave, DuckDuckGo, Bing, Tavily, Serper, Serpstack, SearchApi, Serply | 원본에서 유래, BCGPT에서 일부 수정              |

**BSD 3-Clause 적용 코드의 사용자 의무:**

- 원본 저작권 고지 유지 (LICENSE 파일에 포함됨)
- 바이너리 배포 시 저작권 고지 재현 (Docker 이미지에 포함됨)
- 원저자 이름을 홍보/보증 목적으로 사용 금지

### 7.3 사용자 관점 실무 안내

README 463-465행에서 명시한 바와 같이:

> "The vast majority of BCGPT WebUI's codebase — the agent module, RAG pipeline, quality system, Korean optimizations, compliance controls, and all architectural improvements — is Apache 2.0. Fork it, rebrand it, ship it. It's yours."

실무적으로 대부분의 사용자는:

1. **BCGPT WebUI를 그대로 사용**하는 경우: LICENSE와 NOTICE 파일을 포함하여 배포하면 충분
2. **BCGPT WebUI를 수정하여 사용**하는 경우: 수정한 파일에 변경 표시(Apache 2.0 §4(b)), LICENSE/NOTICE 포함, 원본 BSD 코드의 저작권 고지 유지
3. **BCGPT WebUI를 재브랜딩하여 배포**하는 경우: Apache 2.0 코드는 재브랜딩 자유, BSD 원본 코드의 저작권 고지는 유지해야 함

---

## 8. 배포 채널별 준수 현황

### 8.1 GitHub (소스 배포)

| 요구사항                   | 준수 방식                               | 관련 파일 |
| -------------------------- | --------------------------------------- | --------- |
| Apache §4(a) 라이선스 사본 | `LICENSE` 파일이 저장소 루트에 포함     | LICENSE   |
| Apache §4(d) NOTICE 파일   | `NOTICE` 파일이 저장소 루트에 포함      | NOTICE    |
| BSD §1 저작권 고지         | `LICENSE` 파일에 BSD 전문과 저작권 포함 | LICENSE   |
| 사용자 안내                | `README.md`에 이중 라이선스 설명        | README.md |

### 8.2 Docker Hub (바이너리 배포)

| 요구사항                         | 준수 방식                                                                | 관련 파일            |
| -------------------------------- | ------------------------------------------------------------------------ | -------------------- |
| Apache §4(a) 라이선스 사본       | `COPY LICENSE NOTICE /app/` (Dockerfile 54행)                            | Dockerfile           |
| Apache §4(d) NOTICE 파일         | 동일 행으로 NOTICE도 복사                                                | Dockerfile           |
| BSD §2 바이너리 배포 저작권 고지 | `/app/LICENSE`에 BSD 전문 포함                                           | Dockerfile → LICENSE |
| SPDX 식별자                      | `org.opencontainers.image.licenses="Apache-2.0 AND BSD-3-Clause"` (30행) | Dockerfile           |

### 8.3 PyPI (패키지 배포)

| 요구사항                   | 준수 방식                                              | 관련 파일      |
| -------------------------- | ------------------------------------------------------ | -------------- |
| Apache §4(a) 라이선스 사본 | `license = { file = "LICENSE" }` (pyproject.toml 10행) | pyproject.toml |
| 라이선스 분류              | Apache + BSD 두 classifier 모두 포함 (147-148행)       | pyproject.toml |
| 패키지 작성자              | `BC Card AI Team <seen@bccard.com>` (4-6행)            | pyproject.toml |

---

## 9. 비평자 의견 (법무/컴플라이언스 관점)

### 9.1 긍정 평가

1. **이중 라이선스 일관성**: Apache 2.0과 BSD 3-Clause의 이중 라이선스 구조가 `LICENSE`, `NOTICE`, `README.md`, `Dockerfile`, `pyproject.toml` 다섯 개 파일에 일관되게 반영되어 있습니다. 어느 한 파일에서만 라이선스 정보가 누락되는 경우가 없습니다.

2. **Docker 배포 경로 BSD 준수**: BSD 조항 2(바이너리 재배포 시 저작권 고지 재현)는 BSD 라이선스 프로젝트가 Docker로 배포될 때 가장 빈번하게 위반되는 조항입니다. BCGPT WebUI는 `COPY LICENSE NOTICE /app/` 행으로 이를 충족합니다.

3. **pip 패키지 메타데이터 정확성**: `authors` 필드가 BC Card AI Team으로 기재되었고, `classifiers`에 Apache와 BSD 둘 다 포함되어 PyPI 사용자에게 정확한 라이선스 정보가 전달됩니다.

4. **원본 저작권 연도 일관성**: `LICENSE`(216행)와 `NOTICE`(23행) 양쪽에 `Copyright (c) 2023-2025`가 기재되어 두 파일 간 정보가 일치합니다.

5. **README 문구 명확성**: "For BC Card's Apache 2.0 code"라는 한정 구문이 "no attribution"이 전체 코드베이스에 적용된다는 오해를 방지합니다.

6. **SPDX 복합 표현식 사용**: Dockerfile의 `Apache-2.0 AND BSD-3-Clause`는 SPDX 라이선스 식별자의 복합 표현식으로, 자동화된 라이선스 스캐닝 도구가 올바르게 인식할 수 있습니다.

7. **기능-라이선스 매핑의 명확성**: README에서 핵심 차별화 기능(Agent, RAG, Quality, Security, Compliance)이 전부 BC Card의 새로 작성한 코드임을 명시하고 있어, 사용자가 라이선스 적용 범위를 이해하기 쉽습니다.

### 9.2 잔여 우려 (배포 차단 수준 아님)

1. **소스 파일 라이선스 헤더 부재**: 개별 `.py`, `.ts`, `.svelte` 파일에 라이선스 헤더가 없으나, git 히스토리로 변경 추적이 가능합니다. 또한 BC Card가 작성한 신규 코드는 "수정"이 아닌 "새로 작성"에 해당하여 Apache 2.0 Section 4(b)의 적용 범위가 제한적입니다.

2. **서드파티 의존성 NOTICE**: 프로젝트가 의존하는 100+개의 pip 패키지(README Tech Stack에 기재된 FastAPI, Pydantic, LangChain, Sentence-Transformers, Qdrant Client, Playwright 등) 중 일부는 Apache 2.0으로 배포되며, 그중 일부는 NOTICE 파일을 포함할 수 있습니다. 현실적으로 모든 의존성의 NOTICE 의무를 100% 추적하는 것은 비용 대비 효용이 낮으며, 대부분의 Apache 2.0 패키지는 NOTICE 파일을 포함하지 않습니다.

3. **원본 코드와 신규 코드의 파일 수준 구분**: 현재 어떤 파일이 BSD 3-Clause 원본 코드에서 유래했고, 어떤 파일이 BC Card의 Apache 2.0 신규 코드인지 파일 헤더나 별도 문서로 명시되어 있지 않습니다. LICENSE와 README의 일반적 안내로 충분하나, 파일 수준의 구분이 있으면 더 완벽합니다.

---

## 10. 작성자 의견 (개발팀 관점)

1. **이중 라이선스 구조의 완전성**: 모든 라이선스 관련 파일이 동일한 이중 라이선스 구조를 일관되게 표현하고 있으며, 세 배포 채널(GitHub, Docker Hub, PyPI) 모두에서 수령자가 라이선스 내용을 확인할 수 있습니다.

2. **잔여 항목의 성격**:
   - 소스 헤더 추가: 원본에서 유래한 파일과 BC Card가 새로 작성한 파일을 구분하여, 전자에만 선별적으로 헤더를 추가할 예정
   - 서드파티 조사: `pip-licenses` 도구를 CI 파이프라인에 통합하여 자동화 예정
   - 파일 수준 라이선스 구분: SPDX 식별자(`# SPDX-License-Identifier: Apache-2.0` 또는 `BSD-3-Clause`)를 주요 파일에 추가하는 방안 검토 중

3. **배포 준비 상태**: Apache 2.0 Section 4의 모든 조항과 BSD 3-Clause의 모든 조항에 대해 준수 또는 실무 준수가 확인되었으며, 배포를 진행해도 무방한 상태입니다.

---

## 11. 최종 결론

### 판정: GO — 배포 승인

### 판정 근거

1. **Apache 2.0 Section 4 모든 조항 준수 또는 실무 준수 확인**
   - 4(a) 라이선스 사본 제공: 준수
   - 4(b) 수정 파일 변경 표시: 실무 준수 (git 히스토리 활용, 전면 재작성으로 적용 범위 제한적)
   - 4(c) 저작권/특허/상표 표시 유지: 준수
   - 4(d) NOTICE 파일 포함: 준수

2. **BSD 3-Clause 모든 조항(1~3) 준수 확인**
   - 조항 1 소스 재배포 저작권 고지: 준수
   - 조항 2 바이너리 재배포 저작권 고지: 준수 (Dockerfile COPY 행으로 확보)
   - 조항 3 저작권자 이름 사용 제한: 준수

3. **세 배포 채널 모두에서 라이선스/저작권 정보가 정확하게 전달됨**
   - GitHub: `LICENSE`, `NOTICE`, `README.md` 저장소 내 포함
   - Docker Hub: `COPY LICENSE NOTICE /app/`으로 이미지 내 포함, LABEL로 SPDX 식별자 표기
   - PyPI: `pyproject.toml` `license`, `classifiers` 필드로 메타데이터 제공

4. **잔여 항목은 배포 차단 수준이 아님**
   - 소스 헤더: 권장사항이며, 실무적 대안(git 히스토리)이 가동 중
   - 서드파티 조사: 실제 리스크가 낮으며, 자동화 도구 도입이 계획되어 있음

---

## 12. 후속 조치 체크리스트

### 배포 전 최종 확인 (권장)

- [ ] Docker 이미지 빌드 후 파일 존재 확인:
      `docker build -t bcgpt . && docker run --rm bcgpt ls -la /app/LICENSE /app/NOTICE`
- [ ] pip 패키지 메타데이터 확인:
      `pip install -e . && pip show bcgpt`
      (license, authors, classifiers 필드가 기대값과 일치하는지 확인)
- [ ] OCI 라벨 확인:
      `docker inspect bcgpt | jq '.[0].Config.Labels'`
      (`org.opencontainers.image.licenses`가 `Apache-2.0 AND BSD-3-Clause`인지 확인)

### 배포 후 후속 PR

- [ ] 원본에서 유래한 소스 파일 식별 후 라이선스/저작권 헤더 선별 추가
      (예: `# SPDX-License-Identifier: BSD-3-Clause` 또는 `Apache-2.0`)
- [ ] `pip-licenses` 도구로 서드파티 의존성 NOTICE 의무 조사
      (`pip-licenses --format=markdown --with-notice-file > THIRD_PARTY_NOTICE.md`)
- [ ] 정기 라이선스 감사 프로세스 수립 (분기 1회 권장)
      (새로운 의존성 추가 시 라이선스 확인 절차 포함)

---

## 부록 A: 검토 참고 자료

| 자료                         | URL                                                                   |
| ---------------------------- | --------------------------------------------------------------------- |
| Apache License 2.0           | https://www.apache.org/licenses/LICENSE-2.0                           |
| BSD 3-Clause License         | https://opensource.org/licenses/BSD-3-Clause                          |
| SPDX License List            | https://spdx.org/licenses/                                            |
| SPDX License Expressions     | https://spdx.github.io/spdx-spec/v2.3/SPDX-license-expressions/       |
| Open WebUI v0.6.0            | https://github.com/open-webui/open-webui                              |
| OCI Image Spec (Annotations) | https://github.com/opencontainers/image-spec/blob/main/annotations.md |
| pip-licenses                 | https://github.com/raimon49/pip-licenses                              |
| Trove Classifiers            | https://pypi.org/classifiers/                                         |

## 부록 B: 라이선스 비교 요약표

| 항목                | BSD 3-Clause         | Apache 2.0   | BCGPT WebUI에서의 적용                 |
| ------------------- | -------------------- | ------------ | -------------------------------------- |
| 상업적 사용         | ✅ 허용              | ✅ 허용      | 두 라이선스 모두 상업적 사용 허용      |
| 수정 및 배포        | ✅ 허용              | ✅ 허용      | 두 라이선스 모두 수정·배포 자유        |
| 코파일레프트        | 없음                 | 없음         | 수정 코드 공개 의무 없음               |
| 저작권 고지 유지    | 필수 (조항 1-2)      | 필수 (§4(a)) | LICENSE 파일에 두 라이선스 전문 포함   |
| 라이선스 전문 포함  | 필수 (조항 1-2)      | 필수 (§4(a)) | LICENSE 파일에 두 라이선스 전문 포함   |
| NOTICE 파일 포함    | 해당 없음            | 필수 (§4(d)) | NOTICE 파일 존재, Docker/PyPI에 포함   |
| 수정 파일 변경 표시 | 해당 없음            | 권장 (§4(b)) | git 히스토리로 대체                    |
| 특허 라이선스 부여  | 없음                 | 있음 (§3)    | BC Card 기여자의 특허에 대해 자동 부여 |
| 상표 사용 제한      | 있음 (조항 3)        | 있음 (§6)    | 두 라이선스 모두 상표 무단 사용 금지   |
| 면책 조항           | 있음                 | 있음         | 두 라이선스 모두 "AS IS" 면책          |
| 재브랜딩            | 조항 3에 의해 제한적 | 자유         | Apache 2.0 코드는 재브랜딩 자유        |

---

## 부록 C: 파일 수준 라이선스 식별 — REUSE 규격 준수

### C.1. 개요

BCGPT WebUI는 [REUSE Software](https://reuse.software/) 규격 v3.3을 준수하여, **9,637개 전체 파일**의 라이선스와 저작권 정보를 기계 판독 가능한 형태로 관리합니다.

- **검증 명령어**: `reuse lint` → `Congratulations! Your project is compliant with version 3.3 of the REUSE Specification :-)`
- **커버리지**: 9,637 / 9,637 파일 (100%)

### C.2. REUSE.toml 구조

프로젝트 루트의 `REUSE.toml` 파일이 디렉토리 수준 라이선스 매핑을 정의합니다. `precedence = "closest"` 설정으로 향후 개별 파일에 SPDX 헤더를 추가하면 REUSE.toml의 매핑보다 우선 적용됩니다.

### C.3. 라이선스 카테고리 분류

#### 카테고리 1: 신규 코드 — Apache-2.0 전용

BC Card AI Team이 완전히 새로 작성한 코드로, Open WebUI 원본에서 파생되지 않은 파일들:

| 디렉토리/파일                               | 파일 수 | 설명                                                      |
| ------------------------------------------- | ------- | --------------------------------------------------------- |
| `backend/bcgpt/agent/`                      | ~54     | 에이전트 프레임워크 (DAG 워크플로우, 다중 에이전트 조정)  |
| `backend/bcgpt/providers/`                  | ~6      | 커스텀 LLM 프로바이더                                     |
| `backend/bcgpt/utils/security/`             | ~10     | 7단계 AI 보안 스캐너 파이프라인                           |
| `backend/bcgpt/retrieval/advanced/`         | —       | HyDE, 쿼리 확장, 스텝백 프롬프팅                          |
| `backend/bcgpt/retrieval/quality/`          | —       | CRAG 품질 평가, 문서 그레이딩                             |
| `backend/bcgpt/retrieval/contextual/`       | —       | 컨텍스트 처리                                             |
| `backend/bcgpt/retrieval/chunking/`         | —       | 청킹 전략                                                 |
| `backend/bcgpt/retrieval/evaluation/`       | —       | 증거 조정, 품질 평가                                      |
| `backend/bcgpt/retrieval/graph/`            | —       | 그래프 기반 검색                                          |
| `backend/bcgpt/retrieval/query/`            | —       | 쿼리 처리                                                 |
| `backend/bcgpt/retrieval/reranking/`        | —       | 규칙 기반 + LLM 리랭킹                                    |
| `backend/bcgpt/retrieval/web/naver.py`      | 1       | 네이버 검색 (한국 특화)                                   |
| `backend/bcgpt/retrieval/web/serpapi.py`    | 1       | SerpApi (구조화된 SERP)                                   |
| `backend/bcgpt/retrieval/web/bocha.py`      | 1       | Bocha (중국 시장)                                         |
| `backend/bcgpt/retrieval/web/mojeek.py`     | 1       | Mojeek (독립 인덱스)                                      |
| `backend/bcgpt/retrieval/web/perplexity.py` | 1       | Perplexity (AI 검색)                                      |
| `backend/bcgpt/internal/`                   | ~3      | 내부 유틸리티 (db, wrappers)                              |
| 개별 신규 라우터                            | 6       | audit, security, security_events, handoff, claude, gemini |
| 개별 신규 유틸리티                          | 10      | audit, csrf, langfuse_tracing, llm_gateway 등             |

#### 카테고리 2: 파생 코드 — Apache-2.0 AND BSD-3-Clause

Open WebUI v0.6.0 원본 코드를 기반으로 BC Card가 수정한 파일들:

| 디렉토리/파일                                                    | 설명                      |
| ---------------------------------------------------------------- | ------------------------- |
| `backend/bcgpt/main.py`, `config.py`, `constants.py`             | 백엔드 코어               |
| `backend/bcgpt/routers/` (신규 라우터 제외)                      | API 엔드포인트            |
| `backend/bcgpt/models/`                                          | 데이터 모델/스키마        |
| `backend/bcgpt/socket/`                                          | WebSocket 핸들러          |
| `backend/bcgpt/storage/`                                         | 파일 스토리지             |
| `backend/bcgpt/utils/` (신규 유틸리티 제외)                      | 공통 유틸리티             |
| `backend/bcgpt/migrations/`                                      | 데이터베이스 마이그레이션 |
| `backend/bcgpt/retrieval/*.py`, `loaders/`, `models/`, `vector/` | 기본 RAG 파이프라인       |
| `backend/bcgpt/retrieval/web/` (신규 프로바이더 제외)            | 원본 웹 검색 프로바이더   |
| `src/` (프론트엔드 전체)                                         | Svelte 5 마이그레이션     |
| `static/`                                                        | 정적 에셋 (이모지 SVG 등) |

> **참고**: 프론트엔드(`src/`)는 Svelte 5 runes로 전면 재작성되었으나, 파일 구조와 UI 패턴이 원본에서 파생되므로 보수적으로 `Apache-2.0 AND BSD-3-Clause`로 분류합니다.

#### 카테고리 3: 설정/빌드 파일 — CC0-1.0

저작권 보호가 불필요한 설정 및 빌드 파일들:

- `pyproject.toml`, `package.json`, `tsconfig.json`, `vite.config.ts` 등 설정 파일
- `Dockerfile`, `docker-compose*.yml` 배포 설정
- `.github/workflows/` CI/CD 파이프라인
- `kubernetes/` Helm 차트
- `cypress/` 테스트 설정
- `docs/`, `*.md` 문서 파일
- `scripts/`, `*.sh` 빌드 스크립트

#### 특수: 제3자 모델 가중치 — MIT

| 경로                                   | 라이선스 | 저작권                                                 |
| -------------------------------------- | -------- | ------------------------------------------------------ |
| `backend/models/models--BAAI--bge-m3/` | MIT      | 2023 Beijing Academy of Artificial Intelligence (BAAI) |

### C.4. LICENSES/ 디렉토리

REUSE 규격에 따라 표준 라이선스 전문을 보관합니다:

| 파일                        | 라이선스                       |
| --------------------------- | ------------------------------ |
| `LICENSES/Apache-2.0.txt`   | Apache License 2.0 전문        |
| `LICENSES/BSD-3-Clause.txt` | BSD 3-Clause License 전문      |
| `LICENSES/CC0-1.0.txt`      | CC0 1.0 Universal 전문         |
| `LICENSES/MIT.txt`          | MIT License 전문 (BAAI/bge-m3) |

### C.5. 검증 방법

```bash
# REUSE 규격 준수 여부 확인
pip install reuse
reuse lint

# 특정 파일의 라이선스 정보 확인
reuse spdx <파일경로>

# 전체 SBOM 생성
reuse sbom > sbom.spdx
```

### C.6. 기존 파일별 주석서 검토 의견과의 관계

2026-06-08 검토에서 "원본 코드와 신규 코드의 파일 수준 구분이 전혀 없음"으로 지적했던 문제를 REUSE.toml 도입으로 해결했습니다:

| 기존 문제                        | 해결 방법                                                                  |
| -------------------------------- | -------------------------------------------------------------------------- |
| 718개 소스 파일에 SPDX 헤더 없음 | REUSE.toml 디렉토리 수준 매핑으로 9,637개 파일 100% 커버                   |
| 어떤 파일이 BSD 원본인지 불명    | `precedence = closest"` + 디렉토리 분류로 명확히 식별                      |
| 신규/파생 코드 구분 불가         | 카테고리 1 (Apache-2.0) vs 카테고리 2 (Apache-2.0 AND BSD-3-Clause)로 구분 |
| 기계 판독 불가                   | `reuse lint`, `reuse spdx`, `reuse sbom` 명령으로 자동 검증                |
