from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import create_access_token, verify_password
from app.models import Permission, RolePermission, User
from app.schemas.common import UserPublic


def authenticate_user(db: Session, email: str, password: str) -> User | None:
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


def get_user_permission_codes(db: Session, user: User) -> list[str]:
    statement = (
        select(Permission.code)
        .join(RolePermission, RolePermission.permission_id == Permission.id)
        .where(RolePermission.role_id == user.role_id)
    )
    return sorted(set(db.scalars(statement).all()))


def issue_access_token(user: User) -> str:
    role_name = user.role.name if user.role else ""
    department_code = user.department.code if user.department else ""
    return create_access_token(
        str(user.id),
        extra_claims={"role": role_name, "department": department_code},
    )


def to_user_public(db: Session, user: User) -> UserPublic:
    return UserPublic(
        id=user.id,
        email=user.email,
        full_name=user.full_name,
        role=user.role.name if user.role else "",
        department=user.department.code if user.department else None,
        permissions=get_user_permission_codes(db, user),
    )


def user_has_permission(db: Session, user: User, permission_code: str) -> bool:
    if user.role and user.role.name == "admin":
        return True
    return permission_code in get_user_permission_codes(db, user)

