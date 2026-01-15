"""Event node model."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventType:
    """Event type constants."""

    MEETING = "meeting"
    DEAL = "deal"
    CONFERENCE = "conference"
    CALL = "call"
    EMAIL = "email"
    OTHER = "other"


class EventBase(BaseModel):
    """Base event attributes."""

    title: str = Field(..., min_length=1, max_length=300)
    description: Optional[str] = None
    event_type: str = EventType.MEETING
    date: datetime
    location: Optional[str] = None
    is_online: bool = False
    external_url: Optional[str] = None


class EventCreate(EventBase):
    """Schema for creating an event."""

    pass


class EventUpdate(BaseModel):
    """Schema for updating an event."""

    title: Optional[str] = Field(None, min_length=1, max_length=300)
    description: Optional[str] = None
    event_type: Optional[str] = None
    date: Optional[datetime] = None
    location: Optional[str] = None
    is_online: Optional[bool] = None
    external_url: Optional[str] = None


class Event(EventBase):
    """Complete event model with metadata."""

    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class EventWithParticipants(Event):
    """Event with participant list."""

    participants_count: int = 0
    participants: list[dict] = Field(default_factory=list)  # {person, role}
