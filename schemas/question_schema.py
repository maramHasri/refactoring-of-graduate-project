from marshmallow import Schema, fields, validate

from utils.enums import QuestionStatus


class QuestionSchema(Schema):
    id = fields.Int(dump_only=True)
    bank_id = fields.Int(allow_none=True)
    name = fields.Str(required=True)
    slug = fields.Str(required=True)
    question_type_id = fields.Int(required=True)
    owner_user_id = fields.Int(required=True)
    status = fields.Str()
    question_choices_id = fields.Int(allow_none=True)
    topic_id = fields.Int(allow_none=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class CreateQuestionSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    slug = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    question_type_id = fields.Int(required=True)
    owner_user_id = fields.Int(required=True)
    bank_id = fields.Int(allow_none=True)
    question_choices_id = fields.Int(allow_none=True)
    topic_id = fields.Int(allow_none=True)
    status = fields.Str(
        load_default=QuestionStatus.ACTIVE.value,
        validate=validate.OneOf([s.value for s in QuestionStatus]),
    )


class UpdateQuestionSchema(Schema):
    name = fields.Str(validate=validate.Length(min=1, max=255))
    slug = fields.Str(validate=validate.Length(min=1, max=255))
    question_type_id = fields.Int()
    bank_id = fields.Int(allow_none=True)
    question_choices_id = fields.Int(allow_none=True)
    topic_id = fields.Int(allow_none=True)
    status = fields.Str(validate=validate.OneOf([s.value for s in QuestionStatus]))


class TestQuestionSchema(Schema):
    id = fields.Int(dump_only=True)
    test_id = fields.Int(required=True)
    question_id = fields.Int(required=True)
    kind = fields.Str(required=True)
    points = fields.Decimal(required=True, places=2, as_string=True)
    status = fields.Str()
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class CreateTestQuestionSchema(Schema):
    test_id = fields.Int(required=True)
    question_id = fields.Int(required=True)
    kind = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    points = fields.Decimal(
        required=True,
        places=2,
        validate=validate.Range(min=0),
        as_string=True,
    )
    status = fields.Str(
        load_default=QuestionStatus.ACTIVE.value,
        validate=validate.OneOf([s.value for s in QuestionStatus]),
    )


class UpdateTestQuestionSchema(Schema):
    kind = fields.Str(validate=validate.Length(min=1, max=50))
    points = fields.Decimal(places=2, validate=validate.Range(min=0), as_string=True)
    status = fields.Str(validate=validate.OneOf([s.value for s in QuestionStatus]))
