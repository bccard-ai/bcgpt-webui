from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

import numpy as np


@dataclass(frozen=True)
class FairnessResult:
    """Container for fairness metric results."""

    demographic_parity_difference: float
    demographic_parity_ratio: float
    disparate_impact_ratio: float
    equalized_odds_difference: Optional[float]
    group_selection_rates: dict[str, float]
    group_tpr: Optional[dict[str, float]]
    group_fpr: Optional[dict[str, float]]
    n_groups: int
    n_samples: int


def _safe_rate(numerator: int, denominator: int) -> float:
    """Safe division returning NaN for zero denominator."""
    return float(numerator / denominator) if denominator else float("nan")


def _min_max_ratio(values):
    """Min/max ratio, handling NaN and zero-division."""
    clean = [v for v in values if not np.isnan(v)]
    if not clean:
        return float("nan")
    lo, hi = min(clean), max(clean)
    if hi == 0:
        return 1.0 if lo == 0 else 0.0
    return float(lo / hi)


def compute_fairness_metrics(
    *,
    y_pred: list[int],
    protected_attributes: list[str],
    y_true: Optional[list[int]] = None,
    positive_label: int = 1,
) -> FairnessResult:
    """
    Compute fairness metrics for classified model outputs.

    Args:
        y_pred: Predicted labels (0/1) for each sample
        protected_attributes: Protected attribute value for each sample (e.g. "gender:female")
        y_true: Optional ground truth labels (required for equalized odds)
        positive_label: Label value indicating positive outcome (default 1)

    Returns:
        FairnessResult with all metrics computed
    """
    if len(y_pred) != len(protected_attributes):
        raise ValueError("y_pred and protected_attributes must have same length")
    if y_true is not None and len(y_true) != len(y_pred):
        raise ValueError("y_true and y_pred must have same length")

    n = len(y_pred)
    groups = sorted(set(protected_attributes))

    selection_rates: dict[str, float] = {}
    for group in groups:
        idx = [i for i, g in enumerate(protected_attributes) if g == group]
        positives = sum(y_pred[i] == positive_label for i in idx)
        selection_rates[group] = _safe_rate(positives, len(idx))

    clean_rates = [v for v in selection_rates.values() if not np.isnan(v)]
    dp_diff = (
        float(max(clean_rates) - min(clean_rates)) if clean_rates else float("nan")
    )
    dp_ratio = _min_max_ratio(clean_rates)
    di_ratio = dp_ratio

    eo_diff: Optional[float] = None
    group_tpr: Optional[dict[str, float]] = None
    group_fpr: Optional[dict[str, float]] = None

    if y_true is not None:
        group_tpr = {}
        group_fpr = {}
        for group in groups:
            idx = [i for i, g in enumerate(protected_attributes) if g == group]
            actual_pos = [i for i in idx if y_true[i] == positive_label]
            actual_neg = [i for i in idx if y_true[i] != positive_label]

            tp = sum(y_pred[i] == positive_label for i in actual_pos)
            fp = sum(y_pred[i] == positive_label for i in actual_neg)

            group_tpr[group] = _safe_rate(tp, len(actual_pos))
            group_fpr[group] = _safe_rate(fp, len(actual_neg))

        tprs = [v for v in group_tpr.values() if not np.isnan(v)]
        fprs = [v for v in group_fpr.values() if not np.isnan(v)]
        tpr_gap = (max(tprs) - min(tprs)) if tprs else 0.0
        fpr_gap = (max(fprs) - min(fprs)) if fprs else 0.0
        eo_diff = float(max(tpr_gap, fpr_gap))

    return FairnessResult(
        demographic_parity_difference=dp_diff,
        demographic_parity_ratio=dp_ratio,
        disparate_impact_ratio=di_ratio,
        equalized_odds_difference=eo_diff,
        group_selection_rates=selection_rates,
        group_tpr=group_tpr,
        group_fpr=group_fpr,
        n_groups=len(groups),
        n_samples=n,
    )


def evaluate_fairness_threshold(
    result: FairnessResult,
    *,
    max_dp_difference: float = 0.1,
    min_dp_ratio: float = 0.8,
    max_eo_difference: float = 0.1,
) -> dict:
    """
    Evaluate whether fairness metrics pass configurable thresholds.

    Defaults follow common regulatory standards:
    - Disparate impact 4/5 rule: ratio >= 0.8
    - DP difference <= 0.1 (10 percentage points)
    - EO difference <= 0.1
    """
    checks = {
        "demographic_parity_difference": {
            "value": result.demographic_parity_difference,
            "threshold": max_dp_difference,
            "passed": result.demographic_parity_difference <= max_dp_difference,
            "direction": "<=",
        },
        "demographic_parity_ratio": {
            "value": result.demographic_parity_ratio,
            "threshold": min_dp_ratio,
            "passed": result.demographic_parity_ratio >= min_dp_ratio,
            "direction": ">=",
        },
    }
    if result.equalized_odds_difference is not None:
        checks["equalized_odds_difference"] = {
            "value": result.equalized_odds_difference,
            "threshold": max_eo_difference,
            "passed": result.equalized_odds_difference <= max_eo_difference,
            "direction": "<=",
        }

    all_passed = all(c["passed"] for c in checks.values())
    return {
        "overall_passed": all_passed,
        "checks": checks,
        "n_groups": result.n_groups,
        "n_samples": result.n_samples,
    }
