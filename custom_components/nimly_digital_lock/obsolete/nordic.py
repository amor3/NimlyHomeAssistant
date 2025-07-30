# """Nordic ZBT-1 specific command implementation for Nimly locks."""
# """Nimly  ZBT-1 specific implementation for Nimly Digital Lock.
#
# This module implements the exact command format required by the Nimly
# ZBT-1 specification for the Safe4 ZigBee Door Lock Module.
#
# According to the specification, commands must be sent in this exact format:
# zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 <command id>
#
# Where:
# - Endpoint must be exactly 11
# - Cluster ID must be 0x0101 (Door Lock)
# - Profile ID must be 0x0104 (Home Automation)
# - Command ID must be 0x00 for lock, 0x01 for unlock
# - NO parameters can be passed
# """
#
# import logging
# import asyncio
#
# _LOGGER = logging.getLogger(__name__)
#
# # Import constants from dedicated constants file
# from .const_zbt1 import (
#     SAFE4_ZBT1_ENDPOINT,
#     SAFE4_DOOR_LOCK_CLUSTER,
#     SAFE4_DOOR_LOCK_PROFILE,
#     SAFE4_LOCK_COMMAND,
#     SAFE4_UNLOCK_COMMAND
# )
#
# # Pin code related constants
# ZBT1_SET_PIN_CODE = 0x05      # Set PIN Code
# ZBT1_CLEAR_PIN_CODE = 0x07    # Clear PIN Code
# ZBT1_CLEAR_ALL_PIN_CODES = 0x08  # Clear All PIN Codes
#
# # Import helper functions from zha_mapping
# from .zha_mapping import (
#     format_ieee_with_colons,
#     format_safe4_zbt1_command,
#     validate_ieee
# )
#
# async def send_nordic_command(hass, ieee, command_id, retry_count=5, retry_delay=1.0):
#     """Send a command to a Nordic ZBT-1 device using the exact format required by the spec.
#
#     The Nordic ZBT-1 specification requires commands to be in this format:
#     zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 <command id>
#
#     Args:
#         hass: Home Assistant instance
#         ieee: IEEE address of the device
#         command_id: Command ID (0x00 for lock, 0x01 for unlock)
#         retry_count: Number of retries for sending the command
#         retry_delay: Delay between retries in seconds
#
#     Returns:
#         Boolean indicating success or failure
#     """
#     _LOGGER.info(f"Sending Nordic ZBT-1 command {command_id} to device {ieee}")
#
#     # Validate IEEE address with error handling
#     try:
#         is_valid, ieee_with_colons, error_message = validate_ieee(ieee)
#         if not is_valid:
#             _LOGGER.error(f"Invalid IEEE address: {error_message}")
#             # Continue with original address as fallback instead of returning
#             _LOGGER.warning(f"Attempting to continue with original IEEE address: {ieee}")
#             ieee_with_colons = ieee
#
#         _LOGGER.debug(f"Using formatted IEEE address: {ieee_with_colons}")
#     except Exception as e:
#         _LOGGER.error(f"Error validating IEEE address: {e}")
#         # Use original address as fallback
#         ieee_with_colons = ieee
#         _LOGGER.warning(f"Using original IEEE address as fallback: {ieee_with_colons}")
#
#     # According to Safe4 spec, command must be in format:
#     # zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 <command id>
#     # Home Assistant requires at least empty params or args
#     command_data = format_safe4_zbt1_command(ieee, command_id)
#
#     # Try both service domains
#     service_domains = ["zigbee", "zha"]
#     service_methods = ["issue_zigbee_cluster_command", "command"]
#
#     # Track success
#     success = False
#
#     # Try each service domain and method
#     for domain in service_domains:
#         for method in service_methods:
#             if not hass.services.has_service(domain, method):
#                 _LOGGER.debug(f"Service {domain}.{method} not available")
#                 continue
#
#             # Try multiple attempts
#             for attempt in range(retry_count):
#                 # Try with both params and args formats
#                 command_formats = [
#                     # First try with params (most common)
#                     {**command_data},
#                     # Then try with args instead of params
#                     {key: value for key, value in command_data.items() if key != "params"}
#                 ]
#
#                 if "params" in command_data:
#                     # Add empty args as a fallback format
#                     args_format = {key: value for key, value in command_data.items() if key != "params"}
#                     args_format["args"] = {}
#                     command_formats.append(args_format)
#
#                 for cmd_format in command_formats:
#                     try:
#                         _LOGGER.debug(f"Attempt {attempt+1}/{retry_count} using {domain}.{method} with format: {cmd_format}")
#
#                         # Send the command
#                         await hass.services.async_call(
#                             domain, method, cmd_format, blocking=True
#                         )
#
#                         _LOGGER.info(f"Successfully sent command {command_id} using {domain}.{method}")
#                         success = True
#                         return True
#                     except Exception as e:
#                         _LOGGER.debug(f"Failed format {cmd_format} on attempt {attempt+1} using {domain}.{method}: {e}")
#
#                         # Check for specific error message about missing args/params
#                         error_msg = str(e).lower()
#                         if "must contain at least one of args, params" in error_msg:
#                             _LOGGER.warning("Service requires either args or params to be present")
#                         elif "not a valid value for dictionary value @ data['ieee']" in error_msg:
#                             _LOGGER.warning("IEEE address format is not valid for this service")
#
#                 # If we tried all formats and none worked, wait before the next attempt
#                 if attempt < retry_count - 1:
#                     await asyncio.sleep(retry_delay)
#
#     if not success:
#         _LOGGER.error(f"Failed to send command {command_id} after {retry_count} attempts with all methods")
#
#     return success
#
# async def lock_door(hass, ieee):
#     """Lock the door using Nordic ZBT-1 specification.
#
#     Args:
#         hass: Home Assistant instance
#         ieee: IEEE address of the device
#
#     Returns:
#         Boolean indicating success or failure
#     """
#     _LOGGER.info(f"Locking door with Nordic ZBT-1 format: {ieee}")
#     return await send_nordic_command(hass, ieee, SAFE4_LOCK_COMMAND)
#
# async def unlock_door(hass, ieee):
#     """Unlock the door using Nordic ZBT-1 specification.
#
#     According to the Safe4 ZigBee Door Lock Module specification:
#     - Command must be sent in this exact format:
#       zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 0x01
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
#     _LOGGER.info(f"Unlocking door with Nordic ZBT-1 format: {ieee}")
#     # Use a higher retry count for unlock since this seems to be problematic
#     return await send_nordic_command(hass, ieee, SAFE4_UNLOCK_COMMAND, retry_count=10)
#
# async def read_attribute(hass, ieee, cluster_id, attribute_id, endpoint=SAFE4_ZBT1_ENDPOINT):
#     """Read an attribute from a Nordic ZBT-1 device.
#
#     Args:
#         hass: Home Assistant instance
#         ieee: IEEE address of the device
#         cluster_id: Cluster ID
#         attribute_id: Attribute ID
#         endpoint: Endpoint ID (default is 11 for ZBT-1)
#
#     Returns:
#         Attribute value or None if not available
#     """
#     _LOGGER.debug(f"Reading attribute {attribute_id} from cluster {cluster_id} on endpoint {endpoint}")
#
#     # Format IEEE address with colons
#     ieee_with_colons = format_ieee_with_colons(ieee)
#
#     # Service data for reading attribute
#     service_data = {
#         "ieee": ieee_with_colons,
#         "endpoint_id": endpoint,
#         "cluster_id": cluster_id,
#         "cluster_type": "in",
#         "attribute": attribute_id
#     }
#
#     # Try both service domains
#     service_domains = ["zigbee", "zha"]
#     service_methods = ["get_zigbee_cluster_attribute", "read_zigbee_cluster_attribute"]
#
#     # Try each service domain and method
#     for domain in service_domains:
#         for method in service_methods:
#             if not hass.services.has_service(domain, method):
#                 continue
#
#             try:
#                 _LOGGER.debug(f"Trying to read attribute using {domain}.{method}")
#
#                 # Send the command
#                 result = await hass.services.async_call(
#                     domain, method, service_data, blocking=True, return_response=True
#                 )
#
#                 if result is not None:
#                     _LOGGER.info(f"Successfully read attribute {attribute_id}: {result}")
#                     return result
#             except Exception as e:
#                 _LOGGER.warning(f"Failed to read attribute {attribute_id} using {domain}.{method}: {e}")
#
#     _LOGGER.warning(f"Failed to read attribute {attribute_id} with all methods")
#     return None
#
#
# async def set_pin_code(hass, ieee, user_id, pin_code, status=1, user_type=0, endpoint=SAFE4_ZBT1_ENDPOINT):
#     """Set a PIN code for a user on a Nordic ZBT-1 device.
#
#     Args:
#         hass: Home Assistant instance
#         ieee: IEEE address of the device
#         user_id: User ID (1-255)
#         pin_code: PIN code string (4-10 digits)
#         status: User status (1=enabled, 0=disabled)
#         user_type: User type (0=unrestricted, 1=year/day, 2=week/day, 3=master)
#         endpoint: Endpoint ID (default is 11 for ZBT-1)
#
#     Returns:
#         Boolean indicating success or failure
#     """
#     _LOGGER.info(f"Setting PIN code for user {user_id} on device {ieee}")
#
#     # Format IEEE address with colons
#     ieee_with_colons = format_ieee_with_colons(ieee)
#
#     # Validate user_id
#     if not 1 <= user_id <= 255:
#         _LOGGER.error(f"Invalid user ID: {user_id}. Must be between 1 and 255.")
#         return False
#
#     # Validate pin_code - must be 4-10 digits
#     if not pin_code.isdigit() or not 4 <= len(pin_code) <= 10:
#         _LOGGER.error(f"Invalid PIN code: {pin_code}. Must be 4-10 digits.")
#         return False
#
#     # Format user ID as string
#     user_id_str = str(user_id)
#
#     # Service data for setting PIN code
#     service_data = {
#         "ieee": ieee_with_colons,
#         "endpoint_id": endpoint,
#         "cluster_id": SAFE4_DOOR_LOCK_CLUSTER,
#         "command": ZBT1_SET_PIN_CODE,
#         "command_type": "server",
#         "params": {
#             "user_id": user_id,
#             "user_status": status,
#             "user_type": user_type,
#             "pin_code": pin_code
#         }
#     }
#
#     # Try both service domains
#     service_domains = ["zigbee", "zha"]
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
#                 _LOGGER.debug(f"Trying to set PIN code using {domain}.{method}")
#
#                 # Send the command
#                 await hass.services.async_call(
#                     domain, method, service_data, blocking=True
#                 )
#
#                 _LOGGER.info(f"Successfully set PIN code for user {user_id} using {domain}.{method}")
#                 success = True
#                 return True
#             except Exception as e:
#                 _LOGGER.warning(f"Failed to set PIN code for user {user_id} using {domain}.{method}: {e}")
#
#     if not success:
#         _LOGGER.error(f"Failed to set PIN code for user {user_id} with all methods")
#
#     return success
#
#
# async def clear_pin_code(hass, ieee, user_id, endpoint=SAFE4_ZBT1_ENDPOINT):
#     """Clear a PIN code for a user on a Nordic ZBT-1 device.
#
#     Args:
#         hass: Home Assistant instance
#         ieee: IEEE address of the device
#         user_id: User ID (1-255) or 0 to clear all PIN codes
#         endpoint: Endpoint ID (default is 11 for ZBT-1)
#
#     Returns:
#         Boolean indicating success or failure
#     """
#     _LOGGER.info(f"Clearing PIN code for user {user_id} on device {ieee}")
#
#     # Format IEEE address with colons
#     ieee_with_colons = format_ieee_with_colons(ieee)
#
#     # Determine which command to use based on user_id
#     command_id = ZBT1_CLEAR_ALL_PIN_CODES if user_id == 0 else ZBT1_CLEAR_PIN_CODE
#
#     # Service data for clearing PIN code
#     service_data = {
#         "ieee": ieee_with_colons,
#         "endpoint_id": endpoint,
#         "cluster_id": SAFE4_DOOR_LOCK_CLUSTER,
#         "command": command_id,
#         "command_type": "server"
#     }
#
#     # Add user_id parameter if clearing a specific user
#     if user_id != 0:
#         service_data["params"] = {"user_id": user_id}
#
#     # Try both service domains
#     service_domains = ["zigbee", "zha"]
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
#                 _LOGGER.debug(f"Trying to clear PIN code using {domain}.{method}")
#
#                 # Send the command
#                 await hass.services.async_call(
#                     domain, method, service_data, blocking=True
#                 )
#
#                 _LOGGER.info(f"Successfully cleared PIN code for user {user_id} using {domain}.{method}")
#                 success = True
#                 return True
#             except Exception as e:
#                 _LOGGER.warning(f"Failed to clear PIN code for user {user_id} using {domain}.{method}: {e}")
#
#     if not success:
#         _LOGGER.error(f"Failed to clear PIN code for user {user_id} with all methods")
#
#     return success