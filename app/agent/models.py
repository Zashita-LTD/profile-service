"""Agent data models."""

from datetime import datetime
from enum import Enum
from typing import Any, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AgentRole(str, Enum):
    """Agent role types."""
    BUYER = "buyer"
    SELLER = "seller"
    ASSISTANT = "assistant"
    NEGOTIATOR = "negotiator"
    RESEARCHER = "researcher"


class TaskStatus(str, Enum):
    """Task execution status."""
    PENDING = "pending"
    RUNNING = "running"
    WAITING = "waiting"  # Waiting for external input
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class MessageRole(str, Enum):
    """Message role in conversation."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


class PersonalityTraits(BaseModel):
    """Agent personality configuration."""
    
    # Communication style
    formality: float = Field(default=0.5, ge=0, le=1)  # 0=casual, 1=formal
    verbosity: float = Field(default=0.5, ge=0, le=1)  # 0=terse, 1=verbose
    
    # Negotiation style
    aggressiveness: float = Field(default=0.5, ge=0, le=1)  # 0=passive, 1=aggressive
    risk_tolerance: float = Field(default=0.5, ge=0, le=1)
    
    # Preferences
    price_sensitivity: float = Field(default=0.5, ge=0, le=1)  # 0=quality first, 1=price first
    speed_priority: float = Field(default=0.5, ge=0, le=1)  # 0=thorough, 1=fast
    
    # Derived traits (from profile)
    custom_traits: dict[str, str] = Field(default_factory=dict)


class UserAgent(BaseModel):
    """Personal AI Agent - Digital Twin."""
    
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    name: str
    role: AgentRole = AgentRole.ASSISTANT
    
    # Personality
    personality: PersonalityTraits = Field(default_factory=PersonalityTraits)
    
    # Context
    system_prompt: str = ""
    context_summary: str = ""  # Summary of user's profile
    
    # Preferences (from Taste Graph)
    preferred_brands: list[str] = Field(default_factory=list)
    preferred_styles: list[str] = Field(default_factory=list)
    
    # State
    is_active: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_active: Optional[datetime] = None
    
    # Training
    fine_tuned: bool = False
    training_data_count: int = 0


class AgentMessage(BaseModel):
    """Message in agent conversation."""
    
    id: UUID = Field(default_factory=uuid4)
    role: MessageRole
    content: str
    
    # Tool call info (if role=tool)
    tool_name: Optional[str] = None
    tool_args: Optional[dict] = None
    tool_result: Optional[Any] = None
    
    # Metadata
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    tokens: int = 0


class AgentTask(BaseModel):
    """Task for agent to execute."""
    
    id: UUID = Field(default_factory=uuid4)
    agent_id: UUID
    user_id: UUID
    
    # Task definition
    instruction: str
    context: Optional[str] = None
    
    # Optional image/media for vision tasks
    media_id: Optional[UUID] = None
    
    # Status
    status: TaskStatus = TaskStatus.PENDING
    
    # Execution
    iterations: int = 0
    max_iterations: int = 10
    
    # Results
    result: Optional[str] = None
    error: Optional[str] = None
    
    # Conversation history
    messages: list[AgentMessage] = Field(default_factory=list)
    
    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    
    # Cost tracking
    total_tokens: int = 0
    cost_estimate: float = 0.0


class A2AMessage(BaseModel):
    """Agent-to-Agent protocol message."""
    
    id: UUID = Field(default_factory=uuid4)
    
    # Routing
    from_agent_id: UUID
    to_agent_id: UUID
    conversation_id: UUID
    
    # Message
    message_type: str  # request, response, offer, counter_offer, accept, reject
    content: str
    
    # Structured payload
    payload: dict = Field(default_factory=dict)
    
    # For negotiations
    offer: Optional[dict] = None  # {item, price, terms}
    
    # Metadata
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    requires_response: bool = True
    response_deadline: Optional[datetime] = None


class NegotiationState(BaseModel):
    """State of an A2A negotiation."""
    
    conversation_id: UUID
    buyer_agent_id: UUID
    seller_agent_id: UUID
    
    # What's being negotiated
    item_description: str
    item_quantity: int = 1
    
    # Offers
    buyer_budget: Optional[float] = None
    seller_asking_price: Optional[float] = None
    current_offer: Optional[float] = None
    
    # Terms
    delivery_deadline: Optional[datetime] = None
    additional_terms: dict = Field(default_factory=dict)
    
    # Status
    rounds: int = 0
    max_rounds: int = 10
    status: str = "negotiating"  # negotiating, agreed, failed
    
    # Final agreement
    agreed_price: Optional[float] = None
    agreed_terms: Optional[dict] = None


# API Models

class CreateAgentRequest(BaseModel):
    """Request to create a new agent."""
    user_id: UUID
    name: Optional[str] = None
    role: AgentRole = AgentRole.ASSISTANT


class TrainAgentRequest(BaseModel):
    """Request to train agent with user data."""
    user_id: UUID
    
    # Training data types
    include_photos: bool = True
    include_conversations: bool = True
    include_preferences: bool = True
    
    # Voice sample for TTS/voice matching
    voice_sample_id: Optional[UUID] = None


class ExecuteTaskRequest(BaseModel):
    """Request to execute a task."""
    user_id: UUID
    instruction: str
    
    # Optional context
    context: Optional[str] = None
    media_id: Optional[UUID] = None
    
    # Options
    max_iterations: int = Field(default=10, ge=1, le=50)
    timeout_seconds: int = Field(default=300, ge=30, le=1800)


class TaskResponse(BaseModel):
    """Response from task execution."""
    task_id: UUID
    status: TaskStatus
    result: Optional[str] = None
    error: Optional[str] = None
    
    # Execution stats
    iterations: int
    total_tokens: int
    duration_seconds: float
