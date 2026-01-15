"""Life Stream data models."""

from datetime import datetime
from enum import Enum
from typing import Optional, Union
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class EventType(str, Enum):
    """Types of life events."""
    GEO = "geo"
    PURCHASE = "purchase"
    TRANSACTION = "transaction"
    SOCIAL = "social"
    HEALTH = "health"
    ACTIVITY = "activity"
    COMMUNICATION = "communication"
    CUSTOM = "custom"


class EventSource(str, Enum):
    """Event data source."""
    API = "api"
    MOBILE = "mobile"
    WEARABLE = "wearable"
    IMPORT = "import"
    WEBHOOK = "webhook"


class BaseEvent(BaseModel):
    """Base event model."""
    type: EventType
    ts: datetime = Field(default_factory=datetime.utcnow, alias="timestamp")
    source: EventSource = EventSource.API
    device_id: Optional[str] = None
    
    class Config:
        populate_by_name = True


class GeoEvent(BaseEvent):
    """Geographic location event."""
    type: EventType = EventType.GEO
    lat: float = Field(..., ge=-90, le=90, description="Latitude")
    lon: float = Field(..., ge=-180, le=180, description="Longitude")
    accuracy: Optional[float] = Field(None, ge=0, description="GPS accuracy in meters")
    altitude: Optional[float] = None
    speed: Optional[float] = Field(None, ge=0, description="Speed in m/s")
    heading: Optional[float] = Field(None, ge=0, lt=360, description="Heading in degrees")


class PurchaseEvent(BaseEvent):
    """Purchase/transaction event."""
    type: EventType = EventType.PURCHASE
    item: str
    amount: float = Field(..., ge=0)
    currency: str = "RUB"
    place: Optional[str] = None
    category: Optional[str] = None
    payment_method: Optional[str] = None
    
    # Optional geo
    lat: Optional[float] = None
    lon: Optional[float] = None


class SocialEvent(BaseEvent):
    """Social interaction event."""
    type: EventType = EventType.SOCIAL
    action: str = Field(..., description="Action type: meet, call, message, etc.")
    person_id: Optional[str] = Field(None, description="UUID of person in graph")
    person_name: Optional[str] = None
    context: Optional[str] = None
    duration_minutes: Optional[int] = None
    
    # Optional geo
    lat: Optional[float] = None
    lon: Optional[float] = None


class HealthEvent(BaseEvent):
    """Health/wellness event."""
    type: EventType = EventType.HEALTH
    metric: str = Field(..., description="Metric type: steps, heart_rate, sleep, etc.")
    value: float
    unit: str = ""
    
    # Additional metrics
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    avg_value: Optional[float] = None


class ActivityEvent(BaseEvent):
    """Activity/exercise event."""
    type: EventType = EventType.ACTIVITY
    activity: str = Field(..., description="Activity type: walking, running, cycling, etc.")
    duration_minutes: int
    distance_meters: Optional[float] = None
    calories: Optional[float] = None
    
    # Start/end locations
    start_lat: Optional[float] = None
    start_lon: Optional[float] = None
    end_lat: Optional[float] = None
    end_lon: Optional[float] = None


class CustomEvent(BaseEvent):
    """Custom event with arbitrary payload."""
    type: EventType = EventType.CUSTOM
    event_subtype: str
    payload: dict = Field(default_factory=dict)


# Union type for all events
LifeEvent = Union[GeoEvent, PurchaseEvent, SocialEvent, HealthEvent, ActivityEvent, CustomEvent]


class EventBatch(BaseModel):
    """Batch of life events for ingestion."""
    user_id: UUID
    events: list[LifeEvent]
    
    class Config:
        json_schema_extra = {
            "example": {
                "user_id": "550e8400-e29b-41d4-a716-446655440000",
                "events": [
                    {"type": "geo", "lat": 55.75, "lon": 37.61, "ts": "2023-10-10T10:00:00"},
                    {"type": "purchase", "item": "Latte", "amount": 300, "place": "Starbucks"},
                    {"type": "social", "action": "meet", "person_id": "uuid-peter"}
                ]
            }
        }


# Pattern models
class PatternType(str, Enum):
    """Types of discovered patterns."""
    LOCATION_CLUSTER = "location_cluster"  # Frequently visited place
    ROUTINE = "routine"  # Regular time-based pattern
    HABIT = "habit"  # Behavioral pattern
    RELATIONSHIP = "relationship"  # Social pattern
    ANOMALY = "anomaly"  # Unusual behavior


class DiscoveredPattern(BaseModel):
    """Pattern discovered by AI analysis."""
    id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    pattern_type: PatternType
    name: str
    description: str
    confidence: float = Field(..., ge=0, le=1)
    
    # Location data (for location patterns)
    center_lat: Optional[float] = None
    center_lon: Optional[float] = None
    radius_meters: Optional[float] = None
    
    # Time pattern
    time_pattern: Optional[str] = None  # Cron-like
    frequency_per_week: float = 0
    
    # Validity
    first_seen: datetime
    last_seen: datetime
    occurrences: int = 1
    is_active: bool = True
    
    # Raw data
    data: dict = Field(default_factory=dict)


class MemorySearchQuery(BaseModel):
    """Query for searching life memory."""
    question: str = Field(..., min_length=3, max_length=500)
    user_id: UUID
    
    # Optional filters
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None
    event_types: Optional[list[EventType]] = None
    
    # Search options
    include_ai_reasoning: bool = True
    max_events: int = Field(default=100, ge=1, le=1000)


class MemorySearchResult(BaseModel):
    """Result of memory search."""
    question: str
    answer: str
    confidence: float = Field(..., ge=0, le=1)
    
    # Evidence
    events_found: int
    time_range: Optional[tuple[datetime, datetime]] = None
    
    # Related data
    locations: list[dict] = Field(default_factory=list)
    people: list[dict] = Field(default_factory=list)
    transactions: list[dict] = Field(default_factory=list)
    
    # AI reasoning
    reasoning: Optional[str] = None
    sources: list[str] = Field(default_factory=list)
