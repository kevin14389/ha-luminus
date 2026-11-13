"""Dates : début de contrat et date d'effet du prochain prix."""

from __future__ import annotations

from datetime import date as date_

from homeassistant.components.date import DateEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import DATETIME_DATE_DEBUT_CONTRAT, DATETIME_PRIX_ENERGIE_DATE_EFFET
from .coordinateur import LuminusCoordinateur
from .entity import LuminusEntity

_DEFINITIONS = [
    (DATETIME_DATE_DEBUT_CONTRAT, "Date de début du contrat Luminus", "mdi:calendar-start"),
    (DATETIME_PRIX_ENERGIE_DATE_EFFET, "Date d'entrée en vigueur du prochain prix", "mdi:calendar-clock"),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(
        LuminusDate(entry.runtime_data, key, name, icon) for key, name, icon in _DEFINITIONS
    )


class LuminusDate(LuminusEntity, DateEntity, RestoreEntity):
    def __init__(self, coordinateur: LuminusCoordinateur, key: str, name: str, icon: str) -> None:
        super().__init__(coordinateur, "date", key, name)
        self._attr_icon = icon
        coordinateur.entites[key] = self

    @property
    def native_value(self) -> date_ | None:
        return self._coordinateur.valeurs[self._key]

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is None:
            return
        try:
            self._coordinateur.valeurs[self._key] = date_.fromisoformat(last_state.state)
        except ValueError:
            # "unknown" : aucune date n'avait encore été saisie.
            pass

    async def async_set_value(self, value: date_) -> None:
        self._coordinateur.async_definir(self._key, value)
        self._coordinateur.async_valeur_modifiee()
