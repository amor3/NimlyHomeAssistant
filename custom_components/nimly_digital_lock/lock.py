import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .entity import NimlyDigitalLock

_LOGGER = logging.getLogger(__name__)

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):
    ieee = entry.data["ieee"]
    name = entry.data.get("name", "Nimly Front Door")

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
                _LOGGER.error(f"Error in periodic update for {lock_entity.name}: {e}")
            # Force state update
            lock_entity.async_write_ha_state()
            await asyncio.sleep(30)  # Update every 30 seconds

    # Start the periodic update task
    hass.loop.create_task(periodic_update(lock))
