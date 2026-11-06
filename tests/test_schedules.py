"""Codes written later, in weekly windows, or generated."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.nimly_digital_lock.const import DOMAIN, NimlyService
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError
from homeassistant.util import dt as dt_util

from .conftest import FakeZha

SET = (0x05,)
CLEAR = (0x07,)


def _local(*args: int) -> datetime:
    return datetime(*args, tzinfo=dt_util.get_default_time_zone())


def _calls(fake_zha: FakeZha) -> list[tuple[Any, ...]]:
    """(command, slot) for every command sent, in order."""
    return [(c.args[0], c.kwargs.get("user_id")) for c in fake_zha.cluster.command.await_args_list]


async def _tick(hass: HomeAssistant, freezer: FrozenDateTimeFactory, to: datetime) -> None:
    freezer.move_to(to)
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)


async def test_code_written_later_then_forgotten(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    hass_storage: dict[str, Any],
) -> None:
    freezer.move_to(_local(2026, 11, 9, 7, 0))
    await hass.services.async_call(
        DOMAIN,
        NimlyService.SET_PIN,
        {
            "slot": 5,
            "pin_code": "2580",
            "name": "Plumber",
            "valid_from": "2026-11-09 08:00:00",
            "valid_until": "2026-11-09 12:00:00",
        },
        blocking=True,
    )
    assert _calls(fake_zha) == []
    manager = init_integration.runtime_data
    assert manager.schedules[5].code == "2580"
    await manager.async_flush()
    assert hass_storage[f"{DOMAIN}.{init_integration.entry_id}"]["data"]["schedules"]["5"]["code"]

    await _tick(hass, freezer, _local(2026, 11, 9, 8, 0, 1))
    assert _calls(fake_zha) == [(0x05, 5)]
    assert manager.slots[5]["has_pin"] is True
    # Written: the code is no longer kept in Home Assistant.
    assert manager.schedules == {}
    await manager.async_flush()
    assert hass_storage[f"{DOMAIN}.{init_integration.entry_id}"]["data"]["schedules"] == {}

    await _tick(hass, freezer, _local(2026, 11, 9, 12, 0, 1))
    assert _calls(fake_zha)[-1] == (0x07, 5)


async def test_weekly_windows(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(_local(2026, 11, 9, 7, 0))  # Monday
    await hass.services.async_call(
        DOMAIN,
        NimlyService.SET_PIN,
        {
            "slot": 6,
            "pin_code": "4826",
            "name": "Cleaner",
            "weekdays": ["mon", "thu"],
            "start_time": "08:00:00",
            "end_time": "16:00:00",
        },
        blocking=True,
    )
    assert _calls(fake_zha) == []
    attrs = hass.states.get("sensor.nimlypro_activity_pin_codes").attributes
    assert "4826" not in str(attrs)
    assert attrs["schedules"]["6"]["days"] == [0, 3]
    assert attrs["schedules"]["6"]["from"] == "08:00"

    await _tick(hass, freezer, _local(2026, 11, 9, 8, 0, 1))
    assert _calls(fake_zha) == [(0x05, 6)]
    await _tick(hass, freezer, _local(2026, 11, 9, 16, 0, 1))
    assert _calls(fake_zha)[-1] == (0x07, 6)
    # Tuesday and Wednesday: nothing. Thursday 08:00: written again.
    await _tick(hass, freezer, _local(2026, 11, 11, 12, 0))
    assert len(_calls(fake_zha)) == 2
    await _tick(hass, freezer, _local(2026, 11, 12, 8, 0, 1))
    assert _calls(fake_zha)[-1] == (0x05, 6)
    assert init_integration.runtime_data.schedules[6].recurring


async def test_weekly_window_open_now_writes_at_once(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(_local(2026, 11, 9, 9, 30))  # Monday, inside 08-16
    await hass.services.async_call(
        DOMAIN,
        NimlyService.SET_PIN,
        {
            "slot": 6,
            "pin_code": "4826",
            "weekdays": ["mon"],
            "start_time": "08:00:00",
            "end_time": "16:00:00",
        },
        blocking=True,
    )
    assert _calls(fake_zha) == [(0x05, 6)]
    expires = dt_util.parse_datetime(init_integration.runtime_data.slots[6]["expires"])
    assert expires == dt_util.as_utc(_local(2026, 11, 9, 16, 0))


async def test_schedule_ends(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(_local(2026, 11, 9, 7, 0))
    await hass.services.async_call(
        DOMAIN,
        NimlyService.SET_PIN,
        {
            "slot": 6,
            "pin_code": "4826",
            "weekdays": ["mon", "thu"],
            "start_time": "08:00:00",
            "end_time": "16:00:00",
            "valid_until": "2026-11-10 00:00:00",
        },
        blocking=True,
    )
    await _tick(hass, freezer, _local(2026, 11, 9, 8, 0, 1))
    await _tick(hass, freezer, _local(2026, 11, 9, 16, 0, 1))
    await _tick(hass, freezer, _local(2026, 11, 12, 8, 0, 1))
    assert _calls(fake_zha) == [(0x05, 6), (0x07, 6)]
    assert init_integration.runtime_data.schedules == {}


async def test_missed_window_is_not_written(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Home Assistant down for the whole window: no code for a past window."""
    freezer.move_to(_local(2026, 11, 9, 7, 0))
    await hass.services.async_call(
        DOMAIN,
        NimlyService.SET_PIN,
        {
            "slot": 6,
            "pin_code": "4826",
            "weekdays": ["mon", "thu"],
            "start_time": "08:00:00",
            "end_time": "16:00:00",
        },
        blocking=True,
    )
    await _tick(hass, freezer, _local(2026, 11, 9, 17, 0))
    assert _calls(fake_zha) == []
    await _tick(hass, freezer, _local(2026, 11, 12, 8, 0, 1))
    assert _calls(fake_zha) == [(0x05, 6)]


async def test_manual_clear_cancels_schedule(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(_local(2026, 11, 9, 7, 0))
    base = {"slot": 6, "weekdays": ["mon"], "start_time": "08:00:00", "end_time": "16:00:00"}
    await hass.services.async_call(
        DOMAIN, NimlyService.SET_PIN, {**base, "pin_code": "4826"}, blocking=True
    )
    await hass.services.async_call(DOMAIN, NimlyService.CLEAR_PIN, {"slot": 6}, blocking=True)
    assert init_integration.runtime_data.schedules == {}
    await _tick(hass, freezer, _local(2026, 11, 9, 8, 0, 1))
    assert _calls(fake_zha) == [(0x07, 6)]


async def test_schedule_survives_restart(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    mock_zha_setup: None,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    hass_storage: dict[str, Any],
) -> None:
    freezer.move_to(_local(2026, 11, 9, 7, 0))
    hass_storage[f"{DOMAIN}.{mock_config_entry.entry_id}"] = {
        "version": 1,
        "key": f"{DOMAIN}.{mock_config_entry.entry_id}",
        "data": {
            "slots": {},
            "schedules": {
                "6": {
                    "code": "4826",
                    "name": "Cleaner",
                    "days": [0],
                    "from": "08:00",
                    "to": "16:00",
                },
                "7": {"code": "not digits"},  # damaged: skipped
                "8": {"code": "1234", "days": [0]},  # weekly without times: skipped
            },
        },
    }
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert set(mock_config_entry.runtime_data.schedules) == {6}
    await _tick(hass, freezer, _local(2026, 11, 9, 8, 0, 1))
    assert _calls(fake_zha) == [(0x05, 6)]


async def test_scheduled_write_retried_while_unreachable(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(_local(2026, 11, 9, 7, 0))
    await hass.services.async_call(
        DOMAIN,
        NimlyService.SET_PIN,
        {"slot": 5, "pin_code": "2580", "valid_from": "2026-11-09 08:00:00"},
        blocking=True,
    )
    fake_zha.cluster.command = AsyncMock(side_effect=TimeoutError)
    await _tick(hass, freezer, _local(2026, 11, 9, 8, 0, 1))
    assert 5 in init_integration.runtime_data.schedules
    fake_zha.cluster.command = AsyncMock(return_value=None)
    await _tick(hass, freezer, _local(2026, 11, 9, 8, 11))
    fake_zha.cluster.command.assert_awaited_once()
    assert init_integration.runtime_data.schedules == {}


async def test_generated_code_in_response(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    response = await hass.services.async_call(
        DOMAIN,
        NimlyService.SET_PIN,
        {"slot": 8, "name": "Guest"},
        blocking=True,
        return_response=True,
    )
    code = response["pin_code"]
    assert code.isdigit() and len(code) == 6
    fake_zha.cluster.command.assert_awaited_with(
        0x05, user_id=8, user_status=1, user_type=0, pin_code=code
    )
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, NimlyService.SET_PIN, {"slot": 8}, blocking=True)
    assert err.value.translation_key == "generate_needs_response"


@pytest.mark.parametrize(
    ("data", "key"),
    [
        (
            {"valid_from": "2026-11-09 12:00:00", "valid_until": "2026-11-09 10:00:00"},
            "end_before_start",
        ),
        ({"weekdays": ["mon"], "start_time": "08:00:00", "end_time": "08:00:00"}, "empty_window"),
    ],
)
async def test_schedule_validation(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    data: dict[str, Any],
    key: str,
) -> None:
    freezer.move_to(_local(2026, 11, 9, 7, 0))
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, NimlyService.SET_PIN, {"slot": 5, "pin_code": "2580", **data}, blocking=True
        )
    assert err.value.translation_key == key


async def test_options_schedule_with_generated_code(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(_local(2026, 11, 9, 7, 0))
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "schedule_pin"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            "slot": 6,
            "name": "Cleaner",
            "pin_code": "",
            "weekdays": ["mon"],
            "start_time": "08:00:00",
            "end_time": "16:00:00",
        },
    )
    assert result["step_id"] == "pin_generated"
    code = result["description_placeholders"]["pin"]
    assert init_integration.runtime_data.schedules[6].code == code
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_options_set_pin_later(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(_local(2026, 11, 9, 7, 0))
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "set_pin"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {"slot": 5, "pin_code": "2580", "valid_from": "2026-11-09 08:00:00"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    fake_zha.cluster.command.assert_not_awaited()
    assert init_integration.runtime_data.schedules[5].start == dt_util.as_utc(
        _local(2026, 11, 9, 8, 0)
    )
    assert timedelta(0) < init_integration.runtime_data.schedules[5].start - dt_util.utcnow()


async def test_schedule_never_writes_a_slot_that_became_reserved(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    hass.config_entries.async_update_entry(init_integration, options={"reserved_slots": 1})
    await hass.async_block_till_done()
    freezer.move_to(_local(2026, 11, 9, 7, 0))
    await hass.services.async_call(
        DOMAIN,
        NimlyService.SET_PIN,
        {
            "slot": 2,
            "pin_code": "4826",
            "weekdays": ["mon"],
            "start_time": "08:00:00",
            "end_time": "16:00:00",
        },
        blocking=True,
    )
    hass.config_entries.async_update_entry(init_integration, options={"reserved_slots": 3})
    await _tick(hass, freezer, _local(2026, 11, 9, 8, 0, 1))
    assert _calls(fake_zha) == []
    assert init_integration.runtime_data.schedules == {}


async def test_one_off_dropped_when_too_late_to_retry(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to(_local(2026, 11, 9, 7, 0))
    await hass.services.async_call(
        DOMAIN,
        NimlyService.SET_PIN,
        {
            "slot": 5,
            "pin_code": "2580",
            "valid_from": "2026-11-09 08:00:00",
            "valid_until": "2026-11-09 08:05:00",
        },
        blocking=True,
    )
    fake_zha.cluster.command = AsyncMock(side_effect=TimeoutError)
    await _tick(hass, freezer, _local(2026, 11, 9, 8, 0, 1))
    # The 10-minute retry would come after the end: dropped, code and all.
    assert init_integration.runtime_data.schedules == {}
