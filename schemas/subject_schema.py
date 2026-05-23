from marshmallow import Schema, fields, validate


class SubjectSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)
    workspace_id = fields.Int(required=True)
    code = fields.Str(allow_none=True)
    description = fields.Str(allow_none=True)
    created_by_membership_id = fields.Int(allow_none=True)
    created_at = fields.DateTime(dump_only=True)


class CreateSubjectSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    workspace_id = fields.Int(required=True)
    code = fields.Str(allow_none=True, validate=validate.Length(max=50))
    description = fields.Str(allow_none=True)
    created_by_membership_id = fields.Int(allow_none=True)


class UpdateSubjectSchema(Schema):
    name = fields.Str(validate=validate.Length(min=1, max=255))
    code = fields.Str(allow_none=True, validate=validate.Length(max=50))
    description = fields.Str(allow_none=True)


class MembershipSubjectSchema(Schema):
    id = fields.Int(dump_only=True)
    membership_id = fields.Int(required=True)
    subject_id = fields.Int(required=True)
    created_at = fields.DateTime(dump_only=True)


class CreateMembershipSubjectSchema(Schema):
    membership_id = fields.Int(required=True)
    subject_id = fields.Int(required=True)
