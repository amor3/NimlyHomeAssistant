"""Entity implementations for Nimly Zigbee Digital Lock."""

import logging
from homeassistant.core import HomeAssistant
from homeassistant.components.lock import LockEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.components.sensor import SensorStateClass

from .const import DOMAIN, ATTRIBUTE_MAP, LOCK_CLUSTER_ID, ENDPOINT_ID

_LOGGER = logging.getLogger(__name__)

class NimlyDigitalLock(LockEntity):
    def __init__(self, hass: HomeAssistant, ieee: str, name: str):
        self._hass = hass
        self._ieee = ieee
        self._name = name
        self._unique_id = f"nimly_{ieee.replace(':','')}"
        self._is_locked = None
        self._attrs = {}

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def is_locked(self):
        return self._is_locked

    @property
    def extra_state_attributes(self):
        return self._attrs

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._ieee)},
            "name": self._name,
            "manufacturer": "Safe4",
            "model": "Zigbee Door Lock Module",
            "sw_version": "1.0",
            "entry_type": DeviceEntryType.SERVICE,
        }

    async def async_lock(self, **kwargs):
        await self._send_zcl(0x00)
        self._is_locked = True
        self.async_write_ha_state()

    async def async_unlock(self, **kwargs):
        await self._send_zcl(0x01)
        self._is_locked = False
        self.async_write_ha_state()

    async def async_update(self):
        for attr, (cid, aid) in ATTRIBUTE_MAP.items():
            try:
                resp = await self._hass.services.async_call(
                    "zha", "read_zigbee_cluster_attributes",
                    {
                        "ieee": self._ieee,
                        "endpoint_id": ENDPOINT_ID,
                        "cluster_id": cid,
                        "cluster_type": "in",
                        "attribute": [aid],
                    },
                    return_response=True,
                )
                value = resp[0] if resp else None
                self._attrs[attr] = value
                self._hass.data[f"{DOMAIN}:{self._ieee}:{attr}"] = value
            except Exception as e:
                _LOGGER.debug("Error reading %s: %s", attr, e)

    async def _send_zcl(self, command):
        await self._hass.services.async_call(
            "zha", "issue_zigbee_cluster_command",
            {
                "ieee": self._ieee,
                "endpoint_id": ENDPOINT_ID,
                "cluster_id": LOCK_CLUSTER_ID,
                "cluster_type": "out",
                "command": command,
                "command_type": "client",
                "args": [],
            },
        )

class NimlyLockSensor(SensorEntity):
    def __init__(self, hass: HomeAssistant, ieee: str, attribute: str, name: str):
        self._hass = hass
        self._ieee = ieee
        self._attribute = attribute
        self._name = name
        self._unique_id = f"nimly_{attribute}_{ieee.replace(':','')}"

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def state(self):
        return self._hass.data.get(f"{DOMAIN}:{self._ieee}:{self._attribute}")

    @property
    def device_class(self):
        if self._attribute == "battery":
            return "battery"
        if self._attribute in ["rssi", "rssi_dbm"]:
            return "signal_strength"

    @property
    def unit_of_measurement(self):
        if self._attribute == "battery":
            return PERCENTAGE
        if self._attribute == "battery_voltage":
            return "V"
        if self._attribute == "rssi_dbm":
            return SIGNAL_STRENGTH_DECIBELS
        if self._attribute == "rssi":
            return "dB"

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

class NimlyLockBatteryLowSensor(BinarySensorEntity):
    def __init__(self, hass: HomeAssistant, ieee: str, name: str):
        self._hass = hass
        self._ieee = ieee
        self._name = name
        self._unique_id = f"nimly_battery_low_{ieee.replace(':','')}"

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def is_on(self):
        return self._hass.data.get(f"{DOMAIN}:{self._ieee}:battery_low") == 1

    @property
    def device_class(self):
        return "battery"

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC
