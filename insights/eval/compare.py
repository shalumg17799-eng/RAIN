"""Result-set comparison: order-insensitive rows, numeric tolerance, never SQL text equality."""

import datetime as dt
import decimal
import math
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

MAX_ROWS = 5000


@dataclass(frozen=True)
class Comparison:
    match: bool
    reason: str
    expected_rows: int
    actual_rows: int


def _normalize(value: Any) -> Any:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int | float):
        return float(value)
    if isinstance(value, decimal.Decimal):
        return float(value)
    if isinstance(value, dt.datetime | dt.date | dt.time):
        return value.isoformat()
    if isinstance(value, str):
        text = value.strip()
        looks_numeric = text and text.replace(".", "", 1).replace("-", "", 1).isdigit()
        try:
            return float(text) if looks_numeric else text
        except ValueError:
            return text
    return str(value)


def _cell_matches(expected: Any, actual: Any, rel_tol: float, abs_tol: float) -> bool:
    if expected is None or actual is None:
        return expected is None and actual is None
    if isinstance(expected, float) and isinstance(actual, float):
        return math.isclose(expected, actual, rel_tol=rel_tol, abs_tol=abs_tol)
    if isinstance(expected, bool) or isinstance(actual, bool):
        return expected == actual
    return expected == actual


def _row_matches(
    expected: Sequence[Any], actual: Sequence[Any], rel_tol: float, abs_tol: float
) -> bool:
    if len(expected) != len(actual):
        return False
    return all(_cell_matches(e, a, rel_tol, abs_tol) for e, a in zip(expected, actual, strict=True))


def compare_results(
    expected: Sequence[Sequence[Any]],
    actual: Sequence[Sequence[Any]],
    *,
    rel_tol: float = 1e-6,
    abs_tol: float = 1e-9,
) -> Comparison:
    """Every expected row must be matched by a distinct actual row (and nothing left over)."""
    exp = [tuple(_normalize(v) for v in row) for row in expected][:MAX_ROWS]
    act = [tuple(_normalize(v) for v in row) for row in actual][:MAX_ROWS]
    counts = (len(exp), len(act))
    if len(exp) != len(act):
        return Comparison(False, f"row count differs: expected {len(exp)}, got {len(act)}", *counts)
    if exp and act and len(exp[0]) != len(act[0]):
        reason = f"column count differs: expected {len(exp[0])}, got {len(act[0])}"
        return Comparison(False, reason, *counts)
    unmatched = list(act)
    for row in exp:
        index = next(
            (i for i, c in enumerate(unmatched) if _row_matches(row, c, rel_tol, abs_tol)), None
        )
        if index is None:
            return Comparison(False, "a row in the expected result has no match", *counts)
        unmatched.pop(index)
    return Comparison(True, "match", *counts)
