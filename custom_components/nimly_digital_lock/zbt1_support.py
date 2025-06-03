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

async def async_send_command_zbt1(hass, ieee, command, cluster_id, endpoint_id=11, params=None, retry_count=3):
    _LOGGER.debug(f"Sending command {command} to cluster {cluster_id} on endpoint {endpoint_id}")

    # Format IEEE address with colons
    ieee_with_colons = format_ieee_with_colons(ieee)

    # Service data for sending command
    service_data = {
        "ieee": ieee_with_colons,
        "endpoint_id": endpoint_id,
        "cluster_id": cluster_id,
        "command": command,
        "command_type": "server"
    }

    # Add params if provided
    if params is not None:
        service_data["params"] = params

    # Try both service domains
    service_domains = ["zigbee", "zha"]
    service_methods = ["issue_zigbee_cluster_command", "command"]

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
                        domain, method, service_data, blocking=True
                    )

                    _LOGGER.info(f"Successfully sent command {command} using {domain}.{method}")
                    return True
                except Exception as e:
                    _LOGGER.warning(f"Failed to send command {command} using {domain}.{method} (attempt {attempt+1}): {e}")

                    # If this is not the last attempt, wait before retrying
                    if attempt < retry_count - 1:
                        await asyncio.sleep(1.0)

    _LOGGER.error(f"Failed to send command {command} after {retry_count} attempts with all methods")
    return False

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