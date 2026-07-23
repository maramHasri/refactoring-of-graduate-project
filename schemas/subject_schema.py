from marshmallow import Schema, ValidationError, fields, validates_schema, validate

from utils.enums import QuestionBankVisibility


class CreateSubjectSchema(Schema):
    """POST /subjects — workspace from X-Workspace-Id."""

    name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    description = fields.Str(allow_none=True)


class UpdateSubjectSchema(Schema):
    name = fields.Str(validate=validate.Length(min=1, max=255))
    description = fields.Str(allow_none=True)
    is_archived = fields.Bool()


class AssignStudentSubjectsSchema(Schema):
    membership_id = fields.Int(required=True)
    subject_ids = fields.List(
        fields.Int(), required=True, validate=validate.Length(min=1)
    )


class ReplaceStudentSubjectsSchema(Schema):
    subject_ids = fields.List(fields.Int(), required=True)


class AssignMembershipToSubjectSchema(Schema):
    """Legacy single-student enroll body."""

    membership_id = fields.Int(required=True)


class EnrollStudentsInSubjectSchema(Schema):
    """
    POST /subjects/{id}/students — bulk enroll.

    Accepts ``membership_ids`` (preferred) and/or legacy ``membership_id``.
    """

    membership_ids = fields.List(
        fields.Int(validate=validate.Range(min=1)),
        load_default=None,
        allow_none=True,
        validate=validate.Length(min=1, max=500),
    )
    membership_id = fields.Int(
        load_default=None,
        allow_none=True,
        validate=validate.Range(min=1),
    )

    @validates_schema
    def _require_at_least_one_membership(self, data, **kwargs):
        ids: list[int] = []
        for value in data.get("membership_ids") or []:
            ids.append(int(value))
        if data.get("membership_id") is not None:
            ids.append(int(data["membership_id"]))
        if not ids:
            raise ValidationError(
                {
                    "membership_ids": [
                        "Provide membership_ids (array) or membership_id (single)."
                    ]
                }
            )
        unique: list[int] = []
        seen: set[int] = set()
        for membership_id in ids:
            if membership_id in seen:
                continue
            seen.add(membership_id)
            unique.append(membership_id)
        data["membership_ids"] = unique


# Legacy aliases
SubjectSchema = CreateSubjectSchema
MembershipSubjectSchema = AssignMembershipToSubjectSchema
CreateMembershipSubjectSchema = AssignMembershipToSubjectSchema
EnrollStudentInSubjectSchema = EnrollStudentsInSubjectSchema


class CreateQuestionBankSchema(Schema):
    title = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    subject_id = fields.Int(required=True)
    description = fields.Str(allow_none=True)
    visibility = fields.Str(
        load_default=QuestionBankVisibility.WORKSPACE.value,
        validate=validate.OneOf([v.value for v in QuestionBankVisibility]),
    )


class UpdateQuestionBankSchema(Schema):
    title = fields.Str(validate=validate.Length(min=1, max=255))
    description = fields.Str(allow_none=True)
    visibility = fields.Str(
        validate=validate.OneOf([v.value for v in QuestionBankVisibility])
    )


class QuestionBankListQuerySchema(Schema):
    page = fields.Int(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Int(load_default=20, validate=validate.Range(min=1, max=100))
