"""Graph queries repository for complex Neo4j operations."""

from typing import Optional
from uuid import UUID

from ..database import Neo4jDatabase
from ..models.relationships import ConnectionResponse, GraphPath, PathNode, PathRelationship


class GraphRepository:
    """Repository for complex graph queries."""

    @staticmethod
    async def get_connections(
        person_id: UUID, min_strength: float = 0.0, limit: int = 50
    ) -> list[ConnectionResponse]:
        """Get all connections for a person."""
        query = """
        MATCH (p:Person {id: $person_id})-[r:KNOWS]-(other:Person)
        WHERE r.strength >= $min_strength
        RETURN other.id as person_id,
               other.name as person_name,
               'KNOWS' as relationship_type,
               r.strength as strength,
               r.context as context
        ORDER BY r.strength DESC
        LIMIT $limit
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(
                query,
                person_id=str(person_id),
                min_strength=min_strength,
                limit=limit,
            )
            records = await result.data()

            return [
                ConnectionResponse(
                    person_id=UUID(r["person_id"]),
                    person_name=r["person_name"],
                    relationship_type=r["relationship_type"],
                    strength=r["strength"],
                    context=r["context"],
                )
                for r in records
            ]

    @staticmethod
    async def get_shortest_path(
        person1_id: UUID, person2_id: UUID, max_depth: int = 6
    ) -> Optional[GraphPath]:
        """Find shortest path between two persons."""
        query = f"""
        MATCH path = shortestPath(
            (a:Person {{id: $person1_id}})-[*1..{max_depth}]-(b:Person {{id: $person2_id}})
        )
        RETURN path
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(
                query,
                person1_id=str(person1_id),
                person2_id=str(person2_id),
            )
            record = await result.single()

            if not record:
                return None

            path = record["path"]
            nodes = []
            relationships = []

            for node in path.nodes:
                labels = list(node.labels)
                nodes.append(
                    PathNode(
                        id=node.get("id", str(node.element_id)),
                        label=labels[0] if labels else "Unknown",
                        name=node.get("name", ""),
                        properties=dict(node),
                    )
                )

            for rel in path.relationships:
                relationships.append(
                    PathRelationship(
                        type=rel.type,
                        properties=dict(rel),
                    )
                )

            return GraphPath(
                nodes=nodes,
                relationships=relationships,
                length=len(relationships),
            )

    @staticmethod
    async def get_common_interests(person_id: UUID, limit: int = 20) -> list[dict]:
        """Find people with common interests."""
        query = """
        MATCH (p1:Person {id: $person_id})-[:INTERESTED_IN]->(i:Interest)<-[:INTERESTED_IN]-(p2:Person)
        WHERE p1 <> p2
        WITH p2, collect(i.name) as common_interests, count(i) as interest_count
        RETURN p2.id as person_id,
               p2.name as person_name,
               common_interests,
               interest_count
        ORDER BY interest_count DESC
        LIMIT $limit
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(
                query, person_id=str(person_id), limit=limit
            )
            records = await result.data()

            return [
                {
                    "person_id": r["person_id"],
                    "person_name": r["person_name"],
                    "common_interests": r["common_interests"],
                    "interest_count": r["interest_count"],
                }
                for r in records
            ]

    @staticmethod
    async def get_colleagues(person_id: UUID) -> list[dict]:
        """Find colleagues (people working at the same company)."""
        query = """
        MATCH (p:Person {id: $person_id})-[:WORKS_AT]->(c:Company)<-[w:WORKS_AT]-(colleague:Person)
        WHERE p <> colleague
        RETURN colleague.id as person_id,
               colleague.name as person_name,
               c.name as company,
               w.role as role
        ORDER BY c.name, colleague.name
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(query, person_id=str(person_id))
            records = await result.data()

            return [
                {
                    "person_id": r["person_id"],
                    "person_name": r["person_name"],
                    "company": r["company"],
                    "role": r["role"],
                }
                for r in records
            ]

    @staticmethod
    async def get_network_stats(person_id: UUID) -> dict:
        """Get network statistics for a person."""
        query = """
        MATCH (p:Person {id: $person_id})
        OPTIONAL MATCH (p)-[:KNOWS]-(direct:Person)
        OPTIONAL MATCH (p)-[:KNOWS]-(:Person)-[:KNOWS]-(indirect:Person)
        WHERE p <> indirect AND NOT (p)-[:KNOWS]-(indirect)
        OPTIONAL MATCH (p)-[:WORKS_AT]->(c:Company)
        OPTIONAL MATCH (p)-[:HAS_SKILL]->(s:Skill)
        OPTIONAL MATCH (p)-[:INTERESTED_IN]->(i:Interest)
        RETURN count(DISTINCT direct) as direct_connections,
               count(DISTINCT indirect) as second_degree_connections,
               count(DISTINCT c) as companies,
               count(DISTINCT s) as skills,
               count(DISTINCT i) as interests
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(query, person_id=str(person_id))
            record = await result.single()

            if not record:
                return {
                    "direct_connections": 0,
                    "second_degree_connections": 0,
                    "companies": 0,
                    "skills": 0,
                    "interests": 0,
                }

            return {
                "direct_connections": record["direct_connections"],
                "second_degree_connections": record["second_degree_connections"],
                "companies": record["companies"],
                "skills": record["skills"],
                "interests": record["interests"],
            }

    @staticmethod
    async def find_influencers(limit: int = 10) -> list[dict]:
        """Find most connected people (influencers)."""
        query = """
        MATCH (p:Person)
        OPTIONAL MATCH (p)-[:KNOWS]-(other:Person)
        WITH p, count(other) as connections
        ORDER BY connections DESC
        LIMIT $limit
        RETURN p.id as person_id,
               p.name as person_name,
               connections
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(query, limit=limit)
            records = await result.data()

            return [
                {
                    "person_id": r["person_id"],
                    "person_name": r["person_name"],
                    "connections": r["connections"],
                }
                for r in records
            ]

    @staticmethod
    async def recommend_connections(person_id: UUID, limit: int = 10) -> list[dict]:
        """Recommend new connections based on mutual connections and interests."""
        query = """
        MATCH (p:Person {id: $person_id})-[:KNOWS]-(friend:Person)-[:KNOWS]-(recommended:Person)
        WHERE p <> recommended AND NOT (p)-[:KNOWS]-(recommended)
        WITH recommended, count(DISTINCT friend) as mutual_friends, collect(DISTINCT friend.name) as mutual_friend_names
        
        OPTIONAL MATCH (p:Person {id: $person_id})-[:INTERESTED_IN]->(i:Interest)<-[:INTERESTED_IN]-(recommended)
        WITH recommended, mutual_friends, mutual_friend_names, count(DISTINCT i) as common_interests
        
        RETURN recommended.id as person_id,
               recommended.name as person_name,
               mutual_friends,
               mutual_friend_names,
               common_interests,
               (mutual_friends * 2 + common_interests) as score
        ORDER BY score DESC
        LIMIT $limit
        """

        async with Neo4jDatabase.get_session() as session:
            result = await session.run(query, person_id=str(person_id), limit=limit)
            records = await result.data()

            return [
                {
                    "person_id": r["person_id"],
                    "person_name": r["person_name"],
                    "mutual_friends": r["mutual_friends"],
                    "mutual_friend_names": r["mutual_friend_names"],
                    "common_interests": r["common_interests"],
                    "score": r["score"],
                }
                for r in records
            ]
