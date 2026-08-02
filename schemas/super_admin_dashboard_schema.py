from marshmallow import Schema, fields


class MostActiveOrganizationSchema(Schema):
    organization_id = fields.Int(required=True)
    organization_name = fields.Str(required=True)
    active_users = fields.Int(required=True)
    tests_count = fields.Int(required=True)
    attempts_count = fields.Int(required=True)


class ActivitySeriesAttemptSchema(Schema):
    month = fields.Str(required=True)
    count = fields.Int(required=True)


class ActivitySeriesSchema(Schema):
    period = fields.Str(required=True)
    granularity = fields.Str(required=True)
    attempts = fields.List(fields.Nested(ActivitySeriesAttemptSchema), required=True)


class SuperAdminDashboardSchema(Schema):
    users = fields.Dict(required=True)
    organizations = fields.Dict(required=True)
    content = fields.Dict(required=True)
    tests = fields.Dict(required=True)
    support_reports = fields.Dict(required=True)
    integrity_reports = fields.Dict(required=True)
    activity_series = fields.Nested(ActivitySeriesSchema, required=True)
