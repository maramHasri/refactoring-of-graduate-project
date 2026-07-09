from marshmallow import Schema, fields, validate

from utils.enums import MembershipRole, UserStatus


class SuspendInstitutionSchema(Schema):
    reason = fields.Str(required=True, validate=validate.Length(min=3, max=2000))


class SuspendUserSchema(Schema):
    reason = fields.Str(required=True, validate=validate.Length(min=3, max=2000))


class SuperAdminUsersListQuerySchema(Schema):
    page = fields.Int(load_default=1, validate=validate.Range(min=1))
    per_page = fields.Int(load_default=20, validate=validate.Range(min=1, max=100))
    role = fields.Str(
        allow_none=True,
        validate=validate.OneOf([r.value for r in MembershipRole] + ["SUPER_ADMIN"]),
    )
    institution_id = fields.Int(allow_none=True, validate=validate.Range(min=1))
    status = fields.Str(
        allow_none=True,
        validate=validate.OneOf([s.value for s in UserStatus]),
    )
    search = fields.Str(allow_none=True, validate=validate.Length(max=255))
