from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from uuid import UUID


class RoleCode(StrEnum):
    CUSTOMER = "customer"
    AGENT = "agent"
    SUPERVISOR = "supervisor"
    ADMIN = "admin"
    AUDITOR = "auditor"


class ScopeType(StrEnum):
    SELF = "self"
    ASSIGNED = "assigned"
    TEAM = "team"
    GLOBAL = "global"


class FieldAccess(StrEnum):
    RAW = "raw"
    MASKED = "masked"
    DENIED = "denied"


@dataclass(frozen=True)
class DataScope:
    """服务端生成的数据范围，禁止直接采用客户端提交的 scope。"""

    scope_type: ScopeType
    user_id: UUID
    team_ids: tuple[UUID, ...] = ()
    allowed_fields: dict[str, FieldAccess] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "type": self.scope_type.value,
            "userId": str(self.user_id),
            "teamIds": [str(team_id) for team_id in self.team_ids],
            "fields": {
                key: value.value for key, value in (self.allowed_fields or {}).items()
            },
        }


@dataclass(frozen=True)
class AuthPrincipal:
    user_id: UUID
    username: str
    display_name: str
    roles: frozenset[RoleCode]
    permissions: frozenset[str]
    team_ids: tuple[UUID, ...]
    data_scope: DataScope

    def has_role(self, role: RoleCode) -> bool:
        return role in self.roles

    def can(self, permission: str) -> bool:
        return permission in self.permissions or RoleCode.ADMIN in self.roles
