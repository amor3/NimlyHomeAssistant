import voluptuous as vol
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from .const import DOMAIN

class NimlyDigitalLockConfigFlow(config_entries.ConfigFlow, domain="nimly_digital_lock"):
    VERSION = 1

    async def async_step_user(self, user_input=None):
        if user_input is None:
            return self.async_show_form(
                step_id="user",
                data_schema=vol.Schema({
                    vol.Required("ieee"): cv.string,
                    vol.Required("name", default="Nimly - Door"): cv.string,
                }),
            )
        self._data = user_input
        return self.async_create_entry(title=user_input["name"], data=user_input)

    async def async_step_options(self, user_input=None):
        if user_input is None:
            return self.async_show_form(
                step_id="options",
                data_schema=vol.Schema({
                    vol.Optional("auto_relock_time", default=self.options.get("auto_relock_time", 1)): vol.All(int, vol.Range(min=0)),
                    vol.Optional("sound_volume", default=self.options.get("sound_volume", 2)): vol.All(int, vol.Range(min=0, max=2)),
                }),
            )
        return self.async_create_entry(title=self.entry.title, data=self._data, options=user_input)
