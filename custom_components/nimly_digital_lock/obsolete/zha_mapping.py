# import logging
#
# _LOGGER = logging.getLogger(__name__)
#
# # Import constants from the dedicated constants file
# from .const_zbt1 import (
#     ZBT1_ENDPOINTS,
#     ZBT1_LOCK_COMMAND,
#     ZBT1_UNLOCK_COMMAND,
#     SAFE4_DOOR_LOCK_CLUSTER,
#     SAFE4_POWER_CLUSTER,
#     SAFE4_LOCK_COMMAND,
#     SAFE4_UNLOCK_COMMAND,
#     SAFE4_ZBT1_ENDPOINT,
#     SAFE4_DOOR_LOCK_PROFILE,
#     COMMAND_PROFILE,
#     COMMAND_TYPE
# )
#
# ZBT1_LOCK_COMMANDS = {
#     "lock_door": 0x00,
#     "unlock_door": 0x01,
# }
#
# DOOR_LOCK_COMMANDS = {
#     "toggle": 0x02,
#     "unlock_with_timeout": 0x03,
#     "get_log_record": 0x04,
#     "set_pin_code": 0x05,
#     "get_pin_code": 0x06,
#     "clear_pin_code": 0x07,
#     "clear_all_pin_codes": 0x08,
#     "set_user_status": 0x09,
#     "get_user_status": 0x0A,
#     "set_week_day_schedule": 0x0B,
#     "get_week_day_schedule": 0x0C,
#     "clear_week_day_schedule": 0x0D,
#     "set_year_day_schedule": 0x0E,
#     "get_year_day_schedule": 0x0F,
#     "clear_year_day_schedule": 0x10,
#     "set_holiday_schedule": 0x11,
#     "get_holiday_schedule": 0x12,
#     "clear_holiday_schedule": 0x13,
#     "set_user_type": 0x14,
#     "get_user_type": 0x15,
#     "set_rfid_code": 0x16,
#     "get_rfid_code": 0x17,
#     "clear_rfid_code": 0x18,
#     "clear_all_rfid_codes": 0x19
# }
#
# DOOR_LOCK_CLUSTER = 0x0101
#
#
# def format_ieee(ieee):
#     ieee_clean = ''.join(c for c in ieee if c.lower() in '0123456789abcdef')
#     ieee_with_colons = ':'.join([ieee_clean[i:i+2] for i in range(0, len(ieee_clean), 2)])
#     return ieee_with_colons.lower()
#
# def format_ieee_with_colons(ieee):
#     """Format IEEE address with colons in the correct format.
#
#     This function can handle IEEE in various formats:
#     - With colons: aa:bb:cc:dd:ee:ff:00:11
#     - Without colons: aabbccddeeff0011
#     - With 0x prefix: 0xaabbccddeeff0011
#
#     Returns properly formatted IEEE address with colons.
#     """
#     # Handle None or empty string
#     if not ieee:
#         return ""
#
#     # If already has colons, validate format
#     if ':' in ieee:
#         # Check if format is correct (8 hex pairs separated by colons)
#         parts = ieee.split(':')
#         if len(parts) == 8 and all(len(part) == 2 and all(c.lower() in '0123456789abcdef' for c in part) for part in parts):
#             return ieee.lower()
#
#     # Remove 0x prefix if present
#     if ieee.lower().startswith('0x'):
#         ieee = ieee[2:]
#
#     # Clean the string to only contain hex characters
#     ieee_clean = ''.join(c for c in ieee if c.lower() in '0123456789abcdef')
#
#     # Check if we have a valid length after cleaning
#     if len(ieee_clean) != 16:
#         # If length is odd, pad with a zero to make it even (allows join to work)
#         if len(ieee_clean) % 2 != 0:
#             _LOGGER.warning(f"IEEE address has odd length ({len(ieee_clean)}), padding with 0")
#             ieee_clean = ieee_clean + '0'
#
#         # Still handle special case for very short values (likely network addresses)
#         if len(ieee_clean) <= 4:
#             _LOGGER.warning(f"The provided value '{ieee}' appears to be a network address, not a valid IEEE address")
#             # Don't raise exception, just return the best formatted version we can
#             return ':'.join([ieee_clean[i:i+2] for i in range(0, len(ieee_clean), 2)]).lower()
#
#         # For other unusual lengths, warn but try to format anyway
#         _LOGGER.warning(f"Unusual IEEE address length: {len(ieee_clean)} (expected 16 hex characters)")
#
#     # Format with colons - this should work for any even-length string of hex characters
#     return ':'.join([ieee_clean[i:i+2] for i in range(0, len(ieee_clean), 2)]).lower()
#
# LOCK_CLUSTER_ID = 0x0101
# POWER_CLUSTER_ID = 0x0001
#
# LOCK_COMMANDS = {
#     "lock_door": 0x00,
#     "unlock_door": 0x01,
#     "toggle_door": 0x02,
#     "unlock_with_timeout": 0x03,
#     "get_log_record": 0x04,
#     "set_pin_code": 0x05,
#     "get_pin_code": 0x06,
#     "clear_pin_code": 0x07,
#     "clear_all_pin_codes": 0x08,
#     "set_user_status": 0x09,
#     "get_user_status": 0x0A,
#     "set_week_day_schedule": 0x0B,
#     "get_week_day_schedule": 0x0C,
#     "clear_week_day_schedule": 0x0D,
#     "set_year_day_schedule": 0x0E,
#     "get_year_day_schedule": 0x0F,
#     "clear_year_day_schedule": 0x10
# }
#
# POWER_ATTRIBUTES = {
#     "mains_voltage": 0x0000,
#     "battery_voltage": 0x0020,
#     "battery_percentage_remaining": 0x0021,
#     "battery_alarm_mask": 0x0035,
#     "battery_voltage_min_threshold": 0x0036,
#     "battery_voltage_threshold_1": 0x0037,
#     "battery_voltage_threshold_2": 0x0038,
#     "battery_voltage_threshold_3": 0x0039,
#     "battery_percentage_min_threshold": 0x003A,
#     "battery_percentage_threshold_1": 0x003B,
#     "battery_percentage_threshold_2": 0x003C,
#     "battery_percentage_threshold_3": 0x003D,
#     "battery_low": 0x9000,
# }
#
# LOCK_RESPONSES = {
#     "operation_event": 0x00,
#     "programming_event": 0x01,
#     "lock_status": 0x9000,
#     "unlock_status": 0x9001
# }
#
# DEVICE_LOOKUP_METHODS = [
#     "gateway.get_device",
#     "application_controller.get_device",
#     "coordinator.get_device",
#     "device_registry.get_device",
#     "gateway.devices",
#     "application_controller.devices",
#     "coordinator.devices",
#     "device_registry.devices",
#     "get_device"
# ]
#
# def normalize_ieee(ieee):
#     ieee_no_colons = ieee.replace(':', '')
#     ieee_clean = ''.join(c for c in ieee_no_colons if c.lower() in '0123456789abcdef')
#     ieee_no_colons = ieee_clean.lower()
#     ieee_with_colons = ':'.join([ieee_clean[i:i+2] for i in range(0, len(ieee_clean), 2)]).lower()
#
#     return {
#         "original": ieee,
#         "no_colons": ieee_no_colons,
#         "with_colons": ieee_with_colons
#     }
#
# def format_nwk_address(nwk):
#     if isinstance(nwk, str) and nwk.lower().startswith('0x'):
#         return nwk.lower()
#     if isinstance(nwk, int):
#         return f"0x{nwk:04X}"
#     try:
#         value = int(nwk)
#         return f"0x{value:04X}"
#     except ValueError:
#         return f"0x{nwk}"
#
# def get_zha_address_for_command(hass, ieee=None, nwk=None):
#     addresses = {}
#     if ieee:
#         ieee_formats = normalize_ieee(ieee)
#         addresses["ieee"] = ieee_formats["with_colons"]
#         addresses["ieee_no_colons"] = ieee_formats["no_colons"]
#     if nwk:
#         addresses["nwk"] = format_nwk_address(nwk)
#     return addresses
#
# LOCK_ATTRIBUTES = {
#     "lock_state": 0x0000,
#     "lock_type": 0x0001,
#     "actuator_enabled": 0x0002,
#     "door_state": 0x0003,
#     "door_open_events": 0x0004,
#     "door_closed_events": 0x0005,
#     "open_period": 0x0006
# }
#
# async def is_zbt1_compatible(hass, ieee):
#     try:
#         # Use local get_endpoints function instead of imported one
#         endpoints = await get_endpoints(hass, ieee)
#         if SAFE4_ZBT1_ENDPOINT not in endpoints:
#             _LOGGER.debug(f"Device {ieee} does not have required endpoint {SAFE4_ZBT1_ENDPOINT}")
#             return False
#         return True
#     except Exception as e:
#         _LOGGER.warning(f"Error checking ZBT-1 compatibility for {ieee}: {e}")
#         return True
#
# async def get_endpoints(hass, ieee):
#     try:
#         # Default list of endpoints to try for ZBT1 devices
#         default_endpoints = ZBT1_ENDPOINTS
#         return default_endpoints
#     except Exception as e:
#         _LOGGER.warning(f"Error retrieving endpoints: {e}")
#         return [11, 1, 2, 3, 242]
#
# def format_safe4_zbt1_command(ieee, command_id):
#     """Format command according to Safe4 ZigBee Door Lock Module specification.
#
#     The command format must be exactly:
#     zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 <command id>
#
#     Where:
#     - Endpoint must be exactly 11
#     - Cluster ID must be 0x0101 (Door Lock)
#     - Profile ID must be 0x0104 (Home Automation)
#     - Command ID must be 0x00 for lock, 0x01 for unlock
#     - At least one of args or params must be present (even if empty)
#     """
#     try:
#         # Validate and format IEEE address
#         is_valid, ieee_with_colons, error_message = validate_ieee(ieee)
#         if not is_valid:
#             _LOGGER.error(f"Invalid IEEE address for command: {error_message}")
#             raise ValueError(f"Invalid IEEE address: {error_message}")
#
#         # Log the exact command we're about to send for debugging
#         _LOGGER.debug(f"Formatting ZBT-1 command: IEEE={ieee_with_colons}, command_id={command_id}, "
#                      f"endpoint={SAFE4_ZBT1_ENDPOINT}, cluster={SAFE4_DOOR_LOCK_CLUSTER}")
#
#         # Home Assistant requires at least one of args or params to be present
#         command_data = {
#             "ieee": ieee_with_colons,
#             "endpoint_id": SAFE4_ZBT1_ENDPOINT,  # Must be 11 per spec
#             "cluster_id": SAFE4_DOOR_LOCK_CLUSTER,  # 0x0101 per spec
#             "command": command_id,  # 0x00=lock, 0x01=unlock per spec
#             "command_type": COMMAND_TYPE,  # server
#             "params": {}  # Empty params required by Home Assistant
#         }
#
#         _LOGGER.debug(f"Formatted command data: {command_data}")
#         return command_data
#     except Exception as e:
#         _LOGGER.error(f"Error formatting ZBT-1 command: {e}")
#         # Return a basic command data structure as fallback for ZHA mode
#         return {
#             "ieee": format_ieee_with_colons(ieee),
#             "endpoint_id": SAFE4_ZBT1_ENDPOINT,
#             "cluster_id": SAFE4_DOOR_LOCK_CLUSTER,
#             "command": command_id,
#             "command_type": COMMAND_TYPE,
#             "params": {}
#         }
#
# def get_ieee_no_colons(ieee):
#     return normalize_ieee(ieee)["no_colons"]
#
# def get_cluster_handler_name(gateway_type="zha"):
#     if gateway_type == "zigbee":
#         return "zigbee_cluster_handler"
#     else:
#         return "zha_cluster_handler"
#
#
# def validate_ieee(ieee):
#
#     if not ieee:
#         return False, "", "IEEE address cannot be empty"
#
#     try:
#         # Try to format the IEEE address with colons
#         formatted_ieee = format_ieee_with_colons(ieee)
#
#         # Check if the formatted address is valid
#         parts = formatted_ieee.split(':')
#         if len(parts) != 8:
#             return False, formatted_ieee, f"IEEE address must have 8 parts, found {len(parts)}"
#
#         if not all(len(part) == 2 and all(c.lower() in '0123456789abcdef' for c in part) for part in parts):
#             return False, formatted_ieee, "IEEE address parts must be valid hexadecimal values"
#
#         return True, formatted_ieee, ""
#     except ValueError as e:
#         return False, "", str(e)
#     except Exception as e:
#         # Make sure we return a proper tuple
#         _LOGGER.error(f"Error validating IEEE address: {str(e)}")
#         # If we get here, return proper values with the error message
#         return False, ieee, f"Error validating IEEE address: {str(e)}"
