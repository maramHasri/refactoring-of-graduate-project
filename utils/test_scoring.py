"""Helpers for test total-score sync and auto point distribution."""

from decimal import Decimal, ROUND_HALF_UP

TWOPLACES = Decimal("0.01")


def distribute_points(target_total_score: Decimal, question_count: int) -> list[Decimal]:
    """
    Split ``target_total_score`` across ``question_count`` questions.

    Uses standard half-up rounding for the first N-1 questions; the last question
    receives the remainder so ``sum(points) == target_total_score`` exactly
    (at 2 decimal places).
    """
    if question_count < 0:
        raise ValueError("question_count must be >= 0")
    if question_count == 0:
        return []

    target = Decimal(target_total_score).quantize(TWOPLACES, rounding=ROUND_HALF_UP)
    if question_count == 1:
        return [target]

    base = (target / Decimal(question_count)).quantize(
        TWOPLACES, rounding=ROUND_HALF_UP
    )
    points = [base] * (question_count - 1)
    remainder = (target - (base * (question_count - 1))).quantize(TWOPLACES)
    points.append(remainder)
    return points


def sum_points(points_values) -> Decimal:
    total = Decimal("0")
    for value in points_values:
        total += Decimal(str(value or 0))
    return total.quantize(TWOPLACES)
