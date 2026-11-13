"""Deux journées complètes avec de vrais utility_meter à double tarif
(la configuration habituelle d'un compteur communicant belge) : les
compteurs journaliers se remettent à zéro à minuit, l'intégration
clôture la journée 30 secondes plus tard."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .conftest import aller_a, heure_locale, installer, laisser_tourner, nombre

INDEX_PRELEVEMENT = "sensor.index_prelevement"
INDEX_INJECTION = "sensor.index_injection"
ATTRIBUTS = {"unit_of_measurement": "kWh", "device_class": "energy"}

RESEAU = 18.6666
ENERGIE = 27.0444
FIXE = 0.216


@pytest.fixture
def expected_lingering_timers() -> bool:
    """Les utility_meter déclarés en YAML gardent leur prochain reset
    programmé jusqu'à l'arrêt de Home Assistant."""
    return True


async def index(hass: HomeAssistant, entity_id: str, valeur: float) -> None:
    hass.states.async_set(entity_id, str(valeur), ATTRIBUTS)
    await laisser_tourner(hass)


async def tarif(hass: HomeAssistant, option: str) -> None:
    for compteur in ("daily_energy_delivered", "daily_energy_returned"):
        await hass.services.async_call(
            "select",
            "select_option",
            {"entity_id": f"select.{compteur}", "option": option},
            blocking=True,
        )
    await laisser_tourner(hass)


async def test_deux_jours_avec_de_vrais_compteurs(hass: HomeAssistant, entry, freezer) -> None:
    freezer.move_to(heure_locale("2026-11-12 06:00:00"))
    await index(hass, INDEX_PRELEVEMENT, 1000)
    await index(hass, INDEX_INJECTION, 500)
    assert await async_setup_component(
        hass,
        "utility_meter",
        {
            "utility_meter": {
                "daily_energy_delivered": {
                    "source": INDEX_PRELEVEMENT,
                    "cycle": "daily",
                    "tariffs": ["peak", "offpeak"],
                },
                "daily_energy_returned": {
                    "source": INDEX_INJECTION,
                    "cycle": "daily",
                    "tariffs": ["peak", "offpeak"],
                },
            }
        },
    )
    await hass.async_block_till_done()
    await installer(hass, entry)

    # Jour 1 : 4 kWh prélevés en heures pleines, 3 injectés, puis 2 kWh
    # prélevés en heures creuses.
    await index(hass, INDEX_PRELEVEMENT, 1004)
    await index(hass, INDEX_INJECTION, 503)
    await tarif(hass, "offpeak")
    await index(hass, INDEX_PRELEVEMENT, 1006)
    assert nombre(hass, "sensor.daily_energy_delivered_peak") == 4
    assert nombre(hass, "sensor.daily_energy_delivered_offpeak") == 2
    assert nombre(hass, "sensor.luminus_conso_jour") == 6
    assert nombre(hass, "sensor.luminus_injection_jour") == 3
    jour_1 = (3 * ENERGIE + 6 * RESEAU) / 100 + FIXE
    assert nombre(hass, "sensor.luminus_cout_total_mois") == round(jour_1, 2)

    await aller_a(hass, freezer, "2026-11-13 00:00:01")  # reset des utility_meter
    assert nombre(hass, "sensor.daily_energy_delivered_peak") == 0
    await aller_a(hass, freezer, "2026-11-13 00:00:31")  # clôture de l'intégration

    etat = entry.runtime_data.etat
    assert etat.derniere_cloture == "2026-11-12"
    assert etat.conso_mois_kwh == 6
    assert etat.injection_mois_kwh == 3
    assert etat.net_cumule_periode == 3
    assert nombre(hass, "sensor.luminus_conso_jour") == 0
    assert nombre(hass, "sensor.luminus_cout_total_mois") == round(jour_1 + FIXE, 2)

    # Jour 2 : 1 kWh prélevé, 9 injectés. Le solde du jour (-8) dépasse
    # le cumul de la période (+3) : seuls 3 kWh d'énergie sont remboursés.
    await tarif(hass, "peak")
    await index(hass, INDEX_PRELEVEMENT, 1007)
    await index(hass, INDEX_INJECTION, 512)
    jour_2 = (-3 * ENERGIE + 1 * RESEAU) / 100 + FIXE
    assert nombre(hass, "sensor.luminus_cout_total_jour") == pytest.approx(jour_2, abs=1e-4)

    await aller_a(hass, freezer, "2026-11-14 00:00:01")
    await aller_a(hass, freezer, "2026-11-14 00:00:31")

    etat = entry.runtime_data.etat
    assert etat.derniere_cloture == "2026-11-13"
    assert etat.conso_mois_kwh == 7
    assert etat.injection_mois_kwh == 12
    assert etat.net_cumule_periode == -5
    assert etat.accumulateur_mois == pytest.approx(jour_1 + jour_2, abs=1e-3)
    assert nombre(hass, "sensor.luminus_cout_total_mois") == round(jour_1 + jour_2 + FIXE, 2)
