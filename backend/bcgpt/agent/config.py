"""Agent subsystem configuration.

Declares ``PersistentConfig`` globals (DB-backed, Redis-synced, env-seeded) for
the agent / workflow / multi-agent / quality features, following the exact
pattern used throughout ``bcgpt/config.py``:

    NAME = PersistentConfig(ENV_NAME, "dot.path", default_from_env)

and exposes small helpers to resolve a model's effective autonomy level.

This module imports ``bcgpt.config`` (which touches the DB at import time), so
it is only imported from request-time code (node handlers, routers) — never
from the pure-Python engine core, keeping the engine unit-testable in isolation.
"""

from __future__ import annotations

import os
from typing import Any

from bcgpt.config import PersistentConfig
from bcgpt.agent.types import AgentAutonomyLevel


def _env_bool(name: str, default: str = "False") -> bool:
    return os.environ.get(name, default).strip().lower() == "true"


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.environ.get(name, str(default)))
    except (TypeError, ValueError):
        return default


# === Agent System ===========================================================

AGENT_DEFAULT_AUTONOMY_LEVEL = PersistentConfig(
    "AGENT_DEFAULT_AUTONOMY_LEVEL",
    "agent.default_autonomy_level",
    os.environ.get("AGENT_DEFAULT_AUTONOMY_LEVEL", AgentAutonomyLevel.ASSISTANT.value),
)

AGENT_OPERATOR_MAX_TOOL_ITERATIONS = PersistentConfig(
    "AGENT_OPERATOR_MAX_TOOL_ITERATIONS",
    "agent.operator_max_tool_iterations",
    _env_int("AGENT_OPERATOR_MAX_TOOL_ITERATIONS", 10),
)

AGENT_QUALITY_PIPELINE_ENABLED = PersistentConfig(
    "AGENT_QUALITY_PIPELINE_ENABLED",
    "agent.quality_pipeline_enabled",
    _env_bool("AGENT_QUALITY_PIPELINE_ENABLED", "False"),
)

AGENT_QUALITY_SAMPLING_RATE = PersistentConfig(
    "AGENT_QUALITY_SAMPLING_RATE",
    "agent.quality_sampling_rate",
    _env_float("AGENT_QUALITY_SAMPLING_RATE", 0.1),
)

CODE_SANDBOX_ENABLED = PersistentConfig(
    "CODE_SANDBOX_ENABLED",
    "agent.code_sandbox_enabled",
    _env_bool("CODE_SANDBOX_ENABLED", "False"),
)

# === Workflow Engine ========================================================

WORKFLOW_ENGINE_ENABLED = PersistentConfig(
    "WORKFLOW_ENGINE_ENABLED",
    "agent.workflow.engine_enabled",
    _env_bool("WORKFLOW_ENGINE_ENABLED", "True"),
)

WORKFLOW_DEFAULT_TIMEOUT = PersistentConfig(
    "WORKFLOW_DEFAULT_TIMEOUT",
    "agent.workflow.default_timeout",
    _env_int("WORKFLOW_DEFAULT_TIMEOUT", 300),
)

WORKFLOW_NODE_TIMEOUT = PersistentConfig(
    "WORKFLOW_NODE_TIMEOUT",
    "agent.workflow.node_timeout",
    _env_int("WORKFLOW_NODE_TIMEOUT", 60),
)

# === Multi-Agent ============================================================

MULTI_AGENT_ENABLED = PersistentConfig(
    "MULTI_AGENT_ENABLED",
    "agent.multi_agent.enabled",
    _env_bool("MULTI_AGENT_ENABLED", "False"),
)

MULTI_AGENT_MAX_PARALLEL = PersistentConfig(
    "MULTI_AGENT_MAX_PARALLEL",
    "agent.multi_agent.max_parallel",
    _env_int("MULTI_AGENT_MAX_PARALLEL", 5),
)

MULTI_AGENT_DEBATE_ROUNDS = PersistentConfig(
    "MULTI_AGENT_DEBATE_ROUNDS",
    "agent.multi_agent.debate_rounds",
    _env_int("MULTI_AGENT_DEBATE_ROUNDS", 3),
)

MULTI_AGENT_CONSENSUS_THRESHOLD = PersistentConfig(
    "MULTI_AGENT_CONSENSUS_THRESHOLD",
    "agent.multi_agent.consensus_threshold",
    _env_float("MULTI_AGENT_CONSENSUS_THRESHOLD", 0.8),
)

# === Quality Pipeline =======================================================

QUALITY_CLAIM_DECOMPOSITION_ENABLED = PersistentConfig(
    "QUALITY_CLAIM_DECOMPOSITION_ENABLED",
    "agent.quality.claim_decomposition_enabled",
    _env_bool("QUALITY_CLAIM_DECOMPOSITION_ENABLED", "False"),
)

QUALITY_GROUNDING_ENABLED = PersistentConfig(
    "QUALITY_GROUNDING_ENABLED",
    "agent.quality.grounding_enabled",
    _env_bool("QUALITY_GROUNDING_ENABLED", "False"),
)

QUALITY_DOC_GRADING_ENABLED = PersistentConfig(
    "QUALITY_DOC_GRADING_ENABLED",
    "agent.quality.doc_grading_enabled",
    _env_bool("QUALITY_DOC_GRADING_ENABLED", "False"),
)

# open-moai adoption 1.3 — deterministic, no-LLM citation-grounding audit.
QUALITY_CITATION_AUDIT_ENABLED = PersistentConfig(
    "QUALITY_CITATION_AUDIT_ENABLED",
    "agent.quality.citation_audit_enabled",
    _env_bool("QUALITY_CITATION_AUDIT_ENABLED", "False"),
)

# open-moai adoption 2.3 — deterministic, no-LLM structural document-quality score.
QUALITY_DOC_STRUCTURE_SCORE_ENABLED = PersistentConfig(
    "QUALITY_DOC_STRUCTURE_SCORE_ENABLED",
    "agent.quality.doc_structure_score_enabled",
    _env_bool("QUALITY_DOC_STRUCTURE_SCORE_ENABLED", "False"),
)

QUALITY_DEFAULT_MODEL = PersistentConfig(
    "QUALITY_DEFAULT_MODEL",
    "agent.quality.default_model",
    os.environ.get("QUALITY_DEFAULT_MODEL", ""),
)

QUALITY_CLAIM_MODEL = PersistentConfig(
    "QUALITY_CLAIM_MODEL",
    "agent.quality.claim_model",
    os.environ.get("QUALITY_CLAIM_MODEL", ""),
)

QUALITY_GROUNDING_MODEL = PersistentConfig(
    "QUALITY_GROUNDING_MODEL",
    "agent.quality.grounding_model",
    os.environ.get("QUALITY_GROUNDING_MODEL", ""),
)

QUALITY_DOC_GRADING_MODEL = PersistentConfig(
    "QUALITY_DOC_GRADING_MODEL",
    "agent.quality.doc_grading_model",
    os.environ.get("QUALITY_DOC_GRADING_MODEL", ""),
)

QUALITY_ENTAILMENT_MODEL = PersistentConfig(
    "QUALITY_ENTAILMENT_MODEL",
    "agent.quality.entailment_model",
    os.environ.get("QUALITY_ENTAILMENT_MODEL", ""),
)

LETTUCE_DETECT_ENABLED = PersistentConfig(
    "LETTUCE_DETECT_ENABLED",
    "agent.quality.lettuce_detect_enabled",
    _env_bool("LETTUCE_DETECT_ENABLED", "False"),
)

LETTUCE_DETECT_THRESHOLD = PersistentConfig(
    "LETTUCE_DETECT_THRESHOLD",
    "agent.quality.lettuce_detect_threshold",
    _env_float("LETTUCE_DETECT_THRESHOLD", 0.7),
)


# === Autonomy resolution helpers ============================================

from bcgpt.agent.autonomy import (  # noqa: E402
    AUTONOMY_META_KEY,
    extract_meta,
    read_meta_autonomy,
)
from bcgpt.agent.autonomy import resolve_autonomy_level as _resolve_autonomy_level


def get_default_autonomy_level() -> AgentAutonomyLevel:
    return AgentAutonomyLevel.from_value(AGENT_DEFAULT_AUTONOMY_LEVEL.value)


def resolve_autonomy_level(model: Any) -> AgentAutonomyLevel:
    """Resolve the effective autonomy level for a model.

    Looks for ``meta.autonomy_level`` (and the legacy
    ``meta.capabilities.autonomy_level``); otherwise returns the configured
    default. Always returns a valid level — never raises.
    """
    return _resolve_autonomy_level(model, get_default_autonomy_level())


__all__ = [
    "AUTONOMY_META_KEY",
    "extract_meta",
    "read_meta_autonomy",
    "get_default_autonomy_level",
    "resolve_autonomy_level",
]
