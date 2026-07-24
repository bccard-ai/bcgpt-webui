"""Knowledge-graph persistence (GraphRAG revival, open-moai adoption 3.1).

The GraphRAG knowledge graph was previously an in-memory NetworkX singleton that
was never populated and lost on restart. This stores its serialized form so it
survives restarts (DB-first). The serialized payload is ``KnowledgeGraph``'s
``serialize()`` dict (nodes + edges + entity_docs). PostgreSQL-compatible.
"""

import logging
import time
from typing import Optional

from sqlalchemy import BigInteger, Column, JSON, String

from bcgpt.internal import Base, get_db
from bcgpt.env import SRC_LOG_LEVELS

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])

DEFAULT_SCOPE = "global"


class KnowledgeGraphStore(Base):
    __tablename__ = "knowledge_graph"

    scope = Column(String, primary_key=True)
    data = Column(JSON, nullable=True)
    updated_at = Column(BigInteger, nullable=False)


class KnowledgeGraphStoreTable:
    def save(self, scope: str, data: dict) -> bool:
        try:
            now = int(time.time() * 1000)
            with get_db() as db:
                row = db.query(KnowledgeGraphStore).filter_by(scope=scope).first()
                if row:
                    row.data = data
                    row.updated_at = now
                else:
                    db.add(KnowledgeGraphStore(scope=scope, data=data, updated_at=now))
                db.commit()
            return True
        except Exception as e:
            log.exception("KnowledgeGraphStore.save failed: %s", e)
            return False

    def load(self, scope: str = DEFAULT_SCOPE) -> Optional[dict]:
        try:
            with get_db() as db:
                row = db.query(KnowledgeGraphStore).filter_by(scope=scope).first()
                return row.data if row and row.data else None
        except Exception as e:
            log.exception("KnowledgeGraphStore.load failed: %s", e)
            return None

    def clear(self, scope: str = DEFAULT_SCOPE) -> bool:
        try:
            with get_db() as db:
                db.query(KnowledgeGraphStore).filter_by(scope=scope).delete()
                db.commit()
            return True
        except Exception as e:
            log.exception("KnowledgeGraphStore.clear failed: %s", e)
            return False


KnowledgeGraphStores = KnowledgeGraphStoreTable()
