"""Device triggers: "unlocked with the keypad" and friends in the automation editor."""

from __future__ import annotations

from typing import Any

from homeassistant.components.device_automation import DEVICE_TRIGGER_BASE_SCHEMA
from homeassistant.components.homeassistant.triggers import event as event_trigger
from homeassistant.const import CONF_DEVICE_ID, CONF_DOMAIN, CONF_PLATFORM, CONF_TYPE
from homeassistant.core import CALLBACK_TYPE, HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.trigger import TriggerActionType, TriggerInfo
from homeassistant.helpers.typing import ConfigType

from .compat import vol
from .const import DOMAIN, EVENT_LOCK_ACTIVITY

# Trigger type -> what the activity event must carry. "system": False keeps
# out auto relock and similar, so "locked" means a person locked it.
TRIGGERS: dict[str, dict[str, Any]] = {
    "locked": {"action": "lock", "system": False},
    "unlocked": {"action": "unlock", "system": False},
    "unlocked_keypad": {"action": "unlock", "source": "keypad"},
    "unlocked_rfid": {"action": "unlock", "source": "rfid"},
    "unlocked_fingerprint": {"action": "unlock", "source": "fingerprint"},
    # Models report a command from Home Assistant as 0x00, 0x05 or 0x0A.
    "unlocked_remotely": {"action": "unlock", "remote": True},
    "auto_relocked": {"action": "lock", "source": "auto"},
}

TRIGGER_SCHEMA = DEVICE_TRIGGER_BASE_SCHEMA.extend({vol.Required(CONF_TYPE): vol.In(TRIGGERS)})


def _entry_id(hass: HomeAssistant, device_id: str) -> str | None:
    if (device := dr.async_get(hass).async_get(device_id)) is None:
        return None
    return next((value for domain, value in device.identifiers if domain == DOMAIN), None)


async def async_get_triggers(hass: HomeAssistant, device_id: str) -> list[dict[str, str]]:
    """The triggers this integration's lock device offers."""
    if _entry_id(hass, device_id) is None:
        return []
    return [
        {CONF_PLATFORM: "device", CONF_DOMAIN: DOMAIN, CONF_DEVICE_ID: device_id, CONF_TYPE: kind}
        for kind in TRIGGERS
    ]


async def async_attach_trigger(
    hass: HomeAssistant,
    config: ConfigType,
    action: TriggerActionType,
    trigger_info: TriggerInfo,
) -> CALLBACK_TYPE:
    """Listen for the activity event of this lock that matches the type."""
    event_config = event_trigger.TRIGGER_SCHEMA(
        {
            CONF_PLATFORM: "event",
            event_trigger.CONF_EVENT_TYPE: EVENT_LOCK_ACTIVITY,
            "event_data": {
                "config_entry_id": _entry_id(hass, config[CONF_DEVICE_ID]),
                **TRIGGERS[config[CONF_TYPE]],
            },
        }
    )
    return await event_trigger.async_attach_trigger(
        hass, event_config, action, trigger_info, platform_type="device"
    )
