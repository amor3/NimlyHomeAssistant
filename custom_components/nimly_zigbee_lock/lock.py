from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import NimlyDigitalLock

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
):
    ieee = entry.data["ieee"]
    name = entry.data["name"]
    async_add_entities([NimlyDigitalLock(hass, ieee, name)])
