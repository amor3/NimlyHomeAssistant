import logging

from homeassistant.components.logbook import async_log_entry
from homeassistant.components.lock import LockEntity
from homeassistant.components.zha.logbook import async_describe_events
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.event import async_track_state_change_event
from zigpy.types import EUI64
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from zigpy.zcl.clusters.closures import LockState

from .const import DOMAIN, PLATFORMS, SERVICE_UPDATE
from .entity import NimlyDigitalLock

from .services import async_register_services

# Define ZHA domain constant directly instead of importing from unavailable path
ZHA_DOMAIN = "zha"
from .const import DOMAIN, ATTRIBUTE_MAP
from .zha_mapping import normalize_ieee, format_ieee

_LOGGER = logging.getLogger(__name__)


class MyClusterListener:

    def __init__(self, lock: NimlyDigitalLock):
        self._lock = lock

    def attribute_updated(self, attrid, value, received_timestamp):
        self._lock.attribute_updated(attrid, value)

        _LOGGER.info(
            "[ZCL ANDRE] Attribute Updated - AttrID: 0x%04X, Value: %s, Time: %s",
            attrid, value, received_timestamp
        )

    def cluster_command(self, tsn, command_id, args):
        _LOGGER.info(
            "[ZCL ANDRE] Cluster Command - TSN: %s, Command ID: 0x%02X, Args: %s",
            tsn, command_id, args
        )

    def raw_frame(self, frame):
        _LOGGER.info("[ZCL ANDRE] Raw Frame Received: %s", frame.hex())

    def zdo_command(self, *args, **kwargs):
        _LOGGER.info("[ZDO ANDRE] Command Received: args=%s kwargs=%s", args, kwargs)



def has_matching_ieee(device_entry: DeviceEntry, ieee: str) -> bool:
    """Check if device_entry contains the given IEEE address in identifiers or connections."""
    for domain, identifier in device_entry.identifiers:
        if identifier.lower() == ieee.lower():
            return True

    for conn_type, address in device_entry.connections:
        if address.lower() == ieee.lower():
            return True

    return False


async def async_setup(hass: HomeAssistant, config: dict):
    return True




async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up config entry."""
    _LOGGER.info("ANDREEE Setting up ZHA Device Info config entry")
    try:
        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {
                "device_registry": {},
                "entities": []
            }
        _LOGGER.info("ANDREEE Initialized device registry and entities list")

        await async_register_services(hass)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

        # Initial update
        async def initial_update(event):
            await hass.services.async_call(DOMAIN, SERVICE_UPDATE)

        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED,
            initial_update
        )

        _LOGGER.info("ANDREEE ZHA Device Info config entry setup complete")
        return True
    except Exception as err:
        _LOGGER.error("Error setting up config entry: %s", err)
        return False




async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload config entry."""
    _LOGGER.debug("Unloading ZHA Device Info config entry")
    try:
        result = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
        _LOGGER.debug("ZHA Device Info config entry unloaded")
        return result
    except Exception as err:
        _LOGGER.error("Error unloading config entry: %s", err)
        return False