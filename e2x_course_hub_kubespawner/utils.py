import re
from collections.abc import Iterable
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Self

import yaml
from e2x_course_hub.contract import SpawnRole

from .errors import MissingSpawnRoleError, UnresolvedPlaceholderError


def require_all_spawn_roles(roles: Iterable[SpawnRole], what: str) -> None:
    """
    Raises a MissingSpawnRoleError if *roles* does not contain every spawn role.

    The catalog must define everything for every role, so any role can be spawned.

    Args:
        roles: The spawn roles that are defined.
        what: Describes what is missing a role, used in the error message.
    """
    missing = [role.value for role in SpawnRole if role not in set(roles)]
    if missing:
        raise MissingSpawnRoleError(what, missing)


def load_yaml(yaml_file: Path | str) -> dict:
    """
    Loads a YAML mapping from a file, preserving date-like strings instead of
    parsing them into date objects.

    Args:
        yaml_file (Path | str): Path to the YAML file.
    Returns:
        dict: The contents of the YAML file.
    Raises:
        ValueError: If the YAML file does not contain a mapping at the top level.
    """

    def yaml_constructor(loader, node):
        # Preserve string type for date-like strings
        if isinstance(node.value, str) and re.match(r"^\d{4}-\d{2}-\d{2}$", node.value):
            return node.value
        return loader.construct_scalar(node)

    yaml.add_implicit_resolver(
        "tag:yaml.org,2002:timestamp", re.compile(r"^\d{4}-\d{1,2}-\d{1,2}"), Loader=yaml.SafeLoader
    )
    yaml.add_constructor("tag:yaml.org,2002:timestamp", yaml_constructor, Loader=yaml.SafeLoader)

    with open(yaml_file, "r") as f:
        data = yaml.safe_load(f)

    if not isinstance(data, dict):
        raise TypeError(f"Expected YAML mapping in {yaml_file}")

    return data


PLACEHOLDER_START = "${{"
PLACEHOLDER_END = "}}"


def _placeholder_pattern(namespace: str) -> re.Pattern[str]:
    """Match ``${{ <namespace>.<key> }}``, capturing the key; whitespace inside is allowed."""
    start, end = re.escape(PLACEHOLDER_START), re.escape(PLACEHOLDER_END)
    return re.compile(rf"{start}\s*{re.escape(namespace)}\.(\w+)\s*{end}")


def resolve_placeholders(obj: Any, ctx: "PlaceholderContext", namespace: str = "inputs") -> Any:
    """Recursively resolve ${{namespace.key}} placeholders in a data structure.

    Walks dicts, lists, and strings, replacing occurrences of
    ``${{<namespace>.<key>}}`` with the corresponding value from *ctx*.
    Non-string leaves are returned as-is.

    Args:
        obj: The data structure to resolve (dict, list, str, or scalar).
        ctx: The placeholder values to substitute.
        namespace: The namespace prefix used in placeholders (default: "inputs").

    Returns:
        A deep copy of *obj* with all matching placeholders substituted.

    Raises:
        UnresolvedPlaceholderError: If a placeholder references a key not present in
            *ctx*, or a malformed placeholder (e.g. ``${{input.username}}``) is left.
    """
    if isinstance(obj, dict):
        return {k: resolve_placeholders(v, ctx, namespace) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [resolve_placeholders(v, ctx, namespace) for v in obj]
    elif isinstance(obj, str):
        values = ctx.as_dict()

        def replace_param(match):
            param_name = match.group(1)
            if param_name not in values:
                raise UnresolvedPlaceholderError(
                    f"Parameter '{param_name}' not found in context, in {obj!r}"
                )
            return str(values[param_name])

        resolved = _placeholder_pattern(namespace).sub(replace_param, obj)
        # Anything still starting a placeholder is malformed, e.g. a typo in the namespace
        if PLACEHOLDER_START in resolved:
            raise UnresolvedPlaceholderError(f"Malformed placeholder in {obj!r}")
        return resolved
    else:
        return obj


@dataclass(frozen=True)
class PlaceholderContext:
    """The username/course_id/term_id values substituted into ${{inputs.*}} placeholders."""

    username: str
    course_id: str
    term_id: str

    def as_dict(self) -> dict[str, str]:
        return {"username": self.username, "course_id": self.course_id, "term_id": self.term_id}

    def with_term_id(self, term_id: str) -> Self:
        """Return a copy of this context for a different term (e.g. an archived term)."""
        return replace(self, term_id=term_id)
