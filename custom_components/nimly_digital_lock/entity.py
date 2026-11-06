"""Base entity for the Nimly Digital Lock integration."""

from __future__ import annotations

from homeassistant.core import callback
from homeassistant.helpers.device_registry import DeviceEntry, DeviceInfo
from homeassistant.helpers.entity import Entity

from .const import CONF_MODEL, DOMAIN, MANUFACTURER, ZHA_DOMAIN
from .manager import NimlyLockManager
from .zha import find_zha_device

# Newer Home Assistant links devices by registry id; older only by identifier.
_HAS_VIA_DEVICE_ID = "via_device_id" in DeviceInfo.__annotations__


def build_device_info(manager: NimlyLockManager) -> DeviceInfo:
    """A device of our own, linked to ZHA's device for the same lock.

    It is not merged into ZHA's device: ZHA deletes its device when the
    lock leaves the network, and our entities and their history would go
    with it.
    """
    ieee = manager.ieee
    model = manager.entry.data.get(CONF_MODEL) or None
    zha_device = find_zha_device(manager.hass, ieee)
    base_name = (zha_device.name_by_user or zha_device.name) if zha_device else None
    info = DeviceInfo(
        # Keyed on the entry, so a replaced Zigbee module (new address)
        # keeps the same device and entities after Reconfigure.
        identifiers={(DOMAIN, manager.entry.entry_id)},
        name=f"{base_name or model or 'Nimly'} activity",
        manufacturer=MANUFACTURER,
        model=model,
        serial_number=ieee,
    )
    if zha_device is not None:
        if _HAS_VIA_DEVICE_ID:
            info["via_device_id"] = zha_device.id
        elif (via := _zha_identifier(zha_device)) is not None:
            # Older Home Assistant links by identifier: use the one ZHA's
            # device really has, or the link points at nothing.
            info["via_device"] = via  # type: ignore[typeddict-unknown-key]
    return info


def _zha_identifier(device: DeviceEntry) -> tuple[str, str] | None:
    return next((ident for ident in device.identifiers if ident[0] == ZHA_DOMAIN), None)


class NimlyEntity(Entity):
    """An entity on the Nimly device of one lock."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, manager: NimlyLockManager, key: str) -> None:
        self.manager = manager
        self._attr_unique_id = f"{manager.entry.entry_id}-{key}"
        self._attr_translation_key = key
        self._attr_device_info = build_device_info(manager)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(self.manager.add_listener(self._handle_manager_update))

    @callback
    def _handle_manager_update(self) -> None:
        self.async_write_ha_state()


class NimlyEventEntity(NimlyEntity):
    """An entity whose value comes from lock events through ZHA."""

    @property
    def available(self) -> bool:
        return super().available and self.manager.listening
