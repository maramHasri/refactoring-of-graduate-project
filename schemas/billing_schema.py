from marshmallow import Schema, fields, validate

from utils.enums import (
    BillingCycle,
    PaymentStatus,
    SubscriptionStatus,
    WorkspaceSubscriptionStatus,
)


class PlanSchema(Schema):
    id = fields.Int(dump_only=True)
    name = fields.Str(required=True)
    slug = fields.Str(required=True)
    description = fields.Str(allow_none=True)
    price = fields.Decimal(required=True, places=2, as_string=True)
    billing_cycle = fields.Str(required=True)
    is_active = fields.Bool()
    created_at = fields.DateTime(dump_only=True)


class CreatePlanSchema(Schema):
    name = fields.Str(required=True, validate=validate.Length(min=1, max=100))
    slug = fields.Str(required=True, validate=validate.Length(min=1, max=255))
    description = fields.Str(allow_none=True)
    price = fields.Decimal(
        required=True,
        places=2,
        validate=validate.Range(min=0),
        as_string=True,
    )
    billing_cycle = fields.Str(
        required=True,
        validate=validate.OneOf([c.value for c in BillingCycle]),
    )
    is_active = fields.Bool(load_default=True)


class FeatureSchema(Schema):
    id = fields.Int(dump_only=True)
    key = fields.Str(required=True)
    name = fields.Str(required=True)
    description = fields.Str(allow_none=True)
    created_at = fields.DateTime(dump_only=True)


class CreateFeatureSchema(Schema):
    key = fields.Str(required=True, validate=validate.Length(min=1, max=150))
    name = fields.Str(required=True, validate=validate.Length(min=1, max=150))
    description = fields.Str(allow_none=True)


class PlanFeatureSchema(Schema):
    id = fields.Int(dump_only=True)
    plan_id = fields.Int(required=True)
    feature_id = fields.Int(required=True)
    enabled = fields.Bool()
    limit_value = fields.Int(allow_none=True)
    created_at = fields.DateTime(dump_only=True)


class CreatePlanFeatureSchema(Schema):
    plan_id = fields.Int(required=True)
    feature_id = fields.Int(required=True)
    enabled = fields.Bool(load_default=True)
    limit_value = fields.Int(allow_none=True)


class WorkspaceSubscriptionSchema(Schema):
    id = fields.Int(dump_only=True)
    workspace_id = fields.Int(required=True)
    plan_id = fields.Int(required=True)
    status = fields.Str(required=True)
    started_at = fields.DateTime(required=True)
    expires_at = fields.DateTime(allow_none=True)
    auto_renew = fields.Bool()
    created_at = fields.DateTime(dump_only=True)


class CreateWorkspaceSubscriptionSchema(Schema):
    workspace_id = fields.Int(required=True)
    plan_id = fields.Int(required=True)
    status = fields.Str(
        required=True,
        validate=validate.OneOf([s.value for s in WorkspaceSubscriptionStatus]),
    )
    started_at = fields.DateTime(required=True)
    expires_at = fields.DateTime(allow_none=True)
    auto_renew = fields.Bool(load_default=False)


class SubscriptionSchema(Schema):
    id = fields.Int(dump_only=True)
    workspace_id = fields.Int(required=True)
    plan_id = fields.Int(required=True)
    status = fields.Str()
    started_at = fields.DateTime(required=True)
    expires_at = fields.DateTime(allow_none=True)
    auto_renew = fields.Bool()
    created_at = fields.DateTime(dump_only=True)


class CreateSubscriptionSchema(Schema):
    workspace_id = fields.Int(required=True)
    plan_id = fields.Int(required=True)
    status = fields.Str(
        load_default=SubscriptionStatus.ACTIVE.value,
        validate=validate.OneOf([s.value for s in SubscriptionStatus]),
    )
    started_at = fields.DateTime(required=True)
    expires_at = fields.DateTime(allow_none=True)
    auto_renew = fields.Bool(load_default=False)


class PaymentSchema(Schema):
    id = fields.Int(dump_only=True)
    workspace_subscription_id = fields.Int(required=True)
    provider = fields.Str(allow_none=True)
    transaction_id = fields.Str(allow_none=True)
    amount = fields.Decimal(required=True, places=2, as_string=True)
    currency = fields.Str()
    status = fields.Str()
    request_payload = fields.Dict(allow_none=True)
    response_payload = fields.Dict(allow_none=True)
    created_at = fields.DateTime(dump_only=True)
    paid_at = fields.DateTime(allow_none=True)


class CreatePaymentSchema(Schema):
    workspace_subscription_id = fields.Int(required=True)
    provider = fields.Str(allow_none=True, validate=validate.Length(max=50))
    transaction_id = fields.Str(allow_none=True, validate=validate.Length(max=255))
    amount = fields.Decimal(
        required=True,
        places=2,
        validate=validate.Range(min=0),
        as_string=True,
    )
    currency = fields.Str(load_default="USD", validate=validate.Length(max=10))
    status = fields.Str(
        load_default=PaymentStatus.PENDING.value,
        validate=validate.OneOf([s.value for s in PaymentStatus]),
    )
    request_payload = fields.Dict(allow_none=True)
    response_payload = fields.Dict(allow_none=True)
    paid_at = fields.DateTime(allow_none=True)
