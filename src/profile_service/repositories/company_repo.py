"""Company repository for Neo4j operations."""

from datetime import datetime
from typing import Optional
from uuid import UUID

from ..database import Neo4jDatabase
from ..models.company import Company, CompanyCreate, CompanyUpdate, CompanyWithEmployees


class CompanyRepository:
    """Repository for Company node operations."""

    @staticmethod
    async def create(data: CompanyCreate) -> Company:
        """Create a new Company node."""
        company = Company(**data.model_dump())

        query = """
        CREATE (c:Company {
            id: $id,
            name: $name,
            description: $description,
            website: $website,
            logo_url: $logo_url,
            industry: $industry,
            size: $size,
            location: $location,
            founded_year: $founded_year,
            created_at: $created_at,
            updated_at: $updated_at
        })
        RETURN c
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(
                query,
                id=str(company.id),
                name=company.name,
                description=company.description,
                website=company.website,
                logo_url=company.logo_url,
                industry=company.industry,
                size=company.size,
                location=company.location,
                founded_year=company.founded_year,
                created_at=company.created_at.isoformat(),
                updated_at=company.updated_at.isoformat(),
            )
            await result.consume()

        return company

    @staticmethod
    async def get_by_id(company_id: UUID) -> Optional[Company]:
        """Get a Company by ID."""
        query = """
        MATCH (c:Company {id: $id})
        RETURN c
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(query, id=str(company_id))
            record = await result.single()

            if not record:
                return None

            node = record["c"]
            return Company(
                id=UUID(node["id"]),
                name=node["name"],
                description=node.get("description"),
                website=node.get("website"),
                logo_url=node.get("logo_url"),
                industry=node.get("industry"),
                size=node.get("size"),
                location=node.get("location"),
                founded_year=node.get("founded_year"),
                created_at=datetime.fromisoformat(node["created_at"]),
                updated_at=datetime.fromisoformat(node["updated_at"]),
            )

    @staticmethod
    async def get_with_employees(company_id: UUID) -> Optional[CompanyWithEmployees]:
        """Get a Company with all employees."""
        query = """
        MATCH (c:Company {id: $id})
        OPTIONAL MATCH (p:Person)-[w:WORKS_AT]->(c)
        RETURN c,
               collect({person: p, role: w.role, since: w.since}) as employees,
               count(p) as employees_count
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(query, id=str(company_id))
            record = await result.single()

            if not record:
                return None

            node = record["c"]
            employees = [
                {
                    "person": e["person"]["name"],
                    "person_id": e["person"]["id"],
                    "role": e["role"],
                    "since": e["since"],
                }
                for e in record["employees"]
                if e["person"] is not None
            ]

            return CompanyWithEmployees(
                id=UUID(node["id"]),
                name=node["name"],
                description=node.get("description"),
                website=node.get("website"),
                logo_url=node.get("logo_url"),
                industry=node.get("industry"),
                size=node.get("size"),
                location=node.get("location"),
                founded_year=node.get("founded_year"),
                created_at=datetime.fromisoformat(node["created_at"]),
                updated_at=datetime.fromisoformat(node["updated_at"]),
                employees=employees,
                employees_count=record["employees_count"],
            )

    @staticmethod
    async def list_all(skip: int = 0, limit: int = 100) -> list[Company]:
        """List all Companies with pagination."""
        query = """
        MATCH (c:Company)
        RETURN c
        ORDER BY c.name
        SKIP $skip
        LIMIT $limit
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(query, skip=skip, limit=limit)
            records = await result.data()

            return [
                Company(
                    id=UUID(r["c"]["id"]),
                    name=r["c"]["name"],
                    description=r["c"].get("description"),
                    website=r["c"].get("website"),
                    logo_url=r["c"].get("logo_url"),
                    industry=r["c"].get("industry"),
                    size=r["c"].get("size"),
                    location=r["c"].get("location"),
                    founded_year=r["c"].get("founded_year"),
                    created_at=datetime.fromisoformat(r["c"]["created_at"]),
                    updated_at=datetime.fromisoformat(r["c"]["updated_at"]),
                )
                for r in records
            ]

    @staticmethod
    async def update(company_id: UUID, data: CompanyUpdate) -> Optional[Company]:
        """Update a Company."""
        updates = {k: v for k, v in data.model_dump().items() if v is not None}
        if not updates:
            return await CompanyRepository.get_by_id(company_id)

        updates["updated_at"] = datetime.utcnow().isoformat()

        set_clause = ", ".join([f"c.{k} = ${k}" for k in updates.keys()])
        query = f"""
        MATCH (c:Company {{id: $id}})
        SET {set_clause}
        RETURN c
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(query, id=str(company_id), **updates)
            record = await result.single()

            if not record:
                return None

            node = record["c"]
            return Company(
                id=UUID(node["id"]),
                name=node["name"],
                description=node.get("description"),
                website=node.get("website"),
                logo_url=node.get("logo_url"),
                industry=node.get("industry"),
                size=node.get("size"),
                location=node.get("location"),
                founded_year=node.get("founded_year"),
                created_at=datetime.fromisoformat(node["created_at"]),
                updated_at=datetime.fromisoformat(node["updated_at"]),
            )

    @staticmethod
    async def delete(company_id: UUID) -> bool:
        """Delete a Company and all relationships."""
        query = """
        MATCH (c:Company {id: $id})
        DETACH DELETE c
        RETURN count(c) as deleted
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(query, id=str(company_id))
            record = await result.single()
            return record["deleted"] > 0 if record else False

    @staticmethod
    async def search(query_text: str, limit: int = 20) -> list[Company]:
        """Search Companies by name."""
        query = """
        MATCH (c:Company)
        WHERE toLower(c.name) CONTAINS toLower($query)
        RETURN c
        ORDER BY c.name
        LIMIT $limit
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(query, query=query_text, limit=limit)
            records = await result.data()

            return [
                Company(
                    id=UUID(r["c"]["id"]),
                    name=r["c"]["name"],
                    description=r["c"].get("description"),
                    website=r["c"].get("website"),
                    logo_url=r["c"].get("logo_url"),
                    industry=r["c"].get("industry"),
                    size=r["c"].get("size"),
                    location=r["c"].get("location"),
                    founded_year=r["c"].get("founded_year"),
                    created_at=datetime.fromisoformat(r["c"]["created_at"]),
                    updated_at=datetime.fromisoformat(r["c"]["updated_at"]),
                )
                for r in records
            ]
