"""Reference resolution for agent step inputs. Strict: a missing reference is an error, not None.

`$.input.x`, `$.steps.<id>.output.y` and the engine-owned `$.refine.z` are plain paths. There are no
expressions, indexes or defaults, so the YAML cannot carry logic.
"""

import copy
from collections.abc import Mapping
from typing import Any


class RefError(LookupError):
    """A reference does not resolve."""


def resolve_ref(ref: str, root: Mapping[str, Any]) -> Any:
    """Walk `ref` through `root`. A present-but-null value is fine; an absent key is not."""
    if not ref.startswith("$."):
        raise RefError(f"{ref!r} is not a reference")
    node: Any = root
    walked = "$"
    for part in ref[2:].split("."):
        if not isinstance(node, Mapping) or part not in node:
            raise RefError(f"{ref}: nothing at {walked}.{part}")
        node = node[part]
        walked = f"{walked}.{part}"
    return copy.deepcopy(node)


def resolve_value(value: Any, root: Mapping[str, Any]) -> Any:
    """Resolve every reference inside a literal, dict or list. Other values pass through."""
    if isinstance(value, str):
        return resolve_ref(value, root) if value.startswith("$.") else value
    if isinstance(value, Mapping):
        return {key: resolve_value(item, root) for key, item in value.items()}
    if isinstance(value, list | tuple):
        return [resolve_value(item, root) for item in value]
    return value
