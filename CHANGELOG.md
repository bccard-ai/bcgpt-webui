# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [1.0.0] - 2026-06-05

BCGPT WebUI v1.0.0 consolidates all changes since the initial v1.0.0 release (2026-05-20). The project was forked from [Open WebUI](https://github.com/open-webui/open-webui) v0.6.0 and completely redesigned to comply with Korea's AI Basic Act, financial-sector AI guidelines, and CVE vulnerability remediation — battle-tested in BC Card's enterprise environment.

### Added

#### 🏢 Branding & Project Structure

- 🔄 **BCGPT WebUI Rebranding**: Replaced all Open WebUI references with BCGPT — backend Python package (`open_webui` → `bcgpt`), CLI command (`bcgpt serve`), Docker image (`ghcr.io/bcgpt/bcgpt`), Redis key prefix (`bcgpt:config:*`), PWA manifest, favicon, meta tags, and splash screen fully customized
- 🎨 **BCGPT Custom Splash Screen**: Boot-log terminal-style splash screen with Korean/English bilingual error messages ("다시 시도 / Retry") and spinner animation
- 🖼️ **BCGPT Custom Assets**: SVG favicon (BCGPT text logo), BCGPT brand logo, BC Card corporate logo, static assets (favicons, splash screens, provider icons)
- 📦 **pip Package Distribution**: Install via `pip install bcgpt`

#### 🔀 Svelte 5 Migration (310 Components)

- 🏗️ **Full Svelte 5 Runes Migration**: Migrated 310 out of 328 `.svelte` components to Svelte 5 runes — `$state()`, `$derived()`, `$effect()`, `$props()` replacing legacy `export let`, `let:` directives, and `$:` reactive statements
- 🧩 **Svelte 5 Snippets & Render**: 43 components converted to use `{#snippet}` blocks and `{@render}` tags replacing legacy `<slot>` patterns
- 📦 **Svelte 5 Ecosystem**: Upgraded to `svelte ^5.0.0`, `svelte-check ^4.0.0`, `eslint-plugin-svelte ^3.9.0`, `prettier-plugin-svelte ^4.0.0`, and `@sveltejs/vite-plugin-svelte ^5.0.0`
- 🧱 **Headless UI Components**: Added `bits-ui ^2.18.1` (Svelte 5 compatible headless primitives), `paneforge ^1.0.2` (pane layouts), and `svelte-sonner ^1.1.1` (toast notifications)
- 🎊 **Svelte 5 Compatible Libraries**: `svelte-confetti ^2.3.2`, `@xyflow/svelte ^1.5.2`

#### 🎨 Tailwind CSS v4 Migration

- 🎨 **Tailwind CSS 3 → 4**: Full migration to Tailwind CSS v4 (`tailwindcss ^4.3.0`) with `@import 'tailwindcss'` syntax, `@tailwindcss/postcss` PostCSS plugin, and base-layer compatibility styles for border-color defaults
- 📦 **Typography Plugin Update**: `@tailwindcss/typography ^0.5.19` with v4 compatibility
- 🔍 **Container Queries**: `@tailwindcss/container-queries ^0.1.1` added

#### ⚡ Build Toolchain Upgrade

- ⚡ **Vite 5 → 6**: Upgraded to `vite ^6.4.2` with ES module worker format and improved build performance
- 📦 **SvelteKit 2.61**: Updated `@sveltejs/kit ^2.61.1` with latest adapter-static configuration
- 📝 **TypeScript 5.9**: Upgraded to `typescript ^5.9.3` with `typescript-eslint ^8.60.0`
- 🧪 **Vitest 4**: Upgraded to `vitest ^4.1.7` with dedicated `vitest.config.ts` configuration
- 🖋️ **ESLint 10**: Upgraded to `eslint ^10.4.0` with `@eslint/js ^10.0.1`
- 📊 **rollup-plugin-visualizer ^7.0.1**: Bundle analysis for production builds

#### 🤖 Agent System & AI Features

- 🤖 **Agent Module**: New backend `agent/` module with autonomy, multi-agent orchestration, quality assessment, tool loop, and workflow sub-modules — replacing the legacy pipeline system
- 🧠 **OpenAI Reasoning Model Adapter**: Backend adapter for OpenAI reasoning models — o1, o3, o4-mini, and GPT-5 series with appropriate parameter handling
- 🤖 **AI Transparency Banner**: Chat UI displays an AI-generated content transparency notice, configurable per deployment
- 📊 **Verbosity Parameter**: Chat API supports a `verbosity` parameter for controlling response detail level

#### 🔍 Production RAG Pipeline (from open-moai)

Pre-retrieval — query understanding before search:

- 🧠 **HyDE (Hypothetical Document Embeddings)** — LLM generates a hypothetical answer document, embeds it, and uses it for retrieval instead of the raw query. Includes Korean/English normalization (code fence removal, length capping, minimum length check). New module: `backend/bcgpt/retrieval/query/hyde.py`
- 🔎 **Query Expansion** — LLM generates N alternative phrasings of the same question, deduplicates them, and searches across all variants. New module: `backend/bcgpt/retrieval/query/expansion.py`
- 🪜 **Step-Back Prompting** — Detects Korean/English questions and generates a broader, more abstract version to improve recall on conceptual queries. Includes Korean question particle detection (얼마, 몇, 무슨, 무엇, 어디, 언제, 누구, 어떻게, 왜, 어떤). New module: `backend/bcgpt/retrieval/query/step_back.py`

Retrieval — multi-signal search:

- 🔄 **RRF (Reciprocal Rank Fusion)** — Combines multi-track search results using `1/(k+rank+1)` scoring with configurable weights and top-K selection. New module: `backend/bcgpt/retrieval/rrf.py`
- 🔀 **Hybrid Search Upgrade** — Replaced naive LangChain EnsembleRetriever with manual BM25 + vector + RRF fusion for precise rank-based scoring. Updated: `backend/bcgpt/retrieval/utils.py`
- 🕸️ **Multi-Hop Retrieval** — Automatically detects complex multi-part questions, decomposes them into ordered sub-queries via LLM with dependency tracking, retrieves for each, and merges results. New module: `backend/bcgpt/retrieval/advanced/multi_hop.py`

Post-retrieval — result quality refinement:

- 📏 **Rule-Based Reranking** — 5-component heuristic scoring: exact match, title hit, TF similarity, position bonus, coverage ratio. New module: `backend/bcgpt/retrieval/reranking/rule_based.py`
- 🤖 **LLM Reranking** — LLM scores document relevance on a 1-10 scale with robust JSON parsing and fallback. New module: `backend/bcgpt/retrieval/reranking/llm_rerank.py`
- ✅ **CRAG Quality Assessment** — Composite retrieval quality score (similarity 45%, keyword overlap 25%, coverage 15%, diversity 15%) with sufficient/partial/insufficient verdicts. Logs quality metrics for monitoring. New module: `backend/bcgpt/retrieval/quality/crag.py`
- 📊 **Document Grading** — Per-document relevance assessment via heuristic + LLM grading (correct / ambiguous / incorrect), filtering out incorrect documents before response generation. New module: `backend/bcgpt/retrieval/quality/doc_grading.py`

Advanced — evidence-level processing:

- 🔗 **Evidence Reconciliation** — Jaccard-based redundancy detection, topic grouping, and numeric/negation conflict identification across retrieved documents. Logs findings for transparency. New module: `backend/bcgpt/retrieval/advanced/reconciliation.py`

#### ⚙️ RAG Backend Configuration

- 🔧 **25 New PersistentConfig Variables** — All advanced RAG features configurable via environment variables in `backend/bcgpt/config.py`:
  - `RAG_HYDE_ENABLED`, `RAG_HYDE_MODEL`
  - `RAG_QUERY_EXPANSION_ENABLED`, `RAG_QUERY_EXPANSION_N`
  - `RAG_STEP_BACK_ENABLED`
  - `RAG_RRF_K`
  - `RAG_RULE_BASED_RERANKING_ENABLED`
  - `RAG_LLM_RERANKING_ENABLED`
  - `RAG_CRAG_ENABLED`
  - `RAG_DOC_GRADING_ENABLED`
  - `RAG_EVIDENCE_RECONCILIATION_ENABLED`
  - `RAG_MULTI_HOP_ENABLED`, `RAG_MULTI_QUERY_WEIGHT`
- 🔌 **Main.py Wiring** — All new config variables wired to `app.state.config.*` for runtime access
- 🎛️ **Per-Agent RAG Overrides** — `_get_rag_override()` in `middleware.py` reads `model.info.meta.rag_settings` and overrides global config per request, enabling agent-specific retrieval tuning

#### 🎨 Middleware Orchestration

- 🏗️ **Full Pipeline Integration** — `chat_completion_files_handler()` in `middleware.py` now orchestrates the complete RAG pipeline: pre-retrieval (HyDE → query expansion → step-back) → retrieval (hybrid + RRF) → post-retrieval (rule-based reranking → LLM reranking → CRAG → doc grading → evidence reconciliation) → context injection
- 🔀 **Graceful Feature Toggling** — Each pipeline stage checks its feature flag and skips cleanly when disabled, maintaining backward compatibility

#### 🖥️ Frontend

- 🔧 **API Client Consolidation**: 29 API modules migrated from raw `fetch` to singleton `ApiClient` pattern — 7,000L → 1,500L (78% reduction). Added `webuiClient`, `ollamaClient`, `openaiClient`, `audioClient`, `imagesClient`, `retrievalClient`, `agentsClient` singletons with automatic CSRF token injection
- 📦 **Utility Module Split**: 1,182L monolithic `utils/index.ts` split into 11 domain modules (`string`, `stream`, `chat-history`, `crypto`, `canvas`, `date`, `clipboard`, `text`, `chat-import`, `prompt`, `openapi`, `misc`) with barrel re-export for backward compatibility
- 🏷️ **Store Type Extraction**: 16 inline store types extracted to `src/lib/types/stores.ts` with re-export for backward compatibility
- 🔄 **APIs/index.ts Refactoring**: Migrated from 1,429L to 832L with `webuiClient` singleton for `/api/` endpoints (separate from `apiClient` for `/api/v1/` endpoints). Fixed production URL routing bugs where `WEBUI_BASE_URL=''` caused `/api/v1/api/...` misrouting. ~30 functions migrated to proper client singletons
- 🎛️ **RetrievalSettings.svelte** — New agent-level RAG configuration component with base/custom toggle, k, r, hybrid, k_reranker, query_rewrite, hyde, and rag_template settings. New file: `src/lib/components/workspace/Models/RetrievalSettings.svelte`
- 📝 **ModelEditor.svelte Integration** — RetrievalSettings integrated into agent editor between knowledge and tools selectors, with state persistence and save handler
- 📦 **QuerySettings Type Extension** — Added `hybrid` and `k_reranker` fields to `QuerySettings` in `src/lib/apis/retrieval/index.ts`

#### 🗄️ RAG Management UI

- 📚 **KnowledgeBaseDetail.svelte** — New detail view for knowledge bases with document listing and metadata. New file: `src/lib/components/admin/RagManager/KnowledgeBaseDetail.svelte`
- 🗃️ **VectorDBCollectionDetail.svelte** — New detail view for Qdrant collections with document inspection. New file: `src/lib/components/admin/RagManager/VectorDBCollectionDetail.svelte`
- 🏷️ **Source-Based Labeling** — Knowledge bases and collections display with source-accurate labels (no more "undefined Collection")
- 🎨 **Differentiated Icons** — Knowledge base and vector DB collection chips use distinct icons for clear visual distinction

#### 📋 Audit System

- 📊 **Audit Overview Enhancements** — Enhanced admin audit overview with improved filtering and display. Updated: `src/lib/components/admin/Audit/Overview.svelte`
- 🔍 **Audit LogDetailModal** — New audit log detail modal for detailed log inspection. New file: `src/lib/components/admin/Audit/LogDetailModal.svelte`
- 🔍 **Audit Router Extensions** — New audit query endpoints for detailed activity tracking. Updated: `backend/bcgpt/routers/audit.py`
- 📊 **Personal Data Tracking** — Dedicated view for personal data access records with subject and action details

#### 🔒 Security Hardening (15 Items)

- 🛡️ **Security Header Middleware**: Applied baseline security headers — `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: strict-origin-when-cross-origin`. HSTS, CSP, and Permissions-Policy are optionally configurable via environment variables
- 🔑 **JWT Secret Key Validation**: Application refuses to start if `WEBUI_SECRET_KEY` is empty or set to known defaults (`t0p-s3cr3t`)
- 🔐 **Account Lockout (Lockout-DoS Mitigation)**: 5 failed login attempts triggers a 30-minute lockout. Admin accounts are exempt. Counter resets after lockout expiry
- 🚫 **Account Enumeration Prevention**: Login failures return the same generic error regardless of account existence or lockout status
- ⏱️ **JWT Expiration Configuration**: Default changed from `-1` (indefinite) to `7d`. Configurable via `JWT_EXPIRES_IN` environment variable
- 🌐 **SSRF Protection (Webhooks)**: Notification webhook URLs validated before dispatch — blocks private/loopback/link-local/metadata IPs (169.254.169.254), allows only http/https, blocks redirects
- 🔍 **SSRF Protection (RAG Web Fetch)**: Robust `ipaddress`-based IP blocking — loopback/link-local/metadata always blocked regardless of `ENABLE_RAG_LOCAL_WEB_FETCH` setting. DNS failures are rejected
- 🚷 **Code Execution Authorization Gate**: Non-admin users require both `ENABLE_CODE_EXECUTION` and `features.code_interpreter` permissions to execute code
- 📝 **IDOR Fix (Channel Messages)**: Added ownership or admin verification for message edit and delete operations
- 📁 **IDOR Fix (File Processing)**: Added owner/admin/knowledge-base access verification when accessing arbitrary files by `file_id` at `/process/file`
- 🔇 **Secret Log Leak Prevention**: Removed raw token/PII logging from OAuth callback failure paths. API keys logged as `***redacted***`
- 🍪 **Secure Cookie Settings**: `SameSite` and `Secure` flag support via environment variables
- 🛑 **In-Memory Rate Limiter**: Token-bucket based — signin (10/60s), signup (5/60s), chat/completions (30/60s). Returns HTTP 429
- 📋 **Structured Audit Logging**: ASGI middleware recording request/response bodies, user ID, source IP, and User-Agent. Configurable via `AUDIT_LOG_LEVEL` (NONE/METADATA/REQUEST/REQUEST_RESPONSE)
- 🔐 **Frontend 401 Interceptor Fix**: Global fetch interceptor responds only to 401 (not 403), excludes auth flows and `/auth` pages
- 🛡️ **CSRF Protection**: New `utils/csrf.py` module providing CSRF token validation for state-changing requests

#### ⚡ Python Async Optimization

- 🌐 **Full aiohttp Migration**: Migrated all outbound HTTP calls from synchronous `requests` to `aiohttp` — Ollama API, OpenAI API, TTS/STT, OAuth, Pipeline, and Jupyter code interpreter. Prevents event loop blocking
- ⏱️ **Configurable HTTP Timeouts**: Task-specific timeout settings via `AIOHTTP_CLIENT_TIMEOUT` (default 300s) and `AIOHTTP_CLIENT_TIMEOUT_MODEL_LIST` (default 10s) environment variables
- 🔄 **Parallel Multi-Endpoint Model Fetching**: `asyncio.gather()` fetches model lists from multiple Ollama/OpenAI endpoints in parallel — dramatically reduces model list loading latency in multi-server environments
- 🧵 **asyncio.to_thread Offloading**: ~40 call sites in knowledge base, file, image, search, and folder routers offload synchronous DB/storage operations to threads — maintains event loop responsiveness
- 🔀 **ThreadPoolExecutor Hybrid Search**: RAG hybrid search (BM25 + embedding) runs in parallel via ThreadPoolExecutor. RAG source search processed asynchronously with `loop.run_in_executor()`
- 📄 **aiofiles Async File I/O**: Applied `aiofiles.open()` for TTS audio file writes
- 📡 **SSE Streaming Pipeline**: End-to-end async chain from LLM backend → `StreamingResponse` → buffered Ollama-to-OpenAI streaming conversion (buffer size 3) → `asyncio.Queue`-based real-time chat event streaming
- 🌐 **Async Web Scraping/RAG Loaders**: Four async web loaders (SafeWebBaseLoader, SafePlaywrightURLLoader, SafeFireCrawlLoader, SafeTavilyLoader) — exponential backoff retry, async rate limiting, SSL verification, and async Playwright browser automation
- 🗄️ **Database Connection Pooling**: SQLAlchemy `QueuePool` — configurable via `DATABASE_POOL_SIZE`, `DATABASE_POOL_MAX_OVERFLOW`, `DATABASE_POOL_TIMEOUT`, and `DATABASE_POOL_RECYCLE` environment variables
- 📈 **aiocache Model Caching**: `@cached(ttl=1)` decorator on model list endpoints prevents short-term duplicate API calls
- 📊 **OpenTelemetry Async Hooks**: Async request/response tracing support for both aiohttp and httpx
- 🔄 **Async Task Management System**: UUID-tracked `asyncio.Task` — task creation/cancellation/CleanedError handling, cleanup callbacks, and background periodic tasks (usage pool cleanup)

#### 🇰🇷 Korean/Multilingual RAG Optimization

- 🧠 **Korean-Optimized Embedding Model**: Applied `BAAI/bge-m3` multilingual embedding model — significant RAG performance improvement for Korean and other Asian languages
- 🔄 **Korean-Optimized Reranker**: Applied `BAAI/bge-reranker-v2-m3` multilingual reranker
- 🌐 **External Embedding/Reranking API Configuration**: `RAG_EMBEDDING_MODEL_URI`, `RAG_EMBEDDING_MODEL_API_KEY`, `RAG_RERANKING_MODEL_URI`, and `RAG_RERANKING_MODEL_API_KEY` environment variables for vLLM/OpenAI-compatible embedding API integration
- 📝 **Korean Default Prompt Suggestions**: Changed all default prompt examples to Korean — "공부 도우미", "아이디어 제안", "재미있는 이야기", "코드 샘플 부탁", etc.

#### 🔌 Offline Deployment Support

- 📴 **Offline Mode**: `OFFLINE_MODE` environment variable blocks HuggingFace model downloads (`HF_HUB_OFFLINE=1`). Enables stable deployment in air-gapped environments
- 📂 **Local Model Cache**: `SENTENCE_TRANSFORMERS_HOME=./models` setting serves embedding models from a local directory

#### 🗄️ Production Database

- 🐘 **PostgreSQL Backend**: PostgreSQL + pgvector support replacing SQLite — production-grade stability and scalability
- 🔍 **Qdrant Vector DB**: Qdrant vector database integration replacing ChromaDB — improved large-scale vector search performance

#### 🔍 Search & Retrieval

- 🇰🇷 **Naver Search Integration**: Added Naver (네이버) as a web search provider for Korean-language search — `backend/bcgpt/retrieval/web/naver.py`
- 🔧 **Backend Search Improvements**: Refactored search routing with cleaner provider abstraction

#### 🌐 i18n

- 🌐 **Hardcoded Korean → i18n Keys**: Onboarding, authentication, and layout components converted from hardcoded Korean strings to i18n translation keys for proper multilingual support
- 🇰🇷 **Korean Translations** — Added Korean translations for new RAG management and audit UI elements
- 🇺🇸 **English Translations** — Added English translations for new RAG management and audit UI elements

#### 🎨 UI/UX Improvements

- 🖱️ **Smooth Scrolling**: Chat message auto-scroll changed from instant jump to smooth behavior
- 📝 **Code Block Font Size**: Applied `text-sm` class to code blocks for improved readability
- 🔐 **Auth Page UI Improvements**: Enhanced input field styling — borders, rounded corners, and background colors
- ⚙️ **Admin/Workspace Components**: Settings, model, prompt editor UI updates
- 💬 **Chat Components**: Message, markdown, evaluation modal improvements
- 🔀 **Svelte 5 Migration Fixes**: `svelte:self` → self-import, `<slot>` → `{#snippet}`/`{@render}`, `RichTextInput` `state_unsafe_mutation` fix, `Tooltip` instance cleanup
- 🎨 **Admin Settings Improvements**: Enhanced admin settings UI with logo upload functionality

#### 📜 License & Legal

- 📜 **License change to Apache 2.0**: Project license changed to Apache License 2.0. The original Open WebUI v0.6.0 code retains its BSD 3-Clause License with attribution to Timothy Jaeryang Baek. A NOTICE file was added for fork attribution and third-party license compliance.
- 🎨 **Provider-based model icons in Evaluations**: Admin > Evaluations page now displays provider-specific icons for arena models (OpenAI, Gemini, Claude, Ollama, vLLM, DeepSeek, Perplexity, GLM) matching the Models settings page. Unrecognized models fall back to the BC Card logo.

### Changed

- 💽 **Frontend Framework**: Svelte 4 → Svelte 5 (310 components migrated)
- 🎨 **CSS Framework**: Tailwind CSS 3 → Tailwind CSS 4
- ⚡ **Build Tool**: Vite 5 → Vite 6
- 📝 **TypeScript**: 5.x → 5.9.3
- 🧪 **Test Framework**: Vitest 1.x → Vitest 4
- 🔌 **Dev Port**: 8080 → 8090
- 🌐 **i18n Approach**: Hardcoded Korean → i18n key-based translations
- 📦 **Backend Module**: Complete `open_webui` → `bcgpt` restructuring with new module hierarchy (`agent/`, `providers/`, `utils/`)
- 💽 **Database Default**: SQLite → PostgreSQL (`DATABASE_URL=postgres://...`)
- 🔍 **Vector DB Default**: ChromaDB → Qdrant
- 🐳 **Docker Image**: `ghcr.io/open-webui/open-webui` → `ghcr.io/bcgpt/bcgpt`
- 🔑 **Redis Key Prefix**: `open-webui:*` → `bcgpt:config:*`
- 🔒 **JWT Expiration Default**: `-1` (indefinite) → `7d`
- 🔒 **Tracking Prevention Enabled by Default**: `SCARF_NO_ANALYTICS=true`, `DO_NOT_TRACK=true`, `ANONYMIZED_TELEMETRY=false`
- 📝 **Default Prompt Suggestion Language**: English → Korean
- 🔀 **Hybrid Search Implementation** — Replaced LangChain EnsembleRetriever (0.5/0.5 weighted) with manual BM25 + vector + RRF fusion for better rank-based scoring control
- 🔀 **LangChain 0.3 → 1.x LTS Migration** — Upgraded LangChain ecosystem to v1.x for long-term support (0.3.x maintenance ends Dec 2026): langchain 0.3.30→1.3.4, langchain-core 0.3.86→1.4.1, langchain-community 0.3.27→0.4.2, langchain-text-splitters 0.3.11→1.1.2. Added langchain-classic 1.0.7 (required by langchain-community 0.4.x). Migrated `RerankCompressor` from Pydantic v1 `class Config` to v2 `model_config = ConfigDict(...)`. Fixed legacy import in `parent_child.py`
- 🔐 **JWT Key Strengthening**: Key generation upgraded from `randbytes(12)` to `randbytes(32)` for HS256 compliance
- 🗄️ **Model Cache TTL Increase**: OpenAI/Ollama `get_all_models()` cache TTL increased from 1s to 30s with duplicate call elimination
- 🔍 **RAG Parameter Tuning**: `TOP_K` 3→6, `TOP_K_RERANKER` 3→10, `RELEVANCE_THRESHOLD` 0.0→0.2, `RRF_K` 60→20, per-source diversity cap (`max_per_source=3`)
- 📋 **Frontend Chat List Optimization**: 8 call sites replaced redundant `getChatList` API calls with in-place `updateChatEntryInList` helper
- 📦 **Knowledge API Types** — Extended `KnowledgeBase`, `KnowledgeBaseFile`, and `AccessControlValue` types in `src/lib/apis/knowledge/index.ts`
- 🗄️ **Qdrant Backend** — Enhanced Qdrant vector DB integration with collection listing improvements
- 🔒 **Auth/Security Enhancements**: Environment variable structuring, auth router improvements, security header additions
- 🤖 **Agent Workflow Node Improvements**: API call nodes, conditional branching, plugin utility updates
- 🐍 **Python 3.13 Compatibility**: Updated `unstructured` to 0.16.19 and `rapidocr-onnxruntime` to 1.2.3
- 🌊 **Web Search/RAG Parallel Execution**: Parallel execution of web search and RAG retrieval for improved response latency
- 🔗 **Image Generation API**: Improved connection handling and error processing for OpenAI gpt-image model support
- 🔄 **Model Auto-Routing**: Single-connection model not found triggers automatic routing and registry refresh
- 🗜️ **aiohttp Brotli Fix**: Accept-Encoding header configuration to prevent Brotli encoding errors
- 🌊 **Streaming Timeout Handling**: Backend streaming response handler now properly handles `TimeoutError` with upstream connection cleanup
- 🔧 **Gemini Model Name Cleanup**: Removed preview tags from Gemini model names in backend
- 🌊 **Web Search Error Handling**: Replaced bare `log.exception(e)` with structured `log.warning()` in `process_web_search` handler. Added early empty-results validation, empty content check after web loader, proper `HTTPException` re-raise in nested try/except, and graceful handling of `save_docs_to_vector_db` returning `False`
- 🌊 **Naver Search Resilience**: Added structured error aggregation with `_summarize_errors()`. Partial endpoint failure handling: raises `RuntimeError` only when all endpoints fail or no results returned. Logs warning with endpoint details for partial failures
- 🛡️ **Middleware Web Search Logging**: Added `_exception_message()` helper for consistent error message extraction. Replaced bare `log.exception(e)` with structured `log.warning()` in chat web search handler. Fixed error descriptions to include actual error reason. Fixed template literal bug (`"Searching "{{searchQuery}}""` → f-string)

### Fixed

- 🐛 **resolveUrl Absolute Path Bug**: Fixed URL resolution treating absolute paths as relative, causing 404 on auth endpoints
- 🐛 **resolveUrl Double-Slash**: Fixed double-slash in URLs when combining base URL with leading-slash paths
- 🛡️ **CSRF Token for Unauthenticated Requests**: Added `X-CSRF-Token` header echo-back for signin/signup requests (double-submit pattern), fixing 403 blocks from CSRF middleware
- 📤 **importChat Missing Export**: Restored missing `importChat` export used by Sidebar/RecursiveFolder
- 🖼️ **upload_image Async/Await**: Fixed `upload_file()` coroutine not being awaited — `'coroutine' object has no attribute 'id'`
- 🖼️ **gpt-image Model Minimum Size**: Enforced 1024×1024 minimum size for OpenAI gpt-image models
- 📄 **Demo Image**: Replaced `demo.gif` with `demo.png`
- 🏷️ **Knowledge Selector Labeling** — Fixed "undefined Collection" display when selecting knowledge bases in agent editor
- 🎨 **Knowledge Chip Icons** — Fixed generic grey icons for knowledge base and collection selections — now uses distinct, source-appropriate icons
- 📝 **onSelect Handler** — Fixed CustomEvent handling in Knowledge.svelte selector
- 📦 **FileItem Props** — Fixed missing prop in FileItem component
- 🛡️ **Error Handling**: AbortController timeout, image generation timeout, previous response error recovery
- 📦 **Missing langchain-text-splitters in requirements.txt**: Added `langchain-text-splitters>=1.1.2` to requirements.txt — was only in pyproject.toml, causing potential import failures in Docker builds
- 🔧 **Legacy LangChain Import**: Fixed `from langchain.text_splitter` in `parent_child.py` → `from langchain_text_splitters` (deprecated import path removed in LangChain v1)
- 🔄 **RerankCompressor Pydantic v2 Migration**: Replaced Pydantic v1 inner `class Config: extra = "forbid"; arbitrary_types_allowed = True` with Pydantic v2 `model_config = ConfigDict(extra="forbid", arbitrary_types_allowed=True)` for LangChain 1.x compatibility
- 🐛 **Auth Session Recovery on HMR Reload**: Fixed login breaking after Svelte 5 migration when Vite HMR triggers page reload during `goto('/')`. Auth page now validates HttpOnly session cookie in `onMount` and recovers session automatically with safe socket emit try-catch
- 🛡️ **Security Scanner JSON Parsing Robustness**: Added brace-matching fallback (extract outermost `{…}` via `find("{")`/`rfind("}")`) to `_parse_response` and `_parse_pii_verification` in LLM scanner, and `_parse_response` in guardrail scanner. Fixes "LLM output scan failed, failing open" when LLM returns JSON with leading whitespace or markdown wrapping
- 🐛 **Empty Document RAG Error**: Changed `raise ValueError(EMPTY_CONTENT)` to graceful `return False` with info logging in `save_docs_to_vector_db` when no documents remain after text splitting. Eliminates `HTTPException: 400: The content provided is empty` for edge cases
- 🔧 **Empty Collection Log Noise**: Downgraded empty collection warning from `log.warning` to `log.debug` in `query_doc_with_hybrid_search`. Empty collections are expected when no documents have been uploaded
- 🔧 **Unused Variable Cleanup**: Removed unused `_token` variable in CodeBlock.svelte and duplicate `groupedMessageIdsIdx` declaration in MultiResponseMessages.svelte. Fixed variable scoping in kokoro.worker.ts (renamed destructured `model_id` param to avoid outer scope leak)

### Removed

- 📦 **Pipeline Module**: Legacy pipeline system removed — replaced by the new agent module with multi-agent orchestration
- 👥 **Community Sharing**: Public resource sharing functionality removed for simplified enterprise deployment
- 💬 **Channels**: Discord/Slack-style channel features removed — focus on core chat functionality
- 🛡️ **Security Dashboard**: Standalone security dashboard removed — consolidated into admin settings
- 📦 **Unused Docker Compose**: Removed unnecessary Docker Compose configurations
- 🗑️ **Unnecessary Files**: Cleaned up legacy static assets and unused configuration files
- 📦 **Default Vector DB ChromaDB**: Replaced by Qdrant
- 📦 **Default Database SQLite**: Replaced by PostgreSQL
- 🔤 **English Default Prompt Suggestions**: Replaced by Korean prompts
- 🔄 **Handoff Feature**: Agent-to-human handoff button and functionality removed — not production-ready for current deployment scope

### Dependency Upgrades

#### Frontend

| Package                      | From    | To       |
| ---------------------------- | ------- | -------- |
| svelte                       | ^4.2.20 | ^5.0.0   |
| tailwindcss                  | ^3.x    | ^4.3.0   |
| vite                         | ^5.x    | ^6.4.2   |
| @sveltejs/kit                | ^2.x    | ^2.61.1  |
| @sveltejs/vite-plugin-svelte | ^3.x    | ^5.0.0   |
| typescript                   | ^5.x    | ^5.9.3   |
| vitest                       | ^1.x    | ^4.1.7   |
| eslint                       | ^8.x    | ^10.4.0  |
| prettier                     | ^3.x    | ^3.8.3   |
| marked                       | ^12.x   | ^18.0.4  |
| mermaid                      | ^10.x   | ^11.15.0 |
| i18next                      | ^23.x   | ^26.3.0  |
| zod                          | ^3.x    | ^4.4.3   |
| undici                       | ^6.x    | ^7.26.0  |
| uuid                         | ^9.x    | ^14.0.0  |
| dompurify                    | ^3.0.x  | ^3.4.7   |
| jspdf                        | ^2.x    | ^4.2.1   |
| dayjs                        | ^1.11.x | ^1.11.21 |

#### Backend (Python)

| Package                  | From    | To      |
| ------------------------ | ------- | ------- |
| FastAPI                  | 0.115.7 | 0.136.3 |
| uvicorn                  | 0.34.0  | 0.48.0  |
| pydantic                 | 2.10.6  | 2.13.4  |
| aiohttp                  | 3.11.11 | 3.13.5  |
| sqlalchemy               | 2.0.38  | 2.0.50  |
| alembic                  | —       | 1.18.4  |
| black                    | —       | 26.5.1  |
| boto3                    | —       | 1.43.17 |
| pillow                   | —       | 12.2.0  |
| pyjwt                    | —       | 2.13.0  |
| argon2-cffi              | —       | 25.1.0  |
| duckduckgo-search        | —       | 7.3.2   |
| firecrawl-py             | —       | 1.12.0  |
| langchain                | 0.3.30  | 1.3.4   |
| langchain-core           | 0.3.86  | 1.4.1   |
| langchain-community      | 0.3.27  | 0.4.2   |
| langchain-text-splitters | 0.3.11  | 1.1.2   |
| langchain-classic        | —       | 1.0.7   |

### Backward Compatibility

All new RAG features are **disabled by default**. Existing deployments will behave identically after upgrading — no configuration changes required. Enable features individually via environment variables when ready.

---

## [0.6.0] - 2025-03-31

### Added

- 🧩 **External Tool Server Support via OpenAPI**: Connect BCGPT to any OpenAPI-compatible REST server instantly—offering immediate integration with thousands of developer tools, SDKs, and SaaS systems for powerful extensibility. Learn more: https://github.com/bccard-ai/openapi-servers
- 🛠️ **MCP Server Support via MCPO**: You can now convert and expose your internal MCP tools as interoperable OpenAPI HTTP servers within BCGPT for seamless, plug-n-play AI toolchain creation. Learn more: https://github.com/bccard-ai/mcpo
- 📨 **/messages Chat API Endpoint Support**: For power users building external AI systems, new endpoints allow precise control of messages asynchronously—feed long-running external responses into BCGPT chats without coupling with the frontend.
- 📝 **Client-Side PDF Generation**: PDF exports are now generated fully client-side for drastically improved output quality—perfect for saving conversations or documents.
- 💼 **Enforced Temporary Chats Mode**: Admins can now enforce temporary chat sessions by default to align with stringent data retention and compliance requirements.
- 🌍 **Public Resource Sharing Permission Controls**: Fine-grained user group permissions now allow enabling/disabling public sharing for models, knowledge, prompts, and tools—ideal for privacy, team control, and internal deployments.
- 📦 **Custom pip Options for Tools/Functions**: You can now specify custom pip installation options with "PIP_OPTIONS", "PIP_PACKAGE_INDEX_OPTIONS" environment variables—improving compatibility, support for private indexes, and better control over Python environments.
- 🔢 **Editable Message Counter**: You can now double-click the message count number and jump straight to editing the index—quickly navigate complex chats or regenerate specific messages precisely.
- 🧠 **Embedding Prefix Support Added**: Add custom prefixes to your embeddings for instruct-style tokens, enabling stronger model alignment and more consistent RAG performance.
- 🙈 **Ability to Hide Base Models**: Optionally hide base models from the UI, helping users streamline model visibility and limit access to only usable endpoints..
- 📚 **Docling Content Extraction Support**: BCGPT now supports Docling as a content extraction engine, enabling smarter and more accurate parsing of complex file formats—ideal for advanced document understanding and Retrieval-Augmented Generation (RAG) workflows.
- 🗃️ **Redis Sentinel Support Added**: Enhance deployment redundancy with support for Redis Sentinel for highly available, failover-safe Redis-based caching or pub/sub.
- 📚 **JSON Schema Format for Ollama**: Added support for defining the format using JSON schema in Ollama-compatible models, improving flexibility and validation of model outputs.
- 🔍 **Chat Sidebar Search "Clear" Button**: Quickly clear search filters in chat sidebar using the new ✖️ button—streamline your chat navigation with one click.
- 🗂️ **Auto-Focus + Enter Submit for Folder Name**: When creating a new folder, the system automatically enters rename mode with name preselected—simplifying your org workflow.
- 🧱 **Markdown Alerts Rendering**: Blockquotes with syntax hinting (e.g. ⚠️, ℹ️, ✅) now render styled Markdown alert banners, making messages and documentation more visually structured.
- 🔁 **Hybrid Search Runs in Parallel Now**: Hybrid (BM25 + embedding) search components now run in parallel—dramatically reducing response times and speeding up document retrieval.
- 📋 **Cleaner UI for Tool Call Display**: Optimized the visual layout of called tools inside chat messages for better clarity and reduced visual clutter.
- 🧪 **Playwright Timeout Now Configurable**: Default timeout for Playwright processes is now shorter and adjustable via environment variables—making web scraping more robust and tunable to environments.
- 📈 **OpenTelemetry Support for Observability**: BCGPT now integrates with OpenTelemetry, allowing you to connect with tools like Grafana, Jaeger, or Prometheus for detailed performance insights and real-time visibility—entirely opt-in and fully self-hosted. Even if enabled, no data is ever sent to us, ensuring your privacy and ownership over all telemetry data.
- 🛠 **General UI Enhancements & UX Polish**: Numerous refinements across sidebar, code blocks, modal interactions, button alignment, scrollbar visibility, and folder behavior improve overall fluidity and usability of the interface.
- 🧱 **General Backend Refactoring**: Numerous backend components have been refactored to improve stability, maintainability, and performance—ensuring a more consistent and reliable system across all features.
- 🌍 **Internationalization Language Support Updates**: Added Estonian and Galician languages, improved Spanish (fully revised), Traditional Chinese, Simplified Chinese, Turkish, Catalan, Ukrainian, and German for a more localized and inclusive interface.

### Fixed

- 🧑‍💻 **Firefox Input Height Bug**: Text input in Firefox now maintains proper height, ensuring message boxes look consistent and behave predictably.
- 🧾 **Tika Blank Line Bug**: PDFs processed with Apache Tika 3.1.0.0 no longer introduce excessive blank lines—improving RAG output quality and visual cleanliness.
- 🧪 **CSV Loader Encoding Issues**: CSV files with unknown encodings now automatically detect character sets, resolving import errors in non-UTF-8 datasets.
- ✅ **LDAP Auth Config Fix**: Path to certificate file is now optional for LDAP setups, fixing authentication trouble for users without preconfigured cert paths.
- 📥 **File Deletion in Bypass Mode**: Resolved issue where files couldn't be deleted from knowledge when "bypass embedding" mode was enabled.
- 🧩 **Hybrid Search Result Sorting & Deduplication Fixed**: Fixed citation and sorting issues in RAG hybrid and reranker modes, ensuring retrieved documents are shown in correct order per score.
- 🧷 **Model Export/Import Broken for a Single Model**: Fixed bug where individual models couldn't be exported or re-imported, restoring full portability.
- 📫 **Auth Redirect Fix**: Logged-in users are now routed properly without unnecessary login prompts when already authenticated.

### Changed

- 🧠 **Prompt Autocompletion Disabled By Default**: Autocomplete suggestions while typing are now disabled unless explicitly re-enabled in user preferences—reduces distractions while composing prompts for advanced users.
- 🧾 **Normalize Citation Numbering**: Source citations now properly begin from "1" instead of "0"—improving consistency and professional presentation in AI outputs.
- 📚 **Improved Error Handling from Pipelines**: Pipelines now show the actual returned error message from failed tasks rather than generic "Connection closed"—making debugging far more user-friendly.

### Removed

- 🧾 **ENABLE_AUDIT_LOGS Setting Removed**: Deprecated setting "ENABLE_AUDIT_LOGS" has been fully removed—now controlled via "AUDIT_LOG_LEVEL" instead.

## [0.5.20] - 2025-03-05

### Added

- **⚡ Toggle Code Execution On/Off**: You can now enable or disable code execution, providing more control over security, ensuring a safer and more customizable experience.

### Fixed

- **📜 Pinyin Keyboard Enter Key Now Works Properly**: Resolved an issue where the Enter key for Pinyin keyboards was not functioning as expected, ensuring seamless input for Chinese users.
- **🖼️ Web Manifest Loading Issue Fixed**: Addressed inconsistencies with 'site.webmanifest', guaranteeing proper loading and representation of the app across different browsers and devices.
- **📦 Non-Root Container Issue Resolved**: Fixed a critical issue where the UI failed to load correctly in non-root containers, ensuring reliable deployment in various environments.

## [0.5.19] - 2025-03-04

### Added

- **📊 Logit Bias Parameter Support**: Fine-tune conversation dynamics by adjusting the Logit Bias parameter directly in chat settings, giving you more control over model responses.
- **⌨️ Customizable Enter Behavior**: You can now configure Enter to send messages only when combined with Ctrl (Ctrl+Enter) via Settings > Interface, preventing accidental message sends.
- **📝 Collapsible Code Blocks**: Easily collapse long code blocks to declutter your chat, making it easier to focus on important details.
- **🏷️ Tag Selector in Model Selector**: Quickly find and categorize models with the new tag filtering system in the Model Selector, streamlining model discovery.
- **📈 Experimental Elasticsearch Vector DB Support**: Now supports Elasticsearch as a vector database, offering more flexibility for data retrieval in Retrieval-Augmented Generation (RAG) workflows.
- **⚙️ General Reliability Enhancements**: Various stability improvements across the WebUI, ensuring a smoother, more consistent experience.
- **🌍 Updated Translations**: Refined multilingual support for better localization and accuracy across various languages.

### Fixed

- **🔄 "Stream" Hook Activation**: Fixed an issue where the "Stream" hook only worked when globally enabled, ensuring reliable real-time filtering.
- **📧 LDAP Email Case Sensitivity**: Resolved an issue where LDAP login failed due to email case sensitivity mismatches, improving authentication reliability.
- **💬 WebSocket Chat Event Registration**: Fixed a bug preventing chat event listeners from being registered upon sign-in, ensuring real-time updates work properly.

## [0.5.18] - 2025-02-27

### Fixed

- **🌐 BCGPT Now Works Over LAN in Insecure Context**: Resolved an issue preventing BCGPT from functioning when accessed over a local network in an insecure context, ensuring seamless connectivity.
- **🔄 UI Now Reflects Deleted Connections Instantly**: Fixed an issue where deleting a connection did not update the UI in real time, ensuring accurate system state visibility.
- **🛠️ Models Now Display Correctly with ENABLE_FORWARD_USER_INFO_HEADERS**: Addressed a bug where models were not visible when ENABLE_FORWARD_USER_INFO_HEADERS was set, restoring proper model listing.

## [0.5.17] - 2025-02-27

### Added

- **🚀 Instant Document Upload with Bypass Embedding & Retrieval**: Admins can now enable "Bypass Embedding & Retrieval" in Admin Settings > Documents, significantly speeding up document uploads and ensuring full document context is retained without chunking.
- **🔎 "Stream" Hook for Real-Time Filtering**: The new "stream" hook allows dynamic real-time message filtering. Learn more in our documentation (https://docs.BCGPT.com/features/plugin/functions/filter).
- **☁️ OneDrive Integration**: Early support for OneDrive storage integration has been introduced, expanding file import options.
- **📈 Enhanced Logging with Loguru**: Backend logging has been improved with Loguru, making debugging and issue tracking far more efficient.
- **⚙️ General Stability Enhancements**: Backend and frontend refactoring improves performance, ensuring a smoother and more reliable user experience.
- **🌍 Updated Translations**: Refined multilingual support for better localization and accuracy across various languages.

### Fixed

- **🔄 Reliable Model Imports from the Community Platform**: Resolved import failures, allowing seamless integration of community-shared models without errors.
- **📊 OpenAI Usage Statistics Restored**: Fixed an issue where OpenAI usage metrics were not displaying correctly, ensuring accurate tracking of usage data.
- **🗂️ Deduplication for Retrieved Documents**: Documents retrieved during searches are now intelligently deduplicated, meaning no more redundant results—helping to keep information concise and relevant.

### Changed

- **📝 "Full Context Mode" Renamed for Clarity**: The "Full Context Mode" toggle in Web Search settings is now labeled "Bypass Embedding & Retrieval" for consistency across the UI.

## [0.5.16] - 2025-02-20

### Fixed

- **🔍 Web Search Retrieval Restored**: Resolved a critical issue that broke web search retrieval by reverting deduplication changes, ensuring complete and accurate search results once again.

## [0.5.15] - 2025-02-20

### Added

- **📄 Full Context Mode for Local Document Search (RAG)**: Toggle full context mode from Admin Settings > Documents to inject entire document content into context, improving accuracy for models with large context windows—ideal for deep context understanding.
- **🌍 Smarter Web Search with Agentic Workflows**: Web searches now intelligently gather and refine multiple relevant terms, similar to RAG handling, delivering significantly better search results for more accurate information retrieval.
- **🔎 Experimental Playwright Support for Web Loader**: Web content retrieval is taken to the next level with Playwright-powered scraping for enhanced accuracy in extracted web data.
- **☁️ Experimental Azure Storage Provider**: Early-stage support for Azure Storage allows more cloud storage flexibility directly within BCGPT.
- **📊 Improved Jupyter Code Execution with Plots**: Interactive coding now properly displays inline plots, making data visualization more seamless inside chat interactions.
- **⏳ Adjustable Execution Timeout for Jupyter Interpreter**: Customize execution timeout (default: 60s) for Jupyter-based code execution, allowing longer or more constrained execution based on your needs.
- **▶️ "Running..." Indicator for Jupyter Code Execution**: A visual indicator now appears while code execution is in progress, providing real-time status updates on ongoing computations.
- **⚙️ General Backend & Frontend Stability Enhancements**: Extensive refactoring improves reliability, performance, and overall user experience for a more seamless BCGPT.
- **🌍 Translation Updates**: Various international translation refinements ensure better localization and a more natural user interface experience.

### Fixed

- **📱 Mobile Hover Issue Resolved**: Users can now edit responses smoothly on mobile without interference, fixing a longstanding hover issue.
- **🔄 Temporary Chat Message Duplication Fixed**: Eliminated buggy behavior where messages were being unnecessarily repeated in temporary chat mode, ensuring a smooth and consistent conversation flow.

## [0.5.14] - 2025-02-17

### Fixed

- **🔧 Critical Import Error Resolved**: Fixed a circular import issue preventing 'override_static' from being correctly imported in 'open_webui.config', ensuring smooth system initialization and stability.

## [0.5.13] - 2025-02-17

### Added

- **🌐 Full Context Mode for Web Search**: Enable highly accurate web searches by utilizing full context mode—ideal for models with large context windows, ensuring more precise and insightful results.
- **⚡ Optimized Asynchronous Web Search**: Web searches now load significantly faster with optimized async support, providing users with quicker, more efficient information retrieval.
- **🔄 Auto Text Direction for RTL Languages**: Automatic text alignment based on language input, ensuring seamless conversation flow for Arabic, Hebrew, and other right-to-left scripts.
- **🚀 Jupyter Notebook Support for Code Execution**: The "Run" button in code blocks can now use Jupyter for execution, offering a powerful, dynamic coding experience directly in the chat.
- **🗑️ Message Delete Confirmation Dialog**: Prevent accidental deletions with a new confirmation prompt before removing messages, adding an additional layer of security to your chat history.
- **📥 Download Button for SVG Diagrams**: SVG diagrams generated within chat can now be downloaded instantly, making it easier to save and share complex visual data.
- **✨ General UI/UX Improvements and Backend Stability**: A refined interface with smoother interactions, improved layouts, and backend stability enhancements for a more reliable, polished experience.

### Fixed

- **🛠️ Temporary Chat Message Continue Button Fixed**: The "Continue Response" button for temporary chats now works as expected, ensuring an uninterrupted conversation flow.

### Changed

- **📝 Prompt Variable Update**: Deprecated square bracket '[]' indicators for prompt variables; now requires double curly brackets '{{}}' for consistency and clarity.
- **🔧 Stability Enhancements**: Error handling improved in chat history, ensuring smoother operations when reviewing previous messages.

## [0.5.12] - 2025-02-13

### Added

- **🛠️ Multiple Tool Calls Support for Native Function Mode**: Functions now can call multiple tools within a single response, unlocking better automation and workflow flexibility when using native function calling.

### Fixed

- **📝 Playground Text Completion Restored**: Addressed an issue where text completion in the Playground was not functioning.
- **🔗 Direct Connections Now Work for Regular Users**: Fixed a bug where users with the 'user' role couldn't establish direct API connections, enabling seamless model usage for all user tiers.
- **⚡ Landing Page Input No Longer Lags with Long Text**: Improved input responsiveness on the landing page, ensuring fast and smooth typing experiences even when entering long messages.
- **🔧 Parameter in Functions Fixed**: Fixed an issue where the reserved parameters wasn't recognized within functions, restoring full functionality for advanced task-based automation.

## [0.5.11] - 2025-02-13

### Added

- **🎤 Kokoro-JS TTS Support**: A new on-device, high-quality text-to-speech engine has been integrated, vastly improving voice generation quality—everything runs directly in your browser.
- **🐍 Jupyter Notebook Support in Code Interpreter**: Now, you can configure Code Interpreter to run Python code not only via Pyodide but also through Jupyter, offering a more robust coding environment for AI-driven computations and analysis.
- **🔗 Direct API Connections for Private & Local Inference**: You can now connect BCGPT to your private or localhost API inference endpoints. CORS must be enabled, but this unlocks direct, on-device AI infrastructure support.
- **🔍 Advanced Domain Filtering for Web Search**: You can now specify which domains should be included or excluded from web searches, refining results for more relevant information retrieval.
- **🚀 Improved Image Generation Metadata Handling**: Generated images now retain metadata for better organization and future retrieval.
- **📂 S3 Key Prefix Support**: Fine-grained control over S3 storage file structuring with configurable key prefixes.
- **📸 Support for Image-Only Messages**: Send messages containing only images, facilitating more visual-centric interactions.
- **🌍 Updated Translations**: German, Spanish, Traditional Chinese, and Catalan translations updated for better multilingual support.

### Fixed

- **🔧 OAuth Debug Logs & Username Claim Fixes**: Debug logs have been added for OAuth role and group management, with fixes ensuring proper OAuth username retrieval and claim handling.
- **📌 Citations Formatting & Toggle Fixes**: Inline citation toggles now function correctly, and citations with more than three sources are now fully visible when expanded.
- **📸 ComfyUI Maximum Seed Value Constraint Fixed**: The maximum allowed seed value for ComfyUI has been corrected, preventing unintended behavior.
- **🔑 Connection Settings Stability**: Addressed connection settings issues that were causing instability when saving configurations.
- **📂 GGUF Model Upload Stability**: Fixed upload inconsistencies for GGUF models, ensuring reliable local model handling.
- **🔧 Web Search Configuration Bug**: Fixed issues where web search filters and settings weren't correctly applied.
- **💾 User Settings Persistence Fix**: Ensured user-specific settings are correctly saved and applied across sessions.
- **🔄 OpenID Username Retrieval Enhancement**: Usernames are now correctly picked up and assigned for OpenID Connect (OIDC) logins.

## [0.5.10] - 2025-02-05

### Fixed

- **⚙️ System Prompts Now Properly Templated via API**: Resolved an issue where system prompts were not being correctly processed when used through the API, ensuring template variables now function as expected.
- **📝 '<thinking>' Tag Display Issue Fixed**: Fixed a bug where the 'thinking' tag was disrupting content rendering, ensuring clean and accurate text display.
- **💻 Code Interpreter Stability with Custom Functions**: Addressed failures when using the Code Interpreter with certain custom functions like Anthropic, ensuring smoother execution and better compatibility.

## [0.5.9] - 2025-02-05

### Fixed

- **💡 "Think" Tag Display Issue**: Resolved a bug where the "Think" tag was not functioning correctly, ensuring proper visualization of the model's reasoning process before delivering responses.

## [0.5.8] - 2025-02-05

### Added

- **🖥️ Code Interpreter**: Models can now execute code in real time to refine their answers dynamically, running securely within a sandboxed browser environment using Pyodide. Perfect for calculations, data analysis, and AI-assisted coding tasks!
- **💬 Redesigned Chat Input UI**: Enjoy a sleeker and more intuitive message input with improved feature selection, making it easier than ever to toggle tools, enable search, and interact with AI seamlessly.
- **🛠️ Native Tool Calling Support (Experimental)**: Supported models can now call tools natively, reducing query latency and improving contextual responses. More enhancements coming soon!
- **🔗 Exa Search Engine Integration**: A new search provider has been added, allowing users to retrieve up-to-date and relevant information without leaving the chat interface.
- **🌍 Localized Dates & Times**: Date and time formats now match your system locale, ensuring a more natural, region-specific experience.
- **📎 User Headers for External Embedding APIs**: API calls to external embedding services now include user-related headers.
- **🌍 "Always On" Web Search Toggle**: A new option under Settings > Interface allows users to enable Web Search by default—transform BCGPT into your go-to search engine, ensuring AI-powered results with every query.
- **🚀 General Performance & Stability**: Significant improvements across the platform for a faster, more reliable experience.
- **🖼️ UI/UX Enhancements**: Numerous design refinements improving readability, responsiveness, and accessibility.
- **🌍 Improved Translations**: Chinese, Korean, French, Ukrainian and Serbian translations have been updated with refined terminologies for better clarity.

### Fixed

- **🔄 OAuth Name Field Fallback**: Resolves OAuth login failures by using the email field as a fallback when a name is missing.
- **🔑 Google Drive Credentials Restriction**: Ensures only authenticated users can access Google Drive credentials for enhanced security.
- **🌐 DuckDuckGo Search Rate Limit Handling**: Fixes issues where users would encounter 202 errors due to rate limits when using DuckDuckGo for web search.
- **📁 File Upload Permission Indicator**: Users are now notified when they lack permission to upload files, improving clarity on system restrictions.
- **🔧 Max Tokens Issue**: Fixes cases where 'max_tokens' were not applied correctly, ensuring proper model behavior.
- **🔍 Validation for RAG Web Search URLs**: Filters out invalid or unsupported URLs when using web-based retrieval augmentation.
- **🖋️ Title Generation Bug**: Fixes inconsistencies in title generation, ensuring proper chat organization.

### Removed

- **⚡ Deprecated Non-Web Worker Pyodide Execution**: Moves entirely to browser sandboxing for better performance and security.

## [0.5.7] - 2025-01-23

### Added

- **🌍 Enhanced Internationalization (i18n)**: Refined and expanded translations for greater global accessibility and a smoother experience for international users.

### Fixed

- **🔗 Connection Model ID Resolution**: Resolved an issue preventing model IDs from registering in connections.
- **💡 Prefix ID for Ollama Connections**: Fixed a bug where prefix IDs in Ollama connections were non-functional.
- **🔧 Ollama Model Enable/Disable Functionality**: Addressed the issue of enable/disable toggles not working for Ollama base models.
- **🔒 RBAC Permissions for Tools and Models**: Corrected incorrect Role-Based Access Control (RBAC) permissions for tools and models, ensuring that users now only access features according to their assigned privileges, enhancing security and role clarity.

## [0.5.6] - 2025-01-22

### Added

- **🧠 Effortful Reasoning Control for OpenAI Models**: Introduced the reasoning_effort parameter in chat controls for supported OpenAI models, enabling users to fine-tune how much cognitive effort a model dedicates to its responses, offering greater customization for complex queries and reasoning tasks.

### Fixed

- **🔄 Chat Controls Loading UI Bug**: Resolved an issue where collapsible chat controls appeared as "loading," ensuring a smoother and more intuitive user experience for managing chat settings.

### Changed

- **🔧 Updated Ollama Model Creation**: Revamped the Ollama model creation method to align with their new JSON payload format, ensuring seamless compatibility and more efficient model setup workflows.

## [0.5.5] - 2025-01-22

### Added

- **🤔 Native 'Think' Tag Support**: Introduced the new 'think' tag support that visually displays how long the model is thinking, omitting the reasoning content itself until the next turn. Ideal for creating a more streamlined and focused interaction experience.
- **🖼️ Toggle Image Generation On/Off**: In the chat input menu, you can now easily toggle image generation before initiating chats, providing greater control and flexibility to suit your needs.
- **🔒 Chat Controls Permissions**: Admins can now disable chat controls access for users, offering tighter management and customization over user interactions.
- **🔍 Web Search & Image Generation Permissions**: Easily disable web search and image generation for specific users, improving workflow governance and security for certain environments.
- **🗂️ S3 and GCS Storage Provider Support**: Scaled deployments now benefit from expanded storage options with Amazon S3 and Google Cloud Storage seamlessly integrated as providers.
- **🎨 Enhanced Model Management**: Reintroduced the ability to download and delete models directly in the admin models settings page to minimize user confusion and aid efficient model management.
- **🔗 Improved Connection Handling**: Enhanced backend to smoothly handle multiple identical base URLs, allowing more flexible multi-instance configurations with fewer hiccups.
- **✨ General UI/UX Refinements**: Numerous tweaks across the WebUI make navigation and usability even more user-friendly and intuitive.
- **🌍 Translation Enhancements**: Various translation updates ensure smoother and more polished interactions for international users.

### Fixed

- **⚡ MPS Functionality for Mac Users**: Fixed MPS support, ensuring smooth performance and compatibility for Mac users leveraging MPS.
- **📡 Ollama Connection Management**: Resolved the issue where deleting all Ollama connections prevented adding new ones.

### Changed

- **⚙️ General Stability Refac**: Backend refactoring delivers a more stable, robust platform.
- **🖥️ Desktop App Preparations**: Ongoing work to support the upcoming BCGPT desktop app. Follow our progress and updates here: https://github.com/bccard-ai/desktop

## [0.5.4] - 2025-01-05

### Added

- **🔄 Clone Shared Chats**: Effortlessly clone shared chats to save time and streamline collaboration, perfect for reusing insightful discussions or custom setups.
- **📣 Native Notifications for Channel Messages**: Stay informed with integrated desktop notifications for channel messages, ensuring you never miss important updates while multitasking.
- **🔥 Torch MPS Support**: MPS support for Mac users when BCGPT is installed directly, offering better performance and compatibility for AI workloads.
- **🌍 Enhanced Translations**: Small improvements to various translations, ensuring a smoother global user experience.

### Fixed

- **🖼️ Image-Only Messages in Channels**: You can now send images without accompanying text or content in channels.
- **❌ Proper Exception Handling**: Enhanced error feedback by ensuring exceptions are raised clearly, reducing confusion and promoting smoother debugging.
- **🔍 RAG Query Generation Restored**: Fixed query generation issues for Retrieval-Augmented Generation, improving retrieval accuracy and ensuring seamless functionality.
- **📩 MOA Response Functionality Fixed**: Addressed an error with the MOA response generation feature.
- **💬 Channel Thread Loading with 50+ Messages**: Resolved an issue where channel threads stalled when exceeding 50 messages, ensuring smooth navigation in active discussions.
- **🔑 API Endpoint Restrictions Resolution**: Fixed a critical bug where the 'API_KEY_ALLOWED_ENDPOINTS' setting was not functioning as intended, ensuring API access is limited to specified endpoints for enhanced security.
- **🛠️ Action Functions Restored**: Corrected an issue preventing action functions from working, restoring their utility for customized automations and workflows.
- **📂 Temporary Chat JSON Export Fix**: Resolved a bug blocking temporary chats from being exported in JSON format, ensuring seamless data portability.

### Changed

- **🎛️ Sidebar UI Tweaks**: Chat folders, including pinned folders, now display below the Chats section for better organization; the "New Folder" button has been relocated to the Chats section for a more intuitive workflow.
- **🏗️ Real-Time Save Disabled by Default**: The 'ENABLE_REALTIME_CHAT_SAVE' setting is now off by default, boosting response speed for users who prioritize performance in high-paced workflows or less critical scenarios.
- **🎤 Audio Input Echo Cancellation**: Audio input now features echo cancellation enabled by default, reducing audio feedback for improved clarity during conversations or voice-based interactions.
- **🔧 General Reliability Improvements**: Numerous under-the-hood enhancements have been made to improve platform stability, boost overall performance, and ensure a more seamless, dependable experience across workflows.

## [0.5.3] - 2024-12-31

### Added

- **💬 Channel Reactions with Built-In Emoji Picker**: Easily express yourself in channel threads and messages with reactions, featuring an intuitive built-in emoji picker for seamless selection.
- **🧵 Threads for Channels**: Organize discussions within channels by creating threads, improving clarity and fostering focused conversations.
- **🔄 Reset Button for SVG Pan/Zoom**: Added a handy reset button to SVG Pan/Zoom, allowing users to quickly return diagrams or visuals to their default state without hassle.
- **⚡ Realtime Chat Save Environment Variable**: Introduced the ENABLE_REALTIME_CHAT_SAVE environment variable. Choose between faster responses by disabling realtime chat saving or ensuring chunk-by-chunk data persistency for critical operations.
- **🌍 Translation Enhancements**: Updated and refined translations across multiple languages, providing a smoother experience for international users.
- **📚 Improved Documentation**: Expanded documentation on functions, including clearer guidance on function plugins and detailed instructions for migrating to v0.5. This ensures users can adapt and harness new updates more effectively. (https://docs.BCGPT.com/features/plugin/)

### Fixed

- **🛠️ Ollama Parameters Respected**: Resolved an issue where input parameters for Ollama were being ignored, ensuring precise and consistent model behavior.
- **🔧 Function Plugin Outlet Hook Reliability**: Fixed a bug causing issues with 'event_emitter' and outlet hooks in filter function plugins, guaranteeing smoother operation within custom extensions.
- **🖋️ Weird Custom Status Descriptions**: Adjusted the formatting and functionality for custom user statuses, ensuring they display correctly and intuitively.
- **🔗 Restored API Functionality**: Fixed a critical issue where APIs were not operational for certain configurations, ensuring uninterrupted access.
- **⏳ Custom Pipe Function Completion**: Resolved an issue where chats using specific custom pipe function plugins weren't finishing properly, restoring consistent chat workflows.
- **✅ General Stability Enhancements**: Implemented various under-the-hood improvements to boost overall reliability, ensuring smoother and more consistent performance across the WebUI.

## [0.5.2] - 2024-12-26

### Added

- **🖊️ Typing Indicators in Channels**: Know exactly who's typing in real-time within your channels, enhancing collaboration and keeping everyone engaged.
- **👤 User Status Indicators**: Quickly view a user's status by clicking their profile image in channels for better coordination and availability insights.
- **🔒 Configurable API Key Authentication Restrictions**: Flexibly configure endpoint restrictions for API key authentication, now off by default for a smoother setup in trusted environments.

### Fixed

- **🔧 Playground Functionality Restored**: Resolved a critical issue where the playground wasn't working, ensuring seamless experimentation and troubleshooting workflows.
- **📊 Corrected Ollama Usage Statistics**: Fixed a calculation error in Ollama's usage statistics, providing more accurate tracking and insights for better resource management.
- **🔗 Pipelines Outlet Hook Registration**: Addressed an issue where outlet hooks for pipelines weren't registered, restoring functionality and consistency in pipeline workflows.
- **🎨 Image Generation Error**: Resolved a persistent issue causing errors with 'get_automatic1111_api_auth()' to ensure smooth image generation workflows.
- **🎙️ Text-to-Speech Error**: Fixed the missing argument in Eleven Labs' 'get_available_voices()', restoring full text-to-speech capabilities for uninterrupted voice interactions.
- **🖋️ Title Generation Issue**: Fixed a bug where title generation was not working in certain cases, ensuring consistent and reliable chat organization.

## [0.5.1] - 2024-12-25

### Added

- **🔕 Notification Sound Toggle**: Added a new setting under Settings > Interface to disable notification sounds, giving you greater control over your workspace environment and focus.

### Fixed

- **🔄 Non-Streaming Response Visibility**: Resolved an issue where non-streaming responses were not displayed, ensuring all responses are now reliably shown in your conversations.
- **🖋️ Title Generation with OpenAI APIs**: Fixed a bug preventing title generation when using OpenAI APIs, restoring the ability to automatically generate chat titles for smoother organization.
- **👥 Admin Panel User List**: Addressed the issue where only 50 users were visible in the admin panel. You can now manage and view all users without restrictions.
- **🖼️ Image Generation Error**: Fixed the issue causing 'get_automatic1111_api_auth()' errors in image generation, ensuring seamless creative workflows.
- **⚙️ Pipeline Settings Loading Issue**: Resolved a problem where pipeline settings were stuck at the loading screen, restoring full configurability in the admin panel.

## [0.5.0] - 2024-12-25

### Added

- **💬 True Asynchronous Chat Support**: Create chats, navigate away, and return anytime with responses ready. Ideal for reasoning models and multi-agent workflows, enhancing multitasking like never before.
- **🔔 Chat Completion Notifications**: Never miss a completed response. Receive instant in-UI notifications when a chat finishes in a non-active tab, keeping you updated while you work elsewhere.
- **🌐 Notification Webhook Integration**: Get alerts via webhooks even when your tab is closed! Configure your webhook URL in Settings > Account and receive timely updates for long-running chats or external integration needs.
- **📚 Channels (Beta)**: Explore Discord/Slack-style chat rooms designed for real-time collaboration between users and AIs. Build bots for channels and unlock asynchronous communication for proactive multi-agent workflows. Opt-in via Admin Settings > General. A Comprehensive Bot SDK tutorial (https://github.com/bccard-ai/bot) is incoming, so stay tuned!
- **🖼️ Client-Side Image Compression**: Now compress images before upload (Settings > Interface), saving bandwidth and improving performance seamlessly.
- **🛠️ OAuth Management for User Groups**: Enable group-level management via OAuth integration for enhanced control and scalability in collaborative environments.
- **✅ Structured Output for Ollama**: Pass structured data output directly to Ollama, unlocking new possibilities for streamlined automation and precise data handling.
- **📜 Offline Swagger Documentation**: Developer-friendly Swagger API docs are now available offline, ensuring full accessibility wherever you are.
- **📸 Quick Screen Capture Button**: Effortlessly capture your screen with a single click from the message input menu.
- **🌍 i18n Updates**: Improved and refined translations across several languages, including Ukrainian, German, Brazilian Portuguese, Catalan, and more, ensuring a seamless global user experience.

### Fixed

- **📋 Table Export to CSV**: Resolved issues with CSV export where headers were missing or errors occurred due to values with commas, ensuring smooth and reliable data handling.
- **🔓 BYPASS_MODEL_ACCESS_CONTROL**: Fixed an issue where users could see models but couldn't use them with 'BYPASS_MODEL_ACCESS_CONTROL=True', restoring proper functionality for environments leveraging this setting.

### Changed

- **💡 API Key Authentication Restriction**: Narrowed API key auth permissions to '/api/models' and '/api/chat/completions' for enhanced security and better API governance.
- **⚙️ Backend Overhaul for Performance**: Major backend restructuring; a heads-up that some "Functions" using internal variables may face compatibility issues. Moving forward, websocket support is mandatory to ensure BCGPT operates seamlessly.

### Removed

- **⚠️ Legacy Functionality Clean-Up**: Deprecated outdated backend systems that were non-essential or overlapped with newer implementations, allowing for a leaner, more efficient platform.

## [0.4.8] - 2024-12-07

### Added

- **🔓 Bypass Model Access Control**: Introduced the 'BYPASS_MODEL_ACCESS_CONTROL' environment variable. Easily bypass model access controls for user roles when access control isn't required, simplifying workflows for trusted environments.
- **📝 Markdown in Banners**: Now supports markdown for banners, enabling richer, more visually engaging announcements.
- **🌐 Internationalization Updates**: Enhanced translations across multiple languages, further improving accessibility and global user experience.
- **🎨 Styling Enhancements**: General UI style refinements for a cleaner and more polished interface.
- **📋 Rich Text Reliability**: Improved the reliability and stability of rich text input across chats for smoother interactions.

### Fixed

- **💡 Tailwind Build Issue**: Resolved a breaking bug caused by Tailwind, ensuring smoother builds and overall system reliability.
- **📚 Knowledge Collection Query Fix**: Addressed API endpoint issues with querying knowledge collections, ensuring accurate and reliable information retrieval.

## [0.4.7] - 2024-12-01

### Added

- **✨ Prompt Input Auto-Completion**: Type a prompt and let AI intelligently suggest and complete your inputs. Simply press 'Tab' or swipe right on mobile to confirm. Available only with Rich Text Input (default setting). Disable via Admin Settings for full control.
- **🌍 Improved Translations**: Enhanced localization for multiple languages, ensuring a more polished and accessible experience for international users.

### Fixed

- **🛠️ Tools Export Issue**: Resolved a critical issue where exporting tools wasn't functioning, restoring seamless export capabilities.
- **🔗 Model ID Registration**: Fixed an issue where model IDs weren't registering correctly in the model editor, ensuring reliable model setup and tracking.
- **🖋️ Textarea Auto-Expansion**: Corrected a bug where textareas didn't expand automatically on certain browsers, improving usability for multi-line inputs.
- **🔧 Ollama Embed Endpoint**: Addressed the /ollama/embed endpoint malfunction, ensuring consistent performance and functionality.

### Changed

- **🎨 Knowledge Base Styling**: Refined knowledge base visuals for a cleaner, more modern look, laying the groundwork for further enhancements in upcoming releases.

## [0.4.6] - 2024-11-26

### Added

- **🌍 Enhanced Translations**: Various language translations improved to make the WebUI more accessible and user-friendly worldwide.

### Fixed

- **✏️ Textarea Shifting Bug**: Resolved the issue where the textarea shifted unexpectedly, ensuring a smoother typing experience.
- **⚙️ Model Configuration Modal**: Fixed the issue where the models configuration modal introduced in 0.4.5 wasn't working for some users.
- **🔍 Legacy Query Support**: Restored functionality for custom query generation in RAG when using legacy prompts, ensuring both default and custom templates now work seamlessly.
- **⚡ Improved General Reliability**: Various minor fixes improve platform stability and ensure a smoother overall experience across workflows.

## [0.4.5] - 2024-11-26

### Added

- **🎨 Model Order/Defaults Reintroduced**: Brought back the ability to set model order and default models, now configurable via Admin Settings > Models > Configure (Gear Icon).

### Fixed

- **🔍 Query Generation Issue**: Resolved an error in web search query generation, enhancing search accuracy and ensuring smoother search workflows.
- **📏 Textarea Auto Height Bug**: Fixed a layout issue where textarea input height was shifting unpredictably, particularly when editing system prompts.
- **🔑 Ollama Authentication**: Corrected an issue with Ollama's authorization headers, guaranteeing reliable authentication across all endpoints.
- **⚙️ Missing Min_P Save**: Resolved an issue where the 'min_p' parameter was not being saved in configurations.
- **🛠️ Tools Description**: Fixed a key issue that omitted tool descriptions in tools payload.

## [0.4.4] - 2024-11-22

### Added

- **🌐 Translation Updates**: Refreshed Catalan, Brazilian Portuguese, German, and Ukrainian translations, further enhancing the platform's accessibility and improving the experience for international users.

### Fixed

- **📱 Mobile Controls Visibility**: Resolved an issue where the controls button was not displaying on the new chats page for mobile users, ensuring smoother navigation and functionality on smaller screens.
- **📷 LDAP Profile Image Issue**: Fixed an LDAP integration bug related to profile images, ensuring seamless authentication and a reliable login experience for users.
- **⏳ RAG Query Generation Issue**: Addressed a significant problem where RAG query generation occurred unnecessarily without attached files, drastically improving speed and reducing delays during chat completions.

### Changed

- **⚙️ Legacy Event Emitter Support**: Reintroduced compatibility with legacy "citation" types for event emitters in tools and functions, providing smoother workflows and broader tool support for users.

## [0.4.3] - 2024-11-21

### Added

- **📚 Inline Citations for RAG Results**: Get seamless inline citations for Retrieval-Augmented Generation (RAG) responses using the default RAG prompt. Note: This feature only supports newly uploaded files, improving traceability and providing source clarity.
- **🎨 Better Rich Text Input Support**: Enjoy smoother and more reliable rich text formatting for chats, enhancing communication quality.
- **⚡ Faster Model Retrieval**: Implemented caching optimizations for faster model loading, providing a noticeable speed boost across workflows. Further improvements are on the way!

### Fixed

- **🔗 Pipelines Feature Restored**: Resolved a critical issue that previously prevented Pipelines from functioning, ensuring seamless workflows.
- **✏️ Missing Suffix Field in Ollama Form**: Added the missing "suffix" field to the Ollama generate form, enhancing customization options.

### Changed

- **🗂️ Renamed "Citations" to "Sources"**: Improved clarity and consistency by renaming the "citations" field to "sources" in messages.

## [0.4.2] - 2024-11-20

### Fixed

- **📁 Knowledge Files Visibility Issue**: Resolved the bug preventing individual files in knowledge collections from displaying when referenced with '#'.
- **🔗 OpenAI Endpoint Prefix**: Fixed the issue where certain OpenAI connections that deviate from the official API spec weren't working correctly with prefixes.
- **⚔️ Arena Model Access Control**: Corrected an issue where arena model access control settings were not being saved.
- **🔧 Usage Capability Selector**: Fixed the broken usage capabilities selector in the model editor.

## [0.4.1] - 2024-11-19

### Added

- **📊 Enhanced Feedback System**: Introduced a detailed 1-10 rating scale for feedback alongside thumbs up/down, preparing for more precise model fine-tuning and improving feedback quality.
- **ℹ️ Tool Descriptions on Hover**: Easily access tool descriptions by hovering over the message input, providing a smoother workflow with more context when utilizing tools.

### Fixed

- **🗑️ Graceful Handling of Deleted Users**: Resolved an issue where deleted users caused workspace items (models, knowledge, prompts, tools) to fail, ensuring reliable workspace loading.
- **🔑 API Key Creation**: Fixed an issue preventing users from creating new API keys, restoring secure and seamless API management.
- **🔗 HTTPS Proxy Fix**: Corrected HTTPS proxy issues affecting the '/api/v1/models/' endpoint, ensuring smoother, uninterrupted model management.

## [0.4.0] - 2024-11-19

### Added

- **👥 User Groups**: You can now create and manage user groups, making user organization seamless.
- **🔐 Group-Based Access Control**: Set granular access to models, knowledge, prompts, and tools based on user groups, allowing for more controlled and secure environments.
- **🛠️ Group-Based User Permissions**: Easily manage workspace permissions. Grant users the ability to upload files, delete, edit, or create temporary chats, as well as define their ability to create models, knowledge, prompts, and tools.
- **🔑 LDAP Support**: Newly introduced LDAP authentication adds robust security and scalability to user management.
- **🌐 Enhanced OpenAI-Compatible Connections**: Added prefix ID support to avoid model ID clashes, with explicit model ID support for APIs lacking '/models' endpoint support, ensuring smooth operation with custom setups.
- **🔐 Ollama API Key Support**: Now manage credentials for Ollama when set behind proxies, including the option to utilize prefix ID for proper distinction across multiple Ollama instances.
- **🔄 Connection Enable/Disable Toggle**: Easily enable or disable individual OpenAI and Ollama connections as needed.
- **🎨 Redesigned Model Workspace**: Freshly redesigned to improve usability for managing models across users and groups.
- **🎨 Redesigned Prompt Workspace**: A fresh UI to conveniently organize and manage prompts.
- **🧩 Sorted Functions Workspace**: Functions are now automatically categorized by type (Action, Filter, Pipe), streamlining management.
- **💻 Redesigned Collaborative Workspace**: Enhanced support for multiple users contributing to models, knowledge, prompts, or tools, improving collaboration.
- **🔧 Auto-Selected Tools in Model Editor**: Tools enabled through the model editor are now automatically selected, whereas previously it only gave users the option to enable the tool, reducing manual steps and enhancing efficiency.
- **🔔 Web Search & Tools Indicator**: A clear indication now shows when web search or tools are active, reducing confusion.
- **🔑 Toggle API Key Auth**: Tighten security by easily enabling or disabling API key authentication option for BCGPT.
- **🗂️ Agentic Retrieval**: Improve RAG accuracy via smart pre-processing of chat history to determine the best queries before retrieval.
- **📁 Large Text as File Option**: Optionally convert large pasted text into a file upload, keeping the chat interface cleaner.
- **🗂️ Toggle Citations for Models**: Ability to disable citations has been introduced in the model editor.
- **🔍 User Settings Search**: Quickly search for settings fields, improving ease of use and navigation.
- **🗣️ Experimental SpeechT5 TTS**: Local SpeechT5 support added for improved text-to-speech capabilities.
- **🔄 Unified Reset for Models**: A one-click option has been introduced to reset and remove all models from the Admin Settings.
- **🛠️ Initial Setup Wizard**: The setup process now explicitly informs users that they are creating an admin account during the first-time setup, ensuring clarity. Previously, users encountered the login page right away without this distinction.
- **🌐 Enhanced Translations**: Several language translations, including Ukrainian, Norwegian, and Brazilian Portuguese, were refined for better localization.

### Fixed

- **🎥 YouTube Video Attachments**: Fixed issues preventing proper loading and attachment of YouTube videos as files.
- **🔄 Shared Chat Update**: Corrected issues where shared chats were not updating, improving collaboration consistency.
- **🔍 DuckDuckGo Rate Limit Fix**: Addressed issues with DuckDuckGo search integration, enhancing search stability and performance when operating within rate limits.
- **🧾 Citations Relevance Fix**: Adjusted the relevance percentage calculation for citations, so that BCGPT properly reflect the accuracy of a retrieved document in RAG, ensuring users get clearer insights into sources.
- **🔑 Jina Search API Key Requirement**: Added the option to input an API key for Jina Search, ensuring smooth functionality as keys are now mandatory.

### Changed

- **🛠️ Functions Moved to Admin Panel**: As Functions operate as advanced plugins, they are now accessible from the Admin Panel instead of the workspace.
- **🛠️ Manage Ollama Connections**: The "Models" section in Admin Settings has been relocated to Admin Settings > "Connections" > Ollama Connections. You can now manage Ollama instances via a dedicated "Manage Ollama" modal from "Connections", streamlining the setup and configuration of Ollama models.
- **📊 Base Models in Admin Settings**: Admins can now find all base models, both connections or functions, in the "Models" Admin setting. Global model accessibility can be enabled or disabled here. Models are private by default, requiring explicit permission assignment for user access.
- **📌 Sticky Model Selection for New Chats**: The model chosen from a previous chat now persists when creating a new chat. If you click "New Chat" again from the new chat page, it will revert to your default model.
- **🎨 Design Refactoring**: Overall design refinements across the platform have been made, providing a more cohesive and polished user experience.

### Removed

- **📂 Model List Reordering**: Temporarily removed and will be reintroduced in upcoming user group settings improvements.
- **⚙️ Default Model Setting**: Removed the ability to set a default model for users, will be reintroduced with user group settings in the future.
