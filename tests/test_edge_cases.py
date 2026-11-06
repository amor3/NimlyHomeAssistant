"""Paths that only matter when something is off: timers, failures, odd states."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.nimly_digital_lock import async_migrate_entry
from custom_components.nimly_digital_lock.const import DOMAIN, NimlyService
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.util import dt as dt_util

from .conftest import FakeZha
from .test_zha import _zha_lock


async def test_valid_until_from_action(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    freezer.move_to("2026-11-06 10:00:00+00:00")
    await hass.services.async_call(
        DOMAIN,
        NimlyService.SET_PIN,
        {"slot": 5, "pin_code": "2580", "valid_until": "2026-11-06T12:00:00+00:00"},
        blocking=True,
    )
    slot = init_integration.runtime_data.slots[5]
    assert dt_util.parse_datetime(slot["expires"]) == dt_util.parse_datetime(
        "2026-11-06T12:00:00+00:00"
    )
    freezer.move_to("2026-11-06 12:00:01+00:00")
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    fake_zha.cluster.command.assert_awaited_with(0x07, user_id=5)


async def test_manual_clear_cancels_expiry(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Clearing a temporary code by hand must not clear the slot again later."""
    await hass.services.async_call(
        DOMAIN,
        NimlyService.SET_PIN,
        {"slot": 5, "pin_code": "2580", "valid_for": {"hours": 1}},
        blocking=True,
    )
    await hass.services.async_call(DOMAIN, NimlyService.CLEAR_PIN, {"slot": 5}, blocking=True)
    # Someone else gets the slot with a permanent code.
    await hass.services.async_call(
        DOMAIN, NimlyService.SET_PIN, {"slot": 5, "pin_code": "9753"}, blocking=True
    )
    calls_before = fake_zha.cluster.command.await_count
    freezer.tick(timedelta(hours=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert fake_zha.cluster.command.await_count == calls_before
    assert init_integration.runtime_data.slots[5]["has_pin"] is True


async def test_unload_with_timers_pending(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A pending gap check and an expiry timer do not fire after unload."""
    await hass.services.async_call(
        DOMAIN,
        NimlyService.SET_PIN,
        {"slot": 5, "pin_code": "2580", "valid_for": {"minutes": 1}},
        blocking=True,
    )
    fake_zha.cluster.report(0x0000, 1)
    fake_zha.cluster.report(0x0000, 2)
    manager = init_integration.runtime_data
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    calls_before = fake_zha.cluster.command.await_count
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert fake_zha.cluster.command.await_count == calls_before
    assert manager.missed_reports == 0


async def test_options_clear_pin_unreachable(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    await hass.services.async_call(
        DOMAIN, NimlyService.SET_PIN, {"slot": 4, "pin_code": "1234"}, blocking=True
    )
    fake_zha.cluster.command = AsyncMock(side_effect=TimeoutError)
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "clear_pin"}
    )
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"slot": "4"})
    assert result["errors"] == {"base": "lock_unreachable"}
    assert init_integration.runtime_data.slots[4]["has_pin"] is True


async def test_options_when_not_loaded_show_settings(
    hass: HomeAssistant, fake_zha: FakeZha, mock_zha_setup: None, mock_config_entry: MockConfigEntry
) -> None:
    fake_zha.running = False
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "settings"


async def test_action_on_entry_not_loaded(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    await hass.config_entries.async_unload(init_integration.entry_id)
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            NimlyService.CLEAR_PIN,
            {"config_entry_id": init_integration.entry_id, "slot": 4},
            blocking=True,
        )
    assert err.value.translation_key == "entry_not_loaded"


async def test_pin_capacity_sensor(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    entity_id = "sensor.nimlypro_activity_pin_capacity"
    entity_registry.async_update_entity(entity_id, disabled_by=None)
    await hass.config_entries.async_reload(init_integration.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "50"
    assert state.attributes["min_pin_length"] == 4
    assert state.attributes["max_pin_length"] == 8


async def test_failed_wake_still_retries(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    mock_zha_setup: None,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    _zha_lock(hass, device_registry, entity_registry)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="f4:ce:36:0a:04:4d:31:f5",
        version=2,
        data={"ieee": "f4:ce:36:0a:04:4d:31:f5", "model": "NimlyPRO"},
        options={"wake_with_lock": True},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    async def _refuse(call) -> None:
        raise HomeAssistantError("lock did not answer")

    hass.services.async_register("lock", "lock", _refuse)
    fake_zha.cluster.command = AsyncMock(side_effect=[TimeoutError, None])
    await hass.services.async_call(
        DOMAIN, NimlyService.SET_PIN, {"slot": 3, "pin_code": "1234"}, blocking=True
    )
    assert fake_zha.cluster.command.await_count == 2


async def test_response_carrying_an_exception(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    """zigpy may hand back an exception object as the result."""
    fake_zha.cluster.command = AsyncMock(return_value=RuntimeError("radio"))
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN, NimlyService.SET_PIN, {"slot": 3, "pin_code": "1234"}, blocking=True
        )
    assert err.value.translation_key == "lock_unreachable"
    fake_zha.cluster.command = AsyncMock(return_value=SimpleNamespace(status="odd"))
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN, NimlyService.SET_PIN, {"slot": 3, "pin_code": "1234"}, blocking=True
        )
    assert err.value.translation_key == "lock_rejected"


async def test_migrate_refuses_future_version(hass: HomeAssistant) -> None:
    entry = MockConfigEntry(domain=DOMAIN, version=3, data={"ieee": "x"})
    entry.add_to_hass(hass)
    assert await async_migrate_entry(hass, entry) is False


async def test_unknown_lock_state_report_is_ignored(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    fake_zha.cluster.report(0x0000, object())
    await hass.async_block_till_done()
    assert init_integration.runtime_data.missed_reports == 0


async def test_lock_call_for_another_device_is_not_credited(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    mock_zha_setup: None,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    _zha_lock(hass, device_registry, entity_registry)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    async_mock_service(hass, "lock", "unlock")
    await hass.services.async_call("lock", "unlock", {"entity_id": "lock.garage"}, blocking=True)
    assert mock_config_entry.runtime_data._remote is None  # noqa: SLF001
