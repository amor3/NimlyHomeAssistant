from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import EntityCategory
from .const import DOMAIN, ATTRIBUTE_MAP

class NimlySensor(SensorEntity):
    def __init__(self, hass, ieee, attribute, name, entry_id):
        self._hass = hass
        self._ieee = ieee
        self._attribute = attribute
        self._name = name
        self._unique_id = f"nimly_{attribute}_{ieee.replace(':','')}_{entry_id}"

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def native_value(self):
        return self._hass.data.get(f"{DOMAIN}:{self._ieee}:{self._attribute}")

    @property
    def device_class(self):
        if self._attribute == "battery":
            return "battery"
        if self._attribute in ["rssi", "rssi_dbm"]:
            return "signal_strength"
        return None

    @property
    def native_unit_of_measurement(self):
        if self._attribute == "battery":
            return PERCENTAGE
        if self._attribute == "battery_voltage":
            return "V"
        if self._attribute == "rssi_dbm":
            return SIGNAL_STRENGTH_DECIBELS
        if self._attribute == "rssi":
            return "dB"
        return None

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._ieee)},
            "name": self._name.split(' ')[0] + ' ' + self._name.split(' ')[1],
            "manufacturer": "Safe4",
            "model": "Zigbee Door Lock Module",
            "sw_version": "1.0",
            "entry_type": DeviceEntryType.SERVICE,
        }

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    ieee = entry.data["ieee"]
    name = entry.data.get("name", "Nimly Front Door")
    sensors = [
        NimlySensor(hass, ieee, attr, f"{name} {attr.replace('_',' ').title()}", entry.entry_id)
        for attr in ATTRIBUTE_MAP
    ]
    async_add_entities(sensors)
