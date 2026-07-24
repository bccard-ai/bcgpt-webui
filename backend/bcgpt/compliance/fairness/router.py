"""
Lightweight router exports for fairness testing helpers.

This module intentionally avoids framework-specific dependencies so the fairness
package remains importable with only numpy and the Python standard library.
"""

from .metrics import compute_fairness_metrics, evaluate_fairness_threshold
from .report import generate_fairness_report
from .test_harness import classify_response, run_fairness_test

__all__ = [
    "classify_response",
    "compute_fairness_metrics",
    "evaluate_fairness_threshold",
    "generate_fairness_report",
    "run_fairness_test",
]
