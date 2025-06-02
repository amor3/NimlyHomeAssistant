"""Nabu Casa ZBT-1 specific support for Nimly Digital Lock.

This module adds specific support functions for the Nabu Casa ZBT-1 device.
"""

import logging

_LOGGER = logging.getLogger(__name__)


def get_zbt1_endpoints(hass, device_ieee):
    """Attempt to discover all endpoints for a ZBT-1 device.

    Args:
        hass: Home Assistant instance
        device_ieee: IEEE address of the device

    Returns:
        List of endpoint IDs or None if not found
    """
    # Check if we have zigbee service
    if not hass.services.has_service("zigbee", "get_devices"):
        _LOGGER.debug("Zigbee get_devices service not available")
        return None

    # For now, we'll return a list of common endpoints to try
    # This is a fallback method until we can properly discover endpoints
    _LOGGER.debug(f"Using common endpoints for device {device_ieee}")
    return [1, 2, 3, 242]


async def async_read_attribute_zbt1(hass, ieee, cluster_id, attribute_id, endpoint_id=1):
    """Read an attribute specifically with ZBT-1 formatting.

    Args:
        hass: Home Assistant instance
        ieee: IEEE address of the device
        cluster_id: Zigbee cluster ID
        attribute_id: Attribute ID to read
        endpoint_id: Endpoint ID (default: 1)

    Returns:
        Attribute value or None if not found
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
            "cluster_type": "in"
        }

        _LOGGER.debug(f"Reading ZBT-1 attribute: {service_data}")
        await hass.services.async_call(
            "zigbee", "read_zigbee_cluster_attribute", service_data
        )
        return True
    except Exception as e:
        _LOGGER.warning(f"Failed to read ZBT-1 attribute: {e}")
        return None


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

    # Attempt to send command with specific ZBT-1 format based on Nordic Semiconductor CLI
    try:
        # For ZBT-1, we need to use endpoint 11 and specify the Home Automation profile
        service_data = {
            "ieee": ieee,
            "command": command,
            "cluster_id": cluster_id,
            "endpoint_id": endpoint_id,  # Default to endpoint 11 for ZBT-1
            "command_type": "server",
            "profile_id": 0x0104  # Home Automation profile (0x0104)
        }

        if params:
            service_data["params"] = params

        _LOGGER.debug(f"Sending ZBT-1 command using Nordic format: {service_data}")
        await hass.services.async_call(
            "zigbee", "issue_zigbee_cluster_command", service_data
        )
        return True
    except Exception as e:
        _LOGGER.warning(f"Failed to send ZBT-1 command: {e}")
        return False


import logging

_LOGGER = logging.getLogger(__name__)

def get_zbt1_endpoints(hass, device_ieee):
    """Attempt to discover all endpoints for a ZBT-1 device.

    Args:
        hass: Home Assistant instance
        device_ieee: IEEE address of the device

    Returns:
        List of endpoint IDs or None if not found
    """
    # Check if we have zigbee service
    if not hass.services.has_service("zigbee", "get_devices"):
        _LOGGER.debug("Zigbee get_devices service not available")
        return None

    # Based on Nordic Semiconductor Zigbee CLI documentation, endpoint 11 is used for the lock cluster
    # We'll still include other common endpoints as fallbacks
    _LOGGER.debug(f"Using ZBT-1 endpoints for device {device_ieee}")
    return [11, 1, 2, 3, 242]

async def async_read_attribute_zbt1(hass, ieee, cluster_id, attribute_id, endpoint_id=1):
    """Read an attribute specifically with ZBT-1 formatting.

    Args:
        hass: Home Assistant instance
        ieee: IEEE address of the device
        cluster_id: Zigbee cluster ID
        attribute_id: Attribute ID to read
        endpoint_id: Endpoint ID (default: 1)

    Returns:
        Attribute value or None if not found
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
            "cluster_type": "in"
        }

        _LOGGER.debug(f"Reading ZBT-1 attribute: {service_data}")
        await hass.services.async_call(
            "zigbee", "read_zigbee_cluster_attribute", service_data
        )
        return True
    except Exception as e:
        _LOGGER.warning(f"Failed to read ZBT-1 attribute: {e}")
        return None

async def async_send_command_zbt1(hass, ieee, command, cluster_id, endpoint_id=1, params=None):
    """Send a command specifically formatted for ZBT-1.

    Args:
        hass: Home Assistant instance
        ieee: IEEE address of the device
        command: Command to send (ID or name)
        cluster_id: Zigbee cluster ID
        endpoint_id: Endpoint ID (default: 1)
        params: Optional parameters

    Returns:
        True if successful, False otherwise
    """
    # Check if we have the zigbee service
    if not hass.services.has_service("zigbee", "issue_zigbee_cluster_command"):
        _LOGGER.debug("Zigbee command service not available")
        return False

    # Attempt to send command with specific ZBT-1 format
    try:
        service_data = {
            "ieee": ieee,
            "command": command,
            "cluster_id": cluster_id,
            "endpoint_id": endpoint_id,
            "command_type": "server"
        }

        if params:
            service_data["params"] = params

        _LOGGER.debug(f"Sending ZBT-1 command: {service_data}")
        await hass.services.async_call(
            "zigbee", "issue_zigbee_cluster_command", service_data
        )
        return True
    except Exception as e:
        _LOGGER.warning(f"Failed to send ZBT-1 command: {e}")
        return False
