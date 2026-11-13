"""Fixtures et aides communes aux tests."""

from __future__ import annotations

from datetime import datetime

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.luminus_comfy.const import (
    CONF_DELIVERED_OFFPEAK,
    CONF_DELIVERED_PEAK,
    CONF_RETURNED_OFFPEAK,
    CONF_RETURNED_PEAK,
    DOMAIN,
)

PRELEVEMENT_JOUR = "sensor.daily_energy_delivered_peak"
PRELEVEMENT_NUIT = "sensor.daily_energy_delivered_offpeak"
INJECTION_JOUR = "sensor.daily_energy_returned_peak"
INJECTION_NUIT = "sensor.daily_energy_returned_offpeak"

SOURCES = {
    CONF_DELIVERED_PEAK: PRELEVEMENT_JOUR,
    CONF_DELIVERED_OFFPEAK: PRELEVEMENT_NUIT,
    CONF_RETURNED_PEAK: INJECTION_JOUR,
    CONF_RETURNED_OFFPEAK: INJECTION_NUIT,
}

FUSEAU = "Europe/Brussels"


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(enable_custom_integrations):
    """Sans ça, Home Assistant ne charge pas custom_components/ en test."""


@pytest.fixture(autouse=True)
async def fuseau_belge(hass: HomeAssistant) -> None:
    await hass.config.async_set_time_zone(FUSEAU)


@pytest.fixture
def entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(domain=DOMAIN, data=SOURCES, unique_id=DOMAIN)
    entry.add_to_hass(hass)
    return entry


def heure_locale(texte: str) -> datetime:
    """"2026-11-12 08:00:00" à l'heure belge."""
    return datetime.fromisoformat(texte).replace(tzinfo=dt_util.get_time_zone(FUSEAU))


async def aller_a(hass: HomeAssistant, freezer, texte: str) -> None:
    """Avance l'horloge et laisse tourner ce qui était programmé."""
    moment = heure_locale(texte)
    freezer.move_to(moment)
    async_fire_time_changed(hass, moment)
    await hass.async_block_till_done()


async def installer(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def regler_source(hass: HomeAssistant, entity_id: str, valeur, **attributs) -> None:
    hass.states.async_set(entity_id, str(valeur), attributs)


def nombre(hass: HomeAssistant, entity_id: str) -> float:
    return float(hass.states.get(entity_id).state)


async def regler(hass: HomeAssistant, entity_id: str, valeur, **attributs) -> None:
    """Change un capteur source et laisse l'intégration le relever."""
    regler_source(hass, entity_id, valeur, **attributs)
    await hass.async_block_till_done()


async def demarrer(hass: HomeAssistant, entry: MockConfigEntry, freezer, quand: str) -> None:
    """Installe l'intégration à la date donnée, capteurs sources à 0."""
    freezer.move_to(heure_locale(quand))
    for entity_id in SOURCES.values():
        regler_source(hass, entity_id, 0)
    await installer(hass, entry)


def notifications(hass: HomeAssistant) -> dict:
    from homeassistant.components import persistent_notification

    return persistent_notification._async_get_or_create_notifications(hass)
