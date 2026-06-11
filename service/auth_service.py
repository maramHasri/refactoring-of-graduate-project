"""
Authentication business logic.

Owner registration: intent + OTP → verify → create user/workspace.
Student/invite: user pending → OTP → activate account.
"""
import re
from datetime import datetime, timedelta, timezone

from flask import current_app

from models import (
    Membership,
    PasswordResetCode,
    RegistrationIntent,
    User,
    Workspace,
    WorkspaceProfile,
)
from repositories.otp_repository import RegistrationIntentRepository
from repositories.user_repository import UserRepository
from repositories.workspace_repository import MembershipRepository, WorkspaceRepository
from service.exceptions import (
    ConflictError,
    ForbiddenError,
    NotFoundError,
    UnauthorizedError,
    ValidationError,
)
from service.email_delivery_service import EmailDeliveryError, EmailDeliveryService
from service.otp_service import OtpService
from service.session_service import SessionService
from utils.db import db
from utils.enums import (
    EmailOtpPurpose,
    InstitutionApprovalStatus,
    MembershipRole,
    UserStatus,
    WorkspaceKind,
    WorkspaceStatus,
)
from utils.dev_otp import attach_dev_otp
from utils.join_code import generate_workspace_join_code
from utils.security import (
    generate_invite_token,
    hash_password,
    hash_token,
    verify_password,
)


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:100] or "workspace"


class AuthService:
    def __init__(self):
        self.users = UserRepository()
        self.workspaces = WorkspaceRepository()
        self.memberships = MembershipRepository()
        self.sessions = SessionService()
        self.otps = OtpService()
        self.registration_intents = RegistrationIntentRepository()

    # ── Registration ─────────────────────────────────────────────

    def register_workspace_owner(
        self,
        *,
        email: str,
        password: str,
        full_name: str,
        workspace_name: str,
        workspace_kind: str,
        slug: str | None = None,
        phone_number: str | None = None,
        country: str | None = None,
        city: str | None = None,
        website_url: str | None = None,
        description: str | None = None,
    ) -> dict:
        """
        Step 1–2: Store registration intent and send email OTP.
        User/workspace are created only after POST /auth/verify-otp succeeds.
        """
        email = email.lower().strip()
        existing_user = self.users.find_by_email(email)
        if existing_user:
            if existing_user.email_verified:
                raise ConflictError("Email is already registered")
            # Legacy or incomplete signup — resend OTP instead of blocking with 409
            plain_otp = self.otps.issue_otp(
                email=email,
                purpose=EmailOtpPurpose.VERIFY_ACCOUNT.value,
                user_id=existing_user.id,
            )
            db.session.commit()
            email_sent = self._send_otp_email(email, existing_user.full_name, plain_otp)
            result = {
                "requires_otp_verification": True,
                "email_sent": email_sent,
                "workspace_kind": workspace_kind,
                "resent_otp_for_existing_user": True,
            }
            return attach_dev_otp(result, plain_otp, email=email)

        if workspace_kind not in (WorkspaceKind.SOLO.value, WorkspaceKind.INSTITUTION.value):
            raise ValidationError("Invalid workspace kind")

        slug = slug or _slugify(workspace_name)
        if self.workspaces.find_by_slug(slug):
            raise ConflictError("Workspace slug already exists")

        existing_intent = self.registration_intents.find_by_email(email)
        if existing_intent:
            db.session.delete(existing_intent)
            db.session.flush()

        intent = RegistrationIntent(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name.strip(),
            phone_number=phone_number,
            workspace_name=workspace_name.strip(),
            slug=slug,
            workspace_kind=workspace_kind,
            country=country,
            city=city,
            website_url=website_url,
            description=description,
            expires_at=datetime.now(timezone.utc)
            + timedelta(hours=current_app.config.get("REGISTRATION_INTENT_EXPIRES_HOURS", 48)),
        )
        self.registration_intents.add(intent)

        plain_otp = self.otps.issue_otp(
            email=email,
            purpose=EmailOtpPurpose.REGISTER_OWNER.value,
        )
        db.session.commit()

        email_sent = self._send_otp_email(email, full_name, plain_otp)
        result = {
            "requires_otp_verification": True,
            "email_sent": email_sent,
            "workspace_kind": workspace_kind,
        }
        return attach_dev_otp(result, plain_otp, email=email)

    def register_student_with_join_code(
        self,
        *,
        email: str,
        password: str,
        full_name: str,
        join_code: str,
        phone_number: str | None = None,
    ) -> dict:
        workspace = self.workspaces.find_by_join_code(join_code)
        if not workspace:
            raise NotFoundError("Invalid join code")
        self._ensure_workspace_allows_member_join(workspace)

        email = email.lower().strip()
        if self.users.find_by_email(email):
            raise ConflictError("Email is already registered")

        user = User(
            email=email,
            password_hash=hash_password(password),
            full_name=full_name,
            phone_number=phone_number,
            user_status=UserStatus.PENDING_VERIFICATION.value,
            email_verified=False,
        )
        self.users.add(user)
        db.session.flush()

        membership = Membership(
            user_id=user.id,
            workspace_id=workspace.id,
            role=MembershipRole.STUDENT.value,
            status="ACTIVE",
        )
        self.memberships.add(membership)

        plain_otp = self.otps.issue_otp(
            email=email,
            purpose=EmailOtpPurpose.VERIFY_ACCOUNT.value,
            user_id=user.id,
        )
        db.session.commit()

        email_sent = self._send_otp_email(email, full_name, plain_otp)
        result = {
            "user_id": user.id,
            "workspace_id": workspace.id,
            "membership_id": membership.id,
            "requires_otp_verification": True,
            "email_sent": email_sent,
        }
        return attach_dev_otp(result, plain_otp, email=email)

    def send_account_verification_otp(self, user: User) -> tuple[str, bool]:
        """Issue OTP for an existing pending user (invite / resend flows)."""
        plain_otp = self.otps.issue_otp(
            email=user.email,
            purpose=EmailOtpPurpose.VERIFY_ACCOUNT.value,
            user_id=user.id,
        )
        email_sent = self._send_otp_email(user.email, user.full_name, plain_otp)
        return plain_otp, email_sent

    # ── OTP verification ─────────────────────────────────────────

    def verify_otp(self, *, email: str, otp: str) -> dict:
        email = email.lower().strip()
        self.otps.verify_otp(email=email, otp=otp)

        intent = self.registration_intents.find_active_by_email(email)
        if intent:
            return self._complete_owner_registration(intent)

        user = self.users.find_by_email(email)
        if not user:
            raise ValidationError("No registration found for this email")

        user.email_verified = True
        if user.user_status == UserStatus.PENDING_VERIFICATION.value:
            user.user_status = UserStatus.ACTIVE.value
        db.session.commit()
        return {"success": True, "email_verified": True}

    def resend_otp(self, email: str) -> dict:
        email = email.lower().strip()
        intent = self.registration_intents.find_active_by_email(email)
        if intent:
            plain = self.otps.issue_otp(
                email=email,
                purpose=EmailOtpPurpose.REGISTER_OWNER.value,
            )
            db.session.commit()
            email_sent = self._send_otp_email(email, intent.full_name, plain)
            out = {"success": True, "email_sent": email_sent}
            return attach_dev_otp(out, plain, email=email)

        user = self.users.find_by_email(email)
        if not user:
            raise ValidationError(
                "No account or pending registration found for this email. "
                "Use POST /auth/register first."
            )
        if user.email_verified:
            raise ValidationError("Email is already verified")

        plain, email_sent = self.send_account_verification_otp(user)
        db.session.commit()
        out = {"success": True, "email_sent": email_sent}
        return attach_dev_otp(out, plain, email=email)

    def _complete_owner_registration(self, intent: RegistrationIntent) -> dict:
        if intent.workspace_kind == WorkspaceKind.INSTITUTION.value:
            return self._complete_institution_pending_registration(intent)
        return self._complete_solo_owner_registration(intent)

    def _complete_institution_pending_registration(
        self, intent: RegistrationIntent
    ) -> dict:
        """
        INSTITUTION: create user only; workspace is created on super admin approve.
        """
        if self.users.find_by_email(intent.email):
            raise ConflictError("Email is already registered")

        user = User(
            email=intent.email,
            password_hash=intent.password_hash,
            full_name=intent.full_name,
            phone_number=intent.phone_number,
            user_status=UserStatus.PENDING_APPROVAL.value,
            email_verified=True,
        )
        self.users.add(user)
        db.session.flush()

        intent.user_id = user.id
        intent.approval_status = InstitutionApprovalStatus.PENDING.value
        db.session.commit()

        self._send_institution_pending_review_email(user, intent.workspace_name)

        return {
            "success": True,
            "user_id": user.id,
            "user_status": user.user_status,
            "workspace_kind": intent.workspace_kind,
            "requires_admin_approval": True,
            "message": (
                "Institution registration submitted. "
                "Your request is under review by platform administration."
            ),
        }

    def _complete_solo_owner_registration(self, intent: RegistrationIntent) -> dict:
        if self.users.find_by_email(intent.email):
            raise ConflictError("Email is already registered")
        if self.workspaces.find_by_slug(intent.slug):
            raise ConflictError("Workspace slug already exists")

        user = User(
            email=intent.email,
            password_hash=intent.password_hash,
            full_name=intent.full_name,
            phone_number=intent.phone_number,
            user_status=UserStatus.ACTIVE.value,
            email_verified=True,
        )
        self.users.add(user)
        db.session.flush()

        workspace = Workspace(
            name=intent.workspace_name,
            slug=intent.slug,
            kind=intent.workspace_kind,
            owner_user_id=user.id,
            status=WorkspaceStatus.ACTIVE.value,
            join_code=self._unique_join_code(),
        )
        self.workspaces.add(workspace)
        db.session.flush()

        membership = Membership(
            user_id=user.id,
            workspace_id=workspace.id,
            role=MembershipRole.ADMIN.value,
            status="ACTIVE",
        )
        self.memberships.add(membership)
        db.session.flush()
        workspace.owner_membership_id = membership.id

        if any(
            [
                intent.country,
                intent.city,
                intent.website_url,
                intent.description,
            ]
        ):
            profile = WorkspaceProfile(
                workspace_id=workspace.id,
                country=intent.country,
                city=intent.city,
                website_url=intent.website_url,
                description=intent.description,
            )
            self.workspaces.add(profile)

        intent.consumed_at = datetime.now(timezone.utc)
        db.session.commit()

        return {
            "success": True,
            "user_id": user.id,
            "workspace_id": workspace.id,
            "membership_id": membership.id,
            "workspace_kind": workspace.kind,
            "workspace_status": workspace.status,
            "requires_admin_approval": False,
        }

    # ── Login / logout ───────────────────────────────────────────

    def login(
        self,
        *,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict:
        email = email.lower().strip()
        user = self.users.find_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid email or password")

        if user.user_status == UserStatus.DISABLED.value:
            raise ForbiddenError("Account is disabled")
        if user.user_status == UserStatus.SUSPENDED.value:
            raise ForbiddenError("Account is suspended")
        if not user.email_verified:
            raise ForbiddenError(
                "Email not verified. Enter the OTP sent to your email via POST /auth/verify-otp"
            )

        self._enforce_institution_login_rules(user)

        return self._issue_auth_response(user, ip_address=ip_address, user_agent=user_agent)

    def login_superadmin(
        self,
        *,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict:
        email = email.lower().strip()
        user = self.users.find_superadmin_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid super admin credentials")

        return self._issue_auth_response(user, ip_address=ip_address, user_agent=user_agent)

    def logout(self, jti: str) -> None:
        session = self.sessions.repo.find_active_by_jti(jti)
        if session:
            self.sessions.repo.deactivate(session)
            db.session.commit()

    def logout_all(self, user_id: int) -> int:
        count = self.sessions.repo.deactivate_all_for_user(user_id)
        db.session.commit()
        return count

    def refresh_tokens(self, refresh_token: str) -> dict:
        access, refresh, session = self.sessions.refresh_session(refresh_token)
        user = self.users.get_by_id(session.user_id)
        if not user.is_superadmin:
            if not user.email_verified:
                raise ForbiddenError("Email not verified")
            self._enforce_institution_login_rules(user)
        db.session.commit()
        return {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "Bearer",
            "user": self._serialize_user(user),
        }

    # ── Password reset ─────────────────────────────────────────

    def forgot_password(self, email: str) -> str | None:
        user = self.users.find_by_email(email.lower().strip())
        if not user:
            return None
        raw = generate_invite_token()
        row = PasswordResetCode(
            user_id=user.id,
            reset_code_hash=hash_token(raw),
            expires_at=datetime.now(timezone.utc)
            + timedelta(hours=current_app.config.get("PASSWORD_RESET_EXPIRES_HOURS", 24)),
        )
        self.users.add(row)
        db.session.commit()
        try:
            EmailDeliveryService().send_password_reset_email(
                to_email=user.email,
                full_name=user.full_name,
                raw_token=raw,
            )
        except EmailDeliveryError:
            if current_app.config.get("DEBUG"):
                return raw
        return raw

    def reset_password(self, raw_token: str, new_password: str) -> None:
        row = db.session.execute(
            db.select(PasswordResetCode).where(
                PasswordResetCode.reset_code_hash == hash_token(raw_token),
                PasswordResetCode.is_used.is_(False),
            )
        ).scalar_one_or_none()
        if not row or row.expires_at < datetime.now(timezone.utc):
            raise ValidationError("Invalid or expired reset token")

        user = self.users.get_by_id(row.user_id)
        if not user:
            raise NotFoundError("User not found")

        user.password_hash = hash_password(new_password)
        row.is_used = True
        self.sessions.repo.deactivate_all_for_user(user.id)
        db.session.commit()

    def change_password(self, user_id: int, current_password: str, new_password: str) -> None:
        user = self.users.get_by_id(user_id)
        if not user or not verify_password(current_password, user.password_hash):
            raise UnauthorizedError("Current password is incorrect")
        user.password_hash = hash_password(new_password)
        db.session.commit()

    # ── Helpers ──────────────────────────────────────────────────

    def _enforce_institution_login_rules(self, user: User) -> None:
        if user.user_status == UserStatus.PENDING_APPROVAL.value:
            raise ForbiddenError(
                "Your institution registration request is currently under review. "
                "You will receive an email once it has been approved."
            )
        if user.user_status == UserStatus.REGISTRATION_REJECTED.value:
            intent = self.registration_intents.find_institution_by_user_id(user.id)
            reason = (
                intent.rejection_reason if intent and intent.rejection_reason
                else "No reason provided."
            )
            raise ForbiddenError(
                f"Your institution registration was rejected. Reason: {reason}"
            )

        # Legacy rows: institution workspace created before user-based approval flow
        owned = db.session.execute(
            db.select(Workspace).where(
                Workspace.owner_user_id == user.id,
                Workspace.kind == WorkspaceKind.INSTITUTION.value,
            )
        ).scalars().all()
        for workspace in owned:
            if workspace.status == WorkspaceStatus.PENDING_APPROVAL.value:
                raise ForbiddenError(
                    "Your institution registration request is currently under review. "
                    "You will receive an email once it has been approved."
                )
            if workspace.status == WorkspaceStatus.REJECTED.value:
                reason = workspace.rejection_reason or "No reason provided."
                raise ForbiddenError(
                    f"Your institution registration was rejected. Reason: {reason}"
                )

    def _ensure_workspace_allows_member_join(self, workspace: Workspace) -> None:
        if workspace.status == WorkspaceStatus.PENDING_APPROVAL.value:
            raise ForbiddenError("This institution is not yet approved for members")
        if workspace.status == WorkspaceStatus.REJECTED.value:
            raise ForbiddenError("This institution registration was rejected")
        if workspace.status in (
            WorkspaceStatus.SUSPENDED.value,
            WorkspaceStatus.ARCHIVED.value,
        ):
            raise ForbiddenError("This workspace is not accepting new members")

    def _issue_auth_response(
        self,
        user: User,
        *,
        ip_address: str | None,
        user_agent: str | None,
    ) -> dict:
        user.last_login_at = datetime.now(timezone.utc)
        access, refresh, _session = self.sessions.create_user_session(
            user.id,
            is_superadmin=user.is_superadmin,
            ip_address=ip_address,
            user_agent=user_agent,
        )
        db.session.commit()

        memberships = []
        if not user.is_superadmin:
            memberships = self._serialize_memberships(user.id)

        return {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "Bearer",
            "user": self._serialize_user(user),
            "memberships": memberships,
            "has_memberships": len(memberships) > 0,
            "requires_workspace_selection": len(memberships) > 1,
            "requires_onboarding": len(memberships) == 0 and not user.is_superadmin,
        }

    def _serialize_user(self, user: User) -> dict:
        return {
            "id": user.id,
            "email": user.email,
            "full_name": user.full_name,
            "avatar_url": user.avatar_url,
            "phone_number": user.phone_number,
            "user_status": user.user_status,
            "email_verified": user.email_verified,
            "is_superadmin": user.is_superadmin,
        }

    def _serialize_memberships(self, user_id: int) -> list[dict]:
        rows = db.session.execute(
            db.select(Membership, Workspace)
            .join(Workspace, Workspace.id == Membership.workspace_id)
            .where(Membership.user_id == user_id, Membership.status == "ACTIVE")
        ).all()
        result = []
        for membership, workspace in rows:
            is_owner = workspace.owner_membership_id == membership.id
            result.append(
                {
                    "membership_id": membership.id,
                    "role": membership.role,
                    "is_owner": is_owner,
                    "workspace": {
                        "id": workspace.id,
                        "name": workspace.name,
                        "slug": workspace.slug,
                        "kind": workspace.kind,
                        "status": workspace.status,
                    },
                }
            )
        return result

    def _send_otp_email(self, email: str, full_name: str, plain_otp: str) -> bool:
        try:
            EmailDeliveryService().send_otp_email(
                to_email=email,
                full_name=full_name,
                otp_code=plain_otp,
            )
            current_app.logger.info("OTP email sent to %s", email)
            return True
        except EmailDeliveryError as exc:
            current_app.logger.error(
                "Failed to send OTP email to %s: %s (use dev_otp in DEBUG response)",
                email,
                exc,
            )
            return False

    def _send_institution_pending_review_email(
        self, user: User, institution_name: str
    ) -> None:
        try:
            EmailDeliveryService().send_institution_pending_review_email(
                to_email=user.email,
                full_name=user.full_name,
                institution_name=institution_name,
            )
        except EmailDeliveryError as exc:
            current_app.logger.error("Failed to send institution pending email: %s", exc)

    def _unique_join_code(self) -> str:
        for _ in range(10):
            code = generate_workspace_join_code()
            if not self.workspaces.find_by_join_code(code):
                return code
        raise ConflictError("Could not generate unique join code")
