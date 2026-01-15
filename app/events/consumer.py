"""Kafka event consumer."""

import asyncio
import json
from typing import Optional

from aiokafka import AIOKafkaConsumer

from app.config import get_settings
from app.ingestion.enrichment import EnrichmentPipeline


class EventConsumer:
    """Kafka consumer for processing events from external systems."""
    
    def __init__(self):
        """Initialize consumer."""
        self.settings = get_settings()
        self.consumer: Optional[AIOKafkaConsumer] = None
        self.pipeline = EnrichmentPipeline()
        self._running = False
    
    async def start(self) -> None:
        """Start consuming events."""
        topics = self.settings.kafka_topics.split(",")
        
        self.consumer = AIOKafkaConsumer(
            *topics,
            bootstrap_servers=self.settings.kafka_bootstrap_servers,
            group_id=self.settings.kafka_consumer_group,
            value_deserializer=lambda v: json.loads(v.decode("utf-8")),
            auto_offset_reset="earliest",
        )
        
        await self.consumer.start()
        self._running = True
        
        print(f"🚀 Kafka consumer started, listening to: {topics}")
        
        try:
            async for message in self.consumer:
                if not self._running:
                    break
                    
                await self._process_message(message)
        finally:
            await self.consumer.stop()
    
    async def stop(self) -> None:
        """Stop consuming events."""
        self._running = False
        if self.consumer:
            await self.consumer.stop()
    
    async def _process_message(self, message) -> None:
        """Process a single Kafka message.
        
        Args:
            message: Kafka message
        """
        topic = message.topic
        value = message.value
        
        print(f"📨 Received message from {topic}: {value.get('type', 'unknown')}")
        
        try:
            # Map topic to event type
            event_type = self._get_event_type(topic, value)
            
            event = {
                "type": event_type,
                "source": topic,
                "payload": value.get("data", value),
            }
            
            result = await self.pipeline.process_event(event)
            
            if result.get("processed"):
                print(f"✅ Processed: person_id={result.get('person_id')}")
            else:
                print(f"❌ Failed: {result.get('error')}")
                
        except Exception as e:
            print(f"❌ Error processing message: {e}")
    
    def _get_event_type(self, topic: str, value: dict) -> str:
        """Determine event type from topic and message."""
        # Check explicit type in message
        if "type" in value:
            return value["type"]
        
        # Infer from topic name
        if "email" in topic:
            return "email"
        elif "linkedin" in topic:
            return "linkedin"
        elif "resume" in topic:
            return "resume"
        elif "contact" in topic:
            return "contact"
        
        return "unknown"


async def run_consumer():
    """Run Kafka consumer as standalone service."""
    from app.db.neo4j import Neo4jDB
    from app.db.postgres import init_postgres
    
    # Initialize databases
    await Neo4jDB.connect()
    await init_postgres()
    
    consumer = EventConsumer()
    
    try:
        await consumer.start()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down consumer...")
    finally:
        await consumer.stop()
        await Neo4jDB.disconnect()


if __name__ == "__main__":
    asyncio.run(run_consumer())
