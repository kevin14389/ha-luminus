"""Aides partagées entre les plateformes d'entités."""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo

from .const import DOMAIN


def device_info_for_entry(entry: ConfigEntry) -> DeviceInfo:
    """Regroupe toutes les entités sous un même appareil dans l'UI."""
    return DeviceInfo(
        identifiers={(DOMAIN, entry.entry_id)},
        name="Luminus Comfy Électricité",
        manufacturer="Intégration communautaire non-officielle",
        model="Comfy Electricité - Wallonie - ORES Luxembourg",
        entry_type=DeviceEntryType.SERVICE,
    )
