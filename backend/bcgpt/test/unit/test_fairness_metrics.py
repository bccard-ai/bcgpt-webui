"""
Unit tests for compliance fairness metrics.
Pure numpy — no DB/env dependencies.
"""

import math
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from bcgpt.compliance.fairness.metrics import (
    compute_fairness_metrics,
    evaluate_fairness_threshold,
    FairnessResult,
)


def test_demographic_parity_zero_difference_equal_groups():
    """When both groups have the same selection rate, DP difference = 0."""
    result = compute_fairness_metrics(
        y_pred=[1, 1, 0, 0, 1, 1, 0, 0],
        protected_attributes=["g:a", "g:a", "g:a", "g:a", "g:b", "g:b", "g:b", "g:b"],
    )
    assert result.demographic_parity_difference == 0.0
    assert result.demographic_parity_ratio == 1.0
    assert result.n_groups == 2
    assert result.n_samples == 8


def test_demographic_parity_full_disparity():
    """One group all positive, other all negative → max disparity."""
    result = compute_fairness_metrics(
        y_pred=[1, 1, 1, 0, 0, 0],
        protected_attributes=["g:a", "g:a", "g:a", "g:b", "g:b", "g:b"],
    )
    assert result.demographic_parity_difference == 1.0
    assert result.demographic_parity_ratio == 0.0


def test_disparate_impact_four_fifths_rule_pass():
    """80% selection rate ratio should pass the 4/5 rule."""
    # Group A: 5/10 positive (50%), Group B: 4/10 positive (40%)
    # Ratio = 0.4/0.5 = 0.8 → exactly at threshold
    y_pred = [1] * 5 + [0] * 5 + [1] * 4 + [0] * 6
    attrs = ["a"] * 10 + ["b"] * 10
    result = compute_fairness_metrics(y_pred=y_pred, protected_attributes=attrs)
    assert 0.79 <= result.disparate_impact_ratio <= 0.81


def test_disparate_impact_four_fifths_rule_fail():
    """Clearly biased ratio should fail the 4/5 rule."""
    y_pred = [1] * 9 + [0] * 1 + [1] * 1 + [0] * 9
    attrs = ["a"] * 10 + ["b"] * 10
    result = compute_fairness_metrics(y_pred=y_pred, protected_attributes=attrs)
    assert result.disparate_impact_ratio < 0.5


def test_equalized_odds_no_ground_truth_returns_none():
    """Without y_true, equalized_odds_difference should be None."""
    result = compute_fairness_metrics(
        y_pred=[1, 0, 1, 0],
        protected_attributes=["a", "a", "b", "b"],
    )
    assert result.equalized_odds_difference is None
    assert result.group_tpr is None
    assert result.group_fpr is None


def test_equalized_odds_with_ground_truth():
    """With y_true, TPR and FPR should be computed per group."""
    y_pred = [1, 1, 0, 1, 0, 0]
    y_true = [1, 1, 0, 1, 1, 0]
    attrs = ["a", "a", "a", "b", "b", "b"]

    result = compute_fairness_metrics(
        y_pred=y_pred,
        protected_attributes=attrs,
        y_true=y_true,
    )
    assert result.equalized_odds_difference is not None
    assert result.group_tpr is not None
    assert result.group_fpr is not None
    assert "a" in result.group_tpr
    assert "b" in result.group_tpr


def test_threshold_evaluation_all_pass():
    """When metrics are within thresholds, overall_passed should be True."""
    result = compute_fairness_metrics(
        y_pred=[1, 0, 1, 0],
        protected_attributes=["a", "a", "b", "b"],
    )
    threshold = evaluate_fairness_threshold(result)
    assert threshold["overall_passed"] is True


def test_threshold_evaluation_dp_fail():
    """When DP difference exceeds threshold, overall_passed should be False."""
    result = compute_fairness_metrics(
        y_pred=[1, 1, 1, 0, 0, 0],
        protected_attributes=["a", "a", "a", "b", "b", "b"],
    )
    threshold = evaluate_fairness_threshold(result, max_dp_difference=0.1)
    assert threshold["overall_passed"] is False


def test_multi_group_support():
    """Should handle more than 2 protected groups."""
    result = compute_fairness_metrics(
        y_pred=[1, 0, 1, 0, 1, 0],
        protected_attributes=["x", "y", "x", "z", "y", "z"],
    )
    assert result.n_groups == 3
    assert len(result.group_selection_rates) == 3


def test_single_group_edge_case():
    """Single group should not crash."""
    result = compute_fairness_metrics(
        y_pred=[1, 0, 1],
        protected_attributes=["only", "only", "only"],
    )
    assert result.n_groups == 1
    assert result.demographic_parity_difference == 0.0


def test_length_mismatch_raises():
    """Mismatched y_pred and protected_attributes lengths should raise."""
    try:
        compute_fairness_metrics(
            y_pred=[1, 0],
            protected_attributes=["a", "b", "c"],
        )
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


def test_empty_input_edge_case():
    """Empty inputs should not crash."""
    result = compute_fairness_metrics(
        y_pred=[],
        protected_attributes=[],
    )
    assert result.n_samples == 0
    assert result.n_groups == 0
