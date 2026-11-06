"""Auto relock switch, only when ZHA does not show one for the lock."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import ATTR_ID_AUTO_RELOCK, DOMAIN, FEATURE_AUTO_RELOCK
from .entity import NimlyEventEntity
from .manager import NimlyConfigEntry, NimlyLockManager

PARALLEL_UPDATES = 1


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NimlyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add the switch when ZHA's Nimly quirk does not provide it."""
    if FEATURE_AUTO_RELOCK in entry.runtime_data.fallbacks:
        async_add_entities([NimlyAutoRelockSwitch(entry.runtime_data)])


class NimlyAutoRelockSwitch(NimlyEventEntity, SwitchEntity):
    """Auto relock (attribute 0x0023: 0 off, 1 or more on)."""

    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, manager: NimlyLockManager) -> None:
        super().__init__(manager, "auto_relock")

    @property
    def is_on(self) -> bool | None:
        if (value := self.manager.settings.get(ATTR_ID_AUTO_RELOCK)) is None:
            return None
        return value >= 1

    async def async_turn_on(self, **kwargs: Any) -> None:
        await self._write(1)

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._write(0)

    async def _write(self, value: int) -> None:
        outcome = await self.manager.async_write_setting(ATTR_ID_AUTO_RELOCK, value)
        if not outcome.delivered:
            raise HomeAssistantError(translation_domain=DOMAIN, translation_key=outcome.error_key)
