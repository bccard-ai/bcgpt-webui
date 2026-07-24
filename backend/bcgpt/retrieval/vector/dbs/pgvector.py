"""pgvector database adapter.

Stores document embeddings in a single ``document_chunk`` table using
the PostgreSQL ``pgvector`` extension.  Vectors are padded or validated
against ``PGVECTOR_INITIALIZE_MAX_VECTOR_LENGTH`` at write time to keep
the fixed-dimension column consistent.

If ``PGVECTOR_DB_URL`` is not set the adapter reuses the application's
default SQLAlchemy session.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from sqlalchemy import Column, Integer, MetaData, Table, Text, cast, column, create_engine, select, text, values
from sqlalchemy.dialects.postgresql import JSONB, array
from sqlalchemy.exc import NoSuchTableError
from sqlalchemy.ext.mutable import MutableDict
from sqlalchemy.orm import declarative_base, scoped_session, sessionmaker
from sqlalchemy.pool import NullPool
from sqlalchemy.sql import true

from pgvector.sqlalchemy import Vector

from bcgpt.config import PGVECTOR_DB_URL, PGVECTOR_INITIALIZE_MAX_VECTOR_LENGTH
from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.retrieval.vector import VectorItem, SearchResult, GetResult

VECTOR_LENGTH: int = PGVECTOR_INITIALIZE_MAX_VECTOR_LENGTH
Base = declarative_base()

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["RAG"])


class DocumentChunk(Base):
    """SQLAlchemy ORM model for the ``document_chunk`` table."""

    __tablename__ = "document_chunk"

    id = Column(Text, primary_key=True)
    vector = Column(Vector(dim=VECTOR_LENGTH), nullable=True)
    collection_name = Column(Text, nullable=False)
    text = Column(Text, nullable=True)
    vmetadata = Column(MutableDict.as_mutable(JSONB), nullable=True)


class PgvectorClient:
    """PostgreSQL + pgvector backed vector store."""

    def __init__(self) -> None:
        if not PGVECTOR_DB_URL:
            from bcgpt.internal import Session

            self.session = Session
        else:
            engine = create_engine(PGVECTOR_DB_URL, pool_pre_ping=True, poolclass=NullPool)
            session_factory = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
            self.session = scoped_session(session_factory)

        try:
            self.session.execute(text("CREATE EXTENSION IF NOT EXISTS vector;"))
            self._check_vector_length()
            connection = self.session.connection()
            Base.metadata.create_all(bind=connection)
            self.session.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_document_chunk_vector "
                    "ON document_chunk USING ivfflat (vector vector_cosine_ops) WITH (lists = 100);"
                )
            )
            self.session.execute(
                text(
                    "CREATE INDEX IF NOT EXISTS idx_document_chunk_collection_name "
                    "ON document_chunk (collection_name);"
                )
            )
            self.session.commit()
            log.info("pgvector initialization complete.")
        except Exception:
            self.session.rollback()
            log.exception("Error during pgvector initialization")
            raise

    # ------------------------------------------------------------------
    # Vector length helpers
    # ------------------------------------------------------------------

    def _check_vector_length(self) -> None:
        """Verify that the configured vector length matches the existing schema."""
        metadata = MetaData()
        try:
            table = Table("document_chunk", metadata, autoload_with=self.session.bind)
        except NoSuchTableError:
            return

        if "vector" not in table.columns:
            raise Exception("The 'vector' column does not exist in 'document_chunk'.")

        vector_type = table.columns["vector"].type
        if not isinstance(vector_type, Vector):
            raise Exception("The 'vector' column exists but is not of type 'Vector'.")

        db_vector_length = vector_type.dim
        if db_vector_length != VECTOR_LENGTH:
            raise Exception(
                f"VECTOR_LENGTH {VECTOR_LENGTH} does not match existing vector column dimension {db_vector_length}. "
                "Cannot change vector size after initialization without migrating the data."
            )

    @staticmethod
    def _adjust_vector_length(vector: List[float]) -> List[float]:
        """Pad *vector* with zeros to match ``VECTOR_LENGTH``."""
        current = len(vector)
        if current < VECTOR_LENGTH:
            return vector + [0.0] * (VECTOR_LENGTH - current)
        if current > VECTOR_LENGTH:
            raise Exception(f"Vector length {current} exceeds maximum {VECTOR_LENGTH}.")
        return vector

    # ------------------------------------------------------------------
    # Search / query
    # ------------------------------------------------------------------

    def search(
        self,
        collection_name: str,
        vectors: List[List[float]],
        limit: Optional[int] = None,
    ) -> Optional[SearchResult]:
        """Perform cosine similarity search using LATERAL joins."""
        try:
            if not vectors:
                return None

            vectors = [self._adjust_vector_length(v) for v in vectors]
            num_queries = len(vectors)

            qid_col = column("qid", Integer)
            q_vector_col = column("q_vector", Vector(VECTOR_LENGTH))
            query_vectors = (
                values(qid_col, q_vector_col)
                .data(
                    [(idx, cast(array(v), Vector(VECTOR_LENGTH))) for idx, v in enumerate(vectors)]
                )
                .alias("query_vectors")
            )

            subq = (
                select(
                    DocumentChunk.id,
                    DocumentChunk.text,
                    DocumentChunk.vmetadata,
                    (DocumentChunk.vector.cosine_distance(query_vectors.c.q_vector)).label("distance"),
                )
                .where(DocumentChunk.collection_name == collection_name)
                .order_by(DocumentChunk.vector.cosine_distance(query_vectors.c.q_vector))
            )
            if limit is not None:
                subq = subq.limit(limit)
            subq = subq.lateral("result")

            stmt = (
                select(query_vectors.c.qid, subq.c.id, subq.c.text, subq.c.vmetadata, subq.c.distance)
                .select_from(query_vectors)
                .join(subq, true())
                .order_by(query_vectors.c.qid, subq.c.distance)
            )

            rows = self.session.execute(stmt).all()

            ids: list[list[str]] = [[] for _ in range(num_queries)]
            distances: list[list[float]] = [[] for _ in range(num_queries)]
            documents: list[list[str]] = [[] for _ in range(num_queries)]
            metadatas: list[list[Any]] = [[] for _ in range(num_queries)]

            for row in rows:
                qid = int(row.qid)
                ids[qid].append(row.id)
                # Normalize pgvector distance from [2, 0] to [0, 1] score.
                # See: https://github.com/pgvector/pgvector#querying
                distances[qid].append((2.0 - row.distance) / 2.0)
                documents[qid].append(row.text)
                metadatas[qid].append(row.vmetadata)

            return SearchResult(ids=ids, distances=distances, documents=documents, metadatas=metadatas)
        except Exception:
            log.exception("Error during search")
            return None

    def query(
        self, collection_name: str, filter: Dict[str, Any], limit: Optional[int] = None
    ) -> Optional[GetResult]:
        """Retrieve documents matching metadata *filter* values."""
        try:
            q = self.session.query(DocumentChunk).filter(DocumentChunk.collection_name == collection_name)
            for key, value in filter.items():
                q = q.filter(DocumentChunk.vmetadata[key].astext == str(value))
            if limit is not None:
                q = q.limit(limit)

            results = q.all()
            if not results:
                return None

            return GetResult(
                ids=[[r.id for r in results]],
                documents=[[r.text for r in results]],
                metadatas=[[r.vmetadata for r in results]],
            )
        except Exception:
            log.exception("Error during query")
            return None

    def get(self, collection_name: str, limit: Optional[int] = None) -> Optional[GetResult]:
        """Return all documents in *collection_name*."""
        try:
            q = self.session.query(DocumentChunk).filter(DocumentChunk.collection_name == collection_name)
            if limit is not None:
                q = q.limit(limit)
            results = q.all()
            if not results:
                return None
            return GetResult(
                ids=[[r.id for r in results]],
                documents=[[r.text for r in results]],
                metadatas=[[r.vmetadata for r in results]],
            )
        except Exception:
            log.exception("Error during get")
            return None

    # ------------------------------------------------------------------
    # Mutations
    # ------------------------------------------------------------------

    def insert(self, collection_name: str, items: List[VectorItem]) -> None:
        """Insert new document chunks."""
        try:
            chunks = [
                DocumentChunk(
                    id=item["id"],
                    vector=self._adjust_vector_length(item["vector"]),
                    collection_name=collection_name,
                    text=item["text"],
                    vmetadata=item["metadata"],
                )
                for item in items
            ]
            self.session.bulk_save_objects(chunks)
            self.session.commit()
            log.info("Inserted %d items into collection '%s'.", len(chunks), collection_name)
        except Exception:
            self.session.rollback()
            log.exception("Error during insert")
            raise

    def upsert(self, collection_name: str, items: List[VectorItem]) -> None:
        """Insert or update document chunks."""
        try:
            for item in items:
                vector = self._adjust_vector_length(item["vector"])
                existing = self.session.query(DocumentChunk).filter(DocumentChunk.id == item["id"]).first()
                if existing:
                    existing.vector = vector
                    existing.text = item["text"]
                    existing.vmetadata = item["metadata"]
                    existing.collection_name = collection_name
                else:
                    self.session.add(
                        DocumentChunk(
                            id=item["id"],
                            vector=vector,
                            collection_name=collection_name,
                            text=item["text"],
                            vmetadata=item["metadata"],
                        )
                    )
            self.session.commit()
            log.info("Upserted %d items into collection '%s'.", len(items), collection_name)
        except Exception:
            self.session.rollback()
            log.exception("Error during upsert")
            raise

    def delete(
        self,
        collection_name: str,
        ids: Optional[List[str]] = None,
        filter: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Delete documents by *ids* or metadata *filter*."""
        try:
            q = self.session.query(DocumentChunk).filter(DocumentChunk.collection_name == collection_name)
            if ids:
                q = q.filter(DocumentChunk.id.in_(ids))
            if filter:
                for key, value in filter.items():
                    q = q.filter(DocumentChunk.vmetadata[key].astext == str(value))
            deleted = q.delete(synchronize_session=False)
            self.session.commit()
            log.info("Deleted %d items from collection '%s'.", deleted, collection_name)
        except Exception:
            self.session.rollback()
            log.exception("Error during delete")
            raise

    # ------------------------------------------------------------------
    # Collection helpers
    # ------------------------------------------------------------------

    def has_collection(self, collection_name: str) -> bool:
        """Return ``True`` if *collection_name* has at least one document."""
        try:
            return (
                self.session.query(DocumentChunk)
                .filter(DocumentChunk.collection_name == collection_name)
                .first()
                is not None
            )
        except Exception:
            log.exception("Error checking collection existence")
            return False

    def delete_collection(self, collection_name: str) -> None:
        """Delete all documents in *collection_name*."""
        self.delete(collection_name)
        log.info("Collection '%s' deleted.", collection_name)

    def list_collections(self) -> list:
        """Return distinct collection names with document counts."""
        from bcgpt.retrieval.vector.main import CollectionInfo

        result: list = []
        try:
            rows = self.session.execute(
                text("SELECT collection_name, COUNT(*) as cnt FROM document_chunk GROUP BY collection_name")
            ).all()
            for row in rows:
                result.append(CollectionInfo(name=row[0], document_count=row[1]))
        except Exception:
            log.exception("Error listing collections")
        return result

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def reset(self) -> None:
        """Delete all rows from ``document_chunk``."""
        try:
            deleted = self.session.query(DocumentChunk).delete()
            self.session.commit()
            log.info("Reset complete. Deleted %d items.", deleted)
        except Exception:
            self.session.rollback()
            log.exception("Error during reset")
            raise

    def close(self) -> None:
        """No-op for session cleanup compatibility."""
        pass
