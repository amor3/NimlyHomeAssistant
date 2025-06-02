"""ZBT-1 support for Nabu Casa Zigbee implementation."""

import logging

_LOGGER = logging.getLogger(__name__)

# Common endpoints for ZBT-1 locks
ZBT1_ENDPOINTS = [1, 11, 242, 2, 3]

async def get_zbt1_endpoints(hass, ieee_address):
    """Get the list of endpoints for a ZBT-1 device."""
    return ZBT1_ENDPOINTS

async def async_send_command_zbt1(hass, ieee_address, cluster_id, command, **kwargs):
    """Send a command to a ZBT-1 device using the Nabu Casa Zigbee implementation."""
    _LOGGER.info(f"Sending ZBT-1 command {command} to cluster {cluster_id}")

    endpoint_id = kwargs.get("endpoint_id", 1)
    command_type = kwargs.get("command_type", "server")
    params = kwargs.get("params", {})

    # Determine which service to use - prefer zigbee (Nabu Casa) but fall back to ZHA
    service_domain = "zigbee"
    service_method = "issue_zigbee_cluster_command"

    # Check if the zigbee service is available, fall back to ZHA if not
    has_zigbee = hass.services.has_service("zigbee", service_method)
    if not has_zigbee:
        service_domain = "zha"
        _LOGGER.debug(f"Zigbee service not available, using ZHA service instead")

    # Prepare service data
    service_data = {
        "ieee": ieee_address,
        "endpoint_id": endpoint_id,
        "cluster_id": cluster_id,
        "command": command,
        "command_type": command_type
    }

    if params:
        service_data["params"] = params

    try:
        # Call the service
        await hass.services.async_call(
            service_domain,
            service_method,
            service_data,
            blocking=True
        )
        _LOGGER.info(f"Successfully sent command {command} to endpoint {endpoint_id}")
        return True
    except Exception as e:
        _LOGGER.error(f"Failed to send command {command} to endpoint {endpoint_id}: {e}")
        return False

async def async_read_attribute_zbt1(hass, ieee_address, cluster_id, attribute, **kwargs):
    """Read an attribute from a ZBT-1 device using the Nabu Casa Zigbee implementation."""
    _LOGGER.info(f"Reading ZBT-1 attribute {attribute} from cluster {cluster_id}")

    endpoint_id = kwargs.get("endpoint_id", 1)
    manufacturer = kwargs.get("manufacturer", None)

    # Determine which service to use - prefer zigbee (Nabu Casa) but fall back to ZHA
    service_domain = "zigbee"
    service_method = "get_zigbee_cluster_attribute"

    # Check if the zigbee service is available, fall back to ZHA if not
    has_zigbee = hass.services.has_service("zigbee", service_method)
    if not has_zigbee:
        service_domain = "zha"
        _LOGGER.debug(f"Zigbee service not available, using ZHA service instead")

    # Prepare service data
    service_data = {
        "ieee": ieee_address,
        "endpoint_id": endpoint_id,
        "cluster_id": cluster_id,
        "attribute": attribute
    }

    if manufacturer is not None:
        service_data["manufacturer"] = manufacturer

    try:
        # Call the service
        result = await hass.services.async_call(
            service_domain,
            service_method,
            service_data,
            blocking=True,
            return_response=True
        )
        _LOGGER.info(f"Successfully read attribute {attribute}: {result}")
        return result
    except Exception as e:
        _LOGGER.error(f"Failed to read attribute {attribute} from endpoint {endpoint_id}: {e}")
        return None