from marshmallow import Schema, fields, validate


class RejectInstitutionSchema(Schema):
    reason = fields.Str(required=True, validate=validate.Length(min=3, max=2000))
