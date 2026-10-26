from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

import jwt

from app.core.config import Settings


class TokenError(ValueError):
    """Token 无效、过期或用途不匹配。"""


def create_token(
    subject: UUID,
    token_type: str,
    settings: Settings,
    expires_seconds: int,
    extra: dict[str, Any] | None = None,
) -> tuple[str, str, datetime]:
    now = datetime.now(UTC)
    expires_at = now + timedelta(seconds=expires_seconds)
    jti = str(uuid4())
    payload: dict[str, Any] = {
        "sub": str(subject),
        "jti": jti,
        "type": token_type,
        "iat": now,
        "exp": expires_at,
        **(extra or {}),
    }
    return jwt.encode(payload, settings.app_secret_key, algorithm="HS256"), jti, expires_at


def decode_token(token: str, expected_type: str, settings: Settings) -> dict[str, Any]:
    try:
        payload = jwt.decode(token, settings.app_secret_key, algorithms=["HS256"])
    except jwt.PyJWTError as error:
        raise TokenError("token 无效或已过期") from error
    if payload.get("type") != expected_type or not payload.get("sub"):
        raise TokenError("token 类型不匹配")
    return payload
