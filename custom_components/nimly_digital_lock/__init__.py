"""Nimly Digital Lock integration."""

from .const import DOMAIN

async def async_setup(hass, config):
    """Set up the integration via YAML (if supported)."""
    return True

async def async_setup_entry(hass, entry):
    """Set up integration from config flow entry."""
    # Set up platforms here if you have any (lock, sensor)
    return True
