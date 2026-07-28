from sqlalchemy import Column, Integer, Text, DateTime, Enum
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import declarative_base
from sqlalchemy.sql import func
from pgvector.sqlalchemy import Vector
import uuid
import enum

Base = declarative_base()

class ChunkType(str, enum.Enum):
    text = "text"
    table = "table"
    image_caption = "image_caption"

class RetrievalMethod(str, enum.Enum):
    vector = "vector"
    bm25 = "bm25"
    hybrid = "hybrid"

class DocumentChunk(Base):
    __tablename__ = 'document_chunks'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), nullable=False)
    content = Column(Text, nullable=False)
    chunk_type = Column(Enum(ChunkType), nullable=False)
    page_number = Column(Integer, nullable=False)
    embedding = Column(Vector(768))
    metadata_ = Column("metadata", JSONB) # using metadata_ because metadata is a reserved property of Base
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ExtractedTable(Base):
    __tablename__ = 'extracted_tables'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), nullable=False)
    page_number = Column(Integer, nullable=False)
    table_data = Column(JSONB)
    table_summary = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ExtractedImage(Base):
    __tablename__ = 'extracted_images'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id = Column(UUID(as_uuid=True), nullable=False)
    page_number = Column(Integer, nullable=False)
    image_description = Column(Text)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class Document(Base):
    __tablename__ = 'documents'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    filename = Column(Text, nullable=False)
    status = Column(Text, default="ingesting") # "ingesting", "ready", "failed"
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class ChatSession(Base):
    __tablename__ = 'chat_sessions'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_name = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

class QueryLog(Base):
    __tablename__ = 'query_logs'

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    session_id = Column(UUID(as_uuid=True), nullable=True) # Soft link to chat_sessions
    question = Column(Text, nullable=False)
    retrieved_chunk_ids = Column(JSONB)
    answer = Column(Text)
    retrieval_method = Column(Enum(RetrievalMethod), nullable=False)
    tokens_used = Column(Integer, default=0) # Cost tracking
    confidence_score = Column(Integer, nullable=True) # Accuracy score from 0-100
    created_at = Column(DateTime(timezone=True), server_default=func.now())
