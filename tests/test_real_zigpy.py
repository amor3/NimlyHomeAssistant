"""End to end against real zigpy and ZHA's real Nimly quirk.

Only the radio is faked: the integration talks to a genuine zigpy Door Lock
cluster (with the zhaquirks Nimly quirk applied, as ZHA does), outgoing
frames are captured as bytes, and the lock's answers and reports are fed in
as raw ZCL frames through zigpy's own receive path. This checks the byte
layout against the module specification and that reports reach us the way
the lock sends them, without a manufacturer code.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
import contextvars
from dataclasses import dataclass, field
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry
import zhaquirks
import zigpy.device
import zigpy.endpoint
from zigpy.exceptions import DeliveryError
import zigpy.types as t
from zigpy.zcl import foundation
from zigpy.zdo.types import NodeDescriptor

from custom_components.nimly_digital_lock.const import DOMAIN, NimlyService
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import IEEE, MODEL, FakeZha

LAST_SOURCE = "sensor.nimlypro_activity_last_operated_by"
LAST_USER = "sensor.nimlypro_activity_last_user"

zhaquirks.setup()


def _resolve_quirk(device: zigpy.device.Device) -> Any:
    """Apply quirks as the installed ZHA does."""
    try:
        from zha.quirks import DEVICE_REGISTRY  # noqa: PLC0415 - zha 2.x
    except ImportError:  # zha 0.0.x resolves through zigpy
        import zigpy.quirks  # noqa: PLC0415

        return zigpy.quirks.get_device(device)
    return DEVICE_REGISTRY.resolve(device)


@dataclass
class RealLock:
    """A quirked zigpy lock whose radio is scripted by the test."""

    device: Any
    cluster: Any
    sent: list[bytes] = field(default_factory=list)
    # command id -> payload bytes of the lock's answer (after the ZCL header);
    # None means the lock never answers.
    answers: dict[int, bytes | None] = field(default_factory=dict)
    fail_delivery: int = 0

    def frame(self, payload: bytes) -> None:
        """Deliver a ZCL frame from the lock."""
        self.device.packet_received(
            t.ZigbeePacket(
                src=t.AddrModeAddress(addr_mode=t.AddrMode.NWK, address=0x1234),
                src_ep=11,
                dst=t.AddrModeAddress(addr_mode=t.AddrMode.NWK, address=0x0000),
                dst_ep=11,
                profile_id=0x0104,
                cluster_id=0x0101,
                data=t.SerializableBytes(payload),
                lqi=255,
                rssi=-60,
            )
        )

    def report(self, attribute_id: int, zcl_type: int, value: bytes) -> None:
        """An attribute report as the lock sends it: no manufacturer code."""
        self.frame(
            bytes([0x18, 0x42, 0x0A])  # server to client, disable default rsp
            + attribute_id.to_bytes(2, "little")
            + bytes([zcl_type])
            + value
        )


@pytest.fixture
def real_lock() -> RealLock:
    app = MagicMock()
    app.get_sequence = MagicMock(side_effect=iter(range(1, 250)))
    app._packet_priority_var = contextvars.ContextVar("priority", default=t.PacketPriority.NORMAL)
    device = zigpy.device.Device(app, t.EUI64.convert(IEEE), 0x1234)
    endpoint = device.add_endpoint(11)
    endpoint.status = zigpy.endpoint.Status.ZDO_INIT
    endpoint.profile_id = 0x0104
    endpoint.device_type = 0x000A
    for cluster_id in (0x0000, 0x0001, 0x0003, 0x0101):
        endpoint.add_input_cluster(cluster_id)
    device.manufacturer = "Onesti Products AS"
    device.model = MODEL
    device.node_desc = NodeDescriptor(logical_type=2, mac_capability_flags=0x80)
    quirked = _resolve_quirk(device)
    lock = RealLock(quirked, quirked.endpoints[11].in_clusters[0x0101])
    assert type(lock.cluster).__name__ == "NimlyDoorLock"

    async def _request(**kwargs: Any) -> None:
        data: bytes = kwargs["data"]
        lock.sent.append(data)
        if lock.fail_delivery:
            lock.fail_delivery -= 1
            raise DeliveryError("no ack from the sleeping lock")
        header, _ = foundation.ZCLHeader.deserialize(data)
        if header.frame_control.is_general:
            if header.command_id == foundation.GeneralCommand.Read_Attributes:
                answer = lock.answers.get(-1)
                if answer is not None:
                    asyncio.get_running_loop().call_soon(
                        lock.frame, bytes([0x18, header.tsn, 0x01]) + answer
                    )
            return
        answer = lock.answers.get(header.command_id, b"\x00")
        if answer is not None:
            asyncio.get_running_loop().call_soon(
                lock.frame, bytes([0x19, header.tsn, header.command_id]) + answer
            )

    app.request = AsyncMock(side_effect=_request)
    return lock


@pytest.fixture
async def real_integration(
    hass: HomeAssistant,
    fake_zha: FakeZha,
    add_device_proxy: Callable[..., Any],
    mock_zha_setup: None,
    mock_config_entry: MockConfigEntry,
    real_lock: RealLock,
) -> MockConfigEntry:
    """The integration set up on the real cluster."""
    # Capability read at setup: 50 PIN users, 8 and 4 digits.
    real_lock.answers[-1] = (
        bytes.fromhex("120000213200") + bytes.fromhex("1700002008") + bytes.fromhex("1800002004")
    )
    fake_zha.device_proxies[IEEE] = add_device_proxy(real_lock.cluster)
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done(wait_background_tasks=True)
    return mock_config_entry


async def test_capabilities_from_real_read(
    hass: HomeAssistant, real_integration: MockConfigEntry
) -> None:
    assert real_integration.runtime_data.capabilities == {
        "num_pin_users": 50,
        "max_pin_length": 8,
        "min_pin_length": 4,
    }


async def test_set_pin_bytes_match_the_specification(
    hass: HomeAssistant, real_integration: MockConfigEntry, real_lock: RealLock
) -> None:
    """Spec example: slot 6, PIN 123456 -> 0600 .. .. 06 313233343536."""
    real_lock.sent.clear()
    await hass.services.async_call(
        DOMAIN, NimlyService.SET_PIN, {"slot": 6, "pin_code": "123456"}, blocking=True
    )
    [frame] = real_lock.sent
    header, payload = foundation.ZCLHeader.deserialize(frame)
    assert header.command_id == 0x05
    assert not header.frame_control.is_manufacturer_specific
    assert payload == bytes.fromhex("0600010006313233343536")
    assert real_integration.runtime_data.slots[6]["has_pin"] is True


async def test_clear_pin_bytes(
    hass: HomeAssistant, real_integration: MockConfigEntry, real_lock: RealLock
) -> None:
    real_lock.sent.clear()
    await hass.services.async_call(DOMAIN, NimlyService.CLEAR_PIN, {"slot": 300}, blocking=True)
    [frame] = real_lock.sent
    header, payload = foundation.ZCLHeader.deserialize(frame)
    assert header.command_id == 0x07
    assert payload == bytes.fromhex("2c01")  # 300, little endian


@pytest.mark.parametrize(
    ("status", "key"),
    [(b"\x01", "lock_rejected"), (b"\x03", "lock_rejected_duplicate")],
)
async def test_lock_refuses_code(
    hass: HomeAssistant,
    real_integration: MockConfigEntry,
    real_lock: RealLock,
    status: bytes,
    key: str,
) -> None:
    real_lock.answers[0x05] = status
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN, NimlyService.SET_PIN, {"slot": 6, "pin_code": "123456"}, blocking=True
        )
    assert err.value.translation_key == key
    assert 6 not in real_integration.runtime_data.slots


async def test_one_failed_delivery_recovers(
    hass: HomeAssistant, real_integration: MockConfigEntry, real_lock: RealLock
) -> None:
    real_lock.fail_delivery = 1
    await hass.services.async_call(
        DOMAIN, NimlyService.SET_PIN, {"slot": 7, "pin_code": "2468"}, blocking=True
    )
    assert real_integration.runtime_data.slots[7]["has_pin"] is True


async def test_persistent_delivery_failure_is_unreachable(
    hass: HomeAssistant, real_integration: MockConfigEntry, real_lock: RealLock
) -> None:
    real_lock.fail_delivery = 100
    with pytest.raises(HomeAssistantError) as err:
        await hass.services.async_call(
            DOMAIN, NimlyService.SET_PIN, {"slot": 7, "pin_code": "2468"}, blocking=True
        )
    assert err.value.translation_key == "lock_unreachable"
    assert 7 not in real_integration.runtime_data.slots


async def test_operation_report_without_manufacturer_code(
    hass: HomeAssistant, real_integration: MockConfigEntry, real_lock: RealLock
) -> None:
    """The frame ZHA's own quirk sensors miss since zigpy 0.91.3."""
    real_integration.runtime_data.set_slot_name(5, "Anna")
    real_lock.report(0x0100, 0x1B, (0x02020005).to_bytes(4, "little"))
    await hass.async_block_till_done()
    assert hass.states.get(LAST_SOURCE).state == "keypad"
    assert hass.states.get(LAST_USER).state == "Anna"


async def test_pin_used_report_is_dropped(
    hass: HomeAssistant, real_integration: MockConfigEntry, real_lock: RealLock, caplog
) -> None:
    real_lock.report(0x0101, 0x41, bytes([0x03, 0x12, 0x34, 0x56]))  # BCD 123456
    real_lock.report(0x0100, 0x1B, (0x02020005).to_bytes(4, "little"))
    await hass.async_block_till_done()
    assert "123456" not in caplog.text
    assert hass.states.get(LAST_SOURCE).state == "keypad"


async def test_lock_state_report_feeds_the_gap_watch(
    hass: HomeAssistant, real_integration: MockConfigEntry, real_lock: RealLock
) -> None:
    manager = real_integration.runtime_data
    real_lock.report(0x0000, 0x30, b"\x01")  # locked
    real_lock.report(0x0000, 0x30, b"\x02")  # unlocked
    await hass.async_block_till_done()
    assert manager._report_gap_timer is not None  # noqa: SLF001
    real_lock.report(0x0100, 0x1B, (0x02020004).to_bytes(4, "little"))
    await hass.async_block_till_done()
    assert manager._report_gap_timer is None  # noqa: SLF001


async def test_silent_lock_fails_within_the_bound(
    hass: HomeAssistant, real_integration: MockConfigEntry, real_lock: RealLock
) -> None:
    """zigpy alone would wait 3 x 28 s per attempt for a sleeping end device."""
    real_lock.answers[0x05] = None
    loop = asyncio.get_running_loop()
    started = loop.time()
    with (
        patch("custom_components.nimly_digital_lock.zha.COMMAND_TIMEOUT_S", 0.05),
        pytest.raises(HomeAssistantError) as err,
    ):
        await hass.services.async_call(
            DOMAIN, NimlyService.SET_PIN, {"slot": 7, "pin_code": "2468"}, blocking=True
        )
    assert err.value.translation_key == "lock_unreachable"
    assert loop.time() - started < 5
