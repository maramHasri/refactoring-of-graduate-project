from marshmallow import Schema, fields, validate

from utils.enums import QuestionStatus


class TopicSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)
    workspace_id = fields.Int(required=True)
    code = fields.Str(allow_none=True)
    subject_id = fields.Int(required=True)


class CreateTopicSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    workspace_id = fields.Int(required=True)
    subject_id = fields.Int(required=True)
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
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)
    slug = fields.Str(required=True)
    kind = fields.Str(required=True)
    owner_user_id = fields.Int(required=True)
    status = fields.Str()
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class CreateQuestionChoiceSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    slug = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    kind = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    owner_user_id = fields.Int(required=True)
    status = fields.Str(
        load_default=QuestionStatus.ACTIVE.value,
        validate=validate.OneOf([s.value for s in QuestionStatus]),
    )


class UpdateQuestionChoiceSchema(Schema):
    name = fields.Str(validate=validate.Length(min=1, max=255))
    slug = fields.Str(validate=validate.Length(min=1, max=255))
    kind = fields.Str(validate=validate.Length(min=1, max=50))
    status = fields.Str(validate=validate.OneOf([s.value for s in QuestionStatus]))
