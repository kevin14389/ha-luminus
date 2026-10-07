"""Boutons de correction manuelle - remplacent l'input_button du
package YAML précédent.

Trois boutons :
- correction mois + année en même temps (usage historique : rattraper
  un prix encodé en retard, qui affecte les deux de la même façon).
- correction mois seul / année seule (indépendants, pour corriger une
  pollution qui n'affecte pas les deux accumulateurs du même montant -
  ex. après une erreur de configuration des tarifs corrigée en cours de
  route)."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    BUTTON_APPLIQUER_CORRECTION_ANNEE,
    BUTTON_APPLIQUER_CORRECTION_MANUELLE,
    BUTTON_APPLIQUER_CORRECTION_MOIS,
    DOMAIN,
    NUM_CORRECTION_ANNEE,
    NUM_CORRECTION_MANUELLE,
    NUM_CORRECTION_MOIS,
)
from .entity import device_info_for_entry
from .store import LuminusStore


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(
        [
            LuminusCorrectionButton(
                hass,
                entry,
                BUTTON_APPLIQUER_CORRECTION_MANUELLE,
                "Appliquer la correction manuelle (mois + année)",
                NUM_CORRECTION_MANUELLE,
                cible="les-deux",
            ),
            LuminusCorrectionButton(
                hass,
                entry,
                BUTTON_APPLIQUER_CORRECTION_MOIS,
                "Appliquer la correction manuelle - mois seul",
                NUM_CORRECTION_MOIS,
                cible="mois",
            ),
            LuminusCorrectionButton(
                hass,
                entry,
                BUTTON_APPLIQUER_CORRECTION_ANNEE,
                "Appliquer la correction manuelle - année seule",
                NUM_CORRECTION_ANNEE,
                cible="annee",
            ),
        ]
    )


class LuminusCorrectionButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_icon = "mdi:calculator-variant"

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        key: str,
        name: str,
        number_key: str,
        cible: str,
    ) -> None:
        self._hass = hass
        self._entry = entry
        self._number_entity_id = f"number.luminus_{number_key}"
        self._cible = cible
        self._attr_unique_id = f"{entry.entry_id}_button_{key}"
        self._attr_suggested_object_id = f"luminus_{key}"
        self._attr_name = name
        self._attr_device_info = device_info_for_entry(entry)

    async def async_press(self) -> None:
        store: LuminusStore = self._hass.data[DOMAIN][self._entry.entry_id]["store"]
        state = self._hass.states.get(self._number_entity_id)
        if state is None or state.state in ("unknown", "unavailable"):
            return
        try:
            correction = float(state.state)
        except ValueError:
            return
        if correction == 0:
            return

        if self._cible in ("mois", "les-deux"):
            await store.async_ajouter_cout_mois(correction)
        if self._cible in ("annee", "les-deux"):
            await store.async_ajouter_cout_annee(correction)

        await self._hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": self._number_entity_id, "value": 0},
            blocking=True,
        )
