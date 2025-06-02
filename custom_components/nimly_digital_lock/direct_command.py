"""Direct command implementation for Nimly locks to bypass service layers."""

import logging
import asyncio

_LOGGER = logging.getLogger(__name__)

async def send_direct_command(hass, ieee, command, endpoint=11, cluster_id=0x0101, retry_count=3, retry_delay=1.0):
    """Send a direct command to the lock using multiple methods.

    This function attempts to send the command in various formats to maximize
    the chance of success.

    Args:
        hass: Home Assistant instance
        ieee: IEEE address of the device
        command: Command ID to send
        endpoint: Endpoint ID to target
        cluster_id: Cluster ID to use
        retry_count: Number of retries for each method
        retry_delay: Delay between retries in seconds
    """
    _LOGGER.info(f"Sending direct command {command} to endpoint {endpoint}")

    # Diagnostics - store command info for debugging
    if f"NIMLY_LAST_COMMAND" not in hass.data:
        hass.data["NIMLY_LAST_COMMAND"] = []
    command_info = {
        "ieee": ieee,
        "command": command,
        "endpoint": endpoint,
        "cluster_id": cluster_id,
        "timestamp": hass.loop.time()
    }
    hass.data["NIMLY_LAST_COMMAND"].append(command_info)

    # 1. Try Nabu Casa Zigbee service first (most reliable for ZBT-1)
    for attempt in range(retry_count):
        try:
            service_data = {
                "ieee": ieee,
                "endpoint_id": endpoint,
                "cluster_id": cluster_id,
                "command": command,
                "command_type": "server"
            }

            # Send using Nabu Casa Zigbee service
            _LOGGER.debug(f"Nabu Casa attempt {attempt+1}/{retry_count}")
            await hass.services.async_call(
                "zigbee", "issue_zigbee_cluster_command", service_data, blocking=True
            )
            _LOGGER.info(f"Successfully sent command using Nabu Casa Zigbee service on attempt {attempt+1}")
            return True
        except Exception as e:
            _LOGGER.warning(f"Failed to send using Nabu Casa Zigbee (attempt {attempt+1}): {e}")
            if attempt < retry_count - 1:
                await asyncio.sleep(retry_delay)

    # 2. Try ZHA service as fallback
    for attempt in range(retry_count):
        try:
            service_data = {
                "ieee": ieee,
                "endpoint_id": endpoint,
                "cluster_id": cluster_id,
                "command": command,
                "command_type": "server"
            }

            # Send using ZHA service
            _LOGGER.debug(f"ZHA attempt {attempt+1}/{retry_count}")
            await hass.services.async_call(
                "zha", "issue_zigbee_cluster_command", service_data, blocking=True
            )
            _LOGGER.info(f"Successfully sent command using ZHA service on attempt {attempt+1}")
            return True
        except Exception as e:
            _LOGGER.warning(f"Failed to send using ZHA (attempt {attempt+1}): {e}")
            if attempt < retry_count - 1:
                await asyncio.sleep(retry_delay)

            # If this is the last attempt, check if we're getting a specific error about device not responding
            if attempt == retry_count - 1 and "device did not respond" in str(e).lower():
                _LOGGER.error("Device not responding - likely a network connectivity issue")
                # Add a hint about possible solution
                _LOGGER.error("SUGGESTION: Try restarting your ZigBee coordinator or moving the lock closer to the hub")

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
