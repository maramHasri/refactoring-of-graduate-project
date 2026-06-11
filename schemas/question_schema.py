from marshmallow import Schema, fields, pre_load, validate

from utils.enums import Difficulty, QuestionStatus


class QuestionChoiceInputSchema(Schema):
    body = fields.Str(required=True, validate=validate.Length(min=1))
    is_correct = fields.Bool(required=True)
    order_index = fields.Int(allow_none=True)


class CreateQuestionInBankItemSchema(Schema):
    """Single question inside POST /question-banks/{bankId}/questions questions[]."""

    type_code = fields.Str(required=True, validate=validate.Length(min=2, max=50))
    body = fields.Str(required=True, validate=validate.Length(min=1))
    explanation = fields.Str(allow_none=True)
    points = fields.Float(allow_none=True, validate=validate.Range(min=0))
    difficulty = fields.Str(
        allow_none=True,
        validate=validate.OneOf([d.value for d in Difficulty]),
    )
    topic_id = fields.Int(allow_none=True, load_default=None)
    choices = fields.List(
        fields.Nested(QuestionChoiceInputSchema),
        load_default=list,
    )

    @pre_load
    def normalize_optional_topic_id(self, data, **kwargs):
        """Treat absent, null, or non-positive topic_id as no topic assignment."""
        if not isinstance(data, dict):
            return data
        if "topic_id" not in data or data["topic_id"] is None:
            data.pop("topic_id", None)
            return data
        try:
            if int(data["topic_id"]) <= 0:
                data.pop("topic_id", None)
        except (TypeError, ValueError):
            pass
        return data


class CreateQuestionsInBankSchema(Schema):
    """
    POST /question-banks/{bankId}/questions — always { "questions": [...] }.
    Use a one-element array for a single question (Google Forms–style save).
    """

    questions = fields.List(
        fields.Nested(CreateQuestionInBankItemSchema),
        required=True,
        validate=validate.Length(min=1),
    )


# Backward-compatible alias for imports that referenced the item schema name
CreateQuestionInBankSchema = CreateQuestionsInBankSchema


class QuestionSchema(Schema):
    id = fields.Int(dump_only=True)
    bank_id = fields.Int(allow_none=True)
    type_code = fields.Str()
    body = fields.Str()
    explanation = fields.Str(allow_none=True)
    points = fields.Float(allow_none=True)
    difficulty = fields.Str(allow_none=True)
    topic_id = fields.Int(allow_none=True)
    status = fields.Str()
    owner_user_id = fields.Int()
    choices = fields.List(fields.Dict())
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


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
