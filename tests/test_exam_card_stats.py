"""Focused unit checks for exam-card attempt stats.

Run: python tests/test_exam_card_stats.py
"""

from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def test_serialize_test_includes_exam_card_fields():
    from service.test_service import TestService

    svc = object.__new__(TestService)
    svc.attempts = MagicMock()
    test = SimpleNamespace(
        id=7,
        name="Midterm",
        slug="midterm",
        description=None,
        subject_id=1,
        subject=SimpleNamespace(name="Math"),
        status="CLOSED",
        total_score=100,
        target_total_score=100,
        passing_score=50,
        auto_distribute_scores=False,
        settings_config=None,
        availability_time_mode="FLEXIBLE",
        starts_at=None,
        duration_minutes=60,
        entry_window_minutes=None,
        created_by_membership_id=9,
        published_at=None,
        scheduled_publish_at=None,
        closed_at=None,
        archived_at=None,
        created_at=None,
        updated_at=None,
    )
    with patch.object(TestService, "_load_json", return_value={}):
        with patch(
            "service.test_service.format_local_datetime", return_value=None
        ):
            payload = TestService.serialize_test(
                svc,
                test,
                exam_stats={
                    "participants_count": 42,
                    "average_score": 76.5,
                    "graded_attempts_count": 40,
                    "submitted_attempts_count": 2,
                },
            )

    assert payload["participants_count"] == 42
    assert payload["average_score"] == 76.5
    assert payload["graded_attempts_count"] == 40
    assert payload["submitted_attempts_count"] == 2


def test_serialize_test_empty_stats_defaults():
    from service.test_service import TestService

    svc = object.__new__(TestService)
    svc.attempts = MagicMock()
    svc.attempts.exam_card_stats_for_test.return_value = {
        "participants_count": 0,
        "average_score": None,
        "graded_attempts_count": 0,
        "submitted_attempts_count": 0,
    }
    test = SimpleNamespace(
        id=1,
        name="Draft",
        slug="draft",
        description=None,
        subject_id=1,
        subject=None,
        status="DRAFT",
        total_score=None,
        target_total_score=None,
        passing_score=None,
        auto_distribute_scores=False,
        settings_config=None,
        availability_time_mode=None,
        starts_at=None,
        duration_minutes=None,
        entry_window_minutes=None,
        created_by_membership_id=1,
        published_at=None,
        scheduled_publish_at=None,
        closed_at=None,
        archived_at=None,
        created_at=None,
        updated_at=None,
    )
    with patch.object(TestService, "_load_json", return_value=None):
        with patch(
            "service.test_service.format_local_datetime", return_value=None
        ):
            payload = TestService.serialize_test(svc, test)

    assert payload["participants_count"] == 0
    assert payload["average_score"] is None
    assert payload["graded_attempts_count"] == 0
    assert payload["submitted_attempts_count"] == 0


def test_exam_card_stats_empty_ids():
    from repositories.attempt_repository import TestAttemptRepository

    repo = TestAttemptRepository()
    assert repo.exam_card_stats_by_test_ids([]) == {}


def test_exam_card_stats_maps_sql_rows():
    from repositories.attempt_repository import TestAttemptRepository

    repo = TestAttemptRepository()
    fake_rows = [
        # test_id, participants, graded, submitted, average
        (10, 3, 2, 1, 80.0),
        (11, 0, 0, 0, None),
    ]
    fake_result = MagicMock()
    fake_result.all.return_value = fake_rows

    with patch("repositories.attempt_repository.db") as mock_db:
        mock_db.session.execute.return_value = fake_result
        mock_db.select.return_value = MagicMock()
        out = repo.exam_card_stats_by_test_ids([10, 11, 12])

    assert out[10]["participants_count"] == 3
    assert out[10]["graded_attempts_count"] == 2
    assert out[10]["submitted_attempts_count"] == 1
    assert out[10]["average_score"] == 80.0
    assert out[11]["average_score"] is None
    assert out[12] == {
        "participants_count": 0,
        "average_score": None,
        "graded_attempts_count": 0,
        "submitted_attempts_count": 0,
    }


def test_list_tests_uses_batch_stats():
    from service.test_service import TestService

    svc = object.__new__(TestService)
    svc.tests = MagicMock()
    svc.attempts = MagicMock()
    svc.test_questions = MagicMock()
    row = SimpleNamespace(id=7)
    svc.tests.list_for_creator_paginated.return_value = ([row], 1)
    svc.attempts.exam_card_stats_by_test_ids.return_value = {
        7: {
            "participants_count": 5,
            "average_score": 70.0,
            "graded_attempts_count": 4,
            "submitted_attempts_count": 1,
        }
    }
    svc.test_questions.count_by_test_ids.return_value = {7: 25}

    with patch.object(
        TestService,
        "_serialize_test_list_item",
        return_value={"test_id": 7, "participants_count": 5},
    ) as ser:
        payload = TestService.list_tests(svc, SimpleNamespace(id=1))

    svc.tests.list_for_creator_paginated.assert_called_once_with(
        1,
        include_archived=False,
        offset=0,
        limit=20,
    )
    svc.attempts.exam_card_stats_by_test_ids.assert_called_once_with([7])
    svc.test_questions.count_by_test_ids.assert_called_once_with([7])
    ser.assert_called_once()
    assert ser.call_args.kwargs["exam_stats"]["participants_count"] == 5
    assert ser.call_args.kwargs["questions_count"] == 25
    assert payload["tests"][0]["participants_count"] == 5
    assert payload["total"] == 1


def test_list_tests_includes_questions_count():
    from service.test_service import TestService

    svc = object.__new__(TestService)
    svc.tests = MagicMock()
    svc.attempts = MagicMock()
    svc.test_questions = MagicMock()
    row = SimpleNamespace(id=7)
    svc.tests.list_for_creator_paginated.return_value = ([row], 1)
    svc.attempts.exam_card_stats_by_test_ids.return_value = {7: {}}
    svc.test_questions.count_by_test_ids.return_value = {7: 25}

    with patch.object(
        TestService,
        "_serialize_test_list_item",
        return_value={"test_id": 7},
    ) as ser:
        TestService.list_tests(svc, SimpleNamespace(id=1))

    svc.test_questions.count_by_test_ids.assert_called_once_with([7])
    assert ser.call_args.kwargs["questions_count"] == 25


def test_serialize_test_list_item_aliases():
    from service.test_service import TestService

    svc = object.__new__(TestService)
    with patch.object(
        TestService,
        "serialize_test",
        return_value={"test_id": 7, "name": "Midterm", "questions_count": 25},
    ):
        payload = TestService._serialize_test_list_item(
            svc,
            SimpleNamespace(id=7),
            exam_stats={},
            questions_count=25,
        )

    assert payload["title"] == "Midterm"
    assert payload["question_count"] == 25
    assert payload["questions_count"] == 25


def test_count_by_test_ids_batch():
    from repositories.test_repository import TestQuestionRepository

    repo = TestQuestionRepository()
    fake_rows = [(10, 30), (11, 0)]
    fake_result = MagicMock()
    fake_result.all.return_value = fake_rows

    with patch("repositories.test_repository.db") as mock_db:
        mock_db.session.execute.return_value = fake_result
        mock_db.select.return_value = MagicMock()
        mock_db.func.count.return_value = MagicMock()
        out = repo.count_by_test_ids([10, 11, 12])

    assert out[10] == 30
    assert out[11] == 0
    assert out[12] == 0


def test_serialize_test_omits_questions_count_when_not_provided():
    from service.test_service import TestService

    svc = object.__new__(TestService)
    svc.attempts = MagicMock()
    svc.attempts.exam_card_stats_for_test.return_value = {
        "participants_count": 0,
        "average_score": None,
        "graded_attempts_count": 0,
        "submitted_attempts_count": 0,
    }
    test = SimpleNamespace(
        id=1,
        name="Draft",
        slug="draft",
        description=None,
        subject_id=1,
        subject=None,
        status="DRAFT",
        total_score=None,
        target_total_score=None,
        passing_score=None,
        auto_distribute_scores=False,
        settings_config=None,
        availability_time_mode=None,
        starts_at=None,
        duration_minutes=None,
        entry_window_minutes=None,
        created_by_membership_id=1,
        published_at=None,
        scheduled_publish_at=None,
        closed_at=None,
        archived_at=None,
        created_at=None,
        updated_at=None,
    )
    with patch.object(TestService, "_load_json", return_value=None):
        with patch(
            "service.test_service.format_local_datetime", return_value=None
        ):
            payload = TestService.serialize_test(svc, test)

    assert "questions_count" not in payload


def test_serialize_test_includes_questions_count_when_provided():
    from service.test_service import TestService

    svc = object.__new__(TestService)
    svc.attempts = MagicMock()
    test = SimpleNamespace(
        id=7,
        name="Midterm",
        slug="midterm",
        description=None,
        subject_id=1,
        subject=SimpleNamespace(name="Math"),
        status="CLOSED",
        total_score=100,
        target_total_score=100,
        passing_score=50,
        auto_distribute_scores=False,
        settings_config=None,
        availability_time_mode="FLEXIBLE",
        starts_at=None,
        duration_minutes=60,
        entry_window_minutes=None,
        created_by_membership_id=9,
        published_at=None,
        scheduled_publish_at=None,
        closed_at=None,
        archived_at=None,
        created_at=None,
        updated_at=None,
    )
    with patch.object(TestService, "_load_json", return_value={}):
        with patch(
            "service.test_service.format_local_datetime", return_value=None
        ):
            payload = TestService.serialize_test(
                svc,
                test,
                exam_stats={
                    "participants_count": 42,
                    "average_score": 76.5,
                    "graded_attempts_count": 40,
                    "submitted_attempts_count": 2,
                },
                questions_count=25,
            )

    assert payload["questions_count"] == 25


def test_workspace_serializer_includes_counts():
    from service.workspace_service import WorkspaceService

    svc = object.__new__(WorkspaceService)
    test = SimpleNamespace(
        id=3,
        name="Final",
        slug="final",
        description=None,
        subject_id=1,
        subject=SimpleNamespace(name="CS"),
        status="PUBLISHED",
        total_score=100,
        target_total_score=100,
        passing_score=50,
        availability_time_mode="SCHEDULED",
        starts_at=None,
        duration_minutes=90,
        created_by_membership_id=2,
        created_by=None,
        published_at=None,
        closed_at=None,
        archived_at=None,
        created_at=None,
        updated_at=None,
    )
    with patch(
        "service.workspace_service.format_local_datetime", return_value=None
    ):
        payload = WorkspaceService._serialize_institution_workspace_test(
            svc,
            test,
            exam_stats={
                "participants_count": 10,
                "average_score": None,
                "graded_attempts_count": 0,
                "submitted_attempts_count": 8,
            },
            questions_count=25,
        )

    assert payload["participants_count"] == 10
    assert payload["average_score"] is None
    assert payload["graded_attempts_count"] == 0
    assert payload["submitted_attempts_count"] == 8
    assert payload["questions_count"] == 25
    assert payload["question_count"] == 25
    assert payload["title"] == "Final"


if __name__ == "__main__":
    tests = [name for name, obj in list(globals().items()) if name.startswith("test_")]
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
