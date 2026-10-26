"""增加合成售后分析指标表。

Revision ID: 0004_after_sale_metrics
Revises: 0003_evaluation_tables
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision = "0004_after_sale_metrics"
down_revision = "0003_evaluation_tables"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "after_sale_metrics",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("month", sa.String(7), nullable=False),
        sa.Column("issue_type", sa.String(80), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("ticket_count", sa.Integer(), nullable=False),
        sa.Column("avg_handle_minutes", sa.Integer(), nullable=False),
    )
    op.bulk_insert(
        sa.table(
            "after_sale_metrics",
            sa.column("id", sa.Integer()),
            sa.column("month", sa.String()),
            sa.column("issue_type", sa.String()),
            sa.column("status", sa.String()),
            sa.column("ticket_count", sa.Integer()),
            sa.column("avg_handle_minutes", sa.Integer()),
        ),
        [
            {"id": 1, "month": "2026-10", "issue_type": "物流异常", "status": "open", "ticket_count": 12, "avg_handle_minutes": 45},
            {"id": 2, "month": "2026-10", "issue_type": "产品故障", "status": "resolved", "ticket_count": 8, "avg_handle_minutes": 120},
            {"id": 3, "month": "2026-10", "issue_type": "退货申请", "status": "pending", "ticket_count": 15, "avg_handle_minutes": 60},
        ],
    )


def downgrade() -> None:
    op.drop_table("after_sale_metrics")
