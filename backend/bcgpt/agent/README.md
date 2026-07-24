# BCGPT Agent Subsystem

Implementation of the **Open-MoAI architecture patterns** adapted for BCGPT-WebUI
(see `docs/OPEN-MOAI-ARCHITECTURE-ADOPTION-GUIDE.md`). The package is **additive
and opt-in**: the existing chat flow in `utils/middleware.py` is untouched, and
agents default to `assistant` autonomy, preserving zero-regression behaviour.

## What's here

| Guide phase            | Module                                 | Summary                                                                                                                                                                                                                                                     |
| ---------------------- | -------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 1. Autonomy tiers      | `types.py`, `autonomy.py`, `config.py` | 3-Tier autonomy (`suggest`/`assistant`/`operator`). Stored in `Model.meta.autonomy_level` — **no DB migration** (the `meta` JSON column already allows extra fields).                                                                                       |
| 2. DAG workflow engine | `workflow/`                            | 10 node types, handler registry, DAG validator (cycle/dangling-edge detection), layered concurrent execution, per-node error strategies (stop/continue/retry/fallback), conditional branch pruning, JSON serializer, and an autonomy-aware graph generator. |
| 3. ReAct tool loop     | `tool_loop/`                           | Provider-agnostic N-hop ReAct loop. Uses native `tool_calls` when a provider returns them, else a prompt protocol (fenced JSON). Built-in `rag_search` / `web_search` tools. `MAX_ITERATIONS` safety cap.                                                   |
| 4. Quality pipeline    | `quality/`                             | Claim decomposition → answer grounding → document grading → entailment scoring → weighted report. LLM-backed, config-gated, degrades gracefully.                                                                                                            |
| 5. Multi-agent         | `multi_agent/`                         | Sequential, Parallel, Debate, Consensus, Voting, MoA — one `MultiAgentExecutor` router.                                                                                                                                                                     |
| 6. Definitions         | `definitions/`                         | Agent & skill definitions; import/export as YAML-frontmatter Markdown or JSON.                                                                                                                                                                              |

## Design seams

- **LLM invocation** funnels through `agent/llm.py::llm_complete`, which wraps the
  existing `utils.chat.generate_chat_completion` (non-streaming) — so every agent
  feature reuses BCGPT's provider routing, access control, and pipeline filters.
- **Engine concurrency contract**: node handlers _read_ `state`/`context` and
  _return_ a `NodeResult`; the engine applies results after each topological
  layer, keeping concurrent sibling nodes (e.g. RAG ∥ Web) race-free.
- **Runtime vs data**: `WorkflowState` is serialisable data; runtime deps
  (Request, user, model, event emitter) live on `ExecutionContext`.

## API endpoints

```
GET   /api/v1/agents/autonomy-levels
GET   /api/v1/agents/tools
GET   /api/v1/agents/{model_id}/workflow          # custom (meta) or generated
PUT   /api/v1/agents/{model_id}/workflow          # save custom workflow (owner/admin)
POST  /api/v1/agents/{model_id}/workflow/test     # run the workflow end-to-end
POST  /api/v1/agents/quality/evaluate
GET   /api/v1/agents/multi-agent/patterns
POST  /api/v1/agents/multi-agent/completions      # gated by MULTI_AGENT_ENABLED
GET   /api/v1/skills/            POST /api/v1/skills/
GET   /api/v1/skills/{id}        PUT/DELETE /api/v1/skills/{id}
POST  /api/v1/skills/import      GET /api/v1/skills/{id}/export
```

## Configuration (env vars, all optional)

```
AGENT_DEFAULT_AUTONOMY_LEVEL=assistant
AGENT_OPERATOR_MAX_TOOL_ITERATIONS=10
AGENT_QUALITY_PIPELINE_ENABLED=false
AGENT_QUALITY_SAMPLING_RATE=0.1
WORKFLOW_ENGINE_ENABLED=true
WORKFLOW_DEFAULT_TIMEOUT=300
WORKFLOW_NODE_TIMEOUT=60
MULTI_AGENT_ENABLED=false
MULTI_AGENT_MAX_PARALLEL=5
MULTI_AGENT_DEBATE_ROUNDS=3
MULTI_AGENT_CONSENSUS_THRESHOLD=0.8
QUALITY_CLAIM_DECOMPOSITION_ENABLED=false
QUALITY_GROUNDING_ENABLED=false
QUALITY_DOC_GRADING_ENABLED=false
```

These are declared as `PersistentConfig` in `agent/config.py` (DB-backed,
Redis-synced, env-seeded) following the same pattern as `bcgpt/config.py`.

## Tests

Pure-Python unit tests (no DB / app required):

```bash
cd backend && PYTHONPATH=. pytest bcgpt/agent/tests/ -q
```

Covers the engine (topo sort, layers, cycles, error strategies, conditional
pruning), generator, serializer, ReAct loop (native + prompt + max-iter),
definitions round-trip, and multi-agent routing.

## Notes & deferred items

- **Autonomy storage** uses `Model.meta` rather than a new column (the guide's
  Step 1 migration) — idiomatic for this "Agent-as-Model" codebase and avoids a
  schema migration. A typed `autonomy_level` field is declared on `ModelMeta`.
- **Skills** are stored in an in-process registry (`app.state.AGENT_SKILLS`);
  swap for a DB table later without changing the API surface.
- **MCP integration** and **Agentic Search (6-phase Plan-and-Execute)** are the
  guide's lowest-priority (P3) items and are not implemented here.
- The DAG engine is wired as a standalone, tested subsystem reachable via the
  `/workflow/test` endpoint; integrating it into the main streaming chat path
  (the guide's Phase 2 Step 4 middleware refactor) is intentionally left as a
  follow-up to preserve zero-regression on the hot path.
