"""Cœur de l'intégration : mesure de l'énergie, clôture quotidienne,
changement de mois, prix programmé, historique et corrections.

Mesure de l'énergie. L'intégration ne lit pas les capteurs sources à un
instant précis : elle relève chaque changement de valeur et ajoute la
différence à deux compteurs internes ("en cours" : kWh prélevés et
injectés depuis la dernière clôture). La clôture quotidienne verse ces
compteurs dans le mois et les remet à zéro. Chaque kWh est donc compté
exactement une fois, que Home Assistant soit arrêté à minuit, que les
capteurs sources soient momentanément indisponibles, ou que la clôture
soit lancée deux fois - et ça fonctionne avec des compteurs journaliers
(utility_meter ou autres) comme avec des index qui ne reviennent jamais
à zéro.

Tarifs. Les valeurs des entités number/switch/date vivent dans
self.valeurs ; les entités n'en sont que l'affichage et le moyen de les
modifier. Les calculs ne dépendent donc pas des entity_id.
"""

from __future__ import annotations

import calendar
import logging
import re
from datetime import date, timedelta
from typing import Any

from homeassistant.components import persistent_notification
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, EventStateChangedData, HomeAssistant, State, callback
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.dispatcher import async_dispatcher_send
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.event import async_track_state_change_event, async_track_time_change
from homeassistant.helpers.start import async_at_started
from homeassistant.util import dt as dt_util

from . import calculations as calc
from .const import (
    CONF_DELIVERED_OFFPEAK,
    CONF_DELIVERED_PEAK,
    CONF_RETURNED_OFFPEAK,
    CONF_RETURNED_PEAK,
    DAILY_CLOSEOUT_HOUR,
    DAILY_CLOSEOUT_MINUTE,
    DAILY_CLOSEOUT_SECOND,
    DATETIME_DATE_DEBUT_CONTRAT,
    DATETIME_PRIX_ENERGIE_DATE_EFFET,
    NUM_PRIX_ENERGIE_TTC,
    NUM_PRIX_ENERGIE_TTC_PROCHAIN,
    NUMBER_DEFINITIONS,
    SEUIL_NOUVEAU_CYCLE,
    SIGNAL_MAJ,
    SWITCH_CHANGEMENT_PRIX_PROGRAMME,
    SWITCH_REMISE_FIDELITE_ACTIVE,
)
from .store import Etat, LuminusStore

_LOGGER = logging.getLogger(__name__)
_MOIS_RE = re.compile(r"^\d{4}-(0[1-9]|1[0-2])$")

Notification = tuple[str, str, str]  # (titre, message, identifiant)


def _flottant(valeur: Any) -> float | None:
    try:
        return float(valeur)
    except (TypeError, ValueError):
        return None


def _mois_precedent(annee: int, mois: int) -> str:
    return f"{annee - 1}-12" if mois == 1 else f"{annee}-{mois - 1:02d}"


class LuminusCoordinateur:
    def __init__(self, hass: HomeAssistant, entry: ConfigEntry) -> None:
        self.hass = hass
        self.entry = entry
        self.store = LuminusStore(hass, entry.entry_id)
        self.signal = SIGNAL_MAJ.format(entry.entry_id)
        conf = {**entry.data, **entry.options}
        self._sources_prelevement = [conf[CONF_DELIVERED_PEAK], conf[CONF_DELIVERED_OFFPEAK]]
        self._sources_injection = [conf[CONF_RETURNED_PEAK], conf[CONF_RETURNED_OFFPEAK]]
        self.valeurs: dict[str, Any] = {
            **{key: defaut for key, *_reste, defaut in NUMBER_DEFINITIONS},
            SWITCH_REMISE_FIDELITE_ACTIVE: False,
            SWITCH_CHANGEMENT_PRIX_PROGRAMME: False,
            DATETIME_DATE_DEBUT_CONTRAT: None,
            DATETIME_PRIX_ENERGIE_DATE_EFFET: None,
        }
        # Entités number/switch/date par clé, pour republier leur état
        # quand le coordinateur modifie leur valeur.
        self.entites: dict[str, Entity] = {}
        self._initialisation = False
        self._stockage_perdu = False

    @property
    def etat(self) -> Etat:
        return self.store.etat

    def aujourdhui(self) -> date:
        """Date du jour dans le fuseau de Home Assistant (pas celui du
        système, souvent UTC dans un conteneur)."""
        return dt_util.now().date()

    async def async_charger(self) -> None:
        fichier_present = await self.store.async_load()
        etat = self.etat
        # Un fichier absent alors que l'intégration est installée depuis
        # plusieurs jours : les données ont été perdues (déjà arrivé
        # avec les input_number du package YAML).
        age = dt_util.utcnow() - self.entry.created_at
        self._stockage_perdu = not fichier_present and age > timedelta(days=2)
        self._initialisation = not etat.initialise
        etat.initialise = True
        sources = {*self._sources_prelevement, *self._sources_injection}
        etat.releves = {k: v for k, v in etat.releves.items() if k in sources}
        aujourdhui = self.aujourdhui()
        etat.mois_courant = etat.mois_courant or aujourdhui.strftime("%Y-%m")
        etat.annee_courante = etat.annee_courante or aujourdhui.strftime("%Y")

    @callback
    def async_demarrer(self) -> None:
        """À appeler une fois les entités créées (elles ont alors
        restauré les tarifs)."""
        hass, entry = self.hass, self.entry
        entry.async_on_unload(
            async_track_state_change_event(
                hass,
                [*self._sources_prelevement, *self._sources_injection],
                self._async_source_modifiee,
            )
        )
        entry.async_on_unload(
            async_track_time_change(
                hass,
                self.async_tic,
                hour=DAILY_CLOSEOUT_HOUR,
                minute=DAILY_CLOSEOUT_MINUTE,
                second=DAILY_CLOSEOUT_SECOND,
            )
        )
        # Une fois Home Assistant démarré, pour que les capteurs sources
        # aient eu le temps de restaurer leur état.
        entry.async_on_unload(async_at_started(hass, self.async_tic))

    @callback
    def async_signaler(self) -> None:
        async_dispatcher_send(self.hass, self.signal)

    # --- Mesure de l'énergie ---

    @callback
    def _async_source_modifiee(self, event: Event[EventStateChangedData]) -> None:
        if self._async_relever(event.data["entity_id"], event.data["new_state"]):
            self.store.async_planifier_sauvegarde()
            self.async_signaler()

    @callback
    def _async_relever(self, entity_id: str, state: State | None) -> bool:
        """Ajoute aux compteurs en cours l'énergie mesurée par ce capteur
        depuis son dernier relevé. Retourne True si de l'énergie a été
        ajoutée."""
        if state is None or state.state in (STATE_UNKNOWN, STATE_UNAVAILABLE):
            return False
        valeur = _flottant(state.state)
        if valeur is None:
            return False
        reset = state.attributes.get("last_reset")
        reset = None if reset is None else str(reset)

        etat = self.etat
        precedent = etat.releves.get(entity_id)
        if precedent is None:
            # Jamais relevé. À la toute première mise en route, un
            # compteur qui annonce son dernier reset (utility_meter) est
            # repris depuis le début de son cycle, pour ne pas perdre la
            # partie de la journée déjà écoulée. Sinon on part de sa
            # valeur actuelle : rien ne dit que c'est un compteur
            # journalier, et un capteur ajouté après coup mesure une
            # journée déjà comptée par celui qu'il remplace.
            delta = valeur if self._initialisation and reset is not None else 0.0
        else:
            ancienne = precedent["valeur"]
            if reset is not None and precedent["reset"] is not None:
                nouveau_cycle = reset != precedent["reset"]
            else:
                nouveau_cycle = valeur < ancienne * SEUIL_NOUVEAU_CYCLE
            if nouveau_cycle:
                # Le compteur est reparti de zéro. last_period
                # (utility_meter) donne le total exact du cycle terminé ;
                # à défaut, la dernière valeur relevée.
                fin = _flottant(state.attributes.get("last_period"))
                if fin is None or fin < ancienne:
                    fin = ancienne
                delta = fin - ancienne + valeur
            else:
                delta = max(valeur - ancienne, 0.0)
        etat.releves[entity_id] = {"valeur": valeur, "reset": reset}

        if not delta:
            return False
        if entity_id in self._sources_prelevement:
            etat.prelevement_en_cours = round(etat.prelevement_en_cours + delta, 6)
        else:
            etat.injection_en_cours = round(etat.injection_en_cours + delta, 6)
        return True

    # --- Valeurs affichées par les capteurs ---

    def cout_jour_en_cours(self) -> tuple[float, float]:
        """(coût variable, coût fixe) depuis la dernière clôture."""
        etat = self.etat
        _cumule, variable = calc.cout_variable(
            self.valeurs,
            self.aujourdhui(),
            etat.prelevement_en_cours,
            etat.injection_en_cours,
            etat.net_cumule_periode,
        )
        return variable, calc.cout_fixe_journalier(self.valeurs)

    def cout_mois(self) -> float:
        return self.etat.accumulateur_mois + sum(self.cout_jour_en_cours())

    def total_annee(self) -> dict:
        """Mois archivés de l'année + mois en cours (jours clôturés et
        journée en cours) + correction manuelle de l'année."""
        etat = self.etat
        conso = etat.conso_mois_kwh + etat.prelevement_en_cours
        production = etat.injection_mois_kwh + etat.injection_en_cours
        cout = self.cout_mois() + etat.correction_annee
        for mois, enregistrement in etat.historique_mensuel.items():
            # Le mois en cours vient des compteurs ci-dessus, même s'il a
            # déjà été saisi à la main : ne pas le compter deux fois.
            if mois.startswith(etat.annee_courante) and mois != etat.mois_courant:
                conso += enregistrement.get("consommation_kwh", 0.0)
                production += enregistrement.get("production_kwh", 0.0)
                cout += enregistrement.get("cout_total_eur", 0.0)
        cout = round(cout, 2)
        return {
            "consommation_kwh": round(conso, 3),
            "production_kwh": round(production, 3),
            "solde_net_kwh": round(conso - production, 3),
            "cout_total_eur": cout,
            "prix_moyen_kwh": round(cout / conso, 4) if conso else 0.0,
        }

    # --- Clôture quotidienne, changement de mois, prix programmé ---

    async def async_tic(self, _=None) -> None:
        """Clôture les jours terminés, change de mois/d'année et applique
        un prix programmé arrivé à échéance. Lancé juste après minuit et
        au démarrage ; sans effet si tout est déjà à jour."""
        notifications = self._async_avancer()
        await self.store.async_save()
        self.async_signaler()
        self._async_notifier(notifications)

    @callback
    def _async_avancer(self) -> list[Notification]:
        """Sans aucun await : deux tics simultanés ne peuvent pas
        s'entremêler."""
        notifications: list[Notification] = []
        for entity_id in (*self._sources_prelevement, *self._sources_injection):
            self._async_relever(entity_id, self.hass.states.get(entity_id))

        etat = self.etat
        aujourdhui = self.aujourdhui()
        hier = aujourdhui - timedelta(days=1)
        if not etat.derniere_cloture:
            # Première mise en route : rien à clôturer avant aujourd'hui.
            etat.derniere_cloture = hier.isoformat()
        elif date.fromisoformat(etat.derniere_cloture) < hier:
            notifications.append(self._cloturer(hier))
        self._changer_de_periode(aujourdhui)

        prix = self._appliquer_prix_programme(aujourdhui)
        if prix is not None:
            notifications.append(self._notification_prix(prix))
        if self._stockage_perdu:
            self._stockage_perdu = False
            notifications.append(
                (
                    "⚠️ Luminus - Données internes perdues",
                    "Le fichier de données de l'intégration (.storage/"
                    f"luminus_comfy_{self.entry.entry_id}) est introuvable alors "
                    "que l'intégration est installée depuis plusieurs jours. Les "
                    "totaux du mois, le cumul de période et l'historique repartent "
                    "de zéro : restaure une sauvegarde, ou ressaisis l'historique "
                    "avec le service definir_mois_historique.",
                    "luminus_stockage_perdu",
                )
            )
        return notifications

    def _cloturer(self, hier: date) -> Notification:
        """Verse les compteurs en cours dans le mois. Couvre plusieurs
        jours d'un coup si Home Assistant était arrêté à minuit."""
        etat = self.etat
        jours = (hier - date.fromisoformat(etat.derniere_cloture)).days
        prelevement, injection = etat.prelevement_en_cours, etat.injection_en_cours
        cumule_apres, variable = calc.cout_variable(
            self.valeurs, hier, prelevement, injection, etat.net_cumule_periode
        )
        cout = round(variable + calc.cout_fixe_journalier(self.valeurs) * jours, 4)

        etat.net_cumule_periode = round(cumule_apres, 3)
        etat.conso_mois_kwh = round(etat.conso_mois_kwh + prelevement, 3)
        etat.injection_mois_kwh = round(etat.injection_mois_kwh + injection, 3)
        etat.accumulateur_mois = round(etat.accumulateur_mois + cout, 4)
        etat.prelevement_en_cours = 0.0
        etat.injection_en_cours = 0.0
        etat.derniere_cloture = hier.isoformat()

        titre = f"Coût électricité Luminus - {hier.strftime('%d/%m/%Y')}"
        if jours > 1:
            titre += f" ({jours} jours)"
        return (
            titre,
            f"Prélèvement : {round(prelevement, 3)} kWh — "
            f"Injection : {round(injection, 3)} kWh — "
            f"Cumul de période : {etat.net_cumule_periode} kWh\n\n"
            f"Coût total : {cout} €",
            "luminus_resume_quotidien",
        )

    def _changer_de_periode(self, aujourdhui: date) -> None:
        etat = self.etat
        mois = aujourdhui.strftime("%Y-%m")
        if etat.mois_courant != mois:
            self._archiver_mois()
            etat.accumulateur_mois = 0.0
            etat.conso_mois_kwh = 0.0
            etat.injection_mois_kwh = 0.0
            etat.mois_courant = mois
        annee = aujourdhui.strftime("%Y")
        if etat.annee_courante != annee:
            etat.correction_annee = 0.0
            etat.annee_courante = annee

    def _archiver_mois(self) -> None:
        """Archive le mois qui se termine, sauf s'il a été saisi à la
        main : une saisie manuelle n'est jamais écrasée."""
        etat = self.etat
        existant = etat.historique_mensuel.get(etat.mois_courant)
        if existant is not None and existant.get("source") == "manuel":
            return
        conso, injection, cout = etat.conso_mois_kwh, etat.injection_mois_kwh, etat.accumulateur_mois
        etat.historique_mensuel[etat.mois_courant] = {
            "consommation_kwh": round(conso, 3),
            "production_kwh": round(injection, 3),
            "solde_net_kwh": round(conso - injection, 3),
            # Coût accumulé jour par jour, donc exact même si le prix a
            # changé en cours de mois.
            "cout_total_eur": round(cout, 2),
            "prix_moyen_kwh": round(cout / conso, 4) if conso else 0.0,
            "prix_energie_taxes_ttc": calc.prix_energie_taxes_ttc(self.valeurs, self.aujourdhui()),
            "prix_reseau_ttc": calc.prix_reseau_ttc(self.valeurs),
            "cumule_periode_apres": etat.net_cumule_periode,
            "source": "auto",
        }

    def _appliquer_prix_programme(self, aujourdhui: date) -> float | None:
        """Retourne le nouveau prix s'il vient d'être appliqué."""
        valeurs = self.valeurs
        if not valeurs[SWITCH_CHANGEMENT_PRIX_PROGRAMME]:
            return None
        date_effet = valeurs[DATETIME_PRIX_ENERGIE_DATE_EFFET]
        if date_effet is None or aujourdhui < date_effet:
            return None
        prochain = valeurs[NUM_PRIX_ENERGIE_TTC_PROCHAIN]
        if prochain <= 0:
            return None
        self.async_definir(NUM_PRIX_ENERGIE_TTC, prochain)
        self.async_definir(SWITCH_CHANGEMENT_PRIX_PROGRAMME, False)
        self.async_definir(NUM_PRIX_ENERGIE_TTC_PROCHAIN, 0)
        # Nouveau prix = nouvelle période tarifaire.
        self.etat.net_cumule_periode = 0.0
        return prochain

    @staticmethod
    def _notification_prix(prix: float) -> Notification:
        return (
            "Luminus - Nouveau prix appliqué",
            f"Le prix énergie programmé ({prix} c€/kWh) vient d'être "
            "appliqué. S'il aurait dû entrer en vigueur avant aujourd'hui, "
            "utilise la correction manuelle pour rattraper les jours concernés.",
            "luminus_changement_prix_applique",
        )

    @callback
    def _async_notifier(self, notifications: list[Notification]) -> None:
        for titre, message, identifiant in notifications:
            persistent_notification.async_create(self.hass, message, titre, identifiant)

    # --- Modifications venant des entités et des services ---

    @callback
    def async_definir(self, key: str, valeur: Any) -> None:
        """Change un tarif et republie l'état de son entité."""
        self.valeurs[key] = valeur
        entite = self.entites.get(key)
        if entite is not None and entite.hass is not None:
            entite.async_write_ha_state()

    @callback
    def async_valeur_modifiee(self) -> None:
        """Un tarif vient d'être modifié depuis l'interface."""
        prix = self._appliquer_prix_programme(self.aujourdhui())
        if prix is not None:
            self.entry.async_create_task(self.hass, self.store.async_save())
            self._async_notifier([self._notification_prix(prix)])
        self.async_signaler()

    async def async_appliquer_correction(self, number_key: str, cible: str) -> None:
        """cible : "mois", "annee" ou "les-deux". Le total de l'année
        inclut le mois en cours, donc une correction du mois seul est
        compensée dans le décalage annuel."""
        montant = self.valeurs[number_key]
        if not montant:
            return
        etat = self.etat
        if cible in ("mois", "les-deux"):
            etat.accumulateur_mois = round(etat.accumulateur_mois + montant, 4)
        if cible == "mois":
            etat.correction_annee = round(etat.correction_annee - montant, 4)
        elif cible == "annee":
            etat.correction_annee = round(etat.correction_annee + montant, 4)
        self.async_definir(number_key, 0)
        await self.store.async_save()
        self.async_signaler()

    async def async_definir_mois_historique(
        self, mois: str, consommation_kwh: float, production_kwh: float
    ) -> None:
        """Saisie/correction manuelle d'un mois (ex. import MyOres), au
        tarif actuellement configuré. Reprend le cumul de période du
        mois précédent : les mois s'importent dans l'ordre."""
        if not _MOIS_RE.match(mois):
            raise ServiceValidationError(
                f"Format de mois invalide : {mois!r} (attendu AAAA-MM, ex. 2026-01)"
            )
        if consommation_kwh < 0 or production_kwh < 0:
            raise ServiceValidationError("La consommation et la production doivent être >= 0.")

        annee, mois_num = (int(p) for p in mois.split("-"))
        precedent = self.etat.historique_mensuel.get(_mois_precedent(annee, mois_num), {})
        _cumule, resume = calc.resume_mois(
            consommation_kwh,
            production_kwh,
            calc.prix_energie_taxes_ttc(self.valeurs, self.aujourdhui()),
            calc.prix_reseau_ttc(self.valeurs),
            calc.cout_fixe_journalier(self.valeurs),
            calendar.monthrange(annee, mois_num)[1],
            precedent.get("cumule_periode_apres", 0.0),
        )
        resume["source"] = "manuel"
        self.etat.historique_mensuel[mois] = resume
        await self.store.async_save()
        self.async_signaler()
        self._async_notifier(
            [
                (
                    f"Luminus - Mois {mois} enregistré",
                    f"Consommation : {resume['consommation_kwh']} kWh — "
                    f"Production : {resume['production_kwh']} kWh\n"
                    f"Coût total : {resume['cout_total_eur']} € — "
                    f"Prix moyen : {resume['prix_moyen_kwh']} €/kWh",
                    f"luminus_mois_{mois}",
                )
            ]
        )

    async def async_definir_cumul_periode(self, cumul_kwh: float) -> None:
        """Recale le solde net de la période tarifaire (jours clôturés),
        par exemple après une période où le suivi quotidien n'a pas
        fonctionné."""
        self.etat.net_cumule_periode = round(cumul_kwh, 3)
        await self.store.async_save()
        self.async_signaler()
