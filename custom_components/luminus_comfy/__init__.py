"""Intégration Luminus Comfy Électricité.

Toute la logique est dans coordinateur.py ; ce fichier ne fait que
brancher l'intégration sur Home Assistant (chargement, plateformes,
services).
"""

from __future__ import annotations

import voluptuous as vol

from homeassistant.config_entries import ConfigEntry, ConfigEntryState
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ServiceValidationError

from .const import (
    ATTR_CONSOMMATION_KWH,
    ATTR_CUMUL_KWH,
    ATTR_MOIS,
    ATTR_PRODUCTION_KWH,
    DOMAIN,
    SERVICE_DEFINIR_CUMUL_PERIODE,
    SERVICE_DEFINIR_MOIS_HISTORIQUE,
)
from .coordinateur import LuminusCoordinateur

PLATFORMS = ["sensor", "number", "switch", "date", "button"]

_SCHEMA_MOIS = vol.Schema(
    {
        vol.Required(ATTR_MOIS): str,
        vol.Required(ATTR_CONSOMMATION_KWH): vol.Coerce(float),
        vol.Required(ATTR_PRODUCTION_KWH): vol.Coerce(float),
    }
)
_SCHEMA_CUMUL = vol.Schema({vol.Required(ATTR_CUMUL_KWH): vol.Coerce(float)})


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    coordinateur = LuminusCoordinateur(hass, entry)
    await coordinateur.async_charger()
    entry.runtime_data = coordinateur

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    coordinateur.async_demarrer()
    entry.async_on_unload(entry.add_update_listener(_async_options_modifiees))

    async def _definir_mois(call: ServiceCall) -> None:
        await _coordinateur(hass).async_definir_mois_historique(
            call.data[ATTR_MOIS],
            call.data[ATTR_CONSOMMATION_KWH],
            call.data[ATTR_PRODUCTION_KWH],
        )

    async def _definir_cumul(call: ServiceCall) -> None:
        await _coordinateur(hass).async_definir_cumul_periode(call.data[ATTR_CUMUL_KWH])

    hass.services.async_register(
        DOMAIN, SERVICE_DEFINIR_MOIS_HISTORIQUE, _definir_mois, schema=_SCHEMA_MOIS
    )
    hass.services.async_register(
        DOMAIN, SERVICE_DEFINIR_CUMUL_PERIODE, _definir_cumul, schema=_SCHEMA_CUMUL
    )
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    unloaded = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unloaded:
        hass.services.async_remove(DOMAIN, SERVICE_DEFINIR_MOIS_HISTORIQUE)
        hass.services.async_remove(DOMAIN, SERVICE_DEFINIR_CUMUL_PERIODE)
        # Écrit tout de suite ce qui attendait une sauvegarde différée,
        # avant qu'un rechargement ne relise le fichier.
        await entry.runtime_data.store.async_save()
    return unloaded


async def _async_options_modifiees(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Les capteurs sources ont été changés via "Configurer"."""
    await hass.config_entries.async_reload(entry.entry_id)


def _coordinateur(hass: HomeAssistant) -> LuminusCoordinateur:
    """L'intégration n'accepte qu'une seule entrée de configuration."""
    for entry in hass.config_entries.async_entries(DOMAIN):
        if entry.state is ConfigEntryState.LOADED:
            return entry.runtime_data
    raise ServiceValidationError("L'intégration Luminus Comfy n'est pas chargée.")
