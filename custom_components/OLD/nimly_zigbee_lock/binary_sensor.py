from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import NimlyLockBatteryLowSensor

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
):
    ieee = entry.data["ieee"]
    name = entry.data["name"]
    friendly = f"{name} Battery Low"
    async_add_entities([NimlyLockBatteryLowSensor(hass, ieee, friendly)])
