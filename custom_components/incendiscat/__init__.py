"""The Incendis Catalunya (incendiscat) integration.

Monitors real-time wildfire activity in Catalonia via the Catalan Fire
Department (Bombers) public ArcGIS FeatureServer, plus wildfire-risk data
from the Pla Alfa service.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry, ConfigEntryNotReady
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import IncendiscatDataUpdateCoordinator
from .pla_alfa import PlaAlfaCoordinator

_LOGGER = logging.getLogger(__name__)

# entry.runtime_data alias (docs/04-architecture.md §5, "runtime-data" rule):
# the coordinator lives on the config entry itself, not hass.data[DOMAIN].
#
# runtime_data strategy: rather than reshaping `runtime_data` into a
# 2-coordinator container (which would ripple into every existing reader —
# sensor.py/binary_sensor.py/geo_location.py and 4+ test files), we keep
# `entry.runtime_data` exactly as-is (the Bombers coordinator) and attach
# the Pla Alfa coordinator to it as a plain instance attribute,
# `coordinator.pla_alfa`, set once in `async_setup_entry` below before
# entities are created. This is the "smallest diff" option:
# `IncendiscatDataUpdateCoordinator` is a regular (non-slotted) class, so
# this is a normal, if untyped-on-the-class, attribute — sensor.py
# /binary_sensor.py read it as `entry.runtime_data.pla_alfa`.
type IncendiscatConfigEntry = ConfigEntry[IncendiscatDataUpdateCoordinator]

PLATFORMS: tuple[Platform, ...] = (
    Platform.BINARY_SENSOR,
    Platform.GEO_LOCATION,
    Platform.SENSOR,
)

__all__ = ["DOMAIN", "IncendiscatConfigEntry"]


async def async_setup_entry(hass: HomeAssistant, entry: IncendiscatConfigEntry) -> bool:
    """Set up incendiscat from a config entry.

    Startup-latency strategy (deviation from the previous behavior, where
    both coordinators' first refreshes ran serially inside setup and, with
    slow DNS, could block HA's boot for 2-4 minutes — each fetch burns up
    to ~127s of retries and the second coordinator waited for the first):

    - The Bombers first refresh stays synchronous
      (`async_config_entry_first_refresh()`, the canonical HA pattern: it
      runs the first poll and raises `ConfigEntryNotReady` on failure, so
      HA retries setup later), but its fetch runs with a reduced retry
      schedule — one retry instead of three, see
      `arcgis.FIRST_RETRY_BACKOFFS_SECONDS`. A dead network now fails in
      ~61s instead of ~127s; scheduled polls keep the full ladder.

    - The Pla Alfa first refresh no longer blocks setup at all: it runs as
      an entry-owned background task
      (`ConfigEntry.async_create_background_task` — the HA-native way to
      tie a task to the entry's lifecycle: auto-cancelled on unload, does
      not hold up startup). Until it completes, `fire_risk`/`high_risk`
      come up `unavailable` (their `CoordinatorEntity.available` follows
      `coordinator.last_update_success`, `False` until the first
      successful poll) — a few minutes of unavailability for a
      best-effort dataset instead of minutes of blocked boot. The eager
      start (the default) is what keeps `async_config_entry_first_refresh`
      legal here: it validates the config entry is still in
      `SETUP_IN_PROGRESS`, and an eagerly-started task begins executing
      while `async_setup_entry` is still on the stack, only suspending at
      the first network await.

    A failed Pla Alfa first refresh still must not abort the whole entry:
    fire monitoring is the integration's core value and Pla Alfa is a
    best-effort bonus, so the task catches `ConfigEntryNotReady`, logs,
    and moves on — the entities stay `unavailable` until the next
    successful poll, `PLA_ALFA_SCAN_INTERVAL_HOURS` later. Polling still
    resumes on that schedule because `DataUpdateCoordinator` reschedules
    its next refresh as soon as its first listener (the `fire_risk`/
    `high_risk` entities, added below by `async_forward_entry_setups`)
    subscribes, regardless of whether the *previous* refresh succeeded.
    """
    session = async_get_clientsession(hass)
    coordinator = IncendiscatDataUpdateCoordinator(hass, entry, session)
    await coordinator.async_config_entry_first_refresh()

    pla_alfa_coordinator = PlaAlfaCoordinator(hass, entry, session)
    coordinator.pla_alfa = pla_alfa_coordinator

    async def _pla_alfa_first_refresh() -> None:
        try:
            await pla_alfa_coordinator.async_config_entry_first_refresh()
        except ConfigEntryNotReady as err:
            _LOGGER.warning(
                "Pla Alfa fire-risk data unavailable on startup (%s); "
                "fire_risk/high_risk will show as unavailable until the next "
                "successful poll. Wildfire monitoring is unaffected.",
                err,
            )

    entry.async_create_background_task(
        hass,
        _pla_alfa_first_refresh(),
        "pla alfa first refresh",
    )

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: IncendiscatConfigEntry
) -> None:
    """Reload the entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(
    hass: HomeAssistant, entry: IncendiscatConfigEntry
) -> bool:
    """Unload a incendiscat config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
