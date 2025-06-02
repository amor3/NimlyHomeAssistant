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

    # Get the service domain to use - try both zigbee (Nabu Casa) and ZHA
    service_domains = ["zigbee", "zha"]
    service_method = "issue_zigbee_cluster_command"

    # Normalize IEEE address - try with and without colons
    ieee_no_colons = ieee_address.replace(':', '')
    ieee_with_colons = ':'.join([ieee_no_colons[i:i+2] for i in range(0, len(ieee_no_colons), 2)])

    # Prepare all IEEE formats to try
    ieee_formats = [
        ieee_address,
        ieee_no_colons, 
        ieee_with_colons,
        # Add the known ZHA device IEEE as a fallback
        "f4:ce:36:0a:04:4d:31:f5",
        "f4ce360a044d31f5"
    ]

    # Try each common endpoint with each address format and service domain
    for endpoint_id in COMMON_ENDPOINTS:
        for ieee in ieee_formats:
            for service_domain in service_domains:
                try:
                    _LOGGER.debug(f"Trying endpoint {endpoint_id} with {command_name} command using {service_domain} service and IEEE {ieee}")

                    # Prepare service data for the direct command
                    service_data = {
                        "ieee": ieee,
                        "endpoint_id": endpoint_id,
                        "cluster_id": SAFE4_DOOR_LOCK_CLUSTER,
                        "command": command,
                        "command_type": "server",
                        "params": {}
                    }

                    # Check if the service exists
                    if not hass.services.has_service(service_domain, service_method):
                        _LOGGER.debug(f"Service {service_domain}.{service_method} not available, skipping")
                        continue

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
                    _LOGGER.debug(f"Failed to send {command_name} command to endpoint {endpoint_id} with IEEE {ieee} using {service_domain}: {e}")

        # If we get this far, try with network address
        try:
            # Try with network address (only works with ZHA)
            service_data = {
                "nwk": "0x7FDB",  # The known network address
                "endpoint_id": endpoint_id,
                "cluster_id": SAFE4_DOOR_LOCK_CLUSTER,
                "command": command,
                "command_type": "server",
                "params": {}
            }

            await hass.services.async_call(
                "zha",
                service_method,
                service_data,
                blocking=True
            )

            _LOGGER.info(f"Successfully sent {command_name} command using network address to endpoint {endpoint_id}")
            return True
        except Exception as e:
            _LOGGER.debug(f"Failed to send {command_name} command using network address: {e}")

    # If we get here, none of the endpoints worked
    _LOGGER.error(f"All endpoints failed for {command_name} command")
    return False

async def read_safe4_attribute(hass, ieee_address, cluster_id, attribute_id):
    """Read an attribute from the Safe4 lock device."""

    # Try both zigbee (Nabu Casa) and ZHA services
    service_domains = ["zigbee", "zha"]
    service_methods = ["get_zigbee_cluster_attribute", "read_zigbee_cluster_attribute"]

    # Normalize IEEE address - try with and without colons
    ieee_no_colons = ieee_address.replace(':', '')
    ieee_with_colons = ':'.join([ieee_no_colons[i:i+2] for i in range(0, len(ieee_no_colons), 2)])

    # Prepare all IEEE formats to try
    ieee_formats = [
        ieee_address,
        ieee_no_colons, 
        ieee_with_colons,
        # Add the known ZHA device IEEE as a fallback
        "f4:ce:36:0a:04:4d:31:f5",
        "f4ce360a044d31f5"
    ]

    # For ZBT-1 devices, use the default cluster type
    cluster_type = "in"

    # Try with the recommended endpoint 11 first, then others if that fails
    endpoints = [11, 1, 2, 3, 242]

    for endpoint_id in endpoints:
        for ieee in ieee_formats:
            for service_domain in service_domains:
                for service_method in service_methods:
                    try:
                        # Check if the service exists before trying to call it
                        if not hass.services.has_service(service_domain, service_method):
                            _LOGGER.debug(f"Service {service_domain}.{service_method} not available, skipping")
                            continue

                        _LOGGER.debug(f"Reading attribute {attribute_id} from cluster {cluster_id} endpoint {endpoint_id} using {service_domain}.{service_method}")

                        # Prepare service data
                        service_data = {
                            "ieee": ieee,
                            "endpoint_id": endpoint_id,
                            "cluster_id": cluster_id,
                            "cluster_type": cluster_type,
                            "attribute": attribute_id
                        }

                        # Call the service
                        await hass.services.async_call(
                            service_domain,
                            service_method,
                            service_data,
                            blocking=True
                        )

                        # If we reach here, the call succeeded
                        _LOGGER.info(f"Successfully read attribute {attribute_id} from cluster {cluster_id} endpoint {endpoint_id}")

                        # Get the value from the data store
                        if DOMAIN in hass.data:
                            result = hass.data.get(f"{DOMAIN}:{ieee}:{attribute_id}")
                            return result

                    except Exception as e:
                        _LOGGER.debug(f"Failed to read attribute with {service_domain}.{service_method}: {e}")

    # If we reach here, all attempts failed
    _LOGGER.warning(f"Failed to read attribute {attribute_id} from cluster {cluster_id} with all methods")
    return None

    # For ZBT-1 devices, use the default cluster type
    cluster_type = "in"
