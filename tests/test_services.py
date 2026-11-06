"""Tests for the PIN and slot actions."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from zigpy.exceptions import DeliveryError, ZigbeeException
from zigpy.zcl.foundation import Status

from custom_components.nimly_digital_lock.const import DOMAIN, NimlyService
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError

from .conftest import FakeZha


async def _call(hass: HomeAssistant, entry: MockConfigEntry, service: str, **data) -> None:
    await hass.services.async_call(
        DOMAIN, service, {"config_entry_id": entry.entry_id, **data}, blocking=True
    )


async def test_set_pin(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    await _call(hass, init_integration, NimlyService.SET_PIN, slot=4, pin_code="2468", name="Bo")
    fake_zha.cluster.command.assert_awaited_once_with(
        0x05, user_id=4, user_status=1, user_type=0, pin_code="2468"
    )
    assert init_integration.runtime_data.slots == {
        4: {"name": "Bo", "has_pin": True, "expires": None}
    }
    assert hass.states.get("sensor.nimlypro_activity_pin_codes").state == "1"


@pytest.mark.parametrize(
    ("data", "key"),
    [
        ({"slot": 0, "pin_code": "1234"}, "slot_out_of_range"),
        ({"slot": 2, "pin_code": "1234"}, "slot_out_of_range"),
        ({"slot": 49, "pin_code": "123"}, "invalid_pin"),
        ({"slot": 50, "pin_code": "1234"}, "slot_out_of_range"),  # lock reports 50 users
        ({"slot": 5, "pin_code": "12ab"}, "invalid_pin"),
    ],
)
async def test_set_pin_validation(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry, data, key
) -> None:
    with pytest.raises(ServiceValidationError) as err:
        await _call(hass, init_integration, NimlyService.SET_PIN, **data)
    assert err.value.translation_key == key
    fake_zha.cluster.command.assert_not_awaited()


@pytest.mark.parametrize(
    ("side_effect", "return_value", "key", "attempts"),
    [
        (TimeoutError, None, "lock_unreachable", 3),
        (DeliveryError("no ack"), None, "lock_unreachable", 3),
        (ZigbeeException("pin 123456 failed"), None, "lock_unreachable", 1),
        (None, SimpleNamespace(status=Status.FAILURE), "lock_rejected", 1),
        (None, SimpleNamespace(status=3), "lock_rejected_duplicate", 1),
        (None, SimpleNamespace(status=2), "lock_rejected_memory_full", 1),
        (None, SimpleNamespace(status=3, command_id=5), "lock_rejected", 1),
    ],
)
async def test_set_pin_failures(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
    caplog,
    side_effect,
    return_value,
    key,
    attempts,
) -> None:
    fake_zha.cluster.command = AsyncMock(side_effect=side_effect, return_value=return_value)
    with pytest.raises(HomeAssistantError) as err:
        await _call(hass, init_integration, NimlyService.SET_PIN, slot=4, pin_code="123456")
    assert err.value.translation_key == key
    assert fake_zha.cluster.command.await_count == attempts
    assert init_integration.runtime_data.slots == {}
    assert "123456" not in caplog.text


async def test_set_pin_retry_succeeds(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    fake_zha.cluster.command = AsyncMock(side_effect=[TimeoutError, None])
    await _call(hass, init_integration, NimlyService.SET_PIN, slot=4, pin_code="1234")
    assert fake_zha.cluster.command.await_count == 2
    assert init_integration.runtime_data.slots[4]["has_pin"] is True


async def test_index_error_counts_as_delivered(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    fake_zha.cluster.command = AsyncMock(side_effect=IndexError("tuple index out of range"))
    await _call(hass, init_integration, NimlyService.SET_PIN, slot=4, pin_code="1234")
    assert init_integration.runtime_data.slots[4]["has_pin"] is True


async def test_clear_pin_keeps_name(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    await _call(hass, init_integration, NimlyService.SET_PIN, slot=4, pin_code="1234", name="Bo")
    await _call(hass, init_integration, NimlyService.CLEAR_PIN, slot=4)
    fake_zha.cluster.command.assert_awaited_with(0x07, user_id=4)
    assert init_integration.runtime_data.slots == {
        4: {"name": "Bo", "has_pin": False, "expires": None}
    }


async def test_set_slot_name(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    await _call(hass, init_integration, NimlyService.SET_SLOT_NAME, slot=150, name="Anna finger")
    assert init_integration.runtime_data.slot_name(150) == "Anna finger"
    await _call(hass, init_integration, NimlyService.SET_SLOT_NAME, slot=150, name="")
    assert init_integration.runtime_data.slots == {}
    with pytest.raises(ServiceValidationError):
        await _call(hass, init_integration, NimlyService.SET_SLOT_NAME, slot=1000, name="x")


async def test_unknown_entry(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            NimlyService.CLEAR_PIN,
            {"config_entry_id": "nope", "slot": 4},
            blocking=True,
        )
    assert err.value.translation_key == "entry_not_found"


async def test_slots_persist_across_reload(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    await _call(hass, init_integration, NimlyService.SET_PIN, slot=4, pin_code="1234", name="Bo")
    await hass.config_entries.async_reload(init_integration.entry_id)
    await hass.async_block_till_done()
    manager = init_integration.runtime_data
    assert manager.slots == {4: {"name": "Bo", "has_pin": True, "expires": None}}
    assert manager.capabilities_read is True


async def test_clear_pin_above_reported_capacity(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    """A code written before the capacity was known can still be cleared."""
    await _call(hass, init_integration, NimlyService.CLEAR_PIN, slot=120)
    fake_zha.cluster.command.assert_awaited_once_with(0x07, user_id=120)


async def test_unexpected_error_is_contained(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry, caplog
) -> None:
    fake_zha.cluster.command = AsyncMock(side_effect=ValueError("bad pin_code 864209"))
    with pytest.raises(HomeAssistantError) as err:
        await _call(hass, init_integration, NimlyService.SET_PIN, slot=4, pin_code="864209")
    assert err.value.translation_key == "lock_unreachable"
    assert "864209" not in caplog.text
