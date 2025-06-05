import logging
import voluptuous as vol
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_component import EntityComponent

from .const import DOMAIN
from .protocols import lock_door, unlock_door, send_nordic_command
from .protocols import send_safe4_lock_command, send_safe4_unlock_command
from .direct_command import send_direct_command

_LOGGER = logging.getLogger(__name__)

# Service schemas
SEND_COMMAND_SCHEMA = vol.Schema({
    vol.Required("ieee"): cv.string,
    vol.Required("command"): vol.Any(int, str),  # Allow both int (0, 1) and string ('lock', 'unlock')
    vol.Optional("endpoint", default=11): cv.positive_int,
    vol.Optional("cluster_id", default=0x0101): cv.positive_int,
    vol.Optional("retry_count", default=5): cv.positive_int
})

@callback
def setup_services(hass: HomeAssistant):

    # Service to send a raw command directly to the lock (advanced troubleshooting)
    async def handle_send_raw_command(call: ServiceCall):
        ieee = call.data["ieee"]
        command = call.data["command"]
        endpoint = call.data.get("endpoint", 11)  # Default to endpoint 11 for ZBT-1
        cluster_id = call.data.get("cluster_id", 0x0101)  # Default to Door Lock cluster
        retry_count = call.data.get("retry_count", 5)

        # Convert string commands to their numeric equivalents
        if isinstance(command, str):
            if command.lower() == "lock":
                command = 0x00
            elif command.lower() == "unlock":
                command = 0x01
            else:
                # Try to parse as hex
                try:
                    command = int(command, 16)
                except ValueError:
                    raise HomeAssistantError(f"Unknown command: {command}. Use 'lock', 'unlock', or a numeric command ID.")

        _LOGGER.info(f"Sending raw command {command} to endpoint {endpoint} of device {ieee}")

        # Send using direct_command module
        success = await send_direct_command(
            hass, 
            ieee, 
            command, 
            endpoint=endpoint, 
            cluster_id=cluster_id,
            retry_count=retry_count
        )

        if success:
            _LOGGER.info(f"Successfully sent command {command} to device {ieee}")
            return {"success": True}
        else:
            _LOGGER.error(f"Failed to send command {command} to device {ieee}")
            raise HomeAssistantError(f"Failed to send command {command} to device {ieee}")

    # Service to try unlocking with all methods
    async def handle_try_all_methods(call: ServiceCall):
        ieee = call.data["ieee"]
        command = call.data["command"]

        # Convert string commands to their numeric equivalents
        if isinstance(command, str):
            if command.lower() == "lock":
                command = 0x00
            elif command.lower() == "unlock":
                command = 0x01
            else:
                # Try to parse as hex
                try:
                    command = int(command, 16)
                except ValueError:
                    raise HomeAssistantError(f"Unknown command: {command}. Use 'lock', 'unlock', or a numeric command ID.")

        _LOGGER.info(f"Trying all methods to send command {command} to device {ieee}")

        # Try Nordic specific method first
        try:
            # Import the Nordic-specific command module
            command_name = "lock" if command == 0x00 else "unlock"
            if command_name == "lock":
                from .protocols import lock_door as nordic_lock
                _LOGGER.info(f"Trying Nordic-specific lock command")
                nordic_success = await nordic_lock(hass, ieee)
            else:
                from .protocols import unlock_door as nordic_unlock
                _LOGGER.info(f"Trying Nordic-specific unlock command")
                nordic_success = await nordic_unlock(hass, ieee)

            if nordic_success:
                _LOGGER.info(f"Successfully executed {command_name} command using Nordic-specific format")
                return {"success": True, "method": "nordic"}
        except Exception as e:
            _LOGGER.warning(f"Nordic-specific method failed: {e}")

        # Try Safe4 method
        try:
            if command == 0x00:  # Lock
                safe4_success = await send_safe4_lock_command(hass, ieee)
            else:  # Unlock
                safe4_success = await send_safe4_unlock_command(hass, ieee)

            if safe4_success:
                _LOGGER.info(f"Successfully executed command {command} using Safe4 method")
                return {"success": True, "method": "safe4"}
        except Exception as e:
            _LOGGER.warning(f"Safe4 method failed: {e}")

        # Try direct command method with various endpoints
        endpoints = [11, 1, 242, 2, 3]  # Try endpoint 11 first as required by spec
        for endpoint in endpoints:
            try:
                _LOGGER.info(f"Trying direct command to endpoint {endpoint}")
                success = await send_direct_command(
                    hass, 
                    ieee, 
                    command, 
                    endpoint=endpoint, 
                    retry_count=5
                )

                if success:
                    _LOGGER.info(f"Successfully sent command {command} to endpoint {endpoint}")
                    return {"success": True, "method": "direct", "endpoint": endpoint}
            except Exception as e:
                _LOGGER.warning(f"Direct command to endpoint {endpoint} failed: {e}")

        _LOGGER.error(f"All methods failed for command {command} to device {ieee}")
        raise HomeAssistantError(f"Failed to execute command {command} with all available methods")

    # Register services
    async_register_admin_service(
        hass,
        DOMAIN,
        "send_direct_command",
        handle_send_raw_command,
        schema=SEND_COMMAND_SCHEMA
    )

    async_register_admin_service(
        hass,
        DOMAIN,
        "try_all_methods",
        handle_try_all_methods,
        schema=SEND_COMMAND_SCHEMA
    )

    _LOGGER.info("Nimly Digital Lock services registered")

    return True

@callback
def unload_services(hass: HomeAssistant):
    for service in ["send_direct_command", "try_all_methods"]:
        if hass.services.has_service(DOMAIN, service):
            hass.services.async_remove(DOMAIN, service)
