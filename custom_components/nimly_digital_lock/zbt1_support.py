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

async def async_read_attribute_zbt1(hass, ieee_address, cluster_id, attribute_id, retries=3):
    """Read an attribute directly from the ZHA device object.

    Args:
        hass: Home Assistant instance
        ieee_address: IEEE address of the device
        cluster_id: Cluster ID
        attribute_id: Attribute ID
        retries: Number of retries

    Returns:
        Attribute value or None if failed
    """
    # Try to get the ZHA device
    device = await get_zha_device(hass, ieee_address)
    if not device:
        return None

    # Try each endpoint in order
    from .const import DOMAIN

    # Try ZBT1 endpoint (11) first, then others
    for endpoint_id in ZBT1_ENDPOINTS:
        if endpoint_id not in device.endpoints:
            continue

        endpoint = device.endpoints[endpoint_id]

        # Try to find the cluster
        cluster = endpoint.in_clusters.get(cluster_id)
        if not cluster:
            _LOGGER.debug(f"Cluster {cluster_id} not found on endpoint {endpoint_id}")
            continue

        _LOGGER.debug(f"Found cluster {cluster_id} on endpoint {endpoint_id}, trying to read attribute {attribute_id}")

        # Try to read the attribute with retries
        for attempt in range(retries):
            try:
                result = await cluster.read_attributes([attribute_id], allow_cache=False)

                if result and attribute_id in result[0]:
                    value = result[0][attribute_id]
                    _LOGGER.info(f"Successfully read attribute {attribute_id} with value {value} on endpoint {endpoint_id}")

                    # Store the result in our data store for other components to use
                    hass.data[f"{DOMAIN}:{ieee_address}:{attribute_id}"] = value

                    return value
                else:
                    _LOGGER.debug(f"Attribute {attribute_id} not in result on attempt {attempt+1}")
            except Exception as e:
                _LOGGER.debug(f"Error reading attribute {attribute_id} on endpoint {endpoint_id}, attempt {attempt+1}: {e}")

            # Wait before retry
            if attempt < retries - 1:
                await asyncio.sleep(1)

    _LOGGER.warning(f"Failed to read attribute {attribute_id} from cluster {cluster_id} on any endpoint")
    return None

async def async_send_command_zbt1(hass, ieee_address, command_id, cluster_id=DOOR_LOCK_CLUSTER, endpoint_id=11, args=None):
    """Send a command directly to the ZHA device object.

    Args:
        hass: Home Assistant instance
        ieee_address: IEEE address of the device
        command_id: Command ID
        cluster_id: Cluster ID (default is Door Lock cluster)
        endpoint_id: Endpoint ID (default is 11 for ZBT-1)
        args: Command arguments (default is None)

    Returns:
        Boolean indicating success or failure
    """
    # Try to get the ZHA device
    device = await get_zha_device(hass, ieee_address)
    if not device:
        _LOGGER.error(f"Device with IEEE {ieee_address} not found for direct command")
        return False

    # Check if the endpoint exists
    if endpoint_id not in device.endpoints:
        _LOGGER.error(f"Endpoint {endpoint_id} not found on device {ieee_address}")
        # Try other endpoints as fallback
        endpoints_to_try = [ep for ep in ZBT1_ENDPOINTS if ep in device.endpoints]
        if not endpoints_to_try:
            _LOGGER.error(f"No valid endpoints found on device {ieee_address}")
            return False
        endpoint_id = endpoints_to_try[0]
        _LOGGER.warning(f"Using fallback endpoint {endpoint_id}")

    endpoint = device.endpoints[endpoint_id]

    # Try to find the cluster
    cluster = endpoint.in_clusters.get(cluster_id)
    if not cluster:
        _LOGGER.error(f"Cluster {cluster_id} not found on endpoint {endpoint_id}")
        return False

    _LOGGER.info(f"Found cluster {cluster_id} on endpoint {endpoint_id}, sending command {command_id}")

    # Send the command
    try:
        if args is None:
            # Send without arguments
            await cluster.command(command_id)
        else:
            # Send with arguments
            await cluster.command(command_id, **args)

        _LOGGER.info(f"Successfully sent command {command_id} to cluster {cluster_id} on endpoint {endpoint_id}")
        return True
    except Exception as e:
        _LOGGER.error(f"Error sending command {command_id} to cluster {cluster_id} on endpoint {endpoint_id}: {e}")
        return False

async def refresh_device_state(hass, ieee_address):
    """Force a refresh of device state by reading key attributes.

    Args:
        hass: Home Assistant instance
        ieee_address: IEEE address of the device

    Returns:
        Dictionary with device state information
    """
    device_state = {}

    # Read lock state
    lock_state = await async_read_attribute_zbt1(hass, ieee_address, DOOR_LOCK_CLUSTER, 0x0000)
    if lock_state is not None:
        device_state["lock_state"] = lock_state

    # Read battery percentage
    battery = await async_read_attribute_zbt1(hass, ieee_address, POWER_CLUSTER, 0x0021)
    if battery is not None:
        device_state["battery"] = battery

    # Read battery voltage
    voltage = await async_read_attribute_zbt1(hass, ieee_address, POWER_CLUSTER, 0x0020)
    if voltage is not None:
        # Convert millivolts to volts if needed
        if isinstance(voltage, (int, float)) and voltage > 100:
            voltage = voltage / 1000.0
        device_state["voltage"] = voltage

    return device_state

async def async_read_attribute_zbt1(hass, ieee, cluster_id, attribute_id, endpoint_id=11):
    _LOGGER.debug(f"Reading attribute {attribute_id} from cluster {cluster_id} on endpoint {endpoint_id}")

    # Format IEEE address with colons
    ieee_with_colons = format_ieee_with_colons(ieee)

    # Service data for reading attribute
    service_data = {
        "ieee": ieee_with_colons,
        "endpoint_id": endpoint_id,
        "cluster_id": cluster_id,
        "cluster_type": "in",
        "attribute": attribute_id
    }

    # Try both service domains
    service_domains = ["zigbee", "zha"]
    service_methods = ["get_zigbee_cluster_attribute", "read_zigbee_cluster_attribute"]

    # Try each service domain and method
    for domain in service_domains:
        for method in service_methods:
            if not hass.services.has_service(domain, method):
                continue

            try:
                _LOGGER.debug(f"Trying to read attribute using {domain}.{method}")

                # Send the command
                result = await hass.services.async_call(
                    domain, method, service_data, blocking=True, return_response=True
                )

                if result is not None:
                    _LOGGER.info(f"Successfully read attribute {attribute_id}: {result}")
                    return result
            except Exception as e:
                _LOGGER.warning(f"Failed to read attribute {attribute_id} using {domain}.{method}: {e}")

    _LOGGER.warning(f"Failed to read attribute {attribute_id} with all methods")
    return None