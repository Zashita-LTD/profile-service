"""PostgreSQL models for document storage."""

from datetime import datetime
from typing import Optional
from uuid import uuid4

from sqlalchemy import (
    Column,
    DateTime,
    Enum,
    ForeignKey,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.postgres import Base


class PersonDocument(Base):
    """Document associated with a person (resume, profile, etc.)."""
    
    __tablename__ = "person_documents"
    
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    person_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    
    # Document info
    doc_type: Mapped[str] = mapped_column(
        Enum("resume", "linkedin", "email", "vcard", "other", name="doc_type"),
        nullable=False,
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_url: Mapped[Optional[str]] = mapped_column(String(500))
    
    # Content
    raw_content: Mapped[str] = mapped_column(Text, nullable=False)
    parsed_data: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )
    
    # Relationships
    facts = relationship("PersonFact", back_populates="document", cascade="all, delete")


class PersonFact(Base):
    """Extracted fact about a person."""
    
    __tablename__ = "person_facts"
    
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    person_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    document_id: Mapped[Optional[UUID]] = mapped_column(
        UUID(as_uuid=True), ForeignKey("person_documents.id"), nullable=True
    )
    
    # Fact info
    fact_type: Mapped[str] = mapped_column(
        Enum(
            "career", "education", "skill", "interest", "relationship",
            "contact", "trait", "achievement", "preference", "other",
            name="fact_type"
        ),
        nullable=False,
    )
    category: Mapped[str] = mapped_column(String(100), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Metadata
    confidence: Mapped[float] = mapped_column(default=1.0)
    source: Mapped[str] = mapped_column(String(100), default="manual")
    metadata: Mapped[dict] = mapped_column(JSONB, default=dict)
    
    # Date context
    date_from: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    date_to: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    
    # Relationships
    document = relationship("PersonDocument", back_populates="facts")


class Biography(Base):
    """Generated biography text."""
    
    __tablename__ = "biographies"
    
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    person_id: Mapped[str] = mapped_column(String(36), index=True, nullable=False)
    
    # Content
    style: Mapped[str] = mapped_column(
        Enum("professional", "casual", "detailed", "executive", name="bio_style"),
        default="professional",
    )
    language: Mapped[str] = mapped_column(String(10), default="ru")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Generation info
    model_used: Mapped[str] = mapped_column(String(50), nullable=False)
    facts_count: Mapped[int] = mapped_column(default=0)
    tokens_used: Mapped[int] = mapped_column(default=0)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class EventLog(Base):
    """Log of incoming events from external systems."""
    
    __tablename__ = "event_logs"
    
    id: Mapped[UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid4
    )
    
    # Event info
    event_type: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    source: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    
    # Content
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    
    # Processing
    status: Mapped[str] = mapped_column(
        Enum("pending", "processing", "completed", "failed", name="event_status"),
        default="pending",
    )
    error_message: Mapped[Optional[str]] = mapped_column(Text)
    person_id: Mapped[Optional[str]] = mapped_column(String(36), index=True)
    
    # Timestamps
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    processed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
