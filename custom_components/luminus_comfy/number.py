"""Entités number : tous les tarifs modifiables depuis l'interface Home
Assistant, sans toucher au code."""

from __future__ import annotations

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import NUMBER_DEFINITIONS
from .coordinateur import LuminusCoordinateur
from .entity import LuminusEntity


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(
        LuminusNumber(entry.runtime_data, key, name, unit, min_v, max_v, step)
        for key, name, unit, min_v, max_v, step, _defaut in NUMBER_DEFINITIONS
    )


class LuminusNumber(LuminusEntity, RestoreNumber):
    """Un tarif modifiable. La valeur par défaut (voir const.py) n'est
    utilisée qu'à la toute première création ; ensuite, la valeur
    courante est restaurée au redémarrage."""

    _attr_mode = NumberMode.BOX

    def __init__(
        self,
        coordinateur: LuminusCoordinateur,
        key: str,
        name: str,
        unit: str,
        min_value: float,
        max_value: float,
        step: float,
    ) -> None:
        super().__init__(coordinateur, "number", key, name)
        self._attr_native_unit_of_measurement = unit
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        coordinateur.entites[key] = self

    @property
    def native_value(self) -> float:
        return self._coordinateur.valeurs[self._key]

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_data = await self.async_get_last_number_data()
        if last_data is not None and last_data.native_value is not None:
            self._coordinateur.valeurs[self._key] = last_data.native_value

    async def async_set_native_value(self, value: float) -> None:
        self._coordinateur.async_definir(self._key, value)
        self._coordinateur.async_valeur_modifiee()
