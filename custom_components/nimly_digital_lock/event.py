"""Event entity that fires for every lock and unlock."""

from __future__ import annotations

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import LockAction
from .entity import NimlyEventEntity
from .manager import LockActivity, NimlyConfigEntry, NimlyLockManager

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NimlyConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the activity event entity."""
    async_add_entities([NimlyActivityEvent(entry.runtime_data)])


class NimlyActivityEvent(NimlyEventEntity, EventEntity):
    """Fires lock/unlock with who and how."""

    _attr_event_types = [action.value for action in LockAction]

    def __init__(self, manager: NimlyLockManager) -> None:
        super().__init__(manager, "activity")

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.manager.add_event_listener(self._handle_activity))

    @callback
    def _handle_activity(self, activity: LockActivity) -> None:
        attributes = activity.as_dict()
        self._trigger_event(attributes.pop("action"), attributes)
        self.async_write_ha_state()
