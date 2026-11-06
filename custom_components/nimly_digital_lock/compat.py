"""Compatibility across the Home Assistant versions this integration supports."""

from __future__ import annotations

# Home Assistant 2026.10 moved from voluptuous to probatio, an API-compatible
# fork; older releases only ship voluptuous.
try:
    import probatio as vol
except ImportError:  # pragma: no cover - Home Assistant before 2026.10
    import voluptuous as vol  # type: ignore[no-redef]

__all__ = ["vol"]
