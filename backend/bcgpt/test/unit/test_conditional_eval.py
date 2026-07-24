"""Security tests for the workflow CONDITIONAL node's restricted ``eval``.

The CONDITIONAL node evaluates admin-authored branch expressions with Python
``eval`` (``agent/workflow/nodes/conditional.py``) -- an RCE-adjacent surface.
These tests lock the defenses verified in iter 61 so a future change cannot
silently weaken them:

  * ``__builtins__`` restricted to ``len/bool/min/max/any/all`` -- dangerous
    builtins (open/exec/getattr/__import__) are simply not in scope.
  * dunder access (``__class__``/``__bases__``/``__subclasses__``) is rejected
    by ``_DUNDER_PATTERN`` -- the canonical restricted-eval breakout.
  * ``_FORBIDDEN_TOKENS`` deny-list blocks import/exec/eval/compile/open/
    getattr/setattr/delattr on top.
  * normal expressions over the sanitized workflow namespace evaluate correctly.

These became possible once ``get_config()`` was made tolerant of a missing
``config`` table (iter 62), which unblocked importing config-dependent modules.

Runnable: cd backend && python3 -m pytest bcgpt/test/unit/test_conditional_eval.py -q
"""

from __future__ import annotations

from bcgpt.agent.workflow.nodes.conditional import (
    _is_expression_safe,
    _safe_eval,
)
from bcgpt.agent.workflow.state import WorkflowState

# ---------------------------------------------------------------------------
# _is_expression_safe -- the expression gate (pure)
# ---------------------------------------------------------------------------


def test_safe_expressions_pass():
    assert _is_expression_safe("len(user_input) > 0")
    assert _is_expression_safe("any(rag_results)")
    assert _is_expression_safe('user_input == "hello"')
    assert _is_expression_safe("len(user_input) > 0 and any(rag_results)")


def test_dunder_access_blocked():
    # The canonical restricted-eval breakout chain.
    assert not _is_expression_safe("x.__class__")
    assert not _is_expression_safe("().__class__.__bases__")
    assert not _is_expression_safe("a.__init__")
    assert not _is_expression_safe("obj.__subclasses__")


def test_forbidden_call_tokens_blocked():
    for expr in [
        "import os",
        "exec('x')",
        "eval('x')",
        "compile('x', '', 'exec')",
        "open('/etc/passwd')",
        'getattr(x, "a")',
        'setattr(x, "a", 1)',
        'delattr(x, "a")',
    ]:
        assert not _is_expression_safe(expr), expr


def test_rce_chain_blocked():
    # Combined dunder + import escape.
    assert not _is_expression_safe("__import__('os').system('id')")
    assert not _is_expression_safe("().__class__.__mro__[1].__subclasses__()")


def test_benign_substrings_now_allowed_word_boundary():
    # iter-67 fix: the forbidden-token check uses word boundaries, so benign
    # words that merely contain a forbidden substring are no longer over-blocked.
    for expr in (
        '"important" in user_input',
        "user_input.count('openai')",
        "user_input == 'opened'",
        "evaluate == True",
    ):
        assert _is_expression_safe(expr), expr


def test_forbidden_tokens_still_blocked_as_whole_words():
    # The word-boundary check still rejects the dangerous calls as identifiers.
    for expr in (
        "import os",
        "open('/etc/passwd')",
        "eval('x')",
        'getattr(user_input, "x")',
    ):
        assert not _is_expression_safe(expr), expr


# ---------------------------------------------------------------------------
# _safe_eval -- end-to-end over a WorkflowState
# ---------------------------------------------------------------------------


def test_safe_eval_truthy_branch():
    state = WorkflowState(user_input="hello world")
    assert _safe_eval("len(user_input) > 0", state) is True


def test_safe_eval_falsy_branch():
    state = WorkflowState(user_input="")
    assert _safe_eval("len(user_input) > 0", state) is False


def test_safe_eval_any_over_rag_results():
    assert _safe_eval("any(rag_results)", WorkflowState(rag_results=[1, 2])) is True
    assert _safe_eval("any(rag_results)", WorkflowState(rag_results=[])) is False


def test_safe_eval_allowed_builtins():
    state = WorkflowState(user_input="hello")
    assert _safe_eval("len(user_input) == 5", state) is True
    assert _safe_eval("bool(user_input)", state) is True


def test_safe_eval_namespace_vars():
    state = WorkflowState(variables={"mode": "fast"})
    assert _safe_eval('"mode" in vars', state) is True
    assert _safe_eval('"mode" in vars and len(vars) == 1', state) is True


def test_safe_eval_dunder_blocked_to_false():
    # A dunder escape must be blocked (returns False), never executed.
    assert _safe_eval("().__class__.__bases__", WorkflowState()) is False


def test_safe_eval_getattr_blocked_to_false():
    assert _safe_eval('getattr(user_input, "__class__")', WorkflowState()) is False


def test_safe_eval_open_blocked_to_false():
    assert _safe_eval('open("/etc/passwd")', WorkflowState()) is False


def test_safe_eval_undefined_name_is_false():
    # Names not in the namespace resolve to False (exception -> False), not a crash.
    assert _safe_eval("nonexistent_field > 0", WorkflowState()) is False


def test_safe_eval_syntax_error_is_false():
    assert _safe_eval("len(user_input", WorkflowState(user_input="x")) is False
