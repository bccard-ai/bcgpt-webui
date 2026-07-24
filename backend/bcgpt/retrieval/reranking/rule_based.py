def rule_based_rerank(
    query: str,
    documents: list[dict],
) -> list[dict]:
    query_lower = query.lower()
    query_terms = query_lower.split()
    results = []

    for doc in documents:
        score = doc.get("score", 0.0)
        content = doc.get("text", doc.get("content", ""))
        content_lower = content.lower()
        content_length = len(content)

        bonus = 0.0

        # 1. Exact match bonus
        if query_lower in content_lower:
            bonus += 0.5

        # 2. Title match bonus
        title = doc.get("title", doc.get("name", ""))
        title_lower = title.lower() if title else ""
        title_matches = sum(1 for term in query_terms if term in title_lower)
        bonus += min(0.15 * title_matches, 0.4)

        # 3. Term frequency bonus
        term_count = sum(content_lower.count(term) for term in query_terms)
        bonus += min(0.05 * term_count, 0.3)

        # 4. Position weighting
        if query_terms and content_length > 0:
            first_pos = content_length
            for term in query_terms:
                idx = content_lower.find(term)
                if idx != -1 and idx < first_pos:
                    first_pos = idx
            if first_pos < content_length:
                bonus += 0.1 * (1 - first_pos / content_length)

        # 5. Coverage bonus
        if query_terms:
            terms_found = sum(1 for term in query_terms if term in content_lower)
            coverage = terms_found / len(query_terms)
            bonus += 0.2 * coverage

        doc_copy = dict(doc)
        doc_copy["score"] = score * (1 + bonus)
        results.append(doc_copy)

    results.sort(key=lambda d: d["score"], reverse=True)
    return results
