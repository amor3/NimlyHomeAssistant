"""Entity implementations for Nimly Zigbee Digital Lock."""
import logging
from homeassistant.components.lock import LockEntity
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.components.sensor import SensorStateClass
from homeassistant.components.binary_sensor import BinarySensorEntity
from .const import DOMAIN, ATTRIBUTE_MAP, LOCK_CLUSTER_ID, ENDPOINT_ID

_LOGGER = logging.getLogger(__name__)


class NimlyDigitalLock(LockEntity):
    # ... (same as fixed before, keep as is)
    def __init__(self, hass, ieee, name):
        self._hass = hass
        self._ieee = ieee
        self._name = name
        self._unique_id = f"nimly_{ieee.replace(':', '')}"
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
            "manufacturer": "Nimly",
            "model": "Nimly Door Lock Module",
            "sw_version": "1.0",
            "entry_type": DeviceEntryType.SERVICE,
        }

    async def async_lock(self, **kwargs):
        _LOGGER.info(f"Locking {self._name} [{self._ieee}]")
        try:
            # Get ZHA device
            zha_gateway = self._hass.data.get("zha", {}).get("gateway", None)
            if not zha_gateway:
                _LOGGER.error("ZHA gateway not found")
                return False

            zha_device = zha_gateway.get_device(self._ieee)
            if not zha_device:
                _LOGGER.error(f"ZHA device not found for {self._ieee}")
                return False

            # Find the lock cluster and send lock command
            for endpoint in zha_device.endpoints.values():
                if LOCK_CLUSTER_ID in endpoint.in_clusters:
                    lock_cluster = endpoint.in_clusters[LOCK_CLUSTER_ID]
                    result = await lock_cluster.lock_door()
                    _LOGGER.debug(f"Lock command result: {result}")
                    break

            # Update state regardless of response
            await self.async_update()
            self._is_locked = True
            self.async_write_ha_state()
            return True
        except Exception as e:
            _LOGGER.error(f"Error locking: {e}")
            return False

    async def async_unlock(self, **kwargs):
        _LOGGER.info(f"Unlocking {self._name} [{self._ieee}]")
        try:
            # Get ZHA device
            zha_gateway = self._hass.data.get("zha", {}).get("gateway", None)
            if not zha_gateway:
                _LOGGER.error("ZHA gateway not found")
                return False

            zha_device = zha_gateway.get_device(self._ieee)
            if not zha_device:
                _LOGGER.error(f"ZHA device not found for {self._ieee}")
                return False

            # Find the lock cluster and send unlock command
            for endpoint in zha_device.endpoints.values():
                if LOCK_CLUSTER_ID in endpoint.in_clusters:
                    lock_cluster = endpoint.in_clusters[LOCK_CLUSTER_ID]
                    result = await lock_cluster.unlock_door()
                    _LOGGER.debug(f"Unlock command result: {result}")
                    break

            # Update state regardless of response
            await self.async_update()
            self._is_locked = False
            self.async_write_ha_state()
            return True
        except Exception as e:
            _LOGGER.error(f"Error unlocking: {e}")
            return False

    async def async_update(self):
        # Add detailed logging for debugging
        _LOGGER.debug(f"Starting update for lock {self._name} [{self._ieee}]")

        # Use state data from ZHA component
        try:
            # Get ZHA device
            zha_gateway = self._hass.data.get("zha", {}).get("gateway", None)
            if not zha_gateway:
                _LOGGER.error("ZHA gateway not found")
                return

            zha_device = zha_gateway.get_device(self._ieee)
            if not zha_device:
                _LOGGER.error(f"ZHA device not found for {self._ieee}")
                return

            # Find the lock cluster
            for endpoint in zha_device.endpoints.values():
                if LOCK_CLUSTER_ID in endpoint.in_clusters:
                    lock_cluster = endpoint.in_clusters[LOCK_CLUSTER_ID]
                    # Get lock state
                    result = await lock_cluster.read_attributes([0x0000])
                    if result and 0x0000 in result[0]:
                        state = result[0][0x0000]
                        self._is_locked = state == 1
                        _LOGGER.debug(f"Lock state: {state}, is_locked set to {self._is_locked}")
                    break

            # Read other attributes
            _LOGGER.debug(f"Reading attributes for {self._ieee}")
            for attr, (cid, aid) in ATTRIBUTE_MAP.items():
                try:
                    for endpoint in zha_device.endpoints.values():
                        if cid in endpoint.in_clusters:
                            cluster = endpoint.in_clusters[cid]
                            result = await cluster.read_attributes([aid])
                            if result and aid in result[0]:
                                value = result[0][aid]
                                self._attrs[attr] = value
                                self._hass.data[f"{DOMAIN}:{self._ieee}:{attr}"] = value
                                _LOGGER.debug(f"Set {attr} = {value}")
                            break
                except Exception as e:
                    _LOGGER.error(f"Error reading attribute {attr}: {e}")

        except Exception as e:
            _LOGGER.error(f"Failed to update lock: {e}")




class NimlyLockBatteryLowSensor(BinarySensorEntity):
    def __init__(self, hass, ieee, name, entry_id):
        self._hass = hass
        self._ieee = ieee
        self._name = name
        self._unique_id = f"nimly_battery_low_{ieee.replace(':', '')}_{entry_id}"

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
            "name": self._name.replace(" Battery Low", ""),
            "manufacturer": "Nimly",
            "model": "Nimly Door Lock Module",
            "sw_version": "1.0",
            "entry_type": DeviceEntryType.SERVICE,
        }
