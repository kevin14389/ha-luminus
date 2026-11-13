"""Tarifs modifiables, restauration au redémarrage, prix programmé."""

from __future__ import annotations

import pytest
from homeassistant.core import HomeAssistant, State
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import mock_restore_cache_with_extra_data

from custom_components.luminus_comfy.const import DOMAIN

from .conftest import (
    PRELEVEMENT_JOUR,
    aller_a,
    demarrer,
    installer,
    nombre,
    notifications,
    regler,
)

ENERGIE = "sensor.luminus_prix_energie_taxes_ttc"
MATIN = "2026-11-12 08:00:00"


async def regler_nombre(hass: HomeAssistant, entity_id: str, valeur: float) -> None:
    await hass.services.async_call(
        "number", "set_value", {"entity_id": entity_id, "value": valeur}, blocking=True
    )


async def regler_date(hass: HomeAssistant, entity_id: str, valeur: str) -> None:
    await hass.services.async_call(
        "date", "set_value", {"entity_id": entity_id, "date": valeur}, blocking=True
    )


async def interrupteur(hass: HomeAssistant, entity_id: str, allume: bool) -> None:
    await hass.services.async_call(
        "switch", "turn_on" if allume else "turn_off", {"entity_id": entity_id}, blocking=True
    )


async def test_modifier_un_tarif_met_a_jour_les_capteurs(
    hass: HomeAssistant, entry, freezer
) -> None:
    await demarrer(hass, entry, freezer, MATIN)
    await regler(hass, PRELEVEMENT_JOUR, 10)
    assert nombre(hass, "sensor.luminus_cout_variable_jour") == round(
        10 * (27.0444 + 18.6666) / 100, 4
    )

    await regler_nombre(hass, "number.luminus_ores_cout_reseau_variable", 13.89)

    assert nombre(hass, "sensor.luminus_prix_reseau_ttc") == 14.7234
    assert nombre(hass, "sensor.luminus_cout_variable_jour") == round(
        10 * (27.0444 + 14.7234) / 100, 4
    )


async def test_remise_fidelite(hass: HomeAssistant, entry, freezer) -> None:
    await demarrer(hass, entry, freezer, MATIN)
    await regler_date(hass, "date.luminus_date_debut_contrat", "2023-09-23")
    await regler_nombre(hass, "number.luminus_remise_fidelite_domiciliation_kwh", 0.4717)
    assert nombre(hass, ENERGIE) == 27.0444

    await interrupteur(hass, "switch.luminus_remise_fidelite_active", True)
    assert nombre(hass, ENERGIE) == 24.6714

    await interrupteur(hass, "switch.luminus_remise_fidelite_active", False)
    assert nombre(hass, ENERGIE) == 27.0444


async def test_tarifs_restaures_au_redemarrage(hass: HomeAssistant, entry, freezer) -> None:
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State("number.luminus_prix_energie_ttc", "19.05"),
                {
                    "native_max_value": 100,
                    "native_min_value": 0,
                    "native_step": 0.01,
                    "native_unit_of_measurement": "c€/kWh",
                    "native_value": 19.05,
                },
            ),
            (State("switch.luminus_remise_fidelite_active", "on"), {}),
            (State("date.luminus_date_debut_contrat", "2023-09-23"), {}),
            (State("date.luminus_prix_energie_date_effet", "unknown"), {}),
        ],
    )

    await demarrer(hass, entry, freezer, MATIN)

    assert nombre(hass, "number.luminus_prix_energie_ttc") == 19.05
    assert hass.states.get("switch.luminus_remise_fidelite_active").state == "on"
    assert hass.states.get("date.luminus_date_debut_contrat").state == "2023-09-23"
    assert hass.states.get("date.luminus_prix_energie_date_effet").state == "unknown"
    # 19,05 TTC, -10 % après 24 mois, + énergie verte et taxes.
    assert nombre(hass, ENERGIE) == 25.4594


async def test_calculs_independants_des_entity_id(hass: HomeAssistant, entry, freezer) -> None:
    """Installation existante dont les entités portent encore les noms
    longs attribués par les versions <= 1.2 (Home Assistant ne renomme
    jamais une entité déjà enregistrée)."""
    registre = er.async_get(hass)
    registre.async_get_or_create(
        "number",
        DOMAIN,
        f"{entry.entry_id}_number_prix_energie_ttc",
        config_entry=entry,
        suggested_object_id="luminus_comfy_electricite_prix_energie_fournie_ttc",
    )
    registre.async_get_or_create(
        "switch",
        DOMAIN,
        f"{entry.entry_id}_switch_remise_fidelite_active",
        config_entry=entry,
        suggested_object_id="luminus_comfy_electricite_remise_fidelite_domiciliation_active",
    )
    await demarrer(hass, entry, freezer, MATIN)
    assert hass.states.get("number.luminus_prix_energie_ttc") is None

    await regler_nombre(hass, "number.luminus_comfy_electricite_prix_energie_fournie_ttc", 19.05)
    await regler_date(hass, "date.luminus_date_debut_contrat", "2023-09-23")
    await interrupteur(
        hass, "switch.luminus_comfy_electricite_remise_fidelite_domiciliation_active", True
    )

    assert nombre(hass, ENERGIE) == 25.4594


async def test_prix_programme_applique_apres_la_cloture(
    hass: HomeAssistant, entry, freezer
) -> None:
    """Le jour qui se termine est facturé à l'ancien prix ; le nouveau
    prix ouvre une nouvelle période tarifaire (cumul remis à 0)."""
    await demarrer(hass, entry, freezer, MATIN)
    await regler_nombre(hass, "number.luminus_prix_energie_ttc_prochain", 20.5)
    await regler_date(hass, "date.luminus_prix_energie_date_effet", "2026-11-13")
    await interrupteur(hass, "switch.luminus_changement_prix_programme", True)
    await regler(hass, PRELEVEMENT_JOUR, 10)
    assert nombre(hass, "number.luminus_prix_energie_ttc") == 18.73

    await aller_a(hass, freezer, "2026-11-13 00:00:31")

    etat = entry.runtime_data.etat
    assert etat.accumulateur_mois == pytest.approx(
        10 * (27.0444 + 18.6666) / 100 + 0.216, abs=1e-4
    )
    assert etat.net_cumule_periode == 0
    assert nombre(hass, "number.luminus_prix_energie_ttc") == 20.5
    assert nombre(hass, "number.luminus_prix_energie_ttc_prochain") == 0
    assert hass.states.get("switch.luminus_changement_prix_programme").state == "off"
    assert nombre(hass, ENERGIE) == 28.8144
    assert "20.5" in notifications(hass)["luminus_changement_prix_applique"]["message"]


async def test_prix_programme_en_retard_applique_tout_de_suite(
    hass: HomeAssistant, entry, freezer
) -> None:
    await demarrer(hass, entry, freezer, MATIN)
    entry.runtime_data.etat.net_cumule_periode = 123.0
    await regler_nombre(hass, "number.luminus_prix_energie_ttc_prochain", 20.5)
    await regler_date(hass, "date.luminus_prix_energie_date_effet", "2026-11-01")

    await interrupteur(hass, "switch.luminus_changement_prix_programme", True)
    await hass.async_block_till_done()

    assert nombre(hass, "number.luminus_prix_energie_ttc") == 20.5
    assert hass.states.get("switch.luminus_changement_prix_programme").state == "off"
    assert entry.runtime_data.etat.net_cumule_periode == 0


async def test_prix_programme_incomplet_n_applique_rien(
    hass: HomeAssistant, entry, freezer
) -> None:
    await demarrer(hass, entry, freezer, MATIN)
    await regler_date(hass, "date.luminus_prix_energie_date_effet", "2026-11-01")

    await interrupteur(hass, "switch.luminus_changement_prix_programme", True)

    # Pas de nouveau prix saisi : l'interrupteur reste armé, rien ne change.
    assert nombre(hass, "number.luminus_prix_energie_ttc") == 18.73
    assert hass.states.get("switch.luminus_changement_prix_programme").state == "on"
