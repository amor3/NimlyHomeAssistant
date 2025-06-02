"""Support for ZBT-1 Zigbee devices with Nordic Semiconductor format.

This module adds specific support functions for the Nabu Casa ZBT-1 device.
"""

import logging
from .zha_mapping import ZBT1_ENDPOINTS, COMMAND_PROFILE
from .zha_mapping import LOCK_ATTRIBUTES, POWER_ATTRIBUTES

_LOGGER = logging.getLogger(__name__)

def get_attribute_name(cluster_id, attribute_id):
    """Get the human-readable name of an attribute based on cluster and attribute ID.

    Args:
        cluster_id: The Zigbee cluster ID
        attribute_id: The attribute ID within the cluster

    Returns:
        Human-readable attribute name or the hex ID if not found
    """
    # Door Lock cluster
    if cluster_id == 0x0101:
        # Reverse lookup in LOCK_ATTRIBUTES
        for name, attr_id in LOCK_ATTRIBUTES.items():
            if attr_id == attribute_id:
                return name
    # Power Configuration cluster
    elif cluster_id == 0x0001:
        # Reverse lookup in POWER_ATTRIBUTES
        for name, attr_id in POWER_ATTRIBUTES.items():
            if attr_id == attribute_id:
                return name

    # Return hex string if not found
    return f"0x{attribute_id:04x}"

async def async_send_command_zbt1(hass, ieee, command, cluster_id, endpoint_id=11, params=None):
    """Send a command specifically formatted for Safe4 ZigBee Door Lock using Nordic Semiconductor format.

    Args:
        hass: Home Assistant instance
        ieee: IEEE address of the device
        command: Command to send (ID or name)
        cluster_id: Zigbee cluster ID
        endpoint_id: Endpoint ID (must be 11 for Safe4 ZigBee Door Lock)
        params: Optional parameters (should be None for lock/unlock commands)

    Returns:
        True if successful, False otherwise
    """
    # Always use zigbee integration service for Safe4 ZigBee Door Lock with Nabu Casa
    if not hass.services.has_service("zigbee", "issue_zigbee_cluster_command"):
        _LOGGER.error("Nabu Casa zigbee command service not available - required for Safe4 ZigBee Door Lock")
        return False

    # Format service data exactly as required by Safe4 specification
    try:
        # IMPORTANT: According to Safe4 ZigBee Door Lock specification:
        # - MUST use endpoint 11
        # - MUST use profile 0x0104 (Home Automation)
        # - Command format: zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 <command id>
        # - MUST NOT include any parameters for lock/unlock commands

        # Format IEEE address if needed - ensure it has colons for Nabu Casa
        if ':' not in ieee:
            formatted_ieee = ':'.join([ieee[i:i+2] for i in range(0, len(ieee), 2)])
        else:
            formatted_ieee = ieee

        # Convert command to integer if it's not already
        if isinstance(command, str) and command.startswith('0x'):
            command = int(command, 16)
        elif isinstance(command, str) and command.isdigit():
            command = int(command)

        # Build service data exactly as expected by Nabu Casa ZBT-1
        service_data = {
            "ieee": formatted_ieee,   # IEEE address with colons
            "endpoint_id": 11,       # MUST be exactly 11 per Safe4 spec
            "cluster_id": 0x0101,    # MUST be Door Lock cluster 0x0101
            "profile_id": 0x0104,    # MUST be exactly 0x0104 (HA profile) per spec
            "command": command,      # Command ID as integer (0x00=lock, 0x01=unlock)
            "command_type": "server",
            "manufacturer_code": 0    # Standard manufacturer code
        }

        # CRITICAL: For Safe4 ZigBee Door Lock:
        # - Lock command (0x00) MUST NOT have any parameters
        # - Unlock command (0x01) MUST NOT have any parameters
        # Only add params for other commands if explicitly needed
        if params and command not in [0x00, 0x01, 0, 1]:
            service_data["params"] = params
        elif command in [0x00, 0x01, 0, 1]:
            # Ensure no params for lock/unlock commands
            if "params" in service_data:
                del service_data["params"]

        # Log exact command format matching the Safe4 specification example
        command_name = "lock" if command in [0, 0x00] else "unlock" if command in [1, 0x01] else f"command 0x{command:02x}"
        command_str = f"zcl cmd {formatted_ieee} 11 0x0101 -p 0x0104 0x{command:02x}"

        _LOGGER.info(f"Sending Safe4 ZigBee Door Lock {command_name} command: {command_str}")
        _LOGGER.info(f"Service data: {service_data}")

        # Send the command using zigbee integration service
        try:
            await hass.services.async_call(
                "zigbee", "issue_zigbee_cluster_command", service_data, blocking=True
            )
            _LOGGER.info(f"Safe4 {command_name} command sent successfully")
            return True
        except Exception as e:
            _LOGGER.error(f"Error in zigbee.issue_zigbee_cluster_command: {e}")
            return False
    except Exception as e:
        import traceback
        _LOGGER.error(f"Failed to send Safe4 ZigBee command: {e}")
        _LOGGER.error(f"Traceback: {traceback.format_exc()}")
        _LOGGER.error(f"Service data attempted: {service_data if 'service_data' in locals() else 'Not created'}")
        return False


async def async_read_attribute_zbt1(hass, ieee, cluster_id, attribute_id, endpoint_id=11):
    """Read an attribute from Safe4 ZigBee Door Lock using correct formatting.

    Args:
        hass: Home Assistant instance
        ieee: IEEE address of the device
        cluster_id: Zigbee cluster ID (should be 0x0101 for lock attributes, 0x0001 for power)
        attribute_id: Attribute ID to read
        endpoint_id: Endpoint ID (must be 11 for Safe4 spec)

    Returns:
        True if the read request was sent successfully, None if failed
    """
    # Always use zigbee integration service for Safe4 ZigBee Door Lock with Nabu Casa
    if not hass.services.has_service("zigbee", "read_zigbee_cluster_attribute"):
        _LOGGER.error("Nabu Casa zigbee.read_zigbee_cluster_attribute service not available")
        return None

    # Format according to Safe4 ZigBee Door Lock specification
    try:
        # Format IEEE address if needed - ensure it has colons for Nabu Casa
        if ':' not in ieee:
            formatted_ieee = ':'.join([ieee[i:i+2] for i in range(0, len(ieee), 2)])
        else:
            formatted_ieee = ieee

        # Build service data exactly as needed for Nabu Casa ZBT-1
        service_data = {
            "ieee": formatted_ieee,
            "endpoint_id": 11,       # MUST be exactly 11 per Safe4 spec
            "cluster_id": cluster_id,
            "attribute": attribute_id,
            "cluster_type": "in",
            "profile_id": 0x0104,    # MUST be exactly 0x0104 (HA profile) per spec
            "manufacturer_code": 0    # Standard manufacturer code
        }

        # Log read attribute operation with details
        attr_name = get_attribute_name(cluster_id, attribute_id)
        _LOGGER.info(f"Reading Safe4 attribute {attr_name} (0x{attribute_id:04x}) from cluster 0x{cluster_id:04x} on endpoint 11")
        _LOGGER.debug(f"Read attribute service data: {service_data}")

        try:
            await hass.services.async_call(
                "zigbee", "read_zigbee_cluster_attribute", service_data, blocking=True
            )
            _LOGGER.info(f"Attribute read request sent successfully")
            return True
        except Exception as e:
            _LOGGER.error(f"Error in zigbee.read_zigbee_cluster_attribute: {e}")
            return None
    except Exception as e:
        import traceback
        _LOGGER.error(f"Failed to read Safe4 ZigBee attribute: {e}")
        _LOGGER.error(f"Traceback: {traceback.format_exc()}")
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
