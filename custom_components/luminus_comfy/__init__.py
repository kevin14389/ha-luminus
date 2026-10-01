"""Intégration Luminus Comfy Électricité.

Orchestration : clôture quotidienne (juste après minuit, lit les
attributs "last_period" des 4 capteurs sources pour une capture exacte
sans perte - voir le README pour pourquoi), application du changement
de prix programmé, et vérification de cohérence au démarrage.
"""

from __future__ import annotations

import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import event as event_helper
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
    DATETIME_PRIX_ENERGIE_DATE_EFFET,
    DOMAIN,
    NUM_PRIX_ENERGIE_TTC,
    NUM_PRIX_ENERGIE_TTC_PROCHAIN,
    SWITCH_CHANGEMENT_PRIX_PROGRAMME,
)
from .store import LuminusStore

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["sensor", "number", "switch", "date", "button"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    store = LuminusStore(hass, entry.entry_id)
    await store.async_load()

    hass.data.setdefault(DOMAIN, {})
    hass.data[DOMAIN][entry.entry_id] = {"store": store}

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    entry.async_on_unload(
        event_helper.async_track_time_change(
            hass,
            lambda _now: hass.async_create_task(_async_daily_closeout(hass, entry)),
            hour=DAILY_CLOSEOUT_HOUR,
            minute=DAILY_CLOSEOUT_MINUTE,
            second=DAILY_CLOSEOUT_SECOND,
        )
    )

    entry.async_on_unload(
        event_helper.async_track_time_interval(
            hass,
            lambda _now: hass.async_create_task(_async_check_prix_programme(hass, entry)),
            timedelta(hours=1),
        )
    )

    tracked_prix_programme = {
        f"switch.luminus_{SWITCH_CHANGEMENT_PRIX_PROGRAMME}",
        f"date.luminus_{DATETIME_PRIX_ENERGIE_DATE_EFFET}",
        f"number.luminus_{NUM_PRIX_ENERGIE_TTC_PROCHAIN}",
    }
    entry.async_on_unload(
        event_helper.async_track_state_change_event(
            hass,
            list(tracked_prix_programme),
            lambda _event: hass.async_create_task(_async_check_prix_programme(hass, entry)),
        )
    )

    # Vérifications de rattrapage au démarrage/ajout de l'intégration :
    # un changement de prix qui aurait dû s'appliquer pendant que HA
    # était éteint, et un contrôle de cohérence des accumulateurs (voir
    # le README : un incident après mise à jour HA les a déjà remis à 0
    # sans prévenir à 2 reprises).
    async def _startup(_event=None) -> None:
        await _async_check_prix_programme(hass, entry)
        await _async_verifier_accumulateurs(hass, entry)

    if hass.is_running:
        hass.async_create_task(_startup())
    else:
        entry.async_on_unload(
            hass.bus.async_listen_once(EVENT_HOMEASSISTANT_STARTED, _startup)
        )

    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unloaded


def _attr_last_period_or_current(hass: HomeAssistant, entity_id: str | None) -> float:
    """Valeur exacte du cycle qui vient de se terminer (attribut
    last_period des utility_meter) - évite de perdre les dernières
    minutes avant minuit comme un simple snapshot à 23h55 le ferait.
    Retombe sur l'état courant si l'attribut est absent."""
    if not entity_id:
        return 0.0
    state = hass.states.get(entity_id)
    if state is None:
        return 0.0
    last_period = state.attributes.get("last_period")
    if last_period is not None:
        try:
            return float(last_period)
        except (TypeError, ValueError):
            pass
    try:
        return float(state.state)
    except (TypeError, ValueError):
        return 0.0


async def _async_notify(hass: HomeAssistant, title: str, message: str, notification_id: str) -> None:
    await hass.services.async_call(
        "persistent_notification",
        "create",
        {"title": title, "message": message, "notification_id": notification_id},
        blocking=True,
    )


async def _async_daily_closeout(hass: HomeAssistant, entry: ConfigEntry) -> None:
    conf = {**entry.data, **entry.options}
    store: LuminusStore = hass.data[DOMAIN][entry.entry_id]["store"]

    prelevement_hier = _attr_last_period_or_current(
        hass, conf.get(CONF_DELIVERED_PEAK)
    ) + _attr_last_period_or_current(hass, conf.get(CONF_DELIVERED_OFFPEAK))
    injection_hier = _attr_last_period_or_current(
        hass, conf.get(CONF_RETURNED_PEAK)
    ) + _attr_last_period_or_current(hass, conf.get(CONF_RETURNED_OFFPEAK))

    cumule_avant = store.net_cumule_periode
    cumule_apres, net_fact = calc.net_facturable(cumule_avant, prelevement_hier - injection_hier)

    prix_et = calc.prix_energie_taxes_ttc(hass) / 100
    prix_rs = calc.prix_reseau_ttc(hass) / 100
    cout_fixe = calc.cout_fixe_journalier(hass)
    cout_variable_hier = (net_fact * prix_et) + (prelevement_hier * prix_rs)
    cout_total_hier = round(cout_variable_hier + cout_fixe, 4)

    await store.async_set_net_cumule_periode(cumule_apres)
    # Crédite le jour qui vient de se terminer AVANT de vérifier un
    # éventuel changement de mois/année, pour qu'il compte dans la
    # bonne période (voir ordre équivalent dans le package YAML d'origine).
    await store.async_ajouter_cout_mois(cout_total_hier)
    await store.async_ajouter_cout_annee(cout_total_hier)

    today = dt_util.now().date()
    mois_str = today.strftime("%Y-%m")
    annee_str = today.strftime("%Y")
    if store.mois_courant != mois_str:
        await store.async_reset_mois(mois_str)
    if store.annee_courante != annee_str:
        await store.async_reset_annee(annee_str)

    date_hier = (dt_util.now() - timedelta(days=1)).strftime("%d/%m/%Y")
    await _async_notify(
        hass,
        f"Coût électricité Luminus - {date_hier}",
        (
            f"Prélèvement : {round(prelevement_hier, 3)} kWh — "
            f"Injection : {round(injection_hier, 3)} kWh — "
            f"Cumul de période : {round(cumule_apres, 3)} kWh\n\n"
            f"Coût total du jour : {cout_total_hier} €"
        ),
        "luminus_resume_quotidien",
    )


async def _async_check_prix_programme(hass: HomeAssistant, entry: ConfigEntry) -> None:
    if not calc.get_switch_on(hass, SWITCH_CHANGEMENT_PRIX_PROGRAMME):
        return
    date_effet = calc.get_date(hass, DATETIME_PRIX_ENERGIE_DATE_EFFET)
    if date_effet is None or dt_util.now().date() < date_effet:
        return
    prochain = calc.get_number(hass, NUM_PRIX_ENERGIE_TTC_PROCHAIN)
    if prochain <= 0:
        return

    store: LuminusStore = hass.data[DOMAIN][entry.entry_id]["store"]

    await _async_notify(
        hass,
        "Luminus - Nouveau prix appliqué",
        (
            f"Le prix énergie programmé ({prochain} c€/kWh) vient d'être "
            "appliqué. S'il aurait dû entrer en vigueur avant aujourd'hui, "
            "utilise la correction manuelle pour rattraper les jours concernés."
        ),
        "luminus_changement_prix_applique",
    )

    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": f"number.luminus_{NUM_PRIX_ENERGIE_TTC}", "value": prochain},
        blocking=True,
    )
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": f"switch.luminus_{SWITCH_CHANGEMENT_PRIX_PROGRAMME}"},
        blocking=True,
    )
    await hass.services.async_call(
        "number",
        "set_value",
        {"entity_id": f"number.luminus_{NUM_PRIX_ENERGIE_TTC_PROCHAIN}", "value": 0},
        blocking=True,
    )
    await store.async_reset_net_cumule_periode()


async def _async_verifier_accumulateurs(hass: HomeAssistant, entry: ConfigEntry) -> None:
    store: LuminusStore = hass.data[DOMAIN][entry.entry_id]["store"]
    today = dt_util.now().date()
    suspect_mois = today.day > 2 and store.accumulateur_mois == 0
    suspect_annee = today.timetuple().tm_yday > 2 and store.accumulateur_annee == 0
    if not (suspect_mois or suspect_annee):
        return
    await _async_notify(
        hass,
        "⚠️ Luminus - Accumulateur suspect à 0",
        (
            f"Au démarrage, un accumulateur est à 0 alors qu'on n'est pas en "
            f"tout début de mois/d'année (accumulateur_mois = "
            f"{store.accumulateur_mois} €, accumulateur_annee = "
            f"{store.accumulateur_annee} €). Vérifie si c'est légitime ou "
            "une perte de données."
        ),
        "luminus_accumulateur_suspect",
    )
