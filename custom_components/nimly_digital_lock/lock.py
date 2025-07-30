import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from . import MyClusterListener
from .entity import NimlyDigitalLock
from .const import DOMAIN
import logging


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

    _LOGGER.info(f"Setting up Nimly lock entity with IEEE {ieee} and name {name}")
    _LOGGER.info(f"Known ZHA device with IEEE {zha_ieee} will be used as a fallback")

    # Make sure the data structure is initialized
    if f"{DOMAIN}:{ieee}:lock_state" not in hass.data:
        hass.data[f"{DOMAIN}:{ieee}:lock_state"] = 1  # Default to locked
        _LOGGER.info(f"Initializing lock state to locked (1)")

    lock = NimlyDigitalLock(hass, ieee, name)
    ieee_key = ieee.lower().replace(":", "")

    zha_data = hass.data.get("zha")
    _LOGGER.info("[AM] GATEWAY: %s", zha_data.gateway_proxy.gateway)

    devices = zha_data.gateway_proxy.gateway.devices.items()
    _LOGGER.info("[AM] DEVICES %s", devices)

    for dev_id, d in devices:
        _LOGGER.info("[AM] d: %s", d)

        if str(d.ieee) == ieee.lower():
            _LOGGER.info("[AM] endpoints items: %s", d.endpoints.items())

            for ep_id, endpoint in d.device.endpoints.items():
                if ep_id == 0:
                    continue  # Skip ZDO endpoint

                if 0x0101 in endpoint.in_clusters:
                    _LOGGER.info(f"[AM] Found Door Lock cluster on endpoint {ep_id}")
                    cluster = endpoint.in_clusters[0x0101]

                    listener = MyClusterListener(lock)
                    lock.set_cluster_listener(listener)
                    cluster.add_listener(listener)

                    async_add_entities([lock])

                    _LOGGER.info(f"[AM] Listener added to cluster 0x0101 on endpoint {ep_id}")
                    _LOGGER.info("[AM] Attaching listener to cluster: %s", cluster)
                    break
            else:
                _LOGGER.warning("[AM] Door Lock cluster (0x0101) not found on any endpoint")
        else:
            _LOGGER.info("[AM] FAIL MATCH: dev_id: %s not ieee: %", dev_id, ieee)


    #async_add_entities([lock])
