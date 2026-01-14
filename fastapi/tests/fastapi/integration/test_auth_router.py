
import pytest
from httpx import AsyncClient
from unittest.mock import AsyncMock
from app.core.security import get_password_hash

@pytest.mark.asyncio
async def test_register_and_login_flow(client: AsyncClient, mock_db_pool: AsyncMock):
    # Setup Mock Responses
    # Sequence:
    # 1. Register:
    #    - get_by_username -> None
    #    - get_by_email -> None
    #    - create_user (fetchval) -> 1
    # 2. Login:
    #    - get_by_username -> {id: 1, ...}
    
    async def fetchrow_side_effect(query, *args):
        if "WHERE username =" in query:
            if args[0] == "integrationuser":
                # For Register (first call), we might want it to return None?
                # But fetchrow gets called multiple times.
                # Let's count calls or use a flag?
                # Or easier: setup specific behavior logic.
                pass
            return None # Default not found
        if "WHERE email =" in query:
            return None
        return None

    # We need dynamic behavior for "integrationuser"
    # First time: None (Register). Second time: User dict (Login).
    # Simple way: List iterator or side_effect function with state.
    
    state = {"registered": False}
    hashed = get_password_hash("securepassword")

    async def dynamic_fetchrow(query, *args):
        if "WHERE username =" in query:
            if args[0] == "integrationuser":
                if state["registered"]:
                    return {"id": 1, "username": "integrationuser", "email": "integration@example.com", "hashed_password": hashed, "is_active": True}
                return None
        if "WHERE email =" in query:
            return None
        return None

    mock_db_pool.fetchrow.side_effect = dynamic_fetchrow
    mock_db_pool.fetchval.return_value = 1
    
    # 1. Register
    reg_response = await client.post("/auth/register", json={
        "username": "integrationuser",
        "email": "integration@example.com",
        "password": "securepassword"
    })
    assert reg_response.status_code == 201
    data = reg_response.json()
    assert data["username"] == "integrationuser"
    
    # Update state to simulate DB commit
    state["registered"] = True
    
    # 2. Login
    login_response = await client.post("/auth/login", data={
        "username": "integrationuser",
        "password": "securepassword"
    })
    
    assert login_response.status_code == 200
    token_data = login_response.json()
    assert "access_token" in token_data
    assert token_data["token_type"] == "bearer"
    
@pytest.mark.asyncio
async def test_login_invalid_credentials(client: AsyncClient, mock_db_pool: AsyncMock):
    # Mock user exists but wrong password check relies on security lib
    hashed = get_password_hash("securepassword")
    
    async def fetchrow_side_effect(query, *args):
        if "WHERE username =" in query and args[0] == "nonexistent":
            return None
        return None

    mock_db_pool.fetchrow.side_effect = fetchrow_side_effect

    login_response = await client.post("/auth/login", data={
        "username": "nonexistent",
        "password": "wrongpassword"
    })
    assert login_response.status_code == 401
