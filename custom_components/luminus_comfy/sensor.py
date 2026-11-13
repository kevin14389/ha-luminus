"""Capteurs calculés : prélèvement/injection du jour, prix, coûts,
historique mensuel.

Chaque capteur recalcule sa valeur à la lecture à partir du coordinateur
(compteurs en cours, tarifs, état persisté) - jamais depuis l'état d'un
AUTRE capteur Luminus. Ça évite tout décalage d'un cycle entre capteurs
dépendants, un problème propre aux templates Home Assistant chaînés.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import calculations as calc
from .const import MOIS_FR
from .coordinateur import LuminusCoordinateur
from .entity import LuminusEntity


@dataclass(frozen=True, kw_only=True)
class LuminusSensorDescription(SensorEntityDescription):
    valeur: Callable[[LuminusCoordinateur], float | int]


def _prix_energie_taxes(c: LuminusCoordinateur) -> float:
    return calc.prix_energie_taxes_ttc(c.valeurs, c.aujourdhui())


def _prix_kwh(c: LuminusCoordinateur) -> float:
    return _prix_energie_taxes(c) + calc.prix_reseau_ttc(c.valeurs)


SENSORS: tuple[LuminusSensorDescription, ...] = (
    LuminusSensorDescription(
        key="conso_jour",
        name="Prélèvement",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        icon="mdi:transmission-tower-import",
        valeur=lambda c: round(c.etat.prelevement_en_cours, 3),
    ),
    LuminusSensorDescription(
        key="injection_jour",
        name="Injection",
        device_class=SensorDeviceClass.ENERGY,
        state_class=SensorStateClass.TOTAL,
        native_unit_of_measurement="kWh",
        icon="mdi:transmission-tower-export",
        valeur=lambda c: round(c.etat.injection_en_cours, 3),
    ),
    LuminusSensorDescription(
        key="conso_nette_jour",
        name="Solde net du jour",
        native_unit_of_measurement="kWh",
        icon="mdi:transmission-tower",
        valeur=lambda c: round(c.etat.prelevement_en_cours - c.etat.injection_en_cours, 3),
    ),
    LuminusSensorDescription(
        key="net_cumule_periode",
        name="Cumul net de la période tarifaire",
        native_unit_of_measurement="kWh",
        icon="mdi:scale-balance",
        valeur=lambda c: c.etat.net_cumule_periode,
    ),
    LuminusSensorDescription(
        key="prix_energie_taxes_ttc",
        name="Prix énergie + taxes (TTC)",
        native_unit_of_measurement="c€/kWh",
        icon="mdi:cash-multiple",
        valeur=_prix_energie_taxes,
    ),
    LuminusSensorDescription(
        key="prix_reseau_ttc",
        name="Prix réseau (TTC)",
        native_unit_of_measurement="c€/kWh",
        icon="mdi:transmission-tower",
        valeur=lambda c: calc.prix_reseau_ttc(c.valeurs),
    ),
    # Prix "tout compris" (somme des deux taux), purement informatif :
    # le coût réel applique chaque taux à sa propre base (net / brut).
    LuminusSensorDescription(
        key="prix_kwh_ttc",
        name="Prix kWh (TTC, indicatif)",
        native_unit_of_measurement="c€/kWh",
        icon="mdi:cash-multiple",
        valeur=lambda c: round(_prix_kwh(c), 4),
    ),
    LuminusSensorDescription(
        key="prix_kwh_eur",
        name="Prix kWh (EUR, indicatif)",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR/kWh",
        icon="mdi:currency-eur",
        valeur=lambda c: round(_prix_kwh(c) / 100, 6),
    ),
    LuminusSensorDescription(
        key="cout_fixe_journalier",
        name="Coût fixe journalier",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR",
        icon="mdi:calendar-today",
        valeur=lambda c: calc.cout_fixe_journalier(c.valeurs),
    ),
    LuminusSensorDescription(
        key="cout_variable_jour",
        name="Coût variable du jour",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR",
        icon="mdi:flash",
        valeur=lambda c: c.cout_jour_en_cours()[0],
    ),
    LuminusSensorDescription(
        key="cout_total_jour",
        name="Coût total du jour",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR",
        icon="mdi:cash-check",
        valeur=lambda c: round(sum(c.cout_jour_en_cours()), 4),
    ),
    LuminusSensorDescription(
        key="cout_total_mois",
        name="Coût du mois (estimé)",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR",
        icon="mdi:cash-check",
        valeur=lambda c: round(c.cout_mois(), 2),
    ),
    LuminusSensorDescription(
        key="cout_total_annee",
        name="Coût de l'année (estimé)",
        device_class=SensorDeviceClass.MONETARY,
        native_unit_of_measurement="EUR",
        icon="mdi:cash-check",
        valeur=lambda c: c.total_annee()["cout_total_eur"],
    ),
)

HISTORIQUE = LuminusSensorDescription(
    key="historique_mensuel",
    name="Historique mensuel",
    native_unit_of_measurement="mois",
    icon="mdi:calendar-text",
    valeur=lambda c: len(c.etat.historique_mensuel),
)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    coordinateur: LuminusCoordinateur = entry.runtime_data
    async_add_entities(
        [
            *(LuminusSensor(coordinateur, description) for description in SENSORS),
            HistoriqueMensuelSensor(coordinateur, HISTORIQUE),
        ]
    )


class LuminusSensor(LuminusEntity, SensorEntity):
    entity_description: LuminusSensorDescription

    def __init__(
        self, coordinateur: LuminusCoordinateur, description: LuminusSensorDescription
    ) -> None:
        super().__init__(coordinateur, "sensor", description.key, description.name)
        self.entity_description = description

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_dispatcher_connect(self.hass, self._coordinateur.signal, self._async_republier)
        )

    @callback
    def _async_republier(self) -> None:
        self.async_write_ha_state()

    @property
    def native_value(self) -> float | int:
        return self.entity_description.valeur(self._coordinateur)


class HistoriqueMensuelSensor(LuminusSensor):
    """Mois archivés automatiquement à la clôture + mois saisis/corrigés
    via le service definir_mois_historique. L'état est le nombre de mois
    enregistrés ; le détail est dans les attributs "mois" et
    "total_annee", exploitables depuis une carte Markdown (voir le
    README)."""

    # total_annee change à chaque kWh : sans ça, la liste complète des
    # mois serait réécrite en base de données plusieurs fois par minute.
    _unrecorded_attributes = frozenset({"mois", "total_annee"})

    @property
    def extra_state_attributes(self) -> dict:
        mois = []
        for cle, enregistrement in sorted(self._coordinateur.etat.historique_mensuel.items()):
            annee, mois_num = cle.split("-")
            mois.append(
                {
                    "mois": cle,
                    "mois_label": f"{MOIS_FR[int(mois_num) - 1]} {annee}",
                    **enregistrement,
                }
            )
        return {"mois": mois, "total_annee": self._coordinateur.total_annee()}
