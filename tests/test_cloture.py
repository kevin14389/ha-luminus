"""Clôture quotidienne, changement de mois et d'année."""

from __future__ import annotations

from datetime import date

import pytest
from homeassistant.core import HomeAssistant

from custom_components.luminus_comfy import calculations as calc
from custom_components.luminus_comfy.const import DOMAIN, NUMBER_DEFINITIONS

from .conftest import (
    INJECTION_JOUR,
    PRELEVEMENT_JOUR,
    PRELEVEMENT_NUIT,
    aller_a,
    demarrer,
    installer,
    nombre,
    notifications,
    regler,
)

MOIS = "sensor.luminus_cout_total_mois"
ANNEE = "sensor.luminus_cout_total_annee"
CONSO = "sensor.luminus_conso_jour"
FIXE = 0.216  # coût fixe journalier avec les tarifs par défaut
DEFAUTS = {key: defaut for key, *_reste, defaut in NUMBER_DEFINITIONS}


def cout_variable(prelevement: float, injection: float, cumul: float = 0.0) -> float:
    """Coût attendu avec les tarifs par défaut."""
    return calc.cout_variable(DEFAUTS, date(2026, 11, 12), prelevement, injection, cumul)[1]


async def test_cloture_de_minuit(hass: HomeAssistant, entry, freezer) -> None:
    await demarrer(hass, entry, freezer, "2026-11-12 08:00:00")
    await regler(hass, PRELEVEMENT_JOUR, 10)
    await regler(hass, PRELEVEMENT_NUIT, 5)
    await regler(hass, INJECTION_JOUR, 4)
    jour = cout_variable(15, 4) + FIXE
    assert nombre(hass, MOIS) == round(jour, 2)

    await aller_a(hass, freezer, "2026-11-13 00:00:31")

    etat = entry.runtime_data.etat
    assert etat.derniere_cloture == "2026-11-12"
    assert etat.conso_mois_kwh == 15
    assert etat.injection_mois_kwh == 4
    assert etat.net_cumule_periode == 11
    assert etat.accumulateur_mois == pytest.approx(jour, abs=1e-4)
    assert etat.prelevement_en_cours == 0
    assert etat.injection_en_cours == 0
    # Le mois = le jour clôturé + le coût fixe du jour qui commence.
    assert nombre(hass, CONSO) == 0
    assert nombre(hass, MOIS) == round(jour + FIXE, 2)
    assert nombre(hass, "sensor.luminus_net_cumule_periode") == 11
    resume = notifications(hass)["luminus_resume_quotidien"]
    assert "12/11/2026" in resume["title"]
    assert "Prélèvement : 15.0 kWh" in resume["message"]


async def test_cloture_lancee_deux_fois_ne_compte_qu_une_fois(
    hass: HomeAssistant, entry, freezer
) -> None:
    await demarrer(hass, entry, freezer, "2026-11-12 08:00:00")
    await regler(hass, PRELEVEMENT_JOUR, 10)
    await aller_a(hass, freezer, "2026-11-13 00:00:31")
    avant = entry.runtime_data.etat.accumulateur_mois

    await entry.runtime_data.async_tic()
    await entry.runtime_data.async_tic()

    assert entry.runtime_data.etat.accumulateur_mois == avant
    assert entry.runtime_data.etat.conso_mois_kwh == 10


async def test_redemarrage_juste_apres_minuit(hass: HomeAssistant, entry, freezer) -> None:
    """Rattrapage au démarrage à 00:00:10, puis déclencheur de 00:00:30 :
    la journée n'est créditée qu'une fois."""
    await demarrer(hass, entry, freezer, "2026-11-12 08:00:00")
    await regler(hass, PRELEVEMENT_JOUR, 10)
    assert await hass.config_entries.async_unload(entry.entry_id)

    freezer.move_to("2026-11-12 23:00:10+00:00")  # 00:00:10 heure belge
    await installer(hass, entry)
    assert entry.runtime_data.etat.conso_mois_kwh == 10
    await aller_a(hass, freezer, "2026-11-13 00:00:31")

    assert entry.runtime_data.etat.conso_mois_kwh == 10
    assert entry.runtime_data.etat.accumulateur_mois == pytest.approx(
        cout_variable(10, 0) + FIXE, abs=1e-4
    )


async def test_home_assistant_arrete_a_minuit(hass: HomeAssistant, entry, freezer) -> None:
    """Arrêté de 22 h à 9 h : les capteurs sources ne se sont pas remis à
    zéro et ont continué de compter. Tout est crédité une seule fois, au
    redémarrage, puis la journée suivante normalement."""
    await demarrer(hass, entry, freezer, "2026-11-12 08:00:00")
    await regler(hass, PRELEVEMENT_JOUR, 10)
    assert await hass.config_entries.async_unload(entry.entry_id)

    freezer.move_to("2026-11-13 08:00:00+00:00")
    await regler(hass, PRELEVEMENT_JOUR, 14)
    await installer(hass, entry)

    etat = entry.runtime_data.etat
    assert etat.derniere_cloture == "2026-11-12"
    assert etat.conso_mois_kwh == 14
    assert etat.prelevement_en_cours == 0

    await regler(hass, PRELEVEMENT_JOUR, 20)
    await regler(hass, PRELEVEMENT_JOUR, 0)  # reset de minuit
    await aller_a(hass, freezer, "2026-11-14 00:00:31")

    etat = entry.runtime_data.etat
    assert etat.conso_mois_kwh == 20
    assert etat.accumulateur_mois == pytest.approx(
        cout_variable(14, 0) + cout_variable(6, 0, 14) + 2 * FIXE, abs=1e-3
    )


async def test_arret_de_plusieurs_jours(hass: HomeAssistant, entry, freezer) -> None:
    """Le coût fixe court pour chaque jour, même sans mesure."""
    await demarrer(hass, entry, freezer, "2026-11-12 08:00:00")
    await regler(hass, PRELEVEMENT_JOUR, 10)
    assert await hass.config_entries.async_unload(entry.entry_id)

    freezer.move_to("2026-11-15 08:00:00+00:00")
    await installer(hass, entry)

    etat = entry.runtime_data.etat
    assert etat.derniere_cloture == "2026-11-14"
    assert etat.accumulateur_mois == pytest.approx(cout_variable(10, 0) + 3 * FIXE, abs=1e-4)
    assert "(3 jours)" in notifications(hass)["luminus_resume_quotidien"]["title"]


async def test_compensation_sur_trois_jours(hass: HomeAssistant, entry, freezer) -> None:
    """L'exemple de référence : 5/50, 5/50 puis 20/0. Le cumul de période
    reste négatif, donc 0 € d'énergie : seuls le réseau (30 kWh bruts)
    et le coût fixe sont dus."""
    await demarrer(hass, entry, freezer, "2026-11-12 08:00:00")
    for jour, (prelevement, injection) in zip(
        ("13", "14", "15"), [(5, 50), (5, 50), (20, 0)], strict=True
    ):
        await regler(hass, PRELEVEMENT_JOUR, prelevement)
        await regler(hass, INJECTION_JOUR, injection)
        await regler(hass, PRELEVEMENT_JOUR, 0)
        await regler(hass, INJECTION_JOUR, 0)
        await aller_a(hass, freezer, f"2026-11-{jour} 00:00:31")

    etat = entry.runtime_data.etat
    assert etat.net_cumule_periode == -70
    assert etat.conso_mois_kwh == 30
    assert etat.accumulateur_mois == pytest.approx(30 * 18.6666 / 100 + 3 * FIXE, abs=1e-3)


async def test_changement_de_mois(hass: HomeAssistant, entry, freezer) -> None:
    await demarrer(hass, entry, freezer, "2026-11-30 08:00:00")
    await regler(hass, PRELEVEMENT_JOUR, 10)
    await regler(hass, INJECTION_JOUR, 4)
    novembre = cout_variable(10, 4) + FIXE

    await aller_a(hass, freezer, "2026-12-01 00:00:31")

    etat = entry.runtime_data.etat
    assert etat.mois_courant == "2026-12"
    assert etat.accumulateur_mois == 0
    assert etat.conso_mois_kwh == 0
    assert etat.historique_mensuel["2026-11"] == {
        "consommation_kwh": 10,
        "production_kwh": 4,
        "solde_net_kwh": 6,
        "cout_total_eur": round(novembre, 2),
        "prix_moyen_kwh": round(novembre / 10, 4),
        "prix_energie_taxes_ttc": 27.0444,
        "prix_reseau_ttc": 18.6666,
        "cumule_periode_apres": 6,
        "source": "auto",
    }
    assert nombre(hass, MOIS) == round(FIXE, 2)
    # Le mois archivé est arrondi au centime.
    assert nombre(hass, ANNEE) == round(round(novembre, 2) + FIXE, 2)

    historique = hass.states.get("sensor.luminus_historique_mensuel")
    assert historique.state == "1"
    assert historique.attributes["mois"][0]["mois_label"] == "Novembre 2026"
    assert historique.attributes["total_annee"]["consommation_kwh"] == 10


async def test_mois_saisi_a_la_main_jamais_ecrase(hass: HomeAssistant, entry, freezer) -> None:
    await demarrer(hass, entry, freezer, "2026-11-30 08:00:00")
    await regler(hass, PRELEVEMENT_JOUR, 10)
    await hass.services.async_call(
        DOMAIN,
        "definir_mois_historique",
        {"mois": "2026-11", "consommation_kwh": 900, "production_kwh": 100},
        blocking=True,
    )

    await aller_a(hass, freezer, "2026-12-01 00:00:31")

    novembre = entry.runtime_data.etat.historique_mensuel["2026-11"]
    assert novembre["source"] == "manuel"
    assert novembre["consommation_kwh"] == 900
    assert entry.runtime_data.etat.mois_courant == "2026-12"


async def test_changement_d_annee(hass: HomeAssistant, entry, freezer) -> None:
    await demarrer(hass, entry, freezer, "2026-12-31 08:00:00")
    await regler(hass, PRELEVEMENT_JOUR, 10)
    entry.runtime_data.etat.correction_annee = 50.0

    await aller_a(hass, freezer, "2027-01-01 00:00:31")

    etat = entry.runtime_data.etat
    assert etat.annee_courante == "2027"
    assert etat.correction_annee == 0
    assert "2026-12" in etat.historique_mensuel
    # Décembre 2026 n'entre pas dans le total de 2027.
    assert nombre(hass, ANNEE) == round(FIXE, 2)


async def test_mois_reste_bloque_par_une_ancienne_version(
    hass: HomeAssistant, entry, freezer, hass_storage
) -> None:
    """État laissé par la 1.3.0, dont la clôture ne tournait jamais :
    mois figé sur octobre, date de dernière clôture vide. Octobre a été
    ressaisi à la main entre-temps."""
    hass_storage[f"{DOMAIN}_{entry.entry_id}"] = {
        "version": 1,
        "minor_version": 1,
        "key": f"{DOMAIN}_{entry.entry_id}",
        "data": {
            "accumulateur_mois": 11.51,
            "accumulateur_annee": 2901.68,
            "net_cumule_periode": 28.47,
            "mois_courant": "2026-10",
            "annee_courante": "2026",
            "conso_mois_kwh": 28.47,
            "injection_mois_kwh": 0.0,
            "historique_mensuel": {
                "2026-10": {
                    "consommation_kwh": 950.0,
                    "production_kwh": 120.0,
                    "solde_net_kwh": 830.0,
                    "cout_total_eur": 345.67,
                    "prix_moyen_kwh": 0.3639,
                    "cumule_periode_apres": 830.0,
                    "source": "manuel",
                }
            },
            "derniere_cloture": "",
        },
    }

    await demarrer(hass, entry, freezer, "2026-11-12 08:00:00")

    etat = entry.runtime_data.etat
    assert etat.mois_courant == "2026-11"
    assert etat.derniere_cloture == "2026-11-11"
    assert etat.accumulateur_mois == 0
    assert etat.conso_mois_kwh == 0
    assert etat.historique_mensuel["2026-10"]["cout_total_eur"] == 345.67
    assert nombre(hass, ANNEE) == round(345.67 + FIXE, 2)
