"""Binary sensor platform for Nimly Zigbee Digital Lock."""

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .entity import NimlyLockBatteryLowSensor

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    ieee = entry.data["ieee"]
    name = entry.data.get("name", "Safe4 Front Door")
    async_add_entities([NimlyLockBatteryLowSensor(hass, ieee, f"{name} Battery Low")])
