"""Config and options flow for Nimly Digital Lock."""

from __future__ import annotations

from datetime import datetime, time as dt_time
from typing import Any

from homeassistant.config_entries import (
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
    DateTimeSelector,
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
    SelectOptionDict,
    SelectSelector,
    SelectSelectorConfig,
    SelectSelectorMode,
    TextSelector,
    TextSelectorConfig,
    TextSelectorType,
    TimeSelector,
)
from homeassistant.util import dt as dt_util

from . import rules
from .compat import vol
from .const import (
    CONF_IEEE,
    CONF_MODEL,
    CONF_RESERVED_SLOTS,
    CONF_WAKE_WITH_LOCK,
    DEFAULT_RESERVED_SLOTS,
    DOMAIN,
    MAX_NAME_LENGTH,
    MAX_SLOT,
    RESERVED_SLOTS_MAX,
    RESERVED_SLOTS_MIN,
)
from .manager import MAX_USES, NimlyConfigEntry, NimlyLockManager, PinSchedule, to_utc
from .rules import CREDENTIAL_KINDS
from .zha import SendOutcome, is_zha_running, iter_nimly_locks

CONF_SLOT = "slot"
CONF_NAME = "name"
CONF_PIN_CODE = "pin_code"
CONF_VALID_UNTIL = "valid_until"
CONF_CREDENTIAL = "credential"
CONF_VALID_FROM = "valid_from"
CONF_WEEKDAYS = "weekdays"
CONF_START_TIME = "start_time"
CONF_END_TIME = "end_time"
CONF_MAX_USES = "max_uses"
CREDENTIAL_ANY = "any"
WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _parse_local(value: object) -> datetime | None:
    """A date-time selector value (local, naive) as an aware UTC datetime."""
    if not value or (parsed := dt_util.parse_datetime(str(value))) is None:
        return None
    return to_utc(parsed)


def _title(ieee: str, model: str) -> str:
    tail = ieee.replace(":", "")[-4:].upper()
    return f"{model or 'Nimly'} ({tail})"


class NimlyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Pick a Nimly lock that ZHA has already paired."""

    VERSION = 2

    _discovered: dict[str, str]

    def _unconfigured_locks(self, keep: str | None = None) -> dict[str, str]:
        """Nimly locks in ZHA without an entry (plus keep), as ieee -> model."""
        configured = {
            entry.unique_id for entry in self._async_current_entries(include_ignore=False)
        }
        return {
            ieee: model
            for ieee, model in iter_nimly_locks(self.hass)
            if ieee not in configured or ieee == keep
        }

    @staticmethod
    def _lock_schema(locks: dict[str, str], default: str | None = None) -> vol.Schema:
        options = [
            SelectOptionDict(value=ieee, label=f"{model or 'Nimly'} ({ieee})")
            for ieee, model in sorted(locks.items())
        ]
        return vol.Schema(
            {
                vol.Required(CONF_IEEE, default=default or vol.UNDEFINED): SelectSelector(
                    SelectSelectorConfig(options=options, mode=SelectSelectorMode.LIST)
                )
            }
        )

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if not is_zha_running(self.hass):
            return self.async_abort(reason="zha_not_running")
        locks = self._unconfigured_locks()

        if user_input is not None:
            ieee = user_input[CONF_IEEE]
            await self.async_set_unique_id(ieee)
            self._abort_if_unique_id_configured()
            model = locks.get(ieee, "")
            return self.async_create_entry(
                title=_title(ieee, model), data={CONF_IEEE: ieee, CONF_MODEL: model}
            )

        if not locks:
            return self.async_abort(reason="no_locks")
        return self.async_show_form(step_id="user", data_schema=self._lock_schema(locks))

    async def async_step_integration_discovery(
        self, discovery_info: dict[str, Any]
    ) -> ConfigFlowResult:
        """A Nimly lock ZHA paired after the first one was set up."""
        ieee = str(discovery_info[CONF_IEEE]).lower()
        await self.async_set_unique_id(ieee)
        self._abort_if_unique_id_configured()
        self._discovered = {CONF_IEEE: ieee, CONF_MODEL: str(discovery_info.get(CONF_MODEL, ""))}
        self.context["title_placeholders"] = {"name": _title(ieee, self._discovered[CONF_MODEL])}
        return await self.async_step_discovery_confirm()

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        ieee, model = self._discovered[CONF_IEEE], self._discovered[CONF_MODEL]
        if user_input is not None:
            # Another entry may have taken the address meanwhile (Reconfigure).
            self._abort_if_unique_id_configured()
            return self.async_create_entry(title=_title(ieee, model), data=self._discovered)
        self._set_confirm_only()
        return self.async_show_form(
            step_id="discovery_confirm",
            description_placeholders={"name": _title(ieee, model), "ieee": ieee},
        )

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Point the entry at another Zigbee module, e.g. after replacing it.

        Names, PIN state and entities stay, since they are keyed on the entry.
        """
        entry = self._get_reconfigure_entry()
        current = entry.data[CONF_IEEE]
        if not is_zha_running(self.hass):
            return self.async_abort(reason="zha_not_running")
        locks = self._unconfigured_locks(keep=current)

        if user_input is not None:
            ieee = user_input[CONF_IEEE]
            if ieee != current:
                # A pending discovery card for the new module must not block
                # this; it aborts itself once the address is taken.
                await self.async_set_unique_id(ieee, raise_on_progress=False)
                self._abort_if_unique_id_configured()
            model = locks.get(ieee, "")
            return self.async_update_reload_and_abort(
                entry,
                unique_id=ieee,
                title=_title(ieee, model),
                data={CONF_IEEE: ieee, CONF_MODEL: model},
                # Picking the module already in use changes nothing.
                reload_even_if_entry_is_unchanged=False,
            )

        if not locks:
            return self.async_abort(reason="no_locks")
        default = current if current in locks else None
        return self.async_show_form(
            step_id="reconfigure", data_schema=self._lock_schema(locks, default)
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: NimlyConfigEntry) -> NimlyOptionsFlow:
        return NimlyOptionsFlow()


def _slot_selector(low: int, high: int) -> NumberSelector:
    return NumberSelector(
        NumberSelectorConfig(min=low, max=high, step=1, mode=NumberSelectorMode.BOX)
    )


class NimlyOptionsFlow(OptionsFlowWithReload):
    """Settings and PIN management.

    PIN codes entered here go straight to the lock and are not recorded,
    unlike action calls, which the recorder stores with their data.
    """

    # A code generated in this dialog, and a credential being enrolled,
    # carried to the step that shows them.
    _generated: tuple[int, str]
    _enrolling: tuple[int, str]

    @property
    def _manager(self) -> NimlyLockManager:
        manager: NimlyLockManager = self.config_entry.runtime_data
        return manager

    def _done(self) -> ConfigFlowResult:
        return self.async_create_entry(data=dict(self.config_entry.options))

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if self.config_entry.state is not ConfigEntryState.LOADED:
            # PIN management needs the running lock; settings do not.
            return await self.async_step_settings()
        return self.async_show_menu(
            step_id="init",
            menu_options=[
                "set_pin",
                "schedule_pin",
                "clear_pin",
                "name_slot",
                "enroll_credential",
                "remove_credential",
                "settings",
            ],
        )

    async def async_step_settings(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(
                data={
                    **self.config_entry.options,
                    CONF_RESERVED_SLOTS: int(user_input[CONF_RESERVED_SLOTS]),
                    CONF_WAKE_WITH_LOCK: user_input[CONF_WAKE_WITH_LOCK],
                }
            )
        options = self.config_entry.options
        return self.async_show_form(
            step_id="settings",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_RESERVED_SLOTS,
                        default=options.get(CONF_RESERVED_SLOTS, DEFAULT_RESERVED_SLOTS),
                    ): _slot_selector(RESERVED_SLOTS_MIN, RESERVED_SLOTS_MAX),
                    vol.Required(
                        CONF_WAKE_WITH_LOCK, default=options.get(CONF_WAKE_WITH_LOCK, False)
                    ): BooleanSelector(),
                }
            ),
        )

    def _pin_fields(self, manager: NimlyLockManager) -> dict[Any, Any]:
        return {
            vol.Required(CONF_SLOT, default=manager.first_user_slot): _slot_selector(
                manager.first_user_slot, manager.max_user_slot
            ),
            vol.Optional(CONF_NAME, default=""): TextSelector(),
            # Left empty: a code is generated and shown once.
            vol.Optional(CONF_PIN_CODE, default=""): TextSelector(
                TextSelectorConfig(type=TextSelectorType.PASSWORD)
            ),
        }

    def _check_pin_input(
        self, manager: NimlyLockManager, user_input: dict[str, Any], errors: dict[str, str]
    ) -> tuple[int, str, str | None, bool]:
        """Slot, code (generated if blank), name and whether it was generated."""
        slot = int(user_input[CONF_SLOT])
        code = str(user_input.get(CONF_PIN_CODE) or "")
        generated = not code
        if generated:
            code = rules.generate_pin(manager.capabilities)
        name = str(user_input.get(CONF_NAME, "")).strip() or None
        if not manager.first_user_slot <= slot <= manager.max_user_slot:
            errors[CONF_SLOT] = "slot_out_of_range"
        elif not rules.is_valid_pin(code, manager.capabilities):
            errors[CONF_PIN_CODE] = "invalid_pin"
        elif name is not None and len(name) > MAX_NAME_LENGTH:
            errors[CONF_NAME] = "name_too_long"
        return slot, code, name, generated

    async def async_step_set_pin(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        manager = self._manager
        errors: dict[str, str] = {}
        low, high = rules.pin_length_range(manager.capabilities)
        if user_input is not None:
            slot, code, name, generated = self._check_pin_input(manager, user_input, errors)
            start = _parse_local(user_input.get(CONF_VALID_FROM))
            expires = _parse_local(user_input.get(CONF_VALID_UNTIL))
            # Left empty: no limit.
            uses = int(user_input[CONF_MAX_USES]) if user_input.get(CONF_MAX_USES) else None
            if not errors and expires is not None and expires <= dt_util.utcnow():
                errors[CONF_VALID_UNTIL] = "expiry_in_past"
            elif not errors and start and expires and expires <= start:
                errors[CONF_VALID_UNTIL] = "end_before_start"
            if not errors:
                outcome: SendOutcome | None
                if start is not None and start > dt_util.utcnow():
                    outcome = await manager.async_schedule_pin(
                        slot,
                        PinSchedule(code=code, name=name, start=start, until=expires, uses=uses),
                    )
                else:
                    outcome = await manager.async_set_pin(slot, code, name, expires, uses)
                if outcome is None or outcome.delivered:
                    return await self._finish_pin(slot, code if generated else None)
                errors["base"] = outcome.error_key or "lock_unreachable"
        return self.async_show_form(
            step_id="set_pin",
            data_schema=vol.Schema(
                {
                    **self._pin_fields(manager),
                    vol.Optional(CONF_VALID_FROM): DateTimeSelector(),
                    vol.Optional(CONF_VALID_UNTIL): DateTimeSelector(),
                    vol.Optional(CONF_MAX_USES): _slot_selector(1, MAX_USES),
                }
            ),
            errors=errors,
            description_placeholders={
                "first": str(manager.first_user_slot),
                "min": str(low),
                "max": str(high),
            },
        )

    async def async_step_schedule_pin(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """A code that works on chosen weekdays between two times."""
        manager = self._manager
        errors: dict[str, str] = {}
        if user_input is not None:
            slot, code, name, generated = self._check_pin_input(manager, user_input, errors)
            starts = dt_time.fromisoformat(user_input[CONF_START_TIME])
            ends = dt_time.fromisoformat(user_input[CONF_END_TIME])
            until = _parse_local(user_input.get(CONF_VALID_UNTIL))
            if not errors and starts == ends:
                errors[CONF_END_TIME] = "empty_window"
            elif not errors and until is not None and until <= dt_util.utcnow():
                errors[CONF_VALID_UNTIL] = "expiry_in_past"
            if not errors:
                schedule = PinSchedule(
                    code=code,
                    name=name,
                    start=_parse_local(user_input.get(CONF_VALID_FROM)),
                    until=until,
                    days=frozenset(WEEKDAYS.index(day) for day in user_input[CONF_WEEKDAYS]),
                    time_from=starts,
                    time_to=ends,
                )
                outcome = await manager.async_schedule_pin(slot, schedule)
                if outcome is None or outcome.delivered:
                    return await self._finish_pin(slot, code if generated else None)
                errors["base"] = outcome.error_key or "lock_unreachable"
        return self.async_show_form(
            step_id="schedule_pin",
            data_schema=vol.Schema(
                {
                    **self._pin_fields(manager),
                    vol.Required(CONF_WEEKDAYS): SelectSelector(
                        SelectSelectorConfig(
                            options=list(WEEKDAYS), multiple=True, translation_key="weekday"
                        )
                    ),
                    vol.Required(CONF_START_TIME, default="08:00:00"): TimeSelector(),
                    vol.Required(CONF_END_TIME, default="16:00:00"): TimeSelector(),
                    vol.Optional(CONF_VALID_FROM): DateTimeSelector(),
                    vol.Optional(CONF_VALID_UNTIL): DateTimeSelector(),
                }
            ),
            errors=errors,
        )

    async def _finish_pin(self, slot: int, generated: str | None) -> ConfigFlowResult:
        if generated is None:
            return self._done()
        self._generated = (slot, generated)
        return await self.async_step_pin_generated()

    async def async_step_pin_generated(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Show a generated code once; it is not kept anywhere for display."""
        if user_input is not None:
            return self._done()
        slot, code = self._generated
        return self.async_show_form(
            step_id="pin_generated",
            data_schema=vol.Schema({}),
            description_placeholders={"slot": str(slot), "pin": code},
        )

    def _credential_schema(self, manager: NimlyLockManager) -> vol.Schema:
        return vol.Schema(
            {
                vol.Required(CONF_CREDENTIAL, default="rfid"): SelectSelector(
                    SelectSelectorConfig(
                        options=["rfid", "fingerprint"], translation_key="physical_credential"
                    )
                ),
                vol.Required(CONF_SLOT, default=manager.first_user_slot): _slot_selector(
                    manager.first_user_slot, MAX_SLOT
                ),
            }
        )

    async def async_step_enroll_credential(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Start enrolment of a key tag or finger; then present it at the lock."""
        manager = self._manager
        errors: dict[str, str] = {}
        if user_input is not None:
            kind = user_input[CONF_CREDENTIAL]
            slot = int(user_input[CONF_SLOT])
            low, high = manager.credential_slot_range(kind)
            if not low <= slot <= high:
                errors[CONF_SLOT] = "slot_out_of_range"
            else:
                outcome = await manager.async_enroll(slot, kind)
                if outcome.delivered:
                    self._enrolling = (slot, kind)
                    return await self.async_step_enroll_started()
                errors["base"] = outcome.error_key or "lock_unreachable"
        return self.async_show_form(
            step_id="enroll_credential",
            data_schema=self._credential_schema(manager),
            errors=errors,
        )

    async def async_step_enroll_started(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self._done()
        slot, kind = self._enrolling
        return self.async_show_form(
            step_id="enroll_started",
            data_schema=vol.Schema({}),
            description_placeholders={"slot": str(slot), "kind": kind},
        )

    async def async_step_remove_credential(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        manager = self._manager
        errors: dict[str, str] = {}
        if user_input is not None:
            kind = user_input[CONF_CREDENTIAL]
            slot = int(user_input[CONF_SLOT])
            low, high = manager.credential_slot_range(kind)
            if not low <= slot <= high:
                errors[CONF_SLOT] = "slot_out_of_range"
            else:
                outcome = await manager.async_remove_credential(slot, kind)
                if outcome.delivered:
                    return self._done()
                errors["base"] = outcome.error_key or "lock_unreachable"
        return self.async_show_form(
            step_id="remove_credential",
            data_schema=self._credential_schema(manager),
            errors=errors,
        )

    async def async_step_clear_pin(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        manager = self._manager
        with_pin = {
            number: slot
            for number, slot in manager.slots.items()
            if slot["has_pin"] and number >= manager.first_user_slot
        }
        if not with_pin:
            return self.async_abort(reason="no_pin_codes")
        errors: dict[str, str] = {}
        if user_input is not None:
            outcome = await manager.async_clear_pin(int(user_input[CONF_SLOT]))
            if outcome.delivered:
                return self._done()
            errors["base"] = outcome.error_key or "lock_unreachable"
        options = [
            SelectOptionDict(
                value=str(number),
                label=f"{number}: {slot['name']}" if slot["name"] else str(number),
            )
            for number, slot in with_pin.items()
        ]
        return self.async_show_form(
            step_id="clear_pin",
            data_schema=vol.Schema(
                {vol.Required(CONF_SLOT): SelectSelector(SelectSelectorConfig(options=options))}
            ),
            errors=errors,
        )

    async def async_step_name_slot(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        manager = self._manager
        errors: dict[str, str] = {}
        if (
            user_input is not None
            and len(str(user_input.get(CONF_NAME, "")).strip()) > MAX_NAME_LENGTH
        ):
            errors[CONF_NAME] = "name_too_long"
        elif user_input is not None:
            credential = user_input.get(CONF_CREDENTIAL, CREDENTIAL_ANY)
            manager.set_slot_name(
                int(user_input[CONF_SLOT]),
                user_input.get(CONF_NAME, ""),
                None if credential == CREDENTIAL_ANY else credential,
            )
            return self._done()
        return self.async_show_form(
            step_id="name_slot",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SLOT): _slot_selector(0, MAX_SLOT),
                    vol.Optional(CONF_NAME, default=""): TextSelector(),
                    vol.Optional(CONF_CREDENTIAL, default=CREDENTIAL_ANY): SelectSelector(
                        SelectSelectorConfig(
                            options=[CREDENTIAL_ANY, *CREDENTIAL_KINDS],
                            translation_key="credential",
                        )
                    ),
                }
            ),
            errors=errors,
        )
