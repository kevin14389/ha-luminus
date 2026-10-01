"""Calculs de prix et de coût - portage fidèle des formules Jinja du
package YAML d'origine (déjà validées avec un vrai décompte Luminus et
plusieurs allers-retours de vérification). Fonctions pures : lisent les
états actuels (hass.states) et le cumul de période (passé en argument,
issu du Store persisté), ne gardent aucun état interne - pas de risque
de décalage entre capteurs comme avec les templates HA chaînés.
"""

from __future__ import annotations

from datetime import date

from homeassistant.core import HomeAssistant

from .const import (
    DATETIME_DATE_DEBUT_CONTRAT,
    NUM_COUT_ENERGIE_VERTE,
    NUM_ORES_COUT_RESEAU_VARIABLE,
    NUM_ORES_TERME_FIXE_GRD,
    NUM_PRIX_ENERGIE_TTC,
    NUM_REDEVANCE_FIXE_ANNUELLE,
    NUM_REMISE_FIDELITE_12_MOIS,
    NUM_REMISE_FIDELITE_24_MOIS,
    NUM_TAUX_TVA,
    NUM_TAXE_ACCISE_SPECIAL,
    NUM_TAXE_COTISATION_ENERGIE,
    NUM_TAXE_REDEVANCE_RACCORDEMENT,
    SWITCH_REMISE_FIDELITE_ACTIVE,
)

_UNAVAILABLE = ("unknown", "unavailable", None)


def get_number(hass: HomeAssistant, key: str, default: float = 0.0) -> float:
    state = hass.states.get(f"number.luminus_{key}")
    if state is None or state.state in _UNAVAILABLE:
        return default
    try:
        return float(state.state)
    except ValueError:
        return default


def get_switch_on(hass: HomeAssistant, key: str) -> bool:
    state = hass.states.get(f"switch.luminus_{key}")
    return state is not None and state.state == "on"


def get_date(hass: HomeAssistant, key: str) -> date | None:
    state = hass.states.get(f"date.luminus_{key}")
    if state is None or state.state in _UNAVAILABLE:
        return None
    try:
        return date.fromisoformat(state.state)
    except ValueError:
        return None


def get_source_value(hass: HomeAssistant, entity_id: str | None) -> float:
    if not entity_id:
        return 0.0
    state = hass.states.get(entity_id)
    if state is None or state.state in _UNAVAILABLE:
        return 0.0
    try:
        return float(state.state)
    except ValueError:
        return 0.0


def prelevement_total(hass: HomeAssistant, delivered_peak: str, delivered_offpeak: str) -> float:
    """Prélèvement réseau total (jour+nuit additionnés)."""
    return round(
        get_source_value(hass, delivered_peak) + get_source_value(hass, delivered_offpeak), 3
    )


def injection_totale(hass: HomeAssistant, returned_peak: str, returned_offpeak: str) -> float:
    """Injection réseau totale (jour+nuit additionnées)."""
    return round(
        get_source_value(hass, returned_peak) + get_source_value(hass, returned_offpeak), 3
    )


def prix_energie_taxes_ttc(hass: HomeAssistant) -> float:
    """c€/kWh, HTVA->TTC. S'applique au prélèvement NET (voir
    cout_variable_jour), pas au brut."""
    tva = get_number(hass, NUM_TAUX_TVA)
    energie_ttc = get_number(hass, NUM_PRIX_ENERGIE_TTC)
    energie_ht = energie_ttc / (1 + tva / 100) if (1 + tva / 100) else 0.0

    if get_switch_on(hass, SWITCH_REMISE_FIDELITE_ACTIVE):
        debut = get_date(hass, DATETIME_DATE_DEBUT_CONTRAT)
        if debut is not None:
            jours = (date.today() - debut).days
            mois = jours / 30.44
            r24 = get_number(hass, NUM_REMISE_FIDELITE_24_MOIS)
            r12 = get_number(hass, NUM_REMISE_FIDELITE_12_MOIS)
            if mois >= 24:
                energie_ht *= 1 - r24 / 100
            elif mois >= 12:
                energie_ht *= 1 - r12 / 100

    energie_verte = get_number(hass, NUM_COUT_ENERGIE_VERTE)
    accise = get_number(hass, NUM_TAXE_ACCISE_SPECIAL)
    cotisation = get_number(hass, NUM_TAXE_COTISATION_ENERGIE)
    raccordement = get_number(hass, NUM_TAXE_REDEVANCE_RACCORDEMENT)

    total_ht = energie_ht + energie_verte + accise + cotisation + raccordement
    return round(total_ht * (1 + tva / 100), 4)


def prix_reseau_ttc(hass: HomeAssistant) -> float:
    """c€/kWh, HTVA->TTC. S'applique au prélèvement BRUT, jamais réduit
    par l'injection."""
    tva = get_number(hass, NUM_TAUX_TVA)
    reseau = get_number(hass, NUM_ORES_COUT_RESEAU_VARIABLE)
    return round(reseau * (1 + tva / 100), 4)


def cout_fixe_journalier(hass: HomeAssistant) -> float:
    """EUR/jour : redevance Luminus (déjà TTC) + terme fixe GRD (HTVA->TTC),
    divisés par 365."""
    tva = get_number(hass, NUM_TAUX_TVA)
    redevance_ttc = get_number(hass, NUM_REDEVANCE_FIXE_ANNUELLE)
    grd = get_number(hass, NUM_ORES_TERME_FIXE_GRD)
    grd_ttc = grd * (1 + tva / 100)
    return round((redevance_ttc + grd_ttc) / 365, 4)


def net_facturable(net_cumule_avant: float, delta_net_du_jour: float) -> tuple[float, float]:
    """Méthode "waterfall" sur le cumul de la période tarifaire : ne
    facture que la portion qui fait dépasser le cumul au-dessus de 0.
    Retourne (cumule_apres, net_facturable_aujourdhui)."""
    cumule_apres = net_cumule_avant + delta_net_du_jour
    facturable = max(cumule_apres, 0) - max(net_cumule_avant, 0)
    return cumule_apres, facturable


def cout_variable(
    hass: HomeAssistant,
    prelevement: float,
    injection: float,
    net_cumule_avant: float,
) -> tuple[float, float]:
    """Retourne (cumule_apres, cout_variable_eur). Énergie+taxes sur le
    net facturable (waterfall), réseau toujours sur le brut en entier."""
    cumule_apres, facturable = net_facturable(net_cumule_avant, prelevement - injection)
    prix_et = prix_energie_taxes_ttc(hass) / 100
    prix_rs = prix_reseau_ttc(hass) / 100
    cout = (facturable * prix_et) + (prelevement * prix_rs)
    return cumule_apres, round(cout, 4)
