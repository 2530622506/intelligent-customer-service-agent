from collections.abc import Iterable
from uuid import UUID

from app.auth.types import DataScope, FieldAccess, RoleCode, ScopeType

ROLE_PERMISSIONS: dict[RoleCode, frozenset[str]] = {
    RoleCode.CUSTOMER: frozenset({"conversation:read:self", "order:read:self", "ticket:create:self"}),
    RoleCode.AGENT: frozenset(
        {"conversation:read:assigned", "conversation:reply:assigned", "ticket:write:assigned"}
    ),
    RoleCode.SUPERVISOR: frozenset(
        {"conversation:read:team", "analytics:read:team", "knowledge:write", "evaluation:run"}
    ),
    RoleCode.ADMIN: frozenset({"admin:manage", "knowledge:write", "evaluation:run"}),
    RoleCode.AUDITOR: frozenset({"audit:read", "trace:read"}),
}


def scope_for_roles(
    user_id: UUID,
    roles: frozenset[RoleCode],
    team_ids: Iterable[UUID],
) -> DataScope:
    if RoleCode.ADMIN in roles or RoleCode.AUDITOR in roles:
        scope_type = ScopeType.GLOBAL
    elif RoleCode.SUPERVISOR in roles:
        scope_type = ScopeType.TEAM
    elif RoleCode.AGENT in roles:
        scope_type = ScopeType.ASSIGNED
    else:
        scope_type = ScopeType.SELF

    field_access = {
        "name": FieldAccess.MASKED,
        "phone": FieldAccess.MASKED,
        "address": FieldAccess.DENIED,
        "order_no": FieldAccess.RAW,
    }
    if RoleCode.ADMIN in roles or RoleCode.SUPERVISOR in roles:
        field_access["address"] = FieldAccess.MASKED
    return DataScope(scope_type, user_id, tuple(team_ids), field_access)


def permissions_for_roles(roles: frozenset[RoleCode]) -> frozenset[str]:
    return frozenset(permission for role in roles for permission in ROLE_PERMISSIONS[role])
