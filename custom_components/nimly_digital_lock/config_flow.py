"""Config and options flow for Nimly Digital Lock."""

from __future__ import annotations

from datetime import datetime
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
    MAX_SLOT,
    RESERVED_SLOTS_MAX,
    RESERVED_SLOTS_MIN,
)
from .manager import NimlyConfigEntry, NimlyLockManager, to_utc
from .rules import CREDENTIAL_KINDS
from .zha import is_zha_running, iter_nimly_locks

CONF_SLOT = "slot"
CONF_NAME = "name"
CONF_PIN_CODE = "pin_code"
CONF_VALID_UNTIL = "valid_until"
CONF_CREDENTIAL = "credential"
CREDENTIAL_ANY = "any"


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
            step_id="init", menu_options=["set_pin", "clear_pin", "name_slot", "settings"]
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

    async def async_step_set_pin(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        manager = self._manager
        errors: dict[str, str] = {}
        low, high = rules.pin_length_range(manager.capabilities)
        if user_input is not None:
            slot = int(user_input[CONF_SLOT])
            code = str(user_input[CONF_PIN_CODE])
            if not manager.first_user_slot <= slot <= manager.max_user_slot:
                errors[CONF_SLOT] = "slot_out_of_range"
            elif not rules.is_valid_pin(code, manager.capabilities):
                errors[CONF_PIN_CODE] = "invalid_pin"
            elif (expires := _parse_local(user_input.get(CONF_VALID_UNTIL))) is not None and (
                expires <= dt_util.utcnow()
            ):
                errors[CONF_VALID_UNTIL] = "expiry_in_past"
            else:
                # A blank name keeps the one the slot already has.
                name = str(user_input.get(CONF_NAME, "")).strip() or None
                outcome = await manager.async_set_pin(slot, code, name, expires)
                if outcome.delivered:
                    return self._done()
                errors["base"] = outcome.error_key or "lock_unreachable"
        return self.async_show_form(
            step_id="set_pin",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SLOT, default=manager.first_user_slot): _slot_selector(
                        manager.first_user_slot, manager.max_user_slot
                    ),
                    vol.Optional(CONF_NAME, default=""): TextSelector(),
                    vol.Required(CONF_PIN_CODE): TextSelector(
                        TextSelectorConfig(type=TextSelectorType.PASSWORD)
                    ),
                    vol.Optional(CONF_VALID_UNTIL): DateTimeSelector(),
                }
            ),
            errors=errors,
            description_placeholders={
                "first": str(manager.first_user_slot),
                "min": str(low),
                "max": str(high),
            },
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
        if user_input is not None:
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
        )
