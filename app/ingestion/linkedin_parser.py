"""LinkedIn profile parser."""

import re
from dataclasses import dataclass, field
from typing import Optional

import google.generativeai as genai

from app.config import get_settings


LINKEDIN_ANALYSIS_PROMPT = """
Проанализируй данные профиля LinkedIn и извлеки структурированную информацию.

ДАННЫЕ ПРОФИЛЯ:
---
{profile_data}
---

Извлеки и верни JSON:
{{
    "person": {{
        "name": "ФИО",
        "headline": "заголовок профиля",
        "location": "локация",
        "bio": "краткое описание (About)"
    }},
    "current_position": {{
        "company": "текущая компания",
        "role": "должность",
        "since": год_начала
    }},
    "experience": [
        {{
            "company": "компания",
            "role": "должность",
            "since": год_начала,
            "until": год_окончания,
            "description": "описание"
        }}
    ],
    "education": [
        {{
            "institution": "учебное заведение",
            "degree": "степень",
            "field": "направление",
            "year": год
        }}
    ],
    "skills": ["навык1", "навык2"],
    "connections_count": число_контактов,
    "recommendations_count": число_рекомендаций
}}

Верни ТОЛЬКО JSON:
"""


@dataclass
class LinkedInProfile:
    """Parsed LinkedIn profile data."""
    
    # Person info
    name: Optional[str] = None
    headline: Optional[str] = None
    location: Optional[str] = None
    bio: Optional[str] = None
    linkedin_url: Optional[str] = None
    
    # Current position
    current_company: Optional[str] = None
    current_role: Optional[str] = None
    
    # Experience
    experience: list[dict] = field(default_factory=list)
    
    # Education
    education: list[dict] = field(default_factory=list)
    
    # Skills (list of skill names)
    skills: list[str] = field(default_factory=list)
    
    # Network stats
    connections_count: int = 0
    recommendations_count: int = 0


class LinkedInParser:
    """Parse LinkedIn profiles to extract information."""
    
    def __init__(self):
        """Initialize parser."""
        self.settings = get_settings()
        self._init_gemini()
    
    def _init_gemini(self):
        """Initialize Gemini API."""
        if self.settings.gemini_api_key:
            genai.configure(api_key=self.settings.gemini_api_key)
            self.model = genai.GenerativeModel(self.settings.gemini_model)
        else:
            self.model = None
    
    async def parse(self, profile_data: str | dict) -> LinkedInProfile:
        """Parse LinkedIn profile data.
        
        Args:
            profile_data: Either raw text or dict from LinkedIn API
            
        Returns:
            LinkedInProfile with extracted information
        """
        if isinstance(profile_data, dict):
            return self._parse_api_response(profile_data)
        
        if self.model:
            return await self._parse_with_ai(profile_data)
        else:
            return self._parse_heuristic(profile_data)
    
    def _parse_api_response(self, data: dict) -> LinkedInProfile:
        """Parse structured LinkedIn API response."""
        profile = LinkedInProfile()
        
        # Basic info
        profile.name = f"{data.get('firstName', '')} {data.get('lastName', '')}".strip()
        profile.headline = data.get("headline")
        profile.location = data.get("location", {}).get("name")
        profile.bio = data.get("summary")
        
        # Experience
        positions = data.get("positions", {}).get("values", [])
        for pos in positions:
            job = {
                "company": pos.get("company", {}).get("name"),
                "role": pos.get("title"),
                "since": pos.get("startDate", {}).get("year"),
                "until": pos.get("endDate", {}).get("year"),
                "description": pos.get("summary"),
            }
            profile.experience.append(job)
            
            if pos.get("isCurrent"):
                profile.current_company = job["company"]
                profile.current_role = job["role"]
        
        # Education
        educations = data.get("educations", {}).get("values", [])
        for edu in educations:
            profile.education.append({
                "institution": edu.get("schoolName"),
                "degree": edu.get("degree"),
                "field": edu.get("fieldOfStudy"),
                "year": edu.get("endDate", {}).get("year"),
            })
        
        # Skills
        skills = data.get("skills", {}).get("values", [])
        profile.skills = [s.get("skill", {}).get("name") for s in skills if s.get("skill")]
        
        # Stats
        profile.connections_count = data.get("numConnections", 0)
        
        return profile
    
    async def _parse_with_ai(self, profile_text: str) -> LinkedInProfile:
        """Parse using Gemini AI."""
        import json
        
        prompt = LINKEDIN_ANALYSIS_PROMPT.format(profile_data=profile_text)
        
        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.1,
                    max_output_tokens=2000,
                ),
            )
            
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            
            data = json.loads(text)
            person = data.get("person", {})
            current = data.get("current_position", {})
            
            return LinkedInProfile(
                name=person.get("name"),
                headline=person.get("headline"),
                location=person.get("location"),
                bio=person.get("bio"),
                current_company=current.get("company"),
                current_role=current.get("role"),
                experience=data.get("experience", []),
                education=data.get("education", []),
                skills=data.get("skills", []),
                connections_count=data.get("connections_count", 0),
                recommendations_count=data.get("recommendations_count", 0),
            )
        except Exception as e:
            print(f"LinkedIn AI parsing error: {e}")
            return self._parse_heuristic(profile_text)
    
    def _parse_heuristic(self, profile_text: str) -> LinkedInProfile:
        """Parse using regex patterns."""
        profile = LinkedInProfile()
        
        # Try to extract LinkedIn URL
        linkedin_pattern = r'linkedin\.com/in/[\w\-]+'
        urls = re.findall(linkedin_pattern, profile_text)
        if urls:
            profile.linkedin_url = f"https://www.{urls[0]}"
        
        # Extract connections count
        conn_pattern = r'(\d+)\+?\s*(connections|контакт)'
        conn_match = re.search(conn_pattern, profile_text, re.IGNORECASE)
        if conn_match:
            profile.connections_count = int(conn_match.group(1))
        
        return profile
    
    async def import_to_graph(self, profile_data: str | dict, linkedin_url: Optional[str] = None) -> dict:
        """Parse LinkedIn profile and create/update person in graph.
        
        Args:
            profile_data: LinkedIn profile data
            linkedin_url: Optional LinkedIn URL
            
        Returns:
            Dictionary with person ID and status
        """
        data = await self.parse(profile_data)
        
        if linkedin_url:
            data.linkedin_url = linkedin_url
        
        result = {
            "parsed": data,
            "person_id": None,
            "created": False,
            "updated": False,
        }
        
        if not data.name:
            return result
        
        from app.graph.queries import GraphQueries
        from app.db.neo4j import Neo4jDB
        
        # Create person
        person = await GraphQueries.create_person(
            name=data.name,
            location=data.location,
            bio=data.bio or data.headline,
        )
        result["person_id"] = person.id
        result["created"] = True
        
        person_id = person.id
        
        # Add experience to graph
        async with Neo4jDB.session() as session:
            for job in data.experience:
                if not job.get("company"):
                    continue
                    
                await session.run("""
                    MERGE (c:Company {name: $company})
                    ON CREATE SET c.id = randomUUID(), c.created_at = datetime()
                    WITH c
                    MATCH (p:Person {id: $person_id})
                    MERGE (p)-[r:WORKS_AT]->(c)
                    SET r.role = $role,
                        r.since = $since,
                        r.until = $until,
                        r.is_current = $is_current
                """,
                    company=job["company"],
                    person_id=person_id,
                    role=job.get("role", ""),
                    since=job.get("since"),
                    until=job.get("until"),
                    is_current=job.get("until") is None,
                )
            
            # Add skills
            for skill_name in data.skills:
                if not skill_name:
                    continue
                await session.run("""
                    MERGE (s:Skill {name: $name})
                    WITH s
                    MATCH (p:Person {id: $person_id})
                    MERGE (p)-[r:HAS_SKILL]->(s)
                    SET r.level = 'intermediate',
                        r.source = 'linkedin'
                """,
                    name=skill_name,
                    person_id=person_id,
                )
        
        # Save document to PostgreSQL
        from app.db.postgres import get_db
        from app.db.models import PersonDocument
        import json
        
        async with get_db() as db_session:
            doc = PersonDocument(
                person_id=person_id,
                doc_type="linkedin",
                title=f"LinkedIn - {data.name}",
                source_url=data.linkedin_url,
                raw_content=json.dumps(profile_data) if isinstance(profile_data, dict) else profile_data,
                parsed_data={
                    "headline": data.headline,
                    "experience": data.experience,
                    "education": data.education,
                    "skills": data.skills,
                    "connections": data.connections_count,
                },
            )
            db_session.add(doc)
        
        return result
