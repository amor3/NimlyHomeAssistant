"""Key tags, fingerprints, keypad programming and device triggers."""

from __future__ import annotations

import pytest
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_get_device_automations,
    async_mock_service,
)

from custom_components.nimly_digital_lock.const import DOMAIN, NimlyService
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.const import STATE_OFF, STATE_ON, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from .conftest import FakeZha

KEYPAD = "switch.nimlypro_activity_keypad_programming"


def _custom(fake_zha: FakeZha) -> list[tuple[int, dict[str, int]]]:
    """(command id, fields) of every module command sent through request()."""
    return [
        (c.args[1], {k: v for k, v in c.kwargs.items() if k != "expect_reply"})
        for c in fake_zha.cluster.request.await_args_list
    ]


@pytest.mark.parametrize(("kind", "command"), [("rfid", 0x70), ("fingerprint", 0x71)])
async def test_enroll(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry, kind, command
) -> None:
    await hass.services.async_call(
        DOMAIN, NimlyService.ENROLL_CREDENTIAL, {"slot": 5, "credential": kind}, blocking=True
    )
    assert _custom(fake_zha) == [(command, {"user_id": 5})]
    assert fake_zha.cluster.request.await_args.kwargs["expect_reply"] is False


async def test_remove(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    await hass.services.async_call(
        DOMAIN, NimlyService.REMOVE_CREDENTIAL, {"slot": 900, "credential": "rfid"}, blocking=True
    )
    # The standard Clear RFID Code command.
    fake_zha.cluster.command.assert_awaited_with(0x18, user_id=900)
    await hass.services.async_call(
        DOMAIN,
        NimlyService.REMOVE_CREDENTIAL,
        {"slot": 150, "credential": "fingerprint"},
        blocking=True,
    )
    assert _custom(fake_zha) == [(0x72, {"user_id": 150})]


async def test_credential_slot_limits(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    for data in ({"slot": 1, "credential": "rfid"}, {"slot": 200, "credential": "fingerprint"}):
        with pytest.raises(ServiceValidationError):
            await hass.services.async_call(
                DOMAIN, NimlyService.ENROLL_CREDENTIAL, data, blocking=True
            )
    fake_zha.cluster.request.assert_not_awaited()


async def test_options_enroll(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "enroll_credential"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"credential": "fingerprint", "slot": 150}
    )
    assert result["step_id"] == "enroll_started"
    assert result["description_placeholders"] == {"slot": "150", "kind": "fingerprint"}
    result = await hass.config_entries.options.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY

    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "remove_credential"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"credential": "fingerprint", "slot": 300}
    )
    assert result["errors"] == {"slot": "slot_out_of_range"}


async def test_keypad_programming_switch(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    state = hass.states.get(KEYPAD)
    assert state.state == STATE_UNKNOWN
    assert state.attributes["assumed_state"] is True
    await hass.services.async_call("switch", "turn_off", {"entity_id": KEYPAD}, blocking=True)
    assert _custom(fake_zha) == [(0x73, {})]
    assert hass.states.get(KEYPAD).state == STATE_OFF
    await hass.services.async_call("switch", "turn_on", {"entity_id": KEYPAD}, blocking=True)
    assert _custom(fake_zha)[-1] == (0x74, {})
    # The lock cannot be asked: the last command sent is kept over a reload.
    await hass.config_entries.async_reload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert hass.states.get(KEYPAD).state == STATE_ON


async def test_device_triggers(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    init_integration: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    [device] = dr.async_entries_for_config_entry(device_registry, init_integration.entry_id)
    triggers = await async_get_device_automations(hass, DeviceAutomationType.TRIGGER, device.id)
    types = {t["type"] for t in triggers if t["domain"] == DOMAIN}
    assert {"unlocked_keypad", "auto_relocked", "locked", "unlocked"} <= types

    calls = async_mock_service(hass, "test", "automation")
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": [
                {
                    "triggers": [
                        {
                            "trigger": "device",
                            "domain": DOMAIN,
                            "device_id": device.id,
                            "type": kind,
                        }
                    ],
                    "actions": [{"action": "test.automation", "data": {"kind": kind}}],
                }
                for kind in ("unlocked_keypad", "locked", "auto_relocked")
            ]
        },
    )
    fake_zha.cluster.report(0x0100, 0x02020005)  # keypad unlock
    fake_zha.cluster.report(0x0100, 0x0A010000)  # auto relock (system)
    await hass.async_block_till_done()
    assert sorted(c.data["kind"] for c in calls) == ["auto_relocked", "unlocked_keypad"]


async def test_unlocked_remotely_trigger_on_any_source(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    mock_zha_setup: None,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry,
) -> None:
    """Code Pro answers a command from Home Assistant with source 0x05."""
    from .test_zha import _zha_lock  # noqa: PLC0415

    _, lock_entity_id = _zha_lock(hass, device_registry, entity_registry)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    [device] = dr.async_entries_for_config_entry(device_registry, mock_config_entry.entry_id)
    calls = async_mock_service(hass, "test", "automation")
    async_mock_service(hass, "lock", "unlock")
    assert await async_setup_component(
        hass,
        "automation",
        {
            "automation": {
                "triggers": [
                    {
                        "trigger": "device",
                        "domain": DOMAIN,
                        "device_id": device.id,
                        "type": "unlocked_remotely",
                    }
                ],
                "actions": [{"action": "test.automation"}],
            }
        },
    )
    fake_zha.cluster.report(0x0100, 0x05020000)  # not after a command: not remote
    await hass.services.async_call("lock", "unlock", {"entity_id": lock_entity_id}, blocking=True)
    fake_zha.cluster.report(0x0100, 0x05020000)
    await hass.async_block_till_done()
    assert len(calls) == 1
