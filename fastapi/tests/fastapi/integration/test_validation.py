
import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_register_invalid_email(client: AsyncClient):
    response = await client.post("/auth/register", json={
        "username": "validuser",
        "email": "not-an-email",
        "password": "securepassword"
    })
    assert response.status_code == 422
    
@pytest.mark.asyncio
async def test_register_short_password(client: AsyncClient):
    response = await client.post("/auth/register", json={
        "username": "validuser",
        "email": "valid@example.com",
        "password": "short" # < 8 chars
    })
    assert response.status_code == 422
