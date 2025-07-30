"""ZBT1 specific constants for Nimly Digital Lock."""

# ZBT1 Endpoints
ZBT1_ENDPOINTS = [11, 1, 242, 2, 3]

# Lock Command IDs
ZBT1_LOCK_COMMAND = 0x00
ZBT1_UNLOCK_COMMAND = 0x01

# PIN Code related constants
ZBT1_SET_PIN_CODE = 0x05      # Set PIN Code
ZBT1_CLEAR_PIN_CODE = 0x07    # Clear PIN Code
ZBT1_CLEAR_ALL_PIN_CODES = 0x08  # Clear All PIN Codes

# RFID and other advanced commands
ZBT1_CLEAR_RFID_CODE = 0x18 # Clear RFID Code
ZBT1_SCAN_RFID_CODE = 0x70  # Scan RFID Code (Custom)
ZBT1_SCAN_FINGERPRINT = 0x71 # Scan Fingerprint (Custom)
ZBT1_CLEAR_FINGERPRINT = 0x72 # Clear Fingerprint (Custom)
ZBT1_LOCAL_PROGRAMMING_DISABLE = 0x73 # Local Programming Disable (Custom)
ZBT1_LOCAL_PROGRAMMING_ENABLE = 0x74  # Local Programming Enable (Custom)

# Cluster IDs
SAFE4_DOOR_LOCK_CLUSTER = 0x0101
SAFE4_POWER_CLUSTER = 0x0001

# Lock and Unlock Commands
SAFE4_LOCK_COMMAND = 0x00
SAFE4_UNLOCK_COMMAND = 0x01

# Nordic ZBT-1 specific endpoint
SAFE4_ZBT1_ENDPOINT = 11

# Door Lock Profile
SAFE4_DOOR_LOCK_PROFILE = 0x0104
COMMAND_PROFILE = 0x0104

# Server command type
COMMAND_TYPE = "server"
