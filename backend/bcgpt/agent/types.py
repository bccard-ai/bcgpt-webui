"""Core enums and value types for the agent subsystem.

These mirror the Open-MoAI taxonomy (3-Tier autonomy, 10 node types, 5+ multi
agent patterns) but are expressed as plain ``str`` enums so they serialise
cleanly to JSON and are comparable to the raw strings stored in ``Model.meta``.
"""

from __future__ import annotations

from enum import Enum


class AgentAutonomyLevel(str, Enum):
    """Agent autonomy tier (Open-MoAI 3-Tier model).

    * ``SUGGEST``  – Level 1: fast suggestion, no tools, no pre-search.
    * ``ASSISTANT`` – Level 2 (**default**): fixed pre-search DAG
      (RAG + Web → merge → LLM → response). Handles the vast majority of
      traffic; safe and predictable.
    * ``OPERATOR``  – Level 3: dynamic ReAct tool loop where the LLM decides
      when to search. Must be **explicitly** enabled per model (security gate).
    """

    SUGGEST = "suggest"
    ASSISTANT = "assistant"
    OPERATOR = "operator"

    @classmethod
    def from_value(cls, value: str | None) -> "AgentAutonomyLevel":
        """Coerce an arbitrary string to a level, defaulting to ASSISTANT."""
        if not value:
            return cls.ASSISTANT
        try:
            return cls(str(value).strip().lower())
        except ValueError:
            return cls.ASSISTANT


# ``AgentType`` historically mirrored the autonomy levels in Open-MoAI; kept as
# an alias-style enum for API compatibility with the guide.
class AgentType(str, Enum):
    SUGGEST = "suggest"
    ASSISTANT = "assistant"
    OPERATOR = "operator"


class NodeType(str, Enum):
    """The 10 workflow node types."""

    USER_INPUT = "user_input"
    RAG_SEARCH = "rag_search"
    WEB_SEARCH = "web_search"
    CONTEXT_MERGE = "context_merge"
    CONDITIONAL = "conditional"
    LLM_CALL = "llm_call"
    API_CALL = "api_call"
    TEXT_PROCESSOR = "text_processor"
    PII_PROCESSOR = "pii_processor"
    RESPONSE = "response"

    @classmethod
    def from_value(cls, value: str) -> "NodeType":
        return cls(str(value).strip().lower())


class ErrorStrategy(str, Enum):
    """Per-node error handling strategy used by the workflow engine."""

    STOP = "stop"  # halt the workflow, mark failed
    CONTINUE = "continue"  # skip the node, keep going
    RETRY = "retry"  # retry up to ``max_retries`` then fall back to STOP
    FALLBACK = "fallback"  # substitute ``fallback_value`` and continue

    @classmethod
    def from_value(cls, value: str | None) -> "ErrorStrategy":
        if not value:
            return cls.STOP
        try:
            return cls(str(value).strip().lower())
        except ValueError:
            return cls.STOP


class MultiAgentPattern(str, Enum):
    """Coordination patterns for the multi-agent executor."""

    SEQUENTIAL = "sequential"  # A → B → C pipeline
    PARALLEL = "parallel"  # concurrent, merge outputs
    DEBATE = "debate"  # argue → refine over rounds (anchored refinement)
    CONSENSUS = "consensus"  # progressive escalation: pair verify → debate → synthesize
    VOTING = "voting"  # trace-level synthesis across all agent reasoning
    MOA = "moa"  # Mixture of Agents (proposers → council-style aggregator)
    COUNCIL = "council"  # heterogeneous models + structured 4-section synthesis

    @classmethod
    def from_value(cls, value: str) -> "MultiAgentPattern":
        return cls(str(value).strip().lower())
