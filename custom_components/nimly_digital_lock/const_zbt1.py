"""ZBT1 specific constants for Nimly Digital Lock."""

# ZBT1 Endpoints
ZBT1_ENDPOINTS = [11, 1, 242, 2, 3]

# Lock Command IDs
ZBT1_LOCK_COMMAND = 0x00
ZBT1_UNLOCK_COMMAND = 0x01

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
