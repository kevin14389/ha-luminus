"""Entités number : tous les tarifs modifiables depuis l'interface Home
Assistant, sans toucher au code - remplace les input_number du package
YAML précédent."""

from __future__ import annotations

from homeassistant.components.number import NumberMode, RestoreNumber
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import NUMBER_DEFINITIONS
from .entity import device_info_for_entry


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(
        LuminusNumber(entry, key, name, unit, min_v, max_v, step, default)
        for key, name, unit, min_v, max_v, step, default in NUMBER_DEFINITIONS
    )


class LuminusNumber(RestoreNumber):
    """Un tarif modifiable. La valeur par défaut (voir const.py) n'est
    utilisée qu'à la toute première création ; ensuite, la valeur
    courante est restaurée au redémarrage."""

    _attr_has_entity_name = True
    _attr_mode = NumberMode.BOX
    _attr_should_poll = False

    def __init__(
        self,
        entry: ConfigEntry,
        key: str,
        name: str,
        unit: str,
        min_value: float,
        max_value: float,
        step: float,
        default: float,
    ) -> None:
        self._attr_unique_id = f"{entry.entry_id}_number_{key}"
        self._attr_suggested_object_id = f"luminus_{key}"
        self._attr_name = name
        self._attr_native_unit_of_measurement = unit
        self._attr_native_min_value = min_value
        self._attr_native_max_value = max_value
        self._attr_native_step = step
        self._attr_native_value = default
        self._attr_device_info = device_info_for_entry(entry)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_data = await self.async_get_last_number_data()
        if last_data is not None and last_data.native_value is not None:
            self._attr_native_value = last_data.native_value

    async def async_set_native_value(self, value: float) -> None:
        self._attr_native_value = value
        self.async_write_ha_state()
