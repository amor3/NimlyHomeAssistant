import logging
import asyncio
from .const import DOMAIN, LOCK_CLUSTER_ID, POWER_CLUSTER_ID
from .protocols import read_safe4_attribute
from .protocols import SAFE4_DOOR_LOCK_CLUSTER, SAFE4_POWER_CLUSTER, ZBT1_ENDPOINTS

_LOGGER = logging.getLogger(__name__)

async def start_polling_service(hass, ieee, poll_interval=60):
    _LOGGER.info(f"Starting polling service for lock with IEEE {ieee} (interval: {poll_interval}s)")

    # Format IEEE with colons for consistency
    from .protocols import format_ieee_with_colons
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
    try:
        from .const import DOMAIN

        # Read lock state (0x0000) from Door Lock cluster (0x0101) using ZHA service
        service_data = {
            "ieee": ieee_with_colons,
            "endpoint_id": 11,  # ZBT-1 uses endpoint 11
            "cluster_id": 0x0101,  # Door Lock cluster
            "cluster_type": "in",
            "attribute": 0x0000  # Lock State attribute
        }

        result = await hass.services.async_call(
            "zha", "get_zigbee_cluster_attribute", service_data, blocking=True, return_response=True
        )

        if result is not None:
            # Update the lock state in hass.data using both IEEE formats for consistency
            _LOGGER.debug(f"Lock state poll result: {result}")

            # Lock state is 0 for unlocked, 1 for locked, 2 for error
            if result in [0, 1, 2]:
                # Store in both IEEE formats to ensure consistency
                hass.data[f"{DOMAIN}:{ieee}:lock_state"] = result
                ieee_no_colons = ieee.replace(':', '').lower()
                hass.data[f"{DOMAIN}:{ieee_no_colons}:lock_state"] = result

                # Make the state human-readable for logs
                state_text = "unlocked" if result == 0 else "locked" if result == 1 else "error"
                _LOGGER.info(f"Updated lock state to {result} ({state_text})")

                # Force entity update
                entity_id = f"lock.{DOMAIN}_{ieee.replace(':', '').lower()}"
                try:
                    await hass.services.async_call(
                        "homeassistant", "update_entity", {"entity_id": entity_id}
                    )
                except Exception as update_error:
                    _LOGGER.warning(f"Failed to update entity {entity_id}: {update_error}")
            else:
                _LOGGER.warning(f"Received unexpected lock state value: {result}")
        else:
            # If Safe4 method failed, try with ZBT-1 support module
            # We already imported these modules above, just using them here
            from .const import LOCK_CLUSTER_ID
            from .protocols import async_read_attribute_zbt1

            result = await async_read_attribute_zbt1(hass, ieee_with_colons, LOCK_CLUSTER_ID, 0x0000)
            if result is not None:
                # Store in both IEEE formats for consistency
                hass.data[f"{DOMAIN}:{ieee}:lock_state"] = result
                ieee_no_colons = ieee.replace(':', '').lower()
                hass.data[f"{DOMAIN}:{ieee_no_colons}:lock_state"] = result

                # Make the state human-readable for logs
                state_text = "unlocked" if result == 0 else "locked" if result == 1 else "error"
                _LOGGER.info(f"Updated lock state to {result} ({state_text}) using ZBT-1 method")

                # Force entity update
                entity_id = f"lock.{DOMAIN}_{ieee.replace(':', '').lower()}"
                try:
                    await hass.services.async_call(
                        "homeassistant", "update_entity", {"entity_id": entity_id}
                    )
                except Exception as update_error:
                    _LOGGER.warning(f"Failed to update entity {entity_id}: {update_error}")
            else:
                _LOGGER.debug("Lock state poll returned None from all methods")

    except Exception as e:
        _LOGGER.error(f"Error polling lock state: {e}")

async def poll_battery_level(hass, ieee, ieee_with_colons):
    try:
        from .const import DOMAIN

        # Clean the IEEE for entity IDs
        ieee_clean = ieee.replace(':', '').lower()

        # Read battery percentage (0x0021) from Power cluster (0x0001) using ZHA service
        service_data = {
            "ieee": ieee_with_colons,
            "endpoint_id": 11,  # ZBT-1 uses endpoint 11
            "cluster_id": 0x0001,  # Power Configuration cluster
            "cluster_type": "in",
            "attribute": 0x0021  # Battery percentage remaining
        }

        result = await hass.services.async_call(
            "zha", "get_zigbee_cluster_attribute", service_data, blocking=True, return_response=True
        )

        if result is not None:
            # Update the battery percentage in hass.data
            _LOGGER.debug(f"Battery percentage poll result: {result}")

            # Make sure the value is between 0 and 100
            if isinstance(result, (int, float)) and 0 <= result <= 100:
                # Store in both IEEE formats for consistency
                hass.data[f"{DOMAIN}:{ieee}:battery"] = result
                hass.data[f"{DOMAIN}:{ieee_clean}:battery"] = result
                _LOGGER.info(f"Updated battery percentage to {result}%")

                # Also set battery_low status if below 15%
                battery_low = result < 15
                battery_low_value = 1 if battery_low else 0
                hass.data[f"{DOMAIN}:{ieee}:battery_low"] = battery_low_value
                hass.data[f"{DOMAIN}:{ieee_clean}:battery_low"] = battery_low_value
                _LOGGER.debug(f"Battery low status set to {battery_low}")

                # Force entity updates
                try:
                    await hass.services.async_call(
                        "homeassistant", "update_entity", 
                        {"entity_id": f"sensor.{DOMAIN}_{ieee_clean}_battery"}
                    )
                    await hass.services.async_call(
                        "homeassistant", "update_entity", 
                        {"entity_id": f"binary_sensor.{DOMAIN}_{ieee_clean}_battery_low"}
                    )
                except Exception as update_error:
                    _LOGGER.warning(f"Failed to update battery entities: {update_error}")
            else:
                _LOGGER.warning(f"Received unexpected battery percentage value: {result}")
        else:
            # If Safe4 method failed, try with ZBT-1 support module
            from .protocols import async_read_attribute_zbt1
            from .const import POWER_CLUSTER_ID

            result = await async_read_attribute_zbt1(hass, ieee_with_colons, POWER_CLUSTER_ID, 0x0021)
            if isinstance(result, (int, float)) and 0 <= result <= 100:
                # Store in both IEEE formats for consistency
                hass.data[f"{DOMAIN}:{ieee}:battery"] = result
                hass.data[f"{DOMAIN}:{ieee_clean}:battery"] = result
                _LOGGER.info(f"Updated battery percentage to {result}% using ZBT-1 method")

                # Also set battery_low status if below 15%
                battery_low = result < 15
                battery_low_value = 1 if battery_low else 0
                hass.data[f"{DOMAIN}:{ieee}:battery_low"] = battery_low_value
                hass.data[f"{DOMAIN}:{ieee_clean}:battery_low"] = battery_low_value

                # Force entity updates
                try:
                    await hass.services.async_call(
                        "homeassistant", "update_entity", 
                        {"entity_id": f"sensor.{DOMAIN}_{ieee_clean}_battery"}
                    )
                    await hass.services.async_call(
                        "homeassistant", "update_entity", 
                        {"entity_id": f"binary_sensor.{DOMAIN}_{ieee_clean}_battery_low"}
                    )
                except Exception as update_error:
                    _LOGGER.warning(f"Failed to update battery entities: {update_error}")
            else:
                _LOGGER.debug("Battery percentage poll returned None from all methods")

        # Try to read the battery voltage attribute
        from .protocols import read_safe4_attribute
        voltage_result = await read_safe4_attribute(hass, ieee_with_colons, SAFE4_POWER_CLUSTER, 0x0020)

        if voltage_result is not None:
            # Convert from millivolts to volts if needed
            if isinstance(voltage_result, (int, float)) and voltage_result > 100:
                voltage_result = voltage_result / 1000.0

            # Update the battery voltage in hass.data
            hass.data[f"{DOMAIN}:{ieee}:battery_voltage"] = voltage_result
            hass.data[f"{DOMAIN}:{ieee_clean}:battery_voltage"] = voltage_result
            _LOGGER.info(f"Updated battery voltage to {voltage_result}V")

            # Force entity update
            try:
                await hass.services.async_call(
                    "homeassistant", "update_entity", 
                    {"entity_id": f"sensor.{DOMAIN}_{ieee_clean}_battery_voltage"}
                )
            except Exception as update_error:
                _LOGGER.warning(f"Failed to update battery voltage entity: {update_error}")
        else:
            # If Safe4 method failed, try with ZBT-1 support module
            voltage_result = await async_read_attribute_zbt1(hass, ieee_with_colons, POWER_CLUSTER_ID, 0x0020)
            if voltage_result is not None:
                # Convert from millivolts to volts if needed
                if isinstance(voltage_result, (int, float)) and voltage_result > 100:
                    voltage_result = voltage_result / 1000.0

                # Update the battery voltage in hass.data
                hass.data[f"{DOMAIN}:{ieee}:battery_voltage"] = voltage_result
                hass.data[f"{DOMAIN}:{ieee_clean}:battery_voltage"] = voltage_result
                _LOGGER.info(f"Updated battery voltage to {voltage_result}V using ZBT-1 method")

                # Force entity update
                try:
                    await hass.services.async_call(
                        "homeassistant", "update_entity", 
                        {"entity_id": f"sensor.{DOMAIN}_{ieee_clean}_battery_voltage"}
                    )
                except Exception as update_error:
                    _LOGGER.warning(f"Failed to update battery voltage entity: {update_error}")

    except Exception as e:
        _LOGGER.error(f"Error polling battery level: {e}")
