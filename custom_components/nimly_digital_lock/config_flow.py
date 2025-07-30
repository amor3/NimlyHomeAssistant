import voluptuous as vol
import logging
from homeassistant import config_entries
from homeassistant.core import callback
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)

class NimlyDigitalLockConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Config flow for Nimly Zigbee Digital Lock integration."""
    VERSION = 1
    _user_data: dict

    def normalize_ieee(self, ieee: str):
        ieee_no_colons = ieee.replace(':', '')
        ieee_clean = ''.join(c for c in ieee_no_colons if c.lower() in '0123456789abcdef')
        ieee_no_colons = ieee_clean.lower()
        ieee_with_colons = ':'.join([ieee_clean[i:i+2] for i in range(0, len(ieee_clean), 2)]).lower()

        return {
            "original": ieee,
            "no_colons": ieee_no_colons,
            "with_colons": ieee_with_colons
        }

    async def async_step_user(self, user_input=None):
        errors = {}

        # Get list of available ZigBee devices
        zigbee_devices = await self._get_zigbee_devices()

        if user_input is not None:
            # Check if using dropdown selection
            if "device_selection" in user_input and user_input["device_selection"] != "manual" and "separator" not in user_input["device_selection"]:
                # User selected a device from dropdown
                selected_device = user_input["device_selection"]
                _LOGGER.debug(f"Selected device from dropdown: {selected_device}")

                # Parse IEEE from selection
                # Format is "name (ieee)"
                ieee = selected_device.split("(")[-1].strip(")")                
                name = selected_device.split(" (")[0].strip()

                # Use selected device info
                user_input["ieee"] = ieee
                if not user_input.get("name") or user_input["name"] == "Nimly Front Door":
                    user_input["name"] = name
            else:
                # Manual entry mode - use the ieee field directly
                ieee = user_input["ieee"]

            # Validate IEEE address length
            # Use the normalized IEEE functions from zha_mapping

            ieee_formats = self.normalize_ieee(ieee)
            ieee_clean = ieee_formats["no_colons"]

            # IEEE addresses should be exactly 16 hex characters (64 bits)
            if len(ieee_clean) != 16:
                errors["device_selection" if "device_selection" in user_input else "ieee"] = "invalid_ieee_length"
            else:
                # Get formatted IEEE with colons for consistency
                ieee_formatted = ieee_formats["with_colons"]

                self._user_data = {
                    "ieee": ieee_formatted,  # Store the formatted version
                    "ieee_no_colons": ieee_clean,
                    "ieee_with_colons": ieee_formatted,
                    "name": user_input["name"],
                }
                return self.async_create_entry(
                    title=user_input["name"],
                    data=self._user_data,
                )

        # Prepare device selection options
        device_options = {"manual": "Enter IEEE address manually"}

        # Add all found zigbee devices, prioritizing Nordic ZBT-1 devices
        nordic_devices = []
        other_devices = []

        for device_id, device_info in zigbee_devices.items():
            name = device_info.get("name", "Unknown Device")
            ieee = device_info.get("ieee")
            manufacturer = device_info.get("manufacturer", "")
            model = device_info.get("model", "")

            # Create a readable selection option
            display_name = f"{name}"
            if manufacturer:
                display_name += f" - {manufacturer}"
            if model:
                display_name += f" {model}"
            display_name += f" ({ieee})"

            # Check if this is a Nordic ZBT-1 device
            is_nordic = False
            if manufacturer and "nordic" in manufacturer.lower():
                is_nordic = True
            elif model and any(term in model.lower() for term in ["zbt-1", "zbt1", "safe4"]):
                is_nordic = True
            elif name and any(term in name.lower() for term in ["door lock", "nimly", "safe4"]):
                is_nordic = True

            # Add to appropriate list
            if is_nordic:
                nordic_devices.append((display_name, display_name))
            else:
                other_devices.append((display_name, display_name))

            device_options[display_name] = display_name

        if not user_input or errors:
            # If we have zigbee devices, show dropdown first
            if zigbee_devices:
                data_schema = vol.Schema({
                    vol.Required("device_selection", default="manual"): vol.In(device_options),
                    vol.Optional("ieee"): cv.string,
                    vol.Required("name", default="Nimly Front Door"): cv.string,
                })
            else:
                # No devices found, just show manual entry
                data_schema = vol.Schema({
                    vol.Required("ieee"): cv.string,
                    vol.Required("name", default="Nimly Front Door"): cv.string,
                })

            return self.async_show_form(
                step_id="user",
                data_schema=data_schema,
                errors=errors,
                description_placeholders={
                    "device_count": str(len(zigbee_devices))
                }
            )

    async def _get_zigbee_devices(self):
        """Get all ZigBee devices from both ZHA and Nabu Casa Zigbee integrations."""
        zigbee_devices = {}

        # Get device registry
        device_registry = dr.async_get(self.hass)

        # Check for both ZHA and Zigbee (Nabu Casa) devices
        for device_id, device in device_registry.devices.items():
            # Check if this is a ZHA device
            is_zha = any(identifier[0] == "zha" for identifier in device.identifiers)
            is_zigbee = any(identifier[0] == "zigbee" for identifier in device.identifiers)

            if is_zha or is_zigbee:
                # Extract IEEE address from identifiers
                for identifier in device.identifiers:
                    if identifier[0] in ["zha", "zigbee"]:
                        ieee = identifier[1]

                        # Add to our device list
                        zigbee_devices[device_id] = {
                            "name": device.name or "Unknown Device",
                            "ieee": ieee,
                            "manufacturer": device.manufacturer,
                            "model": device.model,
                            "integration": "zha" if is_zha else "zigbee"
                        }
                        break

        _LOGGER.debug(f"Found {len(zigbee_devices)} ZigBee devices")
        return zigbee_devices

    async def async_step_options(self, user_input=None):
        errors = {}
        if user_input is not None:
            # We don't have access to config_entry here, just use the entry title from _user_data
            return self.async_create_entry(title=self._user_data.get("name", "Nimly Front Door"), data=self._user_data, options=user_input)

        # Use default values since we don't have access to existing options here
        data_schema = vol.Schema({
            vol.Optional("auto_relock_time", default=1): vol.All(int, vol.Range(min=0)),
            vol.Optional("sound_volume", default=2): vol.All(int, vol.Range(min=0, max=2)),
        })
        return self.async_show_form(
            step_id="options",
            data_schema=data_schema,
            errors=errors,
        )

    @config_entries.HANDLERS.register(DOMAIN)
    class OptionsFlowHandler(config_entries.OptionsFlow):
        def __init__(self, config_entry):
            """Initialize options flow."""
            self.config_entry = config_entry

        async def async_step_init(self, user_input=None):
            """Manage options."""
            errors = {}
            if user_input is not None:
                return self.async_create_entry(title="", data=user_input)

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
                step_id="init",
                data_schema=data_schema,
                errors=errors,
            )

    # Properly implement options flow as a class method
    @staticmethod
    @callback
    def async_get_options_flow(config_entry):
        return NimlyDigitalLockConfigFlow.OptionsFlowHandler(config_entry)
