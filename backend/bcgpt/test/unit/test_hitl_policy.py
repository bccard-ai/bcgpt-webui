"""Tests for the HITL risk-classification policy (``compliance/hitl/policy.py``).

``policy.py`` is pure (dataclass + enum only -- no DB/config import), so the whole
risk matrix, the approval decision, and the tool-name -> action-class heuristic are
exercised directly. These lock the iter-68 fix to ``guess_action_class``: high-risk
keywords are now checked before the generic "rag"/"llm" substrings (so a tool like
``rag_db_writer`` classifies as DB_WRITE/approval-required, not RAG_READ), and the
``rag/search`` vs ``web`` check uses correct precedence (``"web_rag"`` -> WEB_SEARCH,
not RAG_READ). A misclassification here would either skip a required HITL approval
(false MINIMAL) or over-gate a benign action.

Runnable: cd backend && python3 -m pytest bcgpt/test/unit/test_hitl_policy.py -q
"""

from __future__ import annotations

from bcgpt.compliance.hitl.policy import (
    ActionClass,
    DEFAULT_RISK_MATRIX,
    RiskPolicy,
    RiskTier,
)

# ---------------------------------------------------------------------------
# classify -- action class -> risk tier (default matrix)
# ---------------------------------------------------------------------------


def test_classify_default_matrix():
    p = RiskPolicy()
    assert p.classify(ActionClass.RAG_READ) is RiskTier.MINIMAL
    assert p.classify(ActionClass.WEB_SEARCH) is RiskTier.LIMITED
    assert p.classify(ActionClass.LLM_CALL) is RiskTier.LIMITED
    assert p.classify(ActionClass.TOOL_EXECUTION) is RiskTier.LIMITED
    assert p.classify(ActionClass.API_CALL) is RiskTier.HIGH
    assert p.classify(ActionClass.EMAIL_SEND) is RiskTier.HIGH
    assert p.classify(ActionClass.DB_WRITE) is RiskTier.HIGH
    assert p.classify(ActionClass.FINANCIAL_TRANSACTION) is RiskTier.CRITICAL
    assert p.classify(ActionClass.REGULATORY_FILING) is RiskTier.CRITICAL


def test_classify_unknown_defaults_to_high():
    # An unrecognised action class defaults to HIGH (conservative), not MINIMAL.
    assert RiskPolicy().classify(ActionClass.UNKNOWN) is RiskTier.HIGH


def test_custom_matrix_overrides():
    p = RiskPolicy(matrix={ActionClass.RAG_READ: RiskTier.CRITICAL})
    assert p.classify(ActionClass.RAG_READ) is RiskTier.CRITICAL
    # Other classes still resolve via the default for unknown-in-matrix -> HIGH.
    assert p.classify(ActionClass.DB_WRITE) is RiskTier.HIGH


# ---------------------------------------------------------------------------
# evaluate -- approval decision
# ---------------------------------------------------------------------------


def test_evaluate_high_and_critical_require_approval():
    p = RiskPolicy()
    assert p.evaluate(ActionClass.DB_WRITE).requires_approval is True
    assert p.evaluate(ActionClass.FINANCIAL_TRANSACTION).requires_approval is True
    assert p.evaluate(ActionClass.API_CALL).requires_approval is True


def test_evaluate_minimal_and_limited_do_not_require_approval():
    p = RiskPolicy()
    assert p.evaluate(ActionClass.RAG_READ).requires_approval is False
    assert p.evaluate(ActionClass.WEB_SEARCH).requires_approval is False
    assert p.evaluate(ActionClass.LLM_CALL).requires_approval is False


def test_evaluate_dual_approval_only_for_critical():
    p = RiskPolicy()
    assert p.evaluate(ActionClass.FINANCIAL_TRANSACTION).requires_dual_approval is True
    assert p.evaluate(ActionClass.REGULATORY_FILING).requires_dual_approval is True
    assert p.evaluate(ActionClass.DB_WRITE).requires_dual_approval is False
    assert p.evaluate(ActionClass.RAG_READ).requires_dual_approval is False


def test_evaluate_custom_approval_tiers():
    # Lower the bar: require approval even for LIMITED actions.
    p = RiskPolicy(
        approval_tiers={
            RiskTier.MINIMAL,
            RiskTier.LIMITED,
            RiskTier.HIGH,
            RiskTier.CRITICAL,
        }
    )
    assert p.evaluate(ActionClass.RAG_READ).requires_approval is True
    assert p.evaluate(ActionClass.WEB_SEARCH).requires_approval is True


# ---------------------------------------------------------------------------
# guess_action_class -- tool-name / node-type heuristic (the iter-68 fix)
# ---------------------------------------------------------------------------


def test_guess_plain_tool_names():
    g = RiskPolicy().guess_action_class
    assert g("vector_search") is ActionClass.RAG_READ
    assert g("web_search") is ActionClass.WEB_SEARCH
    assert g("send_email") is ActionClass.EMAIL_SEND
    assert g("db_query") is ActionClass.DB_WRITE
    assert g("run_transaction") is ActionClass.FINANCIAL_TRANSACTION
    assert g("submit_report") is ActionClass.REGULATORY_FILING
    assert g("random_helper") is ActionClass.TOOL_EXECUTION


def test_guess_node_type_overrides():
    g = RiskPolicy().guess_action_class
    assert g("", node_type="llm_call") is ActionClass.LLM_CALL
    assert g("", node_type="api_call") is ActionClass.API_CALL


def test_guess_high_risk_keyword_not_shadowed_by_rag():
    """Regression (iter-68): a tool whose name contains BOTH 'rag' and a
    high-risk keyword must take the high-risk class -- previously the leading
    'rag' check classified it as RAG_READ (MINIMAL, no approval), which could
    skip a required HITL approval."""
    g = RiskPolicy().guess_action_class
    assert g("rag_db_writer") is ActionClass.DB_WRITE
    assert g("rag_email_sender") is ActionClass.EMAIL_SEND
    assert g("rag_payment_tool") is ActionClass.FINANCIAL_TRANSACTION


def test_guess_web_rag_is_web_not_rag_read():
    """Regression (iter-68 precedence fix): 'web_rag' must be WEB_SEARCH, not
    RAG_READ (the 'not web' guard now applies to the whole rag/search disjunction)."""
    g = RiskPolicy().guess_action_class
    assert g("web_rag_fetch") is ActionClass.WEB_SEARCH
    assert g("rag_search") is ActionClass.RAG_READ  # no web -> still RAG_READ


def test_guess_empty_name_falls_through():
    g = RiskPolicy().guess_action_class
    assert g("") is ActionClass.TOOL_EXECUTION
    assert g(None) is ActionClass.TOOL_EXECUTION  # type: ignore[arg-type]


def test_default_matrix_covers_all_action_classes():
    # Every ActionClass has an entry in the default matrix (no silent HIGH default
    # for a defined class).
    for ac in ActionClass:
        assert ac in DEFAULT_RISK_MATRIX, ac
