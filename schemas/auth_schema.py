from marshmallow import Schema, fields, validate

from utils.enums import WorkspaceKind


class RegisterOwnerSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8), load_only=True)
    full_name = fields.Str(required=True, validate=validate.Length(min=2, max=255))
    workspace_name = fields.Str(required=True, validate=validate.Length(min=2, max=255))
    workspace_kind = fields.Str(
        required=True,
        validate=validate.OneOf([k.value for k in WorkspaceKind]),
    )
    slug = fields.Str(allow_none=True)
    phone_number = fields.Str(allow_none=True, validate=validate.Length(max=20))


class RegisterStudentSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8), load_only=True)
    full_name = fields.Str(required=True, validate=validate.Length(min=2, max=255))
    join_code = fields.Str(required=True, validate=validate.Length(min=4, max=20))
    phone_number = fields.Str(allow_none=True, validate=validate.Length(max=20))


class SuperAdminLoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, load_only=True)


class RefreshTokenSchema(Schema):
    refresh_token = fields.Str(required=True)


class VerifyEmailSchema(Schema):
    token = fields.Str(required=True)


class ForgotPasswordSchema(Schema):
    email = fields.Email(required=True)


class ResetPasswordSchema(Schema):
    token = fields.Str(required=True)
    new_password = fields.Str(required=True, validate=validate.Length(min=8), load_only=True)


class ChangePasswordSchema(Schema):
    current_password = fields.Str(required=True, load_only=True)
    new_password = fields.Str(required=True, validate=validate.Length(min=8), load_only=True)


class JoinWithCodeSchema(Schema):
    join_code = fields.Str(required=True, validate=validate.Length(min=4, max=20))
