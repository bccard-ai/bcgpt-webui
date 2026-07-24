"""User memory CRUD endpoints backed by a vector database for semantic search."""

from __future__ import annotations

import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.models import Memories, MemoryModel
from bcgpt.retrieval import VECTOR_DB_CLIENT
from bcgpt.utils import get_verified_user

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

router = APIRouter()


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class AddMemoryForm(BaseModel):
    """Payload for creating a new memory entry."""

    content: str


class MemoryUpdateModel(BaseModel):
    """Payload for updating an existing memory's content."""

    content: Optional[str] = None


class QueryMemoryForm(BaseModel):
    """Payload for semantic memory search."""

    content: str
    k: Optional[int] = 1


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------


def _user_collection(user_id: str) -> str:
    """Return the vector-db collection name for *user_id*'s memories."""
    return f"user-memory-{user_id}"


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/ef")
async def get_embeddings(request: Request, user=Depends(get_verified_user)):
    """Quick health-check that runs the app-level embedding function."""
    return {"result": request.app.state.EMBEDDING_FUNCTION("hello world")}


@router.get("/", response_model=list[MemoryModel])
async def get_memories(user=Depends(get_verified_user)):
    """List all stored memories for the authenticated user."""
    return Memories.get_memories_by_user_id(user.id)


@router.post("/add", response_model=Optional[MemoryModel])
async def add_memory(
    request: Request,
    form_data: AddMemoryForm,
    user=Depends(get_verified_user),
):
    """Create a new memory, embed it, and upsert into the vector store."""
    memory = Memories.insert_new_memory(user.id, form_data.content)

    VECTOR_DB_CLIENT.upsert(
        collection_name=_user_collection(user.id),
        items=[
            {
                "id": memory.id,
                "text": memory.content,
                "vector": request.app.state.EMBEDDING_FUNCTION(
                    memory.content, user=user
                ),
                "metadata": {"created_at": memory.created_at},
            }
        ],
    )
    return memory


@router.post("/query")
async def query_memory(
    request: Request, form_data: QueryMemoryForm, user=Depends(get_verified_user)
):
    """Search the user's memories by semantic similarity."""
    results = VECTOR_DB_CLIENT.search(
        collection_name=_user_collection(user.id),
        vectors=[
            request.app.state.EMBEDDING_FUNCTION(form_data.content, user=user)
        ],
        limit=form_data.k,
    )
    return results


@router.post("/reset", response_model=bool)
async def reset_memory_from_vector_db(
    request: Request, user=Depends(get_verified_user)
):
    """Drop and rebuild the user's vector collection from relational storage."""
    collection = _user_collection(user.id)
    VECTOR_DB_CLIENT.delete_collection(collection)

    memories = Memories.get_memories_by_user_id(user.id)
    VECTOR_DB_CLIENT.upsert(
        collection_name=collection,
        items=[
            {
                "id": memory.id,
                "text": memory.content,
                "vector": request.app.state.EMBEDDING_FUNCTION(
                    memory.content, user=user
                ),
                "metadata": {
                    "created_at": memory.created_at,
                    "updated_at": memory.updated_at,
                },
            }
            for memory in memories
        ],
    )
    return True


@router.delete("/delete/user", response_model=bool)
async def delete_memory_by_user_id(user=Depends(get_verified_user)):
    """Delete **all** memories for the authenticated user."""
    result = Memories.delete_memories_by_user_id(user.id)
    if result:
        try:
            VECTOR_DB_CLIENT.delete_collection(_user_collection(user.id))
        except Exception as exc:
            log.error("%s", exc)
        return True
    return False


@router.post("/{memory_id}/update", response_model=Optional[MemoryModel])
async def update_memory_by_id(
    memory_id: str,
    request: Request,
    form_data: MemoryUpdateModel,
    user=Depends(get_verified_user),
):
    """Update the content of an existing memory (ownership verified)."""
    existing_memory = Memories.get_memory_by_id(memory_id)
    if existing_memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")

    if existing_memory.user_id != user.id:
        raise HTTPException(
            status_code=403,
            detail="You do not have permission to update this memory",
        )

    memory = Memories.update_memory_by_id(memory_id, form_data.content)
    if memory is None:
        raise HTTPException(status_code=404, detail="Memory not found")

    if form_data.content is not None:
        VECTOR_DB_CLIENT.upsert(
            collection_name=_user_collection(user.id),
            items=[
                {
                    "id": memory.id,
                    "text": memory.content,
                    "vector": request.app.state.EMBEDDING_FUNCTION(
                        memory.content, user=user
                    ),
                    "metadata": {
                        "created_at": memory.created_at,
                        "updated_at": memory.updated_at,
                    },
                }
            ],
        )

    return memory


@router.delete("/{memory_id}", response_model=bool)
async def delete_memory_by_id(memory_id: str, user=Depends(get_verified_user)):
    """Delete a single memory by ID (must belong to the user)."""
    result = Memories.delete_memory_by_id_and_user_id(memory_id, user.id)
    if result:
        VECTOR_DB_CLIENT.delete(
            collection_name=_user_collection(user.id), ids=[memory_id]
        )
        return True
    return False
