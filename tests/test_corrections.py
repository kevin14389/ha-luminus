"""Boutons de correction manuelle : chacun fait ce que dit son nom."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant

from .conftest import demarrer, nombre

MOIS = "sensor.luminus_cout_total_mois"
ANNEE = "sensor.luminus_cout_total_annee"


async def corriger(hass: HomeAssistant, suffixe_nombre: str, suffixe_bouton: str, montant: float) -> None:
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": f"number.luminus_correction_manuelle{suffixe_nombre}", "value": montant},
        blocking=True,
    )
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": f"button.luminus_appliquer_correction{suffixe_bouton}"},
        blocking=True,
    )
    await hass.async_block_till_done()


@pytest.mark.parametrize(
    ("suffixe_nombre", "suffixe_bouton", "effet_mois", "effet_annee"),
    [
        ("", "_manuelle", 24.17, 24.17),
        ("_mois", "_mois", 24.17, 0),
        ("_annee", "_annee", 0, 24.17),
    ],
)
async def test_correction(
    hass: HomeAssistant, entry, freezer, suffixe_nombre, suffixe_bouton, effet_mois, effet_annee
) -> None:
    await demarrer(hass, entry, freezer, "2026-11-12 08:00:00")
    mois, annee = nombre(hass, MOIS), nombre(hass, ANNEE)

    await corriger(hass, suffixe_nombre, suffixe_bouton, 24.17)

    assert nombre(hass, MOIS) == pytest.approx(mois + effet_mois, abs=0.011)
    assert nombre(hass, ANNEE) == pytest.approx(annee + effet_annee, abs=0.011)
    # Le montant saisi est remis à 0 : un second appui ne recompte rien.
    assert nombre(hass, f"number.luminus_correction_manuelle{suffixe_nombre}") == 0
    await hass.services.async_call(
        "button",
        "press",
        {"entity_id": f"button.luminus_appliquer_correction{suffixe_bouton}"},
        blocking=True,
    )
    assert nombre(hass, MOIS) == pytest.approx(mois + effet_mois, abs=0.011)


async def test_correction_negative(hass: HomeAssistant, entry, freezer) -> None:
    await demarrer(hass, entry, freezer, "2026-11-12 08:00:00")
    await corriger(hass, "", "_manuelle", 30)

    await corriger(hass, "", "_manuelle", -10)

    assert entry.runtime_data.etat.accumulateur_mois == 20


async def test_correction_conservee_apres_redemarrage(hass: HomeAssistant, entry, freezer) -> None:
    await demarrer(hass, entry, freezer, "2026-11-12 08:00:00")
    await corriger(hass, "_annee", "_annee", 24.17)
    annee = nombre(hass, ANNEE)

    assert await hass.config_entries.async_unload(entry.entry_id)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert nombre(hass, ANNEE) == annee
