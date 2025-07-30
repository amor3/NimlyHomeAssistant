
"""Battery sensor for Nimly lock."""
from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, _LOGGER
from homeassistant.helpers.device_registry import DeviceEntryType
from ..const import DOMAIN


class BatterySensor(SensorEntity):
    """Battery sensor for Nimly lock."""

    _attr_device_class = SensorDeviceClass.BATTERY
    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = PERCENTAGE
    #_attr_entity_category = EntityCategory.DIAGNOSTIC
    _attr_has_entity_name = True
    _attr_suggested_display_precision = 0  # Show whole numbers only

    def __init__(self, hass: HomeAssistant, ieee: str, lock_name: str) -> None:
        """Initialize the sensor."""
        self.hass = hass
        self._ieee = ieee.lower().replace(":", "")
        self._attr_name = "Battery"
        self._attr_unique_id = f"{DOMAIN}_battery_{self._ieee}"

        # Clean up the entity_id
        clean_name = lock_name.lower()
        clean_name = ''.join(c if c.isalnum() else '_' for c in clean_name)
        clean_name = clean_name.strip('_')  # Remove leading/trailing underscores
        # Replace multiple underscores with single one
        while '__' in clean_name:
            clean_name = clean_name.replace('__', '_')

        self.entity_id = f"sensor.{clean_name}_battery"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, ieee)},
            "name": lock_name,
            "manufacturer": "Nimly",
            "model": "Nimly Lock",
            "sw_version": "1.0",
            "entry_type": DeviceEntryType.SERVICE,
        }
        # Initialize with None to ensure proper state handling
        self._attr_native_value = 100

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._attr_native_value is not None

    @property
    def icon(self) -> str:
        """Return the icon based on battery level."""
        if self._attr_native_value is None:
            return "mdi:battery-unknown"

        battery_level = int(self._attr_native_value)

        if battery_level >= 95:
            return "mdi:battery"
        elif battery_level >= 85:
            return "mdi:battery-90"
        elif battery_level >= 75:
            return "mdi:battery-80"
        elif battery_level >= 65:
            return "mdi:battery-70"
        elif battery_level >= 55:
            return "mdi:battery-60"
        elif battery_level >= 45:
            return "mdi:battery-50"
        elif battery_level >= 35:
            return "mdi:battery-40"
        elif battery_level >= 25:
            return "mdi:battery-30"
        elif battery_level >= 15:
            return "mdi:battery-20"
        elif battery_level >= 5:
            return "mdi:battery-10"
        else:
            return "mdi:battery-alert"

    @property
    def extra_state_attributes(self):
        """Return additional state attributes."""
        attributes = {}
        if self._attr_native_value is not None:
            attributes["battery_level"] = f"{self._attr_native_value}%"

            # Add battery status description
            if self._attr_native_value >= 75:
                attributes["battery_status"] = "Good"
            elif self._attr_native_value >= 25:
                attributes["battery_status"] = "Medium"
            elif self._attr_native_value >= 10:
                attributes["battery_status"] = "Low"
            else:
                attributes["battery_status"] = "Critical"

        return attributes

    def update_state(self, value: int) -> None:
        """Update the sensor with new value."""
        _LOGGER.info(f"[AM] [Battery] Updating sensor {self.entity_id} with value: {value}%")

        # Ensure value is within valid range
        value = max(0, min(100, int(value)))

        # Only update if value actually changed to avoid unnecessary history entries
        if self._attr_native_value != value:
            old_value = self._attr_native_value
            self._attr_native_value = value

            # Force state write to ensure history is recorded
            self.async_write_ha_state()

            _LOGGER.info(f"[AM] [Battery] Battery updated from {old_value}% to {value}% - icon: {self.icon}")
        else:
            _LOGGER.debug(f"[AM] [Battery] Battery value unchanged at {value}%")

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
        return PERCENTAGE

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False