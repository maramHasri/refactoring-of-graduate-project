from marshmallow import Schema, fields, validate

from utils.enums import ReportCategory, ReportStatus


class CreateReportSchema(Schema):
    title = fields.Str(required=True, validate=validate.Length(min=3, max=255))
    description = fields.Str(required=True, validate=validate.Length(min=5, max=5000))
    category = fields.Str(
        required=True,
        validate=validate.OneOf([category.value for category in ReportCategory]),
    )


class ReportsListQuerySchema(Schema):
    page = fields.Int(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Int(load_default=20, validate=validate.Range(min=1, max=100))
    status = fields.Str(
        allow_none=True,
        validate=validate.OneOf([status.value for status in ReportStatus]),
    )
    category = fields.Str(
        allow_none=True,
        validate=validate.OneOf([category.value for category in ReportCategory]),
    )


class UpdateReportStatusSchema(Schema):
    status = fields.Str(
        required=True,
        validate=validate.OneOf([status.value for status in ReportStatus]),
    )
