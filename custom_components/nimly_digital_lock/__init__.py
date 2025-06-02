import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from .const import DOMAIN, ATTRIBUTE_MAP

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
    # Check if ZHA is available
    if "zha" not in hass.data:
        _LOGGER.error("ZHA integration is required but not found")
        return False

    # Initialize the data dictionary for this entry
    ieee = entry.data["ieee"]
    _LOGGER.debug(f"Setting up Nimly Digital Lock with IEEE: {ieee}")

    # Make sure the data store exists
    if DOMAIN not in hass.data:
        hass.data[DOMAIN] = {}

    # Initialize all attributes with None to ensure they exist
    for attr in ATTRIBUTE_MAP:
        hass.data[f"{DOMAIN}:{ieee}:{attr}"] = None
        _LOGGER.debug(f"Initialized attribute {attr} for {ieee}")

    # Verify device exists in ZHA
    zha_gateway = hass.data.get("zha", {}).get("gateway", None)
    if zha_gateway:
        zha_device = zha_gateway.get_device(ieee)
        if not zha_device:
            _LOGGER.error(f"ZHA device not found for {ieee}. Please make sure it's paired to ZHA first.")

    await hass.config_entries.async_forward_entry_setups(entry, ["lock", "sensor", "binary_sensor"])
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_unload_platforms(entry, ["lock", "sensor", "binary_sensor"])
    return True
