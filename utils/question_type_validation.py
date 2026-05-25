"""
Domain validation for unified question creation by type_code.

Keeps rules out of routes/services so new types can be registered in one place.
"""
from service.exceptions import ValidationError

SUPPORTED_TYPE_CODES = frozenset({"MCQ", "TRUE_FALSE", "MULTI_SELECT", "ESSAY"})

_CHOICE_REQUIRED = frozenset({"MCQ", "TRUE_FALSE", "MULTI_SELECT"})
_NO_CHOICES = frozenset({"ESSAY"})


def normalize_type_code(type_code: str) -> str:
    return (type_code or "").strip().upper().replace("-", "_")


def validate_question_create_payload(*, type_code: str, choices: list[dict] | None) -> str:
    """
    Validate request body for POST /question-banks/{id}/questions.
    Returns normalized type_code.
    """
    normalized = normalize_type_code(type_code)
    if normalized not in SUPPORTED_TYPE_CODES:
        raise ValidationError(
            f"Unsupported type_code. Allowed: {', '.join(sorted(SUPPORTED_TYPE_CODES))}"
        )

    choice_list = choices or []

    if normalized in _NO_CHOICES:
        if choice_list:
            raise ValidationError("ESSAY questions must not include choices")
        return normalized

    if normalized in _CHOICE_REQUIRED and not choice_list:
        raise ValidationError(f"{normalized} questions require at least one choice")

    _validate_choice_rows(choice_list)

    if normalized == "TRUE_FALSE":
        if len(choice_list) != 2:
            raise ValidationError("TRUE_FALSE questions must have exactly two choices")
        correct = sum(1 for c in choice_list if c.get("is_correct"))
        if correct != 1:
            raise ValidationError("TRUE_FALSE questions must have exactly one correct choice")

    elif normalized == "MCQ":
        correct = sum(1 for c in choice_list if c.get("is_correct"))
        if correct != 1:
            raise ValidationError("MCQ questions must have exactly one correct choice")
        if len(choice_list) < 2:
            raise ValidationError("MCQ questions must have at least two choices")

    elif normalized == "MULTI_SELECT":
        correct = sum(1 for c in choice_list if c.get("is_correct"))
        if correct < 1:
            raise ValidationError(
                "MULTI_SELECT questions must have at least one correct choice"
            )
        if len(choice_list) < 2:
            raise ValidationError(
                "MULTI_SELECT questions must have at least two choices"
            )

    return normalized


def _validate_choice_rows(choices: list[dict]) -> None:
    for idx, choice in enumerate(choices):
        body = (choice.get("body") or "").strip()
        if not body:
            raise ValidationError(f"Choice at index {idx} must have a non-empty body")
        if "is_correct" not in choice:
            raise ValidationError(f"Choice at index {idx} must include is_correct")
