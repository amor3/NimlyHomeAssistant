from homeassistant.components.sensor import SensorEntity, SensorDeviceClass, SensorStateClass
from homeassistant.const import SIGNAL_STRENGTH_DECIBELS_MILLIWATT
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.core import HomeAssistant
import logging

from ..const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class RSSISensor(SensorEntity):
    """RSSI sensor for Nimly lock."""

    _attr_device_class = SensorDeviceClass.SIGNAL_STRENGTH
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = SIGNAL_STRENGTH_DECIBELS_MILLIWATT  # dBm
    #_attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_suggested_display_precision = 0  # Show whole numbers only

    def __init__(self, hass: HomeAssistant, ieee: str, lock_name: str) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._ieee = ieee.lower().replace(":", "")
        self._attr_name = "RSSI"
        self._attr_unique_id = f"{DOMAIN}_rssi_{self._ieee}"

        # Clean up the entity_id
        clean_name = lock_name.lower()
        clean_name = ''.join(c if c.isalnum() else '_' for c in clean_name)
        clean_name = clean_name.strip('_')  # Remove leading/trailing underscores
        # Replace multiple underscores with single one
        while '__' in clean_name:
            clean_name = clean_name.replace('__', '_')

        self.entity_id = f"sensor.{clean_name}_rssi"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, ieee)},
            "name": lock_name,
            "manufacturer": "Nimly",
            "model": "Nimly Lock",
            "sw_version": "1.0",
            "entry_type": DeviceEntryType.SERVICE,
        }
        # Initialize with a typical RSSI value (e.g., -50 dBm is good signal)
        self._attr_native_value = -50

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return True  # Always available once created

    @property
    def icon(self) -> str:
        """Return the icon based on RSSI level."""
        if self._attr_native_value is None:
            return "mdi:wifi-strength-outline"

        rssi_level = int(self._attr_native_value)

        # RSSI values are negative, with higher (less negative) values being better
        if rssi_level >= -30:
            return "mdi:wifi-strength-4"  # Excellent signal
        elif rssi_level >= -50:
            return "mdi:wifi-strength-3"  # Good signal
        elif rssi_level >= -70:
            return "mdi:wifi-strength-2"  # Fair signal
        elif rssi_level >= -85:
            return "mdi:wifi-strength-1"  # Poor signal
        else:
            return "mdi:wifi-strength-outline"  # Very poor signal

    @property
    def extra_state_attributes(self):
        """Return additional state attributes."""
        attributes = {}
        if self._attr_native_value is not None:
            attributes["rssi_dbm"] = f"{self._attr_native_value} dBm"
            attributes["last_updated"] = self.hass.states.get(self.entity_id).last_updated if self.hass.states.get(
                self.entity_id) else None

            # Add RSSI status description based on typical WiFi/Zigbee standards
            rssi_level = int(self._attr_native_value)
            if rssi_level >= -30:
                attributes["signal_quality"] = "Excellent"
            elif rssi_level >= -50:
                attributes["signal_quality"] = "Good"
            elif rssi_level >= -70:
                attributes["signal_quality"] = "Fair"
            elif rssi_level >= -85:
                attributes["signal_quality"] = "Poor"
            else:
                attributes["signal_quality"] = "Very Poor"

            # Convert to percentage for easier understanding (optional)
            # This is a rough conversion for display purposes
            if rssi_level >= -30:
                signal_percent = 100
            elif rssi_level >= -50:
                signal_percent = 75
            elif rssi_level >= -70:
                signal_percent = 50
            elif rssi_level >= -85:
                signal_percent = 25
            else:
                signal_percent = 10

            attributes["signal_percentage"] = f"{signal_percent}%"

        return attributes

    def update_state(self, value: int) -> None:
        """Update the sensor with new RSSI value."""
        _LOGGER.info(f"[AM] [RSSI] Updating sensor {self.entity_id} with value: {value} dBm")

        # RSSI values are typically between -30 (excellent) and -100 (very poor)
        # Clamp the value to reasonable bounds
        value = max(-100, min(-10, int(value)))

        # Always update to ensure history recording
        old_value = self._attr_native_value
        self._attr_native_value = value

        # Schedule state update to ensure it's recorded in history
        self.schedule_update_ha_state(force_refresh=True)

        _LOGGER.info(f"[AM] [RSSI] RSSI updated from {old_value} dBm to {value} dBm - icon: {self.icon}")

    @property
    def native_value(self):
        """Return the native value of the sensor."""
        return self._attr_native_value

    @property
    def state(self) -> int | None:
        """Return the state of the sensor."""
        return self._attr_native_value

    @property
    def unit_of_measurement(self) -> str:
        """Return the unit of measurement."""
        return SIGNAL_STRENGTH_DECIBELS_MILLIWATT

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False