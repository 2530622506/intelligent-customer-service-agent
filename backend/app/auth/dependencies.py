import secrets
from typing import Annotated
from uuid import UUID

import jwt
from fastapi import Cookie, Depends, Header, HTTPException, Request, status

from app.auth.tokens import TokenError, decode_token
from app.auth.types import AuthPrincipal, RoleCode
from app.core.config import Settings, get_settings

ACCESS_COOKIE = "csa_access_token"
REFRESH_COOKIE = "csa_refresh_token"
CSRF_COOKIE = "csa_csrf_token"


def csrf_token() -> str:
    return secrets.token_urlsafe(32)


def require_csrf(
    request: Request,
    csrf_cookie: Annotated[str | None, Cookie(alias=CSRF_COOKIE)] = None,
    csrf_header: Annotated[str | None, Header(alias="X-CSRF-Token")] = None,
) -> None:
    if request.method in {"GET", "HEAD", "OPTIONS"}:
        return
    if not csrf_cookie or not csrf_header or not secrets.compare_digest(csrf_cookie, csrf_header):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="CSRF 校验失败")


async def get_principal(
    access_cookie: Annotated[str | None, Cookie(alias=ACCESS_COOKIE)] = None,
    authorization: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> AuthPrincipal:
    token = access_cookie
    if not token and authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="需要登录")
    try:
        payload = decode_token(token, "access", settings)
        user_id = UUID(str(payload["sub"]))
        roles = frozenset(RoleCode(value) for value in payload.get("roles", []))
        from app.auth.policy import permissions_for_roles, scope_for_roles

        return AuthPrincipal(
            user_id=user_id,
            username=str(payload.get("username", "")),
            display_name=str(payload.get("display_name", "")),
            roles=roles,
            permissions=permissions_for_roles(roles),
            team_ids=tuple(UUID(value) for value in payload.get("team_ids", [])),
            data_scope=scope_for_roles(user_id, roles, tuple(UUID(value) for value in payload.get("team_ids", []))),
        )
    except (TokenError, ValueError, KeyError, jwt.PyJWTError) as error:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="登录状态无效") from error
