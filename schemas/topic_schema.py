from marshmallow import Schema, fields, validate

from utils.enums import QuestionStatus


class TopicSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)
    workspace_id = fields.Int(required=True)
    code = fields.Str(allow_none=True)
    subject_id = fields.Int(required=True)


class CreateTopicSchema(Schema):
    """POST /subjects/{subjectId}/topics — workspace comes from X-Workspace-Id."""

    name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    code = fields.Str(allow_none=True, validate=validate.Length(max=50))


class UpdateTopicSchema(Schema):
    name = fields.Str(validate=validate.Length(min=1, max=255))
    code = fields.Str(allow_none=True, validate=validate.Length(max=50))


class QuestionTypeSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)
    code = fields.Str(allow_none=True)
    description = fields.Str(allow_none=True)


class CreateQuestionTypeSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    code = fields.Str(allow_none=True, validate=validate.Length(max=50))
    description = fields.Str(allow_none=True)


class QuestionChoiceSchema(Schema):
    """Answer option on a question (see schemas.question_schema for bank APIs)."""

    id = fields.Int(dump_only=True)
    question_id = fields.Int(required=True)
    body = fields.Str(required=True)
    is_correct = fields.Bool()
    order_index = fields.Int(allow_none=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class CreateQuestionChoiceSchema(Schema):
    body = fields.Str(required=True, validate=validate.Length(min=1))
    is_correct = fields.Bool(required=True)
    order_index = fields.Int(allow_none=True)


class UpdateQuestionChoiceSchema(Schema):
    body = fields.Str(validate=validate.Length(min=1))
    is_correct = fields.Bool()
    order_index = fields.Int(allow_none=True)
