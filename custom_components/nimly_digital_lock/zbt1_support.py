"""ZBT-1 support for Nabu Casa Zigbee implementation."""

import logging

_LOGGER = logging.getLogger(__name__)

# Common endpoints for ZBT-1 locks
# NOTE: For Nordic ZBT-1 locks, endpoint MUST be 11 per specification
ZBT1_ENDPOINTS = [11, 1, 242, 2, 3]

async def get_zbt1_endpoints(hass, ieee_address):
    """Get the list of endpoints for a ZBT-1 device."""

    try:
        # Import constants from zha_mapping module
        from .zha_mapping import ZBT1_ENDPOINTS

        # Default endpoints for Nordic ZBT-1 per specification
        default_endpoints = [11, 1, 2, 3]  # Default endpoints per Nordic spec

        if ZBT1_ENDPOINTS:
            return ZBT1_ENDPOINTS
        else:
            _LOGGER.debug(f"No endpoints defined in ZBT1_ENDPOINTS, using defaults")
            return default_endpoints
    except Exception as e:
        _LOGGER.warning(f"Error retrieving ZBT1 endpoints: {e}")
        return [11, 1, 2, 3]  # Return default endpoints on error

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

    # Get endpoint from kwargs or use default of 11 for Nordic ZBT-1 per spec
    endpoint_id = kwargs.get("endpoint_id", 11)
    manufacturer = kwargs.get("manufacturer", None)
    cluster_type = kwargs.get("cluster_type", "in")

    # Normalize IEEE address
    from .zha_mapping import normalize_ieee
    ieee_formats = normalize_ieee(ieee_address)
    ieee_no_colons = ieee_formats["no_colons"]
    ieee_with_colons = ieee_formats["with_colons"]

    # List of endpoints to try - start with requested endpoint, then try known working endpoints
    endpoints_to_try = [endpoint_id]
    if endpoint_id != 11:
        endpoints_to_try.append(11)  # Always try endpoint 11 for Nordic ZBT-1

    # Add other common endpoints if not already included
    for ep in [1, 242, 2, 3]:
        if ep not in endpoints_to_try:
            endpoints_to_try.append(ep)

    # IEEE formats to try
    ieee_formats_to_try = [
        ieee_address,
        ieee_with_colons,
        ieee_no_colons,
        # Add known fallback formats
        "f4:ce:36:0a:04:4d:31:f5",
        "f4ce360a044d31f5"
    ]

    # Determine which service to use - try both zigbee (Nabu Casa) and ZHA
    service_domains = ["zigbee", "zha"]
    service_methods = [
        "get_zigbee_cluster_attribute", 
        "read_zigbee_cluster_attribute",
        "read_attribute", 
        "get_attribute"
    ]

    # Try each endpoint with each IEEE format
    for endpoint in endpoints_to_try:
        for ieee in ieee_formats_to_try:
            # Try each service domain and method until one works
            for service_domain in service_domains:
                for service_method in service_methods:
                    # Check if the service exists
                    if not hass.services.has_service(service_domain, service_method):
                        continue

                    # Prepare service data
                    service_data = {
                        "ieee": ieee,
                        "endpoint_id": endpoint,
                        "cluster_id": cluster_id,
                        "cluster_type": cluster_type,
                        "attribute": attribute
                    }

                    if manufacturer is not None:
                        service_data["manufacturer"] = manufacturer

                    try:
                        # Call the service
                        _LOGGER.debug(f"Trying {service_domain}.{service_method} on endpoint {endpoint} with IEEE {ieee}")
                        await hass.services.async_call(
                            service_domain,
                            service_method,
                            service_data,
                            blocking=True
                        )

                        # For ZHA, the result is stored in the hass.data structure
                        from .const import DOMAIN
                        # Check both the original IEEE and the specific format that worked
                        for ieee_check in [ieee_address, ieee]:
                            result = hass.data.get(f"{DOMAIN}:{ieee_check}:{attribute}")
                            if result is not None:
                                _LOGGER.info(f"Successfully read attribute {attribute} on endpoint {endpoint}: {result}")
                                return result

                    except Exception as e:
                        # Continue silently to try next method
                        pass

    # If we reach here, all methods failed
    _LOGGER.error(f"Failed to read attribute {attribute} from all endpoints with all methods")
    return None