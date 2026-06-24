"""
Invitation onboarding (separate from join-code flow).

Read:  GET /invites/{token} — no DB writes.
Write: POST /invites/{token}/register — new user + membership.
       POST /invites/{token}/accept — existing user + membership.
       POST /invites/{token}/reject — mark rejected.
"""
from datetime import datetime, timedelta, timezone

from flask import current_app

from models import Membership, User, WorkspaceInvite
from repositories.invite_repository import InviteRepository
from repositories.user_repository import UserRepository
from repositories.workspace_repository import MembershipRepository, WorkspaceRepository
from service.auth_service import AuthService
from service.email_delivery_service import EmailDeliveryError, EmailDeliveryService
from service.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from utils.db import db
from utils.enums import InviteStatus, MembershipRole, UserStatus, WorkspaceKind
from utils.rbac import can_invite_with_role
from utils.security import generate_invite_token, hash_password, hash_token


class InviteService:
    def __init__(self):
        self.invites = InviteRepository()
        self.users = UserRepository()
        self.memberships = MembershipRepository()
        self.workspaces = WorkspaceRepository()

    def create_invite(
        self,
        *,
        workspace_id: int,
        email: str,
        assigned_role: str,
        invited_by_membership_id: int | None,
        inviter_role: str | None,
        is_superadmin: bool = False,
    ) -> tuple[WorkspaceInvite, str, bool]:
        """
        Purpose: Create pending invitation.
        Must NOT: create membership or user.
        """
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found")

        if not can_invite_with_role(
            inviter_role, assigned_role, is_superadmin=is_superadmin
        ):
            if inviter_role == MembershipRole.TEACHER.value:
                raise ForbiddenError("Teachers can only invite students")
            if inviter_role == MembershipRole.STUDENT.value:
                raise ForbiddenError("Students cannot send invitations")
            raise ForbiddenError("Insufficient permissions to invite this role")

        if workspace.kind == WorkspaceKind.SOLO.value:
            if assigned_role != MembershipRole.STUDENT.value:
                raise ForbiddenError(
                    "SOLO workspaces can only invite students (owner is the teacher)"
                )

        if assigned_role not in (
            MembershipRole.ADMIN.value,
            MembershipRole.TEACHER.value,
            MembershipRole.STUDENT.value,
        ):
            raise ValidationError("Invalid role for invitation")

        email = email.lower().strip()
        existing = self.invites.find_pending_by_email(workspace_id, email)
        if existing:
            if current_app.config.get("DEBUG"):
                raw = generate_invite_token()
                existing.token_hash = hash_token(raw)
                existing.assigned_role = assigned_role
                existing.invited_by_membership_id = invited_by_membership_id
                existing.expires_at = datetime.now(timezone.utc) + timedelta(
                    days=current_app.config.get("INVITE_TOKEN_EXPIRES_DAYS", 7)
                )
                db.session.commit()
                from utils.dev_invite import log_dev_invite_token

                log_dev_invite_token(
                    email=email, raw_token=raw, workspace_id=workspace_id
                )
                email_sent = self._send_invite_email(
                    workspace=workspace,
                    email=email,
                    assigned_role=assigned_role,
                    raw_token=raw,
                )
                return existing, raw, email_sent
            raise ConflictError("Pending invite already exists for this email")

        raw = generate_invite_token()
        invite = WorkspaceInvite(
            workspace_id=workspace_id,
            email=email,
            assigned_role=assigned_role,
            token_hash=hash_token(raw),
            invited_by_membership_id=invited_by_membership_id,
            status=InviteStatus.PENDING.value,
            expires_at=datetime.now(timezone.utc)
            + timedelta(days=current_app.config.get("INVITE_TOKEN_EXPIRES_DAYS", 7)),
        )
        self.invites.add(invite)
        db.session.commit()

        from utils.dev_invite import log_dev_invite_token

        log_dev_invite_token(email=email, raw_token=raw, workspace_id=workspace_id)

        email_sent = self._send_invite_email(
            workspace=workspace,
            email=email,
            assigned_role=assigned_role,
            raw_token=raw,
        )
        return invite, raw, email_sent

    def preview_invite(self, raw_token: str) -> dict:
        """
        Purpose: Read-only invitation preview.
        Must NOT: mutate database state.
        """
        invite = self._find_by_raw_token(raw_token)
        if not invite:
            raise NotFoundError("Invitation not found")

        workspace = self.workspaces.get_by_id(invite.workspace_id)
        now = datetime.now(timezone.utc)
        display_status = invite.status
        if (
            invite.status == InviteStatus.PENDING.value
            and invite.revoked_at is None
            and invite.expires_at < now
        ):
            display_status = InviteStatus.EXPIRED.value

        return {
            "invited_email": invite.invited_email,
            "assigned_role": invite.assigned_role,
            "workspace_id": invite.workspace_id,
            "workspace_name": workspace.name if workspace else None,
            "workspace_kind": workspace.kind if workspace else None,
            "expires_at": invite.expires_at.isoformat(),
            "status": display_status,
            "is_revoked": invite.revoked_at is not None,
        }

    def register_through_invite(
        self, raw_token: str, *, full_name: str, password: str
    ) -> dict:
        """
        Purpose: New user account + membership from invitation email.
        Email comes from invitation only — not from request body.
        """
        invite = self._get_valid_pending_invite(raw_token, mutate=True)

        if self.users.find_by_email(invite.email):
            raise ConflictError("Account already exists. Please login first.")

        user = User(
            email=invite.email,
            password_hash=hash_password(password),
            full_name=full_name,
            user_status=UserStatus.PENDING_VERIFICATION.value,
            email_verified=False,
        )
        self.users.add(user)
        db.session.flush()

        membership = Membership(
            user_id=user.id,
            workspace_id=invite.workspace_id,
            role=invite.assigned_role,
            status="ACTIVE",
        )
        self.memberships.add(membership)

        now = datetime.now(timezone.utc)
        invite.status = InviteStatus.ACCEPTED.value
        invite.accepted_at = now

        auth = AuthService()
        raw_otp, email_sent = auth.send_account_verification_otp(user)
        db.session.commit()

        result = {
            "message": "Registration successful. Check your email for the verification code.",
            "user_id": user.id,
            "workspace_id": invite.workspace_id,
            "membership_id": membership.id,
            "invited_email": invite.invited_email,
            "requires_otp_verification": True,
            "email_sent": email_sent,
        }
        from utils.dev_otp import attach_dev_otp

        return attach_dev_otp(result, raw_otp, email=user.email)

    def accept_invite(self, raw_token: str, user_id: int) -> Membership:
        """
        Purpose: Existing authenticated user joins via invitation.
        Must NOT: create users.
        """
        invite = self._get_valid_pending_invite(raw_token, mutate=True)
        user = self.users.get_by_id(user_id)
        if not user or user.email.lower() != invite.email.lower():
            raise ForbiddenError("Invite email does not match authenticated user")

        existing = self.memberships.find_by_user_and_workspace(
            user_id, invite.workspace_id
        )
        if existing:
            raise ConflictError("Already a member of this workspace")

        membership = Membership(
            user_id=user_id,
            workspace_id=invite.workspace_id,
            role=invite.assigned_role,
            status="ACTIVE",
        )
        self.memberships.add(membership)
        invite.status = InviteStatus.ACCEPTED.value
        invite.accepted_at = datetime.now(timezone.utc)
        db.session.commit()
        return membership

    def reject_invite(self, raw_token: str) -> None:
        invite = self._find_by_raw_token(raw_token)
        if not invite:
            raise NotFoundError("Invitation not found")
        if invite.status != InviteStatus.PENDING.value:
            raise ValidationError("Invitation is no longer valid")
        if invite.revoked_at is not None:
            raise ValidationError("Invitation has been revoked")

        invite.status = InviteStatus.REJECTED.value
        invite.rejected_at = datetime.now(timezone.utc)
        db.session.commit()

    def revoke_pending_invite(
        self, *, workspace_id: int, email: str, actor_membership_id: int | None
    ) -> None:
        """Admin cancel: mark pending invite revoked (soft)."""
        invite = self.invites.find_pending_by_email(workspace_id, email.lower().strip())
        if not invite:
            raise NotFoundError("Pending invitation not found")
        invite.revoked_at = datetime.now(timezone.utc)
        invite.status = InviteStatus.EXPIRED.value
        db.session.commit()

    def _send_invite_email(
        self,
        *,
        workspace,
        email: str,
        assigned_role: str,
        raw_token: str,
    ) -> bool:
        try:
            EmailDeliveryService().send_workspace_invite_email(
                to_email=email,
                workspace_name=workspace.name,
                assigned_role=assigned_role,
                raw_token=raw_token,
            )
            return True
        except EmailDeliveryError as exc:
            current_app.logger.error(
                "Failed to send invite email to %s: %s (use dev_token / frontend URLs in DEBUG)",
                email,
                exc,
            )
            return False

    def _find_by_raw_token(self, raw_token: str) -> WorkspaceInvite | None:
        return self.invites.find_by_token_hash(hash_token(raw_token))

    def _get_valid_pending_invite(self, raw_token: str, *, mutate: bool) -> WorkspaceInvite:
        invite = self._find_by_raw_token(raw_token)
        if not invite:
            raise NotFoundError("Invitation not found")

        now = datetime.now(timezone.utc)
        if invite.revoked_at is not None:
            raise ValidationError("Invitation has been revoked")
        if invite.status == InviteStatus.REJECTED.value:
            raise ValidationError("Invitation was rejected")
        if invite.status == InviteStatus.ACCEPTED.value:
            raise ValidationError("Invitation has already been accepted")
        if invite.status != InviteStatus.PENDING.value:
            raise ValidationError("Invitation is no longer valid")
        if invite.expires_at < now:
            if mutate:
                invite.status = InviteStatus.EXPIRED.value
                db.session.commit()
            raise ValidationError("Invitation has expired")
        return invite

