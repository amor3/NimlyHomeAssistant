"""Nimly Digital Lock: lock activity and PIN management on top of ZHA."""

from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers import (
    config_validation as cv,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)
from homeassistant.helpers.typing import ConfigType

from .const import (
    CONF_IEEE,
    CONF_MODEL,
    DOMAIN,
    ISSUE_QUIRK_MISSING,
    ISSUE_ZHA_INTERNALS,
    ZHA_DOMAIN,
)
from .discovery import async_discover_locks, async_setup_discovery
from .manager import NimlyConfigEntry, NimlyLockManager, lock_store
from .services import async_setup_services
from .zha import (
    ZhaInternalsMissing,
    find_door_lock_cluster,
    is_zha_running,
    lock_in_zha,
    model_in_zha,
    quirk_status,
)

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.EVENT, Platform.SENSOR]
CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Register the actions and the discovery watch once for all locks."""
    async_setup_services(hass)
    async_setup_discovery(hass)
    return True


def normalize_ieee(value: str) -> str:
    """Lowercase colon-separated IEEE address, as zigpy prints it."""
    digits = re.sub(r"[^0-9a-fA-F]", "", value).lower()
    return ":".join(digits[i : i + 2] for i in range(0, len(digits), 2))


async def async_migrate_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Migrate entries from 1.x, which duplicated ZHA's own entities.

    Version 1 created its own lock, battery, RSSI, switch and select
    entities on a separate service device. ZHA provides all of those, so
    they and the device are removed and the entry is keyed on the address.
    """
    if entry.version > 2:
        return False
    if entry.version == 1:
        ieee = normalize_ieee(entry.data.get(CONF_IEEE, ""))
        entity_registry = er.async_get(hass)
        for entity in er.async_entries_for_config_entry(entity_registry, entry.entry_id):
            entity_registry.async_remove(entity.entity_id)
        device_registry = dr.async_get(hass)
        for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id):
            device_registry.async_update_device(device.id, remove_config_entry_id=entry.entry_id)
        # 1.x had no unique id, so the same lock could be added twice; only
        # the first entry migrated gets the address as its unique id.
        taken = any(
            other.unique_id == ieee
            for other in hass.config_entries.async_entries(DOMAIN)
            if other.entry_id != entry.entry_id
        )
        hass.config_entries.async_update_entry(
            entry,
            data={CONF_IEEE: ieee, CONF_MODEL: model_in_zha(hass, ieee)},
            options={},
            unique_id=None if taken else ieee,
            version=2,
        )
        _LOGGER.info("Migrated %s to version 2; ZHA now owns lock and battery", ieee)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: NimlyConfigEntry) -> bool:
    """Set up one lock."""
    ieee: str = entry.data[CONF_IEEE]
    if not is_zha_running(hass):
        raise ConfigEntryNotReady(translation_domain=DOMAIN, translation_key="zha_not_running")
    if not lock_in_zha(hass, ieee):
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="lock_not_in_zha",
            translation_placeholders={"ieee": ieee},
        )
    if (cluster := find_door_lock_cluster(hass, ieee)) is None:
        # The device is there but its interview has not exposed the
        # Door Lock cluster yet; Home Assistant retries with backoff.
        raise ConfigEntryNotReady(
            translation_domain=DOMAIN,
            translation_key="cluster_missing",
            translation_placeholders={"ieee": ieee},
        )

    manager = NimlyLockManager(hass, entry)
    await manager.async_load()
    entry.runtime_data = manager
    entry.async_on_unload(manager.async_shutdown)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    _start_listening(hass, entry, manager, cluster)
    _check_quirk(hass, entry)
    _watch_zha(hass, entry)
    manager.async_schedule_expiries()
    manager.schedule_capability_refresh()
    async_discover_locks(hass)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: NimlyConfigEntry) -> bool:
    """Unload a lock."""
    await entry.runtime_data.async_flush()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_remove_entry(hass: HomeAssistant, entry: NimlyConfigEntry) -> None:
    """Remove stored slot names when the lock is deleted."""
    await lock_store(hass, entry).async_remove()


async def async_remove_config_entry_device(
    hass: HomeAssistant, entry: NimlyConfigEntry, device_entry: dr.DeviceEntry
) -> bool:
    """Allow removing a device only when it is not this entry's lock."""
    return (DOMAIN, entry.entry_id) not in device_entry.identifiers


@callback
def _start_listening(
    hass: HomeAssistant, entry: NimlyConfigEntry, manager: NimlyLockManager, cluster: Any
) -> None:
    """Subscribe to lock events, or raise a repair issue saying why not."""
    issue_id = f"{ISSUE_ZHA_INTERNALS}_{entry.entry_id}"
    entry.async_on_unload(lambda: ir.async_delete_issue(hass, DOMAIN, issue_id))
    try:
        entry.async_on_unload(manager.async_start_listening(cluster))
    except ZhaInternalsMissing as err:
        _LOGGER.error("Cannot receive events from lock %s: %s", manager.ieee, err)
        ir.async_create_issue(
            hass,
            DOMAIN,
            issue_id,
            is_fixable=False,
            severity=ir.IssueSeverity.ERROR,
            translation_key=ISSUE_ZHA_INTERNALS,
            translation_placeholders={"detail": str(err), "ieee": manager.ieee},
        )
        return
    ir.async_delete_issue(hass, DOMAIN, issue_id)


@callback
def _check_quirk(hass: HomeAssistant, entry: NimlyConfigEntry) -> None:
    """Warn when ZHA runs the lock without a device quirk.

    Without the Nimly quirk ZHA shows no auto relock or volume control and
    may get the battery wrong. This integration works either way.
    """
    issue_id = f"{ISSUE_QUIRK_MISSING}_{entry.entry_id}"
    status = quirk_status(hass, entry.data[CONF_IEEE])
    if status is None or status.applied:
        ir.async_delete_issue(hass, DOMAIN, issue_id)
        return
    _LOGGER.warning(
        "ZHA applied no quirk to lock %s (%s); auto relock and volume are missing in ZHA",
        entry.data[CONF_IEEE],
        status.quirk_class,
    )
    ir.async_create_issue(
        hass,
        DOMAIN,
        issue_id,
        is_fixable=False,
        severity=ir.IssueSeverity.WARNING,
        translation_key=ISSUE_QUIRK_MISSING,
        translation_placeholders={"title": entry.title},
        learn_more_url="https://github.com/amor3/NimlyHomeAssistant#zha-does-not-show-auto-relock-or-volume",
    )


@callback
def _watch_zha(hass: HomeAssistant, entry: NimlyConfigEntry) -> None:
    """Reload when ZHA reloads: its new zigpy objects need a new listener."""

    @callback
    def _on_zha_state_change(zha_entry: ConfigEntry) -> None:
        if entry.state is not ConfigEntryState.LOADED:
            return
        if zha_entry.state is ConfigEntryState.LOADED:
            hass.config_entries.async_schedule_reload(entry.entry_id)
        elif entry.runtime_data.listening:
            entry.runtime_data.listening = False
            entry.runtime_data.async_update_listeners()

    for zha_entry in hass.config_entries.async_entries(ZHA_DOMAIN):

        @callback
        def _state_changed(zha_entry: ConfigEntry = zha_entry) -> None:
            _on_zha_state_change(zha_entry)

        entry.async_on_unload(zha_entry.async_on_state_change(_state_changed))
