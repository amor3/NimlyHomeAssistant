import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .entity import NimlyLockBatteryLowSensor
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    ieee = entry.data["ieee"]
    name = entry.data.get("name", "Nimly Front Door")

    # Create the battery low binary sensor
    battery_low_sensor = NimlyLockBatteryLowSensor(
        hass, ieee, f"{name} Battery Low", entry.entry_id
    )

    # Add the entity
    async_add_entities([battery_low_sensor])

    # Debug log the unique_id to help with troubleshooting
    ieee_clean = ieee.replace(':', '').lower()
    _LOGGER.debug("Binary sensor unique_id: %s_battery_low_%s_%s", DOMAIN, ieee_clean, entry.entry_id)