"""Safe4 lock implementation for Nimly digital locks."""

import logging
import asyncio

_LOGGER = logging.getLogger(__name__)

# Safe4 Door Lock Constants
SAFE4_DOOR_LOCK_CLUSTER = 0x0101  # Door Lock cluster
SAFE4_POWER_CLUSTER = 0x0001  # Power Configuration cluster
SAFE4_LOCK_COMMAND = 0x00  # Lock Door Command
SAFE4_UNLOCK_COMMAND = 0x01  # Unlock Door Command

# Common endpoint IDs for locks
COMMON_ENDPOINTS = [1, 11, 242, 2, 3]

async def send_safe4_lock_command(hass, ieee_address):
    """Send lock command to a Safe4 ZigBee door lock."""
    return await _send_lock_command(hass, ieee_address, SAFE4_LOCK_COMMAND)

async def send_safe4_unlock_command(hass, ieee_address):
    """Send unlock command to a Safe4 ZigBee door lock."""
    return await _send_lock_command(hass, ieee_address, SAFE4_UNLOCK_COMMAND)

async def _send_lock_command(hass, ieee_address, command):
    """Send a lock or unlock command to the Safe4 lock device."""
    command_name = "lock" if command == SAFE4_LOCK_COMMAND else "unlock"
    _LOGGER.info(f"Sending {command_name} command to Safe4 lock {ieee_address}")

    # Get the service domain to use - prefer zigbee (Nabu Casa) but fall back to ZHA
    service_domain = "zigbee"
    service_method = "issue_zigbee_cluster_command"

    # Check if the zigbee service is available, fall back to ZHA if not
    has_zigbee = hass.services.has_service("zigbee", service_method)
    if not has_zigbee:
        service_domain = "zha"
        _LOGGER.debug(f"Zigbee service not available, using ZHA service instead")

    # Try each common endpoint until one works
    for endpoint_id in COMMON_ENDPOINTS:
        try:
            _LOGGER.debug(f"Trying endpoint {endpoint_id} with {command_name} command")

            # Prepare service data for the direct command
            service_data = {
                "ieee": ieee_address,
                "endpoint_id": endpoint_id,
                "cluster_id": SAFE4_DOOR_LOCK_CLUSTER,
                "command": command,
                "command_type": "server",
                "params": {}
            }

            # Call the service
            await hass.services.async_call(
                service_domain,
                service_method,
                service_data,
                blocking=True
            )

            _LOGGER.info(f"Successfully sent {command_name} command to endpoint {endpoint_id}")
            return True
        except Exception as e:
            _LOGGER.warning(f"Failed to send {command_name} command to endpoint {endpoint_id}: {e}")

    # If we get here, none of the endpoints worked
    _LOGGER.error(f"All endpoints failed for {command_name} command")
    return False

async def read_safe4_attribute(hass, ieee_address, cluster_id, attribute_id):
    """Read an attribute from the Safe4 lock device."""

    # Get the service domain to use - prefer zigbee (Nabu Casa) but fall back to ZHA
    service_domain = "zigbee"
    service_method = "get_zigbee_cluster_attribute"

    # Check if the zigbee service is available, fall back to ZHA if not
    has_zigbee = hass.services.has_service("zigbee", service_method)
    if not has_zigbee:
        service_domain = "zha"
        _LOGGER.debug(f"Zigbee service not available, using ZHA service instead")

    # Try each common endpoint until one works
    for endpoint_id in COMMON_ENDPOINTS:
        try:
            _LOGGER.debug(f"Reading attribute {attribute_id} from cluster {cluster_id} at endpoint {endpoint_id}")

            # Prepare service data for the attribute read
            service_data = {
                "ieee": ieee_address,
                "endpoint_id": endpoint_id,
                "cluster_id": cluster_id,
                "attribute": attribute_id,
                "manufacturer": None
            }

            # Call the service
            result = await hass.services.async_call(
                service_domain,
                service_method,
                service_data,
                blocking=True,
                return_response=True
            )

            _LOGGER.info(f"Successfully read attribute {attribute_id}: {result}")
            return result
        except Exception as e:
            _LOGGER.warning(f"Failed to read attribute {attribute_id} from endpoint {endpoint_id}: {e}")

    # If we get here, none of the endpoints worked
    _LOGGER.error(f"All endpoints failed for reading attribute {attribute_id}")
    return None