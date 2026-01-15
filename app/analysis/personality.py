"""AI Personality Analyzer - extracts personality traits from communication patterns."""

from typing import Optional

import google.generativeai as genai

from app.config import get_settings
from app.graph.queries import GraphQueries


PERSONALITY_PROMPT = """
Ты психолог-аналитик. На основе представленных данных о человеке определи его психологический профиль.

ДАННЫЕ О ЧЕЛОВЕКЕ:

Имя: {name}
Описание: {bio}

КАРЬЕРНЫЙ ПУТЬ:
{career_summary}

НАВЫКИ:
{skills_summary}

ИНТЕРЕСЫ:
{interests_summary}

ИСТОРИЯ ОБЩЕНИЯ (если есть):
{communication_history}

---

Проанализируй и верни JSON с тремя полями:

1. personality_type - один из типов:
   - "консерватор" - предпочитает стабильность, проверенные решения
   - "новатор" - любит новое, эксперименты
   - "аналитик" - все взвешивает, любит данные
   - "практик" - ориентирован на результат
   - "коммуникатор" - важны отношения и люди

2. communication_style - стиль общения:
   - "формальный" - строгий, деловой
   - "дружеский" - неформальный, открытый  
   - "сдержанный" - краткий, по делу
   - "эмоциональный" - экспрессивный

3. decision_making - как принимает решения:
   - "аналитический" - собирает данные, анализирует
   - "интуитивный" - доверяет чутью
   - "консенсусный" - советуется с другими
   - "быстрый" - принимает решения оперативно

Верни ТОЛЬКО JSON без markdown:
{{"personality_type": "...", "communication_style": "...", "decision_making": "..."}}
"""


class PersonalityAnalyzer:
    """Analyze personality from graph data and communication patterns."""
    
    def __init__(self):
        """Initialize analyzer."""
        self.settings = get_settings()
        self._init_gemini()
    
    def _init_gemini(self):
        """Initialize Gemini API."""
        if self.settings.gemini_api_key:
            genai.configure(api_key=self.settings.gemini_api_key)
            self.model = genai.GenerativeModel(self.settings.gemini_model)
        else:
            self.model = None
    
    async def analyze(self, person_id: str) -> dict:
        """Analyze personality for a person.
        
        Args:
            person_id: Person ID in graph
            
        Returns:
            Dictionary with personality traits
        """
        # Get facts from graph
        facts = await GraphQueries.get_all_facts(person_id)
        
        if not facts:
            return self._default_traits()
        
        # Get communication history from PostgreSQL
        comm_history = await self._get_communication_history(person_id)
        
        # Build prompt
        prompt = self._build_prompt(facts, comm_history)
        
        # Analyze with AI
        if self.model:
            return await self._analyze_with_gemini(prompt)
        else:
            return self._analyze_heuristic(facts)
    
    def _build_prompt(self, facts: dict, comm_history: str) -> str:
        """Build analysis prompt."""
        person = facts.get("person", {})
        
        # Career summary
        career = facts.get("career", [])
        if career:
            career_parts = []
            for c in career:
                career_parts.append(f"- {c.get('role')} в {c.get('company')}")
            career_summary = "\n".join(career_parts)
        else:
            career_summary = "Нет данных"
        
        # Skills summary
        skills = facts.get("skills", [])
        if skills:
            skills_summary = ", ".join(s.get("skill", "") for s in skills)
        else:
            skills_summary = "Нет данных"
        
        # Interests summary
        interests = facts.get("interests", [])
        if interests:
            interests_summary = ", ".join(i.get("interest", "") for i in interests)
        else:
            interests_summary = "Нет данных"
        
        return PERSONALITY_PROMPT.format(
            name=person.get("name", "Неизвестно"),
            bio=person.get("bio", "Не указано"),
            career_summary=career_summary,
            skills_summary=skills_summary,
            interests_summary=interests_summary,
            communication_history=comm_history or "Нет данных",
        )
    
    async def _analyze_with_gemini(self, prompt: str) -> dict:
        """Analyze using Gemini API."""
        import json
        
        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.3,
                    max_output_tokens=500,
                ),
            )
            
            # Parse JSON from response
            text = response.text.strip()
            # Clean up markdown if present
            if text.startswith("```"):
                text = text.split("\n", 1)[1]
                text = text.rsplit("```", 1)[0]
            
            return json.loads(text)
        except Exception as e:
            print(f"Gemini analysis error: {e}")
            return self._default_traits()
    
    def _analyze_heuristic(self, facts: dict) -> dict:
        """Simple heuristic analysis without AI."""
        career = facts.get("career", [])
        skills = facts.get("skills", [])
        interests = facts.get("interests", [])
        
        # Determine personality type based on career stability
        if len(career) <= 2:
            personality_type = "консерватор"
        elif len(career) > 5:
            personality_type = "новатор"
        else:
            personality_type = "практик"
        
        # Determine based on skills
        tech_skills = ["Python", "Excel", "BIM", "AutoCAD", "программирование"]
        has_tech = any(
            any(t.lower() in s.get("skill", "").lower() for t in tech_skills)
            for s in skills
        )
        if has_tech:
            personality_type = "аналитик"
        
        # Communication style based on interests
        social_interests = ["футбол", "рыбалка", "путешествия", "спорт"]
        has_social = any(
            any(s.lower() in i.get("interest", "").lower() for s in social_interests)
            for i in interests
        )
        communication_style = "дружеский" if has_social else "формальный"
        
        # Decision making
        decision_making = "аналитический" if has_tech else "интуитивный"
        
        return {
            "personality_type": personality_type,
            "communication_style": communication_style,
            "decision_making": decision_making,
        }
    
    def _default_traits(self) -> dict:
        """Return default traits."""
        return {
            "personality_type": "практик",
            "communication_style": "сдержанный",
            "decision_making": "аналитический",
        }
    
    async def _get_communication_history(self, person_id: str) -> str:
        """Get communication history from documents."""
        from sqlalchemy import select
        from app.db.postgres import get_db
        from app.db.models import PersonDocument
        
        try:
            async with get_db() as session:
                result = await session.execute(
                    select(PersonDocument)
                    .where(PersonDocument.person_id == person_id)
                    .where(PersonDocument.doc_type == "email")
                    .order_by(PersonDocument.created_at.desc())
                    .limit(10)
                )
                docs = result.scalars().all()
                
                if not docs:
                    return ""
                
                # Extract snippets from emails
                snippets = []
                for doc in docs:
                    parsed = doc.parsed_data or {}
                    if parsed.get("style_notes"):
                        snippets.append(parsed["style_notes"])
                
                return "\n".join(snippets)
        except Exception:
            return ""
    
    def get_recommendation(self, traits: dict) -> str:
        """Get recommendation based on personality."""
        ptype = traits.get("personality_type", "")
        
        recommendations = {
            "консерватор": (
                "Предпочитает надёжных поставщиков с историей. "
                "Не предлагайте стартапы или экспериментальные решения."
            ),
            "новатор": (
                "Открыт к новым продуктам и технологиям. "
                "Можно предлагать инновационные решения."
            ),
            "аналитик": (
                "Важны цифры, данные, сравнения. "
                "Подготовьте детальные расчёты и обоснования."
            ),
            "практик": (
                "Ориентирован на результат. "
                "Покажите конкретную выгоду и сроки."
            ),
            "коммуникатор": (
                "Важны личные отношения. "
                "Уделите время неформальному общению."
            ),
        }
        
        return recommendations.get(ptype, "Стандартный подход.")
