"""Interrupteurs : remise fidélité et changement de prix programmé."""

from __future__ import annotations

from typing import Any

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import SWITCH_CHANGEMENT_PRIX_PROGRAMME, SWITCH_REMISE_FIDELITE_ACTIVE
from .coordinateur import LuminusCoordinateur
from .entity import LuminusEntity

_DEFINITIONS = [
    (SWITCH_REMISE_FIDELITE_ACTIVE, "Remise fidélité domiciliation active", "mdi:cash-check"),
    (SWITCH_CHANGEMENT_PRIX_PROGRAMME, "Changement de prix programmé actif", "mdi:calendar-clock"),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(
        LuminusSwitch(entry.runtime_data, key, name, icon) for key, name, icon in _DEFINITIONS
    )


class LuminusSwitch(LuminusEntity, SwitchEntity, RestoreEntity):
    def __init__(self, coordinateur: LuminusCoordinateur, key: str, name: str, icon: str) -> None:
        super().__init__(coordinateur, "switch", key, name)
        self._attr_icon = icon
        coordinateur.entites[key] = self

    @property
    def is_on(self) -> bool:
        return self._coordinateur.valeurs[self._key]

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._coordinateur.valeurs[self._key] = last_state.state == "on"

    async def async_turn_on(self, **kwargs: Any) -> None:
        self._coordinateur.async_definir(self._key, True)
        self._coordinateur.async_valeur_modifiee()

    async def async_turn_off(self, **kwargs: Any) -> None:
        self._coordinateur.async_definir(self._key, False)
        self._coordinateur.async_valeur_modifiee()
