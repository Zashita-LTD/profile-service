"""Tests for Person repository."""

import pytest
from uuid import uuid4

from profile_service.repositories.person_repo import PersonRepository


@pytest.mark.asyncio
async def test_create_person(neo4j_session):
    """Test creating a person."""
    repo = PersonRepository()
    
    person_data = {
        "name": "Test User",
        "email": "test@example.com",
        "phone": "+7999123456",
        "location": "Moscow"
    }
    
    result = await repo.create(neo4j_session, **person_data)
    
    assert result is not None
    assert result["name"] == "Test User"
    assert result["email"] == "test@example.com"
    assert "id" in result


@pytest.mark.asyncio
async def test_get_person_by_id(neo4j_session):
    """Test getting a person by ID."""
    repo = PersonRepository()
    
    # Create first
    created = await repo.create(neo4j_session, name="Get Test", email="get@test.com")
    person_id = created["id"]
    
    # Get by ID
    result = await repo.get_by_id(neo4j_session, person_id)
    
    assert result is not None
    assert result["id"] == person_id
    assert result["name"] == "Get Test"


@pytest.mark.asyncio
async def test_update_person(neo4j_session):
    """Test updating a person."""
    repo = PersonRepository()
    
    # Create first
    created = await repo.create(neo4j_session, name="Update Test", email="update@test.com")
    person_id = created["id"]
    
    # Update
    result = await repo.update(neo4j_session, person_id, name="Updated Name")
    
    assert result is not None
    assert result["name"] == "Updated Name"
    assert result["email"] == "update@test.com"


@pytest.mark.asyncio
async def test_delete_person(neo4j_session):
    """Test deleting a person."""
    repo = PersonRepository()
    
    # Create first
    created = await repo.create(neo4j_session, name="Delete Test", email="delete@test.com")
    person_id = created["id"]
    
    # Delete
    deleted = await repo.delete(neo4j_session, person_id)
    assert deleted is True
    
    # Verify deleted
    result = await repo.get_by_id(neo4j_session, person_id)
    assert result is None


@pytest.mark.asyncio
async def test_search_persons(neo4j_session):
    """Test searching persons."""
    repo = PersonRepository()
    
    # Create test data
    await repo.create(neo4j_session, name="Search Viktor", email="viktor@search.com")
    await repo.create(neo4j_session, name="Search Maria", email="maria@search.com")
    await repo.create(neo4j_session, name="Other Person", email="other@test.com")
    
    # Search
    results = await repo.search(neo4j_session, query="Search")
    
    assert len(results) == 2
    names = [r["name"] for r in results]
    assert "Search Viktor" in names
    assert "Search Maria" in names
