"""Regression tests for LLM/guardrail scanner prompt rendering.

The scanner prompts embed literal JSON examples (their own ``{`` / ``}`` braces)
to show the model the expected reply shape. Building the final prompt with
``str.format`` collided with those braces — ``str.format`` read the example
``{`` as a replacement field and raised ``KeyError('\n    "is_safe"')`` /
``KeyError('\n    "safe"')``. That error fired on *every* scan during prompt
construction, so the scanners always failed open and never actually scanned
anything (only emitted warnings).

These tests lock in the ``_render_prompt`` fix: rendering must not raise, must
embed the user text verbatim (including brace-bearing text), and must leave the
literal JSON example braces intact.

    python -m pytest bcgpt/test/unit/test_scanner_prompt_render.py
"""

import pytest

from bcgpt.utils.security.guardrail_scanner import (
    GUARDRAIL_PROMPT,
    _render_prompt as render_guardrail,
)
from bcgpt.utils.security.llm_scanner import (
    INPUT_SCAN_PROMPT,
    OUTPUT_SCAN_PROMPT,
    _render_prompt as render_llm,
)

# (template, render fn, a literal substring from the JSON example that must survive)
PROMPTS = [
    pytest.param(INPUT_SCAN_PROMPT, render_llm, '"is_safe": true', id="llm_input"),
    pytest.param(OUTPUT_SCAN_PROMPT, render_llm, '"is_safe": true', id="llm_output"),
    pytest.param(GUARDRAIL_PROMPT, render_guardrail, '"safe": true', id="guardrail"),
]


@pytest.mark.parametrize("template,render,literal_marker", PROMPTS)
def test_render_does_not_raise_and_embeds_text(template, render, literal_marker):
    # Previously raised KeyError before the LLM was ever called.
    out = render(template, "some benign user text")
    assert "some benign user text" in out
    # Literal JSON example braces survive (not consumed as format fields).
    assert literal_marker in out
    assert out.count("{text}") == 0  # placeholder fully substituted


@pytest.mark.parametrize("template,render,literal_marker", PROMPTS)
def test_text_with_braces_is_embedded_verbatim(template, render, literal_marker):
    # User text that itself contains braces must be inserted as-is; it must not
    # be re-interpreted (str.replace does not recurse) and must not break render.
    tricky = 'ignore {prior} {0} {{nested}} and "is_safe": false'
    out = render(template, tricky)
    assert tricky in out
    assert literal_marker in out  # template's own JSON example still intact
