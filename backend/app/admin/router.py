from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_principal, require_csrf
from app.auth.types import AuthPrincipal, RoleCode
from app.db.base import get_db
from app.models import Permission, Role, User, UserRole

router = APIRouter(prefix="/admin", tags=["admin"])


class AssignRoleRequest(BaseModel):
    role_codes: list[str]


def require_admin(principal: AuthPrincipal) -> None:
    if not principal.has_role(RoleCode.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要管理员权限")


@router.get("/users")
async def list_users(
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, object]]:
    require_admin(principal)
    users = await session.scalars(select(User).order_by(User.created_at.desc()))
    return [{"id": str(user.id), "username": user.username, "displayName": user.display_name, "status": user.status} for user in users]


@router.get("/roles")
async def list_roles(
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, object]]:
    require_admin(principal)
    roles = await session.scalars(select(Role).order_by(Role.code.asc()))
    return [{"id": str(role.id), "code": role.code, "name": role.name, "description": role.description} for role in roles]


@router.get("/permissions")
async def list_permissions(
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> list[dict[str, object]]:
    require_admin(principal)
    permissions = await session.scalars(select(Permission).order_by(Permission.code.asc()))
    return [{"id": str(permission.id), "code": permission.code, "description": permission.description} for permission in permissions]


@router.put("/users/{user_id}/roles", dependencies=[Depends(require_csrf)])
async def assign_roles(
    user_id: UUID,
    payload: AssignRoleRequest,
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    require_admin(principal)
    if not await session.get(User, user_id):
        raise HTTPException(status_code=404, detail="用户不存在")
    roles = list(await session.scalars(select(Role).where(Role.code.in_(payload.role_codes))))
    if len(roles) != len(set(payload.role_codes)):
        raise HTTPException(status_code=400, detail="包含未注册角色")
    await session.execute(delete(UserRole).where(UserRole.user_id == user_id))
    session.add_all([UserRole(user_id=user_id, role_id=role.id) for role in roles])
    await session.commit()
    return {"userId": str(user_id), "roleCodes": [role.code for role in roles]}
