from marshmallow import Schema, fields, validate


class AttemptAnswerSchema(Schema):
    id = fields.Int(dump_only=True)
    attempt_id = fields.Int(required=True)
    question_id = fields.Int(required=True)
    answer_text = fields.Str(allow_none=True)
    selected_choice_id = fields.Int(allow_none=True)
    is_correct = fields.Bool(allow_none=True)
    earned_score = fields.Decimal(places=2, allow_none=True, as_string=True)


class CreateAttemptAnswerSchema(Schema):
    attempt_id = fields.Int(required=True)
    question_id = fields.Int(required=True)
    answer_text = fields.Str(allow_none=True)
    selected_choice_id = fields.Int(allow_none=True)
    is_correct = fields.Bool(allow_none=True)
    earned_score = fields.Decimal(
        places=2,
        allow_none=True,
        validate=validate.Range(min=0),
        as_string=True,
    )


class UpdateAttemptAnswerSchema(Schema):
    answer_text = fields.Str(allow_none=True)
    selected_choice_id = fields.Int(allow_none=True)
    is_correct = fields.Bool(allow_none=True)
    earned_score = fields.Decimal(
        places=2,
        allow_none=True,
        validate=validate.Range(min=0),
        as_string=True,
    )
