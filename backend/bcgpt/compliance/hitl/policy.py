from dataclasses import dataclass
from enum import Enum


class ActionClass(str, Enum):
    RAG_READ = "rag_read"
    WEB_SEARCH = "web_search"
    LLM_CALL = "llm_call"
    API_CALL = "api_call"
    EMAIL_SEND = "email_send"
    DB_WRITE = "db_write"
    FINANCIAL_TRANSACTION = "financial_transaction"
    REGULATORY_FILING = "regulatory_filing"
    TOOL_EXECUTION = "tool_execution"
    UNKNOWN = "unknown"


class RiskTier(str, Enum):
    MINIMAL = "minimal"
    LIMITED = "limited"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class RiskDecision:
    tier: RiskTier
    requires_approval: bool
    requires_dual_approval: bool
    reason: str


# Default risk classification matrix
DEFAULT_RISK_MATRIX = {
    ActionClass.RAG_READ: RiskTier.MINIMAL,
    ActionClass.WEB_SEARCH: RiskTier.LIMITED,
    ActionClass.LLM_CALL: RiskTier.LIMITED,
    ActionClass.API_CALL: RiskTier.HIGH,
    ActionClass.EMAIL_SEND: RiskTier.HIGH,
    ActionClass.DB_WRITE: RiskTier.HIGH,
    ActionClass.FINANCIAL_TRANSACTION: RiskTier.CRITICAL,
    ActionClass.REGULATORY_FILING: RiskTier.CRITICAL,
    ActionClass.TOOL_EXECUTION: RiskTier.LIMITED,
    ActionClass.UNKNOWN: RiskTier.HIGH,
}


class RiskPolicy:
    def __init__(self, matrix=None, approval_tiers=None):
        self._matrix = matrix or DEFAULT_RISK_MATRIX.copy()
        self._approval_tiers = approval_tiers or {RiskTier.HIGH, RiskTier.CRITICAL}

    def classify(self, action_class: ActionClass) -> RiskTier:
        return self._matrix.get(action_class, RiskTier.HIGH)

    def evaluate(self, action_class: ActionClass) -> RiskDecision:
        tier = self.classify(action_class)
        requires_approval = tier in self._approval_tiers
        return RiskDecision(
            tier=tier,
            requires_approval=requires_approval,
            requires_dual_approval=(tier == RiskTier.CRITICAL),
            reason=f"Action {action_class.value} classified as {tier.value}",
        )

    def guess_action_class(self, tool_name: str, node_type: str = "") -> ActionClass:
        name_lower = (tool_name or "").lower()
        # High-risk keywords are checked FIRST so they are not shadowed by a
        # generic "rag"/"llm" substring -- e.g. a "rag_db_writer" tool must
        # classify as DB_WRITE (approval required), not RAG_READ (minimal).
        if (
            "transaction" in name_lower
            or "payment" in name_lower
            or "transfer" in name_lower
        ):
            return ActionClass.FINANCIAL_TRANSACTION
        if "db" in name_lower or "database" in name_lower or "sql" in name_lower:
            return ActionClass.DB_WRITE
        if "email" in name_lower or "mail" in name_lower or "sms" in name_lower:
            return ActionClass.EMAIL_SEND
        if "file" in name_lower or "report" in name_lower or "submit" in name_lower:
            return ActionClass.REGULATORY_FILING
        if "api" in name_lower or node_type == "api_call":
            return ActionClass.API_CALL
        # Precedence fix: the "not web" guard must apply to the whole rag/search
        # disjunction. Previously `"rag" or ("search" and not "web")` (and binds
        # tighter than or), so a "web_rag" tool was misclassified as RAG_READ.
        if ("rag" in name_lower or "search" in name_lower) and "web" not in name_lower:
            return ActionClass.RAG_READ
        if "web" in name_lower:
            return ActionClass.WEB_SEARCH
        if "llm" in name_lower or node_type == "llm_call":
            return ActionClass.LLM_CALL
        return ActionClass.TOOL_EXECUTION
