from marshmallow import Schema, fields, validate

from utils.enums import AnswerGradingStatus


class AttemptAnswerSchema(Schema):
    id = fields.Int(dump_only=True)
    attempt_id = fields.Int(required=True)
    test_question_id = fields.Int(required=True)
    answer_text = fields.Str(allow_none=True)
    selected_choice_indices = fields.List(fields.Int(), allow_none=True)
    is_correct = fields.Bool(allow_none=True)
    earned_score = fields.Float(allow_none=True)
    grading_status = fields.Str(
        allow_none=True,
        validate=validate.OneOf([s.value for s in AnswerGradingStatus]),
    )
    updated_at = fields.DateTime(dump_only=True)


class SaveAttemptAnswerItemSchema(Schema):
    test_question_id = fields.Int(required=True, validate=validate.Range(min=1))
    answer_text = fields.Str(allow_none=True)
    selected_choice_indices = fields.List(fields.Int(), allow_none=True)


class BulkSaveAttemptAnswersSchema(Schema):
    answers = fields.List(
        fields.Nested(SaveAttemptAnswerItemSchema),
        required=True,
        validate=validate.Length(min=1),
    )


class UpdateAttemptAnswerSchema(Schema):
    answer_text = fields.Str(allow_none=True)
    selected_choice_indices = fields.List(fields.Int(), allow_none=True)


class GradeEssayAnswerItemSchema(Schema):
    test_question_id = fields.Int(required=True, validate=validate.Range(min=1))
    earned_score = fields.Float(required=True, validate=validate.Range(min=0))
    teacher_feedback = fields.Str(allow_none=True)


class GradeAttemptEssaysSchema(Schema):
    """POST /tests/{test_id}/attempts/{attempt_id}/grading/manual — teacher manual grading."""

    answers = fields.List(
        fields.Nested(GradeEssayAnswerItemSchema),
        required=True,
        validate=validate.Length(min=1),
    )
