"""Document upload endpoint: parse -> chunk -> embed -> store in Qdrant,
plus (Phase 4) run the NLP pipeline and persist document metadata + computed
fields (entities, topics, summary) in the SQL database.

Qdrant stays a pure vector index (chunk text + embedding, keyed by
document_id). The SQL `documents` table is now the source of truth for
document-level metadata — `filename` is still duplicated onto each Qdrant
chunk's payload so retrieval/citation (Phase 3) doesn't need a join back to
SQL at answer time. Known gap, worth naming: the Qdrant upsert and the SQL
write aren't in one transaction, so a crash between them could leave chunks
indexed with no matching document row. Fine for a portfolio-scope project;
a production system would need an outbox pattern or a reconciliation job.

Phase 8: every route requires a logged-in user. Documents are private per
account — `owner_id` on both the SQL row and each Qdrant chunk's payload —
except GET /{document_id}, which also accepts the MCP server's internal
service key (see core/auth_dependency.py) since the document_metadata tool
looks up a document by ID without carrying the original asker's identity.
"""

import json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, UploadFile
from loguru import logger
from pydantic import BaseModel
from qdrant_client.models import PointStruct
from sqlalchemy.orm import Session

from src.core.auth_dependency import CurrentUser, get_current_user, get_current_user_or_internal
from src.core.config import get_settings
from src.core.exceptions import DocumentNotFoundError, FileTooLargeError
from src.core.rate_limit import RateLimiter
from src.db.database import get_db_session
from src.db.qdrant_client import get_qdrant_client
from src.db.redis_client import get_redis_client
from src.db.sql_models import DocumentRecord
from src.services.chunking import chunk_text
from src.services.document_cache import (
    DocumentSummary,
    get_cached_document_list,
    invalidate_document_list_cache,
    set_cached_document_list,
)
from src.services.document_parser import extract_text
from src.services.embeddings import get_embedding_service
from src.services.nlp import Entity, analyze_document

router = APIRouter()

_settings = get_settings()
_upload_rate_limiter = RateLimiter(
    limit=_settings.rate_limit_requests,
    window_seconds=_settings.rate_limit_window_seconds,
    scope="documents_upload",
)


# --- request/response schemas -----------------------------------------


class DocumentUploadResponse(BaseModel):
    document_id: str
    filename: str
    chunk_count: int
    uploaded_at: datetime
    entities: list[Entity]
    topics: list[str]
    summary: str


class DocumentDetailResponse(BaseModel):
    document_id: str
    filename: str
    chunk_count: int
    uploaded_at: datetime
    summary: str | None
    entities: list[Entity]
    topics: list[str]


class DocumentListResponse(BaseModel):
    documents: list[DocumentSummary]


# --- routes --------------------------------------------------------------


@router.post(
    "/api/documents/upload",
    response_model=DocumentUploadResponse,
    tags=["Documents"],
    summary="Upload a PDF or DOCX document",
    description=(
        "Extracts text, splits it into overlapping chunks, embeds each chunk "
        "into Qdrant, and runs the NLP pipeline (entities, topics, summary)."
    ),
    status_code=201,
    dependencies=[Depends(_upload_rate_limiter)],
)
async def upload_document(
    file: UploadFile,
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> DocumentUploadResponse:
    settings = get_settings()

    # Read the whole file into memory before validating size. Fine at a 20MB
    # cap; a much larger limit would need a streaming size check instead.
    file_bytes = await file.read()
    max_bytes = settings.max_upload_size_mb * 1024 * 1024
    if len(file_bytes) > max_bytes:
        raise FileTooLargeError(
            f"File exceeds the {settings.max_upload_size_mb}MB upload limit."
        )

    text = extract_text(file_bytes, file.content_type or "")
    chunks = chunk_text(text)
    nlp_result = analyze_document(text)

    document_id = str(uuid.uuid4())
    uploaded_at = datetime.now(UTC)
    filename = file.filename or "untitled"

    if chunks:
        vectors = get_embedding_service().embed(chunks)
        points = [
            PointStruct(
                id=str(uuid.uuid4()),
                vector=vector,
                payload={
                    "document_id": document_id,
                    "owner_id": current_user.user_id,
                    "filename": filename,
                    "chunk_index": index,
                    "text": chunk,
                    "uploaded_at": uploaded_at.isoformat(),
                },
            )
            for index, (chunk, vector) in enumerate(zip(chunks, vectors, strict=True))
        ]
        get_qdrant_client().upsert(
            collection_name=settings.qdrant_collection, points=points
        )

    db.add(
        DocumentRecord(
            document_id=document_id,
            owner_id=current_user.user_id,
            filename=filename,
            uploaded_at=uploaded_at,
            chunk_count=len(chunks),
            summary=nlp_result.summary,
            entities_json=json.dumps([e.model_dump() for e in nlp_result.entities]),
            topics_json=json.dumps(nlp_result.topics),
        )
    )
    db.commit()

    await invalidate_document_list_cache(get_redis_client(), owner_id=current_user.user_id)

    logger.info(
        "ingested document {} ({} chunks, {} entities) from {} for user {}",
        document_id,
        len(chunks),
        len(nlp_result.entities),
        filename,
        current_user.user_id,
    )

    return DocumentUploadResponse(
        document_id=document_id,
        filename=filename,
        chunk_count=len(chunks),
        uploaded_at=uploaded_at,
        entities=nlp_result.entities,
        topics=nlp_result.topics,
        summary=nlp_result.summary,
    )


@router.get(
    "/api/documents",
    response_model=DocumentListResponse,
    tags=["Documents"],
    summary="List the current user's uploaded documents",
)
async def list_documents(
    current_user: CurrentUser = Depends(get_current_user),
    db: Session = Depends(get_db_session),
) -> DocumentListResponse:
    settings = get_settings()
    redis_client = get_redis_client()

    cached = await get_cached_document_list(redis_client, owner_id=current_user.user_id)
    if cached is not None:
        return DocumentListResponse(documents=cached)

    records = (
        db.query(DocumentRecord)
        .filter(DocumentRecord.owner_id == current_user.user_id)
        .order_by(DocumentRecord.uploaded_at.desc())
        .all()
    )
    documents = [
        DocumentSummary(
            document_id=record.document_id,
            filename=record.filename,
            chunk_count=record.chunk_count,
            uploaded_at=record.uploaded_at,
            summary=record.summary,
        )
        for record in records
    ]

    await set_cached_document_list(
        redis_client,
        owner_id=current_user.user_id,
        documents=documents,
        ttl_seconds=settings.document_cache_ttl_seconds,
    )
    return DocumentListResponse(documents=documents)


@router.get(
    "/api/documents/{document_id}",
    response_model=DocumentDetailResponse,
    tags=["Documents"],
    summary="Get a document's full metadata, including entities and topics",
    description=(
        "Requires either the owning user's token, or the MCP server's "
        "internal service key (used by the document_metadata tool)."
    ),
)
async def get_document(
    document_id: str,
    current_user: CurrentUser | None = Depends(get_current_user_or_internal),
    db: Session = Depends(get_db_session),
) -> DocumentDetailResponse:
    record = db.get(DocumentRecord, document_id)
    # Same 404 whether the document doesn't exist or belongs to someone
    # else -- distinguishing the two would leak which document IDs exist.
    if record is None or (current_user is not None and record.owner_id != current_user.user_id):
        raise DocumentNotFoundError(f"No document with id '{document_id}'.")

    return DocumentDetailResponse(
        document_id=record.document_id,
        filename=record.filename,
        chunk_count=record.chunk_count,
        uploaded_at=record.uploaded_at,
        summary=record.summary,
        entities=[Entity(**entity) for entity in record.entities],
        topics=record.topics,
    )
