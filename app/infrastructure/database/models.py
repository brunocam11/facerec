"""SQLAlchemy models for face recognition service."""
import uuid
from datetime import datetime
from typing import Dict, Any

from sqlalchemy import JSON, DateTime, Float, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class Collection(Base):
    """Collection model for grouping faces."""
    
    __tablename__ = "collections"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )
    extra_data: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=True
    )
    
    # Relationships
    faces: Mapped[list["FaceRecord"]] = relationship(
        back_populates="collection",
        cascade="all, delete-orphan"
    )


class FaceRecord(Base):
    """Face record model for storing face metadata."""
    
    __tablename__ = "face_records"
    
    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )
    collection_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("collections.id", ondelete="CASCADE")
    )
    external_image_id: Mapped[str | None] = mapped_column(
        String(255),
        nullable=True
    )
    confidence: Mapped[float] = mapped_column(Float)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow
    )
    extra_data: Mapped[Dict[str, Any]] = mapped_column(
        JSON,
        nullable=True
    )
    
    # Relationships
    collection: Mapped[Collection] = relationship(
        back_populates="faces"
    ) 