"""Base commune à toutes les entités de l'intégration."""

from __future__ import annotations

from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo, Entity

from .const import DOMAIN
from .coordinateur import LuminusCoordinateur


class LuminusEntity(Entity):
    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self, coordinateur: LuminusCoordinateur, plateforme: str, key: str, name: str
    ) -> None:
        entry_id = coordinateur.entry.entry_id
        self._coordinateur = coordinateur
        self._key = key
        self._attr_unique_id = f"{entry_id}_{plateforme}_{key}"
        # Home Assistant ne tient compte d'un entity_id proposé par
        # l'intégration que s'il est affecté ici, avant l'ajout de
        # l'entité. (Une entité déjà enregistrée garde son entity_id.)
        self.entity_id = f"{plateforme}.luminus_{key}"
        self._attr_name = name
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry_id)},
            name="Luminus Comfy Électricité",
            manufacturer="Intégration communautaire non-officielle",
            model="Comfy Electricité - Wallonie - ORES Luxembourg",
            entry_type=DeviceEntryType.SERVICE,
        )
