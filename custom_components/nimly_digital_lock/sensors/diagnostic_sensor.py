import logging
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceEntryType
from zigpy.types import EUI64

from ..const import DOMAIN
from ..zbt1_support import async_read_attribute_zbt1

_LOGGER = logging.getLogger(__name__)


LOCK_DIAGNOSTIC_ATTRIBUTES = {
    0x0001: ("lock_type", "Lock Type"),
    #0x0002: ("actuator_enabled", "Actuator Enabled"),
    #0x0003: ("door_state", "Door State"),
    0x0011: ("total_users", "Total Users"),
    0x0012: ("pin_users", "PIN Users"),
    0x0013: ("rfid_users", "RFID Users"),
    0x0017: ("max_pin_length", "Max PIN Length"),
    0x0018: ("min_pin_length", "Min PIN Length"),
    0x0019: ("max_rfid_length", "Max RFID Length"),
    0x001A: ("min_rfid_length", "Min RFID Length"),
}


class LockDiagnosticsSensor(SensorEntity):
    def __init__(self, hass, ieee: str, lock_name: str, attribute_id: int, attr_key: str, friendly_name: str):
        self._hass = hass
        self._ieee = ieee
        self._ieee_obj = EUI64.convert(ieee)
        self._attribute_id = attribute_id
        self._attr_key = attr_key
        self._attr_name = f"{friendly_name}"
        self._attr_unique_id = f"{DOMAIN}_{ieee.replace(':','')}_{attr_key}"
        self._attr_device_class = None
        self._attr_entity_category = EntityCategory.DIAGNOSTIC
        self._attr_entity_registry_enabled_default = True
        self._attr_native_unit_of_measurement = None
        self._attr_device_info = {
            "identifiers": {(DOMAIN, ieee)},
            "name": lock_name,
            "manufacturer": "Nimly",
            "model": "Nimly Lock",
            "entry_type": DeviceEntryType.SERVICE,
        }
        self._attr_native_value = None

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        try:
            value = await async_read_attribute_zbt1(
                self._hass,
                self._ieee_obj,
                endpoint=11,
                cluster=0x0101,
                attribute=self._attribute_id
            )
            self._attr_native_value = value
            _LOGGER.info(f"[Diagnostics] {self._attr_name} = {value}")
            self.async_write_ha_state()
        except Exception as e:
            _LOGGER.warning(f"[Diagnostics] Failed to read {self._attr_name}: {e}")

    @property
    def should_poll(self):
        return False
