"""Proctoring REST API schemas."""
from marshmallow import Schema, fields, validate

from utils.enums import ProctoringViolationStatus


class StartProctoringSessionSchema(Schema):
    device_metadata = fields.Dict(allow_none=True)
    browser_metadata = fields.Dict(allow_none=True)


class IngestProctoringEventSchema(Schema):
    event_type = fields.Str(required=True, validate=validate.Length(min=1, max=50))
    payload = fields.Dict(allow_none=True)
    occurred_at = fields.DateTime(allow_none=True)


class ReviewViolationSchema(Schema):
    status = fields.Str(
        required=True,
        validate=validate.OneOf(
            [
                ProctoringViolationStatus.REVIEWED.value,
                ProctoringViolationStatus.DISMISSED.value,
                ProctoringViolationStatus.CONFIRMED.value,
            ]
        ),
    )
    review_notes = fields.Str(allow_none=True)
