import logging
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceEntry
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity_registry import EntityRegistry
from homeassistant.helpers.event import async_track_state_change_event
from zigpy.types import EUI64
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED

from .const import DOMAIN, PLATFORMS, SERVICE_UPDATE

from .services import async_register_services

# Define ZHA domain constant directly instead of importing from unavailable path
ZHA_DOMAIN = "zha"
from .const import DOMAIN, ATTRIBUTE_MAP
from .zha_mapping import normalize_ieee, format_ieee

_LOGGER = logging.getLogger(__name__)


class MyClusterListener:
    def attribute_updated(self, attrid, value, received_timestamp):
        _LOGGER.debug(
            "[ZCL ANDRE] Attribute Updated - AttrID: 0x%04X, Value: %s, Time: %s",
            attrid, value, received_timestamp
        )

    def cluster_command(self, tsn, command_id, args):
        _LOGGER.debug(
            "[ZCL ANDRE] Cluster Command - TSN: %s, Command ID: 0x%02X, Args: %s",
            tsn, command_id, args
        )

    def raw_frame(self, frame):
        _LOGGER.debug("[ZCL ANDRE] Raw Frame Received: %s", frame.hex())

    def zdo_command(self, *args, **kwargs):
        _LOGGER.debug("[ZDO ANDRE] Command Received: args=%s kwargs=%s", args, kwargs)



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

        zha_data = hass.data.get("zha")


        _LOGGER.info("ANDREEE 123 GATEWAY: %s",  zha_data.gateway_proxy.gateway)

        devices = zha_data.gateway_proxy.gateway.devices.items()

        _LOGGER.info("ANDREEE 123 DEVICES %s",  devices)

        ieee = entry.data["ieee"]

        for dev_id, d in devices:
            _LOGGER.info("ANDREEE 123 ONE DEV: %s", d)
            _LOGGER.info("ANDREEE 123 ONE DEV IEEE: %s", d.ieee)
            _LOGGER.info("ANDREEE 123 ONE DEV MATCH AGAINST: %s", ieee)

            if str(d.ieee) == ieee.lower():
                _LOGGER.info("ANDREEE 123 HIT HIT HIT")

                _LOGGER.info("ANDREEE 123 ONE DEV endpoints items: %s", d.endpoints.items())

                for ep_id, endpoint in d.device.endpoints.items():
                    if ep_id == 0:
                        continue  # Skip ZDO endpoint

                    if 0x0101 in endpoint.in_clusters:
                        _LOGGER.info(f"Found Door Lock cluster on endpoint {ep_id}")
                        cluster = endpoint.in_clusters[0x0101]
                        cluster.add_listener(MyClusterListener())
                        _LOGGER.info(f"Listener added to cluster 0x0101 on endpoint {ep_id}")

                        _LOGGER.info("ANDREEEEE Attaching listener to cluster: %s", cluster)

                        break
                else:
                    _LOGGER.warning("Door Lock cluster (0x0101) not found on any endpoint")

                """
                cluster = d.endpoints[11].in_clusters[0x0101]
                _LOGGER.info("ANDREEE 123 ONE DEV cluster: %s", cluster)

                cluster.add_listener(MyClusterListener())
                _LOGGER.info("ANDREEE 123 ONE DEV listener added.")
                """
            else:
                _LOGGER.info("ANDREEE 123 FAIL MATCH: dev_id: %s not ieee: %", dev_id, ieee)


        """
        _LOGGER.info("ANDREEE 123")
        devize = zha_data.gateway_proxy.gateway.device
        _LOGGER.info("ANDREEE 1234")
        cluster = devize.endpoints[11].in_clusters[0x0101]
        _LOGGER.info("ANDREEE 12345")
        cluster.add_listener(MyClusterListener())
        _LOGGER.info("ANDREEE 123456")
        """

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