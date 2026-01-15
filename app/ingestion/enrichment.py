"""Enrichment Pipeline - orchestrates data enrichment from various sources."""

from typing import Optional
from datetime import datetime

from app.ingestion.email_parser import EmailParser
from app.ingestion.resume_parser import ResumeParser
from app.ingestion.linkedin_parser import LinkedInParser


class EnrichmentPipeline:
    """Orchestrates enrichment from multiple data sources."""
    
    def __init__(self):
        """Initialize pipeline with parsers."""
        self.email_parser = EmailParser()
        self.resume_parser = ResumeParser()
        self.linkedin_parser = LinkedInParser()
    
    async def process_event(self, event: dict) -> dict:
        """Process incoming event and enrich person data.
        
        Args:
            event: Event dictionary with type and payload
            
        Returns:
            Processing result
        """
        event_type = event.get("type", "")
        payload = event.get("payload", {})
        
        result = {
            "event_type": event_type,
            "processed": False,
            "person_id": None,
            "error": None,
        }
        
        try:
            if event_type == "email":
                result.update(await self._process_email(payload))
            elif event_type == "resume":
                result.update(await self._process_resume(payload))
            elif event_type == "linkedin":
                result.update(await self._process_linkedin(payload))
            elif event_type == "contact":
                result.update(await self._process_contact(payload))
            else:
                result["error"] = f"Unknown event type: {event_type}"
        except Exception as e:
            result["error"] = str(e)
        
        # Log event
        await self._log_event(event, result)
        
        return result
    
    async def _process_email(self, payload: dict) -> dict:
        """Process email event."""
        content = payload.get("content", "")
        person_id = payload.get("person_id")
        
        result = await self.email_parser.extract_and_enrich(content, person_id)
        
        return {
            "processed": True,
            "person_id": result.get("person_id"),
            "enriched": result.get("enriched", False),
            "data": {
                "sender_name": result["analysis"].sender_name,
                "sender_email": result["analysis"].sender_email,
                "style": {
                    "formality": result["analysis"].formality,
                    "tone": result["analysis"].tone,
                },
            },
        }
    
    async def _process_resume(self, payload: dict) -> dict:
        """Process resume event."""
        content = payload.get("content", "")
        
        result = await self.resume_parser.import_to_graph(content)
        
        return {
            "processed": True,
            "person_id": result.get("person_id"),
            "created": result.get("created", False),
            "data": {
                "name": result["parsed"].name,
                "skills_count": len(result["parsed"].skills),
                "career_count": len(result["parsed"].career),
            },
        }
    
    async def _process_linkedin(self, payload: dict) -> dict:
        """Process LinkedIn profile event."""
        profile_data = payload.get("profile", {})
        linkedin_url = payload.get("url")
        
        result = await self.linkedin_parser.import_to_graph(profile_data, linkedin_url)
        
        return {
            "processed": True,
            "person_id": result.get("person_id"),
            "created": result.get("created", False),
            "data": {
                "name": result["parsed"].name,
                "headline": result["parsed"].headline,
                "connections": result["parsed"].connections_count,
            },
        }
    
    async def _process_contact(self, payload: dict) -> dict:
        """Process simple contact event (vCard, phone contact)."""
        from app.graph.queries import GraphQueries
        
        name = payload.get("name")
        email = payload.get("email")
        phone = payload.get("phone")
        company = payload.get("company")
        
        if not name:
            return {"processed": False, "error": "Name is required"}
        
        # Create or find person
        person = None
        if email:
            person = await GraphQueries.get_person_by_email(email)
        
        if not person:
            person = await GraphQueries.create_person(
                name=name,
                email=email,
                phone=phone,
            )
        
        person_id = person.id
        
        # If company provided, create relationship
        if company:
            from app.db.neo4j import Neo4jDB
            async with Neo4jDB.session() as session:
                await session.run("""
                    MERGE (c:Company {name: $company})
                    ON CREATE SET c.id = randomUUID()
                    WITH c
                    MATCH (p:Person {id: $person_id})
                    MERGE (p)-[r:WORKS_AT]->(c)
                    SET r.is_current = true
                """,
                    company=company,
                    person_id=person_id,
                )
        
        return {
            "processed": True,
            "person_id": person_id,
            "created": True,
        }
    
    async def _log_event(self, event: dict, result: dict) -> None:
        """Log event processing to PostgreSQL."""
        from app.db.postgres import get_db
        from app.db.models import EventLog
        
        try:
            async with get_db() as session:
                log = EventLog(
                    event_type=event.get("type", "unknown"),
                    source=event.get("source", "unknown"),
                    payload=event,
                    status="completed" if result.get("processed") else "failed",
                    error_message=result.get("error"),
                    person_id=result.get("person_id"),
                    processed_at=datetime.utcnow() if result.get("processed") else None,
                )
                session.add(log)
        except Exception as e:
            print(f"Failed to log event: {e}")
    
    async def enrich_from_all_sources(
        self,
        person_id: str,
        email_content: Optional[str] = None,
        resume_content: Optional[str] = None,
        linkedin_data: Optional[dict] = None,
    ) -> dict:
        """Enrich person from multiple sources at once.
        
        Args:
            person_id: Person ID to enrich
            email_content: Optional email content
            resume_content: Optional resume content
            linkedin_data: Optional LinkedIn profile data
            
        Returns:
            Enrichment summary
        """
        summary = {
            "person_id": person_id,
            "sources_processed": [],
            "facts_added": 0,
        }
        
        if email_content:
            result = await self.email_parser.extract_and_enrich(email_content, person_id)
            if result.get("enriched"):
                summary["sources_processed"].append("email")
                summary["facts_added"] += len(result.get("analysis", {}).facts or [])
        
        if resume_content:
            result = await self.resume_parser.import_to_graph(resume_content)
            if result.get("updated") or result.get("created"):
                summary["sources_processed"].append("resume")
                summary["facts_added"] += len(result.get("parsed", {}).skills or [])
        
        if linkedin_data:
            result = await self.linkedin_parser.import_to_graph(linkedin_data)
            if result.get("updated") or result.get("created"):
                summary["sources_processed"].append("linkedin")
                summary["facts_added"] += len(result.get("parsed", {}).skills or [])
        
        return summary
