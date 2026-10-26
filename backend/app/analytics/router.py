from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.dependencies import get_principal, require_csrf
from app.auth.types import AuthPrincipal, RoleCode
from app.business.schemas import AnalyticsQuery
from app.business.sql_gateway import ReadOnlySQLGateway, SQLPolicyError
from app.db.base import get_db

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.post("/query", dependencies=[Depends(require_csrf)])
async def query_analytics(
    payload: AnalyticsQuery,
    principal: Annotated[AuthPrincipal, Depends(get_principal)],
    session: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, object]:
    if not principal.can("analytics:read:team") and not principal.has_role(RoleCode.ADMIN):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="没有售后分析权限")
    try:
        parsed = ReadOnlySQLGateway().validate(payload.sql)
        # SQL 只能访问固定的合成指标表；DataScope 由权限门禁先决定可否查询。
        result = await session.execute(text(parsed.sql(dialect="postgres")))
        rows = [dict(row._mapping) for row in result]
        return {"accepted": True, "rows": rows, "question": payload.question}
    except SQLPolicyError as error:
        return {"accepted": False, "rows": [], "reason": str(error), "question": payload.question}
