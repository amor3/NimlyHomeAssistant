import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .entity import NimlyLockBatteryLowSensor
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    ieee = entry.data["ieee"]
    name = entry.data.get("name", "Nimly Front Door")
    # Add entry_id to make the unique_id truly unique
    async_add_entities([NimlyLockBatteryLowSensor(hass, ieee, f"{name} Battery Low", entry.entry_id)])
    # Log the unique_id for debugging
    ieee_clean = ieee.replace(':', '').lower()
    _LOGGER.debug(f"Binary sensor unique_id: {DOMAIN}_battery_low_{ieee_clean}_{entry.entry_id}")
