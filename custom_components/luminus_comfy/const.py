"""Constantes pour l'intégration Luminus Comfy Électricité.

Valeurs par défaut validées contre un vrai décompte annuel Luminus
(01.12.2024-30.11.2025) - voir le README du dépôt pour la méthode de
calcul. Spécifique au contrat "Luminus Comfy Electricité", région
Wallonie, réseau ELIA + ORES Luxembourg, régime prosumer sans
compensation d'injection (confirmé par Luminus, pas de rachat de
l'excédent avant 2030 minimum pour ce contrat).
"""

from __future__ import annotations

DOMAIN = "luminus_comfy"

# --- Clés de configuration (config_flow) : les 4 capteurs du compteur
# communicant. "delivered" = prélevé du réseau, "returned" = injecté.
CONF_DELIVERED_PEAK = "delivered_peak_entity"
CONF_DELIVERED_OFFPEAK = "delivered_offpeak_entity"
CONF_RETURNED_PEAK = "returned_peak_entity"
CONF_RETURNED_OFFPEAK = "returned_offpeak_entity"

# --- Clés des entités "number" (tarifs modifiables) ---
NUM_PRIX_ENERGIE_TTC = "prix_energie_ttc"
NUM_REDEVANCE_FIXE_ANNUELLE = "redevance_fixe_annuelle"
NUM_COUT_ENERGIE_VERTE = "cout_energie_verte"
NUM_ORES_COUT_RESEAU_VARIABLE = "ores_cout_reseau_variable"
NUM_ORES_TERME_FIXE_GRD = "ores_terme_fixe_grd"
NUM_TAXE_ACCISE_SPECIAL = "taxe_accise_special"
NUM_TAXE_COTISATION_ENERGIE = "taxe_cotisation_energie"
NUM_TAXE_REDEVANCE_RACCORDEMENT = "taxe_redevance_raccordement"
NUM_TAUX_TVA = "taux_tva"
NUM_REMISE_FIDELITE_12_MOIS = "remise_fidelite_12_mois"
NUM_REMISE_FIDELITE_24_MOIS = "remise_fidelite_24_mois"
NUM_PRIX_ENERGIE_TTC_PROCHAIN = "prix_energie_ttc_prochain"
NUM_REMISE_FIDELITE_DOMICILIATION = "remise_fidelite_domiciliation_kwh"
NUM_RISTORNO_CREDIT_JOURNALIER = "ristorno_credit_journalier"
NUM_CORRECTION_MANUELLE = "correction_manuelle"
NUM_CORRECTION_MOIS = "correction_manuelle_mois"
NUM_CORRECTION_ANNEE = "correction_manuelle_annee"

# (clé, nom, unité, min, max, step, valeur par défaut)
NUMBER_DEFINITIONS: list[tuple[str, str, str, float, float, float, float]] = [
    (NUM_PRIX_ENERGIE_TTC, "Prix énergie fournie (TTC)", "c€/kWh", 0, 100, 0.01, 18.73),
    (NUM_REDEVANCE_FIXE_ANNUELLE, "Redevance fixe annuelle (TTC)", "€/an", 0, 500, 0.01, 65.00),
    (NUM_COUT_ENERGIE_VERTE, "Coûts énergie verte (HTVA)", "c€/kWh", 0, 10, 0.0001, 2.8281),
    (NUM_ORES_COUT_RESEAU_VARIABLE, "ELIA + ORES - Coût réseau combiné (HTVA)", "c€/kWh", 0, 50, 0.01, 17.61),
    (NUM_ORES_TERME_FIXE_GRD, "ORES - Terme fixe GRD (HTVA)", "€/an", 0, 100, 0.01, 13.06),
    (NUM_TAXE_ACCISE_SPECIAL, "Taxe - Droit d'accise spécial (HTVA)", "c€/kWh", 0, 20, 0.0001, 4.7480),
    (NUM_TAXE_COTISATION_ENERGIE, "Taxe - Cotisation sur l'énergie (HTVA)", "c€/kWh", 0, 5, 0.0001, 0.1927),
    (NUM_TAXE_REDEVANCE_RACCORDEMENT, "Taxe - Redevance de raccordement (HTVA)", "c€/kWh", 0, 5, 0.0001, 0.0750),
    (NUM_TAUX_TVA, "Taux de TVA électricité", "%", 0, 25, 0.5, 6),
    (NUM_REMISE_FIDELITE_12_MOIS, "Remise fidélité après 12 mois", "%", 0, 50, 0.5, 5),
    (NUM_REMISE_FIDELITE_24_MOIS, "Remise fidélité après 24 mois", "%", 0, 50, 0.5, 10),
    (NUM_PRIX_ENERGIE_TTC_PROCHAIN, "Prochain prix énergie programmé (TTC)", "c€/kWh", 0, 100, 0.01, 0),
    (NUM_REMISE_FIDELITE_DOMICILIATION, "Remise fidélité domiciliation (HTVA)", "c€/kWh", 0, 5, 0.0001, 0),
    (NUM_RISTORNO_CREDIT_JOURNALIER, "Crédit ristorno journalier (TTC)", "EUR/jour", 0, 5, 0.0001, 0),
    (NUM_CORRECTION_MANUELLE, "Correction manuelle à appliquer (mois + année)", "EUR", -10000, 10000, 0.01, 0),
    (NUM_CORRECTION_MOIS, "Correction manuelle - mois seul", "EUR", -10000, 10000, 0.01, 0),
    (NUM_CORRECTION_ANNEE, "Correction manuelle - année seule", "EUR", -10000, 10000, 0.01, 0),
]

# --- Switches (remplacent les input_boolean) ---
SWITCH_REMISE_FIDELITE_ACTIVE = "remise_fidelite_active"
SWITCH_CHANGEMENT_PRIX_PROGRAMME = "changement_prix_programme"

# --- Datetimes (remplacent les input_datetime) ---
DATETIME_DATE_DEBUT_CONTRAT = "date_debut_contrat"
DATETIME_PRIX_ENERGIE_DATE_EFFET = "prix_energie_date_effet"

# --- Button ---
BUTTON_APPLIQUER_CORRECTION_MANUELLE = "appliquer_correction_manuelle"
BUTTON_APPLIQUER_CORRECTION_MOIS = "appliquer_correction_mois"
BUTTON_APPLIQUER_CORRECTION_ANNEE = "appliquer_correction_annee"

# --- Services ---
SERVICE_DEFINIR_MOIS_HISTORIQUE = "definir_mois_historique"
ATTR_MOIS = "mois"
ATTR_CONSOMMATION_KWH = "consommation_kwh"
ATTR_PRODUCTION_KWH = "production_kwh"
SERVICE_DEFINIR_CUMUL_PERIODE = "definir_cumul_periode"
ATTR_CUMUL_KWH = "cumul_kwh"

# --- Stockage persisté (voir store.py) ---
STORE_VERSION = 1
DELAI_SAUVEGARDE_S = 300

# Signal dispatcher : l'état interne ou un tarif a changé, les entités
# doivent republier leur valeur.
SIGNAL_MAJ = "luminus_comfy_maj_{}"

# Un compteur source qui redescend sous cette fraction de sa dernière
# valeur a commencé un nouveau cycle ; une baisse plus faible est du
# bruit de mesure (même seuil que les statistiques de Home Assistant).
SEUIL_NOUVEAU_CYCLE = 0.9

# Heure de clôture quotidienne
DAILY_CLOSEOUT_HOUR = 0
DAILY_CLOSEOUT_MINUTE = 0
DAILY_CLOSEOUT_SECOND = 30

MOIS_FR = [
    "Janvier", "Février", "Mars", "Avril", "Mai", "Juin",
    "Juillet", "Août", "Septembre", "Octobre", "Novembre", "Décembre",
]
