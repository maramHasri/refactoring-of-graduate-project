from marshmallow import Schema, fields, validate


class CreateStudentGroupSchema(Schema):
    """POST /subjects/{subjectId}/groups"""

    name = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    description = fields.Str(allow_none=True)


class UpdateStudentGroupSchema(Schema):
    """PUT /groups/{groupId}"""

    name = fields.Str(validate=validate.Length(min=1, max=255))
    description = fields.Str(allow_none=True)


class AddStudentGroupMembersSchema(Schema):
    """POST /groups/{groupId}/members"""

    student_ids = fields.List(
        fields.Int(validate=validate.Range(min=1)),
        required=True,
        validate=validate.Length(min=1),
    )
