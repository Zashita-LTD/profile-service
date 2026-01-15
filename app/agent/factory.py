"""Agent Factory - Creates and configures personal AI agents."""

import json
import logging
from typing import Optional
from uuid import UUID

from app.config import get_settings
from app.db.neo4j import Neo4jDB
from app.agent.models import (
    UserAgent,
    AgentRole,
    PersonalityTraits,
)

logger = logging.getLogger("agent_factory")


# System prompt template
SYSTEM_PROMPT_TEMPLATE = """Ты — персональный AI-агент {agent_name}.

## Твоя роль
{role_description}

## О твоём хозяине
{user_profile}

## Личностные черты
{personality_description}

## Предпочтения
- Любимые бренды: {preferred_brands}
- Предпочитаемые стили: {preferred_styles}
- Интересы: {interests}

## Правила поведения
1. Всегда действуй в интересах своего хозяина
2. Учитывай его предпочтения при принятии решений
3. {role_specific_rules}
4. Будь {formality_style} в общении
5. При торге {negotiation_style}

## Инструменты
Ты можешь использовать следующие инструменты:
- search_products: Поиск товаров в каталоге
- get_price: Получение цены товара
- send_message: Отправка сообщения другому агенту
- make_offer: Сделать предложение продавцу
- accept_offer: Принять предложение
- reject_offer: Отклонить предложение
- request_delivery: Запросить доставку
- confirm_payment: Подтвердить оплату

Отвечай на русском языке.
"""

ROLE_DESCRIPTIONS = {
    AgentRole.BUYER: "Ты покупатель. Твоя задача — найти лучшие товары по лучшим ценам для своего хозяина.",
    AgentRole.SELLER: "Ты продавец. Твоя задача — продать товары с максимальной выгодой, сохраняя репутацию.",
    AgentRole.ASSISTANT: "Ты персональный помощник. Твоя задача — помогать хозяину в повседневных делах.",
    AgentRole.NEGOTIATOR: "Ты переговорщик. Твоя задача — вести переговоры и добиваться лучших условий.",
    AgentRole.RESEARCHER: "Ты исследователь. Твоя задача — находить информацию и анализировать данные.",
}

ROLE_RULES = {
    AgentRole.BUYER: "Не превышай бюджет без разрешения. Проверяй надежность продавцов.",
    AgentRole.SELLER: "Не продавай ниже себестоимости. Предлагай дополнительные услуги.",
    AgentRole.ASSISTANT: "Спрашивай уточнения, если задача неясна.",
    AgentRole.NEGOTIATOR: "Никогда не соглашайся на первое предложение. Ищи win-win решения.",
    AgentRole.RESEARCHER: "Проверяй факты из нескольких источников.",
}


class AgentFactory:
    """Factory for creating and configuring personal AI agents."""
    
    def __init__(self):
        self.settings = get_settings()
    
    async def create_agent(
        self,
        user_id: UUID,
        name: Optional[str] = None,
        role: AgentRole = AgentRole.ASSISTANT,
    ) -> UserAgent:
        """Create a new agent for user.
        
        Args:
            user_id: User's UUID
            name: Optional agent name
            role: Agent role
            
        Returns:
            Configured UserAgent
        """
        # Get user profile from Neo4j
        profile = await self._get_user_profile(user_id)
        
        # Extract personality traits from profile
        personality = self._extract_personality(profile)
        
        # Get preferences from Taste Graph
        preferences = await self._get_user_preferences(user_id)
        
        # Generate system prompt
        system_prompt = self._build_system_prompt(
            name=name or profile.get("name", "Agent"),
            role=role,
            profile=profile,
            personality=personality,
            preferences=preferences,
        )
        
        # Create agent
        agent = UserAgent(
            user_id=user_id,
            name=name or f"{profile.get('name', 'User')}'s Agent",
            role=role,
            personality=personality,
            system_prompt=system_prompt,
            context_summary=self._build_context_summary(profile, preferences),
            preferred_brands=preferences.get("brands", []),
            preferred_styles=preferences.get("styles", []),
        )
        
        # Save agent to Neo4j
        await self._save_agent(agent)
        
        logger.info(f"Created agent {agent.id} for user {user_id}")
        return agent
    
    async def get_agent(self, user_id: UUID) -> Optional[UserAgent]:
        """Get existing agent for user."""
        try:
            async with Neo4jDB.session() as session:
                result = await session.run("""
                    MATCH (p:Person {id: $user_id})-[:HAS_AGENT]->(a:Agent)
                    RETURN a
                """, {"user_id": str(user_id)})
                
                record = await result.single()
                if record:
                    data = dict(record["a"])
                    return UserAgent(
                        id=UUID(data["id"]),
                        user_id=user_id,
                        name=data.get("name", ""),
                        role=AgentRole(data.get("role", "assistant")),
                        system_prompt=data.get("system_prompt", ""),
                        context_summary=data.get("context_summary", ""),
                        is_active=data.get("is_active", True),
                    )
                return None
        except Exception as e:
            logger.error(f"Failed to get agent: {e}")
            return None
    
    async def update_agent(self, agent: UserAgent) -> UserAgent:
        """Update agent with fresh context from user profile."""
        
        # Refresh profile and preferences
        profile = await self._get_user_profile(agent.user_id)
        preferences = await self._get_user_preferences(agent.user_id)
        
        # Rebuild system prompt
        agent.system_prompt = self._build_system_prompt(
            name=agent.name,
            role=agent.role,
            profile=profile,
            personality=agent.personality,
            preferences=preferences,
        )
        
        agent.context_summary = self._build_context_summary(profile, preferences)
        agent.preferred_brands = preferences.get("brands", [])
        agent.preferred_styles = preferences.get("styles", [])
        
        # Save updated agent
        await self._save_agent(agent)
        
        return agent
    
    async def _get_user_profile(self, user_id: UUID) -> dict:
        """Get user profile from Neo4j."""
        try:
            async with Neo4jDB.session() as session:
                result = await session.run("""
                    MATCH (p:Person {id: $user_id})
                    OPTIONAL MATCH (p)-[:WORKS_AT]->(c:Company)
                    RETURN p, collect(c.name) as companies
                """, {"user_id": str(user_id)})
                
                record = await result.single()
                if record:
                    person = dict(record["p"])
                    person["companies"] = record["companies"]
                    return person
                return {"name": "User", "companies": []}
        except Exception as e:
            logger.error(f"Failed to get user profile: {e}")
            return {"name": "User"}
    
    async def _get_user_preferences(self, user_id: UUID) -> dict:
        """Get user preferences from Taste Graph."""
        preferences = {
            "brands": [],
            "styles": [],
            "concepts": [],
            "lifestyle": [],
        }
        
        try:
            async with Neo4jDB.session() as session:
                # Get brands
                brands_result = await session.run("""
                    MATCH (p:Person {id: $user_id})-[r:WEARS]->(b:Brand)
                    RETURN b.name as name, r.confidence as confidence
                    ORDER BY r.confidence DESC
                    LIMIT 10
                """, {"user_id": str(user_id)})
                
                records = await brands_result.data()
                preferences["brands"] = [r["name"] for r in records]
                
                # Get concepts/styles
                concepts_result = await session.run("""
                    MATCH (p:Person {id: $user_id})-[r:LIKES]->(c:Concept)
                    RETURN c.name as name, c.category as category, r.strength as strength
                    ORDER BY r.strength DESC
                    LIMIT 15
                """, {"user_id": str(user_id)})
                
                records = await concepts_result.data()
                preferences["concepts"] = records
                preferences["styles"] = [
                    r["name"] for r in records 
                    if r.get("category") in ("style", "taste")
                ]
                
                # Get lifestyle
                lifestyle_result = await session.run("""
                    MATCH (p:Person {id: $user_id})-[r:HAS_LIFESTYLE]->(l:Lifestyle)
                    RETURN l.name as name, l.category as category
                    ORDER BY r.confidence DESC
                    LIMIT 10
                """, {"user_id": str(user_id)})
                
                records = await lifestyle_result.data()
                preferences["lifestyle"] = [r["name"] for r in records]
                
                # Get habits (from Life Stream)
                habits_result = await session.run("""
                    MATCH (p:Person {id: $user_id})-[:HAS_HABIT]->(h:Habit)
                    RETURN h.name as name, h.description as description
                    LIMIT 10
                """, {"user_id": str(user_id)})
                
                records = await habits_result.data()
                preferences["habits"] = records
                
        except Exception as e:
            logger.error(f"Failed to get preferences: {e}")
        
        return preferences
    
    def _extract_personality(self, profile: dict) -> PersonalityTraits:
        """Extract personality traits from profile."""
        traits = PersonalityTraits()
        
        # Use profile hints if available
        if profile.get("personality_type"):
            traits.custom_traits["personality_type"] = profile["personality_type"]
        
        if profile.get("communication_style"):
            style = profile["communication_style"].lower()
            if "формальн" in style:
                traits.formality = 0.8
            elif "дружеск" in style or "неформальн" in style:
                traits.formality = 0.3
        
        if profile.get("decision_making"):
            decision = profile["decision_making"].lower()
            if "аналитик" in decision:
                traits.risk_tolerance = 0.3
            elif "интуит" in decision:
                traits.risk_tolerance = 0.7
        
        return traits
    
    def _build_system_prompt(
        self,
        name: str,
        role: AgentRole,
        profile: dict,
        personality: PersonalityTraits,
        preferences: dict,
    ) -> str:
        """Build system prompt from template."""
        
        # Formality style
        if personality.formality > 0.7:
            formality_style = "формальным и вежливым"
        elif personality.formality < 0.3:
            formality_style = "неформальным и дружелюбным"
        else:
            formality_style = "сбалансированным"
        
        # Negotiation style
        if personality.aggressiveness > 0.7:
            negotiation_style = "торгуйся агрессивно, не уступай легко"
        elif personality.aggressiveness < 0.3:
            negotiation_style = "будь мягким, ищи компромиссы"
        else:
            negotiation_style = "будь настойчивым, но разумным"
        
        # User profile description
        user_profile_parts = []
        if profile.get("name"):
            user_profile_parts.append(f"Имя: {profile['name']}")
        if profile.get("bio"):
            user_profile_parts.append(f"О себе: {profile['bio']}")
        if profile.get("companies"):
            user_profile_parts.append(f"Работает в: {', '.join(profile['companies'])}")
        if profile.get("location"):
            user_profile_parts.append(f"Локация: {profile['location']}")
        
        # Interests from concepts
        interests = [c["name"] for c in preferences.get("concepts", [])]
        
        return SYSTEM_PROMPT_TEMPLATE.format(
            agent_name=name,
            role_description=ROLE_DESCRIPTIONS.get(role, ROLE_DESCRIPTIONS[AgentRole.ASSISTANT]),
            user_profile="\n".join(user_profile_parts) or "Информация о пользователе недоступна",
            personality_description=self._describe_personality(personality),
            preferred_brands=", ".join(preferences.get("brands", [])) or "не определены",
            preferred_styles=", ".join(preferences.get("styles", [])) or "не определены",
            interests=", ".join(interests[:10]) or "не определены",
            role_specific_rules=ROLE_RULES.get(role, ""),
            formality_style=formality_style,
            negotiation_style=negotiation_style,
        )
    
    def _describe_personality(self, personality: PersonalityTraits) -> str:
        """Generate personality description."""
        parts = []
        
        if personality.formality > 0.7:
            parts.append("Предпочитает формальное общение")
        elif personality.formality < 0.3:
            parts.append("Предпочитает неформальное общение")
        
        if personality.price_sensitivity > 0.7:
            parts.append("Очень чувствителен к ценам")
        elif personality.price_sensitivity < 0.3:
            parts.append("Качество важнее цены")
        
        if personality.speed_priority > 0.7:
            parts.append("Ценит скорость")
        elif personality.speed_priority < 0.3:
            parts.append("Предпочитает тщательность")
        
        for trait, value in personality.custom_traits.items():
            parts.append(f"{trait}: {value}")
        
        return "; ".join(parts) if parts else "Стандартный профиль"
    
    def _build_context_summary(self, profile: dict, preferences: dict) -> str:
        """Build short context summary for agent."""
        parts = []
        
        if profile.get("name"):
            parts.append(f"Пользователь: {profile['name']}")
        
        if preferences.get("brands"):
            parts.append(f"Бренды: {', '.join(preferences['brands'][:5])}")
        
        if preferences.get("styles"):
            parts.append(f"Стили: {', '.join(preferences['styles'][:5])}")
        
        if preferences.get("habits"):
            habits = [h["name"] for h in preferences["habits"][:3]]
            parts.append(f"Привычки: {', '.join(habits)}")
        
        return " | ".join(parts)
    
    async def _save_agent(self, agent: UserAgent) -> None:
        """Save agent to Neo4j."""
        try:
            async with Neo4jDB.session() as session:
                await session.run("""
                    MATCH (p:Person {id: $user_id})
                    MERGE (a:Agent {id: $agent_id})
                    ON CREATE SET
                        a.name = $name,
                        a.role = $role,
                        a.system_prompt = $system_prompt,
                        a.context_summary = $context_summary,
                        a.is_active = $is_active,
                        a.created_at = datetime()
                    ON MATCH SET
                        a.system_prompt = $system_prompt,
                        a.context_summary = $context_summary,
                        a.updated_at = datetime()
                    MERGE (p)-[:HAS_AGENT]->(a)
                """, {
                    "user_id": str(agent.user_id),
                    "agent_id": str(agent.id),
                    "name": agent.name,
                    "role": agent.role.value,
                    "system_prompt": agent.system_prompt,
                    "context_summary": agent.context_summary,
                    "is_active": agent.is_active,
                })
        except Exception as e:
            logger.error(f"Failed to save agent: {e}")
            raise
