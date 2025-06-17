from homeassistant.components.sensor import SensorEntity
from homeassistant.helpers.entity import EntityCategory

class LockStateSensor(SensorEntity):
    _attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_should_poll = False
    _attr_icon = "mdi:lock"

    def __init__(self, parent_entity):
        self._attr_name = "Lock State"
        self._attr_unique_id = f"{parent_entity.unique_id}_lock_state"
        self._attr_native_value = "Unknown"

    def update_from_lock(self, state: str):
        self._attr_native_value = state
        self.async_write_ha_state()