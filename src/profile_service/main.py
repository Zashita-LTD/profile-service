"""Profile Service - FastAPI Application."""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import get_settings
from .database import Neo4jDatabase, init_constraints
from .routers import (
    persons_router,
    companies_router,
    relationships_router,
    graph_router,
)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan handler."""
    # Startup
    settings = get_settings()
    print(f"🚀 Starting {settings.service_name} v{settings.service_version}")

    await Neo4jDatabase.connect()
    print("✅ Connected to Neo4j")

    await init_constraints()
    print("✅ Database constraints initialized")

    yield

    # Shutdown
    await Neo4jDatabase.disconnect()
    print("👋 Disconnected from Neo4j")


settings = get_settings()

app = FastAPI(
    title="Profile Service",
    description="Graph-based profile service with Neo4j",
    version=settings.service_version,
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

# Routers
app.include_router(persons_router, prefix="/api")
app.include_router(companies_router, prefix="/api")
app.include_router(relationships_router, prefix="/api")
app.include_router(graph_router, prefix="/api")


@app.get("/")
async def root() -> dict:
    """Root endpoint."""
    return {
        "service": settings.service_name,
        "version": settings.service_version,
        "docs": "/docs",
    }


@app.get("/health")
async def health() -> dict:
    """Health check endpoint."""
    return {"status": "healthy"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "profile_service.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug,
    )
