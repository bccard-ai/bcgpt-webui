<div align="center">

# BCGPT WebUI

**A self-hosted AI workspace for chat, retrieval, agents, and governance**

[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

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
- [Security policy](#security-policy)

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

`OPENAI_API_BASE_URL` can point to an OpenAI-compatible service. For multiple OpenAI-compatible or Ollama connections, use the semicolon-separated `OPENAI_API_BASE_URLS`/`OPENAI_API_KEYS` and `OLLAMA_BASE_URLS` settings documented in [Config Reference](#config-reference) below.

### PostgreSQL and Redis

The `with-db` profile is a useful starting point, not a complete production runbook. It requires a database password and configures secure session cookies:

```bash
export BCGPT_SECRET_KEY="$(python3 -c 'import secrets; print(secrets.token_urlsafe(32))')"
export POSTGRES_PASSWORD="replace-with-a-long-unique-password"

docker compose -f docker-compose.with-db.yml up -d --build
curl --fail http://localhost:8090/readyz
```

Before production use, place the app behind TLS, set a stable secret through your secret manager, restrict network access, choose backup/restore procedures for database, uploads, and vector data, and validate an upgrade and rollback in a non-production environment. The full in-repository deployment review is inlined below in [Deployment and Release Surface Inventory](#deployment-and-release-surface-inventory---2026-06-23).

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

## Deployment and Release Surface Inventory - 2026-06-23

이 문서는 bcgpt-webui의 배포/릴리즈 표면을 현재 워크트리 기준으로 고정한 인벤토리다.
`DEPLOYMENT_RELEASE_OPERATIONS_PLAN_2026-06-23.md`가 목표 운영 모델과 runbook을 다루고, 이
문서는 Dockerfile, Compose, Helm, CI workflow, startup script, health endpoints, migration side
effect, README quickstart가 현재 어떤 계약을 노출하는지 기록한다.

검토 기준: 2026-06-24 KST, 현재 워크트리 (Round 6 갱신). §5 Release Evidence Target에 Round 4/5/6
진행 상태가 주석으로 추가됐다. 구현, workflow, manifest, dependency, lockfile 변경은 하지 않았다.

### 1. Source Evidence Snapshot

| Surface                   | Current evidence                                                                                                                                                                                                                                                                              | Operational meaning                                                                                                                                              |
| ------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Docker build              | `Dockerfile` uses `oven/bun:1-alpine` for the frontend build and `python:3.11-slim` for runtime; installs `backend/requirements.txt`; copies built frontend to `/app/build`; runs as `appuser`; exposes 8090; healthcheck calls `/health`.                                                    | Image is multi-stage and non-root, but runtime Python differs from CI's Python 3.12 jobs and the healthcheck does not use the richer `/healthz`/`/readyz` split. |
| Docker image metadata     | Dockerfile has static OCI labels for title, description, source, vendor, and license.                                                                                                                                                                                                         | No observed build-time label injection for source revision, version, or image digest evidence.                                                                   |
| Compose all-in-one        | `docker-compose.yml` starts `bcgpt` plus `ollama/ollama:0.6.5`, mounts `bcgpt-data:/app/backend/data`, sets `read_only: true`, adds `/tmp` tmpfs, and renders `BCGPT_SECRET_KEY: ""` when unset.                                                                                              | The profile renders successfully, but the default app secret is empty under a hardened root filesystem.                                                          |
| Compose with-db           | `docker-compose.with-db.yml` adds Postgres 16 and Redis 7, requires `POSTGRES_PASSWORD` for render, sets `BCGPT_SESSION_COOKIE_SECURE=true`, keeps `read_only: true`, and still renders `BCGPT_SECRET_KEY: ""` when unset.                                                                    | DB credential preflight exists indirectly through interpolation, but app secret preflight is missing.                                                            |
| Compose without-ollama    | `docker-compose.without-ollama.yml` renders standalone app service with optional empty `BCGPT_SECRET_KEY`, `OPENAI_API_KEY`, and external `OLLAMA_BASE_URL`.                                                                                                                                  | Useful as a lightweight profile, but less hardened than the main profile and still accepts empty secrets.                                                        |
| Compose dev               | `docker-compose.dev.yml` uses Bun and Python images with source bind mounts and hot reload; it does not set `BCGPT_SECRET_KEY`.                                                                                                                                                               | Dev-only behavior can rely on writable mounts and fallback secrets, but this should not be promoted to production runbooks.                                      |
| Compose render checks     | `docker compose -f docker-compose.yml config`, `POSTGRES_PASSWORD=test-secret docker compose -f docker-compose.with-db.yml config`, `docker compose -f docker-compose.without-ollama.yml config`, and `docker compose -f docker-compose.dev.yml config` all returned status 0 in this review. | Rendering proves YAML validity, not production readiness. Secret, probe, storage, and backup preflights remain separate gates.                                   |
| Compose helper script     | `run-compose.sh` defaults to `docker compose -f docker-compose.yaml` and references `docker-compose.gpu.yaml`, `docker-compose.api.yaml`, `docker-compose.data.yaml`, and `docker-compose.playwright.yaml`; current repo files are `.yml` profiles only.                                      | Treat the helper script as drifted until its file references are reconciled or explicitly deprecated.                                                            |
| Backend startup           | `backend/start.sh` writes `.bcgpt_secret_key` in the current working directory when both `BCGPT_SECRET_KEY` and `BCGPT_JWT_SECRET_KEY` are empty. Docker runtime workdir is `/app/backend`.                                                                                                   | Production Compose read-only roots can conflict with fallback secret-file creation because only `/app/backend/data` and `/tmp` are writable.                     |
| Startup dependency writes | `backend/start.sh` installs Playwright browsers/deps and NLTK `punkt_tab` at startup when `RAG_WEB_LOADER_ENGINE=playwright` and `PLAYWRIGHT_WS_URI` is unset.                                                                                                                                | Hidden startup network/write paths need either image build-time ownership or explicit writable/cache volume policy.                                              |
| Helm chart defaults       | `kubernetes/helm/values.yaml` defaults to `image.repository: ghcr.io/bcgpt/bcgpt`, `tag: main`, `pullPolicy: Always`, one RWO PVC, probes all `/health`, and a DB migration initContainer.                                                                                                    | Local chart is usable as a contract example, but defaults are mutable and probes are not readiness-specific.                                                     |
| Helm secrets              | `kubernetes/helm/templates/secret.yaml` emits only non-empty `.Values.secrets`; default `BCGPT_SECRET_KEY` is empty.                                                                                                                                                                          | A default render can omit the app secret entirely unless values are supplied by an operator or external secret system.                                           |
| Helm chart ownership      | `kubernetes/helm/README.md` says charts are hosted in a separate repository while this repo still contains chart templates.                                                                                                                                                                   | Chart source of truth must be decided before telling operators which chart to use.                                                                               |
| Helm render               | `helm template bcgpt kubernetes/helm` was attempted and failed with status 127 because `helm` is not installed on this host.                                                                                                                                                                  | Local review cannot prove rendered manifest state; CI or a documented dev toolchain must own Helm render/lint.                                                   |
| CI workflow               | `.github/workflows/ci.yml` runs frontend lint/typecheck/test/build, frontend audit, backend lint, and backend tests. Backend `pylint --errors-only`, `pip-audit`, and integration tests are non-blocking.                                                                                     | CI has broad coverage but still contains report-only or non-blocking quality/security surfaces.                                                                  |
| Docker publish workflow   | `.github/workflows/docker.yml` pushes GHCR images on `main` and `v*` tags with branch, semver, and sha tags.                                                                                                                                                                                  | No observed workflow-level dependency on CI success, SBOM, provenance, signing, or container scan before publication.                                            |
| Lighthouse workflow       | `.github/workflows/lighthouse.yml` builds and runs Lighthouse CI on push/pull request to `main`.                                                                                                                                                                                              | Performance signal exists, but release promotion is not tied to a full release evidence bundle.                                                                  |
| Health endpoints          | `backend/bcgpt/main.py` exposes `/health`, `/health/db`, `/healthz`, `/livez`, and `/readyz`. `/readyz` checks DB and qdrant, while Redis is optional/non-failing.                                                                                                                            | App has enough endpoint granularity, but Dockerfile and Helm defaults still use `/health`.                                                                       |
| Migration execution       | `backend/bcgpt/config.py` calls Alembic/JSON config migration helpers at import time, `backend/bcgpt/internal/db.py` runs the Peewee bridge at import time, and Helm has an `alembic upgrade head` initContainer.                                                                             | Migration ownership is split across app import and infrastructure. Multi-replica rollout and failure semantics need an ADR.                                      |
| README quickstart         | README Compose production example sets `POSTGRES_PASSWORD`; Docker run examples mount data but do not show `BCGPT_SECRET_KEY`; update docs use `docker compose pull && docker compose up -d`.                                                                                                 | Quickstart remains simple, but production instructions do not yet enforce app secret, immutable image, backup, or rollback evidence.                             |
| Build provenance env      | `vite.config.ts` defaults `VITE_APP_BUILD_HASH` to `dev-build` unless `APP_BUILD_HASH` is injected; backend `BCGPT_BUILD_HASH` also defaults to `dev-build`.                                                                                                                                  | Docker build/publish path does not currently prove frontend/backend build hash injection from git metadata.                                                      |

### 2. Deployment Artifact Inventory

| Artifact               | File or owner                                                                 | Current profile                                                      | Required governance decision                                                                         |
| ---------------------- | ----------------------------------------------------------------------------- | -------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------------- |
| Runtime image          | `Dockerfile`                                                                  | Single combined frontend/backend image on Python 3.11 runtime.       | Pin base-image digests, inject revision labels and build hashes, define scan/SBOM/provenance policy. |
| Compose all-in-one     | `docker-compose.yml`                                                          | Demo/single-node BCGPT + Ollama, read-only root, local named volume. | Decide if it is production-supported or demo-only; require explicit app secret if non-dev.           |
| Compose with-db        | `docker-compose.with-db.yml`                                                  | App + Postgres + Redis, read-only root, named volumes.               | Add app secret preflight, backup/restore procedure, and Redis durability policy.                     |
| Compose without-ollama | `docker-compose.without-ollama.yml`                                           | App-only profile for external providers.                             | Classify hardening posture and required external provider/secret preflight.                          |
| Compose dev            | `docker-compose.dev.yml`                                                      | Hot reload and bind mounts.                                          | Keep dev-only; do not use fallback secret behavior as production precedent.                          |
| Compose helper         | `run-compose.sh`                                                              | Helper menu references missing `.yaml` override files.               | Reconcile with actual `.yml` profiles or mark deprecated in docs.                                    |
| Helm local chart       | `kubernetes/helm`                                                             | In-repo chart with mutable image defaults and `/health` probes.      | Decide canonical/example/test-only ownership, then add render/lint gate if canonical.                |
| Helm README            | `kubernetes/helm/README.md`                                                   | Points to an external chart repository.                              | Link exact external chart/version or update local chart ownership statement.                         |
| CI gate                | `.github/workflows/ci.yml`                                                    | Build/test/audit/lint jobs with several non-blocking checks.         | Define which checks gate release publication and which remain report-only.                           |
| Docker publication     | `.github/workflows/docker.yml`                                                | Publishes GHCR images independently on branch/tag events.            | Gate publish by release-quality checks and attach supply-chain evidence.                             |
| Lighthouse signal      | `.github/workflows/lighthouse.yml`                                            | Runs Lighthouse CI after build.                                      | Tie budgets to release criteria if performance is release-blocking.                                  |
| Startup script         | `backend/start.sh`                                                            | Owns secret fallback and optional Playwright/NLTK runtime install.   | Move hidden writes into declared writable paths or fail fast in production.                          |
| Probe contract         | `backend/bcgpt/main.py`, Dockerfile, Helm values                              | App exposes granular endpoints; deployments default to `/health`.    | Define endpoint mapping per environment and test dependency failure cases.                           |
| Migration contract     | `backend/bcgpt/config.py`, `backend/bcgpt/internal/db.py`, Helm initContainer | Import-time migration plus optional infrastructure initContainer.    | Pick one authoritative migration command and make other paths explicit opt-ins or no-ops.            |
| README deployment docs | `README.md`                                                                   | Install/update commands exist, but production controls are sparse.   | Keep quickstart lightweight while linking to stricter production runbooks.                           |

### 3. Render and Preflight Matrix

| Check                  | Command used in this review                                                         | Current result                                                                    | Missing preflight                                                                       |
| ---------------------- | ----------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| Compose all-in-one     | `docker compose -f docker-compose.yml config`                                       | Pass; rendered output included `BCGPT_SECRET_KEY: ""` and `read_only: true`.      | Reject empty app secret for non-dev use; document writable paths.                       |
| Compose with-db        | `POSTGRES_PASSWORD=test-secret docker compose -f docker-compose.with-db.yml config` | Pass; rendered DB/Redis URLs and `POSTGRES_PASSWORD`, but `BCGPT_SECRET_KEY: ""`. | Require app secret; define DB backup and Redis state policy.                            |
| Compose without-ollama | `docker compose -f docker-compose.without-ollama.yml config`                        | Pass; rendered empty app/provider secrets.                                        | Classify as dev/demo/production and require provider secret posture.                    |
| Compose dev            | `docker compose -f docker-compose.dev.yml config`                                   | Pass; no app secret in rendered env.                                              | Mark fallback-secret behavior dev-only.                                                 |
| Helm template          | `helm template bcgpt kubernetes/helm`                                               | Not executed successfully; `helm_template_status=127`, `helm` command not found.  | Add Helm toolchain bootstrap or CI render/lint.                                         |
| Docker healthcheck     | Source inspection                                                                   | `/health`.                                                                        | Decide `/healthz` vs `/readyz` for container/runtime probes.                            |
| Helm probes            | `kubernetes/helm/values.yaml` inspection                                            | liveness/readiness/startup all `/health`.                                         | Render and test `/healthz` liveness plus `/readyz` readiness after qdrant/Redis policy. |
| Release artifact       | Workflow inspection                                                                 | GHCR publication with tags, no observed SBOM/provenance/signing/scan.             | Add release checklist and evidence artifacts before promotion.                          |
| Migration execution    | Source and Helm inspection                                                          | Import-time plus initContainer path.                                              | Choose one owner, add smoke test, record migration head in release evidence.            |
| Backup/rollback        | README/docs/source search                                                           | Generic quickstart/update only.                                                   | Define RPO/RTO, restore order, image/data rollback decision tree, and staging drill.    |

### 4. Runtime Write and Storage Matrix

| Path or store                    | Current writer                                                                | Declared writable surface                                    | Risk                                                                                               |
| -------------------------------- | ----------------------------------------------------------------------------- | ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------- |
| `/app/backend/data`              | App DB/uploads/cache, model cache paths, Helm PVC mount.                      | Docker volume, Compose named volume, Helm PVC.               | Capacity, backup, and restore semantics differ across SQLite, uploads, cache, and model artifacts. |
| `/tmp`                           | Runtime temporary files and tools.                                            | Compose production profiles mount tmpfs.                     | Size and lifetime are not documented.                                                              |
| `/app/backend/.bcgpt_secret_key` | `backend/start.sh` fallback when app/JWT secrets are empty.                   | Not declared writable under read-only Compose profiles.      | Startup can fail or fallback can behave differently by profile.                                    |
| Playwright browser/deps cache    | `backend/start.sh` when `RAG_WEB_LOADER_ENGINE=playwright` without remote WS. | Not modeled in Docker/Compose/Helm volumes.                  | Runtime install can require network, package manager access, and writable cache paths.             |
| NLTK `punkt_tab`                 | `backend/start.sh` in the same Playwright branch.                             | Not modeled as a release artifact.                           | Startup dependency fetch can be slow or unavailable.                                               |
| SQLite DB                        | Default `DATABASE_URL` under `${DATA_DIR}`.                                   | Local data volume/PVC.                                       | Single-node only unless explicitly supported; backup needs safe snapshot method.                   |
| Postgres DB                      | `docker-compose.with-db.yml` or external `DATABASE_URL`.                      | Compose `postgres-data` or external managed DB.              | Migration and restore order need release runbook ownership.                                        |
| Redis                            | `docker-compose.with-db.yml`; app optional readiness behavior.                | Compose `redis-data` when with-db profile is used.           | Cache vs durable state decision affects backup and HA profile.                                     |
| Uploaded files                   | `Storage` abstraction, local `${DATA_DIR}/uploads`, optional object stores.   | Local volume/PVC or S3/GCS/Azure env.                        | SQL/object/vector reconciliation must be part of backup and DSAR semantics.                        |
| Vector stores                    | Qdrant, Milvus, pgvector, OpenSearch, Elasticsearch settings.                 | External service or local deployment outside this inventory. | Backup/restore and readiness requirements are provider-specific.                                   |
| Frontend sourcemaps/build assets | Vite build with `sourcemap: true`.                                            | Image build artifact.                                        | Source-map publication/upload policy belongs with observability and release provenance.            |

### 5. Release Evidence Target

The release checklist should produce one row per release candidate with these fields.
**Status annotations (2026-06-24, Round 6):**

| Field                     | Current state                                                                    | Target                                                                                  | Round 6 status                                         |
| ------------------------- | -------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- | ------------------------------------------------------ |
| Source commit             | Available from git/GitHub context, but not injected into all artifacts.          | Recorded in release notes, image labels, frontend/backend build hashes, and provenance. | ✅ Checklist template §1                               |
| Image digest              | Generated by registry after push, not surfaced in docs/runbook.                  | Deployment pins digest or sha tag and records digest in release evidence.               | ✅ Checklist template §2 ⬜ Phase 2: digest pinning    |
| Docker base image digests | Base images use tags.                                                            | Release evidence records immutable base digests.                                        | ✅ Checklist template §2 ⬜ Phase 2: digest recording  |
| Frontend build hash       | Defaults to `dev-build` without `APP_BUILD_HASH`.                                | Docker build injects git hash and UI/API can report it.                                 | ✅ Checklist template §1 ⬜ Phase 2: CI injection      |
| Backend build hash        | Defaults to `dev-build` without `BCGPT_BUILD_HASH`.                              | Runtime env or image label exposes the same source revision.                            | ✅ Checklist template §1 ⬜ Phase 2: CI injection      |
| Helm chart version/source | Local `Chart.yaml` is `1.0.0`; README points external.                           | Exact chart source and version are recorded per release.                                | ✅ Checklist template §3 ⬜ `OWNER`: chart ownership   |
| Migration head            | Alembic runs from import/initContainer paths, no release artifact row.           | Authoritative migration command records current head before/after deployment.           | ✅ Checklist template §4 ✅ Round 5 ADR Option D       |
| Frontend audit            | CI uses `bun audit` report-only (Round 4).                                       | Release gate uses the lockfile-correct audit command and waiver register.               | ✅ Round 4 done                                        |
| Backend audit             | `pip-audit` is non-blocking in CI and not installed locally in earlier evidence. | High/critical policy is triaged, then enforced or waived with owner/date.               | ✅ Checklist template §6 ⬜ Phase 2: triage completion |
| Container scan            | Not observed.                                                                    | Blocking scan or explicit waiver artifact.                                              | ✅ Checklist template §6 ⬜ Phase 2: Trivy/Grype       |
| SBOM                      | Not observed.                                                                    | SBOM attached to release.                                                               | ✅ Checklist template §6 ⬜ Phase 2: Syft/CycloneDX    |
| Provenance attestation    | Not observed.                                                                    | Build provenance generated and retained.                                                | ✅ Checklist template §6 ⬜ Phase 2: SLSA/cosign       |
| Image signing             | Not observed.                                                                    | Signing policy selected and implemented or formally declined.                           | ✅ Checklist template §6 ⬜ Phase 2: cosign            |
| Backup/restore smoke      | Not observed.                                                                    | Staging restore evidence attached before production promotion.                          | ✅ Checklist template §7 ⬜ Phase 4: staging drill     |
| Rollback target           | README update pulls latest mutable tags.                                         | Previous immutable digest and data compatibility note recorded.                         | ✅ Checklist template §7                               |

### 6. Current Findings

1. Compose render success can hide production failure because non-dev profiles render empty `BCGPT_SECRET_KEY`
   while hardened profiles use a read-only root filesystem and `start.sh` writes fallback secrets outside the
   data volume.
2. README production examples mention `POSTGRES_PASSWORD` but do not require `BCGPT_SECRET_KEY`, immutable image
   references, backup/restore, or rollback evidence.
3. Helm defaults omit empty secrets, use mutable `main` image tag with `pullPolicy: Always`, and point all probes
   at `/health`.
4. The app already exposes `/healthz` and `/readyz`, so deployment manifests should make an explicit policy
   decision instead of treating `/health` as both liveness and readiness.
5. Docker publish is independent from CI quality/security gates and lacks observed SBOM, provenance, signing, and
   container scan steps.
6. Migration ownership is split across import-time Alembic/JSON config migration, import-time Peewee migration
   bridge, and Helm initContainer.
7. `run-compose.sh` references Compose override files that are not present in the repo's current `.yml` profile
   set, so it should not be treated as canonical until reconciled.
8. Build provenance defaults to `dev-build` for both frontend and backend unless explicit build hash variables
   are injected.
9. Playwright/NLTK startup setup introduces hidden runtime writes and network dependency in one RAG web-loader
   mode.
10. Local Helm chart ownership is ambiguous because the chart exists in-repo while the Helm README points users to
    a separate chart repository.

### 7. Generated Inventory Target

Future automation should write `docs/generated/DEPLOYMENT_RELEASE_SURFACE_INVENTORY.md` with a stable schema:

| Column                 | Meaning                                                                                           |
| ---------------------- | ------------------------------------------------------------------------------------------------- |
| `surface_id`           | Stable id such as `compose.with-db`, `helm.values`, `workflow.docker`, `startup.secret-fallback`. |
| `source_path`          | File path or workflow owner.                                                                      |
| `source_locator`       | Line number, YAML key, route path, or workflow job id.                                            |
| `profile`              | `dev`, `demo`, `compose-prod`, `helm`, `release`, `runtime`, or `shared`.                         |
| `contract`             | The behavior currently exposed to operators or release automation.                                |
| `required_env`         | Required env vars for this surface.                                                               |
| `secret_policy`        | `required`, `optional`, `omitted-when-empty`, `fallback`, or `external`.                          |
| `write_paths`          | Runtime writable paths or storage systems touched.                                                |
| `probe_policy`         | Health/readiness/liveness endpoint relation if applicable.                                        |
| `release_evidence`     | Required release artifact fields.                                                                 |
| `current_status`       | `supported`, `dev-only`, `drifted`, `ambiguous`, or `missing-gate`.                               |
| `owner_decision`       | Human decision needed before implementation.                                                      |
| `verification_command` | Command or source check that proves the row.                                                      |

### 8. Refresh Commands

Use these commands when refreshing the inventory:

```bash
docker compose -f docker-compose.yml config
POSTGRES_PASSWORD=test-secret docker compose -f docker-compose.with-db.yml config
docker compose -f docker-compose.without-ollama.yml config
docker compose -f docker-compose.dev.yml config
helm template bcgpt kubernetes/helm
rg -n "BCGPT_SECRET_KEY|BCGPT_JWT_SECRET_KEY|read_only|healthz|readyz|APP_BUILD_HASH|BCGPT_BUILD_HASH" \
  Dockerfile docker-compose*.yml backend/start.sh backend/bcgpt/main.py backend/bcgpt/env.py vite.config.ts
rg -n "sbom|provenance|cosign|sign|scan|build-push-action|metadata-action|pip-audit|npm audit|bun audit" \
  .github/workflows
rg -n "docker-compose\\.(gpu|api|data|playwright)\\.yaml|docker-compose\\.yaml" run-compose.sh backend/requirements.txt
rg -n "run_migrations\\(|migrate_json_config\\(|handle_peewee_migration\\(|alembic upgrade head" \
  backend/bcgpt/config.py backend/bcgpt/internal/db.py kubernetes/helm
```

Current local verification notes:

- all four Compose render commands above passed during this review;
- rendered non-dev Compose outputs still showed empty app secret values when the operator does not supply them;
- `helm template bcgpt kubernetes/helm` could not run on this host because `helm` is not installed;
- `git diff --check` and trailing-whitespace checks should be run after any documentation refresh.

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

[.env.example](.env.example) contains a deliberately limited, commented sample. The full source-backed configuration catalog—including lifecycle, defaults, provider settings, storage, observability, and feature flags—is inlined below in [Config Reference](#config-reference).

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

For the supported security-reporting channel and project policy, see [Security policy](#security-policy) below.

## Config Reference

Curated configuration reference for bcgpt-webui. This is intentionally not a dump of every discovered key.
The raw inventory is planned in `CONFIG_REFERENCE_CATALOG_PLAN_2026-06-23.md`; this document starts with
the production-critical slice that was cross-checked against source, `.env.example`, Dockerfile, Compose,
and Helm on 2026-06-23 KST.

### Status

Current coverage:

- Included slice: auth/session/JWT/API key, database, Redis, WebSocket manager, container bootstrap, frontend
  build provenance, model provider credentials, auxiliary provider surfaces, and storage/object/vector
  profiles, observability, audit telemetry, handoff notification operations, compliance/privacy retention,
  security scanner, SIEM, AI transparency, chat rate-limit posture, OAuth/LDAP/SCIM enterprise auth, and
  search/external web retrieval providers, advanced RAG/Agent quality-control rows, and frontend
  remote-error/logging decision boundary.
- Auth/session/JWT/cookie/API-key/MFA/OAuth/LDAP/SCIM lifecycle behavior is cross-referenced in
  `AUTH_SESSION_IDENTITY_GOVERNANCE_PLAN_2026-06-23.md` and
  `docs/generated/AUTH_SESSION_IDENTITY_INVENTORY.md`; this config reference owns key mutability, defaults,
  aliases, and deployment coverage.
- Admin Settings/config mutation workflow is cross-referenced in
  `ADMIN_SETTINGS_CONFIG_MUTATION_GOVERNANCE_PLAN_2026-06-23.md` and
  `docs/generated/ADMIN_SETTINGS_CONFIG_MUTATION_INVENTORY.md`; this config reference owns key taxonomy,
  defaults, aliases, and deployment coverage, while the mutation plan owns readback, apply, audit, export, and
  rollback contracts.
- Feature flag rollout, public `/api/config.features`, kill switches, off-state UX, and permission-gated feature
  controls are cross-referenced in `FEATURE_FLAG_ROLLOUT_GOVERNANCE_PLAN_2026-06-23.md` and
  `docs/generated/FEATURE_FLAG_ROLLOUT_INVENTORY.md`; this config reference owns key taxonomy and deployment
  exposure, while the rollout plan owns apply scope, user-visible state, backend enforcement, rollback, and smoke
  evidence.
- Audit/security evidence lifecycle is cross-referenced in
  `AUDIT_SECURITY_EVIDENCE_LIFECYCLE_GOVERNANCE_PLAN_2026-06-23.md` and
  `docs/generated/AUDIT_SECURITY_EVIDENCE_INVENTORY.md`; this config reference owns audit/security key taxonomy
  and defaults, while the evidence plan owns capture posture, retention, export, purge, SIEM delivery, and
  artifact semantics.
- Notification/handoff communication lifecycle is cross-referenced in
  `NOTIFICATION_HANDOFF_COMMUNICATION_GOVERNANCE_PLAN_2026-06-23.md` and
  `docs/generated/NOTIFICATION_HANDOFF_COMMUNICATION_INVENTORY.md`; this config reference owns webhook,
  handoff, SMTP, banner, update-toast, and AI transparency key taxonomy and defaults, while the communication
  plan owns delivery, payload privacy, and user-visible notice behavior.
- Knowledge/retrieval index lifecycle is cross-referenced in
  `KNOWLEDGE_RETRIEVAL_INDEX_LIFECYCLE_GOVERNANCE_PLAN_2026-06-23.md` and
  `docs/generated/KNOWLEDGE_RETRIEVAL_INDEX_INVENTORY.md`; this config reference owns RAG/vector/web/search key
  taxonomy and defaults, while the index plan owns collection namespace ownership, stale-index marking,
  semantic-cache isolation, reindex expectations, and retention behavior.
- Not yet included: final implemented frontend remote-error/logging keys, because no owner-selected
  production transport exists in current source.
- Source inventory baseline: earlier AST-only snapshot found 524 code env/config keys; a 2026-06-23
  hybrid Python AST + JS process-env rerun found 530 unique keys and 381 unique `PersistentConfig` keys.
  `docs/generated/CONFIG_INVENTORY.md` now reports the broader bootstrap scope as 1,042 raw records,
  549 unique keys, and 381 unique `PersistentConfig` keys because it also includes deployment, CI,
  examples, frontend build keys, script env, and `BaseSettings` exposure. Treat these counts as
  extractor-versioned evidence, not interchangeable totals.
- `.env.example` baseline: 44 assignment rows.
- Helm baseline: 13 `.Values.env` keys and 4 `.Values.secrets` keys.

Do not treat absence from this file as proof that a key is unsupported. Until raw and curated inventory are
complete, absence means "not yet cataloged."

### Legend

| Field           | Values                                                                               |
| --------------- | ------------------------------------------------------------------------------------ |
| Lifecycle       | `env-only`, `persistent-seed`, `startup-validation`, `build-time`, `deployment-only` |
| Mutability      | `restart`, `db/admin`, `build`, `deploy`                                             |
| Secret class    | `secret`, `sensitive-config`, `public-config`, `identifier`, `alias`                 |
| Deploy coverage | `env-example`, `helm-env`, `helm-secret`, `compose`, `dockerfile`, `missing`         |

`persistent-seed` means the environment value seeds a `PersistentConfig` row, but the active runtime value
can later come from the database/admin API. Changing the env var after first startup may not change behavior
unless the config row is reset or updated.

### Auth, Session, JWT, API-Key

| Key                                    | Lifecycle / mutability                  | Default / alias                                | Secret class                    | Current deploy coverage                           | Production guidance                                                                                                                                                            |
| -------------------------------------- | --------------------------------------- | ---------------------------------------------- | ------------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `BCGPT_AUTH`                           | env-only / restart                      | `True`                                         | public-config                   | helm-env; missing from `.env.example` and Compose | Production should leave auth enabled. If disabled for local/demo, runbook must state that no protected deployment data is allowed.                                             |
| `BCGPT_SECRET_KEY`                     | env-only + startup-validation / restart | no default; alias fallback `WEBUI_SECRET_KEY`  | secret                          | env-example, helm-secret, compose                 | Required whenever `BCGPT_AUTH=true`. Must be stable across upgrades; changing it invalidates issued sessions/tokens. Compose currently defaults to empty if host var is unset. |
| `WEBUI_SECRET_KEY`                     | alias / restart                         | fallback for `BCGPT_SECRET_KEY`                | secret                          | missing                                           | Legacy compatibility alias only. New docs and deployment profiles should prefer `BCGPT_SECRET_KEY`.                                                                            |
| `BCGPT_AUTH_TRUSTED_EMAIL_HEADER`      | env-only / restart                      | unset                                          | sensitive-config                | env-example comments only                         | Use only behind a trusted reverse proxy and always pair with `BCGPT_AUTH_TRUSTED_PROXY_IPS`; otherwise spoofed headers can authenticate users.                                 |
| `BCGPT_AUTH_TRUSTED_NAME_HEADER`       | env-only / restart                      | unset                                          | sensitive-config                | missing                                           | Same trust boundary as email header; document only with reverse-proxy SSO profile.                                                                                             |
| `BCGPT_AUTH_TRUSTED_PROXY_IPS`         | env-only / restart                      | empty list                                     | sensitive-config                | env-example                                       | Required when trusted-header SSO is enabled. Empty list triggers warning but does not create a safe proxy allowlist.                                                           |
| `BCGPT_SESSION_COOKIE_SAME_SITE`       | env-only / restart                      | `lax`                                          | public-config                   | dockerfile                                        | Production default is reasonable for same-site deployments; cross-site SSO/embedding needs explicit owner review.                                                              |
| `BCGPT_SESSION_COOKIE_SECURE`          | env-only / restart                      | `false`                                        | public-config                   | compose with-db sets `true`                       | Production behind TLS should set `true`; local non-TLS dev may keep `false`.                                                                                                   |
| `BCGPT_AUTH_COOKIE_SAME_SITE`          | env-only / restart                      | falls back to `BCGPT_SESSION_COOKIE_SAME_SITE` | public-config                   | missing                                           | Catalog with session cookie settings; avoid configuring conflicting SameSite semantics without SSO testing.                                                                    |
| `BCGPT_AUTH_COOKIE_SECURE`             | env-only / restart                      | falls back to `BCGPT_SESSION_COOKIE_SECURE`    | public-config                   | missing                                           | Production should normally match session cookie secure flag.                                                                                                                   |
| `JWT_ALGORITHM`                        | env-only / restart                      | `HS256`                                        | public-config                   | env-example                                       | `RS256` requires valid private/public key material. Misconfiguration falls back to HS256, so release smoke must check actual JWKS/signing behavior.                            |
| `JWT_KEY_ID`                           | env-only / restart                      | `bcgpt-key-1`                                  | identifier                      | env-example                                       | Not a secret. Rotate alongside RSA keys when RS256 is used.                                                                                                                    |
| `JWT_RSA_PRIVATE_KEY`                  | env-only / restart                      | unset                                          | secret                          | env-example comments only                         | Prefer file or external secret mount. Inline value must preserve escaped newlines.                                                                                             |
| `JWT_RSA_PRIVATE_KEY_FILE`             | env-only / restart                      | unset                                          | sensitive-config path to secret | env-example comments only                         | Recommended Kubernetes/Compose pattern for RSA private key material.                                                                                                           |
| `JWT_RSA_PUBLIC_KEY`                   | env-only / restart                      | unset                                          | sensitive-config                | env-example comments only                         | Public key is not secret, but still must match private key and rotation policy.                                                                                                |
| `JWT_RSA_PUBLIC_KEY_FILE`              | env-only / restart                      | unset                                          | sensitive-config path           | env-example comments only                         | Preferred for mounted public key file when using RS256.                                                                                                                        |
| `JWT_EXPIRES_IN`                       | persistent-seed / db-admin              | `7d`                                           | public-config                   | missing                                           | Because this is `PersistentConfig`, env is seed/default. Expiry policy needs auth owner approval before changing from default.                                                 |
| `ENABLE_API_KEY`                       | persistent-seed / db-admin              | `True`                                         | public-config                   | missing                                           | Production reference must pair this with endpoint restrictions and audit policy.                                                                                               |
| `ENABLE_API_KEY_ENDPOINT_RESTRICTIONS` | persistent-seed / db-admin              | `False`                                        | public-config                   | missing                                           | Should be enabled before treating API keys as production-safe broad credentials.                                                                                               |
| `API_KEY_ALLOWED_ENDPOINTS`            | persistent-seed / db-admin              | empty                                          | public-config                   | missing                                           | Not a secret despite `KEY` in name. Needs route/method scope semantics from access-control plan.                                                                               |

Validation evidence:

- `main.py` lifespan calls `validate_settings()`.
- `settings.py` validates `BCGPT_SECRET_KEY` length but only warns when empty.
- `env.py` raises if `BCGPT_AUTH` is true and `BCGPT_SECRET_KEY`/`WEBUI_SECRET_KEY` is absent.

### OAuth, LDAP, SCIM

These rows cover enterprise auth federation and provisioning. Most rows are `PersistentConfig` seeds, so the
environment value initializes a DB-backed runtime setting rather than guaranteeing the active value forever.

#### OAuth Provider Registration

| Key(s)                                                                                                                            | Lifecycle / mutability                                  | Default / alias                                                                       | Secret class                                                     | Current deploy coverage | Production guidance                                                                                                                                                      |
| --------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------- | ------------------------------------------------------------------------------------- | ---------------------------------------------------------------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `ENABLE_OAUTH_SIGNUP`                                                                                                             | persistent-seed / db-admin                              | `False`                                                                               | public-config                                                    | missing                 | Required for new OAuth users to be created. Pair with domain allowlist, role policy, and first-user bootstrap tests.                                                     |
| `OAUTH_MERGE_ACCOUNTS_BY_EMAIL`                                                                                                   | persistent-seed / db-admin                              | `False`                                                                               | sensitive-config                                                 | missing                 | Existing-account linking checks `email_verified` for non-GitHub providers. Keep disabled unless the IdP reliably asserts verified email.                                 |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GOOGLE_OAUTH_SCOPE`, `GOOGLE_REDIRECT_URI`                                           | persistent-seed / db-admin plus provider registry smoke | id unset; secret unset; scope `openid email profile`; redirect unset                  | secret for client secret; identifier/sensitive-config for others | missing                 | Google is registered only when client id and secret exist. Verify `/api/config` provider list and callback after rotation.                                               |
| `MICROSOFT_CLIENT_ID`, `MICROSOFT_CLIENT_SECRET`, `MICROSOFT_CLIENT_TENANT_ID`, `MICROSOFT_OAUTH_SCOPE`, `MICROSOFT_REDIRECT_URI` | persistent-seed / db-admin plus provider registry smoke | id/secret/tenant/redirect unset; scope `openid email profile`                         | secret for client secret; identifier/sensitive-config for others | missing                 | Microsoft is registered only when id, secret, and tenant id exist. Tenant id is required to build the discovery URL.                                                     |
| `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `GITHUB_CLIENT_SCOPE`, `GITHUB_CLIENT_REDIRECT_URI`                                   | persistent-seed / db-admin plus provider registry smoke | id/secret/redirect unset; scope `user:email`                                          | secret for client secret; identifier/sensitive-config for others | missing                 | GitHub uses `id` as the sub claim and fetches primary verified email when missing from userinfo.                                                                         |
| `OAUTH_CLIENT_ID`, `OAUTH_CLIENT_SECRET`, `OPENID_PROVIDER_URL`, `OPENID_REDIRECT_URI`, `OAUTH_SCOPES`, `OAUTH_PROVIDER_NAME`     | persistent-seed / db-admin plus provider registry smoke | id/secret/provider/redirect unset; scopes `openid email profile`; provider name `SSO` | secret for client secret; sensitive-config/identifier for others | missing                 | Generic OIDC registers only when client id, secret, and provider metadata URL exist. Logout fetches the provider metadata URL at signout when an id token cookie exists. |
| `OAUTH_ALLOWED_DOMAINS`                                                                                                           | persistent-seed / db-admin                              | `*`                                                                                   | sensitive-config                                                 | missing                 | `*` allows any verified provider email domain. Production enterprise SSO should usually list explicit domains.                                                           |

#### OAuth Claims, Roles, And Groups

| Key                             | Lifecycle / mutability     | Default / alias                                                               | Secret class       | Current deploy coverage | Production guidance                                                                                                                                                                         |
| ------------------------------- | -------------------------- | ----------------------------------------------------------------------------- | ------------------ | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `OAUTH_EMAIL_CLAIM`             | persistent-seed / db-admin | `email`                                                                       | identifier         | missing                 | Callback requires this claim or a provider-specific fallback. Smoke with real IdP token shape.                                                                                              |
| `OAUTH_USERNAME_CLAIM`          | persistent-seed / db-admin | `name`                                                                        | identifier         | missing                 | Missing claim falls back to email as display name.                                                                                                                                          |
| `OAUTH_PICTURE_CLAIM`           | persistent-seed / db-admin | `picture`                                                                     | identifier         | missing                 | Profile picture URL is validated and fetched without redirects; still treat as IdP-supplied external content.                                                                               |
| `OAUTH_GROUPS_CLAIM`            | persistent-seed / db-admin | canonical persistent key seeds from env `OAUTH_GROUP_CLAIM`; default `groups` | identifier / alias | missing                 | Do not document `OAUTH_GROUPS_CLAIM` as an env var until owner decides whether `OAUTH_GROUP_CLAIM` is intentional compatibility or drift. Runtime claim path supports dotted nested fields. |
| `OAUTH_GROUP_CLAIM`             | alias / restart seed       | seeds `OAUTH_GROUPS_CLAIM`                                                    | alias              | missing                 | Alias/drift candidate only. Add examples only after the auth owner chooses the canonical external name.                                                                                     |
| `ENABLE_OAUTH_ROLE_MANAGEMENT`  | persistent-seed / db-admin | `False`                                                                       | public-config      | missing                 | When enabled, role claim values can grant `admin`. Add negative tests before enabling in regulated profiles.                                                                                |
| `OAUTH_ROLES_CLAIM`             | persistent-seed / db-admin | `roles`                                                                       | identifier         | missing                 | Dotted nested claim path; returns no roles if the leaf is not a list.                                                                                                                       |
| `OAUTH_ALLOWED_ROLES`           | persistent-seed / db-admin | `user,admin` parsed as list                                                   | public-config      | missing                 | Values map matched claim entries to local `user`; keep separate from IdP display labels.                                                                                                    |
| `OAUTH_ADMIN_ROLES`             | persistent-seed / db-admin | `admin` parsed as list                                                        | sensitive-config   | missing                 | Any match grants local admin when role management is enabled. Requires route-level admin regression tests.                                                                                  |
| `ENABLE_OAUTH_GROUP_MANAGEMENT` | persistent-seed / db-admin | `False`                                                                       | public-config      | missing                 | Syncs non-admin users into existing local groups by name; it does not create groups from IdP claims.                                                                                        |

#### LDAP

| Key                                                      | Lifecycle / mutability                                | Default / alias                                                    | Secret class             | Current deploy coverage | Production guidance                                                                                                                                                                         |
| -------------------------------------------------------- | ----------------------------------------------------- | ------------------------------------------------------------------ | ------------------------ | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `ENABLE_LDAP`                                            | persistent-seed / db-admin with startup import caveat | `false`                                                            | public-config            | missing                 | `routers/auths.py` imports `ldap3` classes only when the initial value is true. Treat LDAP enablement as a startup-profile setting until an enable-after-start smoke test proves otherwise. |
| `LDAP_SERVER_LABEL`                                      | persistent-seed / db-admin                            | `LDAP Server`                                                      | public-config            | missing                 | UI/admin display name only.                                                                                                                                                                 |
| `LDAP_SERVER_HOST`, `LDAP_SERVER_PORT`                   | persistent-seed / db-admin                            | `localhost`, `389`                                                 | sensitive-config         | missing                 | Host/port are admin-updateable but should be approved through deployment/profile governance.                                                                                                |
| `LDAP_ATTRIBUTE_FOR_MAIL`, `LDAP_ATTRIBUTE_FOR_USERNAME` | persistent-seed / db-admin                            | `mail`, `uid`                                                      | identifier               | missing                 | Search and extraction depend on these names. Add directory fixture tests for each supported IdP profile.                                                                                    |
| `LDAP_APP_DN`, `LDAP_APP_PASSWORD`                       | persistent-seed / db-admin                            | unset                                                              | secret                   | missing                 | Bind credentials are required by the admin form. Store through secret management; avoid returning cleartext in admin-read APIs.                                                             |
| `LDAP_SEARCH_BASE`                                       | persistent-seed / db-admin                            | unset                                                              | sensitive-config         | missing                 | Required by admin validation and used as the user search base.                                                                                                                              |
| `LDAP_SEARCH_FILTER`                                     | persistent-seed / db-admin                            | unset; seeds from `LDAP_SEARCH_FILTER`, then `LDAP_SEARCH_FILTERS` | sensitive-config / alias | missing                 | Persistent key name is singular even though the runtime attribute is `LDAP_SEARCH_FILTERS`. Keep both names explicit until owner policy is set.                                             |
| `LDAP_SEARCH_FILTERS`                                    | alias / restart seed                                  | fallback for `LDAP_SEARCH_FILTER`                                  | alias                    | missing                 | Runtime attribute name and legacy env fallback. Do not use as the primary external example without an alias decision.                                                                       |
| `LDAP_USE_TLS`                                           | persistent-seed / db-admin                            | `True`                                                             | public-config            | missing                 | Admin validation requires a certificate path when TLS is enabled. Env-seeded inconsistent values need startup smoke coverage.                                                               |
| `LDAP_CA_CERT_FILE`, `LDAP_CIPHERS`                      | persistent-seed / db-admin                            | CA unset; ciphers `ALL`                                            | sensitive-config         | missing                 | `LDAP_CA_CERT_FILE` should be a mounted trusted CA path. `ALL` is broad; production profile should specify an approved cipher policy.                                                       |

#### SCIM 2.0 Provisioning

| Key            | Lifecycle / mutability     | Default | Secret class  | Current deploy coverage                                | Production guidance                                                                                                                              |
| -------------- | -------------------------- | ------- | ------------- | ------------------------------------------------------ | ------------------------------------------------------------------------------------------------------------------------------------------------ |
| `SCIM_ENABLED` | persistent-seed / db-admin | `False` | public-config | env-example only                                       | Disabled endpoints return 404. Enabling should require bearer-token, provisioning, and deprovisioning smoke tests.                               |
| `SCIM_TOKEN`   | persistent-seed / db-admin | unset   | secret        | env-example only; missing from Helm Secret and Compose | Router fails closed with 401 when token is unset or wrong and uses constant-time comparison. Move to Helm/secret manager before production SCIM. |

Validation evidence:

- `config.py` defines OAuth, LDAP, and SCIM rows as `PersistentConfig` and builds `OAUTH_PROVIDERS` with
  `load_oauth_providers()`.
- `main.py` installs Authlib session middleware only when `OAUTH_PROVIDERS` is non-empty and exposes provider
  names through `/api/config`.
- `utils/oauth.py` enforces email domain allowlist, email-verified merge-by-email, role claim mapping, group
  synchronization, and no-redirect profile image fetch.
- `routers/auths.py` gates LDAP login on `ENABLE_LDAP`, validates LDAP admin config writes, and auto-provisions
  LDAP users after a successful bind.
- `routers/scim.py` gates every SCIM endpoint on `SCIM_ENABLED` and `SCIM_TOKEN`.
- `.env.example` exposes only `JWT_*` and SCIM rows from this enterprise-auth slice; inspected Compose/Helm
  templates do not expose OAuth, LDAP, or SCIM rows.

### Database

| Key                          | Lifecycle / mutability                  | Default                         | Secret class            | Current deploy coverage                           | Production guidance                                                               |
| ---------------------------- | --------------------------------------- | ------------------------------- | ----------------------- | ------------------------------------------------- | --------------------------------------------------------------------------------- |
| `DATABASE_URL`               | env-only + startup-validation / restart | `sqlite:///{DATA_DIR}/bcgpt.db` | secret/sensitive-config | helm-secret, compose with-db, settings validation | Production HA profile should use Postgres. SQLite is single-node/local posture.   |
| `DATABASE_SCHEMA`            | env-only / restart                      | unset                           | public-config           | missing                                           | PostgreSQL-only schema selector; document only for Postgres profiles.             |
| `DATABASE_POOL_SIZE`         | env-only / restart                      | `0`                             | public-config           | missing                                           | Tune for Postgres only after load profile is known.                               |
| `DATABASE_POOL_MAX_OVERFLOW` | env-only / restart                      | `0`                             | public-config           | missing                                           | Pair with pool size; avoid hidden connection exhaustion in multi-worker profiles. |
| `DATABASE_POOL_TIMEOUT`      | env-only / restart                      | `30`                            | public-config           | missing                                           | Production should align timeout with DB failover/health policy.                   |
| `DATABASE_POOL_RECYCLE`      | env-only / restart                      | `3600`                          | public-config           | missing                                           | Useful for managed DB idle connection handling; keep in deployment profile notes. |

Validation evidence:

- `settings.py` validates that `DATABASE_URL` is non-empty and starts with `sqlite://`, `postgresql://`, or
  `postgres://`.
- `env.py` normalizes `postgres://` to `postgresql://`.
- Compose with-db requires `POSTGRES_PASSWORD`, but app-level `BCGPT_SECRET_KEY` still defaults to empty if
  the host variable is not set.

### Redis And WebSocket

| Key                            | Lifecycle / mutability | Default                   | Secret class     | Current deploy coverage | Production guidance                                                                                         |
| ------------------------------ | ---------------------- | ------------------------- | ---------------- | ----------------------- | ----------------------------------------------------------------------------------------------------------- |
| `REDIS_URL`                    | env-only / restart     | empty                     | sensitive-config | compose with-db         | Enables generic Redis usage where code consumes it, but does not by itself enable cross-instance Socket.IO. |
| `REDIS_SENTINEL_HOSTS`         | env-only / restart     | empty                     | sensitive-config | missing                 | Use only with Sentinel profile and document failover smoke.                                                 |
| `REDIS_SENTINEL_PORT`          | env-only / restart     | `26379`                   | public-config    | missing                 | Pair with Sentinel hosts.                                                                                   |
| `ENABLE_WEBSOCKET_SUPPORT`     | env-only / restart     | `True`                    | public-config    | missing                 | Disabling falls back to polling behavior; needs realtime smoke if changed.                                  |
| `WEBSOCKET_MANAGER`            | env-only / restart     | empty/in-process          | public-config    | missing                 | Multi-replica profile must set `redis`; `REDIS_URL` alone is not enough.                                    |
| `WEBSOCKET_REDIS_URL`          | env-only / restart     | falls back to `REDIS_URL` | sensitive-config | missing                 | Required when `WEBSOCKET_MANAGER=redis` unless `REDIS_URL` is intentionally reused.                         |
| `WEBSOCKET_REDIS_LOCK_TIMEOUT` | env-only / restart     | `60`                      | public-config    | missing                 | Tune with reconnect and room membership behavior.                                                           |
| `WEBSOCKET_SENTINEL_HOSTS`     | env-only / restart     | empty                     | sensitive-config | missing                 | Sentinel-specific Socket.IO manager profile.                                                                |
| `WEBSOCKET_SENTINEL_PORT`      | env-only / restart     | `26379`                   | public-config    | missing                 | Pair with Sentinel hosts.                                                                                   |
| `ENABLE_REALTIME_CHAT_SAVE`    | env-only / restart     | `False`                   | public-config    | missing                 | This is realtime durability posture, not generic chat setting. Coordinate with realtime/state plan.         |

Deployment guidance:

- Compose with-db includes Redis and sets `REDIS_URL`, but does not set `WEBSOCKET_MANAGER=redis`.
- Helm values do not expose WebSocket manager keys.
- Multi-replica Kubernetes must not be documented as horizontally safe until `WEBSOCKET_MANAGER=redis` and
  reconnection/room rejoin smoke tests are defined.

### Container, Runtime, Build Provenance

| Key                   | Lifecycle / mutability      | Default                                            | Secret class          | Current deploy coverage             | Production guidance                                                                         |
| --------------------- | --------------------------- | -------------------------------------------------- | --------------------- | ----------------------------------- | ------------------------------------------------------------------------------------------- |
| `DOCKER`              | env-only / restart          | `False`                                            | public-config         | dockerfile, helm configmap template | Container image sets `true`; local dev usually false.                                       |
| `DATA_DIR`            | env-only / restart          | `backend/data` or package data path                | sensitive-config path | dockerfile, compose dev             | Owns DB/uploads/cache. Must map to persistent volume or external storage profile.           |
| `FRONTEND_BUILD_DIR`  | env-only / restart          | project `build`                                    | public-config path    | dockerfile, compose dev             | Must point to built frontend assets in packaged deployment.                                 |
| `PORT`                | startup-validation / deploy | `8090`                                             | public-config         | dockerfile, helm configmap template | Service/health probes must match.                                                           |
| `HOST`                | startup-validation / deploy | `0.0.0.0`                                          | public-config         | dockerfile                          | Container should keep `0.0.0.0`; local host binding may differ.                             |
| `WORKERS`             | startup-validation / deploy | `1`                                                | public-config         | missing                             | Multi-worker/multi-replica changes need DB migration and Socket.IO state review.            |
| `ENV`                 | env-only / restart          | `dev`                                              | public-config         | missing                             | Production should set explicit `prod` after confirming startup validation/feature defaults. |
| `BCGPT_BUILD_HASH`    | env-only / restart          | `dev-build`                                        | identifier            | missing                             | Backend-side build hash; should be injected from source commit in release images.           |
| `APP_BUILD_HASH`      | build-time                  | `dev-build` fallback through `VITE_APP_BUILD_HASH` | identifier            | missing                             | Must be injected during frontend build for production release evidence.                     |
| `VITE_APP_VERSION`    | build-time define           | package version                                    | identifier            | vite define only                    | UI version display; not a runtime env var.                                                  |
| `VITE_APP_BUILD_HASH` | build-time define           | `APP_BUILD_HASH` or `dev-build`                    | identifier            | vite define only                    | UI build hash display; release gate should fail or warn on `dev-build` in production image. |

### Model Providers And Auxiliary Credentials

Most provider rows below are `PersistentConfig`: the env value seeds the database-backed runtime config, and
admin APIs can later change the active value. Treat provider keys returned by admin config APIs as secret
reads until a masking/write-only policy is designed.

#### Chat LLM Providers And Routing

| Key                         | Lifecycle / mutability     | Default / alias                                    | Secret class     | Current deploy coverage           | Production guidance                                                                                                                   |
| --------------------------- | -------------------------- | -------------------------------------------------- | ---------------- | --------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------- |
| `ENABLE_OLLAMA_API`         | persistent-seed / db-admin | `True`                                             | public-config    | missing                           | Disabling removes Ollama models from aggregation. Multi-instance behavior depends on `OLLAMA_BASE_URLS`.                              |
| `OLLAMA_BASE_URL`           | alias / restart            | empty; falls back from `OLLAMA_API_BASE_URL`       | sensitive-config | env-example, helm-env, compose    | Single endpoint convenience value that seeds `OLLAMA_BASE_URLS`. Prefer documenting `OLLAMA_BASE_URLS` for multi-instance production. |
| `OLLAMA_API_BASE_URL`       | env-only alias / restart   | `http://localhost:11434/api`                       | sensitive-config | missing                           | Legacy/API-path form that is normalized to `OLLAMA_BASE_URL` by stripping `/api` when needed.                                         |
| `OLLAMA_BASE_URLS`          | persistent-seed / db-admin | semicolon split from `OLLAMA_BASE_URL`             | sensitive-config | missing                           | Canonical multi-instance list. Changing env after first startup may not override DB/admin config.                                     |
| `OLLAMA_API_CONFIGS`        | persistent-seed / db-admin | `{}`                                               | sensitive-config | missing                           | Holds per-instance options such as key-bearing configs, model ids, tags, and prefixes. Treat as secret-capable.                       |
| `ENABLE_OPENAI_API`         | persistent-seed / db-admin | `True`                                             | public-config    | missing                           | Controls OpenAI-compatible server-side model aggregation and routing.                                                                 |
| `OPENAI_API_KEY`            | alias / restart            | empty                                              | secret           | env-example, helm-secret, compose | Single-key seed for `OPENAI_API_KEYS`. Do not rely on this for multi-provider rotation.                                               |
| `OPENAI_API_KEYS`           | persistent-seed / db-admin | semicolon split from `OPENAI_API_KEY`              | secret           | missing                           | Canonical key list aligned by index with `OPENAI_API_BASE_URLS`; admin `/openai/config` currently returns values.                     |
| `OPENAI_API_BASE_URL`       | alias / restart            | `https://api.openai.com/v1` when empty             | sensitive-config | env-example, helm-env             | Single URL seed for `OPENAI_API_BASE_URLS`; OpenAI-compatible providers share this path.                                              |
| `OPENAI_API_BASE_URLS`      | persistent-seed / db-admin | semicolon split from `OPENAI_API_BASE_URL`         | sensitive-config | missing                           | Canonical URL list. Release smoke should verify key/url length alignment and model-list behavior.                                     |
| `OPENAI_API_CONFIGS`        | persistent-seed / db-admin | `{}`                                               | sensitive-config | missing                           | Per-connection config can affect model ids, prefixes, tags, and enablement; needs export/import secret policy.                        |
| `ENABLE_GEMINI_API`         | persistent-seed / db-admin | `False`                                            | public-config    | missing                           | Native Gemini adapter is opt-in and model aggregation checks this flag.                                                               |
| `GEMINI_API_KEY`            | alias / restart            | empty                                              | secret           | missing                           | Single-key alias that seeds `GEMINI_API_KEYS`.                                                                                        |
| `GEMINI_API_KEYS`           | persistent-seed / db-admin | semicolon split from `GEMINI_API_KEY`              | secret           | missing                           | Admin config endpoint currently returns key values. Rotation and masking policy are not documented yet.                               |
| `GEMINI_API_BASE_URL`       | persistent-seed / db-admin | `https://generativelanguage.googleapis.com/v1beta` | sensitive-config | missing                           | Native adapter default. Include in provider capability and regional/privacy review.                                                   |
| `GEMINI_API_CONFIGS`        | persistent-seed / db-admin | `{}`                                               | sensitive-config | missing                           | Secret-capable provider config object. Needs schema and masking policy before broad export/import.                                    |
| `ENABLE_CLAUDE_API`         | persistent-seed / db-admin | `False`                                            | public-config    | missing                           | Native Claude adapter is opt-in and model aggregation checks this flag.                                                               |
| `CLAUDE_API_KEY`            | alias / restart            | empty                                              | secret           | missing                           | Single-key alias that seeds `CLAUDE_API_KEYS`.                                                                                        |
| `CLAUDE_API_KEYS`           | persistent-seed / db-admin | semicolon split from `CLAUDE_API_KEY`              | secret           | missing                           | Admin config endpoint currently returns key values. Rotation and masking policy are not documented yet.                               |
| `CLAUDE_API_BASE_URL`       | persistent-seed / db-admin | `https://api.anthropic.com`                        | sensitive-config | missing                           | Native adapter default. Include in provider capability and regional/privacy review.                                                   |
| `CLAUDE_API_CONFIGS`        | persistent-seed / db-admin | `{}`                                               | sensitive-config | missing                           | Secret-capable provider config object. Needs schema and masking policy before broad export/import.                                    |
| `LITELLM_GATEWAY_ENABLED`   | persistent-seed / db-admin | `False`                                            | public-config    | missing                           | Non-streaming chat tries LiteLLM first when enabled, then falls back. Audit must record route taken.                                  |
| `LITELLM_FALLBACK_MODEL`    | persistent-seed / db-admin | empty                                              | public-config    | missing                           | Fallback behavior can obscure provider accountability unless logged with model/provider route metadata.                               |
| `LITELLM_NUM_RETRIES`       | persistent-seed / db-admin | `3`                                                | public-config    | missing                           | Coordinate with upstream provider retry/cost policy.                                                                                  |
| `LITELLM_TIMEOUT`           | persistent-seed / db-admin | `60`                                               | public-config    | missing                           | Separate from global `AIOHTTP_CLIENT_TIMEOUT`; document per-provider timeout expectations.                                            |
| `ENABLE_DIRECT_CONNECTIONS` | persistent-seed / db-admin | `True`                                             | public-config    | missing                           | Server feature flag only. User `directConnections` URL/key settings are browser-owned and are not deployment env.                     |

Validation evidence:

- `main.py::_apply_config()` transfers these `PersistentConfig` values into `app.state.config`.
- OpenAI/Ollama/Gemini/Claude config endpoints are admin-gated, but admin reads currently include key values.
- Model aggregation uses OpenAI/Ollama routers and Gemini/Claude providers directly; completion routing can
  additionally try LiteLLM and browser direct bridge paths.

#### RAG, Image, And Audio Provider Surfaces

| Key                                    | Lifecycle / mutability     | Default / alias                                                                     | Secret class     | Current deploy coverage  | Production guidance                                                                                                            |
| -------------------------------------- | -------------------------- | ----------------------------------------------------------------------------------- | ---------------- | ------------------------ | ------------------------------------------------------------------------------------------------------------------------------ |
| `RAG_EMBEDDING_MODEL`                  | persistent-seed / db-admin | `sentence-transformers/all-MiniLM-L6-v2`                                            | public-config    | helm-env                 | Model selection affects retrieval quality and local/downloaded model footprint.                                                |
| `RAG_EMBEDDING_MODEL_URI`              | persistent-seed / db-admin | empty                                                                               | sensitive-config | missing                  | External embedding endpoint/model artifact URI. Needs storage/network/secret owner review.                                     |
| `RAG_EMBEDDING_MODEL_API_KEY`          | persistent-seed / db-admin | empty                                                                               | secret           | helm-secret              | Separate from OpenAI chat key. Treat as embedding-provider credential.                                                         |
| `RAG_OPENAI_API_BASE_URL`              | persistent-seed / db-admin | falls back to `OPENAI_API_BASE_URL`                                                 | sensitive-config | missing                  | Embedding provider can drift from chat provider; document intended separation.                                                 |
| `RAG_OPENAI_API_KEY`                   | persistent-seed / db-admin | falls back to resolved `OPENAI_API_KEY`                                             | secret           | missing                  | If omitted, embedding may reuse chat OpenAI key; rotation runbooks must make that explicit.                                    |
| `RAG_OLLAMA_BASE_URL`                  | persistent-seed / db-admin | falls back to `OLLAMA_BASE_URL`                                                     | sensitive-config | missing                  | Required when `RAG_EMBEDDING_ENGINE=ollama` uses a different endpoint than chat Ollama.                                        |
| `RAG_OLLAMA_API_KEY`                   | persistent-seed / db-admin | empty                                                                               | secret           | missing                  | Optional credential for Ollama-compatible embedding endpoint.                                                                  |
| `RAG_EMBEDDING_BATCH_SIZE`             | persistent-seed / db-admin | `RAG_EMBEDDING_BATCH_SIZE` or legacy `RAG_EMBEDDING_OPENAI_BATCH_SIZE`, default `1` | public-config    | missing                  | Cost/latency control for embedding endpoints; document per-provider limits.                                                    |
| `IMAGE_GENERATION_ENGINE`              | persistent-seed / db-admin | `openai`                                                                            | public-config    | missing                  | Selects OpenAI, Gemini, AUTOMATIC1111, or ComfyUI paths; engine-specific required keys differ.                                 |
| `ENABLE_IMAGE_GENERATION`              | persistent-seed / db-admin | `False` from empty default                                                          | public-config    | missing                  | Production should not enable until engine key/url requirements and cost controls are documented.                               |
| `IMAGES_OPENAI_API_BASE_URL`           | persistent-seed / db-admin | falls back to `OPENAI_API_BASE_URL`                                                 | sensitive-config | missing                  | Image generation can intentionally use a different OpenAI-compatible endpoint than chat.                                       |
| `IMAGES_OPENAI_API_KEY`                | persistent-seed / db-admin | falls back to resolved `OPENAI_API_KEY`                                             | secret           | missing                  | If omitted, image generation may reuse chat key; cost/rotation policy must state this.                                         |
| `IMAGES_GEMINI_API_BASE_URL`           | persistent-seed / db-admin | falls back to `GEMINI_API_BASE_URL`                                                 | sensitive-config | missing                  | Gemini image endpoint should be verified separately from Gemini chat model listing.                                            |
| `IMAGES_GEMINI_API_KEY`                | persistent-seed / db-admin | falls back to `GEMINI_API_KEY`                                                      | secret           | missing                  | If Gemini image and chat credentials differ, admin runbook must keep them separate.                                            |
| `AUTOMATIC1111_BASE_URL`               | persistent-seed / db-admin | empty                                                                               | sensitive-config | env-example comment only | Required for AUTOMATIC1111 engine. Add SSRF/network placement review before production exposure.                               |
| `AUTOMATIC1111_API_AUTH`               | persistent-seed / db-admin | empty                                                                               | secret           | missing                  | Basic-auth style credential; must not be exported or logged in clear text.                                                     |
| `COMFYUI_BASE_URL`                     | persistent-seed / db-admin | empty                                                                               | sensitive-config | missing                  | Required for ComfyUI engine. Needs queue/progress/error smoke before production enablement.                                    |
| `COMFYUI_API_KEY`                      | persistent-seed / db-admin | empty                                                                               | secret           | missing                  | Optional ComfyUI credential; classify with other image provider secrets.                                                       |
| `COMFYUI_WORKFLOW`                     | persistent-seed / db-admin | bundled default workflow                                                            | sensitive-config | missing                  | Workflow JSON is operational config and may contain endpoint/model assumptions.                                                |
| `COMFYUI_WORKFLOW_NODES`               | persistent-seed / db-admin | empty list                                                                          | sensitive-config | missing                  | Source currently uses the same persistent key string as `COMFYUI_WORKFLOW`; track as drift before full image config hardening. |
| `DEEPGRAM_API_KEY`                     | persistent-seed / db-admin | empty                                                                               | secret           | missing                  | Required when STT engine is Deepgram.                                                                                          |
| `AUDIO_STT_OPENAI_API_BASE_URL`        | persistent-seed / db-admin | falls back to `OPENAI_API_BASE_URL`                                                 | sensitive-config | missing                  | Runtime attribute is exposed as `STT_OPENAI_API_BASE_URL`; document env-to-runtime alias.                                      |
| `AUDIO_STT_OPENAI_API_KEY`             | persistent-seed / db-admin | falls back to resolved `OPENAI_API_KEY`                                             | secret           | missing                  | Runtime attribute is exposed as `STT_OPENAI_API_KEY`; may reuse chat key if omitted.                                           |
| `AUDIO_STT_ENGINE`                     | persistent-seed / db-admin | empty/local                                                                         | public-config    | missing                  | Engine choice determines whether Whisper/local, OpenAI, or Deepgram credentials are required.                                  |
| `AUDIO_STT_MODEL`                      | persistent-seed / db-admin | empty                                                                               | public-config    | missing                  | Helm exposes `WHISPER_MODEL`, but this env row is separate from local Whisper model defaults.                                  |
| `AUDIO_TTS_OPENAI_API_BASE_URL`        | persistent-seed / db-admin | falls back to `OPENAI_API_BASE_URL`                                                 | sensitive-config | missing                  | Runtime attribute is exposed as `TTS_OPENAI_API_BASE_URL`; document env-to-runtime alias.                                      |
| `AUDIO_TTS_OPENAI_API_KEY`             | persistent-seed / db-admin | falls back to resolved `OPENAI_API_KEY`                                             | secret           | missing                  | Runtime attribute is exposed as `TTS_OPENAI_API_KEY`; may reuse chat key if omitted.                                           |
| `AUDIO_TTS_API_KEY`                    | persistent-seed / db-admin | empty                                                                               | secret           | missing                  | Used by non-OpenAI TTS engines such as ElevenLabs/Azure speech paths.                                                          |
| `AUDIO_TTS_ENGINE`                     | persistent-seed / db-admin | empty/local                                                                         | public-config    | missing                  | Engine choice determines OpenAI, ElevenLabs, Azure, transformers, or browser/local behavior.                                   |
| `AUDIO_TTS_MODEL`                      | persistent-seed / db-admin | `tts-1`                                                                             | public-config    | missing                  | Provider-specific model id; needs capability and pricing policy.                                                               |
| `AUDIO_TTS_VOICE`                      | persistent-seed / db-admin | `alloy`                                                                             | public-config    | missing                  | Provider-specific voice id; verify UI/API compatibility per engine.                                                            |
| `AUDIO_TTS_AZURE_SPEECH_REGION`        | persistent-seed / db-admin | `eastus`                                                                            | sensitive-config | missing                  | Azure regional routing and data residency decision.                                                                            |
| `AUDIO_TTS_AZURE_SPEECH_OUTPUT_FORMAT` | persistent-seed / db-admin | `audio-24khz-160kbitrate-mono-mp3`                                                  | public-config    | missing                  | Audio format affects client playback and bandwidth budget.                                                                     |

Deployment guidance:

- `.env.example`, Compose, and Helm do not expose Gemini, Claude, LiteLLM, direct-connection flag, image
  provider, or audio provider credential rows.
- Helm exposes `RAG_EMBEDDING_MODEL` and `RAG_EMBEDDING_MODEL_API_KEY`, but not the RAG OpenAI/Ollama URL/key
  rows that embedding runtime can use.
- Provider credentials require a separate secret-read/masking/export policy because current admin config
  endpoints return full values for admins.

### Search And External Web Retrieval Providers

These rows cover web-search engines, outbound page-loading engines, and the RAG web-search posture controls.
Most are `PersistentConfig` rows: environment values seed DB-backed admin config, and subsequent runtime values
can come from the admin RAG settings API. The admin RAG config response currently serializes provider secret
fields, so this surface should be treated as an admin secret-read surface until masked/write-only semantics are
implemented.

#### Search Posture And Query Controls

| Key                                         | Lifecycle / mutability       | Default              | Secret class     | Current deploy coverage | Production guidance                                                                                                                                                                                                                                    |
| ------------------------------------------- | ---------------------------- | -------------------- | ---------------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `ENABLE_RAG_WEB_SEARCH`                     | persistent-seed / db-admin   | `False`              | public-config    | missing                 | Global web-search feature switch. Pair with user permission `features.web_search`, provider key smoke, and outbound network policy.                                                                                                                    |
| `RAG_WEB_SEARCH_ENGINE`                     | persistent-seed / db-admin   | unset                | identifier       | missing                 | Must match one of the engine ids used by backend/frontend: `naver`, `searxng`, `google_pse`, `brave`, `kagi`, `mojeek`, `bocha`, `serpstack`, `serper`, `serply`, `searchapi`, `serpapi`, `duckduckgo`, `tavily`, `jina`, `bing`, `exa`, `perplexity`. |
| `BYPASS_WEB_SEARCH_EMBEDDING_AND_RETRIEVAL` | persistent-seed / db-admin   | `False`              | public-config    | missing                 | When true, loaded web content is returned directly instead of being embedded into a collection. Treat as a privacy and prompt-context policy decision.                                                                                                 |
| `RAG_WEB_SEARCH_RESULT_COUNT`               | persistent-seed / db-admin   | `3`                  | public-config    | missing                 | Caps search result count before page loading. Tune with provider quota and page-fetch latency.                                                                                                                                                         |
| `RAG_WEB_SEARCH_CONCURRENT_REQUESTS`        | persistent-seed / db-admin   | `10`                 | public-config    | missing                 | Used as page-loader request rate/concurrency control. Needs outbound quota/load testing before increasing.                                                                                                                                             |
| `RAG_WEB_SEARCH_TRUST_ENV`                  | persistent-seed / db-admin   | `False`              | sensitive-config | missing                 | Lets web loaders honor `http_proxy`/`https_proxy` env. Enable only when proxy ownership, egress logging, and SSRF posture are documented.                                                                                                              |
| `RAG_WEB_SEARCH_DOMAIN_FILTER_LIST`         | persistent config / db-admin | `[]`; not env-seeded | public-config    | missing                 | Domain suffix allowlist for provider results. It filters returned URLs but is not a full egress allowlist; keep separate network controls.                                                                                                             |
| `RAG_WEB_SEARCH_QUERY_REWRITE_ENABLED`      | persistent-seed / db-admin   | `True`               | public-config    | missing                 | Query rewrite is enabled by default for web search. It should be covered by privacy/audit policy because user query text can be sent to the selected rewrite model.                                                                                    |
| `RAG_WEB_SEARCH_QUERY_REWRITE_MODEL`        | persistent-seed / db-admin   | unset                | identifier       | missing                 | Optional model override for web-search query rewriting. Align with model/provider governance and token budget policy.                                                                                                                                  |
| `RAG_WEB_SEARCH_CONCURRENT_QUERIES`         | persistent-seed / db-admin   | `True`               | public-config    | missing                 | Enables concurrent rewritten query execution. Tune with provider quota and failure aggregation behavior.                                                                                                                                               |

#### Search Engine Credentials

| Key(s)                                                             | Lifecycle / mutability          | Default                                                          | Secret class                                                  | Current deploy coverage | Production guidance                                                                                                                                                                    |
| ------------------------------------------------------------------ | ------------------------------- | ---------------------------------------------------------------- | ------------------------------------------------------------- | ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `SEARXNG_QUERY_URL`                                                | persistent-seed / db-admin      | unset                                                            | sensitive-config                                              | missing                 | Required for `searxng`; no API key row exists. Treat URL as an internal/external service dependency and include health/egress smoke.                                                   |
| `GOOGLE_PSE_API_KEY`, `GOOGLE_PSE_ENGINE_ID`                       | persistent-seed / db-admin      | unset                                                            | secret for API key; identifier for engine id                  | missing                 | Required together for `google_pse`. Add quota and custom-search-engine ownership to deployment profile.                                                                                |
| `NAVER_CLIENT_ID`, `NAVER_CLIENT_SECRET`, `NAVER_SEARCH_ENDPOINTS` | persistent-seed / db-admin      | id/secret unset; endpoints `webkr`                               | secret for client secret; identifier/public-config for others | missing                 | Required id+secret for `naver`. Endpoint list supports comma-separated `webkr`, `news`, `blog`, `cafearticle`, `kin`; partial endpoint failures are summarized by tests.               |
| `BRAVE_SEARCH_API_KEY`                                             | persistent-seed / db-admin      | unset                                                            | secret                                                        | missing                 | Required for `brave`.                                                                                                                                                                  |
| `KAGI_SEARCH_API_KEY`                                              | persistent-seed / db-admin      | unset                                                            | secret                                                        | missing                 | Required for `kagi`.                                                                                                                                                                   |
| `MOJEEK_SEARCH_API_KEY`                                            | persistent-seed / db-admin      | unset                                                            | secret                                                        | missing                 | Required for `mojeek`.                                                                                                                                                                 |
| `BOCHA_SEARCH_API_KEY`                                             | persistent-seed / db-admin      | unset                                                            | secret                                                        | missing                 | Required for `bocha`.                                                                                                                                                                  |
| `SERPSTACK_API_KEY`, `SERPSTACK_HTTPS`                             | persistent-seed / db-admin      | key unset; HTTPS `True`                                          | secret for API key; public-config for HTTPS switch            | missing                 | Required key for `serpstack`. Production should keep HTTPS enabled.                                                                                                                    |
| `SERPER_API_KEY`                                                   | persistent-seed / db-admin      | unset                                                            | secret                                                        | missing                 | Required for `serper`.                                                                                                                                                                 |
| `SERPLY_API_KEY`                                                   | persistent-seed / db-admin      | unset                                                            | secret                                                        | missing                 | Required for `serply`.                                                                                                                                                                 |
| `TAVILY_API_KEY`, `TAVILY_EXTRACT_DEPTH`                           | persistent-seed / db-admin      | key unset; extract depth `basic`                                 | secret for API key; public-config for depth                   | missing                 | Key is used by both `tavily` search and the `tavily` web loader. Coordinate quota/cost policy across both paths.                                                                       |
| `SEARCHAPI_API_KEY`, `SEARCHAPI_ENGINE`                            | persistent-seed / db-admin      | unset                                                            | secret for API key; identifier for engine                     | missing                 | Required key for `searchapi`; engine is provider-specific and should be pinned in deployment runbooks.                                                                                 |
| `SERPAPI_API_KEY`, `SERPAPI_ENGINE`                                | persistent-seed / db-admin      | unset                                                            | secret for API key; identifier for engine                     | missing                 | Required key for `serpapi`; engine is provider-specific and should be pinned in deployment runbooks.                                                                                   |
| `JINA_API_KEY`                                                     | persistent-seed / db-admin      | unset                                                            | secret                                                        | missing                 | Used by `jina`; dispatcher does not pre-check this key before calling the provider function, so smoke tests should verify missing/invalid-key behavior.                                |
| `BING_SEARCH_V7_ENDPOINT`, `BING_SEARCH_V7_SUBSCRIPTION_KEY`       | persistent-seed / db-admin      | endpoint `https://api.bing.microsoft.com/v7.0/search`; key unset | sensitive-config endpoint; secret key                         | missing                 | Used by `bing`; dispatcher does not pre-check the subscription key before outbound request.                                                                                            |
| `EXA_API_KEY`                                                      | persistent-seed / db-admin      | unset                                                            | secret                                                        | missing                 | Used by `exa`; provider function returns an empty result set on errors, so monitor no-result rates.                                                                                    |
| `PERPLEXITY_API_KEY`                                               | persistent-seed / db-admin      | unset                                                            | secret                                                        | missing                 | Used by `perplexity`; provider function returns an empty result set on errors and returns citation URLs from an LLM response. Treat as model-provider spend and citation quality risk. |
| `duckduckgo` engine                                                | external library path / runtime | no API key                                                       | public-config                                                 | no env needed           | Uses the `ddgs` library without an API key. Still needs outbound network, privacy, rate-limit, and result-quality smoke tests.                                                         |

#### Web Loader, YouTube, And External Fetch Controls

| Key                                                   | Lifecycle / mutability     | Default                                         | Secret class                                       | Current deploy coverage | Production guidance                                                                                                                                                      |
| ----------------------------------------------------- | -------------------------- | ----------------------------------------------- | -------------------------------------------------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| `ENABLE_RAG_WEB_LOADER_SSL_VERIFICATION`              | persistent-seed / db-admin | `True`                                          | public-config                                      | missing                 | Despite the UI label wording, backend passes this to `verify_ssl`. Production should keep verification enabled unless a documented internal CA/profile exists.           |
| `RAG_WEB_LOADER_ENGINE`                               | persistent-seed / db-admin | `safe_web`                                      | identifier                                         | missing                 | Selects `safe_web`, `playwright`, `firecrawl`, or `tavily` loader. Unknown values fall back through a defaultdict to `SafeWebBaseLoader`; document intended values only. |
| `PLAYWRIGHT_WS_URI`, `PLAYWRIGHT_TIMEOUT`             | persistent-seed / db-admin | URI unset; timeout `10` seconds                 | sensitive-config URI; public-config timeout        | missing                 | Used when loader engine is `playwright`. Treat remote browser endpoint as high-risk outbound infrastructure.                                                             |
| `FIRECRAWL_API_KEY`, `FIRECRAWL_API_BASE_URL`         | persistent-seed / db-admin | key unset; base URL `https://api.firecrawl.dev` | secret key; sensitive-config URL                   | missing                 | Used when loader engine is `firecrawl`. Move key to secret manager and smoke test base URL/timeout behavior.                                                             |
| `YOUTUBE_LOADER_LANGUAGE`, `YOUTUBE_LOADER_PROXY_URL` | persistent-seed / db-admin | language `en`; proxy unset                      | public-config language; sensitive-config proxy URL | missing                 | YouTube ingestion uses this loader config. Proxy URL may contain credentials; classify as secret if credentials are embedded.                                            |

Validation evidence:

- `config.py` defines the web-search and web-loader rows as `PersistentConfig`.
- `main.py` transfers these rows into `app.state.config`.
- `routers/retrieval.py` serializes and updates web-search provider settings through the admin RAG config API
  and dispatches `/process/web/search` to the selected engine.
- `src/lib/components/admin/Settings/WebSearch.svelte` exposes the 18 engine ids and uses `SensitiveInput`
  for many provider credential fields, but backend admin reads still return the configured values.
- `retrieval/web/utils.py` selects `safe_web`, `playwright`, `firecrawl`, or `tavily` page loaders after
  search results produce URLs.
- Current unit tests cover Naver failure aggregation and generic retrieval merge behavior; they do not prove
  every provider's credential, quota, or real-network behavior.
- Inspected `.env.example`, Compose, and Helm templates do not expose the search provider, web-loader, or
  YouTube proxy rows.

### Advanced RAG And Agent Quality Controls

These rows cover retrieval-quality behavior, answer-evaluation toggles, graph/context retrieval, multi-agent
orchestration, workflow execution, and agent quality checks. Most rows are `PersistentConfig` seeds, so the
environment value is a bootstrap/default and the active value can later come from DB-backed admin config.
This section intentionally separates "row exists" from "production effect is proven"; several features are
global-only, log-only, endpoint-only, or exposed through a narrower admin surface than the config module defines.

#### Retrieval Defaults, Reranking, And Templates

| Key(s)                                                                          | Lifecycle / mutability     | Default / alias                                              | Secret class                                       | Current deploy coverage             | Production guidance                                                                                                                     |
| ------------------------------------------------------------------------------- | -------------------------- | ------------------------------------------------------------ | -------------------------------------------------- | ----------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- |
| `BYPASS_EMBEDDING_AND_RETRIEVAL`                                                | persistent-seed / db-admin | `False`                                                      | public-config                                      | missing                             | Bypasses normal embedding/retrieval paths. Treat as a break-glass or test profile flag, not a production optimization.                  |
| `RAG_TOP_K`, `RAG_TOP_K_RERANKER`, `RAG_RELEVANCE_THRESHOLD`                    | persistent-seed / db-admin | `6`, `10`, `0.2`                                             | public-config                                      | missing                             | Core recall/precision controls. Tune with golden query sets, not only latency.                                                          |
| `ENABLE_RAG_HYBRID_SEARCH`, `RAG_FULL_CONTEXT`                                  | persistent-seed / db-admin | `False`, `False`                                             | public-config                                      | missing                             | Hybrid/full-context modes change retrieval scope and token cost. Document per-deployment cost and data-boundary expectations.           |
| `RAG_TEMPLATE`                                                                  | persistent-seed / db-admin | default RAG prompt template                                  | sensitive-config                                   | missing                             | Template changes can affect citation behavior and leakage posture; keep versioned in release evidence.                                  |
| `RAG_RERANKING_MODEL`, `RAG_RERANKING_MODEL_URI`, `RAG_RERANKING_MODEL_API_KEY` | persistent-seed / db-admin | unset                                                        | secret for API key; sensitive-config for model/URI | `RAG_RERANKING_MODEL` helm-env only | Reranker model and artifact URI can add network/model-cache risk. API key belongs in Secret storage if used.                            |
| `RAG_RERANKING_MODEL_AUTO_UPDATE`, `RAG_RERANKING_MODEL_TRUST_REMOTE_CODE`      | env-only / restart         | auto-update `True` unless offline; trust remote code `False` | public-config                                      | missing                             | Auto-update and remote-code trust affect supply-chain posture. Regulated profiles should pin artifacts and leave remote-code trust off. |

#### Pre/Post Retrieval Enhancements

| Key(s)                                                                                                                      | Lifecycle / mutability     | Default / alias                                 | Secret class                     | Current deploy coverage | Production guidance                                                                                                                                            |
| --------------------------------------------------------------------------------------------------------------------------- | -------------------------- | ----------------------------------------------- | -------------------------------- | ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `RAG_HYDE_ENABLED`, `RAG_HYDE_MODEL`                                                                                        | persistent-seed / db-admin | `False`, unset                                  | model id can be sensitive-config | missing                 | Global pre-retrieval hypothetical-answer generation. Adds provider cost and sends query-derived content to the selected model.                                 |
| `RAG_QUERY_EXPANSION_ENABLED`, `RAG_QUERY_EXPANSION_MAX`, `RAG_STEP_BACK_ENABLED`                                           | persistent-seed / db-admin | `False`, `3`, `False`                           | public-config                    | missing                 | Global pre-retrieval rewrites. Define per-agent/global precedence before exposing as product-level controls.                                                   |
| `RAG_RRF_K`, `RAG_RRF_VECTOR_WEIGHT`, `RAG_RRF_KEYWORD_WEIGHT`                                                              | persistent-seed / db-admin | `20`, `0.7`, `0.3`                              | public-config                    | missing                 | Reciprocal-rank fusion tuning. Needs benchmark coverage across vector and keyword result distributions.                                                        |
| `RAG_RULE_BASED_RERANKING_ENABLED`, `RAG_LLM_RERANKING_ENABLED`, `RAG_LLM_RERANKING_MODEL`                                  | persistent-seed / db-admin | `False`, `False`, unset                         | model id can be sensitive-config | missing                 | LLM reranking adds cost/privacy exposure. Keep separate from local/deterministic reranking in owner docs.                                                      |
| `RAG_CROSS_ENCODER_RERANKING_ENABLED`, `RAG_CROSS_ENCODER_MODEL`, `RAG_CROSS_ENCODER_MAX_LENGTH`, `RAG_CROSS_ENCODER_TOP_K` | persistent-seed / db-admin | `False`, `BAAI/bge-reranker-v2-m3`, `512`, `10` | model id can be sensitive-config | missing                 | Advanced RAG admin API/UI can update these rows. Validate model availability/cache and latency before enabling.                                                |
| `RAG_CRAG_ENABLED`, `RAG_CRAG_THRESHOLD_SUFFICIENT`, `RAG_CRAG_THRESHOLD_INSUFFICIENT`                                      | persistent-seed / db-admin | `False`, `65`, `40`                             | public-config                    | missing                 | Current middleware path logs CRAG quality; threshold rows were not observed as scorer inputs there. Do not claim corrective retrieval until wired and tested.  |
| `RAG_DOC_GRADING_ENABLED`, `RAG_EVIDENCE_RECONCILIATION_ENABLED`                                                            | persistent-seed / db-admin | `False`, `False`                                | public-config                    | missing                 | Document grading and reconciliation are useful quality signals; current reconciliation path is logging-only unless downstream answer/prompt handling is added. |
| `RAG_MMR_ENABLED`, `RAG_MMR_LAMBDA`                                                                                         | persistent-seed / db-admin | `False`, `0.7`                                  | public-config                    | env-example             | MMR changes diversity/precision tradeoff. Keep lambda tuning tied to retrieval-quality evaluation.                                                             |

#### Ingestion, Graph, Cache, And Advanced Retrieval

| Key(s)                                                                                                                                                                                                                             | Lifecycle / mutability     | Default / alias                                                    | Secret class                     | Current deploy coverage | Production guidance                                                                                                                                      |
| ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------- | ------------------------------------------------------------------ | -------------------------------- | ----------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `RAG_CHUNK_QUALITY_ENABLED`, `RAG_COLUMN_PROFILER_ENABLED`                                                                                                                                                                         | persistent-seed / db-admin | `False`, `False`                                                   | public-config                    | env-example             | Ingestion-time quality controls. Roll out with rejected-chunk metrics and fixture coverage for CSV/table workloads.                                      |
| `RAG_MULTI_HOP_ENABLED`, `RAG_MULTI_HOP_MAX_HOPS`, `RAG_MULTI_QUERY_WEIGHT_ORIGINAL`, `RAG_MULTI_QUERY_WEIGHT_EXPANDED`                                                                                                            | persistent-seed / db-admin | `False`, `3`, `1.0`, `0.5`                                         | public-config                    | missing                 | Config and helper code exist, but no main chat call path was confirmed. Treat as planned/experimental until end-to-end effect is proven.                 |
| `RAG_PARENT_CHILD_ENABLED`, `RAG_PARENT_CHILD_PARENT_SIZE`, `RAG_PARENT_CHILD_CHILD_SIZE`                                                                                                                                          | persistent-seed / db-admin | `False`, `2000`, `200`                                             | public-config                    | missing                 | Creates derived parent/child retrieval artifacts. Backup/delete/rebuild runbooks must cover derived stores.                                              |
| `RAG_SEMANTIC_CACHE_ENABLED`, `RAG_SEMANTIC_CACHE_THRESHOLD`, `RAG_SEMANTIC_CACHE_TTL`                                                                                                                                             | persistent-seed / db-admin | `False`, `0.95`, `3600`                                            | public-config                    | missing                 | Caching can improve latency but may replay stale or policy-changed context. Define invalidation and privacy posture before enabling.                     |
| `RAG_CONTEXTUAL_RETRIEVAL_ENABLED`, `RAG_CONTEXTUAL_RETRIEVAL_MODEL`, `RAG_CONTEXTUAL_RETRIEVAL_MAX_CONTEXT_TOKENS`, `RAG_CONTEXTUAL_RETRIEVAL_BATCH_SIZE`                                                                         | persistent-seed / db-admin | `False`, unset, `200`, `10`                                        | model id can be sensitive-config | missing                 | Advanced RAG admin API/UI can update these rows. The frontend fallback defaults differ for token/batch fields, so use backend values as canonical.       |
| `RAG_GRAPH_ENABLED`, `RAG_GRAPH_ENTITY_EXTRACTION_MODEL`, `RAG_GRAPH_MAX_ENTITIES`, `RAG_GRAPH_MAX_RELATIONS`, `RAG_GRAPH_COMMUNITY_DETECTION_ENABLED`, `RAG_GRAPH_MAX_HOPS`, `RAG_GRAPH_PPR_ENABLED`, `RAG_GRAPH_MIN_ENTITY_DOCS` | persistent-seed / db-admin | `False`, unset, `100`, `100`, `True`, `2`, `True`, `1`             | model id can be sensitive-config | missing                 | GraphRAG affects ingest and retrieval. Admin API/UI exposes only a subset; backup, delete, and rebuild semantics need lifecycle evidence.                |
| `RAG_EVALUATION_ENABLED`, `RAG_EVALUATION_MODEL`, `RAG_EVALUATION_METRICS`, `RAG_EVALUATION_LOG_RESULTS`                                                                                                                           | persistent-seed / db-admin | `False`, unset, `faithfulness,relevance,context_precision`, `True` | model id can be sensitive-config | missing                 | Main chat middleware was observed calling retrieval evaluation with LLM metrics disabled. Align metric vocabulary before relying on faithfulness scores. |
| `CONTENT_ISOLATION_ENABLED`, `CONTENT_ISOLATION_METHOD`, `QUERY_REWRITE_ENTITY_GUARD_ENABLED`                                                                                                                                      | persistent-seed / db-admin | `False`, `datamarking`, `True`                                     | public-config                    | env-example             | RAG safety controls. Keep prompt-injection/entity-preservation fixtures tied to retrieval and rewrite changes.                                           |

#### Agent, Workflow, Multi-Agent, And Quality Pipeline

| Key(s)                                                                                                                                                                     | Lifecycle / mutability     | Default / alias          | Secret class                     | Current deploy coverage                                                          | Production guidance                                                                                                                                       |
| -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------- | ------------------------ | -------------------------------- | -------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `AGENT_DEFAULT_AUTONOMY_LEVEL`, `AGENT_OPERATOR_MAX_TOOL_ITERATIONS`                                                                                                       | persistent-seed / db-admin | `assistant`, `10`        | public-config                    | missing; agent README only                                                       | Controls default autonomy and ReAct/tool-loop budget. Pair operator mode with tool permission and audit policy.                                           |
| `WORKFLOW_ENGINE_ENABLED`, `WORKFLOW_DEFAULT_TIMEOUT`, `WORKFLOW_NODE_TIMEOUT`                                                                                             | persistent-seed / db-admin | `True`, `300`, `60`      | public-config                    | missing; agent README only                                                       | Workflow execution needs node-level timeout, cancellation, and persistence expectations in the runbook.                                                   |
| `MULTI_AGENT_ENABLED`, `MULTI_AGENT_MAX_PARALLEL`, `MULTI_AGENT_DEBATE_ROUNDS`, `MULTI_AGENT_CONSENSUS_THRESHOLD`                                                          | persistent-seed / db-admin | `False`, `5`, `3`, `0.8` | public-config                    | missing; agent README only                                                       | Router gates multi-agent completions on the enable flag. Verify pattern/executor semantics before treating consensus threshold as a hard quality control. |
| `AGENT_QUALITY_PIPELINE_ENABLED`, `AGENT_QUALITY_SAMPLING_RATE`                                                                                                            | persistent-seed / db-admin | `False`, `0.1`           | public-config                    | missing; agent README only                                                       | Current source search found explicit endpoint/config usage, not automatic chat-path sampling. Treat as pipeline posture until sampling path is wired.     |
| `QUALITY_CLAIM_DECOMPOSITION_ENABLED`, `QUALITY_GROUNDING_ENABLED`, `QUALITY_DOC_GRADING_ENABLED`, `QUALITY_CITATION_AUDIT_ENABLED`, `QUALITY_DOC_STRUCTURE_SCORE_ENABLED` | persistent-seed / db-admin | all `False`              | public-config                    | `QUALITY_CITATION_AUDIT_ENABLED` env-example; others missing/agent README subset | The quality endpoint consumes all five toggles, but agent admin get/update currently omits citation audit and doc-structure score.                        |
| `QUALITY_DEFAULT_MODEL`, `QUALITY_CLAIM_MODEL`, `QUALITY_GROUNDING_MODEL`, `QUALITY_DOC_GRADING_MODEL`, `QUALITY_ENTAILMENT_MODEL`                                         | persistent-seed / db-admin | unset                    | model id can be sensitive-config | missing                                                                          | Model selection affects cost, data routing, and scoring behavior. Keep in provider governance and golden eval metadata.                                   |
| `LETTUCE_DETECT_ENABLED`, `LETTUCE_DETECT_THRESHOLD`                                                                                                                       | persistent-seed / db-admin | `False`, `0.7`           | public-config                    | missing                                                                          | Hallucination detector posture. Needs threshold calibration and false-positive review before block/score policy decisions.                                |

Validation evidence:

- `config.py` defines the advanced RAG rows as `PersistentConfig`; `agent/config.py` defines the agent,
  workflow, multi-agent, quality, and LettuceDetect rows.
- `main.py` transfers the advanced RAG and agent rows into `app.state.config`.
- `routers/retrieval.py` Advanced RAG config get/update covers only contextual retrieval, cross-encoder,
  GraphRAG, and RAG evaluation; frontend `AdvancedRag.svelte` mirrors that narrower admin surface.
- `utils/middleware.py` uses global HyDE/query-expansion/step-back before retrieval and several global
  reranking/evaluation/reconciliation hooks after retrieval. CRAG thresholds were not observed as middleware
  scorer inputs, and RAG evaluation is retrieval-only in the main chat path.
- `agent/routers/agents.py` exposes `/quality/evaluate` and an admin config API. The endpoint consumes
  citation-audit and doc-structure toggles, but the admin config get/update surface and frontend Agent settings
  omit those two flags.
- Focused deployment search found `.env.example` exposing only content isolation, MMR, citation audit,
  query-rewrite entity guard, chunk quality, and column profiler rows from this slice; Helm exposes only
  `RAG_RERANKING_MODEL`; Compose/Docker templates did not expose this advanced slice.

### Storage, Upload Guardrails, Vector Stores

Most storage backend rows are env-only values read at import/startup. The selected storage provider and vector
DB client are initialized as module-level singletons in current code paths, so changing these rows should be
treated as restart-required and should be paired with a smoke test.

#### Object Storage And Upload Paths

| Key                                   | Lifecycle / mutability | Default / alias                               | Secret class                   | Current deploy coverage                                      | Production guidance                                                                                            |
| ------------------------------------- | ---------------------- | --------------------------------------------- | ------------------------------ | ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------- |
| `STORAGE_PROVIDER`                    | env-only / restart     | `local`                                       | public-config                  | missing                                                      | Selects `local`, `s3`, `gcs`, or `azure`. Unsupported values fail provider initialization.                     |
| `UPLOAD_DIR`                          | derived path / restart | `DATA_DIR/uploads`                            | sensitive-config path          | dockerfile/compose/helm indirectly through `DATA_DIR` or PVC | Local provider writes here; object-store providers still stage uploads locally before remote upload.           |
| `S3_ACCESS_KEY_ID`                    | env-only / restart     | unset; falls back to AWS credential chain     | secret                         | missing                                                      | Use Secret or workload identity. Explicit key requires paired `S3_SECRET_ACCESS_KEY`.                          |
| `S3_SECRET_ACCESS_KEY`                | env-only / restart     | unset; falls back to AWS credential chain     | secret                         | missing                                                      | Never place in ConfigMap or `.env.example` as a real value.                                                    |
| `S3_REGION_NAME`                      | env-only / restart     | unset                                         | sensitive-config               | missing                                                      | Required for many AWS-compatible deployments; document alongside bucket region and endpoint.                   |
| `S3_BUCKET_NAME`                      | env-only / restart     | unset                                         | sensitive-config identifier    | missing                                                      | Required when `STORAGE_PROVIDER=s3`; preflight should verify bucket existence and permissions.                 |
| `S3_KEY_PREFIX`                       | env-only / restart     | empty                                         | public-config/sensitive-config | missing                                                      | Namespace prefix for uploaded objects; include tenant/environment naming policy before shared bucket use.      |
| `S3_ENDPOINT_URL`                     | env-only / restart     | unset                                         | sensitive-config               | missing                                                      | Needed for S3-compatible stores; include SSRF/network placement review for non-AWS endpoints.                  |
| `S3_USE_ACCELERATE_ENDPOINT`          | env-only / restart     | `False`                                       | public-config                  | missing                                                      | AWS-specific performance option; only enable after bucket acceleration is configured.                          |
| `S3_ADDRESSING_STYLE`                 | env-only / restart     | unset                                         | public-config                  | missing                                                      | Needed by some S3-compatible stores; document virtual-hosted vs path-style decision.                           |
| `GCS_BUCKET_NAME`                     | env-only / restart     | unset                                         | sensitive-config identifier    | missing                                                      | Required when `STORAGE_PROVIDER=gcs`; preflight should verify bucket and object IAM.                           |
| `GOOGLE_APPLICATION_CREDENTIALS_JSON` | env-only / restart     | unset; falls back to ADC                      | secret                         | missing                                                      | Inline service account JSON is supported but should normally be mounted or supplied through workload identity. |
| `AZURE_STORAGE_ENDPOINT`              | env-only / restart     | unset                                         | sensitive-config               | missing                                                      | Required for Azure Blob provider; document account endpoint and private network posture.                       |
| `AZURE_STORAGE_CONTAINER_NAME`        | env-only / restart     | unset                                         | sensitive-config identifier    | missing                                                      | Required for Azure Blob provider; preflight should verify container permissions.                               |
| `AZURE_STORAGE_KEY`                   | env-only / restart     | unset; falls back to `DefaultAzureCredential` | secret                         | missing                                                      | Prefer managed identity where possible; otherwise store in Secret.                                             |

Validation evidence:

- `backend/bcgpt/config.py` defines storage provider rows and creates `UPLOAD_DIR` under `DATA_DIR`.
- `backend/bcgpt/storage/provider.py` supports local, S3, GCS, and Azure providers, and creates a module-level
  `Storage` singleton from `STORAGE_PROVIDER`.
- S3/GCS/Azure providers stage files locally before uploading to object storage; local staging cleanup and
  bucket/container preflight are therefore part of the production profile.
- Docker/Compose/Helm document local persistence through `/app/backend/data` and PVCs, but do not expose
  object-store provider credentials in the inspected templates.

#### Upload And Cache Guardrails

| Key                             | Lifecycle / mutability          | Default / alias            | Secret class          | Current deploy coverage | Production guidance                                                                                        |
| ------------------------------- | ------------------------------- | -------------------------- | --------------------- | ----------------------- | ---------------------------------------------------------------------------------------------------------- |
| `RAG_FILE_MAX_SIZE`             | persistent-seed / db-admin      | `100`                      | public-config         | env-example             | Upload size limit in MB for RAG files. Coordinate frontend limits and backend enforcement.                 |
| `RAG_FILE_MAX_COUNT`            | persistent-seed / db-admin      | unset/none                 | public-config         | missing                 | Chat-context file count guardrail, not a global storage quota.                                             |
| `FILE_MAGIC_VALIDATION_ENABLED` | persistent-seed / db-admin      | `True`                     | public-config         | env-example             | Keep enabled in production; this validates known binary signatures after extension checks.                 |
| `SECURITY_SCAN_FILE_UPLOADS`    | persistent-seed / db-admin      | `True`                     | public-config         | missing                 | Security scan for RAG source content in middleware paths; not an upload-time antivirus/quarantine control. |
| `TIKTOKEN_CACHE_DIR`            | env-only / restart              | `CACHE_DIR/tiktoken`       | sensitive-config path | helm-env                | Tokenizer cache path; include in persistence/cache warmup policy if offline deploys are required.          |
| `SENTENCE_TRANSFORMERS_HOME`    | env-only / restart              | library default unless set | sensitive-config path | helm-env                | Embedding model cache root used by retrieval embedding paths; needs volume/cache ownership policy.         |
| `HF_HOME`                       | external library env / restart  | library default unless set | sensitive-config path | helm-env                | Exposed by Helm for Hugging Face cache placement; not directly owned by app config in inspected source.    |
| `WHISPER_MODEL`                 | deployment/runtime env          | unset in app config        | public-config         | helm-env                | Helm exposes it for local Whisper posture; app-level STT model row is `AUDIO_STT_MODEL`.                   |
| `WHISPER_MODEL_DIR`             | external/library path / restart | library default unless set | sensitive-config path | helm-env                | Helm exposes model cache path; include in image/offline model preparation runbook.                         |

Validation evidence:

- `routers/files.py` enforces max file size, dangerous extension blocking, and optional magic-byte validation
  before writing to storage.
- `RAG_FILE_MAX_COUNT` is surfaced as a frontend/chat-context guardrail, not as an object-store quota.
- `SECURITY_SCAN_FILE_UPLOADS` is read by the security middleware/RAG source scan path; it is not the same as
  upload quarantine or malware scanning.
- Helm exposes model/cache-related paths, while `.env.example` currently exposes only
  `RAG_FILE_MAX_SIZE` and `FILE_MAGIC_VALIDATION_ENABLED` from this guardrail set.

#### Vector Database Backends

| Key                                     | Lifecycle / mutability                  | Default / alias                    | Secret class              | Current deploy coverage | Production guidance                                                                                                                                       |
| --------------------------------------- | --------------------------------------- | ---------------------------------- | ------------------------- | ----------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `VECTOR_DB`                             | env-only / restart                      | `qdrant`                           | public-config             | missing                 | Selects vector adapter. Current connector supports `milvus`, `qdrant`, `opensearch`, `pgvector`, and `elasticsearch`; unknown values fall back to Qdrant. |
| `QDRANT_URL`                            | persistent-seed / db-admin              | empty; can seed from `QDRANT_URI`  | sensitive-config          | missing                 | External Qdrant endpoint. Empty value leaves the adapter without a constructed Qdrant client until configured.                                            |
| `QDRANT_URI`                            | alias / restart                         | legacy seed alias for `QDRANT_URL` | sensitive-config          | missing                 | Alias only; new deployment docs should prefer `QDRANT_URL`.                                                                                               |
| `QDRANT_API_KEY`                        | persistent-seed / db-admin              | empty                              | secret                    | missing                 | Qdrant credential. Admin retrieval config updates can reinitialize the client.                                                                            |
| `MILVUS_URI`                            | env-only / restart                      | `DATA_DIR/vector_db/milvus.db`     | sensitive-config path/url | missing                 | Local file default is single-node posture; remote Milvus needs backup and auth profile.                                                                   |
| `MILVUS_DB`                             | env-only / restart                      | `default`                          | public-config             | missing                 | Milvus database name; coordinate with collection naming and tenant/environment policy.                                                                    |
| `MILVUS_TOKEN`                          | env-only / restart                      | unset                              | secret                    | missing                 | Milvus auth token; store as Secret when remote Milvus is used.                                                                                            |
| `OPENSEARCH_URI`                        | env-only / restart                      | `https://localhost:9200`           | sensitive-config          | missing                 | Default is not a production endpoint. Must pair with TLS and index lifecycle policy.                                                                      |
| `OPENSEARCH_SSL`                        | env-only / restart                      | `true`                             | public-config             | missing                 | Keep enabled unless using a controlled local/dev profile.                                                                                                 |
| `OPENSEARCH_CERT_VERIFY`                | env-only / restart                      | `false`                            | public-config             | missing                 | Production should set `true` and provide trusted cert material.                                                                                           |
| `OPENSEARCH_USERNAME`                   | env-only / restart                      | unset                              | secret                    | missing                 | Basic auth user; classify with vector credentials.                                                                                                        |
| `OPENSEARCH_PASSWORD`                   | env-only / restart                      | unset                              | secret                    | missing                 | Basic auth password; store in Secret.                                                                                                                     |
| `ELASTICSEARCH_URL`                     | env-only / restart                      | `https://localhost:9200`           | sensitive-config          | missing                 | Default is local/dev posture; production needs managed endpoint and index lifecycle policy.                                                               |
| `ELASTICSEARCH_CA_CERTS`                | env-only / restart                      | unset                              | sensitive-config path     | missing                 | CA bundle path for TLS verification.                                                                                                                      |
| `ELASTICSEARCH_API_KEY`                 | env-only / restart                      | unset                              | secret                    | missing                 | Preferred Elasticsearch auth option when supported; do not combine casually with basic auth.                                                              |
| `ELASTICSEARCH_USERNAME`                | env-only / restart                      | unset                              | secret                    | missing                 | Basic auth user fallback.                                                                                                                                 |
| `ELASTICSEARCH_PASSWORD`                | env-only / restart                      | unset                              | secret                    | missing                 | Basic auth password fallback.                                                                                                                             |
| `ELASTICSEARCH_CLOUD_ID`                | env-only / restart                      | unset                              | sensitive-config          | missing                 | Elastic Cloud routing identifier; pair with API key or basic auth.                                                                                        |
| `SSL_ASSERT_FINGERPRINT`                | env-only / restart                      | unset                              | sensitive-config          | missing                 | Optional certificate fingerprint pinning; document rotation process before use.                                                                           |
| `ELASTICSEARCH_INDEX_PREFIX`            | env-only / restart                      | `bcgpt_collections`                | public-config             | missing                 | Namespace prefix for collections; include environment/tenant naming policy.                                                                               |
| `PGVECTOR_DB_URL`                       | env-only + startup-validation / restart | falls back to `DATABASE_URL`       | secret/sensitive-config   | missing                 | Must be PostgreSQL when `VECTOR_DB=pgvector`; source raises if URL is not Postgres.                                                                       |
| `PGVECTOR_INITIALIZE_MAX_VECTOR_LENGTH` | env-only / restart                      | `1536`                             | public-config             | missing                 | Determines pgvector table/index initialization length; must match embedding model dimensionality strategy.                                                |

Validation evidence:

- `backend/bcgpt/retrieval/vector/connector.py` selects the vector client at import based on `VECTOR_DB`.
- Qdrant exposes runtime admin update/reinitialize behavior for URL and API key, but deployment templates do
  not expose those rows.
- Pgvector validates that `PGVECTOR_DB_URL` is PostgreSQL when `VECTOR_DB=pgvector`.
- Milvus, OpenSearch, Elasticsearch, and pgvector credentials/topology are absent from the inspected
  `.env.example`, Compose, and Helm values/templates.
- Vector reset, upload reset, file delete, and knowledge delete paths can mutate SQL, object storage, and
  vector DB independently; lifecycle and reconciliation details stay in
  `STORAGE_FILE_INGESTION_LIFECYCLE_PLAN_2026-06-23.md`.

### Observability, Audit Telemetry, Handoff Operations

Rows in this section mix env-only bootstrap settings and DB-backed `PersistentConfig` rows. OpenTelemetry
bootstrap is env-only and restart-required. Prometheus, LangFuse, audit, AI interaction audit, user webhooks,
and handoff feature rows are seeded from env but can be changed through admin/runtime config paths in current
code. Handoff SMTP rows are a separate runtime env-only path read when email notifications are sent.
Notification and handoff delivery ownership, including retry/dead-letter posture and browser/banner/AI notice
fixtures, is tracked in `NOTIFICATION_HANDOFF_COMMUNICATION_GOVERNANCE_PLAN_2026-06-23.md`.

#### Logging, Audit, And AI Interaction Telemetry

| Key                                                      | Lifecycle / mutability                         | Default / alias                    | Secret class                | Current deploy coverage | Production guidance                                                                                                                                                                                           |
| -------------------------------------------------------- | ---------------------------------------------- | ---------------------------------- | --------------------------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GLOBAL_LOG_LEVEL`                                       | env-only / restart                             | invalid/empty falls back to `INFO` | public-config               | missing                 | Process-wide logging floor. Production should use `INFO` unless debugging a scoped incident.                                                                                                                  |
| `AUDIO_LOG_LEVEL` and other subsystem `*_LOG_LEVEL` rows | env-only / restart                             | falls back to `GLOBAL_LOG_LEVEL`   | public-config               | missing                 | Supported subsystem prefixes are `AUDIO`, `COMFYUI`, `CONFIG`, `DB`, `IMAGES`, `MAIN`, `MODELS`, `OLLAMA`, `OPENAI`, `RAG`, `WEBHOOK`, `SOCKET`, and `OAUTH`. Use targeted overrides instead of global debug. |
| `AUDIT_LOG_LEVEL`                                        | persistent-seed / db-admin plus logger startup | `NONE`                             | public-config               | missing                 | Controls audit capture depth and Loguru audit file sink. Production policy must choose `METADATA`, `REQUEST`, or `REQUEST_RESPONSE` explicitly if file audit logs are required.                               |
| `AUDIT_EXCLUDED_PATHS`                                   | persistent-seed / db-admin                     | `/chats,/folders`                  | sensitive-config            | missing                 | Exclusion list affects audit coverage. Review before citing audit logs as complete evidence.                                                                                                                  |
| `MAX_BODY_LOG_SIZE`                                      | persistent-seed / db-admin                     | `2048`                             | public-config               | missing                 | Request/response body capture cap. Larger values increase PII and storage exposure.                                                                                                                           |
| `AUDIT_LOG_FILE_ROTATION_SIZE`                           | env-only / restart                             | `10MB`                             | public-config               | missing                 | Applies to Loguru audit file rotation when `AUDIT_LOG_LEVEL != NONE`; coordinate with volume retention.                                                                                                       |
| `AI_INTERACTION_AUDIT_ENABLED`                           | persistent-seed / db-admin                     | `False`                            | public-config               | env-example             | Writes structured AI interaction audit rows without message content. Enable only after retention and correlation-id policy are defined.                                                                       |
| `WEBHOOK_URL`                                            | persistent-seed / db-admin                     | empty                              | sensitive-config            | missing                 | General user/signup webhook destination. Treat as an outbound integration endpoint and validate network placement.                                                                                            |
| `ENABLE_USER_WEBHOOKS`                                   | persistent-seed / db-admin                     | `True`                             | public-config               | missing                 | Feature flag for user webhooks. Production should document whether signup/user events are allowed to leave the deployment boundary.                                                                           |
| `BCGPT_URL`                                              | persistent-seed / db-admin                     | `http://localhost:3000`            | sensitive-config/public URL | missing                 | Public base URL used in links and notification-adjacent paths. Production must set the externally reachable HTTPS URL, not the local default.                                                                 |

Validation evidence:

- `backend/bcgpt/env.py` builds `GLOBAL_LOG_LEVEL` and the subsystem `SRC_LOG_LEVELS` map at import.
- `backend/bcgpt/utils/logger.py` routes standard logging through Loguru, writes stdout logs, and adds a
  rotating audit file sink only when `AUDIT_LOG_LEVEL != NONE`.
- `backend/bcgpt/config.py` defines audit rows as `PersistentConfig`, so env values are seeds/defaults for
  admin-configurable runtime values.
- Audit/security evidence lifecycle policy, including capture posture, exclusions, export/purge evidence, and
  security-event UI/SIEM scope, is tracked in `AUDIT_SECURITY_EVIDENCE_LIFECYCLE_GOVERNANCE_PLAN_2026-06-23.md`.
- `utils/middleware.py::_log_ai_interaction` records model/provider, token, RAG/tool/web, latency, and
  guardrail metadata without message content when `AI_INTERACTION_AUDIT_ENABLED` is enabled.
- `BCGPT_URL` is a DB-backed config row used by admin/general settings and public-link generation paths.
- `.env.example` exposes only `AI_INTERACTION_AUDIT_ENABLED` from this group; log/audit/webhook rows are
  absent from inspected `.env.example`, Compose, and Helm templates.

#### OpenTelemetry, Prometheus, And LangFuse

| Key                           | Lifecycle / mutability     | Default / alias              | Secret class                | Current deploy coverage | Production guidance                                                                                                                 |
| ----------------------------- | -------------------------- | ---------------------------- | --------------------------- | ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------- |
| `ENABLE_OTEL`                 | env-only / restart         | `False`                      | public-config               | missing                 | Enables OTel setup in `main.py`. Requires collector endpoint, dependency smoke, and sampling policy.                                |
| `OTEL_EXPORTER_OTLP_ENDPOINT` | env-only / restart         | `http://localhost:4317`      | sensitive-config            | missing                 | OTLP gRPC endpoint. Default is local/dev and will not work in most production clusters.                                             |
| `OTEL_SERVICE_NAME`           | env-only / restart         | `bcgpt`                      | identifier                  | missing                 | Service name sent in OTel resource. Include environment and release naming conventions in deployment profile.                       |
| `OTEL_RESOURCE_ATTRIBUTES`    | env-only / restart         | empty                        | public/sensitive-config     | missing                 | Declared in env, but current setup does not visibly apply it to the Resource. Do not promise it until implemented or verified.      |
| `OTEL_TRACES_SAMPLER`         | env-only / restart         | `parentbased_always_on`      | public-config               | missing                 | Declared in env, but current setup does not visibly map it to an SDK sampler. Needs implementation or removal from public contract. |
| `PROMETHEUS_METRICS_ENABLED`  | persistent-seed / db-admin | `False`                      | public-config               | missing                 | Initializes custom RAG metrics and attempts FastAPI `/metrics`; fallback may start standalone `:9090` if instrumentator is missing. |
| `RAG_TRACING_ENABLED`         | persistent-seed / db-admin | `False`                      | public-config               | missing                 | Adds LangFuse span processor only when `ENABLE_OTEL=true`; RAG-specific decorator currently has no observed call sites.             |
| `LANGFUSE_PUBLIC_KEY`         | persistent-seed / db-admin | empty                        | sensitive-config/identifier | missing                 | Required for LangFuse tracing with `RAG_TRACING_ENABLED`; classify with external observability credentials.                         |
| `LANGFUSE_SECRET_KEY`         | persistent-seed / db-admin | empty                        | secret                      | missing                 | LangFuse secret credential. Store in Secret and do not expose through broad config export.                                          |
| `LANGFUSE_HOST`               | persistent-seed / db-admin | `https://cloud.langfuse.com` | sensitive-config            | missing                 | External observability destination; regulated deployments need data residency and prompt/content policy review.                     |

Validation evidence:

- `main.py::_setup_observability()` calls OTel setup when `ENABLE_OTEL`, then adds LangFuse only when
  `RAG_TRACING_ENABLED`; Prometheus setup runs separately when `PROMETHEUS_METRICS_ENABLED`.
- `utils/telemetry/setup.py` currently uses `OTEL_SERVICE_NAME` and `OTEL_EXPORTER_OTLP_ENDPOINT`, but not the
  declared `OTEL_RESOURCE_ATTRIBUTES` or `OTEL_TRACES_SAMPLER` values.
- `backend/requirements.txt` includes OTel and LangFuse packages, but no Prometheus package rows were found in
  inspected dependency manifests; local host behavior should not be assumed as packaged image behavior.
- `utils/prometheus_metrics.py` initializes custom `bcgpt_*` metrics if `prometheus_client` is importable and
  falls back to a standalone `:9090` metrics server when `prometheus_fastapi_instrumentator` is unavailable.
- Deployment examples do not expose OTel, Prometheus, RAG tracing, or LangFuse rows.

#### Frontend Error Logging And Browser Metrics

Current source does not implement a production frontend remote logging transport. Do not document
`SENTRY_*`, `PUBLIC_SENTRY_*`, `FRONTEND_LOG_*`, or browser `OTEL_*` rows as supported until a transport is
chosen and wired. The detailed decision path is in `FRONTEND_REMOTE_LOGGING_DECISION_PLAN_2026-06-23.md`.

| Key or candidate                           | Lifecycle / mutability | Default / alias                                  | Secret class                                                               | Current deploy coverage | Production guidance                                                                                                       |
| ------------------------------------------ | ---------------------- | ------------------------------------------------ | -------------------------------------------------------------------------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------------- |
| `VITE_APP_VERSION`, `VITE_APP_BUILD_HASH`  | build-time define      | package version; `APP_BUILD_HASH` or `dev-build` | identifier                                                                 | vite define only        | Already cataloged under build provenance. Use as release/build metadata for future frontend error events.                 |
| Browser `logger` level                     | not implemented as env | `info` constructor default in source             | public-config candidate                                                    | missing                 | `src/lib/utils/logger.ts` supports `setLevel()`, but no env/config row sets it. Do not rely on deploy-time control yet.   |
| `SENTRY_*` / `PUBLIC_SENTRY_*`             | not implemented        | none                                             | mixed: browser DSN is visible; upload token is secret                      | missing                 | Candidate only. Requires dependency, registration, redaction, source-map upload policy, and privacy review.               |
| `FRONTEND_LOG_*` / `PUBLIC_FRONTEND_LOG_*` | not implemented        | none                                             | mixed: public endpoint visible; server token/retention not browser-exposed | missing                 | Candidate only for a self-hosted browser log endpoint. Requires backend intake, rate limits, retention, and dashboarding. |
| `BROWSER_OTEL_*` / `PUBLIC_BROWSER_OTEL_*` | not implemented        | none                                             | public/sensitive-config                                                    | missing                 | Candidate only. Requires browser SDK, CORS-safe collector exposure, sampling, and correlation-id policy.                  |
| `web-vitals` export                        | source helper only     | console-only best effort                         | public-config candidate                                                    | missing                 | `webVitals.ts` dynamically imports and logs metrics to console; no dependency or remote export was confirmed.             |

Validation evidence:

- `src/lib/utils/logger.ts` has a pluggable `LogTransport` and default `ConsoleTransport`, with min level
  `info`.
- `src/lib/utils/__tests__/logger.test.ts` proves custom transports receive entries, but source search found
  no production `logger.addTransport()` registration.
- `src/hooks.client.ts` global SvelteKit client errors still use direct `console.error`.
- `src/lib/utils/webVitals.ts` logs Web Vitals to console only and does not export to a remote endpoint.
- `package.json` and `bun.lock` do not include an explicit Sentry/browser OTel dependency; `@sveltejs/kit`
  and Vitest mention OTel only as optional peer metadata.
- Current frontend env exposure search found only `VITE_APP_VERSION` and `VITE_APP_BUILD_HASH`.
- Focused `.env.example`, Dockerfile, Compose, and Helm searches found no Sentry, frontend remote-log, or
  browser OTel rows.

#### Handoff Notifications And SMTP

| Key                        | Lifecycle / mutability     | Default / alias       | Secret class            | Current deploy coverage | Production guidance                                                                                                |
| -------------------------- | -------------------------- | --------------------- | ----------------------- | ----------------------- | ------------------------------------------------------------------------------------------------------------------ |
| `HANDOFF_ENABLED`          | persistent-seed / db-admin | `True`                | public-config           | missing                 | Enables user-to-agent/admin handoff requests. Document support workflow and SLA before relying on it.              |
| `HANDOFF_EMAIL_ENABLED`    | persistent-seed / db-admin | `False`               | public-config           | missing                 | Sends handoff notification email when SMTP env is configured. Requires SMTP smoke and recipient policy.            |
| `HANDOFF_EMAIL_RECIPIENTS` | persistent-seed / db-admin | `[]` JSON/string      | sensitive-config        | missing                 | Recipient list. Treat as operational contact data and validate JSON/string parsing behavior.                       |
| `HANDOFF_WEBHOOK_ENABLED`  | persistent-seed / db-admin | `False`               | public-config           | missing                 | Sends handoff webhook notifications. Pair with outbound allowlist and retry/failure policy.                        |
| `HANDOFF_WEBHOOK_URL`      | persistent-seed / db-admin | empty                 | sensitive-config        | missing                 | Webhook endpoint is validated for SSRF before send and redirects are disabled. Still needs network owner approval. |
| `HANDOFF_SMTP_HOST`        | env-only / runtime read    | empty                 | sensitive-config        | missing                 | Required for handoff email. Read directly from env at notification time, not `PersistentConfig`.                   |
| `HANDOFF_SMTP_PORT`        | env-only / runtime read    | `587`                 | public-config           | missing                 | SMTP port; code currently starts TLS unconditionally.                                                              |
| `HANDOFF_SMTP_USER`        | env-only / runtime read    | empty                 | secret/sensitive-config | missing                 | SMTP username; may be empty for unauthenticated relay profiles.                                                    |
| `HANDOFF_SMTP_PASSWORD`    | env-only / runtime read    | empty                 | secret                  | missing                 | SMTP password. Store in Secret and keep out of admin config export.                                                |
| `HANDOFF_EMAIL_FROM`       | env-only / runtime read    | `noreply@bcgpt.local` | sensitive-config        | missing                 | Sender address. Production must set a verified domain-aligned address.                                             |

Validation evidence:

- `config.py` defines handoff feature, email, recipients, webhook, and webhook URL as `PersistentConfig`.
- `routers/handoff.py` exposes admin config get/update and user/admin handoff request/status paths.
- `utils/handoff_notifications.py` reads SMTP host/port/user/password/from directly from `os.environ` during
  email send, sends STARTTLS, and validates handoff webhook URL before posting with redirects disabled.
- `NOTIFICATION_HANDOFF_COMMUNICATION_GOVERNANCE_PLAN_2026-06-23.md` tracks the current best-effort delivery
  posture, handoff workflow decision, and user-visible banner/AI notice contracts.
- No handoff or SMTP rows are exposed in inspected `.env.example`, Compose, or Helm templates.
- Detailed probe, metrics, tracing, frontend error transport, and request-id propagation decisions remain in
  `OBSERVABILITY_OPERABILITY_PLAN_2026-06-23.md`.

### Compliance, Privacy Retention, Security Scanner

Most rows in this section are `PersistentConfig`: env values seed DB-backed runtime config and can be changed
through admin/API paths. This section catalogs the operator-facing keys; it does not prove a complete
regulated workflow. DSAR fulfillment, provenance privacy mode, legal hold, incident escalation, security-event
retention, and data inventory details remain in `DATA_PRIVACY_COMPLIANCE_OPERATIONS_PLAN_2026-06-23.md`.

#### Retention And Compliance Module Switches

| Key                             | Lifecycle / mutability     | Default / alias        | Secret class  | Current deploy coverage | Production guidance                                                                                                                                         |
| ------------------------------- | -------------------------- | ---------------------- | ------------- | ----------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `CHAT_RETENTION_DAYS`           | persistent-seed / db-admin | `0` disables retention | public-config | env-example             | Daily task anonymizes or deletes chats older than this threshold. Production needs dry-run counts and legal-hold policy before enabling deletion.           |
| `CHAT_RETENTION_ANONYMIZE`      | persistent-seed / db-admin | `False`                | public-config | env-example             | When true, old chats are PII-masked instead of deleted. Verify masking quality before relying on it for compliance.                                         |
| `AUDIT_RETENTION_DAYS`          | persistent-seed / db-admin | `90`                   | public-config | missing                 | Daily audit purge uses this value. Coordinate with backup, legal hold, and audit evidence retention before lowering.                                        |
| `SECURITY_EVENT_RETENTION_DAYS` | persistent-seed / db-admin | `1825`                 | public-config | missing                 | Model/table supports purge, but no background purge task was observed. Treat as manual/admin retention until scheduled purge exists.                        |
| `COMPLIANCE_ENABLED`            | persistent-seed / db-admin | `False`                | public-config | env-example             | Master switch for compliance routers. Enabling exposes multiple backend compliance modules; rollout needs owner/runbook.                                    |
| `COMPLIANCE_INVENTORY_ENABLED`  | persistent-seed / db-admin | `False`                | public-config | env-example             | Model inventory flag. Current routers mostly check only `COMPLIANCE_ENABLED`, so do not assume this is a hard route gate.                                   |
| `COMPLIANCE_AIIA_ENABLED`       | persistent-seed / db-admin | `False`                | public-config | env-example             | AI impact assessment flag; daily task logs expired approved AIIA records only when enabled.                                                                 |
| `COMPLIANCE_HITL_ENABLED`       | persistent-seed / db-admin | `False`                | public-config | env-example             | Configures HITL `ApprovalGates`; this is one of the module flags with observed runtime effect beyond router visibility.                                     |
| `COMPLIANCE_HITL_SLA_SECONDS`   | persistent-seed / db-admin | `300`                  | public-config | env-example             | HITL approval SLA. Align with escalation/notification path before treating as enforceable SLA.                                                              |
| `COMPLIANCE_INCIDENT_ENABLED`   | persistent-seed / db-admin | `False`                | public-config | env-example             | Incident module flag. Current incident routers were observed gating on master `COMPLIANCE_ENABLED`; verify module hard-gate before documenting it as one.   |
| `COMPLIANCE_FAIRNESS_ENABLED`   | persistent-seed / db-admin | `False`                | public-config | env-example             | Fairness/bias testing flag. Backend helpers exist, but operator workflow/UI is still thin.                                                                  |
| `COMPLIANCE_PROVENANCE_ENABLED` | persistent-seed / db-admin | `False`                | public-config | env-example             | Enables RAG provenance writes and daily expired-provenance purge. Provenance rows can include truncated query/response text with 10-year default retention. |
| `COMPLIANCE_DSAR_ENABLED`       | persistent-seed / db-admin | `False`                | public-config | env-example             | DSAR module flag. Request API exists, but export/erase/explain processor execution workflow is not wired end-to-end.                                        |
| `COMPLIANCE_VENDOR_ENABLED`     | persistent-seed / db-admin | `False`                | public-config | env-example             | Vendor/AIBOM module flag. Needs subprocessor inventory and owner cadence before regulated production use.                                                   |

Validation evidence:

- `.env.example` documents chat retention and compliance module flags, but inspected Compose/Helm templates do
  not expose them.
- `main.py` starts daily audit, chat-retention, and compliance maintenance tasks; compliance maintenance only
  logs expired AIIA records and purges expired provenance when the relevant flags are enabled.
- Compliance routers were observed mostly checking `COMPLIANCE_ENABLED`, while module flags are not uniformly
  hard route gates. `COMPLIANCE_HITL_ENABLED` and `COMPLIANCE_PROVENANCE_ENABLED` have clearer runtime effects.
- `AIRAGProvenance` defaults `retention_until` to 10 years and stores hashes plus optional truncated
  query/response text, so privacy mode must be an owner decision.

#### AI Transparency And Chat Rate Limits

| Key                          | Lifecycle / mutability     | Default / alias                       | Secret class  | Current deploy coverage | Production guidance                                                                                             |
| ---------------------------- | -------------------------- | ------------------------------------- | ------------- | ----------------------- | --------------------------------------------------------------------------------------------------------------- |
| `AI_TRANSPARENCY_ENABLED`    | persistent-seed / db-admin | `True`                                | public-config | missing                 | Transparency notice flag. Treat as compliance UX posture, not scanner behavior.                                 |
| `AI_NOTIFICATION_TITLE`      | persistent-seed / db-admin | `AI Assistant Notice`                 | public-config | missing                 | Notice title. Localize and legal-review before regulated production launch.                                     |
| `AI_NOTIFICATION_MESSAGE`    | persistent-seed / db-admin | default AI-use notice                 | public-config | missing                 | Long-form notice text. Needs jurisdiction/product-specific owner approval.                                      |
| `AI_DISCLAIMER_TEXT`         | persistent-seed / db-admin | default financial-decision disclaimer | public-config | missing                 | Disclaimer text. Keep aligned with product domain and regulatory posture.                                       |
| `AI_RESPONSE_LABEL`          | persistent-seed / db-admin | `AI-Generated Response`               | public-config | missing                 | AI response label. Verify UI surfaces before claiming transparency compliance.                                  |
| `RATE_LIMIT_CHAT_ENABLED`    | persistent-seed / db-admin | `True`                                | public-config | missing                 | Chat rate limiter flag. Security admin API exposes it; production needs user/IP/Redis behavior documented.      |
| `RATE_LIMIT_CHAT_PER_MINUTE` | persistent-seed / db-admin | `30`                                  | public-config | missing                 | Per-minute chat limit. Tune with traffic profile and support policy.                                            |
| `RATE_LIMIT_CHAT_PER_HOUR`   | persistent-seed / db-admin | `500`                                 | public-config | missing                 | Per-hour chat limit. Coordinate with token budget and abuse monitoring.                                         |
| `RATE_LIMIT_CHAT_PER_DAY`    | persistent-seed / db-admin | `5000`                                | public-config | missing                 | Per-day chat limit. Treat as abuse/cost guardrail, not a contractual quota until UX/error handling is verified. |

Validation evidence:

- `config.py` defines AI transparency and chat rate-limit rows as `PersistentConfig`.
- `routers/security.py` exposes these rows through the admin security config get/update surface.
- `utils/middleware.py` checks `RATE_LIMIT_CHAT_ENABLED` and the per-period limits in chat middleware paths.
- `.env.example`, Compose, and Helm do not expose AI transparency or chat rate-limit rows.

#### Security Scanner, Canary, And SIEM

| Key                                      | Lifecycle / mutability     | Default / alias     | Secret class                   | Current deploy coverage | Production guidance                                                                                             |
| ---------------------------------------- | -------------------------- | ------------------- | ------------------------------ | ----------------------- | --------------------------------------------------------------------------------------------------------------- |
| `SECURITY_SCANNER_ENABLED`               | persistent-seed / db-admin | `False`             | public-config                  | missing                 | Master switch for prompt/input/output scanning pipeline. Enable first in shadow mode with event review.         |
| `SECURITY_SHADOW_MODE`                   | persistent-seed / db-admin | `True`              | public-config                  | missing                 | When true, detections are logged but not blocked. Production rollout should start here.                         |
| `SECURITY_LOG_DETECTIONS`                | persistent-seed / db-admin | `True`              | public-config                  | missing                 | Persists detections to `security_event`. Retention and masked-sample policy must be set.                        |
| `SECURITY_EMERGENCY_STOP`                | persistent-seed / db-admin | `False`             | public-config                  | missing                 | Global emergency stop flag in security config. Needs runbook for owner, blast radius, and rollback.             |
| `SECURITY_PROMPT_INJECTION_ENABLED`      | persistent-seed / db-admin | `False`             | public-config                  | missing                 | Enables prompt-injection scanner. Keep test fixtures aligned with supported languages and threat classes.       |
| `SECURITY_JAILBREAK_ENABLED`             | persistent-seed / db-admin | `False`             | public-config                  | missing                 | Enables jailbreak scanner. Pair with false-positive review in shadow rollout.                                   |
| `SECURITY_PII_ENABLED`                   | persistent-seed / db-admin | `False`             | public-config                  | missing                 | Enables PII scanner/masking. Required before relying on output/input PII controls.                              |
| `SECURITY_PII_MASK_MODE`                 | persistent-seed / db-admin | `redact`            | public-config                  | missing                 | PII mask mode. Document redaction/tokenization semantics before exporting logs/events.                          |
| `SECURITY_TOXICITY_ENABLED`              | persistent-seed / db-admin | `False`             | public-config                  | missing                 | Enables toxicity scanner. Custom policy must define blocked categories and appeals path.                        |
| `SECURITY_TOXICITY_CUSTOM_WORD_LIST`     | persistent-seed / db-admin | empty               | sensitive-config               | missing                 | Custom words can encode policy-sensitive terms. Review before config export/import.                             |
| `SECURITY_SECRETS_ENABLED`               | persistent-seed / db-admin | `False`             | public-config                  | missing                 | Enables secret detector. Pair with incident workflow for detected credential leakage.                           |
| `SECURITY_OUTPUT_FILTER_ENABLED`         | persistent-seed / db-admin | `False`             | public-config                  | missing                 | Enables output filter scanner. Important for internal URL, system prompt, PII, and secret leakage controls.     |
| `SECURITY_CONVERSATION_SCANNING_ENABLED` | persistent-seed / db-admin | `False`             | public-config                  | missing                 | Enables conversation-level risk scoring. Needs threshold calibration before blocking.                           |
| `SECURITY_CONVERSATION_THRESHOLD`        | persistent-seed / db-admin | `2.0`               | public-config                  | missing                 | Conversation risk threshold. Treat as policy value, not universal model score.                                  |
| `SECURITY_CONFIDENCE_THRESHOLD`          | persistent-seed / db-admin | `0.0`               | public-config                  | missing                 | Minimum scanner confidence. Raising it can suppress deterministic scanner results.                              |
| `SECURITY_SCAN_FILE_UPLOADS`             | persistent-seed / db-admin | `True`              | public-config                  | missing                 | Also cataloged under upload guardrails. It scans RAG source content; it is not malware quarantine.              |
| `SECURITY_SCAN_WEB_RESULTS`              | persistent-seed / db-admin | `True`              | public-config                  | missing                 | Scans web results before use in RAG/chat contexts. Pair with web-provider latency/error budget.                 |
| `SECURITY_LLM_SCANNER_ENABLED`           | persistent-seed / db-admin | `False`             | public-config                  | missing                 | Uses configured model for LLM-assisted scanner verification. Adds cost, latency, provider privacy exposure.     |
| `SECURITY_LLM_SCANNER_MODEL`             | persistent-seed / db-admin | empty               | public-config/sensitive-config | missing                 | Model id for LLM scanner. Must be approved for security scanning data classes.                                  |
| `SECURITY_GUARDRAIL_ENABLED`             | persistent-seed / db-admin | `False`             | public-config                  | missing                 | Enables model-based guardrail scanner. Verify fallback/error behavior before block mode.                        |
| `SECURITY_GUARDRAIL_MODEL`               | persistent-seed / db-admin | empty               | public-config/sensitive-config | missing                 | Guardrail model id. Keep separate from chat/provider routing policy.                                            |
| `SECURITY_GUARDRAIL_ACTION`              | persistent-seed / db-admin | `block`             | public-config                  | missing                 | Action when guardrail triggers. Document allowed values and user-visible error behavior.                        |
| `SECURITY_CANARY_TOKENS_ENABLED`         | persistent-seed / db-admin | `False`             | public-config                  | missing                 | Enables canary-token insertion/detection. Needs incident workflow for leaks before production use.              |
| `SECURITY_CANARY_TOKEN_POSITION`         | persistent-seed / db-admin | `system_prompt_end` | public-config                  | missing                 | Canary placement. Coordinate with prompt templates and model/system prompt leakage tests.                       |
| `SECURITY_SIEM_WEBHOOK_ENABLED`          | persistent-seed / db-admin | `False`             | public-config                  | missing                 | Sends security events to SIEM webhook. Requires outbound allowlist, retry/failure policy, and redaction review. |
| `SECURITY_SIEM_WEBHOOK_URL`              | persistent-seed / db-admin | empty               | secret/sensitive-config        | missing                 | SIEM endpoint URL. Treat as sensitive integration endpoint.                                                     |
| `SECURITY_SIEM_WEBHOOK_HEADERS`          | persistent-seed / db-admin | `{}`                | secret                         | missing                 | Header JSON can contain bearer tokens/API keys; store as Secret and avoid clear-text admin export.              |

Validation evidence:

- `config.py` defines security scanner, guardrail, canary, SIEM, AI transparency, and chat rate-limit rows as
  `PersistentConfig`.
- `routers/security.py` exposes a broad admin get/update surface for scanner toggles, AI transparency, rate
  limits, canary tokens, and SIEM webhook settings.
- `utils/security/__init__.py` persists detections into `security_event` when logging is enabled and can send
  SIEM webhook events when SIEM webhook config is enabled.
- `security_events.py` supports export and manual purge; no background security-event purge task was observed
  in `main.py`.
- Security event retention, export artifact semantics, and SIEM delivery evidence are tracked in
  `AUDIT_SECURITY_EVIDENCE_LIFECYCLE_GOVERNANCE_PLAN_2026-06-23.md`.
- `.env.example`, Compose, and Helm do not expose the inspected `SECURITY_*`, `AI_TRANSPARENCY_*`,
  `AI_NOTIFICATION_*`, `AI_DISCLAIMER_TEXT`, `AI_RESPONSE_LABEL`, or `RATE_LIMIT_CHAT_*` rows.

### Immediate Gaps

1. `.env.example` documents `BCGPT_SECRET_KEY`, trusted proxy IPs, JWT RSA examples, and some feature flags,
   but omits `BCGPT_AUTH`, cookie secure/SameSite keys, database pool keys, Redis/WebSocket keys, and
   `WORKERS`/`ENV`/build hash keys.
2. Helm Secret placement currently covers only `BCGPT_SECRET_KEY`, `DATABASE_URL`, `OPENAI_API_KEY`, and
   `RAG_EMBEDDING_MODEL_API_KEY`.
3. Compose production with DB provides Redis but does not enable the Redis-backed Socket.IO manager.
4. `PersistentConfig` auth/API-key rows need explicit owner policy because env values are seed/defaults, not
   always active runtime values.
5. The startup validation layer is real but narrow; it should not be cited as full config validation.
6. Provider rows have broad deployment gaps: plural OpenAI/Ollama keys, Gemini/Claude, LiteLLM, direct,
   image, and audio provider settings are mostly absent from `.env.example`, Compose, and Helm.
7. Current admin provider config APIs should be treated as secret-read surfaces until masked/write-only update
   semantics are designed.
8. Storage/vector rows are mostly absent from deployment examples: object-store credentials, vector DB
   topology, vector credentials, `RAG_FILE_MAX_COUNT`, and `SECURITY_SCAN_FILE_UPLOADS` are not exposed in the
   inspected `.env.example`, Compose, or Helm values/templates.
9. Local/PVC storage is documented through `/app/backend/data`, but SQL/object/vector lifecycle consistency,
   backup/restore ordering, reset behavior, and orphan reconciliation are not proven by config rows alone.
10. Observability and handoff rows are mostly absent from deployment examples: OTel, Prometheus, LangFuse,
    log-level, audit-detail, public URL, handoff, and SMTP rows are not exposed in inspected Compose/Helm
    templates, and `.env.example` exposes only `AI_INTERACTION_AUDIT_ENABLED` from this slice.
11. Declared OTel resource attribute/sampler rows and Prometheus exposition mode are not fully proven by code
    paths; they need explicit smoke tests before being advertised as production-ready behavior.
12. Compliance/security rows have split deployment coverage: `.env.example` exposes compliance module and chat
    retention flags, but Compose/Helm do not; security scanner, SIEM, AI transparency, rate-limit, audit
    retention, and security-event retention rows are absent from inspected deployment templates.
13. Compliance module flags are not uniformly hard gates, and security-event retention is manual/admin-only in
    observed code paths; document them as posture/config rows until route-level and scheduled-retention tests
    prove stronger behavior.
14. OAuth/LDAP/SCIM rows are mostly absent from deployment examples. SCIM appears in `.env.example` but not
    Helm Secret/Compose; OAuth and LDAP rows are absent from inspected `.env.example`, Compose, and Helm
    templates. LDAP has a startup import caveat, and OAuth provider registry behavior needs callback smoke
    tests after credential or metadata changes.
15. Search/external provider rows are absent from inspected `.env.example`, Compose, and Helm templates.
    Admin RAG config currently returns provider secret values, provider missing-key behavior is not uniform
    across engines, and only a small subset of provider failure behavior is covered by unit tests.
16. Advanced RAG/Agent quality rows have split deployment and admin coverage. `.env.example` exposes only a
    small subset, Helm exposes only `RAG_RERANKING_MODEL`, Compose/Docker expose none from the focused slice,
    Advanced RAG admin config covers only four feature groups, and agent admin config omits citation-audit and
    doc-structure toggles even though the explicit quality endpoint consumes them. Several features remain
    retrieval-only, log-only, endpoint-only, or not proven in the main chat path.
17. Frontend remote-error/logging is a decision boundary, not an implemented config surface. The logger is
    transport-ready but console-only, `handleError` and Web Vitals still use console paths, source maps are
    emitted without a documented upload/access policy, and no Sentry/self-hosted/browser OTel deployment rows
    exist in inspected source or manifests.
18. Public feature config needs schema alignment: the inspected `/api/config.features` block does not expose every
    frontend `Config.features` key in `src/lib/types/stores.ts` (`enable_direct_tools`,
    `enable_context_compression`, `enable_smart_query`), and `permissions.features` currently has narrower backend
    defaults/schema than the frontend chat controls read.

### Next Slices

1. Raw generated inventory and complete curated reference separation.
2. Replace the frontend remote-error/logging candidate rows with implemented rows after the owner chooses
   Sentry, browser OTel, a self-hosted endpoint, or an explicit no-remote-logging posture.

### Verification Commands

Commands used for this slice:

```bash
rg -n "BCGPT_SECRET_KEY|BCGPT_AUTH|DATABASE_URL|REDIS_URL|WEBSOCKET|JWT_|COOKIE|API_KEY|POSTGRES|OPENAI_API_KEY|DATA_DIR|FRONTEND_BUILD_DIR" \
  docker-compose*.yml .env.example kubernetes/helm/values.yaml Dockerfile

rg -n "ENABLE_(OPENAI|OLLAMA|GEMINI|CLAUDE)|OPENAI_API|OLLAMA|GEMINI_API|CLAUDE_API|LITELLM|ENABLE_DIRECT_CONNECTIONS|RAG_OPENAI|RAG_OLLAMA|IMAGES_|AUDIO_|AUTOMATIC1111|COMFYUI|DEEPGRAM" \
  backend/bcgpt .env.example docker-compose*.yml kubernetes/helm docs \
  --glob '!backend/bcgpt/static/**'

rg -n "STORAGE_PROVIDER|S3_|GCS_BUCKET_NAME|GOOGLE_APPLICATION_CREDENTIALS_JSON|AZURE_STORAGE|RAG_FILE_MAX|FILE_MAGIC_VALIDATION_ENABLED|SECURITY_SCAN_FILE_UPLOADS|VECTOR_DB|QDRANT_|MILVUS_|OPENSEARCH_|ELASTICSEARCH_|PGVECTOR_" \
  backend/bcgpt .env.example Dockerfile docker-compose*.yml kubernetes/helm docs \
  --glob '!backend/bcgpt/static/**'

rg -n "ENABLE_OTEL|OTEL_|PROMETHEUS_METRICS_ENABLED|RAG_TRACING_ENABLED|LANGFUSE_|AI_INTERACTION_AUDIT_ENABLED|AUDIT_LOG_LEVEL|GLOBAL_LOG_LEVEL|_LOG_LEVEL|WEBHOOK_URL|ENABLE_USER_WEBHOOKS|BCGPT_URL|HANDOFF_|HANDOFF_SMTP|HANDOFF_EMAIL_FROM" \
  backend/bcgpt .env.example Dockerfile docker-compose*.yml kubernetes/helm docs \
  --glob '!backend/bcgpt/static/**'

rg -n "SENTRY|FRONTEND_.*LOG|REMOTE_.*LOG|BROWSER_.*OTEL|VITE_.*SENTRY|VITE_.*OTEL|PUBLIC_.*SENTRY|PUBLIC_.*OTEL|PUBLIC_.*LOG|logger.addTransport|LogTransport|web-vitals|console\\.(log|warn|error|info|debug)" \
  src package.json bun.lock vite.config.ts .env.example Dockerfile docker-compose*.yml kubernetes/helm docs

rg -n "COMPLIANCE_|SECURITY_|CHAT_RETENTION|AUDIT_RETENTION|AI_TRANSPARENCY|AI_NOTIFICATION|AI_DISCLAIMER|AI_RESPONSE_LABEL|RATE_LIMIT_CHAT|SIEM|CANARY" \
  backend/bcgpt .env.example Dockerfile docker-compose*.yml kubernetes/helm docs \
  --glob '!backend/bcgpt/static/**'

rg -n "ENABLE_OAUTH|OAUTH_|GOOGLE_CLIENT|MICROSOFT_CLIENT|GITHUB_CLIENT|OPENID_|ENABLE_LDAP|LDAP_|SCIM_" \
  backend/bcgpt .env.example Dockerfile docker-compose*.yml kubernetes/helm docs \
  --glob '!backend/bcgpt/static/**'

rg -n "ENABLE_RAG_WEB_SEARCH|RAG_WEB_SEARCH|BYPASS_WEB_SEARCH|SEARXNG|GOOGLE_PSE|NAVER_|BRAVE_SEARCH|KAGI_SEARCH|MOJEEK|BOCHA|SERPSTACK|SERPER|SERPLY|TAVILY|SEARCHAPI|SERPAPI|JINA|BING_SEARCH|EXA_API|PERPLEXITY|RAG_WEB_LOADER|PLAYWRIGHT|FIRECRAWL|YOUTUBE_LOADER" \
  backend/bcgpt src .env.example Dockerfile docker-compose*.yml kubernetes/helm docs \
  --glob '!backend/bcgpt/static/**'

rg -n "RAG_(HYDE|QUERY_EXPANSION|STEP_BACK|RRF|RULE_BASED|LLM_RERANKING|CRAG|DOC_GRADING|EVIDENCE_RECONCILIATION|MMR|CHUNK_QUALITY|COLUMN_PROFILER|MULTI_HOP|MULTI_QUERY|PARENT_CHILD|SEMANTIC_CACHE|CONTEXTUAL|CROSS_ENCODER|GRAPH|EVALUATION|TOP_K|RELEVANCE|RERANKING|TEMPLATE|FULL_CONTEXT)|CONTENT_ISOLATION|QUERY_REWRITE_ENTITY_GUARD|AGENT_DEFAULT|AGENT_OPERATOR|AGENT_QUALITY|WORKFLOW_|MULTI_AGENT|QUALITY_|LETTUCE" \
  backend/bcgpt src .env.example Dockerfile docker-compose*.yml kubernetes/helm docs \
  --glob '!backend/bcgpt/static/**'

python - <<'PY'
# AST/text inventory script from CONFIG_REFERENCE_CATALOG_PLAN_2026-06-23.md
PY
```

Before expanding this reference, re-run the AST inventory and compare new rows against `.env.example`,
Compose, Helm, Dockerfile, and frontend build-time constants.

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

## Contributing to BCGPT

Welcome, contributors! Your interest in contributing to BCGPT is greatly appreciated. This document guides you through the process, ensuring your contributions enhance the project effectively.

### Key Points

#### Ollama vs. BCGPT

It's crucial to distinguish between Ollama and BCGPT:

- **BCGPT** focuses on providing an intuitive and responsive web interface for chat interactions, with multi-agent orchestration, workflow automation, and enterprise-grade AI features.
- **Ollama** is the underlying technology that powers local model inference.

If your issue or contribution pertains directly to the core Ollama technology, please direct it to the appropriate [Ollama project repository](https://ollama.com/). BCGPT's repository is dedicated to the web interface and backend services.

#### Reporting Issues

Noticed something off? Have an idea? Check our [Issues tab](https://github.com/bccard-ai/bcgpt-webui/issues) to see if it's already been reported or suggested. If not, feel free to open a new issue. When reporting an issue, please follow our issue templates. These templates are designed to ensure that all necessary details are provided from the start, enabling us to address your concerns more efficiently.

> [!IMPORTANT]
>
> - **Template Compliance:** Please be aware that failure to follow the provided issue template, or not providing the requested information at all, will likely result in your issue being closed without further consideration. This approach is critical for maintaining the manageability and integrity of issue tracking.
> - **Detail is Key:** To ensure your issue is understood and can be effectively addressed, it's imperative to include comprehensive details. Descriptions should be clear, including steps to reproduce, expected outcomes, and actual results. Lack of sufficient detail may hinder our ability to resolve your issue.

#### Scope of Support

We've noticed an uptick in issues not directly related to BCGPT but rather to the environment it's run in, especially Docker setups. While we strive to support Docker deployment, understanding Docker fundamentals is crucial for a smooth experience.

- **Docker Deployment Support**: BCGPT supports Docker deployment. Familiarity with Docker is assumed. For Docker basics, please refer to the [official Docker documentation](https://docs.docker.com/get-started/overview/).

- **Advanced Configurations**: Setting up reverse proxies for HTTPS and managing Docker deployments requires foundational knowledge. There are numerous online resources available to learn these skills. Ensuring you have this knowledge will greatly enhance your experience with BCGPT and similar projects.

### Tech Stack (v2.0)

BCGPT v2.0 uses the following stack. Familiarize yourself before contributing:

#### Frontend

- **Svelte 5** with runes (`$state`, `$derived`, `$effect`, `$props`) — legacy `export let` / `$:` syntax is deprecated
- **SvelteKit** for routing and SSR
- **Tailwind CSS v4** with `@import 'tailwindcss'` and `@tailwindcss/postcss`
- **TypeScript 5.9+** with strict mode
- **Vite 6** as the build tool

#### Backend

- **Python 3.11+** with FastAPI
- **bcgpt** package with `agent/`, `providers/`, `utils/` modules
- **Pydantic v2** for data validation

#### Testing & Quality

- **Vitest 4** for frontend unit tests
- **Cypress** for E2E tests
- **ESLint 10** + **Prettier** for code formatting
- **Ruff** for Python linting

- **pytest** for backend unit tests — fast, dependency-light tests in `backend/bcgpt/test/unit/` (run: `cd backend && python -m pytest bcgpt/test/unit/ -v`). Currently 232 backend unit tests covering security scanners, auth/JWT, RAG components, and quality pipeline.

### Contributing

Looking to contribute? Here's how you can help:

#### Pull Requests

We welcome pull requests. Before submitting one, please:

1. Open a discussion regarding your ideas [here](https://github.com/bccard-ai/bcgpt-webui/discussions/new/choose).
2. Follow the project's coding standards and include tests for new features.
3. Update documentation as necessary.
4. Write clear, descriptive commit messages.
5. It's essential to complete your pull request in a timely manner. We move fast, and having PRs hang around too long is not feasible. If you can't get it done within a reasonable time frame, we may have to close it to keep the project moving forward.

##### Svelte 5 Guidelines

When working on frontend code:

- Use **runes** (`$state`, `$derived`, `$effect`, `$props`) instead of legacy reactive declarations (`$:`, `export let`)
- Use `{#snippet}` and `@render` for component composition instead of slots where applicable
- Follow the patterns established in existing components — check nearby files for conventions
- All new components MUST use Svelte 5 runes syntax

##### Backend Guidelines

When working on backend code:

- The backend is organized under `backend/bcgpt/`
- New providers go in `providers/`, new agent capabilities in `agent/`
- Use Pydantic v2 models for all API schemas
- Follow the existing async patterns in the codebase

#### Documentation & Tutorials

Help us make BCGPT more accessible by improving documentation, writing tutorials, or creating guides on setting up and optimizing the web UI.

#### Translations and Internationalization

Help us make BCGPT available to a wider audience. We use JSON files to store translations. You can find the existing translation files in the `src/lib/i18n/locales` directory. Each directory corresponds to a specific language, for example, `en-US` for English (US), `fr-FR` for French (France) and so on. You can refer to [ISO 639 Language Codes](http://www.lingoes.net/en/translator/langcode.htm) to find the appropriate code for a specific language.

To add a new language:

- Create a new directory in the `src/lib/i18n/locales` path with the appropriate language code as its name. For instance, if you're adding translations for Spanish (Spain), create a new directory named `es-ES`.
- Copy the American English translation file(s) (from `en-US` directory in `src/lib/i18n/locale`) to this new directory and update the string values in JSON format according to your language. Make sure to preserve the structure of the JSON object.
- Add the language code and its respective title to languages file at `src/lib/i18n/locales/languages.json`.

#### Questions & Feedback

Got questions or feedback? Open an issue. We're here to help!

### Thank You!

Your contributions, big or small, make a significant impact on BCGPT. We're excited to see what you bring to the project!

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

## Security Policy

Our primary goal is to ensure the protection and confidentiality of sensitive data stored by users on BCGPT.

### Supported Versions

| Version | Supported          |
| ------- | ------------------ |
| 2.x     | :white_check_mark: |
| 1.x     | :x:                |
| others  | :x:                |

### Zero Tolerance for External Platforms

Based on a precedent of an unacceptable degree of spamming and unsolicited communications from third-party platforms, we forcefully reaffirm our stance. **We refuse to engage with, join, or monitor any platforms outside of GitHub for vulnerability reporting.** Our reasons are not just procedural but are deep-seated in the ethos of our project, which champions transparency and direct community interaction inherent in the open-source culture. Any attempts to divert our processes to external platforms will be met with outright rejection. This policy is non-negotiable and understands no exceptions.

Any reports or solicitations arriving from sources other than our designated GitHub repository will be dismissed without consideration. We've seen how external engagements can dilute and compromise the integrity of community-driven projects, and we're not here to gamble with the security and privacy of our user community.

### Reporting a Vulnerability

We appreciate the community's interest in identifying potential vulnerabilities. However, effective immediately, we will **not** accept low-effort vulnerability reports. To ensure that submissions are constructive and actionable, please adhere to the following guidelines:

Reports not submitted through our designated GitHub repository will be disregarded, and we will categorically reject invitations to collaborate on external platforms. Our aggressive stance on this matter underscores our commitment to a secure, transparent, and open community where all operations are visible and contributors are accountable.

1. **No Vague Reports**: Submissions such as "I found a vulnerability" without any details will be treated as spam and will not be accepted.

2. **In-Depth Understanding Required**: Reports must reflect a clear understanding of the codebase and provide specific details about the vulnerability, including the affected components and potential impacts.

3. **Proof of Concept (PoC) is Mandatory**: Each submission must include a well-documented proof of concept (PoC) that demonstrates the vulnerability. If confidentiality is a concern, reporters are encouraged to create a private fork of the repository and share access with the maintainers. Reports lacking valid evidence will be disregarded.

4. **Required Patch Submission**: Along with the PoC, reporters must provide a patch or actionable steps to remediate the identified vulnerability. This helps us evaluate and implement fixes rapidly.

5. **Streamlined Merging Process**: When vulnerability reports meet the above criteria, we can consider them for immediate merging, similar to regular pull requests. Well-structured and thorough submissions will expedite the process of enhancing our security.

**Non-compliant submissions will be closed, and repeat violators may be banned.** Our goal is to foster a constructive reporting environment where quality submissions promote better security for all users.

### Product Security

We regularly audit our internal processes and system architecture for vulnerabilities using a combination of automated and manual testing techniques. We also perform SAST and SCA scans as part of our CI pipeline.

For immediate concerns or detailed reports that meet our guidelines, please create an issue in our [issue tracker](https://github.com/bccard-ai/bcgpt-webui/issues).

---

_Last updated on **2026-06-17**._

## License and attribution

BCGPT WebUI is licensed under the [Apache License 2.0](LICENSE). It originated from [Open WebUI](https://github.com/open-webui/open-webui) v0.6.0; the required upstream notices are retained in [NOTICE](NOTICE).
