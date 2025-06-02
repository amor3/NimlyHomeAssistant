"""Direct command implementation for Nimly locks to bypass service layers."""

import logging
import asyncio

_LOGGER = logging.getLogger(__name__)

async def send_direct_command(hass, ieee, command, endpoint=11, cluster_id=0x0101):
    """Send a direct command to the lock using multiple methods.

    This function attempts to send the command in various formats to maximize
    the chance of success.
    """
    _LOGGER.info(f"Sending direct command {command} to endpoint {endpoint}")

    # 1. Try Nabu Casa Zigbee service first (most reliable for ZBT-1)
    try:
        service_data = {
            "ieee": ieee,
            "endpoint_id": endpoint,
            "cluster_id": cluster_id,
            "command": command,
            "command_type": "server"
        }

        # Send using Nabu Casa Zigbee service
        await hass.services.async_call(
            "zigbee", "issue_zigbee_cluster_command", service_data, blocking=True
        )
        _LOGGER.info(f"Successfully sent command using Nabu Casa Zigbee service")
        return True
    except Exception as e:
        _LOGGER.warning(f"Failed to send using Nabu Casa Zigbee: {e}")

    # 2. Try ZHA service as fallback
    try:
        service_data = {
            "ieee": ieee,
            "endpoint_id": endpoint,
            "cluster_id": cluster_id,
            "command": command,
            "command_type": "server"
        }

        # Send using ZHA service
        await hass.services.async_call(
            "zha", "issue_zigbee_cluster_command", service_data, blocking=True
        )
        _LOGGER.info(f"Successfully sent command using ZHA service")
        return True
    except Exception as e:
        _LOGGER.warning(f"Failed to send using ZHA: {e}")

    # 3. Try alternate IEEE formats
    ieee_no_colons = ieee.replace(':', '')
    ieee_with_colons = ':'.join([ieee_no_colons[i:i+2] for i in range(0, len(ieee_no_colons), 2)])

    formats_to_try = [
        ieee_no_colons,
        ieee_with_colons,
        # Add the known ZHA device IEEE address as a last resort
        "f4:ce:36:0a:04:4d:31:f5",
        "f4ce360a044d31f5"
    ]

    for ieee_format in formats_to_try:
        try:
            service_data = {
                "ieee": ieee_format,
                "endpoint_id": endpoint,
                "cluster_id": cluster_id,
                "command": command,
                "command_type": "server"
            }

            # Try both services with each format
            for service_domain in ["zigbee", "zha"]:
                try:
                    await hass.services.async_call(
                        service_domain, "issue_zigbee_cluster_command", service_data, blocking=True
                    )
                    _LOGGER.info(f"Successfully sent command using {service_domain} with IEEE {ieee_format}")
                    return True
                except Exception as e:
                    _LOGGER.debug(f"Failed with {service_domain} and IEEE {ieee_format}: {e}")
        except Exception as e:
            _LOGGER.debug(f"Error trying IEEE format {ieee_format}: {e}")

    # 4. Try with network address (nwk) if that's available
    try:
        # Use the known network address
        nwk = "0x7FDB"
        service_data = {
            "nwk": nwk,
            "endpoint_id": endpoint,
            "cluster_id": cluster_id,
            "command": command,
            "command_type": "server"
        }

        await hass.services.async_call(
            "zha", "issue_zigbee_cluster_command", service_data, blocking=True
        )
        _LOGGER.info(f"Successfully sent command using network address {nwk}")
        return True
    except Exception as e:
        _LOGGER.warning(f"Failed to send using network address: {e}")

    _LOGGER.error("All command sending methods failed")
    return False

# Specific functions for lock operations
async def lock_door(hass, ieee):
    """Lock the door using direct command."""
    return await send_direct_command(hass, ieee, 0x00)  # 0x00 = Lock command

async def unlock_door(hass, ieee):
    """Unlock the door using direct command."""
    return await send_direct_command(hass, ieee, 0x01)  # 0x01 = Unlock command
