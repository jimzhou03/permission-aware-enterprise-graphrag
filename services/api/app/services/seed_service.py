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


def seed_demo_data(db: Session) -> None:
    role_map = {
        "admin": _get_or_create_role(db, "admin", "System administrator"),
        "hr": _get_or_create_role(db, "hr", "Human resources"),
        "finance": _get_or_create_role(db, "finance", "Finance department"),
        "tech": _get_or_create_role(db, "tech", "Technology department"),
        "visitor": _get_or_create_role(db, "visitor", "Public visitor"),
    }
    dept_map = {
        "public": _get_or_create_department(db, "public", "Public"),
        "hr": _get_or_create_department(db, "hr", "Human Resources"),
        "finance": _get_or_create_department(db, "finance", "Finance"),
        "tech": _get_or_create_department(db, "tech", "Technology"),
    }

    perm_map = {
        "qa:ask": _get_or_create_permission(db, "qa:ask", "Ask questions"),
        "admin:users:read": _get_or_create_permission(db, "admin:users:read", "Read users"),
        "admin:kb:write": _get_or_create_permission(db, "admin:kb:write", "Manage knowledge bases"),
        "audit:read": _get_or_create_permission(db, "audit:read", "Read audit logs"),
    }

    _bind_role_permissions(db, role_map["admin"], list(perm_map.keys()), perm_map)
    _bind_role_permissions(db, role_map["hr"], ["qa:ask"], perm_map)
    _bind_role_permissions(db, role_map["finance"], ["qa:ask"], perm_map)
    _bind_role_permissions(db, role_map["tech"], ["qa:ask"], perm_map)
    _bind_role_permissions(db, role_map["visitor"], ["qa:ask"], perm_map)

    _get_or_create_user(db, "admin@example.local", "Admin User", role_map["admin"], dept_map["public"])
    _get_or_create_user(db, "hr@example.local", "HR User", role_map["hr"], dept_map["hr"])
    _get_or_create_user(db, "finance@example.local", "Finance User", role_map["finance"], dept_map["finance"])
    _get_or_create_user(db, "tech@example.local", "Tech User", role_map["tech"], dept_map["tech"])
    _get_or_create_user(db, "visitor@example.local", "Visitor User", role_map["visitor"], dept_map["public"])

    kb_public = _get_or_create_knowledge_base(
        db,
        "public-general",
        "Public General Policy",
        "Fictional company public handbook and workplace basics.",
        "public",
        dept_map["public"],
    )
    kb_hr = _get_or_create_knowledge_base(
        db,
        "hr-policy",
        "HR Policy",
        "Fictional HR policy base.",
        "private",
        dept_map["hr"],
    )
    kb_finance = _get_or_create_knowledge_base(
        db,
        "finance-policy",
        "Finance Policy",
        "Fictional finance policy base.",
        "private",
        dept_map["finance"],
    )
    kb_tech = _get_or_create_knowledge_base(
        db,
        "tech-policy",
        "Tech Policy",
        "Fictional technology operations policy base.",
        "private",
        dept_map["tech"],
    )

    # Explicit ACL entries keep policy deterministic and reviewable.
    _ensure_acl(db, kb_public, role=role_map["admin"])
    _ensure_acl(db, kb_public, role=role_map["hr"])
    _ensure_acl(db, kb_public, role=role_map["finance"])
    _ensure_acl(db, kb_public, role=role_map["tech"])
    _ensure_acl(db, kb_public, role=role_map["visitor"])

    _ensure_acl(db, kb_hr, role=role_map["admin"])
    _ensure_acl(db, kb_hr, role=role_map["hr"])
    _ensure_acl(db, kb_finance, role=role_map["admin"])
    _ensure_acl(db, kb_finance, role=role_map["finance"])
    _ensure_acl(db, kb_tech, role=role_map["admin"])
    _ensure_acl(db, kb_tech, role=role_map["tech"])

    db.commit()

