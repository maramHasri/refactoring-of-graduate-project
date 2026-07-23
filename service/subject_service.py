"""
Subject lifecycle and subject_memberships (teacher/student assignments).
"""

from utils.messages import Messages
from datetime import datetime, timezone

from models import Subject, SubjectMembership
from repositories.subject_repository import (
    SubjectMembershipRepository,
    SubjectRepository,
)
from repositories.topic_repository import TopicRepository
from repositories.workspace_repository import MembershipRepository, WorkspaceRepository
from service.exceptions import ConflictError, ForbiddenError, NotFoundError, ValidationError
from utils.academic_rbac import (
    can_assign_teachers_to_subject,
    can_enroll_students_in_subject,
    can_manage_subjects,
    verify_subject_teacher_access,
)
from utils.db import db
from utils.enums import MembershipRole, MembershipStatus, SubjectMembershipStatus, SubjectRole


class SubjectService:
    def __init__(self):
        self.subjects = SubjectRepository()
        self.subject_memberships = SubjectMembershipRepository()
        self.memberships = MembershipRepository()
        self.workspaces = WorkspaceRepository()
        self.topics = TopicRepository()

    def create_subject(
        self,
        *,
        workspace_id: int,
        name: str,
        actor_membership,
        description: str | None = None,
    ) -> Subject:
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError(Messages.WORKSPACE_NOT_FOUND)
        if not can_manage_subjects(workspace, actor_membership):
            raise ForbiddenError(Messages.ONLY_WORKSPACE_OWNER_OR_ADMIN_CAN_CREATE_SUBJECTS)

        name = name.strip()
        if self.subjects.find_by_workspace_and_name(workspace_id, name):
            raise ConflictError(Messages.A_SUBJECT_WITH_THIS_NAME_ALREADY_EXISTS_IN_THE_WORKSPACE)

        subject = Subject(
            name=name,
            workspace_id=workspace_id,
            description=description,
            created_by_membership_id=actor_membership.id,
        )
        self.subjects.add(subject)
        db.session.commit()
        return subject

    def list_workspace_subjects(self, workspace_id: int, actor_membership) -> list[dict]:
        workspace = self.workspaces.get_by_id(workspace_id)
        if not workspace:
            raise NotFoundError(Messages.WORKSPACE_NOT_FOUND)

        if can_manage_subjects(workspace, actor_membership):
            rows = self.subjects.list_active_by_workspace(workspace_id)
            topics_map = self.topics.map_by_subject_ids(
                workspace_id, [s.id for s in rows]
            )
            return [
                self._serialize_subject(s, topics_map=topics_map) for s in rows
            ]

        if actor_membership.role == MembershipRole.TEACHER.value:
            links = self._subjects_for_membership(actor_membership.id, workspace_id)
            topics_map = self.topics.map_by_subject_ids(
                workspace_id, [s.id for s in links]
            )
            return [
                self._serialize_subject(s, topics_map=topics_map) for s in links
            ]

        if actor_membership.role == MembershipRole.STUDENT.value:
            links = self._subjects_for_membership(actor_membership.id, workspace_id)
            topics_map = self.topics.map_by_subject_ids(
                workspace_id, [s.id for s in links]
            )
            return [
                self._serialize_subject(s, topics_map=topics_map) for s in links
            ]

        raise ForbiddenError(Messages.INSUFFICIENT_PERMISSIONS_TO_LIST_SUBJECTS)

    def get_subject(
        self, subject_id: int, workspace_id: int, actor_membership
    ) -> dict:
        subject = self._get_subject_or_404(subject_id, workspace_id)
        self._ensure_can_view_subject(subject, actor_membership)
        topics_map = self.topics.map_by_subject_ids(workspace_id, [subject.id])
        return self._serialize_subject(subject, topics_map=topics_map)

    def update_subject(
        self,
        subject_id: int,
        workspace_id: int,
        actor_membership,
        data: dict,
    ) -> Subject:
        workspace = self.workspaces.get_by_id(workspace_id)
        subject = self._get_subject_or_404(subject_id, workspace_id)
        if not can_manage_subjects(workspace, actor_membership):
            raise ForbiddenError(Messages.ONLY_WORKSPACE_OWNER_OR_ADMIN_CAN_UPDATE_SUBJECTS)

        if "name" in data and data["name"]:
            name = data["name"].strip()
            existing = self.subjects.find_by_workspace_and_name(workspace_id, name)
            if existing and existing.id != subject.id:
                raise ConflictError(Messages.A_SUBJECT_WITH_THIS_NAME_ALREADY_EXISTS)
            subject.name = name
        if "description" in data:
            subject.description = data["description"]
        if "is_archived" in data and data["is_archived"] is not None:
            subject.is_archived = bool(data["is_archived"])

        db.session.commit()
        return subject

    def archive_subject(
        self, subject_id: int, workspace_id: int, actor_membership
    ) -> Subject:
        workspace = self.workspaces.get_by_id(workspace_id)
        subject = self._get_subject_or_404(subject_id, workspace_id)
        if not can_manage_subjects(workspace, actor_membership):
            raise ForbiddenError(Messages.ONLY_WORKSPACE_OWNER_OR_ADMIN_CAN_ARCHIVE_SUBJECTS)

        now = datetime.now(timezone.utc)
        subject.is_archived = True
        subject.deleted_at = now
        db.session.commit()
        return subject

    def assign_teacher_to_subject(
        self,
        *,
        workspace_id: int,
        subject_id: int,
        teacher_membership_id: int,
        actor_membership,
    ) -> SubjectMembership:
        workspace = self.workspaces.get_by_id(workspace_id)
        subject = self._get_subject_or_404(subject_id, workspace_id)
        if not can_assign_teachers_to_subject(workspace, actor_membership):
            raise ForbiddenError(Messages.ONLY_WORKSPACE_OWNER_OR_ADMIN_CAN_ASSIGN_TEACHERS)

        teacher = self.memberships.get_by_id(teacher_membership_id)
        if not teacher or teacher.workspace_id != workspace_id:
            raise NotFoundError(Messages.MEMBERSHIP_NOT_FOUND_IN_THIS_WORKSPACE)
        if teacher.status != "ACTIVE":
            raise ValidationError(Messages.MEMBERSHIP_IS_NOT_ACTIVE)
        if teacher.role not in (
            MembershipRole.TEACHER.value,
            MembershipRole.ADMIN.value,
        ):
            raise ValidationError(Messages.ONLY_WORKSPACE_TEACHERS_OR_ADMINS_CAN_BE_ASSIGNED_AS_SUBJECT_TEACHERS)

        if self.subject_memberships.find_active(teacher_membership_id, subject_id):
            raise ConflictError(Messages.TEACHER_IS_ALREADY_ASSIGNED_TO_THIS_SUBJECT)

        link = SubjectMembership(
            subject_id=subject_id,
            membership_id=teacher_membership_id,
            subject_role=SubjectRole.TEACHER.value,
            assigned_by_membership_id=actor_membership.id,
            status=SubjectMembershipStatus.ACTIVE.value,
        )
        self.subject_memberships.add(link)
        db.session.commit()
        return link

    def remove_teacher_from_subject(
        self,
        *,
        workspace_id: int,
        subject_id: int,
        teacher_membership_id: int,
        actor_membership,
    ) -> None:
        workspace = self.workspaces.get_by_id(workspace_id)
        self._get_subject_or_404(subject_id, workspace_id)
        if not can_assign_teachers_to_subject(workspace, actor_membership):
            raise ForbiddenError(Messages.ONLY_WORKSPACE_OWNER_OR_ADMIN_CAN_REMOVE_TEACHERS)

        link = self.subject_memberships.find_active_by_role(
            teacher_membership_id, subject_id, SubjectRole.TEACHER.value
        )
        if not link:
            raise NotFoundError(Messages.TEACHER_ASSIGNMENT_NOT_FOUND)
        self.subject_memberships.soft_remove(link)
        db.session.commit()

    def list_subject_teachers(
        self, subject_id: int, workspace_id: int, actor_membership
    ) -> list[dict]:
        subject = self._get_subject_or_404(subject_id, workspace_id)
        self._ensure_can_view_subject(subject, actor_membership)
        links = self.subject_memberships.list_teachers_for_subject(subject_id)
        return [self._serialize_assignment(link) for link in links]

    def enroll_student_in_subject(
        self,
        *,
        workspace_id: int,
        subject_id: int,
        student_membership_id: int,
        actor_membership,
    ) -> SubjectMembership:
        result = self.enroll_students_in_subject(
            workspace_id=workspace_id,
            subject_id=subject_id,
            student_membership_ids=[student_membership_id],
            actor_membership=actor_membership,
            skip_already_enrolled=False,
        )
        if result["assignments"]:
            # Fresh enroll or reactivation — recover link by membership id.
            membership_id = student_membership_id
            link = self.subject_memberships.find_active_by_role(
                membership_id, subject_id, SubjectRole.STUDENT.value
            )
            if link:
                return link
        raise ConflictError(Messages.STUDENT_IS_ALREADY_ENROLLED_IN_THIS_SUBJECT)

    def enroll_students_in_subject(
        self,
        *,
        workspace_id: int,
        subject_id: int,
        student_membership_ids: list[int],
        actor_membership,
        skip_already_enrolled: bool = True,
    ) -> dict:
        """
        Enroll one or more workspace STUDENT memberships into a subject.

        When ``skip_already_enrolled`` is True (bulk default), active enrollments
        are skipped. When False (single legacy path), already-enrolled raises 409.
        Soft-removed STUDENT links are reactivated.
        """
        workspace = self.workspaces.get_by_id(workspace_id)
        self._get_subject_or_404(subject_id, workspace_id)
        actor_link = self.subject_memberships.find_active_by_role(
            actor_membership.id, subject_id, SubjectRole.TEACHER.value
        )
        if not can_enroll_students_in_subject(workspace, actor_membership, actor_link):
            raise ForbiddenError(
                Messages.ONLY_ADMIN_OWNER_OR_ASSIGNED_SUBJECT_TEACHERS_CAN_ENROLL_STUDENTS
            )

        if not student_membership_ids:
            raise ValidationError(Messages.STUDENT_MEMBERSHIP_IDS_MUST_CONTAIN_AT_LEAST_ONE_ID)

        enrolled_links: list[SubjectMembership] = []
        skipped_membership_ids: list[int] = []

        for student_membership_id in student_membership_ids:
            student = self.memberships.get_by_id(student_membership_id)
            if not student or student.workspace_id != workspace_id:
                raise NotFoundError(Messages.MEMBERSHIP_NOT_FOUND_IN_THIS_WORKSPACE)
            if student.role != MembershipRole.STUDENT.value:
                raise ValidationError(Messages.ONLY_STUDENTS_CAN_BE_ENROLLED_IN_A_SUBJECT)
            if student.status != "ACTIVE":
                raise ValidationError(Messages.MEMBERSHIP_IS_NOT_ACTIVE)

            active_any = self.subject_memberships.find_active(
                student_membership_id, subject_id
            )
            if active_any:
                if active_any.subject_role != SubjectRole.STUDENT.value:
                    raise ConflictError(
                        Messages.MEMBERSHIP_ALREADY_HAS_A_DIFFERENT_SUBJECT_ROLE_ON_THIS_SUBJECT
                    )
                if skip_already_enrolled:
                    skipped_membership_ids.append(student_membership_id)
                    continue
                raise ConflictError(Messages.STUDENT_IS_ALREADY_ENROLLED_IN_THIS_SUBJECT)

            existing = self.subject_memberships.find_by_membership_and_subject(
                student_membership_id, subject_id
            )
            if existing:
                if existing.subject_role != SubjectRole.STUDENT.value:
                    raise ConflictError(
                        Messages.MEMBERSHIP_ALREADY_HAS_A_DIFFERENT_SUBJECT_ROLE_ON_THIS_SUBJECT
                    )
                self.subject_memberships.reactivate(
                    existing,
                    assigned_by_membership_id=actor_membership.id,
                    subject_role=SubjectRole.STUDENT.value,
                )
                enrolled_links.append(existing)
                continue

            link = SubjectMembership(
                subject_id=subject_id,
                membership_id=student_membership_id,
                subject_role=SubjectRole.STUDENT.value,
                assigned_by_membership_id=actor_membership.id,
                status=SubjectMembershipStatus.ACTIVE.value,
            )
            self.subject_memberships.add(link)
            enrolled_links.append(link)

        db.session.commit()
        return {
            "enrolled_count": len(enrolled_links),
            "skipped_count": len(skipped_membership_ids),
            "skipped_membership_ids": skipped_membership_ids,
            "assignments": [
                self._serialize_assignment(link) for link in enrolled_links
            ],
        }

    def remove_student_from_subject(
        self,
        *,
        workspace_id: int,
        subject_id: int,
        student_membership_id: int,
        actor_membership,
    ) -> None:
        workspace = self.workspaces.get_by_id(workspace_id)
        subject = self._get_subject_or_404(subject_id, workspace_id)
        actor_link = self.subject_memberships.find_active_by_role(
            actor_membership.id, subject_id, SubjectRole.TEACHER.value
        )
        if not can_enroll_students_in_subject(workspace, actor_membership, actor_link):
            raise ForbiddenError(Messages.INSUFFICIENT_PERMISSIONS_TO_REMOVE_STUDENT_ENROLLMENT)

        link = self.subject_memberships.find_active_by_role(
            student_membership_id, subject_id, SubjectRole.STUDENT.value
        )
        if not link:
            raise NotFoundError(Messages.STUDENT_ENROLLMENT_NOT_FOUND)
        self.subject_memberships.soft_remove(link)
        db.session.commit()

    def list_subject_students(
        self, subject_id: int, workspace_id: int, actor_membership
    ) -> list[dict]:
        subject = self._get_subject_or_404(subject_id, workspace_id)
        workspace = self.workspaces.get_by_id(workspace_id)
        actor_link = self.subject_memberships.find_active_by_role(
            actor_membership.id, subject_id, SubjectRole.TEACHER.value
        )

        if can_manage_subjects(workspace, actor_membership):
            pass
        elif verify_subject_teacher_access(actor_link):
            pass
        else:
            raise ForbiddenError(Messages.TEACHERS_MAY_ONLY_LIST_STUDENTS_FOR_SUBJECTS_THEY_TEACH)

        links = self.subject_memberships.list_students_for_subject(subject_id)
        return [self._serialize_assignment(link) for link in links]

    def assign_subjects_to_student(
        self,
        *,
        workspace_id: int,
        student_membership_id: int,
        subject_ids: list[int],
        actor_membership,
    ) -> dict:
        workspace = self.workspaces.get_by_id(workspace_id)
        if not can_manage_subjects(workspace, actor_membership):
            raise ForbiddenError(Messages.ONLY_WORKSPACE_OWNER_OR_ADMIN_CAN_ASSIGN_SUBJECTS_TO_STUDENTS)

        self._validate_student_membership(workspace_id, student_membership_id)
        unique_subject_ids = self._validate_subject_ids(workspace_id, subject_ids)

        for subject_id in unique_subject_ids:
            self._ensure_student_subject_link(
                student_membership_id=student_membership_id,
                subject_id=subject_id,
                actor_membership_id=actor_membership.id,
            )

        db.session.commit()
        return self._serialize_student_subjects_response(
            workspace_id, student_membership_id
        )

    def list_student_subjects(
        self,
        *,
        workspace_id: int,
        student_membership_id: int,
        actor_membership,
    ) -> dict:
        workspace = self.workspaces.get_by_id(workspace_id)
        self._ensure_can_view_student_subjects(
            workspace, actor_membership, student_membership_id
        )
        self._validate_student_membership(workspace_id, student_membership_id)
        return self._serialize_student_subjects_response(
            workspace_id, student_membership_id
        )

    def replace_student_subjects(
        self,
        *,
        workspace_id: int,
        student_membership_id: int,
        subject_ids: list[int],
        actor_membership,
    ) -> dict:
        workspace = self.workspaces.get_by_id(workspace_id)
        if not can_manage_subjects(workspace, actor_membership):
            raise ForbiddenError(Messages.ONLY_WORKSPACE_OWNER_OR_ADMIN_CAN_UPDATE_STUDENT_SUBJECT_ASSIGNMENTS)

        self._validate_student_membership(workspace_id, student_membership_id)
        desired_subject_ids = set(self._validate_subject_ids(workspace_id, subject_ids))

        current_links = self.subject_memberships.list_student_assignments_for_membership(
            student_membership_id, workspace_id
        )
        current_subject_ids = {link.subject_id for link in current_links}

        for link in current_links:
            if link.subject_id not in desired_subject_ids:
                self.subject_memberships.soft_remove(link)

        for subject_id in desired_subject_ids - current_subject_ids:
            self._ensure_student_subject_link(
                student_membership_id=student_membership_id,
                subject_id=subject_id,
                actor_membership_id=actor_membership.id,
            )

        db.session.commit()
        return self._serialize_student_subjects_response(
            workspace_id, student_membership_id
        )

    def remove_student_subject(
        self,
        *,
        workspace_id: int,
        student_membership_id: int,
        subject_id: int,
        actor_membership,
    ) -> dict:
        workspace = self.workspaces.get_by_id(workspace_id)
        if not can_manage_subjects(workspace, actor_membership):
            raise ForbiddenError(Messages.ONLY_WORKSPACE_OWNER_OR_ADMIN_CAN_REMOVE_STUDENT_SUBJECT_ASSIGNMENTS)

        self._validate_student_membership(workspace_id, student_membership_id)
        self._get_subject_or_404(subject_id, workspace_id)

        link = self.subject_memberships.find_active_by_role(
            student_membership_id, subject_id, SubjectRole.STUDENT.value
        )
        if not link:
            raise NotFoundError(Messages.STUDENT_SUBJECT_ASSIGNMENT_NOT_FOUND)

        self.subject_memberships.soft_remove(link)
        db.session.commit()
        return self._serialize_student_subjects_response(
            workspace_id, student_membership_id
        )

    def get_actor_subject_link(
        self, membership_id: int, subject_id: int
    ) -> SubjectMembership | None:
        return self.subject_memberships.find_active(membership_id, subject_id)

    def _get_subject_or_404(self, subject_id: int, workspace_id: int) -> Subject:
        subject = self.subjects.get_active_by_id(subject_id, workspace_id)
        if not subject:
            raise NotFoundError(Messages.SUBJECT_NOT_FOUND)
        return subject

    def _ensure_can_view_subject(self, subject: Subject, actor_membership) -> None:
        workspace = self.workspaces.get_by_id(subject.workspace_id)
        if can_manage_subjects(workspace, actor_membership):
            return
        link = self.subject_memberships.find_active(actor_membership.id, subject.id)
        if link:
            return
        raise ForbiddenError(Messages.YOU_DO_NOT_HAVE_ACCESS_TO_THIS_SUBJECT)

    def _subjects_for_membership(
        self, membership_id: int, workspace_id: int
    ) -> list[Subject]:
        return list(
            db.session.execute(
                db.select(Subject)
                .join(
                    SubjectMembership,
                    SubjectMembership.subject_id == Subject.id,
                )
                .where(
                    SubjectMembership.membership_id == membership_id,
                    Subject.workspace_id == workspace_id,
                    Subject.deleted_at.is_(None),
                    SubjectMembership.deleted_at.is_(None),
                    SubjectMembership.status == SubjectMembershipStatus.ACTIVE.value,
                )
                .order_by(Subject.name)
            ).scalars().all()
        )

    def _serialize_topic_summary(self, topic) -> dict:
        return {
            "id": topic.id,
            "name": topic.name,
        }

    def _serialize_subject(
        self,
        subject: Subject,
        *,
        workspace_id: int | None = None,
        topics_map: dict | None = None,
    ) -> dict:
        if topics_map is not None:
            topic_rows = topics_map.get(subject.id, [])
        elif workspace_id is not None:
            topic_rows = self.topics.list_by_subject(subject.id, workspace_id)
        else:
            topic_rows = []

        return {
            "id": subject.id,
            "name": subject.name,
            "title": subject.name,
            "description": subject.description,
            "workspace_id": subject.workspace_id,
            "is_archived": subject.is_archived,
            "created_by_membership_id": subject.created_by_membership_id,
            "created_at": subject.created_at.isoformat() if subject.created_at else None,
            "updated_at": subject.updated_at.isoformat() if subject.updated_at else None,
            "topics": [self._serialize_topic_summary(t) for t in topic_rows],
        }

    def _serialize_assignment(self, link: SubjectMembership) -> dict:
        membership = self.memberships.get_by_id(link.membership_id)
        user = membership.user if membership else None
        return {
            "assignment_id": link.id,
            "membership_id": link.membership_id,
            "subject_id": link.subject_id,
            "subject_role": link.subject_role,
            "membership_role": membership.role if membership else None,
            "full_name": user.full_name if user else None,
            "assigned_at": link.created_at.isoformat() if link.created_at else None,
        }

    def _validate_student_membership(
        self, workspace_id: int, membership_id: int
    ):
        membership = self.memberships.get_by_id(membership_id)
        if not membership or membership.workspace_id != workspace_id:
            raise NotFoundError(Messages.MEMBERSHIP_NOT_FOUND_IN_THIS_WORKSPACE)
        if membership.role != MembershipRole.STUDENT.value:
            raise ValidationError(Messages.MEMBERSHIP_ROLE_MUST_BE_STUDENT)
        if membership.status != MembershipStatus.ACTIVE.value:
            raise ValidationError(Messages.MEMBERSHIP_IS_NOT_ACTIVE)
        return membership

    def _validate_subject_ids(
        self, workspace_id: int, subject_ids: list[int]
    ) -> list[int]:
        if not subject_ids:
            raise ValidationError(Messages.SUBJECT_IDS_IS_REQUIRED)
        unique_ids: list[int] = []
        seen: set[int] = set()
        for subject_id in subject_ids:
            if subject_id in seen:
                continue
            seen.add(subject_id)
            self._get_subject_or_404(subject_id, workspace_id)
            unique_ids.append(subject_id)
        return unique_ids

    def _ensure_student_subject_link(
        self,
        *,
        student_membership_id: int,
        subject_id: int,
        actor_membership_id: int,
    ) -> SubjectMembership:
        existing = self.subject_memberships.find_active_by_role(
            student_membership_id, subject_id, SubjectRole.STUDENT.value
        )
        if existing:
            return existing

        row = self.subject_memberships.find_by_membership_and_subject(
            student_membership_id, subject_id
        )
        if row:
            if row.subject_role != SubjectRole.STUDENT.value:
                raise ConflictError(Messages.MEMBERSHIP_ALREADY_HAS_A_DIFFERENT_SUBJECT_ROLE_ON_THIS_SUBJECT)
            self.subject_memberships.reactivate(
                row,
                assigned_by_membership_id=actor_membership_id,
                subject_role=SubjectRole.STUDENT.value,
            )
            return row

        link = SubjectMembership(
            subject_id=subject_id,
            membership_id=student_membership_id,
            subject_role=SubjectRole.STUDENT.value,
            assigned_by_membership_id=actor_membership_id,
            status=SubjectMembershipStatus.ACTIVE.value,
        )
        self.subject_memberships.add(link)
        return link

    def _ensure_can_view_student_subjects(
        self,
        workspace,
        actor_membership,
        student_membership_id: int,
    ) -> None:
        if can_manage_subjects(workspace, actor_membership):
            return
        if actor_membership.id == student_membership_id:
            return
        raise ForbiddenError(Messages.INSUFFICIENT_PERMISSIONS_TO_VIEW_STUDENT_SUBJECT_ASSIGNMENTS)

    def _serialize_student_subjects_response(
        self, workspace_id: int, student_membership_id: int
    ) -> dict:
        links = self.subject_memberships.list_student_assignments_for_membership(
            student_membership_id, workspace_id
        )
        subject_ids = [link.subject_id for link in links]
        topics_map = self.topics.map_by_subject_ids(workspace_id, subject_ids)
        subjects = []
        for link in links:
            subject = self.subjects.get_by_id(link.subject_id)
            if subject:
                subjects.append(
                    self._serialize_subject(subject, topics_map=topics_map)
                )
        return {
            "membership_id": student_membership_id,
            "assigned_subjects": subjects,
            "count": len(subjects),
        }
