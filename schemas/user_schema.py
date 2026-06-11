from marshmallow import Schema, fields, validate

from utils.enums import UserStatus


class UserSchema(Schema):
    id = fields.Int(dump_only=True)
    full_name = fields.Str(required=True)
    email = fields.Email(required=True)
    avatar_url = fields.Str(allow_none=True)
    phone_number = fields.Str(allow_none=True)
    user_status = fields.Str(dump_only=True)
    email_verified = fields.Bool(dump_only=True)
    is_superadmin = fields.Bool(dump_only=True)
    last_login_at = fields.DateTime(dump_only=True)
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class RegisterSchema(Schema):
    full_name = fields.Str(required=True, validate=validate.Length(min=2, max=255))
    email = fields.Email(required=True)
    password = fields.Str(required=True, validate=validate.Length(min=8), load_only=True)
    phone_number = fields.Str(allow_none=True, validate=validate.Length(max=20))


class LoginSchema(Schema):
    email = fields.Email(required=True)
    password = fields.Str(required=True, load_only=True)


class ResendOtpSchema(Schema):
    email = fields.Email(required=True)


# Legacy alias
ResendVerificationSchema = ResendOtpSchema


class UpdateUserSchema(Schema):
    full_name = fields.Str(validate=validate.Length(min=2, max=255))
    avatar_url = fields.Str(allow_none=True)
    phone_number = fields.Str(allow_none=True, validate=validate.Length(max=20))
    user_status = fields.Str(
        validate=validate.OneOf([s.value for s in UserStatus]),
    )
    email_verified = fields.Bool()
