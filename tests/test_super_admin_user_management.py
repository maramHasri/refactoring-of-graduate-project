"""Unit tests for Super Admin user update / hard-delete.

Run: python tests/test_super_admin_user_management.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _svc():
    from service.super_admin_management_service import SuperAdminManagementService

    svc = SuperAdminManagementService()
    svc.users = MagicMock()
    svc.repo = MagicMock()
    svc.sessions = MagicMock()
    svc.user_profiles = MagicMock()
    return svc


def test_update_user_reuses_user_service_profile_update():
    from app_factory import create_app
    from utils.messages import Messages

    svc = _svc()
    actor = SimpleNamespace(id=1)
    target = SimpleNamespace(id=15, deleted_at=None, full_name="Old", phone_number=None)
    updated = SimpleNamespace(
        id=15,
        deleted_at=None,
        full_name="New Name",
        phone_number="+9639",
        email="a@b.com",
        user_status="ACTIVE",
        created_at=None,
        suspended_at=None,
        suspension_reason=None,
        is_superadmin=False,
    )
    svc.users.get_by_id.return_value = target
    svc.user_profiles.update_profile.return_value = updated
    svc.repo.load_memberships_for_users.return_value = {15: []}

    with create_app().app_context():
        result = svc.update_user(
            15, {"full_name": "New Name", "phone_number": "+9639"}, actor_user=actor
        )
    svc.user_profiles.update_profile.assert_called_once_with(
        target, {"full_name": "New Name", "phone_number": "+9639"}
    )
    assert result["message"] == Messages.USER_UPDATED_SUCCESSFULLY
    assert result["user"]["name"] == "New Name"
    assert result["user"]["phone_number"] == "+9639"


def test_update_user_rejects_soft_deleted():
    from service.exceptions import ConflictError
    from utils.messages import Messages

    svc = _svc()
    svc.users.get_by_id.return_value = SimpleNamespace(id=9, deleted_at="2026-01-01")
    try:
        svc.update_user(9, {"full_name": "X"}, actor_user=SimpleNamespace(id=1))
        assert False, "expected ConflictError"
    except ConflictError as exc:
        assert Messages.ACCOUNT_IS_DELETED in str(exc)


def test_hard_delete_blocks_self_and_other_superadmin():
    from service.exceptions import ForbiddenError
    from utils.messages import Messages

    svc = _svc()
    actor = SimpleNamespace(id=1)
    svc.users.get_by_id.return_value = SimpleNamespace(
        id=1, is_superadmin=True, deleted_at=None
    )
    try:
        svc.hard_delete_user(1, actor_user=actor)
        assert False
    except ForbiddenError as exc:
        assert Messages.SUPER_ADMINS_CANNOT_DELETE_THEIR_OWN_ACCOUNT in str(exc)

    svc.users.get_by_id.return_value = SimpleNamespace(
        id=2, is_superadmin=True, deleted_at=None
    )
    try:
        svc.hard_delete_user(2, actor_user=actor)
        assert False
    except ForbiddenError as exc:
        assert Messages.SUPER_ADMINS_CANNOT_PERMANENTLY_DELETE_OTHER_SUPER_ADMINS in str(
            exc
        )


def test_hard_delete_blocks_owners_of_orgs_or_questions():
    from service.exceptions import ConflictError
    from utils.messages import Messages

    svc = _svc()
    actor = SimpleNamespace(id=1)
    target = SimpleNamespace(id=20, is_superadmin=False, deleted_at=None)
    svc.users.get_by_id.return_value = target
    svc.repo.count_owned_workspaces.return_value = 1
    svc.repo.count_owned_questions.return_value = 0
    try:
        svc.hard_delete_user(20, actor_user=actor)
        assert False
    except ConflictError as exc:
        assert Messages.CANNOT_PERMANENTLY_DELETE_USER_WHO_OWNS_ORGANIZATIONS in str(exc)

    svc.repo.count_owned_workspaces.return_value = 0
    svc.repo.count_owned_questions.return_value = 3
    try:
        svc.hard_delete_user(20, actor_user=actor)
        assert False
    except ConflictError as exc:
        assert Messages.CANNOT_PERMANENTLY_DELETE_USER_WHO_OWNS_QUESTIONS in str(exc)


def test_hard_delete_success_path():
    from unittest.mock import patch

    from app_factory import create_app
    from utils.messages import Messages

    svc = _svc()
    actor = SimpleNamespace(id=1)
    target = SimpleNamespace(id=20, is_superadmin=False, deleted_at=None)
    svc.users.get_by_id.return_value = target
    svc.repo.count_owned_workspaces.return_value = 0
    svc.repo.count_owned_questions.return_value = 0

    with create_app().app_context(), patch(
        "service.super_admin_management_service.db"
    ) as mock_db:
        result = svc.hard_delete_user(20, actor_user=actor)

    svc.sessions.deactivate_all_for_user.assert_called_once_with(20)
    mock_db.session.delete.assert_called_once_with(target)
    mock_db.session.commit.assert_called_once()
    assert result == {
        "message": Messages.USER_PERMANENTLY_DELETED_SUCCESSFULLY,
        "user_id": 20,
    }


def test_routes_registered():
    from router import super_admin_management_routes as routes

    source = Path(routes.__file__).read_text(encoding="utf-8")
    assert 'route("/users/<int:user_id>", methods=["PATCH"])' in source
    assert 'route("/users/<int:user_id>", methods=["DELETE"])' in source
    assert "@require_superadmin" in source


if __name__ == "__main__":
    tests = [name for name, obj in globals().items() if name.startswith("test_")]
    failed = 0
    for name in tests:
        try:
            globals()[name]()
            print(f"OK  {name}")
        except Exception as exc:
            failed += 1
            print(f"FAIL {name}: {exc}")
    if failed:
        raise SystemExit(1)
    print(f"\n{len(tests)} passed")
