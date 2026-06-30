from marshmallow import Schema, fields, pre_load, validate

from schemas.app_timezone_fields import LocalDateTime
from schemas.question_schema import CreateQuestionInBankItemSchema, QuestionChoiceInputSchema
from utils.enums import (
    AvailabilityTimeMode,
    Difficulty,
    TestAttemptStatus,
    TestQuestionSourceType,
    TestStatus,
)


class TestSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)
    slug = fields.Str(required=True)
    description = fields.Str(allow_none=True)
    subject_id = fields.Int(required=True)
    total_score = fields.Float(allow_none=True)
    passing_score = fields.Float(allow_none=True)
    auto_distribute_scores = fields.Bool()
    settings_config = fields.Dict(allow_none=True)
    created_by_membership_id = fields.Int(allow_none=True)
    status = fields.Str()
    availability_time_mode = fields.Str(allow_none=True)
    starts_at = LocalDateTime(allow_none=True)
    duration_minutes = fields.Int(allow_none=True)
    entry_window_minutes = fields.Int(allow_none=True)
    published_at = fields.DateTime(dump_only=True)
    scheduled_publish_at = fields.DateTime(dump_only=True)
    closed_at = fields.DateTime(dump_only=True)
    archived_at = fields.DateTime(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class CreateTestSchema(Schema):
    """Step 1 exam creation payload from the UI."""

    name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    description = fields.Str(allow_none=True)
    subject_id = fields.Int(required=True)
    duration_minutes = fields.Int(
        load_default=30,
        validate=validate.Range(min=1),
    )
    total_score = fields.Float(
        load_default=100,
        validate=validate.Range(min=0),
    )
    passing_score = fields.Float(
        load_default=50,
        validate=validate.Range(min=0),
    )
    auto_distribute_scores = fields.Bool(load_default=False)


class UpdateTestSchema(Schema):
    name = fields.Str(validate=validate.Length(min=1, max=255))
    slug = fields.Str(validate=validate.Length(min=1, max=255))
    description = fields.Str(allow_none=True)
    total_score = fields.Float(allow_none=True, validate=validate.Range(min=0))
    passing_score = fields.Float(allow_none=True, validate=validate.Range(min=0))
    settings_config = fields.Dict(allow_none=True)
    status = fields.Str(validate=validate.OneOf([s.value for s in TestStatus]))
    availability_time_mode = fields.Str(
        allow_none=True,
        validate=validate.OneOf([m.value for m in AvailabilityTimeMode]),
    )
    starts_at = LocalDateTime(allow_none=True)
    duration_minutes = fields.Int(allow_none=True, validate=validate.Range(min=1))
    entry_window_minutes = fields.Int(allow_none=True, validate=validate.Range(min=0))


class AddBankQuestionsToTestSchema(Schema):
    question_ids = fields.List(
        fields.Int(validate=validate.Range(min=1)),
        required=True,
        validate=validate.Length(min=1),
    )
    source_type = fields.Str(
        load_default=TestQuestionSourceType.QUESTION_BANK.value,
        validate=validate.OneOf([s.value for s in TestQuestionSourceType]),
    )


class ScheduleTestSchema(Schema):
    publish_at = LocalDateTime(required=True)


class AddManualQuestionsToTestSchema(Schema):
    questions = fields.List(
        fields.Nested(CreateQuestionInBankItemSchema),
        required=True,
        validate=validate.Length(min=1),
    )


class AddQuestionsFromBankSelectionSchema(Schema):
    bank_id = fields.Int(required=True)
    question_ids = fields.List(
        fields.Int(validate=validate.Range(min=1)),
        required=True,
        validate=validate.Length(min=1),
    )


class DifficultyDistributionSchema(Schema):
    easy = fields.Int(required=True, validate=validate.Range(min=0, max=100))
    medium = fields.Int(required=True, validate=validate.Range(min=0, max=100))
    hard = fields.Int(required=True, validate=validate.Range(min=0, max=100))


class BlueprintTopicSchema(Schema):
    topic_id = fields.Int(required=True, validate=validate.Range(min=1))
    percentage = fields.Int(required=True, validate=validate.Range(min=1, max=100))
    difficulty_distribution = fields.Nested(
        DifficultyDistributionSchema, required=True
    )


class BlueprintBankSchema(Schema):
    bank_id = fields.Int(required=True, validate=validate.Range(min=1))
    question_count = fields.Int(required=True, validate=validate.Range(min=1, max=200))
    topics = fields.List(
        fields.Nested(BlueprintTopicSchema),
        required=True,
        validate=validate.Length(min=1),
    )


class ExamBlueprintSchema(Schema):
    """POST /tests/{test_id}/questions/random-from-banks — exam blueprint generator."""

    banks = fields.List(
        fields.Nested(BlueprintBankSchema),
        required=True,
        validate=validate.Length(min=1),
    )


class AIGenerateQuestionsSchema(Schema):
    count = fields.Int(required=True, validate=validate.Range(min=1, max=50))
    type_code = fields.Str(load_default="MCQ", validate=validate.Length(min=2, max=50))
    difficulty = fields.Str(
        allow_none=True,
        validate=validate.OneOf(["EASY", "MEDIUM", "HARD"]),
    )
    topics = fields.List(fields.Str(validate=validate.Length(min=1)), load_default=list)
    learning_objectives = fields.List(
        fields.Str(validate=validate.Length(min=1)), load_default=list
    )
    additional_instructions = fields.Str(allow_none=True)


class AssignStudentsToTestSchema(Schema):
    student_membership_ids = fields.List(
        fields.Int(validate=validate.Range(min=1)),
        required=True,
        validate=validate.Length(min=1),
    )


class UpdateTestQuestionSchema(Schema):
    """PATCH /tests/{test_id}/questions/{test_question_id} — partial snapshot update."""

    type_code = fields.Str(validate=validate.Length(min=2, max=50))
    body = fields.Str(validate=validate.Length(min=1))
    explanation = fields.Str(allow_none=True)
    points = fields.Float(allow_none=True, validate=validate.Range(min=0))
    difficulty = fields.Str(
        allow_none=True,
        validate=validate.OneOf([d.value for d in Difficulty]),
    )
    topic_id = fields.Int(allow_none=True)
    choices = fields.List(fields.Nested(QuestionChoiceInputSchema))

    @pre_load
    def normalize_optional_topic_id(self, data, **kwargs):
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


class TestAttemptSchema(Schema):
    id = fields.Int(dump_only=True)
    student_membership_id = fields.Int(required=True)
    test_id = fields.Int(required=True)
    user_id = fields.Int(required=True)
    status = fields.Str()
    started_at = fields.DateTime(required=True)
    submitted_at = fields.DateTime(allow_none=True)
    expires_at = fields.DateTime(allow_none=True)
    last_activity_at = fields.DateTime(allow_none=True)
    submission_source = fields.Str(allow_none=True)
    raw_score = fields.Float(allow_none=True)
    final_score = fields.Float(allow_none=True)


class CreateTestAttemptSchema(Schema):
    student_membership_id = fields.Int(required=True)
    test_id = fields.Int(required=True)
    user_id = fields.Int(required=True)
    started_at = fields.DateTime(required=True)
    expires_at = fields.DateTime(allow_none=True)
    status = fields.Str(
        load_default=TestAttemptStatus.IN_PROGRESS.value,
        validate=validate.OneOf([s.value for s in TestAttemptStatus]),
    )


class UpdateTestAttemptSchema(Schema):
    status = fields.Str(validate=validate.OneOf([s.value for s in TestAttemptStatus]))
    submitted_at = fields.DateTime(allow_none=True)
    expires_at = fields.DateTime(allow_none=True)
    raw_score = fields.Float(allow_none=True)
    final_score = fields.Float(allow_none=True)
