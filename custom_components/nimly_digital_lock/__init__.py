import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from .const import DOMAIN, ATTRIBUTE_MAP

_LOGGER = logging.getLogger(__name__)

async def async_setup(hass: HomeAssistant, config: dict):
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry):
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

    # Check if ZHA is available but don't fail if it's not
    # This allows the integration to load even without ZHA
    if "zha" not in hass.data:
        _LOGGER.warning("ZHA integration not found. Some features may not work.")
    else:
        # Try to access ZHA gateway - the structure may vary by HA version
        try:
            # Different ways to access ZHA gateway depending on HA version
            zha_data = hass.data["zha"]
            if hasattr(zha_data, "gateway"):
                zha_gateway = zha_data.gateway
                if zha_gateway and hasattr(zha_gateway, "get_device"):
                    zha_device = zha_gateway.get_device(ieee)
                    if not zha_device:
                        _LOGGER.warning(f"ZHA device {ieee} not found. Please make sure it's paired to ZHA first.")
                    else:
                        _LOGGER.debug(f"Found ZHA device: {ieee}")
        except Exception as e:
            _LOGGER.warning(f"Error accessing ZHA: {e}")

    await hass.config_entries.async_forward_entry_setups(entry, ["lock", "sensor", "binary_sensor"])
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_unload_platforms(entry, ["lock", "sensor", "binary_sensor"])
    return True
