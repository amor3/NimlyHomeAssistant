from homeassistant.core import HomeAssistant
import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import EntityCategory
from .const import DOMAIN, ATTRIBUTE_MAP

_LOGGER = logging.getLogger(__name__)

class NimlySensor(SensorEntity):
    def __init__(self, hass, ieee, attribute, name, entry_id):
        self._hass = hass
        self._ieee = ieee
        self._attribute = attribute
        self._name = name

        # Create truly unique ID by incorporating more components
        # Using a consistent format that's guaranteed to be unique across different installations
        from .protocols import normalize_ieee
        ieee_clean = normalize_ieee(ieee)["no_colons"]
        self._unique_id = f"{DOMAIN}_{attribute}_{ieee_clean}_{entry_id}"
        self._attr_has_entity_name = True

        # Set entity_id format to avoid collisions with other integrations
        self._attr_entity_id = f"{DOMAIN}_{ieee_clean}_{attribute}"

        # Initialize data for debugging
        _LOGGER.debug(f"Initializing sensor: {self._name} for attribute {attribute} with unique_id {self._unique_id}")
        key = f"{DOMAIN}:{ieee}:{attribute}"
        if key not in self._hass.data:
            _LOGGER.warning(f"Key {key} not found in hass.data, initializing to None")
            self._hass.data[key] = None

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def native_value(self):
        key = f"{DOMAIN}:{self._ieee}:{self._attribute}"
        value = self._hass.data.get(key)
        _LOGGER.debug(f"Sensor {self._name} reading {key}: {value}")
        return value

    async def async_update(self):
        """Update method to refresh data from the lock entity."""
        # We're not doing an actual update here since the lock entity handles that
        # This is just to ensure we're getting the latest data
        key = f"{DOMAIN}:{self._ieee}:{self._attribute}"
        value = self._hass.data.get(key)
        _LOGGER.debug(f"Sensor {self._name} updating, current value for {key}: {value}")

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
        # Extract the base name (e.g., "Nordic Front Door") from the sensor name
        # regardless of how many parts there are
        parts = self._name.split(' ')
        if len(parts) >= 3:
            # First two parts are likely "Nordic Front Door"
            base_name = parts[0] + ' ' + parts[1] + ' ' + parts[2]
        else:
            # Fallback to just the name
            base_name = self._name

        return {
            "identifiers": {(DOMAIN, self._ieee)},
            "name": base_name,
            "manufacturer": "Nordic Semiconductor",
            "model": "ZBT-1 Safe4 Door Lock",
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
