"""Nordic ZBT-1 specific command implementation for Nimly locks."""
"""Nordic Semiconductor ZBT-1 specific implementation for Nimly Digital Lock.

This module implements the exact command format required by the Nordic Semiconductor
ZBT-1 specification for the Safe4 ZigBee Door Lock Module.

According to the specification, commands must be sent in this exact format:
zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 <command id>

Where:
- Endpoint must be exactly 11
- Cluster ID must be 0x0101 (Door Lock)
- Profile ID must be 0x0104 (Home Automation)
- Command ID must be 0x00 for lock, 0x01 for unlock
- NO parameters can be passed
"""

import logging
import asyncio

_LOGGER = logging.getLogger(__name__)

# Import constants from dedicated constants file
from .const_zbt1 import (
    SAFE4_ZBT1_ENDPOINT,
    SAFE4_DOOR_LOCK_CLUSTER,
    SAFE4_DOOR_LOCK_PROFILE,
    SAFE4_LOCK_COMMAND,
    SAFE4_UNLOCK_COMMAND
)

# Import helper functions from zha_mapping
from .zha_mapping import (
    format_ieee_with_colons,
    format_safe4_zbt1_command
)

async def send_nordic_command(hass, ieee, command_id, retry_count=5, retry_delay=1.0):
    """Send a command to a Nordic ZBT-1 device using the exact format required by the spec.

    The Nordic ZBT-1 specification requires commands to be in this format:
    zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 <command id>

    Args:
        hass: Home Assistant instance
        ieee: IEEE address of the device
        command_id: Command ID (0x00 for lock, 0x01 for unlock)
        retry_count: Number of retries for sending the command
        retry_delay: Delay between retries in seconds

    Returns:
        Boolean indicating success or failure
    """
    _LOGGER.info(f"Sending Nordic ZBT-1 command {command_id} to device {ieee}")

    # Format IEEE address with colons
    ieee_with_colons = format_ieee_with_colons(ieee)

    # Get the command parameters in the correct format
    command_data = format_safe4_zbt1_command(ieee, command_id)

    # Try both service domains
    service_domains = ["zigbee", "zha"]
    service_methods = ["issue_zigbee_cluster_command", "command"]

    # Track success
    success = False

    # Try each service domain and method
    for domain in service_domains:
        for method in service_methods:
            if not hass.services.has_service(domain, method):
                continue

            # Try multiple attempts
            for attempt in range(retry_count):
                try:
                    _LOGGER.debug(f"Attempt {attempt+1}/{retry_count} using {domain}.{method}")

                    # Send the command
                    await hass.services.async_call(
                        domain, method, command_data, blocking=True
                    )

                    _LOGGER.info(f"Successfully sent command {command_id} using {domain}.{method}")
                    success = True
                    return True
                except Exception as e:
                    _LOGGER.warning(f"Failed to send command {command_id} using {domain}.{method}: {e}")

                    # If this is not the last attempt, wait before retrying
                    if attempt < retry_count - 1:
                        await asyncio.sleep(retry_delay)

    if not success:
        _LOGGER.error(f"Failed to send command {command_id} after {retry_count} attempts with all methods")

    return success

async def lock_door(hass, ieee):
    """Lock the door using Nordic ZBT-1 specification.

    Args:
        hass: Home Assistant instance
        ieee: IEEE address of the device

    Returns:
        Boolean indicating success or failure
    """
    _LOGGER.info(f"Locking door with Nordic ZBT-1 format: {ieee}")
    return await send_nordic_command(hass, ieee, SAFE4_LOCK_COMMAND)

async def unlock_door(hass, ieee):
    """Unlock the door using Nordic ZBT-1 specification.

    Args:
        hass: Home Assistant instance
        ieee: IEEE address of the device

    Returns:
        Boolean indicating success or failure
    """
    _LOGGER.info(f"Unlocking door with Nordic ZBT-1 format: {ieee}")
    return await send_nordic_command(hass, ieee, SAFE4_UNLOCK_COMMAND)

async def read_attribute(hass, ieee, cluster_id, attribute_id, endpoint=SAFE4_ZBT1_ENDPOINT):
    """Read an attribute from a Nordic ZBT-1 device.

    Args:
        hass: Home Assistant instance
        ieee: IEEE address of the device
        cluster_id: Cluster ID
        attribute_id: Attribute ID
        endpoint: Endpoint ID (default is 11 for ZBT-1)

    Returns:
        Attribute value or None if not available
    """
    _LOGGER.debug(f"Reading attribute {attribute_id} from cluster {cluster_id} on endpoint {endpoint}")

    # Format IEEE address with colons
    ieee_with_colons = format_ieee_with_colons(ieee)

    # Service data for reading attribute
    service_data = {
        "ieee": ieee_with_colons,
        "endpoint_id": endpoint,
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
import logging

# Constants as specified in Nordic Semiconductor documentation
ZBT1_DOOR_LOCK_CLUSTER = 0x0101  # Door Lock cluster
ZBT1_HOME_AUTOMATION_PROFILE = 0x0104  # Home Automation profile
ZBT1_ENDPOINT = 11  # MUST be exactly 11 per spec

# Door Lock Command IDs (from ZCL 7.3.2.16 Server Commands)
ZBT1_LOCK_COMMAND = 0x00    # Lock Door
ZBT1_UNLOCK_COMMAND = 0x01  # Unlock Door
ZBT1_SET_PIN_CODE = 0x05    # Set PIN Code
ZBT1_CLEAR_PIN_CODE = 0x07  # Clear PIN Code
ZBT1_CLEAR_RFID_CODE = 0x18 # Clear RFID Code
ZBT1_SCAN_RFID_CODE = 0x70  # Scan RFID Code (Custom)
ZBT1_SCAN_FINGERPRINT = 0x71 # Scan Fingerprint (Custom)
ZBT1_CLEAR_FINGERPRINT = 0x72 # Clear Fingerprint (Custom)
ZBT1_LOCAL_PROGRAMMING_DISABLE = 0x73 # Local Programming Disable (Custom)
ZBT1_LOCAL_PROGRAMMING_ENABLE = 0x74  # Local Programming Enable (Custom)