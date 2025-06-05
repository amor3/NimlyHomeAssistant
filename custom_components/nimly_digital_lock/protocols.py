import logging
import asyncio

from .const_zbt1 import (
    ZBT1_ENDPOINTS,
    ZBT1_LOCK_COMMAND,
    ZBT1_UNLOCK_COMMAND,
    SAFE4_DOOR_LOCK_CLUSTER,
    SAFE4_POWER_CLUSTER,
    SAFE4_LOCK_COMMAND,
    SAFE4_UNLOCK_COMMAND,
    SAFE4_ZBT1_ENDPOINT,
    SAFE4_DOOR_LOCK_PROFILE,
    COMMAND_PROFILE,
    COMMAND_TYPE
)

# Initialize logger
_LOGGER = logging.getLogger(__name__)
COMMON_ENDPOINTS = ZBT1_ENDPOINTS

# Begin zha_mapping functions

_LOGGER = logging.getLogger(__name__)

# Import constants from the dedicated constants file

ZBT1_LOCK_COMMANDS = {
    "lock_door": 0x00,
    "unlock_door": 0x01,
}

DOOR_LOCK_COMMANDS = {
    "toggle": 0x02,
    "unlock_with_timeout": 0x03,
    "get_log_record": 0x04,
    "set_pin_code": 0x05,
    "get_pin_code": 0x06,
    "clear_pin_code": 0x07,
    "clear_all_pin_codes": 0x08,
    "set_user_status": 0x09,
    "get_user_status": 0x0A,
    "set_week_day_schedule": 0x0B,
    "get_week_day_schedule": 0x0C,
    "clear_week_day_schedule": 0x0D,
    "set_year_day_schedule": 0x0E,
    "get_year_day_schedule": 0x0F,
    "clear_year_day_schedule": 0x10,
    "set_holiday_schedule": 0x11,
    "get_holiday_schedule": 0x12,
    "clear_holiday_schedule": 0x13,
    "set_user_type": 0x14,
    "get_user_type": 0x15,
    "set_rfid_code": 0x16,
    "get_rfid_code": 0x17,
    "clear_rfid_code": 0x18,
    "clear_all_rfid_codes": 0x19
}

DOOR_LOCK_CLUSTER = 0x0101


def format_ieee(ieee):
    ieee_clean = ''.join(c for c in ieee if c.lower() in '0123456789abcdef')
    ieee_with_colons = ':'.join([ieee_clean[i:i+2] for i in range(0, len(ieee_clean), 2)])
    return ieee_with_colons.lower()

def format_ieee_with_colons(ieee):
    """Format IEEE address with colons in the correct format.

    This function can handle IEEE in various formats:
    - With colons: aa:bb:cc:dd:ee:ff:00:11
    - Without colons: aabbccddeeff0011
    - With 0x prefix: 0xaabbccddeeff0011

    Returns properly formatted IEEE address with colons.
    """
    # Handle None or empty string
    if not ieee:
        return ""

    # If already has colons, validate format
    if ':' in ieee:
        # Check if format is correct (8 hex pairs separated by colons)
        parts = ieee.split(':')
        if len(parts) == 8 and all(len(part) == 2 and all(c.lower() in '0123456789abcdef' for c in part) for part in parts):
            return ieee.lower()

    # Remove 0x prefix if present
    if ieee.lower().startswith('0x'):
        ieee = ieee[2:]

    # Clean the string to only contain hex characters
    ieee_clean = ''.join(c for c in ieee if c.lower() in '0123456789abcdef')

    # Check if we have a valid length after cleaning
    if len(ieee_clean) != 16:
        # If length is odd, pad with a zero to make it even (allows join to work)
        if len(ieee_clean) % 2 != 0:
            _LOGGER.warning(f"IEEE address has odd length ({len(ieee_clean)}), padding with 0")
            ieee_clean = ieee_clean + '0'

        # Still handle special case for very short values (likely network addresses)
        if len(ieee_clean) <= 4:
            _LOGGER.warning(f"The provided value '{ieee}' appears to be a network address, not a valid IEEE address")
            # Don't raise exception, just return the best formatted version we can
            return ':'.join([ieee_clean[i:i+2] for i in range(0, len(ieee_clean), 2)]).lower()

        # For other unusual lengths, warn but try to format anyway
        _LOGGER.warning(f"Unusual IEEE address length: {len(ieee_clean)} (expected 16 hex characters)")

    # Format with colons - this should work for any even-length string of hex characters
    return ':'.join([ieee_clean[i:i+2] for i in range(0, len(ieee_clean), 2)]).lower()

LOCK_CLUSTER_ID = 0x0101
POWER_CLUSTER_ID = 0x0001

LOCK_COMMANDS = {
    "lock_door": 0x00,
    "unlock_door": 0x01,
    "toggle_door": 0x02,
    "unlock_with_timeout": 0x03,
    "get_log_record": 0x04,
    "set_pin_code": 0x05,
    "get_pin_code": 0x06,
    "clear_pin_code": 0x07,
    "clear_all_pin_codes": 0x08,
    "set_user_status": 0x09,
    "get_user_status": 0x0A,
    "set_week_day_schedule": 0x0B,
    "get_week_day_schedule": 0x0C,
    "clear_week_day_schedule": 0x0D,
    "set_year_day_schedule": 0x0E,
    "get_year_day_schedule": 0x0F,
    "clear_year_day_schedule": 0x10
}

POWER_ATTRIBUTES = {
    "mains_voltage": 0x0000,
    "battery_voltage": 0x0020,
    "battery_percentage_remaining": 0x0021,
    "battery_alarm_mask": 0x0035,
    "battery_voltage_min_threshold": 0x0036,
    "battery_voltage_threshold_1": 0x0037,
    "battery_voltage_threshold_2": 0x0038,
    "battery_voltage_threshold_3": 0x0039,
    "battery_percentage_min_threshold": 0x003A,
    "battery_percentage_threshold_1": 0x003B,
    "battery_percentage_threshold_2": 0x003C,
    "battery_percentage_threshold_3": 0x003D,
    "battery_low": 0x9000,
}

LOCK_RESPONSES = {
    "operation_event": 0x00,
    "programming_event": 0x01,
    "lock_status": 0x9000,
    "unlock_status": 0x9001
}

DEVICE_LOOKUP_METHODS = [
    "gateway.get_device",
    "application_controller.get_device",
    "coordinator.get_device",
    "device_registry.get_device",
    "gateway.devices",
    "application_controller.devices",
    "coordinator.devices",
    "device_registry.devices",
    "get_device"
]

def normalize_ieee(ieee):
    ieee_no_colons = ieee.replace(':', '')
    ieee_clean = ''.join(c for c in ieee_no_colons if c.lower() in '0123456789abcdef')
    ieee_no_colons = ieee_clean.lower()
    ieee_with_colons = ':'.join([ieee_clean[i:i+2] for i in range(0, len(ieee_clean), 2)]).lower()

    return {
        "original": ieee,
        "no_colons": ieee_no_colons,
        "with_colons": ieee_with_colons
    }

def format_nwk_address(nwk):
    if isinstance(nwk, str) and nwk.lower().startswith('0x'):
        return nwk.lower()
    if isinstance(nwk, int):
        return f"0x{nwk:04X}"
    try:
        value = int(nwk)
        return f"0x{value:04X}"
    except ValueError:
        return f"0x{nwk}"

def get_zha_address_for_command(hass, ieee=None, nwk=None):
    addresses = {}
    if ieee:
        ieee_formats = normalize_ieee(ieee)
        addresses["ieee"] = ieee_formats["with_colons"]
        addresses["ieee_no_colons"] = ieee_formats["no_colons"]
    if nwk:
        addresses["nwk"] = format_nwk_address(nwk)
    return addresses

LOCK_ATTRIBUTES = {
    "lock_state": 0x0000,
    "lock_type": 0x0001,
    "actuator_enabled": 0x0002,
    "door_state": 0x0003,
    "door_open_events": 0x0004,
    "door_closed_events": 0x0005,
    "open_period": 0x0006
}

async def is_zbt1_compatible(hass, ieee):
    try:
        # Use local get_endpoints function instead of imported one
        endpoints = await get_endpoints(hass, ieee)
        if SAFE4_ZBT1_ENDPOINT not in endpoints:
            _LOGGER.debug(f"Device {ieee} does not have required endpoint {SAFE4_ZBT1_ENDPOINT}")
            return False
        return True
    except Exception as e:
        _LOGGER.warning(f"Error checking ZBT-1 compatibility for {ieee}: {e}")
        return True

async def get_endpoints(hass, ieee):
    try:
        # Default list of endpoints to try for ZBT1 devices
        default_endpoints = ZBT1_ENDPOINTS
        return default_endpoints
    except Exception as e:
        _LOGGER.warning(f"Error retrieving endpoints: {e}")
        return [11, 1, 2, 3, 242]

def format_safe4_zbt1_command(ieee, command_id):
    """Format command according to Safe4 ZigBee Door Lock Module specification.

    The command format must be exactly:
    zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 <command id>

    Where:
    - Endpoint must be exactly 11
    - Cluster ID must be 0x0101 (Door Lock)
    - Profile ID must be 0x0104 (Home Automation)
    - Command ID must be 0x00 for lock, 0x01 for unlock
    - At least one of args or params must be present (even if empty)
    """
    try:
        # Validate and format IEEE address
        is_valid, ieee_with_colons, error_message = validate_ieee(ieee)
        if not is_valid:
            _LOGGER.error(f"Invalid IEEE address for command: {error_message}")
            raise ValueError(f"Invalid IEEE address: {error_message}")

        # Log the exact command we're about to send for debugging
        _LOGGER.debug(f"Formatting ZBT-1 command: IEEE={ieee_with_colons}, command_id={command_id}, "
                     f"endpoint={SAFE4_ZBT1_ENDPOINT}, cluster={SAFE4_DOOR_LOCK_CLUSTER}")

        # Home Assistant requires at least one of args or params to be present
        command_data = {
            "ieee": ieee_with_colons,
            "endpoint_id": SAFE4_ZBT1_ENDPOINT,  # Must be 11 per spec
            "cluster_id": SAFE4_DOOR_LOCK_CLUSTER,  # 0x0101 per spec
            "command": command_id,  # 0x00=lock, 0x01=unlock per spec
            "command_type": COMMAND_TYPE,  # server
            "params": {}  # Empty params required by Home Assistant
        }

        _LOGGER.debug(f"Formatted command data: {command_data}")
        return command_data
    except Exception as e:
        _LOGGER.error(f"Error formatting ZBT-1 command: {e}")
        # Return a basic command data structure as fallback for ZHA mode
        return {
            "ieee": format_ieee_with_colons(ieee),
            "endpoint_id": SAFE4_ZBT1_ENDPOINT,
            "cluster_id": SAFE4_DOOR_LOCK_CLUSTER,
            "command": command_id,
            "command_type": COMMAND_TYPE,
            "params": {}
        }

def get_ieee_no_colons(ieee):
    return normalize_ieee(ieee)["no_colons"]

def get_cluster_handler_name(gateway_type="zha"):
    if gateway_type == "zigbee":
        return "zigbee_cluster_handler"
    else:
        return "zha_cluster_handler"


def validate_ieee(ieee):

    if not ieee:
        return False, "", "IEEE address cannot be empty"

    try:
        # Try to format the IEEE address with colons
        formatted_ieee = format_ieee_with_colons(ieee)

        # Check if the formatted address is valid
        parts = formatted_ieee.split(':')
        if len(parts) != 8:
            return False, formatted_ieee, f"IEEE address must have 8 parts, found {len(parts)}"

        if not all(len(part) == 2 and all(c.lower() in '0123456789abcdef' for c in part) for part in parts):
            return False, formatted_ieee, "IEEE address parts must be valid hexadecimal values"

        return True, formatted_ieee, ""
    except ValueError as e:
        return False, "", str(e)
    except Exception as e:
        # Make sure we return a proper tuple
        _LOGGER.error(f"Error validating IEEE address: {str(e)}")
        # If we get here, return proper values with the error message
        return False, ieee, f"Error validating IEEE address: {str(e)}"

# Begin zbt1_support functions

_LOGGER = logging.getLogger(__name__)

# Import from the dedicated constants file

# Import helper functions from zha_mapping

async def get_zbt1_endpoints(hass, ieee):
    try:
        default_endpoints = [11, 1, 2, 3, 242]
        return default_endpoints
    except Exception as e:
        _LOGGER.warning(f"Error retrieving ZBT1 endpoints: {e}")
        return [11, 1, 2, 3, 242]




# Define ZHA domain constant directly instead of importing from unavailable path
ZHA_DOMAIN = "zha"


# Standard cluster IDs
DOOR_LOCK_CLUSTER = 0x0101
POWER_CLUSTER = 0x0001

# Nordic ZBT-1 uses endpoint 11
ZBT1_ENDPOINTS = [11, 1, 2, 3]

async def get_zha_device(hass, ieee_address):
    """Get the ZHA device object directly from the ZHA gateway.

    Args:
        hass: Home Assistant instance
        ieee_address: IEEE address of the device (with or without colons)

    Returns:
        ZHA device object or None if not found
    """
    # Clean up IEEE address for comparison
    ieee_clean = ieee_address.replace(':', '').lower()

    # Try to get the ZHA gateway
    if ZHA_DOMAIN not in hass.data or 'gateway' not in hass.data[ZHA_DOMAIN]:
        _LOGGER.warning("ZHA gateway not found in Home Assistant data")
        return None

    gateway = hass.data[ZHA_DOMAIN]['gateway']
    if not hasattr(gateway, 'devices'):
        _LOGGER.warning("ZHA gateway does not have devices attribute")
        return None

    # Look for our device in the gateway devices
    for device in gateway.devices.values():
        if hasattr(device, 'ieee') and str(device.ieee).replace(':', '').lower() == ieee_clean:
            _LOGGER.info(f"Found ZHA device: {device.ieee}")
            return device

    _LOGGER.warning(f"Device with IEEE {ieee_address} not found in ZHA gateway")
    return None

async def async_read_attribute_zbt1(hass, ieee, cluster_id, attribute_id, endpoint_id=11):
    """
    Try to read a Zigbee attribute from one of the known ZBT1 endpoints.
    If endpoint_id is given, try it first; otherwise loop through ZBT1_ENDPOINTS.
    """
    ieee_colon = format_ieee_with_colons(ieee)

    # If the caller already told us a preferred endpoint_id (e.g. 11), try it first
    endpoints_to_try = [endpoint_id] + [ep for ep in ZBT1_ENDPOINTS if ep != endpoint_id] \
                      if endpoint_id is not None \
                      else ZBT1_ENDPOINTS

    for ep in endpoints_to_try:
        if ep is None:
            continue
        try:
            service_data = {
                "ieee": ieee_colon,
                "endpoint_id": ep,
                "cluster_id": cluster_id,
                "attribute": attribute_id,
            }
            _LOGGER.debug(f"Trying ZBT-1 read: cluster={hex(cluster_id)} attr={hex(attribute_id)} on ep {ep}")
            result = await hass.services.async_call(
                "zha",
                "read_attribute",
                service_data,
                blocking=True,
                return_response=True,
            )
            if result is not None:
                _LOGGER.info(f"ZBT-1 read got {attribute_id=} on ep {ep}: {result}")
                return result
        except Exception as e:
            _LOGGER.debug(f"ZBT-1 read failed on ep={ep} (cluster={hex(cluster_id)}, attr={hex(attribute_id)}): {e}")

    _LOGGER.warning(f"ZBT-1 read never succeeded (cluster={hex(cluster_id)}, attr={hex(attribute_id)})")
    return None

async def async_send_command_zbt1(hass, ieee_address, command, cluster_id, endpoint_id=11, params=None):
    """Send a Zigbee command for ZBT1 devices via ZHA."""
    ieee_colon = format_ieee_with_colons(ieee_address)
    # Prepare args list
    args = params if params is not None else []
    service_data = {
        "ieee": ieee_colon,
        "endpoint_id": endpoint_id,
        "cluster_id": cluster_id,
        "command": command,
        "args": args,
    }
    try:
        await hass.services.async_call(
            "zha",
            "issue_zigbee_cluster_command",
            service_data,
            blocking=True,
        )
        _LOGGER.info(f"Sent ZBT1 command {command} on cluster {hex(cluster_id)} ep {endpoint_id}")
        return True
    except Exception as e:
        _LOGGER.error(f"Error sending ZBT1 command: {e}")
        return False

# Begin nordic functions
"""Nordic ZBT-1 specific command implementation for Nimly locks."""
"""Nordic Semiconductor ZBT-1 specific implementation for Nimly Digital Lock.

This module implements the exact command format required by the Nordic Semiconductor
ZBT-1 specification for the Safe4 ZigBee Door Lock Module.

According to the specification, commands must be sent in this exact format:
zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 <command id>

Where:
- Endpoint must be exactly 11
- Cluster ID must be 0x0101 (Door Lock)
- Profile ID must be 0x0104 (Home Automation)
- Command ID must be 0x00 for lock, 0x01 for unlock
- NO parameters can be passed
"""


_LOGGER = logging.getLogger(__name__)

# Import constants from dedicated constants file

# Pin code related constants
ZBT1_SET_PIN_CODE = 0x05      # Set PIN Code
ZBT1_CLEAR_PIN_CODE = 0x07    # Clear PIN Code
ZBT1_CLEAR_ALL_PIN_CODES = 0x08  # Clear All PIN Codes

# Import helper functions from zha_mapping

async def send_nordic_command(hass, ieee, command_id, retry_count=5, retry_delay=1.0):
    """Send a command to a Nordic ZBT-1 device using the exact format required by the spec.

    The Nordic ZBT-1 specification requires commands to be in this format:
    zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 <command id>

    Args:
        hass: Home Assistant instance
        ieee: IEEE address of the device
        command_id: Command ID (0x00 for lock, 0x01 for unlock)
        retry_count: Number of retries for sending the command
        retry_delay: Delay between retries in seconds

    Returns:
        Boolean indicating success or failure
    """
    _LOGGER.info(f"Sending Nordic ZBT-1 command {command_id} to device {ieee}")

    # Validate IEEE address with error handling
    try:
        is_valid, ieee_with_colons, error_message = validate_ieee(ieee)
        if not is_valid:
            _LOGGER.error(f"Invalid IEEE address: {error_message}")
            # Continue with original address as fallback instead of returning
            _LOGGER.warning(f"Attempting to continue with original IEEE address: {ieee}")
            ieee_with_colons = ieee

        _LOGGER.debug(f"Using formatted IEEE address: {ieee_with_colons}")
    except Exception as e:
        _LOGGER.error(f"Error validating IEEE address: {e}")
        # Use original address as fallback
        ieee_with_colons = ieee
        _LOGGER.warning(f"Using original IEEE address as fallback: {ieee_with_colons}")

    # According to Safe4 spec, command must be in format:
    # zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 <command id>
    # Home Assistant requires at least empty params or args
    command_data = format_safe4_zbt1_command(ieee, command_id)

    # Try both service domains
    service_domains = ["zigbee", "zha"]
    service_methods = ["issue_zigbee_cluster_command", "command"]

    # Track success
    success = False

    # Try each service domain and method
    for domain in service_domains:
        for method in service_methods:
            if not hass.services.has_service(domain, method):
                _LOGGER.debug(f"Service {domain}.{method} not available")
                continue

            # Try multiple attempts
            for attempt in range(retry_count):
                # Try with both params and args formats
                command_formats = [
                    # First try with params (most common)
                    {**command_data},
                    # Then try with args instead of params
                    {key: value for key, value in command_data.items() if key != "params"}
                ]

                if "params" in command_data:
                    # Add empty args as a fallback format
                    args_format = {key: value for key, value in command_data.items() if key != "params"}
                    args_format["args"] = {}
                    command_formats.append(args_format)

                for cmd_format in command_formats:
                    try:
                        _LOGGER.debug(f"Attempt {attempt+1}/{retry_count} using {domain}.{method} with format: {cmd_format}")

                        # Send the command
                        await hass.services.async_call(
                            domain, method, cmd_format, blocking=True
                        )

                        _LOGGER.info(f"Successfully sent command {command_id} using {domain}.{method}")
                        success = True
                        return True
                    except Exception as e:
                        _LOGGER.debug(f"Failed format {cmd_format} on attempt {attempt+1} using {domain}.{method}: {e}")

                        # Check for specific error message about missing args/params
                        error_msg = str(e).lower()
                        if "must contain at least one of args, params" in error_msg:
                            _LOGGER.warning("Service requires either args or params to be present")
                        elif "not a valid value for dictionary value @ data['ieee']" in error_msg:
                            _LOGGER.warning("IEEE address format is not valid for this service")

                # If we tried all formats and none worked, wait before the next attempt
                if attempt < retry_count - 1:
                    await asyncio.sleep(retry_delay)

    if not success:
        _LOGGER.error(f"Failed to send command {command_id} after {retry_count} attempts with all methods")

    return success

async def lock_door(hass, ieee):
    """Lock the door using Nordic ZBT-1 specification.

    Args:
        hass: Home Assistant instance
        ieee: IEEE address of the device

    Returns:
        Boolean indicating success or failure
    """
    _LOGGER.info(f"Locking door with Nordic ZBT-1 format: {ieee}")
    return await send_nordic_command(hass, ieee, SAFE4_LOCK_COMMAND)

async def unlock_door(hass, ieee):
    """Unlock the door using Nordic ZBT-1 specification.

    According to the Safe4 ZigBee Door Lock Module specification:
    - Command must be sent in this exact format: 
      zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 0x01
    - Endpoint must be exactly 11
    - Cluster ID must be 0x0101 (Door Lock)
    - Profile ID must be 0x0104 (Home Automation)
    - Command ID must be 0x01 for unlock
    - NO parameters can be passed

    Args:
        hass: Home Assistant instance
        ieee: IEEE address of the device

    Returns:
        Boolean indicating success or failure
    """
    _LOGGER.info(f"Unlocking door with Nordic ZBT-1 format: {ieee}")
    # Use a higher retry count for unlock since this seems to be problematic
    return await send_nordic_command(hass, ieee, SAFE4_UNLOCK_COMMAND, retry_count=10)

async def read_attribute(hass, ieee, cluster_id, attribute_id, endpoint=SAFE4_ZBT1_ENDPOINT):
    """Read an attribute from a Nordic ZBT-1 device.

    Args:
        hass: Home Assistant instance
        ieee: IEEE address of the device
        cluster_id: Cluster ID
        attribute_id: Attribute ID
        endpoint: Endpoint ID (default is 11 for ZBT-1)

    Returns:
        Attribute value or None if not available
    """
    _LOGGER.debug(f"Reading attribute {attribute_id} from cluster {cluster_id} on endpoint {endpoint}")

    # Format IEEE address with colons
    ieee_with_colons = format_ieee_with_colons(ieee)

    # Service data for reading attribute
    service_data = {
        "ieee": ieee_with_colons,
        "endpoint_id": endpoint,
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


async def set_pin_code(hass, ieee, user_id, pin_code, status=1, user_type=0, endpoint=SAFE4_ZBT1_ENDPOINT):
    """Set a PIN code for a user on a Nordic ZBT-1 device.

    Args:
        hass: Home Assistant instance
        ieee: IEEE address of the device
        user_id: User ID (1-255)
        pin_code: PIN code string (4-10 digits)
        status: User status (1=enabled, 0=disabled)
        user_type: User type (0=unrestricted, 1=year/day, 2=week/day, 3=master)
        endpoint: Endpoint ID (default is 11 for ZBT-1)

    Returns:
        Boolean indicating success or failure
    """
    _LOGGER.info(f"Setting PIN code for user {user_id} on device {ieee}")

    # Format IEEE address with colons
    ieee_with_colons = format_ieee_with_colons(ieee)

    # Validate user_id
    if not 1 <= user_id <= 255:
        _LOGGER.error(f"Invalid user ID: {user_id}. Must be between 1 and 255.")
        return False

    # Validate pin_code - must be 4-10 digits
    if not pin_code.isdigit() or not 4 <= len(pin_code) <= 10:
        _LOGGER.error(f"Invalid PIN code: {pin_code}. Must be 4-10 digits.")
        return False

    # Format user ID as string
    user_id_str = str(user_id)

    # Service data for setting PIN code
    service_data = {
        "ieee": ieee_with_colons,
        "endpoint_id": endpoint,
        "cluster_id": SAFE4_DOOR_LOCK_CLUSTER,
        "command": ZBT1_SET_PIN_CODE,
        "command_type": "server",
        "params": {
            "user_id": user_id,
            "user_status": status,
            "user_type": user_type,
            "pin_code": pin_code
        }
    }

    # Try both service domains
    service_domains = ["zigbee", "zha"]
    service_methods = ["issue_zigbee_cluster_command", "command"]

    # Track success
    success = False

    # Try each service domain and method
    for domain in service_domains:
        for method in service_methods:
            if not hass.services.has_service(domain, method):
                continue

            try:
                _LOGGER.debug(f"Trying to set PIN code using {domain}.{method}")

                # Send the command
                await hass.services.async_call(
                    domain, method, service_data, blocking=True
                )

                _LOGGER.info(f"Successfully set PIN code for user {user_id} using {domain}.{method}")
                success = True
                return True
            except Exception as e:
                _LOGGER.warning(f"Failed to set PIN code for user {user_id} using {domain}.{method}: {e}")

    if not success:
        _LOGGER.error(f"Failed to set PIN code for user {user_id} with all methods")

    return success


async def clear_pin_code(hass, ieee, user_id, endpoint=SAFE4_ZBT1_ENDPOINT):
    """Clear a PIN code for a user on a Nordic ZBT-1 device.

    Args:
        hass: Home Assistant instance
        ieee: IEEE address of the device
        user_id: User ID (1-255) or 0 to clear all PIN codes
        endpoint: Endpoint ID (default is 11 for ZBT-1)

    Returns:
        Boolean indicating success or failure
    """
    _LOGGER.info(f"Clearing PIN code for user {user_id} on device {ieee}")

    # Format IEEE address with colons
    ieee_with_colons = format_ieee_with_colons(ieee)

    # Determine which command to use based on user_id
    command_id = ZBT1_CLEAR_ALL_PIN_CODES if user_id == 0 else ZBT1_CLEAR_PIN_CODE

    # Service data for clearing PIN code
    service_data = {
        "ieee": ieee_with_colons,
        "endpoint_id": endpoint,
        "cluster_id": SAFE4_DOOR_LOCK_CLUSTER,
        "command": command_id,
        "command_type": "server"
    }

    # Add user_id parameter if clearing a specific user
    if user_id != 0:
        service_data["params"] = {"user_id": user_id}

    # Try both service domains
    service_domains = ["zigbee", "zha"]
    service_methods = ["issue_zigbee_cluster_command", "command"]

    # Track success
    success = False

    # Try each service domain and method
    for domain in service_domains:
        for method in service_methods:
            if not hass.services.has_service(domain, method):
                continue

            try:
                _LOGGER.debug(f"Trying to clear PIN code using {domain}.{method}")

                # Send the command
                await hass.services.async_call(
                    domain, method, service_data, blocking=True
                )

                _LOGGER.info(f"Successfully cleared PIN code for user {user_id} using {domain}.{method}")
                success = True
                return True
            except Exception as e:
                _LOGGER.warning(f"Failed to clear PIN code for user {user_id} using {domain}.{method}: {e}")

    if not success:
        _LOGGER.error(f"Failed to clear PIN code for user {user_id} with all methods")

    return success

# Begin Safe4 lock functions merged from safe4_lock.py
async def send_safe4_lock_command(hass, ieee):
    """Send the lock command according to Safe4 ZigBee Door Lock Module specification.

    Command format: `zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 0x00`
    - Endpoint must be exactly 11
    - Cluster ID must be 0x0101 (Door Lock)
    - Profile ID must be 0x0104 (Home Automation)
    - Command ID must be 0x00 for lock
    - NO parameters can be passed

    Args:
        hass: Home Assistant instance
        ieee: IEEE address of the device

    Returns:
        Boolean indicating success or failure
    """
    _LOGGER.info(f"Sending Safe4 lock command to device {ieee}")

    # Format IEEE address with colons
    ieee_with_colons = format_ieee_with_colons(ieee)

    # Get the command parameters in the correct format
    command_data = format_safe4_zbt1_command(ieee, SAFE4_LOCK_COMMAND)

    # Only use ZHA service domain
    service_domains = ["zha"]
    service_methods = ["issue_zigbee_cluster_command", "command"]

    # Track success
    success = False

    # Try each service domain and method
    for domain in service_domains:
        for method in service_methods:
            if not hass.services.has_service(domain, method):
                continue

            try:
                _LOGGER.debug(f"Trying {domain}.{method} for Safe4 lock command")

                # Send the command
                await hass.services.async_call(
                    domain, method, command_data, blocking=True
                )

                _LOGGER.info(f"Successfully sent Safe4 lock command using {domain}.{method}")
                success = True
                return True
            except Exception as e:
                _LOGGER.warning(f"Failed to send Safe4 lock command using {domain}.{method}: {e}")

    if not success:
        _LOGGER.error("Failed to send Safe4 lock command with all methods")

    return success

async def send_safe4_unlock_command(hass, ieee):
    """Send the unlock command according to Safe4 ZigBee Door Lock Module specification.

    Command format: `zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 0x01`
    - Endpoint must be exactly 11
    - Cluster ID must be 0x0101 (Door Lock)
    - Profile ID must be 0x0104 (Home Automation)
    - Command ID must be 0x01 for unlock
    - NO parameters can be passed

    Args:
        hass: Home Assistant instance
        ieee: IEEE address of the device

    Returns:
        Boolean indicating success or failure
    """
    _LOGGER.info(f"Sending Safe4 unlock command to device {ieee}")

    # Format IEEE address with colons
    ieee_with_colons = format_ieee_with_colons(ieee)

    # Get the command parameters in the correct format
    command_data = format_safe4_zbt1_command(ieee, SAFE4_UNLOCK_COMMAND)

    # Only use ZHA service domain
    service_domains = ["zha"]
    service_methods = ["issue_zigbee_cluster_command", "command"]

    # Track success
    success = False

    # Try each service domain and method
    for domain in service_domains:
        for method in service_methods:
            if not hass.services.has_service(domain, method):
                continue

            try:
                _LOGGER.debug(f"Trying {domain}.{method} for Safe4 unlock command")

                # Send the command
                await hass.services.async_call(
                    domain, method, command_data, blocking=True
                )

                _LOGGER.info(f"Successfully sent Safe4 unlock command using {domain}.{method}")
                success = True
                return True
            except Exception as e:
                _LOGGER.warning(f"Failed to send Safe4 unlock command using {domain}.{method}: {e}")

    if not success:
        _LOGGER.error("Failed to send Safe4 unlock command with all methods")

    return success


async def get_lock_status(hass, ieee):
    """Get the current lock status from a Safe4 ZigBee Door Lock Module device.

    Args:
        hass: Home Assistant instance
        ieee: IEEE address of the device

    Returns:
        0 for unlocked, 1 for locked, or None if not available
    """
    _LOGGER.debug(f"Getting lock status for device {ieee}")

    # Read the lock state attribute
    result = await read_safe4_attribute(hass, ieee, SAFE4_DOOR_LOCK_CLUSTER, 0x0000)

    if result is not None:
        _LOGGER.info(f"Lock status: {result}")
        return result

    _LOGGER.warning("Failed to get lock status")
    return None

async def get_battery_level(hass, ieee):
    """Get the battery level from a Safe4 ZigBee Door Lock Module device.

    Args:
        hass: Home Assistant instance
        ieee: IEEE address of the device

    Returns:
        Battery level percentage or None if not available
    """
    _LOGGER.debug(f"Getting battery level for device {ieee}")

    # Read the battery percentage remaining attribute
    result = await read_safe4_attribute(hass, ieee, SAFE4_POWER_CLUSTER, 0x0021)

    if result is not None:
        _LOGGER.info(f"Battery level: {result}%")
        return result

    _LOGGER.warning("Failed to get battery level")
    return None

async def read_safe4_attribute(hass, ieee, cluster_id, attribute_id, endpoint=11):
    """
    Try to read a single attribute from any of the common endpoints (in order).
    Calls zha.read_attribute under the hood, and returns the first non-None result.
    """
    # Format the IEEE the way ZHA expects (with colons)

    ieee_colon = format_ieee_with_colons(ieee)

    for ep_id in COMMON_ENDPOINTS:
        try:
            service_data = {
                "ieee": ieee_colon,
                "endpoint_id": ep_id,
                "cluster_id": cluster_id,
                "attribute": attribute_id,
            }
            _LOGGER.debug(f"Trying Safe4 read: cluster={hex(cluster_id)} attr={hex(attribute_id)} on endpoint {ep_id}")
            result = await hass.services.async_call(
                "zha",
                "read_attribute",
                service_data,
                blocking=True,
                return_response=True,
            )
            if result is not None:
                _LOGGER.info(f"Safe4 read got attribute_id={attribute_id} on ep {ep_id}: {result}")
                return result
        except Exception as e:
            _LOGGER.debug(f"Safe4 read failed on ep={ep_id} (cluster={hex(cluster_id)}, attr={hex(attribute_id)}): {e}")

    _LOGGER.warning(f"Safe4 read never succeeded (cluster={hex(cluster_id)}, attr={hex(attribute_id)})")
    return None

async def try_direct_zha_gateway_access(hass, ieee_address, cluster_id, attribute_id, cluster_type, ieee_formats):
    from .const import DOMAIN
    ZHA_DOMAIN = "zha"

    # Validate inputs to prevent errors
    if not ieee_address or not ieee_formats:
        _LOGGER.warning("Missing IEEE address or formats in try_direct_zha_gateway_access")
        return None

    # Ensure we have a list of formats
    if not isinstance(ieee_formats, list):
        ieee_formats = [ieee_formats]

    try:

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

    # Try to import ZHA_DOMAIN directly if needed
    try:
        from homeassistant.components.zha.core.const import DOMAIN as ZHA_DOMAIN
    except ImportError:
        ZHA_DOMAIN = "zha"

    return None

    # Try direct ZHA gateway access as last resort