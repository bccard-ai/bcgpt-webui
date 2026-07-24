"""Parent-Child Document Retrieval.

Small child chunks for precise retrieval, large parent chunks for LLM context.
When a child chunk matches, its parent chunk is returned instead.

Architecture:
- Child chunks: small segments embedded and stored in the main Qdrant collection
- Parent chunks: large segments stored in a separate docstore collection
- During retrieval, matching child chunks are resolved to their parent chunks
"""

import logging
import uuid

from langchain_text_splitters import RecursiveCharacterTextSplitter

from bcgpt.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MAIN"])

# Parent chunk: large context (e.g., 2000 chars)
PARENT_CHUNK_SIZE = 2000
PARENT_CHUNK_OVERLAP = 200

# Child chunk: small for precise retrieval (e.g., 200 chars)
CHILD_CHUNK_SIZE = 200
CHILD_CHUNK_OVERLAP = 20

# Docstore collection suffix
DOCSTORE_SUFFIX = "_parent_docstore"


def create_parent_child_chunks(
    documents: list,
    parent_chunk_size: int = PARENT_CHUNK_SIZE,
    parent_chunk_overlap: int = PARENT_CHUNK_OVERLAP,
    child_chunk_size: int = CHILD_CHUNK_SIZE,
    child_chunk_overlap: int = CHILD_CHUNK_OVERLAP,
) -> tuple[list[dict], list[dict]]:
    """Split documents into parent and child chunks with linkage.

    Args:
        documents: LangChain Document objects (typically from a first-pass split)

    Returns:
        (parent_chunks, child_chunks) where each is a list of dicts:
        {
            "id": str,
            "text": str,
            "metadata": dict,
            "parent_id": str or None,  # None for parent chunks
            "chunk_type": "parent" or "child",
        }
    """
    parents = []
    children = []

    parent_splitter = RecursiveCharacterTextSplitter(
        chunk_size=parent_chunk_size,
        chunk_overlap=parent_chunk_overlap,
        add_start_index=True,
    )
    child_splitter = RecursiveCharacterTextSplitter(
        chunk_size=child_chunk_size,
        chunk_overlap=child_chunk_overlap,
        add_start_index=True,
    )

    for doc in documents:
        parent_docs = parent_splitter.split_documents([doc])

        for p_doc in parent_docs:
            # Unique id per parent CHUNK, not per document. A large document
            # splits into multiple parent chunks; each must be independently
            # resolvable in the docstore, or they collide on one id and all but
            # the last-written are silently lost on retrieval.
            parent_id = str(uuid.uuid4())
            parents.append(
                {
                    "id": parent_id,
                    "text": p_doc.page_content,
                    "metadata": {
                        **p_doc.metadata,
                        "chunk_type": "parent",
                        "parent_id": parent_id,
                    },
                    "parent_id": None,
                    "chunk_type": "parent",
                }
            )

            child_docs = child_splitter.split_documents([p_doc])
            for c_doc in child_docs:
                child_id = str(uuid.uuid4())
                children.append(
                    {
                        "id": child_id,
                        "text": c_doc.page_content,
                        "metadata": {
                            **c_doc.metadata,
                            "chunk_type": "child",
                            "parent_id": parent_id,
                        },
                        "parent_id": parent_id,
                        "chunk_type": "child",
                    }
                )

    log.info(f"Parent-child split: {len(parents)} parents, {len(children)} children")
    return parents, children


def resolve_to_parents(
    search_results: list[dict],
) -> tuple[list[dict], set[str]]:
    """Identify child chunk matches and collect their parent_ids for lookup.

    Args:
        search_results: List of search result dicts with "metadata" containing
                        "parent_id" and "chunk_type", plus "score".

    Returns:
        (child_results, parent_ids) where:
        - child_results: list of child result dicts that need parent resolution
        - parent_ids: set of parent_id strings to look up from docstore
    """
    parent_ids = set()
    child_results = []

    for result in search_results:
        metadata = result.get("metadata", {})
        chunk_type = metadata.get("chunk_type", "")
        parent_id = metadata.get("parent_id")

        if chunk_type == "child" and parent_id:
            parent_ids.add(parent_id)
            child_results.append(result)

    return child_results, parent_ids


def build_parent_score_map(
    child_results: list[dict],
) -> dict[str, float]:
    """Build mapping of parent_id -> best child score.

    When multiple children share the same parent, keep the highest score.

    Args:
        child_results: List of child search result dicts

    Returns:
        dict mapping parent_id -> best score
    """
    parent_scores: dict[str, float] = {}

    for result in child_results:
        metadata = result.get("metadata", {})
        parent_id = metadata.get("parent_id")
        score = result.get("score", 0.0)

        if parent_id:
            if parent_id not in parent_scores or score > parent_scores[parent_id]:
                parent_scores[parent_id] = score

    return parent_scores


def get_docstore_collection_name(collection_name: str) -> str:
    """Get the docstore collection name for a given main collection."""
    return f"{collection_name}{DOCSTORE_SUFFIX}"


def load_parents_from_docstore(
    collection_name: str,
    parent_ids: set[str],
) -> dict[str, dict]:
    """Load parent chunks from the docstore collection.

    Args:
        collection_name: The main collection name (docstore name is derived)
        parent_ids: Set of parent_id strings to load

    Returns:
        dict mapping parent_id -> {"text": str, "metadata": dict}
    """
    if not parent_ids:
        return {}

    from bcgpt.retrieval.vector.connector import VECTOR_DB_CLIENT

    docstore_name = get_docstore_collection_name(collection_name)

    if not VECTOR_DB_CLIENT.has_collection(collection_name=docstore_name):
        log.warning(f"Parent docstore collection '{docstore_name}' not found")
        return {}

    parents = {}
    try:
        for parent_id in parent_ids:
            result = VECTOR_DB_CLIENT.query(
                collection_name=docstore_name,
                filter={"parent_id": parent_id},
            )
            if result and result.ids and result.ids[0]:
                for idx, pid in enumerate(result.ids[0]):
                    text = result.documents[0][idx] if result.documents else ""
                    meta = result.metadatas[0][idx] if result.metadatas else {}
                    actual_parent_id = meta.get("parent_id", str(pid))
                    parents[actual_parent_id] = {
                        "text": text,
                        "metadata": meta,
                    }
    except Exception as e:
        log.exception(f"Error loading parents from docstore: {e}")

    return parents


def replace_children_with_parents(
    distances: list[float],
    documents: list[str],
    metadatas: list[dict],
    collection_name: str,
) -> tuple[list[float], list[str], list[dict]]:
    """Replace child chunk matches with their parent chunks.

    Non-child results pass through unchanged.

    Args:
        distances: Search result distances/scores
        documents: Search result document texts
        metadatas: Search result metadatas
        collection_name: Collection name for docstore lookup

    Returns:
        (resolved_distances, resolved_documents, resolved_metadatas)
    """
    results = []
    for i in range(len(distances)):
        results.append(
            {
                "score": distances[i],
                "text": documents[i],
                "metadata": metadatas[i],
            }
        )

    child_results, parent_ids = resolve_to_parents(results)

    if not child_results or not parent_ids:
        return distances, documents, metadatas

    parent_store = load_parents_from_docstore(collection_name, parent_ids)
    parent_scores = build_parent_score_map(child_results)

    resolved_distances = []
    resolved_documents = []
    resolved_metadatas = []
    seen_parent_ids = set()

    for result in results:
        metadata = result.get("metadata", {})
        chunk_type = metadata.get("chunk_type", "")
        if chunk_type != "child":
            resolved_distances.append(result["score"])
            resolved_documents.append(result["text"])
            resolved_metadatas.append(metadata)

    for parent_id, score in sorted(
        parent_scores.items(), key=lambda x: x[1], reverse=True
    ):
        if parent_id in seen_parent_ids:
            continue
        seen_parent_ids.add(parent_id)

        if parent_id in parent_store:
            parent = parent_store[parent_id]
            resolved_distances.append(score)
            resolved_documents.append(parent["text"])
            resolved_metadatas.append(parent["metadata"])
        else:
            log.warning(
                f"Parent {parent_id} not found in docstore, "
                f"falling back to best child"
            )
            for cr in child_results:
                if cr["metadata"].get("parent_id") == parent_id:
                    resolved_distances.append(cr["score"])
                    resolved_documents.append(cr["text"])
                    resolved_metadatas.append(cr["metadata"])
                    break

    combined = list(zip(resolved_distances, resolved_documents, resolved_metadatas))
    combined.sort(key=lambda x: x[0], reverse=True)

    if combined:
        d, doc, m = zip(*combined)
        return list(d), list(doc), list(m)
    return [], [], []
