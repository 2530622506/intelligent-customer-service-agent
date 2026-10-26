"""创建合成演示账号和角色，不写入真实客户数据。"""

import asyncio

from sqlalchemy import select

from app.auth.passwords import hash_password
from app.auth.types import RoleCode
from app.db.base import session_factory
from app.models import Role, User, UserRole

DEMO_PASSWORD = "demo123456"
DEMO_USERS = (
    ("demo-customer", "演示客户", RoleCode.CUSTOMER),
    ("demo-agent", "演示客服", RoleCode.AGENT),
    ("demo-supervisor", "演示主管", RoleCode.SUPERVISOR),
    ("demo-admin", "演示管理员", RoleCode.ADMIN),
    ("demo-auditor", "演示审计员", RoleCode.AUDITOR),
)


async def seed() -> None:
    async with session_factory() as session:
        roles: dict[RoleCode, Role] = {}
        for role_code in RoleCode:
            role = await session.scalar(select(Role).where(Role.code == role_code.value))
            if role is None:
                role = Role(code=role_code.value, name=role_code.value)
                session.add(role)
                await session.flush()
            roles[role_code] = role

        for username, display_name, role_code in DEMO_USERS:
            user = await session.scalar(select(User).where(User.username == username))
            if user is None:
                user = User(
                    username=username,
                    display_name=display_name,
                    password_hash=hash_password(DEMO_PASSWORD),
                    status="active",
                )
                session.add(user)
                await session.flush()
            relation = await session.scalar(
                select(UserRole).where(UserRole.user_id == user.id, UserRole.role_id == roles[role_code].id)
            )
            if relation is None:
                session.add(UserRole(user_id=user.id, role_id=roles[role_code].id))
        await session.commit()


if __name__ == "__main__":
    asyncio.run(seed())
