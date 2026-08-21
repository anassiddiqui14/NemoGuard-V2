"""
Unit tests for src/api/auth.py's role hierarchy (build plan Priority 7 /
spec §11.2): _effective_roles, require_role, require_any_role.
"""

import pytest
from fastapi import HTTPException

from src.api.auth import User, _effective_roles, require_role, require_any_role


def make_user(roles):
    return User(user_id="u1", email="u1@x.com", roles=roles, tenant_id="t", workspace_id="w")


class TestEffectiveRoles:
    def test_viewer_only_has_viewer(self):
        assert _effective_roles(["viewer"]) == {"viewer"}

    def test_operator_includes_viewer(self):
        assert _effective_roles(["operator"]) == {"viewer", "operator"}

    def test_commander_includes_operator_and_viewer(self):
        assert _effective_roles(["commander"]) == {"viewer", "operator", "commander"}

    def test_admin_includes_everything_except_service(self):
        effective = _effective_roles(["admin"])
        assert effective == {"viewer", "operator", "commander", "approver", "auditor", "admin"}

    def test_approver_is_not_included_by_commander(self):
        effective = _effective_roles(["commander"])
        assert "approver" not in effective

    def test_auditor_is_isolated(self):
        assert _effective_roles(["auditor"]) == {"auditor"}

    def test_service_is_isolated(self):
        assert _effective_roles(["service"]) == {"service"}

    def test_multiple_roles_union(self):
        effective = _effective_roles(["viewer", "approver"])
        assert effective == {"viewer", "approver"}

    def test_unknown_role_passes_through(self):
        # Defensive: an unrecognized role string shouldn't crash, just be
        # treated as its own isolated role.
        assert _effective_roles(["some_future_role"]) == {"some_future_role"}


class TestRequireRole:
    @pytest.mark.asyncio
    async def test_commander_satisfies_operator_requirement(self):
        checker = require_role("operator")
        user = make_user(["commander"])
        result = await _call_checker(checker, user)
        assert result is user

    @pytest.mark.asyncio
    async def test_viewer_does_not_satisfy_operator_requirement(self):
        checker = require_role("operator")
        user = make_user(["viewer"])
        with pytest.raises(HTTPException) as exc_info:
            await _call_checker(checker, user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_admin_satisfies_any_operational_requirement(self):
        checker = require_role("commander")
        user = make_user(["admin"])
        result = await _call_checker(checker, user)
        assert result is user

    @pytest.mark.asyncio
    async def test_commander_does_not_satisfy_approver_requirement(self):
        checker = require_role("approver")
        user = make_user(["commander"])
        with pytest.raises(HTTPException) as exc_info:
            await _call_checker(checker, user)
        assert exc_info.value.status_code == 403

    @pytest.mark.asyncio
    async def test_approver_satisfies_approver_requirement(self):
        checker = require_role("approver")
        user = make_user(["approver"])
        result = await _call_checker(checker, user)
        assert result is user


class TestRequireAnyRole:
    @pytest.mark.asyncio
    async def test_matches_any_acceptable_role(self):
        checker = require_any_role("approver", "admin")
        user = make_user(["approver"])
        result = await _call_checker(checker, user)
        assert result is user

    @pytest.mark.asyncio
    async def test_rejects_when_no_role_matches(self):
        checker = require_any_role("approver", "auditor")
        user = make_user(["commander"])
        with pytest.raises(HTTPException) as exc_info:
            await _call_checker(checker, user)
        assert exc_info.value.status_code == 403


async def _call_checker(checker, user):
    """
    require_role/require_any_role return an async function with a FastAPI
    Depends() default parameter. Call the underlying logic directly by
    invoking it with the user as the current_user argument (bypassing
    FastAPI's DI, which isn't running in a unit test).
    """
    return await checker(current_user=user)
