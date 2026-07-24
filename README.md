<div align="center">

# BCGPT WebUI

**A self-hosted AI workspace for chat, retrieval, agents, and governance**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

English | [한국어](README_KR.md)

</div>

![BCGPT WebUI](demo.png)

## Overview

BCGPT WebUI is a self-hosted web application for working with large language models. It combines a SvelteKit frontend with a FastAPI backend and supports local Ollama models, OpenAI-compatible APIs, Gemini, and Claude connections. The application includes chat, knowledge bases and retrieval, web search, workspace assets, agent workflows, administration, audit views, and optional governance features.

It began from Open WebUI v0.6.0 and is now maintained as the `bcgpt` Python package and a Svelte 5 application. See [CHANGELOG.md](CHANGELOG.md) for release history and [NOTICE](NOTICE) for upstream notices.

> [!IMPORTANT]
> BCGPT WebUI is software, not a compliance certification or a guarantee of model accuracy. Advanced retrieval, agent, security, FinOps, and compliance capabilities must be enabled, configured, tested, and operated for the deployment where they are used. Many are off by default.

## Contents

- [What is included](#what-is-included)
- [Quick start](#quick-start)
- [Deployment options](#deployment-options)
- [Configuration and operations](#configuration-and-operations)
- [Development](#development)
- [Architecture](#architecture)
- [Testing and quality checks](#testing-and-quality-checks)
- [Documentation and support](#documentation-and-support)

## What is included

### Chat and workspace

- Multi-provider chat with streaming responses, Markdown/LaTeX rendering, conversation history, folders, tags, shared links, channels, memories, prompt templates, file uploads, and PWA assets.
- Server-side providers for Ollama, OpenAI-compatible APIs, Gemini, and Claude. An OpenAI-compatible endpoint can be used for compatible gateways and model servers.
- Admin and workspace screens for model definitions, knowledge bases, prompts, tools, functions, users, groups, connections, audit data, evaluations, and RAG management.
- Image, audio, task, pipeline, and model-management API surfaces where their respective providers and settings are configured.

### Knowledge, retrieval, and web search

- File and URL ingestion, knowledge-base management, hybrid retrieval, configurable embedding and reranking models, and support for Qdrant, Milvus, pgvector, OpenSearch, and Elasticsearch vector stores.
- Optional retrieval components include HyDE, query expansion, step-back prompting, reciprocal-rank fusion, rule-based and LLM reranking, CRAG, document grading, evidence reconciliation, multi-hop retrieval, parent/child chunking, contextual retrieval, semantic caching, cross-encoder reranking, GraphRAG, MMR, ingestion quality scoring, and column profiling.
- Web-search adapters for Bing, Bocha, Brave, DuckDuckGo, Exa, Google Programmable Search, Jina, Kagi, Mojeek, Naver, Perplexity, SearchAPI, SearXNG, SerpApi, Serper, Serply, Serpstack, and Tavily. Provider credentials and the `ENABLE_RAG_WEB_SEARCH` switch are required before web search can be used.

### Agents and quality controls

- Three model autonomy levels: `suggest`, `assistant`, and `operator`. The operator level uses a bounded ReAct-style tool loop.
- A DAG workflow engine with ten node types: user input, RAG search, web search, context merge, conditional, LLM call, API call, text processor, PII processor, and response. Nodes support stop, continue, retry, and fallback error strategies.
- Multi-agent patterns: sequential, parallel, debate, consensus, voting, mixture of agents (MoA), and council.
- Optional answer-quality stages for claim decomposition, grounding, document grading, entailment scoring, citation auditing, and hallucination detection.

`MULTI_AGENT_ENABLED` and `AGENT_QUALITY_PIPELINE_ENABLED` default to `false`. The workflow engine is enabled by default, but its behavior still depends on the configured model, tools, retrieval, and web-search services. The implementation details and API routes are documented in [backend/bcgpt/agent/README.md](backend/bcgpt/agent/README.md).

### Identity, security, and governance

- Authentication, user roles, groups, API keys, OAuth/OIDC, LDAP, trusted-header SSO, TOTP MFA, RS256/JWKS JWT signing, and SCIM 2.0 provisioning are present in the codebase. Individual integrations are configuration-dependent.
- CSRF protection, baseline security headers, rate limiting, audit logging, file-signature validation, SSRF defenses for outbound fetching, and configurable content and model guardrails are available.
- Optional controls include token/cost tracking and budgets, chat retention/anonymization, AI-interaction audit records, AI transparency messaging, emergency stop, SIEM webhook forwarding, and a compliance module for model inventory, impact assessments, approval gates, incidents, fairness tests, RAG provenance, data-subject requests, and vendor records.

Do not enable a control merely because it exists. Review its settings, data-retention implications, external dependencies, and authorization model first. In particular, tool/function code executes with the server process's privileges; by default only administrators may author it. Do not set `TOOLS_ALLOW_NON_ADMIN_CODE=true` without appropriate operating-system or container isolation.

## Quick start

The quickest local deployment starts BCGPT WebUI and Ollama together. Docker Desktop (or Docker Engine) with the Compose v2 plugin is required.

```bash
git clone https://github.com/bccard-ai/bcgpt-webui.git
cd bcgpt-webui

# Keep this value stable. Changing it invalidates existing sessions.
export BCGPT_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"

docker compose up -d --build
curl --fail http://localhost:8090/healthz
```

Open <http://localhost:8090>, complete the initial onboarding flow, and configure a model. The bundled Ollama service does not automatically download a model; pull one explicitly, then refresh the model list in the UI:

```bash
docker exec -it ollama ollama pull <model-name>
```

The named Docker volumes `bcgpt-data` and `ollama-data` retain application data and Ollama models. This all-in-one quick start is a local convenience profile; use the PostgreSQL profile below as the standard database deployment baseline. Stopping or recreating the containers does not remove these volumes unless you explicitly remove them.

## Deployment options

### Docker Compose files

| File                                                                   | Intended use                                       | Services                       |
| ---------------------------------------------------------------------- | -------------------------------------------------- | ------------------------------ |
| [docker-compose.yml](docker-compose.yml)                               | Local all-in-one deployment                        | BCGPT WebUI, Ollama            |
| [docker-compose.without-ollama.yml](docker-compose.without-ollama.yml) | External model provider or remote Ollama           | BCGPT WebUI                    |
| [docker-compose.with-db.yml](docker-compose.with-db.yml)               | Starting point for PostgreSQL and Redis deployment | BCGPT WebUI, PostgreSQL, Redis |
| [docker-compose.dev.yml](docker-compose.dev.yml)                       | Docker-based hot-reload development                | Vite frontend, FastAPI backend |

All Compose files build the local [Dockerfile](Dockerfile). The runtime listens on port `8090`, stores local application data at `/app/backend/data`, and exposes `/healthz` for a process liveness check.

### External provider or remote Ollama

Use the standalone profile when BCGPT WebUI should not start its own Ollama container:

```bash
export BCGPT_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export OPENAI_API_KEY="replace-with-your-key"

docker compose -f docker-compose.without-ollama.yml up -d --build
```

For a remote Ollama server, provide an address reachable from the BCGPT container:

```bash
export BCGPT_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export OLLAMA_BASE_URL="https://ollama.example.internal"

docker compose -f docker-compose.without-ollama.yml up -d --build
```

`OPENAI_API_BASE_URL` can point to an OpenAI-compatible service. For multiple OpenAI-compatible or Ollama connections, use the semicolon-separated `OPENAI_API_BASE_URLS`/`OPENAI_API_KEYS` and `OLLAMA_BASE_URLS` settings documented in [docs/CONFIG_REFERENCE.md](docs/CONFIG_REFERENCE.md).

### PostgreSQL and Redis

The `with-db` profile is a useful starting point, not a complete production runbook. It requires a database password and configures secure session cookies:

```bash
export BCGPT_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export POSTGRES_PASSWORD="replace-with-a-long-unique-password"

docker compose -f docker-compose.with-db.yml up -d --build
curl --fail http://localhost:8090/readyz
```

Before production use, place the app behind TLS, set a stable secret through your secret manager, restrict network access, choose backup/restore procedures for database, uploads, and vector data, and validate an upgrade and rollback in a non-production environment. The in-repository deployment review records known boundaries in [docs/DEPLOYMENT_RELEASE_SURFACE_INVENTORY_2026-06-23.md](docs/DEPLOYMENT_RELEASE_SURFACE_INVENTORY_2026-06-23.md).

### Kubernetes and Helm

The repository includes a Helm chart under [kubernetes/helm](kubernetes/helm). Review and override its image, secrets, storage, probes, and environment settings before use:

```bash
helm upgrade --install bcgpt ./kubernetes/helm \
  --set secrets.BCGPT_SECRET_KEY="replace-with-a-stable-secret"
```

Render the chart before applying it:

```bash
helm template bcgpt ./kubernetes/helm
```

The chart's own [README](kubernetes/helm/README.md) also points to a separately hosted chart location. Treat the local chart as source-controlled deployment configuration and verify the chart/version you intend to operate.

### Manual image run

```bash
docker build -t bcgpt-webui .
docker volume create bcgpt-data

docker run -d --name bcgpt \
  -p 8090:8090 \
  -e BCGPT_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')" \
  -v bcgpt-data:/app/backend/data \
  bcgpt-webui
```

Pass provider credentials with `-e` flags or, preferably, your platform's secret mechanism. Do not use [run-compose.sh](run-compose.sh) as a canonical deployment method: it refers to Compose override files that are not currently present in this repository.

## Configuration and operations

### Essential settings

| Setting                                  | Purpose                        | Operational note                                                                                                                                                      |
| ---------------------------------------- | ------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `BCGPT_SECRET_KEY`                       | Signs sessions and JWTs        | Required when authentication is enabled; use a long, random, stable secret.                                                                                           |
| `DATABASE_URL`                           | Primary database URL           | PostgreSQL is the standard deployment database. The code retains a SQLite fallback in `DATA_DIR` only when this value is absent, for local/development compatibility. |
| `OLLAMA_BASE_URL`                        | One Ollama endpoint            | The all-in-one Compose profile sets this to its `ollama` service.                                                                                                     |
| `OPENAI_API_KEY` / `OPENAI_API_BASE_URL` | OpenAI or compatible API       | Use plural URL/key settings for multiple connections.                                                                                                                 |
| `CORS_ALLOW_ORIGIN`                      | Allowed browser origins        | Configure explicit origins when frontend and backend have different origins.                                                                                          |
| `BCGPT_SESSION_COOKIE_SECURE`            | Secure cookie flag             | Set to `true` behind HTTPS; the development launcher overrides it for localhost HTTP.                                                                                 |
| `RAG_FILE_MAX_SIZE`                      | Maximum upload size in MB      | Default is `100`.                                                                                                                                                     |
| `VECTOR_DB`                              | Retrieval vector-store backend | Default is `qdrant`; configure its service/credentials separately where needed.                                                                                       |

[.env.example](.env.example) contains a deliberately limited, commented sample. The full source-backed configuration catalog—including lifecycle, defaults, provider settings, storage, observability, and feature flags—is [docs/CONFIG_REFERENCE.md](docs/CONFIG_REFERENCE.md).

Many application values are `PersistentConfig` settings: environment values seed the initial stored configuration, while subsequent administrator changes are persisted. Treat environment changes as deployment inputs, not as proof that they are the active runtime values. Confirm important settings through the administrator UI or the relevant API after deployment.

### Health and API endpoints

| Endpoint     | Meaning                                                                       |
| ------------ | ----------------------------------------------------------------------------- |
| `/health`    | Basic application response                                                    |
| `/health/db` | Basic response with a database query                                          |
| `/healthz`   | Process liveness                                                              |
| `/livez`     | Liveness with database check                                                  |
| `/readyz`    | Readiness with database and configured vector-store checks; Redis is optional |

FastAPI's interactive API documentation (`/docs`) and OpenAPI document (`/openapi.json`) are enabled only when `ENV=dev`. They are not exposed by the normal production configuration.

### Security checklist

- Keep `BCGPT_AUTH=true` outside of disposable local experiments and generate a unique `BCGPT_SECRET_KEY` before every new environment.
- Terminate TLS at a reverse proxy or load balancer, set secure cookie flags, and limit direct access to the backend port, database, Redis, and provider services.
- If using trusted-header SSO, set `BCGPT_AUTH_TRUSTED_PROXY_IPS` to the actual proxy IPs/CIDRs. Do not trust an identity header from an unrestricted network path.
- Store API keys, SCIM tokens, OAuth/LDAP credentials, and object-store credentials in a secret manager rather than committing them to `.env` files.
- Review user permissions, model access rules, API-key restrictions, tool/function authoring, web-search access, retention, audit logging, and external integrations before inviting users.
- Test feature flags and failure modes in a staging environment. Some security, scanner, compliance, quality, and observability controls are opt-in or have deployment-specific dependencies.

For the supported security-reporting channel and project policy, see [docs/SECURITY.md](docs/SECURITY.md).

## Development

### Local development

Requirements: Python 3.11+ and Bun 1.3+.

Install Bun first. On macOS or Linux, use Bun's official installer:

```bash
curl -fsSL https://bun.com/install | bash
bun --version
```

On Windows PowerShell, run `powershell -c "irm bun.sh/install.ps1|iex"`, then open a new terminal and verify with `bun --version`. See the [Bun installation guide](https://bun.com/docs/installation) for package-manager and platform-specific options.

Create and activate a Python virtual environment, then install the backend requirements. The activated environment makes the `python` command used by the development scripts resolve to the correct interpreter.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r backend/requirements.txt
```

On Windows PowerShell, create and activate it with `py -3.11 -m venv .venv` and `.venv\Scripts\Activate.ps1` before running the same `python -m pip` commands.

Install the frontend dependencies and start both services:

```bash
bun install
bun run dev
```

This command fetches the required Pyodide asset, starts Vite at <http://localhost:5173>, and starts the FastAPI backend at <http://localhost:8090>. The development launcher also checks and installs backend requirements when needed, so the explicit Pip step above can be skipped when you prefer automatic setup. It creates a stable development signing key under `node_modules/.cache`, enables backend reload, and Vite proxies `/api`, `/ollama`, `/openai`, and `/ws` to the backend.

Use the following commands when you need individual processes or checks:

```bash
# frontend only
bun run dev:frontend

# backend only (with the same dependency/key helper used by bun run dev)
bun run dev:backend

# static build and local preview
bun run build
bun run preview
```

The Docker hot-reload profile is also available:

```bash
docker compose -f docker-compose.dev.yml up
```

### Project layout

| Path                  | Contents                                                                                             |
| --------------------- | ---------------------------------------------------------------------------------------------------- |
| `src/`                | SvelteKit application, UI components, API clients, i18n, and styles                                  |
| `backend/bcgpt/`      | FastAPI application, models, routers, providers, retrieval, agents, security, and compliance modules |
| `backend/bcgpt/test/` | Backend unit and integration test suites                                                             |
| `kubernetes/helm/`    | Helm chart source                                                                                    |
| `scripts/`            | Development, config-inventory, route-inventory, and quality helpers                                  |
| `docs/`               | Configuration reference, operating plans, inventories, and policies                                  |

## Architecture

The built application is served by the FastAPI process in production; it is not a separate Node server. Local development uses Vite as a frontend development server and proxies backend traffic to FastAPI.

```text
Browser / PWA
   │
   ├─ production: FastAPI serves the built SvelteKit application
   └─ development: Vite (:5173) proxies API and WebSocket traffic
                         │
                         ▼
                 FastAPI / bcgpt (:8090)
                  ├─ auth, users, chats, files, audit, admin APIs
                  ├─ provider adapters: Ollama, OpenAI-compatible, Gemini, Claude
                  ├─ retrieval: storage, embeddings, vector DB, web search
                  └─ agent, quality, security, and optional compliance modules
                         │
                         ▼
             PostgreSQL (standard) · optional Redis · vector/object stores
```

## Testing and quality checks

Run these commands from the repository root:

```bash
# frontend tests, Svelte diagnostics, and lint checks
bun run test:frontend
bun run check
bun run lint:frontend:check

# backend unit tests
make test-backend-unit

# combined default test target
make test

# source-derived inventories and regression checks
bun run check:routes
bun run check:ratchet
bun run check:fetch
make config-inventory
```

`make test-backend-integration` requires its Docker/PostgreSQL integration environment; `make test-backend-integration-collect` performs collection only. Use `bun run format:check` before submitting documentation or frontend changes and `bun run format` only when you intend to apply formatting changes across its configured file set.

## Documentation and support

| Topic                         | Document                                                                                                           |
| ----------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Full configuration catalog    | [docs/CONFIG_REFERENCE.md](docs/CONFIG_REFERENCE.md)                                                               |
| Agent subsystem and endpoints | [backend/bcgpt/agent/README.md](backend/bcgpt/agent/README.md)                                                     |
| Contributing                  | [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md)                                                                       |
| Security policy               | [docs/SECURITY.md](docs/SECURITY.md)                                                                               |
| Release/deployment review     | [docs/DEPLOYMENT_RELEASE_SURFACE_INVENTORY_2026-06-23.md](docs/DEPLOYMENT_RELEASE_SURFACE_INVENTORY_2026-06-23.md) |
| Change history                | [CHANGELOG.md](CHANGELOG.md)                                                                                       |

Report bugs and feature requests through the [issue tracker](https://github.com/bccard-ai/bcgpt-webui/issues). For contribution guidance, read [docs/CONTRIBUTING.md](docs/CONTRIBUTING.md) before opening a pull request.

## License and attribution

BCGPT WebUI is licensed under the [Apache License 2.0](LICENSE). It originated from [Open WebUI](https://github.com/open-webui/open-webui) v0.6.0; the required upstream notices are retained in [NOTICE](NOTICE).

---

[한국어 README 보기](README_KR.md)
