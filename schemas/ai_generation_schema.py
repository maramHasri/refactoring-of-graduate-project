from marshmallow import Schema, fields, validate

from schemas.question_schema import QuestionChoiceInputSchema
from utils.enums import Difficulty


class UpdateAIGeneratedQuestionSchema(Schema):
    question_text = fields.Str(required=True, validate=validate.Length(min=1))
    type_code = fields.Str(required=True, validate=validate.Length(min=2, max=50))
    options = fields.List(
        fields.Nested(QuestionChoiceInputSchema),
        required=True,
        validate=validate.Length(min=1),
    )
    explanation = fields.Str(allow_none=True)
    difficulty = fields.Str(
        allow_none=True,
        validate=validate.OneOf([d.value for d in Difficulty]),
    )
    points = fields.Float(allow_none=True, validate=validate.Range(min=0))
    topic_id = fields.Int(required=True, validate=validate.Range(min=1))
