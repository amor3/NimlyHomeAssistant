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


@pytest.fixture(autouse=True)
def repeated_reports(request: pytest.FixtureRequest) -> Generator[None]:
    """Tests send the same report in quick succession; a test marked
    repeated_reports keeps the filter that drops repeats."""
    if request.node.get_closest_marker("repeated_reports"):
        yield
        return
    with patch("custom_components.nimly_digital_lock.manager.DUPLICATE_REPORT_S", 0):
        yield


@dataclass
class FakeDoorLockCluster:
    """The parts of a zigpy Door Lock cluster the integration uses."""

    command: AsyncMock = field(default_factory=lambda: AsyncMock(return_value=None))
    # What a read answers: 50 PIN users, 8 and 4 digits, auto relock on,
    # volume normal.
    values: dict[int, Any] = field(
        default_factory=lambda: {0x0012: 50, 0x0017: 8, 0x0018: 4, 0x0023: 1, 0x0024: 2}
    )
    read_attributes: AsyncMock = field(default_factory=AsyncMock)
    listeners: list[Callable[[Any], None]] = field(default_factory=list)

    # The module's own commands go out through request().
    request: AsyncMock = field(default_factory=lambda: AsyncMock(return_value=None))
    write_attributes: AsyncMock = field(
        default_factory=lambda: AsyncMock(return_value=[[SimpleNamespace(status=0)]])
    )

    def __post_init__(self) -> None:
        # Unless a test scripted the read, answer from the value table.
        mock = self.read_attributes
        if mock.side_effect is None and not isinstance(mock.return_value, tuple):
            mock.side_effect = lambda ids, **_: (
                {i: self.values[i] for i in ids if i in self.values},
                {},
            )

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
    power: Any = None,
) -> Any:
    in_clusters = {0x0101: cluster} if cluster else {}
    if power is not None:
        in_clusters[0x0001] = power
    endpoint = SimpleNamespace(in_clusters=in_clusters)
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
    power: FakeDoorLockCluster
    running: bool = True


@pytest.fixture
def fake_zha() -> Generator[FakeZha]:
    """ZHA with one paired Nimly lock."""
    cluster = FakeDoorLockCluster()
    power = FakeDoorLockCluster(values={0x0021: 87})
    zha = FakeZha(
        cluster=cluster,
        device_proxies={IEEE: _device_proxy(cluster, power=power)},
        power=power,
    )

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


@pytest.fixture(autouse=True)
def no_deprecated_usage(caplog: pytest.LogCaptureFixture) -> Generator[None]:
    """Fail a test in which Home Assistant reports deprecated use by us."""
    yield
    reports = [
        record.getMessage()
        for phase in ("setup", "call")
        for record in caplog.get_records(phase)
        if "Detected that custom integration 'nimly_digital_lock'" in record.getMessage()
    ]
    assert not reports, reports


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "zha_features(*features): what ZHA shows for the lock (default: all)"
    )
    config.addinivalue_line("markers", "real_zha_features: detect from the entity registry")
    config.addinivalue_line("markers", "repeated_reports: keep dropping repeated event reports")


@pytest.fixture(autouse=True)
def zha_features(request: pytest.FixtureRequest) -> Generator[set[str]]:
    """ZHA's quirk works unless a test says otherwise, so no fallbacks are made."""
    from custom_components.nimly_digital_lock.const import FALLBACK_FEATURES  # noqa: PLC0415

    marker = request.node.get_closest_marker("zha_features")
    features = set(marker.args) if marker else set(FALLBACK_FEATURES)
    if request.node.get_closest_marker("real_zha_features"):
        yield features
        return
    with patch("custom_components.nimly_digital_lock.zha_features", return_value=features):
        yield features
