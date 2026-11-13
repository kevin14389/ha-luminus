"""Calculs de prix et de coût - portage fidèle des formules Jinja du
package YAML d'origine (déjà validées avec un vrai décompte Luminus et
plusieurs allers-retours de vérification).

Fonctions pures : tout ce dont elles ont besoin est passé en argument
(les tarifs dans un dictionnaire clé -> valeur, la date du jour, les
kWh), elles ne lisent ni Home Assistant ni le stockage.
"""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
from typing import Any

from .const import (
    DATETIME_DATE_DEBUT_CONTRAT,
    NUM_COUT_ENERGIE_VERTE,
    NUM_ORES_COUT_RESEAU_VARIABLE,
    NUM_ORES_TERME_FIXE_GRD,
    NUM_PRIX_ENERGIE_TTC,
    NUM_REDEVANCE_FIXE_ANNUELLE,
    NUM_REMISE_FIDELITE_12_MOIS,
    NUM_REMISE_FIDELITE_24_MOIS,
    NUM_REMISE_FIDELITE_DOMICILIATION,
    NUM_RISTORNO_CREDIT_JOURNALIER,
    NUM_TAUX_TVA,
    NUM_TAXE_ACCISE_SPECIAL,
    NUM_TAXE_COTISATION_ENERGIE,
    NUM_TAXE_REDEVANCE_RACCORDEMENT,
    SWITCH_REMISE_FIDELITE_ACTIVE,
)

Valeurs = Mapping[str, Any]


def _nombre(valeurs: Valeurs, key: str) -> float:
    return float(valeurs.get(key) or 0.0)


def prix_energie_taxes_ttc(valeurs: Valeurs, aujourdhui: date) -> float:
    """c€/kWh, HTVA->TTC. S'applique au prélèvement NET (voir
    cout_variable), pas au brut."""
    tva = _nombre(valeurs, NUM_TAUX_TVA)
    energie_ht = _nombre(valeurs, NUM_PRIX_ENERGIE_TTC) / (1 + tva / 100)

    remise_domiciliation = 0.0
    if valeurs.get(SWITCH_REMISE_FIDELITE_ACTIVE):
        debut = valeurs.get(DATETIME_DATE_DEBUT_CONTRAT)
        if debut is not None:
            mois = (aujourdhui - debut).days / 30.44
            if mois >= 24:
                energie_ht *= 1 - _nombre(valeurs, NUM_REMISE_FIDELITE_24_MOIS) / 100
            elif mois >= 12:
                energie_ht *= 1 - _nombre(valeurs, NUM_REMISE_FIDELITE_12_MOIS) / 100
        # Remise fixe par kWh net : une ligne distincte du pourcentage
        # sur le décompte, les deux s'additionnent.
        remise_domiciliation = _nombre(valeurs, NUM_REMISE_FIDELITE_DOMICILIATION)

    total_ht = (
        energie_ht
        + _nombre(valeurs, NUM_COUT_ENERGIE_VERTE)
        + _nombre(valeurs, NUM_TAXE_ACCISE_SPECIAL)
        + _nombre(valeurs, NUM_TAXE_COTISATION_ENERGIE)
        + _nombre(valeurs, NUM_TAXE_REDEVANCE_RACCORDEMENT)
        - remise_domiciliation
    )
    return round(total_ht * (1 + tva / 100), 4)


def prix_reseau_ttc(valeurs: Valeurs) -> float:
    """c€/kWh, HTVA->TTC. S'applique au prélèvement BRUT, jamais réduit
    par l'injection."""
    tva = _nombre(valeurs, NUM_TAUX_TVA)
    return round(_nombre(valeurs, NUM_ORES_COUT_RESEAU_VARIABLE) * (1 + tva / 100), 4)


def cout_fixe_journalier(valeurs: Valeurs) -> float:
    """EUR/jour : redevance Luminus (déjà TTC) + terme fixe GRD (HTVA->TTC),
    divisés par 365, moins le crédit ristorno journalier (TTC)."""
    tva = _nombre(valeurs, NUM_TAUX_TVA)
    grd_ttc = _nombre(valeurs, NUM_ORES_TERME_FIXE_GRD) * (1 + tva / 100)
    annuel = _nombre(valeurs, NUM_REDEVANCE_FIXE_ANNUELLE) + grd_ttc
    return round(annuel / 365 - _nombre(valeurs, NUM_RISTORNO_CREDIT_JOURNALIER), 4)


def net_facturable(net_cumule_avant: float, delta_net: float) -> tuple[float, float]:
    """Méthode "waterfall" sur le cumul de la période tarifaire : ne
    facture que la portion qui fait dépasser le cumul au-dessus de 0.
    Retourne (cumule_apres, net_facturable)."""
    cumule_apres = net_cumule_avant + delta_net
    facturable = max(cumule_apres, 0) - max(net_cumule_avant, 0)
    return cumule_apres, facturable


def cout_variable(
    valeurs: Valeurs,
    aujourdhui: date,
    prelevement: float,
    injection: float,
    net_cumule_avant: float,
) -> tuple[float, float]:
    """Retourne (cumule_apres, cout_variable_eur). Énergie+taxes sur le
    net facturable (waterfall), réseau toujours sur le brut en entier."""
    cumule_apres, facturable = net_facturable(net_cumule_avant, prelevement - injection)
    cout = (
        facturable * prix_energie_taxes_ttc(valeurs, aujourdhui)
        + prelevement * prix_reseau_ttc(valeurs)
    ) / 100
    return cumule_apres, round(cout, 4)


def resume_mois(
    consommation_kwh: float,
    production_kwh: float,
    prix_energie_taxes_ttc_c: float,
    prix_reseau_ttc_c: float,
    cout_fixe_journalier_eur: float,
    jours_du_mois: int,
    net_cumule_avant: float = 0.0,
) -> tuple[float, dict]:
    """Résumé d'un mois complet à partir de totaux kWh (pas d'un cumul
    jour par jour) : utilisé par le service definir_mois_historique pour
    importer un historique (ex. MyOres).

    Enchaîne avec le cumul de la période tarifaire (net_cumule_avant,
    venant du mois précédent) exactement comme le fait le suivi
    quotidien : un mois très négatif (grosse injection) compense les
    mois précédents de la MÊME période tarifaire au lieu d'être plafonné
    isolément à 0. Traiter chaque mois isolément gonflait le total (cas
    réel : 3206 € au lieu de ~2862 € sur neuf mois).

    Retourne (cumule_apres, résumé) : cumule_apres sert de
    net_cumule_avant au mois suivant, d'où l'obligation d'importer les
    mois dans l'ordre chronologique."""
    cumule_apres, net_facturable_kwh = net_facturable(
        net_cumule_avant, consommation_kwh - production_kwh
    )
    cout_variable_eur = (
        net_facturable_kwh * prix_energie_taxes_ttc_c + consommation_kwh * prix_reseau_ttc_c
    ) / 100
    cout_total_eur = round(cout_variable_eur + cout_fixe_journalier_eur * jours_du_mois, 2)
    resume = {
        "consommation_kwh": round(consommation_kwh, 3),
        "production_kwh": round(production_kwh, 3),
        "solde_net_kwh": round(consommation_kwh - production_kwh, 3),
        "cout_total_eur": cout_total_eur,
        "prix_moyen_kwh": round(cout_total_eur / consommation_kwh, 4) if consommation_kwh else 0.0,
        "prix_energie_taxes_ttc": prix_energie_taxes_ttc_c,
        "prix_reseau_ttc": prix_reseau_ttc_c,
        "cumule_periode_apres": round(cumule_apres, 3),
    }
    return cumule_apres, resume
