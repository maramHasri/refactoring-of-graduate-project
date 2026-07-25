"""Focused unit checks for teacher-owned student groups.

Run: python tests/test_student_groups.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _svc():
    from service.student_group_service import StudentGroupService

    svc = object.__new__(StudentGroupService)
    svc.groups = MagicMock()
    svc.subjects = MagicMock()
    svc.subject_memberships = MagicMock()
    svc.memberships = MagicMock()
    svc.workspaces = MagicMock()
    return svc


def test_create_group_requires_assigned_teacher():
    from service.exceptions import ForbiddenError
    from service.student_group_service import StudentGroupService
    from utils.messages import Messages

    svc = _svc()
    workspace = SimpleNamespace(id=1, owner_membership_id=99)
    actor = SimpleNamespace(id=10, role="TEACHER")
    svc.workspaces.get_by_id.return_value = workspace
    svc.subjects.get_active_by_id.return_value = SimpleNamespace(id=5, name="Programming")
    svc.subject_memberships.find_active_by_role.return_value = None

    with patch(
        "service.student_group_service.can_create_subject_student_group",
        return_value=False,
    ):
        try:
            svc.create_group(
                workspace_id=1,
                subject_id=5,
                name="Group A",
                actor_membership=actor,
            )
            assert False, "expected ForbiddenError"
        except ForbiddenError as exc:
            assert Messages.ONLY_ASSIGNED_SUBJECT_TEACHERS_CAN_CREATE_STUDENT_GROUPS in str(
                exc
            )


def test_create_group_success_for_assigned_teacher():
    svc = _svc()
    workspace = SimpleNamespace(id=1, owner_membership_id=99)
    actor = SimpleNamespace(id=10, role="TEACHER")
    subject = SimpleNamespace(id=5, name="Programming")
    svc.workspaces.get_by_id.return_value = workspace
    svc.subjects.get_active_by_id.return_value = subject
    svc.subject_memberships.find_active_by_role.return_value = SimpleNamespace(id=1)
    svc.groups.find_by_subject_and_name.return_value = None

    with patch(
        "service.student_group_service.can_create_subject_student_group",
        return_value=True,
    ), patch("service.student_group_service.db") as db:
        group = svc.create_group(
            workspace_id=1,
            subject_id=5,
            name="Group A",
            actor_membership=actor,
        )
    assert group.name == "Group A"
    assert group.created_by_membership_id == 10
    assert group.subject_id == 5
    svc.groups.add.assert_called_once()
    db.session.commit.assert_called_once()


def test_add_members_rejects_unsubscribed_student():
    from service.exceptions import ValidationError
    from utils.messages import Messages

    svc = _svc()
    actor = SimpleNamespace(id=10, role="TEACHER")
    group = SimpleNamespace(
        id=3,
        subject_id=5,
        workspace_id=1,
        created_by_membership_id=10,
        name="Group A",
    )
    svc.groups.get_in_workspace.return_value = group
    svc.subject_memberships.find_active_by_role.side_effect = [
        SimpleNamespace(id=99),  # teacher link for owner check
        None,  # student enrollment missing
    ]
    svc.groups.list_member_ids.return_value = set()
    svc.memberships.get_by_id.return_value = SimpleNamespace(
        id=20, workspace_id=1, role="STUDENT", status="ACTIVE", user=None
    )

    with patch(
        "service.student_group_service.verify_subject_teacher_access",
        return_value=True,
    ):
        try:
            svc.add_members(
                workspace_id=1,
                group_id=3,
                student_ids=[20],
                actor_membership=actor,
            )
            assert False, "expected ValidationError"
        except ValidationError as exc:
            assert "20" in str(exc)


def test_add_members_atomic_conflict_rejects_all():
    from service.exceptions import StudentGroupSubjectConflictError

    svc = _svc()
    actor = SimpleNamespace(id=10, role="TEACHER")
    group = SimpleNamespace(
        id=3,
        subject_id=5,
        workspace_id=1,
        created_by_membership_id=10,
        name="Group B",
    )
    other = SimpleNamespace(
        id=2,
        name="Group A",
        created_by_membership_id=11,
        created_by=SimpleNamespace(user=SimpleNamespace(full_name="Teacher A")),
    )
    svc.groups.get_in_workspace.return_value = group
    svc.groups.list_member_ids.return_value = set()
    svc.subject_memberships.find_active_by_role.return_value = SimpleNamespace(id=1)

    def membership_by_id(mid):
        return SimpleNamespace(
            id=mid,
            workspace_id=1,
            role="STUDENT",
            status="ACTIVE",
            user=SimpleNamespace(full_name=f"Student {mid}"),
        )

    svc.memberships.get_by_id.side_effect = membership_by_id
    svc.groups.map_current_groups_for_students_in_subject.return_value = {20: other}

    with patch(
        "service.student_group_service.verify_subject_teacher_access",
        return_value=True,
    ):
        try:
            svc.add_members(
                workspace_id=1,
                group_id=3,
                student_ids=[20, 21],
                actor_membership=actor,
            )
            assert False, "expected StudentGroupSubjectConflictError"
        except StudentGroupSubjectConflictError as exc:
            assert exc.error_code == "STUDENT_GROUP_SUBJECT_CONFLICT"
            assert len(exc.conflicts) == 1
            assert exc.conflicts[0]["membership_id"] == 20
            assert exc.conflicts[0]["existing_group_name"] == "Group A"
    svc.groups.add.assert_not_called()


def test_non_owner_cannot_update_group():
    from service.exceptions import ForbiddenError
    from utils.messages import Messages

    svc = _svc()
    actor = SimpleNamespace(id=10, role="TEACHER")
    group = SimpleNamespace(
        id=3,
        subject_id=5,
        workspace_id=1,
        created_by_membership_id=99,
        name="Group A",
    )
    svc.groups.get_in_workspace.return_value = group
    svc.subject_memberships.find_active_by_role.return_value = SimpleNamespace(id=1)

    with patch(
        "service.student_group_service.verify_subject_teacher_access",
        return_value=True,
    ):
        try:
            svc.update_group(
                workspace_id=1,
                group_id=3,
                actor_membership=actor,
                data={"name": "Renamed"},
            )
            assert False, "expected ForbiddenError"
        except ForbiddenError as exc:
            assert Messages.ONLY_THE_GROUP_OWNER_CAN_MANAGE_THIS_STUDENT_GROUP in str(exc)


def test_available_students_marks_assigned():
    svc = _svc()
    actor = SimpleNamespace(id=10, role="TEACHER")
    workspace = SimpleNamespace(id=1, owner_membership_id=1)
    svc.workspaces.get_by_id.return_value = workspace
    svc.subjects.get_active_by_id.return_value = SimpleNamespace(id=5)
    svc.subject_memberships.find_active_by_role.return_value = SimpleNamespace(id=1)

    enrolled = SimpleNamespace(
        membership_id=20,
        membership=SimpleNamespace(
            id=20,
            user=SimpleNamespace(full_name="Student 1", email="a@x.com"),
        ),
    )
    svc.subject_memberships.list_students_for_subject.return_value = [enrolled]
    other = SimpleNamespace(
        id=2,
        name="Group A",
        created_by_membership_id=11,
        created_by=SimpleNamespace(user=SimpleNamespace(full_name="Teacher A")),
    )
    svc.groups.map_current_groups_for_students_in_subject.return_value = {20: other}

    with patch(
        "service.student_group_service.can_view_subject_student_groups",
        return_value=True,
    ):
        items = svc.list_available_students(
            workspace_id=1, subject_id=5, actor_membership=actor
        )
    assert items[0]["is_available"] is False
    assert items[0]["current_group"]["name"] == "Group A"


def test_assign_schema_requires_students_or_groups():
    from marshmallow import ValidationError
    from schemas.test_schema import AssignStudentsToTestSchema

    try:
        AssignStudentsToTestSchema().load({})
        assert False, "expected ValidationError"
    except ValidationError:
        pass

    data = AssignStudentsToTestSchema().load({"group_ids": [1]})
    assert data["group_ids"] == [1]
    assert data["student_membership_ids"] == []


if __name__ == "__main__":
    test_create_group_requires_assigned_teacher()
    test_create_group_success_for_assigned_teacher()
    test_add_members_rejects_unsubscribed_student()
    test_add_members_atomic_conflict_rejects_all()
    test_non_owner_cannot_update_group()
    test_available_students_marks_assigned()
    test_assign_schema_requires_students_or_groups()
    print("all student group checks passed")
