"""Personal Agent Module.

Provides:
- UserAgent - Digital twin with personality and context
- Agent Factory - Creates and configures agents
- Agent Executor - Executes tasks with tool use
- A2A Protocol - Agent-to-Agent communication
- REST API - Train, task, negotiate endpoints
"""

from app.agent.models import (
    UserAgent,
    AgentTask,
    AgentMessage,
    A2AMessage,
    TaskStatus,
    AgentRole,
    PersonalityTraits,
    NegotiationState,
)
from app.agent.factory import AgentFactory, get_factory
from app.agent.protocol import A2AProtocol
from app.agent.executor import AgentExecutor, get_executor

__all__ = [
    # Models
    "UserAgent",
    "AgentTask",
    "AgentMessage",
    "A2AMessage",
    "TaskStatus",
    "AgentRole",
    "PersonalityTraits",
    "NegotiationState",
    # Services
    "AgentFactory",
    "get_factory",
    "A2AProtocol",
    "AgentExecutor",
    "get_executor",
]
