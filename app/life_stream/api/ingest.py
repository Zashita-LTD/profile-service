"""Ingestion API router for Life Stream events."""

from datetime import datetime
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field

from app.life_stream.clickhouse import ClickHouseDB
from app.life_stream.models import (
    EventBatch,
    EventType,
    GeoEvent,
    PurchaseEvent,
    SocialEvent,
    HealthEvent,
    LifeEvent,
)


router = APIRouter(prefix="/api/v1/stream", tags=["Life Stream"])


class IngestResponse(BaseModel):
    """Response from ingest endpoint."""
    success: bool
    events_received: int
    events_stored: int
    errors: list[str] = Field(default_factory=list)


class SingleEventInput(BaseModel):
    """Single event for direct ingestion."""
    user_id: UUID
    type: str
    ts: Optional[datetime] = None
    
    # Geo fields
    lat: Optional[float] = None
    lon: Optional[float] = None
    accuracy: Optional[float] = None
    speed: Optional[float] = None
    
    # Purchase fields
    item: Optional[str] = None
    amount: Optional[float] = None
    place: Optional[str] = None
    category: Optional[str] = None
    
    # Social fields
    action: Optional[str] = None
    person_id: Optional[str] = None
    person_name: Optional[str] = None
    
    # Health fields
    metric: Optional[str] = None
    value: Optional[float] = None
    unit: Optional[str] = None
    
    # Generic
    payload: Optional[dict] = None


@router.post("/ingest", response_model=IngestResponse)
async def ingest_events(batch: EventBatch) -> IngestResponse:
    """Ingest batch of life events.
    
    Accepts a batch of events and stores them in ClickHouse for analysis.
    
    Example:
    ```json
    {
        "user_id": "550e8400-e29b-41d4-a716-446655440000",
        "events": [
            {"type": "geo", "lat": 55.75, "lon": 37.61, "ts": "2023-10-10T10:00:00"},
            {"type": "purchase", "item": "Latte", "amount": 300, "place": "Starbucks"},
            {"type": "social", "action": "meet", "person_id": "uuid-peter"}
        ]
    }
    ```
    """
    errors = []
    valid_events = []
    
    for i, event in enumerate(batch.events):
        try:
            valid_events.append(event)
        except Exception as e:
            errors.append(f"Event {i}: {str(e)}")
    
    if not valid_events:
        raise HTTPException(
            status_code=400,
            detail=f"No valid events in batch. Errors: {errors}"
        )
    
    try:
        stored = await ClickHouseDB.insert_events(
            user_id=batch.user_id,
            events=valid_events,
            source="api",
        )
        
        return IngestResponse(
            success=True,
            events_received=len(batch.events),
            events_stored=stored,
            errors=errors,
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to store events: {str(e)}"
        )


@router.post("/ingest/single", response_model=IngestResponse)
async def ingest_single_event(event: SingleEventInput) -> IngestResponse:
    """Ingest single event with flexible schema.
    
    Simplified endpoint for single events without strict typing.
    """
    try:
        # Convert to proper event type
        event_type = EventType(event.type)
        typed_event: LifeEvent
        
        if event_type == EventType.GEO:
            if event.lat is None or event.lon is None:
                raise ValueError("Geo events require lat and lon")
            typed_event = GeoEvent(
                lat=event.lat,
                lon=event.lon,
                accuracy=event.accuracy,
                speed=event.speed,
                ts=event.ts or datetime.utcnow(),
            )
        elif event_type == EventType.PURCHASE:
            if not event.item:
                raise ValueError("Purchase events require item")
            typed_event = PurchaseEvent(
                item=event.item,
                amount=event.amount or 0,
                place=event.place,
                category=event.category,
                lat=event.lat,
                lon=event.lon,
                ts=event.ts or datetime.utcnow(),
            )
        elif event_type == EventType.SOCIAL:
            if not event.action:
                raise ValueError("Social events require action")
            typed_event = SocialEvent(
                action=event.action,
                person_id=event.person_id,
                person_name=event.person_name,
                lat=event.lat,
                lon=event.lon,
                ts=event.ts or datetime.utcnow(),
            )
        elif event_type == EventType.HEALTH:
            if not event.metric or event.value is None:
                raise ValueError("Health events require metric and value")
            typed_event = HealthEvent(
                metric=event.metric,
                value=event.value,
                unit=event.unit or "",
                ts=event.ts or datetime.utcnow(),
            )
        else:
            raise ValueError(f"Unsupported event type: {event.type}")
        
        stored = await ClickHouseDB.insert_events(
            user_id=event.user_id,
            events=[typed_event],
            source="api",
        )
        
        return IngestResponse(
            success=True,
            events_received=1,
            events_stored=stored,
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to store event: {str(e)}")


@router.get("/events/{user_id}")
async def get_user_events(
    user_id: UUID,
    start_time: Annotated[Optional[datetime], Query()] = None,
    end_time: Annotated[Optional[datetime], Query()] = None,
    event_types: Annotated[Optional[str], Query(description="Comma-separated event types")] = None,
    limit: Annotated[int, Query(ge=1, le=10000)] = 100,
):
    """Get events for a user.
    
    Args:
        user_id: User UUID
        start_time: Filter events after this time
        end_time: Filter events before this time
        event_types: Comma-separated list of event types (geo, purchase, social, health)
        limit: Maximum number of events to return
    """
    types = None
    if event_types:
        try:
            types = [EventType(t.strip()) for t in event_types.split(",")]
        except ValueError as e:
            raise HTTPException(status_code=400, detail=f"Invalid event type: {e}")
    
    try:
        events = await ClickHouseDB.get_events(
            user_id=user_id,
            start_time=start_time,
            end_time=end_time,
            event_types=types,
            limit=limit,
        )
        
        return {
            "user_id": str(user_id),
            "count": len(events),
            "events": events,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch events: {str(e)}")


@router.get("/stats/{user_id}")
async def get_user_stats(user_id: UUID):
    """Get event statistics for a user.
    
    Returns count of events by type, time range, etc.
    """
    try:
        stats = await ClickHouseDB.get_event_stats(user_id)
        return {
            "user_id": str(user_id),
            **stats,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch stats: {str(e)}")


@router.get("/patterns/{user_id}")
async def get_user_patterns(
    user_id: UUID,
    pattern_type: Annotated[Optional[str], Query()] = None,
    active_only: Annotated[bool, Query()] = True,
):
    """Get discovered patterns for a user.
    
    Returns habits, routines, and location clusters discovered by Pattern Miner.
    """
    try:
        patterns = await ClickHouseDB.get_patterns(
            user_id=user_id,
            pattern_type=pattern_type,
            active_only=active_only,
        )
        
        return {
            "user_id": str(user_id),
            "count": len(patterns),
            "patterns": patterns,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch patterns: {str(e)}")
