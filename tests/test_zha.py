"""Tests for following ZHA: reloads, the wake-up and the linked device."""

from __future__ import annotations

from unittest.mock import AsyncMock

from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_mock_service,
    mock_restore_cache_with_extra_data,
)

from custom_components.nimly_digital_lock.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import IEEE, FakeZha

LAST_USER = "sensor.front_door_activity_last_user"


def _zha_lock(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry, entity_registry: er.EntityRegistry
) -> tuple[MockConfigEntry, str]:
    """A ZHA config entry with ZHA's own device and lock entity for the lock."""
    zha_entry = MockConfigEntry(domain="zha", state=ConfigEntryState.LOADED)
    zha_entry.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=zha_entry.entry_id,
        connections={(dr.CONNECTION_ZIGBEE, IEEE)},
        identifiers={("zha", IEEE)},
        name="Front door",
    )
    lock = entity_registry.async_get_or_create(
        "lock", "zha", f"{IEEE}-11-257", config_entry=zha_entry, device_id=device.id
    )
    return zha_entry, lock.entity_id


async def test_device_linked_to_zha(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    mock_zha_setup: None,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    zha_entry, _ = _zha_lock(hass, device_registry, entity_registry)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    [ours] = dr.async_entries_for_config_entry(device_registry, mock_config_entry.entry_id)
    [zha] = dr.async_entries_for_config_entry(device_registry, zha_entry.entry_id)
    assert (DOMAIN, mock_config_entry.entry_id) in ours.identifiers
    assert ours.id != zha.id
    assert ours.via_device_id == zha.id
    assert ours.name == "Front door activity"


async def test_follows_zha_reload(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    mock_zha_setup: None,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    zha_entry, _ = _zha_lock(hass, device_registry, entity_registry)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    old_listener = fake_zha.cluster.listeners[0]

    zha_entry.mock_state(hass, ConfigEntryState.NOT_LOADED)
    await hass.async_block_till_done()
    assert hass.states.get(LAST_USER).state == STATE_UNAVAILABLE

    zha_entry.mock_state(hass, ConfigEntryState.LOADED)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert len(fake_zha.cluster.listeners) == 1
    assert fake_zha.cluster.listeners[0] is not old_listener
    assert hass.states.get(LAST_USER).state != STATE_UNAVAILABLE


async def test_wake_with_lock_before_retry(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    mock_zha_setup: None,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    _, lock_entity_id = _zha_lock(hass, device_registry, entity_registry)
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=IEEE,
        version=2,
        data={"ieee": IEEE, "model": "NimlyPRO"},
        options={"wake_with_lock": True},
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    lock_calls = async_mock_service(hass, "lock", "lock")
    fake_zha.cluster.command = AsyncMock(side_effect=[TimeoutError, None])

    await hass.services.async_call(
        DOMAIN,
        "set_pin",
        {"config_entry_id": entry.entry_id, "slot": 3, "pin_code": "1234"},
        blocking=True,
    )

    assert [call.data["entity_id"] for call in lock_calls] == [lock_entity_id]
    assert entry.runtime_data.transport.wake_echo_pending()
    # The lock reports the wake-up as a Zigbee lock: marked as a system event.
    fake_zha.cluster.report(0x0100, 0x00010000)
    await hass.async_block_till_done()
    activity = hass.states.get("event.front_door_activity_activity")
    assert activity.attributes["system"] is True


async def test_no_wake_by_default(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
) -> None:
    lock_calls = async_mock_service(hass, "lock", "lock")
    fake_zha.cluster.command = AsyncMock(side_effect=[TimeoutError, None])
    await hass.services.async_call(
        DOMAIN,
        "set_pin",
        {"config_entry_id": init_integration.entry_id, "slot": 3, "pin_code": "1234"},
        blocking=True,
    )
    assert lock_calls == []


async def test_last_user_restored(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    mock_zha_setup: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(
                    "sensor.nimlypro_activity_last_user",
                    "Anna",
                    {"slot": 5, "source": "keypad", "action": "unlock"},
                ),
                {"native_value": "Anna", "native_unit_of_measurement": None},
            )
        ],
    )
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    state = hass.states.get("sensor.nimlypro_activity_last_user")
    assert state.state == "Anna"
    assert state.attributes["slot"] == 5
