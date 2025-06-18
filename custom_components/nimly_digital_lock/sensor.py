from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import EntityCategory

from custom_components.nimly_digital_lock import NimlyDigitalLock


class LockStateSensor(SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False
    _attr_icon = "mdi:lock"

    def __init__(self, lock_entity: NimlyDigitalLock):
        self._lock_entity = lock_entity
        self._attr_should_poll = False
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_native_value = "Unknown"

    async def async_added_to_hass(self):
        # Safe to access lock entity name and unique_id now
        self._attr_name = f"{self._lock_entity.name} Lock State"
        self._attr_unique_id = f"{self._lock_entity.unique_id}_lock_state"
        self._attr_device_info = self._lock_entity.device_info

    def update_from_lock(self, state: str):
        self._attr_native_value = state
        self.async_write_ha_state()