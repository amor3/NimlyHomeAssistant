"""Support for ZBT-1 Zigbee devices with Nordic Semiconductor format.

This module adds specific support functions for the Nabu Casa ZBT-1 device.
"""

import logging
from .zha_mapping import ZBT1_ENDPOINTS, COMMAND_PROFILE

_LOGGER = logging.getLogger(__name__)

async def async_send_command_zbt1(hass, ieee, command, cluster_id, endpoint_id=11, params=None):
    """Send a command specifically formatted for ZBT-1 using Nordic Semiconductor format.

    Args:
        hass: Home Assistant instance
        ieee: IEEE address of the device
        command: Command to send (ID or name)
        cluster_id: Zigbee cluster ID
        endpoint_id: Endpoint ID (default: 11 for ZBT-1)
        params: Optional parameters

    Returns:
        True if successful, False otherwise
    """
    # Check if we have the zigbee service
    if not hass.services.has_service("zigbee", "issue_zigbee_cluster_command"):
        _LOGGER.debug("Zigbee command service not available")
        return False

    # Attempt to send command with specific ZBT-1 format based on Safe4 Specification
    try:
        # According to Safe4 ZigBee Door Lock specification:
        # - Must use endpoint 11
        # - Must use profile 0x0104 (Home Automation)
        # - Command format: zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 <command id>
        # - NO parameters for lock/unlock commands

        service_data = {
            "ieee": ieee,            # IEEE address with colons
            "command": command,      # Numeric command ID (0x00=lock, 0x01=unlock)
            "cluster_id": cluster_id, # Must be 0x0101 for Door Lock cluster
            "endpoint_id": 11,       # Must be exactly 11 per Safe4 spec
            "command_type": "server",
            "profile_id": 0x0104,    # Must be exactly 0x0104 (HA profile) per spec
            "manufacturer_code": 0    # Must be standard manufacturer code
        }

        # Only add params if they're explicitly provided and command requires them
        # For lock/unlock (0x00/0x01), NO parameters should be passed
        if params and command not in [0x00, 0x01]:
            service_data["params"] = params

        # Log the exact command for debugging in CLI format
        command_str = f"zcl cmd {ieee} 11 0x{cluster_id:04x} -p 0x0104 0x{command:02x}"
        _LOGGER.info(f"Sending Safe4 ZigBee Door Lock command: {command_str}")
        _LOGGER.debug(f"Service data: {service_data}")

        # Send the command with proper logging
        await hass.services.async_call(
            "zigbee", "issue_zigbee_cluster_command", service_data
        )
        _LOGGER.info(f"Command sent successfully")
        return True
    except Exception as e:
        import traceback
        _LOGGER.error(f"Failed to send Safe4 ZigBee command: {e}")
        _LOGGER.error(f"Traceback: {traceback.format_exc()}")
        _LOGGER.error(f"Service data attempted: {service_data if 'service_data' in locals() else 'Not created'}")
        return False


async def async_read_attribute_zbt1(hass, ieee, cluster_id, attribute_id, endpoint_id=11):
    """Read an attribute specifically with ZBT-1 formatting.

    Args:
        hass: Home Assistant instance
        ieee: IEEE address of the device
        cluster_id: Zigbee cluster ID
        attribute_id: Attribute ID to read
        endpoint_id: Endpoint ID (default: 11)

    Returns:
        True if the read request was sent successfully, None if failed
    """
    # Check if we have the zigbee service
    if not hass.services.has_service("zigbee", "read_zigbee_cluster_attribute"):
        _LOGGER.debug("Zigbee read_attribute service not available")
        return None

    # Attempt to read with specific ZBT-1 format
    try:
        service_data = {
            "ieee": ieee,
            "cluster_id": cluster_id,
            "attribute": attribute_id,
            "endpoint_id": endpoint_id,
            "cluster_type": "in",
            "profile_id": COMMAND_PROFILE,  # Home Automation profile from constants
            "manufacturer_code": 0  # Nordic Semiconductor uses standard manufacturer code
        }

        _LOGGER.debug(f"Reading ZBT-1 attribute using Nordic format: {service_data}")
        await hass.services.async_call(
            "zigbee", "read_zigbee_cluster_attribute", service_data
        )
        return True
    except Exception as e:
        _LOGGER.warning(f"Failed to read ZBT-1 attribute: {e}")
        # For ZBT-1 devices, not finding a service is a normal condition when using ZHA
        # Return None to indicate the operation didn't succeed
        return None


def get_zbt1_endpoints(hass, device_ieee):
    """Attempt to discover all endpoints for a ZBT-1 device.

    Args:
        hass: Home Assistant instance
        device_ieee: IEEE address of the device

    Returns:
        List of endpoint IDs or None if not found
    """
    try:
        # For Nabu Casa ZBT-1 devices, we know that endpoint 11 is the primary endpoint
        # This is based on Nordic Semiconductor Zigbee CLI documentation
        # Even if get_devices service is not available, we can still return known endpoints
        _LOGGER.debug(f"Using ZBT-1 endpoints for device {device_ieee}")

        # According to Safe4 ZigBee spec, only endpoint 11 should be used
        return [11]
    except Exception as e:
        _LOGGER.warning(f"Error determining ZBT-1 endpoints: {e}")
        # Return the most common endpoint (11) as fallback
        return [11]
