"""
Authentication business logic.

Onboarding flows:
1. Owner registration: user + workspace + ADMIN membership + owner_membership_id
2. Student + join code: user + STUDENT membership (no workspace creation)
3. Existing user join: membership only (invite or join code)

Super admin: platform operator, no workspace required, is_superadmin=True.
"""
import re
from datetime import datetime, timedelta, timezone

from flask import current_app

from models import (
    EmailVerificationToken,
    Membership,
    PasswordResetCode,
    User,
    Workspace,
)
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
from service.session_service import SessionService
from utils.db import db
from utils.enums import InviteStatus, MembershipRole, UserStatus, WorkspaceKind
from utils.join_code import generate_workspace_join_code
from utils.security import generate_invite_token, hash_password, hash_token, verify_password


def _slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return slug[:100] or "workspace"


class AuthService:
    def __init__(self):
        self.users = UserRepository()
        self.workspaces = WorkspaceRepository()
        self.memberships = MembershipRepository()
        self.sessions = SessionService()

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
    ) -> dict:
        """
        Purpose: Institution/SOLO owner onboarding.
        Side effects: user, workspace, membership, join_code, optional verification token.
        """
        email = email.lower().strip()
        if self.users.find_by_email(email):
            raise ConflictError("Email is already registered")

        if workspace_kind not in (WorkspaceKind.SOLO.value, WorkspaceKind.INSTITUTION.value):
            raise ValidationError("Invalid workspace kind")

        slug = slug or _slugify(workspace_name)
        if self.workspaces.find_by_slug(slug):
            raise ConflictError("Workspace slug already exists")

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

        workspace = Workspace(
            name=workspace_name,
            slug=slug,
            kind=workspace_kind,
            owner_user_id=user.id,
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

        raw_token, _ = self.create_email_verification_token(user)
        db.session.commit()

        email_sent = self._send_verification_email(user, raw_token)

        result = {
            "user_id": user.id,
            "workspace_id": workspace.id,
            "membership_id": membership.id,
            "requires_email_verification": True,
            "email_sent": email_sent,
        }
        if not email_sent and current_app.config.get("DEBUG"):
            result["dev_verification_token"] = raw_token
        return result

    def register_student_with_join_code(
        self,
        *,
        email: str,
        password: str,
        full_name: str,
        join_code: str,
        phone_number: str | None = None,
    ) -> dict:
        """
        Purpose: New student account + STUDENT membership via permanent workspace join code.
        Must NOT: create a workspace.
        """
        workspace = self.workspaces.find_by_join_code(join_code)
        if not workspace:
            raise NotFoundError("Invalid join code")

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

        raw_token, _ = self.create_email_verification_token(user)
        db.session.commit()

        email_sent = self._send_verification_email(user, raw_token)

        result = {
            "user_id": user.id,
            "workspace_id": workspace.id,
            "membership_id": membership.id,
            "requires_email_verification": True,
            "email_sent": email_sent,
        }
        if not email_sent and current_app.config.get("DEBUG"):
            result["dev_verification_token"] = raw_token
        return result

    # ── Login / logout ───────────────────────────────────────────

    def login(
        self,
        *,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict:
        """
        Purpose: Authenticate any user (including super admin).
        Must NOT: create memberships or modify workspace context in JWT.
        """
        email = email.lower().strip()
        user = self.users.find_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid email or password")

        if user.user_status == UserStatus.DISABLED.value:
            raise ForbiddenError("Account is disabled")
        if user.user_status == UserStatus.SUSPENDED.value:
            raise ForbiddenError("Account is suspended")

        return self._issue_auth_response(user, ip_address=ip_address, user_agent=user_agent)

    def login_superadmin(
        self,
        *,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> dict:
        """
        Purpose: Dedicated super-admin login (must have is_superadmin=True).
        """
        email = email.lower().strip()
        user = self.users.find_superadmin_by_email(email)
        if not user or not verify_password(password, user.password_hash):
            raise UnauthorizedError("Invalid super admin credentials")

        return self._issue_auth_response(user, ip_address=ip_address, user_agent=user_agent)

    def logout(self, jti: str) -> None:
        """Deactivate single session by access token jti."""
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
        db.session.commit()
        return {
            "access_token": access,
            "refresh_token": refresh,
            "token_type": "Bearer",
            "user": self._serialize_user(user),
        }

    # ── Email verification ─────────────────────────────────────

    def create_email_verification_token(self, user: User) -> tuple[str, EmailVerificationToken]:
        raw = generate_invite_token()
        token = EmailVerificationToken(
            user_id=user.id,
            token_hash=hash_token(raw),
            email=user.email,
            expires_at=datetime.now(timezone.utc)
            + timedelta(hours=current_app.config.get("EMAIL_VERIFICATION_EXPIRES_HOURS", 48)),
        )
        self.users.add(token)
        return raw, token

    def verify_email(self, raw_token: str) -> User:
        """
        Purpose: Mark email verified.
        Must NOT: create sessions automatically.
        """
        token_row = db.session.execute(
            db.select(EmailVerificationToken).where(
                EmailVerificationToken.token_hash == hash_token(raw_token)
            )
        ).scalar_one_or_none()
        if not token_row or token_row.is_used:
            raise ValidationError("Invalid verification token")
        if token_row.expires_at < datetime.now(timezone.utc):
            raise ValidationError("Verification token has expired")

        user = self.users.get_by_id(token_row.user_id)
        if not user:
            raise NotFoundError("User not found")

        user.email_verified = True
        if user.user_status == UserStatus.PENDING_VERIFICATION.value:
            user.user_status = UserStatus.ACTIVE.value
        token_row.is_used = True
        token_row.used_at = datetime.now(timezone.utc)
        db.session.commit()
        return user

    def resend_verification(self, email: str) -> dict:
        user = self.users.find_by_email(email)
        if not user:
            return {"message": "If the account exists, a verification email was sent", "email_sent": False}
        if user.email_verified:
            raise ValidationError("Email is already verified")
        raw, _ = self.create_email_verification_token(user)
        db.session.commit()
        email_sent = self._send_verification_email(user, raw)
        out = {"message": "If the account exists, a verification email was sent", "email_sent": email_sent}
        if not email_sent and current_app.config.get("DEBUG"):
            out["dev_verification_token"] = raw
        return out

    # ── Password reset ─────────────────────────────────────────

    def forgot_password(self, email: str) -> str | None:
        """
        Purpose: Start password reset.
        Must NOT: change password or create sessions.
        """
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
        """
        Purpose: Complete password reset.
        Side effects: password update, revoke all sessions, invalidate token.
        """
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
                    },
                }
            )
        return result

    def _send_verification_email(self, user: User, raw_token: str) -> bool:
        try:
            EmailDeliveryService().send_verification_email(
                to_email=user.email,
                full_name=user.full_name,
                raw_token=raw_token,
            )
            return True
        except EmailDeliveryError as exc:
            current_app.logger.error("Failed to send verification email: %s", exc)
            return False

    def _unique_join_code(self) -> str:
        for _ in range(10):
            code = generate_workspace_join_code()
            if not self.workspaces.find_by_join_code(code):
                return code
        raise ConflictError("Could not generate unique join code")
