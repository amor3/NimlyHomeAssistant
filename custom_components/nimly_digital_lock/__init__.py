import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED

from .const import DOMAIN, PLATFORMS, SERVICE_UPDATE
from .entity import NimlyDigitalLock

from .services import async_register_services

# Define ZHA domain constant directly instead of importing from unavailable path
ZHA_DOMAIN = "zha"
from .const import DOMAIN, ATTRIBUTE_MAP

_LOGGER = logging.getLogger(__name__)


class MyClusterListener:

    def __init__(self, lock: NimlyDigitalLock):
        self._lock = lock
        self._diagnostic_sensors = {}

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
    _LOGGER.info("[AM] Setting up ZHA Device Info config entry")
    try:
        if DOMAIN not in hass.data:
            hass.data[DOMAIN] = {
                "device_registry": {},
                "entities": [],
                "battery_sensors": {},
                "rssi_sensors": {},
            }
        _LOGGER.info("[AM] Initialized device registry and entities list")

        await async_register_services(hass)

        _LOGGER.info("[AM] Adding platform: %s", PLATFORMS)
        await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)


        # Initial update
        async def initial_update(event):
            await hass.services.async_call(DOMAIN, SERVICE_UPDATE)

        hass.bus.async_listen_once(
            EVENT_HOMEASSISTANT_STARTED,
            initial_update
        )

        _LOGGER.info("[AM] ZHA Device Info config entry setup complete")
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