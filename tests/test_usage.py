"""Codes with a limited number of uses, and unlock counts per person."""

from __future__ import annotations

from datetime import timedelta
from typing import Any
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockUser,
    async_mock_service,
)

from custom_components.nimly_digital_lock.const import DOMAIN, NimlyService
from homeassistant.core import Context, HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import issue_registry as ir

from .conftest import FakeZha
from .test_attribution import zha_lock_setup  # noqa: F401

UNLOCKS = "sensor.nimlypro_activity_unlocks"
PIN_CODES = "sensor.nimlypro_activity_pin_codes"


def _keypad_unlock(slot: int) -> int:
    return 0x02020000 | slot


def _calls(fake_zha: FakeZha) -> list[tuple[Any, ...]]:
    return [(c.args[0], c.kwargs.get("user_id")) for c in fake_zha.cluster.command.await_args_list]


async def _set(hass: HomeAssistant, **data: Any) -> None:
    await hass.services.async_call(DOMAIN, NimlyService.SET_PIN, data, blocking=True)


async def _report(hass: HomeAssistant, fake_zha: FakeZha, value: int) -> None:
    fake_zha.cluster.report(0x0100, value)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_one_time_code(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    await _set(hass, slot=5, pin_code="2580", name="Courier", max_uses=1)
    manager = init_integration.runtime_data
    assert manager.uses_left(5) == 1
    assert hass.states.get(PIN_CODES).attributes["slots"]["5"]["uses_left"] == 1

    await _report(hass, fake_zha, _keypad_unlock(5))
    assert _calls(fake_zha)[-1] == (0x07, 5)
    assert manager.slots[5]["has_pin"] is False
    assert manager.uses_left(5) is None
    # The name and the count stay for the record.
    assert manager.slot_name(5) == "Courier"
    assert hass.states.get(UNLOCKS).attributes["by_user"] == {"Courier": 1}


async def test_limited_code_counts_only_its_own_unlocks(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    await _set(hass, slot=5, pin_code="2580", max_uses=2)
    manager = init_integration.runtime_data
    await _report(hass, fake_zha, 0x04020005)  # key tag in slot 5: not the code
    await _report(hass, fake_zha, 0x02010005)  # locking with the code: not an unlock
    await _report(hass, fake_zha, _keypad_unlock(6))  # another slot
    assert manager.uses_left(5) == 2
    await _report(hass, fake_zha, _keypad_unlock(5))
    assert manager.uses_left(5) == 1
    assert (0x07, 5) not in _calls(fake_zha)
    await _report(hass, fake_zha, _keypad_unlock(5))
    assert _calls(fake_zha)[-1] == (0x07, 5)


async def test_new_code_without_limit_drops_the_limit(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    await _set(hass, slot=5, pin_code="2580", max_uses=1)
    await _set(hass, slot=5, pin_code="2581")
    await _report(hass, fake_zha, _keypad_unlock(5))
    assert init_integration.runtime_data.slots[5]["has_pin"] is True
    assert (0x07, 5) not in _calls(fake_zha)


async def test_used_up_code_retried_and_repaired(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    await _set(hass, slot=5, pin_code="2580", max_uses=1)
    fake_zha.cluster.command = AsyncMock(side_effect=TimeoutError)
    await _report(hass, fake_zha, _keypad_unlock(5))
    manager = init_integration.runtime_data
    assert manager.slots[5]["has_pin"] is True
    assert manager.uses_left(5) == 0
    # A further unlock with it is counted but starts no second clear.
    calls = fake_zha.cluster.command.await_count
    await _report(hass, fake_zha, _keypad_unlock(5))
    assert fake_zha.cluster.command.await_count == calls
    assert manager.usage["pin:5"]["count"] == 2
    assert (
        ir.async_get(hass).async_get_issue(
            DOMAIN, f"expired_pin_not_cleared_{init_integration.entry_id}_5"
        )
        is None
    )


async def test_used_up_code_cleared_after_restart(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    mock_zha_setup: None,
    mock_config_entry: MockConfigEntry,
    hass_storage: dict[str, Any],
) -> None:
    hass_storage[f"{DOMAIN}.{mock_config_entry.entry_id}"] = {
        "version": 1,
        "key": f"{DOMAIN}.{mock_config_entry.entry_id}",
        "data": {
            "slots": {
                "5": {"name": "Courier", "has_pin": True},
                "6": {"name": "Bo", "has_pin": True},
            },
            "uses_left": {"5": 0, "6": 3, "7": 1, "x": 1, "8": "many"},
            "usage": {
                "pin:5": {"count": 1, "last": None},
                "pin:9": "broken",
                "pin:x": {"count": 1},
                "rfid": {"count": 1},
                "door:3": {"count": 1},
            },
            "unlocks_total": 4,
        },
    }
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    manager = mock_config_entry.runtime_data
    assert _calls(fake_zha) == [(0x07, 5)]
    # Slot 7 has no code, so its limit is dropped; damaged records are skipped.
    assert manager.uses_left(6) == 3
    assert manager.uses_left(7) is None
    assert set(manager.usage) == {"pin:5"}
    assert hass.states.get(UNLOCKS).state == "4"


async def test_validation(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    with pytest.raises(ServiceValidationError) as err:
        await _set(
            hass,
            slot=5,
            pin_code="2580",
            max_uses=1,
            weekdays=["mon"],
            start_time="08:00:00",
            end_time="16:00:00",
        )
    assert err.value.translation_key == "uses_with_weekly"
    with pytest.raises(Exception):  # noqa: B017
        await _set(hass, slot=5, pin_code="2580", max_uses=0)
    fake_zha.cluster.command.assert_not_awaited()


async def test_options_one_time_code(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "set_pin"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"slot": 5, "name": "Courier", "pin_code": "2580", "max_uses": 1}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert init_integration.runtime_data.uses_left(5) == 1


async def test_unlock_counts_per_person(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    manager = init_integration.runtime_data
    manager.set_slot_name(5, "Anna")
    manager.set_slot_name(5, "Bo", "fingerprint")
    manager.set_slot_name(7, "Anna", "rfid")
    await hass.async_block_till_done()
    for value in (
        _keypad_unlock(5),
        _keypad_unlock(5),
        0x03020005,  # fingerprint 5: Bo
        0x04020007,  # key tag 7: Anna again
        0x01020000,  # button inside: nobody
        0x0A010000,  # auto relock: not an unlock
        _keypad_unlock(9),  # unnamed slot
    ):
        await _report(hass, fake_zha, value)
    state = hass.states.get(UNLOCKS)
    assert state.state == "5"
    assert state.attributes["by_user"] == {"Anna": 3, "Bo": 1, "Slot 9": 1}
    assert state.attributes["credentials"]["pin:5"]["count"] == 2
    assert state.attributes["credentials"]["pin:5"]["last_unlock"] is not None

    # A new code in a slot starts its count again; the total keeps going up.
    await _set(hass, slot=5, pin_code="2580")
    state = hass.states.get(UNLOCKS)
    assert "pin:5" not in state.attributes["credentials"]
    assert state.state == "5"


async def test_unlock_from_home_assistant_counts_the_user(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    zha_lock_setup: tuple[MockConfigEntry, str],  # noqa: F811
    hass_admin_user: MockUser,
) -> None:
    entry, lock_entity_id = zha_lock_setup
    async_mock_service(hass, "lock", "unlock")
    await hass.services.async_call(
        "lock",
        "unlock",
        {"entity_id": lock_entity_id},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    await _report(hass, fake_zha, 0x00020000)
    key = f"ha:{hass_admin_user.id}"
    assert entry.runtime_data.usage[key]["count"] == 1
    # Counted by user id; shown by the name at the last unlock.
    state = hass.states.get("sensor.front_door_activity_unlocks")
    assert state.attributes["by_user"] == {hass_admin_user.name: 1}


async def test_counts_survive_reload(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    await _set(hass, slot=5, pin_code="2580", max_uses=3)
    await _report(hass, fake_zha, _keypad_unlock(5))
    await hass.config_entries.async_reload(init_integration.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    manager = init_integration.runtime_data
    assert manager.uses_left(5) == 2
    assert manager.usage["pin:5"]["count"] == 1
    assert hass.states.get(UNLOCKS).state == "1"


@pytest.mark.repeated_reports
async def test_repeated_report_counts_once(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    await _set(hass, slot=5, pin_code="2580", max_uses=2)
    manager = init_integration.runtime_data
    # A retransmission, or a read of 0x0100, repeats the report.
    await _report(hass, fake_zha, _keypad_unlock(5))
    await _report(hass, fake_zha, _keypad_unlock(5))
    assert manager.uses_left(5) == 1
    assert manager.unlocks_total == 1
    # The same operation later is a new one.
    freezer.tick(timedelta(seconds=31))
    await _report(hass, fake_zha, _keypad_unlock(5))
    assert manager.unlocks_total == 2
    assert _calls(fake_zha)[-1] == (0x07, 5)


async def test_clear_keeps_a_code_written_meanwhile(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    await _set(hass, slot=5, pin_code="2580", max_uses=1)
    manager = init_integration.runtime_data
    # A new code lands before the used-up clear gets the radio.
    await _set(hass, slot=5, pin_code="2581")
    calls = fake_zha.cluster.command.await_count
    await manager._async_expire(5)  # noqa: SLF001
    assert fake_zha.cluster.command.await_count == calls
    assert manager.slots[5]["has_pin"] is True


@pytest.mark.parametrize("replace", [True, False])
async def test_repair_goes_when_code_is_replaced_or_cleared(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry, replace: bool
) -> None:
    await _set(hass, slot=5, pin_code="2580", max_uses=1)
    manager = init_integration.runtime_data
    working = fake_zha.cluster.command
    fake_zha.cluster.command = AsyncMock(side_effect=TimeoutError)
    await _report(hass, fake_zha, _keypad_unlock(5))
    await manager._async_expire(5, attempt=2)  # noqa: SLF001
    issue_id = f"expired_pin_not_cleared_{init_integration.entry_id}_5"
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is not None
    fake_zha.cluster.command = working
    if replace:
        await _set(hass, slot=5, pin_code="2581")
    else:
        await hass.services.async_call(DOMAIN, NimlyService.CLEAR_PIN, {"slot": 5}, blocking=True)
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None


async def test_new_person_on_a_credential_counts_from_zero(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    manager = init_integration.runtime_data
    await _report(hass, fake_zha, 0x03020005)  # fingerprint 5, no name yet
    # Naming it keeps the count: it is the same finger.
    manager.set_slot_name(5, "Bo", "fingerprint")
    assert manager.usage["fingerprint:5"]["count"] == 1
    await _report(hass, fake_zha, 0x04020005)  # key tag 5
    # Renamed to someone else: that finger counts again; the tag keeps its count.
    manager.set_slot_name(5, "Cecilia", "fingerprint")
    assert "fingerprint:5" not in manager.usage
    assert manager.usage["rfid:5"]["count"] == 1
    # A tag enrolled or removed in the slot counts again too.
    await hass.services.async_call(
        DOMAIN, NimlyService.ENROLL_CREDENTIAL, {"slot": 5, "credential": "rfid"}, blocking=True
    )
    assert manager.usage == {}
    assert hass.states.get(UNLOCKS).attributes["by_user"] == {}
    assert hass.states.get(UNLOCKS).state == "2"


async def test_unlock_updates_only_usage_entities(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    await _set(hass, slot=5, pin_code="2580", max_uses=3)
    keypad = "switch.nimlypro_activity_keypad_programming"
    # Copied: Home Assistant updates last_reported on the state object itself.
    reported = hass.states.get(keypad).last_reported
    await _report(hass, fake_zha, _keypad_unlock(5))
    assert hass.states.get(PIN_CODES).attributes["slots"]["5"]["uses_left"] == 2
    assert hass.states.get(UNLOCKS).state == "1"
    assert hass.states.get(keypad).last_reported == reported
