"""Neo4j graph queries."""

from typing import Optional
from uuid import uuid4

from app.db.neo4j import Neo4jDB
from app.graph.nodes import PersonNode, CompanyNode, SkillNode


class GraphQueries:
    """Graph database queries."""
    
    # ==================== PERSON ====================
    
    @staticmethod
    async def create_person(
        name: str,
        email: Optional[str] = None,
        phone: Optional[str] = None,
        location: Optional[str] = None,
        bio: Optional[str] = None,
    ) -> PersonNode:
        """Create a new person."""
        person_id = str(uuid4())
        async with Neo4jDB.session() as session:
            result = await session.run("""
                CREATE (p:Person {
                    id: $id, name: $name, email: $email, phone: $phone,
                    location: $location, bio: $bio,
                    created_at: datetime(), updated_at: datetime()
                })
                RETURN p {.*}
            """, id=person_id, name=name, email=email, phone=phone,
                location=location, bio=bio)
            record = await result.single()
            return PersonNode.from_record(record["p"])
    
    @staticmethod
    async def get_person(person_id: str) -> Optional[PersonNode]:
        """Get person by ID."""
        async with Neo4jDB.session() as session:
            result = await session.run("""
                MATCH (p:Person {id: $id})
                RETURN p {.*}
            """, id=person_id)
            record = await result.single()
            return PersonNode.from_record(record["p"]) if record else None
    
    @staticmethod
    async def get_person_by_email(email: str) -> Optional[PersonNode]:
        """Get person by email."""
        async with Neo4jDB.session() as session:
            result = await session.run("""
                MATCH (p:Person {email: $email})
                RETURN p {.*}
            """, email=email)
            record = await result.single()
            return PersonNode.from_record(record["p"]) if record else None
    
    @staticmethod
    async def update_person_traits(
        person_id: str,
        personality_type: Optional[str] = None,
        communication_style: Optional[str] = None,
        decision_making: Optional[str] = None,
    ) -> Optional[PersonNode]:
        """Update person's personality traits."""
        async with Neo4jDB.session() as session:
            result = await session.run("""
                MATCH (p:Person {id: $id})
                SET p.personality_type = COALESCE($personality_type, p.personality_type),
                    p.communication_style = COALESCE($communication_style, p.communication_style),
                    p.decision_making = COALESCE($decision_making, p.decision_making),
                    p.updated_at = datetime()
                RETURN p {.*}
            """, id=person_id, personality_type=personality_type,
                communication_style=communication_style, decision_making=decision_making)
            record = await result.single()
            return PersonNode.from_record(record["p"]) if record else None
    
    # ==================== CAREER ====================
    
    @staticmethod
    async def get_career(person_id: str) -> list[dict]:
        """Get person's career history."""
        async with Neo4jDB.session() as session:
            result = await session.run("""
                MATCH (p:Person {id: $id})-[r:WORKS_AT]->(c:Company)
                RETURN c {.*} as company, r {.*} as relation
                ORDER BY COALESCE(r.until, 9999) DESC, r.since DESC
            """, id=person_id)
            records = [record async for record in result]
            return [
                {
                    "company": CompanyNode.from_record(r["company"]),
                    "role": r["relation"].get("role"),
                    "since": r["relation"].get("since"),
                    "until": r["relation"].get("until"),
                    "is_current": r["relation"].get("is_current", False),
                }
                for r in records
            ]
    
    # ==================== FRIENDS / CONNECTIONS ====================
    
    @staticmethod
    async def get_friends(person_id: str, depth: int = 1, min_strength: float = 0.0) -> list[dict]:
        """Get person's friends up to specified depth."""
        async with Neo4jDB.session() as session:
            result = await session.run(f"""
                MATCH path = (p:Person {{id: $id}})-[:KNOWS*1..{depth}]-(friend:Person)
                WHERE friend.id <> $id
                WITH friend, min(length(path)) as distance,
                     [r IN relationships(path) | r.strength] as strengths
                WHERE ALL(s IN strengths WHERE s >= $min_strength)
                RETURN friend {{.*}} as person, distance,
                       reduce(avg = 0.0, s IN strengths | avg + s) / size(strengths) as avg_strength
                ORDER BY distance, avg_strength DESC
            """, id=person_id, min_strength=min_strength)
            records = [record async for record in result]
            return [
                {
                    "person": PersonNode.from_record(r["person"]),
                    "distance": r["distance"],
                    "avg_strength": r["avg_strength"],
                }
                for r in records
            ]
    
    @staticmethod
    async def find_path_to_person(from_id: str, to_id: str, max_depth: int = 6) -> Optional[dict]:
        """Find shortest path between two people."""
        async with Neo4jDB.session() as session:
            result = await session.run(f"""
                MATCH path = shortestPath(
                    (a:Person {{id: $from_id}})-[:KNOWS*1..{max_depth}]-(b:Person {{id: $to_id}})
                )
                RETURN [n IN nodes(path) | n {{.*}}] as nodes,
                       [r IN relationships(path) | r {{.*}}] as relations,
                       length(path) as distance
            """, from_id=from_id, to_id=to_id)
            record = await result.single()
            if not record:
                return None
            return {
                "nodes": [PersonNode.from_record(n) for n in record["nodes"]],
                "relations": record["relations"],
                "distance": record["distance"],
            }
    
    # ==================== SKILLS ====================
    
    @staticmethod
    async def get_skills(person_id: str) -> list[dict]:
        """Get person's skills."""
        async with Neo4jDB.session() as session:
            result = await session.run("""
                MATCH (p:Person {id: $id})-[r:HAS_SKILL]->(s:Skill)
                RETURN s {.*} as skill, r {.*} as relation
                ORDER BY r.level DESC, r.years_experience DESC
            """, id=person_id)
            records = [record async for record in result]
            return [
                {
                    "skill": SkillNode.from_record(r["skill"]),
                    "level": r["relation"].get("level"),
                    "years_experience": r["relation"].get("years_experience"),
                }
                for r in records
            ]
    
    @staticmethod
    async def find_experts(
        skill: str,
        location: Optional[str] = None,
        min_level: str = "intermediate",
        limit: int = 10,
    ) -> list[dict]:
        """Find experts with a specific skill."""
        level_order = {"beginner": 1, "intermediate": 2, "advanced": 3, "expert": 4}
        min_level_num = level_order.get(min_level, 2)
        
        async with Neo4jDB.session() as session:
            query = """
                MATCH (p:Person)-[r:HAS_SKILL]->(s:Skill)
                WHERE toLower(s.name) CONTAINS toLower($skill)
            """
            if location:
                query += " AND toLower(p.location) CONTAINS toLower($location)"
            
            query += """
                WITH p, s, r,
                     CASE r.level
                         WHEN 'expert' THEN 4
                         WHEN 'advanced' THEN 3
                         WHEN 'intermediate' THEN 2
                         ELSE 1
                     END as level_num
                WHERE level_num >= $min_level_num
                RETURN p {.*} as person, s {.*} as skill, r {.*} as relation, level_num
                ORDER BY level_num DESC, r.years_experience DESC
                LIMIT $limit
            """
            
            result = await session.run(
                query,
                skill=skill, location=location, min_level_num=min_level_num, limit=limit
            )
            records = [record async for record in result]
            return [
                {
                    "person": PersonNode.from_record(r["person"]),
                    "skill": SkillNode.from_record(r["skill"]),
                    "level": r["relation"].get("level"),
                    "years_experience": r["relation"].get("years_experience"),
                }
                for r in records
            ]
    
    # ==================== INTERESTS ====================
    
    @staticmethod
    async def get_common_interests(person1_id: str, person2_id: str) -> list[str]:
        """Find common interests between two people."""
        async with Neo4jDB.session() as session:
            result = await session.run("""
                MATCH (p1:Person {id: $id1})-[:INTERESTED_IN]->(i:Interest)
                      <-[:INTERESTED_IN]-(p2:Person {id: $id2})
                RETURN i.name as interest
            """, id1=person1_id, id2=person2_id)
            records = [record async for record in result]
            return [r["interest"] for r in records]
    
    # ==================== ANALYTICS ====================
    
    @staticmethod
    async def get_network_stats(person_id: str) -> dict:
        """Get network statistics for a person."""
        async with Neo4jDB.session() as session:
            result = await session.run("""
                MATCH (p:Person {id: $id})
                OPTIONAL MATCH (p)-[:KNOWS]-(direct:Person)
                OPTIONAL MATCH (p)-[:KNOWS*2]-(second:Person)
                WHERE second <> p AND NOT (p)-[:KNOWS]-(second)
                OPTIONAL MATCH (p)-[:WORKS_AT]->(c:Company)
                OPTIONAL MATCH (p)-[:HAS_SKILL]->(s:Skill)
                OPTIONAL MATCH (p)-[:INTERESTED_IN]->(i:Interest)
                RETURN 
                    count(DISTINCT direct) as direct_connections,
                    count(DISTINCT second) as second_degree,
                    count(DISTINCT c) as companies,
                    count(DISTINCT s) as skills,
                    count(DISTINCT i) as interests
            """, id=person_id)
            record = await result.single()
            return {
                "direct_connections": record["direct_connections"],
                "second_degree": record["second_degree"],
                "companies": record["companies"],
                "skills": record["skills"],
                "interests": record["interests"],
                "network_reach": record["direct_connections"] + record["second_degree"],
            }
    
    @staticmethod
    async def get_all_facts(person_id: str) -> dict:
        """Get all facts about a person for biography generation."""
        async with Neo4jDB.session() as session:
            # Get person
            person_result = await session.run("""
                MATCH (p:Person {id: $id})
                RETURN p {.*}
            """, id=person_id)
            person_record = await person_result.single()
            if not person_record:
                return {}
            
            # Get career
            career_result = await session.run("""
                MATCH (p:Person {id: $id})-[r:WORKS_AT]->(c:Company)
                RETURN c.name as company, r.role as role, r.since as since, r.until as until
                ORDER BY COALESCE(r.until, 9999) DESC
            """, id=person_id)
            career = [record async for record in career_result]
            
            # Get skills
            skills_result = await session.run("""
                MATCH (p:Person {id: $id})-[r:HAS_SKILL]->(s:Skill)
                RETURN s.name as skill, r.level as level, r.years_experience as years
            """, id=person_id)
            skills = [record async for record in skills_result]
            
            # Get interests
            interests_result = await session.run("""
                MATCH (p:Person {id: $id})-[:INTERESTED_IN]->(i:Interest)
                RETURN i.name as interest, i.category as category
            """, id=person_id)
            interests = [record async for record in interests_result]
            
            # Get connections
            connections_result = await session.run("""
                MATCH (p:Person {id: $id})-[r:KNOWS]-(friend:Person)
                WHERE r.strength >= 0.7
                RETURN friend.name as name, r.context as context, r.since as since
                ORDER BY r.strength DESC
                LIMIT 10
            """, id=person_id)
            connections = [record async for record in connections_result]
            
            return {
                "person": dict(person_record["p"]),
                "career": [dict(c) for c in career],
                "skills": [dict(s) for s in skills],
                "interests": [dict(i) for i in interests],
                "connections": [dict(c) for c in connections],
            }
