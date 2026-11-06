"""Tests for diagnostics."""

from __future__ import annotations

from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.components.diagnostics import (
    get_diagnostics_for_config_entry,
)

from custom_components.nimly_digital_lock.const import DOMAIN
from homeassistant.core import HomeAssistant

from .conftest import IEEE, FakeZha


async def test_diagnostics_redacted(
    hass: HomeAssistant, hass_client, fake_zha: FakeZha, init_integration: MockConfigEntry
) -> None:
    await hass.services.async_call(
        DOMAIN,
        "set_pin",
        {
            "config_entry_id": init_integration.entry_id,
            "slot": 4,
            "pin_code": "135790",
            "name": "Bo",
        },
        blocking=True,
    )
    fake_zha.cluster.report(0x0100, 0x02020004)
    await hass.async_block_till_done()

    diagnostics = await get_diagnostics_for_config_entry(hass, hass_client, init_integration)
    text = str(diagnostics)
    assert IEEE not in text
    assert "Bo" not in text
    assert "135790" not in text
    assert diagnostics["listening"] is True
    assert diagnostics["slots"] == {"4": {"named": True, "has_pin": True}}
    assert diagnostics["last_event"]["source"] == "keypad"
    assert diagnostics["zha"]["has_on_event"] is True
