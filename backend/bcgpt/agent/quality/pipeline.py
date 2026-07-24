"""QualityPipeline: orchestrate the four quality stages into one report."""

from __future__ import annotations

import asyncio
import logging
from dataclasses import asdict, dataclass, field
from typing import Any

from bcgpt.agent.quality.answer_grounder import AnswerGrounder
from bcgpt.agent.quality.citation_audit import audit_citations
from bcgpt.agent.quality.claim_verifier import ClaimVerifier
from bcgpt.agent.quality.doc_quality_score import score_document
from bcgpt.agent.quality.document_grader import DocumentGrader
from bcgpt.agent.quality.entailment_scorer import EntailmentScorer
from bcgpt.agent.quality.lettuce_detect import check_hallucination

log = logging.getLogger(__name__)


@dataclass
class QualityReport:
    claims: list[str] = field(default_factory=list)
    grounding: list[dict] = field(default_factory=list)
    doc_grades: list[dict] = field(default_factory=list)
    grounding_score: float = 0.0
    doc_quality_score: float = 0.0
    entailment_score: float = 0.0
    overall_score: float = 0.0
    rationale: str = ""
    lettuce_detect: dict = field(default_factory=dict)
    citation_audit: dict = field(default_factory=dict)
    doc_structure_score: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


# Stage weights for the overall score.
_W_GROUNDING = 0.4
_W_DOC = 0.2
_W_ENTAIL = 0.4


def _compute_overall_score(
    grounding_score: float,
    doc_quality_score: float,
    entailment_score: float,
    *,
    grounding_enabled: bool = True,
    doc_enabled: bool = True,
    entail_enabled: bool = True,
) -> float:
    """Weighted overall quality, renormalized over the INCLUDED stages.

    A stage flagged ``False`` -- disabled by config OR skipped/failed at runtime
    -- is excluded (its weight removed from the denominator) so the reported
    figure stays on a comparable 0..1 scale across configurations and is robust
    to a flaky LLM call. Previously a non-contributing stage counted as 0.0,
    deflating the score (e.g. capping it at 0.6 when grounding was off, or when
    grounding's LLM call errored). Returns 0.0 when no stage is included.
    """
    total = 0.0
    weight_sum = 0.0
    if entail_enabled:
        total += _W_ENTAIL * entailment_score
        weight_sum += _W_ENTAIL
    if grounding_enabled:
        total += _W_GROUNDING * grounding_score
        weight_sum += _W_GROUNDING
    if doc_enabled:
        total += _W_DOC * doc_quality_score
        weight_sum += _W_DOC
    if weight_sum <= 0:
        return 0.0
    return round(total / weight_sum, 4)


class QualityPipeline:
    """Runs claim decomposition → grounding → doc grading → entailment.

    Each stage is independently toggleable; disabled stages contribute a
    neutral value so the overall score stays comparable.
    """

    def __init__(
        self,
        request: Any,
        user: Any,
        model_id: str,
        *,
        claim_decomposition: bool = True,
        grounding: bool = True,
        doc_grading: bool = True,
        entailment: bool = True,
        citation_audit: bool = False,
        doc_structure_score: bool = False,
        lettuce_detect: bool = True,
        lettuce_detect_threshold: float = 0.7,
        default_model: str = "",
        claim_model: str = "",
        grounding_model: str = "",
        doc_grading_model: str = "",
        entailment_model: str = "",
    ) -> None:
        self.request = request
        self.user = user
        self.model_id = model_id
        self.enable_claims = claim_decomposition
        self.enable_grounding = grounding
        self.enable_doc = doc_grading
        self.enable_entail = entailment
        self.enable_citation_audit = citation_audit
        self.enable_doc_structure = doc_structure_score
        self.enable_lettuce = lettuce_detect
        self.lettuce_threshold = lettuce_detect_threshold

        base = default_model or model_id
        self.claim_verifier = ClaimVerifier(request, user, claim_model or base)
        self.answer_grounder = AnswerGrounder(request, user, grounding_model or base)
        self.document_grader = DocumentGrader(request, user, doc_grading_model or base)
        self.entailment_scorer = EntailmentScorer(
            request, user, entailment_model or base
        )

    async def evaluate(
        self, response: str, sources: list[dict], query: str
    ) -> QualityReport:
        report = QualityReport()

        # Deterministic, no-LLM citation-grounding audit. Cheap, so run it first
        # and unconditionally of the LettuceDetect early-return below.
        # Deterministic, no-LLM structural document-quality score (long-form output).
        if self.enable_doc_structure:
            try:
                report.doc_structure_score = score_document(response)
            except Exception as exc:
                log.warning("Doc structure score failed: %s", exc)

        if self.enable_citation_audit:
            try:
                report.citation_audit = audit_citations(response, sources)
            except Exception as exc:
                log.warning("Citation audit failed: %s", exc)

        # Pre-filter: fast encoder-based hallucination check.
        # If enabled and the answer passes (no hallucinated spans), the
        # expensive LLM stages are skipped since the answer is already clean.
        if self.enable_lettuce:
            lettuce_result = check_hallucination(
                response=response,
                sources=sources,
                query=query,
                threshold=self.lettuce_threshold,
            )
            report.lettuce_detect = lettuce_result
            if lettuce_result.get("passed") and lettuce_result.get("enabled"):
                log.info("LettuceDetect passed — skipping LLM quality stages")
                report.overall_score = 1.0
                return report
        else:
            report.lettuce_detect = {
                "passed": True,
                "spans": [],
                "max_confidence": 0.0,
                "enabled": False,
            }

        # Claims → grounding is sequential (grounding needs claims). Doc grading
        # and entailment are independent, so run them concurrently. Each stage
        # catches its own errors and reports whether it CONTRIBUTED a score; a
        # stage that is disabled OR fails at runtime is excluded from the overall
        # (via _compute_overall_score's renormalization), so a flaky LLM call
        # cannot silently tank the quality score by contributing a 0.
        async def run_grounding() -> bool:
            try:
                if self.enable_claims:
                    report.claims = await self.claim_verifier.decompose(response)
                if self.enable_grounding and report.claims:
                    report.grounding = await self.answer_grounder.verify(
                        report.claims, sources
                    )
                    report.grounding_score = AnswerGrounder.score(report.grounding)
                    return True
            except Exception as exc:
                log.warning("Quality grounding stage failed: %s", exc)
            return False

        async def run_doc_grading() -> bool:
            if not self.enable_doc or not sources:
                return False
            try:
                report.doc_grades = await self.document_grader.grade(sources, query)
                report.doc_quality_score = DocumentGrader.score(report.doc_grades)
                return True
            except Exception as exc:
                log.warning("Quality doc-grading stage failed: %s", exc)
            return False

        async def run_entailment() -> bool:
            if not self.enable_entail:
                return False
            try:
                res = await self.entailment_scorer.score(response, sources)
                report.entailment_score = res.get("entailment", 0.0)
                report.rationale = res.get("rationale", "")
                return True
            except Exception as exc:
                log.warning("Quality entailment stage failed: %s", exc)
            return False

        grounding_ok, doc_ok, entail_ok = await asyncio.gather(
            run_grounding(), run_doc_grading(), run_entailment()
        )

        report.overall_score = _compute_overall_score(
            report.grounding_score,
            report.doc_quality_score,
            report.entailment_score,
            grounding_enabled=grounding_ok,
            doc_enabled=doc_ok,
            entail_enabled=entail_ok,
        )
        return report
