from marshmallow import Schema, fields


class MostActiveOrganizationSchema(Schema):
    organization_id = fields.Int(required=True)
    organization_name = fields.Str(required=True)
    active_users = fields.Int(required=True)
    tests_count = fields.Int(required=True)
    attempts_count = fields.Int(required=True)


class SuperAdminDashboardSchema(Schema):
    users = fields.Dict(required=True)
    organizations = fields.Dict(required=True)
    content = fields.Dict(required=True)
    tests = fields.Dict(required=True)
    reports = fields.Dict(required=True)
