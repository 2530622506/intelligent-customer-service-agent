"""增加评测数据集、运行和评分表。

Revision ID: 0003_evaluation_tables
Revises: 0002_refresh_session
"""
from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision = "0003_evaluation_tables"
down_revision = "0002_refresh_session"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "eval_dataset",
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_eval_dataset"),
        sa.UniqueConstraint("name", name="uq_eval_dataset_name"),
    )
    op.create_table(
        "eval_case",
        sa.Column("dataset_id", sa.UUID(), nullable=False),
        sa.Column("case_key", sa.String(120), nullable=False),
        sa.Column("question", sa.Text(), nullable=False),
        sa.Column("expected_output", sa.JSON(), nullable=False),
        sa.Column("enabled", sa.Boolean(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["eval_dataset.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_eval_case"),
        sa.UniqueConstraint("dataset_id", "case_key", name="uq_eval_case_key"),
    )
    op.create_table(
        "eval_run",
        sa.Column("dataset_id", sa.UUID(), nullable=False),
        sa.Column("model_name", sa.String(120), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("filter_value", sa.String(160), nullable=True),
        sa.Column("summary", sa.JSON(), nullable=False),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["dataset_id"], ["eval_dataset.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_eval_run"),
    )
    op.create_table(
        "eval_score",
        sa.Column("run_id", sa.UUID(), nullable=False),
        sa.Column("case_id", sa.UUID(), nullable=False),
        sa.Column("metric", sa.String(120), nullable=False),
        sa.Column("value", sa.Float(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("id", sa.UUID(), nullable=False),
        sa.ForeignKeyConstraint(["case_id"], ["eval_case.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["run_id"], ["eval_run.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_eval_score"),
        sa.UniqueConstraint("run_id", "case_id", "metric", name="uq_eval_score_metric"),
    )


def downgrade() -> None:
    op.drop_table("eval_score")
    op.drop_table("eval_run")
    op.drop_table("eval_case")
    op.drop_table("eval_dataset")
