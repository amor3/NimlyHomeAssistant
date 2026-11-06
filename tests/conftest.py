"""Fixtures for Nimly Digital Lock tests: a fake ZHA gateway with one lock."""

from __future__ import annotations

from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.nimly_digital_lock.const import CONF_IEEE, CONF_MODEL, DOMAIN, MANUFACTURER
from homeassistant.core import HomeAssistant

IEEE = "f4:ce:36:0a:04:4d:31:f5"
MODEL = "NimlyPRO"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations: None) -> None:
    """Load the integration from custom_components."""


@pytest.fixture(autouse=True)
def no_retry_delay() -> Generator[None]:
    """Retries without waiting."""
    with patch("custom_components.nimly_digital_lock.zha.SEND_RETRY_DELAY_S", 0):
        yield


@dataclass
class FakeDoorLockCluster:
    """The parts of a zigpy Door Lock cluster the integration uses."""

    command: AsyncMock = field(default_factory=lambda: AsyncMock(return_value=None))
    read_attributes: AsyncMock = field(
        default_factory=lambda: AsyncMock(return_value=({0x0012: 50, 0x0017: 8, 0x0018: 4}, {}))
    )
    listeners: list[Callable[[Any], None]] = field(default_factory=list)

    def on_event(self, name: str, callback: Callable[[Any], None]) -> Callable[[], None]:
        assert name == "attribute_report"
        self.listeners.append(callback)
        return lambda: self.listeners.remove(callback)

    def report(self, attribute_id: int, value: Any) -> None:
        """Deliver an attribute report as zigpy would."""
        event = SimpleNamespace(attribute_id=attribute_id, raw_value=value, value=value)
        for callback in list(self.listeners):
            callback(event)


def _device_proxy(
    cluster: Any,
    manufacturer: str = MANUFACTURER,
    model: str = MODEL,
    quirk_applied: bool = True,
) -> Any:
    endpoint = SimpleNamespace(in_clusters={0x0101: cluster} if cluster else {})
    zigpy_device = SimpleNamespace(endpoints={0: SimpleNamespace(in_clusters={}), 11: endpoint})
    zha_device = SimpleNamespace(
        manufacturer=manufacturer,
        model=model,
        device=zigpy_device,
        quirk_applied=quirk_applied,
        quirk_class="zhaquirks.nimly.lock:NimlyPRO" if quirk_applied else "zigpy.device.Device",
    )
    return SimpleNamespace(device=zha_device)


@dataclass
class FakeZha:
    """A fake ZHA gateway proxy and the lock in it."""

    cluster: FakeDoorLockCluster
    device_proxies: dict[str, Any]
    running: bool = True


@pytest.fixture
def fake_zha() -> Generator[FakeZha]:
    """ZHA with one paired Nimly lock."""
    cluster = FakeDoorLockCluster()
    zha = FakeZha(cluster=cluster, device_proxies={IEEE: _device_proxy(cluster)})

    def _get_proxy(hass: HomeAssistant) -> Any:
        if not zha.running:
            raise ValueError("No gateway object exists")
        return SimpleNamespace(device_proxies=zha.device_proxies)

    with patch(
        "custom_components.nimly_digital_lock.zha.get_zha_gateway_proxy",
        side_effect=_get_proxy,
    ):
        yield zha


@pytest.fixture
def add_device_proxy() -> Callable[..., Any]:
    """Build a device proxy for extra devices in a test."""
    return _device_proxy


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """A config entry for the lock."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="NimlyPRO (31F5)",
        unique_id=IEEE,
        version=2,
        data={CONF_IEEE: IEEE, CONF_MODEL: MODEL},
    )


@pytest.fixture
def mock_zha_setup() -> Generator[None]:
    """Skip setting up the real ZHA integration, a manifest dependency."""
    with patch("homeassistant.components.zha.async_setup", return_value=True):
        yield


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    mock_zha_setup: None,
    mock_config_entry: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the integration with the fake lock."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
