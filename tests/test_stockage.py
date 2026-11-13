"""Persistance : reprise des données existantes, perte du fichier."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.luminus_comfy.const import DOMAIN

from .conftest import (
    PRELEVEMENT_JOUR,
    SOURCES,
    demarrer,
    heure_locale,
    installer,
    nombre,
    notifications,
    regler,
    regler_source,
)

RESET_12 = "2026-11-11T23:00:00+00:00"


def fichier_1_3_1(entry: MockConfigEntry) -> dict:
    """Fichier .storage tel que l'écrit la version 1.3.1."""
    return {
        "version": 1,
        "minor_version": 1,
        "key": f"{DOMAIN}_{entry.entry_id}",
        "data": {
            "accumulateur_mois": 41.37,
            "accumulateur_annee": 2901.68,
            "net_cumule_periode": 96.412,
            "mois_courant": "2026-11",
            "annee_courante": "2026",
            "conso_mois_kwh": 118.204,
            "injection_mois_kwh": 21.792,
            "historique_mensuel": {
                "2026-09": {
                    "consommation_kwh": 610.0,
                    "production_kwh": 1011.62,
                    "solde_net_kwh": -401.62,
                    "cout_total_eur": -12.34,
                    "prix_moyen_kwh": -0.0202,
                    "prix_energie_taxes_ttc": 24.9594,
                    "prix_reseau_ttc": 14.7234,
                    "cumule_periode_apres": 3928.73,
                    "source": "manuel",
                },
                "2026-10": {
                    "consommation_kwh": 950.0,
                    "production_kwh": 120.0,
                    "solde_net_kwh": 830.0,
                    "cout_total_eur": 345.67,
                    "prix_moyen_kwh": 0.3639,
                    "prix_energie_taxes_ttc": 24.9594,
                    "prix_reseau_ttc": 14.7234,
                    "cumule_periode_apres": 4758.73,
                    "source": "manuel",
                },
            },
            "derniere_cloture": "2026-11-11",
        },
    }


async def test_mise_a_jour_depuis_1_3_1(hass: HomeAssistant, entry, freezer, hass_storage) -> None:
    """Mise à jour en pleine journée : totaux et historique conservés,
    et la journée en cours (lue sur les utility_meter) n'est ni perdue
    ni comptée deux fois."""
    hass_storage[f"{DOMAIN}_{entry.entry_id}"] = fichier_1_3_1(entry)
    freezer.move_to(heure_locale("2026-11-12 15:00:00"))
    for entity_id, valeur in zip(SOURCES.values(), (6.0, 2.5, 1.0, 0.0), strict=True):
        regler_source(hass, entity_id, valeur, last_reset=RESET_12, last_period="9.9")

    await installer(hass, entry)

    etat = entry.runtime_data.etat
    assert etat.accumulateur_mois == 41.37
    assert etat.net_cumule_periode == 96.412
    assert etat.conso_mois_kwh == 118.204
    assert etat.derniere_cloture == "2026-11-11"
    assert etat.historique_mensuel["2026-10"]["cout_total_eur"] == 345.67
    assert nombre(hass, "sensor.luminus_conso_jour") == 8.5
    assert nombre(hass, "sensor.luminus_injection_jour") == 1.0
    assert hass.states.get("sensor.luminus_historique_mensuel").state == "2"
    total = hass.states.get("sensor.luminus_historique_mensuel").attributes["total_annee"]
    assert total["consommation_kwh"] == round(610 + 950 + 118.204 + 8.5, 3)
    assert "luminus_stockage_perdu" not in notifications(hass)

    # L'ancien accumulateur annuel, inutilisé, disparaît du fichier.
    await hass.config_entries.async_unload(entry.entry_id)
    donnees = hass_storage[f"{DOMAIN}_{entry.entry_id}"]["data"]
    assert "accumulateur_annee" not in donnees
    assert donnees["accumulateur_mois"] == 41.37
    assert donnees["prelevement_en_cours"] == 8.5


async def test_etat_conserve_apres_redemarrage(hass: HomeAssistant, entry, freezer) -> None:
    await demarrer(hass, entry, freezer, "2026-11-12 08:00:00")
    await regler(hass, PRELEVEMENT_JOUR, 3.0)
    entry.runtime_data.etat.accumulateur_mois = 12.5

    assert await hass.config_entries.async_unload(entry.entry_id)
    await installer(hass, entry)

    assert entry.runtime_data.etat.accumulateur_mois == 12.5
    assert nombre(hass, "sensor.luminus_conso_jour") == 3.0


async def test_fichier_de_donnees_disparu(hass: HomeAssistant, freezer) -> None:
    """Intégration installée depuis 11 jours, mais plus aucun fichier de
    données : l'utilisateur est prévenu au lieu de voir des totaux
    repartir de zéro sans explication."""
    freezer.move_to(heure_locale("2026-11-01 08:00:00"))
    entry = MockConfigEntry(domain=DOMAIN, data=SOURCES, unique_id=DOMAIN)
    entry.add_to_hass(hass)

    freezer.move_to(heure_locale("2026-11-12 08:00:00"))
    await installer(hass, entry)

    assert "luminus_stockage_perdu" in notifications(hass)


async def test_premiere_installation_sans_alerte(hass: HomeAssistant, entry, freezer) -> None:
    await demarrer(hass, entry, freezer, "2026-11-12 08:00:00")

    assert notifications(hass) == {}
