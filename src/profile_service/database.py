"""Neo4j database connection and session management."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from neo4j import AsyncGraphDatabase, AsyncDriver, AsyncSession

from .config import get_settings


class Neo4jDatabase:
    """Neo4j database connection manager."""

    _driver: AsyncDriver | None = None

    @classmethod
    async def connect(cls) -> None:
        """Establish connection to Neo4j."""
        settings = get_settings()
        cls._driver = AsyncGraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
        )
        # Verify connection
        await cls._driver.verify_connectivity()

    @classmethod
    async def disconnect(cls) -> None:
        """Close Neo4j connection."""
        if cls._driver:
            await cls._driver.close()
            cls._driver = None

    @classmethod
    def get_driver(cls) -> AsyncDriver:
        """Get Neo4j driver instance."""
        if not cls._driver:
            raise RuntimeError("Database not connected. Call connect() first.")
        return cls._driver

    @classmethod
    @asynccontextmanager
    async def get_session(cls) -> AsyncGenerator[AsyncSession, None]:
        """Get a Neo4j session as async context manager."""
        driver = cls.get_driver()
        session = driver.session()
        try:
            yield session
        finally:
            await session.close()


async def init_constraints() -> None:
    """Initialize database constraints and indexes."""
    async with Neo4jDatabase.get_session() as session:
        # Unique constraints
        constraints = [
            "CREATE CONSTRAINT person_id IF NOT EXISTS FOR (p:Person) REQUIRE p.id IS UNIQUE",
            "CREATE CONSTRAINT company_id IF NOT EXISTS FOR (c:Company) REQUIRE c.id IS UNIQUE",
            "CREATE CONSTRAINT skill_name IF NOT EXISTS FOR (s:Skill) REQUIRE s.name IS UNIQUE",
            "CREATE CONSTRAINT interest_name IF NOT EXISTS FOR (i:Interest) REQUIRE i.name IS UNIQUE",
            "CREATE CONSTRAINT event_id IF NOT EXISTS FOR (e:Event) REQUIRE e.id IS UNIQUE",
        ]

        for constraint in constraints:
            await session.run(constraint)

        # Indexes for faster lookups
        indexes = [
            "CREATE INDEX person_email IF NOT EXISTS FOR (p:Person) ON (p.email)",
            "CREATE INDEX company_name IF NOT EXISTS FOR (c:Company) ON (c.name)",
            "CREATE INDEX event_date IF NOT EXISTS FOR (e:Event) ON (e.date)",
        ]

        for index in indexes:
            await session.run(index)
