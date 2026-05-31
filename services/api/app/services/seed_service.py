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
        "bilingual_admin": _get_or_create_role(db, "bilingual_admin", "Cross-department demo administrator"),
        "tech_staff": _get_or_create_role(db, "tech_staff", "Technology department demo staff"),
        "sales_staff": _get_or_create_role(db, "sales_staff", "Sales department demo staff"),
        "marketing_staff": _get_or_create_role(db, "marketing_staff", "Marketing department demo staff"),
        "support_staff": _get_or_create_role(db, "support_staff", "Support department demo staff"),
        "hr_staff": _get_or_create_role(db, "hr_staff", "HR department demo staff"),
        "admin_staff": _get_or_create_role(db, "admin_staff", "Administration department demo staff"),
        "product_staff": _get_or_create_role(db, "product_staff", "Product department demo staff"),
        "visitor": _get_or_create_role(db, "visitor", "Public visitor"),
    }
    dept_map = {
        "public": _get_or_create_department(db, "public", "Public"),
        "company": _get_or_create_department(db, "company", "Company Internal"),
        "tech": _get_or_create_department(db, "tech", "Technology Department"),
        "sales": _get_or_create_department(db, "sales", "Sales Department"),
        "marketing": _get_or_create_department(db, "marketing", "Marketing Department"),
        "support": _get_or_create_department(db, "support", "Support Department"),
        "hr": _get_or_create_department(db, "hr", "Human Resources Department"),
        "admin": _get_or_create_department(db, "admin", "Administration Department"),
        "product": _get_or_create_department(db, "product", "Product Department"),
    }

    perm_map = {
        "qa:ask": _get_or_create_permission(db, "qa:ask", "Ask questions"),
        "admin:users:read": _get_or_create_permission(db, "admin:users:read", "Read users"),
        "admin:kb:write": _get_or_create_permission(db, "admin:kb:write", "Manage knowledge bases"),
        "audit:read": _get_or_create_permission(db, "audit:read", "Read audit logs"),
    }

    _bind_role_permissions(db, role_map["bilingual_admin"], list(perm_map.keys()), perm_map)
    _bind_role_permissions(db, role_map["tech_staff"], ["qa:ask"], perm_map)
    _bind_role_permissions(db, role_map["sales_staff"], ["qa:ask"], perm_map)
    _bind_role_permissions(db, role_map["marketing_staff"], ["qa:ask"], perm_map)
    _bind_role_permissions(db, role_map["support_staff"], ["qa:ask"], perm_map)
    _bind_role_permissions(db, role_map["hr_staff"], ["qa:ask"], perm_map)
    _bind_role_permissions(db, role_map["admin_staff"], ["qa:ask"], perm_map)
    _bind_role_permissions(db, role_map["product_staff"], ["qa:ask"], perm_map)
    _bind_role_permissions(db, role_map["visitor"], ["qa:ask"], perm_map)

    managed_users = {
        "tech_staff@example.local",
        "sales_staff@example.local",
        "marketing_staff@example.local",
        "support_staff@example.local",
        "hr_staff@example.local",
        "admin_staff@example.local",
        "product_staff@example.local",
        "bilingual_admin@example.local",
        "visitor@example.local",
    }
    _deactivate_unmanaged_users(db, managed_users)

    _get_or_create_user(
        db,
        "tech_staff@example.local",
        "Tech Staff User",
        role_map["tech_staff"],
        dept_map["tech"],
    )
    _get_or_create_user(
        db,
        "sales_staff@example.local",
        "Sales Staff User",
        role_map["sales_staff"],
        dept_map["sales"],
    )
    _get_or_create_user(
        db,
        "marketing_staff@example.local",
        "Marketing Staff User",
        role_map["marketing_staff"],
        dept_map["marketing"],
    )
    _get_or_create_user(
        db,
        "support_staff@example.local",
        "Support Staff User",
        role_map["support_staff"],
        dept_map["support"],
    )
    _get_or_create_user(
        db,
        "hr_staff@example.local",
        "HR Staff User",
        role_map["hr_staff"],
        dept_map["hr"],
    )
    _get_or_create_user(
        db,
        "admin_staff@example.local",
        "Administration Staff User",
        role_map["admin_staff"],
        dept_map["admin"],
    )
    _get_or_create_user(
        db,
        "product_staff@example.local",
        "Product Staff User",
        role_map["product_staff"],
        dept_map["product"],
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

    kb_public_policy = _get_or_create_knowledge_base(
        db,
        "public-policy",
        "公开资料中心",
        "星海智造机器人有限公司公开介绍、访客须知与公开产品简介。",
        "private",
        dept_map["public"],
    )
    kb_company_internal = _get_or_create_knowledge_base(
        db,
        "company-internal",
        "全员内部通用知识库",
        "Demo v0.9.4 fictional company-internal docs: 权限申请、跨部门协作、内部知识库使用规范。",
        "private",
        dept_map["company"],
    )
    kb_tech_internal = _get_or_create_knowledge_base(
        db,
        "tech-internal",
        "技术部内部知识库",
        "Demo v0.9.4 fictional tech docs: 机器人故障诊断、SDK 集成、部署排障。",
        "private",
        dept_map["tech"],
    )
    kb_sales_internal = _get_or_create_knowledge_base(
        db,
        "sales-internal",
        "销售部内部知识库",
        "Demo v0.9.4 fictional sales docs: 报价策略、客户分级、本季度客户策略。",
        "private",
        dept_map["sales"],
    )
    kb_marketing_internal = _get_or_create_knowledge_base(
        db,
        "marketing-internal",
        "市场部内部知识库",
        "Demo v0.9.4 fictional marketing docs: 品牌定位、展会宣传、内容发布审核。",
        "private",
        dept_map["marketing"],
    )
    kb_support_internal = _get_or_create_knowledge_base(
        db,
        "support-internal",
        "客服部内部知识库",
        "Demo v0.9.4 fictional support docs: 售后工单、保修标准、投诉升级。",
        "private",
        dept_map["support"],
    )
    kb_hr_internal = _get_or_create_knowledge_base(
        db,
        "hr-internal",
        "人事部内部知识库",
        "Demo v0.9.4 fictional HR docs: 招聘、入职、试用期目标、绩效评估。",
        "private",
        dept_map["hr"],
    )
    kb_admin_internal = _get_or_create_knowledge_base(
        db,
        "admin-internal",
        "行政部内部知识库",
        "Demo v0.9.4 fictional admin docs: 采购申请、会议室预约、办公资产管理。",
        "private",
        dept_map["admin"],
    )
    kb_product_internal = _get_or_create_knowledge_base(
        db,
        "product-internal",
        "产品部内部知识库",
        "Demo v0.9.4 fictional product docs: 产品生产流程、需求评审、版本发布、竞品分析。",
        "private",
        dept_map["product"],
    )

    managed_kb_codes = {
        "public-policy",
        "company-internal",
        "tech-internal",
        "sales-internal",
        "marketing-internal",
        "support-internal",
        "hr-internal",
        "admin-internal",
        "product-internal",
    }
    _deactivate_unmanaged_knowledge_bases(db, managed_kb_codes)

    # Explicit ACL entries keep policy deterministic and reviewable.
    _ensure_acl(db, kb_public_policy, role=role_map["tech_staff"])
    _ensure_acl(db, kb_company_internal, role=role_map["tech_staff"])
    _ensure_acl(db, kb_tech_internal, role=role_map["tech_staff"])

    _ensure_acl(db, kb_public_policy, role=role_map["sales_staff"])
    _ensure_acl(db, kb_company_internal, role=role_map["sales_staff"])
    _ensure_acl(db, kb_sales_internal, role=role_map["sales_staff"])

    _ensure_acl(db, kb_public_policy, role=role_map["marketing_staff"])
    _ensure_acl(db, kb_company_internal, role=role_map["marketing_staff"])
    _ensure_acl(db, kb_marketing_internal, role=role_map["marketing_staff"])

    _ensure_acl(db, kb_public_policy, role=role_map["support_staff"])
    _ensure_acl(db, kb_company_internal, role=role_map["support_staff"])
    _ensure_acl(db, kb_support_internal, role=role_map["support_staff"])

    _ensure_acl(db, kb_public_policy, role=role_map["hr_staff"])
    _ensure_acl(db, kb_company_internal, role=role_map["hr_staff"])
    _ensure_acl(db, kb_hr_internal, role=role_map["hr_staff"])

    _ensure_acl(db, kb_public_policy, role=role_map["admin_staff"])
    _ensure_acl(db, kb_company_internal, role=role_map["admin_staff"])
    _ensure_acl(db, kb_admin_internal, role=role_map["admin_staff"])

    _ensure_acl(db, kb_public_policy, role=role_map["product_staff"])
    _ensure_acl(db, kb_company_internal, role=role_map["product_staff"])
    _ensure_acl(db, kb_product_internal, role=role_map["product_staff"])

    _ensure_acl(db, kb_public_policy, role=role_map["visitor"])

    _ensure_acl(db, kb_company_internal, role=role_map["bilingual_admin"])
    _ensure_acl(db, kb_tech_internal, role=role_map["bilingual_admin"])
    _ensure_acl(db, kb_sales_internal, role=role_map["bilingual_admin"])
    _ensure_acl(db, kb_marketing_internal, role=role_map["bilingual_admin"])
    _ensure_acl(db, kb_support_internal, role=role_map["bilingual_admin"])
    _ensure_acl(db, kb_hr_internal, role=role_map["bilingual_admin"])
    _ensure_acl(db, kb_admin_internal, role=role_map["bilingual_admin"])
    _ensure_acl(db, kb_product_internal, role=role_map["bilingual_admin"])
    _ensure_acl(db, kb_public_policy, role=role_map["bilingual_admin"])

    db.commit()
