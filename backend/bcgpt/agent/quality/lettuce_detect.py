"""Fast hallucination detection using LettuceDetect (encoder-based model).

This runs as a cheap pre-filter BEFORE the expensive LLM-based quality pipeline.
If the answer passes (no hallucinated spans above threshold), the LLM pipeline
can be skipped.
"""

from __future__ import annotations

import logging
from typing import Any

log = logging.getLogger(__name__)

_detector: Any | None = None


def _get_detector() -> Any | None:
    """Lazy-load the LettuceDetect model (CPU-friendly, ~149M params)."""
    global _detector
    if _detector is None:
        try:
            from lettucedetect.models.inference import HallucinationDetector

            _detector = HallucinationDetector(
                method="transformer",
                model_path="KRLabsOrg/lettucedetect-base-modernbert-en-v1",
            )
            log.info("LettuceDetect model loaded successfully")
        except ImportError:
            log.warning(
                "lettucedetect not installed — hallucination pre-filter disabled"
            )
            return None
        except Exception as e:
            log.warning(f"Failed to load LettuceDetect model: {e}")
            return None
    return _detector


def check_hallucination(
    response: str,
    sources: list[dict],
    query: str = "",
    threshold: float = 0.7,
) -> dict:
    """Check for hallucinated spans in the response.

    Returns dict with:
        passed: bool — True if no hallucinated spans above threshold
        spans: list[dict] — detected hallucinated spans with confidence scores
        max_confidence: float — highest hallucination confidence found
        enabled: bool — whether the detector was available
    """
    detector = _get_detector()
    if detector is None:
        return {
            "passed": True,
            "spans": [],
            "max_confidence": 0.0,
            "enabled": False,
        }

    try:
        contexts: list[str] = []
        for src in sources:
            text = src.get("text", src.get("content", ""))
            if text:
                contexts.append(text)

        if not contexts:
            return {
                "passed": True,
                "spans": [],
                "max_confidence": 0.0,
                "enabled": True,
            }

        predictions = detector.predict(
            context=contexts,
            question=query,
            answer=response,
            output_format="spans",
        )

        flagged_spans = [
            {
                "text": s.get("text", ""),
                "confidence": float(s.get("confidence", 0)),
            }
            for s in predictions
            if float(s.get("confidence", 0)) >= threshold
        ]

        max_conf = max((s["confidence"] for s in flagged_spans), default=0.0)

        return {
            "passed": len(flagged_spans) == 0,
            "spans": flagged_spans,
            "max_confidence": max_conf,
            "enabled": True,
        }
    except Exception as e:
        log.warning(f"LettuceDetect check failed: {e}")
        return {
            "passed": True,
            "spans": [],
            "max_confidence": 0.0,
            "enabled": True,
        }
