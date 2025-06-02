import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

class NimlyDigitalLockConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Nimly Zigbee Digital Lock integration."""
    VERSION = 1
    _user_data: dict

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input:
            # Normalize IEEE address format
            ieee = user_input["ieee"]
            # Remove any non-hex characters (like colons)
            ieee_clean = ''.join(c for c in ieee if c.lower() in '0123456789abcdef')
            # Format with colons for consistency
            ieee_formatted = ':'.join([ieee_clean[i:i+2] for i in range(0, len(ieee_clean), 2)])

            self._user_data = {
                "ieee": ieee_formatted,  # Store the formatted version
                "name": user_input["name"],
            }
            return self.async_create_entry(
                title=user_input["name"],
                data=self._user_data,
            )

        data_schema = vol.Schema({
            vol.Required("ieee"): cv.string,
            vol.Required("name", default="Nimly Front Door"): cv.string,
        })
        return self.async_show_form(
            step_id="user",
            data_schema=data_schema,
            errors=errors,
        )

    async def async_step_options(self, user_input=None):
        errors = {}
        if user_input is not None:
            return self.async_create_entry(title=self.config_entry.title, data=self._user_data, options=user_input)

        data_schema = vol.Schema({
            vol.Optional("auto_relock_time", default=self.config_entry.options.get("auto_relock_time", 1)): vol.All(int, vol.Range(min=0)),
            vol.Optional("sound_volume", default=self.config_entry.options.get("sound_volume", 2)): vol.All(int, vol.Range(min=0, max=2)),
        })
        return self.async_show_form(
            step_id="options",
            data_schema=data_schema,
            errors=errors,
        )
