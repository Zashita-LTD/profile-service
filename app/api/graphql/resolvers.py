"""GraphQL resolvers."""

from typing import Optional

import strawberry

from app.api.graphql.types import (
    PersonType,
    ExpertType,
    SkillType,
    BiographyType,
    ConnectionPathType,
    PathNodeType,
    CreatePersonInput,
    GenerateBiographyInput,
)
from app.graph.queries import GraphQueries


@strawberry.type
class Query:
    """GraphQL queries."""
    
    @strawberry.field
    async def person(self, id: str) -> Optional[PersonType]:
        """Get person by ID.
        
        Example:
        ```graphql
        query {
            person(id: "123") {
                name
                career { company { name } role }
                friends(depth: 2) { person { name } distance }
            }
        }
        ```
        """
        person = await GraphQueries.get_person(id)
        if not person:
            return None
        return PersonType(
            id=person.id,
            name=person.name,
            email=person.email,
            phone=person.phone,
            bio=person.bio,
            location=person.location,
            avatar_url=person.avatar_url,
            personality_type=person.personality_type,
            communication_style=person.communication_style,
            decision_making=person.decision_making,
        )
    
    @strawberry.field
    async def person_by_email(self, email: str) -> Optional[PersonType]:
        """Get person by email."""
        person = await GraphQueries.get_person_by_email(email)
        if not person:
            return None
        return PersonType(
            id=person.id,
            name=person.name,
            email=person.email,
            phone=person.phone,
            bio=person.bio,
            location=person.location,
        )
    
    @strawberry.field
    async def find_experts(
        self,
        skill: str,
        location: Optional[str] = None,
        min_level: str = "intermediate",
        limit: int = 10,
    ) -> list[ExpertType]:
        """Find experts with a specific skill.
        
        Example:
        ```graphql
        query {
            findExperts(skill: "BIM", location: "Moscow", minLevel: "advanced") {
                person { name location }
                skill { name level yearsExperience }
            }
        }
        ```
        """
        experts = await GraphQueries.find_experts(skill, location, min_level, limit)
        return [
            ExpertType(
                person=PersonType(
                    id=e["person"].id,
                    name=e["person"].name,
                    email=e["person"].email,
                    location=e["person"].location,
                ),
                skill=SkillType(
                    name=e["skill"].name,
                    category=e["skill"].category,
                    level=e["level"],
                    years_experience=e["years_experience"],
                ),
            )
            for e in experts
        ]
    
    @strawberry.field
    async def find_path(
        self,
        from_id: str,
        to_id: str,
        max_depth: int = 6,
    ) -> Optional[ConnectionPathType]:
        """Find shortest path between two people.
        
        Example:
        ```graphql
        query {
            findPath(fromId: "123", toId: "456") {
                nodes { name }
                distance
                intermediaries
            }
        }
        ```
        """
        path = await GraphQueries.find_path_to_person(from_id, to_id, max_depth)
        if not path:
            return None
        
        nodes = [
            PathNodeType(id=n.id, name=n.name)
            for n in path["nodes"]
        ]
        intermediaries = [n.name for n in path["nodes"][1:-1]]
        
        return ConnectionPathType(
            nodes=nodes,
            distance=path["distance"],
            intermediaries=intermediaries,
        )
    
    @strawberry.field
    async def common_interests(
        self,
        person1_id: str,
        person2_id: str,
    ) -> list[str]:
        """Find common interests between two people."""
        return await GraphQueries.get_common_interests(person1_id, person2_id)


@strawberry.type
class Mutation:
    """GraphQL mutations."""
    
    @strawberry.mutation
    async def create_person(self, input: CreatePersonInput) -> PersonType:
        """Create a new person."""
        person = await GraphQueries.create_person(
            name=input.name,
            email=input.email,
            phone=input.phone,
            location=input.location,
            bio=input.bio,
        )
        return PersonType(
            id=person.id,
            name=person.name,
            email=person.email,
            phone=person.phone,
            bio=person.bio,
            location=person.location,
        )
    
    @strawberry.mutation
    async def generate_biography(self, input: GenerateBiographyInput) -> BiographyType:
        """Generate AI biography for a person.
        
        Example:
        ```graphql
        mutation {
            generateBiography(input: {personId: "123", style: "professional"}) {
                content
                factsCount
            }
        }
        ```
        """
        from app.analysis.biography import BiographyGenerator
        from datetime import datetime
        
        generator = BiographyGenerator()
        result = await generator.generate(
            person_id=input.person_id,
            style=input.style,
            language=input.language,
        )
        
        return BiographyType(
            id=result["id"],
            person_id=input.person_id,
            content=result["content"],
            style=input.style,
            language=input.language,
            model_used=result["model_used"],
            facts_count=result["facts_count"],
            created_at=datetime.utcnow(),
        )
    
    @strawberry.mutation
    async def analyze_personality(self, person_id: str) -> PersonType:
        """Analyze personality from interactions and facts."""
        from app.analysis.personality import PersonalityAnalyzer
        
        analyzer = PersonalityAnalyzer()
        traits = await analyzer.analyze(person_id)
        
        person = await GraphQueries.update_person_traits(
            person_id=person_id,
            personality_type=traits.get("personality_type"),
            communication_style=traits.get("communication_style"),
            decision_making=traits.get("decision_making"),
        )
        
        if not person:
            raise ValueError(f"Person {person_id} not found")
        
        return PersonType(
            id=person.id,
            name=person.name,
            email=person.email,
            location=person.location,
            personality_type=person.personality_type,
            communication_style=person.communication_style,
            decision_making=person.decision_making,
        )
