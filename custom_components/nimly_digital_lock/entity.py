"""Entity implementations for Nimly Zigbee Digital Lock."""
import logging
from homeassistant.components.lock import LockEntity
from homeassistant.const import PERCENTAGE, SIGNAL_STRENGTH_DECIBELS
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.components.sensor import SensorStateClass
from homeassistant.components.binary_sensor import BinarySensorEntity
from .const import DOMAIN, ATTRIBUTE_MAP, ATTRIBUTE_CLUSTER_MAPPING, LOCK_CLUSTER_ID, POWER_CLUSTER_ID, ENDPOINT_ID
# Import LOCK_COMMANDS for command ID lookup
from .zha_mapping import LOCK_COMMANDS
from .zbt1_support import async_read_attribute_zbt1, async_send_command_zbt1, get_zbt1_endpoints

_LOGGER = logging.getLogger(__name__)


class NimlyDigitalLock(LockEntity):

    async def _send_zigbee_command(self, command, cluster_id=LOCK_CLUSTER_ID, endpoint_id=1, params={}):
        """Helper method to send Zigbee commands directly using service calls.
        Works with both ZHA and Nabu Casa zigbee integration.
        """
        # Determine which service to use (zha or zigbee)
        service_domain = self._hass.data.get(f"{DOMAIN}_ZIGBEE_SERVICE", "zha")
        _LOGGER.debug(f"Using {service_domain} service domain for commands with command {command}, cluster {cluster_id}, endpoint {endpoint_id}")

        # Check if the service exists
        has_service = self._hass.services.has_service(service_domain, "issue_zigbee_cluster_command")
        if not has_service:
            _LOGGER.warning(f"Service {service_domain}.issue_zigbee_cluster_command not available")

            # Try alternative service names
            alternatives = ["send_zigbee_command", "execute_zigbee_command"]
            service_method = None

            for alt in alternatives:
                if self._hass.services.has_service(service_domain, alt):
                    _LOGGER.info(f"Found alternative service: {service_domain}.{alt}")
                    service_method = alt
                    break

            if not service_method:
                # Check the other service domain as fallback
                fallback_domain = "zigbee" if service_domain == "zha" else "zha"
                if self._hass.services.has_service(fallback_domain, "issue_zigbee_cluster_command"):
                    service_domain = fallback_domain
                    service_method = "issue_zigbee_cluster_command"
                    _LOGGER.info(f"Using fallback service domain: {service_domain}")
                else:
                    # No services available, cannot operate without them
                    _LOGGER.error("No Zigbee services available for sending commands. Cannot communicate with lock.")
                    return False
        else:
            service_method = "issue_zigbee_cluster_command"

        # Try with different IEEE formats
        formats_to_try = [self._ieee, self._ieee_no_colons, self._ieee_with_colons]

        for ieee_format in formats_to_try:
            try:
                # For Nabu Casa ZBT-1, command format is essentially the same
                service_data = {
                    "ieee": ieee_format,
                    "command": command,
                    "command_type": "server",
                    "cluster_id": cluster_id,
                    "endpoint_id": endpoint_id
                }

                # Add params if not empty
                if params:
                    service_data["params"] = params

                _LOGGER.debug(f"Sending {service_domain} command using {service_method}: {service_data}")
                await self._hass.services.async_call(
                    service_domain, service_method, service_data
                )
                return True
            except Exception as e:
                _LOGGER.warning(f"Failed to send command {command} with IEEE format {ieee_format}: {e}")

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
        """Helper method to read Zigbee attributes directly using service calls.
        Works with both ZHA and Nabu Casa zigbee integration.
        """
        # Check if services are available first
        service_domain = self._hass.data.get(f"{DOMAIN}_ZIGBEE_SERVICE", "zha")
        _LOGGER.debug(f"Using {service_domain} service domain for attribute read")

        # Verify service exists before trying to call it
        has_service = self._hass.services.has_service(service_domain, "read_zigbee_cluster_attribute")
        if not has_service:
            _LOGGER.warning(f"Service {service_domain}.read_zigbee_cluster_attribute not available")

            # Try alternative service name for ZHA
            alternative_service = "get_zigbee_cluster_attribute"
            if self._hass.services.has_service(service_domain, alternative_service):
                _LOGGER.info(f"Found alternative service: {service_domain}.{alternative_service}")
                service_method = alternative_service
            else:
                # Try the other service domain as fallback
                fallback_domain = "zigbee" if service_domain == "zha" else "zha"
                if self._hass.services.has_service(fallback_domain, "read_zigbee_cluster_attribute"):
                    service_domain = fallback_domain
                    service_method = "read_zigbee_cluster_attribute"
                    _LOGGER.info(f"Using fallback service domain: {service_domain}")
                else:
                    # No services available, cannot operate without them
                    _LOGGER.error("No Zigbee services available for reading attributes. Cannot communicate with lock.")
                    return False
        else:
            service_method = "read_zigbee_cluster_attribute"

        # Try with different IEEE formats
        formats_to_try = [self._ieee, self._ieee_no_colons, self._ieee_with_colons]

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
        """Lock the door."""
        _LOGGER.info(f"Locking {self._name} [{self._ieee}]")

        # Get device info
        device_info = self._hass.data.get(f"{DOMAIN}_ZHA_DEVICE")

        # Check if ZHA services are available
        service_domain = self._hass.data.get(f"{DOMAIN}_ZIGBEE_SERVICE", "zha")
        has_command_service = self._hass.services.has_service(service_domain, "issue_zigbee_cluster_command")

        # If services are available, try to send the command
        if has_command_service:
            _LOGGER.debug(f"Calling Zigbee service to lock door using IEEE: {self._ieee}")

            # First try with the standard method
            success = await self._send_zigbee_command("lock_door")

            # If that fails, try with numeric command ID directly
            if not success and "lock_door" in LOCK_COMMANDS:
                _LOGGER.info("First lock attempt failed, trying with numeric command ID")
                command_id = LOCK_COMMANDS["lock_door"]
                success = await self._send_zigbee_command(command_id)

            # If still unsuccessful, try ZBT-1 specific method
            if not success:
                _LOGGER.info("Standard lock attempts failed, trying ZBT-1 specific method")
                # Try with Nordic Semiconductor format, primarily on endpoint 11
                endpoints = get_zbt1_endpoints(self._hass, self._ieee) or [11, 1, 2, 3]

                for endpoint in endpoints:
                    _LOGGER.debug(f"Trying lock with ZBT-1 method on endpoint {endpoint}")

                    # For ZBT-1 with Nordic Semiconductor format
                    # Command format: zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 <command id>
                    success = await async_send_command_zbt1(
                        self._hass,
                        self._ieee_with_colons,  # Use IEEE with colons for ZBT-1
                        LOCK_COMMANDS["lock_door"],  # Command ID 0x00 for lock
                        LOCK_CLUSTER_ID,  # 0x0101 Door Lock cluster
                        endpoint_id=endpoint,  # Try endpoint 11 first (Nordic default)
                        params={}  # Ensure empty params are passed
                    )

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
        """Unlock the door."""
        _LOGGER.info(f"Unlocking {self._name} [{self._ieee}]")

        # Get device info
        device_info = self._hass.data.get(f"{DOMAIN}_ZHA_DEVICE")

        # Check if ZHA services are available
        service_domain = self._hass.data.get(f"{DOMAIN}_ZIGBEE_SERVICE", "zha")
        has_command_service = self._hass.services.has_service(service_domain, "issue_zigbee_cluster_command")

        # If services are available, try to send the command
        if has_command_service:
            _LOGGER.debug(f"Calling Zigbee service to unlock door using IEEE: {self._ieee}")

            # First try with the standard method
            success = await self._send_zigbee_command("unlock_door")

            # If that fails, try with numeric command ID directly
            if not success and "unlock_door" in LOCK_COMMANDS:
                _LOGGER.info("First unlock attempt failed, trying with numeric command ID")
                command_id = LOCK_COMMANDS["unlock_door"]
                success = await self._send_zigbee_command(command_id)

            # If still unsuccessful, try ZBT-1 specific method
            if not success:
                _LOGGER.info("Standard unlock attempts failed, trying ZBT-1 specific method")
                # Try with Nordic Semiconductor format, primarily on endpoint 11
                endpoints = get_zbt1_endpoints(self._hass, self._ieee) or [11, 1, 2, 3]

                for endpoint in endpoints:
                    _LOGGER.debug(f"Trying unlock with ZBT-1 method on endpoint {endpoint}")

                    # For ZBT-1 with Nordic Semiconductor format
                    # Command format: zcl cmd <IEEE Addr> 11 0x0101 -p 0x0104 <command id>
                    success = await async_send_command_zbt1(
                        self._hass,
                        self._ieee_with_colons,  # Use IEEE with colons for ZBT-1
                        LOCK_COMMANDS["unlock_door"],  # Command ID 0x01 for unlock
                        LOCK_CLUSTER_ID,  # 0x0101 Door Lock cluster
                        endpoint_id=endpoint,  # Try endpoint 11 first (Nordic default)
                        params={}  # Ensure empty params are passed
                    )

                    if success:
                        _LOGGER.info(f"ZBT-1 unlock successful on endpoint {endpoint}")
                        break

            if success:
                _LOGGER.info("Unlock command sent successfully")
            else:
                _LOGGER.warning("Failed to send unlock command after multiple attempts. Using simulated state.")
        else:
            if not has_command_service:
                _LOGGER.error(f"Service {service_domain}.issue_zigbee_cluster_command not available. Cannot control lock.")
            else:
                _LOGGER.info("Operating in simulated mode or device info not found")

        # Update our internal state
        self._is_locked = False
        self._hass.data[f"{DOMAIN}:{self._ieee}:lock_state"] = 0
        self.async_write_ha_state()
        return True

    async def async_update(self):
        """Update entity state and attributes."""
        _LOGGER.debug(f"Updating lock state for {self._name} [{self._ieee}]")

        # Service domain should always be zigbee for ZBT-1
        service_domain = "zigbee"

        # Try to read the current lock state from the physical device
        try:
            # Try reading from multiple endpoints to find the one that works
            # Use endpoint 11 first for ZBT-1 per Nordic Semiconductor docs
            endpoints = get_zbt1_endpoints(self._hass, self._ieee) or [11, 1, 2, 3, 242]

            for endpoint in endpoints:
                try:
                    _LOGGER.debug(f"Reading lock state from endpoint {endpoint}")
                    # Try ZBT-1 specific method first
                    result = await async_read_attribute_zbt1(
                        self._hass, 
                        self._ieee_with_colons, 
                        LOCK_CLUSTER_ID, 
                        0,  # Lock state attribute
                        endpoint_id=endpoint
                    )

                    if not result:
                        # Fall back to standard method
                        await self._read_zigbee_attribute(LOCK_CLUSTER_ID, 0, endpoint)

                    # Also try to read the battery level
                    battery_result = await async_read_attribute_zbt1(
                        self._hass, 
                        self._ieee_with_colons, 
                        POWER_CLUSTER_ID, 
                        0x0021,  # Battery percentage remaining
                        endpoint_id=endpoint
                    )

                    if not battery_result:
                        # Fall back to standard method
                        await self._read_zigbee_attribute(POWER_CLUSTER_ID, 0x0021, endpoint)

                except Exception as e:
                    _LOGGER.debug(f"Failed to read from endpoint {endpoint}: {e}")
        except Exception as e:
            _LOGGER.warning(f"Error reading attributes from device: {e}")

        # Use current value from data store
        lock_state = self._hass.data.get(f"{DOMAIN}:{self._ieee}:lock_state")
        if lock_state is not None:
            self._is_locked = (lock_state == 1)
            _LOGGER.debug(f"Current lock state: {self._is_locked}")
        else:
            # If no state stored yet, default to unknown
            self._is_locked = None
            _LOGGER.warning("Lock state unknown - has not been set yet")

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
            "manufacturer": "Nimly",
            "model": "Nimly Door Lock Module",
            "sw_version": "1.0",
            "entry_type": DeviceEntryType.SERVICE,
        }
