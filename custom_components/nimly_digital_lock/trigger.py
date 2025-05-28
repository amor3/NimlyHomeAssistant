import voluptuous as vol
from homeassistant.components.automation import AutomationActionType
from homeassistant.const import CONF_IEEE
import homeassistant.helpers.config_validation as cv

TRIGGER_SCHEMA = vol.Schema({
    vol.Required("platform"): "nimly_digital_lock",
    vol.Required("event"): vol.In(["locked", "unlocked"]),
    vol.Optional(CONF_IEEE): cv.string,
})

async def async_validate_trigger(hass, config):
    return config

async def async_attach_trigger(hass, config, action, automation_info):
    def _listener(event):
        data = event.data
        command = data.get("command")
        if (config["event"] == "locked" and command == 0x00) or (config["event"] == "unlocked" and command == 0x01):
            hass.async_run_job(action, {"trigger": {"event": config["event"], "ieee": data.get("device_ieee")}})
    hass.bus.async_listen("zha_event", _listener)
    return lambda: None
