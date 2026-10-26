from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Cookie, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import (
    ACCESS_COOKIE,
    CSRF_COOKIE,
    REFRESH_COOKIE,
    csrf_token,
    get_principal,
    require_csrf,
)
from app.auth.passwords import verify_password
from app.auth.policy import permissions_for_roles, scope_for_roles
from app.auth.schemas import LoginRequest, LoginResponse, UserView
from app.auth.tokens import TokenError, create_token, decode_token
from app.auth.types import AuthPrincipal, RoleCode
from app.core.config import Settings, get_settings
from app.db.base import get_db
from app.models import RefreshSession, Role, TeamMember, User, UserRole

router = APIRouter(prefix="/auth", tags=["auth"])


async def _roles_and_teams(session: AsyncSession, user_id: UUID) -> tuple[frozenset[RoleCode], tuple[UUID, ...]]:
    role_rows = await session.execute(
        select(Role.code).join(UserRole, UserRole.role_id == Role.id).where(UserRole.user_id == user_id)
    )
    team_rows = await session.execute(select(TeamMember.team_id).where(TeamMember.user_id == user_id))
    return (
        frozenset(RoleCode(row) for row in role_rows.scalars()),
        tuple(team_rows.scalars()),
    )


def _user_view(user: User, roles: frozenset[RoleCode], team_ids: tuple[UUID, ...]) -> UserView:
    return UserView(
        id=str(user.id),
        username=user.username,
        display_name=user.display_name,
        roles=sorted(role.value for role in roles),
        permissions=sorted(permissions_for_roles(roles)),
        data_scope=scope_for_roles(user.id, roles, team_ids).as_dict(),
    )


def _set_auth_cookies(response: Response, access: str, refresh: str, csrf: str, settings: Settings) -> None:
    response.set_cookie(
        ACCESS_COOKIE,
        access,
        max_age=settings.jwt_access_expires_seconds,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        domain=settings.auth_cookie_domain,
        path="/",
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh,
        max_age=settings.jwt_refresh_expires_seconds,
        httponly=True,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        domain=settings.auth_cookie_domain,
        path="/",
    )
    response.set_cookie(
        CSRF_COOKIE,
        csrf,
        max_age=settings.jwt_refresh_expires_seconds,
        httponly=False,
        secure=settings.auth_cookie_secure,
        samesite=settings.auth_cookie_samesite,
        domain=settings.auth_cookie_domain,
        path="/",
    )


@router.post("/login", response_model=LoginResponse)
async def login(
    payload: LoginRequest,
    response: Response,
    session: Annotated[AsyncSession, Depends(get_db)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> LoginResponse:
    result = await session.execute(select(User).where(User.username == payload.username))
    user = result.scalar_one_or_none()
    if not user or user.status != "active" or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户名或密码错误")
    roles, team_ids = await _roles_and_teams(session, user.id)
    access, _, _ = create_token(
        user.id, "access", settings, settings.jwt_access_expires_seconds,
        {"username": user.username, "display_name": user.display_name, "roles": [r.value for r in roles], "team_ids": [str(t) for t in team_ids]},
    )
    refresh, refresh_jti, refresh_exp = create_token(
        user.id, "refresh", settings, settings.jwt_refresh_expires_seconds
    )
    session.add(RefreshSession(user_id=user.id, token_jti=refresh_jti, expires_at=refresh_exp))
    await session.commit()
    csrf = csrf_token()
    _set_auth_cookies(response, access, refresh, csrf, settings)
    return LoginResponse(user=_user_view(user, roles, team_ids), csrf_token=csrf)


@router.get("/me", response_model=UserView)
async def me(
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> UserView:
    user = await session.get(User, principal.user_id)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="用户不存在")
    return _user_view(user, principal.roles, principal.team_ids)


@router.post("/logout", dependencies=[Depends(require_csrf)])
async def logout(
    response: Response,
    refresh_cookie: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
    session: AsyncSession = Depends(get_db),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> dict[str, str]:
    if refresh_cookie:
        try:
            payload = decode_token(refresh_cookie, "refresh", settings)
            refresh = await session.scalar(
                select(RefreshSession).where(RefreshSession.token_jti == str(payload["jti"]))
            )
            if refresh and refresh.revoked_at is None:
                refresh.revoked_at = datetime.now(UTC)
                await session.commit()
        except (TokenError, KeyError, ValueError):
            pass
    for cookie in (ACCESS_COOKIE, REFRESH_COOKIE, CSRF_COOKIE):
        response.delete_cookie(cookie, domain=settings.auth_cookie_domain, path="/")
    return {"message": "已退出登录"}


@router.post("/refresh", response_model=LoginResponse, dependencies=[Depends(require_csrf)])
async def refresh(
    response: Response,
    refresh_cookie: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
    session: AsyncSession = Depends(get_db),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> LoginResponse:
    """轮换 refresh token；旧 token 一旦使用即撤销，避免重放。"""
    if not refresh_cookie:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="需要刷新令牌")
    try:
        payload = decode_token(refresh_cookie, "refresh", settings)
        refresh_row = await session.scalar(
            select(RefreshSession).where(RefreshSession.token_jti == str(payload["jti"]))
        )
        if not refresh_row or refresh_row.revoked_at is not None:
            raise TokenError("刷新令牌已撤销")
        user = await session.get(User, UUID(str(payload["sub"])))
        if not user or user.status != "active":
            raise TokenError("用户不可用")

        roles, team_ids = await _roles_and_teams(session, user.id)
        access, _, _ = create_token(
            user.id,
            "access",
            settings,
            settings.jwt_access_expires_seconds,
            {
                "username": user.username,
                "display_name": user.display_name,
                "roles": [role.value for role in roles],
                "team_ids": [str(team_id) for team_id in team_ids],
            },
        )
        new_refresh, new_jti, new_exp = create_token(
            user.id, "refresh", settings, settings.jwt_refresh_expires_seconds
        )
        refresh_row.revoked_at = datetime.now(UTC)
        refresh_row.rotated_to_jti = new_jti
        session.add(RefreshSession(user_id=user.id, token_jti=new_jti, expires_at=new_exp))
        await session.commit()
        csrf = csrf_token()
        _set_auth_cookies(response, access, new_refresh, csrf, settings)
        return LoginResponse(user=_user_view(user, roles, team_ids), csrf_token=csrf)
    except (TokenError, KeyError, ValueError) as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="刷新令牌无效") from error
