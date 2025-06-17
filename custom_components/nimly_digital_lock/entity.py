import logging
from homeassistant.components.lock import LockEntity
from homeassistant.components.logbook import async_log_entry
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.components.binary_sensor import BinarySensorEntity
from zigpy.types import EUI64
from zigpy.zcl.clusters.closures import LockState

from .const import DOMAIN, ATTRIBUTE_MAP, LOCK_CLUSTER_ID, POWER_CLUSTER_ID, ENDPOINT_ID
DATA_ZHA = "zha"

# Import from zha_mapping
from .zha_mapping import (
    LOCK_COMMANDS
)
from .zbt1_support import async_read_attribute_zbt1, async_send_command_zbt1, get_zbt1_endpoints


_LOGGER = logging.getLogger(__name__)



class NimlyDigitalLock(LockEntity):

    def set_cluster_listener(self, listener):
        self._cluster_listener = listener

    def attribute_updated(self, attr_id, value):
        _LOGGER.info(f"Received lock attribute report: {attr_id:#06x}, Value: {value}")

        # 0x0000 - Lock State
        if attr_id == 0x0000:
            self._is_locked = LockState(value) == LockState.Locked
            self._hass.data[f"{DOMAIN}:{self._ieee}:lock_state"] = 1 if self._is_locked else 0
            self.async_write_ha_state()
            _LOGGER.info(f"Lock is now: {'locked' if self._is_locked else 'unlocked'}")

            # Update diagnostics entity state attribute
            self._attr_extra_state_attributes = {
                **(self._attr_extra_state_attributes or {}),
                "Lock state": "Locked" if self._is_locked else "Unlocked"
            }

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
        elif attr_id == 0x0021:
            battery_percent = int(value / 2)
            _LOGGER.info(f"Battery level: {battery_percent}%")
            self._attr_extra_state_attributes = {
                **(self._attr_extra_state_attributes or {}),
                "Battery level": f"{battery_percent}%"
            }
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
        elif attr_id == 0x0103 and isinstance(value, int):
            result_code = value
            result_str = "OK" if result_code == 0 else f"Error Code {result_code}"
            _LOGGER.info(f"Lock operation result: {result_str}")
            async_log_entry(
                self._hass,
                name="Nimly Lock",
                message=f"Lock result: {result_str}",
                domain=DOMAIN,
                entity_id=self.entity_id,
            )

        else:
            _LOGGER.debug(f"Unhandled attribute report: {attr_id:#06x} = {value}")












    async def async_added_to_hass(self):
        self._hass = self.hass

        try:
            ieee = EUI64.convert(self._ieee_with_colons)
            zha_data = self._hass.data[DATA_ZHA]

            # Loop through all known entities to find the Door Lock cluster
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


    """   
    async def async_added_to_hass(self):
        self._hass = self.hass

        try:

            ieee = EUI64.convert(self._ieee_with_colons)
            zha_data = self._hass.data["zha"]
            _LOGGER.info(f"ANDRE DATA to be zha_data: {zha_data}")

            gateway = zha_data.gateway_proxy
            _LOGGER.info(f"ANDRE DATA to be gateway: {gateway}")

            # Use async_get_device instead of accessing .devices
            zha_device = await gateway.async_get_device(ieee)
            if zha_device is None:
                _LOGGER.error(f"Could not find ZHA device for IEEE: {self._ieee_with_colons}")
                return

            # Now access the endpoint and cluster
            endpoint = zha_device.device.endpoints[11]
            cluster = endpoint.in_clusters[0x0101]  # Door Lock cluster

            # Add attribute listener
            cluster.add_attribute_listener(self)

            def attribute_updated(self, attribute, value):
                _LOGGER.info(f"ANDRE WAS HERE Lock attribute updated: {attribute} = {value}")
                if attribute == 0x0000:  # Lock State attribute
                    self._is_locked = value == 1
                    self.async_write_ha_state()

            # Setup attribute listener (Zigpy level)
            def handle_report(attribute_id, value):
                _LOGGER.info(f"ANDRE AM AM Zigbee report: attr={attribute_id}, value={value}")
                if attribute_id == 0x0100:
                    val = value.value if hasattr(value, "value") else value
                    event = (val >> 16) & 0xFF
                    method = (val >> 24) & 0xFF
                    user_id = val & 0xFFFF
                    self._is_locked = event == 0x01
                    self.async_write_ha_state()

            cluster.add_attribute_listener(handle_report)
            cluster.add_attribute_listener(attribute_updated)
            _LOGGER.info("Subscribed to Door Lock cluster attribute reports")

        except Exception as e:
            _LOGGER.error(f"Failed to subscribe to cluster updates: {e}")
        """


    async def async_will_remove_from_hass(self):
        if self._remove_listener:
            self._remove_listener()
            self._remove_listener = None





    async def _send_zigbee_command(self, command, cluster_id=LOCK_CLUSTER_ID, endpoint_id=11, params={}):
        # Determine which service to use (zha or zigbee)
        service_domains = ["zigbee", "zha"]
        _LOGGER.debug(f"Trying service domains for commands with command {command}, cluster {cluster_id}, endpoint {endpoint_id}")

        # Try multiple service methods as different integrations use different names
        service_methods = ["issue_zigbee_cluster_command", "send_zigbee_command", "execute_zigbee_command", "command"]

        # Keep track of whether we found any service
        found_service = False
        service_domain = None
        service_method = None

        # First check if any of the services exist
        for domain in service_domains:
            for method in service_methods:
                if self._hass.services.has_service(domain, method):
                    _LOGGER.info(f"Found available service: {domain}.{method}")
                    service_domain = domain
                    service_method = method
                    found_service = True
                    # Don't break here, we want to log all available services

        if not found_service:
            # No services available, cannot operate without them
            _LOGGER.error("No Zigbee services available for sending commands. Cannot communicate with lock.")
            return False

        # Use the first available service that was found
        _LOGGER.info(f"Using {service_domain}.{service_method} for sending Zigbee commands")

        # Try with different address formats, only using IEEE format (nwk not supported directly)
        formats_to_try = [
            # Original device formats
            {"ieee": self._ieee},
            {"ieee": self._ieee_no_colons},
            {"ieee": self._ieee_with_colons},
            # ZHA device formats
            {"ieee": self._zha_ieee},
            {"ieee": self._zha_ieee_no_colons},
            # Try with network address as ieee parameter
            {"ieee": self._zha_nwk}
        ]

        for address_format in formats_to_try:
            try:
                # For Nabu Casa ZBT-1, command format is essentially the same
                service_data = {
                    # Add the appropriate address key (ieee or nwk)
                    **address_format,
                    "command": command,
                    "command_type": "server",
                    "cluster_id": cluster_id,
                    "endpoint_id": endpoint_id
                }

                # Add params if not empty
                if params:
                    service_data["params"] = params

                _LOGGER.debug(f"Sending {service_domain} command using {service_method}: {service_data}")

                # First check if the service is available
                if not self._hass.services.has_service(service_domain, service_method):
                    _LOGGER.warning(f"Service {service_domain}.{service_method} is not available")
                    continue

                await self._hass.services.async_call(
                    service_domain, service_method, service_data
                )
                # Get the address used (either IEEE or nwk) for the log message
                address_used = "unknown address"
                if "ieee" in address_format:
                    address_used = f"IEEE {address_format['ieee']}"
                elif "nwk" in address_format:
                    address_used = f"NWK {address_format['nwk']}"
                _LOGGER.info(f"Successfully sent command to {address_used} using {service_domain}.{service_method}")
                return True
            except Exception as e:
                # Get the address used (either IEEE or nwk) for the log message
                address_used = "unknown address"
                if "ieee" in address_format:
                    address_used = f"IEEE {address_format['ieee']}"
                elif "nwk" in address_format:
                    address_used = f"NWK {address_format['nwk']}"
                _LOGGER.warning(f"Failed to send command {command} with {address_used}: {e}")

        # If we get here, all attempts failed
        _LOGGER.error(f"Failed to send command {command} with all IEEE formats")

        # Let's try one more approach - with numeric command ID instead of string command
        # This is helpful for some Zigbee implementations including Nabu Casa
        # Use the properly imported LOCK_COMMANDS from above
        if command in LOCK_COMMANDS:
            command_id = LOCK_COMMANDS[command]
            _LOGGER.debug(f"Trying with numeric command ID {command_id} instead of string command {command}")

            for ieee_format in formats_to_try:
                try:
                    service_data = {
                        "ieee": ieee_format,
                        "command": command_id,  # Use numeric ID instead of string
                        "command_type": "server",
                        "cluster_id": cluster_id,
                        "endpoint_id": endpoint_id
                    }

                    if params:
                        service_data["params"] = params

                    _LOGGER.debug(f"Sending {service_domain} command with ID: {service_data}")
                    await self._hass.services.async_call(
                        service_domain, "issue_zigbee_cluster_command", service_data
                    )
                    return True
                except Exception as e:
                    _LOGGER.warning(f"Failed to send command ID {command_id} with IEEE format {ieee_format}: {e}")

        _LOGGER.error(f"All attempts to send command {command} failed")
        return False

    async def _read_zigbee_attribute(self, cluster_id, attribute_id, endpoint_id=1):
        # Try multiple service domains
        service_domains = ["zigbee", "zha"]
        _LOGGER.debug(f"Trying service domains for attribute read")

        # Try multiple service methods as different integrations use different names
        service_methods = [
            "read_zigbee_cluster_attribute", 
            "get_zigbee_cluster_attribute",
            "read_attribute", 
            "get_attribute"
        ]

        # Keep track of whether we found any service
        found_service = False
        service_domain = None
        service_method = None

        # First check if any of the services exist
        for domain in service_domains:
            for method in service_methods:
                if self._hass.services.has_service(domain, method):
                    _LOGGER.info(f"Found available attribute read service: {domain}.{method}")
                    service_domain = domain
                    service_method = method
                    found_service = True
                    # Don't break here, we want to log all available services

        if not found_service:
            # No services available, cannot operate without them
            _LOGGER.error("No Zigbee services available for reading attributes. Cannot communicate with lock.")
            return False

        # Use the first available service that was found
        _LOGGER.info(f"Using {service_domain}.{service_method} for reading Zigbee attributes")

        # Try with different IEEE formats, including the specific ZHA IEEE address
        formats_to_try = [self._ieee, self._ieee_no_colons, self._ieee_with_colons, self._zha_ieee, self._zha_ieee_no_colons]

        # Log the available endpoints for ZBT-1
        try:
            zbt1_endpoints = await get_zbt1_endpoints(self._hass, self._ieee)
            _LOGGER.debug(f"Available ZBT-1 endpoints for {self._ieee}: {zbt1_endpoints}")

            # Also try to get endpoints for the specific ZHA device
            zha_zbt1_endpoints = await get_zbt1_endpoints(self._hass, self._zha_ieee)
            _LOGGER.debug(f"Available ZBT-1 endpoints for ZHA device {self._zha_ieee}: {zha_zbt1_endpoints}")
        except Exception as e:
            _LOGGER.warning(f"Error getting ZBT-1 endpoints: {e}")

        for ieee_format in formats_to_try:
            try:
                # Different parameter formats for different integrations
                if service_domain == "zigbee":  # Nabu Casa Zigbee
                    service_data = {
                        "ieee": ieee_format,
                        "cluster_id": cluster_id,
                        "cluster_type": "in",
                        "attribute": attribute_id,
                        "endpoint_id": endpoint_id
                    }
                else:  # Standard ZHA
                    service_data = {
                        "ieee": ieee_format,
                        "cluster_id": cluster_id,
                        "cluster_type": "in",
                        "attribute": attribute_id,
                        "endpoint_id": endpoint_id
                    }

                # Remove None values as they may cause issues
                service_data = {k: v for k, v in service_data.items() if v is not None}

                _LOGGER.debug(f"Reading {service_domain} attribute using {service_method}: {service_data}")
                await self._hass.services.async_call(
                    service_domain, service_method, service_data
                )
                return True
            except Exception as e:
                _LOGGER.warning(f"Failed to read attribute {attribute_id} with IEEE format {ieee_format}: {e}")

        _LOGGER.error(f"Failed to read attribute {attribute_id} with all IEEE formats")
        return False

    def __init__(self, hass, ieee, name):
        self._cluster_listener = None
        self._remove_listener = None
        self._hass = hass
        self._ieee = ieee
        self._name = name

        # Normalize IEEE formats
        self._ieee_no_colons = ieee.replace(':', '').lower()
        self._ieee_with_colons = ':'.join([self._ieee_no_colons[i:i+2] for i in range(0, len(self._ieee_no_colons), 2)]) if ':' not in ieee else ieee

        # Get the actual ZHA device IEEE address from Home Assistant if available
        zha_device_info = self._hass.data.get(f"{DOMAIN}_ZHA_DEVICE", {})
        self._zha_ieee = zha_device_info.get("zha_ieee", "")

        # If no ZHA device was found during setup, we'll use our own IEEE as fallback
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
        self._attr_extra_state_attributes = {}

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

    @property
    def extra_state_attributes(self):
        return self._attr_extra_state_attributes or {}
    #def extra_state_attributes(self):
    #    return self._attrs


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



    # async def async_update(self):
    #     #_LOGGER.info(f"Updating lock state for {self._name} [{self._ieee}]")
    #     #_LOGGER.info(f"Updating lock, extra_state_attributes: {self.extra_state_attributes}")
    #
    #     try:
    #         ieee = EUI64.convert(self._ieee_with_colons)
    #         zha_data = self._hass.data["zha"]
    #
    #         #_LOGGER.info(f"AM zha_data: {zha_data}]")
    #
    #         # Find the ZHA entity for Door Lock cluster (0x0101) on endpoint 11
    #         for (dev_ieee, ep_id, cluster_id, cluster_type), entity in zha_data.entities.items():
    #             if (
    #                     dev_ieee == ieee
    #                     and ep_id == 11
    #                     and cluster_id == 0x0101
    #                     and cluster_type == "in"
    #             ):
    #                 cluster = entity.cluster
    #                 break
    #         else:
    #             _LOGGER.warning(f"Lock entity not found in ZHA entity map for {self._ieee}")
    #             return
    #
    #         # Read lock state (0x0000)
    #         result = await cluster.read_attributes([0x0000])
    #         lock_state = result.get(0x0000)
    #
    #         if lock_state is not None:
    #             self._is_locked = lock_state == 1
    #             _LOGGER.info(f"Lock state is: {'locked' if self._is_locked else 'unlocked'}")
    #             self._hass.data[f"{DOMAIN}:{self._ieee}:lock_state"] = lock_state
    #         else:
    #             _LOGGER.warning(f"Lock did not return Lock State attribute for {self._ieee}")
    #
    #     except Exception as e:
    #         _LOGGER.warning(f"ANDRE AM - FAIL lock state: {e}")
    #
    #
    #
    #
    #     """
    #     # Read battery percentage (0x0021) from Power cluster (0x0001)
    #     try:
    #         service_data = {
    #             "ieee": self._ieee_with_colons,
    #             "endpoint_id": 11,  # ZBT-1 uses endpoint 11
    #             "cluster_id": 0x0001,  # Power Configuration cluster
    #             "cluster_type": "in",
    #             "attribute": 0x0021  # Battery percentage remaining
    #         }
    #
    #         result = await self._hass.services.async_call(
    #             "zha", "issue_zigbee_cluster_command", service_data, blocking=True, return_response=True
    #         )
    #
    #         if result is not None and 0 <= result <= 100:
    #             _LOGGER.info(f"Battery percentage read result: {result}%")
    #             self._hass.data[f"{DOMAIN}:{self._ieee}:battery"] = result
    #
    #             # Set battery_low status if below 15%
    #             battery_low = result < 15
    #             battery_low_value = 1 if battery_low else 0
    #             self._hass.data[f"{DOMAIN}:{self._ieee}:battery_low"] = battery_low_value
    #     except Exception as e:
    #         _LOGGER.warning(f"Failed to read battery percentage: {e}")
    #
    #     # Try to read attributes using the Safe4 module with multiple endpoints
    #     # The Safe4 module already handles multiple endpoints and IEEE formats
    #     try:
    #         # Read lock state using Safe4 module
    #         _LOGGER.info(f"Reading lock state from cluster {SAFE4_DOOR_LOCK_CLUSTER} using Safe4 module")
    #         lock_state = await read_safe4_attribute(
    #             self._hass,
    #             self._ieee_with_colons,
    #             SAFE4_DOOR_LOCK_CLUSTER,
    #             0x0000  # Lock state attribute
    #         )
    #
    #         if lock_state is not None:
    #             _LOGGER.info(f"Successfully read lock state: {lock_state}")
    #             # Store the result - use both IEEE formats to ensure consistency
    #             self._hass.data[f"{DOMAIN}:{self._ieee}:lock_state"] = lock_state
    #             self._hass.data[f"{DOMAIN}:{self._ieee_with_colons}:lock_state"] = lock_state
    #             self._is_locked = (lock_state == 1)
    #         else:
    #             # Try alternative method
    #             _LOGGER.debug("Safe4 module failed for lock state, trying ZBT-1 method")
    #             lock_state = await async_read_attribute_zbt1(
    #                 self._hass,
    #                 self._ieee_with_colons,
    #                 LOCK_CLUSTER_ID,
    #                 0x0000,  # Lock state attribute
    #                 endpoint_id=11  # Start with endpoint 11 per Safe4 spec
    #             )
    #
    #             if lock_state is not None:
    #                 _LOGGER.info(f"Successfully read lock state via ZBT1: {lock_state}")
    #                 self._hass.data[f"{DOMAIN}:{self._ieee}:lock_state"] = lock_state
    #                 self._hass.data[f"{DOMAIN}:{self._ieee_with_colons}:lock_state"] = lock_state
    #                 self._is_locked = (lock_state == 1)
    #
    #         # Read battery level
    #         _LOGGER.debug(f"Reading battery level from cluster {SAFE4_POWER_CLUSTER}")
    #         battery = await read_safe4_attribute(
    #             self._hass,
    #             self._ieee_with_colons,
    #             SAFE4_POWER_CLUSTER,
    #             0x0021  # Battery percentage remaining
    #         )
    #
    #         if battery is not None:
    #             _LOGGER.info(f"Successfully read battery level: {battery}")
    #             # Store the result in both formats for consistency
    #             self._hass.data[f"{DOMAIN}:{self._ieee}:battery"] = battery
    #             self._hass.data[f"{DOMAIN}:{self._ieee_with_colons}:battery"] = battery
    #
    #             # Also set battery_low status if below 15%
    #             if isinstance(battery, (int, float)) and battery < 15:
    #                 self._hass.data[f"{DOMAIN}:{self._ieee}:battery_low"] = 1
    #             else:
    #                 self._hass.data[f"{DOMAIN}:{self._ieee}:battery_low"] = 0
    #         else:
    #             # Try alternative method
    #             _LOGGER.debug("Safe4 module failed for battery, trying ZBT-1 method")
    #             battery = await async_read_attribute_zbt1(
    #                 self._hass,
    #                 self._ieee_with_colons,
    #                 POWER_CLUSTER_ID,
    #                 0x0021,  # Battery percentage remaining
    #                 endpoint_id=11  # Start with endpoint 11 per Safe4 spec
    #             )
    #
    #             if battery is not None:
    #                 _LOGGER.info(f"Successfully read battery via ZBT1: {battery}")
    #                 self._hass.data[f"{DOMAIN}:{self._ieee}:battery"] = battery
    #                 self._hass.data[f"{DOMAIN}:{self._ieee_with_colons}:battery"] = battery
    #
    #                 # Also set battery_low status if below 15%
    #                 if isinstance(battery, (int, float)) and battery < 15:
    #                     self._hass.data[f"{DOMAIN}:{self._ieee}:battery_low"] = 1
    #                 else:
    #                     self._hass.data[f"{DOMAIN}:{self._ieee}:battery_low"] = 0
    #
    #         # Try to read battery voltage as well
    #         battery_voltage = await read_safe4_attribute(
    #             self._hass,
    #             self._ieee_with_colons,
    #             SAFE4_POWER_CLUSTER,
    #             0x0020  # Battery voltage
    #         )
    #
    #         if battery_voltage is not None:
    #             # Convert from millivolts to volts if needed
    #             if battery_voltage > 100:
    #                 battery_voltage = battery_voltage / 1000.0
    #
    #             _LOGGER.info(f"Successfully read battery voltage: {battery_voltage}V")
    #             self._hass.data[f"{DOMAIN}:{self._ieee}:battery_voltage"] = battery_voltage
    #             self._hass.data[f"{DOMAIN}:{self._ieee_with_colons}:battery_voltage"] = battery_voltage
    #
    #     except Exception as e:
    #         _LOGGER.warning(f"Error reading attributes from device: {str(e)}")
    #     """
    #
    #     """
    #     # Use current value from data store
    #     lock_state = self._hass.data.get(f"{DOMAIN}:{self._ieee}:lock_state")
    #     if lock_state is not None:
    #         self._is_locked = (lock_state == 1)
    #         _LOGGER.debug(f"Current lock state: {self._is_locked}")
    #     else:
    #         # If no state could be read, show an error
    #         _LOGGER.error("Could not determine lock state - Nordic ZBT-1 device may be unreachable")
    #         # Default to locked for security
    #         self._is_locked = True
    #         self._hass.data[f"{DOMAIN}:{self._ieee}:lock_state"] = 1
    #
    #     # Debug: Log all lock-related keys in hass.data to help troubleshoot
    #     lock_keys = []
    #     for key in self._hass.data:
    #         if f"{DOMAIN}:" in key:
    #             lock_keys.append(key)
    #     _LOGGER.debug(f"All lock data keys: {lock_keys}")
    #
    #     for key in lock_keys:
    #         _LOGGER.debug(f"  {key}: {self._hass.data[key]}")
    #
    #     # Update attributes from stored values
    #     for attr in ATTRIBUTE_MAP:
    #         value = self._hass.data.get(f"{DOMAIN}:{self._ieee}:{attr}")
    #         if value is not None:
    #             self._attrs[attr] = value
    #
    #     # Add last update timestamp
    #     self._attrs["last_updated"] = self._hass.data.get(
    #         f"{DOMAIN}:{self._ieee}:last_update",
    #         "unknown"
    #     )
    #
    #     # Store current time as last update
    #     from datetime import datetime
    #     self._hass.data[f"{DOMAIN}:{self._ieee}:last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    #
    #     _LOGGER.debug(f"Updated lock state: {self._is_locked}, attributes: {self._attrs}")
    #     """





class NimlyLockBatteryLowSensor(BinarySensorEntity):
    def __init__(self, hass, ieee, name, entry_id):
        self._hass = hass
        self._ieee = ieee
        self._name = name

        # Create unique ID with domain prefix to avoid collisions
        ieee_clean = ieee.replace(':', '').lower()
        self._unique_id = f"{DOMAIN}_battery_low_{ieee_clean}_{entry_id}"

        # Set entity_id format to avoid collisions
        self._attr_entity_id = f"{DOMAIN}_{ieee_clean}_battery_low"

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
            "model": "Digital Lock",
            "sw_version": "1.0",
            "entry_type": DeviceEntryType.SERVICE,
        }
