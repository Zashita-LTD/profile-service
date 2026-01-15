"""Agent API - Endpoints for agent management and tasks."""

from fastapi import APIRouter, HTTPException, Depends, BackgroundTasks, UploadFile, File
from fastapi.responses import StreamingResponse
from typing import Optional
from uuid import UUID
from datetime import datetime
from pydantic import BaseModel, Field
import io

from app.config import get_settings
from app.db.neo4j import Neo4jDB
from app.agent.models import (
    UserAgent,
    AgentTask,
    TaskStatus,
    AgentRole,
    PersonalityTraits,
)
from app.agent.factory import AgentFactory, get_factory
from app.agent.executor import AgentExecutor, get_executor

router = APIRouter(prefix="/agent", tags=["agent"])


# Request/Response models

class AgentTrainRequest(BaseModel):
    """Request to train/create user agent."""
    user_id: UUID
    agent_role: AgentRole = AgentRole.BUYER
    custom_instructions: Optional[str] = None
    preferred_brands: list[str] = Field(default_factory=list)
    preferred_styles: list[str] = Field(default_factory=list)


class AgentResponse(BaseModel):
    """Response with agent details."""
    id: UUID
    user_id: UUID
    role: AgentRole
    name: str
    system_prompt: str
    personality: PersonalityTraits
    preferred_brands: list[str]
    preferred_styles: list[str]
    created_at: datetime
    active: bool


class TaskCreateRequest(BaseModel):
    """Request to create agent task."""
    instruction: str = Field(..., min_length=1, max_length=2000)
    context: Optional[dict] = None
    priority: int = Field(default=5, ge=1, le=10)
    max_iterations: int = Field(default=10, ge=1, le=50)


class TaskResponse(BaseModel):
    """Response with task details."""
    id: UUID
    agent_id: UUID
    instruction: str
    status: TaskStatus
    result: Optional[str] = None
    error: Optional[str] = None
    iterations: int
    total_tokens: int
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


class TaskListResponse(BaseModel):
    """Response with list of tasks."""
    items: list[TaskResponse]
    total: int


class QuickActionRequest(BaseModel):
    """Request for quick agent action."""
    action: str = Field(..., description="One of: search, compare, recommend, negotiate")
    query: str = Field(..., min_length=1)
    params: dict = Field(default_factory=dict)


class QuickActionResponse(BaseModel):
    """Response for quick action."""
    action: str
    result: dict
    execution_time_ms: int


# Endpoints

@router.post("/train", response_model=AgentResponse)
async def train_agent(
    request: AgentTrainRequest,
    factory: AgentFactory = Depends(get_factory),
):
    """Train/create a personal agent for user.
    
    This creates an AI agent based on:
    - User's profile data from Neo4j
    - Media analysis (taste profile)
    - Event history (Life Stream)
    - Custom instructions
    
    The agent learns user's preferences and can act on their behalf.
    """
    try:
        agent = await factory.create_agent(
            user_id=request.user_id,
            role=request.agent_role,
            custom_instructions=request.custom_instructions,
            preferred_brands=request.preferred_brands,
            preferred_styles=request.preferred_styles,
        )
        
        return AgentResponse(
            id=agent.id,
            user_id=agent.user_id,
            role=agent.role,
            name=agent.name,
            system_prompt=agent.system_prompt,
            personality=agent.personality,
            preferred_brands=agent.preferred_brands,
            preferred_styles=agent.preferred_styles,
            created_at=agent.created_at,
            active=agent.active,
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to train agent: {str(e)}")


@router.get("/{user_id}", response_model=AgentResponse)
async def get_agent(
    user_id: UUID,
    factory: AgentFactory = Depends(get_factory),
):
    """Get user's agent."""
    
    agent = await factory.get_agent(user_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return AgentResponse(
        id=agent.id,
        user_id=agent.user_id,
        role=agent.role,
        name=agent.name,
        system_prompt=agent.system_prompt,
        personality=agent.personality,
        preferred_brands=agent.preferred_brands,
        preferred_styles=agent.preferred_styles,
        created_at=agent.created_at,
        active=agent.active,
    )


@router.put("/{user_id}/retrain", response_model=AgentResponse)
async def retrain_agent(
    user_id: UUID,
    custom_instructions: Optional[str] = None,
    factory: AgentFactory = Depends(get_factory),
):
    """Retrain agent with updated profile data."""
    
    existing = await factory.get_agent(user_id)
    if not existing:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Retrain with fresh data
    agent = await factory.create_agent(
        user_id=user_id,
        role=existing.role,
        custom_instructions=custom_instructions or existing.system_prompt,
        preferred_brands=existing.preferred_brands,
        preferred_styles=existing.preferred_styles,
    )
    
    return AgentResponse(
        id=agent.id,
        user_id=agent.user_id,
        role=agent.role,
        name=agent.name,
        system_prompt=agent.system_prompt,
        personality=agent.personality,
        preferred_brands=agent.preferred_brands,
        preferred_styles=agent.preferred_styles,
        created_at=agent.created_at,
        active=agent.active,
    )


@router.delete("/{user_id}")
async def delete_agent(
    user_id: UUID,
    factory: AgentFactory = Depends(get_factory),
):
    """Deactivate user's agent."""
    
    deleted = await factory.delete_agent(user_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    return {"deleted": True, "user_id": str(user_id)}


@router.post("/{user_id}/task", response_model=TaskResponse)
async def create_task(
    user_id: UUID,
    request: TaskCreateRequest,
    background_tasks: BackgroundTasks,
    factory: AgentFactory = Depends(get_factory),
    executor: AgentExecutor = Depends(get_executor),
):
    """Create and execute a task for user's agent.
    
    Example tasks:
    - "Найди кроссовки Nike до 15000 рублей"
    - "Сравни iPhone 15 и Samsung S24"
    - "Договорись о скидке на ноутбук"
    """
    
    agent = await factory.get_agent(user_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    # Create task
    task = AgentTask(
        agent_id=agent.id,
        instruction=request.instruction,
        context=request.context,
        priority=request.priority,
        max_iterations=request.max_iterations,
    )
    
    # Execute in background
    background_tasks.add_task(_execute_task, task, agent, executor)
    
    return TaskResponse(
        id=task.id,
        agent_id=task.agent_id,
        instruction=task.instruction,
        status=TaskStatus.PENDING,
        iterations=0,
        total_tokens=0,
        created_at=task.created_at,
    )


async def _execute_task(task: AgentTask, agent: UserAgent, executor: AgentExecutor):
    """Background task execution."""
    try:
        await executor.execute_task(task, agent)
    except Exception as e:
        import logging
        logging.error(f"Task {task.id} failed: {e}")


@router.get("/{user_id}/task/{task_id}", response_model=TaskResponse)
async def get_task(
    user_id: UUID,
    task_id: UUID,
):
    """Get task status and results."""
    
    # In production, fetch from database
    # For now, return placeholder
    raise HTTPException(status_code=501, detail="Task persistence not implemented")


@router.get("/{user_id}/tasks", response_model=TaskListResponse)
async def list_tasks(
    user_id: UUID,
    status: Optional[TaskStatus] = None,
    limit: int = 20,
):
    """List user's agent tasks."""
    
    # In production, fetch from database
    return TaskListResponse(items=[], total=0)


@router.post("/{user_id}/quick", response_model=QuickActionResponse)
async def quick_action(
    user_id: UUID,
    request: QuickActionRequest,
    factory: AgentFactory = Depends(get_factory),
    executor: AgentExecutor = Depends(get_executor),
):
    """Execute quick agent action without full task flow.
    
    Supported actions:
    - search: Quick product search
    - compare: Compare products
    - recommend: Get recommendation
    - negotiate: Start negotiation
    """
    import time
    
    agent = await factory.get_agent(user_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    start = time.time()
    
    if request.action == "search":
        result = await executor._tool_search_products(
            {"query": request.query, **request.params},
            agent
        )
    elif request.action == "compare":
        product_ids = request.params.get("product_ids", [])
        result = await executor._tool_compare_products(
            {"product_ids": product_ids},
            agent
        )
    elif request.action == "recommend":
        # Use agent preferences for recommendation
        result = {
            "query": request.query,
            "recommendations": [
                {"type": "based_on_style", "items": agent.preferred_styles[:3]},
                {"type": "based_on_brands", "items": agent.preferred_brands[:3]},
            ],
            "personality_fit": agent.personality.model_dump(),
        }
    elif request.action == "negotiate":
        # Would start A2A negotiation
        result = {
            "status": "negotiation_started",
            "target": request.params.get("seller_id"),
            "budget": request.params.get("budget"),
        }
    else:
        raise HTTPException(status_code=400, detail=f"Unknown action: {request.action}")
    
    elapsed_ms = int((time.time() - start) * 1000)
    
    return QuickActionResponse(
        action=request.action,
        result=result,
        execution_time_ms=elapsed_ms,
    )


# A2A Endpoints

@router.post("/{user_id}/negotiate/start")
async def start_negotiation(
    user_id: UUID,
    seller_id: UUID,
    item: str,
    budget: float,
    quantity: int = 1,
    factory: AgentFactory = Depends(get_factory),
):
    """Start A2A negotiation with seller."""
    from app.agent.protocol import A2AProtocol
    
    buyer = await factory.get_agent(user_id)
    if not buyer:
        raise HTTPException(status_code=404, detail="Buyer agent not found")
    
    protocol = A2AProtocol()
    await protocol.connect()
    
    try:
        state = await protocol.start_negotiation(
            buyer_agent=buyer,
            seller_agent_id=seller_id,
            item_description=item,
            budget=budget,
            quantity=quantity,
        )
        
        return {
            "conversation_id": str(state.conversation_id),
            "status": state.status,
            "item": state.item_description,
            "budget": state.buyer_budget,
        }
    finally:
        await protocol.disconnect()


@router.post("/{user_id}/negotiate/{conversation_id}/offer")
async def make_offer(
    user_id: UUID,
    conversation_id: UUID,
    price: float,
    terms: Optional[dict] = None,
    factory: AgentFactory = Depends(get_factory),
):
    """Make offer in negotiation."""
    from app.agent.protocol import A2AProtocol
    
    agent = await factory.get_agent(user_id)
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    
    protocol = A2AProtocol()
    await protocol.connect()
    
    try:
        message = await protocol.make_offer(
            agent_id=agent.id,
            conversation_id=conversation_id,
            price=price,
            terms=terms,
        )
        
        return {
            "message_id": str(message.id),
            "price": price,
            "status": "sent",
        }
    finally:
        await protocol.disconnect()


@router.get("/{user_id}/negotiate/{conversation_id}")
async def get_negotiation_status(
    user_id: UUID,
    conversation_id: UUID,
):
    """Get negotiation status."""
    from app.agent.protocol import A2AProtocol
    
    protocol = A2AProtocol()
    state = protocol.get_negotiation_state(conversation_id)
    
    if not state:
        raise HTTPException(status_code=404, detail="Negotiation not found")
    
    return {
        "conversation_id": str(state.conversation_id),
        "status": state.status,
        "rounds": state.rounds,
        "current_offer": state.current_offer,
        "agreed_price": state.agreed_price,
        "item": state.item_description,
    }


# =====================
# Voice Chat Endpoints
# =====================

class VoiceChatResponse(BaseModel):
    """Response for voice chat."""
    user_text: str
    agent_text: str
    has_audio: bool


@router.post("/{user_id}/voice-chat")
async def voice_chat(
    user_id: UUID,
    audio: UploadFile = File(...),
    return_audio: bool = True,
):
    """Voice chat with agent.
    
    Send audio, get audio response.
    
    - Input: Audio file (webm, wav, mp3, m4a)
    - Output: JSON with transcription + audio stream
    
    For streaming audio response, use Accept: audio/mpeg header.
    """
    from app.agent.voice import get_voice_processor
    
    # Validate file
    if not audio.filename:
        raise HTTPException(status_code=400, detail="No audio file")
    
    ext = audio.filename.split('.')[-1].lower()
    if ext not in ['webm', 'wav', 'mp3', 'm4a', 'ogg', 'flac']:
        raise HTTPException(status_code=400, detail=f"Unsupported audio format: {ext}")
    
    # Read audio
    audio_bytes = await audio.read()
    if len(audio_bytes) > 10 * 1024 * 1024:  # 10MB limit
        raise HTTPException(status_code=400, detail="Audio file too large (max 10MB)")
    
    # Process
    try:
        processor = get_voice_processor()
        result = await processor.process(
            audio_bytes=audio_bytes,
            user_id=str(user_id),
            audio_format=ext,
            return_audio=return_audio,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Voice processing failed: {str(e)}")
    
    # Return with audio
    if return_audio and result.get("audio"):
        # Return as multipart or just audio
        return StreamingResponse(
            io.BytesIO(result["audio"]),
            media_type="audio/mpeg",
            headers={
                "X-User-Text": result["user_text"][:200],
                "X-Agent-Text": result["agent_text"][:500],
            }
        )
    
    # Return JSON only
    return VoiceChatResponse(
        user_text=result["user_text"],
        agent_text=result["agent_text"],
        has_audio=bool(result.get("audio")),
    )


@router.post("/{user_id}/voice-transcribe")
async def voice_transcribe(
    user_id: UUID,
    audio: UploadFile = File(...),
):
    """Transcribe audio to text only (no agent processing).
    
    Useful for voice-to-text input without AI response.
    """
    from app.agent.voice import get_voice_processor
    
    # Validate
    if not audio.filename:
        raise HTTPException(status_code=400, detail="No audio file")
    
    ext = audio.filename.split('.')[-1].lower()
    audio_bytes = await audio.read()
    
    try:
        processor = get_voice_processor()
        text = await processor.transcribe_only(audio_bytes, ext)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
    
    return {"text": text}


@router.post("/{user_id}/voice-speak")
async def voice_speak(
    user_id: UUID,
    text: str,
):
    """Convert text to speech audio.
    
    Returns MP3 audio stream.
    """
    from app.agent.voice import get_voice_processor
    
    if not text or len(text) > 5000:
        raise HTTPException(status_code=400, detail="Text must be 1-5000 characters")
    
    try:
        processor = get_voice_processor()
        audio = await processor.speak_only(text)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Speech synthesis failed: {str(e)}")
    
    return StreamingResponse(
        io.BytesIO(audio),
        media_type="audio/mpeg",
    )
