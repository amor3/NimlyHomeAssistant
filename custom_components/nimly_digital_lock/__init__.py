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
        # Inspect ZHA data structure to help debug access issues
        zha_data = hass.data["zha"]
        _LOGGER.debug(f"ZHA data type: {type(zha_data)}")

        # Log the structure of the ZHA data
        if isinstance(zha_data, dict):
            _LOGGER.debug(f"ZHA data keys: {list(zha_data.keys())}")
        else:
            _LOGGER.debug(f"ZHA data attributes: {dir(zha_data)}")

        # Try to access ZHA gateway - the structure may vary by HA version
        try:
            gateway_found = False
            # Method 1: Direct gateway attribute
            if hasattr(zha_data, "gateway"):
                _LOGGER.debug("Found gateway via attribute")
                zha_gateway = zha_data.gateway
                gateway_found = True
            # Method 2: Gateway in dict
            elif isinstance(zha_data, dict) and "gateway" in zha_data:
                _LOGGER.debug("Found gateway via dictionary key")
                zha_gateway = zha_data["gateway"]
                gateway_found = True
            # Method 3: For newer ZHA versions using different structure
            elif hasattr(zha_data, "application_controller") and zha_data.application_controller:
                _LOGGER.debug("Found application_controller")
                zha_gateway = zha_data.application_controller
                gateway_found = True

            if gateway_found:
                _LOGGER.debug(f"Gateway type: {type(zha_gateway)}")
                _LOGGER.debug(f"Gateway methods: {dir(zha_gateway)}")

                # Try different methods to get the device
                if hasattr(zha_gateway, "get_device"):
                    _LOGGER.debug("Using get_device method")
                    zha_device = zha_gateway.get_device(ieee)
                elif hasattr(zha_gateway, "devices") and isinstance(zha_gateway.devices, dict):
                    _LOGGER.debug("Accessing devices dictionary")
                    zha_device = zha_gateway.devices.get(ieee)
                else:
                    _LOGGER.warning("Could not find a way to access ZHA devices")
                    return True

                if zha_device:
                    _LOGGER.debug(f"Found ZHA device: {ieee}")
                    _LOGGER.debug(f"Device type: {type(zha_device)}")
                    _LOGGER.debug(f"Device endpoints: {zha_device.endpoints.keys() if hasattr(zha_device, 'endpoints') else 'No endpoints'}")
                else:
                    _LOGGER.warning(f"ZHA device {ieee} not found. Please make sure it's paired to ZHA first.")
            else:
                _LOGGER.warning("Could not find ZHA gateway in data structure")
        except Exception as e:
            _LOGGER.warning(f"Error accessing ZHA: {e}")

    await hass.config_entries.async_forward_entry_setups(entry, ["lock", "sensor", "binary_sensor"])
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry):
    await hass.config_entries.async_unload_platforms(entry, ["lock", "sensor", "binary_sensor"])
    return True
