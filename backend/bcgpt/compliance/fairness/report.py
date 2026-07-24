"""
Report generation for fairness test results.
"""


def generate_fairness_report(
    test_name: str,
    model_id: str,
    results: dict,
    *,
    framework: str = "FSC Financial AI Guidelines",
) -> dict:
    """
    Generate a structured fairness report suitable for regulatory submission.
    """
    metrics = results.get("metrics", {})
    threshold = results.get("threshold_evaluation", {})
    per_group = results.get("per_group", {})

    return {
        "report_metadata": {
            "test_name": test_name,
            "model_id": model_id,
            "framework": framework,
            "report_type": "AI Fairness Assessment Report",
        },
        "summary": {
            "overall_passed": threshold.get("overall_passed", False),
            "n_samples": metrics.get("n_samples", 0),
            "n_groups": metrics.get("n_groups", 0),
        },
        "metrics": metrics,
        "threshold_evaluation": threshold,
        "per_group_breakdown": per_group,
        "recommendations": _generate_recommendations(metrics, threshold),
    }


def _generate_recommendations(metrics: dict, threshold: dict) -> list[str]:
    """Generate actionable recommendations based on test results."""
    recommendations = []

    dp_diff = metrics.get("demographic_parity_difference", 0)
    if dp_diff > 0.1:
        recommendations.append(
            f"Demographic parity difference ({dp_diff:.3f}) exceeds 0.1 threshold. "
            "Review training data balance and model behavior across protected groups."
        )

    dp_ratio = metrics.get("demographic_parity_ratio", 1.0)
    if dp_ratio < 0.8:
        recommendations.append(
            f"Disparate impact ratio ({dp_ratio:.3f}) is below the 4/5 rule (0.8). "
            "This may indicate discriminatory bias requiring remediation."
        )

    eo_diff = metrics.get("equalized_odds_difference")
    if eo_diff is not None and eo_diff > 0.1:
        recommendations.append(
            f"Equalized odds difference ({eo_diff:.3f}) exceeds 0.1 threshold. "
            "True positive and false positive rates vary significantly across groups."
        )

    if not recommendations:
        recommendations.append(
            "All fairness metrics within acceptable thresholds. Continue periodic monitoring."
        )

    return recommendations
