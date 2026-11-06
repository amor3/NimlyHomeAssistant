"""Diagnostics for Nimly Digital Lock: no codes, addresses or slot names."""

from __future__ import annotations

from typing import Any

from homeassistant.components.diagnostics import async_redact_data
from homeassistant.core import HomeAssistant

from .const import CONF_IEEE
from .manager import NimlyConfigEntry
from .zha import find_door_lock_cluster, find_lock_entity_id, is_zha_running, quirk_status

TO_REDACT = {CONF_IEEE, "unique_id", "title"}


async def async_get_config_entry_diagnostics(
    hass: HomeAssistant, entry: NimlyConfigEntry
) -> dict[str, Any]:
    """Return diagnostics for a config entry."""
    manager = entry.runtime_data
    cluster = find_door_lock_cluster(hass, manager.ieee)
    last = manager.last_event
    quirk = quirk_status(hass, manager.ieee)
    return {
        "entry": async_redact_data(entry.as_dict(), TO_REDACT),
        "zha": {
            "running": is_zha_running(hass),
            "door_lock_cluster": type(cluster).__name__ if cluster is not None else None,
            "has_on_event": callable(getattr(cluster, "on_event", None)),
            "zha_lock_entity": find_lock_entity_id(hass, manager.ieee) is not None,
            "quirk_applied": quirk.applied if quirk else None,
            "quirk_class": quirk.quirk_class if quirk else None,
        },
        "listening": manager.listening,
        # What ZHA lacks and the integration provides itself.
        "fallbacks": sorted(manager.fallbacks),
        "settings": {f"0x{key:04x}": value for key, value in manager.settings.items()},
        "battery": manager.battery,
        "missed_reports": manager.missed_reports,
        "capabilities": manager.capabilities,
        "capabilities_read": manager.capabilities_read,
        "first_user_slot": manager.first_user_slot,
        "slots": {
            str(number): {
                "named": bool(slot["name"]),
                "named_kinds": sorted(slot["names"]),
                "has_pin": slot["has_pin"],
                "expires": slot["expires"],
            }
            for number, slot in manager.slots.items()
        },
        "last_event": (
            {
                "action": last.action,
                "source": last.source,
                "slot": last.slot,
                "raw": f"0x{last.raw:08x}",
            }
            if last
            else None
        ),
    }
