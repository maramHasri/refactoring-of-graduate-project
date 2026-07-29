from marshmallow import Schema, fields, pre_load, validates_schema, validate, ValidationError

from schemas.app_timezone_fields import LocalDateTime
from schemas.question_schema import QuestionChoiceInputSchema
from utils.enums import (
    AvailabilityTimeMode,
    Difficulty,
    TestAttemptStatus,
    TestQuestionSourceType,
    TestStatus,
)
from utils.messages import Messages


class TestSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)
    slug = fields.Str(required=True)
    description = fields.Str(allow_none=True)
    subject_id = fields.Int(required=True)
    total_score = fields.Float(allow_none=True)
    target_total_score = fields.Float(allow_none=True)
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


class TestsListQuerySchema(Schema):
    """GET /tests | GET /tests/my — paginated teacher test list."""

    page = fields.Int(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Int(load_default=20, validate=validate.Range(min=1, max=100))
    include_archived = fields.Bool(load_default=False)


class CreateTestSchema(Schema):
    """Step 1 exam / survey creation payload from the UI."""

    name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    description = fields.Str(allow_none=True)
    subject_id = fields.Int(required=True)
    availability_time_mode = fields.Str(
        allow_none=True,
        validate=validate.OneOf([m.value for m in AvailabilityTimeMode]),
    )
    # No load_default=30 — Survey must stay null; exams default in TestService.
    duration_minutes = fields.Int(allow_none=True, validate=validate.Range(min=1))
    closed_at = LocalDateTime(allow_none=True)
    total_score = fields.Float(
        load_default=100,
        validate=validate.Range(min=0),
    )
    passing_score = fields.Float(
        load_default=50,
        validate=validate.Range(min=0),
    )
    auto_distribute_scores = fields.Bool(load_default=False)

    @validates_schema
    def validate_survey_or_exam_fields(self, data, **kwargs):
        mode = (data.get("availability_time_mode") or "").upper()
        if mode == AvailabilityTimeMode.SURVEY.value:
            if data.get("closed_at") is None:
                raise ValidationError(
                    Messages.SURVEY_CLOSED_AT_IS_REQUIRED, field_name="closed_at"
                )
            if data.get("duration_minutes") is not None:
                raise ValidationError(
                    Messages.SURVEY_DURATION_IS_NOT_ALLOWED,
                    field_name="duration_minutes",
                )


class UpdateTestSchema(Schema):
    name = fields.Str(validate=validate.Length(min=1, max=255))
    slug = fields.Str(validate=validate.Length(min=1, max=255))
    description = fields.Str(allow_none=True)
    total_score = fields.Float(allow_none=True, validate=validate.Range(min=0))
    passing_score = fields.Float(allow_none=True, validate=validate.Range(min=0))
    auto_distribute_scores = fields.Bool()
    settings_config = fields.Dict(allow_none=True)
    status = fields.Str(validate=validate.OneOf([s.value for s in TestStatus]))
    availability_time_mode = fields.Str(
        allow_none=True,
        validate=validate.OneOf([m.value for m in AvailabilityTimeMode]),
    )
    starts_at = LocalDateTime(allow_none=True)
    duration_minutes = fields.Int(allow_none=True, validate=validate.Range(min=1))
    entry_window_minutes = fields.Int(allow_none=True, validate=validate.Range(min=0))
    closed_at = LocalDateTime(allow_none=True)


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


class ManualTestQuestionItemSchema(Schema):
    type_code = fields.Str(required=True, validate=validate.Length(min=2, max=50))
    body = fields.Str(required=True, validate=validate.Length(min=1))
    image_path = fields.Str(allow_none=True, validate=validate.Length(max=512))
    explanation = fields.Str(allow_none=True)
    points = fields.Float(allow_none=True, validate=validate.Range(min=0))
    difficulty = fields.Str(
        allow_none=True,
        validate=validate.OneOf([d.value for d in Difficulty]),
    )
    topic_id = fields.Int(required=True, validate=validate.Range(min=1))
    choices = fields.List(
        fields.Nested(QuestionChoiceInputSchema),
        load_default=list,
    )


class AddManualQuestionsToTestSchema(Schema):
    questions = fields.List(
        fields.Nested(ManualTestQuestionItemSchema),
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
    topic_ids = fields.List(
        fields.Int(validate=validate.Range(min=1)),
        required=True,
        validate=validate.Length(min=1),
    )
    count = fields.Int(required=True, validate=validate.Range(min=1, max=50))
    type_code = fields.Str(load_default="MCQ", validate=validate.Length(min=2, max=50))
    difficulty = fields.Str(
        allow_none=True,
        validate=validate.OneOf(["EASY", "MEDIUM", "HARD"]),
    )
    learning_objectives = fields.List(
        fields.Str(validate=validate.Length(min=1)), load_default=list
    )
    additional_instructions = fields.Str(allow_none=True)


class ImportAIQuestionsSchema(Schema):
    request_id = fields.Int(required=True, validate=validate.Range(min=1))
    question_ids = fields.List(
        fields.Int(validate=validate.Range(min=1)),
        required=True,
        validate=validate.Length(min=1),
    )


class AssignStudentsToTestSchema(Schema):
    student_membership_ids = fields.List(
        fields.Int(validate=validate.Range(min=1)),
        load_default=list,
    )
    group_ids = fields.List(
        fields.Int(validate=validate.Range(min=1)),
        load_default=list,
    )

    @validates_schema
    def require_students_or_groups(self, data, **kwargs):
        student_ids = data.get("student_membership_ids") or []
        group_ids = data.get("group_ids") or []
        if not student_ids and not group_ids:
            raise ValidationError(
                Messages.AT_LEAST_ONE_OF_STUDENT_MEMBERSHIP_IDS_OR_GROUP_IDS_IS_REQUIRED
            )


class UpdateTestQuestionSchema(Schema):
    """PATCH /tests/{test_id}/questions/{test_question_id} — partial snapshot update."""

    type_code = fields.Str(validate=validate.Length(min=2, max=50))
    body = fields.Str(validate=validate.Length(min=1))
    image_path = fields.Str(allow_none=True, validate=validate.Length(max=512))
    remove_image = fields.Bool(load_default=False)
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
    termination_reason = fields.Str(allow_none=True)
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
