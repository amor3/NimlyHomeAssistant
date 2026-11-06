"""Sensors: last action, how, who, and the PIN codes set from Home Assistant."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import RestoreSensor, SensorDeviceClass, SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import rules
from .const import LockAction, LockSource
from .entity import NimlyEntity, NimlyEventEntity
from .manager import LockActivity, NimlyConfigEntry, NimlyLockManager
from .rules import LockEvent

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NimlyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensors."""
    manager = entry.runtime_data
    async_add_entities(
        [
            LastActionSensor(manager),
            LastSourceSensor(manager),
            LastUserSensor(manager),
            PinCodesSensor(manager),
            PinCapacitySensor(manager),
        ]
    )


class _LockEventSensor(NimlyEventEntity, RestoreSensor):
    """A sensor that follows lock events and survives a restart."""

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_sensor_data()) is not None:
            self._attr_native_value = last.native_value
        if (state := await self.async_get_last_state()) is not None:
            self._attr_extra_state_attributes = {
                k: v for k, v in state.attributes.items() if k in ("slot", "source", "action")
            }
        self.async_on_remove(self.manager.add_event_listener(self._handle_lock_event))

    @callback
    def _handle_lock_event(self, activity: LockActivity) -> None:
        if self._apply(activity.event):
            self.async_write_ha_state()

    def _apply(self, event: LockEvent) -> bool:
        raise NotImplementedError


class LastActionSensor(_LockEventSensor):
    """Locked or unlocked, as last reported."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [action.value for action in LockAction]

    def __init__(self, manager: NimlyLockManager) -> None:
        super().__init__(manager, "last_action")

    def _apply(self, event: LockEvent) -> bool:
        self._attr_native_value = event.action.value
        self._attr_extra_state_attributes = {"source": event.source.value, "slot": event.slot}
        return True


class LastSourceSensor(_LockEventSensor):
    """How the lock was last operated."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [source.value for source in LockSource]

    def __init__(self, manager: NimlyLockManager) -> None:
        super().__init__(manager, "last_source")

    def _apply(self, event: LockEvent) -> bool:
        self._attr_native_value = event.source.value
        self._attr_extra_state_attributes = {"action": event.action.value, "slot": event.slot}
        return True


class LastUserSensor(_LockEventSensor):
    """Who last used a code, tag or finger.

    Only credential events update it, so the auto relock seconds later
    does not wipe out who opened the door.
    """

    def __init__(self, manager: NimlyLockManager) -> None:
        super().__init__(manager, "last_user")

    def _apply(self, event: LockEvent) -> bool:
        if not event.by_credential or event.slot is None:
            return False
        self._attr_native_value = self.manager.slot_name(event.slot) or f"Slot {event.slot}"
        self._attr_extra_state_attributes = {
            "slot": event.slot,
            "source": event.source.value,
            "action": event.action.value,
        }
        return True


class PinCodesSensor(NimlyEntity, SensorEntity):
    """How many slots have a PIN code set from Home Assistant."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, manager: NimlyLockManager) -> None:
        super().__init__(manager, "pin_codes")

    @property
    def native_value(self) -> int:
        return sum(1 for slot in self.manager.slots.values() if slot["has_pin"])

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        # Names and whether a code is set; never the code itself.
        return {
            "first_user_slot": self.manager.first_user_slot,
            "slots": {
                str(number): {"name": slot["name"], "has_pin": slot["has_pin"]}
                for number, slot in self.manager.slots.items()
            },
        }


class PinCapacitySensor(NimlyEntity, SensorEntity):
    """PIN slots the lock reports, once it has answered."""

    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_entity_registry_enabled_default = False

    def __init__(self, manager: NimlyLockManager) -> None:
        super().__init__(manager, "pin_capacity")

    @property
    def native_value(self) -> int | None:
        return self.manager.capabilities.get("num_pin_users")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        low, high = rules.pin_length_range(self.manager.capabilities)
        return {"min_pin_length": low, "max_pin_length": high}
