import voluptuous as vol
from homeassistant import config_entries
from homeassistant.helpers import config_validation as cv

from .const import DOMAIN

class NimlyZigbeeLockConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    VERSION = 1

    def __init__(self):
        self._data = {}

    async def async_step_user(self, user_input=None):
        errors = {}
        if user_input is not None:
            self._data = {
                "ieee": user_input["ieee"].lower(),
                "name": user_input["name"],
            }
            return self.async_create_entry(title=user_input["name"], data=self._data)

        data_schema = vol.Schema({
            vol.Required("ieee"): cv.string,
            vol.Required("name", default="Front Door Lock"): cv.string,
        })
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )

    async def async_step_options(self, user_input=None):
        if user_input is not None:
            return self.async_create_entry(
                title=self.config_entry.title,
                data=self._data,
                options=user_input,
            )

        data_schema = vol.Schema({
            vol.Optional(
                "auto_relock_time",
                default=self.config_entry.options.get("auto_relock_time", 1)
            ): vol.All(int, vol.Range(min=0)),
            vol.Optional(
                "sound_volume",
                default=self.config_entry.options.get("sound_volume", 2)
            ): vol.All(int, vol.Range(min=0, max=2)),
        })
        return self.async_show_form(
            step_id="options", data_schema=data_schema, errors={}
        )
