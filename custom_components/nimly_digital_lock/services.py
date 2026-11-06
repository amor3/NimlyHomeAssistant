"""Actions for managing PIN codes and slot names."""

from __future__ import annotations

from datetime import datetime

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.util import dt as dt_util

from . import rules
from .compat import vol
from .const import CONF_IEEE, DOMAIN, MAX_SLOT, NimlyService, NimlyServiceArgument as Arg
from .manager import NimlyConfigEntry, NimlyLockManager, to_utc
from .rules import CREDENTIAL_KINDS
from .zha import SendOutcome

_BASE = {
    # Either names the lock; with a single lock set up, neither is needed.
    vol.Exclusive(Arg.CONFIG_ENTRY_ID.value, "lock"): cv.string,
    vol.Exclusive(ATTR_DEVICE_ID, "lock"): cv.string,
    vol.Required(Arg.SLOT.value): vol.All(vol.Coerce(int), vol.Range(min=0)),
}

SET_PIN_SCHEMA = vol.Schema(
    {
        **_BASE,
        vol.Required(Arg.PIN_CODE.value): cv.string,
        vol.Optional(Arg.NAME.value): cv.string,
        vol.Exclusive(Arg.VALID_UNTIL.value, "expiry"): cv.datetime,
        vol.Exclusive(Arg.VALID_FOR.value, "expiry"): cv.positive_time_period,
    }
)
CLEAR_PIN_SCHEMA = vol.Schema(_BASE)
SET_SLOT_NAME_SCHEMA = vol.Schema(
    {
        **_BASE,
        vol.Required(Arg.NAME.value): vol.Any(cv.string, ""),
        vol.Optional(Arg.CREDENTIAL.value): vol.In(CREDENTIAL_KINDS),
    }
)


def _entry_for_device(hass: HomeAssistant, device_id: str) -> NimlyConfigEntry | None:
    """The entry for our own device, or for ZHA's device of the same lock."""
    if (device := dr.async_get(hass).async_get(device_id)) is None:
        return None
    entries: list[NimlyConfigEntry] = hass.config_entries.async_entries(DOMAIN)
    # Child devices (newer Home Assistant) have no connections.
    connections = device.connections if isinstance(device, dr.DeviceEntry) else set()
    for entry in entries:
        if (DOMAIN, entry.entry_id) in device.identifiers:
            return entry
        if (dr.CONNECTION_ZIGBEE, str(entry.data.get(CONF_IEEE, "")).lower()) in connections:
            return entry
    return None


def _manager(hass: HomeAssistant, call: ServiceCall) -> NimlyLockManager:
    entry: NimlyConfigEntry | None
    if (entry_id := call.data.get(Arg.CONFIG_ENTRY_ID)) is not None:
        entry = hass.config_entries.async_get_entry(entry_id)
    elif (device_id := call.data.get(ATTR_DEVICE_ID)) is not None:
        entry = _entry_for_device(hass, device_id)
    else:
        loaded = [
            candidate
            for candidate in hass.config_entries.async_entries(DOMAIN)
            if candidate.state is ConfigEntryState.LOADED
        ]
        if len(loaded) != 1:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="lock_required")
        entry = loaded[0]
    if entry is None or entry.domain != DOMAIN:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="entry_not_found")
    if entry.state is not ConfigEntryState.LOADED:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="entry_not_loaded")
    return entry.runtime_data


def _expiry(call: ServiceCall) -> datetime | None:
    """When a temporary code should be cleared, as aware UTC, or None."""
    if (period := call.data.get(Arg.VALID_FOR)) is not None:
        return dt_util.utcnow() + period
    if (until := call.data.get(Arg.VALID_UNTIL)) is None:
        return None
    if (until := to_utc(until)) <= dt_util.utcnow():
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="expiry_in_past")
    return until


def _check_slot(manager: NimlyLockManager, slot: int, highest: int) -> None:
    if not manager.first_user_slot <= slot <= highest:
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="slot_out_of_range",
            translation_placeholders={
                "slot": str(slot),
                "first": str(manager.first_user_slot),
                "last": str(highest),
            },
        )


def _raise_for(outcome: SendOutcome) -> None:
    if not outcome.delivered:
        raise HomeAssistantError(translation_domain=DOMAIN, translation_key=outcome.error_key)


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration's actions."""

    async def set_pin(call: ServiceCall) -> None:
        manager = _manager(hass, call)
        slot: int = call.data[Arg.SLOT]
        code: str = call.data[Arg.PIN_CODE]
        _check_slot(manager, slot, manager.max_user_slot)
        if not rules.is_valid_pin(code, manager.capabilities):
            low, high = rules.pin_length_range(manager.capabilities)
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="invalid_pin",
                translation_placeholders={"min": str(low), "max": str(high)},
            )
        _raise_for(await manager.async_set_pin(slot, code, call.data.get(Arg.NAME), _expiry(call)))

    async def clear_pin(call: ServiceCall) -> None:
        manager = _manager(hass, call)
        slot: int = call.data[Arg.SLOT]
        # A code may sit above the capacity reported later, so allow any slot.
        _check_slot(manager, slot, MAX_SLOT)
        _raise_for(await manager.async_clear_pin(slot))

    async def set_slot_name(call: ServiceCall) -> None:
        manager = _manager(hass, call)
        slot: int = call.data[Arg.SLOT]
        # Fingerprint and tag slots sit far above the PIN capacity, so any
        # slot the lock can number may be named.
        if not 0 <= slot <= MAX_SLOT:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="slot_out_of_range",
                translation_placeholders={"slot": str(slot), "first": "0", "last": str(MAX_SLOT)},
            )
        manager.set_slot_name(slot, call.data[Arg.NAME], call.data.get(Arg.CREDENTIAL))

    hass.services.async_register(DOMAIN, NimlyService.SET_PIN, set_pin, SET_PIN_SCHEMA)
    hass.services.async_register(DOMAIN, NimlyService.CLEAR_PIN, clear_pin, CLEAR_PIN_SCHEMA)
    hass.services.async_register(
        DOMAIN, NimlyService.SET_SLOT_NAME, set_slot_name, SET_SLOT_NAME_SCHEMA
    )
