"""Formulaire d'installation et changement des capteurs sources."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.luminus_comfy.const import (
    CONF_DELIVERED_OFFPEAK,
    CONF_DELIVERED_PEAK,
    DOMAIN,
)

from .conftest import PRELEVEMENT_JOUR, SOURCES, demarrer, nombre, regler


async def test_installation(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], SOURCES)
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == SOURCES
    assert hass.states.get("sensor.luminus_cout_total_mois") is not None


async def test_deux_fois_le_meme_capteur_refuse(hass: HomeAssistant) -> None:
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {**SOURCES, CONF_DELIVERED_OFFPEAK: SOURCES[CONF_DELIVERED_PEAK]}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "duplicate_entities"}


async def test_une_seule_installation(hass: HomeAssistant) -> None:
    MockConfigEntry(domain=DOMAIN, data=SOURCES, unique_id=DOMAIN).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(DOMAIN, context={"source": "user"})

    result = await hass.config_entries.flow.async_configure(result["flow_id"], SOURCES)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_changer_un_capteur_source(hass: HomeAssistant, entry, freezer) -> None:
    """Le nouveau capteur est suivi tout de suite, sans redémarrage ; ce
    qu'il affichait déjà n'est pas recompté (l'ancien l'a déjà mesuré)."""
    await demarrer(hass, entry, freezer, "2026-11-12 08:00:00")
    await regler(hass, PRELEVEMENT_JOUR, 3.0)
    nouveau = "sensor.nouveau_compteur_jour"
    await regler(hass, nouveau, 3.0)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {**SOURCES, CONF_DELIVERED_PEAK: nouveau}
    )
    await hass.async_block_till_done()
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert nombre(hass, "sensor.luminus_conso_jour") == 3.0

    await regler(hass, PRELEVEMENT_JOUR, 9.0)  # l'ancien capteur n'est plus suivi
    await regler(hass, nouveau, 4.5)

    assert nombre(hass, "sensor.luminus_conso_jour") == 4.5
