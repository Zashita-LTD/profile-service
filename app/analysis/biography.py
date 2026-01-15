"""AI Biography Generator - creates compelling life stories from graph facts."""

import json
from typing import Optional
from uuid import uuid4

import google.generativeai as genai

from app.config import get_settings
from app.graph.queries import GraphQueries


BIOGRAPHY_PROMPT_TEMPLATE = """
Ты профессиональный биограф. На основе представленных фактов о человеке создай связный, увлекательный текст биографии.

ФАКТЫ О ЧЕЛОВЕКЕ:

Имя: {name}
Локация: {location}
Описание: {bio}

КАРЬЕРА:
{career_text}

НАВЫКИ:
{skills_text}

ИНТЕРЕСЫ:
{interests_text}

СВЯЗИ (близкие контакты):
{connections_text}

---

ТРЕБОВАНИЯ К БИОГРАФИИ:
- Стиль: {style}
- Язык: {language}
- Создай связный текст, объединяющий факты в историю жизни
- Покажи причинно-следственные связи в карьере
- Упомяни ключевые навыки и как они развивались
- Отрази интересы и их связь с карьерой/личностью
- Упомяни важные связи (коллеги, партнёры)
- НЕ выдумывай факты, которых нет в исходных данных
- Длина: 3-5 абзацев

СТИЛИ:
- professional: Формальный, для резюме/LinkedIn
- casual: Неформальный, дружеский тон
- detailed: Подробный, с деталями и нюансами
- executive: Краткий, для презентаций руководству

Напиши биографию:
"""


class BiographyGenerator:
    """Generate biographical stories using AI."""
    
    def __init__(self):
        """Initialize generator."""
        self.settings = get_settings()
        self._init_gemini()
    
    def _init_gemini(self):
        """Initialize Gemini API."""
        if self.settings.gemini_api_key:
            genai.configure(api_key=self.settings.gemini_api_key)
            self.model = genai.GenerativeModel(self.settings.gemini_model)
        else:
            self.model = None
    
    async def generate(
        self,
        person_id: str,
        style: str = "professional",
        language: str = "ru",
    ) -> dict:
        """Generate biography for a person.
        
        Args:
            person_id: Person ID in graph
            style: Biography style (professional, casual, detailed, executive)
            language: Output language (ru, en)
            
        Returns:
            Dictionary with biography content and metadata
        """
        # Get all facts from graph
        facts = await GraphQueries.get_all_facts(person_id)
        
        if not facts:
            return {
                "id": str(uuid4()),
                "content": "Недостаточно данных для генерации биографии.",
                "model_used": "none",
                "facts_count": 0,
            }
        
        # Format facts for prompt
        prompt = self._build_prompt(facts, style, language)
        
        # Generate with AI
        if self.model:
            content, model_used = await self._generate_with_gemini(prompt)
        else:
            content = self._generate_fallback(facts, style)
            model_used = "template"
        
        # Count facts
        facts_count = (
            len(facts.get("career", []))
            + len(facts.get("skills", []))
            + len(facts.get("interests", []))
            + len(facts.get("connections", []))
        )
        
        # Save to PostgreSQL
        biography_id = await self._save_biography(
            person_id=person_id,
            content=content,
            style=style,
            language=language,
            model_used=model_used,
            facts_count=facts_count,
        )
        
        return {
            "id": biography_id,
            "content": content,
            "model_used": model_used,
            "facts_count": facts_count,
        }
    
    def _build_prompt(self, facts: dict, style: str, language: str) -> str:
        """Build prompt from facts."""
        person = facts.get("person", {})
        
        # Format career
        career_items = []
        for c in facts.get("career", []):
            period = f"{c.get('since', '?')}"
            if c.get("until"):
                period += f"-{c['until']}"
            else:
                period += " - настоящее время"
            career_items.append(f"- {c.get('role', 'Сотрудник')} в {c.get('company', '?')} ({period})")
        career_text = "\n".join(career_items) if career_items else "Нет данных"
        
        # Format skills
        skill_items = []
        for s in facts.get("skills", []):
            level = s.get("level", "")
            years = f", {s.get('years')} лет опыта" if s.get("years") else ""
            skill_items.append(f"- {s.get('skill', '?')} ({level}{years})")
        skills_text = "\n".join(skill_items) if skill_items else "Нет данных"
        
        # Format interests
        interest_items = [f"- {i.get('interest', '?')}" for i in facts.get("interests", [])]
        interests_text = "\n".join(interest_items) if interest_items else "Нет данных"
        
        # Format connections
        conn_items = []
        for c in facts.get("connections", []):
            context = f" ({c.get('context', '')})" if c.get("context") else ""
            since = f" с {c.get('since')}" if c.get("since") else ""
            conn_items.append(f"- {c.get('name', '?')}{context}{since}")
        connections_text = "\n".join(conn_items) if conn_items else "Нет данных"
        
        return BIOGRAPHY_PROMPT_TEMPLATE.format(
            name=person.get("name", "Неизвестно"),
            location=person.get("location", "Не указано"),
            bio=person.get("bio", "Не указано"),
            career_text=career_text,
            skills_text=skills_text,
            interests_text=interests_text,
            connections_text=connections_text,
            style=style,
            language=language,
        )
    
    async def _generate_with_gemini(self, prompt: str) -> tuple[str, str]:
        """Generate using Gemini API."""
        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.7,
                    max_output_tokens=2000,
                ),
            )
            return response.text, self.settings.gemini_model
        except Exception as e:
            # Fallback to template if AI fails
            return f"Ошибка генерации: {str(e)}", "error"
    
    def _generate_fallback(self, facts: dict, style: str) -> str:
        """Generate simple biography without AI."""
        person = facts.get("person", {})
        name = person.get("name", "Человек")
        
        parts = [f"{name}"]
        
        if person.get("location"):
            parts[0] += f" из {person['location']}"
        parts[0] += "."
        
        # Career
        career = facts.get("career", [])
        if career:
            current = next((c for c in career if not c.get("until")), None)
            if current:
                parts.append(
                    f"В настоящее время работает {current.get('role', '')} "
                    f"в компании {current.get('company', '')}."
                )
            if len(career) > 1:
                parts.append(f"За карьеру сменил {len(career)} мест работы.")
        
        # Skills
        skills = facts.get("skills", [])
        if skills:
            skill_names = [s.get("skill", "") for s in skills[:5]]
            parts.append(f"Владеет навыками: {', '.join(skill_names)}.")
        
        # Interests
        interests = facts.get("interests", [])
        if interests:
            int_names = [i.get("interest", "") for i in interests[:3]]
            parts.append(f"Интересуется: {', '.join(int_names)}.")
        
        return " ".join(parts)
    
    async def _save_biography(
        self,
        person_id: str,
        content: str,
        style: str,
        language: str,
        model_used: str,
        facts_count: int,
    ) -> str:
        """Save biography to PostgreSQL."""
        from app.db.postgres import get_db
        from app.db.models import Biography
        
        biography = Biography(
            person_id=person_id,
            content=content,
            style=style,
            language=language,
            model_used=model_used,
            facts_count=facts_count,
        )
        
        async with get_db() as session:
            session.add(biography)
            await session.flush()
            return str(biography.id)
