"""Quality control pipeline (Open-MoAI pattern).

    LLM Response
        │
        ▼
   ClaimVerifier ──▶ AnswerGrounder ──▶ DocumentGrader ──▶ EntailmentScorer
   (decompose to     (each claim         (doc relevance      (overall support
    atomic claims)    backed by src?)     to the query)       sufficiency)

All stages are LLM-backed, gated behind config flags, and degrade gracefully
(any failure yields a neutral score rather than raising), so enabling the
pipeline can never break a chat response.
"""

from bcgpt.agent.quality.claim_verifier import ClaimVerifier
from bcgpt.agent.quality.answer_grounder import AnswerGrounder
from bcgpt.agent.quality.document_grader import DocumentGrader
from bcgpt.agent.quality.entailment_scorer import EntailmentScorer
from bcgpt.agent.quality.pipeline import QualityPipeline, QualityReport
from bcgpt.agent.quality.lettuce_detect import check_hallucination

__all__ = [
    "ClaimVerifier",
    "AnswerGrounder",
    "DocumentGrader",
    "EntailmentScorer",
    "QualityPipeline",
    "QualityReport",
    "check_hallucination",
]
