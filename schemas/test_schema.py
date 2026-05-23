from marshmallow import Schema, fields, validate

from utils.enums import AvailabilityTimeMode, TestAttemptStatus, TestStatus


class TestSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)
    slug = fields.Str(required=True)
    grading_mode = fields.Str(allow_none=True)
    created_by_membership_id = fields.Int(allow_none=True)
    status = fields.Str()
    availability_time_mode = fields.Str(allow_none=True)
    starts_at = fields.DateTime(allow_none=True)
    duration_minutes = fields.Int(allow_none=True)
    entry_window_minutes = fields.Int(allow_none=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class CreateTestSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    slug = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    grading_mode = fields.Str(allow_none=True, validate=validate.Length(max=50))
    created_by_membership_id = fields.Int(allow_none=True)
    status = fields.Str(
        load_default=TestStatus.ACTIVE.value,
        validate=validate.OneOf([s.value for s in TestStatus]),
    )
    availability_time_mode = fields.Str(
        allow_none=True,
        validate=validate.OneOf([m.value for m in AvailabilityTimeMode]),
    )
    starts_at = fields.DateTime(allow_none=True)
    duration_minutes = fields.Int(allow_none=True, validate=validate.Range(min=1))
    entry_window_minutes = fields.Int(allow_none=True, validate=validate.Range(min=0))


class UpdateTestSchema(Schema):
    name = fields.Str(validate=validate.Length(min=1, max=255))
    slug = fields.Str(validate=validate.Length(min=1, max=255))
    grading_mode = fields.Str(allow_none=True, validate=validate.Length(max=50))
    status = fields.Str(validate=validate.OneOf([s.value for s in TestStatus]))
    availability_time_mode = fields.Str(
        allow_none=True,
        validate=validate.OneOf([m.value for m in AvailabilityTimeMode]),
    )
    starts_at = fields.DateTime(allow_none=True)
    duration_minutes = fields.Int(allow_none=True, validate=validate.Range(min=1))
    entry_window_minutes = fields.Int(allow_none=True, validate=validate.Range(min=0))


class TestAttemptSchema(Schema):
    id = fields.Int(dump_only=True)
    student_membership_id = fields.Int(required=True)
    test_id = fields.Int(required=True)
    user_id = fields.Int(required=True)
    status = fields.Str()
    started_at = fields.DateTime(required=True)
    submitted_at = fields.DateTime(allow_none=True)
    expires_at = fields.DateTime(allow_none=True)
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
