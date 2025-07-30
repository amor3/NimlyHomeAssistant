# """Safe4 lock implementation for Nimly digital locks."""
#
# import logging
# import asyncio
# from .const import DOMAIN
#
# _LOGGER = logging.getLogger(__name__)
#
# # Safe4 Door Lock Constants
# SAFE4_DOOR_LOCK_CLUSTER = 0x0101  # Door Lock cluster
# SAFE4_POWER_CLUSTER = 0x0001  # Power Configuration cluster
# SAFE4_LOCK_COMMAND = 0x00  # Lock Door Command
# SAFE4_UNLOCK_COMMAND = 0x01  # Unlock Door Command
#
# # Common endpoint IDs for locks
# # NOTE: For Nordic ZBT-1 locks, endpoint MUST be 11 per specification
# # Prioritize endpoint 11 for Safe4 locks
#
# # Helper function to discover available zigbee services
# def discover_available_services(hass):
#     """Discover ZHA services in Home Assistant."""
#     available_services = {}
#     domain = "zha"  # Only use ZHA domain
#     domain_services = []
#     all_services = hass.services.async_services().get(domain, {})
#     for service_name in all_services:
#         if any(keyword in service_name for keyword in ["zigbee", "cluster", "command", "attribute"]):
#             domain_services.append(service_name)
#     if domain_services:
#         available_services[domain] = domain_services
#
#     _LOGGER.debug(f"Found ZHA services: {domain_services}")
#     return available_services
#
#
# async def _send_lock_command(hass, ieee_address, command):
#     """Send a lock or unlock command to the Safe4 lock device.
#
#     For Nordic ZBT-1, the command format must follow exactly:
#     zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 <command id>
#
#     Where:
#     - endpoint MUST be 11
#     - cluster MUST be 0x0101 (Door Lock)
#     - profile MUST be 0x0104 (Home Automation)
#     - command MUST be 0x00 (lock) or 0x01 (unlock)
#     - NO parameters are allowed
#     """
#     command_name = "lock" if command == SAFE4_LOCK_COMMAND else "unlock"
#     _LOGGER.info(f"Sending {command_name} command to Safe4 lock {ieee_address} using Nordic ZBT-1 format")
#
#     # First, discover available services in Home Assistant
#     available_services = discover_available_services(hass)
#     _LOGGER.debug(f"Available Zigbee services: {available_services}")
#
#     # Always use ZHA domain only
#     service_domains = ["zha"]
#     service_methods = []
#
#     # Add discovered ZHA services to our list
#     if "zha" in available_services:
#         service_methods.extend(available_services["zha"])
#
#     # If no ZHA services were discovered, use default ZHA methods
#     if not service_methods:
#         service_methods = [
#             "issue_zigbee_cluster_command",
#             "command",
#             "execute_zigbee_command",
#             "issue_command",
#             "send_command",
#             "command_server"
#         ]
#
#     # Use a cleaner implementation for IEEE normalization
#     from .zha_mapping import normalize_ieee
#     ieee_formats = normalize_ieee(ieee_address)
#     ieee_no_colons = ieee_formats["no_colons"]
#     ieee_with_colons = ieee_formats["with_colons"]
#
#     # Prepare all IEEE formats to try
#     ieee_formats = [
#         ieee_address,
#         ieee_no_colons,
#         ieee_with_colons
#     ]
#
#     # Log what we're going to try
#     _LOGGER.debug(f"Will try service domains: {service_domains}")
#     _LOGGER.debug(f"Will try service methods: {service_methods}")
#
#     # Try the exact Nordic ZBT-1 format first (endpoint 11 ONLY first)
#     # This is critical - the Nordic docs specify endpoint MUST be 11
#     for ieee in ieee_formats:
#         for service_domain in service_domains:
#             for service_method in service_methods:
#                 if not hass.services.has_service(service_domain, service_method):
#                     continue
#
#                 _LOGGER.debug(f"Trying exact Nordic ZBT-1 format with endpoint 11, {service_domain}.{service_method} and IEEE {ieee}")
#
#                 # EXACT format per Nordic ZBT-1 specification
#                 # zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 <command id>
#                 service_data = {
#                     "ieee": ieee,
#                     "endpoint_id": 11,      # MUST be 11 for ZBT-1
#                     "cluster_id": 0x0101,   # Door Lock cluster
#                     "command": command,     # 0x00 (lock) or 0x01 (unlock)
#                     "command_type": "server"
#                 }
#
#                 # Profile parameter is not needed for ZHA
#                 pass
#
#                 # CRITICAL: For ZBT-1 per Nordic spec, NO parameters allowed
#                 # Different from standard Zigbee where PIN is sometimes needed
#                 try:
#                     # Try both with empty params and without params key
#                     # Some implementations don't support params at all
#                     service_data_with_params = {**service_data, "params": []}
#
#                     try:
#                         # First try with empty params
#                         for attempt in range(5):
#                             try:
#                                 await hass.services.async_call(
#                                     service_domain,
#                                     service_method,
#                                     service_data_with_params,
#                                     blocking=True
#                                 )
#                                 _LOGGER.info(f"Successfully sent {command_name} command using endpoint 11 with empty params on attempt {attempt+1}")
#                                 return True
#                             except Exception as e:
#                                 _LOGGER.warning(f"Attempt {attempt+1} failed: {e}")
#                                 await asyncio.sleep(1.5 * (2 ** attempt))
#                         _LOGGER.info(f"Successfully sent {command_name} command using endpoint 11 with empty params")
#                         return True
#                     except Exception as e:
#                         if "extra keys not allowed" in str(e).lower() or "params" in str(e).lower():
#                             # Try without params key at all
#                             await hass.services.async_call(
#                                 service_domain,
#                                 service_method,
#                                 service_data,  # Original without params
#                                 blocking=True
#                             )
#                             _LOGGER.info(f"Successfully sent {command_name} command using endpoint 11 without params key")
#                             return True
#                         else:
#                             # Some other error, continue to next method
#                             pass
#
#                 except Exception as e:
#                     # Continue to next method
#                     pass
#
#     # If the exact Nordic format failed, try with other endpoints as fallback
#     # Use a prioritized list with endpoint 11 first
#     endpoints = [11, 1, 242, 2, 3]
#
#     # Try each endpoint with each address format and service domain
#     for endpoint_id in endpoints:
#         for ieee in ieee_formats:
#             for service_domain in service_domains:
#                 for service_method in service_methods:
#                     try:
#                         # Check if the service exists before trying
#                         if not hass.services.has_service(service_domain, service_method):
#                             continue
#
#                         _LOGGER.debug(f"Trying endpoint {endpoint_id} with {command_name} command using {service_domain}.{service_method} and IEEE {ieee}")
#
#                         # Prepare service data
#                         service_data = {
#                             "ieee": ieee,
#                             "endpoint_id": endpoint_id,
#                             "cluster_id": SAFE4_DOOR_LOCK_CLUSTER,
#                             "command": command,
#                             "command_type": "server"
#                         }
#
#                         # ZHA doesn't need profile parameter
#                         pass
#
#                         # Try both with empty params and without params
#                         try:
#                             # First try with empty params
#                             service_data_with_params = {**service_data, "params": []}
#                             await hass.services.async_call(
#                                 service_domain,
#                                 service_method,
#                                 service_data_with_params,
#                                 blocking=True
#                             )
#                             _LOGGER.info(f"Successfully sent {command_name} command to endpoint {endpoint_id}")
#                             return True
#                         except Exception as e:
#                             # If failed with params, try without
#                             if "extra keys not allowed" in str(e).lower() or "params" in str(e).lower():
#                                 await hass.services.async_call(
#                                     service_domain,
#                                     service_method,
#                                     service_data,  # Without params
#                                     blocking=True
#                                 )
#                                 _LOGGER.info(f"Successfully sent {command_name} command to endpoint {endpoint_id} without params")
#                                 return True
#
#                     except Exception as e:
#                         # Continue to next method
#                         pass
#
#         # If we get this far, try with network address
#         for service_method in service_methods:
#             try:
#                 # Try with network address (only works with ZHA)
#                 # Use ieee key with nwk format for ZHA
#                 service_data = {
#                     "ieee": "0x7FDB",  # The known network address used as ieee
#                     "endpoint_id": endpoint_id,
#                     "cluster_id": SAFE4_DOOR_LOCK_CLUSTER,
#                     "command": command,
#                     "command_type": "server",
#                     "params": []
#                 }
#
#                 # Check if the service exists
#                 if not hass.services.has_service("zha", service_method):
#                     _LOGGER.debug(f"Service zha.{service_method} not available for network address, skipping")
#                     continue
#
#                 try:
#                     await hass.services.async_call(
#                         "zha",
#                         service_method,
#                         service_data,
#                         blocking=True
#                     )
#
#                     _LOGGER.info(f"Successfully sent {command_name} command using network address to endpoint {endpoint_id}")
#                     return True
#                 except Exception as e:
#                     _LOGGER.debug(f"Failed to send {command_name} command using network address: {e}")
#             except Exception as e:
#                 _LOGGER.debug(f"Failed to setup network address command: {e}")
#
#     # If we get here, none of the endpoints worked
#     _LOGGER.error(f"All endpoints failed for {command_name} command")
#     return False
#
# # Import constants from dedicated constants file
# from .const_zbt1 import (
#     SAFE4_DOOR_LOCK_CLUSTER,
#     SAFE4_POWER_CLUSTER,
#     SAFE4_LOCK_COMMAND,
#     SAFE4_UNLOCK_COMMAND
# )
#
# # Import helper functions from zha_mapping
# from .zha_mapping import (
#     format_ieee_with_colons,
#     format_safe4_zbt1_command
# )
#
# async def send_safe4_lock_command(hass, ieee):
#     """Send the lock command according to Safe4 ZigBee Door Lock Module specification.
#
#     Command format: `zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 0x00`
#     - Endpoint must be exactly 11
#     - Cluster ID must be 0x0101 (Door Lock)
#     - Profile ID must be 0x0104 (Home Automation)
#     - Command ID must be 0x00 for lock
#     - NO parameters can be passed
#
#     Args:
#         hass: Home Assistant instance
#         ieee: IEEE address of the device
#
#     Returns:
#         Boolean indicating success or failure
#     """
#     _LOGGER.info(f"Sending Safe4 lock command to device {ieee}")
#
#     # Format IEEE address with colons
#     ieee_with_colons = format_ieee_with_colons(ieee)
#
#     # Get the command parameters in the correct format
#     command_data = format_safe4_zbt1_command(ieee, SAFE4_LOCK_COMMAND)
#
#     # Only use ZHA service domain
#     service_domains = ["zha"]
#     service_methods = ["issue_zigbee_cluster_command", "command"]
#
#     # Track success
#     success = False
#
#     # Try each service domain and method
#     for domain in service_domains:
#         for method in service_methods:
#             if not hass.services.has_service(domain, method):
#                 continue
#
#             try:
#                 _LOGGER.debug(f"Trying {domain}.{method} for Safe4 lock command")
#
#                 # Send the command
#                 await hass.services.async_call(
#                     domain, method, command_data, blocking=True
#                 )
#
#                 _LOGGER.info(f"Successfully sent Safe4 lock command using {domain}.{method}")
#                 success = True
#                 return True
#             except Exception as e:
#                 _LOGGER.warning(f"Failed to send Safe4 lock command using {domain}.{method}: {e}")
#
#     if not success:
#         _LOGGER.error("Failed to send Safe4 lock command with all methods")
#
#     return success
#
# async def send_safe4_unlock_command(hass, ieee):
#     """Send the unlock command according to Safe4 ZigBee Door Lock Module specification.
#
#     Command format: `zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 0x01`
#     - Endpoint must be exactly 11
#     - Cluster ID must be 0x0101 (Door Lock)
#     - Profile ID must be 0x0104 (Home Automation)
#     - Command ID must be 0x01 for unlock
#     - NO parameters can be passed
#
#     Args:
#         hass: Home Assistant instance
#         ieee: IEEE address of the device
#
#     Returns:
#         Boolean indicating success or failure
#     """
#     _LOGGER.info(f"Sending Safe4 unlock command to device {ieee}")
#
#     # Format IEEE address with colons
#     ieee_with_colons = format_ieee_with_colons(ieee)
#
#     # Get the command parameters in the correct format
#     command_data = format_safe4_zbt1_command(ieee, SAFE4_UNLOCK_COMMAND)
#
#     # Only use ZHA service domain
#     service_domains = ["zha"]
#     service_methods = ["issue_zigbee_cluster_command", "command"]
#
#     # Track success
#     success = False
#
#     # Try each service domain and method
#     for domain in service_domains:
#         for method in service_methods:
#             if not hass.services.has_service(domain, method):
#                 continue
#
#             try:
#                 _LOGGER.debug(f"Trying {domain}.{method} for Safe4 unlock command")
#
#                 # Send the command
#                 await hass.services.async_call(
#                     domain, method, command_data, blocking=True
#                 )
#
#                 _LOGGER.info(f"Successfully sent Safe4 unlock command using {domain}.{method}")
#                 success = True
#                 return True
#             except Exception as e:
#                 _LOGGER.warning(f"Failed to send Safe4 unlock command using {domain}.{method}: {e}")
#
#     if not success:
#         _LOGGER.error("Failed to send Safe4 unlock command with all methods")
#
#     return success
#
#
# async def get_lock_status(hass, ieee):
#     """Get the current lock status from a Safe4 ZigBee Door Lock Module device.
#
#     Args:
#         hass: Home Assistant instance
#         ieee: IEEE address of the device
#
#     Returns:
#         0 for unlocked, 1 for locked, or None if not available
#     """
#     _LOGGER.debug(f"Getting lock status for device {ieee}")
#
#     # Read the lock state attribute
#     result = await read_safe4_attribute(hass, ieee, SAFE4_DOOR_LOCK_CLUSTER, 0x0000)
#
#     if result is not None:
#         _LOGGER.info(f"Lock status: {result}")
#         return result
#
#     _LOGGER.warning("Failed to get lock status")
#     return None
#
# async def get_battery_level(hass, ieee):
#     """Get the battery level from a Safe4 ZigBee Door Lock Module device.
#
#     Args:
#         hass: Home Assistant instance
#         ieee: IEEE address of the device
#
#     Returns:
#         Battery level percentage or None if not available
#     """
#     _LOGGER.debug(f"Getting battery level for device {ieee}")
#
#     # Read the battery percentage remaining attribute
#     result = await read_safe4_attribute(hass, ieee, SAFE4_POWER_CLUSTER, 0x0021)
#
#     if result is not None:
#         _LOGGER.info(f"Battery level: {result}%")
#         return result
#
#     _LOGGER.warning("Failed to get battery level")
#     return None
#
# async def read_safe4_attribute(hass, ieee, cluster_id, attribute_id, endpoint=11):
#     """Read an attribute from a device.
#
#     Args:
#         hass: Home Assistant instance
#         ieee: IEEE address of the device
#         cluster_id: Cluster ID
#         attribute_id: Attribute ID
#         endpoint: Endpoint ID (default is 11)
#
#     Returns:
#         Attribute value or None if not available
#     """
#     from .zbt1_support import async_read_attribute_zbt1
#
#     # Try using the ZBT1 support module to read the attribute
#     result = await async_read_attribute_zbt1(hass, ieee, cluster_id, attribute_id, endpoint)
#     return result
#
# async def try_direct_zha_gateway_access(hass, ieee_address, cluster_id, attribute_id, cluster_type, ieee_formats):
#     from .const import DOMAIN
#     ZHA_DOMAIN = "zha"
#
#     # Validate inputs to prevent errors
#     if not ieee_address or not ieee_formats:
#         _LOGGER.warning("Missing IEEE address or formats in try_direct_zha_gateway_access")
#         return None
#
#     # Ensure we have a list of formats
#     if not isinstance(ieee_formats, list):
#         ieee_formats = [ieee_formats]
#
#     try:
#
#         if ZHA_DOMAIN in hass.data:
#             zha_gateway = hass.data[ZHA_DOMAIN].get("gateway")
#             if zha_gateway and hasattr(zha_gateway, "devices"):
#                 # Try to find our device
#                 device = None
#                 for dev in zha_gateway.devices.values():
#                     for ieee_format in ieee_formats:
#                         if hasattr(dev, "ieee") and str(dev.ieee).replace(':', '').lower() == ieee_format.replace(':', '').lower():
#                             device = dev
#                             _LOGGER.info(f"Found ZHA device: {device.ieee}")
#                             break
#                     if device:
#                         break
#
#                 if device and hasattr(device, "endpoints"):
#                     # Try all endpoints to find the one with our cluster
#                     for ep_id, endpoint in device.endpoints.items():
#                         # Check if this endpoint has the cluster we need
#                         try:
#                             # Different properties for different cluster types
#                             if cluster_type == "in":
#                                 cluster = endpoint.in_clusters.get(cluster_id)
#                             else:
#                                 cluster = endpoint.out_clusters.get(cluster_id)
#
#                             if cluster:
#                                 _LOGGER.info(f"Found cluster {cluster_id} on endpoint {ep_id}")
#                                 # Try to read the attribute directly
#                                 result = await cluster.read_attributes([attribute_id])
#                                 if result and attribute_id in result[0]:
#                                     value = result[0][attribute_id]
#                                     _LOGGER.info(f"Successfully read attribute {attribute_id} with value {value} via direct ZHA")
#                                     # Store the result in our data store
#                                     hass.data[f"{DOMAIN}:{ieee_address}:{attribute_id}"] = value
#                                     return value
#                         except Exception as e:
#                             _LOGGER.debug(f"Failed to read attribute via direct ZHA on endpoint {ep_id}: {e}")
#     except Exception as e:
#         _LOGGER.debug(f"Failed to use direct ZHA gateway access: {e}")
#
#     # Try to import ZHA_DOMAIN directly if needed
#     try:
#         from homeassistant.components.zha.core.const import DOMAIN as ZHA_DOMAIN
#     except ImportError:
#         ZHA_DOMAIN = "zha"
#
#     return None
#
#     # Try direct ZHA gateway access as last resort
