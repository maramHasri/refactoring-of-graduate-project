from marshmallow import Schema, fields, pre_load, validate

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
    country = fields.Str(allow_none=True, validate=validate.Length(max=120))
    city = fields.Str(allow_none=True, validate=validate.Length(max=120))
    website_url = fields.Str(allow_none=True, validate=validate.Length(max=255))
    description = fields.Str(allow_none=True)


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


class VerifyOtpSchema(Schema):
    email = fields.Email(required=True)
    otp = fields.Str(required=True, validate=validate.Regexp(r"^\d{6}$"))

    @pre_load
    def normalize_otp(self, data, **kwargs):
        if isinstance(data, dict) and "otp" in data:
            raw = data["otp"]
            if isinstance(raw, int):
                data["otp"] = f"{raw:06d}"
            else:
                data["otp"] = str(raw).strip()
        return data


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
