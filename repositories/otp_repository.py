from datetime import datetime, timezone

from models import EmailOtp, RegistrationIntent
from repositories.base_repository import BaseRepository
from utils.db import db
from utils.enums import EmailOtpPurpose, InstitutionApprovalStatus, WorkspaceKind


class EmailOtpRepository(BaseRepository):
    def find_active_for_email(
        self,
        email: str,
        *,
        purpose: str | None = None,
        purposes: list[str] | None = None,
    ) -> EmailOtp | None:
        query = db.select(EmailOtp).where(
            EmailOtp.email == email.lower().strip(),
            EmailOtp.is_used.is_(False),
            EmailOtp.expires_at > datetime.now(timezone.utc),
        )
        if purpose:
            query = query.where(EmailOtp.purpose == purpose)
        elif purposes:
            query = query.where(EmailOtp.purpose.in_(purposes))
        return db.session.execute(
            query.order_by(EmailOtp.created_at.desc()).limit(1)
        ).scalar_one_or_none()

    def find_verified_password_reset_otp(self, email: str) -> EmailOtp | None:
        return db.session.execute(
            db.select(EmailOtp).where(
                EmailOtp.email == email.lower().strip(),
                EmailOtp.purpose == EmailOtpPurpose.RESET_PASSWORD.value,
                EmailOtp.is_used.is_(False),
                EmailOtp.verified_at.isnot(None),
                EmailOtp.expires_at > datetime.now(timezone.utc),
            ).order_by(EmailOtp.verified_at.desc()).limit(1)
        ).scalar_one_or_none()

    def invalidate_active_for_email(self, email: str) -> None:
        rows = db.session.execute(
            db.select(EmailOtp).where(
                EmailOtp.email == email.lower().strip(),
                EmailOtp.is_used.is_(False),
            )
        ).scalars().all()
        now = datetime.now(timezone.utc)
        for row in rows:
            row.is_used = True
            row.used_at = now

    def count_sent_since(self, email: str, since: datetime) -> int:
        return (
            db.session.execute(
                db.select(db.func.count(EmailOtp.id)).where(
                    EmailOtp.email == email.lower().strip(),
                    EmailOtp.created_at >= since,
                )
            ).scalar()
            or 0
        )

    def latest_created_at(self, email: str) -> datetime | None:
        return db.session.execute(
            db.select(EmailOtp.created_at)
            .where(EmailOtp.email == email.lower().strip())
            .order_by(EmailOtp.created_at.desc())
            .limit(1)
        ).scalar_one_or_none()


class RegistrationIntentRepository(BaseRepository):
    def find_active_by_email(self, email: str) -> RegistrationIntent | None:
        """Pre-OTP intent only (not yet linked to a user)."""
        now = datetime.now(timezone.utc)
        return db.session.execute(
            db.select(RegistrationIntent).where(
                RegistrationIntent.email == email.lower().strip(),
                RegistrationIntent.user_id.is_(None),
                RegistrationIntent.consumed_at.is_(None),
                RegistrationIntent.expires_at > now,
            )
        ).scalar_one_or_none()

    def find_by_email(self, email: str) -> RegistrationIntent | None:
        return db.session.execute(
            db.select(RegistrationIntent).where(
                RegistrationIntent.email == email.lower().strip()
            )
        ).scalar_one_or_none()

    def find_pending_institution_by_user_id(
        self, user_id: int
    ) -> RegistrationIntent | None:
        return db.session.execute(
            db.select(RegistrationIntent).where(
                RegistrationIntent.user_id == user_id,
                RegistrationIntent.workspace_kind == WorkspaceKind.INSTITUTION.value,
                RegistrationIntent.approval_status
                == InstitutionApprovalStatus.PENDING.value,
                RegistrationIntent.consumed_at.is_(None),
            )
        ).scalar_one_or_none()

    def find_institution_by_user_id(
        self, user_id: int
    ) -> RegistrationIntent | None:
        return db.session.execute(
            db.select(RegistrationIntent).where(
                RegistrationIntent.user_id == user_id,
                RegistrationIntent.workspace_kind == WorkspaceKind.INSTITUTION.value,
            )
        ).scalar_one_or_none()

    def list_pending_institutions(self) -> list[RegistrationIntent]:
        return list(
            db.session.execute(
                db.select(RegistrationIntent)
                .where(
                    RegistrationIntent.workspace_kind
                    == WorkspaceKind.INSTITUTION.value,
                    RegistrationIntent.approval_status
                    == InstitutionApprovalStatus.PENDING.value,
                    RegistrationIntent.consumed_at.is_(None),
                )
                .order_by(RegistrationIntent.created_at.desc())
            ).scalars().all()
        )
