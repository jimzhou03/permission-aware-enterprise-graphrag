from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User
from app.schemas.auth import AuthAllowedKnowledgeBase, AuthMeResponse, AuthPermissionScope, LoginRequest, TokenResponse
from app.services.auth_service import authenticate_user, issue_access_token, to_user_public
from app.services.permission_service import list_allowed_knowledge_bases


router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> TokenResponse:
    user = authenticate_user(db, payload.email, payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
        )
    access_token = issue_access_token(user)
    return TokenResponse(access_token=access_token, user=to_user_public(db, user))


@router.get("/me", response_model=AuthMeResponse)
def me(current_user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> AuthMeResponse:
    user_public = to_user_public(db, current_user)
    allowed_kbs = list_allowed_knowledge_bases(db, current_user)
    return AuthMeResponse(
        user=user_public,
        permission_scope=AuthPermissionScope(
            role=user_public.role,
            department=user_public.department,
            allowed_kb_codes=[item.code for item in allowed_kbs],
            allowed_knowledge_bases=[
                AuthAllowedKnowledgeBase(code=item.code, name=item.name)
                for item in allowed_kbs
            ],
        ),
    )
