"""Person repository for Neo4j operations."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from ..database import Neo4jDatabase
from ..models.person import Person, PersonCreate, PersonUpdate, PersonWithRelations


class PersonRepository:
    """Repository for Person node operations."""

    @staticmethod
    async def create(data: PersonCreate) -> Person:
        """Create a new Person node."""
        person = Person(**data.model_dump())

        query = """
        CREATE (p:Person {
            id: $id,
            name: $name,
            email: $email,
            phone: $phone,
            avatar_url: $avatar_url,
            bio: $bio,
            location: $location,
            created_at: $created_at,
            updated_at: $updated_at
        })
        RETURN p
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(
                query,
                id=str(person.id),
                name=person.name,
                email=person.email,
                phone=person.phone,
                avatar_url=person.avatar_url,
                bio=person.bio,
                location=person.location,
                created_at=person.created_at.isoformat(),
                updated_at=person.updated_at.isoformat(),
            )
            await result.consume()

        return person

    @staticmethod
    async def get_by_id(person_id: UUID) -> Optional[Person]:
        """Get a Person by ID."""
        query = """
        MATCH (p:Person {id: $id})
        RETURN p
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(query, id=str(person_id))
            record = await result.single()

            if not record:
                return None

            node = record["p"]
            return Person(
                id=UUID(node["id"]),
                name=node["name"],
                email=node.get("email"),
                phone=node.get("phone"),
                avatar_url=node.get("avatar_url"),
                bio=node.get("bio"),
                location=node.get("location"),
                created_at=datetime.fromisoformat(node["created_at"]),
                updated_at=datetime.fromisoformat(node["updated_at"]),
            )

    @staticmethod
    async def get_with_relations(person_id: UUID) -> Optional[PersonWithRelations]:
        """Get a Person with all related entities."""
        query = """
        MATCH (p:Person {id: $id})
        OPTIONAL MATCH (p)-[w:WORKS_AT]->(c:Company)
        OPTIONAL MATCH (p)-[:HAS_SKILL]->(s:Skill)
        OPTIONAL MATCH (p)-[:INTERESTED_IN]->(i:Interest)
        OPTIONAL MATCH (p)-[:KNOWS]-(other:Person)
        RETURN p,
               collect(DISTINCT {company: c, role: w.role, since: w.since}) as companies,
               collect(DISTINCT s.name) as skills,
               collect(DISTINCT i.name) as interests,
               count(DISTINCT other) as connections_count
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(query, id=str(person_id))
            record = await result.single()

            if not record:
                return None

            node = record["p"]
            companies = [
                {"company": c["company"]["name"], "role": c["role"], "since": c["since"]}
                for c in record["companies"]
                if c["company"] is not None
            ]

            return PersonWithRelations(
                id=UUID(node["id"]),
                name=node["name"],
                email=node.get("email"),
                phone=node.get("phone"),
                avatar_url=node.get("avatar_url"),
                bio=node.get("bio"),
                location=node.get("location"),
                created_at=datetime.fromisoformat(node["created_at"]),
                updated_at=datetime.fromisoformat(node["updated_at"]),
                companies=companies,
                skills=[s for s in record["skills"] if s],
                interests=[i for i in record["interests"] if i],
                connections_count=record["connections_count"],
            )

    @staticmethod
    async def list_all(skip: int = 0, limit: int = 100) -> list[Person]:
        """List all Persons with pagination."""
        query = """
        MATCH (p:Person)
        RETURN p
        ORDER BY p.name
        SKIP $skip
        LIMIT $limit
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(query, skip=skip, limit=limit)
            records = await result.data()

            return [
                Person(
                    id=UUID(r["p"]["id"]),
                    name=r["p"]["name"],
                    email=r["p"].get("email"),
                    phone=r["p"].get("phone"),
                    avatar_url=r["p"].get("avatar_url"),
                    bio=r["p"].get("bio"),
                    location=r["p"].get("location"),
                    created_at=datetime.fromisoformat(r["p"]["created_at"]),
                    updated_at=datetime.fromisoformat(r["p"]["updated_at"]),
                )
                for r in records
            ]

    @staticmethod
    async def update(person_id: UUID, data: PersonUpdate) -> Optional[Person]:
        """Update a Person."""
        updates = {k: v for k, v in data.model_dump().items() if v is not None}
        if not updates:
            return await PersonRepository.get_by_id(person_id)

        updates["updated_at"] = datetime.utcnow().isoformat()

        set_clause = ", ".join([f"p.{k} = ${k}" for k in updates.keys()])
        query = f"""
        MATCH (p:Person {{id: $id}})
        SET {set_clause}
        RETURN p
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(query, id=str(person_id), **updates)
            record = await result.single()

            if not record:
                return None

            node = record["p"]
            return Person(
                id=UUID(node["id"]),
                name=node["name"],
                email=node.get("email"),
                phone=node.get("phone"),
                avatar_url=node.get("avatar_url"),
                bio=node.get("bio"),
                location=node.get("location"),
                created_at=datetime.fromisoformat(node["created_at"]),
                updated_at=datetime.fromisoformat(node["updated_at"]),
            )

    @staticmethod
    async def delete(person_id: UUID) -> bool:
        """Delete a Person and all their relationships."""
        query = """
        MATCH (p:Person {id: $id})
        DETACH DELETE p
        RETURN count(p) as deleted
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(query, id=str(person_id))
            record = await result.single()
            return record["deleted"] > 0 if record else False

    @staticmethod
    async def search(query_text: str, limit: int = 20) -> list[Person]:
        """Search Persons by name or email."""
        query = """
        MATCH (p:Person)
        WHERE toLower(p.name) CONTAINS toLower($query)
           OR toLower(p.email) CONTAINS toLower($query)
        RETURN p
        ORDER BY p.name
        LIMIT $limit
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(query, query=query_text, limit=limit)
            records = await result.data()

            return [
                Person(
                    id=UUID(r["p"]["id"]),
                    name=r["p"]["name"],
                    email=r["p"].get("email"),
                    phone=r["p"].get("phone"),
                    avatar_url=r["p"].get("avatar_url"),
                    bio=r["p"].get("bio"),
                    location=r["p"].get("location"),
                    created_at=datetime.fromisoformat(r["p"]["created_at"]),
                    updated_at=datetime.fromisoformat(r["p"]["updated_at"]),
                )
                for r in records
            ]
