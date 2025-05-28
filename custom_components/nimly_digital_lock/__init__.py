from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from .lock import async_setup_entry as lock_async_setup_entry

async def async_setup(hass: HomeAssistant, config: dict):
    """Set up the integration."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    """Set up from config flow entry."""
    await lock_async_setup_entry(hass, entry, hass.helpers.entity_platform.async_add_entities)
    return True

from homeassistant.helpers import config_validation as cv

CONFIG_SCHEMA = cv.config_entry_only_config_schema
