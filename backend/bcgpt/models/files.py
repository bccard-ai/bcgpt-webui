"""File model and table operations.

Manages file metadata stored in the database, including content hashes,
arbitrary JSON data/metadata blobs, and access-control rules.
"""

import logging
import time
from typing import Optional

from pydantic import BaseModel, ConfigDict
from sqlalchemy import BigInteger, Column, JSON, String, Text

from bcgpt.env import SRC_LOG_LEVELS
from bcgpt.internal import Base, JSONField, get_db

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS["MODELS"])


# ---------------------------------------------------------------------------
# SQLAlchemy ORM model
# ---------------------------------------------------------------------------

class File(Base):
    """Persistent representation of a file metadata row."""

    __tablename__ = "file"

    id = Column(String, primary_key=True)
    user_id = Column(String)
    hash = Column(Text, nullable=True)

    filename = Column(Text)
    path = Column(Text, nullable=True)

    data = Column(JSON, nullable=True)
    meta = Column(JSON, nullable=True)

    access_control = Column(JSON, nullable=True)

    created_at = Column(BigInteger)
    updated_at = Column(BigInteger)


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class FileModel(BaseModel):
    """Full file representation returned to callers."""

    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    hash: Optional[str] = None

    filename: str
    path: Optional[str] = None

    data: Optional[dict] = None
    meta: Optional[dict] = None

    access_control: Optional[dict] = None

    created_at: Optional[int]  # epoch seconds
    updated_at: Optional[int]  # epoch seconds


class FileMeta(BaseModel):
    """Standard metadata fields for a file entry."""

    name: Optional[str] = None
    content_type: Optional[str] = None
    size: Optional[int] = None

    model_config = ConfigDict(extra="allow")


class FileModelResponse(BaseModel):
    """File payload returned in API responses (excludes path)."""

    id: str
    user_id: str
    hash: Optional[str] = None

    filename: str
    data: Optional[dict] = None
    meta: FileMeta

    created_at: int  # epoch seconds
    updated_at: int  # epoch seconds

    model_config = ConfigDict(extra="allow")


class FileMetadataResponse(BaseModel):
    """Minimal metadata-only view of a file."""

    id: str
    meta: dict
    created_at: int  # epoch seconds
    updated_at: int  # epoch seconds


class FileForm(BaseModel):
    """Schema for creating a new file entry."""

    id: str
    hash: Optional[str] = None
    filename: str
    path: str
    data: dict = {}
    meta: dict = {}
    access_control: Optional[dict] = None


# ---------------------------------------------------------------------------
# Table-level CRUD
# ---------------------------------------------------------------------------

class FilesTable:
    """Collection of database helpers for the ``file`` table."""

    def insert_new_file(
        self, user_id: str, form_data: FileForm
    ) -> Optional[FileModel]:
        """Create a new file metadata entry and return its model."""
        with get_db() as db:
            file = FileModel(
                **{
                    **form_data.model_dump(),
                    "user_id": user_id,
                    "created_at": int(time.time()),
                    "updated_at": int(time.time()),
                }
            )

            try:
                result = File(**file.model_dump())
                db.add(result)
                db.commit()
                db.refresh(result)
                if result:
                    return FileModel.model_validate(result)
                else:
                    return None
            except Exception as e:
                log.exception("Error inserting a new file: %s", e)
                return None

    def get_file_by_id(self, id: str) -> Optional[FileModel]:
        """Fetch a single file by its primary key."""
        with get_db() as db:
            try:
                file = db.get(File, id)
                return FileModel.model_validate(file)
            except Exception:
                return None

    def get_file_metadata_by_id(
        self, id: str
    ) -> Optional[FileMetadataResponse]:
        """Fetch only the metadata portion of a file entry."""
        with get_db() as db:
            try:
                file = db.get(File, id)
                return FileMetadataResponse(
                    id=file.id,
                    meta=file.meta,
                    created_at=file.created_at,
                    updated_at=file.updated_at,
                )
            except Exception:
                return None

    def get_files(self) -> list[FileModel]:
        """Return every file entry in the database."""
        with get_db() as db:
            return [
                FileModel.model_validate(file) for file in db.query(File).all()
            ]

    def get_files_by_ids(self, ids: list[str]) -> list[FileModel]:
        """Return files matching the given IDs, most recently updated first."""
        with get_db() as db:
            return [
                FileModel.model_validate(file)
                for file in db.query(File)
                .filter(File.id.in_(ids))
                .order_by(File.updated_at.desc())
                .all()
            ]

    def get_file_metadatas_by_ids(
        self, ids: list[str]
    ) -> list[FileMetadataResponse]:
        """Return metadata-only views for the given file IDs."""
        with get_db() as db:
            return [
                FileMetadataResponse(
                    id=file.id,
                    meta=file.meta,
                    created_at=file.created_at,
                    updated_at=file.updated_at,
                )
                for file in db.query(File)
                .filter(File.id.in_(ids))
                .order_by(File.updated_at.desc())
                .all()
            ]

    def get_files_by_user_id(self, user_id: str) -> list[FileModel]:
        """Return all file entries owned by a specific user."""
        with get_db() as db:
            return [
                FileModel.model_validate(file)
                for file in db.query(File).filter_by(user_id=user_id).all()
            ]

    def update_file_hash_by_id(
        self, id: str, hash: str
    ) -> Optional[FileModel]:
        """Update the content hash of a file entry."""
        with get_db() as db:
            try:
                file = db.query(File).filter_by(id=id).first()
                file.hash = hash
                db.commit()

                return FileModel.model_validate(file)
            except Exception:
                return None

    def update_file_data_by_id(
        self, id: str, data: dict
    ) -> Optional[FileModel]:
        """Merge new data into the existing JSON data blob of a file."""
        with get_db() as db:
            try:
                file = db.query(File).filter_by(id=id).first()
                file.data = {**(file.data if file.data else {}), **data}
                db.commit()
                return FileModel.model_validate(file)
            except Exception:
                return None

    def update_file_metadata_by_id(
        self, id: str, meta: dict
    ) -> Optional[FileModel]:
        """Merge new metadata into the existing JSON meta blob of a file."""
        with get_db() as db:
            try:
                file = db.query(File).filter_by(id=id).first()
                file.meta = {**(file.meta if file.meta else {}), **meta}
                db.commit()
                return FileModel.model_validate(file)
            except Exception:
                return None

    def delete_file_by_id(self, id: str) -> bool:
        """Delete a single file entry by its primary key."""
        with get_db() as db:
            try:
                db.query(File).filter_by(id=id).delete()
                db.commit()

                return True
            except Exception:
                return False

    def delete_all_files(self) -> bool:
        """Delete every file entry in the database."""
        with get_db() as db:
            try:
                db.query(File).delete()
                db.commit()

                return True
            except Exception:
                return False


Files = FilesTable()
