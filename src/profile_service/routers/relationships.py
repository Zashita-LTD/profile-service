"""Relationship API endpoints."""

from fastapi import APIRouter, HTTPException

from ..models.relationships import (
    WorksAtRelation,
    KnowsRelation,
    InterestedInRelation,
    HasSkillRelation,
    ParticipatedInRelation,
)
from ..repositories.relationship_repo import RelationshipRepository

router = APIRouter(prefix="/relationships", tags=["Relationships"])


@router.post("/works-at", status_code=201)
async def create_works_at(data: WorksAtRelation) -> dict:
    """Create WORKS_AT relationship: Person works at Company."""
    success = await RelationshipRepository.create_works_at(data)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Failed to create relationship. Check if Person and Company exist.",
        )
    return {"status": "created", "relationship": "WORKS_AT"}


@router.delete("/works-at/{person_id}/{company_id}", status_code=204)
async def remove_works_at(person_id: str, company_id: str) -> None:
    """Remove WORKS_AT relationship."""
    deleted = await RelationshipRepository.remove_works_at(person_id, company_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Relationship not found")


@router.post("/knows", status_code=201)
async def create_knows(data: KnowsRelation) -> dict:
    """Create KNOWS relationship: Person knows Person."""
    if data.person_id == data.other_person_id:
        raise HTTPException(status_code=400, detail="Person cannot know themselves")

    success = await RelationshipRepository.create_knows(data)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Failed to create relationship. Check if both Persons exist.",
        )
    return {"status": "created", "relationship": "KNOWS"}


@router.patch("/knows/{person_id}/{other_person_id}/strength")
async def update_knows_strength(
    person_id: str, other_person_id: str, strength: float
) -> dict:
    """Update KNOWS relationship strength."""
    if strength < 0 or strength > 1:
        raise HTTPException(status_code=400, detail="Strength must be between 0 and 1")

    success = await RelationshipRepository.update_knows_strength(
        person_id, other_person_id, strength
    )
    if not success:
        raise HTTPException(status_code=404, detail="Relationship not found")
    return {"status": "updated", "strength": strength}


@router.post("/interested-in", status_code=201)
async def create_interested_in(data: InterestedInRelation) -> dict:
    """Create INTERESTED_IN relationship: Person interested in Interest."""
    success = await RelationshipRepository.create_interested_in(data)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Failed to create relationship. Check if Person exists.",
        )
    return {"status": "created", "relationship": "INTERESTED_IN", "interest": data.interest_name}


@router.delete("/interested-in/{person_id}/{interest_name}", status_code=204)
async def remove_interested_in(person_id: str, interest_name: str) -> None:
    """Remove INTERESTED_IN relationship."""
    deleted = await RelationshipRepository.remove_interested_in(person_id, interest_name)
    if not deleted:
        raise HTTPException(status_code=404, detail="Relationship not found")


@router.post("/has-skill", status_code=201)
async def create_has_skill(data: HasSkillRelation) -> dict:
    """Create HAS_SKILL relationship: Person has Skill."""
    success = await RelationshipRepository.create_has_skill(data)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Failed to create relationship. Check if Person exists.",
        )
    return {"status": "created", "relationship": "HAS_SKILL", "skill": data.skill_name}


@router.delete("/has-skill/{person_id}/{skill_name}", status_code=204)
async def remove_has_skill(person_id: str, skill_name: str) -> None:
    """Remove HAS_SKILL relationship."""
    deleted = await RelationshipRepository.remove_has_skill(person_id, skill_name)
    if not deleted:
        raise HTTPException(status_code=404, detail="Relationship not found")


@router.post("/participated-in", status_code=201)
async def create_participated_in(data: ParticipatedInRelation) -> dict:
    """Create PARTICIPATED_IN relationship: Person participated in Event."""
    success = await RelationshipRepository.create_participated_in(data)
    if not success:
        raise HTTPException(
            status_code=400,
            detail="Failed to create relationship. Check if Person and Event exist.",
        )
    return {"status": "created", "relationship": "PARTICIPATED_IN"}
