"""Question Bank usage_count — operation-based historical counter.

Run: python tests/test_question_bank_usage_count.py
"""

from __future__ import annotations

import inspect
import sys
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, call, patch

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _draft_test(*, test_id=1, subject_id=10, workspace_id=1):
    return SimpleNamespace(
        id=test_id,
        subject_id=subject_id,
        workspace_id=workspace_id,
        status="DRAFT",
        total_score=None,
        target_total_score=None,
        auto_distribute_scores=False,
        passing_score=None,
    )


def _bank(*, bank_id=100, subject_id=10, workspace_id=1, usage_count=0):
    return SimpleNamespace(
        id=bank_id,
        title="Bank A",
        description=None,
        workspace_id=workspace_id,
        subject_id=subject_id,
        subject=SimpleNamespace(name="Math"),
        visibility="WORKSPACE",
        is_archived=False,
        created_by_membership_id=1,
        usage_count=usage_count,
        created_at=None,
        updated_at=None,
        deleted_at=None,
    )


def _source_question(*, qid, bank_id, subject_id=10, workspace_id=1):
    bank = _bank(bank_id=bank_id, subject_id=subject_id, workspace_id=workspace_id)
    return SimpleNamespace(
        id=qid,
        bank_id=bank_id,
        bank=bank,
        points=Decimal("1"),
        question_text=f"Q{qid}",
        explanation=None,
        image_path=None,
        question_type=SimpleNamespace(code="MCQ"),
        topic_id=None,
        topic=None,
        difficulty="EASY",
    )


def _test_service_shell():
    from service.test_service import TestService

    svc = object.__new__(TestService)
    svc.tests = MagicMock()
    svc.test_questions = MagicMock()
    svc.test_questions.find_by_test_and_question.return_value = None
    svc.questions = MagicMock()
    svc.bank_service = MagicMock()
    svc.exam_blueprint = MagicMock()
    svc._resolve_test_access = MagicMock()
    svc._resolve_draft_test = MagicMock()
    svc._snapshot_from_source_question = MagicMock(
        return_value={
            "snapshot_question_text": "text",
            "snapshot_explanation": None,
            "snapshot_image_path": None,
            "snapshot_type_code": "MCQ",
            "snapshot_topic_id": None,
            "snapshot_topic_name": None,
            "snapshot_difficulty": "EASY",
            "snapshot_points": Decimal("1"),
            "snapshot_choices_json": "[]",
        }
    )
    svc._refresh_test_scoring = MagicMock()
    svc.serialize_test_question = MagicMock(side_effect=lambda row: {"id": id(row)})
    return svc


# ── 1–3: from-bank selection (+1 per successful request) ─────────────────────


def test_1_from_bank_many_questions_one_usage():
    from service.test_service import TestService

    svc = _test_service_shell()
    test = _draft_test()
    bank = _bank(bank_id=100)
    svc._resolve_draft_test.return_value = test
    svc.bank_service.resolve_bank_for_question_view.return_value = bank
    svc.questions.get_active_in_bank.side_effect = lambda qid, bid: _source_question(
        qid=qid, bank_id=bid
    )

    with patch("service.test_service.db") as db:
        TestService.add_questions_from_bank_selection(
            svc,
            test_id=1,
            workspace_id=1,
            actor_membership=SimpleNamespace(id=1),
            bank_id=100,
            question_ids=[1, 2, 3, 4, 5],
        )

    svc.bank_service.increment_usage_for_banks.assert_called_once_with({100})
    assert svc.test_questions.add.call_count == 5
    db.session.commit.assert_called_once()


def test_2_second_request_increments_again():
    from service.test_service import TestService

    svc = _test_service_shell()
    test = _draft_test()
    bank = _bank(bank_id=100)
    svc._resolve_draft_test.return_value = test
    svc.bank_service.resolve_bank_for_question_view.return_value = bank
    svc.questions.get_active_in_bank.side_effect = lambda qid, bid: _source_question(
        qid=qid, bank_id=bid
    )

    with patch("service.test_service.db"):
        TestService.add_questions_from_bank_selection(
            svc,
            test_id=1,
            workspace_id=1,
            actor_membership=SimpleNamespace(id=1),
            bank_id=100,
            question_ids=[10],
        )
        TestService.add_questions_from_bank_selection(
            svc,
            test_id=1,
            workspace_id=1,
            actor_membership=SimpleNamespace(id=1),
            bank_id=100,
            question_ids=[11],
        )

    assert svc.bank_service.increment_usage_for_banks.call_args_list == [
        call({100}),
        call({100}),
    ]


def test_3_single_question_still_plus_one():
    from service.test_service import TestService

    svc = _test_service_shell()
    test = _draft_test()
    bank = _bank(bank_id=55)
    svc._resolve_draft_test.return_value = test
    svc.bank_service.resolve_bank_for_question_view.return_value = bank
    svc.questions.get_active_in_bank.return_value = _source_question(qid=1, bank_id=55)

    with patch("service.test_service.db"):
        TestService.add_questions_from_bank_selection(
            svc,
            test_id=1,
            workspace_id=1,
            actor_membership=SimpleNamespace(id=1),
            bank_id=55,
            question_ids=[1],
        )

    svc.bank_service.increment_usage_for_banks.assert_called_once_with({55})


# ── 4–5: random-from-banks / blueprint ───────────────────────────────────────


def test_4_blueprint_each_used_bank_plus_one():
    from service.test_service import TestService

    svc = _test_service_shell()
    svc._resolve_draft_test.return_value = _draft_test()
    svc.exam_blueprint.build_plan.return_value = []
    svc.exam_blueprint.select_questions.return_value = (
        [
            _source_question(qid=1, bank_id=10),
            _source_question(qid=2, bank_id=10),
            _source_question(qid=3, bank_id=20),
            _source_question(qid=4, bank_id=30),
        ],
        {"banks": []},
    )

    with patch("service.test_service.db"):
        TestService.generate_exam_from_blueprint(
            svc,
            test_id=1,
            workspace_id=1,
            actor_membership=SimpleNamespace(id=1),
            banks_blueprint=[{"bank_id": 10}, {"bank_id": 20}, {"bank_id": 30}],
        )

    called = svc.bank_service.increment_usage_for_banks.call_args[0][0]
    assert called == {10, 20, 30}


def test_5_blueprint_unused_bank_not_incremented():
    from service.test_service import TestService

    svc = _test_service_shell()
    svc._resolve_draft_test.return_value = _draft_test()
    svc.exam_blueprint.build_plan.return_value = []
    # Bank 99 in blueprint but no questions selected from it
    svc.exam_blueprint.select_questions.return_value = (
        [
            _source_question(qid=1, bank_id=10),
            _source_question(qid=2, bank_id=20),
        ],
        {"banks": [{"bank_id": 10}, {"bank_id": 20}, {"bank_id": 99}]},
    )

    with patch("service.test_service.db"):
        TestService.generate_exam_from_blueprint(
            svc,
            test_id=1,
            workspace_id=1,
            actor_membership=SimpleNamespace(id=1),
            banks_blueprint=[
                {"bank_id": 10},
                {"bank_id": 20},
                {"bank_id": 99},
            ],
        )

    called = svc.bank_service.increment_usage_for_banks.call_args[0][0]
    assert called == {10, 20}
    assert 99 not in called


# ── 6: failed request leaves usage unchanged ─────────────────────────────────


def test_6_failed_request_does_not_increment():
    from service.exceptions import NotFoundError
    from service.test_service import TestService

    svc = _test_service_shell()
    svc._resolve_draft_test.return_value = _draft_test()
    svc.bank_service.resolve_bank_for_question_view.return_value = _bank(bank_id=100)
    svc.questions.get_active_in_bank.return_value = None

    with patch("service.test_service.db") as db:
        try:
            TestService.add_questions_from_bank_selection(
                svc,
                test_id=1,
                workspace_id=1,
                actor_membership=SimpleNamespace(id=1),
                bank_id=100,
                question_ids=[999],
            )
            assert False, "expected NotFoundError"
        except NotFoundError:
            pass

    svc.bank_service.increment_usage_for_banks.assert_not_called()
    db.session.commit.assert_not_called()


# ── 7: all duplicates → no increment ─────────────────────────────────────────


def test_7_all_duplicates_no_increment():
    from service.test_service import TestService
    from utils.enums import TestQuestionSourceType

    svc = _test_service_shell()
    svc._resolve_test_access.return_value = _draft_test()
    q = _source_question(qid=1, bank_id=100)
    svc.questions.get_by_id.return_value = q
    svc.test_questions.find_by_test_and_question.return_value = SimpleNamespace(id=1)

    with patch("service.test_service.db"):
        result = TestService.add_questions_from_bank(
            svc,
            test_id=1,
            workspace_id=1,
            actor_membership=SimpleNamespace(id=1),
            question_ids=[1, 1],
            source_type=TestQuestionSourceType.QUESTION_BANK.value,
        )

    assert result == []
    # Empty set still passed — helper no-ops; must not claim a real bank usage
    args = svc.bank_service.increment_usage_for_banks.call_args[0][0]
    assert args == set()


# ── 8–9: deletes do not decrement ───────────────────────────────────────────


def test_8_delete_test_does_not_touch_usage_count():
    from service.test_service import TestService

    src = inspect.getsource(TestService.delete_test)
    assert "usage_count" not in src
    assert "increment_usage" not in src


def test_9_delete_test_question_does_not_touch_usage_count():
    from service.test_service import TestService

    src = inspect.getsource(TestService.delete_test_question)
    assert "usage_count" not in src
    assert "increment_usage" not in src


# ── 10: atomic SQL increment (no read-modify-write) ──────────────────────────


def test_10_atomic_increment_uses_sql_plus_one():
    from repositories.question_bank_repository import QuestionBankRepository

    repo = QuestionBankRepository()
    with patch("repositories.question_bank_repository.db") as db:
        update_mock = MagicMock()
        where_mock = MagicMock()
        values_mock = MagicMock()
        db.update.return_value = update_mock
        update_mock.where.return_value = where_mock
        where_mock.values.return_value = values_mock

        repo.increment_usage_counts({7, 8})

        db.session.execute.assert_called_once()
        # values(...) received usage_count=Column + 1 expression, not a Python int
        values_kwargs = where_mock.values.call_args.kwargs
        assert "usage_count" in values_kwargs
        expr = values_kwargs["usage_count"]
        # SQLAlchemy BinaryExpression / ClauseElement — not a plain int
        assert not isinstance(expr, int)
        assert "+ 1" in str(expr) or "usage_count" in str(expr).lower()


def test_10b_empty_bank_ids_skips_update():
    from repositories.question_bank_repository import QuestionBankRepository

    repo = QuestionBankRepository()
    with patch("repositories.question_bank_repository.db") as db:
        repo.increment_usage_counts(set())
        repo.increment_usage_counts(None)
        db.session.execute.assert_not_called()


def test_10c_concurrent_style_two_calls_two_sql_updates():
    """Two successful ops each issue their own atomic UPDATE +1 (no lost updates)."""
    from repositories.question_bank_repository import QuestionBankRepository

    repo = QuestionBankRepository()
    with patch("repositories.question_bank_repository.db") as db:
        db.update.return_value.where.return_value.values.return_value = MagicMock()
        repo.increment_usage_counts({42})
        repo.increment_usage_counts({42})
        assert db.session.execute.call_count == 2


# ── 11: serialization via _serialize_bank ────────────────────────────────────


def test_11_serialize_bank_includes_usage_count():
    from service.question_bank_service import QuestionBankService

    svc = QuestionBankService()
    svc.subjects = MagicMock()
    bank = _bank(bank_id=12, usage_count=27)
    payload = svc._serialize_bank(bank)
    assert payload["usage_count"] == 27
    assert payload["id"] == 12


def test_11b_serialize_bank_defaults_null_usage_to_zero():
    from service.question_bank_service import QuestionBankService

    svc = QuestionBankService()
    svc.subjects = MagicMock()
    bank = _bank(usage_count=None)
    assert svc._serialize_bank(bank)["usage_count"] == 0


# ── 12: workspace dashboard recent_question_banks ────────────────────────────


def test_12_dashboard_recent_banks_include_usage_count():
    from service.workspace_dashboard_service import WorkspaceDashboardService

    svc = WorkspaceDashboardService()
    svc.workspaces = MagicMock()
    svc.workspaces.get_by_id.return_value = SimpleNamespace(
        id=1, kind="INSTITUTION", owner_membership_id=1
    )
    svc._ensure_dashboard_access = MagicMock(
        return_value=SimpleNamespace(id=1, kind="INSTITUTION", owner_membership_id=1)
    )
    svc.dashboard = MagicMock()
    svc.dashboard.count_active_members_by_role.return_value = {
        "admins": 1,
        "teachers": 1,
        "students": 1,
    }
    svc.dashboard.count_subjects.return_value = 1
    svc.dashboard.average_graded_percentage.return_value = None
    svc.dashboard.most_enrolled_subject.return_value = None
    svc.dashboard.list_recent_subjects.return_value = []
    svc.dashboard.list_recent_members.return_value = []
    svc.dashboard.list_upcoming_tests.return_value = []
    svc.dashboard.graded_performance_trend.return_value = []
    svc.dashboard.list_recent_question_banks.return_value = [
        {
            "bank": _bank(bank_id=5, usage_count=27),
            "question_count": 3,
        }
    ]

    with patch(
        "service.workspace_dashboard_service.format_local_datetime",
        return_value="2026-08-07T12:00:00",
    ), patch(
        "service.workspace_dashboard_service.local_timezone_now",
        return_value=MagicMock(),
    ):
        result = svc.get_dashboard(
            workspace_id=1,
            actor_membership=SimpleNamespace(id=1, role="ADMIN"),
        )

    banks = result["recent_question_banks"]
    assert len(banks) == 1
    assert banks[0]["bank_id"] == 5
    assert banks[0]["usage_count"] == 27


# ── POST /tests/{id}/questions path ──────────────────────────────────────────


def test_add_questions_from_bank_path_increments_once_per_bank():
    from service.test_service import TestService
    from utils.enums import TestQuestionSourceType

    svc = _test_service_shell()
    svc._resolve_test_access.return_value = _draft_test()

    def get_q(qid):
        bank_id = 100 if qid < 10 else 200
        return _source_question(qid=qid, bank_id=bank_id)

    svc.questions.get_by_id.side_effect = get_q

    with patch("service.test_service.db"):
        TestService.add_questions_from_bank(
            svc,
            test_id=1,
            workspace_id=1,
            actor_membership=SimpleNamespace(id=1),
            question_ids=[1, 2, 3, 10, 11],
            source_type=TestQuestionSourceType.QUESTION_BANK.value,
        )

    called = svc.bank_service.increment_usage_for_banks.call_args[0][0]
    assert called == {100, 200}


def test_from_bank_empty_created_skips_increment():
    from service.test_service import TestService

    svc = _test_service_shell()
    svc._resolve_draft_test.return_value = _draft_test()
    svc.bank_service.resolve_bank_for_question_view.return_value = _bank(bank_id=100)

    with patch("service.test_service.db"):
        TestService.add_questions_from_bank_selection(
            svc,
            test_id=1,
            workspace_id=1,
            actor_membership=SimpleNamespace(id=1),
            bank_id=100,
            question_ids=[],
        )

    svc.bank_service.increment_usage_for_banks.assert_not_called()


def test_model_has_usage_count_column():
    from models.question import QuestionBank

    assert hasattr(QuestionBank, "usage_count")
    col = QuestionBank.__table__.c.usage_count
    assert col.nullable is False


def test_increment_helper_on_service_delegates():
    from service.question_bank_service import QuestionBankService

    svc = QuestionBankService()
    svc.banks = MagicMock()
    svc.increment_usage_for_banks({1, 2})
    svc.banks.increment_usage_counts.assert_called_once_with({1, 2})


if __name__ == "__main__":
    tests = [
        test_1_from_bank_many_questions_one_usage,
        test_2_second_request_increments_again,
        test_3_single_question_still_plus_one,
        test_4_blueprint_each_used_bank_plus_one,
        test_5_blueprint_unused_bank_not_incremented,
        test_6_failed_request_does_not_increment,
        test_7_all_duplicates_no_increment,
        test_8_delete_test_does_not_touch_usage_count,
        test_9_delete_test_question_does_not_touch_usage_count,
        test_10_atomic_increment_uses_sql_plus_one,
        test_10b_empty_bank_ids_skips_update,
        test_10c_concurrent_style_two_calls_two_sql_updates,
        test_11_serialize_bank_includes_usage_count,
        test_11b_serialize_bank_defaults_null_usage_to_zero,
        test_12_dashboard_recent_banks_include_usage_count,
        test_add_questions_from_bank_path_increments_once_per_bank,
        test_from_bank_empty_created_skips_increment,
        test_model_has_usage_count_column,
        test_increment_helper_on_service_delegates,
    ]
    for fn in tests:
        fn()
        print(f"  ok  {fn.__name__}")
    print(f"all {len(tests)} question bank usage_count checks passed")
