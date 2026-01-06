
from fastapi import HTTPException, status
from datetime import timedelta

from ..repositories.user_repository import UserRepository
from ..schemas.auth import UserCreate, UserLogin, Token, AppClientCreate
from ..core.security import verify_password, get_password_hash, create_access_token, ACCESS_TOKEN_EXPIRE_MINUTES

class AuthService:
    def __init__(self, user_repo: UserRepository):
        self.user_repo = user_repo

    async def register_user(self, user_data: UserCreate) -> int:
        # Check if user exists
        if await self.user_repo.get_by_username(user_data.username):
            raise HTTPException(status_code=400, detail="Username already registered")
        if await self.user_repo.get_by_email(user_data.email):
            raise HTTPException(status_code=400, detail="Email already registered")
        
        hashed_password = get_password_hash(user_data.password)
        user_id = await self.user_repo.create_user(user_data.username, user_data.email, hashed_password)
        return user_id

    async def authenticate_user(self, login_data: UserLogin) -> Token:
        user = await self.user_repo.get_by_username(login_data.username)
        if not user or not verify_password(login_data.password, user['hashed_password']):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Incorrect username or password",
                headers={"WWW-Authenticate": "Bearer"},
            )
        
        access_token_expires = timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        access_token = create_access_token(
            data={"sub": user['username']}, expires_delta=access_token_expires
        )
        return Token(access_token=access_token, token_type="bearer")
