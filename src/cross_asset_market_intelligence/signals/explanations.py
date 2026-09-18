"""Small deterministic explanation primitive for persisted signal statements."""

from __future__ import annotations

from collections.abc import Mapping


def render_explanation(template: str, values: Mapping[str, object]) -> str:
    """Render a named-field template deterministically; callers persist its result."""
    return template.format_map(_StrictValues(values))


class _StrictValues(dict[str, object]):
    def __missing__(self, key: str) -> object:
        raise KeyError(f"Missing deterministic explanation value: {key}")
