"""
Domain validation for unified question creation by type_code.

Keeps rules out of routes/services so new types can be registered in one place.
"""

from utils.messages import Messages
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
        raise ValidationError(Messages.UNSUPPORTED_TYPE_CODE_ALLOWED_JOIN_SORTED_SUPPORTED_TYPE_CODES.format(join_sorted_supported_type_codes=', '.join(sorted(SUPPORTED_TYPE_CODES))))

    choice_list = choices or []

    if normalized in _NO_CHOICES:
        if choice_list:
            raise ValidationError(Messages.ESSAY_QUESTIONS_MUST_NOT_INCLUDE_CHOICES)
        return normalized

    if normalized in _CHOICE_REQUIRED and not choice_list:
        raise ValidationError(Messages.NORMALIZED_QUESTIONS_REQUIRE_AT_LEAST_ONE_CHOICE.format(normalized=normalized))

    _validate_choice_rows(choice_list)

    if normalized == "TRUE_FALSE":
        if len(choice_list) != 2:
            raise ValidationError(Messages.TRUE_FALSE_QUESTIONS_MUST_HAVE_EXACTLY_TWO_CHOICES)
        correct = sum(1 for c in choice_list if c.get("is_correct"))
        if correct != 1:
            raise ValidationError(Messages.TRUE_FALSE_QUESTIONS_MUST_HAVE_EXACTLY_ONE_CORRECT_CHOICE)

    elif normalized == "MCQ":
        correct = sum(1 for c in choice_list if c.get("is_correct"))
        if correct != 1:
            raise ValidationError(Messages.MCQ_QUESTIONS_MUST_HAVE_EXACTLY_ONE_CORRECT_CHOICE)
        if len(choice_list) < 2:
            raise ValidationError(Messages.MCQ_QUESTIONS_MUST_HAVE_AT_LEAST_TWO_CHOICES)

    elif normalized == "MULTI_SELECT":
        correct = sum(1 for c in choice_list if c.get("is_correct"))
        if correct < 1:
            raise ValidationError(
                Messages.MULTI_SELECT_QUESTIONS_MUST_HAVE_AT_LEAST_ONE_CORRECT_CHOICE
            )
        if len(choice_list) < 2:
            raise ValidationError(
                Messages.MULTI_SELECT_QUESTIONS_MUST_HAVE_AT_LEAST_TWO_CHOICES
            )

    return normalized


def _validate_choice_rows(choices: list[dict]) -> None:
    for idx, choice in enumerate(choices):
        body = (choice.get("body") or "").strip()
        if not body:
            raise ValidationError(Messages.CHOICE_AT_INDEX_IDX_MUST_HAVE_A_NON_EMPTY_BODY.format(idx=idx))
        if "is_correct" not in choice:
            raise ValidationError(Messages.CHOICE_AT_INDEX_IDX_MUST_INCLUDE_IS_CORRECT.format(idx=idx))
