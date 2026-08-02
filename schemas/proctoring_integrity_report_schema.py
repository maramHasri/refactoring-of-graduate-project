"""Schemas for Proctoring Integrity Reports (not Support Reports)."""

from marshmallow import Schema, fields, validate

from schemas.app_timezone_fields import LocalDateTime
from utils.enums import ProctoringIntegrityReportStatus


class IntegrityReportsListQuerySchema(Schema):
    page = fields.Int(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Int(load_default=20, validate=validate.Range(min=1, max=100))
    status = fields.Str(
        allow_none=True,
        load_default=None,
        validate=validate.OneOf(
            [s.value for s in ProctoringIntegrityReportStatus]
        ),
    )
    test_id = fields.Int(allow_none=True, load_default=None)
    subject_id = fields.Int(allow_none=True, load_default=None)
    student_membership_id = fields.Int(allow_none=True, load_default=None)
    search = fields.Str(allow_none=True, load_default=None)
    date_from = LocalDateTime(allow_none=True, load_default=None)
    date_to = LocalDateTime(allow_none=True, load_default=None)


class ReviewIntegrityReportSchema(Schema):
    status = fields.Str(
        required=True,
        validate=validate.OneOf(
            [
                ProctoringIntegrityReportStatus.CONFIRMED.value,
                ProctoringIntegrityReportStatus.DISMISSED.value,
            ]
        ),
    )
    review_note = fields.Str(
        allow_none=True,
        load_default=None,
        validate=validate.Length(max=5000),
    )
