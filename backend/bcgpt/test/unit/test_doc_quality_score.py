"""Unit tests for bcgpt.agent.quality.doc_quality_score (deterministic, no LLM)."""

import pytest
from bcgpt.agent.quality.doc_quality_score import score_document

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

GOOD_DOC = """\
# Introduction

This document covers the key ideas in depth.

## Background

Understanding the **background** is essential.
Here we provide context and history.

The field has grown rapidly over recent decades.

## Methods

We applied the following steps:

- Collect raw data from sources
- Clean and normalise the dataset
- Run the analysis pipeline

Results were reviewed by two independent auditors.

## Conclusion

In *summary*, the approach proved effective and scalable.
"""

# Same word-count ballpark, no headings, no lists, no emphasis, one big block
WALL_DOC = (
    "This document covers the key ideas in depth understanding the background "
    "is essential here we provide context and history the field has grown rapidly "
    "over recent decades we applied the following steps collect raw data from "
    "sources clean and normalise the dataset run the analysis pipeline results "
    "were reviewed by two independent auditors in summary the approach proved "
    "effective and scalable and we believe it will continue to do so going forward "
    "with no markdown structure whatsoever just a giant wall of plain text that "
    "keeps going and going without any structural cues for the reader at all."
)

HEADINGS_ONLY_DOC = """\
# Title

## Section One

## Section Two

### Sub-section

"""

BULLET_DOC = """\
# Shopping list

- Apples
- Bananas
- Carrots
- Dates
- Elderberries
"""

NO_LIST_DOC = """\
# My Document

This paragraph has no list items whatsoever.
Just plain text describing things without enumerating them.

Another paragraph with more text.
"""


# ---------------------------------------------------------------------------
# Test 1 — well-structured doc scores higher than flat wall-of-text
# ---------------------------------------------------------------------------


def test_good_vs_wall():
    good_result = score_document(GOOD_DOC)
    wall_result = score_document(WALL_DOC)
    assert (
        good_result["score"] > wall_result["score"]
    ), f"Expected good ({good_result['score']}) > wall ({wall_result['score']})"


# ---------------------------------------------------------------------------
# Test 2 — empty string
# ---------------------------------------------------------------------------


def test_empty_string():
    result = score_document("")
    assert result["score"] == 0.0
    for dim_name, val in result["dimensions"].items():
        assert (
            val == 0.0
        ), f"Dimension {dim_name!r} should be 0.0 for empty input, got {val}"


def test_whitespace_only():
    result = score_document("   \n\n\t  \n")
    assert result["score"] == 0.0
    for val in result["dimensions"].values():
        assert val == 0.0


# ---------------------------------------------------------------------------
# Test 3 — headings detection
# ---------------------------------------------------------------------------


def test_heading_present():
    doc_with_headings = "# Title\n\nSome content here.\n\n## Sub\n\nMore content.\n"
    result = score_document(doc_with_headings)
    assert (
        result["dimensions"]["heading"] > 0
    ), "heading dim should be > 0 when headings present"


def test_no_heading():
    doc_no_headings = "This is just plain text.\n\nAnother paragraph.\n"
    result = score_document(doc_no_headings)
    assert (
        result["dimensions"]["heading"] == 0.0
    ), "heading dim should be 0.0 with no headings"
    assert any(
        "heading" in s.lower() or "Add or fix" in s for s in result["suggestions"]
    ), "heading suggestion should be present when heading dim == 0"


# ---------------------------------------------------------------------------
# Test 4 — list detection
# ---------------------------------------------------------------------------


def test_list_present():
    result = score_document(BULLET_DOC)
    assert result["dimensions"]["list"] > 0, "list dim should be > 0 with bullet items"


def test_no_list():
    result = score_document(NO_LIST_DOC)
    assert (
        result["dimensions"]["list"] == 0.0
    ), "list dim should be 0.0 with no list items"
    assert any(
        "list" in s.lower() or "bullet" in s.lower() for s in result["suggestions"]
    ), "list suggestion should be present when list dim == 0"


# ---------------------------------------------------------------------------
# Test 5 — score in [0, 100] and dims in [0, 1]
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "doc",
    [
        GOOD_DOC,
        WALL_DOC,
        HEADINGS_ONLY_DOC,
        BULLET_DOC,
        NO_LIST_DOC,
        "",
        "   ",
        "# Only a heading\n",
        "- one\n- two\n- three\n",
        "**bold** and *italic* everywhere **again** *yes*\n",
    ],
)
def test_score_bounds(doc):
    result = score_document(doc)
    assert 0.0 <= result["score"] <= 100.0, f"score out of bounds: {result['score']}"
    for name, val in result["dimensions"].items():
        assert 0.0 <= val <= 1.0, f"dim {name!r} out of [0,1]: {val}"


# ---------------------------------------------------------------------------
# Test 6 — headings-only doc
# ---------------------------------------------------------------------------


def test_headings_only():
    result = score_document(HEADINGS_ONLY_DOC)
    assert (
        result["dimensions"]["heading"] > 0
    ), "heading should be > 0 in headings-only doc"
    assert (
        result["dimensions"]["list"] == 0.0
    ), "list should be 0.0 in headings-only doc"
    assert (
        result["dimensions"]["emphasis"] == 0.0
    ), "emphasis should be 0.0 in headings-only doc"


# ---------------------------------------------------------------------------
# Test 7 — suggestions only for dims < 0.7
# ---------------------------------------------------------------------------


def test_suggestions_threshold():
    good_result = score_document(GOOD_DOC)
    poor_result = score_document(WALL_DOC)

    # Poor doc should have at least as many suggestions as good doc
    assert len(poor_result["suggestions"]) >= len(
        good_result["suggestions"]
    ), "poor doc should have >= suggestions compared to good doc"

    # Verify: suggestions for dims >= 0.7 must NOT appear
    good_dims = good_result["dimensions"]
    good_suggestions_text = " ".join(good_result["suggestions"])
    # Map suggestion text back to dimension names by checking _SUGGESTIONS mapping
    from bcgpt.agent.quality.doc_quality_score import _SUGGESTIONS

    for dim, sugg in _SUGGESTIONS.items():
        if good_dims[dim] >= 0.7:
            assert sugg not in good_result["suggestions"], (
                f"Suggestion for dim {dim!r} (score={good_dims[dim]:.2f}) should not appear "
                f"when score >= 0.7"
            )
        else:
            assert sugg in good_result["suggestions"], (
                f"Suggestion for dim {dim!r} (score={good_dims[dim]:.2f}) SHOULD appear "
                f"when score < 0.7"
            )
