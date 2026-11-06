"""Pure rules for slots, PIN codes, lock events and log masking.

No Home Assistant imports, so the logic can be tested on its own.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, time, timedelta
import re
import secrets

from .const import (
    CREDENTIAL_SOURCES,
    DEFAULT_RESERVED_SLOTS,
    MAX_NAME_LENGTH,
    MAX_SLOT,
    PIN_LENGTH_FALLBACK,
    PIN_LENGTH_SANE,
    RESERVED_SLOTS_MAX,
    RESERVED_SLOTS_MIN,
    LockAction,
    LockSource,
)

_SOURCE_MAP: dict[int, LockSource] = {
    0x00: LockSource.ZIGBEE,
    0x01: LockSource.BUTTON,
    0x02: LockSource.KEYPAD,
    0x03: LockSource.FINGERPRINT,
    0x04: LockSource.RFID,
    0x05: LockSource.UNATTRIBUTED,
    0x0A: LockSource.AUTO,
}

_ACTION_MAP: dict[int, LockAction] = {
    0x01: LockAction.LOCK,
    0x02: LockAction.UNLOCK,
}

# Codes and key tags share one slot numbering, fingerprints have their own
# (000-199), so fingerprint 5 and code 5 may be different people.
_CREDENTIAL_KIND: dict[LockSource, str] = {
    LockSource.KEYPAD: "pin",
    LockSource.RFID: "rfid",
    LockSource.FINGERPRINT: "fingerprint",
}
CREDENTIAL_KINDS = tuple(_CREDENTIAL_KIND.values())

_DIGIT_RUN = re.compile(rf"\d{{{PIN_LENGTH_SANE[0]},}}")


@dataclass(frozen=True, slots=True)
class LockEvent:
    """One decoded Event Status (0x0100) report."""

    action: LockAction
    source: LockSource
    slot: int | None
    raw: int

    @property
    def by_credential(self) -> bool:
        """Whether a person's code, tag or finger operated the lock."""
        return self.source in CREDENTIAL_SOURCES

    @property
    def credits_user(self) -> bool:
        """Whether the slot names who did it.

        Locking from the outside with a palm or # needs no code, and is
        likely reported as keypad on slot 0; that is not the master user.
        """
        if not self.by_credential or self.slot is None:
            return False
        return not (
            self.action is LockAction.LOCK and self.source is LockSource.KEYPAD and self.slot == 0
        )

    @property
    def credential(self) -> str | None:
        """The credential kind, for names kept per kind: pin, rfid or fingerprint."""
        return _CREDENTIAL_KIND.get(self.source)


def decode_event_status(value: int) -> LockEvent | None:
    """Decode the 32-bit Event Status bitmap.

    Layout (Safe4 specification): bits 0-15 user slot, bits 16-23 the
    event (1 locked, 2 unlocked), bits 24-31 the method.
    """
    if not 0 <= value <= 0xFFFFFFFF:
        return None
    slot = value & 0xFFFF
    action = _ACTION_MAP.get((value >> 16) & 0xFF, LockAction.UNKNOWN)
    source = _SOURCE_MAP.get((value >> 24) & 0xFF, LockSource.UNKNOWN)
    if source is LockSource.AUTO and action is LockAction.UNLOCK:
        # Auto relock cannot unlock: 0x0A has been seen on unlocks too and
        # then only means "nobody to attribute this to".
        source = LockSource.UNATTRIBUTED
    # Slot 0 is the master code, so it only names someone when a
    # credential was used; a Zigbee or auto lock reports 0 for "nobody".
    if slot == 0 and source not in CREDENTIAL_SOURCES:
        return LockEvent(action, source, None, value)
    return LockEvent(action, source, slot, value)


def is_system_event(event: LockEvent, wake_echo_pending: bool = False) -> bool:
    """Whether an event is the lock acting on its own, not a person.

    Auto relock, an unattributed lock with no slot (how some models
    report auto relock), and the echo of a wake-up lock this integration
    sent itself.
    """
    anonymous_lock = event.action is LockAction.LOCK and event.slot is None
    if event.source is LockSource.AUTO:
        return True
    if event.source is LockSource.UNATTRIBUTED:
        return anonymous_lock
    if event.source is LockSource.ZIGBEE:
        return anonymous_lock and wake_echo_pending
    return False


def first_user_slot(reserved_slots: object) -> int:
    """Lowest slot Home Assistant may write, from the reserved-slot option."""
    if isinstance(reserved_slots, bool) or not isinstance(reserved_slots, int | float):
        return DEFAULT_RESERVED_SLOTS
    return max(RESERVED_SLOTS_MIN, min(RESERVED_SLOTS_MAX, int(reserved_slots)))


def max_user_slot(capabilities: Mapping[str, int]) -> int:
    """Highest slot to accept: from NumberOfPINUsersSupported when sane."""
    num = capabilities.get("num_pin_users")
    if isinstance(num, int) and RESERVED_SLOTS_MAX < num <= MAX_SLOT + 1:
        return num - 1
    return MAX_SLOT


def _sane_length(value: object) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int):
        return None
    if not PIN_LENGTH_SANE[0] <= value <= PIN_LENGTH_SANE[1]:
        return None
    return value


def pin_length_range(capabilities: Mapping[str, int]) -> tuple[int, int]:
    """Shortest and longest PIN the lock accepts."""
    low = _sane_length(capabilities.get("min_pin_length")) or PIN_LENGTH_FALLBACK[0]
    high = _sane_length(capabilities.get("max_pin_length")) or PIN_LENGTH_FALLBACK[1]
    if low > high:
        return PIN_LENGTH_FALLBACK
    return low, high


def is_valid_pin(code: str, capabilities: Mapping[str, int]) -> bool:
    """Whether code is ASCII digits within the lock's length range."""
    low, high = pin_length_range(capabilities)
    return code.isascii() and code.isdigit() and low <= len(code) <= high


@dataclass(frozen=True, slots=True)
class ParentLink:
    """The router the lock talks through (attribute 0x0103)."""

    nwk: int
    rssi_dbm: int


def decode_diagnostics(value: int) -> ParentLink | None:
    """Decode 0x0103: bits 0-15 parent NWK, 16-23 RSSI, 24-31 RSSI in dBm (signed)."""
    if not 0 < value <= 0xFFFFFFFF:
        return None
    dbm = (value >> 24) & 0xFF
    return ParentLink(nwk=value & 0xFFFF, rssi_dbm=dbm - 256 if dbm > 127 else dbm)


def next_window(
    now: datetime, days: frozenset[int], start: time, end: time
) -> tuple[datetime, datetime] | None:
    """The weekly window that contains now, else the next one.

    now is aware and in the local time zone; days are weekdays (Monday 0).
    A window whose end is not after its start runs past midnight, and
    belongs to the day it starts on.
    """
    if not days:
        return None
    zone = now.tzinfo
    for offset in range(-1, 8):
        day = now.date() + timedelta(days=offset)
        if day.weekday() not in days:
            continue
        begins = datetime.combine(day, start, tzinfo=zone)
        end_day = day if end > start else day + timedelta(days=1)
        ends = datetime.combine(end_day, end, tzinfo=zone)
        if ends > now:
            return begins, ends
    return None


def generate_pin(capabilities: Mapping[str, int], length: int | None = None) -> str:
    """A random PIN the lock accepts, avoiding the codes people guess first."""
    low, high = pin_length_range(capabilities)
    size = max(low, min(high, length or max(low, 6)))
    while True:
        code = "".join(secrets.choice("0123456789") for _ in range(size))
        if not _guessable(code):
            return code


def _guessable(code: str) -> bool:
    """All one digit, or a straight run up or down (1234, 9876)."""
    if len(set(code)) == 1:
        return True
    steps = {(int(b) - int(a)) % 10 for a, b in zip(code, code[1:], strict=False)}
    return steps in ({1}, {9})


def clean_name(name: object) -> str:
    """A slot name as stored: text, trimmed, at most MAX_NAME_LENGTH characters."""
    return str(name).strip()[:MAX_NAME_LENGTH]


def redact_digits(text: object) -> str:
    """Mask every run of digits long enough to be a PIN code."""
    return _DIGIT_RUN.sub("****", str(text))
