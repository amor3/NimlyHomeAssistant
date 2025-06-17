import logging
from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from . import MyClusterListener, ZHA_DOMAIN
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


    zha_data = hass.data.get("zha")
    _LOGGER.info("ANDREEE 123 GATEWAY: %s", zha_data.gateway_proxy.gateway)

    devices = zha_data.gateway_proxy.gateway.devices.items()
    _LOGGER.info("ANDREEE 123 DEVICES %s", devices)

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

                    listener = MyClusterListener(lock)

                    lock.set_cluster_listener(listener)
                    cluster.add_listener(listener)

                    _LOGGER.info(f"Listener added to cluster 0x0101 on endpoint {ep_id}")

                    _LOGGER.info("ANDREEEEE Attaching listener to cluster: %s", cluster)

                    break
            else:
                _LOGGER.warning("Door Lock cluster (0x0101) not found on any endpoint")
        else:
            _LOGGER.info("ANDREEE 123 FAIL MATCH: dev_id: %s not ieee: %", dev_id, ieee)
