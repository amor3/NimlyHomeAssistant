"""Nimly Zigbee Digital Lock integration."""
from homeassistant.helpers import config_validation as cv
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

CONFIG_SCHEMA = cv.config_entry_only_config_schema

async def async_setup(hass: HomeAssistant, config: dict):
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    return True
