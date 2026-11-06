"""Sensors: last action, how, who, and the PIN codes set from Home Assistant."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import rules
from .const import FEATURE_BATTERY, LockAction, LockSource
from .entity import NimlyEntity, NimlyEventEntity
from .manager import LockActivity, NimlyConfigEntry, NimlyLockManager
from .zha import device_for_nwk

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
            LastReportSensor(manager),
            ParentRouterSensor(manager),
        ]
    )
    if FEATURE_BATTERY in manager.fallbacks:
        async_add_entities([BatterySensor(manager)])


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
        if self._apply(activity):
            if activity.context is not None:
                self.async_set_context(activity.context)
            self.async_write_ha_state()

    def _apply(self, activity: LockActivity) -> bool:
        raise NotImplementedError


class LastActionSensor(_LockEventSensor):
    """Locked or unlocked, as last reported."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [action.value for action in LockAction]

    def __init__(self, manager: NimlyLockManager) -> None:
        super().__init__(manager, "last_action")

    def _apply(self, activity: LockActivity) -> bool:
        event = activity.event
        self._attr_native_value = event.action.value
        self._attr_extra_state_attributes = {"source": event.source.value, "slot": event.slot}
        return True


class LastSourceSensor(_LockEventSensor):
    """How the lock was last operated."""

    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = [source.value for source in LockSource]

    def __init__(self, manager: NimlyLockManager) -> None:
        super().__init__(manager, "last_source")

    def _apply(self, activity: LockActivity) -> bool:
        event = activity.event
        self._attr_native_value = event.source.value
        self._attr_extra_state_attributes = {"action": event.action.value, "slot": event.slot}
        return True


class LastUserSensor(_LockEventSensor):
    """Who last operated the lock: a code, tag or finger, or a Home Assistant user.

    Events that name nobody (auto relock, a palm lock from outside) leave it
    alone, so the relock seconds later does not wipe out who opened the door.
    """

    def __init__(self, manager: NimlyLockManager) -> None:
        super().__init__(manager, "last_user")

    def _apply(self, activity: LockActivity) -> bool:
        event = activity.event
        if activity.ha_user is not None:
            self._attr_native_value = activity.ha_user
            self._attr_extra_state_attributes = {
                "slot": None,
                "source": event.source.value,
                "action": event.action.value,
            }
            return True
        if not event.credits_user or event.slot is None:
            return False
        self._attr_native_value = activity.user or self.manager.slot_label(event.slot)
        self._attr_extra_state_attributes = {
            "slot": event.slot,
            "source": event.source.value,
            "action": event.action.value,
        }
        return True


class LastReportSensor(_LockEventSensor):
    """When the lock last reported an operation; shows that reports arrive."""

    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, manager: NimlyLockManager) -> None:
        super().__init__(manager, "last_report")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        # Restored as text by RestoreSensor; a timestamp sensor needs a datetime.
        if isinstance(self._attr_native_value, str):
            self._attr_native_value = dt_util.parse_datetime(self._attr_native_value)
        self._attr_extra_state_attributes = {}

    def _apply(self, activity: LockActivity) -> bool:
        self._attr_native_value = dt_util.utcnow()
        self._attr_extra_state_attributes = {"raw": f"0x{activity.event.raw:08x}"}
        return True


class BatterySensor(NimlyEventEntity, RestoreSensor):
    """Battery level, only when ZHA does not show one for the lock.

    The lock reports percent where ZCL expects half-percent, and it presents
    itself as mains powered, so without ZHA's Nimly quirk ZHA shows no
    battery or half the real value.
    """

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, manager: NimlyLockManager) -> None:
        super().__init__(manager, "battery")
        self._restored: int | None = None

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        if (last := await self.async_get_last_sensor_data()) is not None and isinstance(
            last.native_value, int | float
        ):
            self._restored = int(last.native_value)

    @property
    def native_value(self) -> int | None:
        return self.manager.battery if self.manager.battery is not None else self._restored


class ParentRouterSensor(NimlyEventEntity, SensorEntity):
    """The Zigbee router the lock talks through, and the signal to it.

    Most dropouts on these locks are range: this shows which device the
    lock depends on (attribute 0x0103).
    """

    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, manager: NimlyLockManager) -> None:
        super().__init__(manager, "parent_router")

    @property
    def native_value(self) -> str | None:
        if (parent := self.manager.parent) is None:
            return None
        if parent.nwk == 0x0000:
            return "Coordinator"
        if (found := device_for_nwk(self.hass, parent.nwk)) is not None:
            return found[1]
        return f"0x{parent.nwk:04X}"

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        if (parent := self.manager.parent) is None:
            return {}
        found = device_for_nwk(self.hass, parent.nwk)
        return {
            "nwk": f"0x{parent.nwk:04X}",
            "ieee": found[0] if found else None,
            "rssi_dbm": parent.rssi_dbm,
        }


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
            # When scheduled codes are written; never the codes.
            "schedules": {
                str(number): schedule.summary()
                for number, schedule in self.manager.schedules.items()
            },
            "slots": {
                str(number): {
                    "name": slot["name"],
                    "names": slot["names"],
                    "has_pin": slot["has_pin"],
                    "expires": slot["expires"],
                }
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
