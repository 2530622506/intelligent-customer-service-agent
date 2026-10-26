from __future__ import annotations

from dataclasses import dataclass

import sqlglot
from sqlglot import exp


class SQLPolicyError(ValueError):
    """SQL 违反只读、表 / 字段或结果规模策略。"""


@dataclass(frozen=True)
class SQLPolicy:
    allowed_tables: frozenset[str] = frozenset({"after_sale_metrics"})
    allowed_columns: frozenset[str] = frozenset(
        {"issue_type", "status", "ticket_count", "avg_handle_minutes", "month"}
    )
    max_limit: int = 100


class ReadOnlySQLGateway:
    def __init__(self, policy: SQLPolicy | None = None) -> None:
        self.policy = policy or SQLPolicy()

    def validate(self, sql: str) -> exp.Expression:
        if ";" in sql or "--" in sql or "/*" in sql:
            raise SQLPolicyError("SQL 不允许包含多语句或注释")
        try:
            parsed = sqlglot.parse_one(sql, read="postgres")
        except sqlglot.ParseError as error:
            raise SQLPolicyError("SQL 语法无效") from error
        if not isinstance(parsed, exp.Select):
            raise SQLPolicyError("只允许 SELECT 查询")
        tables = {table.name for table in parsed.find_all(exp.Table)}
        unknown_tables = tables - self.policy.allowed_tables
        if unknown_tables:
            raise SQLPolicyError(f"不允许访问表：{sorted(unknown_tables)}")
        columns = {column.name for column in parsed.find_all(exp.Column)}
        unknown_columns = columns - self.policy.allowed_columns
        if unknown_columns and "*" not in columns:
            raise SQLPolicyError(f"不允许访问字段：{sorted(unknown_columns)}")
        limit = parsed.args.get("limit")
        if limit and isinstance(limit.expression, exp.Literal) and int(limit.expression.this) > self.policy.max_limit:
            raise SQLPolicyError(f"LIMIT 不能超过 {self.policy.max_limit}")
        return parsed
