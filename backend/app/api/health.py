import asyncio
from typing import Annotated, Any
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Response

from app.core.config import Settings, get_settings

router = APIRouter(prefix="/health", tags=["health"])


def _host_port(url: str, default_port: int) -> tuple[str, int]:
    parsed = urlsplit(url)
    host = parsed.hostname or "localhost"
    port = parsed.port or default_port
    return host, port


async def _tcp_check(url: str, default_port: int) -> bool:
    host, port = _host_port(url, default_port)
    try:
        reader, writer = await asyncio.wait_for(
            asyncio.open_connection(host, port), timeout=0.8
        )
        writer.close()
        await writer.wait_closed()
        del reader
        return True
    except (OSError, TimeoutError, ValueError):
        return False


async def _dependency_checks(settings: Settings) -> dict[str, bool]:
    checks = await asyncio.gather(
        _tcp_check(settings.database_url, 5432),
        _tcp_check(settings.redis_url, 6379),
        _tcp_check(settings.rabbitmq_url, 5672),
        _tcp_check(settings.milvus_uri, 19530),
        _tcp_check(settings.neo4j_uri, 7687),
        _tcp_check(settings.rustfs_endpoint, 9000),
    )
    return dict(
        zip(
            ("postgres", "redis", "rabbitmq", "milvus", "neo4j", "rustfs"),
            checks,
            strict=True,
        )
    )


@router.get("/live")
async def liveness(
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, str]:
    return {"status": "ok", "service": settings.app_name}


@router.get("/ready")
async def readiness(
    response: Response,
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict[str, Any]:
    checks = await _dependency_checks(settings) if settings.readiness_strict else {}
    ready = all(checks.values()) if checks else True
    if not ready:
        response.status_code = 503
    return {
        "status": "ready" if ready else "not_ready",
        "service": settings.app_name,
        "checks": checks,
    }
