DOMAIN = "zigbee_digital_lock"

import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.components.lock import LockEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import DEVICE_CLASS_BATTERY, DEVICE_CLASS_SIGNAL_STRENGTH, PERCENTAGE
from homeassistant.helpers.device_registry import DeviceEntryType

_LOGGER = logging.getLogger(__name__)

LOCK_CLUSTER_ID = 0x0101
POWER_CLUSTER_ID = 0x0001
PROFILE_ID = 0x0104
ENDPOINT_ID = 11

ZCL_COMMAND_LOCK = 0x00
ZCL_COMMAND_UNLOCK = 0x01

ATTRIBUTE_MAP = {
    "battery": (POWER_CLUSTER_ID, 0x0021),
    "battery_voltage": (POWER_CLUSTER_ID, 0x0020),
    "battery_low": (POWER_CLUSTER_ID, 0x9000),
    "diagnostics": (LOCK_CLUSTER_ID, 0x0103),
    "auto_relock_time": (LOCK_CLUSTER_ID, 0x0023),
    "sound_volume": (LOCK_CLUSTER_ID, 0x0024),
    "total_users": (LOCK_CLUSTER_ID, 0x0011),
    "pin_users": (LOCK_CLUSTER_ID, 0x0012),
    "rfid_users": (LOCK_CLUSTER_ID, 0x0013),
    "max_pin_length": (LOCK_CLUSTER_ID, 0x0017),
    "min_pin_length": (LOCK_CLUSTER_ID, 0x0018),
    "max_rfid_length": (LOCK_CLUSTER_ID, 0x0019),
    "min_rfid_length": (LOCK_CLUSTER_ID, 0x001A),
    "pin_used": (LOCK_CLUSTER_ID, 0x0101),
    "rfid_used": (LOCK_CLUSTER_ID, 0x0102),
    "lock_type": (LOCK_CLUSTER_ID, 0x0001),
    "actuator_enabled": (LOCK_CLUSTER_ID, 0x0002),
    "door_state": (LOCK_CLUSTER_ID, 0x0003),
}

SENSOR_ATTRIBUTES = ["battery", "battery_voltage", "rssi", "rssi_dbm"]

from homeassistant.components.binary_sensor import BinarySensorEntity

async def async_setup_entry(hass: HomeAssistant, config_entry: ConfigEntry, async_add_entities):
    ieee = config_entry.data.get("ieee")
    name = config_entry.data.get("name", "Safe4 Front Door")
    lock = ZigbeeDigitalLock(hass, ieee, name)
    sensors = [ZigbeeLockSensor(hass, ieee, attr, f"{name} {attr.replace('_', ' ').title()}") for attr in SENSOR_ATTRIBUTES]
    binary = ZigbeeLockBinarySensor(hass, ieee, f"{name} Battery Low")
    async_add_entities([lock] + sensors + [binary])

class ZigbeeDigitalLock(LockEntity):
    def __init__(self, hass, ieee, name):
        self._hass = hass
        self._ieee = ieee
        self._name = name
        self._unique_id = f"zigbee_lock_{ieee.replace(':', '')}"
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
        await self._send_zcl_command(ZCL_COMMAND_LOCK)
        self._is_locked = True
        self.async_write_ha_state()

    async def async_unlock(self, **kwargs):
        await self._send_zcl_command(ZCL_COMMAND_UNLOCK)
        self._is_locked = False
        self.async_write_ha_state()

    async def async_update(self):
        for attr_name, (cluster_id, attr_id) in ATTRIBUTE_MAP.items():
            try:
                value = await self._read_zigbee_attribute(cluster_id, attr_id)
                if attr_name == "diagnostics" and isinstance(value, int):
                    value_bytes = value.to_bytes(4, byteorder="little")
                    self._attrs["parent_nwk"] = int.from_bytes(value_bytes[0:2], byteorder="little")
                    self._hass.data[f"{DOMAIN}:{self._ieee}:rssi"] = value_bytes[2]
                    self._hass.data[f"{DOMAIN}:{self._ieee}:rssi_dbm"] = value_bytes[3]
                else:
                    self._attrs[attr_name] = value
                    if attr_name in ["battery", "battery_voltage", "battery_low"]:
                        self._hass.data[f"{DOMAIN}:{self._ieee}:{attr_name}"] = value
            except Exception as e:
                _LOGGER.debug("Failed to read %s: %s", attr_name, str(e))

    async def _send_zcl_command(self, command_id: int, payload=None):
        await self._hass.services.async_call("zha", "issue_zigbee_cluster_command", {
            "ieee": self._ieee,
            "endpoint_id": ENDPOINT_ID,
            "cluster_id": LOCK_CLUSTER_ID,
            "cluster_type": "out",
            "command": command_id,
            "command_type": "client",
            "args": payload or [],
        })

    async def _read_zigbee_attribute(self, cluster_id, attribute_id):
        response = await self._hass.services.async_call(
            "zha", "read_zigbee_cluster_attributes",
            {
                "ieee": self._ieee,
                "endpoint_id": ENDPOINT_ID,
                "cluster_id": cluster_id,
                "cluster_type": "in",
                "attribute": [attribute_id]
            },
            return_response=True
        )
        return response[0] if response else None

from homeassistant.helpers.entity import EntityCategory
from homeassistant.components.sensor import SensorStateClass

class ZigbeeLockBinarySensor(BinarySensorEntity):
    def __init__(self, hass, ieee, name):
        self._hass = hass
        self._ieee = ieee
        self._name = name
        self._unique_id = f"zigbee_lock_battery_low_{ieee.replace(':', '')}"

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

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._ieee)},
        }

    async def async_update(self):
        pass

class ZigbeeLockSensor(SensorEntity):
    def __init__(self, hass, ieee, attribute, name):
        self._hass = hass
        self._ieee = ieee
        self._attribute = attribute
        self._name = name
        self._unique_id = f"zigbee_lock_sensor_{attribute}_{ieee.replace(':', '')}"

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
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._ieee)},
        }

    @property
    def device_class(self):
        if self._attribute == "battery":
            return DEVICE_CLASS_BATTERY
        if self._attribute in ["rssi", "rssi_dbm"]:
            return DEVICE_CLASS_SIGNAL_STRENGTH

    @property
    def unit_of_measurement(self):
        if self._attribute == "battery":
            return PERCENTAGE
        if self._attribute == "battery_voltage":
            return "V"
        if self._attribute == "rssi_dbm":
            return "dBm"
        if self._attribute == "rssi":
            return "dB"

    @property
    def entity_category(self):
        return EntityCategory.DIAGNOSTIC

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def icon(self):
        if self._attribute == "rssi":
            return "mdi:signal"
        if self._attribute == "rssi_dbm":
            return "mdi:wifi"
        return None

    @property
    def available(self):
        return DOMAIN in self._hass.data and self._ieee is not None

    async def async_update(self):
        pass
