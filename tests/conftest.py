"""Pytest configuration and fixtures."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, MagicMock


@pytest_asyncio.fixture
async def neo4j_session():
    """Mock Neo4j session for testing."""
    session = AsyncMock()
    
    # Store data in memory for tests
    data_store = {}
    
    async def mock_run(query, **params):
        """Mock query execution."""
        result = MagicMock()
        
        if "CREATE" in query and ":Person" in query:
            # Create person
            from uuid import uuid4
            person_id = params.get("id", str(uuid4()))
            person = {
                "id": person_id,
                "name": params.get("name"),
                "email": params.get("email"),
                "phone": params.get("phone"),
                "bio": params.get("bio"),
                "location": params.get("location"),
            }
            data_store[person_id] = person
            
            record = MagicMock()
            record.data.return_value = {"p": person}
            result.single.return_value = record
            
        elif "MATCH (p:Person {id:" in query or "MATCH (p:Person)" in query and "WHERE p.id" in query:
            # Get by ID
            person_id = params.get("id")
            if person_id in data_store:
                record = MagicMock()
                record.data.return_value = {"p": data_store[person_id]}
                result.single.return_value = record
            else:
                result.single.return_value = None
                
        elif "DELETE" in query:
            # Delete
            person_id = params.get("id")
            if person_id in data_store:
                del data_store[person_id]
            result.single.return_value = MagicMock()
            result.single.return_value.data.return_value = {"deleted": True}
            
        elif "SET" in query:
            # Update
            person_id = params.get("id")
            if person_id in data_store:
                for key, value in params.items():
                    if key != "id" and value is not None:
                        data_store[person_id][key] = value
                record = MagicMock()
                record.data.return_value = {"p": data_store[person_id]}
                result.single.return_value = record
            else:
                result.single.return_value = None
                
        else:
            # Search and other queries
            records = []
            query_lower = params.get("query", "").lower() if "query" in params else ""
            for person in data_store.values():
                if query_lower and query_lower in person.get("name", "").lower():
                    record = MagicMock()
                    record.data.return_value = {"p": person}
                    records.append(record)
            
            async def async_iter():
                for r in records:
                    yield r
            
            result.__aiter__ = lambda: async_iter()
        
        return result
    
    session.run = mock_run
    
    yield session
