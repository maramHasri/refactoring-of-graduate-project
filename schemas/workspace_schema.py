from marshmallow import Schema, fields, validate

from utils.enums import (
    InviteStatus,
    MembershipRole,
    MembershipStatus,
    WorkspaceKind,
    WorkspaceStatus,
)


class WorkspaceSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)
    slug = fields.Str(required=True)
    kind = fields.Str(required=True)
    owner_user_id = fields.Int(required=True)
    status = fields.Str()
    subject_assignment_mode = fields.Str(allow_none=True)
    is_verified_by_superadmin = fields.Bool()
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class CreateWorkspaceSchema(Schema):
    """POST /workspaces — authenticated owner creates a workspace."""

    name = fields.Str(required=True, validate=validate.Length(min=2, max=255))
    slug = fields.Str(allow_none=True, validate=validate.Length(min=2, max=255))
    kind = fields.Str(
        required=True,
        validate=validate.OneOf([k.value for k in WorkspaceKind]),
    )


class UpdateWorkspaceSchema(Schema):
    name = fields.Str(validate=validate.Length(min=2, max=255))
    slug = fields.Str(validate=validate.Length(min=2, max=255))
    kind = fields.Str(validate=validate.OneOf([k.value for k in WorkspaceKind]))
    status = fields.Str(validate=validate.OneOf([s.value for s in WorkspaceStatus]))
    subject_assignment_mode = fields.Str(allow_none=True, validate=validate.Length(max=30))
    is_verified_by_superadmin = fields.Bool()


class MembershipSchema(Schema):
    id = fields.Int(dump_only=True)
    user_id = fields.Int(required=True)
    workspace_id = fields.Int(required=True)
    role = fields.Str(required=True)
    status = fields.Str()
    created_at = fields.DateTime(dump_only=True)
    joined_at = fields.DateTime(dump_only=True)


class CreateMembershipSchema(Schema):
    user_id = fields.Int(required=True)
    workspace_id = fields.Int(required=True)
    role = fields.Str(
        required=True,
        validate=validate.OneOf([r.value for r in MembershipRole]),
    )
    status = fields.Str(
        load_default=MembershipStatus.ACTIVE.value,
        validate=validate.OneOf([s.value for s in MembershipStatus]),
    )
    joined_at = fields.DateTime(allow_none=True)


class UpdateMembershipSchema(Schema):
    role = fields.Str(validate=validate.OneOf([r.value for r in MembershipRole]))
    status = fields.Str(validate=validate.OneOf([s.value for s in MembershipStatus]))


class WorkspaceInviteSchema(Schema):
    id = fields.Int(dump_only=True)
    workspace_id = fields.Int(required=True)
    email = fields.Email(required=True)
    assigned_role = fields.Str(required=True)
    status = fields.Str()
    expires_at = fields.DateTime(required=True)
    accepted_at = fields.DateTime(allow_none=True)
    invited_by_membership_id = fields.Int(allow_none=True)
    created_at = fields.DateTime(dump_only=True)


class CreateInviteSchema(Schema):
    """POST /invites — workspace from X-Workspace-Id header."""

    email = fields.Email(required=True)
    assigned_role = fields.Str(
        required=True,
        validate=validate.OneOf([r.value for r in MembershipRole]),
    )


class CreateWorkspaceInviteSchema(CreateInviteSchema):
    workspace_id = fields.Int(required=True)
    token = fields.Str(required=True, load_only=True)
    invited_by_membership_id = fields.Int(allow_none=True)
    expires_at = fields.DateTime(required=True)
    status = fields.Str(
        load_default=InviteStatus.PENDING.value,
        validate=validate.OneOf([s.value for s in InviteStatus]),
    )


class RegisterThroughInviteSchema(Schema):
    """POST /invites/{token}/register — email comes from invitation only."""

    full_name = fields.Str(required=True, validate=validate.Length(min=2, max=255))
    password = fields.Str(required=True, validate=validate.Length(min=8), load_only=True)


class AcceptWorkspaceInviteSchema(Schema):
    token = fields.Str(required=True)


class WorkspaceProfileSchema(Schema):
    id = fields.Int(dump_only=True)
    workspace_id = fields.Int(required=True)
    description = fields.Str(allow_none=True)
    country = fields.Str(allow_none=True, validate=validate.Length(max=120))
    city = fields.Str(allow_none=True, validate=validate.Length(max=120))
    logo = fields.Str(allow_none=True, validate=validate.Length(max=255))
    website_url = fields.Str(allow_none=True, validate=validate.Length(max=255))
    created_at = fields.DateTime(dump_only=True)
    updated_at = fields.DateTime(dump_only=True)


class CreateWorkspaceProfileSchema(Schema):
    workspace_id = fields.Int(required=True)
    description = fields.Str(allow_none=True)
    country = fields.Str(allow_none=True, validate=validate.Length(max=120))
    city = fields.Str(allow_none=True, validate=validate.Length(max=120))
    logo = fields.Str(allow_none=True, validate=validate.Length(max=255))
    website_url = fields.Str(allow_none=True, validate=validate.Length(max=255))


class UpdateWorkspaceProfileSchema(Schema):
    description = fields.Str(allow_none=True)
    country = fields.Str(allow_none=True, validate=validate.Length(max=120))
    city = fields.Str(allow_none=True, validate=validate.Length(max=120))
    logo = fields.Str(allow_none=True, validate=validate.Length(max=255))
    website_url = fields.Str(allow_none=True, validate=validate.Length(max=255))
