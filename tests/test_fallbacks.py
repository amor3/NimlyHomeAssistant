"""Auto relock, sound volume and battery when ZHA does not show them."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nimly_digital_lock.const import DOMAIN
from custom_components.nimly_digital_lock.zha import zha_features
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import IEEE, FakeZha
from .test_zha import _zha_lock

SWITCH = "switch.nimlypro_activity_auto_relock"
SELECT = "select.nimlypro_activity_sound_volume"
BATTERY = "sensor.nimlypro_activity_battery"


def _entity_id(hass: HomeAssistant, entry: MockConfigEntry, domain: str, key: str) -> str | None:
    return er.async_get(hass).async_get_entity_id(domain, DOMAIN, f"{entry.entry_id}-{key}")


async def test_no_fallbacks_when_zha_shows_everything(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    assert init_integration.runtime_data.fallbacks == frozenset()
    for domain, key in (
        ("switch", "auto_relock"),
        ("select", "sound_volume"),
        ("sensor", "battery"),
    ):
        assert _entity_id(hass, init_integration, domain, key) is None


@pytest.mark.zha_features()
async def test_fallbacks_when_zha_shows_nothing(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    await hass.async_block_till_done(wait_background_tasks=True)
    # Read from the lock at setup.
    assert hass.states.get(SWITCH).state == STATE_ON
    assert hass.states.get(SELECT).state == "normal"
    battery = hass.states.get(BATTERY)
    assert battery.state == "87"
    assert battery.attributes["unit_of_measurement"] == "%"

    # Reports from the lock update them.
    fake_zha.cluster.report(0x0023, 0)
    fake_zha.cluster.report(0x0024, 1)
    fake_zha.power.report(0x0021, 54)
    await hass.async_block_till_done()
    assert hass.states.get(SWITCH).state == STATE_OFF
    assert hass.states.get(SELECT).state == "low"
    assert hass.states.get(BATTERY).state == "54"

    # 0xFF is "unknown": ignored.
    fake_zha.power.report(0x0021, 0xFF)
    await hass.async_block_till_done()
    assert hass.states.get(BATTERY).state == "54"


@pytest.mark.zha_features("battery")
async def test_only_missing_features_are_added(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    assert init_integration.runtime_data.fallbacks == frozenset({"auto_relock", "sound_volume"})
    assert hass.states.get(SWITCH) is not None
    assert hass.states.get(SELECT) is not None
    assert hass.states.get(BATTERY) is None


@pytest.mark.zha_features()
async def test_write_settings(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    await hass.async_block_till_done(wait_background_tasks=True)
    await hass.services.async_call("switch", "turn_off", {"entity_id": SWITCH}, blocking=True)
    fake_zha.cluster.write_attributes.assert_awaited_with({0x0023: 0})
    assert hass.states.get(SWITCH).state == STATE_OFF

    await hass.services.async_call(
        "select", "select_option", {"entity_id": SELECT, "option": "off"}, blocking=True
    )
    fake_zha.cluster.write_attributes.assert_awaited_with({0x0024: 0})
    assert hass.states.get(SELECT).state == "off"


@pytest.mark.zha_features()
@pytest.mark.parametrize(
    ("side_effect", "return_value", "key"),
    [
        (TimeoutError, None, "lock_unreachable"),
        (None, [[SimpleNamespace(status=0x86)]], "lock_rejected"),
    ],
)
async def test_write_failure(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
    side_effect,
    return_value,
    key,
) -> None:
    await hass.async_block_till_done(wait_background_tasks=True)
    fake_zha.cluster.write_attributes = AsyncMock(
        side_effect=side_effect, return_value=return_value
    )
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call("switch", "turn_off", {"entity_id": SWITCH}, blocking=True)
    assert err.value.translation_key == key
    assert hass.states.get(SWITCH).state == STATE_ON


@pytest.mark.zha_features()
async def test_unknown_until_the_lock_answers(
    hass: HomeAssistant, fake_zha: FakeZha, mock_zha_setup: None, mock_config_entry: MockConfigEntry
) -> None:
    fake_zha.cluster.values.clear()
    fake_zha.power.values.clear()
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert hass.states.get(SWITCH).state == STATE_UNKNOWN
    assert hass.states.get(SELECT).state == STATE_UNKNOWN
    assert hass.states.get(BATTERY).state == STATE_UNKNOWN


async def test_fallbacks_removed_once_zha_shows_them(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    mock_zha_setup: None,
    mock_config_entry: MockConfigEntry,
    zha_features: set[str],
) -> None:
    zha_features.clear()
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert _entity_id(hass, mock_config_entry, "switch", "auto_relock") is not None

    # The quirk works again (say after an update): no doubles left behind.
    zha_features.update({"auto_relock", "sound_volume", "battery"})
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    for domain, key in (
        ("switch", "auto_relock"),
        ("select", "sound_volume"),
        ("sensor", "battery"),
    ):
        assert _entity_id(hass, mock_config_entry, domain, key) is None


@pytest.mark.real_zha_features
async def test_detect_features_from_zha_entities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    zha_entry, _ = _zha_lock(hass, device_registry, entity_registry)
    [device] = dr.async_entries_for_config_entry(device_registry, zha_entry.entry_id)
    assert zha_features(hass, IEEE) == set()

    entity_registry.async_get_or_create(
        "switch",
        "zha",
        f"{IEEE}-11-257-auto_relock_time",
        config_entry=zha_entry,
        device_id=device.id,
        translation_key="auto_relock",
    )
    assert zha_features(hass, IEEE) == {"auto_relock"}
    # A voltage sensor is not the battery level.
    entity_registry.async_get_or_create(
        "sensor",
        "zha",
        f"{IEEE}-11-1-battery_voltage",
        config_entry=zha_entry,
        device_id=device.id,
        original_device_class="voltage",
    )
    assert zha_features(hass, IEEE) == {"auto_relock"}
    entity_registry.async_get_or_create(
        "number",
        "zha",
        f"{IEEE}-11-257-sound_volume",
        config_entry=zha_entry,
        device_id=device.id,
        disabled_by=er.RegistryEntryDisabler.USER,  # turned off still counts
    )
    entity_registry.async_get_or_create(
        "sensor",
        "zha",
        f"{IEEE}-11-1-battery_percentage_remaining",
        config_entry=zha_entry,
        device_id=device.id,
        original_device_class="battery",
    )
    assert zha_features(hass, IEEE) == {"auto_relock", "sound_volume", "battery"}
