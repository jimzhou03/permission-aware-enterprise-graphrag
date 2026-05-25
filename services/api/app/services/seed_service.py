from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import get_password_hash
from app.models import (
    Department,
    KnowledgeBase,
    KnowledgeBaseACL,
    Permission,
    Role,
    RolePermission,
    User,
)


DEFAULT_PASSWORD = "Passw0rd!123"


def _get_or_create_role(db: Session, name: str, description: str) -> Role:
    role = db.scalar(select(Role).where(Role.name == name))
    if role:
        return role
    role = Role(name=name, description=description)
    db.add(role)
    db.flush()
    return role


def _get_or_create_department(db: Session, code: str, name: str) -> Department:
    department = db.scalar(select(Department).where(Department.code == code))
    if department:
        return department
    department = Department(code=code, name=name)
    db.add(department)
    db.flush()
    return department


def _get_or_create_permission(db: Session, code: str, description: str) -> Permission:
    permission = db.scalar(select(Permission).where(Permission.code == code))
    if permission:
        return permission
    permission = Permission(code=code, description=description)
    db.add(permission)
    db.flush()
    return permission


def _bind_role_permissions(db: Session, role: Role, permission_codes: list[str], perm_map: dict[str, Permission]) -> None:
    existing_codes = set(
        db.scalars(
            select(Permission.code)
            .join(RolePermission, RolePermission.permission_id == Permission.id)
            .where(RolePermission.role_id == role.id)
        ).all()
    )
    for code in permission_codes:
        if code in existing_codes:
            continue
        db.add(RolePermission(role_id=role.id, permission_id=perm_map[code].id))


def _get_or_create_user(
    db: Session,
    email: str,
    full_name: str,
    role: Role,
    department: Department | None,
) -> User:
    user = db.scalar(select(User).where(User.email == email))
    if user:
        user.role_id = role.id
        user.department_id = department.id if department else None
        user.is_active = True
        return user

    user = User(
        email=email,
        full_name=full_name,
        password_hash=get_password_hash(DEFAULT_PASSWORD),
        role_id=role.id,
        department_id=department.id if department else None,
        is_active=True,
    )
    db.add(user)
    db.flush()
    return user


def _get_or_create_knowledge_base(
    db: Session,
    code: str,
    name: str,
    description: str,
    visibility: str,
    department: Department | None,
) -> KnowledgeBase:
    kb = db.scalar(select(KnowledgeBase).where(KnowledgeBase.code == code))
    if kb:
        kb.name = name
        kb.description = description
        kb.visibility = visibility
        kb.department_id = department.id if department else None
        kb.is_active = True
        return kb

    kb = KnowledgeBase(
        code=code,
        name=name,
        description=description,
        visibility=visibility,
        department_id=department.id if department else None,
        version=1,
        is_active=True,
    )
    db.add(kb)
    db.flush()
    return kb


def _ensure_acl(db: Session, kb: KnowledgeBase, role: Role | None = None, department: Department | None = None) -> None:
    acl = db.scalar(
        select(KnowledgeBaseACL).where(
            KnowledgeBaseACL.knowledge_base_id == kb.id,
            KnowledgeBaseACL.role_id == (role.id if role else None),
            KnowledgeBaseACL.department_id == (department.id if department else None),
        )
    )
    if acl is None:
        db.add(
            KnowledgeBaseACL(
                knowledge_base_id=kb.id,
                role_id=role.id if role else None,
                department_id=department.id if department else None,
                access_level="read",
            )
        )


def _deactivate_unmanaged_users(db: Session, managed_emails: set[str]) -> None:
    users = list(db.scalars(select(User)).all())
    for user in users:
        if user.email not in managed_emails:
            user.is_active = False


def _deactivate_unmanaged_knowledge_bases(db: Session, managed_codes: set[str]) -> None:
    kbs = list(db.scalars(select(KnowledgeBase)).all())
    for kb in kbs:
        if kb.code not in managed_codes:
            kb.is_active = False


def seed_demo_data(db: Session) -> None:
    role_map = {
        "bilingual_admin": _get_or_create_role(db, "bilingual_admin", "Bilingual demo administrator"),
        "cn_staff": _get_or_create_role(db, "cn_staff", "Chinese department demo staff"),
        "en_staff": _get_or_create_role(db, "en_staff", "English department demo staff"),
        "visitor": _get_or_create_role(db, "visitor", "Public visitor"),
    }
    dept_map = {
        "public": _get_or_create_department(db, "public", "Public"),
        "cn": _get_or_create_department(db, "cn", "Chinese Department"),
        "en": _get_or_create_department(db, "en", "English Department"),
    }

    perm_map = {
        "qa:ask": _get_or_create_permission(db, "qa:ask", "Ask questions"),
        "admin:users:read": _get_or_create_permission(db, "admin:users:read", "Read users"),
        "admin:kb:write": _get_or_create_permission(db, "admin:kb:write", "Manage knowledge bases"),
        "audit:read": _get_or_create_permission(db, "audit:read", "Read audit logs"),
    }

    _bind_role_permissions(db, role_map["bilingual_admin"], list(perm_map.keys()), perm_map)
    _bind_role_permissions(db, role_map["cn_staff"], ["qa:ask"], perm_map)
    _bind_role_permissions(db, role_map["en_staff"], ["qa:ask"], perm_map)
    _bind_role_permissions(db, role_map["visitor"], ["qa:ask"], perm_map)

    managed_users = {
        "cn_staff@example.local",
        "en_staff@example.local",
        "bilingual_admin@example.local",
        "visitor@example.local",
    }
    _deactivate_unmanaged_users(db, managed_users)

    _get_or_create_user(
        db,
        "cn_staff@example.local",
        "CN Staff User",
        role_map["cn_staff"],
        dept_map["cn"],
    )
    _get_or_create_user(
        db,
        "en_staff@example.local",
        "EN Staff User",
        role_map["en_staff"],
        dept_map["en"],
    )
    _get_or_create_user(
        db,
        "bilingual_admin@example.local",
        "Bilingual Admin User",
        role_map["bilingual_admin"],
        dept_map["public"],
    )
    _get_or_create_user(
        db,
        "visitor@example.local",
        "Visitor User",
        role_map["visitor"],
        dept_map["public"],
    )

    kb_cn_public = _get_or_create_knowledge_base(
        db,
        "cn-public",
        "CN Public Policy",
        "Fictional Chinese public policy handbook for internal demo.",
        "private",
        dept_map["cn"],
    )
    kb_cn_internal = _get_or_create_knowledge_base(
        db,
        "cn-internal",
        "CN Internal Handbook",
        "Fictional Chinese internal department handbook for demo.",
        "private",
        dept_map["cn"],
    )
    kb_en_public = _get_or_create_knowledge_base(
        db,
        "en-public",
        "EN Public Policy",
        "Fictional English public policy handbook for internal demo.",
        "private",
        dept_map["en"],
    )
    kb_en_internal = _get_or_create_knowledge_base(
        db,
        "en-internal",
        "EN Internal Handbook",
        "Fictional English internal department handbook for demo.",
        "private",
        dept_map["en"],
    )
    kb_public_policy = _get_or_create_knowledge_base(
        db,
        "public-policy",
        "Public Policy Handbook",
        "Fictional visitor-safe public handbook for demo.",
        "private",
        dept_map["public"],
    )

    managed_kb_codes = {"cn-public", "cn-internal", "en-public", "en-internal", "public-policy"}
    _deactivate_unmanaged_knowledge_bases(db, managed_kb_codes)

    # Explicit ACL entries keep policy deterministic and reviewable.
    _ensure_acl(db, kb_cn_public, role=role_map["cn_staff"])
    _ensure_acl(db, kb_cn_internal, role=role_map["cn_staff"])
    _ensure_acl(db, kb_en_public, role=role_map["en_staff"])
    _ensure_acl(db, kb_en_internal, role=role_map["en_staff"])
    _ensure_acl(db, kb_public_policy, role=role_map["visitor"])

    _ensure_acl(db, kb_cn_public, role=role_map["bilingual_admin"])
    _ensure_acl(db, kb_cn_internal, role=role_map["bilingual_admin"])
    _ensure_acl(db, kb_en_public, role=role_map["bilingual_admin"])
    _ensure_acl(db, kb_en_internal, role=role_map["bilingual_admin"])
    _ensure_acl(db, kb_public_policy, role=role_map["bilingual_admin"])

    db.commit()
