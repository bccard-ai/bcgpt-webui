<div align="center">

# BCGPT WebUI

**채팅, 검색·검색증강, 에이전트, 거버넌스를 위한 셀프 호스팅 AI 워크스페이스**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

[English](README.md) | 한국어

</div>

![BCGPT WebUI](demo.png)

## 개요

BCGPT WebUI는 대규모 언어 모델을 활용하기 위한 셀프 호스팅 웹 애플리케이션입니다. SvelteKit 프런트엔드와 FastAPI 백엔드로 구성되며, 로컬 Ollama 모델, OpenAI 호환 API, Gemini, Claude 연결을 지원합니다. 채팅, 지식 베이스와 검색증강, 웹 검색, 워크스페이스 자산, 에이전트 워크플로, 관리자 기능, 감사 화면, 선택적 거버넌스 기능을 제공합니다.

이 프로젝트는 Open WebUI v0.6.0에서 출발했으며, 현재는 `bcgpt` Python 패키지와 Svelte 5 애플리케이션으로 유지됩니다. 릴리스 이력은 [CHANGELOG.md](CHANGELOG.md), 업스트림 고지 사항은 [NOTICE](NOTICE)에서 확인할 수 있습니다.

> [!IMPORTANT]
> BCGPT WebUI는 소프트웨어이며, 컴플라이언스 인증이나 모델 정확성 보증이 아닙니다. 고급 검색증강, 에이전트, 보안, FinOps, 컴플라이언스 기능은 실제 사용하는 배포 환경에서 활성화·설정·검증·운영해야 합니다. 다수의 기능은 기본적으로 꺼져 있습니다.

## 목차

- [포함 기능](#포함-기능)
- [빠른 시작](#빠른-시작)
- [배포 방식](#배포-방식)
- [설정 및 운영](#설정-및-운영)
- [개발](#개발)
- [아키텍처](#아키텍처)
- [테스트 및 품질 검사](#테스트-및-품질-검사)
- [문서 및 지원](#문서-및-지원)

## 포함 기능

### 채팅과 워크스페이스

- 스트리밍 응답을 지원하는 다중 제공자 채팅, Markdown/LaTeX 렌더링, 대화 이력, 폴더, 태그, 공유 링크, 채널, 메모리, 프롬프트 템플릿, 파일 업로드, PWA 자산을 제공합니다.
- Ollama, OpenAI 호환 API, Gemini, Claude를 위한 서버 측 제공자 어댑터를 제공합니다. OpenAI 호환 엔드포인트는 호환 게이트웨이 및 모델 서버에 사용할 수 있습니다.
- 모델 정의, 지식 베이스, 프롬프트, 도구, 함수, 사용자, 그룹, 연결, 감사 데이터, 평가, RAG 관리를 위한 관리자·워크스페이스 화면을 제공합니다.
- 해당 제공자와 설정이 구성된 경우 이미지, 오디오, 작업, 파이프라인, 모델 관리 API 표면을 제공합니다.

### 지식, 검색증강, 웹 검색

- 파일 및 URL 수집, 지식 베이스 관리, 하이브리드 검색, 임베딩·리랭킹 모델 설정, Qdrant·Milvus·pgvector·OpenSearch·Elasticsearch 벡터 스토어 지원을 제공합니다.
- 선택적 검색증강 구성 요소로 HyDE, 쿼리 확장, step-back prompting, RRF(상호 순위 융합), 규칙 기반/LLM 리랭킹, CRAG, 문서 등급화, 근거 조정, 멀티홉 검색, 부모/자식 청킹, 컨텍스트 검색, 시맨틱 캐시, cross-encoder 리랭킹, GraphRAG, MMR, 수집 품질 점수화, 열 프로파일링을 제공합니다.
- Bing, Bocha, Brave, DuckDuckGo, Exa, Google Programmable Search, Jina, Kagi, Mojeek, Naver, Perplexity, SearchAPI, SearXNG, SerpApi, Serper, Serply, Serpstack, Tavily 웹 검색 어댑터를 포함합니다. 웹 검색을 사용하려면 제공자 자격 증명과 `ENABLE_RAG_WEB_SEARCH` 스위치가 필요합니다.

### 에이전트와 품질 제어

- 모델 자율성 수준 `suggest`, `assistant`, `operator`를 제공합니다. `operator` 수준은 반복 횟수가 제한된 ReAct 스타일 도구 루프를 사용합니다.
- 사용자 입력, RAG 검색, 웹 검색, 컨텍스트 병합, 조건, LLM 호출, API 호출, 텍스트 처리, PII 처리, 응답의 10가지 노드로 구성된 DAG 워크플로 엔진을 제공합니다. 각 노드는 중지·계속·재시도·대체 오류 전략을 지원합니다.
- 순차, 병렬, 토론, 합의, 투표, MoA(Mixture of Agents), council 다중 에이전트 패턴을 제공합니다.
- 주장 분해, 근거성, 문서 등급화, 함의 점수화, 인용 감사, 환각 탐지를 위한 선택적 응답 품질 단계를 제공합니다.

`MULTI_AGENT_ENABLED`와 `AGENT_QUALITY_PIPELINE_ENABLED`의 기본값은 `false`입니다. 워크플로 엔진은 기본 활성화되어 있지만 실제 동작은 구성한 모델, 도구, 검색증강, 웹 검색 서비스에 따라 달라집니다. 구현 세부 사항과 API 경로는 [backend/bcgpt/agent/README.md](backend/bcgpt/agent/README.md)에 설명되어 있습니다.

### ID, 보안, 거버넌스

- 인증, 사용자 역할, 그룹, API 키, OAuth/OIDC, LDAP, 신뢰 헤더 SSO, TOTP MFA, RS256/JWKS JWT 서명, SCIM 2.0 프로비저닝이 코드베이스에 포함되어 있습니다. 각 통합 기능은 설정에 따라 동작합니다.
- CSRF 보호, 기본 보안 헤더, 속도 제한, 감사 로그, 파일 시그니처 검사, 외부 요청 SSRF 방어, 설정 가능한 콘텐츠·모델 가드레일을 제공합니다.
- 선택적 제어로 토큰/비용 추적 및 예산, 채팅 보존/익명화, AI 상호작용 감사 기록, AI 투명성 안내, 비상 중지, SIEM 웹훅 전달, 모델 인벤토리·영향평가·승인 게이트·사고·공정성 시험·RAG 출처·정보주체 요청·벤더 기록을 위한 컴플라이언스 모듈이 있습니다.

기능이 존재한다고 해서 바로 활성화하지 마십시오. 설정, 데이터 보존 영향, 외부 의존성, 권한 모델을 먼저 검토해야 합니다. 특히 도구/함수 코드는 서버 프로세스 권한으로 실행됩니다. 기본적으로는 관리자만 작성할 수 있지만, 적절한 OS 또는 컨테이너 격리 없이 `TOOLS_ALLOW_NON_ADMIN_CODE=true`를 설정하면 안 됩니다.

## 빠른 시작

가장 빠른 로컬 배포 방식은 BCGPT WebUI와 Ollama를 함께 실행하는 것입니다. Docker Desktop(또는 Docker Engine)과 Compose v2 플러그인이 필요합니다.

```bash
git clone https://github.com/bccard-ai/bcgpt-webui.git
cd bcgpt-webui

# 이 값은 안정적으로 유지해야 합니다. 변경하면 기존 세션이 무효화됩니다.
export BCGPT_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"

docker compose up -d --build
curl --fail http://localhost:8090/healthz
```

<http://localhost:8090>을 열어 초기 온보딩을 완료하고 모델을 구성합니다. 함께 실행되는 Ollama 서비스는 모델을 자동으로 내려받지 않으므로, 모델을 명시적으로 가져온 뒤 UI에서 모델 목록을 새로고침해야 합니다.

```bash
docker exec -it ollama ollama pull <model-name>
```

명명된 Docker 볼륨 `bcgpt-data`와 `ollama-data`는 애플리케이션 데이터와 Ollama 모델을 유지합니다. 이 올인원 빠른 시작 프로필은 로컬 편의용이며, 표준 DB 배포 기준으로는 아래 PostgreSQL 프로필을 사용하십시오. 볼륨을 명시적으로 삭제하지 않는 한 컨테이너를 중지하거나 다시 만들어도 데이터는 삭제되지 않습니다.

## 배포 방식

### Docker Compose 파일

| 파일                                                                   | 용도                              | 서비스                          |
| ---------------------------------------------------------------------- | --------------------------------- | ------------------------------- |
| [docker-compose.yml](docker-compose.yml)                               | 로컬 올인원 배포                  | BCGPT WebUI, Ollama             |
| [docker-compose.without-ollama.yml](docker-compose.without-ollama.yml) | 외부 모델 제공자 또는 원격 Ollama | BCGPT WebUI                     |
| [docker-compose.with-db.yml](docker-compose.with-db.yml)               | PostgreSQL·Redis 배포의 시작점    | BCGPT WebUI, PostgreSQL, Redis  |
| [docker-compose.dev.yml](docker-compose.dev.yml)                       | Docker 기반 핫리로드 개발         | Vite 프런트엔드, FastAPI 백엔드 |

모든 Compose 파일은 로컬 [Dockerfile](Dockerfile)을 빌드합니다. 런타임은 `8090` 포트를 사용하며, 로컬 애플리케이션 데이터를 `/app/backend/data`에 저장하고 프로세스 liveness 검사용 `/healthz`를 노출합니다.

### 외부 제공자 또는 원격 Ollama

BCGPT WebUI가 자체 Ollama 컨테이너를 시작하지 않아야 한다면 standalone 프로필을 사용합니다.

```bash
export BCGPT_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export OPENAI_API_KEY="replace-with-your-key"

docker compose -f docker-compose.without-ollama.yml up -d --build
```

원격 Ollama 서버에는 BCGPT 컨테이너가 접근할 수 있는 주소를 지정합니다.

```bash
export BCGPT_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export OLLAMA_BASE_URL="https://ollama.example.internal"

docker compose -f docker-compose.without-ollama.yml up -d --build
```

`OPENAI_API_BASE_URL`은 OpenAI 호환 서비스 주소로 설정할 수 있습니다. 여러 OpenAI 호환 또는 Ollama 연결에는 [docs/CONFIG_REFERENCE.md](docs/CONFIG_REFERENCE.md)에 설명된 세미콜론 구분 `OPENAI_API_BASE_URLS`/`OPENAI_API_KEYS`, `OLLAMA_BASE_URLS` 설정을 사용합니다.

### PostgreSQL과 Redis

`with-db` 프로필은 유용한 시작점이지만 완전한 프로덕션 운영 절차는 아닙니다. 데이터베이스 비밀번호가 필요하며 안전한 세션 쿠키를 설정합니다.

```bash
export BCGPT_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export POSTGRES_PASSWORD="replace-with-a-long-unique-password"

docker compose -f docker-compose.with-db.yml up -d --build
curl --fail http://localhost:8090/readyz
```

프로덕션 사용 전에는 TLS 역방향 프록시 또는 로드 밸런서를 배치하고, 시크릿 관리자로 안정적인 시크릿을 주입하며, 네트워크 접근을 제한하고, 데이터베이스·업로드·벡터 데이터의 백업/복구 절차를 정하고, 비프로덕션 환경에서 업그레이드·롤백을 검증하십시오. 저장소 내 배포 검토의 알려진 경계는 [docs/DEPLOYMENT_RELEASE_SURFACE_INVENTORY_2026-06-23.md](docs/DEPLOYMENT_RELEASE_SURFACE_INVENTORY_2026-06-23.md)에 기록되어 있습니다.

### Kubernetes와 Helm

저장소에는 [kubernetes/helm](kubernetes/helm) 아래 Helm 차트가 포함되어 있습니다. 사용 전에 이미지, 시크릿, 스토리지, 프로브, 환경 설정을 검토하고 오버라이드하십시오.

```bash
helm upgrade --install bcgpt ./kubernetes/helm \
  --set secrets.BCGPT_SECRET_KEY="replace-with-a-stable-secret"
```

적용 전 차트를 렌더링합니다.

```bash
helm template bcgpt ./kubernetes/helm
```

차트 자체 [README](kubernetes/helm/README.md)는 별도로 호스팅되는 차트 위치도 가리킵니다. 로컬 차트는 소스 관리되는 배포 설정으로 취급하고, 실제 운영할 차트와 버전을 확인하십시오.

### 수동 이미지 실행

```bash
docker build -t bcgpt-webui .
docker volume create bcgpt-data

docker run -d --name bcgpt \
  -p 8090:8090 \
  -e BCGPT_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')" \
  -v bcgpt-data:/app/backend/data \
  bcgpt-webui
```

제공자 자격 증명은 `-e` 플래그 또는 가능하면 플랫폼의 시크릿 메커니즘으로 전달하십시오. [run-compose.sh](run-compose.sh)는 현재 저장소에 없는 Compose override 파일을 참조하므로 표준 배포 방법으로 사용하면 안 됩니다.

## 설정 및 운영

### 필수 설정

| 설정                                     | 목적                        | 운영 참고                                                                                                                      |
| ---------------------------------------- | --------------------------- | ------------------------------------------------------------------------------------------------------------------------------ |
| `BCGPT_SECRET_KEY`                       | 세션 및 JWT 서명            | 인증이 켜져 있으면 필수입니다. 길고 무작위이며 안정적인 시크릿을 사용하십시오.                                                 |
| `DATABASE_URL`                           | 기본 데이터베이스 URL       | PostgreSQL이 표준 배포 데이터베이스입니다. 이 값이 없을 때 코드에 남아 있는 `DATA_DIR`의 SQLite 폴백은 로컬/개발 호환용입니다. |
| `OLLAMA_BASE_URL`                        | Ollama 엔드포인트 하나      | 올인원 Compose 프로필은 자체 `ollama` 서비스로 설정합니다.                                                                     |
| `OPENAI_API_KEY` / `OPENAI_API_BASE_URL` | OpenAI 또는 호환 API        | 여러 연결에는 복수 URL/키 설정을 사용하십시오.                                                                                 |
| `CORS_ALLOW_ORIGIN`                      | 허용 브라우저 origin        | 프런트엔드와 백엔드 origin이 다르면 명시적으로 설정하십시오.                                                                   |
| `BCGPT_SESSION_COOKIE_SECURE`            | 안전한 쿠키 플래그          | HTTPS 뒤에서는 `true`로 설정합니다. 개발 런처는 localhost HTTP를 위해 이를 오버라이드합니다.                                   |
| `RAG_FILE_MAX_SIZE`                      | MB 단위 최대 업로드 크기    | 기본값은 `100`입니다.                                                                                                          |
| `VECTOR_DB`                              | 검색증강 벡터 스토어 백엔드 | 기본값은 `qdrant`입니다. 필요하면 서비스·자격 증명을 별도 구성하십시오.                                                        |

[.env.example](.env.example)는 의도적으로 제한된 주석형 예시입니다. 수명 주기, 기본값, 제공자 설정, 스토리지, 관측성, 기능 플래그를 포함한 전체 소스 기반 설정 카탈로그는 [docs/CONFIG_REFERENCE.md](docs/CONFIG_REFERENCE.md)를 참조하십시오.

많은 애플리케이션 값은 `PersistentConfig` 설정입니다. 환경 변수는 초기 저장 설정의 시드 역할을 하고, 이후 관리자 변경은 영속화됩니다. 환경 변수를 배포 입력으로 취급해야 하며, 그것만으로 현재 런타임 값이라고 판단하면 안 됩니다. 중요한 설정은 배포 후 관리자 UI 또는 해당 API에서 확인하십시오.

### 상태 확인 및 API 엔드포인트

| 엔드포인트   | 의미                                                                     |
| ------------ | ------------------------------------------------------------------------ |
| `/health`    | 기본 애플리케이션 응답                                                   |
| `/health/db` | 데이터베이스 쿼리를 포함한 기본 응답                                     |
| `/healthz`   | 프로세스 liveness                                                        |
| `/livez`     | 데이터베이스 검사 포함 liveness                                          |
| `/readyz`    | 데이터베이스와 구성된 벡터 스토어 검사 포함 readiness; Redis는 선택 사항 |

FastAPI 대화형 API 문서(`/docs`)와 OpenAPI 문서(`/openapi.json`)는 `ENV=dev`일 때만 활성화됩니다. 일반 프로덕션 설정에서는 노출되지 않습니다.

### 보안 점검 목록

- 일회성 로컬 실험이 아니라면 `BCGPT_AUTH=true`를 유지하고, 새 환경마다 고유한 `BCGPT_SECRET_KEY`를 생성하십시오.
- 역방향 프록시 또는 로드 밸런서에서 TLS를 종료하고, 보안 쿠키 플래그를 설정하며, 백엔드 포트·데이터베이스·Redis·제공자 서비스의 직접 접근을 제한하십시오.
- 신뢰 헤더 SSO 사용 시 실제 프록시 IP/CIDR을 `BCGPT_AUTH_TRUSTED_PROXY_IPS`에 설정하십시오. 제한되지 않은 네트워크 경로의 ID 헤더를 신뢰해서는 안 됩니다.
- API 키, SCIM 토큰, OAuth/LDAP 자격 증명, 객체 스토어 자격 증명은 `.env` 파일에 커밋하지 말고 시크릿 관리자에 보관하십시오.
- 사용자를 초대하기 전에 사용자 권한, 모델 접근 규칙, API 키 제한, 도구/함수 작성, 웹 검색 접근, 보존, 감사 로그, 외부 통합을 검토하십시오.
- 스테이징 환경에서 기능 플래그와 장애 상황을 시험하십시오. 일부 보안·스캐너·컴플라이언스·품질·관측성 제어는 opt-in이거나 배포 환경 의존성이 있습니다.

지원되는 보안 제보 채널과 프로젝트 정책은 [docs/SECURITY.md](docs/SECURITY.md)를 참조하십시오.

## 개발

### 로컬 개발

요구 사항은 Python 3.11+ 및 Bun 1.3+입니다.

먼저 Bun을 설치합니다. macOS 또는 Linux에서는 Bun 공식 설치기를 사용합니다.

```bash
curl -fsSL https://bun.com/install | bash
bun --version
```

Windows PowerShell에서는 `powershell -c "irm bun.sh/install.ps1|iex"`를 실행한 뒤 새 터미널을 열어 `bun --version`으로 확인합니다. 패키지 관리자와 플랫폼별 설치 방법은 [Bun 설치 안내](https://bun.com/docs/installation)를 참조하십시오.

Python 가상환경을 만들고 활성화한 뒤 백엔드 의존성을 설치합니다. 가상환경을 활성화하면 개발 스크립트가 사용하는 `python` 명령이 올바른 인터프리터를 가리킵니다.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
```

Windows PowerShell에서는 `py -3.11 -m venv .venv` 및 `.venv\Scripts\Activate.ps1`로 가상환경을 만들고 활성화한 뒤 동일한 `python -m pip` 명령을 실행합니다.

프런트엔드 의존성을 설치하고 두 서비스를 함께 실행합니다.

```bash
bun install
bun run dev
```

이 명령은 필요한 Pyodide 자산을 내려받고 Vite를 <http://localhost:5173>에서 시작하며 FastAPI 백엔드를 <http://localhost:8090>에서 시작합니다. 개발 런처도 필요 시 백엔드 의존성을 검사·설치하므로, 자동 설정을 선호한다면 위 Pip 설치 단계는 생략할 수 있습니다. 또한 `node_modules/.cache`에 안정적인 개발용 서명 키를 생성하고, 백엔드 reload를 활성화하며, Vite는 `/api`, `/ollama`, `/openai`, `/ws`를 백엔드로 프록시합니다.

개별 프로세스 또는 검사가 필요한 경우 다음 명령을 사용합니다.

```bash
# 프런트엔드만 실행
bun run dev:frontend

# 백엔드만 실행(bun run dev와 같은 의존성/키 도우미 사용)
bun run dev:backend

# 정적 빌드 및 로컬 미리보기
bun run build
bun run preview
```

Docker 핫리로드 프로필도 사용할 수 있습니다.

```bash
docker compose -f docker-compose.dev.yml up
```

### 프로젝트 구조

| 경로                  | 내용                                                                                    |
| --------------------- | --------------------------------------------------------------------------------------- |
| `src/`                | SvelteKit 애플리케이션, UI 컴포넌트, API 클라이언트, i18n, 스타일                       |
| `backend/bcgpt/`      | FastAPI 애플리케이션, 모델, 라우터, 제공자, 검색증강, 에이전트, 보안, 컴플라이언스 모듈 |
| `backend/bcgpt/test/` | 백엔드 단위 및 통합 테스트 모음                                                         |
| `kubernetes/helm/`    | Helm 차트 소스                                                                          |
| `scripts/`            | 개발, 설정 인벤토리, 라우트 인벤토리, 품질 도우미                                       |
| `docs/`               | 설정 참조, 운영 계획, 인벤토리, 정책                                                    |

## 아키텍처

프로덕션에서는 빌드된 애플리케이션을 FastAPI 프로세스가 제공합니다. 별도의 Node 서버가 아닙니다. 로컬 개발에서는 Vite가 프런트엔드 개발 서버로 동작하고 백엔드 트래픽을 FastAPI로 프록시합니다.

```text
브라우저 / PWA
   │
   ├─ 프로덕션: FastAPI가 빌드된 SvelteKit 애플리케이션 제공
   └─ 개발: Vite (:5173)가 API 및 WebSocket 트래픽 프록시
                         │
                         ▼
                 FastAPI / bcgpt (:8090)
                  ├─ 인증, 사용자, 채팅, 파일, 감사, 관리자 API
                  ├─ 제공자 어댑터: Ollama, OpenAI 호환, Gemini, Claude
                  ├─ 검색증강: 스토리지, 임베딩, 벡터 DB, 웹 검색
                  └─ 에이전트, 품질, 보안, 선택적 컴플라이언스 모듈
                         │
                         ▼
          PostgreSQL(표준) · 선택적 Redis · 벡터/객체 스토어
```

## 테스트 및 품질 검사

저장소 루트에서 다음 명령을 실행합니다.

```bash
# 프런트엔드 테스트, Svelte 진단, lint 검사
bun run test:frontend
bun run check
bun run lint:frontend:check

# 백엔드 단위 테스트
make test-backend-unit

# 기본 통합 테스트 대상
make test

# 소스 기반 인벤토리 및 회귀 검사
bun run check:routes
bun run check:ratchet
bun run check:fetch
make config-inventory
```

`make test-backend-integration`은 Docker/PostgreSQL 통합 테스트 환경이 필요합니다. `make test-backend-integration-collect`는 수집만 수행합니다. 문서나 프런트엔드 변경 전에는 `bun run format:check`를 사용하고, 설정된 파일 전체에 포맷 변경을 적용할 의도가 있을 때만 `bun run format`을 사용하십시오.

## 문서 및 지원

| 주제                             | 문서                                                                                                               |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| 전체 설정 카탈로그               | [docs/CONFIG_REFERENCE.md](docs/CONFIG_REFERENCE.md)                                                               |
| 에이전트 서브시스템과 엔드포인트 | [backend/bcgpt/agent/README.md](backend/bcgpt/agent/README.md)                                                     |
| 기여                             | [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)                                                                       |
| 보안 정책                        | [docs/SECURITY.md](docs/SECURITY.md)                                                                               |
| 릴리스/배포 검토                 | [docs/DEPLOYMENT_RELEASE_SURFACE_INVENTORY_2026-06-23.md](docs/DEPLOYMENT_RELEASE_SURFACE_INVENTORY_2026-06-23.md) |
| 변경 이력                        | [CHANGELOG.md](CHANGELOG.md)                                                                                       |

버그와 기능 제안은 [이슈 트래커](https://github.com/bccard-ai/bcgpt-webui/issues)를 통해 등록해 주십시오. Pull Request를 열기 전에는 [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)를 읽어 주십시오.

## 라이선스 및 고지

BCGPT WebUI는 [Apache License 2.0](LICENSE)으로 배포됩니다. [Open WebUI](https://github.com/open-webui/open-webui) v0.6.0에서 출발했으며, 필요한 업스트림 고지 사항은 [NOTICE](NOTICE)에 유지되어 있습니다.

---

[Read this README in English](README.md)
