"""Tests for the config and options flows."""

from __future__ import annotations

from unittest.mock import AsyncMock

from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nimly_digital_lock.const import (
    CONF_RESERVED_SLOTS,
    CONF_WAKE_WITH_LOCK,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IGNORE, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import IEEE, MODEL, FakeZha


async def test_user_flow(
    hass: HomeAssistant, fake_zha: FakeZha, mock_zha_setup: None, add_device_proxy
) -> None:
    # A non-Nimly Zigbee device is not offered.
    fake_zha.device_proxies["00:11:22:33:44:55:66:77"] = add_device_proxy(
        object(), manufacturer="IKEA of Sweden", model="TRADFRI bulb"
    )
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.FORM
    options = result["data_schema"].schema["ieee"].config["options"]
    assert [option["value"] for option in options] == [IEEE]

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"ieee": IEEE})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "NimlyPRO (31F5)"
    assert result["data"] == {"ieee": IEEE, "model": MODEL}
    assert result["result"].unique_id == IEEE


async def test_user_flow_zha_not_running(hass: HomeAssistant, fake_zha: FakeZha) -> None:
    fake_zha.running = False
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "zha_not_running"


async def test_user_flow_no_unconfigured_locks(
    hass: HomeAssistant, fake_zha: FakeZha, mock_config_entry: MockConfigEntry
) -> None:
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_locks"


async def test_options_settings(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    assert result["type"] is FlowResultType.MENU
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "settings"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {CONF_RESERVED_SLOTS: 1, CONF_WAKE_WITH_LOCK: True}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert init_integration.options == {CONF_RESERVED_SLOTS: 1, CONF_WAKE_WITH_LOCK: True}
    manager = init_integration.runtime_data
    assert manager.first_user_slot == 1
    assert manager.transport.wake_with_lock is True


async def test_options_set_and_clear_pin(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "set_pin"}
    )
    # The slot selector starts at the first user slot, so master slots
    # cannot be picked; a too short code is refused before sending.
    assert result["data_schema"].schema["slot"].config["min"] == 3
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"slot": 3, "name": "Anna", "pin_code": "12"}
    )
    assert result["errors"] == {"pin_code": "invalid_pin"}
    fake_zha.cluster.command.assert_not_awaited()

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"slot": 3, "name": "Anna", "pin_code": "123456"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    fake_zha.cluster.command.assert_awaited_once_with(
        0x05, user_id=3, user_status=1, user_type=0, pin_code="123456"
    )
    assert init_integration.runtime_data.slots == {
        3: {"name": "Anna", "has_pin": True, "expires": None, "names": {}}
    }
    # Nothing about the code is kept in the entry.
    assert "123456" not in str(init_integration.as_dict())

    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "clear_pin"}
    )
    result = await hass.config_entries.options.async_configure(result["flow_id"], {"slot": "3"})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    fake_zha.cluster.command.assert_awaited_with(0x07, user_id=3)
    assert init_integration.runtime_data.slots == {
        3: {"name": "Anna", "has_pin": False, "expires": None, "names": {}}
    }


async def test_options_set_pin_unreachable(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    fake_zha.cluster.command = AsyncMock(side_effect=TimeoutError)
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "set_pin"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"slot": 3, "pin_code": "123456"}
    )
    assert result["errors"] == {"base": "lock_unreachable"}
    assert fake_zha.cluster.command.await_count == 3
    assert init_integration.runtime_data.slots == {}


async def test_options_clear_pin_without_codes(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "clear_pin"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_pin_codes"


async def test_options_name_slot(hass: HomeAssistant, init_integration: MockConfigEntry) -> None:
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "name_slot"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"slot": 0, "name": "Master"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert init_integration.runtime_data.slot_name(0) == "Master"


async def test_options_set_pin_blank_name_keeps_name(
    hass: HomeAssistant, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    init_integration.runtime_data.set_slot_name(5, "Anna")
    result = await hass.config_entries.options.async_init(init_integration.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"next_step_id": "set_pin"}
    )
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {"slot": 5, "name": "  ", "pin_code": "4321"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert init_integration.runtime_data.slots == {
        5: {"name": "Anna", "has_pin": True, "expires": None, "names": {}}
    }


async def test_ignored_lock_can_be_added_by_hand(
    hass: HomeAssistant, fake_zha: FakeZha, mock_zha_setup: None
) -> None:
    MockConfigEntry(domain=DOMAIN, source=SOURCE_IGNORE, unique_id=IEEE, data={}).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": SOURCE_USER})
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {"ieee": IEEE})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    entries = hass.config_entries.async_entries(DOMAIN, include_ignore=True)
    assert [entry.source for entry in entries] == [SOURCE_USER]
