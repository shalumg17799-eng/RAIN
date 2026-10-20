"""One YAML loader for every file we read (agents, skill manifests, app profiles).

PyYAML follows YAML 1.1, where the bare words `on`, `off`, `yes` and `no` are booleans. That turns
the agent route key `on:` into `True`, and a label list `[yes, no]` into `[True, False]`. This
loader keeps `true` and `false` as booleans and treats the other words as the strings they are.
"""

import re
from typing import Any

import yaml

_BOOL_TAG = "tag:yaml.org,2002:bool"


class _Loader(yaml.SafeLoader):
    pass


_Loader.yaml_implicit_resolvers = {
    first: [(tag, rx) for tag, rx in resolvers if tag != _BOOL_TAG]
    for first, resolvers in yaml.SafeLoader.yaml_implicit_resolvers.items()
}
_Loader.add_implicit_resolver(
    _BOOL_TAG, re.compile(r"^(?:true|True|TRUE|false|False|FALSE)$"), list("tTfF")
)


def load_yaml(text: str) -> Any:
    """Parse YAML text. Malformed text is a ValueError, which every loader here already handles."""
    try:
        return yaml.load(text, Loader=_Loader)  # noqa: S506 - _Loader is a SafeLoader subclass
    except yaml.YAMLError as exc:
        raise ValueError(f"invalid YAML: {exc}") from exc
