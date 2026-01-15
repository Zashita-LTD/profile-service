"""Taste Graph - Neo4j models for preferences, brands, and concepts."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from uuid import uuid4


@dataclass
class ConceptNode:
    """Concept node representing abstract preference (style, taste)."""
    
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    category: str = ""  # style, lifestyle, taste, interest
    description: Optional[str] = None
    
    # Aggregated stats
    global_popularity: float = 0.0  # How many people like this
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    @classmethod
    def from_record(cls, record: dict) -> "ConceptNode":
        return cls(
            id=record.get("id", ""),
            name=record.get("name", ""),
            category=record.get("category", ""),
            description=record.get("description"),
            global_popularity=record.get("global_popularity", 0.0),
        )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "description": self.description,
            "global_popularity": self.global_popularity,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class BrandNode:
    """Brand node representing commercial brands."""
    
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    category: str = ""  # clothing, electronics, automotive, food, etc.
    
    # Brand metadata
    logo_url: Optional[str] = None
    website: Optional[str] = None
    price_tier: str = ""  # budget, mid, premium, luxury
    country: Optional[str] = None
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    @classmethod
    def from_record(cls, record: dict) -> "BrandNode":
        return cls(
            id=record.get("id", ""),
            name=record.get("name", ""),
            category=record.get("category", ""),
            logo_url=record.get("logo_url"),
            website=record.get("website"),
            price_tier=record.get("price_tier", ""),
            country=record.get("country"),
        )
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "category": self.category,
            "logo_url": self.logo_url,
            "website": self.website,
            "price_tier": self.price_tier,
            "country": self.country,
            "created_at": self.created_at.isoformat(),
        }


@dataclass
class LifestyleNode:
    """Lifestyle indicator node."""
    
    id: str = field(default_factory=lambda: str(uuid4()))
    name: str = ""
    category: str = ""  # health, wealth, social, work, hobby
    description: Optional[str] = None
    
    created_at: datetime = field(default_factory=datetime.utcnow)
    
    @classmethod
    def from_record(cls, record: dict) -> "LifestyleNode":
        return cls(
            id=record.get("id", ""),
            name=record.get("name", ""),
            category=record.get("category", ""),
            description=record.get("description"),
        )


# Relationship types for Taste Graph

@dataclass
class LikesRelationship:
    """Person -[:LIKES]-> Concept relationship."""
    
    strength: float = 0.5  # 0-1
    evidence_count: int = 1
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    source: str = "media"  # media, manual, import


@dataclass
class WearsRelationship:
    """Person -[:WEARS]-> Brand relationship."""
    
    confidence: float = 0.5
    evidence_count: int = 1
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)
    frequency: str = "sometimes"  # rarely, sometimes, often, always


@dataclass
class HasLifestyleRelationship:
    """Person -[:HAS_LIFESTYLE]-> Lifestyle relationship."""
    
    confidence: float = 0.5
    description: str = ""
    first_seen: datetime = field(default_factory=datetime.utcnow)
    last_seen: datetime = field(default_factory=datetime.utcnow)


# Query helpers

TASTE_GRAPH_INIT_QUERIES = [
    # Constraints
    "CREATE CONSTRAINT concept_name IF NOT EXISTS FOR (c:Concept) REQUIRE c.name IS UNIQUE",
    "CREATE CONSTRAINT brand_name IF NOT EXISTS FOR (b:Brand) REQUIRE b.name IS UNIQUE",
    "CREATE CONSTRAINT lifestyle_name IF NOT EXISTS FOR (l:Lifestyle) REQUIRE (l.name, l.category) IS UNIQUE",
    
    # Indexes
    "CREATE INDEX concept_category IF NOT EXISTS FOR (c:Concept) ON (c.category)",
    "CREATE INDEX brand_category IF NOT EXISTS FOR (b:Brand) ON (b.category)",
    "CREATE INDEX brand_price_tier IF NOT EXISTS FOR (b:Brand) ON (b.price_tier)",
    "CREATE INDEX lifestyle_category IF NOT EXISTS FOR (l:Lifestyle) ON (l.category)",
]


async def init_taste_graph_schema(neo4j_session) -> None:
    """Initialize Taste Graph schema in Neo4j."""
    for query in TASTE_GRAPH_INIT_QUERIES:
        try:
            await neo4j_session.run(query)
        except Exception:
            pass  # Constraint may already exist
