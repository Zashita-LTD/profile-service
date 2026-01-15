"""Relationship models for graph edges."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class WorksAtRelation(BaseModel):
    """Person works at Company relationship."""

    person_id: UUID
    company_id: UUID
    role: str = Field(..., min_length=1, max_length=100)
    since: Optional[int] = None  # Year started
    until: Optional[int] = None  # Year ended (None = current)
    is_current: bool = True


class KnowsRelation(BaseModel):
    """Person knows Person relationship."""

    person_id: UUID
    other_person_id: UUID
    strength: float = Field(0.5, ge=0.0, le=1.0)  # Connection strength 0.0-1.0
    context: Optional[str] = None  # "work", "school", "conference", etc.
    since: Optional[datetime] = None


class InterestedInRelation(BaseModel):
    """Person interested in Interest relationship."""

    person_id: UUID
    interest_name: str  # Interest is identified by name
    level: Optional[str] = None  # "casual", "hobby", "professional"


class HasSkillRelation(BaseModel):
    """Person has Skill relationship."""

    person_id: UUID
    skill_name: str  # Skill is identified by name
    level: Optional[str] = None  # "beginner", "intermediate", "advanced", "expert"
    years_experience: Optional[int] = None


class ParticipatedInRelation(BaseModel):
    """Person participated in Event relationship."""

    person_id: UUID
    event_id: UUID
    role: str = "participant"  # "host", "speaker", "participant", "organizer"


# Response models for relationship queries

class ConnectionResponse(BaseModel):
    """Response model for person connections."""

    person_id: UUID
    person_name: str
    relationship_type: str
    strength: Optional[float] = None
    context: Optional[str] = None


class PathNode(BaseModel):
    """Node in a graph path."""

    id: str
    label: str
    name: str
    properties: dict = Field(default_factory=dict)


class PathRelationship(BaseModel):
    """Relationship in a graph path."""

    type: str
    properties: dict = Field(default_factory=dict)


class GraphPath(BaseModel):
    """Complete path between two nodes."""

    nodes: list[PathNode]
    relationships: list[PathRelationship]
    length: int
