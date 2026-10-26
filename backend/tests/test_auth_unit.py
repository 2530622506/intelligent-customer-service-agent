from uuid import uuid4

from app.auth.passwords import hash_password, verify_password
from app.auth.policy import permissions_for_roles, scope_for_roles
from app.auth.tokens import create_token, decode_token
from app.auth.types import RoleCode, ScopeType
from app.core.config import Settings


def test_password_hash_is_not_plaintext_and_verifies() -> None:
    encoded = hash_password("demo-password")

    assert encoded != "demo-password"
    assert verify_password("demo-password", encoded)
    assert not verify_password("wrong-password", encoded)


def test_role_policy_generates_server_side_scope() -> None:
    user_id = uuid4()
    scope = scope_for_roles(user_id, frozenset({RoleCode.CUSTOMER}), ())

    assert scope.scope_type is ScopeType.SELF
    assert scope.user_id == user_id
    assert permissions_for_roles(frozenset({RoleCode.ADMIN}))


def test_refresh_and_access_tokens_have_distinct_types() -> None:
    settings = Settings(app_secret_key="unit-test-secret")
    user_id = uuid4()
    access, _, _ = create_token(user_id, "access", settings, 60)
    refresh, _, _ = create_token(user_id, "refresh", settings, 60)

    assert decode_token(access, "access", settings)["sub"] == str(user_id)
    assert decode_token(refresh, "refresh", settings)["sub"] == str(user_id)
