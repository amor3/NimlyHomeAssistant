import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry
from .entity import NimlyDigitalLock
from .const import DOMAIN
from homeassistant.components.lock import LockEntity
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from zigpy.types import EUI64
import logging

_LOGGER = logging.getLogger(__name__)

"""
async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities):

    ieee = entry.data["ieee"]
    name = entry.data.get("name", "Nimly Front Door")

    # Example static setup - replace with dynamic discovery if needed
    locks = [
        {
            "name": name,
            "ieee": ieee
        },
    ]

    entities = [NimlyDigitalLockEntity(lock["name"], lock["ieee"]) for lock in locks]
    async_add_entities(entities)

class NimlyDigitalLockEntity(LockEntity):
    def __init__(self, name, ieee):
        self._name = name
        self._ieee = ieee.lower()
        self._ieee_with_colons = ":".join(self._ieee[i:i+2] for i in range(0, 16, 2))
        self._is_locked = None
        self._remove_listener = None
        self._hass = None

    @property
    def name(self):
        return self._name

    @property
    def is_locked(self):
        return self._is_locked

    async def async_added_to_hass(self):
        self._hass = self.hass
        self._remove_listener = async_dispatcher_connect(
            self._hass,
            "zha_event",
            self._handle_zha_event
        )
        _LOGGER.info(f"ZHA event listener registered for {self._name}")

    async def async_will_remove_from_hass(self):
        if self._remove_listener:
            self._remove_listener()
            self._remove_listener = None

    async def _handle_zha_event(self, event):
        data = event.data

        if data.get("device_ieee") != self._ieee_with_colons:
            return

        if data.get("cluster_id") != 0x0101 or data.get("endpoint_id") != 11:
            return

        command = data.get("command")
        args = data.get("args", {})

        user_id = args.get("user_id")
        method = args.get("operation_event_source")

        if command == "lock_operation":
            self._is_locked = True
        elif command == "unlock_operation":
            self._is_locked = False
        else:
            _LOGGER.debug(f"Ignored ZHA command: {command}")
            return

        result_json = {
            "event": command,
            "user_id": user_id,
            "method": method
        }

        _LOGGER.info(f"ZHA lock event received: {result_json}")
        self._hass.data[f"{DOMAIN}:{self._ieee}:lock_state"] = result_json

        self.async_write_ha_state()
        """

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
        from .zbt1_support import async_read_attribute_zbt1
        from .zha_mapping import SAFE4_DOOR_LOCK_CLUSTER

        # Don't wait for result here, just trigger a poll that will update state
        # and be available next update cycle
        hass.async_create_task(
            async_read_attribute_zbt1(hass, ieee, SAFE4_DOOR_LOCK_CLUSTER, 0x0000)
        )
    except Exception as e:
        _LOGGER.debug(f"Direct polling in update failed (will use cached state): {e}")

    # Set up a periodic update every 30 seconds
    import asyncio

    """
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
            await asyncio.sleep(5)  # Update every 30 seconds

    hass.loop.create_task(periodic_update(lock))
    """

    async def _handle_zha_event(self, event):
        data = event.data

        if data.get("device_ieee") != self._ieee_with_colons:
            return

        if data.get("cluster_id") != 0x0101 or data.get("endpoint_id") != 11:
            return

        command = data.get("command")
        args = data.get("args", {})

        user_id = args.get("user_id")
        method = args.get("operation_event_source")

        if command == "lock_operation":
            self._is_locked = True
        elif command == "unlock_operation":
            self._is_locked = False
        else:
            _LOGGER.debug(f"Ignored ZHA command: {command}")
            return

        result_json = {
            "event": command,
            "user_id": user_id,
            "method": method
        }

        _LOGGER.info(f"ZHA lock event received: {result_json}")
        self._hass.data[f"{DOMAIN}:{self._ieee}:lock_state"] = result_json

        self.async_write_ha_state()