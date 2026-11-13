"""Boutons de correction manuelle. Chacun ajoute le montant saisi dans
son entité number, puis remet ce montant à 0 :

- mois + année : rattraper un prix encodé en retard, par exemple.
- mois seul : le total de l'année ne bouge pas.
- année seule : le total du mois ne bouge pas.
"""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import (
    BUTTON_APPLIQUER_CORRECTION_ANNEE,
    BUTTON_APPLIQUER_CORRECTION_MANUELLE,
    BUTTON_APPLIQUER_CORRECTION_MOIS,
    NUM_CORRECTION_ANNEE,
    NUM_CORRECTION_MANUELLE,
    NUM_CORRECTION_MOIS,
)
from .coordinateur import LuminusCoordinateur
from .entity import LuminusEntity

# (clé, nom, entité number du montant, cible)
_DEFINITIONS = [
    (
        BUTTON_APPLIQUER_CORRECTION_MANUELLE,
        "Appliquer la correction manuelle (mois + année)",
        NUM_CORRECTION_MANUELLE,
        "les-deux",
    ),
    (
        BUTTON_APPLIQUER_CORRECTION_MOIS,
        "Appliquer la correction manuelle - mois seul",
        NUM_CORRECTION_MOIS,
        "mois",
    ),
    (
        BUTTON_APPLIQUER_CORRECTION_ANNEE,
        "Appliquer la correction manuelle - année seule",
        NUM_CORRECTION_ANNEE,
        "annee",
    ),
]


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    async_add_entities(
        LuminusCorrectionButton(entry.runtime_data, key, name, number_key, cible)
        for key, name, number_key, cible in _DEFINITIONS
    )


class LuminusCorrectionButton(LuminusEntity, ButtonEntity):
    _attr_icon = "mdi:calculator-variant"

    def __init__(
        self,
        coordinateur: LuminusCoordinateur,
        key: str,
        name: str,
        number_key: str,
        cible: str,
    ) -> None:
        super().__init__(coordinateur, "button", key, name)
        self._number_key = number_key
        self._cible = cible

    async def async_press(self) -> None:
        await self._coordinateur.async_appliquer_correction(self._number_key, self._cible)
