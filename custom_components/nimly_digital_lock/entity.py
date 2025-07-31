import asyncio
import logging
import struct
from typing import Any

from homeassistant.components.lock import LockEntity
from homeassistant.components.logbook import async_log_entry
from homeassistant.helpers.device_registry import DeviceEntryType
from zigpy.types import EUI64
from zigpy.zcl.clusters.closures import LockState

from .const import DOMAIN

DATA_ZHA = "zha"

_LOGGER = logging.getLogger(__name__)


class NimlyDigitalLock(LockEntity):

    def register_diagnostic_sensor(self, key: str, sensor: Any) -> None:
        if sensor is None:
            _LOGGER.error(f"[AM] Attempted to register None sensor for key: {key}")
            return

        _LOGGER.info(f"[AM] Registering diagnostic sensor - Key: {key}, Sensor: {sensor.entity_id}")
        self._diagnostic_sensors[key] = sensor
        _LOGGER.info(f"[AM] Registered sensors: {list(self._diagnostic_sensors.keys())}")


    def _update_sensor(self, key, value):
        try:
            if not isinstance(value, (int, float)):
                _LOGGER.error(f"[AM] [_update_sensor] Invalid value type: {type(value)}. Expected int or float")
                return
            value = int(value)

            # First try to get sensor from local registry
            sensor = self._diagnostic_sensors.get(key)

            _LOGGER.info(f"[AM] [_update_sensor] Updating sensor - key: {key}, value: {value}")
            _LOGGER.info(f"[AM] [_update_sensor] Found sensor to update: {sensor.entity_id}")
            sensor.update_state(value)
            _LOGGER.info(f"[AM] [_update_sensor] Sensor update completed with value: {value}")

        except Exception as e:
            _LOGGER.error(f"[AM] [_update_sensor] Failed to update sensor: {str(e)}", exc_info=True)



    def set_cluster_listener(self, listener):
        self._cluster_listener = listener

    def attribute_updated(self, attr_id, value):
        _LOGGER.info(f"Received lock attribute report: {attr_id:#06x}, Value: {value}")

        # 0x0000 - Lock State
        if attr_id == 0x0000:
            self._is_locked = LockState(value) == LockState.Locked

            #lock_state_str = "Locked" if self._is_locked else "Unlocked"
            #self._update_sensor("lock_state", lock_state_str)

            self._hass.data[f"{DOMAIN}:{self._ieee}:lock_state"] = 1 if self._is_locked else 0
            self.async_write_ha_state()
            _LOGGER.info(f"Lock is now: {'locked' if self._is_locked else 'unlocked'}")

            # Update diagnostics entity state attribute
            #self._attr_extra_state_attributes = {
            #    **(self._attr_extra_state_attributes or {}),
            #    "Lock state": "Locked" if self._is_locked else "Unlocked"
            #}

        # 0x0001 - Lock Type (Optional)
        elif attr_id == 0x0001:
            _LOGGER.info(f"Lock type reported: {value}")

        # 0x0002 - Actuator Enabled (Optional)
        elif attr_id == 0x0002:
            enabled_str = "enabled" if value else "disabled"
            _LOGGER.info(f"Actuator is {enabled_str}")

        # 0x0003 - Door State (Optional)
        elif attr_id == 0x0003:
            door_state_map = {
                0x00: "Open",
                0x01: "Closed",
                0x02: "Error",
                0x03: "Jammed",
                0x04: "Forced Open",
            }
            door_state = door_state_map.get(value, f"Unknown ({value})")
            _LOGGER.info(f"Door state: {door_state}")
            async_log_entry(
                self._hass,
                name="Nimly Lock",
                message=f"Door state: {door_state}",
                domain=DOMAIN,
                entity_id=self.entity_id,
            )

        # 0x0021 - Battery Percentage Remaining (Power Cluster)
        elif attr_id == 0x0021:  # Battery Percentage Remaining
            battery_percent = int(value / 2)  # value is in half-percent units
            _LOGGER.info(f"Battery level: {battery_percent}%")

            if (
                    DOMAIN in self._hass.data
                    and "battery_sensors" in self._hass.data[DOMAIN]
            ):
                ieee_no_colons = self._ieee.lower().replace(":", "")
                if ieee_no_colons in self._hass.data[DOMAIN]["battery_sensors"]:
                    self._hass.data[DOMAIN]["battery_sensors"][ieee_no_colons].update_state(battery_percent)
                    _LOGGER.info(f"Updated battery sensor with {battery_percent}%")

            self._update_sensor("battery", battery_percent)
            self.async_write_ha_state()

            async_log_entry(
                self._hass,
                name="Nimly Lock",
                message=f"Battery level: {battery_percent}%",
                domain=DOMAIN,
                entity_id=self.entity_id,
            )

        # 0x0100 - Event Status (User + Action + Method)
        elif attr_id == 0x0100 and isinstance(value, int):
            user_id = value & 0xFFFF
            event = (value >> 16) & 0xFF
            method = (value >> 24) & 0xFF

            event_str = {1: "Locked", 2: "Unlocked"}.get(event, f"Unknown ({event})")
            method_str = {
                0: "Key", 1: "Button", 2: "Code Panel (PIN)",
                3: "Fingerprint", 4: "RFID", 5: "Other"
            }.get(method, f"Unknown ({method})")

            _LOGGER.info(f"Lock Event: {event_str} via {method_str}, User ID: {user_id}")
            self._hass.data[f"{DOMAIN}:{self._ieee}:last_method"] = method_str

            async_log_entry(
                self._hass,
                name="Nimly Lock",
                message=f"{event_str} via {method_str} (User ID: {user_id})",
                domain=DOMAIN,
                entity_id=self.entity_id,
            )

        # 0x0101 - PIN Used
        elif attr_id == 0x0101 and isinstance(value, bytes):
            try:
                pin = value.decode(errors="ignore")
                _LOGGER.info(f"Wrong PIN used: {pin}")
                async_log_entry(
                    self._hass,
                    name="Nimly Lock",
                    message=f"Wrong PIN used",
                    domain=DOMAIN,
                    entity_id=self.entity_id,
                )
            except Exception as e:
                _LOGGER.warning(f"Could not decode PIN value: {value} ({e})")

        # 0x0102 - RFID Used
        elif attr_id == 0x0102 and isinstance(value, bytes):
            try:
                rfid = value.hex().upper()
                _LOGGER.info(f"RFID used: {rfid}")
                async_log_entry(
                    self._hass,
                    name="Nimly Lock",
                    message=f"RFID used: {rfid}",
                    domain=DOMAIN,
                    entity_id=self.entity_id,
                )
            except Exception as e:
                _LOGGER.warning(f"Could not decode RFID value: {value} ({e})")

        # 0x0103 - Diagnostics / Result Code
        # elif attr_id == 0x0103 and isinstance(value, int):
        #     result_code = value
        #     result_str = "OK" if result_code == 0 else f"Error Code {result_code}"
        #     _LOGGER.info(f"Lock operation result: {result_str}")
        #     async_log_entry(
        #         self._hass,
        #         name="Nimly Lock",
        #         message=f"Lock result: {result_str}",
        #         domain=DOMAIN,
        #         entity_id=self.entity_id,
        #     )

        else:
            _LOGGER.debug(f"Unhandled attribute report: {attr_id:#06x} = {value}")

    async def _poll_battery(self):
        _LOGGER.info(f"[AM] [_poll_battery] POLLING BATTERY")

        from .zbt1_support import async_read_attribute_zbt1
        try:
            value = await async_read_attribute_zbt1(
                self.hass,
                self._ieee,
                endpoint=1,
                cluster=0x0001,
                attribute=0x0021
            )

            if isinstance(value, int):
                battery_percent = min(100, round(value / 2))

                _LOGGER.info(f"[AM] [Battery] Polled battery: {battery_percent}%")
                self._update_sensor("battery", battery_percent)
            else:
                _LOGGER.info(f"[AM] [Battery] Not isInstance in battery...Got value: {value}")

        except Exception as e:
            _LOGGER.warning(f"[AM] Failed to poll battery: {e}")

    async def _poll_rssi(self):
        _LOGGER.info(f"[AM] [_poll_rssi] POLLING RSSI")

        from .zbt1_support import async_read_attribute_zbt1

        try:
            value = await async_read_attribute_zbt1(
                self.hass,
                self._ieee,
                endpoint=11,
                cluster=0x0101,
                attribute=0x0103
            )

            if isinstance(value, int):
                # Convert the 32-bit int into 4 bytes (little-endian)
                value_bytes = value.to_bytes(4, byteorder="little")
                parent_nwk, rssi, rssi_dbm = struct.unpack("<HBB", value_bytes)

                # Convert unsigned RSSI dBm to signed int if necessary
                rssi_dbm_signed = rssi_dbm - 256 if rssi_dbm > 127 else rssi_dbm

                _LOGGER.info(
                    f"[AM] [RSSI] Diagnostics Data – Parent NWK: {hex(parent_nwk)}, "
                    f"RSSI: {rssi}, RSSI dBm: {rssi_dbm_signed}"
                )

                self._update_sensor("rssi", rssi_dbm_signed)

            else:
                _LOGGER.warning(f"[AM] [RSSI] Unexpected value type: {value} ({type(value)})")

        except Exception as e:
            _LOGGER.warning(f"[AM] Failed to poll RSSI: {e}")


    async def async_added_to_hass(self):
        self._hass = self.hass

        if "entities" not in self._hass.data[DOMAIN]:
            self._hass.data[DOMAIN]["entities"] = []
        self._hass.data[DOMAIN]["entities"].append(self)

        ieee_key = self._ieee.lower().replace(":", "")

        if "battery_sensors" in self._hass.data[DOMAIN] and ieee_key in self._hass.data[DOMAIN]["battery_sensors"]:
            battery_sensor = self._hass.data[DOMAIN]["battery_sensors"][ieee_key]
            self.register_diagnostic_sensor("battery", battery_sensor)
            _LOGGER.info(f"[AM] Found and registered existing battery sensor: {battery_sensor.entity_id}")

        if "rssi_sensors" in self._hass.data[DOMAIN] and ieee_key in self._hass.data[DOMAIN]["rssi_sensors"]:
            rssi_sensor = self._hass.data[DOMAIN]["rssi_sensors"][ieee_key]
            self.register_diagnostic_sensor("rssi", rssi_sensor)
            _LOGGER.info(f"[AM] Found and registered existing rssi sensor: {rssi_sensor.entity_id}")

        async def battery_polling_loop():
            while True:
                await self._poll_battery()
                await asyncio.sleep(310)

        async def rssi_polling_loop():
            while True:
                await self._poll_rssi()
                await asyncio.sleep(120)

        self.hass.loop.create_task(battery_polling_loop())
        self.hass.loop.create_task(rssi_polling_loop())

        try:
            ieee = EUI64.convert(self._ieee_with_colons)
            zha_data = self._hass.data[DATA_ZHA]

            for (dev_ieee, ep_id, cluster_id, cluster_type), entity in getattr(zha_data, "entities", {}).items():
                if (
                        dev_ieee == ieee
                        and ep_id == 11
                        and cluster_id == 0x0101
                        and cluster_type == "in"
                ):
                    cluster = entity.cluster
                    cluster.add_attribute_listener(self)
                    _LOGGER.info(f"Subscribed to attribute reports on Door Lock cluster for {self._name}")
                    return

        except Exception as e:
            _LOGGER.error(f"Failed to subscribe to cluster updates: {e}")




    async def async_will_remove_from_hass(self):
        if self._remove_listener:
            self._remove_listener()
            self._remove_listener = None

    def __init__(self, hass, ieee, name):
        self._cluster_listener = None
        self._remove_listener = None
        self._hass = hass
        self._ieee = ieee
        self._name = name

        self._ieee_no_colons = ieee.replace(':', '').lower()
        self._ieee_with_colons = ':'.join([self._ieee_no_colons[i:i+2] for i in range(0, len(self._ieee_no_colons), 2)]) if ':' not in ieee else ieee

        zha_device_info = self._hass.data.get(f"{DOMAIN}_ZHA_DEVICE", {})
        self._zha_ieee = zha_device_info.get("zha_ieee", "")

        if not self._zha_ieee:
            self._zha_ieee = self._ieee_with_colons
            _LOGGER.debug(f"No ZHA device found during setup, using own IEEE as fallback: {self._zha_ieee}")

        self._zha_ieee_no_colons = self._zha_ieee.replace(':', '').lower() if self._zha_ieee else ""

        # Add network address (nwk) support
        self._zha_nwk = "0x7FDB"

        # Log all available address formats for debugging
        _LOGGER.info(f"Available formats for device: Original: {ieee}, No colons: {self._ieee_no_colons}, With colons: {self._ieee_with_colons}")
        _LOGGER.info(f"ZHA device: IEEE: {self._zha_ieee}, Network Address: {self._zha_nwk}")

        # Use domain as prefix to ensure uniqueness across integrations
        self._unique_id = f"{DOMAIN}_lock_{self._ieee_no_colons}"
        # Set entity_id format to avoid collisions
        self._attr_entity_id = f"{DOMAIN}_{self._ieee_no_colons}"

        self._is_locked = None
        #self._attrs = {}
        #self._attr_extra_state_attributes = {"Lock state": "Unknown"}
        self._diagnostic_sensors = {}


        _LOGGER.debug(f"Initialized lock with IEEE formats - Original: {ieee}, No colons: {self._ieee_no_colons}, With colons: {self._ieee_with_colons}")

    @property
    def name(self):
        return self._name

    @property
    def unique_id(self):
        return self._unique_id

    @property
    def is_locked(self):
        # Get the current lock state from the data storage
        lock_state = self._hass.data.get(f"{DOMAIN}:{self._ieee}:lock_state")
        # Update the internal state to match
        self._is_locked = bool(lock_state) if lock_state is not None else self._is_locked
        return self._is_locked

    #@property
    #def extra_state_attributes(self):
    #    return self._attr_extra_state_attributes or {}
    #def extra_state_attributes(self):
    #    return self._attrs


    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._ieee)},
            "name": self._name,
            "manufacturer": "Nimly",
            "model": "Nimly Lock",
            "sw_version": "1.0",
            "entry_type": DeviceEntryType.SERVICE,
        }



    async def async_lock(self, **kwargs):
        _LOGGER.info(f"AM Going to lock the lock...")
        _LOGGER.info(f"Locking {self._name} [{self._ieee}]")

        try:
            service_data = {
                "ieee": self._ieee_with_colons,
                "endpoint_id": 11,  # ZBT-1 uses endpoint 11
                "cluster_id": 0x0101,  # Door Lock cluster
                "command": 0x00,  # Lock command
                "command_type": "server",
                "params": {}  # Empty params required by HA
            }

            await self._hass.services.async_call(
                "zha", "issue_zigbee_cluster_command", service_data, blocking=True
            )

            _LOGGER.info(f"Successfully locked {self.name}")
            # Update internal state
            self._is_locked = True
            self._hass.data[f"{DOMAIN}:{self._ieee}:lock_state"] = 1
            self.async_write_ha_state()

            #await self._poll_battery()

            return True

        except Exception as e:
            _LOGGER.error(f"Failed to unlock: {e}")
            return False

    async def async_unlock(self, **kwargs):
        _LOGGER.info(f"AM Going to unlock lock...")
        _LOGGER.info(f"Unlocking {self._name} [{self._ieee}]")

        # Standard ZHA unlock command
        try:
            # Use ZHA service with Door Lock cluster (0x0101) and unlock command (0x01)
            service_data = {
                "ieee": self._ieee_with_colons,
                "endpoint_id": 11,  # ZBT-1 uses endpoint 11
                "cluster_id": 0x0101,  # Door Lock cluster
                "command": 0x01,  # Unlock command
                "command_type": "server",
                "params": {}  # Empty params required by HA
            }

            await self._hass.services.async_call(
                "zha", "issue_zigbee_cluster_command", service_data, blocking=True
            )

            _LOGGER.info(f"Successfully sent unlock command")
            self._is_locked = False
            self._hass.data[f"{DOMAIN}:{self._ieee}:lock_state"] = 0
            self.async_write_ha_state()

            return True
        except Exception as e:
            _LOGGER.error(f"Failed to unlock: {e}")
            return False
