"""Graph query API endpoints."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from ..models.relationships import GraphPath
from ..repositories.graph_repo import GraphRepository

router = APIRouter(prefix="/graph", tags=["Graph Queries"])


@router.get("/connections/{person_id}")
async def get_connections(
    person_id: UUID,
    min_strength: float = Query(0.0, ge=0.0, le=1.0),
    limit: int = Query(50, ge=1, le=200),
) -> list[dict]:
    """Get all connections for a person."""
    connections = await GraphRepository.get_connections(
        person_id, min_strength=min_strength, limit=limit
    )
    return [c.model_dump() for c in connections]


@router.get("/shortest-path", response_model=GraphPath | None)
async def get_shortest_path(
    person1_id: UUID,
    person2_id: UUID,
    max_depth: int = Query(6, ge=1, le=10),
) -> GraphPath | None:
    """Find shortest path between two persons."""
    if person1_id == person2_id:
        raise HTTPException(status_code=400, detail="Cannot find path to self")

    path = await GraphRepository.get_shortest_path(person1_id, person2_id, max_depth)
    if not path:
        raise HTTPException(
            status_code=404,
            detail=f"No path found within {max_depth} hops",
        )
    return path


@router.get("/common-interests/{person_id}")
async def get_common_interests(
    person_id: UUID,
    limit: int = Query(20, ge=1, le=100),
) -> list[dict]:
    """Find people with common interests."""
    return await GraphRepository.get_common_interests(person_id, limit=limit)


@router.get("/colleagues/{person_id}")
async def get_colleagues(person_id: UUID) -> list[dict]:
    """Find colleagues (people working at the same company)."""
    return await GraphRepository.get_colleagues(person_id)


@router.get("/stats/{person_id}")
async def get_network_stats(person_id: UUID) -> dict:
    """Get network statistics for a person."""
    return await GraphRepository.get_network_stats(person_id)


@router.get("/influencers")
async def get_influencers(
    limit: int = Query(10, ge=1, le=50),
) -> list[dict]:
    """Find most connected people (influencers)."""
    return await GraphRepository.find_influencers(limit=limit)


@router.get("/recommendations/{person_id}")
async def get_recommendations(
    person_id: UUID,
    limit: int = Query(10, ge=1, le=50),
) -> list[dict]:
    """Get connection recommendations for a person."""
    return await GraphRepository.recommend_connections(person_id, limit=limit)
