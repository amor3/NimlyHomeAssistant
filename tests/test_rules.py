"""Tests for the pure rules: event decoding, slots, PINs and masking."""

from __future__ import annotations

import pytest

from custom_components.nimly_digital_lock.const import LockAction, LockSource
from custom_components.nimly_digital_lock.rules import (
    decode_event_status,
    first_user_slot,
    is_system_event,
    is_valid_pin,
    max_user_slot,
    pin_length_range,
    redact_digits,
)


@pytest.mark.parametrize(
    ("raw", "action", "source", "slot"),
    [
        (0x02020005, LockAction.UNLOCK, LockSource.KEYPAD, 5),
        (0x03020096, LockAction.UNLOCK, LockSource.FINGERPRINT, 150),
        (0x04010384, LockAction.LOCK, LockSource.RFID, 900),
        (0x00010000, LockAction.LOCK, LockSource.ZIGBEE, None),
        (0x0A010000, LockAction.LOCK, LockSource.AUTO, None),
        (0x02020000, LockAction.UNLOCK, LockSource.KEYPAD, 0),
        (0x01020000, LockAction.UNLOCK, LockSource.BUTTON, None),
        (0x7F090001, LockAction.UNKNOWN, LockSource.UNKNOWN, 1),
    ],
)
def test_decode_event_status(
    raw: int, action: LockAction, source: LockSource, slot: int | None
) -> None:
    event = decode_event_status(raw)
    assert event is not None
    assert (event.action, event.source, event.slot) == (action, source, slot)


def test_decode_rejects_out_of_range() -> None:
    assert decode_event_status(-1) is None
    assert decode_event_status(0x1_0000_0000) is None


def test_system_events() -> None:
    auto = decode_event_status(0x0A010000)
    remote_lock = decode_event_status(0x00010000)
    unattributed_lock = decode_event_status(0x05010000)
    unattributed_unlock = decode_event_status(0x05020000)
    keypad = decode_event_status(0x02020005)
    assert auto and is_system_event(auto)
    assert unattributed_lock and is_system_event(unattributed_lock)
    assert unattributed_unlock and not is_system_event(unattributed_unlock)
    assert remote_lock and not is_system_event(remote_lock)
    assert is_system_event(remote_lock, wake_echo_pending=True)
    assert keypad and not is_system_event(keypad, wake_echo_pending=True)


@pytest.mark.parametrize(
    ("value", "expected"),
    [(None, 3), (1, 1), (2, 2), (3, 3), (0, 1), (9, 3), (2.0, 2), (True, 3), ("2", 3)],
)
def test_first_user_slot(value: object, expected: int) -> None:
    assert first_user_slot(value) == expected


def test_max_user_slot() -> None:
    assert max_user_slot({"num_pin_users": 50}) == 49
    assert max_user_slot({}) == 999
    assert max_user_slot({"num_pin_users": 0}) == 999
    assert max_user_slot({"num_pin_users": 5000}) == 999


def test_pin_rules() -> None:
    assert pin_length_range({}) == (4, 8)
    assert pin_length_range({"min_pin_length": 6, "max_pin_length": 6}) == (6, 6)
    assert pin_length_range({"min_pin_length": 2}) == (4, 8)
    assert pin_length_range({"min_pin_length": 9, "max_pin_length": 5}) == (4, 8)
    assert is_valid_pin("1234", {})
    assert not is_valid_pin("123", {})
    assert not is_valid_pin("123456789", {})
    assert not is_valid_pin("12a4", {})
    assert not is_valid_pin("١٢٣٤", {})  # non-ASCII digits


def test_redact_digits() -> None:
    assert redact_digits("pin_code=123456 slot 3") == "pin_code=**** slot 3"
    assert redact_digits(ValueError("code 9876")) == "code ****"


def test_auto_source_on_unlock_is_unattributed() -> None:
    """Auto relock cannot unlock; 0x0A on an unlock means nobody known."""
    event = decode_event_status(0x0A020000)
    assert event is not None
    assert event.source is LockSource.UNATTRIBUTED
    assert not is_system_event(event)


def test_credits_user() -> None:
    palm_lock = decode_event_status(0x02010000)
    master_unlock = decode_event_status(0x02020000)
    finger_lock = decode_event_status(0x03010001)
    assert palm_lock and not palm_lock.credits_user
    assert master_unlock and master_unlock.credits_user
    assert finger_lock and finger_lock.credits_user
    assert finger_lock.credential == "fingerprint"
