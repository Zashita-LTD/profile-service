"""Agent-to-Agent (A2A) Protocol.

Enables communication and negotiation between agents via Kafka.
Supports:
- Request/Response messaging
- Offer/Counter-offer negotiation
- Automated deal closure
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Callable, Optional
from uuid import UUID, uuid4

from aiokafka import AIOKafkaProducer, AIOKafkaConsumer

from app.config import get_settings
from app.agent.models import (
    A2AMessage,
    NegotiationState,
    UserAgent,
    AgentRole,
)

logger = logging.getLogger("a2a_protocol")


class A2AProtocol:
    """Agent-to-Agent communication protocol."""
    
    def __init__(self):
        self.settings = get_settings()
        self._producer: Optional[AIOKafkaProducer] = None
        self._consumer: Optional[AIOKafkaConsumer] = None
        self._message_handlers: dict[str, Callable] = {}
        self._active_negotiations: dict[UUID, NegotiationState] = {}
    
    async def connect(self) -> None:
        """Connect to Kafka for A2A messaging."""
        self._producer = AIOKafkaProducer(
            bootstrap_servers=self.settings.kafka_bootstrap_servers,
            value_serializer=lambda v: json.dumps(v, default=str).encode(),
        )
        await self._producer.start()
        
        self._consumer = AIOKafkaConsumer(
            self.settings.kafka_agent_topic,
            bootstrap_servers=self.settings.kafka_bootstrap_servers,
            group_id="agent-a2a",
            value_deserializer=lambda v: json.loads(v.decode()),
        )
        await self._consumer.start()
        
        logger.info("A2A Protocol connected to Kafka")
    
    async def disconnect(self) -> None:
        """Disconnect from Kafka."""
        if self._producer:
            await self._producer.stop()
        if self._consumer:
            await self._consumer.stop()
    
    async def send_message(self, message: A2AMessage) -> None:
        """Send A2A message via Kafka."""
        if not self._producer:
            raise RuntimeError("A2A Protocol not connected")
        
        await self._producer.send_and_wait(
            self.settings.kafka_agent_topic,
            value={
                "id": str(message.id),
                "from_agent_id": str(message.from_agent_id),
                "to_agent_id": str(message.to_agent_id),
                "conversation_id": str(message.conversation_id),
                "message_type": message.message_type,
                "content": message.content,
                "payload": message.payload,
                "offer": message.offer,
                "timestamp": message.timestamp.isoformat(),
                "requires_response": message.requires_response,
            }
        )
        
        logger.info(f"Sent A2A message: {message.id} ({message.message_type})")
    
    async def receive_messages(self, agent_id: UUID) -> list[A2AMessage]:
        """Receive pending messages for agent."""
        messages = []
        
        # In production, filter by to_agent_id
        # For simplicity, we collect all and filter
        try:
            async for msg in self._consumer:
                data = msg.value
                if data.get("to_agent_id") == str(agent_id):
                    messages.append(A2AMessage(
                        id=UUID(data["id"]),
                        from_agent_id=UUID(data["from_agent_id"]),
                        to_agent_id=UUID(data["to_agent_id"]),
                        conversation_id=UUID(data["conversation_id"]),
                        message_type=data["message_type"],
                        content=data["content"],
                        payload=data.get("payload", {}),
                        offer=data.get("offer"),
                        timestamp=datetime.fromisoformat(data["timestamp"]),
                        requires_response=data.get("requires_response", True),
                    ))
                
                if len(messages) >= 10:  # Batch limit
                    break
        except Exception as e:
            logger.error(f"Error receiving messages: {e}")
        
        return messages
    
    # Negotiation helpers
    
    async def start_negotiation(
        self,
        buyer_agent: UserAgent,
        seller_agent_id: UUID,
        item_description: str,
        budget: float,
        quantity: int = 1,
        deadline: Optional[datetime] = None,
    ) -> NegotiationState:
        """Start a negotiation between buyer and seller agents."""
        
        conversation_id = uuid4()
        
        state = NegotiationState(
            conversation_id=conversation_id,
            buyer_agent_id=buyer_agent.id,
            seller_agent_id=seller_agent_id,
            item_description=item_description,
            item_quantity=quantity,
            buyer_budget=budget,
            delivery_deadline=deadline,
        )
        
        self._active_negotiations[conversation_id] = state
        
        # Send initial request
        message = A2AMessage(
            from_agent_id=buyer_agent.id,
            to_agent_id=seller_agent_id,
            conversation_id=conversation_id,
            message_type="request",
            content=f"Здравствуйте! Ищу: {item_description}, количество: {quantity}. Готов обсудить условия.",
            payload={
                "item": item_description,
                "quantity": quantity,
                "deadline": deadline.isoformat() if deadline else None,
            },
        )
        
        await self.send_message(message)
        
        logger.info(f"Started negotiation {conversation_id}")
        return state
    
    async def make_offer(
        self,
        agent_id: UUID,
        conversation_id: UUID,
        price: float,
        terms: Optional[dict] = None,
    ) -> A2AMessage:
        """Make an offer in negotiation."""
        
        state = self._active_negotiations.get(conversation_id)
        if not state:
            raise ValueError(f"Negotiation {conversation_id} not found")
        
        # Determine recipient
        if agent_id == state.buyer_agent_id:
            to_agent = state.seller_agent_id
            message_type = "offer"
        else:
            to_agent = state.buyer_agent_id
            message_type = "counter_offer"
        
        state.current_offer = price
        state.rounds += 1
        
        if terms:
            state.additional_terms.update(terms)
        
        message = A2AMessage(
            from_agent_id=agent_id,
            to_agent_id=to_agent,
            conversation_id=conversation_id,
            message_type=message_type,
            content=f"Предлагаю цену: {price} руб." + (f" Условия: {terms}" if terms else ""),
            offer={
                "price": price,
                "quantity": state.item_quantity,
                "terms": terms or {},
            },
        )
        
        await self.send_message(message)
        return message
    
    async def accept_offer(
        self,
        agent_id: UUID,
        conversation_id: UUID,
    ) -> A2AMessage:
        """Accept current offer in negotiation."""
        
        state = self._active_negotiations.get(conversation_id)
        if not state:
            raise ValueError(f"Negotiation {conversation_id} not found")
        
        if not state.current_offer:
            raise ValueError("No offer to accept")
        
        # Determine recipient
        if agent_id == state.buyer_agent_id:
            to_agent = state.seller_agent_id
        else:
            to_agent = state.buyer_agent_id
        
        state.status = "agreed"
        state.agreed_price = state.current_offer
        state.agreed_terms = state.additional_terms.copy()
        
        message = A2AMessage(
            from_agent_id=agent_id,
            to_agent_id=to_agent,
            conversation_id=conversation_id,
            message_type="accept",
            content=f"Принимаю предложение! Цена: {state.agreed_price} руб.",
            offer={
                "price": state.agreed_price,
                "quantity": state.item_quantity,
                "terms": state.agreed_terms,
            },
            requires_response=False,
        )
        
        await self.send_message(message)
        
        logger.info(f"Negotiation {conversation_id} completed at {state.agreed_price}")
        return message
    
    async def reject_offer(
        self,
        agent_id: UUID,
        conversation_id: UUID,
        reason: str = "",
    ) -> A2AMessage:
        """Reject offer and end negotiation."""
        
        state = self._active_negotiations.get(conversation_id)
        if not state:
            raise ValueError(f"Negotiation {conversation_id} not found")
        
        # Determine recipient
        if agent_id == state.buyer_agent_id:
            to_agent = state.seller_agent_id
        else:
            to_agent = state.buyer_agent_id
        
        state.status = "failed"
        
        message = A2AMessage(
            from_agent_id=agent_id,
            to_agent_id=to_agent,
            conversation_id=conversation_id,
            message_type="reject",
            content=f"К сожалению, не можем договориться." + (f" Причина: {reason}" if reason else ""),
            requires_response=False,
        )
        
        await self.send_message(message)
        return message
    
    def get_negotiation_state(self, conversation_id: UUID) -> Optional[NegotiationState]:
        """Get current state of negotiation."""
        return self._active_negotiations.get(conversation_id)
    
    # Auto-negotiation
    
    async def auto_negotiate(
        self,
        buyer_agent: UserAgent,
        seller_agent_id: UUID,
        item_description: str,
        budget: float,
        min_acceptable: float,
    ) -> NegotiationState:
        """Automatically negotiate within budget.
        
        Buyer agent will:
        1. Start low (e.g., 70% of budget)
        2. Gradually increase up to budget
        3. Accept if within min_acceptable
        """
        
        state = await self.start_negotiation(
            buyer_agent=buyer_agent,
            seller_agent_id=seller_agent_id,
            item_description=item_description,
            budget=budget,
        )
        
        # Simple auto-negotiation logic
        current_offer = budget * 0.7
        increment = (budget - current_offer) / 5  # 5 rounds max
        
        while state.rounds < state.max_rounds and state.status == "negotiating":
            # Make offer
            await self.make_offer(
                agent_id=buyer_agent.id,
                conversation_id=state.conversation_id,
                price=current_offer,
            )
            
            # Wait for response (simplified)
            await asyncio.sleep(1)
            
            # Check if seller accepted (in real scenario, check messages)
            # For demo, simulate acceptance if close enough
            if current_offer >= min_acceptable:
                state.agreed_price = current_offer
                state.status = "agreed"
                break
            
            current_offer = min(current_offer + increment, budget)
        
        return state


# Message type handlers for different scenarios

def create_buyer_response_handler(agent: UserAgent, protocol: A2AProtocol):
    """Create handler for buyer agent responses."""
    
    async def handle_message(message: A2AMessage) -> Optional[A2AMessage]:
        """Handle incoming message for buyer agent."""
        
        if message.message_type == "offer":
            # Evaluate seller's offer
            offer_price = message.offer.get("price", 0) if message.offer else 0
            
            state = protocol.get_negotiation_state(message.conversation_id)
            if not state or not state.buyer_budget:
                return None
            
            # Decision logic based on personality
            price_sensitivity = agent.personality.price_sensitivity
            
            # Accept if within budget and sensitivity threshold
            threshold = state.buyer_budget * (1 - price_sensitivity * 0.3)
            
            if offer_price <= threshold:
                return await protocol.accept_offer(agent.id, message.conversation_id)
            elif offer_price <= state.buyer_budget:
                # Counter-offer
                counter = (offer_price + state.buyer_budget * 0.8) / 2
                return await protocol.make_offer(
                    agent.id,
                    message.conversation_id,
                    counter,
                )
            else:
                return await protocol.reject_offer(
                    agent.id,
                    message.conversation_id,
                    "Превышает бюджет",
                )
        
        return None
    
    return handle_message
