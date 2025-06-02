import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .entity import NimlyDigitalLock

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    ieee = entry.data["ieee"]
    name = entry.data.get("name", "Nimly Front Door")

    # Check if we should use the known ZHA device instead
    zha_ieee = "f4:ce:36:0a:04:4d:31:f5"

    # Log info about the device setup
    _LOGGER.info(f"Setting up Nimly lock entity with IEEE {ieee} and name {name}")
    _LOGGER.info(f"Known ZHA device with IEEE {zha_ieee} will be used as a fallback")

    # Create the lock entity
    lock = NimlyDigitalLock(hass, ieee, name)
    async_add_entities([lock])

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
