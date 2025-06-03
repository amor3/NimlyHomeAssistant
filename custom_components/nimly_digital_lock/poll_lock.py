"""Polling service for Nimly digital locks."""

import logging
import asyncio
from .const import DOMAIN, LOCK_CLUSTER_ID, POWER_CLUSTER_ID
from .safe4_lock import read_safe4_attribute

_LOGGER = logging.getLogger(__name__)

async def start_polling_service(hass, ieee, poll_interval=60):
    """Start a polling service to periodically check lock state and battery."""
    _LOGGER.info(f"Starting polling service for lock with IEEE {ieee} (interval: {poll_interval}s)")

    # Format IEEE with colons for consistency
    from .zha_mapping import format_ieee_with_colons
    ieee_with_colons = format_ieee_with_colons(ieee)

    while True:
        try:
            # Poll lock state
            await poll_lock_state(hass, ieee, ieee_with_colons)

            # Poll battery level
            await poll_battery_level(hass, ieee, ieee_with_colons)

        except Exception as e:
            _LOGGER.error(f"Error in polling service: {e}")

        # Sleep for the specified interval
        await asyncio.sleep(poll_interval)

async def poll_lock_state(hass, ieee, ieee_with_colons):
    """Poll the lock state and update the entity."""
    try:
        # Try to read the lock state attribute
        result = await read_safe4_attribute(hass, ieee_with_colons, LOCK_CLUSTER_ID, 0x0000)

        if result is not None:
            # Update the lock state in hass.data
            _LOGGER.debug(f"Lock state poll result: {result}")

            # Lock state is 0 for unlocked, 1 for locked, 2 for error
            if result in [0, 1, 2]:
                hass.data[f"{DOMAIN}:{ieee}:lock_state"] = result
                _LOGGER.info(f"Updated lock state to {result} ('unlocked' if 0, 'locked' if 1, 'error' if 2)")

                # Force entity update
                entity_id = f"lock.{DOMAIN}_{ieee.replace(':', '').lower()}"
                await hass.services.async_call(
                    "homeassistant", "update_entity", {"entity_id": entity_id}
                )
            else:
                _LOGGER.warning(f"Received unexpected lock state value: {result}")
        else:
            _LOGGER.debug("Lock state poll returned None")

    except Exception as e:
        _LOGGER.error(f"Error polling lock state: {e}")

async def poll_battery_level(hass, ieee, ieee_with_colons):
    """Poll the battery level and update the entity."""
    try:
        # Try to read the battery percentage attribute
        result = await read_safe4_attribute(hass, ieee_with_colons, POWER_CLUSTER_ID, 0x0021)

        if result is not None:
            # Update the battery percentage in hass.data
            _LOGGER.debug(f"Battery percentage poll result: {result}")

            # Make sure the value is between 0 and 100
            if 0 <= result <= 100:
                hass.data[f"{DOMAIN}:{ieee}:battery"] = result
                _LOGGER.info(f"Updated battery percentage to {result}%")

                # Also set battery_low status if below 15%
                battery_low = result < 15
                hass.data[f"{DOMAIN}:{ieee}:battery_low"] = battery_low
                _LOGGER.debug(f"Battery low status set to {battery_low}")

                # Force entity updates
                await hass.services.async_call(
                    "homeassistant", "update_entity", 
                    {"entity_id": f"sensor.{DOMAIN}_{ieee.replace(':', '').lower()}_battery"}
                )
                await hass.services.async_call(
                    "homeassistant", "update_entity", 
                    {"entity_id": f"binary_sensor.{DOMAIN}_{ieee.replace(':', '').lower()}_battery_low"}
                )
            else:
                _LOGGER.warning(f"Received unexpected battery percentage value: {result}")
        else:
            _LOGGER.debug("Battery percentage poll returned None")

        # Try to read the battery voltage attribute
        voltage_result = await read_safe4_attribute(hass, ieee_with_colons, POWER_CLUSTER_ID, 0x0020)

        if voltage_result is not None:
            # Convert from millivolts to volts if needed
            if voltage_result > 100:
                voltage_result = voltage_result / 1000.0

            # Update the battery voltage in hass.data
            hass.data[f"{DOMAIN}:{ieee}:battery_voltage"] = voltage_result
            _LOGGER.info(f"Updated battery voltage to {voltage_result}V")

            # Force entity update
            await hass.services.async_call(
                "homeassistant", "update_entity", 
                {"entity_id": f"sensor.{DOMAIN}_{ieee.replace(':', '').lower()}_battery_voltage"}
            )

    except Exception as e:
        _LOGGER.error(f"Error polling battery level: {e}")
