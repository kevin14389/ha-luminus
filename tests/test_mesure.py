"""Comptage de l'énergie à partir des capteurs sources."""

from __future__ import annotations

from homeassistant.core import HomeAssistant

from .conftest import (
    INJECTION_JOUR,
    INJECTION_NUIT,
    PRELEVEMENT_JOUR,
    PRELEVEMENT_NUIT,
    SOURCES,
    demarrer,
    heure_locale,
    installer,
    nombre,
    regler,
    regler_source,
)

MATIN = "2026-11-12 08:00:00"
# last_reset tel que le publie un utility_meter (UTC) : minuit, heure belge.
RESET_12 = "2026-11-11T23:00:00+00:00"
RESET_13 = "2026-11-12T23:00:00+00:00"

CONSO = "sensor.luminus_conso_jour"
INJECTION = "sensor.luminus_injection_jour"
NET = "sensor.luminus_conso_nette_jour"


async def test_additionne_jour_et_nuit(hass: HomeAssistant, entry, freezer) -> None:
    await demarrer(hass, entry, freezer, MATIN)

    await regler(hass, PRELEVEMENT_JOUR, 1.5)
    await regler(hass, PRELEVEMENT_NUIT, 2.25)
    await regler(hass, INJECTION_JOUR, 0.4)
    await regler(hass, INJECTION_NUIT, 0.1)
    await regler(hass, PRELEVEMENT_JOUR, 2.0)

    assert nombre(hass, CONSO) == 4.25
    assert nombre(hass, INJECTION) == 0.5
    assert nombre(hass, NET) == 3.75


async def test_premiere_installation_compteur_journalier_utility_meter(
    hass: HomeAssistant, entry, freezer
) -> None:
    """Un utility_meter annonce son dernier reset : la partie de la
    journée déjà écoulée à l'installation est reprise."""
    freezer.move_to(heure_locale(MATIN))
    regler_source(hass, PRELEVEMENT_JOUR, 3.2, last_reset=RESET_12, last_period="11.0")
    regler_source(hass, PRELEVEMENT_NUIT, 4.1, last_reset=RESET_12, last_period="6.0")
    regler_source(hass, INJECTION_JOUR, 0.7, last_reset=RESET_12, last_period="9.0")
    regler_source(hass, INJECTION_NUIT, 0, last_reset=RESET_12, last_period="0")
    await installer(hass, entry)

    assert nombre(hass, CONSO) == 7.3
    assert nombre(hass, INJECTION) == 0.7


async def test_premiere_installation_capteur_quelconque(
    hass: HomeAssistant, entry, freezer
) -> None:
    """Sans last_reset, impossible de savoir si le capteur est
    journalier : on part de sa valeur actuelle (ça marche donc aussi
    avec un index qui ne revient jamais à zéro)."""
    freezer.move_to(heure_locale(MATIN))
    for entity_id in SOURCES.values():
        regler_source(hass, entity_id, 12345.6)
    await installer(hass, entry)
    assert nombre(hass, CONSO) == 0

    await regler(hass, PRELEVEMENT_JOUR, 12350.6)
    assert nombre(hass, CONSO) == 5.0


async def test_source_absente_au_demarrage_puis_disponible(
    hass: HomeAssistant, entry, freezer
) -> None:
    """Un utility_meter sans tarif reste "unknown" au démarrage jusqu'à
    sa première mesure."""
    freezer.move_to(heure_locale(MATIN))
    await installer(hass, entry)
    assert nombre(hass, CONSO) == 0

    await regler(hass, PRELEVEMENT_JOUR, "unknown", last_reset="2026-11-12T07:00:00+00:00")
    assert nombre(hass, CONSO) == 0
    await regler(hass, PRELEVEMENT_JOUR, 3.2, last_reset=RESET_12, last_period="11.0")
    assert nombre(hass, CONSO) == 3.2


async def test_nouveau_cycle_utility_meter(hass: HomeAssistant, entry, freezer) -> None:
    """Au reset, last_period donne le total exact du cycle terminé :
    rien n'est perdu entre le dernier relevé et minuit."""
    freezer.move_to(heure_locale(MATIN))
    regler_source(hass, PRELEVEMENT_JOUR, 0, last_reset=RESET_12, last_period="0")
    await installer(hass, entry)
    await regler(hass, PRELEVEMENT_JOUR, 7.0, last_reset=RESET_12, last_period="0")

    await regler(hass, PRELEVEMENT_JOUR, 0.2, last_reset=RESET_13, last_period="7.3")

    assert nombre(hass, CONSO) == 7.5


async def test_nouveau_cycle_sans_attributs(hass: HomeAssistant, entry, freezer) -> None:
    await demarrer(hass, entry, freezer, MATIN)
    await regler(hass, PRELEVEMENT_JOUR, 7.0)

    await regler(hass, PRELEVEMENT_JOUR, 0.2)

    assert nombre(hass, CONSO) == 7.2


async def test_petite_baisse_ignoree(hass: HomeAssistant, entry, freezer) -> None:
    """Une baisse de moins de 10 % est du bruit de mesure, pas un
    nouveau cycle."""
    await demarrer(hass, entry, freezer, MATIN)
    await regler(hass, PRELEVEMENT_JOUR, 7.0)

    await regler(hass, PRELEVEMENT_JOUR, 6.999)
    assert nombre(hass, CONSO) == 7.0

    await regler(hass, PRELEVEMENT_JOUR, 7.1)
    assert nombre(hass, CONSO) == 7.101


async def test_source_indisponible_puis_de_retour(hass: HomeAssistant, entry, freezer) -> None:
    await demarrer(hass, entry, freezer, MATIN)
    await regler(hass, PRELEVEMENT_JOUR, 3.0)

    await regler(hass, PRELEVEMENT_JOUR, "unavailable")
    assert nombre(hass, CONSO) == 3.0
    await regler(hass, PRELEVEMENT_JOUR, "n'importe quoi")
    assert nombre(hass, CONSO) == 3.0

    await regler(hass, PRELEVEMENT_JOUR, 4.5)
    assert nombre(hass, CONSO) == 4.5


async def test_rien_de_perdu_pendant_un_arret(hass: HomeAssistant, entry, freezer) -> None:
    """Ce que les capteurs sources ont mesuré pendant que l'intégration
    ne tournait pas est repris au redémarrage."""
    await demarrer(hass, entry, freezer, MATIN)
    await regler(hass, PRELEVEMENT_JOUR, 3.0)
    await regler(hass, INJECTION_JOUR, 1.0)

    assert await hass.config_entries.async_unload(entry.entry_id)
    await regler(hass, PRELEVEMENT_JOUR, 4.5)
    await regler(hass, INJECTION_JOUR, 1.25)
    await installer(hass, entry)

    assert nombre(hass, CONSO) == 4.5
    assert nombre(hass, INJECTION) == 1.25


async def test_nouveau_cycle_pendant_un_arret(hass: HomeAssistant, entry, freezer) -> None:
    freezer.move_to(heure_locale("2026-11-12 22:00:00"))
    regler_source(hass, PRELEVEMENT_JOUR, 7.0, last_reset=RESET_12, last_period="0")
    await installer(hass, entry)
    assert nombre(hass, CONSO) == 7.0

    assert await hass.config_entries.async_unload(entry.entry_id)
    # Rechargé le même soir, d'où pas de clôture : seul le relevé compte.
    regler_source(hass, PRELEVEMENT_JOUR, 1.2, last_reset=RESET_13, last_period="7.4")
    await installer(hass, entry)

    assert nombre(hass, CONSO) == 8.6


async def test_etat_plus_ancien_que_le_dernier_releve_ignore(
    hass: HomeAssistant, entry, freezer
) -> None:
    """Notification en retard d'un état déjà dépassé (la clôture a lu un
    état plus récent entre-temps) : elle ne doit rien ajouter."""
    from datetime import timedelta

    from homeassistant.core import State
    from homeassistant.util import dt as dt_util

    await demarrer(hass, entry, freezer, MATIN)
    coordinateur = entry.runtime_data
    maintenant = dt_util.utcnow()
    recent = State(PRELEVEMENT_JOUR, "7", last_updated=maintenant + timedelta(seconds=2))
    ancien = State(PRELEVEMENT_JOUR, "6", last_updated=maintenant + timedelta(seconds=1))

    coordinateur._async_relever(PRELEVEMENT_JOUR, recent)
    coordinateur._async_relever(PRELEVEMENT_JOUR, ancien)
    coordinateur._async_relever(PRELEVEMENT_JOUR, recent)

    assert coordinateur.etat.prelevement_en_cours == 7
