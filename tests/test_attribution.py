"""Tests for who gets credited, credential names, missing reports and targeting."""

from __future__ import annotations

from datetime import timedelta

from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    MockUser,
    async_capture_events,
    async_fire_time_changed,
    async_mock_service,
)

from custom_components.nimly_digital_lock.const import DOMAIN, EVENT_LOCK_ACTIVITY, NimlyService
from custom_components.nimly_digital_lock.zha import find_zha_device
from homeassistant.core import Context, HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr, entity_registry as er, issue_registry as ir

from .conftest import IEEE, FakeDoorLockCluster, FakeZha
from .test_zha import _zha_lock

ACTIVITY = "event.front_door_activity_activity"
LAST_USER = "sensor.front_door_activity_last_user"


@pytest.fixture
async def zha_lock_setup(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    mock_zha_setup: None,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> tuple[MockConfigEntry, str]:
    """The integration set up next to ZHA's device and lock entity."""
    _, lock_entity_id = _zha_lock(hass, device_registry, entity_registry)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry, lock_entity_id


async def test_unlock_from_home_assistant_credits_user(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    zha_lock_setup: tuple[MockConfigEntry, str],
    hass_admin_user: MockUser,
) -> None:
    _, lock_entity_id = zha_lock_setup
    async_mock_service(hass, "lock", "unlock")
    events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    context = Context(user_id=hass_admin_user.id)

    await hass.services.async_call(
        "lock", "unlock", {"entity_id": lock_entity_id}, blocking=True, context=context
    )
    await hass.async_block_till_done(wait_background_tasks=True)
    fake_zha.cluster.report(0x0100, 0x00020000)  # Zigbee unlock, no slot
    await hass.async_block_till_done()

    [event] = events
    assert event.data["ha_user"] == hass_admin_user.name
    assert event.data["system"] is False
    assert event.context is context
    assert hass.states.get(LAST_USER).state == hass_admin_user.name
    activity = hass.states.get(ACTIVITY)
    assert activity.attributes["ha_user"] == hass_admin_user.name
    assert activity.context.user_id == hass_admin_user.id

    # Used once: the next Zigbee report is not credited again.
    fake_zha.cluster.report(0x0100, 0x00020000)
    await hass.async_block_till_done()
    assert events[1].data["ha_user"] is None


async def test_remote_command_matches_action_and_window(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    zha_lock_setup: tuple[MockConfigEntry, str],
    hass_admin_user: MockUser,
    freezer: FrozenDateTimeFactory,
) -> None:
    entry, lock_entity_id = zha_lock_setup
    async_mock_service(hass, "lock", "unlock")
    events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    context = Context(user_id=hass_admin_user.id)
    await hass.services.async_call(
        "lock", "unlock", {"entity_id": lock_entity_id}, blocking=True, context=context
    )
    await hass.async_block_till_done(wait_background_tasks=True)

    # A lock is not the answer to an unlock (Code Pro reports auto relock
    # as an unattributed lock).
    fake_zha.cluster.report(0x0100, 0x05010000)
    await hass.async_block_till_done()
    assert events[-1].data["ha_user"] is None
    assert events[-1].data["system"] is True

    # Too late is not the answer either.
    entry.runtime_data._remote = entry.runtime_data._remote.__class__(  # noqa: SLF001
        entry.runtime_data._remote.action,  # noqa: SLF001
        entry.runtime_data._remote.at - 60,  # noqa: SLF001
        context,
        hass_admin_user.name,
    )
    fake_zha.cluster.report(0x0100, 0x00020000)
    await hass.async_block_till_done()
    assert events[-1].data["ha_user"] is None


async def test_automation_lock_keeps_context_without_user(
    hass: HomeAssistant, fake_zha: FakeZha, zha_lock_setup: tuple[MockConfigEntry, str]
) -> None:
    _, lock_entity_id = zha_lock_setup
    async_mock_service(hass, "lock", "lock")
    events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    context = Context()  # as an automation's call has, with no user
    await hass.services.async_call(
        "lock", "lock", {"entity_id": lock_entity_id}, blocking=True, context=context
    )
    fake_zha.cluster.report(0x0100, 0x00010000)
    await hass.async_block_till_done()
    assert events[0].context is context
    assert events[0].data["ha_user"] is None
    assert events[0].data["system"] is False


async def test_credential_names(
    hass: HomeAssistant, fake_zha: FakeZha, zha_lock_setup: tuple[MockConfigEntry, str]
) -> None:
    entry, _ = zha_lock_setup
    base = {"config_entry_id": entry.entry_id, "slot": 5}
    await hass.services.async_call(
        DOMAIN, NimlyService.SET_SLOT_NAME, {**base, "name": "Anna"}, blocking=True
    )
    await hass.services.async_call(
        DOMAIN,
        NimlyService.SET_SLOT_NAME,
        {**base, "name": "Bo", "credential": "fingerprint"},
        blocking=True,
    )
    events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    for raw in (0x02020005, 0x03020005, 0x04020005):  # keypad, fingerprint, tag
        fake_zha.cluster.report(0x0100, raw)
    await hass.async_block_till_done()
    assert [e.data["user"] for e in events] == ["Anna", "Bo", "Anna"]
    assert hass.states.get(LAST_USER).state == "Anna"

    await hass.services.async_call(
        DOMAIN,
        NimlyService.SET_SLOT_NAME,
        {**base, "name": "", "credential": "fingerprint"},
        blocking=True,
    )
    await hass.services.async_call(
        DOMAIN, NimlyService.SET_SLOT_NAME, {**base, "name": ""}, blocking=True
    )
    assert entry.runtime_data.slots == {}


async def test_palm_lock_and_master_unlock(
    hass: HomeAssistant, fake_zha: FakeZha, zha_lock_setup: tuple[MockConfigEntry, str]
) -> None:
    entry, _ = zha_lock_setup
    entry.runtime_data.set_slot_name(0, "Master")
    fake_zha.cluster.report(0x0100, 0x02020000)  # master code unlock
    await hass.async_block_till_done()
    assert hass.states.get(LAST_USER).state == "Master"
    entry.runtime_data.set_slot_name(4, "Anna")
    fake_zha.cluster.report(0x0100, 0x02020004)
    fake_zha.cluster.report(0x0100, 0x02010000)  # palm lock from outside
    await hass.async_block_till_done()
    assert hass.states.get(LAST_USER).state == "Anna"


async def test_missing_operation_reports_raise_issue(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    issue_id = f"events_missing_{init_integration.entry_id}"
    issues = ir.async_get(hass)
    fake_zha.cluster.report(0x0000, 1)
    for state in (2, 2, 1, 2):  # a repeated value is no change
        fake_zha.cluster.report(0x0000, state)
        freezer.tick(timedelta(seconds=16))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    assert init_integration.runtime_data.missed_reports == 3
    assert issues.async_get_issue(DOMAIN, issue_id) is not None

    fake_zha.cluster.report(0x0000, 1)
    fake_zha.cluster.report(0x0100, 0x02010004)
    await hass.async_block_till_done()
    assert init_integration.runtime_data.missed_reports == 0
    assert issues.async_get_issue(DOMAIN, issue_id) is None


async def test_report_in_time_is_not_missed(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    fake_zha.cluster.report(0x0000, 1)
    for _ in range(4):
        fake_zha.cluster.report(0x0000, 2)
        fake_zha.cluster.report(0x0100, 0x02020004)
        fake_zha.cluster.report(0x0000, 1)
        fake_zha.cluster.report(0x0100, 0x0A010000)
        freezer.tick(timedelta(seconds=16))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    assert init_integration.runtime_data.missed_reports == 0


async def test_target_by_device_or_single_lock(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    add_device_proxy,
    zha_lock_setup: tuple[MockConfigEntry, str],
    device_registry: dr.DeviceRegistry,
) -> None:
    entry, _ = zha_lock_setup
    [ours] = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    zha_device = find_zha_device(hass, IEEE)
    assert zha_device is not None

    for target in ({"device_id": ours.id}, {"device_id": zha_device.id}, {}):
        await hass.services.async_call(
            DOMAIN,
            NimlyService.SET_SLOT_NAME,
            {**target, "slot": 7, "name": "Cleaner"},
            blocking=True,
        )
    assert entry.runtime_data.slot_name(7) == "Cleaner"

    # With a second lock, a call naming neither is refused.
    ieee2 = "f4:ce:36:aa:bb:cc:dd:ee"
    fake_zha.device_proxies[ieee2] = add_device_proxy(FakeDoorLockCluster())
    second = MockConfigEntry(domain=DOMAIN, unique_id=ieee2, version=2, data={"ieee": ieee2})
    second.add_to_hass(hass)
    await hass.config_entries.async_setup(second.entry_id)
    await hass.async_block_till_done()
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN, NimlyService.SET_SLOT_NAME, {"slot": 7, "name": "x"}, blocking=True
        )
    assert err.value.translation_key == "lock_required"
    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(
            DOMAIN,
            NimlyService.SET_SLOT_NAME,
            {"device_id": "nope", "slot": 7, "name": "x"},
            blocking=True,
        )
    assert err.value.translation_key == "entry_not_found"


async def test_options_name_slot_per_credential(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "name_slot"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"slot": 150, "name": "Anna", "credential": "fingerprint"}
    )
    manager = init_integration.runtime_data
    assert manager.slot_name(150, "fingerprint") == "Anna"
    assert manager.slot_name(150, "pin") is None


async def test_reconfigure_same_module_does_not_reload(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    manager = init_integration.runtime_data
    result = await init_integration.start_reconfigure_flow(hass)
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"ieee": IEEE})
    await hass.async_block_till_done()
    assert result["reason"] == "reconfigure_successful"
    assert init_integration.runtime_data is manager


async def test_lock_reported_as_auto_is_credited(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    zha_lock_setup: tuple[MockConfigEntry, str],
    hass_admin_user: MockUser,
) -> None:
    """NimlyPRO may answer a lock from the app with source 0x0A."""
    _, lock_entity_id = zha_lock_setup
    async_mock_service(hass, "lock", "lock")
    events = async_capture_events(hass, EVENT_LOCK_ACTIVITY)
    await hass.services.async_call(
        "lock",
        "lock",
        {"entity_id": lock_entity_id},
        blocking=True,
        context=Context(user_id=hass_admin_user.id),
    )
    fake_zha.cluster.report(0x0100, 0x0A010000)
    fake_zha.cluster.report(0x0100, 0x0A010000)  # a later one is auto relock again
    await hass.async_block_till_done()
    assert events[0].data["ha_user"] == hass_admin_user.name
    assert events[0].data["system"] is False
    assert events[1].data["ha_user"] is None
    assert events[1].data["system"] is True


async def test_removing_entry_removes_its_issues(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    fake_zha.cluster.report(0x0000, 1)
    for state in (2, 1, 2):
        fake_zha.cluster.report(0x0000, state)
        freezer.tick(timedelta(seconds=16))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
    issue_id = f"events_missing_{init_integration.entry_id}"
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is not None
    await hass.config_entries.async_remove(init_integration.entry_id)
    await hass.async_block_till_done()
    assert ir.async_get(hass).async_get_issue(DOMAIN, issue_id) is None
