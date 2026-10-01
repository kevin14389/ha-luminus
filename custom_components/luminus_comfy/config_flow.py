"""Config flow pour Luminus Comfy Électricité.

Une seule étape : sélectionner les 4 capteurs du compteur communicant
(prélèvement jour/nuit, injection jour/nuit). Tous les tarifs restent
modifiables ensuite via les entités "number" créées par l'intégration -
pas besoin de les redemander ici, leurs valeurs par défaut sont déjà
celles validées contre un vrai décompte Luminus (voir const.py).
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.helpers.selector import EntitySelector, EntitySelectorConfig

from .const import (
    CONF_DELIVERED_OFFPEAK,
    CONF_DELIVERED_PEAK,
    CONF_RETURNED_OFFPEAK,
    CONF_RETURNED_PEAK,
    DOMAIN,
)

_ENERGY_SENSOR_SELECTOR = EntitySelector(
    EntitySelectorConfig(domain="sensor", device_class="energy")
)

STEP_USER_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_DELIVERED_PEAK): _ENERGY_SENSOR_SELECTOR,
        vol.Required(CONF_DELIVERED_OFFPEAK): _ENERGY_SENSOR_SELECTOR,
        vol.Required(CONF_RETURNED_PEAK): _ENERGY_SENSOR_SELECTOR,
        vol.Required(CONF_RETURNED_OFFPEAK): _ENERGY_SENSOR_SELECTOR,
    }
)


class LuminusComfyConfigFlow(config_entries.ConfigFlow, domain=DOMAIN):
    """Gère la configuration initiale."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            entities = {
                user_input[CONF_DELIVERED_PEAK],
                user_input[CONF_DELIVERED_OFFPEAK],
                user_input[CONF_RETURNED_PEAK],
                user_input[CONF_RETURNED_OFFPEAK],
            }
            if len(entities) != 4:
                errors["base"] = "duplicate_entities"
            else:
                await self.async_set_unique_id(DOMAIN)
                self._abort_if_unique_id_configured()
                return self.async_create_entry(
                    title="Luminus Comfy Électricité", data=user_input
                )

        return self.async_show_form(
            step_id="user", data_schema=STEP_USER_SCHEMA, errors=errors
        )

    @staticmethod
    def async_get_options_flow(
        config_entry: config_entries.ConfigEntry,
    ) -> LuminusComfyOptionsFlow:
        return LuminusComfyOptionsFlow(config_entry)


class LuminusComfyOptionsFlow(config_entries.OptionsFlow):
    """Permet de changer les 4 capteurs après coup (ex. changement
    d'intégration compteur) sans devoir retirer/réinstaller."""

    def __init__(self, config_entry: config_entries.ConfigEntry) -> None:
        self._config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> config_entries.ConfigFlowResult:
        errors: dict[str, str] = {}
        current = {**self._config_entry.data, **self._config_entry.options}

        if user_input is not None:
            entities = {
                user_input[CONF_DELIVERED_PEAK],
                user_input[CONF_DELIVERED_OFFPEAK],
                user_input[CONF_RETURNED_PEAK],
                user_input[CONF_RETURNED_OFFPEAK],
            }
            if len(entities) != 4:
                errors["base"] = "duplicate_entities"
            else:
                return self.async_create_entry(title="", data=user_input)

        schema = vol.Schema(
            {
                vol.Required(
                    CONF_DELIVERED_PEAK, default=current.get(CONF_DELIVERED_PEAK)
                ): _ENERGY_SENSOR_SELECTOR,
                vol.Required(
                    CONF_DELIVERED_OFFPEAK, default=current.get(CONF_DELIVERED_OFFPEAK)
                ): _ENERGY_SENSOR_SELECTOR,
                vol.Required(
                    CONF_RETURNED_PEAK, default=current.get(CONF_RETURNED_PEAK)
                ): _ENERGY_SENSOR_SELECTOR,
                vol.Required(
                    CONF_RETURNED_OFFPEAK, default=current.get(CONF_RETURNED_OFFPEAK)
                ): _ENERGY_SENSOR_SELECTOR,
            }
        )
        return self.async_show_form(
            step_id="init", data_schema=schema, errors=errors
        )
