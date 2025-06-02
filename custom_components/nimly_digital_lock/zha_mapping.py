"""ZHA mapping constants for Nimly Digital Lock.

This module provides mapping between string command names and their numeric IDs.
"""

import logging

_LOGGER = logging.getLogger(__name__)

# Door Lock cluster command IDs - ZBT-1 specific mapping
ZBT1_LOCK_COMMANDS = {
    "lock_door": 0x00,
    "unlock_door": 0x01,
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


def format_ieee(ieee):
    """Format IEEE address to lowercase with colons.

    Args:
        ieee: IEEE address in any format

    Returns:
        Formatted IEEE address with colons
    """
    # Remove any non-hex characters
    ieee_clean = ''.join(c for c in ieee if c.lower() in '0123456789abcdef')
    # Format with colons for consistency
    ieee_with_colons = ':'.join([ieee_clean[i:i+2] for i in range(0, len(ieee_clean), 2)])
    return ieee_with_colons.lower()

def format_ieee_with_colons(ieee):
    """Ensures IEEE address has colons, preserving original case.

    This function is optimized for Nabu Casa ZBT-1 which may require specific IEEE format.

    Args:
        ieee: IEEE address with or without colons

    Returns:
        IEEE address with colons
    """
    # If already contains colons, return as is
    if ':' in ieee:
        return ieee

    # Remove any non-hex characters
    ieee_clean = ''.join(c for c in ieee if c.lower() in '0123456789abcdef')

    # Format with colons
    return ':'.join([ieee_clean[i:i+2] for i in range(0, len(ieee_clean), 2)])

# Standard Zigbee Cluster IDs
LOCK_CLUSTER_ID = 0x0101  # Door Lock cluster
POWER_CLUSTER_ID = 0x0001  # Power Configuration cluster

# Zigbee Door Lock Cluster Commands (from ZCL spec)
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

# Door Lock Cluster Attributes reference

# Zigbee Power Configuration Cluster Attributes
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
    # Non-standard attributes that some devices might use
    "battery_low": 0x9000,
}

# Zigbee Door Lock Cluster Command Responses
LOCK_RESPONSES = {
    "operation_event": 0x00,
    "programming_event": 0x01,
    # ZHA custom commands
    "lock_status": 0x9000,
    "unlock_status": 0x9001
}

# Methods to get device by IEEE in different ZHA implementations
DEVICE_LOOKUP_METHODS = [
    # ZHA gateway methods
    "gateway.get_device",
    "application_controller.get_device",
    "coordinator.get_device",
    "device_registry.get_device",
    # Direct dictionary access
    "gateway.devices",
    "application_controller.devices",
    "coordinator.devices",
    "device_registry.devices",
    # Direct function
    "get_device"
]

def normalize_ieee(ieee):
    """Normalize IEEE address to different formats for compatibility.

    Args:
        ieee: An IEEE address in any format (with or without colons)

    Returns:
        dict: Dictionary with three formats: original, no_colons, with_colons
    """
    # Remove colons if present
    ieee_no_colons = ieee.replace(':', '')

    # Clean up to only contain hex characters
    ieee_clean = ''.join(c for c in ieee_no_colons if c.lower() in '0123456789abcdef')
    ieee_no_colons = ieee_clean.lower()

    # Add colons if not present
    ieee_with_colons = ':'.join([ieee_clean[i:i+2] for i in range(0, len(ieee_clean), 2)]).lower()

    return {
        "original": ieee,
        "no_colons": ieee_no_colons,
        "with_colons": ieee_with_colons
    }

def format_nwk_address(nwk):
    """Format network address (nwk) for ZHA service calls.

    Args:
        nwk: Network address, like 0x7FDB

    Returns:
        Properly formatted network address for ZHA/zigbee calls
    """
    # If already in hex format (0x prefix), return as is
    if isinstance(nwk, str) and nwk.lower().startswith('0x'):
        return nwk.lower()

    # If it's a number, convert to hex
    if isinstance(nwk, int):
        return f"0x{nwk:04X}"

    # If it's a string but not in hex format, convert
    try:
        # Try parsing as decimal
        value = int(nwk)
        return f"0x{value:04X}"
    except ValueError:
        # If not a number, assume it's already hex but missing prefix
        return f"0x{nwk}"

def get_zha_address_for_command(hass, ieee=None, nwk=None):
    """Get the best address to use for ZHA commands.

    Args:
        hass: Home Assistant instance
        ieee: IEEE address (optional)
        nwk: Network address (optional)

    Returns:
        Dictionary with address options to try in order of preference
    """
    # Collect available addresses
    addresses = {}

    # Process IEEE if provided
    if ieee:
        ieee_formats = normalize_ieee(ieee)
        addresses["ieee"] = ieee_formats["with_colons"]
        addresses["ieee_no_colons"] = ieee_formats["no_colons"]

    # Process network address if provided
    if nwk:
        addresses["nwk"] = format_nwk_address(nwk)
"""ZHA mapping for lock commands and attributes."""

# We already have LOCK_COMMANDS defined above - not redefining

# ZBT-1 specific lock commands
ZBT1_LOCK_COMMANDS = {
    "lock": 0x00,      # Lock Door
    "unlock": 0x01,    # Unlock Door
}

# Export individual command constants for direct use
ZBT1_LOCK_COMMAND = 0x00    # Lock command
ZBT1_UNLOCK_COMMAND = 0x01  # Unlock command

# Lock attributes - Defined at module level to avoid duplicate declarations
if 'LOCK_ATTRIBUTES' not in globals():
    LOCK_ATTRIBUTES = {
        "lock_state": 0x0000,  # Lock State
        "lock_type": 0x0001,  # Lock Type
        "actuator_enabled": 0x0002,  # Actuator Enabled
        "door_state": 0x0003,  # Door State
        "door_open_events": 0x0004,  # Door Open Events
        "door_closed_events": 0x0005,  # Door Closed Events
    "open_period": 0x0006,  # Open Period
    "num_lock_records_supported": 0x0010,  # Number of Log Records Supported
    "num_total_users_supported": 0x0011,  # Number of Total Users Supported
    "num_pin_users_supported": 0x0012,  # Number of PIN Users Supported
    "num_rfid_users_supported": 0x0013,  # Number of RFID Users Supported
    "num_week_day_schedules_supported_per_user": 0x0014,  # Number of Week Day Schedules Supported Per User
    "num_year_day_schedules_supported_per_user": 0x0015,  # Number of Year Day Schedules Supported Per User
    "num_holiday_schedules_supported": 0x0016,  # Number of Holiday Schedules Supported
    "max_pin_len": 0x0017,  # Max PIN Code Length
    "min_pin_len": 0x0018,  # Min PIN Code Length
    "max_rfid_len": 0x0019,  # Max RFID Code Length
    "min_rfid_len": 0x001A,  # Min RFID Code Length
    "enable_logging": 0x0020,  # Enable Logging
    "language": 0x0021,  # Language
    "led": 0x0022,  # LED
    "auto_relock_time": 0x0023,  # Auto Relock Time
    "sound_volume": 0x0024,  # Sound Volume
    "operating_mode": 0x0025,  # Operating Mode
    "supported_operating_modes": 0x0026,  # Supported Operating Modes
    "default_configuration_register": 0x0027,  # Default Configuration Register
    "enable_local_programming": 0x0028,  # Enable Local Programming
    "enable_one_touch_locking": 0x0029,  # Enable One Touch Locking
    "enable_inside_status_led": 0x002A,  # Enable Inside Status LED
    "enable_privacy_mode_button": 0x002B,  # Enable Privacy Mode Button
    "wrong_code_entry_limit": 0x0030,  # Wrong Code Entry Limit
    "user_code_temporary_disable_time": 0x0031,  # User Code Temporary Disable Time
    "send_pin_ota": 0x0032,  # Send PIN Over the Air
    "require_pin_for_rf_operation": 0x0033,  # Require PIN for RF Operation
    "zigbee_security_level": 0x0034,  # Security Level
    "alarm_mask": 0x0040,  # Alarm Mask
    "keypad_operation_event_mask": 0x0041,  # Keypad Operation Event Mask
    "rf_operation_event_mask": 0x0042,  # RF Operation Event Mask
    "manual_operation_event_mask": 0x0043,  # Manual Operation Event Mask
    "rfid_operation_event_mask": 0x0044,  # RFID Operation Event Mask
    "keypad_programming_event_mask": 0x0045,  # Keypad Programming Event Mask
    "rf_programming_event_mask": 0x0046,  # RF Programming Event Mask
    "rfid_programming_event_mask": 0x0047,  # RFID Programming Event Mask
    "pin_used": 0x0101,  # PIN used for specific code
    "rfid_used": 0x0102,  # RFID used for specific code
    "diagnostics": 0x0103,  # Diagnostic information
}

# Power Configuration attributes
POWER_ATTRIBUTES = {
    "mains_voltage": 0x0000,  # MainsVoltage
    "mains_frequency": 0x0001,  # MainsFrequency
    "mains_alarm_mask": 0x0010,  # MainsAlarmMask
    "mains_voltage_min_threshold": 0x0011,  # MainsVoltageMinThreshold
    "mains_voltage_max_threshold": 0x0012,  # MainsVoltageMaxThreshold
    "mains_voltage_dwell_trip_point": 0x0013,  # MainsVoltageDwellTripPoint
    "battery_voltage": 0x0020,  # BatteryVoltage
    "battery_percentage_remaining": 0x0021,  # BatteryPercentageRemaining
    "battery_manufacturer": 0x0030,  # BatteryManufacturer
    "battery_size": 0x0031,  # BatterySize
    "battery_a_h_rating": 0x0032,  # BatteryAHrRating
    "battery_quantity": 0x0033,  # BatteryQuantity
    "battery_rated_voltage": 0x0034,  # BatteryRatedVoltage
    "battery_alarm_mask": 0x0035,  # BatteryAlarmMask
    "battery_voltage_min_threshold": 0x0036,  # BatteryVoltageMinThreshold
    "battery_voltage_threshold_1": 0x0037,  # BatteryVoltageThreshold1
    "battery_voltage_threshold_2": 0x0038,  # BatteryVoltageThreshold2
    "battery_voltage_threshold_3": 0x0039,  # BatteryVoltageThreshold3
    "battery_percentage_min_threshold": 0x003A,  # BatteryPercentageMinThreshold
    "battery_percentage_threshold_1": 0x003B,  # BatteryPercentageThreshold1
    "battery_percentage_threshold_2": 0x003C,  # BatteryPercentageThreshold2
    "battery_percentage_threshold_3": 0x003D,  # BatteryPercentageThreshold3
    "battery_alarm_state": 0x003E,  # BatteryAlarmState
    "battery_low": 0x9000,  # Custom attribute for battery low
}

def get_ieee_no_colons(ieee):
    """Get IEEE address in lowercase without colons.

    Args:
        ieee: IEEE address in any format

    Returns:
        Lowercase IEEE address without colons
    """
    return normalize_ieee(ieee)["no_colons"]

def format_ieee(ieee):
    """Format IEEE address with lowercase and normalized format with colons.

    Args:
        ieee: IEEE address in any format

    Returns:
        Lowercase IEEE address with colons
    """
    return normalize_ieee(ieee)["with_colons"]

def format_ieee_with_colons(ieee):
    """Format IEEE address with colons regardless of input format.
    This is an alias for format_ieee for backward compatibility.
    """
    # Format the IEEE to include colons
    ieee_no_colons = ieee.replace(':', '').lower()
    return ':'.join([ieee_no_colons[i:i+2] for i in range(0, len(ieee_no_colons), 2)])

# Add mapping for different ZHA gateway implementations
def get_cluster_handler_name(gateway_type="zha"):
    """Get the appropriate cluster handler name based on gateway type."""
    if gateway_type == "zigbee":
        return "zigbee_cluster_handler"  # For Nabu Casa Zigbee integration
    else:
        return "zha_cluster_handler"  # For standard ZHA

# Zigbee profile ID used by ZBT-1 devices
COMMAND_PROFILE = 0x0104  # Home Automation profile

# Safe4 ZigBee Door Lock specific constants
ZBT1_ENDPOINTS = [11]  # Safe4 spec requires endpoint 11 only

# Safe4 ZigBee Door Lock command constants per specification
SAFE4_LOCK_COMMAND = 0x00
SAFE4_UNLOCK_COMMAND = 0x01