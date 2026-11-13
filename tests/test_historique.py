"""Services definir_mois_historique et definir_cumul_periode."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from custom_components.luminus_comfy.const import DOMAIN

from .conftest import PRELEVEMENT_JOUR, demarrer, nombre, notifications, regler

FIXE = 0.216


async def definir_mois(hass: HomeAssistant, mois: str, conso: float, production: float) -> None:
    await hass.services.async_call(
        DOMAIN,
        "definir_mois_historique",
        {"mois": mois, "consommation_kwh": conso, "production_kwh": production},
        blocking=True,
    )


async def test_import_enchaine_le_cumul_de_periode(hass: HomeAssistant, entry, freezer) -> None:
    """Janvier consomme, juillet injecte plus qu'il ne prélève : le
    solde négatif de juillet rembourse de l'énergie facturée en janvier
    au lieu d'être compté à 0."""
    await demarrer(hass, entry, freezer, "2026-11-12 08:00:00")

    await definir_mois(hass, "2026-01", 1000, 100)
    await definir_mois(hass, "2026-02", 300, 700)

    historique = entry.runtime_data.etat.historique_mensuel
    assert historique["2026-01"]["cumule_periode_apres"] == 900
    assert historique["2026-01"]["source"] == "manuel"
    assert historique["2026-01"]["cout_total_eur"] == round(
        (900 * 27.0444 + 1000 * 18.6666) / 100 + FIXE * 31, 2
    )
    assert historique["2026-02"]["cumule_periode_apres"] == 500
    assert historique["2026-02"]["cout_total_eur"] == round(
        (-400 * 27.0444 + 300 * 18.6666) / 100 + FIXE * 28, 2
    )
    assert "2026-02" in notifications(hass)["luminus_mois_2026-02"]["title"]


async def test_capteur_historique_et_total_de_l_annee(hass: HomeAssistant, entry, freezer) -> None:
    await demarrer(hass, entry, freezer, "2026-11-12 08:00:00")
    await definir_mois(hass, "2025-12", 800, 0)
    await definir_mois(hass, "2026-02", 600, 100)
    await definir_mois(hass, "2026-01", 1000, 100)
    await regler(hass, PRELEVEMENT_JOUR, 10)

    etat = hass.states.get("sensor.luminus_historique_mensuel")
    assert etat.state == "3"
    assert [m["mois"] for m in etat.attributes["mois"]] == ["2025-12", "2026-01", "2026-02"]
    assert etat.attributes["mois"][1]["mois_label"] == "Janvier 2026"

    historique = entry.runtime_data.etat.historique_mensuel
    total = etat.attributes["total_annee"]
    # 2025 n'entre pas dans le total de 2026 ; le mois en cours, si.
    assert total["consommation_kwh"] == 1610
    assert total["production_kwh"] == 200
    assert total["solde_net_kwh"] == 1410
    assert total["cout_total_eur"] == pytest.approx(
        historique["2026-01"]["cout_total_eur"]
        + historique["2026-02"]["cout_total_eur"]
        + nombre(hass, "sensor.luminus_cout_total_mois"),
        abs=0.011,
    )
    assert nombre(hass, "sensor.luminus_cout_total_annee") == total["cout_total_eur"]


async def test_mois_en_cours_saisi_a_la_main_pas_compte_deux_fois(
    hass: HomeAssistant, entry, freezer
) -> None:
    await demarrer(hass, entry, freezer, "2026-11-12 08:00:00")
    avant = nombre(hass, "sensor.luminus_cout_total_annee")

    await definir_mois(hass, "2026-11", 900, 100)

    assert nombre(hass, "sensor.luminus_cout_total_annee") == avant


@pytest.mark.parametrize("mois", ["2026-13", "2026-1", "janvier", "26-01", "2026-00"])
async def test_mois_invalide_refuse(hass: HomeAssistant, entry, freezer, mois) -> None:
    await demarrer(hass, entry, freezer, "2026-11-12 08:00:00")

    with pytest.raises(ServiceValidationError):
        await definir_mois(hass, mois, 100, 0)

    assert entry.runtime_data.etat.historique_mensuel == {}


async def test_kwh_negatifs_refuses(hass: HomeAssistant, entry, freezer) -> None:
    await demarrer(hass, entry, freezer, "2026-11-12 08:00:00")

    with pytest.raises(ServiceValidationError):
        await definir_mois(hass, "2026-01", -1, 0)


async def test_definir_cumul_periode(hass: HomeAssistant, entry, freezer) -> None:
    """Avec un cumul de période positif, un jour très producteur
    rembourse de l'énergie ; avec un cumul nul, il ne rembourse rien."""
    await demarrer(hass, entry, freezer, "2026-11-12 08:00:00")
    await regler(hass, "sensor.daily_energy_returned_peak", 40)
    assert nombre(hass, "sensor.luminus_cout_variable_jour") == 0

    await hass.services.async_call(
        DOMAIN, "definir_cumul_periode", {"cumul_kwh": 812.4}, blocking=True
    )

    assert nombre(hass, "sensor.luminus_net_cumule_periode") == 812.4
    assert nombre(hass, "sensor.luminus_cout_variable_jour") == round(-40 * 27.0444 / 100, 4)
