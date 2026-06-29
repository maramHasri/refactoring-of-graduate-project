"""
Teacher-friendly exam CSV import parser.

Spreadsheet columns only — no JSON inside cells.
Legacy format (type_code, body, choices-as-JSON) is still detected for backward compatibility.
"""
from __future__ import annotations

import csv
import json
import logging
import re
from dataclasses import dataclass
from io import StringIO
from typing import Any

from repositories.topic_repository import TopicRepository
from service.exceptions import ValidationError
from utils.question_type_validation import normalize_type_code

logger = logging.getLogger(__name__)

SUPPORTED_TYPES = frozenset({"MCQ", "TRUE_FALSE", "MULTI_SELECT", "ESSAY"})
VALID_DIFFICULTIES = frozenset({"EASY", "MEDIUM", "HARD"})
CHOICE_HEADERS = ("Choice A", "Choice B", "Choice C", "Choice D", "Choice E", "Choice F")
LETTER_TO_INDEX = {chr(ord("A") + i): i for i in range(6)}

TEACHER_HEADERS = (
    "Question Type",
    "Question",
    "Explanation",
    "Difficulty",
    "Points",
    "Topic ID",
    *CHOICE_HEADERS,
    "Correct Answers",
)


@dataclass
class ParsedCsvRow:
    row_number: int
    payload: dict[str, Any] | None = None
    error: str | None = None


def read_csv_text(raw_bytes: bytes) -> str:
    if not raw_bytes:
        raise ValidationError("Uploaded CSV file is empty")
    return raw_bytes.decode("utf-8-sig")


def parse_exam_csv(
    text: str,
    *,
    subject_id: int,
    workspace_id: int,
) -> tuple[list[dict], list[dict]]:
    """
    Parse CSV text into question payloads and row-level failures.

    Returns (payloads, failed_rows) where failed_rows items are:
      {"row": int, "error": str}
    """
    reader = csv.DictReader(StringIO(text))
    if not reader.fieldnames:
        raise ValidationError("CSV headers are required")

    fieldnames = [name.strip() for name in reader.fieldnames if name]
    rows = list(reader)
    if not rows:
        raise ValidationError("CSV file must contain at least one question row")

    logger.info("[CSV Import] Reading file... %s data row(s) found", len(rows))

    lowered = {_normalize_key(name) for name in fieldnames}
    use_teacher = "question type" in lowered
    use_legacy = "type_code" in lowered and "body" in lowered

    if not use_teacher and not use_legacy:
        raise ValidationError(
            "Unrecognized CSV format. Download the template from GET /templates/exam-questions-csv "
            "or use legacy headers: type_code, body, choices"
        )

    topics = TopicRepository()
    parsed: list[ParsedCsvRow] = []

    for index, row in enumerate(rows):
        row_number = index + 2  # 1-based, +1 for header row
        normalized_row = {_normalize_key(k): (v or "").strip() for k, v in row.items() if k}
        if _is_blank_row(normalized_row):
            logger.info("[CSV Import] Row %s skipped (blank row)", row_number)
            continue

        try:
            if use_teacher:
                payload = _parse_teacher_row(
                    normalized_row,
                    row_number=row_number,
                    subject_id=subject_id,
                    workspace_id=workspace_id,
                    topics=topics,
                )
            else:
                payload = _parse_legacy_row(normalized_row, row_number=row_number)
            parsed.append(ParsedCsvRow(row_number=row_number, payload=payload))
            logger.info("[CSV Import] Row %s parsed successfully", row_number)
        except ValidationError as exc:
            message = str(exc.message) if hasattr(exc, "message") else str(exc)
            parsed.append(ParsedCsvRow(row_number=row_number, error=message))
            logger.warning("[CSV Import] Row %s invalid: %s", row_number, message)

    payloads = [item.payload for item in parsed if item.payload]
    failed_rows = [
        {"row": item.row_number, "error": item.error}
        for item in parsed
        if item.error
    ]

    if not payloads and failed_rows:
        raise ValidationError(
            f"All {len(failed_rows)} row(s) failed validation. "
            f"First error (row {failed_rows[0]['row']}): {failed_rows[0]['error']}"
        )
    if not payloads:
        raise ValidationError("CSV file must contain at least one non-empty question row")

    return payloads, failed_rows


def _is_legacy_format(fieldnames: list[str]) -> bool:
    lowered = {_normalize_key(name) for name in fieldnames}
    return "type_code" in lowered and "body" in lowered


def _is_teacher_format(fieldnames: list[str]) -> bool:
    lowered = {_normalize_key(name) for name in fieldnames}
    return "question type" in lowered or (
        "question" in lowered and "choice a" in lowered
    )


def _normalize_key(key: str) -> str:
    return re.sub(r"\s+", " ", (key or "").strip()).lower()


def _is_blank_row(row: dict[str, str]) -> bool:
    return not any(value for value in row.values())


def _cell(row: dict[str, str], *keys: str) -> str:
    for key in keys:
        value = row.get(_normalize_key(key), "")
        if value:
            return value.strip()
    return ""


def _parse_legacy_row(row: dict[str, str], *, row_number: int) -> dict:
    type_code = _cell(row, "type_code")
    body = _cell(row, "body")
    if not type_code or not body:
        raise ValidationError(f"Row {row_number}: type_code and body are required")

    choices_raw = _cell(row, "choices")
    choices: list[dict] = []
    if choices_raw:
        try:
            choices = json.loads(choices_raw)
        except json.JSONDecodeError as exc:
            raise ValidationError(
                f"Row {row_number}: choices must be valid JSON array"
            ) from exc

    return {
        "type_code": type_code,
        "body": body,
        "explanation": _cell(row, "explanation") or None,
        "points": _cell(row, "points") or None,
        "difficulty": _cell(row, "difficulty") or None,
        "topic_id": _cell(row, "topic_id") or None,
        "choices": choices,
    }


def _parse_teacher_row(
    row: dict[str, str],
    *,
    row_number: int,
    subject_id: int,
    workspace_id: int,
    topics: TopicRepository,
) -> dict:
    raw_type = _cell(row, "Question Type", "question type")
    body = _cell(row, "Question", "question")
    if not raw_type:
        raise ValidationError(f"Row {row_number}: Question Type is required")
    if not body:
        raise ValidationError(f"Row {row_number}: Question text is required")

    type_code = normalize_type_code(raw_type)
    if type_code not in SUPPORTED_TYPES:
        raise ValidationError(
            f"Row {row_number}: invalid question type '{raw_type}'. "
            f"Allowed: MCQ, TRUE_FALSE, MULTI_SELECT, ESSAY"
        )

    difficulty_raw = _cell(row, "Difficulty", "difficulty")
    difficulty = None
    if difficulty_raw:
        difficulty = difficulty_raw.strip().upper()
        if difficulty not in VALID_DIFFICULTIES:
            raise ValidationError(
                f"Row {row_number}: invalid difficulty '{difficulty_raw}'. "
                "Allowed: EASY, MEDIUM, HARD"
            )

    points_raw = _cell(row, "Points", "points")
    points = None
    if points_raw:
        try:
            points = float(points_raw)
        except ValueError as exc:
            raise ValidationError(
                f"Row {row_number}: Points must be a number"
            ) from exc
        if points <= 0:
            raise ValidationError(f"Row {row_number}: Points must be greater than 0")

    topic_id_raw = _cell(row, "Topic ID", "topic id")
    topic_id = None
    if topic_id_raw:
        try:
            topic_id = int(topic_id_raw)
        except ValueError as exc:
            raise ValidationError(
                f"Row {row_number}: Topic ID must be a valid integer"
            ) from exc
        if topic_id <= 0:
            raise ValidationError(f"Row {row_number}: Topic ID must be positive")
        topic = topics.get_in_subject(topic_id, subject_id=subject_id, workspace_id=workspace_id)
        if not topic:
            raise ValidationError(
                f"Row {row_number}: Topic ID {topic_id} does not belong to the exam subject"
            )

    choice_texts = [_cell(row, header) for header in CHOICE_HEADERS]
    correct_raw = _cell(row, "Correct Answers", "correct answers").upper().replace(",", "")
    correct_letters = _parse_correct_letters(correct_raw, row_number=row_number)

    if type_code == "ESSAY":
        if correct_raw:
            raise ValidationError(
                f"Row {row_number}: ESSAY questions must leave Correct Answers empty"
            )
        return {
            "type_code": type_code,
            "body": body,
            "explanation": _cell(row, "Explanation", "explanation") or None,
            "points": points,
            "difficulty": difficulty,
            "topic_id": topic_id,
            "choices": [],
        }

    choices = _build_choices(
        choice_texts,
        correct_letters=correct_letters,
        type_code=type_code,
        row_number=row_number,
    )

    return {
        "type_code": type_code,
        "body": body,
        "explanation": _cell(row, "Explanation", "explanation") or None,
        "points": points,
        "difficulty": difficulty,
        "topic_id": topic_id,
        "choices": choices,
    }


def _parse_correct_letters(raw: str, *, row_number: int) -> list[str]:
    if not raw:
        return []
    letters = list(raw.replace(" ", ""))
    if not letters:
        return []

    invalid = [letter for letter in letters if letter not in LETTER_TO_INDEX]
    if invalid:
        raise ValidationError(
            f"Row {row_number}: invalid correct answer letter(s): "
            f"{', '.join(sorted(set(invalid)))}. Use A-F only"
        )

    if len(letters) != len(set(letters)):
        duplicates = sorted({letter for letter in letters if letters.count(letter) > 1})
        raise ValidationError(
            f"Row {row_number}: duplicate correct answer letter(s): "
            f"{', '.join(duplicates)}"
        )
    return letters


def _build_choices(
    choice_texts: list[str],
    *,
    correct_letters: list[str],
    type_code: str,
    row_number: int,
) -> list[dict]:
    filled_indices = [index for index, text in enumerate(choice_texts) if text]
    if not filled_indices and type_code != "ESSAY":
        raise ValidationError(f"Row {row_number}: at least one choice is required")

    for letter in correct_letters:
        index = LETTER_TO_INDEX[letter]
        if not choice_texts[index]:
            raise ValidationError(
                f'Row {row_number}: correct answer "{letter}" references an empty choice'
            )

    if type_code == "TRUE_FALSE":
        if any(choice_texts[2:]):
            raise ValidationError(
                f"Row {row_number}: TRUE_FALSE questions may only use Choice A and Choice B"
            )
        if len(correct_letters) != 1 or correct_letters[0] not in ("A", "B"):
            raise ValidationError(
                f"Row {row_number}: TRUE_FALSE questions must have exactly one correct "
                "answer: A or B"
            )
    elif type_code == "MCQ":
        if len(correct_letters) != 1:
            raise ValidationError(
                f"Row {row_number}: MCQ questions must have exactly one correct answer"
            )
    elif type_code == "MULTI_SELECT":
        if len(correct_letters) < 1:
            raise ValidationError(
                f"Row {row_number}: MULTI_SELECT questions must have at least one correct answer"
            )

    correct_indices = {LETTER_TO_INDEX[letter] for letter in correct_letters}
    choices: list[dict] = []
    for index in filled_indices:
        choices.append(
            {
                "body": choice_texts[index],
                "is_correct": index in correct_indices,
                "order_index": index,
            }
        )
    return choices
