"""
Authentication routes.
POST /auth/register
POST /auth/login
GET  /auth/me
"""
from uuid import UUID
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, ConfigDict, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import get_current_user
from app.core.exceptions import AuthenticationError
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models.user import User
from app.db.session import get_async_db
from app.repositories.user_repo import UserRepository

router = APIRouter(prefix="/auth", tags=["Authentication"])


class RegisterRequest(BaseModel):
    email: EmailStr
    full_name: str
    password: str


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    is_active: bool

    model_config = ConfigDict(from_attributes=True)


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterRequest, db: AsyncSession = Depends(get_async_db)):
    repo = UserRepository(db)
    if await repo.email_exists(body.email):
        raise HTTPException(status_code=409, detail="Email already registered")

    user = User(
        email=body.email,
        full_name=body.full_name,
        hashed_password=hash_password(body.password),
    )
    user = await repo.create(user)
    return user


@router.post("/login", response_model=TokenResponse)
async def login(body: LoginRequest, db: AsyncSession = Depends(get_async_db)):
    repo = UserRepository(db)
    user = await repo.get_by_email(body.email)

    if not user or not verify_password(body.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    if not user.is_active:
        raise HTTPException(status_code=403, detail="Account is deactivated")

    token = create_access_token(subject=str(user.id))
    return {"access_token": token, "token_type": "bearer"}


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return current_user
