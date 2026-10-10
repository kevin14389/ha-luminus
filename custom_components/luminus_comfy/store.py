"""Stockage persisté des accumulateurs.

Utilise le mécanisme Store natif de Home Assistant (fichier JSON dédié
dans .storage/), indépendant du cycle de restauration d'état des
entités. Les input_number du package YAML précédent ont subi une perte
de données à au moins 2 reprises après des mises à jour Home Assistant
sans cause identifiée avec certitude - ce stockage dédié est un pari
raisonnable pour éviter que ça se reproduise, mais rien ne garantit
qu'il est totalement immunisé si la cause était plus profonde (ex. un
problème sur le répertoire .storage lui-même).
"""

from __future__ import annotations

from datetime import date

from homeassistant.core import HomeAssistant
from homeassistant.helpers.storage import Store

from .const import (
    DOMAIN,
    STORE_KEY_ACCUMULATEUR_ANNEE,
    STORE_KEY_ACCUMULATEUR_MOIS,
    STORE_KEY_ANNEE_COURANTE,
    STORE_KEY_CONSO_MOIS_KWH,
    STORE_KEY_DERNIERE_CLOTURE,
    STORE_KEY_HISTORIQUE_MENSUEL,
    STORE_KEY_INJECTION_MOIS_KWH,
    STORE_KEY_MOIS_COURANT,
    STORE_KEY_NET_CUMULE_PERIODE,
    STORE_VERSION,
)

_DEFAULTS = {
    STORE_KEY_ACCUMULATEUR_MOIS: 0.0,
    STORE_KEY_ACCUMULATEUR_ANNEE: 0.0,
    STORE_KEY_NET_CUMULE_PERIODE: 0.0,
    STORE_KEY_MOIS_COURANT: "",
    STORE_KEY_ANNEE_COURANTE: "",
    STORE_KEY_CONSO_MOIS_KWH: 0.0,
    STORE_KEY_INJECTION_MOIS_KWH: 0.0,
    STORE_KEY_HISTORIQUE_MENSUEL: {},
    STORE_KEY_DERNIERE_CLOTURE: "",
}


class LuminusStore:
    """Accumulateurs persistés pour une entrée de config donnée."""

    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store = Store(hass, STORE_VERSION, f"{DOMAIN}_{entry_id}")
        self._data: dict = dict(_DEFAULTS)

    async def async_load(self) -> None:
        stored = await self._store.async_load()
        if stored:
            self._data.update(stored)
        today = date.today()
        # Première utilisation, ou migration depuis le package YAML :
        # initialise les repères de cycle sur le mois/l'année courants
        # pour ne pas déclencher un reset immédiat au premier calcul.
        if not self._data[STORE_KEY_MOIS_COURANT]:
            self._data[STORE_KEY_MOIS_COURANT] = today.strftime("%Y-%m")
        if not self._data[STORE_KEY_ANNEE_COURANTE]:
            self._data[STORE_KEY_ANNEE_COURANTE] = today.strftime("%Y")

    async def _async_save(self) -> None:
        await self._store.async_save(self._data)

    # --- Accumulateur mensuel ---
    @property
    def accumulateur_mois(self) -> float:
        return self._data[STORE_KEY_ACCUMULATEUR_MOIS]

    @property
    def mois_courant(self) -> str:
        return self._data[STORE_KEY_MOIS_COURANT]

    async def async_ajouter_cout_mois(self, montant: float) -> None:
        self._data[STORE_KEY_ACCUMULATEUR_MOIS] = round(
            self._data[STORE_KEY_ACCUMULATEUR_MOIS] + montant, 2
        )
        await self._async_save()

    async def async_reset_mois(self, nouveau_mois: str) -> None:
        self._data[STORE_KEY_ACCUMULATEUR_MOIS] = 0.0
        self._data[STORE_KEY_MOIS_COURANT] = nouveau_mois
        await self._async_save()

    async def async_set_accumulateur_mois(self, valeur: float) -> None:
        """Pour correction manuelle ou restauration suite à un incident."""
        self._data[STORE_KEY_ACCUMULATEUR_MOIS] = round(valeur, 2)
        await self._async_save()

    # --- Accumulateur annuel ---
    @property
    def accumulateur_annee(self) -> float:
        return self._data[STORE_KEY_ACCUMULATEUR_ANNEE]

    @property
    def annee_courante(self) -> str:
        return self._data[STORE_KEY_ANNEE_COURANTE]

    async def async_ajouter_cout_annee(self, montant: float) -> None:
        self._data[STORE_KEY_ACCUMULATEUR_ANNEE] = round(
            self._data[STORE_KEY_ACCUMULATEUR_ANNEE] + montant, 2
        )
        await self._async_save()

    async def async_reset_annee(self, nouvelle_annee: str) -> None:
        self._data[STORE_KEY_ACCUMULATEUR_ANNEE] = 0.0
        self._data[STORE_KEY_ANNEE_COURANTE] = nouvelle_annee
        await self._async_save()

    async def async_set_accumulateur_annee(self, valeur: float) -> None:
        self._data[STORE_KEY_ACCUMULATEUR_ANNEE] = round(valeur, 2)
        await self._async_save()

    # --- Cumul net de la période tarifaire (peut être négatif) ---
    @property
    def net_cumule_periode(self) -> float:
        return self._data[STORE_KEY_NET_CUMULE_PERIODE]

    async def async_set_net_cumule_periode(self, valeur: float) -> None:
        self._data[STORE_KEY_NET_CUMULE_PERIODE] = round(valeur, 3)
        await self._async_save()

    async def async_reset_net_cumule_periode(self) -> None:
        self._data[STORE_KEY_NET_CUMULE_PERIODE] = 0.0
        await self._async_save()

    # --- Cumuls kWh du mois en cours (prélèvement/injection brut), pour
    # alimenter l'archivage automatique mensuel ---
    @property
    def conso_mois_kwh(self) -> float:
        return self._data[STORE_KEY_CONSO_MOIS_KWH]

    @property
    def injection_mois_kwh(self) -> float:
        return self._data[STORE_KEY_INJECTION_MOIS_KWH]

    async def async_ajouter_kwh_mois(self, conso_kwh: float, injection_kwh: float) -> None:
        self._data[STORE_KEY_CONSO_MOIS_KWH] = round(
            self._data[STORE_KEY_CONSO_MOIS_KWH] + conso_kwh, 3
        )
        self._data[STORE_KEY_INJECTION_MOIS_KWH] = round(
            self._data[STORE_KEY_INJECTION_MOIS_KWH] + injection_kwh, 3
        )
        await self._async_save()

    async def async_reset_kwh_mois(self) -> None:
        self._data[STORE_KEY_CONSO_MOIS_KWH] = 0.0
        self._data[STORE_KEY_INJECTION_MOIS_KWH] = 0.0
        await self._async_save()

    # --- Historique mensuel archivé : {"YYYY-MM": {consommation_kwh,
    # production_kwh, cout_total_eur, prix_energie_taxes_ttc,
    # prix_reseau_ttc, source: "auto"|"manuel"}} ---
    @property
    def historique_mensuel(self) -> dict:
        return self._data[STORE_KEY_HISTORIQUE_MENSUEL]

    def historique_mois(self, mois: str) -> dict | None:
        return self._data[STORE_KEY_HISTORIQUE_MENSUEL].get(mois)

    async def async_set_historique_mois(self, mois: str, enregistrement: dict) -> None:
        self._data[STORE_KEY_HISTORIQUE_MENSUEL][mois] = enregistrement
        await self._async_save()

    # --- Dernier jour clôturé avec succès (rattrapage au démarrage si
    # l'intégration était arrêtée pile au passage de minuit) ---
    @property
    def derniere_cloture(self) -> str:
        return self._data[STORE_KEY_DERNIERE_CLOTURE]

    async def async_set_derniere_cloture(self, valeur: str) -> None:
        self._data[STORE_KEY_DERNIERE_CLOTURE] = valeur
        await self._async_save()
