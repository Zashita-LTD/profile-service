"""GraphQL types."""

from datetime import datetime
from typing import Optional

import strawberry


@strawberry.type
class SkillType:
    """Skill type."""
    name: str
    category: Optional[str] = None
    level: Optional[str] = None
    years_experience: Optional[int] = None


@strawberry.type
class InterestType:
    """Interest type."""
    name: str
    category: Optional[str] = None
    icon: Optional[str] = None


@strawberry.type
class CompanyType:
    """Company type."""
    id: str
    name: str
    description: Optional[str] = None
    website: Optional[str] = None
    industry: Optional[str] = None
    size: Optional[str] = None
    location: Optional[str] = None
    logo_url: Optional[str] = None


@strawberry.type
class CareerType:
    """Career entry type."""
    company: CompanyType
    role: str
    since: Optional[int] = None
    until: Optional[int] = None
    is_current: bool = False


@strawberry.type
class ConnectionType:
    """Connection/friend type."""
    person: "PersonType"
    distance: int
    strength: float
    context: Optional[str] = None


@strawberry.type
class PathNodeType:
    """Node in connection path."""
    id: str
    name: str


@strawberry.type
class ConnectionPathType:
    """Path between two people."""
    nodes: list[PathNodeType]
    distance: int
    intermediaries: list[str]


@strawberry.type
class NetworkStatsType:
    """Network statistics."""
    direct_connections: int
    second_degree: int
    companies: int
    skills: int
    interests: int
    network_reach: int


@strawberry.type
class PersonalityType:
    """Personality traits."""
    personality_type: Optional[str] = None
    communication_style: Optional[str] = None
    decision_making: Optional[str] = None
    
    @strawberry.field
    def summary(self) -> Optional[str]:
        """Get personality summary."""
        parts = []
        if self.personality_type:
            parts.append(f"Тип: {self.personality_type}")
        if self.communication_style:
            parts.append(f"Коммуникация: {self.communication_style}")
        if self.decision_making:
            parts.append(f"Принятие решений: {self.decision_making}")
        return ". ".join(parts) if parts else None


@strawberry.type
class PersonType:
    """Person type with lazy loading."""
    id: str
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    bio: Optional[str] = None
    location: Optional[str] = None
    avatar_url: Optional[str] = None
    personality_type: Optional[str] = None
    communication_style: Optional[str] = None
    decision_making: Optional[str] = None
    
    @strawberry.field
    async def career(self) -> list[CareerType]:
        """Get career history."""
        from app.graph.queries import GraphQueries
        from app.graph.nodes import CompanyNode
        
        career_data = await GraphQueries.get_career(self.id)
        return [
            CareerType(
                company=CompanyType(
                    id=c["company"].id,
                    name=c["company"].name,
                    description=c["company"].description,
                    website=c["company"].website,
                    industry=c["company"].industry,
                    size=c["company"].size,
                    location=c["company"].location,
                    logo_url=c["company"].logo_url,
                ),
                role=c["role"] or "",
                since=c["since"],
                until=c["until"],
                is_current=c["is_current"],
            )
            for c in career_data
        ]
    
    @strawberry.field
    async def skills(self) -> list[SkillType]:
        """Get skills."""
        from app.graph.queries import GraphQueries
        
        skills_data = await GraphQueries.get_skills(self.id)
        return [
            SkillType(
                name=s["skill"].name,
                category=s["skill"].category,
                level=s["level"],
                years_experience=s["years_experience"],
            )
            for s in skills_data
        ]
    
    @strawberry.field
    async def friends(self, depth: int = 1, min_strength: float = 0.0) -> list[ConnectionType]:
        """Get friends/connections up to depth."""
        from app.graph.queries import GraphQueries
        
        friends_data = await GraphQueries.get_friends(self.id, depth, min_strength)
        return [
            ConnectionType(
                person=PersonType(
                    id=f["person"].id,
                    name=f["person"].name,
                    email=f["person"].email,
                    location=f["person"].location,
                ),
                distance=f["distance"],
                strength=f["avg_strength"],
            )
            for f in friends_data
        ]
    
    @strawberry.field
    async def network_stats(self) -> NetworkStatsType:
        """Get network statistics."""
        from app.graph.queries import GraphQueries
        
        stats = await GraphQueries.get_network_stats(self.id)
        return NetworkStatsType(**stats)
    
    @strawberry.field
    def personality(self) -> PersonalityType:
        """Get personality traits."""
        return PersonalityType(
            personality_type=self.personality_type,
            communication_style=self.communication_style,
            decision_making=self.decision_making,
        )


@strawberry.type
class ExpertType:
    """Expert search result."""
    person: PersonType
    skill: SkillType
    match_score: float = 1.0


@strawberry.type
class BiographyType:
    """Generated biography."""
    id: str
    person_id: str
    content: str
    style: str
    language: str
    model_used: str
    facts_count: int
    created_at: datetime


@strawberry.input
class CreatePersonInput:
    """Input for creating a person."""
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    bio: Optional[str] = None


@strawberry.input
class GenerateBiographyInput:
    """Input for biography generation."""
    person_id: str
    style: str = "professional"  # professional, casual, detailed, executive
    language: str = "ru"
