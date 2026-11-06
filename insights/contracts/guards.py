"""The no-rows guard. Run state, audit, SSE events and skill outputs must never hold row data.

Types already make rows unrepresentable in the contracts. This guard is the backstop for anything
that is still a plain dict: it refuses the key names that would carry rows and anything that is
not JSON. The end-to-end proof is the canary test (a planted value must never appear in state,
audit or events), added with the executor in S9.
"""

import json
from typing import Any

FORBIDDEN_KEYS = frozenset(
    {"rows", "row", "row_data", "rowset", "result_rows", "records", "data_rows", "cells", "data"}
)


class RowsLeakError(ValueError):
    """Something that looks like result data was about to enter state, audit or an event."""


def find_row_leaks(obj: Any, path: str = "$") -> list[str]:
    """Paths of every forbidden key found anywhere inside `obj`."""
    found: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            here = f"{path}.{key}"
            if isinstance(key, str) and key.lower() in FORBIDDEN_KEYS:
                found.append(here)
            found.extend(find_row_leaks(value, here))
    elif isinstance(obj, list | tuple):
        for index, item in enumerate(obj):
            found.extend(find_row_leaks(item, f"{path}[{index}]"))
    return found


def assert_no_rows(obj: Any, where: str) -> None:
    leaks = find_row_leaks(obj)
    if leaks:
        raise RowsLeakError(f"{where}: row-like data at {', '.join(leaks)}")


def assert_json_safe(obj: Any, where: str) -> None:
    """State must be JSON-serializable. NaN and infinity are refused as well."""
    try:
        json.dumps(obj, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{where}: not JSON-serializable: {exc}") from exc
