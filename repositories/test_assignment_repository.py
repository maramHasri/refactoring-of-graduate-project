from datetime import datetime

from models import Membership, TestStudentAssignment, User
from repositories.base_repository import BaseRepository
from utils.db import db


class TestStudentAssignmentRepository(BaseRepository):
    def find(self, *, test_id: int, student_membership_id: int) -> TestStudentAssignment | None:
        return db.session.execute(
            db.select(TestStudentAssignment).where(
                TestStudentAssignment.test_id == test_id,
                TestStudentAssignment.student_membership_id == student_membership_id,
            )
        ).scalar_one_or_none()

    def list_for_test(self, test_id: int) -> list[TestStudentAssignment]:
        return list(
            db.session.execute(
                db.select(TestStudentAssignment)
                .where(TestStudentAssignment.test_id == test_id)
                .order_by(TestStudentAssignment.student_membership_id)
            ).scalars().all()
        )

    def list_for_test_with_student_profile(self, test_id: int) -> list[dict]:
        rows = db.session.execute(
            db.select(TestStudentAssignment, Membership, User)
            .join(
                Membership,
                Membership.id == TestStudentAssignment.student_membership_id,
            )
            .join(User, User.id == Membership.user_id)
            .where(TestStudentAssignment.test_id == test_id)
            .order_by(Membership.id)
        ).all()
        return [
            {
                "assignment": assignment,
                "membership": membership,
                "user": user,
            }
            for assignment, membership, user in rows
        ]

    def list_pending_invites_for_test(self, test_id: int) -> list[TestStudentAssignment]:
        return list(
            db.session.execute(
                db.select(TestStudentAssignment).where(
                    TestStudentAssignment.test_id == test_id,
                    TestStudentAssignment.invite_status.in_(("PENDING", "FAILED")),
                )
            ).scalars().all()
        )

    def mark_invite_sent(self, row: TestStudentAssignment, *, sent_at: datetime) -> None:
        row.invite_status = "SENT"
        row.invite_sent_at = sent_at
        row.invite_error = None

    def mark_invite_failed(self, row: TestStudentAssignment, *, error_message: str) -> None:
        row.invite_status = "FAILED"
        row.invite_error = error_message

    def delete(self, row: TestStudentAssignment) -> None:
        db.session.delete(row)
