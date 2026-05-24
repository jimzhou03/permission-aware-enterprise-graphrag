from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.models import KnowledgeBase, KnowledgeBaseACL, User


def list_allowed_knowledge_bases(db: Session, user: User) -> list[KnowledgeBase]:
    statement = select(KnowledgeBase).where(KnowledgeBase.is_active.is_(True))

    # Admin can view all active knowledge bases by default in Phase 1.
    if user.role and user.role.name == "admin":
        return list(db.scalars(statement.order_by(KnowledgeBase.code)).all())

    predicates = [
        KnowledgeBase.visibility == "public",
        KnowledgeBase.acl_entries.any(KnowledgeBaseACL.role_id == user.role_id),
    ]
    if user.department_id is not None:
        predicates.append(
            KnowledgeBase.acl_entries.any(KnowledgeBaseACL.department_id == user.department_id)
        )

    scoped_statement = statement.where(or_(*predicates)).order_by(KnowledgeBase.code)
    return list(db.scalars(scoped_statement).unique().all())


def list_allowed_kb_codes(db: Session, user: User) -> list[str]:
    return [kb.code for kb in list_allowed_knowledge_bases(db, user)]

