"""创建首版业务事实源表结构。

Revision ID: 0001_initial_schema
Revises:
"""
from collections.abc import Sequence

from alembic import op
from app import models  # noqa: F401  # 确保全部模型已经注册到 metadata。
from app.db.base import Base

revision = "0001_initial_schema"
down_revision = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 初始迁移以完整 metadata 为单一来源；后续结构变化必须生成独立 Alembic revision。
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind)


def downgrade() -> None:
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind)
