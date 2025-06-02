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

    # Normalize IEEE address format - ZHA might use different formats
    # Try both with and without colons
    ieee_no_colons = ieee.replace(':', '')
    ieee_with_colons = ':'.join([ieee_no_colons[i:i+2] for i in range(0, len(ieee_no_colons), 2)]) if ':' not in ieee else ieee
    _LOGGER.debug(f"IEEE address formats - Original: {ieee}, No colons: {ieee_no_colons}, With colons: {ieee_with_colons}")

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
            # Method 3: For newer ZHA versions using application_controller
            elif hasattr(zha_data, "application_controller") and zha_data.application_controller:
                _LOGGER.debug("Found application_controller")
                zha_gateway = zha_data.application_controller
                gateway_found = True
            # Method 4: Check for coordinator in newer ZHA versions
            elif hasattr(zha_data, "coordinator") and zha_data.coordinator:
                _LOGGER.debug("Found coordinator")
                zha_gateway = zha_data.coordinator
                gateway_found = True
            # Method 5: Check for device_registry
            elif hasattr(zha_data, "device_registry") and zha_data.device_registry:
                _LOGGER.debug("Found device_registry")
                zha_gateway = zha_data.device_registry
                gateway_found = True
            # Method 6: Look for a get_device method directly
            elif hasattr(zha_data, "get_device"):
                _LOGGER.debug("Found get_device method directly on zha_data")
                gateway_found = True
                # We'll handle this special case below

            # Direct method on zha_data - special case from method 6 above
            if gateway_found and 'zha_gateway' not in locals() and hasattr(zha_data, "get_device"):
                _LOGGER.debug("Using zha_data.get_device method directly")
                try:
                    zha_device = zha_data.get_device(ieee)
                    if zha_device:
                        _LOGGER.debug(f"Found ZHA device directly: {ieee}")
                        _LOGGER.debug(f"Device type: {type(zha_device)}")
                        _LOGGER.debug(f"Device attributes: {dir(zha_device)}")
                    else:
                        _LOGGER.warning(f"ZHA device {ieee} not found. Please make sure it's paired to ZHA first.")
                except Exception as e:
                    _LOGGER.warning(f"Error accessing device via zha_data.get_device: {e}")
            # Regular gateway methods
            elif gateway_found and 'zha_gateway' in locals():
                _LOGGER.debug(f"Gateway type: {type(zha_gateway)}")
                _LOGGER.debug(f"Gateway methods: {dir(zha_gateway)}")

                # Try different methods to get the device
                device_found = False

                # Method 1: get_device method
                if hasattr(zha_gateway, "get_device"):
                    _LOGGER.debug("Using get_device method")
                    try:
                        # Try with original format
                        zha_device = zha_gateway.get_device(ieee)
                        if zha_device:
                            device_found = True
                            _LOGGER.debug(f"Found device with original IEEE format: {ieee}")
                        else:
                            # Try with no colons
                            _LOGGER.debug(f"Trying with no colons: {ieee_no_colons}")
                            zha_device = zha_gateway.get_device(ieee_no_colons)
                            if zha_device:
                                device_found = True
                                _LOGGER.debug(f"Found device with no colons format: {ieee_no_colons}")
                            else:
                                # Try with colons
                                _LOGGER.debug(f"Trying with colons: {ieee_with_colons}")
                                zha_device = zha_gateway.get_device(ieee_with_colons)
                                if zha_device:
                                    device_found = True
                                    _LOGGER.debug(f"Found device with colons format: {ieee_with_colons}")
                    except Exception as e:
                        _LOGGER.warning(f"Error with get_device method: {e}")

                # Method 2: direct devices dictionary
                if not device_found and hasattr(zha_gateway, "devices"):
                    _LOGGER.debug("Checking gateway.devices")
                    if isinstance(zha_gateway.devices, dict):
                        zha_device = zha_gateway.devices.get(ieee)
                        if zha_device:
                            device_found = True
                    elif hasattr(zha_gateway.devices, "get"):
                        try:
                            zha_device = zha_gateway.devices.get(ieee)
                            if zha_device:
                                device_found = True
                        except Exception as e:
                            _LOGGER.warning(f"Error accessing devices.get: {e}")

                # Method 3: Check for a device_registry
                if not device_found and hasattr(zha_gateway, "device_registry"):
                    _LOGGER.debug("Checking device_registry")
                    if hasattr(zha_gateway.device_registry, "get"):
                        try:
                            # Try all IEEE formats
                            for addr_format in [ieee, ieee_no_colons, ieee_with_colons]:
                                zha_device = zha_gateway.device_registry.get(addr_format)
                                if zha_device:
                                    device_found = True
                                    _LOGGER.debug(f"Found device in registry with format: {addr_format}")
                                    break
                        except Exception as e:
                            _LOGGER.warning(f"Error accessing device_registry.get: {e}")

                # Method 4: Last resort - scan all devices
                if not device_found and hasattr(zha_gateway, "devices"):
                    _LOGGER.debug("Last resort: Scanning all ZHA devices")
                    try:
                        # Get all devices and iterate through them
                        if isinstance(zha_gateway.devices, dict):
                            all_devices = zha_gateway.devices.values()
                        elif hasattr(zha_gateway.devices, "values"):
                            all_devices = zha_gateway.devices.values()
                        else:
                            all_devices = []

                        for device in all_devices:
                            device_ieee = None
                            # Try different attribute names for IEEE
                            if hasattr(device, 'ieee'):
                                device_ieee = str(device.ieee)
                            elif hasattr(device, 'ieee_address'):
                                device_ieee = str(device.ieee_address)
                            elif hasattr(device, 'address'):
                                device_ieee = str(device.address)

                            if device_ieee:
                                # Normalize for comparison
                                device_ieee_clean = device_ieee.replace(':', '').lower()
                                search_ieee_clean = ieee_no_colons.lower()

                                if device_ieee_clean == search_ieee_clean:
                                    zha_device = device
                                    device_found = True
                                    _LOGGER.debug(f"Found device by scanning: {device_ieee}")
                                    break
                    except Exception as e:
                        _LOGGER.warning(f"Error scanning ZHA devices: {e}")

                # Log results
                if device_found and 'zha_device' in locals() and zha_device:
                    _LOGGER.debug(f"Found ZHA device: {ieee}")
                    _LOGGER.debug(f"Device type: {type(zha_device)}")
                    _LOGGER.debug(f"Device attributes: {dir(zha_device)}")

                    # Log endpoint info if available
                    if hasattr(zha_device, 'endpoints'):
                        _LOGGER.debug(f"Device endpoints: {zha_device.endpoints.keys() if hasattr(zha_device.endpoints, 'keys') else 'Endpoints structure unknown'}")
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
