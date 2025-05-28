DOMAIN = "nimly_digital_lock"
import logging, voluptuous as vol
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.typing import HomeAssistantType
from homeassistant.components.lock import LockEntity
from homeassistant.components.sensor import SensorEntity
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.components.sensor import SensorStateClass

_LOGGER = logging.getLogger(__name__)
LOCK_CLUSTER_ID = 0x0101
POWER_CLUSTER_ID = 0x0001
ENDPOINT_ID = 11
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

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    ieee = entry.data["ieee"]
    name = entry.data.get("name", "Nimly - Door")
    lock = ZigbeeDigitalLock(hass, ieee, name)
    sensors = [ZigbeeLockSensor(hass, ieee, attr, f"{name} {attr.replace('_',' ').title()}") for attr in ATTRIBUTE_MAP]
    binary = ZigbeeLockBinarySensor(hass, ieee, f"{name} Battery Low")
    async_add_entities([lock] + sensors + [binary])

class ZigbeeDigitalLock(LockEntity):
    def __init__(self, hass, ieee, name):
        self._hass = hass; self._ieee = ieee; self._name = name
        self._unique_id = f"zigbee_lock_{ieee.replace(':','')}"
        self._is_locked = None; self._attrs = {}
    @property
    def name(self): return self._name
    @property
    def unique_id(self): return self._unique_id
    @property
    def is_locked(self): return self._is_locked
    @property
    def extra_state_attributes(self): return self._attrs
    @property
    def device_info(self):
        return {"identifiers": {(DOMAIN, self._ieee)}, "name": self._name,
                "manufacturer":"Nimly","model":"Nimly Zigbee Door Lock","sw_version":"1.0",
                "entry_type":DeviceEntryType.SERVICE}
    async def async_lock(self, **kwargs):
        # Implement lock command
        self._is_locked = True; self.async_write_ha_state()
    async def async_unlock(self, **kwargs):
        # Implement unlock command
        self._is_locked = False; self.async_write_ha_state()
    async def async_update(self):
        for attr, (cid, aid) in ATTRIBUTE_MAP.items():
            try:
                value = await self._hass.services.async_call("zha","read_zigbee_cluster_attributes",{
                    "ieee":self._ieee,"endpoint_id":ENDPOINT_ID,
                    "cluster_id":cid,"cluster_type":"in","attribute":[aid]},
                    return_response=True)
                val = value[0] if value else None
                self._attrs[attr] = val
                self._hass.data.setdefault(f"{DOMAIN}:{self._ieee}:{attr}", val)
            except Exception: pass

class ZigbeeLockBinarySensor(BinarySensorEntity):
    def __init__(self, hass, ieee, name):
        self._hass=hass; self._ieee=ieee; self._name=name
        self._unique_id=f"zigbee_lock_battery_low_{ieee.replace(':','')}"
    @property
    def name(self): return self._name
    @property
    def unique_id(self): return self._unique_id
    @property
    def is_on(self): return self._hass.data.get(f"{DOMAIN}:{self._ieee}:battery_low")==1
    @property
    def device_class(self): return "battery"
    @property
    def entity_category(self): return EntityCategory.DIAGNOSTIC
    @property
    def device_info(self): return {"identifiers": {(DOMAIN, self._ieee)}}
    @property
    def available(self): return True
    async def async_update(self): pass

class ZigbeeLockSensor(SensorEntity):
    def __init__(self, hass, ieee, attribute, name):
        self._hass=hass; self._ieee=ieee; self._attribute=attribute; self._name=name
        self._unique_id=f"zigbee_lock_sensor_{attribute}_{ieee.replace(':','')}"
    @property
    def name(self): return self._name
    @property
    def unique_id(self): return self._unique_id
    @property
    def state(self): return self._hass.data.get(f"{DOMAIN}:{self._ieee}:{self._attribute}")
    @property
    def device_class(self):
        if self._attribute=="battery": return "battery"
        if self._attribute in ["rssi","rssi_dbm"]: return "signal_strength"
    @property
    def unit_of_measurement(self):
        if self._attribute=="battery": return PERCENTAGE
        if self._attribute=="battery_voltage": return "V"
        if self._attribute=="rssi_dbm": return SIGNAL_STRENGTH_DECIBELS
        if self._attribute=="rssi": return "dB"
    @property
    def entity_category(self): return EntityCategory.DIAGNOSTIC
    @property
    def state_class(self): return SensorStateClass.MEASUREMENT
    @property
    def icon(self):
        if self._attribute=="rssi": return "mdi:signal"
        if self._attribute=="rssi_dbm": return "mdi:wifi"
    @property
    def available(self): return True
    async def async_update(self): pass
