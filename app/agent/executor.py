"""Agent Task Executor - Runs agent tasks with tool use."""

import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Callable, Optional
from uuid import UUID

from app.config import get_settings
from app.db.neo4j import Neo4jDB
from app.agent.models import (
    UserAgent,
    AgentTask,
    AgentMessage,
    MessageRole,
    TaskStatus,
)
from app.agent.factory import AgentFactory

logger = logging.getLogger("agent_executor")


# Tool definitions
AGENT_TOOLS = [
    {
        "name": "search_products",
        "description": "Поиск товаров в каталоге по описанию",
        "parameters": {
            "query": "Поисковый запрос",
            "category": "Категория товара (опционально)",
            "max_price": "Максимальная цена (опционально)",
        }
    },
    {
        "name": "get_product_details",
        "description": "Получить детальную информацию о товаре",
        "parameters": {
            "product_id": "ID товара",
        }
    },
    {
        "name": "compare_products",
        "description": "Сравнить несколько товаров",
        "parameters": {
            "product_ids": "Список ID товаров для сравнения",
        }
    },
    {
        "name": "analyze_image",
        "description": "Проанализировать изображение (стиль, бренды)",
        "parameters": {
            "image_id": "ID изображения из галереи",
        }
    },
    {
        "name": "send_agent_message",
        "description": "Отправить сообщение агенту продавца",
        "parameters": {
            "seller_id": "ID продавца",
            "message": "Текст сообщения",
        }
    },
    {
        "name": "make_purchase_offer",
        "description": "Сделать предложение о покупке",
        "parameters": {
            "product_id": "ID товара",
            "price": "Предлагаемая цена",
            "quantity": "Количество",
        }
    },
    {
        "name": "request_delivery",
        "description": "Запросить доставку",
        "parameters": {
            "order_id": "ID заказа",
            "address": "Адрес доставки",
            "preferred_time": "Предпочтительное время",
        }
    },
    {
        "name": "get_user_preferences",
        "description": "Получить предпочтения пользователя",
        "parameters": {
            "category": "Категория предпочтений (стиль, бренды, бюджет)",
        }
    },
]


class AgentExecutor:
    """Executes agent tasks with AI and tools."""
    
    def __init__(self):
        self.settings = get_settings()
        self._ai_client = None
        self._tools: dict[str, Callable] = {}
        self._register_default_tools()
    
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
    
    def _register_default_tools(self):
        """Register default tool implementations."""
        self._tools = {
            "search_products": self._tool_search_products,
            "get_product_details": self._tool_get_product_details,
            "compare_products": self._tool_compare_products,
            "analyze_image": self._tool_analyze_image,
            "get_user_preferences": self._tool_get_preferences,
            "send_agent_message": self._tool_send_message,
            "make_purchase_offer": self._tool_make_offer,
            "request_delivery": self._tool_request_delivery,
        }
    
    def register_tool(self, name: str, func: Callable):
        """Register custom tool."""
        self._tools[name] = func
    
    async def execute_task(self, task: AgentTask, agent: UserAgent) -> AgentTask:
        """Execute a task for an agent.
        
        Args:
            task: Task to execute
            agent: Agent executing the task
            
        Returns:
            Updated task with results
        """
        logger.info(f"Executing task {task.id} for agent {agent.id}")
        
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        
        # Initialize conversation with system prompt
        task.messages.append(AgentMessage(
            role=MessageRole.SYSTEM,
            content=agent.system_prompt,
        ))
        
        # Add user instruction
        task.messages.append(AgentMessage(
            role=MessageRole.USER,
            content=task.instruction + (f"\n\nКонтекст: {task.context}" if task.context else ""),
        ))
        
        ai_client = await self._get_ai_client()
        if not ai_client:
            task.status = TaskStatus.FAILED
            task.error = "No AI client configured"
            return task
        
        try:
            # Agent loop
            while task.iterations < task.max_iterations:
                task.iterations += 1
                
                # Generate response
                response = await self._generate_response(ai_client, task.messages, agent)
                
                # Check if tool call
                if response.tool_name:
                    # Execute tool
                    tool_result = await self._execute_tool(
                        response.tool_name,
                        response.tool_args or {},
                        agent,
                    )
                    
                    # Add tool result to conversation
                    task.messages.append(AgentMessage(
                        role=MessageRole.TOOL,
                        content=str(tool_result),
                        tool_name=response.tool_name,
                        tool_args=response.tool_args,
                        tool_result=tool_result,
                    ))
                else:
                    # Final response
                    task.messages.append(response)
                    task.result = response.content
                    task.status = TaskStatus.COMPLETED
                    break
                
                task.total_tokens += response.tokens
            
            if task.iterations >= task.max_iterations:
                task.status = TaskStatus.FAILED
                task.error = "Max iterations reached"
                
        except Exception as e:
            logger.error(f"Task execution failed: {e}")
            task.status = TaskStatus.FAILED
            task.error = str(e)
        
        task.completed_at = datetime.utcnow()
        return task
    
    async def _generate_response(
        self,
        ai_client,
        messages: list[AgentMessage],
        agent: UserAgent,
    ) -> AgentMessage:
        """Generate AI response with optional tool use."""
        
        # Build prompt for tool-use capable models
        tools_prompt = "\n\nДоступные инструменты:\n"
        for tool in AGENT_TOOLS:
            tools_prompt += f"- {tool['name']}: {tool['description']}\n"
        
        tools_prompt += """
Если нужно использовать инструмент, ответь в формате:
TOOL: <имя_инструмента>
ARGS: <json с аргументами>

Если задача выполнена, просто дай финальный ответ пользователю.
"""
        
        # Convert messages to format for AI
        conversation = []
        for msg in messages:
            if msg.role == MessageRole.SYSTEM:
                conversation.append({"role": "system", "content": msg.content + tools_prompt})
            elif msg.role == MessageRole.USER:
                conversation.append({"role": "user", "content": msg.content})
            elif msg.role == MessageRole.ASSISTANT:
                conversation.append({"role": "assistant", "content": msg.content})
            elif msg.role == MessageRole.TOOL:
                conversation.append({
                    "role": "user", 
                    "content": f"Результат инструмента {msg.tool_name}:\n{msg.content}"
                })
        
        # Generate response
        if hasattr(ai_client, 'generate_content'):
            # Gemini
            prompt = "\n".join([f"{m['role']}: {m['content']}" for m in conversation])
            response = await ai_client.generate_content_async(prompt)
            response_text = response.text
            tokens = 0  # Gemini doesn't return token count easily
        else:
            # OpenAI
            response = await ai_client.chat.completions.create(
                model=self.settings.openai_model,
                messages=conversation,
            )
            response_text = response.choices[0].message.content
            tokens = response.usage.total_tokens if response.usage else 0
        
        # Parse for tool calls
        if "TOOL:" in response_text:
            lines = response_text.split("\n")
            tool_name = None
            tool_args = {}
            
            for line in lines:
                if line.startswith("TOOL:"):
                    tool_name = line.replace("TOOL:", "").strip()
                elif line.startswith("ARGS:"):
                    try:
                        args_str = line.replace("ARGS:", "").strip()
                        tool_args = json.loads(args_str)
                    except json.JSONDecodeError:
                        pass
            
            return AgentMessage(
                role=MessageRole.ASSISTANT,
                content=response_text,
                tool_name=tool_name,
                tool_args=tool_args,
                tokens=tokens,
            )
        
        return AgentMessage(
            role=MessageRole.ASSISTANT,
            content=response_text,
            tokens=tokens,
        )
    
    async def _execute_tool(
        self,
        tool_name: str,
        args: dict,
        agent: UserAgent,
    ) -> Any:
        """Execute a tool and return result."""
        if tool_name not in self._tools:
            return f"Ошибка: инструмент '{tool_name}' не найден"
        
        try:
            result = await self._tools[tool_name](args, agent)
            return result
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}")
            return f"Ошибка при выполнении {tool_name}: {str(e)}"
    
    # Default tool implementations
    
    async def _tool_search_products(self, args: dict, agent: UserAgent) -> dict:
        """Search products (mock implementation)."""
        query = args.get("query", "")
        category = args.get("category", "")
        max_price = args.get("max_price")
        
        # In production, call Product Service
        return {
            "results": [
                {"id": "prod-1", "name": f"{query} вариант 1", "price": 1500},
                {"id": "prod-2", "name": f"{query} вариант 2", "price": 2000},
                {"id": "prod-3", "name": f"{query} премиум", "price": 3500},
            ],
            "total": 3,
            "query": query,
        }
    
    async def _tool_get_product_details(self, args: dict, agent: UserAgent) -> dict:
        """Get product details (mock)."""
        product_id = args.get("product_id", "")
        return {
            "id": product_id,
            "name": "Пример товара",
            "description": "Детальное описание товара",
            "price": 2500,
            "in_stock": True,
            "seller": "Магазин А",
        }
    
    async def _tool_compare_products(self, args: dict, agent: UserAgent) -> dict:
        """Compare products (mock)."""
        product_ids = args.get("product_ids", [])
        return {
            "comparison": [
                {"id": pid, "score": 0.8 - i * 0.1} 
                for i, pid in enumerate(product_ids)
            ],
            "recommendation": product_ids[0] if product_ids else None,
        }
    
    async def _tool_analyze_image(self, args: dict, agent: UserAgent) -> dict:
        """Analyze image (calls Vision Worker)."""
        image_id = args.get("image_id", "")
        # In production, call Vision Worker
        return {
            "image_id": image_id,
            "detected_style": "современный минимализм",
            "detected_brands": ["Ikea", "Muji"],
            "similar_products": ["prod-4", "prod-5"],
        }
    
    async def _tool_get_preferences(self, args: dict, agent: UserAgent) -> dict:
        """Get user preferences from agent context."""
        category = args.get("category", "all")
        return {
            "brands": agent.preferred_brands,
            "styles": agent.preferred_styles,
            "personality": agent.personality.model_dump(),
        }
    
    async def _tool_send_message(self, args: dict, agent: UserAgent) -> dict:
        """Send message to seller agent."""
        seller_id = args.get("seller_id", "")
        message = args.get("message", "")
        # In production, use A2A Protocol
        return {
            "sent": True,
            "to": seller_id,
            "message": message,
            "status": "delivered",
        }
    
    async def _tool_make_offer(self, args: dict, agent: UserAgent) -> dict:
        """Make purchase offer."""
        product_id = args.get("product_id", "")
        price = args.get("price", 0)
        quantity = args.get("quantity", 1)
        return {
            "offer_id": str(uuid4()),
            "product_id": product_id,
            "price": price,
            "quantity": quantity,
            "status": "pending",
        }
    
    async def _tool_request_delivery(self, args: dict, agent: UserAgent) -> dict:
        """Request delivery."""
        order_id = args.get("order_id", "")
        address = args.get("address", "")
        return {
            "delivery_id": str(uuid4()),
            "order_id": order_id,
            "address": address,
            "estimated_time": "2-3 рабочих дня",
            "status": "scheduled",
        }


# Singleton executor
_executor: Optional[AgentExecutor] = None


def get_executor() -> AgentExecutor:
    """Get agent executor singleton."""
    global _executor
    if _executor is None:
        _executor = AgentExecutor()
    return _executor


from uuid import uuid4
