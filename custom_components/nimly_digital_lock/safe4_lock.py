"""Safe4 lock implementation for Nimly digital locks."""

import logging
import asyncio

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

# Safe4 Door Lock Constants
SAFE4_DOOR_LOCK_CLUSTER = 0x0101  # Door Lock cluster
SAFE4_POWER_CLUSTER = 0x0001  # Power Configuration cluster
SAFE4_LOCK_COMMAND = 0x00  # Lock Door Command
SAFE4_UNLOCK_COMMAND = 0x01  # Unlock Door Command

# Common endpoint IDs for locks
# NOTE: For Nordic ZBT-1 locks, endpoint MUST be 11 per specification
# Prioritize endpoint 11 for Safe4 locks
COMMON_ENDPOINTS = [11, 1, 242, 2, 3]

# Helper function to discover available zigbee services
def discover_available_services(hass):
    """Discover all available Zigbee services in Home Assistant."""
    available_services = {}
    for domain in ["zigbee", "zha"]:
        domain_services = []
        all_services = hass.services.async_services().get(domain, {})
        for service_name in all_services:
            if any(keyword in service_name for keyword in ["zigbee", "cluster", "command", "attribute"]):
                domain_services.append(service_name)
        if domain_services:
            available_services[domain] = domain_services

    return available_services

async def send_safe4_lock_command(hass, ieee_address):
    """Send lock command to a Safe4 ZigBee door lock."""
    return await _send_lock_command(hass, ieee_address, SAFE4_LOCK_COMMAND)

async def send_safe4_unlock_command(hass, ieee_address):
    """Send unlock command to a Safe4 ZigBee door lock."""
    return await _send_lock_command(hass, ieee_address, SAFE4_UNLOCK_COMMAND)

async def _send_lock_command(hass, ieee_address, command):
    """Send a lock or unlock command to the Safe4 lock device.

    For Nordic ZBT-1, the command format must follow exactly:
    zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 <command id>

    Where:
    - endpoint MUST be 11
    - cluster MUST be 0x0101 (Door Lock)
    - profile MUST be 0x0104 (Home Automation)
    - command MUST be 0x00 (lock) or 0x01 (unlock)
    - NO parameters are allowed
    """
    command_name = "lock" if command == SAFE4_LOCK_COMMAND else "unlock"
    _LOGGER.info(f"Sending {command_name} command to Safe4 lock {ieee_address} using Nordic ZBT-1 format")

    # First, discover available services in Home Assistant
    available_services = discover_available_services(hass)
    _LOGGER.debug(f"Available Zigbee services: {available_services}")

    # If we found services, use them directly
    service_domains = []
    service_methods = []

    # Add discovered services to our list
    for domain, methods in available_services.items():
        service_domains.append(domain)
        service_methods.extend(methods)

    # If no services were discovered, use our default list
    if not service_domains:
        service_domains = ["zigbee", "zha"]
    if not service_methods:
        service_methods = [
            "issue_zigbee_cluster_command", 
            "send_zigbee_command", 
            "command", 
            "execute_zigbee_command", 
            "issue_command", 
            "send_command",
            "command_server"
        ]

    # Use a cleaner implementation for IEEE normalization
    from .zha_mapping import normalize_ieee
    ieee_formats = normalize_ieee(ieee_address)
    ieee_no_colons = ieee_formats["no_colons"]
    ieee_with_colons = ieee_formats["with_colons"]

    # Prepare all IEEE formats to try
    ieee_formats = [
        ieee_address,
        ieee_no_colons, 
        ieee_with_colons,
        # Add the known ZHA device IEEE as a fallback
        "f4:ce:36:0a:04:4d:31:f5",
        "f4ce360a044d31f5"
    ]

    # Log what we're going to try
    _LOGGER.debug(f"Will try service domains: {service_domains}")
    _LOGGER.debug(f"Will try service methods: {service_methods}")

    # Try the exact Nordic ZBT-1 format first (endpoint 11 ONLY first)
    # This is critical - the Nordic docs specify endpoint MUST be 11
    for ieee in ieee_formats:
        for service_domain in service_domains:
            for service_method in service_methods:
                if not hass.services.has_service(service_domain, service_method):
                    continue

                _LOGGER.debug(f"Trying exact Nordic ZBT-1 format with endpoint 11, {service_domain}.{service_method} and IEEE {ieee}")

                # EXACT format per Nordic ZBT-1 specification
                # zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 <command id>
                service_data = {
                    "ieee": ieee,
                    "endpoint_id": 11,      # MUST be 11 for ZBT-1
                    "cluster_id": 0x0101,   # Door Lock cluster
                    "command": command,     # 0x00 (lock) or 0x01 (unlock)
                    "command_type": "server"
                }

                # Try with profile parameter for Nabu Casa
                if service_domain == "zigbee":
                    try:
                        service_data["profile"] = 0x0104  # Home Automation profile
                    except Exception:
                        # If profile not supported, continue without it
                        pass

                # CRITICAL: For ZBT-1 per Nordic spec, NO parameters allowed
                # Different from standard Zigbee where PIN is sometimes needed
                try:
                    # Try both with empty params and without params key
                    # Some implementations don't support params at all
                    service_data_with_params = {**service_data, "params": {}}

                    try:
                        # First try with empty params
                        await hass.services.async_call(
                            service_domain,
                            service_method,
                            service_data_with_params,
                            blocking=True
                        )
                        _LOGGER.info(f"Successfully sent {command_name} command using endpoint 11 with empty params")
                        return True
                    except Exception as e:
                        if "extra keys not allowed" in str(e).lower() or "params" in str(e).lower():
                            # Try without params key at all
                            await hass.services.async_call(
                                service_domain,
                                service_method,
                                service_data,  # Original without params
                                blocking=True
                            )
                            _LOGGER.info(f"Successfully sent {command_name} command using endpoint 11 without params key")
                            return True
                        else:
                            # Some other error, continue to next method
                            pass

                except Exception as e:
                    # Continue to next method
                    pass

    # If the exact Nordic format failed, try with other endpoints as fallback
    # Use a prioritized list with endpoint 11 first
    endpoints = [11, 1, 242, 2, 3]

    # Try each endpoint with each address format and service domain
    for endpoint_id in endpoints:
        for ieee in ieee_formats:
            for service_domain in service_domains:
                for service_method in service_methods:
                    try:
                        # Check if the service exists before trying
                        if not hass.services.has_service(service_domain, service_method):
                            continue

                        _LOGGER.debug(f"Trying endpoint {endpoint_id} with {command_name} command using {service_domain}.{service_method} and IEEE {ieee}")

                        # Prepare service data
                        service_data = {
                            "ieee": ieee,
                            "endpoint_id": endpoint_id,
                            "cluster_id": SAFE4_DOOR_LOCK_CLUSTER,
                            "command": command,
                            "command_type": "server"
                        }

                        # Try with and without profile parameter
                        if service_domain == "zigbee":
                            try:
                                service_data["profile"] = 0x0104
                            except Exception:
                                # If profile not supported, continue without it
                                pass

                        # Try both with empty params and without params
                        try:
                            # First try with empty params
                            service_data_with_params = {**service_data, "params": {}}
                            await hass.services.async_call(
                                service_domain,
                                service_method,
                                service_data_with_params,
                                blocking=True
                            )
                            _LOGGER.info(f"Successfully sent {command_name} command to endpoint {endpoint_id}")
                            return True
                        except Exception as e:
                            # If failed with params, try without
                            if "extra keys not allowed" in str(e).lower() or "params" in str(e).lower():
                                await hass.services.async_call(
                                    service_domain,
                                    service_method,
                                    service_data,  # Without params
                                    blocking=True
                                )
                                _LOGGER.info(f"Successfully sent {command_name} command to endpoint {endpoint_id} without params")
                                return True

                    except Exception as e:
                        # Continue to next method
                        pass

        # If we get this far, try with network address
        for service_method in service_methods:
            try:
                # Try with network address (only works with ZHA)
                # Use ieee key with nwk format for ZHA
                service_data = {
                    "ieee": "0x7FDB",  # The known network address used as ieee
                    "endpoint_id": endpoint_id,
                    "cluster_id": SAFE4_DOOR_LOCK_CLUSTER,
                    "command": command,
                    "command_type": "server",
                    "params": {}
                }

                # Check if the service exists
                if not hass.services.has_service("zha", service_method):
                    _LOGGER.debug(f"Service zha.{service_method} not available for network address, skipping")
                    continue

                try:
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
            except Exception as e:
                _LOGGER.debug(f"Failed to setup network address command: {e}")

    # If we get here, none of the endpoints worked
    _LOGGER.error(f"All endpoints failed for {command_name} command")
    return False

async def read_safe4_attribute(hass, ieee_address, cluster_id, attribute_id):
    """Read an attribute from the Safe4 lock device."""

    # First, discover available services in Home Assistant
    available_services = discover_available_services(hass)
    _LOGGER.debug(f"Available Zigbee attribute services: {available_services}")

    # If we found services, use them directly
    service_domains = []
    service_methods = []

    # Add discovered services to our list
    for domain, methods in available_services.items():
        service_domains.append(domain)
        service_methods.extend(methods)

    # If no services were discovered, use our default list
    if not service_domains:
        service_domains = ["zigbee", "zha"]
    if not service_methods:
        service_methods = [
            "get_zigbee_cluster_attribute", 
            "read_zigbee_cluster_attribute",
            "read_attribute",
            "get_attribute",
            "get_zigbee_attribute",
            "read_zigbee_attribute",
            "get_cluster_attribute",
            "cluster_attribute",
            "attribute_read"
        ]

    # Use a cleaner import of normalize_ieee
    from .zha_mapping import normalize_ieee
    ieee_formats = normalize_ieee(ieee_address)
    ieee_no_colons = ieee_formats["no_colons"]
    ieee_with_colons = ieee_formats["with_colons"]

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
    endpoints = [11, 1, 242, 2, 3]

    # Track whether any service calls were attempted
    service_calls_attempted = False

    for endpoint_id in endpoints:
        for ieee in ieee_formats:
            for service_domain in service_domains:
                for service_method in service_methods:
                    try:
                        # Check if the service exists before trying to call it
                        if not hass.services.has_service(service_domain, service_method):
                            continue

                        service_calls_attempted = True
                        _LOGGER.debug(f"Reading attribute {attribute_id} from cluster {cluster_id} endpoint {endpoint_id} using {service_domain}.{service_method}")

                        # Prepare service data
                        service_data = {
                            "ieee": ieee,
                            "endpoint_id": endpoint_id,
                            "cluster_id": cluster_id,
                            "cluster_type": cluster_type,
                            "attribute": attribute_id
                        }

                        # Handle optional parameters based on service domain
                        if service_domain == "zha" and "get_zigbee_cluster_attribute" in service_method:
                            # Only add params if service supports it
                            try:
                                service_data["params"] = {"pin_code": ""}
                            except Exception:
                                # If params not supported, continue without it
                                pass

                        # Call the service with a shorter timeout
                        await hass.services.async_call(
                            service_domain,
                            service_method,
                            service_data,
                            blocking=True
                        )

                        # If we reach here, the call succeeded without exception
                        # Check if a result was stored in the data store
                        for check_ieee in [ieee, ieee_address]:
                            attr_key = f"{DOMAIN}:{check_ieee}:{attribute_id}"
                            if attr_key in hass.data:
                                result = hass.data.get(attr_key)
                                if result is not None:
                                    _LOGGER.info(f"Successfully read attribute {attribute_id} from endpoint {endpoint_id}: {result}")
                                    return result

                    except Exception as e:
                        # Continue silently to try next method
                        pass

    # If no service calls were attempted, log a more helpful message
    if not service_calls_attempted:
        _LOGGER.error("No compatible Zigbee services found for reading attributes - please check your Zigbee integration")
    else:
        _LOGGER.warning(f"Failed to read attribute {attribute_id} from cluster {cluster_id} with all methods")
        return None

    try:
        _LOGGER.info("Attempting direct ZHA gateway access as fallback")
        from homeassistant.components.zha.core.gateway import ZHAGateway
        from homeassistant.components.zha.core.const import DOMAIN as ZHA_DOMAIN

        if ZHA_DOMAIN in hass.data:
            zha_gateway = hass.data[ZHA_DOMAIN].get("gateway")
            if zha_gateway and hasattr(zha_gateway, "devices"):
                # Try to find our device
                device = None
                for dev in zha_gateway.devices.values():
                    for ieee_format in ieee_formats:
                        if hasattr(dev, "ieee") and str(dev.ieee).replace(':', '').lower() == ieee_format.replace(':', '').lower():
                            device = dev
                            _LOGGER.info(f"Found ZHA device: {device.ieee}")
                            break
                    if device:
                        break

                if device and hasattr(device, "endpoints"):
                    # Try all endpoints to find the one with our cluster
                    for ep_id, endpoint in device.endpoints.items():
                        # Check if this endpoint has the cluster we need
                        try:
                            # Different properties for different cluster types
                            if cluster_type == "in":
                                cluster = endpoint.in_clusters.get(cluster_id)
                            else:
                                cluster = endpoint.out_clusters.get(cluster_id)

                            if cluster:
                                _LOGGER.info(f"Found cluster {cluster_id} on endpoint {ep_id}")
                                # Try to read the attribute directly
                                result = await cluster.read_attributes([attribute_id])
                                if result and attribute_id in result[0]:
                                    value = result[0][attribute_id]
                                    _LOGGER.info(f"Successfully read attribute {attribute_id} with value {value} via direct ZHA")
                                    # Store the result in our data store
                                    hass.data[f"{DOMAIN}:{ieee_address}:{attribute_id}"] = value
                                    return value
                        except Exception as e:
                            _LOGGER.debug(f"Failed to read attribute via direct ZHA on endpoint {ep_id}: {e}")
    except Exception as e:
        _LOGGER.debug(f"Failed to use direct ZHA gateway access: {e}")

    # If we reach here, all attempts failed
    _LOGGER.warning(f"Failed to read attribute {attribute_id} from cluster {cluster_id} with all methods")
    return None
