"""Relationship repository for Neo4j operations."""

from ..database import Neo4jDatabase
from ..models.relationships import (
    WorksAtRelation,
    KnowsRelation,
    InterestedInRelation,
    HasSkillRelation,
    ParticipatedInRelation,
)


class RelationshipRepository:
    """Repository for relationship operations."""

    @staticmethod
    async def create_works_at(data: WorksAtRelation) -> bool:
        """Create WORKS_AT relationship between Person and Company."""
        query = """
        MATCH (p:Person {id: $person_id})
        MATCH (c:Company {id: $company_id})
        MERGE (p)-[r:WORKS_AT]->(c)
        SET r.role = $role,
            r.since = $since,
            r.until = $until,
            r.is_current = $is_current
        RETURN r
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(
                query,
                person_id=str(data.person_id),
                company_id=str(data.company_id),
                role=data.role,
                since=data.since,
                until=data.until,
                is_current=data.is_current,
            )
            record = await result.single()
            return record is not None

    @staticmethod
    async def remove_works_at(person_id: str, company_id: str) -> bool:
        """Remove WORKS_AT relationship."""
        query = """
        MATCH (p:Person {id: $person_id})-[r:WORKS_AT]->(c:Company {id: $company_id})
        DELETE r
        RETURN count(r) as deleted
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(
                query, person_id=person_id, company_id=company_id
            )
            record = await result.single()
            return record["deleted"] > 0 if record else False

    @staticmethod
    async def create_knows(data: KnowsRelation) -> bool:
        """Create KNOWS relationship between two Persons."""
        query = """
        MATCH (p1:Person {id: $person_id})
        MATCH (p2:Person {id: $other_person_id})
        MERGE (p1)-[r:KNOWS]->(p2)
        SET r.strength = $strength,
            r.context = $context,
            r.since = $since
        RETURN r
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(
                query,
                person_id=str(data.person_id),
                other_person_id=str(data.other_person_id),
                strength=data.strength,
                context=data.context,
                since=data.since.isoformat() if data.since else None,
            )
            record = await result.single()
            return record is not None

    @staticmethod
    async def update_knows_strength(
        person_id: str, other_person_id: str, strength: float
    ) -> bool:
        """Update KNOWS relationship strength."""
        query = """
        MATCH (p1:Person {id: $person_id})-[r:KNOWS]-(p2:Person {id: $other_person_id})
        SET r.strength = $strength
        RETURN r
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(
                query,
                person_id=person_id,
                other_person_id=other_person_id,
                strength=strength,
            )
            record = await result.single()
            return record is not None

    @staticmethod
    async def create_interested_in(data: InterestedInRelation) -> bool:
        """Create INTERESTED_IN relationship, creating Interest if needed."""
        query = """
        MATCH (p:Person {id: $person_id})
        MERGE (i:Interest {name: $interest_name})
        MERGE (p)-[r:INTERESTED_IN]->(i)
        SET r.level = $level
        RETURN r
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(
                query,
                person_id=str(data.person_id),
                interest_name=data.interest_name,
                level=data.level,
            )
            record = await result.single()
            return record is not None

    @staticmethod
    async def remove_interested_in(person_id: str, interest_name: str) -> bool:
        """Remove INTERESTED_IN relationship."""
        query = """
        MATCH (p:Person {id: $person_id})-[r:INTERESTED_IN]->(i:Interest {name: $interest_name})
        DELETE r
        RETURN count(r) as deleted
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(
                query, person_id=person_id, interest_name=interest_name
            )
            record = await result.single()
            return record["deleted"] > 0 if record else False

    @staticmethod
    async def create_has_skill(data: HasSkillRelation) -> bool:
        """Create HAS_SKILL relationship, creating Skill if needed."""
        query = """
        MATCH (p:Person {id: $person_id})
        MERGE (s:Skill {name: $skill_name})
        MERGE (p)-[r:HAS_SKILL]->(s)
        SET r.level = $level,
            r.years_experience = $years_experience
        RETURN r
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(
                query,
                person_id=str(data.person_id),
                skill_name=data.skill_name,
                level=data.level,
                years_experience=data.years_experience,
            )
            record = await result.single()
            return record is not None

    @staticmethod
    async def remove_has_skill(person_id: str, skill_name: str) -> bool:
        """Remove HAS_SKILL relationship."""
        query = """
        MATCH (p:Person {id: $person_id})-[r:HAS_SKILL]->(s:Skill {name: $skill_name})
        DELETE r
        RETURN count(r) as deleted
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(
                query, person_id=person_id, skill_name=skill_name
            )
            record = await result.single()
            return record["deleted"] > 0 if record else False

    @staticmethod
    async def create_participated_in(data: ParticipatedInRelation) -> bool:
        """Create PARTICIPATED_IN relationship between Person and Event."""
        query = """
        MATCH (p:Person {id: $person_id})
        MATCH (e:Event {id: $event_id})
        MERGE (p)-[r:PARTICIPATED_IN]->(e)
        SET r.role = $role
        RETURN r
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(
                query,
                person_id=str(data.person_id),
                event_id=str(data.event_id),
                role=data.role,
            )
            record = await result.single()
            return record is not None
