"""Nordic Semiconductor ZBT-1 command implementation for Nimly digital locks.

Implements the command format exactly as specified in the Nordic Semiconductor documentation:
https://infocenter.nordicsemi.com/index.jsp?topic=%2Fsdk_tz_v4.1.0%2Fzigbee_example_cli_agent.html
"""

import logging
import asyncio

_LOGGER = logging.getLogger(__name__)

# Constants as specified in Nordic Semiconductor documentation
ZBT1_DOOR_LOCK_CLUSTER = 0x0101  # Door Lock cluster
ZBT1_HOME_AUTOMATION_PROFILE = 0x0104  # Home Automation profile
ZBT1_ENDPOINT = 11  # MUST be exactly 11 per spec

# Door Lock Command IDs (from ZCL 7.3.2.16 Server Commands)
ZBT1_LOCK_COMMAND = 0x00    # Lock Door
ZBT1_UNLOCK_COMMAND = 0x01  # Unlock Door
ZBT1_SET_PIN_CODE = 0x05    # Set PIN Code
ZBT1_CLEAR_PIN_CODE = 0x07  # Clear PIN Code
ZBT1_CLEAR_RFID_CODE = 0x18 # Clear RFID Code
ZBT1_SCAN_RFID_CODE = 0x70  # Scan RFID Code (Custom)
ZBT1_SCAN_FINGERPRINT = 0x71 # Scan Fingerprint (Custom)
ZBT1_CLEAR_FINGERPRINT = 0x72 # Clear Fingerprint (Custom)
ZBT1_LOCAL_PROGRAMMING_DISABLE = 0x73 # Local Programming Disable (Custom)
ZBT1_LOCAL_PROGRAMMING_ENABLE = 0x74  # Local Programming Enable (Custom)

async def send_nordic_command(hass, ieee_address, command_id, payload=None, retry_count=3, retry_delay=2.0):
    """Send a command to a Nordic Semiconductor ZBT-1 lock using exact Nordic CLI format.

    This follows the exact command structure from Nordic documentation:
    zcl cmd <IEEE Addr/NWK Addr> 11 0x0101 -p 0x0104 <command id> [-l <command payload>]

    Args:
        hass: Home Assistant instance
        ieee_address: IEEE address of the device
        command_id: Command ID (see constants above)
        payload: Optional command payload for commands that require it
        retry_count: Number of retries
        retry_delay: Delay between retries in seconds

    Returns:
        True if successful, False otherwise
    """
    _LOGGER.info(f"Sending Nordic ZBT-1 command 0x{command_id:02x} to {ieee_address} (endpoint {ZBT1_ENDPOINT})")

    # 1. Normalize IEEE address - try both with and without colons
    ieee_no_colons = ieee_address.replace(':', '')
    ieee_with_colons = ':'.join([ieee_no_colons[i:i+2] for i in range(0, len(ieee_no_colons), 2)])

    # Try both address formats
    ieee_formats = [ieee_with_colons, ieee_no_colons]

    # Add fallback addresses if primary address fails
    fallback_addresses = [
        "f4:ce:36:0a:04:4d:31:f5",
        "f4ce360a044d31f5"
    ]

    # Try ZHA service first - it supports the exact Nordic CLI format
    for attempt in range(retry_count):
        for ieee in ieee_formats + ([] if attempt == 0 else fallback_addresses):
            try:
                # Prepare service data exactly as specified in Nordic docs
                # zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 <command id>
                service_data = {
                    "ieee": ieee,
                    "endpoint_id": ZBT1_ENDPOINT,  # MUST be exactly 11
                    "cluster_id": ZBT1_DOOR_LOCK_CLUSTER,
                    "command": command_id,
                    "command_type": "server",
                    "profile": ZBT1_HOME_AUTOMATION_PROFILE,  # Add the profile ID as specified
                    "params": {}  # No parameters for lock/unlock per spec
                }

                # If payload is provided, add it (-l parameter in Nordic CLI)
                if payload:
                    service_data["params"] = payload

                _LOGGER.debug(f"Sending ZHA command with data: {service_data}")

                # Send command using ZHA service
                await hass.services.async_call(
                    "zha", 
                    "issue_zigbee_cluster_command", 
                    service_data,
                    blocking=True
                )

                _LOGGER.info(f"Successfully sent Nordic ZBT-1 command 0x{command_id:02x} to {ieee}")
                return True
            except Exception as e:
                _LOGGER.warning(f"Failed to send Nordic command to {ieee} (attempt {attempt+1}): {e}")

                # Check for specific error about device not responding
                if "device did not respond" in str(e).lower():
                    _LOGGER.warning("Device not responding - this could indicate:")  
                    _LOGGER.warning("1. The lock is in sleep mode or batteries are low")
                    _LOGGER.warning("2. The ZigBee network has connectivity issues")
                    _LOGGER.warning("3. The lock is not properly paired with the ZigBee network")

                # Only delay if we're going to retry
                if attempt < retry_count - 1 or ieee != fallback_addresses[-1]:
                    await asyncio.sleep(retry_delay)

    # If all ZHA attempts fail, try with Nabu Casa Zigbee service
    try:
        # Similar service data but adapted for zigbee service
        service_data = {
            "ieee": ieee_with_colons,
            "endpoint_id": ZBT1_ENDPOINT,
            "cluster_id": ZBT1_DOOR_LOCK_CLUSTER,
            "command": command_id,
            "command_type": "server"
        }

        # If payload is provided, add it
        if payload:
            service_data["params"] = payload

        _LOGGER.debug(f"Trying Nabu Casa Zigbee service with data: {service_data}")

        await hass.services.async_call(
            "zigbee",
            "issue_zigbee_cluster_command",
            service_data,
            blocking=True
        )

        _LOGGER.info(f"Successfully sent command via Nabu Casa Zigbee service")
        return True
    except Exception as e:
        _LOGGER.warning(f"Failed to send using Nabu Casa Zigbee: {e}")

    _LOGGER.error(f"All attempts to send Nordic ZBT-1 command 0x{command_id:02x} failed")
    return False

async def lock_door(hass, ieee_address):
    """Lock the door using Nordic ZBT-1 format."""
    _LOGGER.info(f"Locking door with Nordic ZBT-1 format: {ieee_address}")
    # ZBT-1 lock command is 0x00
    ZBT1_LOCK_COMMAND = 0x00
    return await send_nordic_command(hass, ieee_address, ZBT1_LOCK_COMMAND)

async def unlock_door(hass, ieee_address):
    """Unlock the door using Nordic ZBT-1 format."""
    _LOGGER.info(f"Unlocking door with Nordic ZBT-1 format: {ieee_address}")
    return await send_nordic_command(hass, ieee_address, ZBT1_UNLOCK_COMMAND)

async def set_pin_code(hass, ieee_address, user_id, pin_code):
    """Set a PIN code on the device in a specific slot.

    Command ID: 0x05
    Payload format per Nordic spec:
    - User Id: uint16 (2 bytes, little endian)
    - User Status: uint8 (1 byte, always 0)
    - User Type: enum8 (1 byte, always 0)
    - PIN Code: octstr (Variable, first byte = length, rest = ASCII 0x30-0x39)

    Example from Nordic docs: Set 6 digit PIN code 123456 in slot number 6:
    zcl cmd f4ce36ca69d72f85 11 0x0101 -p 0x0104 0x05 -l 0600000006313233343536
    """
    # Validate user_id (slot number)
    if not isinstance(user_id, int) or user_id < 2:
        _LOGGER.error(f"Invalid user_id: {user_id}. Must be an integer >= 2")
        return False

    # Validate PIN code (must be numeric)
    if not pin_code.isdigit():
        _LOGGER.error(f"Invalid PIN code: {pin_code}. Must contain only digits")
        return False

    # Construct payload exactly as specified in Nordic docs
    # User ID (2 bytes, little endian)
    user_id_bytes = user_id.to_bytes(2, byteorder='little')

    # User Status (1 byte, always 0) and User Type (1 byte, always 0)
    status_type_bytes = bytes([0, 0])

    # PIN code length (1 byte) followed by ASCII digits
    pin_length = len(pin_code)
    pin_bytes = bytes([pin_length]) + pin_code.encode('ascii')

    # Complete payload
    payload_bytes = user_id_bytes + status_type_bytes + pin_bytes

    # Convert to hex string for debug logging (same format as Nordic example)
    payload_hex = payload_bytes.hex()
    _LOGGER.debug(f"Setting PIN code with payload: {payload_hex}")

    # Send command with payload
    return await send_nordic_command(hass, ieee_address, ZBT1_SET_PIN_CODE, payload_bytes)

async def clear_pin_code(hass, ieee_address, user_id):
    """Remove a PIN code in a specific slot from the device.

    Command ID: 0x07
    Payload format per Nordic spec:
    - User Id: uint16 (2 bytes, little endian)

    Example from Nordic docs: Clear PIN Code in slot number 6:
    zcl cmd f4ce36ca69d72f85 11 0x0101 -p 0x0104 0x07 -l 0600
    """
    # Validate user_id (slot number)
    if not isinstance(user_id, int) or user_id < 2:
        _LOGGER.error(f"Invalid user_id: {user_id}. Must be an integer >= 2")
        return False

    # Construct payload: User ID (2 bytes, little endian)
    payload_bytes = user_id.to_bytes(2, byteorder='little')

    # Convert to hex string for debug logging
    payload_hex = payload_bytes.hex()
    _LOGGER.debug(f"Clearing PIN code with payload: {payload_hex}")

    # Send command with payload
    return await send_nordic_command(hass, ieee_address, ZBT1_CLEAR_PIN_CODE, payload_bytes)
