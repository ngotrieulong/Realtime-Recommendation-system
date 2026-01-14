
import pytest
from unittest.mock import AsyncMock, patch
from fastapi import HTTPException
from app.services.auth_service import AuthService
from app.schemas.auth import UserCreate, UserLogin
from app.core.security import get_password_hash

@pytest.mark.asyncio
async def test_register_user_success():
    # Arrange
    mock_repo = AsyncMock()
    mock_repo.get_by_username.return_value = None
    mock_repo.get_by_email.return_value = None
    mock_repo.create_user.return_value = 1
    
    service = AuthService(mock_repo)
    user_data = UserCreate(username="testuser", email="test@example.com", password="password123")
    
    # Act
    user_id = await service.register_user(user_data)
    
    # Assert
    assert user_id == 1
    mock_repo.create_user.assert_called_once()
    
@pytest.mark.asyncio
async def test_register_user_already_exists_username():
    # Arrange
    mock_repo = AsyncMock()
    mock_repo.get_by_username.return_value = {"id": 1, "username": "testuser"}
    
    service = AuthService(mock_repo)
    user_data = UserCreate(username="testuser", email="test@example.com", password="password123")
    
    # Act & Assert
    with pytest.raises(HTTPException) as exc:
        await service.register_user(user_data)
    assert exc.value.status_code == 400
    assert "Username already registered" in exc.value.detail

@pytest.mark.asyncio
async def test_authenticate_user_success():
    # Arrange
    mock_repo = AsyncMock()
    hashed = get_password_hash("password123")
    mock_repo.get_by_username.return_value = {
        "id": 1, 
        "username": "testuser", 
        "hashed_password": hashed
    }
    
    service = AuthService(mock_repo)
    login_data = UserLogin(username="testuser", password="password123")
    
    # Act
    token = await service.authenticate_user(login_data)
    
    # Assert
    assert token.access_token is not None
    assert token.token_type == "bearer"

@pytest.mark.asyncio
async def test_authenticate_user_invalid_password():
    # Arrange
    mock_repo = AsyncMock()
    hashed = get_password_hash("password123")
    mock_repo.get_by_username.return_value = {
        "id": 1, 
        "username": "testuser", 
        "hashed_password": hashed
    }
    
    service = AuthService(mock_repo)
    login_data = UserLogin(username="testuser", password="wrongpassword")
    
    # Act & Assert
    with pytest.raises(HTTPException) as exc:
        await service.authenticate_user(login_data)
    assert exc.value.status_code == 401
