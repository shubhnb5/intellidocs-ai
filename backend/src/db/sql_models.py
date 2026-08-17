"""SQLAlchemy ORM models.

SQLite for local dev/demo; swapping to Postgres in production is a
DATABASE_URL change plus adding a driver dependency — the models don't
change, since SQLAlchemy abstracts the dialect.
"""

import json
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class UserRecord(Base):
    """One row per registered account. Password is never stored in
    plaintext or reversibly — only a bcrypt hash (see services/security.py).
    """

    __tablename__ = "users"

    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str] = mapped_column(String, nullable=False, unique=True, index=True)
    hashed_password: Mapped[str] = mapped_column(String, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class DocumentRecord(Base):
    """One row per uploaded document. This is the source of truth for
    document-level metadata; Qdrant stays a pure vector index (chunk text +
    embedding), with only a denormalized copy of `filename` in each chunk's
    payload so retrieval/citation don't need a join back here.

    `owner_id` (Phase 8) makes documents private per-account: uploads are
    stamped with the uploader's user_id, and list/get filter on it. The same
    id is duplicated onto each Qdrant chunk's payload (see documents.py) so
    RAG retrieval can filter to one user's chunks without a join back here.
    """

    __tablename__ = "documents"

    document_id: Mapped[str] = mapped_column(String, primary_key=True)
    owner_id: Mapped[str] = mapped_column(String, ForeignKey("users.user_id"), nullable=False)
    filename: Mapped[str] = mapped_column(String, nullable=False)
    uploaded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    chunk_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Stored as JSON text rather than normalized child tables — entities and
    # topics are always read as a whole alongside their document, never
    # queried or filtered on individually, so normalizing would only add
    # join overhead for no real benefit at this scale.
    entities_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")
    topics_json: Mapped[str] = mapped_column(Text, nullable=False, default="[]")

    @property
    def entities(self) -> list[dict]:
        return json.loads(self.entities_json)

    @property
    def topics(self) -> list[str]:
        return json.loads(self.topics_json)
