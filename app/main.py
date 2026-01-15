"""Profile Service - Universal Human Profile / Digital Biographer.

FastAPI application with GraphQL API, Neo4j graph database, ClickHouse analytics,
MinIO media storage, ChromaDB embeddings, and AI analysis.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.db.neo4j import Neo4jDB
from app.db.postgres import init_postgres, close_postgres
from app.api.graphql.schema import graphql_router
from app.life_stream.clickhouse import ClickHouseDB
from app.life_stream.api import ingest_router, memory_router
from app.media.api import router as media_router
from app.media.storage import MediaStorage
from app.agent.api import router as agent_router
from app.api.nft import router as nft_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    settings = get_settings()
    print(f"🚀 Starting Profile Service v0.4.0")
    print(f"📊 Connecting to Neo4j: {settings.neo4j_uri}")
    print(f"🐘 Connecting to PostgreSQL: {settings.postgres_host}")
    print(f"⚡ Connecting to ClickHouse: {settings.clickhouse_host}:{settings.clickhouse_port}")
    print(f"📦 Connecting to MinIO: {settings.minio_endpoint}")
    print(f"🧠 Connecting to ChromaDB: {settings.chromadb_host}:{settings.chromadb_port}")
    
    await Neo4jDB.connect()
    await init_postgres()
    
    # Connect to ClickHouse for Life Stream
    try:
        await ClickHouseDB.connect()
        print("✅ ClickHouse connected (Life Stream enabled)")
    except Exception as e:
        print(f"⚠️ ClickHouse not available: {e}")
        print("   Life Stream features will be disabled")
    
    # Connect to MinIO for Media Storage
    try:
        media_storage = MediaStorage()
        await media_storage.connect()
        app.state.media_storage = media_storage
        print("✅ MinIO connected (Media Storage enabled)")
    except Exception as e:
        print(f"⚠️ MinIO not available: {e}")
        print("   Media features will be disabled")
        app.state.media_storage = None
    
    # Connect to ChromaDB for Embeddings
    try:
        import chromadb
        chroma_client = chromadb.HttpClient(
            host=settings.chromadb_host,
            port=settings.chromadb_port,
        )
        app.state.chroma_client = chroma_client
        print("✅ ChromaDB connected (Embeddings enabled)")
    except Exception as e:
        print(f"⚠️ ChromaDB not available: {e}")
        print("   Embedding search will be disabled")
        app.state.chroma_client = None
    
    print("✅ All databases connected")
    
    yield
    
    # Shutdown
    print("🛑 Shutting down...")
    await Neo4jDB.disconnect()
    await close_postgres()
    await ClickHouseDB.disconnect()
    if hasattr(app.state, 'media_storage') and app.state.media_storage:
        await app.state.media_storage.disconnect()
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
    
    ### 🆕 Life Stream Module (Big Data):
    
    - ⚡ **ClickHouse Integration** - высокопроизводительное хранение событий
    - 📍 **Geo Tracking** - отслеживание локации и маршрутов
    - 💳 **Purchase History** - история покупок и транзакций
    - 🤝 **Social Events** - встречи и взаимодействия
    - 🧩 **Pattern Mining** - автоматическое обнаружение паттернов и привычек
    - 🧠 **Memory Search** - "Второй мозг" с RAG поиском
    
    ### 🆕 Media Understanding Module:
    
    - 📷 **Media Storage** - MinIO S3-совместимое хранилище
    - 🔐 **Encryption at Rest** - AES-256-GCM шифрование
    - 🖼️ **Vision AI** - Gemini Vision анализ изображений и видео
    - 🎨 **Taste Graph** - граф предпочтений (бренды, стили, лайфстайл)
    - 🔍 **Similarity Search** - поиск похожих изображений через ChromaDB
    
    ### 🆕 Personal Agent Module:
    
    - 🤖 **Agent Factory** - создание персонального AI-агента
    - 🧠 **Personality Model** - личностные черты из профиля
    - 🛠️ **Tool Use** - агент умеет искать, сравнивать, рекомендовать
    - 🤝 **A2A Protocol** - Agent-to-Agent переговоры через Kafka
    - ⚡ **Quick Actions** - быстрые действия без полного task flow
    
    ### GraphQL Endpoint: `/graphql`
    
    ### Life Stream Endpoints:
    - `POST /api/v1/stream/ingest` - прием потока событий
    - `GET /api/v1/stream/events/{user_id}` - получение событий
    - `GET /api/v1/stream/patterns/{user_id}` - обнаруженные паттерны
    - `POST /api/v1/search/memory` - поиск по памяти (RAG)
    
    ### Media Endpoints:
    - `POST /api/v1/media/upload` - загрузка медиа
    - `GET /api/v1/media/{user_id}/gallery` - галерея пользователя
    - `GET /api/v1/media/{user_id}/taste-profile` - профиль вкусов
    - `POST /api/v1/media/{user_id}/similar` - поиск похожих
    
    ### Agent Endpoints:
    - `POST /api/v1/agent/train` - обучение персонального агента
    - `POST /api/v1/agent/{user_id}/task` - создание задачи агенту
    - `POST /api/v1/agent/{user_id}/quick` - быстрое действие
    - `POST /api/v1/agent/{user_id}/negotiate/start` - начать переговоры
    
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
    version="0.4.0",
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

# Life Stream routers
app.include_router(ingest_router)
app.include_router(memory_router)

# Media router
app.include_router(media_router, prefix="/api/v1")

# Agent router
app.include_router(agent_router, prefix="/api/v1")

# NFT/Blockchain router
app.include_router(nft_router, prefix="/api/v1")


@app.get("/")
async def root():
    """Root endpoint with service info."""
    return {
        "service": "Profile Service - Digital Biographer",
        "version": "0.4.0",
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
            # Life Stream
            "Life Stream (Big Data)",
            "ClickHouse Analytics",
            "Pattern Mining AI",
            "Memory Search (RAG)",
            # Media Understanding
            "Media Understanding",
            "MinIO Storage (S3)",
            "Vision AI Analysis",
            "Taste Graph",
            "Similarity Search",
            # Personal Agent
            "Personal Agent",
            "Agent Factory",
            "A2A Protocol",
            "Tool Use & Tasks",
        ],
        "life_stream": {
            "ingest": "/api/v1/stream/ingest",
            "events": "/api/v1/stream/events/{user_id}",
            "patterns": "/api/v1/stream/patterns/{user_id}",
            "memory_search": "/api/v1/search/memory",
        },
        "media": {
            "upload": "/api/v1/media/upload",
            "gallery": "/api/v1/media/{user_id}/gallery",
            "taste_profile": "/api/v1/media/{user_id}/taste-profile",
            "similar": "/api/v1/media/{user_id}/similar",
        },
        "agent": {
            "train": "/api/v1/agent/train",
            "task": "/api/v1/agent/{user_id}/task",
            "quick": "/api/v1/agent/{user_id}/quick",
            "negotiate": "/api/v1/agent/{user_id}/negotiate/start",
        },
    }


@app.get("/health")
async def health():
    """Health check endpoint."""
    # Check ClickHouse
    clickhouse_status = "disconnected"
    try:
        if ClickHouseDB._client:
            clickhouse_status = "connected"
    except Exception:
        pass
    
    # Check MinIO
    minio_status = "disconnected"
    try:
        if hasattr(app.state, 'media_storage') and app.state.media_storage:
            minio_status = "connected"
    except Exception:
        pass
    
    # Check ChromaDB
    chromadb_status = "disconnected"
    try:
        if hasattr(app.state, 'chroma_client') and app.state.chroma_client:
            chromadb_status = "connected"
    except Exception:
        pass
    
    return {
        "status": "healthy",
        "neo4j": "connected",
        "postgres": "connected",
        "clickhouse": clickhouse_status,
        "minio": minio_status,
        "chromadb": chromadb_status,
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
