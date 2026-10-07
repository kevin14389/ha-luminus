"""Capteurs calculés : prélèvement/injection combinés, prix, coûts.

Chaque capteur recalcule sa valeur à la lecture (propriété native_value),
à partir des états actuels des 4 capteurs sources, des entités number/
switch/date, et du Store persisté - jamais depuis l'état d'un AUTRE
capteur Luminus. Ça évite tout décalage d'un cycle entre capteurs
dépendants, un problème propre aux templates Home Assistant chaînés.
"""

from __future__ import annotations

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity, SensorStateClass
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_interval
from homeassistant.util import dt as dt_util
from datetime import timedelta

from . import calculations as calc
from .const import (
    CONF_DELIVERED_OFFPEAK,
    CONF_DELIVERED_PEAK,
    CONF_RETURNED_OFFPEAK,
    CONF_RETURNED_PEAK,
    DOMAIN,
    MOIS_FR,
    NUMBER_DEFINITIONS,
    SWITCH_CHANGEMENT_PRIX_PROGRAMME,
    SWITCH_REMISE_FIDELITE_ACTIVE,
    DATETIME_DATE_DEBUT_CONTRAT,
    DATETIME_PRIX_ENERGIE_DATE_EFFET,
)
from .entity import device_info_for_entry
from .store import LuminusStore


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    conf = {**entry.data, **entry.options}
    store: LuminusStore = hass.data[DOMAIN][entry.entry_id]["store"]

    entities: list[LuminusSensorBase] = [
        PrelevementTotalSensor(entry, conf),
        InjectionTotaleSensor(entry, conf),
        ConsoNetteJourSensor(entry, conf),
        PrixEnergieTaxesSensor(entry, conf),
        PrixReseauSensor(entry, conf),
        PrixKwhTtcSensor(entry, conf),
        PrixKwhEurSensor(entry, conf),
        CoutFixeJournalierSensor(entry, conf),
        CoutVariableJourSensor(entry, conf, store),
        CoutTotalJourSensor(entry, conf, store),
        CoutTotalMoisSensor(entry, conf, store),
        CoutTotalAnneeSensor(entry, conf, store),
        HistoriqueMensuelSensor(entry, conf, store),
    ]
    async_add_entities(entities)

    # Un seul listener central : tout changement d'un capteur source,
    # d'un tarif, d'un interrupteur ou d'une date déclenche un
    # recalcul (lecture fraîche) de TOUS les capteurs Luminus, plus un
    # rafraîchissement périodique pour les calculs basés sur la date du
    # jour (remise fidélité).
    tracked = {
        conf.get(CONF_DELIVERED_PEAK),
        conf.get(CONF_DELIVERED_OFFPEAK),
        conf.get(CONF_RETURNED_PEAK),
        conf.get(CONF_RETURNED_OFFPEAK),
        f"switch.luminus_{SWITCH_REMISE_FIDELITE_ACTIVE}",
        f"switch.luminus_{SWITCH_CHANGEMENT_PRIX_PROGRAMME}",
        f"date.luminus_{DATETIME_DATE_DEBUT_CONTRAT}",
        f"date.luminus_{DATETIME_PRIX_ENERGIE_DATE_EFFET}",
        *(f"number.luminus_{key}" for key, *_ in NUMBER_DEFINITIONS),
    }
    tracked.discard(None)

    @callback
    def _refresh_all(_event=None) -> None:
        for ent in entities:
            if ent.hass is not None:
                ent.async_write_ha_state()

    entry.async_on_unload(
        async_track_state_change_event(hass, list(tracked), _refresh_all)
    )
    entry.async_on_unload(
        async_track_time_interval(hass, _refresh_all, timedelta(minutes=5))
    )


class LuminusSensorBase(SensorEntity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(self, entry: ConfigEntry, conf: dict, key: str, name: str) -> None:
        self._entry = entry
        self._conf = conf
        self._attr_unique_id = f"{entry.entry_id}_sensor_{key}"
        self._attr_suggested_object_id = f"luminus_{key}"
        self._attr_name = name
        self._attr_device_info = device_info_for_entry(entry)


class PrelevementTotalSensor(LuminusSensorBase):
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "kWh"
    _attr_icon = "mdi:transmission-tower-import"

    def __init__(self, entry: ConfigEntry, conf: dict) -> None:
        super().__init__(entry, conf, "conso_jour", "Prélèvement")

    @property
    def native_value(self) -> float:
        return calc.prelevement_total(
            self.hass, self._conf.get(CONF_DELIVERED_PEAK), self._conf.get(CONF_DELIVERED_OFFPEAK)
        )


class InjectionTotaleSensor(LuminusSensorBase):
    _attr_device_class = SensorDeviceClass.ENERGY
    _attr_state_class = SensorStateClass.TOTAL
    _attr_native_unit_of_measurement = "kWh"
    _attr_icon = "mdi:transmission-tower-export"

    def __init__(self, entry: ConfigEntry, conf: dict) -> None:
        super().__init__(entry, conf, "injection_jour", "Injection")

    @property
    def native_value(self) -> float:
        return calc.injection_totale(
            self.hass, self._conf.get(CONF_RETURNED_PEAK), self._conf.get(CONF_RETURNED_OFFPEAK)
        )


class ConsoNetteJourSensor(LuminusSensorBase):
    _attr_native_unit_of_measurement = "kWh"
    _attr_icon = "mdi:transmission-tower"

    def __init__(self, entry: ConfigEntry, conf: dict) -> None:
        super().__init__(entry, conf, "conso_nette_jour", "Solde net du jour")

    @property
    def native_value(self) -> float:
        prelevement = calc.prelevement_total(
            self.hass, self._conf.get(CONF_DELIVERED_PEAK), self._conf.get(CONF_DELIVERED_OFFPEAK)
        )
        injection = calc.injection_totale(
            self.hass, self._conf.get(CONF_RETURNED_PEAK), self._conf.get(CONF_RETURNED_OFFPEAK)
        )
        return round(prelevement - injection, 3)


class PrixEnergieTaxesSensor(LuminusSensorBase):
    _attr_native_unit_of_measurement = "c€/kWh"
    _attr_icon = "mdi:cash-multiple"

    def __init__(self, entry: ConfigEntry, conf: dict) -> None:
        super().__init__(entry, conf, "prix_energie_taxes_ttc", "Prix énergie + taxes (TTC)")

    @property
    def native_value(self) -> float:
        return calc.prix_energie_taxes_ttc(self.hass)


class PrixReseauSensor(LuminusSensorBase):
    _attr_native_unit_of_measurement = "c€/kWh"
    _attr_icon = "mdi:transmission-tower"

    def __init__(self, entry: ConfigEntry, conf: dict) -> None:
        super().__init__(entry, conf, "prix_reseau_ttc", "Prix réseau (TTC)")

    @property
    def native_value(self) -> float:
        return calc.prix_reseau_ttc(self.hass)


class PrixKwhTtcSensor(LuminusSensorBase):
    """Prix informatif "tout compris" (somme des deux taux) - utile pour
    comparer ou brancher sur le Tableau de bord Énergie, ne sert pas au
    calcul du coût réel (voir CoutVariableJourSensor)."""

    _attr_native_unit_of_measurement = "c€/kWh"
    _attr_icon = "mdi:cash-multiple"

    def __init__(self, entry: ConfigEntry, conf: dict) -> None:
        super().__init__(entry, conf, "prix_kwh_ttc", "Prix kWh (TTC, indicatif)")

    @property
    def native_value(self) -> float:
        return round(calc.prix_energie_taxes_ttc(self.hass) + calc.prix_reseau_ttc(self.hass), 4)


class PrixKwhEurSensor(LuminusSensorBase):
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "EUR/kWh"
    _attr_icon = "mdi:currency-eur"

    def __init__(self, entry: ConfigEntry, conf: dict) -> None:
        super().__init__(entry, conf, "prix_kwh_eur", "Prix kWh (EUR, indicatif)")

    @property
    def native_value(self) -> float:
        total = calc.prix_energie_taxes_ttc(self.hass) + calc.prix_reseau_ttc(self.hass)
        return round(total / 100, 6)


class CoutFixeJournalierSensor(LuminusSensorBase):
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "EUR"
    _attr_icon = "mdi:calendar-today"

    def __init__(self, entry: ConfigEntry, conf: dict) -> None:
        super().__init__(entry, conf, "cout_fixe_journalier", "Coût fixe journalier")

    @property
    def native_value(self) -> float:
        return calc.cout_fixe_journalier(self.hass)


class CoutVariableJourSensor(LuminusSensorBase):
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "EUR"
    _attr_icon = "mdi:flash"

    def __init__(self, entry: ConfigEntry, conf: dict, store: LuminusStore) -> None:
        super().__init__(entry, conf, "cout_variable_jour", "Coût variable du jour")
        self._store = store

    @property
    def native_value(self) -> float:
        prelevement = calc.prelevement_total(
            self.hass, self._conf.get(CONF_DELIVERED_PEAK), self._conf.get(CONF_DELIVERED_OFFPEAK)
        )
        injection = calc.injection_totale(
            self.hass, self._conf.get(CONF_RETURNED_PEAK), self._conf.get(CONF_RETURNED_OFFPEAK)
        )
        _cumule_apres, cout = calc.cout_variable(
            self.hass, prelevement, injection, self._store.net_cumule_periode
        )
        return cout


class CoutTotalJourSensor(LuminusSensorBase):
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "EUR"
    _attr_icon = "mdi:cash-check"

    def __init__(self, entry: ConfigEntry, conf: dict, store: LuminusStore) -> None:
        super().__init__(entry, conf, "cout_total_jour", "Coût total du jour")
        self._store = store

    @property
    def native_value(self) -> float:
        prelevement = calc.prelevement_total(
            self.hass, self._conf.get(CONF_DELIVERED_PEAK), self._conf.get(CONF_DELIVERED_OFFPEAK)
        )
        injection = calc.injection_totale(
            self.hass, self._conf.get(CONF_RETURNED_PEAK), self._conf.get(CONF_RETURNED_OFFPEAK)
        )
        _cumule_apres, variable = calc.cout_variable(
            self.hass, prelevement, injection, self._store.net_cumule_periode
        )
        fixe = calc.cout_fixe_journalier(self.hass)
        return round(variable + fixe, 4)


class CoutTotalMoisSensor(LuminusSensorBase):
    """Somme des jours déjà clôturés ce mois-ci (figés au prix du jour,
    voir __init__.py) + la progression du jour en cours."""

    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "EUR"
    _attr_icon = "mdi:cash-check"

    def __init__(self, entry: ConfigEntry, conf: dict, store: LuminusStore) -> None:
        super().__init__(entry, conf, "cout_total_mois", "Coût du mois (estimé)")
        self._store = store

    @property
    def native_value(self) -> float:
        prelevement = calc.prelevement_total(
            self.hass, self._conf.get(CONF_DELIVERED_PEAK), self._conf.get(CONF_DELIVERED_OFFPEAK)
        )
        injection = calc.injection_totale(
            self.hass, self._conf.get(CONF_RETURNED_PEAK), self._conf.get(CONF_RETURNED_OFFPEAK)
        )
        _cumule_apres, variable = calc.cout_variable(
            self.hass, prelevement, injection, self._store.net_cumule_periode
        )
        fixe = calc.cout_fixe_journalier(self.hass)
        aujourdhui = variable + fixe
        return round(self._store.accumulateur_mois + aujourdhui, 2)


class CoutTotalAnneeSensor(LuminusSensorBase):
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "EUR"
    _attr_icon = "mdi:cash-check"

    def __init__(self, entry: ConfigEntry, conf: dict, store: LuminusStore) -> None:
        super().__init__(entry, conf, "cout_total_annee", "Coût de l'année (estimé)")
        self._store = store

    @property
    def native_value(self) -> float:
        prelevement = calc.prelevement_total(
            self.hass, self._conf.get(CONF_DELIVERED_PEAK), self._conf.get(CONF_DELIVERED_OFFPEAK)
        )
        injection = calc.injection_totale(
            self.hass, self._conf.get(CONF_RETURNED_PEAK), self._conf.get(CONF_RETURNED_OFFPEAK)
        )
        _cumule_apres, variable = calc.cout_variable(
            self.hass, prelevement, injection, self._store.net_cumule_periode
        )
        fixe = calc.cout_fixe_journalier(self.hass)
        aujourdhui = variable + fixe
        return round(self._store.accumulateur_annee + aujourdhui, 2)


class HistoriqueMensuelSensor(LuminusSensorBase):
    """Historique mensuel (mois archivés automatiquement à la clôture +
    mois saisis/corrigés via le service definir_mois_historique). L'état
    est le nombre de mois enregistrés ; le détail est dans l'attribut
    "mois", exploitable depuis une carte Markdown - voir le README pour
    un exemple de carte."""

    _attr_icon = "mdi:calendar-text"
    _attr_native_unit_of_measurement = "mois"

    def __init__(self, entry: ConfigEntry, conf: dict, store: LuminusStore) -> None:
        super().__init__(entry, conf, "historique_mensuel", "Historique mensuel")
        self._store = store

    @property
    def native_value(self) -> int:
        return len(self._store.historique_mensuel)

    @property
    def extra_state_attributes(self) -> dict:
        mois_tries = sorted(self._store.historique_mensuel.items())
        liste = []
        for cle, enregistrement in mois_tries:
            annee, mois_num = (int(p) for p in cle.split("-"))
            liste.append(
                {
                    "mois": cle,
                    "mois_label": f"{MOIS_FR[mois_num - 1]} {annee}",
                    **enregistrement,
                }
            )
        return {"mois": liste, "total_annee": self._total_annee()}

    def _total_annee(self) -> dict:
        """Agrège les mois archivés de l'année en cours + la progression
        du mois en cours (pas encore archivé) - toujours à jour, pas
        seulement jusqu'au dernier mois clôturé."""
        annee_en_cours = str(dt_util.now().year)
        mois_en_cours = dt_util.now().strftime("%Y-%m")

        conso = 0.0
        production = 0.0
        cout_archive = 0.0
        for cle, enregistrement in self._store.historique_mensuel.items():
            # Le mois en cours est exclu de la boucle : sa contribution
            # vient du cumul live ci-dessous, pas de l'archive (même si
            # une saisie manuelle existe déjà pour ce mois, pour éviter
            # de la compter deux fois).
            if cle.startswith(annee_en_cours) and cle != mois_en_cours:
                conso += enregistrement.get("consommation_kwh", 0.0)
                production += enregistrement.get("production_kwh", 0.0)
                cout_archive += enregistrement.get("cout_total_eur", 0.0)

        # Mois en cours : jours déjà clôturés (store) + la journée en cours (live).
        # Utilise accumulateur_mois (remis à zéro chaque mois), pas
        # accumulateur_annee : celui-ci couvre toute l'année glissante et
        # compterait les mois déjà archivés ci-dessus une seconde fois.
        prelevement_jour = calc.prelevement_total(
            self.hass, self._conf.get(CONF_DELIVERED_PEAK), self._conf.get(CONF_DELIVERED_OFFPEAK)
        )
        injection_jour = calc.injection_totale(
            self.hass, self._conf.get(CONF_RETURNED_PEAK), self._conf.get(CONF_RETURNED_OFFPEAK)
        )
        conso += self._store.conso_mois_kwh + prelevement_jour
        production += self._store.injection_mois_kwh + injection_jour

        _cumule_apres, variable = calc.cout_variable(
            self.hass, prelevement_jour, injection_jour, self._store.net_cumule_periode
        )
        cout_total_eur = round(
            cout_archive + self._store.accumulateur_mois + variable + calc.cout_fixe_journalier(self.hass), 2
        )
        prix_moyen = round(cout_total_eur / conso, 4) if conso else 0.0

        return {
            "consommation_kwh": round(conso, 3),
            "production_kwh": round(production, 3),
            "solde_net_kwh": round(conso - production, 3),
            "cout_total_eur": cout_total_eur,
            "prix_moyen_kwh": prix_moyen,
        }
