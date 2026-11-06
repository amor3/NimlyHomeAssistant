"""Tests for discovery, reconfigure, temporary codes, rebinding and repairs."""

from __future__ import annotations

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry, async_fire_time_changed

from custom_components.nimly_digital_lock import async_remove_config_entry_device
from custom_components.nimly_digital_lock.const import DOMAIN, NimlyService
from homeassistant.config_entries import SOURCE_IGNORE, SOURCE_INTEGRATION_DISCOVERY
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir
from homeassistant.util import dt as dt_util

from .conftest import IEEE, FakeDoorLockCluster, FakeZha

IEEE2 = "f4:ce:36:aa:bb:cc:dd:ee"
LAST_SOURCE = "sensor.nimlypro_activity_last_operated_by"


def _announce_device(hass: HomeAssistant, device_registry: dr.DeviceRegistry, ieee: str) -> None:
    """What ZHA does when it pairs a device: a device registry entry."""
    zha_entry = MockConfigEntry(domain="zha")
    zha_entry.add_to_hass(hass)
    device_registry.async_get_or_create(
        config_entry_id=zha_entry.entry_id, connections={(dr.CONNECTION_ZIGBEE, ieee)}
    )


async def test_new_lock_is_discovered(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    add_device_proxy,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    second = FakeDoorLockCluster()
    fake_zha.device_proxies[IEEE2] = add_device_proxy(second, model="NimlyCode")
    _announce_device(hass, device_registry, IEEE2)
    await hass.async_block_till_done()

    [flow] = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert flow["context"]["source"] == SOURCE_INTEGRATION_DISCOVERY
    assert flow["context"]["unique_id"] == IEEE2
    assert flow["step_id"] == "discovery_confirm"

    # A second registry update does not start a second flow.
    _announce_device(hass, device_registry, IEEE2)
    await hass.async_block_till_done()
    assert len(hass.config_entries.flow.async_progress_by_handler(DOMAIN)) == 1

    result = await hass.config_entries.flow.async_configure(flow["flow_id"], {})
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NimlyCode (DDEE)"
    assert result["data"] == {"ieee": IEEE2, "model": "NimlyCode"}
    assert len(second.listeners) == 1


async def test_ignored_lock_is_not_offered_again(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    add_device_proxy,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    MockConfigEntry(domain=DOMAIN, source=SOURCE_IGNORE, unique_id=IEEE2, data={}).add_to_hass(hass)
    fake_zha.device_proxies[IEEE2] = add_device_proxy(FakeDoorLockCluster())
    _announce_device(hass, device_registry, IEEE2)
    await hass.async_block_till_done()
    assert hass.config_entries.flow.async_progress_by_handler(DOMAIN) == []


async def test_reconfigure_to_new_module_keeps_entities(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    add_device_proxy,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    await hass.services.async_call(
        DOMAIN,
        NimlyService.SET_PIN,
        {"config_entry_id": init_integration.entry_id, "slot": 4, "pin_code": "1234", "name": "Bo"},
        blocking=True,
    )
    entities_before = {
        e.unique_id: e.entity_id
        for e in er.async_entries_for_config_entry(entity_registry, init_integration.entry_id)
    }
    # The old module is gone from ZHA, the new one is paired.
    new_cluster = FakeDoorLockCluster()
    fake_zha.device_proxies.clear()
    fake_zha.device_proxies[IEEE2] = add_device_proxy(new_cluster)

    result = await init_integration.start_reconfigure_flow(hass)
    assert result["step_id"] == "reconfigure"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"ieee": IEEE2})
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert init_integration.unique_id == IEEE2
    assert init_integration.data["ieee"] == IEEE2
    assert init_integration.runtime_data.slots[4]["name"] == "Bo"
    entities_after = {
        e.unique_id: e.entity_id
        for e in er.async_entries_for_config_entry(entity_registry, init_integration.entry_id)
    }
    assert entities_after == entities_before
    assert len(new_cluster.listeners) == 1


async def test_reconfigure_refuses_configured_lock(
    hass: HomeAssistant, fake_zha: FakeZha, add_device_proxy, init_integration: MockConfigEntry
) -> None:
    other = MockConfigEntry(domain=DOMAIN, unique_id=IEEE2, version=2, data={"ieee": IEEE2})
    other.add_to_hass(hass)
    fake_zha.device_proxies[IEEE2] = add_device_proxy(FakeDoorLockCluster())
    result = await init_integration.start_reconfigure_flow(hass)
    options = result["data_schema"].schema["ieee"].config["options"]
    assert [option["value"] for option in options] == [IEEE]


async def test_temporary_pin_is_cleared(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    await hass.services.async_call(
        DOMAIN,
        NimlyService.SET_PIN,
        {
            "config_entry_id": init_integration.entry_id,
            "slot": 5,
            "pin_code": "2580",
            "name": "Plumber",
            "valid_for": {"hours": 2},
        },
        blocking=True,
    )
    slot = init_integration.runtime_data.slots[5]
    assert slot["has_pin"] is True
    assert dt_util.parse_datetime(slot["expires"]) == dt_util.utcnow() + timedelta(hours=2)
    attrs = hass.states.get("sensor.nimlypro_activity_pin_codes").attributes
    assert attrs["slots"]["5"]["expires"] == slot["expires"]

    freezer.tick(timedelta(hours=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert init_integration.runtime_data.slots[5]["has_pin"] is True

    freezer.tick(timedelta(hours=1, seconds=1))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    fake_zha.cluster.command.assert_awaited_with(0x07, user_id=5)
    assert init_integration.runtime_data.slots == {
        5: {"name": "Plumber", "has_pin": False, "expires": None, "names": {}}
    }


async def test_expired_pin_retried_while_lock_unreachable(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    await hass.services.async_call(
        DOMAIN,
        NimlyService.SET_PIN,
        {
            "config_entry_id": init_integration.entry_id,
            "slot": 5,
            "pin_code": "2580",
            "valid_for": {"minutes": 1},
        },
        blocking=True,
    )
    fake_zha.cluster.command = AsyncMock(side_effect=TimeoutError)
    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert fake_zha.cluster.command.await_count == 3
    assert init_integration.runtime_data.slots[5]["has_pin"] is True

    fake_zha.cluster.command = AsyncMock(return_value=None)
    freezer.tick(timedelta(minutes=11))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    fake_zha.cluster.command.assert_awaited_once_with(0x07, user_id=5)
    assert init_integration.runtime_data.slots == {}


async def test_pin_expired_while_home_assistant_was_down(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    mock_zha_setup: None,
    mock_config_entry: MockConfigEntry,
    hass_storage,
) -> None:
    hass_storage[f"{DOMAIN}.{mock_config_entry.entry_id}"] = {
        "version": 1,
        "key": f"{DOMAIN}.{mock_config_entry.entry_id}",
        "data": {
            "slots": {
                "6": {
                    "name": "Guest",
                    "has_pin": True,
                    "expires": (dt_util.utcnow() - timedelta(days=1)).isoformat(),
                }
            },
            "capabilities": None,
        },
    }
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    # The overdue timer fires on the next loop turn and clears in the background.
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    fake_zha.cluster.command.assert_awaited_once_with(0x07, user_id=6)
    assert mock_config_entry.runtime_data.slots[6]["has_pin"] is False


async def test_permanent_pin_drops_earlier_expiry(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    base = {"config_entry_id": init_integration.entry_id, "slot": 5, "pin_code": "2580"}
    await hass.services.async_call(
        DOMAIN, NimlyService.SET_PIN, {**base, "valid_for": {"hours": 1}}, blocking=True
    )
    await hass.services.async_call(DOMAIN, NimlyService.SET_PIN, base, blocking=True)
    assert init_integration.runtime_data.slots[5]["expires"] is None
    freezer.tick(timedelta(hours=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert fake_zha.cluster.command.await_count == 2  # the two writes, no clear


async def test_expiry_validation(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    base = {"config_entry_id": init_integration.entry_id, "slot": 5, "pin_code": "2580"}
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            NimlyService.SET_PIN,
            {**base, "valid_until": "2000-01-01 10:00:00"},
            blocking=True,
        )
    assert err.value.translation_key == "expiry_in_past"
    with pytest.raises(Exception, match="valid_for|valid_until|exclusion"):
        await hass.services.async_call(
            DOMAIN,
            NimlyService.SET_PIN,
            {**base, "valid_until": "2999-01-01 10:00:00", "valid_for": {"hours": 1}},
            blocking=True,
        )
    fake_zha.cluster.command.assert_not_awaited()


async def test_options_temporary_pin(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "set_pin"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"slot": 3, "pin_code": "1234", "valid_until": "2000-01-01 00:00:00"}
    )
    assert result["errors"] == {"valid_until": "expiry_in_past"}
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"slot": 3, "pin_code": "1234", "valid_until": "2999-06-01 12:00:00"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    expires = dt_util.parse_datetime(init_integration.runtime_data.slots[3]["expires"])
    assert expires == dt_util.as_utc(
        dt_util.parse_datetime("2999-06-01 12:00:00").replace(
            tzinfo=dt_util.get_default_time_zone()
        )
    )


async def test_follows_zha_rebinding_the_device(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    add_device_proxy,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    old = fake_zha.cluster
    new = FakeDoorLockCluster()
    fake_zha.device_proxies[IEEE] = add_device_proxy(new)
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert old.listeners == []
    assert len(new.listeners) == 1
    new.report(0x0100, 0x02020005)
    await hass.async_block_till_done()
    assert hass.states.get(LAST_SOURCE).state == "keypad"

    # The lock leaves ZHA: unavailable; it returns: available again.
    fake_zha.device_proxies.clear()
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(LAST_SOURCE).state == STATE_UNAVAILABLE
    fake_zha.device_proxies[IEEE] = add_device_proxy(new)
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(LAST_SOURCE).state == "keypad"


@pytest.mark.parametrize(("applied", "expected"), [(True, False), (False, True)])
async def test_quirk_missing_issue(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    add_device_proxy,
    mock_zha_setup: None,
    mock_config_entry: MockConfigEntry,
    applied: bool,
    expected: bool,
) -> None:
    fake_zha.device_proxies[IEEE] = add_device_proxy(fake_zha.cluster, quirk_applied=applied)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    issue = ir.async_get(hass).async_get_issue(
        DOMAIN, f"quirk_missing_{mock_config_entry.entry_id}"
    )
    assert (issue is not None) is expected


async def test_remove_config_entry_device(
    hass: HomeAssistant, init_integration: MockConfigEntry, device_registry: dr.DeviceRegistry
) -> None:
    [own] = dr.async_entries_for_config_entry(device_registry, init_integration.entry_id)
    assert not await async_remove_config_entry_device(hass, init_integration, own)
    stale = device_registry.async_get_or_create(
        config_entry_id=init_integration.entry_id, identifiers={(DOMAIN, "old")}
    )
    assert await async_remove_config_entry_device(hass, init_integration, stale)


async def test_expiry_clears_even_after_reserved_slots_raised(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """A code Home Assistant wrote must expire even if its slot became reserved."""
    hass.config_entries.async_update_entry(init_integration, options={"reserved_slots": 1})
    manager = init_integration.runtime_data
    await manager.async_set_pin(2, "1357", expires=dt_util.utcnow() + timedelta(minutes=5))
    hass.config_entries.async_update_entry(init_integration, options={"reserved_slots": 3})
    freezer.tick(timedelta(minutes=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    fake_zha.cluster.command.assert_awaited_with(0x07, user_id=2)
    assert manager.slots == {}


async def test_refused_expiry_raises_repair_issue(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    manager = init_integration.runtime_data
    await manager.async_set_pin(5, "1357", "Guest", dt_util.utcnow() + timedelta(minutes=1))
    fake_zha.cluster.command = AsyncMock(return_value=SimpleNamespace(status=1))
    issue_id = f"expired_pin_not_cleared_{init_integration.entry_id}_5"
    issues = ir.async_get(hass)

    freezer.tick(timedelta(minutes=2))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert issues.async_get_issue(DOMAIN, issue_id) is None  # one refusal may be a blip

    freezer.tick(timedelta(minutes=11))  # first retry after 10 minutes
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    issue = issues.async_get_issue(DOMAIN, issue_id)
    assert issue is not None
    assert issue.translation_placeholders["name"] == "Guest"

    fake_zha.cluster.command = AsyncMock(return_value=None)
    freezer.tick(timedelta(minutes=21))  # then after 20: the delay doubles
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert issues.async_get_issue(DOMAIN, issue_id) is None
    assert manager.slots[5]["has_pin"] is False


async def test_discovery_confirm_after_reconfigure_aborts(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    add_device_proxy,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    fake_zha.device_proxies[IEEE2] = add_device_proxy(FakeDoorLockCluster())
    _announce_device(hass, device_registry, IEEE2)
    await hass.async_block_till_done()
    [discovery] = hass.config_entries.flow.async_progress_by_handler(DOMAIN)

    result = await init_integration.start_reconfigure_flow(hass)
    await hass.config_entries.flow.async_configure(result["flow_id"], {"ieee": IEEE2})
    await hass.async_block_till_done()

    assert init_integration.unique_id == IEEE2
    result = await hass.config_entries.flow.async_configure(discovery["flow_id"], {})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_rebind_without_event_hook_reports_once(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    add_device_proxy,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
    caplog: pytest.LogCaptureFixture,
) -> None:
    fake_zha.device_proxies[IEEE] = add_device_proxy(SimpleNamespace())
    for _ in range(3):
        freezer.tick(timedelta(seconds=61))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    assert caplog.text.count("Cannot listen to lock") == 1
    issue_id = f"zha_internals_{init_integration.entry_id}"
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is not None
    assert hass.states.get(LAST_SOURCE).state == STATE_UNAVAILABLE

    fake_zha.device_proxies[IEEE] = add_device_proxy(FakeDoorLockCluster())
    freezer.tick(timedelta(seconds=61))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None
    assert hass.states.get(LAST_SOURCE).state != STATE_UNAVAILABLE
