"""Neo4j node models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4


@dataclass
class PersonNode:
    """Person node in graph."""
    
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    email: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    avatar_url: Optional[str] = None
    
    # Personality traits (from AI analysis)
    personality_type: Optional[str] = None  # e.g., "INTJ", "консерватор"
    communication_style: Optional[str] = None  # e.g., "формальный", "дружеский"
    decision_making: Optional[str] = None  # e.g., "аналитик", "интуит"
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    
    @classmethod
    def from_record(cls, record: dict) -> "PersonNode":
        """Create from Neo4j record."""
        return cls(
            id=record.get("id", ""),
            name=record.get("name", ""),
            email=record.get("email"),
            phone=record.get("phone"),
            bio=record.get("bio"),
            location=record.get("location"),
            avatar_url=record.get("avatar_url"),
            personality_type=record.get("personality_type"),
            communication_style=record.get("communication_style"),
            decision_making=record.get("decision_making"),
        )
    
    def to_dict(self) -> dict:
        """Convert to dict for Neo4j."""
        return {
            "id": self.id,
            "name": self.name,
            "email": self.email,
            "phone": self.phone,
            "bio": self.bio,
            "location": self.location,
            "avatar_url": self.avatar_url,
            "personality_type": self.personality_type,
            "communication_style": self.communication_style,
            "decision_making": self.decision_making,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


@dataclass
class CompanyNode:
    """Company node in graph."""
    
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    description: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    size: Optional[str] = None  # "1-10", "11-50", "51-200", "201-500", "500+"
    location: Optional[str] = None
    logo_url: Optional[str] = None
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    @classmethod
    def from_record(cls, record: dict) -> "CompanyNode":
        """Create from Neo4j record."""
        return cls(
            id=record.get("id", ""),
            name=record.get("name", ""),
            description=record.get("description"),
            website=record.get("website"),
            industry=record.get("industry"),
            size=record.get("size"),
            location=record.get("location"),
            logo_url=record.get("logo_url"),
        )
    
    def to_dict(self) -> dict:
        """Convert to dict."""
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "website": self.website,
            "industry": self.industry,
            "size": self.size,
            "location": self.location,
            "logo_url": self.logo_url,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class SkillNode:
    """Skill node in graph."""
    
    name: str = ""
    category: Optional[str] = None  # "programming", "management", "construction"
    level: Optional[str] = None  # "beginner", "intermediate", "advanced", "expert"
    
    @classmethod
    def from_record(cls, record: dict) -> "SkillNode":
        """Create from Neo4j record."""
        return cls(
            name=record.get("name", ""),
            category=record.get("category"),
        )


@dataclass
class InterestNode:
    """Interest node in graph."""
    
    name: str = ""
    category: Optional[str] = None  # "sport", "music", "business"
    icon: Optional[str] = None  # emoji
    
    @classmethod
    def from_record(cls, record: dict) -> "InterestNode":
        """Create from Neo4j record."""
        return cls(
            name=record.get("name", ""),
            category=record.get("category"),
            icon=record.get("icon"),
        )


@dataclass
class EventNode:
    """Event node in graph."""
    
    id: str = field(default_factory=lambda: str(uuid4()))
    title: str = ""
    description: Optional[str] = None
    event_type: str = "meeting"  # "meeting", "conference", "webinar", "exhibition"
    date: Optional[datetime] = None
    location: Optional[str] = None
    
    @classmethod
    def from_record(cls, record: dict) -> "EventNode":
        """Create from Neo4j record."""
        return cls(
            id=record.get("id", ""),
            title=record.get("title", ""),
            description=record.get("description"),
            event_type=record.get("event_type", "meeting"),
            location=record.get("location"),
        )
