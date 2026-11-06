"""Constants for the Nimly Digital Lock integration."""

from __future__ import annotations

from enum import StrEnum
from typing import Final

DOMAIN: Final = "nimly_digital_lock"
ZHA_DOMAIN: Final = "zha"

# Every Nimly/EasyAccess lock with the Zigbee module reports this manufacturer.
MANUFACTURER: Final = "Onesti Products AS"

# Model identifiers from the Safe4 Zigbee module specification and the field.
SUPPORTED_MODELS: Final = (
    "NimlyCode",
    "NimlyCodePRO",
    "NimlyTouch",
    "NimlyPRO",
    "NimlyPRO24",
    "NimlyIn",
    "NimlyShared",
    "NimlyKeybox",
    "NimlyTwist",
    "EasyFingerTouch",
    "EasyCodeTouch",
    "easyCodeTouch_v1",
)

CONF_IEEE: Final = "ieee"
CONF_MODEL: Final = "model"
CONF_RESERVED_SLOTS: Final = "reserved_slots"
CONF_WAKE_WITH_LOCK: Final = "wake_with_lock"

DOOR_LOCK_CLUSTER_ID: Final = 0x0101
LOCK_ENDPOINT_ID: Final = 11

# Door Lock cluster attributes (Safe4 Zigbee module specification).
ATTR_ID_NUM_PIN_USERS: Final = 0x0012
ATTR_ID_MAX_PIN_LENGTH: Final = 0x0017
ATTR_ID_MIN_PIN_LENGTH: Final = 0x0018
ATTR_ID_EVENT_STATUS: Final = 0x0100
# 0x0101 "PIN Used" carries the last typed PIN code in clear text. It is
# never read and its reports are dropped.
ATTR_ID_PIN_USED: Final = 0x0101

# Door Lock cluster server commands.
CMD_SET_PIN: Final = 0x05
CMD_CLEAR_PIN: Final = 0x07

# Slot layout: slot 0 is the master code on every model, and the Safe4
# specification reserves the first slots for master codes. User slots start
# after the reserved ones; Home Assistant never writes a PIN below that.
MAX_SLOT: Final = 999
RESERVED_SLOTS_MIN: Final = 1
RESERVED_SLOTS_MAX: Final = 3
DEFAULT_RESERVED_SLOTS: Final = 3

PIN_LENGTH_FALLBACK: Final = (4, 8)
PIN_LENGTH_SANE: Final = (4, 20)

# Retries for a command that times out on a sleeping lock.
SEND_ATTEMPTS: Final = 3
SEND_RETRY_DELAY_S: Final = 2.0
WAKE_ECHO_WINDOW_S: Final = 30.0

EVENT_LOCK_ACTIVITY: Final = f"{DOMAIN}_activity"

ISSUE_ZHA_INTERNALS: Final = "zha_internals"
ISSUE_QUIRK_MISSING: Final = "quirk_missing"
ISSUE_EXPIRED_PIN: Final = "expired_pin_not_cleared"

STORAGE_VERSION: Final = 1


class LockAction(StrEnum):
    """What the lock did."""

    LOCK = "lock"
    UNLOCK = "unlock"
    UNKNOWN = "unknown"


class LockSource(StrEnum):
    """How the lock was operated, from the top byte of attribute 0x0100."""

    ZIGBEE = "zigbee"
    BUTTON = "button"
    KEYPAD = "keypad"
    FINGERPRINT = "fingerprint"
    RFID = "rfid"
    UNATTRIBUTED = "unattributed"
    AUTO = "auto"
    UNKNOWN = "unknown"


# Credentials tied to a user slot; only these name a person.
CREDENTIAL_SOURCES: Final = frozenset({LockSource.KEYPAD, LockSource.FINGERPRINT, LockSource.RFID})


class NimlyService(StrEnum):
    """Actions registered by the integration."""

    SET_PIN = "set_pin"
    CLEAR_PIN = "clear_pin"
    SET_SLOT_NAME = "set_slot_name"


class NimlyServiceArgument(StrEnum):
    """Fields of the registered actions."""

    CONFIG_ENTRY_ID = "config_entry_id"
    SLOT = "slot"
    PIN_CODE = "pin_code"
    NAME = "name"
    VALID_UNTIL = "valid_until"
    VALID_FOR = "valid_for"
