
from fastapi import APIRouter, Depends, status
from fastapi.security import OAuth2PasswordRequestForm

from ..schemas.auth import UserCreate, Token, UserResponse
from ..dependencies import get_db_pool
from ..repositories.user_repository import UserRepository
from ..services.auth_service import AuthService
from ..limiter import limiter
from fastapi import Request

router = APIRouter()

async def get_auth_service(db = Depends(get_db_pool)) -> AuthService:
    return AuthService(UserRepository(db))

@router.post("/auth/register", status_code=status.HTTP_201_CREATED)
@limiter.limit("5/minute")
async def register(
    user_data: UserCreate, 
    request: Request,
    service: AuthService = Depends(get_auth_service)
):
    """Register a new user"""
    user_id = await service.register_user(user_data)
    return {"id": user_id, "username": user_data.username, "message": "User registered successfully"}

@router.post("/auth/login", response_model=Token)
@limiter.limit("10/minute")
async def login(
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    service: AuthService = Depends(get_auth_service)
):
    """Login to get JWT token"""
    # map form_data to schema
    # OAuth2PasswordRequestForm has username and password
    from ..schemas.auth import UserLogin
    login_data = UserLogin(username=form_data.username, password=form_data.password)
    return await service.authenticate_user(login_data)
