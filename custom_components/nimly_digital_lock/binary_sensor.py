"""Battery low, as the lock itself reports it (attribute 0x9000)."""

from __future__ import annotations

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity  # type: ignore[attr-defined]
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .entity import NimlyEventEntity
from .manager import NimlyConfigEntry, NimlyLockManager

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NimlyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the battery low sensor."""
    async_add_entities([NimlyBatteryLow(entry.runtime_data)])


class NimlyBatteryLow(NimlyEventEntity, BinarySensorEntity):
    """On when the lock says its batteries need replacing."""

    _attr_device_class = BinarySensorDeviceClass.BATTERY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    def __init__(self, manager: NimlyLockManager) -> None:
        super().__init__(manager, "battery_low")

    @property
    def is_on(self) -> bool | None:
        return self.manager.battery_low
