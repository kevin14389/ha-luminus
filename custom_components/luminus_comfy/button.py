"""Bouton de correction manuelle - remplace l'input_button du package
YAML précédent. Ajoute number.luminus_correction_manuelle aux
accumulateurs mensuel/annuel persistés, puis le remet à 0."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import BUTTON_APPLIQUER_CORRECTION_MANUELLE, DOMAIN, NUM_CORRECTION_MANUELLE
from .entity import device_info_for_entry
from .store import LuminusStore


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities([LuminusCorrectionButton(hass, entry)])


class LuminusCorrectionButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:calculator-variant"

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self._hass = hass
        self._entry = entry
        self._attr_unique_id = f"{entry.entry_id}_button_{BUTTON_APPLIQUER_CORRECTION_MANUELLE}"
        self._attr_suggested_object_id = f"luminus_{BUTTON_APPLIQUER_CORRECTION_MANUELLE}"
        self._attr_name = "Appliquer la correction manuelle"
        self._attr_device_info = device_info_for_entry(entry)

    async def async_press(self) -> None:
        store: LuminusStore = self._hass.data[DOMAIN][self._entry.entry_id]["store"]
        correction_entity_id = f"number.luminus_{NUM_CORRECTION_MANUELLE}"
        state = self._hass.states.get(correction_entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return
        try:
            correction = float(state.state)
        except ValueError:
            return
        if correction == 0:
            return

        await store.async_ajouter_cout_mois(correction)
        await store.async_ajouter_cout_annee(correction)

        await self._hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": correction_entity_id, "value": 0},
            blocking=True,
        )
