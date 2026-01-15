"""ClickHouse database client for Life Stream."""

import json
from contextlib import asynccontextmanager
from datetime import datetime
from typing import Any, AsyncGenerator, Optional
from uuid import UUID

import clickhouse_connect
from clickhouse_connect.driver.asyncclient import AsyncClient

from app.config import get_settings
from app.life_stream.models import LifeEvent, GeoEvent, EventType


class ClickHouseDB:
    """ClickHouse async connection manager for Life Stream events."""
    
    _client: Optional[AsyncClient] = None
    
    @classmethod
    async def connect(cls) -> None:
        """Connect to ClickHouse."""
        settings = get_settings()
        cls._client = await clickhouse_connect.get_async_client(
            host=settings.clickhouse_host,
            port=settings.clickhouse_port,
            username=settings.clickhouse_user,
            password=settings.clickhouse_password,
            database=settings.clickhouse_database,
        )
        # Verify connection
        result = await cls._client.query("SELECT 1")
        print(f"✅ ClickHouse connected: {settings.clickhouse_host}:{settings.clickhouse_port}")
    
    @classmethod
    async def disconnect(cls) -> None:
        """Disconnect from ClickHouse."""
        if cls._client:
            await cls._client.close()
            cls._client = None
    
    @classmethod
    def get_client(cls) -> AsyncClient:
        """Get ClickHouse client."""
        if not cls._client:
            raise RuntimeError("ClickHouse not connected")
        return cls._client
    
    @classmethod
    async def insert_events(
        cls,
        user_id: UUID,
        events: list[LifeEvent],
        source: str = "api"
    ) -> int:
        """Insert batch of events into ClickHouse.
        
        Args:
            user_id: User UUID
            events: List of life events
            source: Data source identifier
            
        Returns:
            Number of inserted events
        """
        if not events:
            return 0
        
        client = cls.get_client()
        
        # Prepare data for insertion
        rows = []
        for event in events:
            row = cls._event_to_row(user_id, event, source)
            rows.append(row)
        
        # Column names matching the table schema
        columns = [
            "user_id", "timestamp", "event_type", "event_subtype", "source",
            "device_id", "latitude", "longitude", "accuracy", "altitude",
            "speed", "payload"
        ]
        
        await client.insert(
            "events",
            rows,
            column_names=columns,
        )
        
        return len(rows)
    
    @classmethod
    def _event_to_row(cls, user_id: UUID, event: LifeEvent, source: str) -> tuple:
        """Convert event to ClickHouse row tuple."""
        # Extract common fields
        timestamp = getattr(event, 'ts', datetime.utcnow())
        event_type = event.type.value
        device_id = getattr(event, 'device_id', '') or ''
        
        # Extract geo fields
        lat = getattr(event, 'lat', None)
        lon = getattr(event, 'lon', None)
        accuracy = getattr(event, 'accuracy', None)
        altitude = getattr(event, 'altitude', None)
        speed = getattr(event, 'speed', None)
        
        # Build payload JSON (exclude common fields)
        payload_dict = event.model_dump(exclude={
            'type', 'ts', 'timestamp', 'source', 'device_id',
            'lat', 'lon', 'accuracy', 'altitude', 'speed'
        })
        payload = json.dumps(payload_dict, default=str)
        
        # Determine subtype
        subtype = ""
        if hasattr(event, 'event_subtype'):
            subtype = event.event_subtype
        elif hasattr(event, 'action'):
            subtype = event.action
        elif hasattr(event, 'metric'):
            subtype = event.metric
        elif hasattr(event, 'activity'):
            subtype = event.activity
        
        return (
            str(user_id),
            timestamp,
            event_type,
            subtype,
            source,
            device_id,
            lat,
            lon,
            accuracy,
            altitude,
            speed,
            payload,
        )
    
    @classmethod
    async def get_events(
        cls,
        user_id: UUID,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        event_types: Optional[list[EventType]] = None,
        limit: int = 1000,
    ) -> list[dict]:
        """Query events from ClickHouse.
        
        Args:
            user_id: User UUID
            start_time: Start of time range
            end_time: End of time range
            event_types: Filter by event types
            limit: Maximum number of events
            
        Returns:
            List of event dictionaries
        """
        client = cls.get_client()
        
        # Build query
        query = """
            SELECT 
                id,
                user_id,
                timestamp,
                event_type,
                event_subtype,
                source,
                latitude,
                longitude,
                accuracy,
                speed,
                payload
            FROM events
            WHERE user_id = {user_id:UUID}
        """
        
        params = {"user_id": str(user_id), "limit": limit}
        
        if start_time:
            query += " AND timestamp >= {start_time:DateTime64}"
            params["start_time"] = start_time
        
        if end_time:
            query += " AND timestamp <= {end_time:DateTime64}"
            params["end_time"] = end_time
        
        if event_types:
            types_str = ",".join(f"'{t.value}'" for t in event_types)
            query += f" AND event_type IN ({types_str})"
        
        query += " ORDER BY timestamp DESC LIMIT {limit:UInt32}"
        
        result = await client.query(query, parameters=params)
        
        # Convert to list of dicts
        events = []
        for row in result.result_rows:
            event = {
                "id": str(row[0]),
                "user_id": str(row[1]),
                "timestamp": row[2].isoformat() if row[2] else None,
                "event_type": row[3],
                "event_subtype": row[4],
                "source": row[5],
                "latitude": row[6],
                "longitude": row[7],
                "accuracy": row[8],
                "speed": row[9],
                "payload": json.loads(row[10]) if row[10] else {},
            }
            events.append(event)
        
        return events
    
    @classmethod
    async def get_geo_points(
        cls,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
        limit: int = 10000,
    ) -> list[dict]:
        """Get geo points for pattern analysis.
        
        Args:
            user_id: User UUID
            start_time: Start of time range
            end_time: End of time range
            limit: Maximum points
            
        Returns:
            List of geo point dictionaries
        """
        client = cls.get_client()
        
        query = """
            SELECT 
                timestamp,
                latitude,
                longitude,
                accuracy,
                speed
            FROM events
            WHERE user_id = {user_id:UUID}
              AND event_type = 'geo'
              AND latitude IS NOT NULL
              AND longitude IS NOT NULL
              AND timestamp BETWEEN {start_time:DateTime64} AND {end_time:DateTime64}
            ORDER BY timestamp
            LIMIT {limit:UInt32}
        """
        
        result = await client.query(query, parameters={
            "user_id": str(user_id),
            "start_time": start_time,
            "end_time": end_time,
            "limit": limit,
        })
        
        return [
            {
                "timestamp": row[0],
                "lat": row[1],
                "lon": row[2],
                "accuracy": row[3],
                "speed": row[4],
            }
            for row in result.result_rows
        ]
    
    @classmethod
    async def get_hourly_geo_summary(
        cls,
        user_id: UUID,
        start_time: datetime,
        end_time: datetime,
    ) -> list[dict]:
        """Get hourly geo summary for pattern analysis."""
        client = cls.get_client()
        
        query = """
            SELECT 
                hour,
                center_lat,
                center_lon,
                points_count,
                avg_speed,
                max_speed
            FROM geo_hourly
            WHERE user_id = {user_id:UUID}
              AND hour BETWEEN {start_time:DateTime} AND {end_time:DateTime}
            ORDER BY hour
        """
        
        result = await client.query(query, parameters={
            "user_id": str(user_id),
            "start_time": start_time,
            "end_time": end_time,
        })
        
        return [
            {
                "hour": row[0],
                "center_lat": row[1],
                "center_lon": row[2],
                "points_count": row[3],
                "avg_speed": row[4],
                "max_speed": row[5],
            }
            for row in result.result_rows
        ]
    
    @classmethod
    async def save_pattern(cls, pattern: dict) -> str:
        """Save discovered pattern to ClickHouse."""
        client = cls.get_client()
        
        columns = [
            "user_id", "pattern_type", "name", "description", "confidence",
            "data", "center_lat", "center_lon", "radius",
            "time_pattern", "frequency_per_week",
            "first_seen", "last_seen", "occurrences", "is_active"
        ]
        
        row = (
            str(pattern["user_id"]),
            pattern["pattern_type"],
            pattern["name"],
            pattern["description"],
            pattern["confidence"],
            json.dumps(pattern.get("data", {})),
            pattern.get("center_lat"),
            pattern.get("center_lon"),
            pattern.get("radius_meters"),
            pattern.get("time_pattern", ""),
            pattern.get("frequency_per_week", 0),
            pattern["first_seen"],
            pattern["last_seen"],
            pattern.get("occurrences", 1),
            pattern.get("is_active", True),
        )
        
        await client.insert("patterns", [row], column_names=columns)
        return str(pattern.get("id", ""))
    
    @classmethod
    async def get_patterns(
        cls,
        user_id: UUID,
        pattern_type: Optional[str] = None,
        active_only: bool = True,
    ) -> list[dict]:
        """Get discovered patterns for user."""
        client = cls.get_client()
        
        query = """
            SELECT 
                id, user_id, pattern_type, name, description, confidence,
                data, center_lat, center_lon, radius,
                time_pattern, frequency_per_week,
                first_seen, last_seen, occurrences, is_active
            FROM patterns
            WHERE user_id = {user_id:UUID}
        """
        
        params = {"user_id": str(user_id)}
        
        if pattern_type:
            query += " AND pattern_type = {pattern_type:String}"
            params["pattern_type"] = pattern_type
        
        if active_only:
            query += " AND is_active = true"
        
        query += " ORDER BY confidence DESC, occurrences DESC"
        
        result = await client.query(query, parameters=params)
        
        patterns = []
        for row in result.result_rows:
            patterns.append({
                "id": str(row[0]),
                "user_id": str(row[1]),
                "pattern_type": row[2],
                "name": row[3],
                "description": row[4],
                "confidence": row[5],
                "data": json.loads(row[6]) if row[6] else {},
                "center_lat": row[7],
                "center_lon": row[8],
                "radius_meters": row[9],
                "time_pattern": row[10],
                "frequency_per_week": row[11],
                "first_seen": row[12].isoformat() if row[12] else None,
                "last_seen": row[13].isoformat() if row[13] else None,
                "occurrences": row[14],
                "is_active": row[15],
            })
        
        return patterns
    
    @classmethod
    async def save_insight(cls, insight: dict) -> str:
        """Save AI-generated insight."""
        client = cls.get_client()
        
        columns = [
            "user_id", "neo4j_node_id", "insight_type", "title", "description",
            "evidence_event_ids", "evidence_count",
            "time_range_start", "time_range_end",
            "ai_model", "confidence", "reasoning"
        ]
        
        row = (
            str(insight["user_id"]),
            insight.get("neo4j_node_id", ""),
            insight["insight_type"],
            insight["title"],
            insight["description"],
            [str(eid) for eid in insight.get("evidence_event_ids", [])],
            insight.get("evidence_count", 0),
            insight.get("time_range_start"),
            insight.get("time_range_end"),
            insight.get("ai_model", "gemini-1.5-flash"),
            insight["confidence"],
            insight.get("reasoning", ""),
        )
        
        await client.insert("insights", [row], column_names=columns)
        return str(insight.get("id", ""))
    
    @classmethod
    async def search_events_for_rag(
        cls,
        user_id: UUID,
        query_text: str,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None,
        limit: int = 100,
    ) -> list[dict]:
        """Search events for RAG context retrieval.
        
        Uses full-text search on payload JSON.
        """
        client = cls.get_client()
        
        # Build search query with text matching
        query = """
            SELECT 
                id,
                timestamp,
                event_type,
                event_subtype,
                latitude,
                longitude,
                payload
            FROM events
            WHERE user_id = {user_id:UUID}
              AND (
                  hasToken(lower(payload), lower({search_text:String}))
                  OR lower(event_subtype) LIKE lower({search_pattern:String})
              )
        """
        
        params = {
            "user_id": str(user_id),
            "search_text": query_text,
            "search_pattern": f"%{query_text}%",
            "limit": limit,
        }
        
        if start_time:
            query += " AND timestamp >= {start_time:DateTime64}"
            params["start_time"] = start_time
        
        if end_time:
            query += " AND timestamp <= {end_time:DateTime64}"
            params["end_time"] = end_time
        
        query += " ORDER BY timestamp DESC LIMIT {limit:UInt32}"
        
        result = await client.query(query, parameters=params)
        
        return [
            {
                "id": str(row[0]),
                "timestamp": row[1].isoformat() if row[1] else None,
                "event_type": row[2],
                "event_subtype": row[3],
                "latitude": row[4],
                "longitude": row[5],
                "payload": json.loads(row[6]) if row[6] else {},
            }
            for row in result.result_rows
        ]
    
    @classmethod
    async def get_event_stats(cls, user_id: UUID) -> dict:
        """Get event statistics for user."""
        client = cls.get_client()
        
        query = """
            SELECT 
                event_type,
                count() as cnt,
                min(timestamp) as first_event,
                max(timestamp) as last_event
            FROM events
            WHERE user_id = {user_id:UUID}
            GROUP BY event_type
            ORDER BY cnt DESC
        """
        
        result = await client.query(query, parameters={"user_id": str(user_id)})
        
        stats = {
            "total_events": 0,
            "by_type": {},
            "first_event": None,
            "last_event": None,
        }
        
        for row in result.result_rows:
            event_type = row[0]
            count = row[1]
            first = row[2]
            last = row[3]
            
            stats["total_events"] += count
            stats["by_type"][event_type] = {
                "count": count,
                "first": first.isoformat() if first else None,
                "last": last.isoformat() if last else None,
            }
            
            if first and (not stats["first_event"] or first < stats["first_event"]):
                stats["first_event"] = first
            if last and (not stats["last_event"] or last > stats["last_event"]):
                stats["last_event"] = last
        
        if stats["first_event"]:
            stats["first_event"] = stats["first_event"].isoformat()
        if stats["last_event"]:
            stats["last_event"] = stats["last_event"].isoformat()
        
        return stats
