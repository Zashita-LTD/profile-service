"""Neo4j async connection."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession

from app.config import get_settings


class Neo4jDB:
    """Neo4j database connection manager."""
    
    _driver: AsyncDriver | None = None
    
    @classmethod
    async def connect(cls) -> None:
        """Connect to Neo4j."""
        settings = get_settings()
        cls._driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        # Verify connection
        await cls._driver.verify_connectivity()
        await cls._init_constraints()
    
    @classmethod
    async def disconnect(cls) -> None:
        """Disconnect from Neo4j."""
        if cls._driver:
            await cls._driver.close()
            cls._driver = None
    
    @classmethod
    @asynccontextmanager
    async def session(cls) -> AsyncGenerator[AsyncSession, None]:
        """Get Neo4j session."""
        if not cls._driver:
            raise RuntimeError("Neo4j not connected")
        async with cls._driver.session() as session:
            yield session
    
    @classmethod
    async def _init_constraints(cls) -> None:
        """Initialize Neo4j constraints and indexes."""
        constraints = [
            "CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT person_email IF NOT EXISTS FOR (p:Person) REQUIRE p.email IS UNIQUE",
            "CREATE CONSTRAINT company_id IF NOT EXISTS FOR (c:Company) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT skill_name IF NOT EXISTS FOR (s:Skill) REQUIRE s.name IS UNIQUE",
            "CREATE CONSTRAINT interest_name IF NOT EXISTS FOR (i:Interest) REQUIRE i.name IS UNIQUE",
            "CREATE CONSTRAINT event_id IF NOT EXISTS FOR (e:Event) REQUIRE e.id IS UNIQUE",
            # Indexes for search
            "CREATE INDEX person_name IF NOT EXISTS FOR (p:Person) ON (p.name)",
            "CREATE INDEX person_location IF NOT EXISTS FOR (p:Person) ON (p.location)",
            "CREATE INDEX company_name IF NOT EXISTS FOR (c:Company) ON (c.name)",
            "CREATE INDEX skill_category IF NOT EXISTS FOR (s:Skill) ON (s.category)",
        ]
        async with cls.session() as session:
            for constraint in constraints:
                try:
                    await session.run(constraint)
                except Exception:
                    pass  # Constraint may already exist


async def get_neo4j() -> type[Neo4jDB]:
    """Get Neo4j connection class."""
    return Neo4jDB
