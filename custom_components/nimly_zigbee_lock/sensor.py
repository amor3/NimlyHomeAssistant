from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .entity import NimlyLockSensor
from .const import ATTRIBUTE_MAP

SENSOR_ATTRIBUTES = [
    "battery_voltage",
    "battery_percent_remaining",
    "diagnostics_data",
]

async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback
):
    ieee = entry.data["ieee"]
    name = entry.data["name"]

    sensors = []
    for attr in ATTRIBUTE_MAP:
        if attr in SENSOR_ATTRIBUTES:
            friendly_name = f"{name} {attr.replace('_',' ').title()}"
            sensors.append(NimlyLockSensor(hass, ieee, attr, friendly_name))

    async_add_entities(sensors)
