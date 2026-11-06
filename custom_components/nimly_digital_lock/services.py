"""Actions for managing PIN codes and slot names."""

from __future__ import annotations

from datetime import datetime, timedelta
from functools import partial
from typing import Any

from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID
from homeassistant.core import (
    HomeAssistant,
    ServiceCall,
    ServiceResponse,
    SupportsResponse,
    callback,
)
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import config_validation as cv, device_registry as dr
from homeassistant.util import dt as dt_util

from . import rules
from .compat import vol
from .const import (
    CONF_IEEE,
    DOMAIN,
    MAX_NAME_LENGTH,
    MAX_SLOT,
    NimlyService,
    NimlyServiceArgument as Arg,
)
from .manager import MAX_USES, NimlyConfigEntry, NimlyLockManager, PinSchedule, to_utc
from .rules import CREDENTIAL_KINDS
from .zha import SendOutcome

_BASE = {
    # Either names the lock; with a single lock set up, neither is needed.
    vol.Exclusive(Arg.CONFIG_ENTRY_ID.value, "lock"): cv.string,
    vol.Exclusive(ATTR_DEVICE_ID, "lock"): cv.string,
    vol.Required(Arg.SLOT.value): vol.All(vol.Coerce(int), vol.Range(min=0)),
}

_NAME = vol.All(cv.string, vol.Length(max=MAX_NAME_LENGTH))
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

SET_PIN_SCHEMA = vol.Schema(
    {
        **_BASE,
        # Left out: a code is generated and returned as the response.
        vol.Optional(Arg.PIN_CODE.value): cv.string,
        vol.Optional(Arg.NAME.value): _NAME,
        vol.Optional(Arg.VALID_FROM.value): cv.datetime,
        vol.Exclusive(Arg.VALID_UNTIL.value, "expiry"): cv.datetime,
        vol.Exclusive(Arg.VALID_FOR.value, "expiry"): cv.positive_time_period,
        vol.Inclusive(Arg.WEEKDAYS.value, "weekly"): vol.All(
            cv.ensure_list, vol.Length(min=1), [vol.In(WEEKDAYS)]
        ),
        vol.Inclusive(Arg.START_TIME.value, "weekly"): cv.time,
        vol.Inclusive(Arg.END_TIME.value, "weekly"): cv.time,
        vol.Optional(Arg.MAX_USES.value): vol.All(vol.Coerce(int), vol.Range(min=1, max=MAX_USES)),
    }
)
CLEAR_PIN_SCHEMA = vol.Schema(_BASE)
SET_SLOT_NAME_SCHEMA = vol.Schema(
    {
        **_BASE,
        vol.Required(Arg.NAME.value): vol.Any(_NAME, ""),
        vol.Optional(Arg.CREDENTIAL.value): vol.In(CREDENTIAL_KINDS),
    }
)
CREDENTIAL_SCHEMA = vol.Schema(
    {**_BASE, vol.Required(Arg.CREDENTIAL.value): vol.In(("rfid", "fingerprint"))}
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
    period: timedelta | None = call.data.get(Arg.VALID_FOR)
    if period is not None:
        return dt_util.utcnow() + period
    if (until := call.data.get(Arg.VALID_UNTIL)) is None:
        return None
    if (until := to_utc(until)) <= dt_util.utcnow():
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="expiry_in_past")
    return until


def _when(value: datetime | None) -> datetime | None:
    return to_utc(value) if value is not None else None


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


async def _async_set_pin(hass: HomeAssistant, call: ServiceCall) -> ServiceResponse:
    """Write a code now, later or weekly; a left-out code is generated."""
    manager = _manager(hass, call)
    slot: int = call.data[Arg.SLOT]
    _check_slot(manager, slot, manager.max_user_slot)
    generated = Arg.PIN_CODE not in call.data
    if generated and not call.return_response:
        # A generated code is only ever shown in the response.
        raise ServiceValidationError(
            translation_domain=DOMAIN, translation_key="generate_needs_response"
        )
    code: str = rules.generate_pin(manager.capabilities) if generated else call.data[Arg.PIN_CODE]
    if not rules.is_valid_pin(code, manager.capabilities):
        low, high = rules.pin_length_range(manager.capabilities)
        raise ServiceValidationError(
            translation_domain=DOMAIN,
            translation_key="invalid_pin",
            translation_placeholders={"min": str(low), "max": str(high)},
        )
    name: str | None = call.data.get(Arg.NAME)
    expires = _expiry(call)
    start = _when(call.data.get(Arg.VALID_FROM))
    if start is not None and expires is not None and expires <= start:
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="end_before_start")
    days = frozenset(WEEKDAYS.index(day) for day in call.data.get(Arg.WEEKDAYS, ()))
    uses: int | None = call.data.get(Arg.MAX_USES)
    if uses is not None and days:
        # A weekly code is written again for every window.
        raise ServiceValidationError(translation_domain=DOMAIN, translation_key="uses_with_weekly")
    scheduled = bool(days) or (start is not None and start > dt_util.utcnow())
    if scheduled:
        if days and call.data[Arg.START_TIME] == call.data[Arg.END_TIME]:
            raise ServiceValidationError(translation_domain=DOMAIN, translation_key="empty_window")
        schedule = PinSchedule(
            code=code,
            name=name,
            start=start,
            until=expires,
            days=days,
            time_from=call.data.get(Arg.START_TIME),
            time_to=call.data.get(Arg.END_TIME),
            uses=uses,
        )
        outcome = await manager.async_schedule_pin(slot, schedule)
        if outcome is not None:
            _raise_for(outcome)
    else:
        _raise_for(await manager.async_set_pin(slot, code, name, expires, uses))
    if not call.return_response:
        return None
    response: dict[str, Any] = {"slot": slot, "scheduled": scheduled}
    if generated:
        response["pin_code"] = code
    return response


@callback
def async_setup_services(hass: HomeAssistant) -> None:
    """Register the integration's actions."""

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

    async def enroll_credential(call: ServiceCall) -> None:
        manager = _manager(hass, call)
        slot: int = call.data[Arg.SLOT]
        kind: str = call.data[Arg.CREDENTIAL]
        _check_slot(manager, slot, manager.credential_slot_range(kind)[1])
        _raise_for(await manager.async_enroll(slot, kind))

    async def remove_credential(call: ServiceCall) -> None:
        manager = _manager(hass, call)
        slot: int = call.data[Arg.SLOT]
        kind: str = call.data[Arg.CREDENTIAL]
        _check_slot(manager, slot, manager.credential_slot_range(kind)[1])
        _raise_for(await manager.async_remove_credential(slot, kind))

    hass.services.async_register(
        DOMAIN,
        NimlyService.SET_PIN,
        partial(_async_set_pin, hass),
        SET_PIN_SCHEMA,
        supports_response=SupportsResponse.OPTIONAL,
    )
    hass.services.async_register(
        DOMAIN, NimlyService.ENROLL_CREDENTIAL, enroll_credential, CREDENTIAL_SCHEMA
    )
    hass.services.async_register(
        DOMAIN, NimlyService.REMOVE_CREDENTIAL, remove_credential, CREDENTIAL_SCHEMA
    )
    hass.services.async_register(DOMAIN, NimlyService.CLEAR_PIN, clear_pin, CLEAR_PIN_SCHEMA)
    hass.services.async_register(
        DOMAIN, NimlyService.SET_SLOT_NAME, set_slot_name, SET_SLOT_NAME_SCHEMA
    )
