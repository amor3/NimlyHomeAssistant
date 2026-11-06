"""Radio priority, damaged storage, limits, diagnostics buffer, new sensors."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)

from custom_components.nimly_digital_lock.compat import vol
from custom_components.nimly_digital_lock.const import DOMAIN, NimlyService
from custom_components.nimly_digital_lock.zha import RadioGate
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import FakeZha


async def test_commands_go_before_background_reads() -> None:
    gate = RadioGate()
    order: list[str] = []
    release = asyncio.Event()

    async def background(name: str) -> None:
        async with gate.background():
            order.append(name)
            await release.wait()

    async def user(name: str) -> None:
        async with gate.user():
            order.append(name)

    first = asyncio.create_task(background("read 1"))
    await asyncio.sleep(0)
    second = asyncio.create_task(background("read 2"))
    command = asyncio.create_task(user("command"))
    await asyncio.sleep(0)
    release.set()
    await asyncio.gather(first, second, command)
    # The running read finishes; the waiting command goes before the next read.
    assert order == ["read 1", "command", "read 2"]


async def test_damaged_storage_is_skipped(
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
                "4": {"name": "Bo", "has_pin": True},
                "x": {"name": "not a slot"},
                "5": "not a record",
            },
            "capabilities": {"num_pin_users": "many"},
            "schedules": "broken",
        },
    }
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    manager = mock_config_entry.runtime_data
    assert set(manager.slots) == {4}
    assert manager.schedules == {}
    # The unreadable capabilities were dropped and read again from the lock.
    assert manager.capabilities["num_pin_users"] == 50


async def test_name_length_limit(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    with pytest.raises(vol.Invalid):
        await hass.services.async_call(
            DOMAIN, NimlyService.SET_SLOT_NAME, {"slot": 4, "name": "x" * 65}, blocking=True
        )
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "name_slot"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"slot": 4, "name": "x" * 65}
    )
    assert result["errors"] == {"name": "name_too_long"}


async def test_recent_reports_in_diagnostics(
    hass: HomeAssistant, hass_client, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    for _ in range(25):
        fake_zha.cluster.report(0x0100, 0x02020004)
    fake_zha.cluster.report(0x0101, b"\x04\x12\x34")  # PIN used: never kept
    fake_zha.cluster.report(0x0102, b"\xde\xad")  # RFID used: never kept
    await hass.async_block_till_done()
    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
    reports = diagnostics["recent_reports"]
    assert len(reports) == 20
    assert {r["attribute"] for r in reports} == {"0x0100"}
    assert reports[-1]["value"] == "0x02020004"


async def test_battery_low_sensor(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    entity_id = "binary_sensor.nimlypro_activity_battery_low"
    assert hass.states.get(entity_id).state == STATE_UNKNOWN
    fake_zha.power.report(0x9000, 1)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON
    fake_zha.power.report(0x9000, 0)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF


async def test_parent_router_sensor(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    router = SimpleNamespace(
        device=SimpleNamespace(manufacturer="IKEA", model="plug", nwk=0x5A5A, name="Hall plug")
    )
    fake_zha.device_proxies["00:11:22:33:44:55:66:77"] = router
    entity_id = "sensor.nimlypro_activity_parent_router"
    fake_zha.cluster.report(0x0103, (0xC5 << 24) | (0xA0 << 16) | 0x5A5A)
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "Hall plug"
    assert state.attributes["rssi_dbm"] == -59
    assert state.attributes["nwk"] == "0x5A5A"
    fake_zha.cluster.report(0x0103, (0xD0 << 24) | 0x0000)
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "Coordinator"


async def test_unsupported_attributes_are_not_asked_again(
    hass: HomeAssistant, fake_zha: FakeZha, mock_zha_setup: None, mock_config_entry: MockConfigEntry
) -> None:
    asked: list[list[int]] = []

    async def _read(ids: list[int], **_: Any) -> tuple[dict[int, Any], dict[int, Any]]:
        asked.append(list(ids))
        return {}, {i: 0x86 for i in ids}  # the lock has none of them

    fake_zha.power.read_attributes = AsyncMock(side_effect=_read)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    for _ in range(3):
        fake_zha.cluster.report(0x0100, 0x02020004)
        await hass.async_block_till_done(wait_background_tasks=True)
    assert asked == [[0x9000]]


async def test_custom_command_on_cluster_without_it(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    """A radio failure on the module's own command is reported, not raised."""
    fake_zha.cluster.request = AsyncMock(side_effect=TimeoutError)
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN,
            NimlyService.ENROLL_CREDENTIAL,
            {"slot": 5, "credential": "rfid"},
            blocking=True,
        )
    assert err.value.translation_key == "lock_unreachable"
