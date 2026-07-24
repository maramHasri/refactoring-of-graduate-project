"""Unit tests for auto score distribution helpers."""

from decimal import Decimal

from utils.test_scoring import distribute_points, sum_points


def test_distribute_points_even_split():
    points = distribute_points(Decimal("100"), 4)
    assert points == [
        Decimal("25.00"),
        Decimal("25.00"),
        Decimal("25.00"),
        Decimal("25.00"),
    ]
    assert sum_points(points) == Decimal("100.00")


def test_distribute_points_remainder_on_last_question():
    points = distribute_points(Decimal("100"), 3)
    assert points[:2] == [Decimal("33.33"), Decimal("33.33")]
    assert points[2] == Decimal("33.34")
    assert sum_points(points) == Decimal("100.00")


def test_distribute_points_single_question():
    points = distribute_points(Decimal("75.5"), 1)
    assert points == [Decimal("75.50")]


def test_distribute_points_zero_questions():
    assert distribute_points(Decimal("100"), 0) == []
