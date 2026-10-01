"""Interrupteurs : remise fidélité et changement de prix programmé -
remplace les input_boolean du package YAML précédent."""

from __future__ import annotations

from homeassistant.components.switch import SwitchEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import SWITCH_CHANGEMENT_PRIX_PROGRAMME, SWITCH_REMISE_FIDELITE_ACTIVE
from .entity import device_info_for_entry

_DEFINITIONS = [
    (SWITCH_REMISE_FIDELITE_ACTIVE, "Remise fidélité domiciliation active", "mdi:cash-check"),
    (SWITCH_CHANGEMENT_PRIX_PROGRAMME, "Changement de prix programmé actif", "mdi:calendar-clock"),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(
        LuminusSwitch(entry, key, name, icon) for key, name, icon in _DEFINITIONS
    )


class LuminusSwitch(SwitchEntity, RestoreEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, key: str, name: str, icon: str) -> None:
        self._attr_unique_id = f"{entry.entry_id}_switch_{key}"
        self._attr_suggested_object_id = f"luminus_{key}"
        self._attr_name = name
        self._attr_icon = icon
        self._attr_is_on = False
        self._attr_device_info = device_info_for_entry(entry)

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        last_state = await self.async_get_last_state()
        if last_state is not None:
            self._attr_is_on = last_state.state == "on"

    async def async_turn_on(self, **kwargs) -> None:
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs) -> None:
        self._attr_is_on = False
        self.async_write_ha_state()
