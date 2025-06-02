"""Safe4 ZigBee Door Lock implementation.

This module implements the exact command format required by Safe4 ZigBee Door Lock
according to the provided specification document.
"""

import logging

_LOGGER = logging.getLogger(__name__)

# Safe4 command constants
SAFE4_LOCK_COMMAND = 0x00
SAFE4_UNLOCK_COMMAND = 0x01
SAFE4_DOOR_LOCK_CLUSTER = 0x0101
SAFE4_POWER_CLUSTER = 0x0001
SAFE4_ENDPOINT = 11
SAFE4_PROFILE = 0x0104  # Home Automation profile

async def send_safe4_lock_command(hass, ieee):
    """Send lock command using exact Safe4 format.

    Command format: zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 0x00

    Args:
        hass: Home Assistant instance
        ieee: IEEE address (with or without colons)

    Returns:
        True if command sent successfully, False otherwise
    """
    return await send_safe4_command(hass, ieee, SAFE4_LOCK_COMMAND)

async def send_safe4_unlock_command(hass, ieee):
    """Send unlock command using exact Safe4 format.

    Command format: zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 0x01

    Args:
        hass: Home Assistant instance
        ieee: IEEE address (with or without colons)

    Returns:
        True if command sent successfully, False otherwise
    """
    return await send_safe4_command(hass, ieee, SAFE4_UNLOCK_COMMAND)

async def send_safe4_command(hass, ieee, command_id):
    """Send a command to Safe4 ZigBee Door Lock using exact specification format.

    Args:
        hass: Home Assistant instance
        ieee: IEEE address (with or without colons)
        command_id: Command ID (0x00 for lock, 0x01 for unlock)

    Returns:
        True if command sent successfully, False otherwise
    """
    # Check if the zigbee service is available
    if not hass.services.has_service("zigbee", "issue_zigbee_cluster_command"):
        _LOGGER.error("Nabu Casa zigbee service not available - cannot control Safe4 lock")
        return False

    # Format IEEE address if needed
    if ':' not in ieee:
        formatted_ieee = ':'.join([ieee[i:i+2] for i in range(0, len(ieee), 2)])
    else:
        formatted_ieee = ieee

    # Get command name for logging
    command_name = "lock" if command_id == SAFE4_LOCK_COMMAND else "unlock"

    # Prepare service data exactly as required by the spec
    service_data = {
        "ieee": formatted_ieee,
        "endpoint_id": SAFE4_ENDPOINT,       # Must be exactly 11
        "cluster_id": SAFE4_DOOR_LOCK_CLUSTER,  # 0x0101
        "profile_id": SAFE4_PROFILE,        # 0x0104
        "command": command_id,              # 0x00 or 0x01
        "command_type": "server",
        "manufacturer_code": 0              # Standard manufacturer code
    }

    # Log exact command in CLI format from the spec
    command_str = f"zcl cmd {formatted_ieee} 11 0x0101 -p 0x0104 0x{command_id:02x}"
    _LOGGER.info(f"Sending Safe4 {command_name} command: {command_str}")

    try:
        await hass.services.async_call(
            "zigbee", "issue_zigbee_cluster_command", service_data, blocking=True
        )
        _LOGGER.info(f"Safe4 {command_name} command sent successfully")
        return True
    except Exception as e:
        import traceback
        _LOGGER.error(f"Failed to send Safe4 {command_name} command: {e}")
        _LOGGER.error(f"Traceback: {traceback.format_exc()}")
        _LOGGER.error(f"Service data attempted: {service_data}")
        return False

async def read_safe4_attribute(hass, ieee, cluster_id, attribute_id):
    """Read an attribute from Safe4 ZigBee Door Lock using exact specification format.

    Args:
        hass: Home Assistant instance
        ieee: IEEE address (with or without colons)
        cluster_id: Cluster ID (0x0101 for Door Lock, 0x0001 for Power)
        attribute_id: Attribute ID to read

    Returns:
        True if read request sent successfully, False otherwise
    """
    # Check if the zigbee service is available
    if not hass.services.has_service("zigbee", "read_zigbee_cluster_attribute"):
        _LOGGER.error("Nabu Casa zigbee service not available - cannot read Safe4 attributes")
        return False

    # Format IEEE address if needed
    if ':' not in ieee:
        formatted_ieee = ':'.join([ieee[i:i+2] for i in range(0, len(ieee), 2)])
    else:
        formatted_ieee = ieee

    # Get attribute name for logging
    attr_name = attribute_id
    if cluster_id == SAFE4_DOOR_LOCK_CLUSTER:
        from .zha_mapping import LOCK_ATTRIBUTES
        for name, attr_id in LOCK_ATTRIBUTES.items():
            if attr_id == attribute_id:
                attr_name = name
                break
    elif cluster_id == SAFE4_POWER_CLUSTER:
        from .zha_mapping import POWER_ATTRIBUTES
        for name, attr_id in POWER_ATTRIBUTES.items():
            if attr_id == attribute_id:
                attr_name = name
                break

    # Prepare service data exactly as required by the spec
    service_data = {
        "ieee": formatted_ieee,
        "endpoint_id": SAFE4_ENDPOINT,       # Must be exactly 11
        "cluster_id": cluster_id,
        "attribute": attribute_id,
        "cluster_type": "in",
        "profile_id": SAFE4_PROFILE,        # 0x0104
        "manufacturer_code": 0              # Standard manufacturer code
    }

    # Log read operation
    _LOGGER.info(f"Reading Safe4 attribute {attr_name} (0x{attribute_id:04x}) from cluster 0x{cluster_id:04x}")

    try:
        await hass.services.async_call(
            "zigbee", "read_zigbee_cluster_attribute", service_data, blocking=True
        )
        _LOGGER.info(f"Safe4 attribute read request sent successfully")
        return True
    except Exception as e:
        import traceback
        _LOGGER.error(f"Failed to read Safe4 attribute: {e}")
        _LOGGER.error(f"Traceback: {traceback.format_exc()}")
        _LOGGER.error(f"Service data attempted: {service_data}")
        return False
