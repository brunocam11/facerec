"""SQLAlchemy models for face recognition service."""
import uuid
from datetime import datetime
from typing import Dict, Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String, Index
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Collection(Base):
    """Collection/Album model for grouping faces."""
    
    __tablename__ = "collections"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    external_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        comment="External system collection identifier"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )
    extra_data: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional metadata from external system"
    )
    
    # Relationships
    faces: Mapped[list["Face"]] = relationship(
        back_populates="collection",
        cascade="all, delete-orphan"
    )


class Face(Base):
    """Face record for linking external images with their vector embeddings."""
    
    __tablename__ = "faces"
    __table_args__ = (
        Index('idx_faces_external_refs', 'external_image_id', 'collection_id'),
    )
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collections.id", ondelete="CASCADE")
    )
    external_image_id: Mapped[str] = mapped_column(
        String(255),
        nullable=False,
        comment="External system image identifier (e.g. S3 key)"
    )
    vector_id: Mapped[str] = mapped_column(
        String(255),
        unique=True,
        nullable=False,
        comment="ID of the face vector in the vector database"
    )
    confidence: Mapped[float] = mapped_column(
        Float,
        comment="Face detection confidence score"
    )
    bbox_left: Mapped[float] = mapped_column(Float)
    bbox_top: Mapped[float] = mapped_column(Float)
    bbox_width: Mapped[float] = mapped_column(Float)
    bbox_height: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )
    extra_data: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=True,
        comment="Additional metadata from external system"
    )
    
    # Relationships
    collection: Mapped[Collection] = relationship(
        back_populates="faces"
    ) 