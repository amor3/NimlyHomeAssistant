"""Runtime state for one Nimly lock: slots, capabilities and lock events."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
import logging
from typing import Any, TypedDict

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from . import rules
from .const import (
    ATTR_ID_EVENT_STATUS,
    ATTR_ID_PIN_USED,
    CMD_CLEAR_PIN,
    CMD_SET_PIN,
    CONF_IEEE,
    CONF_RESERVED_SLOTS,
    CONF_WAKE_WITH_LOCK,
    DEFAULT_RESERVED_SLOTS,
    DOMAIN,
    EVENT_LOCK_ACTIVITY,
    MAX_SLOT,
    STORAGE_VERSION,
)
from .rules import LockEvent
from .zha import LockTransport, SendOutcome, subscribe_attribute_reports

_LOGGER = logging.getLogger(__name__)


class SlotData(TypedDict):
    """What Home Assistant knows about one lock slot."""

    name: str
    has_pin: bool


@dataclass(frozen=True, slots=True)
class LockActivity:
    """A lock event with who it was and whether a person did it."""

    event: LockEvent
    user: str | None
    system: bool

    def as_dict(self) -> dict[str, Any]:
        return {
            "action": self.event.action.value,
            "source": self.event.source.value,
            "slot": self.event.slot,
            "user": self.user,
            "system": self.system,
        }


type NimlyConfigEntry = ConfigEntry[NimlyLockManager]


def lock_store(hass: HomeAssistant, entry: ConfigEntry) -> Store[dict[str, Any]]:
    """The store holding one lock's slot names and capabilities."""
    return Store(hass, STORAGE_VERSION, f"{DOMAIN}.{entry.entry_id}")


class NimlyLockManager:
    """Owns everything this integration knows about one lock."""

    def __init__(self, hass: HomeAssistant, entry: NimlyConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.ieee: str = entry.data[CONF_IEEE]
        self.transport = LockTransport(hass, self.ieee)
        self.transport.wake_with_lock = bool(entry.options.get(CONF_WAKE_WITH_LOCK, False))
        self._store = lock_store(hass, entry)
        self._capability_task: asyncio.Task[None] | None = None
        self._slots: dict[str, SlotData] = {}
        self.capabilities: dict[str, int] = {}
        self.capabilities_read = False
        self.listening = False
        self.last_event: LockEvent | None = None
        self._listeners: list[Callable[[], None]] = []
        self._event_listeners: list[Callable[[LockActivity], None]] = []
        self._pin_lock = asyncio.Lock()
        self._capability_lock = asyncio.Lock()

    async def async_load(self) -> None:
        """Load stored slot names and capabilities."""
        data = await self._store.async_load() or {}
        self._slots = {
            str(key): SlotData(name=str(value.get("name", "")), has_pin=bool(value.get("has_pin")))
            for key, value in data.get("slots", {}).items()
        }
        if isinstance(caps := data.get("capabilities"), dict):
            self.capabilities = {k: int(v) for k, v in caps.items()}
            self.capabilities_read = True

    @callback
    def _schedule_save(self) -> None:
        self._store.async_delay_save(self._data_to_save, 1)

    def _data_to_save(self) -> dict[str, Any]:
        return {
            "slots": {key: dict(slot) for key, slot in self._slots.items()},
            "capabilities": self.capabilities if self.capabilities_read else None,
        }

    async def async_flush(self) -> None:
        """Write pending changes now, before an unload drops the delayed save."""
        await self._store.async_save(self._data_to_save())

    # Listeners for entities

    @callback
    def add_listener(self, update: Callable[[], None]) -> Callable[[], None]:
        """Call update when slots, availability or capabilities change."""
        self._listeners.append(update)
        return lambda: self._listeners.remove(update)

    @callback
    def add_event_listener(self, handle: Callable[[LockActivity], None]) -> Callable[[], None]:
        """Call handle for every decoded lock event."""
        self._event_listeners.append(handle)
        return lambda: self._event_listeners.remove(handle)

    @callback
    def async_update_listeners(self) -> None:
        for update in list(self._listeners):
            update()

    # Slots

    @property
    def first_user_slot(self) -> int:
        return rules.first_user_slot(
            self.entry.options.get(CONF_RESERVED_SLOTS, DEFAULT_RESERVED_SLOTS)
        )

    @property
    def max_user_slot(self) -> int:
        return rules.max_user_slot(self.capabilities)

    @property
    def slots(self) -> dict[int, SlotData]:
        """Copy of all slots Home Assistant has a name or PIN for."""
        return {
            int(key): SlotData(**slot)
            for key, slot in sorted(self._slots.items(), key=lambda i: int(i[0]))
        }

    def slot_name(self, slot: int) -> str | None:
        """The name given to a slot, or None."""
        return self._slots.get(str(slot), {}).get("name") or None

    @callback
    def set_slot_name(self, slot: int, name: str) -> None:
        """Name a slot; an empty name removes it."""
        key = str(slot)
        current = self._slots.get(key, SlotData(name="", has_pin=False))
        current["name"] = name.strip()
        if not current["name"] and not current["has_pin"]:
            self._slots.pop(key, None)
        else:
            self._slots[key] = current
        self._schedule_save()
        self.async_update_listeners()

    def _check_writable(self, slot: int, highest: int) -> None:
        if not self.first_user_slot <= slot <= highest:
            raise ValueError(f"slot {slot} is outside the writable range")

    async def async_set_pin(self, slot: int, code: str, name: str | None = None) -> SendOutcome:
        """Write a PIN code to a slot; a name of None keeps the current one."""
        self._check_writable(slot, self.max_user_slot)
        async with self._pin_lock:
            outcome = await self._send(
                CMD_SET_PIN,
                {"user_id": slot, "user_status": 1, "user_type": 0, "pin_code": code},
            )
            if outcome.delivered:
                current = self._slots.get(str(slot), SlotData(name="", has_pin=False))
                current["has_pin"] = True
                if name is not None:
                    current["name"] = name.strip()
                self._slots[str(slot)] = current
                self._schedule_save()
                self.async_update_listeners()
            return outcome

    async def async_clear_pin(self, slot: int) -> SendOutcome:
        """Remove the PIN code from a slot; the name stays.

        Any user slot may be cleared, even above the reported capacity: a
        code may have been written before the capacity was known.
        """
        self._check_writable(slot, MAX_SLOT)
        async with self._pin_lock:
            outcome = await self._send(CMD_CLEAR_PIN, {"user_id": slot})
            if outcome.delivered and (current := self._slots.get(str(slot))) is not None:
                current["has_pin"] = False
                if not current["name"]:
                    self._slots.pop(str(slot))
                self._schedule_save()
                self.async_update_listeners()
            return outcome

    async def _send(self, command: int, params: dict[str, Any]) -> SendOutcome:
        outcome = await self.transport.send(command, params)
        if outcome.lock_answered:
            # The radio is awake right now; the best moment for a read.
            self.schedule_capability_refresh()
        return outcome

    # Capabilities

    async def async_refresh_capabilities(self) -> None:
        """Read the lock's PIN limits once it answers; stored afterwards."""
        if self.capabilities_read:
            return
        async with self._capability_lock:
            if self.capabilities_read:
                return
            if (capabilities := await self.transport.read_capabilities()) is None:
                return
            self.capabilities = capabilities
            self.capabilities_read = True
            self._schedule_save()
        _LOGGER.debug("Lock %s reported capabilities %s", self.ieee, self.capabilities)
        self.async_update_listeners()

    @callback
    def schedule_capability_refresh(self) -> None:
        """Start a capability read unless one is done or already running."""
        if self.capabilities_read or (
            self._capability_task is not None and not self._capability_task.done()
        ):
            return
        self._capability_task = self.entry.async_create_background_task(
            self.hass,
            self.async_refresh_capabilities(),
            f"{DOMAIN} capability read {self.ieee}",
        )

    # Lock events

    @callback
    def async_start_listening(self, cluster: Any) -> Callable[[], None]:
        """Subscribe to the cluster's attribute reports."""
        unsubscribe = subscribe_attribute_reports(cluster, self._handle_report)
        self.listening = True
        self.async_update_listeners()

        @callback
        def _stop() -> None:
            unsubscribe()
            self.listening = False

        return _stop

    @callback
    def _handle_report(self, attribute_id: int, raw: Any) -> None:
        if attribute_id == ATTR_ID_PIN_USED:
            # Carries the PIN in clear text; never stored or logged.
            return
        self.schedule_capability_refresh()
        if attribute_id != ATTR_ID_EVENT_STATUS:
            return
        try:
            value = int(raw)
        except (TypeError, ValueError):
            try:
                value = int(raw.value)
            except (TypeError, ValueError, AttributeError):
                _LOGGER.debug("Unparsable event status from %s", self.ieee)
                return
        if (event := rules.decode_event_status(value)) is None:
            return
        self.handle_event(event)

    @callback
    def handle_event(self, event: LockEvent) -> None:
        """Publish a decoded lock event to entities and the event bus."""
        _LOGGER.debug(
            "Lock %s: %s via %s, slot %s (0x%08x)",
            self.ieee,
            event.action,
            event.source,
            event.slot,
            event.raw,
        )
        self.last_event = event
        activity = LockActivity(
            event=event,
            user=self.slot_name(event.slot) if event.slot is not None else None,
            system=rules.is_system_event(event, self.transport.wake_echo_pending()),
        )
        for handle in list(self._event_listeners):
            handle(activity)
        self.hass.bus.async_fire(
            EVENT_LOCK_ACTIVITY,
            {"config_entry_id": self.entry.entry_id, "ieee": self.ieee, **activity.as_dict()},
        )
