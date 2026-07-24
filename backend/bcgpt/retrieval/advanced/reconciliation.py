import re


def jaccard_similarity(text_a: str, text_b: str) -> float:
    set_a = set(text_a.lower().split())
    set_b = set(text_b.lower().split())
    if not set_a and not set_b:
        return 0.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union)


def detect_redundancy(documents: list[dict], threshold: float = 0.7) -> list[tuple]:
    redundant_pairs = []
    for i in range(len(documents)):
        content_i = documents[i].get("text", documents[i].get("content", ""))
        for j in range(i + 1, len(documents)):
            content_j = documents[j].get("text", documents[j].get("content", ""))
            sim = jaccard_similarity(content_i, content_j)
            if sim > threshold:
                redundant_pairs.append((i, j))
    return redundant_pairs


def group_by_topic(
    query: str, documents: list[dict], threshold: float = 0.6
) -> list[list]:
    query_terms = set(query.lower().split())
    if not documents:
        return []

    doc_sims = []
    for doc in documents:
        content = doc.get("text", doc.get("content", ""))
        doc_words = set(content.lower().split())
        if query_terms and doc_words:
            sim = len(query_terms & doc_words) / len(query_terms | doc_words)
        else:
            sim = 0.0
        doc_sims.append(sim)

    assigned = [False] * len(documents)
    groups = []

    for i in range(len(documents)):
        if assigned[i]:
            continue
        group = [i]
        assigned[i] = True
        for j in range(i + 1, len(documents)):
            if assigned[j]:
                continue
            content_i = documents[i].get("text", documents[i].get("content", ""))
            content_j = documents[j].get("text", documents[j].get("content", ""))
            sim = jaccard_similarity(content_i, content_j)
            if sim >= threshold:
                group.append(j)
                assigned[j] = True
        groups.append(group)

    return groups


def detect_conflicts(
    documents: list[dict], topic_groups: list[list] | None = None
) -> list[dict]:
    if topic_groups is None:
        return []

    number_pattern = re.compile(r"\d+(?:\.\d+)?%?")
    negation_pattern = re.compile(r"\b(not|no|never)\b|없다|아니다", re.IGNORECASE)

    conflicts = []
    for group in topic_groups:
        if len(group) < 2:
            continue

        doc_numbers = {}
        for idx in group:
            content = documents[idx].get("text", documents[idx].get("content", ""))
            nums = set(number_pattern.findall(content))
            doc_numbers[idx] = nums

        for i_pos in range(len(group)):
            for j_pos in range(i_pos + 1, len(group)):
                idx_i = group[i_pos]
                idx_j = group[j_pos]
                nums_i = doc_numbers[idx_i]
                nums_j = doc_numbers[idx_j]

                if nums_i and nums_j and nums_i != nums_j:
                    conflicts.append(
                        {
                            "type": "number",
                            "docs": [idx_i, idx_j],
                            "detail": f"Number mismatch: {nums_i} vs {nums_j}",
                        }
                    )

                content_i = documents[idx_i].get(
                    "text", documents[idx_i].get("content", "")
                )
                content_j = documents[idx_j].get(
                    "text", documents[idx_j].get("content", "")
                )

                neg_i = bool(negation_pattern.search(content_i))
                neg_j = bool(negation_pattern.search(content_j))

                if neg_i != neg_j:
                    conflicts.append(
                        {
                            "type": "negation",
                            "docs": [idx_i, idx_j],
                            "detail": "Negation asymmetry between documents",
                        }
                    )

    return conflicts


def reconcile_evidence(
    query: str,
    documents: list[dict],
) -> dict:
    redundant_pairs = detect_redundancy(documents)
    topic_groups = group_by_topic(query, documents)
    conflicts = detect_conflicts(documents, topic_groups)

    return {
        "redundant_pairs": redundant_pairs,
        "topic_groups": topic_groups,
        "conflicts": conflicts,
    }
