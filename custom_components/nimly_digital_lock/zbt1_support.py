import logging
import asyncio

_LOGGER = logging.getLogger(__name__)

# Import from the dedicated constants file
from .const_zbt1 import ZBT1_ENDPOINTS

# Import helper functions from zha_mapping
from .zha_mapping import (
    format_ieee_with_colons,
    normalize_ieee
)

async def get_zbt1_endpoints(hass, ieee):
    try:
        default_endpoints = [11, 1, 2, 3, 242]
        return default_endpoints
    except Exception as e:
        _LOGGER.warning(f"Error retrieving ZBT1 endpoints: {e}")
        return [11, 1, 2, 3, 242]



import logging
import asyncio

# Define ZHA domain constant directly instead of importing from unavailable path
ZHA_DOMAIN = "zha"


# Standard cluster IDs
DOOR_LOCK_CLUSTER = 0x0101
POWER_CLUSTER = 0x0001

# Nordic ZBT-1 uses endpoint 11
ZBT1_ENDPOINTS = [11, 1, 2, 3]

async def get_zha_device(hass, ieee_address):
    """Get the ZHA device object directly from the ZHA gateway.

    Args:
        hass: Home Assistant instance
        ieee_address: IEEE address of the device (with or without colons)

    Returns:
        ZHA device object or None if not found
    """
    # Clean up IEEE address for comparison
    ieee_clean = ieee_address.replace(':', '').lower()

    # Try to get the ZHA gateway
    if ZHA_DOMAIN not in hass.data or 'gateway' not in hass.data[ZHA_DOMAIN]:
        _LOGGER.warning("ZHA gateway not found in Home Assistant data")
        return None

    gateway = hass.data[ZHA_DOMAIN]['gateway']
    if not hasattr(gateway, 'devices'):
        _LOGGER.warning("ZHA gateway does not have devices attribute")
        return None

    # Look for our device in the gateway devices
    for device in gateway.devices.values():
        if hasattr(device, 'ieee') and str(device.ieee).replace(':', '').lower() == ieee_clean:
            _LOGGER.info(f"Found ZHA device: {device.ieee}")
            return device

    _LOGGER.warning(f"Device with IEEE {ieee_address} not found in ZHA gateway")
    return None

async def async_read_attribute_zbt1(hass, ieee, cluster_id, attribute_id, endpoint_id=11):
    """
    Try to read a Zigbee attribute from one of the known ZBT1 endpoints.
    If endpoint_id is given, try it first; otherwise loop through ZBT1_ENDPOINTS.
    """
    ieee_colon = format_ieee_with_colons(ieee)

    # If the caller already told us a preferred endpoint_id (e.g. 11), try it first
    endpoints_to_try = [endpoint_id] + [ep for ep in ZBT1_ENDPOINTS if ep != endpoint_id] \
                      if endpoint_id is not None \
                      else ZBT1_ENDPOINTS

    for ep in endpoints_to_try:
        if ep is None:
            continue
        try:
            service_data = {
                "ieee": ieee_colon,
                "endpoint_id": ep,
                "cluster_id": cluster_id,
                "attribute": attribute_id,
            }
            _LOGGER.debug(f"Trying ZBT-1 read: cluster={hex(cluster_id)} attr={hex(attribute_id)} on ep {ep}")
            result = await hass.services.async_call(
                "zha",
                "read_attribute",
                service_data,
                blocking=True,
                return_response=True,
            )
            if result is not None:
                _LOGGER.info(f"ZBT-1 read got {attribute_id=} on ep {ep}: {result}")
                return result
        except Exception as e:
            _LOGGER.debug(f"ZBT-1 read failed on ep={ep} (cluster={hex(cluster_id)}, attr={hex(attribute_id)}): {e}")

    _LOGGER.warning(f"ZBT-1 read never succeeded (cluster={hex(cluster_id)}, attr={hex(attribute_id)})")
    return None