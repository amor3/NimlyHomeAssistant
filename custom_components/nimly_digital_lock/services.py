import voluptuous as vol
from homeassistant.helpers import config_validation as cv

import logging
from datetime import datetime
from homeassistant.core import HomeAssistant
from homeassistant.helpers.service import async_register_admin_service
from homeassistant.helpers.json import save_json

from .const import DOMAIN, SERVICE_UPDATE, SERVICE_EXPORT, SERVICE_SCHEMAS

_LOGGER = logging.getLogger(__name__)



# Service schemas
SEND_COMMAND_SCHEMA = vol.Schema({
    vol.Required("ieee"): cv.string,
    vol.Required("command"): vol.Any(int, str),  # Allow both int (0, 1) and string ('lock', 'unlock')
    vol.Optional("endpoint", default=11): cv.positive_int,
    vol.Optional("cluster_id", default=0x0101): cv.positive_int,
    vol.Optional("retry_count", default=5): cv.positive_int
})


async def async_register_services(hass: HomeAssistant) -> None:
    """Register services for ZHA Device Info."""

    async def handle_update(call) -> None:
        """Update device info."""
        _LOGGER.info("AMMM Updating ZHA device info")
        zha_data = hass.data.get("zha")

        if not zha_data or not zha_data.gateway_proxy:
            _LOGGER.info("AMMM ZHA gateway not found")
            return

        device_registry = {}
        try:
            for device in zha_data.gateway_proxy.gateway.devices.values():
                if device is None:
                    continue

                try:
                    last_seen = device.last_seen
                    if isinstance(last_seen, float):
                        last_seen = datetime.fromtimestamp(last_seen)

                    nwk_hex = f"0x{device.nwk:04x}"
                    device_info = {
                        "ieee": str(device.ieee),
                        "nwk": nwk_hex,
                        "manufacturer": device.manufacturer,
                        "model": device.model,
                        "name": device.name,
                        "quirk_applied": device.quirk_applied,
                        "power_source": device.power_source,
                        "lqi": device.lqi,
                        "rssi": device.rssi,
                        "last_seen": last_seen.isoformat() if last_seen else None,
                        "available": device.available,
                    }

                    # Add quirk_class if quirk is applied
                    if device.quirk_applied:
                        quirk = device.quirk_class
                        if isinstance(quirk, str):
                            device_info["quirk_class"] = quirk
                        elif hasattr(quirk, "__name__"):
                            device_info["quirk_class"] = quirk.__name__
                        else:
                            device_info["quirk_class"] = str(quirk)

                    device_registry[str(device.ieee)] = device_info

                    _LOGGER.info("AMMMUpdated info for device %s", device.ieee)
                    _LOGGER.info("AMMMUpdated DEVICE %s", device)
                except Exception as dev_err:
                    _LOGGER.info("AMMM Error processing device %s: %s", device.ieee, dev_err)

            # Store updated registry
            hass.data[DOMAIN]["device_registry"] = device_registry

            # Update the state of each ZHA Device Info sensor
            for entity in hass.data[DOMAIN]["entities"]:
                entity.async_write_ha_state()

        except Exception as err:
            _LOGGER.exception("Error processing devices: %s", err)

    async def handle_export(call) -> None:
        """Export device info to JSON."""
        path = call.data.get("path", hass.config.path("zha_devices.json"))
        try:
            device_registry = hass.data[DOMAIN]["device_registry"]
            if device_registry:
                await hass.async_add_executor_job(save_json, path, device_registry)
                _LOGGER.info("Exported ZHA device info to %s", path)
            else:
                _LOGGER.error("No device registry data to export")
        except Exception as err:
            _LOGGER.error("Failed to export: %s", err)

    # Register services
    async_register_admin_service(
        hass, DOMAIN, SERVICE_UPDATE, handle_update,
        schema=SERVICE_SCHEMAS[SERVICE_UPDATE]
    )
    _LOGGER.debug("Registered update service")

    async_register_admin_service(
        hass, DOMAIN, SERVICE_EXPORT, handle_export,
        schema=SERVICE_SCHEMAS[SERVICE_EXPORT]
    )
    _LOGGER.debug("Registered export service")