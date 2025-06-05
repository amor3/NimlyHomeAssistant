import logging
from homeassistant.components.lock import LockEntity
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.components.sensor import SensorStateClass
from homeassistant.components.binary_sensor import BinarySensorEntity
from homeassistant.core import callback
from .const import DOMAIN, ATTRIBUTE_MAP, ATTRIBUTE_CLUSTER_MAPPING, LOCK_CLUSTER_ID, POWER_CLUSTER_ID, ENDPOINT_ID

# Import constants from dedicated constants file
from .const_zbt1 import (
    SAFE4_DOOR_LOCK_CLUSTER,
    SAFE4_POWER_CLUSTER
)

# Import from zha_mapping
from .protocols import (
    LOCK_COMMANDS, 
    format_ieee_with_colons, 
    format_ieee, 
    normalize_ieee, 
    POWER_ATTRIBUTES, 
    LOCK_ATTRIBUTES
)
from .protocols import async_read_attribute_zbt1, async_send_command_zbt1, get_zbt1_endpoints
from .protocols import send_safe4_lock_command, send_safe4_unlock_command, read_safe4_attribute

# Import these constants from dedicated constants file instead
from .const_zbt1 import SAFE4_LOCK_COMMAND, SAFE4_UNLOCK_COMMAND

_LOGGER = logging.getLogger(__name__)



class NimlyDigitalLock(LockEntity):

    async def _send_zigbee_command(self, command, cluster_id=LOCK_CLUSTER_ID, endpoint_id=1, params={}):
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
            zbt1_endpoints = [11, 1, 2, 3, 242]  # Default endpoints to try

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
        self._attrs = {}

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
        _LOGGER.info(f"Locking {self._name} [{self._ieee}] using Nordic ZBT-1 specification")

        # First try with the Nordic ZBT-1 command module (exact format from Nordic docs)
        from .protocols import lock_door
        _LOGGER.info(f"Attempting lock with Nordic ZBT-1 command module")
        success = await lock_door(self._hass, self._ieee_with_colons)

        # If Nordic command succeeds, update state and return
        if success:
            _LOGGER.info(f"Successfully locked {self.name} using Nordic ZBT-1 format")
            # Update internal state
            self._is_locked = True
            self._hass.data[f"{DOMAIN}:{self._ieee}:lock_state"] = 1
            self.async_write_ha_state()
            return True

        # If Nordic command fails, try with the direct command module as fallback
        from .direct_command import send_direct_command
        from .protocols import SAFE4_LOCK_COMMAND
        _LOGGER.info(f"Nordic command failed, trying direct command module")
        success = await send_direct_command(self._hass, self._ieee_with_colons, SAFE4_LOCK_COMMAND)

        # If direct command fails, try the Safe4 lock module
        _LOGGER.info(f"Direct command failed, trying Safe4 module")
        success = await send_safe4_lock_command(
            self._hass,
            self._ieee_with_colons  # IEEE address with colons
        )

        if success:
            _LOGGER.info(f"Successfully locked {self.name} using Safe4 command format")
            # Update internal state
            self._is_locked = True
            self._hass.data[f"{DOMAIN}:{self._ieee}:lock_state"] = 1
            self.async_write_ha_state()
            return True

        # If the Safe4 method failed, try standard methods as fallback
        _LOGGER.warning("Safe4 lock command failed, trying standard methods")

        # Check if ZHA services are available
        service_domain = self._hass.data.get(f"{DOMAIN}_ZIGBEE_SERVICE", "zigbee")
        has_command_service = self._hass.services.has_service(service_domain, "issue_zigbee_cluster_command")

        if has_command_service:
            _LOGGER.debug(f"Trying standard service to lock door: {service_domain}")

            # If that fails, try with numeric command ID directly
            if not success:
                try:
                    if "lock_door" in LOCK_COMMANDS:
                        _LOGGER.info("First lock attempt failed, trying with numeric command ID")
                        command_id = LOCK_COMMANDS["lock_door"]
                        success = await self._send_zigbee_command(command_id)
                except Exception as e:
                    _LOGGER.warning(f"Error trying to use LOCK_COMMANDS: {e}")

            # If still unsuccessful, try ZBT-1 specific method
            if not success:
                _LOGGER.info("Standard lock attempts failed, trying ZBT-1 specific method according to Safe4 spec")
                # Try a last resort approach - direct ZHA device control if available
                try:
                    # This is a more direct approach using ZHA internals
                    from homeassistant.components.zha.core.gateway import ZHAGateway
                    from homeassistant.components.zha.core.const import DOMAIN as ZHA_DOMAIN

                    if ZHA_DOMAIN in self._hass.data:
                        zha_gateway = self._hass.data[ZHA_DOMAIN].get("gateway")
                        if zha_gateway and hasattr(zha_gateway, "devices"):
                            # Try to find the device by nwk or ieee
                            device = None
                            for dev in zha_gateway.devices.values():
                                if (hasattr(dev, "ieee") and str(dev.ieee).replace(':', '').lower() == self._zha_ieee.replace(':', '').lower()) or \
                                   (hasattr(dev, "nwk") and str(dev.nwk) == self._zha_nwk.replace('0x', '')):
                                    device = dev
                                    _LOGGER.info(f"Found ZHA device: {device.ieee} / nwk: {device.nwk}")
                                    break

                            if device:
                                # Try to get the doorlock cluster
                                if hasattr(device, "endpoints"):
                                    for endpoint_id, endpoint in device.endpoints.items():
                                        if hasattr(endpoint, "door_lock"):
                                            _LOGGER.info(f"Found door_lock cluster on endpoint {endpoint_id}")
                                            # Try to lock via direct ZHA API
                                            await endpoint.door_lock.lock()
                                            _LOGGER.info("Sent lock command via direct ZHA API")
                                            success = True
                                            break
                except Exception as e:
                    _LOGGER.warning(f"Failed to use direct ZHA device control: {e}")

                # Nordic Semiconductor format requires endpoint 11 and specific command format
                endpoints = [11]  # According to the Safe4 spec, endpoint must be 11

                # First try using the known ZHA device directly with IEEE address
                _LOGGER.info(f"Attempting to send lock command to ZHA device with IEEE {self._zha_ieee}")
                try:
                    # For Safe4 ZigBee Door Lock with Nordic Semiconductor format
                    # Command format exactly as specified: zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 0x00
                    success = await async_send_command_zbt1(
                        self._hass,
                        self._zha_ieee,  # Use the ZHA device's IEEE address
                        SAFE4_LOCK_COMMAND,  # Command ID must be exactly 0x00 for lock per spec
                        0x0101,  # Door Lock cluster 0x0101
                        endpoint_id=11,  # Must be endpoint 11 per Safe4 specification
                        params=None  # NO parameters allowed per specification
                    )

                    if not success:
                        # If IEEE address fails, try with network address
                        _LOGGER.info(f"Attempting to send lock command using network address {self._zha_nwk}")
                        # ZHA doesn't directly support nwk parameter, use ieee instead

                        # Try direct ZHA service call with network address as ieee
                        service_data = {
                            "ieee": self._zha_nwk,  # Use network address as ieee parameter
                            "command": SAFE4_LOCK_COMMAND,
                            "command_type": "server",
                            "cluster_id": 0x0101,  # Door Lock cluster
                            "endpoint_id": 11,
                            "params": {"pin_code": ""}
                        }

                        await self._hass.services.async_call(
                            "zha", "issue_zigbee_cluster_command", service_data
                        )
                        _LOGGER.info(f"Lock command sent using network address {self._zha_nwk}")
                        success = True

                    if success:
                        _LOGGER.info(f"Successfully sent lock command to ZHA device {self._zha_ieee}")
                        self._is_locked = True
                        self._hass.data[f"{DOMAIN}:{self._ieee}:lock_state"] = 1
                        self.async_write_ha_state()
                        return True
                except Exception as e:
                    _LOGGER.warning(f"Failed to send lock command to ZHA device: {e}")

                for endpoint in endpoints:
                    _LOGGER.info(f"Trying lock with ZBT-1 method on endpoint {endpoint} per Safe4 specification")

                    # For Safe4 ZigBee Door Lock with Nordic Semiconductor format
                    # Command format exactly as specified: zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 0x00
                    # Command ID must be 0x00 with NO parameters
                    success = await async_send_command_zbt1(
                        self._hass,
                        self._ieee_with_colons,  # IEEE address with colons
                        SAFE4_LOCK_COMMAND,  # Command ID must be exactly 0x00 for lock per spec
                        0x0101,  # Door Lock cluster 0x0101
                        endpoint_id=11,  # Must be endpoint 11 per Safe4 specification
                        params=None  # NO parameters allowed per specification
                    )

                    if success:
                        _LOGGER.info("Successfully sent Safe4 lock command")
                        # Update internal state
                        self._is_locked = True
                        self._hass.data[f"{DOMAIN}:{self._ieee}:lock_state"] = 1
                        return
                    else:
                        _LOGGER.error("Failed to send Safe4 lock command")

                    if success:
                        _LOGGER.info(f"ZBT-1 lock successful on endpoint {endpoint}")
                        break

            if success:
                _LOGGER.info("Lock command sent successfully")
            else:
                _LOGGER.warning("Failed to send lock command after multiple attempts. Using simulated state.")
        else:
            if not has_command_service:
                _LOGGER.error(f"Service {service_domain}.issue_zigbee_cluster_command not available. Cannot control lock.")
            else:
                _LOGGER.info("Operating in simulated mode or device info not found")

        # Update our internal state
        self._is_locked = True
        self._hass.data[f"{DOMAIN}:{self._ieee}:lock_state"] = 1
        self.async_write_ha_state()
        return True

    async def async_unlock(self, **kwargs):
        _LOGGER.info(f"Unlocking {self._name} [{self._ieee}] via direct command")
        try:
            from .protocols import unlock_door

            success = await unlock_door(self._hass, self._ieee_with_colons)
        except Exception as e:
            _LOGGER.error(f"Error sending direct unlock: {e}")
            return False

        if success:
            _LOGGER.info(f"Successfully unlocked {self.name} using direct command")
            self._is_locked = False
            self._hass.data[f"{DOMAIN}:{self._ieee}:lock_state"] = 0
            self.async_write_ha_state()
            return True
        else:
            _LOGGER.error("Direct unlock command failed")
            return False
    async def async_update(self):
        _LOGGER.debug(f"Updating lock state for {self._name} [{self._ieee}]")

        # Read lock state (0x0000) from Door Lock cluster (0x0101)
        try:
            service_data = {
                "ieee": self._ieee_with_colons,
                "endpoint_id": 11,  # ZBT-1 uses endpoint 11
                "cluster_id": 0x0101,  # Door Lock cluster
                "cluster_type": "in",
                "attribute": 0x0000  # Lock State attribute
            }

            result = await self._hass.services.async_call(
                "zha", "get_zigbee_cluster_attribute", service_data, blocking=True, return_response=True
            )

            if result is not None:
                _LOGGER.debug(f"Lock state read result: {result}")
                self._is_locked = result == 1
                self._hass.data[f"{DOMAIN}:{self._ieee}:lock_state"] = result
        except Exception as e:
            _LOGGER.warning(f"Failed to read lock state: {e}")

        # Read battery percentage (0x0021) from Power cluster (0x0001)
        try:
            service_data = {
                "ieee": self._ieee_with_colons,
                "endpoint_id": 11,  # ZBT-1 uses endpoint 11 
                "cluster_id": 0x0001,  # Power Configuration cluster
                "cluster_type": "in",
                "attribute": 0x0021  # Battery percentage remaining
            }

            result = await self._hass.services.async_call(
                "zha", "get_zigbee_cluster_attribute", service_data, blocking=True, return_response=True
            )

            if result is not None and 0 <= result <= 100:
                _LOGGER.debug(f"Battery percentage read result: {result}%")
                self._hass.data[f"{DOMAIN}:{self._ieee}:battery"] = result

                # Set battery_low status if below 15%
                battery_low = result < 15
                battery_low_value = 1 if battery_low else 0
                self._hass.data[f"{DOMAIN}:{self._ieee}:battery_low"] = battery_low_value
        except Exception as e:
            _LOGGER.warning(f"Failed to read battery percentage: {e}")

        # Try to read attributes using the Safe4 module with multiple endpoints
        # The Safe4 module already handles multiple endpoints and IEEE formats
        try:
            # Read lock state using Safe4 module
            _LOGGER.debug(f"Reading lock state from cluster {SAFE4_DOOR_LOCK_CLUSTER} using Safe4 module")
            lock_state = await read_safe4_attribute(
                self._hass,
                self._ieee_with_colons,
                SAFE4_DOOR_LOCK_CLUSTER,
                0x0000  # Lock state attribute
            )

            if lock_state is not None:
                _LOGGER.info(f"Successfully read lock state: {lock_state}")
                # Store the result - use both IEEE formats to ensure consistency
                self._hass.data[f"{DOMAIN}:{self._ieee}:lock_state"] = lock_state
                self._hass.data[f"{DOMAIN}:{self._ieee_with_colons}:lock_state"] = lock_state
                self._is_locked = (lock_state == 1)
            else:
                # Try alternative method
                _LOGGER.debug("Safe4 module failed for lock state, trying ZBT-1 method")
                lock_state = await async_read_attribute_zbt1(
                    self._hass, 
                    self._ieee_with_colons, 
                    LOCK_CLUSTER_ID, 
                    0x0000,  # Lock state attribute
                    endpoint_id=11  # Start with endpoint 11 per Safe4 spec
                )

                if lock_state is not None:
                    _LOGGER.info(f"Successfully read lock state via ZBT1: {lock_state}")
                    self._hass.data[f"{DOMAIN}:{self._ieee}:lock_state"] = lock_state
                    self._hass.data[f"{DOMAIN}:{self._ieee_with_colons}:lock_state"] = lock_state
                    self._is_locked = (lock_state == 1)

            # Read battery level
            _LOGGER.debug(f"Reading battery level from cluster {SAFE4_POWER_CLUSTER}")
            battery = await read_safe4_attribute(
                self._hass,
                self._ieee_with_colons,
                SAFE4_POWER_CLUSTER,
                0x0021  # Battery percentage remaining
            )

            if battery is not None:
                _LOGGER.info(f"Successfully read battery level: {battery}")
                # Store the result in both formats for consistency
                self._hass.data[f"{DOMAIN}:{self._ieee}:battery"] = battery
                self._hass.data[f"{DOMAIN}:{self._ieee_with_colons}:battery"] = battery

                # Also set battery_low status if below 15%
                if isinstance(battery, (int, float)) and battery < 15:
                    self._hass.data[f"{DOMAIN}:{self._ieee}:battery_low"] = 1
                else:
                    self._hass.data[f"{DOMAIN}:{self._ieee}:battery_low"] = 0
            else:
                # Try alternative method
                _LOGGER.debug("Safe4 module failed for battery, trying ZBT-1 method")
                battery = await async_read_attribute_zbt1(
                    self._hass, 
                    self._ieee_with_colons, 
                    POWER_CLUSTER_ID, 
                    0x0021,  # Battery percentage remaining
                    endpoint_id=11  # Start with endpoint 11 per Safe4 spec
                )

                if battery is not None:
                    _LOGGER.info(f"Successfully read battery via ZBT1: {battery}")
                    self._hass.data[f"{DOMAIN}:{self._ieee}:battery"] = battery
                    self._hass.data[f"{DOMAIN}:{self._ieee_with_colons}:battery"] = battery

                    # Also set battery_low status if below 15%
                    if isinstance(battery, (int, float)) and battery < 15:
                        self._hass.data[f"{DOMAIN}:{self._ieee}:battery_low"] = 1
                    else:
                        self._hass.data[f"{DOMAIN}:{self._ieee}:battery_low"] = 0

            # Try to read battery voltage as well
            battery_voltage = await read_safe4_attribute(
                self._hass,
                self._ieee_with_colons,
                SAFE4_POWER_CLUSTER,
                0x0020  # Battery voltage
            )

            if battery_voltage is not None:
                # Convert from millivolts to volts if needed
                if battery_voltage > 100:
                    battery_voltage = battery_voltage / 1000.0

                _LOGGER.info(f"Successfully read battery voltage: {battery_voltage}V")
                self._hass.data[f"{DOMAIN}:{self._ieee}:battery_voltage"] = battery_voltage
                self._hass.data[f"{DOMAIN}:{self._ieee_with_colons}:battery_voltage"] = battery_voltage

        except Exception as e:
            _LOGGER.warning(f"Error reading attributes from device: {str(e)}")

        # Use current value from data store
        lock_state = self._hass.data.get(f"{DOMAIN}:{self._ieee}:lock_state")
        if lock_state is not None:
            self._is_locked = (lock_state == 1)
            _LOGGER.debug(f"Current lock state: {self._is_locked}")
        else:
            # If no state could be read, show an error
            _LOGGER.error("Could not determine lock state - Nordic ZBT-1 device may be unreachable")
            # Default to locked for security
            self._is_locked = True
            self._hass.data[f"{DOMAIN}:{self._ieee}:lock_state"] = 1

        # Debug: Log all lock-related keys in hass.data to help troubleshoot
        lock_keys = []
        for key in self._hass.data:
            if f"{DOMAIN}:" in key:
                lock_keys.append(key)
        _LOGGER.debug(f"All lock data keys: {lock_keys}")

        for key in lock_keys:
            _LOGGER.debug(f"  {key}: {self._hass.data[key]}")

        # Update attributes from stored values
        for attr in ATTRIBUTE_MAP:
            value = self._hass.data.get(f"{DOMAIN}:{self._ieee}:{attr}")
            if value is not None:
                self._attrs[attr] = value

        # Add last update timestamp
        self._attrs["last_updated"] = self._hass.data.get(
            f"{DOMAIN}:{self._ieee}:last_update", 
            "unknown"
        )

        # Store current time as last update
        from datetime import datetime
        self._hass.data[f"{DOMAIN}:{self._ieee}:last_update"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        _LOGGER.debug(f"Updated lock state: {self._is_locked}, attributes: {self._attrs}")




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
            "manufacturer": "Nordic Semiconductor",
            "model": "ZBT-1 Safe4 Door Lock",
            "sw_version": "1.0",
            "entry_type": DeviceEntryType.SERVICE,
        }
