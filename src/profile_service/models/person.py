"""Person node model."""

from datetime import datetime
from typing import Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, EmailStr


class PersonBase(BaseModel):
    """Base person attributes."""

    name: str = Field(..., min_length=1, max_length=200)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None


class PersonCreate(PersonBase):
    """Schema for creating a person."""

    pass


class PersonUpdate(BaseModel):
    """Schema for updating a person."""

    name: Optional[str] = Field(None, min_length=1, max_length=200)
    email: Optional[EmailStr] = None
    phone: Optional[str] = None
    avatar_url: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None


class Person(PersonBase):
    """Complete person model with metadata."""

    id: UUID = Field(default_factory=uuid4)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    class Config:
        from_attributes = True


class PersonWithRelations(Person):
    """Person with related entities."""

    companies: list[dict] = Field(default_factory=list)  # {company, role, since}
    skills: list[str] = Field(default_factory=list)
    interests: list[str] = Field(default_factory=list)
    connections_count: int = 0
