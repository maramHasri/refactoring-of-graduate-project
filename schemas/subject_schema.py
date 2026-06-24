from marshmallow import Schema, fields, validate

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
    membership_id = fields.Int(required=True)


# Legacy aliases
SubjectSchema = CreateSubjectSchema
MembershipSubjectSchema = AssignMembershipToSubjectSchema
CreateMembershipSubjectSchema = AssignMembershipToSubjectSchema


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
