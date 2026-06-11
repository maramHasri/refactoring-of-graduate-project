"""
Super admin — institution registration approval by owner user_id.
Workspace is created only when the request is approved.
"""
from datetime import datetime, timezone

from models import Membership, RegistrationIntent, User, Workspace, WorkspaceProfile
from repositories.otp_repository import RegistrationIntentRepository
from repositories.user_repository import UserRepository
from repositories.workspace_repository import MembershipRepository, WorkspaceRepository
from service.email_delivery_service import EmailDeliveryError, EmailDeliveryService
from service.exceptions import ConflictError, NotFoundError, ValidationError
from utils.db import db
from utils.enums import (
    InstitutionApprovalStatus,
    MembershipRole,
    UserStatus,
    WorkspaceKind,
    WorkspaceStatus,
)
from utils.join_code import generate_workspace_join_code


class InstitutionAdminService:
    def __init__(self):
        self.users = UserRepository()
        self.workspaces = WorkspaceRepository()
        self.memberships = MembershipRepository()
        self.registration_intents = RegistrationIntentRepository()

    def list_pending_institutions(self) -> list[dict]:
        rows = self.registration_intents.list_pending_institutions()
        return [self._serialize_institution_request(intent) for intent in rows]

    def get_institution_request(self, user_id: int) -> dict:
        intent = self._get_institution_intent_for_user(user_id)
        return self._serialize_institution_request(intent)

    def approve_institution(self, user_id: int) -> dict:
        intent = self._get_pending_institution_intent(user_id)
        user = self._get_user_or_404(user_id)

        if self.workspaces.find_by_slug(intent.slug):
            raise ConflictError("Workspace slug is no longer available")

        try:
            workspace = Workspace(
                name=intent.workspace_name,
                slug=intent.slug,
                kind=WorkspaceKind.INSTITUTION.value,
                owner_user_id=user.id,
                status=WorkspaceStatus.ACTIVE.value,
                is_verified_by_superadmin=True,
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

            now = datetime.now(timezone.utc)
            intent.approval_status = InstitutionApprovalStatus.APPROVED.value
            intent.consumed_at = now
            intent.reviewed_at = now
            intent.rejection_reason = None

            user.user_status = UserStatus.ACTIVE.value
            user.email_verified = True

            db.session.commit()
        except Exception:
            db.session.rollback()
            raise

        try:
            EmailDeliveryService().send_institution_approved_email(
                to_email=user.email,
                full_name=user.full_name,
                institution_name=workspace.name,
            )
        except EmailDeliveryError:
            pass

        return {
            "success": True,
            "workspace": {
                "id": workspace.id,
                "kind": workspace.kind,
                "owner_user_id": workspace.owner_user_id,
                "name": workspace.name,
                "slug": workspace.slug,
                "status": workspace.status,
            },
        }

    def reject_institution(self, user_id: int, *, reason: str) -> dict:
        intent = self._get_pending_institution_intent(user_id)
        user = self._get_user_or_404(user_id)
        reason = (reason or "").strip()
        if not reason:
            raise ValidationError("Rejection reason is required")

        now = datetime.now(timezone.utc)
        intent.approval_status = InstitutionApprovalStatus.REJECTED.value
        intent.rejection_reason = reason
        intent.reviewed_at = now
        user.user_status = UserStatus.REGISTRATION_REJECTED.value

        db.session.commit()

        try:
            EmailDeliveryService().send_institution_rejected_email(
                to_email=user.email,
                full_name=user.full_name,
                institution_name=intent.workspace_name,
                reason=reason,
            )
        except EmailDeliveryError:
            pass

        return {"success": True}

    def _get_user_or_404(self, user_id: int) -> User:
        user = self.users.get_by_id(user_id)
        if not user:
            raise NotFoundError("User not found")
        return user

    def _get_institution_intent_for_user(self, user_id: int) -> RegistrationIntent:
        intent = self.registration_intents.find_institution_by_user_id(user_id)
        if not intent:
            raise NotFoundError("Institution registration request not found")
        return intent

    def _get_pending_institution_intent(self, user_id: int) -> RegistrationIntent:
        intent = self.registration_intents.find_pending_institution_by_user_id(user_id)
        if not intent:
            raise ValidationError(
                "No pending institution registration found for this user"
            )
        return intent

    def _serialize_institution_request(self, intent: RegistrationIntent) -> dict:
        user = self.users.get_by_id(intent.user_id) if intent.user_id else None
        return {
            "user_id": intent.user_id,
            "institution_name": intent.workspace_name,
            "slug": intent.slug,
            "workspace_kind": intent.workspace_kind,
            "approval_status": intent.approval_status,
            "submitted_at": intent.created_at.isoformat() if intent.created_at else None,
            "reviewed_at": intent.reviewed_at.isoformat() if intent.reviewed_at else None,
            "owner": {
                "user_id": user.id if user else None,
                "full_name": user.full_name if user else intent.full_name,
                "email": user.email if user else intent.email,
                "phone_number": user.phone_number if user else intent.phone_number,
                "user_status": user.user_status if user else None,
            },
            "profile": {
                "country": intent.country,
                "city": intent.city,
                "website_url": intent.website_url,
                "description": intent.description,
            },
            "rejection_reason": intent.rejection_reason,
        }

    def _unique_join_code(self) -> str:
        for _ in range(10):
            code = generate_workspace_join_code()
            if not self.workspaces.find_by_join_code(code):
                return code
        raise ConflictError("Could not generate unique join code")
