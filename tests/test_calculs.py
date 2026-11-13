"""Formules de prix et de coût (fonctions pures, sans Home Assistant)."""

from __future__ import annotations

from datetime import date

import pytest

from custom_components.luminus_comfy import calculations as calc
from custom_components.luminus_comfy.const import (
    DATETIME_DATE_DEBUT_CONTRAT,
    NUM_ORES_COUT_RESEAU_VARIABLE,
    NUM_ORES_TERME_FIXE_GRD,
    NUM_PRIX_ENERGIE_TTC,
    NUM_REMISE_FIDELITE_DOMICILIATION,
    NUM_RISTORNO_CREDIT_JOURNALIER,
    NUMBER_DEFINITIONS,
    SWITCH_REMISE_FIDELITE_ACTIVE,
)

AUJOURDHUI = date(2026, 11, 12)


@pytest.fixture
def defauts() -> dict:
    return {key: defaut for key, *_reste, defaut in NUMBER_DEFINITIONS}


def test_prix_par_defaut(defauts) -> None:
    assert calc.prix_energie_taxes_ttc(defauts, AUJOURDHUI) == 27.0444
    assert calc.prix_reseau_ttc(defauts) == 18.6666
    assert calc.cout_fixe_journalier(defauts) == 0.216


def test_prix_reel_verifie_a_la_main(defauts) -> None:
    """Réglages de l'installation réelle (octobre 2026) : le prix
    affiché, 39,68 c€/kWh, a été recalculé à la main depuis le décompte."""
    valeurs = {
        **defauts,
        NUM_PRIX_ENERGIE_TTC: 19.05,
        NUM_ORES_COUT_RESEAU_VARIABLE: 13.89,
        NUM_ORES_TERME_FIXE_GRD: 13.30,
        NUM_REMISE_FIDELITE_DOMICILIATION: 0.4717,
        SWITCH_REMISE_FIDELITE_ACTIVE: True,
        DATETIME_DATE_DEBUT_CONTRAT: date(2023, 9, 23),
    }
    energie = calc.prix_energie_taxes_ttc(valeurs, AUJOURDHUI)
    reseau = calc.prix_reseau_ttc(valeurs)
    assert energie == 24.9594
    assert reseau == 14.7234
    assert round(energie + reseau, 2) == 39.68


@pytest.mark.parametrize(
    ("debut", "attendu"),
    [
        (None, 27.0444),  # date de début inconnue : pas de remise en %
        (date(2026, 6, 1), 27.0444),  # moins de 12 mois
        (date(2025, 6, 1), 26.1079),  # 12 à 24 mois : -5 % sur l'énergie
        (date(2023, 9, 23), 25.1714),  # plus de 24 mois : -10 %
    ],
)
def test_remise_fidelite_selon_anciennete(defauts, debut, attendu) -> None:
    valeurs = {**defauts, SWITCH_REMISE_FIDELITE_ACTIVE: True, DATETIME_DATE_DEBUT_CONTRAT: debut}
    assert calc.prix_energie_taxes_ttc(valeurs, AUJOURDHUI) == attendu


def test_remise_ignoree_si_interrupteur_eteint(defauts) -> None:
    valeurs = {
        **defauts,
        SWITCH_REMISE_FIDELITE_ACTIVE: False,
        DATETIME_DATE_DEBUT_CONTRAT: date(2023, 9, 23),
        NUM_REMISE_FIDELITE_DOMICILIATION: 0.4717,
    }
    assert calc.prix_energie_taxes_ttc(valeurs, AUJOURDHUI) == 27.0444


def test_ristorno_deduit_du_cout_fixe(defauts) -> None:
    valeurs = {**defauts, NUM_RISTORNO_CREDIT_JOURNALIER: 0.1}
    assert calc.cout_fixe_journalier(valeurs) == 0.116


def test_net_facturable_ne_facture_que_ce_qui_depasse_zero() -> None:
    assert calc.net_facturable(0, 10) == (10, 10)
    assert calc.net_facturable(0, -45) == (-45, 0)
    assert calc.net_facturable(-45, 20) == (-25, 0)
    assert calc.net_facturable(-5, 20) == (15, 15)
    # Un jour très producteur rembourse l'énergie déjà facturée dans la période.
    assert calc.net_facturable(30, -50) == (-20, -30)


def test_exemple_des_trois_jours(defauts) -> None:
    """J1 : 5 kWh prélevés / 50 injectés, J2 idem, J3 : 20 / 0. Le cumul
    de la période reste négatif : 0 € d'énergie et de taxes sur les
    trois jours, seul le réseau est dû sur les 30 kWh prélevés."""
    cumul, total = 0.0, 0.0
    for prelevement, injection in [(5, 50), (5, 50), (20, 0)]:
        cumul, cout = calc.cout_variable(defauts, AUJOURDHUI, prelevement, injection, cumul)
        total += cout
    assert cumul == -70
    assert total == pytest.approx(30 * 18.6666 / 100, abs=0.001)


def test_cout_variable_net_pour_energie_brut_pour_reseau(defauts) -> None:
    cumul, cout = calc.cout_variable(defauts, AUJOURDHUI, 10, 4, 100)
    assert cumul == 106
    assert cout == round((6 * 27.0444 + 10 * 18.6666) / 100, 4)


def test_resume_mois_enchaine_le_cumul() -> None:
    """Un mois d'été à solde négatif compense les mois précédents au lieu
    d'être plafonné à 0 pour lui-même."""
    cumul, janvier = calc.resume_mois(1000, 100, 25.0, 15.0, 0.2, 31)
    assert cumul == 900
    assert janvier["cout_total_eur"] == round(900 * 0.25 + 1000 * 0.15 + 0.2 * 31, 2)

    cumul, juillet = calc.resume_mois(300, 700, 25.0, 15.0, 0.2, 31, cumul)
    assert cumul == 500
    assert juillet["cumule_periode_apres"] == 500
    assert juillet["solde_net_kwh"] == -400
    assert juillet["cout_total_eur"] == round(-400 * 0.25 + 300 * 0.15 + 0.2 * 31, 2)


def test_resume_mois_sans_consommation() -> None:
    _cumul, resume = calc.resume_mois(0, 0, 25.0, 15.0, 0.2, 30)
    assert resume["prix_moyen_kwh"] == 0.0
    assert resume["cout_total_eur"] == 6.0
