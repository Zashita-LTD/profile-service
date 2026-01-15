"""Memory Search API - Second Brain Interface.

RAG-based search across life events with natural language queries.
Examples:
- "С кем я обедал в прошлую пятницу?"
- "Где я был в выходные?"
- "Сколько я потратил на кофе за месяц?"
"""

import json
from datetime import datetime, timedelta
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from app.config import get_settings
from app.life_stream.clickhouse import ClickHouseDB
from app.life_stream.models import MemorySearchQuery, MemorySearchResult, EventType
from app.db.neo4j import Neo4jDB


router = APIRouter(prefix="/api/v1/search", tags=["Memory Search"])


class MemoryQuestion(BaseModel):
    """Natural language question about life events."""
    question: str = Field(..., min_length=3, max_length=500, examples=[
        "С кем я обедал в прошлую пятницу?",
        "Где я был в выходные?",
        "Сколько я потратил на кофе за месяц?"
    ])
    user_id: UUID
    
    # Optional time constraints
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    
    # Options
    include_reasoning: bool = True


class MemoryAnswer(BaseModel):
    """Answer to memory question."""
    question: str
    answer: str
    confidence: float = Field(..., ge=0, le=1)
    
    # Context
    events_analyzed: int
    time_range: Optional[dict] = None
    
    # Related entities
    locations: list[dict] = Field(default_factory=list)
    people: list[dict] = Field(default_factory=list)
    transactions: list[dict] = Field(default_factory=list)
    
    # AI
    reasoning: Optional[str] = None
    sources: list[str] = Field(default_factory=list)


class MemoryRAG:
    """RAG (Retrieval Augmented Generation) for life memory search."""
    
    def __init__(self):
        self.settings = get_settings()
        self._ai_client = None
    
    async def _get_ai_client(self):
        """Get AI client."""
        if self._ai_client is None:
            if self.settings.gemini_api_key:
                import google.generativeai as genai
                genai.configure(api_key=self.settings.gemini_api_key)
                self._ai_client = genai.GenerativeModel(self.settings.gemini_model)
            elif self.settings.openai_api_key:
                from openai import AsyncOpenAI
                self._ai_client = AsyncOpenAI(api_key=self.settings.openai_api_key)
        return self._ai_client
    
    async def search(self, query: MemoryQuestion) -> MemoryAnswer:
        """Search life memory with RAG.
        
        1. Parse question to understand intent
        2. Retrieve relevant events from ClickHouse
        3. Retrieve related entities from Neo4j
        4. Generate answer using AI
        """
        # Parse time constraints from question
        start_date, end_date = self._parse_time_from_question(
            query.question, query.start_date, query.end_date
        )
        
        # Step 1: Retrieve events from ClickHouse
        events = await self._retrieve_events(
            user_id=query.user_id,
            question=query.question,
            start_date=start_date,
            end_date=end_date,
        )
        
        # Step 2: Retrieve related data from Neo4j
        people = await self._retrieve_people(query.user_id, events)
        patterns = await ClickHouseDB.get_patterns(query.user_id, active_only=True)
        
        # Step 3: Build context for AI
        context = self._build_context(query.question, events, people, patterns)
        
        # Step 4: Generate answer
        answer_text, reasoning = await self._generate_answer(
            query.question, context, query.include_reasoning
        )
        
        # Build response
        locations = self._extract_locations(events)
        people_list = self._extract_people(events, people)
        transactions = self._extract_transactions(events)
        
        return MemoryAnswer(
            question=query.question,
            answer=answer_text,
            confidence=self._calculate_confidence(events, answer_text),
            events_analyzed=len(events),
            time_range={
                "start": start_date.isoformat() if start_date else None,
                "end": end_date.isoformat() if end_date else None,
            },
            locations=locations,
            people=people_list,
            transactions=transactions,
            reasoning=reasoning if query.include_reasoning else None,
            sources=[f"ClickHouse events: {len(events)}", f"Neo4j people: {len(people)}"],
        )
    
    def _parse_time_from_question(
        self,
        question: str,
        start_date: Optional[datetime],
        end_date: Optional[datetime],
    ) -> tuple[datetime, datetime]:
        """Parse time range from natural language question."""
        now = datetime.utcnow()
        
        # Use provided dates if available
        if start_date and end_date:
            return start_date, end_date
        
        q_lower = question.lower()
        
        # Parse common Russian time expressions
        if "сегодня" in q_lower:
            start = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end = now
        elif "вчера" in q_lower:
            yesterday = now - timedelta(days=1)
            start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end = yesterday.replace(hour=23, minute=59, second=59)
        elif "прошлую пятницу" in q_lower or "в пятницу" in q_lower:
            # Find last Friday
            days_since_friday = (now.weekday() - 4) % 7
            if days_since_friday == 0:
                days_since_friday = 7
            friday = now - timedelta(days=days_since_friday)
            start = friday.replace(hour=0, minute=0, second=0, microsecond=0)
            end = friday.replace(hour=23, minute=59, second=59)
        elif "выходные" in q_lower or "weekend" in q_lower:
            # Last weekend
            days_since_sunday = (now.weekday() + 1) % 7
            sunday = now - timedelta(days=days_since_sunday)
            saturday = sunday - timedelta(days=1)
            start = saturday.replace(hour=0, minute=0, second=0, microsecond=0)
            end = sunday.replace(hour=23, minute=59, second=59)
        elif "неделю" in q_lower or "week" in q_lower:
            start = now - timedelta(days=7)
            end = now
        elif "месяц" in q_lower or "month" in q_lower:
            start = now - timedelta(days=30)
            end = now
        else:
            # Default: last 7 days
            start = now - timedelta(days=7)
            end = now
        
        return start, end
    
    async def _retrieve_events(
        self,
        user_id: UUID,
        question: str,
        start_date: datetime,
        end_date: datetime,
    ) -> list[dict]:
        """Retrieve relevant events from ClickHouse."""
        # Determine which event types to query based on question
        event_types = self._infer_event_types(question)
        
        # Get events
        events = await ClickHouseDB.get_events(
            user_id=user_id,
            start_time=start_date,
            end_time=end_date,
            event_types=event_types,
            limit=500,
        )
        
        # Also do text search if question contains specific keywords
        keywords = self._extract_keywords(question)
        if keywords:
            for keyword in keywords[:3]:  # Limit to 3 keywords
                search_results = await ClickHouseDB.search_events_for_rag(
                    user_id=user_id,
                    query_text=keyword,
                    start_time=start_date,
                    end_time=end_date,
                    limit=50,
                )
                # Merge results
                existing_ids = {e["id"] for e in events}
                for event in search_results:
                    if event["id"] not in existing_ids:
                        events.append(event)
        
        return events
    
    def _infer_event_types(self, question: str) -> Optional[list[EventType]]:
        """Infer event types from question."""
        q_lower = question.lower()
        types = []
        
        if any(w in q_lower for w in ["где", "был", "место", "адрес", "локация"]):
            types.append(EventType.GEO)
        if any(w in q_lower for w in ["обедал", "ел", "кафе", "ресторан", "еда"]):
            types.extend([EventType.GEO, EventType.PURCHASE])
        if any(w in q_lower for w in ["кем", "встреча", "встречался", "person"]):
            types.append(EventType.SOCIAL)
        if any(w in q_lower for w in ["потратил", "купил", "покупка", "деньги", "оплата"]):
            types.append(EventType.PURCHASE)
        if any(w in q_lower for w in ["шагов", "сон", "пульс", "здоровье", "активность"]):
            types.append(EventType.HEALTH)
        
        return list(set(types)) if types else None
    
    def _extract_keywords(self, question: str) -> list[str]:
        """Extract search keywords from question."""
        # Remove common words
        stop_words = {
            "я", "мы", "с", "кем", "где", "когда", "как", "сколько",
            "в", "на", "за", "по", "был", "была", "были", "что",
            "the", "a", "is", "was", "were", "with", "who", "where",
        }
        
        words = question.lower().split()
        keywords = [w for w in words if w not in stop_words and len(w) > 2]
        return keywords
    
    async def _retrieve_people(self, user_id: UUID, events: list[dict]) -> list[dict]:
        """Retrieve people related to events from Neo4j."""
        # Extract person IDs from social events
        person_ids = set()
        for event in events:
            if event.get("event_type") == "social":
                payload = event.get("payload", {})
                if isinstance(payload, str):
                    payload = json.loads(payload)
                if "person_id" in payload:
                    person_ids.add(payload["person_id"])
        
        if not person_ids:
            return []
        
        try:
            async with Neo4jDB.session() as session:
                query = """
                    MATCH (p:Person)
                    WHERE p.id IN $person_ids
                    RETURN p.id as id, p.name as name, p.email as email
                """
                result = await session.run(query, {"person_ids": list(person_ids)})
                records = await result.data()
                return records
        except Exception:
            return []
    
    def _build_context(
        self,
        question: str,
        events: list[dict],
        people: list[dict],
        patterns: list[dict],
    ) -> str:
        """Build context string for AI."""
        context_parts = []
        
        # Events summary
        if events:
            context_parts.append(f"## События ({len(events)} записей)")
            # Group by type
            by_type = {}
            for e in events:
                t = e.get("event_type", "unknown")
                if t not in by_type:
                    by_type[t] = []
                by_type[t].append(e)
            
            for event_type, type_events in by_type.items():
                context_parts.append(f"\n### {event_type.upper()} ({len(type_events)})")
                for e in type_events[:10]:  # Limit per type
                    ts = e.get("timestamp", "")
                    payload = e.get("payload", {})
                    if isinstance(payload, str):
                        payload = json.loads(payload) if payload else {}
                    
                    if event_type == "geo":
                        lat, lon = e.get("latitude"), e.get("longitude")
                        context_parts.append(f"- {ts}: Координаты ({lat}, {lon})")
                    elif event_type == "purchase":
                        item = payload.get("item", "")
                        amount = payload.get("amount", 0)
                        place = payload.get("place", "")
                        context_parts.append(f"- {ts}: {item} - {amount} руб. ({place})")
                    elif event_type == "social":
                        action = e.get("event_subtype", "") or payload.get("action", "")
                        person = payload.get("person_name", "") or payload.get("person_id", "")
                        context_parts.append(f"- {ts}: {action} с {person}")
                    else:
                        context_parts.append(f"- {ts}: {json.dumps(payload)[:100]}")
        
        # People
        if people:
            context_parts.append(f"\n## Люди ({len(people)})")
            for p in people:
                context_parts.append(f"- {p.get('name', 'Unknown')} ({p.get('email', '')})")
        
        # Patterns
        if patterns:
            context_parts.append(f"\n## Известные паттерны ({len(patterns)})")
            for p in patterns[:5]:
                context_parts.append(f"- {p.get('name')}: {p.get('description')}")
        
        return "\n".join(context_parts)
    
    async def _generate_answer(
        self,
        question: str,
        context: str,
        include_reasoning: bool,
    ) -> tuple[str, Optional[str]]:
        """Generate answer using AI."""
        ai_client = await self._get_ai_client()
        
        if not ai_client:
            # Fallback without AI
            return self._generate_simple_answer(question, context), None
        
        prompt = f"""Ты - помощник "Второй мозг", который помогает пользователю вспомнить события из его жизни.

Вопрос пользователя: {question}

Контекст (данные из базы событий):
{context}

Задача:
1. Проанализируй контекст и найди ответ на вопрос
2. Дай краткий и полезный ответ на русском языке
3. Если информации недостаточно, скажи об этом честно

{"Также объясни свои рассуждения." if include_reasoning else ""}

Формат ответа:
{{"answer": "твой ответ", "reasoning": "объяснение логики (если требуется)"}}
"""
        
        try:
            if hasattr(ai_client, 'generate_content'):
                # Gemini
                response = await ai_client.generate_content_async(prompt)
                response_text = response.text
            else:
                # OpenAI
                response = await ai_client.chat.completions.create(
                    model=self.settings.openai_model,
                    messages=[{"role": "user", "content": prompt}],
                )
                response_text = response.choices[0].message.content
            
            # Parse response
            try:
                start_idx = response_text.find('{')
                end_idx = response_text.rfind('}') + 1
                if start_idx != -1 and end_idx > start_idx:
                    data = json.loads(response_text[start_idx:end_idx])
                    return data.get("answer", response_text), data.get("reasoning")
            except json.JSONDecodeError:
                pass
            
            return response_text, None
            
        except Exception as e:
            return f"Ошибка при генерации ответа: {str(e)}", None
    
    def _generate_simple_answer(self, question: str, context: str) -> str:
        """Generate simple answer without AI."""
        lines = context.split("\n")
        event_count = sum(1 for l in lines if l.startswith("- "))
        
        if event_count == 0:
            return "К сожалению, за указанный период не найдено подходящих событий."
        
        return f"Найдено {event_count} событий за указанный период. Для подробного анализа настройте AI API (Gemini или OpenAI)."
    
    def _calculate_confidence(self, events: list[dict], answer: str) -> float:
        """Calculate answer confidence based on available data."""
        if not events:
            return 0.1
        
        # More events = more confidence (up to a point)
        event_score = min(0.5, len(events) / 100)
        
        # Check if answer contains hedging
        hedging_words = ["возможно", "вероятно", "не уверен", "недостаточно", "нет данных"]
        hedging_penalty = sum(0.1 for w in hedging_words if w in answer.lower())
        
        return max(0.1, min(0.95, 0.5 + event_score - hedging_penalty))
    
    def _extract_locations(self, events: list[dict]) -> list[dict]:
        """Extract unique locations from events."""
        locations = []
        seen = set()
        
        for e in events:
            lat = e.get("latitude")
            lon = e.get("longitude")
            if lat and lon:
                key = f"{round(lat, 4)},{round(lon, 4)}"
                if key not in seen:
                    seen.add(key)
                    locations.append({
                        "lat": lat,
                        "lon": lon,
                        "timestamp": e.get("timestamp"),
                    })
        
        return locations[:20]  # Limit
    
    def _extract_people(self, events: list[dict], people: list[dict]) -> list[dict]:
        """Extract people from events."""
        people_map = {p.get("id"): p for p in people}
        result = []
        seen_ids = set()
        
        for e in events:
            if e.get("event_type") == "social":
                payload = e.get("payload", {})
                if isinstance(payload, str):
                    payload = json.loads(payload) if payload else {}
                
                person_id = payload.get("person_id")
                if person_id and person_id not in seen_ids:
                    seen_ids.add(person_id)
                    if person_id in people_map:
                        result.append(people_map[person_id])
                    else:
                        result.append({
                            "id": person_id,
                            "name": payload.get("person_name", "Unknown"),
                        })
        
        return result
    
    def _extract_transactions(self, events: list[dict]) -> list[dict]:
        """Extract transactions from events."""
        transactions = []
        
        for e in events:
            if e.get("event_type") in ("purchase", "transaction"):
                payload = e.get("payload", {})
                if isinstance(payload, str):
                    payload = json.loads(payload) if payload else {}
                
                transactions.append({
                    "timestamp": e.get("timestamp"),
                    "item": payload.get("item", ""),
                    "amount": payload.get("amount", 0),
                    "place": payload.get("place", ""),
                    "category": payload.get("category", ""),
                })
        
        return transactions[:50]  # Limit


# Create singleton
_rag = MemoryRAG()


@router.post("/memory", response_model=MemoryAnswer)
async def search_memory(query: MemoryQuestion) -> MemoryAnswer:
    """Search your life memory with natural language.
    
    Ask questions like:
    - "С кем я обедал в прошлую пятницу?"
    - "Где я был в выходные?"
    - "Сколько я потратил на кофе за месяц?"
    
    The system will:
    1. Parse your question to understand time range and intent
    2. Retrieve relevant events from ClickHouse
    3. Find related people from Neo4j graph
    4. Generate an answer using AI (Gemini/OpenAI)
    """
    try:
        return await _rag.search(query)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Memory search failed: {str(e)}")


@router.get("/memory/{user_id}/summary")
async def get_memory_summary(
    user_id: UUID,
    days: Annotated[int, Query(ge=1, le=365)] = 7,
):
    """Get a summary of recent life events.
    
    Returns high-level statistics and notable events.
    """
    try:
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(days=days)
        
        # Get stats
        stats = await ClickHouseDB.get_event_stats(user_id)
        
        # Get patterns
        patterns = await ClickHouseDB.get_patterns(user_id, active_only=True)
        
        # Get recent events sample
        events = await ClickHouseDB.get_events(
            user_id=user_id,
            start_time=start_time,
            end_time=end_time,
            limit=100,
        )
        
        return {
            "user_id": str(user_id),
            "period_days": days,
            "stats": stats,
            "patterns_count": len(patterns),
            "recent_events_sample": len(events),
            "patterns": patterns[:5],  # Top 5 patterns
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get summary: {str(e)}")
