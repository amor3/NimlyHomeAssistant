"""Sound volume, only when ZHA does not show it for the lock."""

from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_ID_SOUND_VOLUME, DOMAIN, FEATURE_SOUND_VOLUME, SOUND_VOLUME_OPTIONS
from .entity import NimlyEventEntity
from .manager import NimlyConfigEntry, NimlyLockManager

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NimlyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the select when ZHA's Nimly quirk does not provide it."""
    if FEATURE_SOUND_VOLUME in entry.runtime_data.fallbacks:
        async_add_entities([NimlySoundVolumeSelect(entry.runtime_data)])


class NimlySoundVolumeSelect(NimlyEventEntity, SelectEntity):
    """Sound volume (attribute 0x0024: 0 off, 1 low, 2 normal)."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_options = list(SOUND_VOLUME_OPTIONS)

    def __init__(self, manager: NimlyLockManager) -> None:
        super().__init__(manager, "sound_volume")

    @property
    def current_option(self) -> str | None:
        value = self.manager.settings.get(ATTR_ID_SOUND_VOLUME)
        if value is None or not 0 <= value < len(SOUND_VOLUME_OPTIONS):
            return None
        return SOUND_VOLUME_OPTIONS[value]

    async def async_select_option(self, option: str) -> None:
        outcome = await self.manager.async_write_setting(
            ATTR_ID_SOUND_VOLUME, SOUND_VOLUME_OPTIONS.index(option)
        )
        if not outcome.delivered:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key=outcome.error_key)
