"""Offer Nimly locks that ZHA pairs after the first one is set up.

Home Assistant only loads a custom integration that has a config entry, so
the first lock is added by hand; from then on, every Nimly lock ZHA knows
without an entry shows up under Discovered.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import SOURCE_INTEGRATION_DISCOVERY
from homeassistant.core import Event, HomeAssistant, callback
from homeassistant.helpers import device_registry as dr

from .const import CONF_IEEE, CONF_MODEL, DOMAIN
from .zha import iter_nimly_locks

_LOGGER = logging.getLogger(__name__)


@callback
def async_setup_discovery(hass: HomeAssistant) -> None:
    """Look for new locks whenever ZHA adds or updates a Zigbee device."""

    @callback
    def _on_device_registry_updated(event: Event[dr.EventDeviceRegistryUpdatedData]) -> None:
        if event.data["action"] not in ("create", "update"):
            return
        async_discover_locks(hass)

    hass.bus.async_listen(dr.EVENT_DEVICE_REGISTRY_UPDATED, _on_device_registry_updated)


@callback
def async_discover_locks(hass: HomeAssistant) -> None:
    """Start a discovery flow for each Nimly lock without a config entry."""
    # Ignored entries carry only a unique id, so it counts as known too.
    known = {
        str(address).lower()
        for entry in hass.config_entries.async_entries(DOMAIN, include_ignore=True)
        for address in (entry.unique_id, entry.data.get(CONF_IEEE))
        if address
    }
    in_progress = {
        str(flow["context"].get("unique_id", "")).lower()
        for flow in hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    }
    for ieee, model in iter_nimly_locks(hass):
        if ieee in known or ieee in in_progress:
            continue
        _LOGGER.debug("Nimly lock %s in ZHA has no config entry; offering it", ieee)
        hass.async_create_task(
            hass.config_entries.flow.async_init(
                DOMAIN,
                context={"source": SOURCE_INTEGRATION_DISCOVERY},
                data={CONF_IEEE: ieee, CONF_MODEL: model},
            ),
            eager_start=True,
        )
