import asyncio
import logging
from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.helpers.device_registry import DeviceEntryType
from zigpy.types import EUI64

from ..zbt1_support import async_write_attribute_zbt1, async_read_attribute_zbt1
from ..const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class AutoRelockSwitch(SwitchEntity):

    def __init__(self, hass, ieee, lock_name: str):
        self._hass = hass
        self._ieee = ieee.lower()
        self._ieee_no_colons = self._ieee.replace(":", "")
        self._ieee_with_colons = ":".join(self._ieee[i:i + 2] for i in range(0, len(self._ieee), 2)) if ":" not in self._ieee else self._ieee

        self._attr_name = "Auto Relock"
        self._attr_unique_id = f"{DOMAIN}_{self._ieee_no_colons}_auto_relock"
        self._attr_entity_category = EntityCategory.CONFIG
        self._attr_entity_registry_enabled_default = True
        self._attr_should_poll = False

        clean_name = ''.join(c if c.isalnum() else '_' for c in lock_name.lower()).strip('_')
        while '__' in clean_name:
            clean_name = clean_name.replace('__', '_')
        self.entity_id = f"switch.{clean_name}_auto_relock"

        self._attr_device_info = {
            "identifiers": {(DOMAIN, str(ieee))},
            "name": lock_name,
            "manufacturer": "Nimly",
            "model": "Nimly Lock",
            "sw_version": "1.0",
            "entry_type": DeviceEntryType.SERVICE,
        }

        self._attr_is_on = False  # default state before reading from device

    async def async_added_to_hass(self):

        await super().async_added_to_hass()

        #await log_basic_info(self._hass, self._ieee)

        try:
            value = await async_read_attribute_zbt1(
                self.hass,
                EUI64.convert(self._ieee),
                endpoint=11,
                cluster=0x0101,
                attribute=0x0023
            )

            if isinstance(value, int):
                self._attr_is_on = value >= 1
                _LOGGER.info(f"[AutoRelockSwitch] Initial value: {value} -> {'On' if self._attr_is_on else 'Off'}")
                self.async_write_ha_state()
            else:
                _LOGGER.warning(f"[AutoRelockSwitch] Unexpected attribute value: {value} ({type(value)})")
        except Exception as e:
            _LOGGER.warning(f"[AutoRelockSwitch] Failed to read Auto Relock: {e}")

    async def async_turn_on(self, **kwargs):
        """Turn on auto relock (write 1)."""
        try:
            await async_write_attribute_zbt1(
                self._hass,
                ieee=self._ieee,
                endpoint_id=11,
                cluster_id=0x0101,
                attribute_id=0x0023,
                value=1
            )
            self._attr_is_on = True
            self.async_write_ha_state()
            _LOGGER.info("[AutoRelockSwitch] Auto Relock enabled (1)")
        except Exception as e:
            _LOGGER.error(f"[AutoRelockSwitch] Failed to turn ON: {e}", exc_info=True)

    async def async_turn_off(self, **kwargs):
        """Turn off auto relock (write 0)."""
        try:
            await async_write_attribute_zbt1(
                self._hass,
                ieee=self._ieee,
                endpoint_id=11,
                cluster_id=0x0101,
                attribute_id=0x0023,
                value=0
            )
            self._attr_is_on = False
            self.async_write_ha_state()
            _LOGGER.info("[AutoRelockSwitch] Auto Relock disabled (0)")
        except Exception as e:
            _LOGGER.error(f"[AutoRelockSwitch] Failed to turn OFF: {e}", exc_info=True)



async def log_basic_info(hass, ieee):
    try:
        ieee_obj = EUI64.convert(ieee)
        endpoint = 1
        cluster_id = 0x0000  # Basic Cluster
        attributes = {
            0x0000: "ZCL Version",
            0x0001: "Application Version",
            0x0002: "Stack Version",
            0x0003: "HW Version",
            0x0004: "Manufacturer Name",
            0x0005: "Model Identifier",
            0x0006: "Date Code",
            0x0007: "Power Source",
            0x0010: "Location",
            0x0012: "BDB Enabled",
            0x4000: "SW Version",
        }

        for attr_id, name in attributes.items():
            value = await async_read_attribute_zbt1(
                hass, ieee_obj, endpoint=endpoint, cluster=cluster_id, attribute=attr_id
            )
            _LOGGER.info(f"[Zigbee Basic Info] {name} (0x{attr_id:04X}): {value}")

    except Exception as e:
        _LOGGER.error(f"[Zigbee Basic Info] Failed to read basic info: {e}")