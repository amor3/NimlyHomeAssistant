"""Everything that knows ZHA and zigpy internals.

ZHA has no public API for a device's zigpy clusters, so this module walks the
object layout of a running ZHA: the gateway proxy, its device proxies and the
.device chain down to the zigpy device. Keeping it in one file means a ZHA
change is a change here only.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable, Iterator
from dataclasses import dataclass
import enum
import logging
import time
from typing import Any

from zigpy.exceptions import DeliveryError, ZigbeeException
from zigpy.zcl.foundation import Status

from homeassistant.components.zha.helpers import get_zha_gateway_proxy
from homeassistant.core import Context, HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .const import (
    ATTR_ID_MAX_PIN_LENGTH,
    ATTR_ID_MIN_PIN_LENGTH,
    ATTR_ID_NUM_PIN_USERS,
    CMD_SET_PIN,
    COMMAND_TIMEOUT_S,
    DOOR_LOCK_CLUSTER_ID,
    FEATURE_AUTO_RELOCK,
    FEATURE_BATTERY,
    FEATURE_SOUND_VOLUME,
    MANUFACTURER,
    SEND_ATTEMPTS,
    SEND_RETRY_DELAY_S,
    WAKE_ECHO_WINDOW_S,
    WAKE_TIMEOUT_S,
    ZHA_DOMAIN,
)
from .rules import redact_digits

_LOGGER = logging.getLogger(__name__)

# ZHADeviceProxy -> Device -> zigpy device (or quirk), plus one spare level.
_CHAIN_DEPTH = 4

_CAPABILITY_KEYS: dict[int | str, str] = {
    ATTR_ID_NUM_PIN_USERS: "num_pin_users",
    "num_of_pin_users_supported": "num_pin_users",
    ATTR_ID_MAX_PIN_LENGTH: "max_pin_length",
    "max_pin_len": "max_pin_length",
    ATTR_ID_MIN_PIN_LENGTH: "min_pin_length",
    "min_pin_len": "min_pin_length",
}

# Set PIN Code Response status values from the ZCL Door Lock specification.
_SET_PIN_MEMORY_FULL = 0x02
_SET_PIN_DUPLICATE_CODE = 0x03


class ZhaInternalsMissing(Exception):
    """The ZHA or zigpy structure this integration relies on is missing."""


class Delivery(enum.Enum):
    """What became of a command sent to the lock."""

    DELIVERED = "delivered"
    REJECTED = "rejected"
    UNREACHED = "unreached"


@dataclass(frozen=True, slots=True)
class SendOutcome:
    """Result of LockTransport.send."""

    delivery: Delivery
    error_key: str | None = None

    @property
    def delivered(self) -> bool:
        return self.delivery is Delivery.DELIVERED

    @property
    def lock_answered(self) -> bool:
        return self.delivery is not Delivery.UNREACHED


DELIVERED = SendOutcome(Delivery.DELIVERED)
UNREACHED = SendOutcome(Delivery.UNREACHED, "lock_unreachable")


def _gateway_proxy(hass: HomeAssistant) -> Any:
    try:
        return get_zha_gateway_proxy(hass)
    except (ValueError, KeyError):
        return None


def is_zha_running(hass: HomeAssistant) -> bool:
    """Whether ZHA has a running gateway."""
    return _gateway_proxy(hass) is not None


def _iter_device_proxies(hass: HomeAssistant) -> Iterator[tuple[str, Any]]:
    if (gateway := _gateway_proxy(hass)) is None:
        return
    for ieee, proxy in gateway.device_proxies.items():
        yield str(ieee).lower(), proxy


def _metadata(proxy: Any) -> tuple[str, str]:
    device = getattr(proxy, "device", proxy)
    return getattr(device, "manufacturer", "") or "", getattr(device, "model", "") or ""


def _walk_to_cluster(obj: Any, cluster_id: int = DOOR_LOCK_CLUSTER_ID) -> Any:
    for _ in range(_CHAIN_DEPTH):
        for ep_id, endpoint in getattr(obj, "endpoints", {}).items():
            if ep_id == 0:
                continue
            if cluster_id in (clusters := getattr(endpoint, "in_clusters", {})):
                return clusters[cluster_id]
        if not hasattr(obj, "device"):
            break
        obj = obj.device
    return None


def iter_nimly_locks(hass: HomeAssistant) -> Iterator[tuple[str, str]]:
    """Yield (ieee, model) for every Nimly lock ZHA knows.

    The manufacturer and the Door Lock cluster decide; modules sometimes
    report a sibling model name, so the model is informational only.
    """
    for ieee, proxy in _iter_device_proxies(hass):
        manufacturer, model = _metadata(proxy)
        if manufacturer == MANUFACTURER and _walk_to_cluster(proxy) is not None:
            yield ieee, model


def lock_in_zha(hass: HomeAssistant, ieee: str) -> bool:
    """Whether ZHA lists a device with this address."""
    return any(dev_ieee == ieee.lower() for dev_ieee, _ in _iter_device_proxies(hass))


def model_in_zha(hass: HomeAssistant, ieee: str) -> str:
    """The model string ZHA reports for the lock, or ""."""
    for dev_ieee, proxy in _iter_device_proxies(hass):
        if dev_ieee == ieee.lower():
            return _metadata(proxy)[1]
    return ""


@dataclass(frozen=True, slots=True)
class QuirkStatus:
    """Whether ZHA applied a device quirk to the lock, and which."""

    applied: bool
    quirk_class: str


def quirk_status(hass: HomeAssistant, ieee: str) -> QuirkStatus | None:
    """ZHA's quirk status for the lock, or None when ZHA cannot tell."""
    for dev_ieee, proxy in _iter_device_proxies(hass):
        if dev_ieee != ieee.lower():
            continue
        device = getattr(proxy, "device", None)
        applied = getattr(device, "quirk_applied", None)
        if not isinstance(applied, bool):
            return None
        return QuirkStatus(applied, str(getattr(device, "quirk_class", "")))
    return None


def find_door_lock_cluster(hass: HomeAssistant, ieee: str) -> Any:
    """The lock's zigpy Door Lock cluster, or None."""
    return find_cluster(hass, ieee, DOOR_LOCK_CLUSTER_ID)


def find_cluster(hass: HomeAssistant, ieee: str, cluster_id: int) -> Any:
    """One of the lock's zigpy server clusters, or None."""
    for dev_ieee, proxy in _iter_device_proxies(hass):
        if dev_ieee == ieee.lower():
            return _walk_to_cluster(proxy, cluster_id)
    return None


def zha_features(hass: HomeAssistant, ieee: str) -> set[str]:
    """Which of auto relock, sound volume and battery ZHA shows for the lock.

    Read from ZHA's entities on its device, disabled ones included (a user
    who turned one off made a choice). Matched three ways, so a change in
    how ZHA forms unique ids does not make the integration duplicate them.
    """
    if (device := find_zha_device(hass, ieee)) is None:
        return set()
    features: set[str] = set()
    for entry in er.async_entries_for_device(
        er.async_get(hass), device.id, include_disabled_entities=True
    ):
        if entry.platform != ZHA_DOMAIN:
            continue
        key = f"{entry.translation_key or ''} {entry.unique_id}".lower()
        if "auto_relock" in key:
            features.add(FEATURE_AUTO_RELOCK)
        if "sound_volume" in key:
            features.add(FEATURE_SOUND_VOLUME)
        # The percentage, not a battery voltage sensor next to it.
        if entry.domain == "sensor" and (
            entry.original_device_class == "battery" or "battery_percentage" in key
        ):
            features.add(FEATURE_BATTERY)
    return features


def find_zha_device(hass: HomeAssistant, ieee: str) -> dr.DeviceEntry | None:
    """ZHA's device registry entry for the lock."""
    connection = (dr.CONNECTION_ZIGBEE, ieee.lower())
    registry = dr.async_get(hass)
    for zha_entry in hass.config_entries.async_entries(ZHA_DOMAIN):
        for device in dr.async_entries_for_config_entry(registry, zha_entry.entry_id):
            if connection in device.connections:
                return device
    return None


def find_lock_entity_id(hass: HomeAssistant, ieee: str) -> str | None:
    """Entity id of ZHA's lock entity for the device."""
    if (device := find_zha_device(hass, ieee)) is None:
        return None
    for entry in er.async_entries_for_device(er.async_get(hass), device.id):
        if entry.domain == "lock" and entry.platform == ZHA_DOMAIN:
            return entry.entity_id
    return None


class _AttributeListener:
    """Listener object for zigpy versions without Cluster.on_event."""

    def __init__(self, handle: Callable[[int, Any], None]) -> None:
        self._handle = handle

    def attribute_updated(self, attrid: int, value: Any, *_: Any) -> None:
        self._handle(attrid, value)


def subscribe_attribute_reports(
    cluster: Any, handle: Callable[[int, Any], None]
) -> Callable[[], None]:
    """Call handle(attribute_id, raw_value) for every attribute report."""
    if callable(on_event := getattr(cluster, "on_event", None)):
        unsubscribe: Callable[[], None] = on_event(
            "attribute_report",
            lambda event: handle(event.attribute_id, event.raw_value),
        )
        return unsubscribe
    add = getattr(cluster, "add_listener", None)
    remove = getattr(cluster, "remove_listener", None)
    if not callable(add) or not callable(remove):
        raise ZhaInternalsMissing(f"{type(cluster).__name__} has no event hook")
    listener = _AttributeListener(handle)
    add(listener)
    return lambda: remove(listener)


class LockTransport:
    """Sends commands to, and reads from, one lock's Door Lock cluster."""

    def __init__(self, hass: HomeAssistant, ieee: str) -> None:
        self.hass = hass
        self.ieee = ieee
        self.wake_with_lock = False
        self._last_wake: float | None = None
        # The context of our own wake-up call, so it is not taken for a
        # person locking the door.
        self.wake_context: Context | None = None

    def cluster(self) -> Any:
        return find_door_lock_cluster(self.hass, self.ieee)

    def wake_echo_pending(self) -> bool:
        """Whether a Zigbee lock event may be the echo of our own wake-up."""
        return (
            self._last_wake is not None and time.monotonic() - self._last_wake < WAKE_ECHO_WINDOW_S
        )

    async def _wake(self) -> None:
        """Wake the radio with a lock command through ZHA's lock entity.

        This moves the bolt, so it only runs when the user enabled it.
        """
        if (entity_id := find_lock_entity_id(self.hass, self.ieee)) is None:
            return
        self._last_wake = time.monotonic()
        self.wake_context = Context()
        try:
            async with asyncio.timeout(WAKE_TIMEOUT_S):
                await self.hass.services.async_call(
                    "lock",
                    "lock",
                    {"entity_id": entity_id},
                    blocking=True,
                    context=self.wake_context,
                )
        except Exception as err:  # noqa: BLE001 - a failed wake must not abort the retry
            _LOGGER.debug("Wake-up of %s failed: %s", self.ieee, type(err).__name__)

    async def _attempts(
        self, what: str, cluster: Any, call: Callable[[Any], Awaitable[Any]]
    ) -> Any:
        """Run call(cluster) in bounded, retried attempts. Never raises.

        Returns the answer, or a SendOutcome when the lock was not reached.
        Nothing logged here may contain the call's arguments: they can hold
        a PIN code.
        """
        for attempt in range(1, SEND_ATTEMPTS + 1):
            try:
                # zigpy waits 28 s per try for an end device and retries
                # timeouts itself; the parent drops the frame after 7.68 s
                # anyway, so a bounded attempt fails fast and retries here.
                async with asyncio.timeout(COMMAND_TIMEOUT_S):
                    return await call(cluster)
            except IndexError:
                # Older ZHA/zigpy fail to parse the lock's one-field
                # response after it arrived, so the request got through.
                return DELIVERED
            except (TimeoutError, DeliveryError) as err:
                if attempt == SEND_ATTEMPTS:
                    _LOGGER.warning(
                        "Lock %s did not answer %s after %d attempts: %s",
                        self.ieee,
                        what,
                        attempt,
                        type(err).__name__,
                    )
                    return UNREACHED
                _LOGGER.debug(
                    "%s to %s: %s on attempt %d, retrying",
                    what,
                    self.ieee,
                    type(err).__name__,
                    attempt,
                )
                if self.wake_with_lock and attempt == 1:
                    await self._wake()
                await asyncio.sleep(SEND_RETRY_DELAY_S)
            except ZigbeeException as err:
                _LOGGER.warning(
                    "Zigbee error sending %s to %s: %s", what, self.ieee, redact_digits(err)
                )
                return UNREACHED
            except Exception as err:  # noqa: BLE001 - the message may quote the PIN
                # Only the type is logged: a serialization error can echo arguments.
                _LOGGER.error("Unexpected %s sending %s to %s", type(err).__name__, what, self.ieee)
                return UNREACHED
        return UNREACHED

    async def send(self, command: int, params: dict[str, Any]) -> SendOutcome:
        """Send a Door Lock cluster command. Never raises.

        Calls the zigpy cluster directly instead of ZHA's
        issue_zigbee_cluster_command action, because every action call is
        stored by the recorder and a PIN code would end up in the database.
        """
        if (cluster := self.cluster()) is None:
            _LOGGER.warning("Door Lock cluster for %s not found in ZHA", self.ieee)
            return UNREACHED
        response = await self._attempts(
            f"command 0x{command:02x}", cluster, lambda c: c.command(command, **params)
        )
        if isinstance(response, SendOutcome):
            return response
        return self._outcome(command, response)

    async def write_attribute(self, attribute_id: int, value: int) -> SendOutcome:
        """Write a Door Lock attribute (auto relock, sound volume). Never raises."""
        if (cluster := self.cluster()) is None:
            return UNREACHED
        response = await self._attempts(
            f"write of 0x{attribute_id:04x}",
            cluster,
            lambda c: c.write_attributes({attribute_id: value}),
        )
        if isinstance(response, SendOutcome):
            return response
        # zigpy answers [records]; one record with SUCCESS means all were written.
        records = response[0] if isinstance(response, list | tuple) and response else []
        statuses = [getattr(record, "status", None) for record in records or []]
        if statuses and all(status == Status.SUCCESS for status in statuses):
            return DELIVERED
        _LOGGER.warning(
            "Lock %s refused writing 0x%04x: %s", self.ieee, attribute_id, statuses or response
        )
        return SendOutcome(Delivery.REJECTED, "lock_rejected")

    async def read_attributes(self, cluster_id: int, attribute_ids: list[int]) -> dict[int, Any]:
        """Read attributes once, bounded; what the lock answered, maybe nothing."""
        if (cluster := find_cluster(self.hass, self.ieee, cluster_id)) is None:
            return {}
        try:
            async with asyncio.timeout(COMMAND_TIMEOUT_S):
                result = await cluster.read_attributes(attribute_ids)
        except (TimeoutError, DeliveryError):
            return {}
        except Exception:  # noqa: BLE001 - one odd firmware must not break setup
            _LOGGER.debug("Attribute read from %s failed", self.ieee, exc_info=True)
            return {}
        success = result[0] if isinstance(result, tuple) and result else {}
        return {key: value for key, value in success.items() if isinstance(key, int)}

    def _outcome(self, command: int, response: Any) -> SendOutcome:
        if response is None:
            return DELIVERED
        if isinstance(response, Exception):
            _LOGGER.warning(
                "Command 0x%02x to %s failed: %s",
                command,
                self.ieee,
                type(response).__name__,
            )
            return UNREACHED
        status = getattr(response, "status", None)
        if status is None or status == Status.SUCCESS:
            return DELIVERED
        try:
            code = int(status)
        except (TypeError, ValueError):
            code = None
        error_key = "lock_rejected"
        # Only Set PIN Code's own response (not a Default Response, which
        # carries command_id) gives 2 and 3 these meanings.
        if command == CMD_SET_PIN and not hasattr(response, "command_id"):
            if code == _SET_PIN_DUPLICATE_CODE:
                error_key = "lock_rejected_duplicate"
            elif code == _SET_PIN_MEMORY_FULL:
                error_key = "lock_rejected_memory_full"
        _LOGGER.warning("Lock %s refused command 0x%02x with status %s", self.ieee, command, code)
        return SendOutcome(Delivery.REJECTED, error_key)

    async def read_capabilities(self) -> dict[str, int] | None:
        """Read PIN capacity and length limits; None when the lock is asleep."""
        if (cluster := self.cluster()) is None:
            return None
        try:
            async with asyncio.timeout(COMMAND_TIMEOUT_S):
                result = await cluster.read_attributes(
                    [ATTR_ID_NUM_PIN_USERS, ATTR_ID_MAX_PIN_LENGTH, ATTR_ID_MIN_PIN_LENGTH]
                )
        except (TimeoutError, DeliveryError):
            return None
        except Exception:  # noqa: BLE001 - one odd firmware must not break setup
            _LOGGER.debug("Capability read from %s failed", self.ieee, exc_info=True)
            return None
        success = result[0] if isinstance(result, tuple) and result else {}
        capabilities: dict[str, int] = {}
        for key, value in success.items():
            if (name := _CAPABILITY_KEYS.get(key)) is not None and value is not None:
                capabilities[name] = int(value)
        return capabilities
