"""Unit tests for the QualityPipeline overall-score computation.

The four LLM stages (claim decomposition / grounding / doc grading / entailment)
are not exercised here; these tests lock the *scoring* decision logic in
``agent/quality/pipeline.py``:

  * ``_compute_overall_score`` -- the 2026-06-22 fix that RENORMALIZES the
    weighted score over the enabled stages, so disabling a stage no longer
    deflates the result (previously a disabled stage contributed 0.0, capping
    the score -- e.g. grounding off -> max 0.6 instead of 1.0 -- contradicting
    the documented "comparable across configurations" behaviour).
  * the lettuce-pass short-circuit (``evaluate`` returns overall=1.0 and skips
    the LLM stages when the hallucination pre-filter passes).

The overall score is only ever returned as informational data
(``agents.py: report.to_dict()`` -- no threshold gate), so renormalization is
behaviour-safe.

Runnable standalone via:
    cd backend && python3 -m pytest bcgpt/test/unit/test_quality_pipeline.py -q
"""

from __future__ import annotations

import asyncio

from bcgpt.agent.quality import pipeline as qpipe
from bcgpt.agent.quality.pipeline import (
    QualityPipeline,
    _W_DOC,
    _W_ENTAIL,
    _W_GROUNDING,
    _compute_overall_score,
)

# ---------------------------------------------------------------------------
# Weight invariant
# ---------------------------------------------------------------------------


def test_stage_weights_sum_to_one():
    """The full-config weights must cover the whole 0..1 range."""
    assert _W_GROUNDING + _W_DOC + _W_ENTAIL == 1.0


# ---------------------------------------------------------------------------
# _compute_overall_score -- renormalization over enabled stages
# ---------------------------------------------------------------------------


def test_all_enabled_perfect_scores_is_one():
    assert _compute_overall_score(1.0, 1.0, 1.0) == 1.0


def test_all_enabled_zero_scores_is_zero():
    assert _compute_overall_score(0.0, 0.0, 0.0) == 0.0


def test_all_enabled_weighted_average():
    # 0.4*0.5 + 0.2*1.0 + 0.4*0.5 = 0.2 + 0.2 + 0.2 = 0.6
    assert _compute_overall_score(0.5, 1.0, 0.5) == 0.6


def test_disabled_grounding_does_not_deflate_score():
    """Regression: pre-fix a disabled stage contributed 0.0, so grounding off
    capped the score at 0.6 even with perfect doc+entail. Renormalization
    restores it to 1.0."""
    assert _compute_overall_score(0.0, 1.0, 1.0, grounding_enabled=False) == 1.0


def test_disabled_entailment_renormalizes():
    # doc=1, grounding=1, entail off -> (0.4 + 0.2)/0.6 = 1.0
    assert _compute_overall_score(1.0, 1.0, 0.0, entail_enabled=False) == 1.0


def test_disabled_doc_renormalizes():
    # grounding=1, entail=1, doc off -> (0.4 + 0.4)/0.8 = 1.0
    assert _compute_overall_score(1.0, 0.0, 1.0, doc_enabled=False) == 1.0


def test_single_enabled_stage_uses_it_directly():
    # Only entail enabled -> overall == entailment_score.
    assert (
        _compute_overall_score(
            0.9, 0.1, 0.7, grounding_enabled=False, doc_enabled=False
        )
        == 0.7
    )


def test_all_disabled_returns_zero():
    assert (
        _compute_overall_score(
            1.0,
            1.0,
            1.0,
            grounding_enabled=False,
            doc_enabled=False,
            entail_enabled=False,
        )
        == 0.0
    )


def test_score_rounded_to_four_decimals():
    # 0.4*(1/3) + 0.2*0 + 0.4*(1/3) = 0.8/3 = 0.26666... -> round 4dp = 0.2667
    score = _compute_overall_score(1 / 3, 0.0, 1 / 3)
    assert score == 0.2667


# ---------------------------------------------------------------------------
# evaluate -- lettuce-pass short-circuit (no LLM stages invoked)
# ---------------------------------------------------------------------------


def test_lettuce_pass_short_circuits_to_perfect_score(monkeypatch):
    """When the hallucination pre-filter passes (and is enabled), the expensive
    LLM stages are skipped and overall_score is 1.0."""
    monkeypatch.setattr(
        qpipe,
        "check_hallucination",
        lambda **kw: {
            "passed": True,
            "enabled": True,
            "spans": [],
            "max_confidence": 0.0,
        },
    )
    pipeline = QualityPipeline(None, None, "m")  # defaults: lettuce_detect=True
    report = asyncio.run(
        pipeline.evaluate("response text", [{"text": "a source"}], "query")
    )
    assert report.overall_score == 1.0
    assert report.lettuce_detect["passed"] is True
    # LLM stages skipped -> these stay empty
    assert report.claims == []
    assert report.grounding == []


# ---------------------------------------------------------------------------
# evaluate -- a FAILED stage is excluded (renormalized out), not scored 0
# ---------------------------------------------------------------------------


async def _raising(*_a, **_k):
    raise RuntimeError("stage blew up")


async def _entail_perfect(*_a, **_k):
    return {"entailment": 1.0, "rationale": ""}


def test_failed_stage_is_excluded_not_counted_as_zero(monkeypatch):
    """A stage whose LLM call raises must be excluded from the overall (via
    renormalization), not scored 0 and allowed to deflate the result.

    Pre-fix (config-enabled stage that errors): overall = 0.4*0 + 0.4*1.0 = 0.4.
    Post-fix: the failed grounding stage is excluded -> 0.4*1.0/0.4 = 1.0.
    """
    monkeypatch.setattr(
        qpipe,
        "check_hallucination",
        lambda **kw: {
            "passed": False,
            "enabled": True,
            "spans": [{"text": "x", "confidence": 0.9}],
            "max_confidence": 0.9,
        },
    )
    pipeline = QualityPipeline(None, None, "m", doc_grading=False)
    pipeline.claim_verifier.decompose = _raising  # grounding fails
    pipeline.entailment_scorer.score = _entail_perfect  # entail succeeds
    report = asyncio.run(pipeline.evaluate("response", [{"text": "a source"}], "query"))
    assert report.overall_score == 1.0  # entail alone, renormalized
    assert report.grounding == []  # grounding never completed
    assert report.entailment_score == 1.0


def test_all_stages_failing_yields_zero(monkeypatch):
    """When every stage fails, there is no signal -> overall 0.0 (not an error)."""
    monkeypatch.setattr(
        qpipe,
        "check_hallucination",
        lambda **kw: {
            "passed": False,
            "enabled": True,
            "spans": [],
            "max_confidence": 0.0,
        },
    )
    pipeline = QualityPipeline(None, None, "m")
    pipeline.claim_verifier.decompose = _raising
    pipeline.document_grader.grade = _raising
    pipeline.entailment_scorer.score = _raising
    report = asyncio.run(pipeline.evaluate("response", [{"text": "src"}], "query"))
    assert report.overall_score == 0.0
