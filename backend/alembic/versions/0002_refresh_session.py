"""增加 refresh token 轮换会话表。

Revision ID: 0002_refresh_session
Revises: 0001_initial_schema
"""
from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy import inspect

from alembic import op

revision = "0002_refresh_session"
down_revision = "0001_initial_schema"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 0001 使用 metadata.create_all；新库可能已经拥有该表，所以迁移必须幂等。
    if inspect(op.get_bind()).has_table("refresh_session"):
        return
    op.create_table(
        "refresh_session",
        sa.Column("user_id", sa.UUID(), nullable=False),
        sa.Column("token_jti", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rotated_to_jti", sa.String(length=128), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["app_user.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_refresh_session"),
        sa.UniqueConstraint("token_jti", name="uq_refresh_session_token_jti"),
    )


def downgrade() -> None:
    if inspect(op.get_bind()).has_table("refresh_session"):
        op.drop_table("refresh_session")
