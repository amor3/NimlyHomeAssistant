"""Sensor platform for Nimly Zigbee Digital Lock."""

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import SensorEntity
from .entity import NimlyLockSensor
from .const import ATTRIBUTE_MAP

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    ieee = entry.data["ieee"]
    name = entry.data.get("name", "Safe4 Front Door")
    sensors = [
        NimlyLockSensor(hass, ieee, attr, f"{name} {attr.replace('_',' ').title()}")
        for attr in ATTRIBUTE_MAP
    ]
    async_add_entities(sensors)
