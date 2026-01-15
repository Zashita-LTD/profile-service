"""Resume/CV parser."""

import re
from dataclasses import dataclass, field
from typing import Optional

import google.generativeai as genai

from app.config import get_settings


RESUME_ANALYSIS_PROMPT = """
Проанализируй резюме и извлеки структурированную информацию.

РЕЗЮМЕ:
---
{resume_content}
---

Извлеки и верни JSON:
{{
    "person": {{
        "name": "ФИО",
        "email": "email",
        "phone": "телефон",
        "location": "город/регион",
        "bio": "краткое описание (если есть)"
    }},
    "career": [
        {{
            "company": "название компании",
            "role": "должность",
            "since": год_начала,
            "until": год_окончания_или_null,
            "description": "описание обязанностей"
        }}
    ],
    "education": [
        {{
            "institution": "учебное заведение",
            "degree": "степень/специальность",
            "year": год_окончания
        }}
    ],
    "skills": [
        {{
            "name": "навык",
            "level": "beginner/intermediate/advanced/expert",
            "category": "категория"
        }}
    ],
    "languages": [
        {{"language": "язык", "level": "уровень"}}
    ],
    "certifications": [
        {{"name": "сертификат", "year": год}}
    ]
}}

Верни ТОЛЬКО JSON:
"""


@dataclass
class ResumeData:
    """Parsed resume data."""
    
    # Person info
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    location: Optional[str] = None
    bio: Optional[str] = None
    
    # Career
    career: list[dict] = field(default_factory=list)
    
    # Education
    education: list[dict] = field(default_factory=list)
    
    # Skills
    skills: list[dict] = field(default_factory=list)
    
    # Languages
    languages: list[dict] = field(default_factory=list)
    
    # Certifications
    certifications: list[dict] = field(default_factory=list)


class ResumeParser:
    """Parse resumes to extract structured information."""
    
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
    
    async def parse(self, resume_content: str) -> ResumeData:
        """Parse resume and extract information.
        
        Args:
            resume_content: Resume text content
            
        Returns:
            ResumeData with extracted information
        """
        if self.model:
            return await self._parse_with_ai(resume_content)
        else:
            return self._parse_heuristic(resume_content)
    
    async def _parse_with_ai(self, resume_content: str) -> ResumeData:
        """Parse using Gemini AI."""
        import json
        
        prompt = RESUME_ANALYSIS_PROMPT.format(resume_content=resume_content)
        
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
            
            return ResumeData(
                name=person.get("name"),
                email=person.get("email"),
                phone=person.get("phone"),
                location=person.get("location"),
                bio=person.get("bio"),
                career=data.get("career", []),
                education=data.get("education", []),
                skills=data.get("skills", []),
                languages=data.get("languages", []),
                certifications=data.get("certifications", []),
            )
        except Exception as e:
            print(f"Resume AI parsing error: {e}")
            return self._parse_heuristic(resume_content)
    
    def _parse_heuristic(self, resume_content: str) -> ResumeData:
        """Parse using regex patterns."""
        data = ResumeData()
        
        # Extract email
        email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
        emails = re.findall(email_pattern, resume_content)
        if emails:
            data.email = emails[0]
        
        # Extract phone
        phone_pattern = r'[\+]?[78]?[\s\-]?\(?[0-9]{3}\)?[\s\-]?[0-9]{3}[\s\-]?[0-9]{2}[\s\-]?[0-9]{2}'
        phones = re.findall(phone_pattern, resume_content)
        if phones:
            data.phone = phones[0]
        
        # Extract years (for experience detection)
        year_pattern = r'\b(19|20)\d{2}\b'
        years = re.findall(year_pattern, resume_content)
        
        # Try to extract skills from common sections
        skill_keywords = [
            "python", "java", "javascript", "sql", "excel", "word",
            "управление", "продажи", "переговоры", "bim", "autocad",
        ]
        for kw in skill_keywords:
            if kw.lower() in resume_content.lower():
                data.skills.append({
                    "name": kw.capitalize(),
                    "level": "intermediate",
                    "category": "detected",
                })
        
        return data
    
    async def import_to_graph(self, resume_content: str) -> dict:
        """Parse resume and create/update person in graph.
        
        Args:
            resume_content: Resume text
            
        Returns:
            Dictionary with created person ID and status
        """
        data = await self.parse(resume_content)
        
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
        
        # Check if person exists by email
        existing_person = None
        if data.email:
            existing_person = await GraphQueries.get_person_by_email(data.email)
        
        if existing_person:
            # Update existing
            result["person_id"] = existing_person.id
            result["updated"] = True
        else:
            # Create new person
            person = await GraphQueries.create_person(
                name=data.name,
                email=data.email,
                phone=data.phone,
                location=data.location,
                bio=data.bio,
            )
            result["person_id"] = person.id
            result["created"] = True
        
        person_id = result["person_id"]
        
        # Add career to graph
        async with Neo4jDB.session() as session:
            for job in data.career:
                # Create or get company
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
                    company=job.get("company", "Unknown"),
                    person_id=person_id,
                    role=job.get("role", ""),
                    since=job.get("since"),
                    until=job.get("until"),
                    is_current=job.get("until") is None,
                )
            
            # Add skills
            for skill in data.skills:
                await session.run("""
                    MERGE (s:Skill {name: $name})
                    ON CREATE SET s.category = $category
                    WITH s
                    MATCH (p:Person {id: $person_id})
                    MERGE (p)-[r:HAS_SKILL]->(s)
                    SET r.level = $level
                """,
                    name=skill.get("name", ""),
                    category=skill.get("category"),
                    person_id=person_id,
                    level=skill.get("level", "intermediate"),
                )
        
        # Save document to PostgreSQL
        from app.db.postgres import get_db
        from app.db.models import PersonDocument
        
        async with get_db() as db_session:
            doc = PersonDocument(
                person_id=person_id,
                doc_type="resume",
                title=f"Resume - {data.name}",
                raw_content=resume_content,
                parsed_data={
                    "career": data.career,
                    "education": data.education,
                    "skills": data.skills,
                    "languages": data.languages,
                },
            )
            db_session.add(doc)
        
        return result
