from datetime import datetime

from marshmallow import fields

from utils.app_timezone import parse_local_datetime


class LocalDateTime(fields.Field):
    """Deserialize naive local datetimes into app-timezone-aware datetimes."""

    def _deserialize(self, value, attr, data, **kwargs):
        if value is None:
            return None
        try:
            return parse_local_datetime(value)
        except (TypeError, ValueError) as exc:
            raise fields.ValidationError("Invalid local datetime format") from exc

    def _serialize(self, value, attr, obj, **kwargs):
        if value is None:
            return None
        if isinstance(value, datetime):
            from utils.app_timezone import format_local_datetime

            return format_local_datetime(value)
        return value
