import re

_KR_PARTICLES = re.compile(r"[은는이가을를의에도에서로으로와과하다]$", re.UNICODE)


def _normalize_korean(word: str) -> str:
    return _KR_PARTICLES.sub("", word)


def evaluate_retrieval_quality(
    query: str,
    documents: list[dict],
) -> dict:
    if not documents:
        return {
            "score": 0.0,
            "verdict": "insufficient",
            "metrics": {
                "avg_similarity": 0.0,
                "keyword_overlap": 0.0,
                "content_coverage": 0.0,
                "diversity": 0.0,
            },
        }

    query_terms = [_normalize_korean(t.lower()) for t in query.split()]
    query_terms = [t for t in query_terms if t]

    # avg_similarity
    scores = [doc.get("score", 0.0) for doc in documents]
    avg_similarity = sum(scores) / len(scores)

    # keyword_overlap
    all_content = " ".join(
        doc.get("text", doc.get("content", "")).lower() for doc in documents
    )
    all_tokens = [_normalize_korean(t) for t in all_content.split()]
    if query_terms:
        found = sum(1 for qt in query_terms if qt in all_tokens)
        keyword_overlap = found / len(query_terms)
    else:
        keyword_overlap = 0.0

    # content_coverage
    covered = 0
    for doc in documents:
        content = doc.get("text", doc.get("content", ""))
        if len(content) > 100:
            content_lower = content.lower()
            if any(term in content_lower for term in query_terms):
                covered += 1
    content_coverage = covered / len(documents)

    # diversity via pairwise Jaccard
    doc_word_sets = []
    for doc in documents:
        content = doc.get("text", doc.get("content", ""))
        words = set(content.lower().split())
        doc_word_sets.append(words)

    if len(doc_word_sets) > 1:
        pairwise_jaccard = []
        for i in range(len(doc_word_sets)):
            for j in range(i + 1, len(doc_word_sets)):
                a, b = doc_word_sets[i], doc_word_sets[j]
                if a or b:
                    jaccard = len(a & b) / len(a | b)
                else:
                    jaccard = 0.0
                pairwise_jaccard.append(jaccard)
        avg_jaccard = sum(pairwise_jaccard) / len(pairwise_jaccard)
        diversity = 1.0 - avg_jaccard
    else:
        diversity = 0.0

    composite = (
        0.45 * avg_similarity
        + 0.25 * keyword_overlap
        + 0.15 * content_coverage
        + 0.15 * diversity
    ) * 100

    if composite >= 65:
        verdict = "sufficient"
    elif composite >= 40:
        verdict = "partial"
    else:
        verdict = "insufficient"

    return {
        "score": composite,
        "verdict": verdict,
        "metrics": {
            "avg_similarity": avg_similarity,
            "keyword_overlap": keyword_overlap,
            "content_coverage": content_coverage,
            "diversity": diversity,
        },
    }
