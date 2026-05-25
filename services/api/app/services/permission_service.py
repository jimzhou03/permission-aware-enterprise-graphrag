from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.models import KnowledgeBase, KnowledgeBaseACL, User
from app.services.auth_service import user_has_permission


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


def can_write_knowledge_base(db: Session, user: User, kb: KnowledgeBase) -> bool:
    allowed_kb_ids = {item.id for item in list_allowed_knowledge_bases(db, user)}
    if kb.id not in allowed_kb_ids:
        return False

    if user_has_permission(db, user, "admin:kb:write"):
        return True

    predicates = [KnowledgeBaseACL.role_id == user.role_id]
    if user.department_id is not None:
        predicates.append(KnowledgeBaseACL.department_id == user.department_id)
    statement = select(KnowledgeBaseACL).where(
        and_(
            KnowledgeBaseACL.knowledge_base_id == kb.id,
            KnowledgeBaseACL.access_level.in_(["write", "admin"]),
            or_(*predicates),
        )
    )
    return db.scalar(statement) is not None
