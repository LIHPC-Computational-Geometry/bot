"""Namespaced curve tag utilities for the viewer adapter boundary."""

from __future__ import annotations

CAD_NS = "cad"
SPLINE_NS = "spline"


def encode(namespace: str, local_id: str | int) -> str:
    """Build a namespaced curve tag (e.g. ``cad:42``, ``spline:curve-<uuid>``)."""
    return f"{namespace}:{local_id}"


def decode(tag: str) -> tuple[str, str] | None:
    """Split a namespaced tag into ``(namespace, local_id)`` or return ``None``."""
    if not tag or ":" not in tag:
        return None
    namespace, local_id = tag.split(":", 1)
    if not namespace or not local_id:
        return None
    return namespace, local_id


def prefix(tag: str) -> str | None:
    """Return the namespace portion of a tag, or ``None`` if malformed."""
    decoded = decode(tag)
    return decoded[0] if decoded is not None else None


def is_namespaced(tag: str) -> bool:
    """Return whether ``tag`` contains a namespace prefix."""
    return decode(tag) is not None


def parse_cad_local_id(tag: str) -> int | None:
    """Safely parse the local CAD integer from a namespaced tag."""
    decoded = decode(tag)
    if decoded is None or decoded[0] != CAD_NS:
        return None
    try:
        return int(decoded[1])
    except TypeError, ValueError:
        return None
