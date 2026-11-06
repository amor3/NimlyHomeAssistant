"""Config and options flow for Nimly Digital Lock."""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlowWithReload,
)
from homeassistant.core import callback
from homeassistant.helpers.selector import (
    BooleanSelector,
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

from . import rules
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
from .manager import NimlyConfigEntry, NimlyLockManager
from .zha import is_zha_running, iter_nimly_locks

CONF_SLOT = "slot"
CONF_NAME = "name"
CONF_PIN_CODE = "pin_code"


def _title(ieee: str, model: str) -> str:
    tail = ieee.replace(":", "")[-4:].upper()
    return f"{model or 'Nimly'} ({tail})"


class NimlyConfigFlow(ConfigFlow, domain=DOMAIN):
    """Pick a Nimly lock that ZHA has already paired."""

    VERSION = 2

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if not is_zha_running(self.hass):
            return self.async_abort(reason="zha_not_running")

        configured = {entry.unique_id for entry in self._async_current_entries()}
        locks = {
            ieee: model for ieee, model in iter_nimly_locks(self.hass) if ieee not in configured
        }

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

        options = [
            SelectOptionDict(value=ieee, label=f"{model or 'Nimly'} ({ieee})")
            for ieee, model in sorted(locks.items())
        ]
        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_IEEE): SelectSelector(
                        SelectSelectorConfig(options=options, mode=SelectSelectorMode.LIST)
                    )
                }
            ),
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
        return self.config_entry.runtime_data

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
            else:
                # A blank name keeps the one the slot already has.
                name = str(user_input.get(CONF_NAME, "")).strip() or None
                outcome = await manager.async_set_pin(slot, code, name)
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
            manager.set_slot_name(int(user_input[CONF_SLOT]), user_input.get(CONF_NAME, ""))
            return self._done()
        return self.async_show_form(
            step_id="name_slot",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_SLOT): _slot_selector(0, MAX_SLOT),
                    vol.Optional(CONF_NAME, default=""): TextSelector(),
                }
            ),
        )
