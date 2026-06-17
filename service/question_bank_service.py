"""
Question banks — subject-centered, visibility-aware.
"""
from datetime import datetime, timezone

from models import QuestionBank
from repositories.question_bank_repository import QuestionBankRepository
from repositories.subject_repository import SubjectMembershipRepository, SubjectRepository
from repositories.workspace_repository import WorkspaceRepository
from service.exceptions import ForbiddenError, NotFoundError, ValidationError
from utils.academic_rbac import (
    can_manage_subjects,
    can_modify_question_bank,
    can_view_question_bank,
    verify_subject_teacher_access,
)
from utils.db import db
from utils.enums import QuestionBankVisibility
from utils.pagination import build_pagination_meta, normalize_pagination


class QuestionBankService:
    def __init__(self):
        self.banks = QuestionBankRepository()
        self.subjects = SubjectRepository()
        self.subject_memberships = SubjectMembershipRepository()
        self.workspaces = WorkspaceRepository()
    def create_question_bank(
        self,
        *,
        workspace_id: int,
        subject_id: int,
        title: str,
        actor_membership,
        description: str | None = None,
        visibility: str = QuestionBankVisibility.WORKSPACE.value,
    ) -> QuestionBank:
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found")

        self.resolve_bank_subject_for_teacher_write(
            workspace=workspace,
            subject_id=subject_id,
            actor_membership=actor_membership,
        )

        if visibility not in [v.value for v in QuestionBankVisibility]:
            raise ValidationError("Invalid visibility value")

        bank = QuestionBank(
            title=title.strip(),
            description=description,
            workspace_id=workspace_id,
            subject_id=subject_id,
            created_by_membership_id=actor_membership.id,
            visibility=visibility,
        )
        self.banks.add(bank)
        db.session.commit()
        return bank

    def list_my_question_banks(
        self, workspace_id: int, actor_membership
    ) -> list[dict]:
        rows = self.banks.list_by_creator(actor_membership.id, workspace_id)
        return [self._serialize_bank(b) for b in rows]

    def list_workspace_question_banks(
        self,
        *,
        workspace_id: int,
        actor_membership,
        page: int | None = None,
        per_page: int | None = None,
    ) -> dict:
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found")

        if can_manage_subjects(workspace, actor_membership):
            subject_ids = [
                subject.id
                for subject in self.subjects.list_active_by_workspace(workspace_id)
            ]
        else:
            subject_ids = self.subject_memberships.list_teacher_subject_ids(
                actor_membership.id, workspace_id
            )

        page, per_page, offset = normalize_pagination(page, per_page)
        total = self.banks.count_workspace_discoverable(
            workspace_id=workspace_id,
            exclude_membership_id=actor_membership.id,
            subject_ids=subject_ids,
        )
        rows = self.banks.list_workspace_discoverable(
            workspace_id=workspace_id,
            exclude_membership_id=actor_membership.id,
            subject_ids=subject_ids,
            offset=offset,
            limit=per_page,
        )
        return {
            "question_banks": [self._serialize_bank(bank) for bank in rows],
            "count": len(rows),
            **build_pagination_meta(total=total, page=page, per_page=per_page),
        }

    def list_community_question_banks(
        self,
        *,
        page: int | None = None,
        per_page: int | None = None,
    ) -> dict:
        page, per_page, offset = normalize_pagination(page, per_page)
        total = self.banks.count_community()
        rows = self.banks.list_community(offset=offset, limit=per_page)
        return {
            "question_banks": [self._serialize_bank(bank) for bank in rows],
            "count": len(rows),
            **build_pagination_meta(total=total, page=page, per_page=per_page),
        }

    def list_subject_question_banks(
        self,
        *,
        workspace_id: int,
        subject_id: int,
        actor_membership,
    ) -> list[dict]:
        workspace = self.workspaces.get_by_id(workspace_id)
        subject = self.subjects.get_active_by_id(subject_id, workspace_id)
        if not subject:
            raise NotFoundError("Subject not found")

        actor_link = self.subject_memberships.find_active(
            actor_membership.id, subject_id
        )
        if not can_manage_subjects(workspace, actor_membership) and not actor_link:
            raise ForbiddenError("You do not have access to this subject")

        rows = self.banks.list_by_subject(subject_id, workspace_id)
        result = []
        for bank in rows:
            if can_view_question_bank(
                bank.visibility,
                workspace=workspace,
                actor=actor_membership,
                actor_subject_link=actor_link,
                is_bank_creator=bank.created_by_membership_id == actor_membership.id,
            ):
                result.append(self._serialize_bank(bank))
        return result

    def update_question_bank(
        self,
        bank_id: int,
        workspace_id: int,
        actor_membership,
        data: dict,
    ) -> QuestionBank:
        workspace = self.workspaces.get_by_id(workspace_id)
        bank = self.banks.get_active_by_id(bank_id, workspace_id)
        if not bank:
            raise NotFoundError("Question bank not found")

        is_creator = bank.created_by_membership_id == actor_membership.id
        if not can_modify_question_bank(
            workspace, actor_membership, is_bank_creator=is_creator
        ):
            raise ForbiddenError("Only the creator or workspace admin can update this bank")

        if "title" in data and data["title"]:
            bank.title = data["title"].strip()
        if "description" in data:
            bank.description = data["description"]
        if "visibility" in data and data["visibility"]:
            if data["visibility"] not in [v.value for v in QuestionBankVisibility]:
                raise ValidationError("Invalid visibility value")
            bank.visibility = data["visibility"]

        db.session.commit()
        return bank

    def archive_question_bank(
        self, bank_id: int, workspace_id: int, actor_membership
    ) -> QuestionBank:
        workspace = self.workspaces.get_by_id(workspace_id)
        bank = self.banks.get_active_by_id(bank_id, workspace_id)
        if not bank:
            raise NotFoundError("Question bank not found")

        is_creator = bank.created_by_membership_id == actor_membership.id
        if not can_modify_question_bank(
            workspace, actor_membership, is_bank_creator=is_creator
        ):
            raise ForbiddenError("Only the creator or workspace admin can delete this bank")

        now = datetime.now(timezone.utc)
        bank.is_archived = True
        bank.deleted_at = now
        db.session.commit()
        return bank

    def resolve_bank_for_question_write(
        self, *, bank_id: int, workspace_id: int, actor_membership
    ) -> QuestionBank:
        """
        Shared guard for creating/updating questions in a bank.
        Reused by QuestionService to avoid duplicating RBAC checks.
        """
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found")

        bank = self.banks.get_active_by_id(bank_id, workspace_id)
        if not bank:
            raise NotFoundError("Question bank not found")

        self.resolve_bank_subject_for_teacher_write(
            workspace=workspace,
            subject_id=bank.subject_id,
            actor_membership=actor_membership,
        )
        return bank

    def resolve_bank_for_question_view(
        self, *, bank_id: int, workspace_id: int, actor_membership
    ) -> QuestionBank:
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError("Workspace not found")

        bank = self.banks.get_active_by_id(bank_id, workspace_id)
        if not bank:
            raise NotFoundError("Question bank not found")

        actor_link = self.subject_memberships.find_active(
            actor_membership.id, bank.subject_id
        )
        if not can_view_question_bank(
            bank.visibility,
            workspace=workspace,
            actor=actor_membership,
            actor_subject_link=actor_link,
            is_bank_creator=bank.created_by_membership_id == actor_membership.id,
        ):
            raise ForbiddenError("You do not have access to this question bank")

        return bank

    def resolve_bank_subject_for_teacher_write(
        self,
        *,
        workspace,
        subject_id: int,
        actor_membership,
    ) -> None:
        subject = self.subjects.get_active_by_id(subject_id, workspace.id)
        if not subject:
            raise NotFoundError("Subject not found in this workspace")

        actor_link = self.subject_memberships.find_active(
            actor_membership.id, subject_id
        )
        if can_manage_subjects(workspace, actor_membership):
            return
        if verify_subject_teacher_access(actor_link):
            return
        raise ForbiddenError(
            "You must be assigned to this subject as TEACHER to manage question banks"
        )

    def _serialize_bank(self, bank: QuestionBank) -> dict:
        subject = bank.subject
        if subject is None and bank.subject_id:
            subject = self.subjects.get_active_by_id(bank.subject_id, bank.workspace_id)
        return {
            "id": bank.id,
            "title": bank.title,
            "description": bank.description,
            "workspace_id": bank.workspace_id,
            "subject_id": bank.subject_id,
            "subject_name": subject.name if subject else None,
            "visibility": bank.visibility,
            "is_archived": bank.is_archived,
            "created_by_membership_id": bank.created_by_membership_id,
            "created_at": bank.created_at.isoformat() if bank.created_at else None,
            "updated_at": bank.updated_at.isoformat() if bank.updated_at else None,
        }
