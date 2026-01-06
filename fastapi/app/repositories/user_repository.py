
from sqlalchemy.future import select
from asyncpg import Pool
from typing import Optional

from ..models.user import UserDB, AppClientDB
# Note: For asyncpg + sqlalchemy core we'd use raw SQL or SQLAlchemy async session.
# Since we used asyncpg directly in other repos, let's stick to raw SQL for consistency 
# OR switch to SQLAlchemy AsyncSession if we need the ORM features.
# The previous repos used `self.db.fetchrow(query)`.
# However, UserDB is an ORM class. Using raw SQL with asyncpg is slightly manual mapping.
# Let's use raw SQL to match the existing pattern in this codebase.

class UserRepository:
    def __init__(self, db: Pool):
        self.db = db

    async def get_by_username(self, username: str) -> Optional[dict]:
        query = "SELECT * FROM users WHERE username = $1"
        row = await self.db.fetchrow(query, username)
        return dict(row) if row else None
    
    async def get_by_email(self, email: str) -> Optional[dict]:
        query = "SELECT * FROM users WHERE email = $1"
        row = await self.db.fetchrow(query, email)
        return dict(row) if row else None

    async def create_user(self, username: str, email: str, hashed_password: str) -> int:
        query = """
            INSERT INTO users (username, email, hashed_password, is_active, created_at)
            VALUES ($1, $2, $3, TRUE, NOW())
            RETURNING id
        """
        user_id = await self.db.fetchval(query, username, email, hashed_password)
        return user_id

    async def get_app_client(self, api_key: str) -> Optional[dict]:
        # In real world, we might not query by raw API key if hashed. 
        # But for App Auth, often client_id + client_secret is used.
        # If using single API Key, we have to verify it.
        # If hashed, we can't query by it directly.
        # We need client_id to look it up, then verify secret.
        # Let's assume API Key is passed in header "X-API-Key" and contains "client_id:secret".
        pass 
    
    async def get_app_client_by_id(self, client_id: str) -> Optional[dict]:
        query = "SELECT * FROM app_clients WHERE client_id = $1"
        row = await self.db.fetchrow(query, client_id)
        return dict(row) if row else None
