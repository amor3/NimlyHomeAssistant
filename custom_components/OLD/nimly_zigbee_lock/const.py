DOMAIN = "nimly_zigbee_lock"

ENDPOINT_ID = 11
LOCK_CLUSTER_ID = 0x0101
POWER_CLUSTER_ID = 0x0001

ATTRIBUTE_MAP = {
    "battery_voltage": (POWER_CLUSTER_ID, 0x0020),
    "battery_percent_remaining": (POWER_CLUSTER_ID, 0x0021),
    "battery_low": (POWER_CLUSTER_ID, 0x9000),
    "lock_state": (LOCK_CLUSTER_ID, 0x0000),
    "lock_type": (LOCK_CLUSTER_ID, 0x0001),
    "actuator_enabled": (LOCK_CLUSTER_ID, 0x0002),
    "door_state": (LOCK_CLUSTER_ID, 0x0003),
    "total_users": (LOCK_CLUSTER_ID, 0x0011),
    "pin_users": (LOCK_CLUSTER_ID, 0x0012),
    "rfid_users": (LOCK_CLUSTER_ID, 0x0013),
    "max_pin_length": (LOCK_CLUSTER_ID, 0x0017),
    "min_pin_length": (LOCK_CLUSTER_ID, 0x0018),
    "max_rfid_length": (LOCK_CLUSTER_ID, 0x0019),
    "min_rfid_length": (LOCK_CLUSTER_ID, 0x001A),
    "auto_relock_time": (LOCK_CLUSTER_ID, 0x0023),
    "sound_volume": (LOCK_CLUSTER_ID, 0x0024),
    "pin_used": (LOCK_CLUSTER_ID, 0x0101),
    "rfid_used": (LOCK_CLUSTER_ID, 0x0102),
    "event_status": (LOCK_CLUSTER_ID, 0x0100),
    "diagnostics_data": (LOCK_CLUSTER_ID, 0x0103),
}

COMMAND_LOCK = 0x00
COMMAND_UNLOCK = 0x01
COMMAND_SET_PIN = 0x05
COMMAND_CLEAR_PIN = 0x07
COMMAND_CLEAR_RFID = 0x18
COMMAND_SCAN_RFID = 0x70
COMMAND_SCAN_FINGERPRINT = 0x71
COMMAND_CLEAR_FINGERPRINT = 0x72
COMMAND_LOCAL_PROG_DISABLE = 0x73
COMMAND_LOCAL_PROG_ENABLE = 0x74

SERVICE_SET_PIN = "set_pin_code"
SERVICE_CLEAR_PIN = "clear_pin_code"
SERVICE_SET_RFID = "set_rfid_code"
SERVICE_CLEAR_RFID = "clear_rfid_code"
SERVICE_SCAN_RFID = "scan_rfid"
SERVICE_SCAN_FINGERPRINT = "scan_fingerprint"
SERVICE_CLEAR_FINGERPRINT = "clear_fingerprint"
SERVICE_LOCAL_PROG_DISABLE = "local_program_disable"
SERVICE_LOCAL_PROG_ENABLE = "local_program_enable"

ATTR_SLOT = "slot"
ATTR_PIN = "pin"
ATTR_RFID = "rfid"
ATTR_IEEE = "ieee"
