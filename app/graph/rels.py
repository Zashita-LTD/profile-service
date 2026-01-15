"""Neo4j relationship models."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class WorksAtRel:
    """WORKS_AT relationship: (Person)-[:WORKS_AT]->(Company)."""
    
    role: str = ""
    department: Optional[str] = None
    since: Optional[int] = None  # year
    until: Optional[int] = None  # year (None = current)
    is_current: bool = True
    
    @classmethod
    def from_record(cls, record: dict) -> "WorksAtRel":
        """Create from Neo4j record."""
        return cls(
            role=record.get("role", ""),
            department=record.get("department"),
            since=record.get("since"),
            until=record.get("until"),
            is_current=record.get("is_current", True),
        )
    
    def to_dict(self) -> dict:
        """Convert to dict."""
        return {
            "role": self.role,
            "department": self.department,
            "since": self.since,
            "until": self.until,
            "is_current": self.is_current,
        }


@dataclass
class KnowsRel:
    """KNOWS relationship: (Person)-[:KNOWS]->(Person)."""
    
    strength: float = 0.5  # 0.0 (acquaintance) to 1.0 (close friend)
    context: Optional[str] = None  # "work", "personal", "business", "event"
    since: Optional[int] = None  # year
    interaction_count: int = 0
    last_interaction: Optional[datetime] = None
    notes: Optional[str] = None
    
    @classmethod
    def from_record(cls, record: dict) -> "KnowsRel":
        """Create from Neo4j record."""
        return cls(
            strength=record.get("strength", 0.5),
            context=record.get("context"),
            since=record.get("since"),
            interaction_count=record.get("interaction_count", 0),
            notes=record.get("notes"),
        )
    
    def to_dict(self) -> dict:
        """Convert to dict."""
        return {
            "strength": self.strength,
            "context": self.context,
            "since": self.since,
            "interaction_count": self.interaction_count,
            "last_interaction": self.last_interaction.isoformat() if self.last_interaction else None,
            "notes": self.notes,
        }


@dataclass
class HasSkillRel:
    """HAS_SKILL relationship: (Person)-[:HAS_SKILL]->(Skill)."""
    
    level: str = "intermediate"  # "beginner", "intermediate", "advanced", "expert"
    years_experience: Optional[int] = None
    certified: bool = False
    last_used: Optional[int] = None  # year
    
    @classmethod
    def from_record(cls, record: dict) -> "HasSkillRel":
        """Create from Neo4j record."""
        return cls(
            level=record.get("level", "intermediate"),
            years_experience=record.get("years_experience"),
            certified=record.get("certified", False),
            last_used=record.get("last_used"),
        )
    
    def to_dict(self) -> dict:
        """Convert to dict."""
        return {
            "level": self.level,
            "years_experience": self.years_experience,
            "certified": self.certified,
            "last_used": self.last_used,
        }


@dataclass
class InterestedInRel:
    """INTERESTED_IN relationship: (Person)-[:INTERESTED_IN]->(Interest)."""
    
    level: str = "hobby"  # "hobby", "passionate", "professional"
    since: Optional[int] = None
    
    @classmethod
    def from_record(cls, record: dict) -> "InterestedInRel":
        """Create from Neo4j record."""
        return cls(
            level=record.get("level", "hobby"),
            since=record.get("since"),
        )
    
    def to_dict(self) -> dict:
        """Convert to dict."""
        return {
            "level": self.level,
            "since": self.since,
        }


@dataclass
class ParticipatedInRel:
    """PARTICIPATED_IN relationship: (Person)-[:PARTICIPATED_IN]->(Event)."""
    
    role: str = "attendee"  # "attendee", "speaker", "organizer", "sponsor"
    notes: Optional[str] = None
    
    @classmethod
    def from_record(cls, record: dict) -> "ParticipatedInRel":
        """Create from Neo4j record."""
        return cls(
            role=record.get("role", "attendee"),
            notes=record.get("notes"),
        )
    
    def to_dict(self) -> dict:
        """Convert to dict."""
        return {
            "role": self.role,
            "notes": self.notes,
        }
