"""Profile Service - Universal Human Profile / Digital Biographer.

FastAPI application with GraphQL API, Neo4j graph database, and AI analysis.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.neo4j import Neo4jDB
from app.db.postgres import init_postgres, close_postgres
from app.api.graphql.schema import graphql_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    settings = get_settings()
    print(f"🚀 Starting Profile Service v0.2.0")
    print(f"📊 Connecting to Neo4j: {settings.neo4j_uri}")
    print(f"🐘 Connecting to PostgreSQL: {settings.postgres_host}")
    
    await Neo4jDB.connect()
    await init_postgres()
    
    print("✅ All databases connected")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down...")
    await Neo4jDB.disconnect()
    await close_postgres()
    print("👋 Goodbye!")


# Create FastAPI app
app = FastAPI(
    title="Profile Service",
    description="""
    ## Universal Human Profile - Digital Biographer
    
    Сервис для построения глубоких цифровых профилей людей (Human Knowledge Graph).
    
    ### Возможности:
    
    - 🔗 **GraphQL API** - гибкие запросы к графу связей
    - 🧠 **AI Biography** - генерация связных биографий
    - 🎯 **Expert Search** - поиск экспертов по навыкам
    - 🔍 **Path Finding** - поиск пути между людьми
    - 📧 **Email Analysis** - анализ стиля общения
    - 📄 **Resume Import** - импорт из резюме
    - 💼 **LinkedIn Import** - импорт из LinkedIn
    
    ### GraphQL Endpoint: `/graphql`
    
    Примеры запросов:
    
    ```graphql
    query {
        person(id: "...") {
            name
            career { company { name } role }
            friends(depth: 2) { person { name } distance }
            personality { personalityType communicationStyle }
        }
    }
    
    query {
        findExperts(skill: "BIM", location: "Moscow") {
            person { name }
            skill { level yearsExperience }
        }
    }
    
    mutation {
        generateBiography(input: {personId: "...", style: "professional"}) {
            content
            factsCount
        }
    }
    ```
    """,
    version="0.2.0",
    lifespan=lifespan,
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# GraphQL router
app.include_router(graphql_router, prefix="/graphql")


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "Profile Service - Digital Biographer",
        "version": "0.2.0",
        "graphql": "/graphql",
        "docs": "/docs",
        "features": [
            "GraphQL API",
            "Neo4j Knowledge Graph",
            "AI Biography Generator",
            "Expert Search",
            "Path Finding (6 degrees)",
            "Email/Resume/LinkedIn Import",
            "Personality Analysis",
        ],
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "neo4j": "connected",
        "postgres": "connected",
    }


# REST API endpoints for ingestion
from fastapi import HTTPException
from pydantic import BaseModel
from typing import Optional


class EmailInput(BaseModel):
    content: str
    person_id: Optional[str] = None


class ResumeInput(BaseModel):
    content: str


class LinkedInInput(BaseModel):
    profile: dict
    url: Optional[str] = None


class ContactInput(BaseModel):
    name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    company: Optional[str] = None


@app.post("/api/ingest/email")
async def ingest_email(data: EmailInput):
    """Process email and extract information."""
    from app.ingestion.email_parser import EmailParser
    
    parser = EmailParser()
    result = await parser.extract_and_enrich(data.content, data.person_id)
    
    return {
        "success": True,
        "person_id": result.get("person_id"),
        "enriched": result.get("enriched"),
        "sender": {
            "name": result["analysis"].sender_name,
            "email": result["analysis"].sender_email,
            "company": result["analysis"].sender_company,
        },
        "style": {
            "formality": result["analysis"].formality,
            "tone": result["analysis"].tone,
        },
    }


@app.post("/api/ingest/resume")
async def ingest_resume(data: ResumeInput):
    """Import resume and create/update person."""
    from app.ingestion.resume_parser import ResumeParser
    
    parser = ResumeParser()
    result = await parser.import_to_graph(data.content)
    
    if not result.get("person_id"):
        raise HTTPException(status_code=400, detail="Could not parse resume")
    
    return {
        "success": True,
        "person_id": result["person_id"],
        "created": result.get("created", False),
        "updated": result.get("updated", False),
        "parsed": {
            "name": result["parsed"].name,
            "email": result["parsed"].email,
            "skills_count": len(result["parsed"].skills),
            "career_count": len(result["parsed"].career),
        },
    }


@app.post("/api/ingest/linkedin")
async def ingest_linkedin(data: LinkedInInput):
    """Import LinkedIn profile."""
    from app.ingestion.linkedin_parser import LinkedInParser
    
    parser = LinkedInParser()
    result = await parser.import_to_graph(data.profile, data.url)
    
    if not result.get("person_id"):
        raise HTTPException(status_code=400, detail="Could not parse LinkedIn profile")
    
    return {
        "success": True,
        "person_id": result["person_id"],
        "created": result.get("created", False),
        "parsed": {
            "name": result["parsed"].name,
            "headline": result["parsed"].headline,
            "connections": result["parsed"].connections_count,
        },
    }


@app.post("/api/ingest/contact")
async def ingest_contact(data: ContactInput):
    """Create person from simple contact."""
    from app.ingestion.enrichment import EnrichmentPipeline
    
    pipeline = EnrichmentPipeline()
    result = await pipeline.process_event({
        "type": "contact",
        "source": "api",
        "payload": data.model_dump(),
    })
    
    if not result.get("processed"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to create contact"))
    
    return {
        "success": True,
        "person_id": result["person_id"],
    }


if __name__ == "__main__":
    import uvicorn
    
    settings = get_settings()
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.api_debug,
    )
