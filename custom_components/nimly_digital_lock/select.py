from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.config_entries import ConfigEntry

from .configuration.sound_volume_select import SoundVolumeSelect, _LOGGER


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:

    _LOGGER.info(f"[AM] Setting up select platform for entry: {entry.entry_id}")

    ieee = entry.data["ieee"]
    name = entry.data.get("name", "Nimly Front Door")
    #ieee_key = ieee.lower().replace(":", "")
    sound_volume_select = SoundVolumeSelect(hass, ieee, name)

    async_add_entities([sound_volume_select], True)
