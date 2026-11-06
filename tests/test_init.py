"""Tests for setup, lock events, migration and unload."""

from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from pytest_homeassistant_custom_component.common import MockConfigEntry, async_capture_events

from custom_components.nimly_digital_lock.const import DOMAIN, EVENT_LOCK_ACTIVITY
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir

from .conftest import IEEE, MODEL, FakeZha

ACTIVITY = "event.nimlypro_activity_activity"
LAST_ACTION = "sensor.nimlypro_activity_last_action"
LAST_SOURCE = "sensor.nimlypro_activity_last_operated_by"
LAST_USER = "sensor.nimlypro_activity_last_user"
PIN_CODES = "sensor.nimlypro_activity_pin_codes"


async def test_setup_creates_entities(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    assert init_integration.state is ConfigEntryState.LOADED
    for entity_id in (ACTIVITY, LAST_ACTION, LAST_SOURCE, LAST_USER, PIN_CODES):
        state = hass.states.get(entity_id)
        assert state is not None, entity_id
        assert state.state != STATE_UNAVAILABLE
    assert hass.states.get(LAST_USER).state == STATE_UNKNOWN
    assert hass.states.get(PIN_CODES).state == "0"
    # PIN capacity is disabled by default.
    assert hass.states.get("sensor.nimlypro_activity_pin_capacity") is None


async def test_capabilities_read_after_setup(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    manager = init_integration.runtime_data
    assert manager.capabilities == {"num_pin_users": 50, "max_pin_length": 8, "min_pin_length": 4}
    assert manager.max_user_slot == 49


async def test_keypad_unlock_then_auto_relock(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    init_integration.runtime_data.set_slot_name(5, "Anna")

    fake_zha.cluster.report(0x0100, 0x02020005)  # keypad unlock, slot 5
    await hass.async_block_till_done()

    assert hass.states.get(LAST_ACTION).state == "unlock"
    assert hass.states.get(LAST_SOURCE).state == "keypad"
    assert hass.states.get(LAST_USER).state == "Anna"
    activity = hass.states.get(ACTIVITY)
    assert activity.attributes["event_type"] == "unlock"
    assert activity.attributes["user"] == "Anna"
    assert activity.attributes["system"] is False

    fake_zha.cluster.report(0x0100, 0x0A010000)  # auto relock
    await hass.async_block_till_done()

    assert hass.states.get(LAST_ACTION).state == "lock"
    assert hass.states.get(LAST_SOURCE).state == "auto"
    # Who opened the door survives the relock.
    assert hass.states.get(LAST_USER).state == "Anna"
    assert hass.states.get(ACTIVITY).attributes["system"] is True

    assert [e.data["action"] for e in events] == ["unlock", "lock"]
    assert events[0].data["user"] == "Anna"
    assert events[0].data["slot"] == 5
    assert events[1].data["system"] is True


async def test_unnamed_slot_and_wrapped_value(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    fake_zha.cluster.report(0x0100, SimpleNamespace(value=0x04020384))  # rfid, slot 900
    await hass.async_block_till_done()
    assert hass.states.get(LAST_USER).state == "Slot 900"
    assert hass.states.get(LAST_SOURCE).state == "rfid"


async def test_pin_used_attribute_is_ignored(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry, caplog
) -> None:
    events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    fake_zha.cluster.report(0x0101, b"\x041234")
    fake_zha.cluster.report(0x0100, "garbage")
    await hass.async_block_till_done()
    assert not events
    assert "1234" not in caplog.text


async def test_listener_fallback_for_older_zigpy(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    add_device_proxy,
    mock_zha_setup: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """zigpy before 0.91 has no Cluster.on_event, only add_listener."""
    listeners = []
    cluster = SimpleNamespace(add_listener=listeners.append, remove_listener=listeners.remove)
    fake_zha.device_proxies[IEEE] = add_device_proxy(cluster)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    [listener] = listeners
    listener.attribute_updated(0x0100, 0x03020096, None)  # fingerprint, slot 150
    await hass.async_block_till_done()
    assert hass.states.get(LAST_SOURCE).state == "fingerprint"
    assert hass.states.get(LAST_USER).state == "Slot 150"

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert listeners == []


async def test_not_ready_while_cluster_missing(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    add_device_proxy,
    mock_zha_setup: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    """A device whose interview has not exposed the Door Lock cluster is retried."""
    fake_zha.device_proxies[IEEE] = add_device_proxy(None)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert (
        ir.async_get(hass).async_get_issue(DOMAIN, f"zha_internals_{mock_config_entry.entry_id}")
        is None
    )


async def test_one_capability_read_at_a_time(
    hass: HomeAssistant, fake_zha: FakeZha, mock_zha_setup: None, mock_config_entry: MockConfigEntry
) -> None:
    release = asyncio.Event()

    async def _slow_read(*_):
        await release.wait()
        raise TimeoutError

    fake_zha.cluster.read_attributes = AsyncMock(side_effect=_slow_read)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=False)
    for _ in range(5):
        fake_zha.cluster.report(0x0100, 0x00010000)
    await hass.async_block_till_done(wait_background_tasks=False)
    assert fake_zha.cluster.read_attributes.await_count == 1
    release.set()
    await hass.async_block_till_done()
    assert mock_config_entry.runtime_data.capabilities_read is False


async def test_not_ready_without_zha(
    hass: HomeAssistant, fake_zha: FakeZha, mock_zha_setup: None, mock_config_entry: MockConfigEntry
) -> None:
    fake_zha.running = False
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_not_ready_when_lock_missing(
    hass: HomeAssistant, fake_zha: FakeZha, mock_zha_setup: None, mock_config_entry: MockConfigEntry
) -> None:
    fake_zha.device_proxies.clear()
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_repair_issue_without_event_hook(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    add_device_proxy,
    mock_zha_setup: None,
    mock_config_entry: MockConfigEntry,
) -> None:
    fake_zha.device_proxies[IEEE] = add_device_proxy(SimpleNamespace())
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    issue = ir.async_get(hass).async_get_issue(
        DOMAIN, f"zha_internals_{mock_config_entry.entry_id}"
    )
    assert issue is not None
    assert hass.states.get(ACTIVITY).state == STATE_UNAVAILABLE

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    assert (
        ir.async_get(hass).async_get_issue(DOMAIN, f"zha_internals_{mock_config_entry.entry_id}")
        is None
    )


async def test_unload_unsubscribes(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    assert len(fake_zha.cluster.listeners) == 1
    assert await hass.config_entries.async_unload(init_integration.entry_id)
    assert init_integration.state is ConfigEntryState.NOT_LOADED
    assert fake_zha.cluster.listeners == []


async def test_reload_does_not_duplicate_listener(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    await hass.config_entries.async_reload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert len(fake_zha.cluster.listeners) == 1


async def test_migrate_from_v1(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    mock_zha_setup: None,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    old = MockConfigEntry(
        domain=DOMAIN,
        title="Nimly Front Door",
        version=1,
        data={
            "ieee": "F4:CE:36:0A:04:4D:31:F5",
            "ieee_no_colons": "f4ce360a044d31f5",
            "ieee_with_colons": "f4:ce:36:0a:04:4d:31:f5",
            "name": "Nimly Front Door",
        },
        options={"auto_relock_time": 1, "sound_volume": 2},
    )
    old.add_to_hass(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=old.entry_id, identifiers={(DOMAIN, "F4:CE:36:0A:04:4D:31:F5")}
    )
    old_lock = entity_registry.async_get_or_create(
        "lock",
        DOMAIN,
        "nimly_digital_lock_lock_f4ce360a044d31f5",
        config_entry=old,
        device_id=device.id,
    )

    await hass.config_entries.async_setup(old.entry_id)
    await hass.async_block_till_done()

    assert old.state is ConfigEntryState.LOADED
    assert old.version == 2
    assert old.unique_id == IEEE
    assert old.data == {"ieee": IEEE, "model": MODEL}
    assert old.options == {}
    assert entity_registry.async_get(old_lock.entity_id) is None
    assert hass.states.get(LAST_ACTION) is not None


async def test_remove_entry_deletes_store(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry, hass_storage
) -> None:
    init_integration.runtime_data.set_slot_name(4, "Bo")
    await hass.async_block_till_done()
    await hass.config_entries.async_remove(init_integration.entry_id)
    await hass.async_block_till_done()
    assert f"{DOMAIN}.{init_integration.entry_id}" not in hass_storage
