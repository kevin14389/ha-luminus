"""Dates : début de contrat et date d'effet du prochain prix - remplace
les input_datetime (has_time: false) du package YAML précédent."""

from __future__ import annotations

from datetime import date as date_

from homeassistant.components.date import DateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DATETIME_DATE_DEBUT_CONTRAT, DATETIME_PRIX_ENERGIE_DATE_EFFET
from .entity import device_info_for_entry

_DEFINITIONS = [
    (DATETIME_DATE_DEBUT_CONTRAT, "Date de début du contrat Luminus", "mdi:calendar-start"),
    (DATETIME_PRIX_ENERGIE_DATE_EFFET, "Date d'entrée en vigueur du prochain prix", "mdi:calendar-clock"),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(
        LuminusDate(entry, key, name, icon) for key, name, icon in _DEFINITIONS
    )


class LuminusDate(DateEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, key: str, name: str, icon: str) -> None:
        self._attr_unique_id = f"{entry.entry_id}_date_{key}"
        self._attr_suggested_object_id = f"luminus_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_native_value: date_ | None = None
        self._attr_device_info = device_info_for_entry(entry)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None and last_state.state not in (None, "unknown", "unavailable"):
            try:
                self._attr_native_value = date_.fromisoformat(last_state.state)
            except ValueError:
                self._attr_native_value = None

    async def async_set_value(self, value: date_) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()
