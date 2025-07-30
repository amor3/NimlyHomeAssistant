import asyncio
import logging
from homeassistant.components.select import SelectEntity
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.core import HomeAssistant
from zigpy.types import EUI64

from ..const import DOMAIN
from ..zbt1_support import async_read_attribute_zbt1, async_write_attribute_zbt1

_LOGGER = logging.getLogger(__name__)


class SoundVolumeSelect(SelectEntity):
    """Sound volume select for Nimly lock."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_has_entity_name = True
    _attr_icon = "mdi:volume-high"
    _attr_options = ["Off", "Low", "Normal"]

    def __init__(self, hass: HomeAssistant, ieee: str, lock_name: str) -> None:
        """Initialize the select."""
        self.hass = hass
        self._ieee = ieee.lower().replace(":", "")
        self._attr_name = "Sound Volume"
        self._attr_unique_id = f"{DOMAIN}_sound_volume_{self._ieee}"

        clean_name = ''.join(c if c.isalnum() else '_' for c in lock_name.lower()).strip('_')
        while '__' in clean_name:
            clean_name = clean_name.replace('__', '_')
        self.entity_id = f"select.{clean_name}_sound_volume"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(ieee))},
            "name": lock_name,
            "manufacturer": "Nimly",
            "model": "Nimly Lock",
            "sw_version": "1.0",
            "entry_type": DeviceEntryType.SERVICE,
        }

        self._attr_current_option = None  # Will be updated on add

    async def async_added_to_hass(self) -> None:
        try:
            await asyncio.sleep(10)

            value = await async_read_attribute_zbt1(
                self.hass,
                EUI64.convert(self._ieee),
                endpoint=11,
                cluster=0x0101,
                attribute=0x0024,
            )
            if isinstance(value, int) and value in (0, 1, 2):
                self._attr_current_option = self._attr_options[value]
                _LOGGER.info(f"[AM] [SoundVolume] Read initial value: {value}")
            else:
                _LOGGER.warning(f"[AM] [SoundVolume] Unexpected initial value: {value}")
        except Exception as e:
            _LOGGER.warning(f"[AM] [SoundVolume] Failed to read volume: {e}")

        self.async_write_ha_state()

    async def async_select_option(self, option: str) -> None:
        """Change the selected option."""
        if option not in self._attr_options:
            _LOGGER.error(f"[AM] [SoundVolume] Invalid option: {option}")
            return

        value = self._attr_options.index(option)

        try:

            await async_write_attribute_zbt1(
                self.hass,
                ieee=self._ieee,
                endpoint_id=11,
                cluster_id=0x0101,
                attribute_id=0x0024,
                value=value,
            )

            self._attr_current_option = option
            self.async_write_ha_state()
            _LOGGER.info(f"[AM] [SoundVolume] Changed to: {option} ({value})")
        except Exception as e:
            _LOGGER.error(f"[AM] [SoundVolume] Failed to write volume: {e}")

    @property
    def icon(self) -> str:
        """Return the icon based on volume level."""
        icons = {
            "Off": "mdi:volume-off",
            "Low": "mdi:volume-medium",
            "Normal": "mdi:volume-high",
        }
        return icons.get(self._attr_current_option, "mdi:volume-medium")

    @property
    def extra_state_attributes(self):
        """Return additional state attributes."""
        if self._attr_current_option:
            return {
                "volume_label": self._attr_current_option,
                "volume_level": self._attr_options.index(self._attr_current_option),
            }
        return {}

    @property
    def should_poll(self) -> bool:
        """No polling needed."""
        return False
