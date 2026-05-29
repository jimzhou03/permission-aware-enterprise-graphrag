from pydantic import BaseModel, Field

from app.schemas.common import UserPublic


class LoginRequest(BaseModel):
    email: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserPublic


class AuthAllowedKnowledgeBase(BaseModel):
    code: str
    name: str


class AuthPermissionScope(BaseModel):
    role: str
    department: str | None
    allowed_kb_codes: list[str] = Field(default_factory=list)
    allowed_knowledge_bases: list[AuthAllowedKnowledgeBase] = Field(default_factory=list)


class AuthMeResponse(BaseModel):
    user: UserPublic
    permission_scope: AuthPermissionScope
