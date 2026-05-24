from pydantic import BaseModel, EmailStr

from app.schemas.common import UserPublic


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic

