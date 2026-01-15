"""Person API endpoints."""

from typing import Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query

from ..models.person import Person, PersonCreate, PersonUpdate, PersonWithRelations
from ..repositories.person_repo import PersonRepository

router = APIRouter(prefix="/persons", tags=["Persons"])


@router.post("", response_model=Person, status_code=201)
async def create_person(data: PersonCreate) -> Person:
    """Create a new person."""
    return await PersonRepository.create(data)


@router.get("", response_model=list[Person])
async def list_persons(
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=500),
) -> list[Person]:
    """List all persons with pagination."""
    return await PersonRepository.list_all(skip=skip, limit=limit)


@router.get("/search", response_model=list[Person])
async def search_persons(
    q: str = Query(..., min_length=1),
    limit: int = Query(20, ge=1, le=100),
) -> list[Person]:
    """Search persons by name or email."""
    return await PersonRepository.search(q, limit=limit)


@router.get("/{person_id}", response_model=Person)
async def get_person(person_id: UUID) -> Person:
    """Get a person by ID."""
    person = await PersonRepository.get_by_id(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return person


@router.get("/{person_id}/full", response_model=PersonWithRelations)
async def get_person_full(person_id: UUID) -> PersonWithRelations:
    """Get a person with all relations."""
    person = await PersonRepository.get_with_relations(person_id)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return person


@router.put("/{person_id}", response_model=Person)
async def update_person(person_id: UUID, data: PersonUpdate) -> Person:
    """Update a person."""
    person = await PersonRepository.update(person_id, data)
    if not person:
        raise HTTPException(status_code=404, detail="Person not found")
    return person


@router.delete("/{person_id}", status_code=204)
async def delete_person(person_id: UUID) -> None:
    """Delete a person."""
    deleted = await PersonRepository.delete(person_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Person not found")
