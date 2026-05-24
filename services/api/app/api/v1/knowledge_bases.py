from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.deps import get_current_user
from app.models import User
from app.schemas.common import KnowledgeBasePublic
from app.services.permission_service import list_allowed_knowledge_bases


router = APIRouter(prefix="/knowledge-bases", tags=["knowledge-bases"])


@router.get("", response_model=list[KnowledgeBasePublic])
def list_knowledge_bases(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[KnowledgeBasePublic]:
    knowledge_bases = list_allowed_knowledge_bases(db, current_user)
    return [
        KnowledgeBasePublic(
            id=kb.id,
            code=kb.code,
            name=kb.name,
            description=kb.description,
            department=kb.department.code if kb.department else None,
            visibility=kb.visibility,
            version=kb.version,
        )
        for kb in knowledge_bases
    ]

