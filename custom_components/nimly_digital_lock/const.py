import voluptuous as vol

DOMAIN = "nimly_digital_lock"
# Standard ZigBee Cluster IDs
LOCK_CLUSTER_ID = 0x0101  # Door Lock cluster
POWER_CLUSTER_ID = 0x0001  # Power Configuration cluster
# We'll discover the correct endpoint ID during device initialization
ENDPOINT_ID = None  # This will be discovered per device

PLATFORMS = ["lock", "sensor", "select", "switch"]

COMMON_ENDPOINTS = [11, 1, 242, 2, 3]

SERVICE_UPDATE = "update"
SERVICE_EXPORT = "export"

SERVICE_SCHEMAS = {
    SERVICE_UPDATE: vol.Schema({}),
    SERVICE_EXPORT: vol.Schema({
        vol.Optional("path"): str,
    })
}
# Attribute map for sensors and other status info
ATTRIBUTE_MAP = [
    'battery',
    'battery_voltage',
    'battery_low',
    'door_state',
    'lock_state',
    'actuator_enabled',
    'auto_relock_time',
    'sound_volume',
    'total_users',
    'pin_users',
    'rfid_users'
]

# Mapping of attributes to cluster ID and attribute ID
ATTRIBUTE_CLUSTER_MAPPING = {
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
    "lock_state": (LOCK_CLUSTER_ID, 0x0000),
}
