"""Life Stream module - Big Data for Human Life Events.

This module provides:
- ClickHouse integration for high-volume event storage
- Ingestion API for receiving life events (geo, purchases, social, health)
- Pattern Mining workers for discovering habits and routines
- Memory Search API with RAG for querying your life data
"""

from app.life_stream.models import (
    LifeEvent,
    GeoEvent,
    PurchaseEvent,
    SocialEvent,
    HealthEvent,
    EventBatch,
)
from app.life_stream.clickhouse import ClickHouseDB

__all__ = [
    "LifeEvent",
    "GeoEvent", 
    "PurchaseEvent",
    "SocialEvent",
    "HealthEvent",
    "EventBatch",
    "ClickHouseDB",
]
