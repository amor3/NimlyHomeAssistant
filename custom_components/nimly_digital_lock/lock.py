import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .entity import NimlyDigitalLock
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    ieee = entry.data["ieee"]
    name = entry.data.get("name", "Nimly Front Door")

    # Get the actual ZHA device from discovery if available
    zha_ieee = ""

    # Check if we found a ZHA device during setup
    if f"{DOMAIN}_ZHA_DEVICE" in hass.data and "zha_ieee" in hass.data[f"{DOMAIN}_ZHA_DEVICE"]:
        zha_device_ieee = hass.data[f"{DOMAIN}_ZHA_DEVICE"]["zha_ieee"]
        _LOGGER.info(f"Using discovered ZHA device IEEE: {zha_device_ieee}")
        zha_ieee = zha_device_ieee

    # Log info about the device setup
    _LOGGER.info(f"Setting up Nimly lock entity with IEEE {ieee} and name {name}")
    _LOGGER.info(f"Known ZHA device with IEEE {zha_ieee} will be used as a fallback")

    # Make sure the data structure is initialized
    if f"{DOMAIN}:{ieee}:lock_state" not in hass.data:
        hass.data[f"{DOMAIN}:{ieee}:lock_state"] = 1  # Default to locked
        _LOGGER.info(f"Initializing lock state to locked (1)")

    # Create the lock entity
    lock = NimlyDigitalLock(hass, ieee, name)
    async_add_entities([lock])

    # Try polling device directly
    try:
        # Use async_add_executor_job to run async code in synchronous method
        from .protocols import async_read_attribute_zbt1
        from .protocols import SAFE4_DOOR_LOCK_CLUSTER

        # Don't wait for result here, just trigger a poll that will update state
        # and be available next update cycle
        hass.async_create_task(
            async_read_attribute_zbt1(hass, ieee, SAFE4_DOOR_LOCK_CLUSTER, 0x0000)
        )
    except Exception as e:
        _LOGGER.debug(f"Direct polling in update failed (will use cached state): {e}")

    # Set up a periodic update every 30 seconds
    import asyncio

    async def periodic_update(lock_entity):
        _LOGGER.debug(f"Starting periodic update for lock entity {lock_entity.name}")
        while True:
            try:
                await lock_entity.async_update()
                _LOGGER.debug(f"Periodic update completed successfully for {lock_entity.name}")
            except Exception as e:
                import traceback
                _LOGGER.error(f"Error in periodic update for {lock_entity.name}: {e}")
                _LOGGER.error(f"Traceback: {traceback.format_exc()}")
            # Force state update
            lock_entity.async_write_ha_state()
            await asyncio.sleep(30)  # Update every 30 seconds

    # Start the periodic update task
    hass.loop.create_task(periodic_update(lock))
