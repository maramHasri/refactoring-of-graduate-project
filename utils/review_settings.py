"""Helpers for exam review_settings stored on Test.settings_config."""

from __future__ import annotations

import json


def parse_settings_config(value) -> dict:
    if not value:
        return {}
    if isinstance(value, dict):
        return value
    if isinstance(value, list):
        return {}
    try:
        parsed = json.loads(value)
    except (TypeError, json.JSONDecodeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def allow_review_after_grading(settings_config) -> bool:
    """
    Whether students may open graded attempt content for study/review.

    Controls educational content only (questions, answers, correct choices,
    feedback). Does not control score visibility, results lists, or analytics.
    """
    settings = parse_settings_config(settings_config)
    review_settings = settings.get("review_settings") or {}
    if not isinstance(review_settings, dict):
        return False
    return bool(review_settings.get("allow_review_after_grading", False))
