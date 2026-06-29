"""Percentage-to-integer allocation using the largest-remainder method."""


def distribute_by_percentages(total: int, weights: dict[str, int]) -> dict[str, int]:
    """
    Split `total` across keys proportional to integer weights that must sum to 100.

    Example: total=20, weights={"a": 30, "b": 50, "c": 20} -> {a: 6, b: 10, c: 4}
    """
    if total < 0:
        raise ValueError("total must be non-negative")
    if not weights:
        return {}
    weight_sum = sum(weights.values())
    if weight_sum != 100:
        raise ValueError(f"weights must sum to 100 (got {weight_sum})")
    if total == 0:
        return {key: 0 for key in weights}

    raw = {key: total * weight / 100.0 for key, weight in weights.items()}
    allocated = {key: int(raw[key]) for key in weights}
    remainder = total - sum(allocated.values())
    if remainder > 0:
        order = sorted(
            weights.keys(),
            key=lambda key: raw[key] - allocated[key],
            reverse=True,
        )
        for index in range(remainder):
            allocated[order[index % len(order)]] += 1
    return allocated
