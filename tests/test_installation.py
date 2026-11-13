"""Installation : entités créées, noms, valeurs par défaut."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from custom_components.luminus_comfy.const import DOMAIN, NUMBER_DEFINITIONS

from .conftest import installer, nombre

ENTITES_ATTENDUES = {
    *(f"number.luminus_{key}" for key, *_ in NUMBER_DEFINITIONS),
    "switch.luminus_remise_fidelite_active",
    "switch.luminus_changement_prix_programme",
    "date.luminus_date_debut_contrat",
    "date.luminus_prix_energie_date_effet",
    "button.luminus_appliquer_correction_manuelle",
    "button.luminus_appliquer_correction_mois",
    "button.luminus_appliquer_correction_annee",
    "sensor.luminus_conso_jour",
    "sensor.luminus_injection_jour",
    "sensor.luminus_conso_nette_jour",
    "sensor.luminus_net_cumule_periode",
    "sensor.luminus_prix_energie_taxes_ttc",
    "sensor.luminus_prix_reseau_ttc",
    "sensor.luminus_prix_kwh_ttc",
    "sensor.luminus_prix_kwh_eur",
    "sensor.luminus_cout_fixe_journalier",
    "sensor.luminus_cout_variable_jour",
    "sensor.luminus_cout_total_jour",
    "sensor.luminus_cout_total_mois",
    "sensor.luminus_cout_total_annee",
    "sensor.luminus_historique_mensuel",
}


async def test_entites_creees_avec_les_noms_courts(hass: HomeAssistant, entry) -> None:
    await installer(hass, entry)

    assert entry.state is ConfigEntryState.LOADED
    registre = er.async_get(hass)
    creees = {e.entity_id for e in er.async_entries_for_config_entry(registre, entry.entry_id)}
    assert creees == ENTITES_ATTENDUES
    for entity_id in ENTITES_ATTENDUES:
        etat = hass.states.get(entity_id)
        assert etat is not None, entity_id
        assert etat.state != "unavailable", entity_id


async def test_prix_par_defaut(hass: HomeAssistant, entry) -> None:
    await installer(hass, entry)

    assert nombre(hass, "sensor.luminus_prix_energie_taxes_ttc") == 27.0444
    assert nombre(hass, "sensor.luminus_prix_reseau_ttc") == 18.6666
    assert nombre(hass, "sensor.luminus_prix_kwh_ttc") == 45.711
    assert nombre(hass, "sensor.luminus_cout_fixe_journalier") == 0.216


async def test_services_enregistres_puis_retires(hass: HomeAssistant, entry) -> None:
    await installer(hass, entry)
    assert hass.services.has_service(DOMAIN, "definir_mois_historique")
    assert hass.services.has_service(DOMAIN, "definir_cumul_periode")

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()
    assert not hass.services.has_service(DOMAIN, "definir_mois_historique")
    assert not hass.services.has_service(DOMAIN, "definir_cumul_periode")
