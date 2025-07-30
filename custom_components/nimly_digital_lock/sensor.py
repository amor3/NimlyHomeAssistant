"""Sensor platform for Nimly Digital Lock."""
import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .sensors.battery_sensor import BatterySensor
from .sensors.rssi_sensor import RSSISensor

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities from config entry."""
    _LOGGER.info(f"[AM] Setting up sensor platform for entry: {entry.entry_id}")

    ieee = entry.data["ieee"]
    name = entry.data.get("name", "Nimly Front Door")
    ieee_key = ieee.lower().replace(":", "")

    # Create and register battery sensor

    battery_sensor = BatterySensor(hass, ieee, name)
    rssi_sensor = RSSISensor(hass, ieee, name)
    #sound_volume_select = SoundVolumeSelect(hass, ieee, name)

    hass.data[DOMAIN]["battery_sensors"][ieee_key] = battery_sensor
    hass.data[DOMAIN]["rssi_sensors"][ieee_key] = rssi_sensor
    #hass.data[DOMAIN]["lock_sound_volume_select"][ieee_key] = lock_sound_volume_select

    async_add_entities([battery_sensor, rssi_sensor], True)

    _LOGGER.info(f"[AM] Added battery sensor: {battery_sensor.entity_id}")
    _LOGGER.info(f"[AM] Added rssi sensor: {rssi_sensor.entity_id}")
    #_LOGGER.info(f"[AM] Added lock sound volume select: {rssi_sensor.entity_id}")

    if "entities" in hass.data[DOMAIN]:
        for entity in hass.data[DOMAIN]["entities"]:
            if hasattr(entity, 'register_diagnostic_sensor') and entity._ieee == ieee:
                entity.register_diagnostic_sensor("battery", battery_sensor)
                entity.register_diagnostic_sensor("rssi", rssi_sensor)
                _LOGGER.info(f"[AM] Registered sensors with lock: {entity.name}")