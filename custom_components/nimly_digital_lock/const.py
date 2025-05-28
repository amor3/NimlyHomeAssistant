"""Constants for the Nimly Digital Lock integration."""

DOMAIN = "nimly_digital_lock"
LOCK_CLUSTER_ID = 0x0101
POWER_CLUSTER_ID = 0x0001
ENDPOINT_ID = 11

ATTRIBUTE_MAP = {
    "battery": (POWER_CLUSTER_ID, 0x0021),
    "battery_voltage": (POWER_CLUSTER_ID, 0x0020),
    "battery_low": (POWER_CLUSTER_ID, 0x9000),
    "diagnostics": (LOCK_CLUSTER_ID, 0x0103),
    "auto_relock_time": (LOCK_CLUSTER_ID, 0x0023),
    "sound_volume": (LOCK_CLUSTER_ID, 0x0024),
    "total_users": (LOCK_CLUSTER_ID, 0x0011),
    "pin_users": (LOCK_CLUSTER_ID, 0x0012),
    "rfid_users": (LOCK_CLUSTER_ID, 0x0013),
    "max_pin_length": (LOCK_CLUSTER_ID, 0x0017),
    "min_pin_length": (LOCK_CLUSTER_ID, 0x0018),
    "max_rfid_length": (LOCK_CLUSTER_ID, 0x0019),
    "min_rfid_length": (LOCK_CLUSTER_ID, 0x001A),
    "pin_used": (LOCK_CLUSTER_ID, 0x0101),
    "rfid_used": (LOCK_CLUSTER_ID, 0x0102),
    "lock_type": (LOCK_CLUSTER_ID, 0x0001),
    "actuator_enabled": (LOCK_CLUSTER_ID, 0x0002),
    "door_state": (LOCK_CLUSTER_ID, 0x0003),
}
