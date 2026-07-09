from marshmallow import Schema, fields


class TopicAnalyticsSchema(Schema):
    topic_id = fields.Int(allow_none=True)
    topic_name = fields.Str(required=True)
    performance = fields.Float(allow_none=True)
    mastery_percentage = fields.Float(allow_none=True)
    weighted_earned_points = fields.Float(required=True)
    weighted_possible_points = fields.Float(required=True)
    classification = fields.Str(required=True)


class CourseAnalyticsSchema(Schema):
    subject_id = fields.Int(required=True)
    subject_name = fields.Str(required=True)
    course_id = fields.Int(allow_none=True)
    course_name = fields.Str(allow_none=True)
    student = fields.Dict(keys=fields.Str(), values=fields.Raw())
    overall_performance = fields.Float(required=True)
    topics = fields.List(fields.Nested(TopicAnalyticsSchema), required=True)
    strengths = fields.List(fields.Nested(TopicAnalyticsSchema), required=True)
    weaknesses = fields.List(fields.Nested(TopicAnalyticsSchema), required=True)


class TestAnalyticsSchema(Schema):
    test_id = fields.Int(required=True)
    test_title = fields.Str(allow_none=True)
    final_score = fields.Float(required=True)
    percentage = fields.Float(required=True)
    attempt_id = fields.Int(required=True)
    topics = fields.List(fields.Nested(TopicAnalyticsSchema), required=True)
