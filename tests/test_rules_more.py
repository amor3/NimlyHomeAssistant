"""Pure rules added for schedules, generated codes, names and diagnostics."""

from __future__ import annotations

from datetime import datetime, time
from zoneinfo import ZoneInfo

import pytest

from custom_components.nimly_digital_lock.rules import (
    clean_name,
    decode_diagnostics,
    generate_pin,
    next_window,
)

STOCKHOLM = ZoneInfo("Europe/Stockholm")
MON, TUE, THU, SUN = 0, 1, 3, 6


def _at(*args: int) -> datetime:
    return datetime(*args, tzinfo=STOCKHOLM)


def test_window_later_today_and_current() -> None:
    days = frozenset({MON, THU})
    monday_early = _at(2026, 11, 9, 7, 0)  # a Monday
    assert next_window(monday_early, days, time(8), time(16)) == (
        _at(2026, 11, 9, 8, 0),
        _at(2026, 11, 9, 16, 0),
    )
    monday_noon = _at(2026, 11, 9, 12, 0)
    assert next_window(monday_noon, days, time(8), time(16))[0] == _at(2026, 11, 9, 8, 0)
    monday_evening = _at(2026, 11, 9, 17, 0)
    assert next_window(monday_evening, days, time(8), time(16))[0] == _at(2026, 11, 12, 8, 0)


def test_window_across_midnight() -> None:
    """22:00-06:00 on Sundays belongs to Sunday and runs into Monday."""
    days = frozenset({SUN})
    monday_night = _at(2026, 11, 9, 2, 0)
    assert next_window(monday_night, days, time(22), time(6)) == (
        _at(2026, 11, 8, 22, 0),
        _at(2026, 11, 9, 6, 0),
    )


def test_window_over_daylight_saving_change() -> None:
    """Local wall-clock times hold on the day summer time ends."""
    begins, ends = next_window(_at(2026, 10, 25, 0, 0), frozenset({SUN}), time(8), time(16))
    assert (begins.hour, ends.hour) == (8, 16)
    assert (ends - begins).total_seconds() == 8 * 3600


def test_no_days_no_window() -> None:
    assert next_window(_at(2026, 11, 9, 7), frozenset(), time(8), time(16)) is None


@pytest.mark.parametrize("caps", [{}, {"min_pin_length": 4, "max_pin_length": 8}])
def test_generated_pin(caps: dict[str, int]) -> None:
    for _ in range(200):
        code = generate_pin(caps)
        assert code.isdigit() and len(code) == 6
        assert len(set(code)) > 1
        assert code not in ("123456", "654321", "234567", "987654")
    assert len(generate_pin({"min_pin_length": 8, "max_pin_length": 8})) == 8


def test_clean_name() -> None:
    assert clean_name("  Anna  ") == "Anna"
    assert len(clean_name("x" * 200)) == 64


def test_decode_diagnostics() -> None:
    link = decode_diagnostics(0xC5A01234)  # NWK 0x1234, RSSI 0xA0, -59 dBm
    assert link is not None
    assert (link.nwk, link.rssi_dbm) == (0x1234, -59)
    assert decode_diagnostics(0) is None
