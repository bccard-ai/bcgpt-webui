"""Node handler implementations + the default registry factory."""

from __future__ import annotations

from bcgpt.agent.types import NodeType
from bcgpt.agent.workflow.registry import NodeHandlerRegistry

from bcgpt.agent.workflow.nodes.base import NodeHandler
from bcgpt.agent.workflow.nodes.user_input import UserInputHandler
from bcgpt.agent.workflow.nodes.rag_search import RAGSearchHandler
from bcgpt.agent.workflow.nodes.web_search import WebSearchHandler
from bcgpt.agent.workflow.nodes.context_merge import ContextMergeHandler
from bcgpt.agent.workflow.nodes.conditional import ConditionalHandler
from bcgpt.agent.workflow.nodes.llm_call import LLMCallHandler
from bcgpt.agent.workflow.nodes.api_call import APICallHandler
from bcgpt.agent.workflow.nodes.text_processor import TextProcessorHandler
from bcgpt.agent.workflow.nodes.pii_processor import PIIProcessorHandler
from bcgpt.agent.workflow.nodes.response import ResponseHandler

__all__ = [
    "NodeHandler",
    "UserInputHandler",
    "RAGSearchHandler",
    "WebSearchHandler",
    "ContextMergeHandler",
    "ConditionalHandler",
    "LLMCallHandler",
    "APICallHandler",
    "TextProcessorHandler",
    "PIIProcessorHandler",
    "ResponseHandler",
    "create_default_registry",
]


def create_default_registry() -> NodeHandlerRegistry:
    """Build a registry with all 10 built-in node handlers registered."""
    registry = NodeHandlerRegistry()
    registry.register(NodeType.USER_INPUT, UserInputHandler())
    registry.register(NodeType.RAG_SEARCH, RAGSearchHandler())
    registry.register(NodeType.WEB_SEARCH, WebSearchHandler())
    registry.register(NodeType.CONTEXT_MERGE, ContextMergeHandler())
    registry.register(NodeType.CONDITIONAL, ConditionalHandler())
    registry.register(NodeType.LLM_CALL, LLMCallHandler())
    registry.register(NodeType.API_CALL, APICallHandler())
    registry.register(NodeType.TEXT_PROCESSOR, TextProcessorHandler())
    registry.register(NodeType.PII_PROCESSOR, PIIProcessorHandler())
    registry.register(NodeType.RESPONSE, ResponseHandler())
    return registry
