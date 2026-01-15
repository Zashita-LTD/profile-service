"""Email signature and style parser."""

import re
from dataclasses import dataclass
from typing import Optional

import google.generativeai as genai

from app.config import get_settings


EMAIL_ANALYSIS_PROMPT = """
Проанализируй email и извлеки информацию о отправителе.

EMAIL:
---
{email_content}
---

Извлеки и верни JSON:
{{
    "sender": {{
        "name": "Полное имя из подписи",
        "position": "Должность",
        "company": "Компания",
        "phone": "Телефон",
        "email": "Email"
    }},
    "style_analysis": {{
        "formality": "formal/informal/neutral",
        "tone": "friendly/business/cold/warm",
        "verbosity": "brief/moderate/verbose"
    }},
    "extracted_facts": [
        {{"type": "тип факта", "value": "значение"}}
    ]
}}

Типы фактов: skill, interest, preference, relationship, location, achievement

Верни ТОЛЬКО JSON:
"""


@dataclass
class EmailAnalysis:
    """Email analysis result."""
    
    sender_name: Optional[str] = None
    sender_position: Optional[str] = None
    sender_company: Optional[str] = None
    sender_phone: Optional[str] = None
    sender_email: Optional[str] = None
    
    formality: str = "neutral"
    tone: str = "business"
    verbosity: str = "moderate"
    
    facts: list[dict] = None
    
    def __post_init__(self):
        if self.facts is None:
            self.facts = []


class EmailParser:
    """Parse emails to extract information about sender."""
    
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
    
    async def parse(self, email_content: str) -> EmailAnalysis:
        """Parse email and extract information.
        
        Args:
            email_content: Raw email content (body + signature)
            
        Returns:
            EmailAnalysis with extracted information
        """
        if self.model:
            return await self._parse_with_ai(email_content)
        else:
            return self._parse_heuristic(email_content)
    
    async def _parse_with_ai(self, email_content: str) -> EmailAnalysis:
        """Parse using Gemini AI."""
        import json
        
        prompt = EMAIL_ANALYSIS_PROMPT.format(email_content=email_content)
        
        try:
            response = await self.model.generate_content_async(
                prompt,
                generation_config=genai.GenerationConfig(
                    temperature=0.2,
                    max_output_tokens=1000,
                ),
            )
            
            text = response.text.strip()
            if text.startswith("```"):
                text = text.split("\n", 1)[1].rsplit("```", 1)[0]
            
            data = json.loads(text)
            sender = data.get("sender", {})
            style = data.get("style_analysis", {})
            
            return EmailAnalysis(
                sender_name=sender.get("name"),
                sender_position=sender.get("position"),
                sender_company=sender.get("company"),
                sender_phone=sender.get("phone"),
                sender_email=sender.get("email"),
                formality=style.get("formality", "neutral"),
                tone=style.get("tone", "business"),
                verbosity=style.get("verbosity", "moderate"),
                facts=data.get("extracted_facts", []),
            )
        except Exception as e:
            print(f"Email AI parsing error: {e}")
            return self._parse_heuristic(email_content)
    
    def _parse_heuristic(self, email_content: str) -> EmailAnalysis:
        """Parse using regex patterns."""
        analysis = EmailAnalysis()
        
        # Extract email
        email_pattern = r'[\w\.-]+@[\w\.-]+\.\w+'
        emails = re.findall(email_pattern, email_content)
        if emails:
            analysis.sender_email = emails[0]
        
        # Extract phone
        phone_pattern = r'[\+]?[(]?[0-9]{1,3}[)]?[-\s\.]?[(]?[0-9]{1,4}[)]?[-\s\.]?[0-9]{1,4}[-\s\.]?[0-9]{1,9}'
        phones = re.findall(phone_pattern, email_content)
        if phones:
            analysis.sender_phone = phones[0]
        
        # Try to extract name from signature
        lines = email_content.strip().split('\n')
        for i, line in enumerate(lines):
            # Look for "С уважением" or similar
            if any(phrase in line.lower() for phrase in ['с уважением', 'best regards', 'regards']):
                if i + 1 < len(lines):
                    potential_name = lines[i + 1].strip()
                    if potential_name and not '@' in potential_name and not potential_name.startswith('+'):
                        analysis.sender_name = potential_name
                break
        
        # Analyze style
        word_count = len(email_content.split())
        analysis.verbosity = "brief" if word_count < 50 else "verbose" if word_count > 200 else "moderate"
        
        # Check formality
        informal_markers = ['привет', 'здорово', 'hi', 'hey']
        formal_markers = ['уважаемый', 'dear', 'добрый день']
        
        lower_content = email_content.lower()
        if any(m in lower_content for m in informal_markers):
            analysis.formality = "informal"
            analysis.tone = "friendly"
        elif any(m in lower_content for m in formal_markers):
            analysis.formality = "formal"
            analysis.tone = "business"
        
        return analysis
    
    async def extract_and_enrich(self, email_content: str, person_id: Optional[str] = None) -> dict:
        """Extract info from email and add facts to graph.
        
        Args:
            email_content: Email content
            person_id: Optional person ID if known
            
        Returns:
            Dictionary with extracted info and enrichment status
        """
        analysis = await self.parse(email_content)
        
        result = {
            "analysis": analysis,
            "person_id": person_id,
            "enriched": False,
        }
        
        # If we have email and no person_id, try to find person
        if analysis.sender_email and not person_id:
            from app.graph.queries import GraphQueries
            person = await GraphQueries.get_person_by_email(analysis.sender_email)
            if person:
                person_id = person.id
                result["person_id"] = person_id
        
        # If we have person_id, add facts
        if person_id and analysis.facts:
            from app.db.postgres import get_db
            from app.db.models import PersonFact
            
            async with get_db() as session:
                for fact in analysis.facts:
                    fact_record = PersonFact(
                        person_id=person_id,
                        fact_type=fact.get("type", "other"),
                        category="email_extraction",
                        value=fact.get("value", ""),
                        source="email",
                        metadata={
                            "formality": analysis.formality,
                            "tone": analysis.tone,
                        },
                    )
                    session.add(fact_record)
                result["enriched"] = True
        
        return result
