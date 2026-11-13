"""État persisté de l'intégration.

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

from dataclasses import asdict, dataclass, field, fields

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.storage import Store

from .const import DELAI_SAUVEGARDE_S, DOMAIN, STORE_VERSION


@dataclass
class Etat:
    """Les noms de champs sont les clés du fichier .storage : les
    renommer ferait perdre les données des installations existantes."""

    # Coût des jours déjà clôturés du mois en cours (EUR).
    accumulateur_mois: float = 0.0
    # kWh prélevés/injectés des jours déjà clôturés du mois en cours.
    conso_mois_kwh: float = 0.0
    injection_mois_kwh: float = 0.0
    # Décalage manuel du total annuel (EUR), remis à 0 au changement d'année.
    correction_annee: float = 0.0
    # Solde net (kWh, peut être négatif) depuis le dernier changement de
    # prix, jours clôturés uniquement.
    net_cumule_periode: float = 0.0
    mois_courant: str = ""  # "YYYY-MM" du mois en cours d'accumulation
    annee_courante: str = ""  # "YYYY"
    derniere_cloture: str = ""  # "YYYY-MM-DD" du dernier jour clôturé
    # {"YYYY-MM": {...}} - voir coordinateur.py pour le contenu.
    historique_mensuel: dict[str, dict] = field(default_factory=dict)
    # kWh mesurés depuis la dernière clôture, pas encore clôturés.
    prelevement_en_cours: float = 0.0
    injection_en_cours: float = 0.0
    # Dernier relevé de chaque capteur source :
    # {entity_id: {"valeur": kWh, "reset": last_reset ou None}}.
    releves: dict[str, dict] = field(default_factory=dict)
    # Faux tant que les capteurs sources n'ont jamais été relevés.
    initialise: bool = False


class LuminusStore:
    def __init__(self, hass: HomeAssistant, entry_id: str) -> None:
        self._store: Store[dict] = Store(hass, STORE_VERSION, f"{DOMAIN}_{entry_id}")
        self._sauvegarde_planifiee = False
        self.etat = Etat()

    async def async_load(self) -> bool:
        """Retourne False si aucun fichier n'existait."""
        stored = await self._store.async_load()
        if stored is None:
            return False
        connus = {f.name for f in fields(Etat)}
        self.etat = Etat(**{k: v for k, v in stored.items() if k in connus})
        return True

    async def async_save(self) -> None:
        self._sauvegarde_planifiee = False
        await self._store.async_save(asdict(self.etat))

    @callback
    def async_planifier_sauvegarde(self) -> None:
        """Au plus une écriture par DELAI_SAUVEGARDE_S, même si les
        capteurs sources changent toutes les secondes. (Appeler
        async_delay_save à chaque changement repousserait l'écriture
        indéfiniment.)"""
        if self._sauvegarde_planifiee:
            return
        self._sauvegarde_planifiee = True
        self._store.async_delay_save(self._donnees_a_sauver, DELAI_SAUVEGARDE_S)

    @callback
    def _donnees_a_sauver(self) -> dict:
        self._sauvegarde_planifiee = False
        return asdict(self.etat)
