"""The Incendis Catalunya (incendiscat) integration.

Monitors real-time wildfire activity in Catalonia via the Catalan Fire
Department (Bombers) public ArcGIS FeatureServer, plus wildfire-risk data
from the Pla Alfa service.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.start import async_at_started

from .const import DOMAIN, PLA_ALFA_SCAN_INTERVAL_HOURS
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

    Startup-latency strategy. Both first refreshes used to run serially
    inside setup, which with slow DNS blocked HA's boot for 2-4 minutes:
    every fetch could burn the full ~127s retry ladder and Pla Alfa only
    started once Bombers was done.

    - The Bombers first refresh stays synchronous
      (`async_config_entry_first_refresh()`: the canonical HA pattern and
      what the `test_before_setup` quality-scale rule asks for: run the first
      poll, raise `ConfigEntryNotReady` on failure, let HA retry setup
      later), but it is now *bounded*: no in-client retries and a wall-clock
      deadline over the whole paginated fetch, so the window HA's boot waits
      on us is at most `arcgis.FIRST_REFRESH_DEADLINE_SECONDS`. HA's own
      setup-retry schedule (5/10/20/40/80s) replaces the retries we dropped
      and, unlike them, does not hold up the boot.

    - The Pla Alfa first refresh is off the critical path entirely. It is
      deferred with `async_at_started`, so it runs once HA has finished
      booting rather than competing with it (the pattern core uses for the
      same need, see `cert_expiry`/`here_travel_time`), and then runs as an
      entry-owned background task: auto-cancelled if the entry is unloaded
      mid-fetch. `async_refresh()`, not
      `async_config_entry_first_refresh()`, because the latter asserts the
      entry is still `SETUP_IN_PROGRESS` and raises `ConfigEntryError` once
      setup has returned.

    Until that refresh lands, `fire_risk`/`high_risk` report `unavailable`:
    both override `available` to also require `coordinator.data`, because
    `DataUpdateCoordinator.last_update_success` starts out `True` and
    `CoordinatorEntity`'s default would otherwise publish a data-less
    `unknown` as if it were a reading.

    A failed Pla Alfa refresh must not abort the entry: fire monitoring is
    the integration's core value and Pla Alfa is a best-effort bonus, so we
    only log what it means for the user, and the two entities stay
    `unavailable` until the next successful poll,
    `PLA_ALFA_SCAN_INTERVAL_HOURS` later. Polling still resumes on that
    schedule because `DataUpdateCoordinator` reschedules its next refresh as
    soon as its first listener (those same entities, added below by
    `async_forward_entry_setups`) subscribes, regardless of whether the
    *previous* refresh succeeded.
    """
    session = async_get_clientsession(hass)
    coordinator = IncendiscatDataUpdateCoordinator(hass, entry, session)
    await coordinator.async_config_entry_first_refresh()

    pla_alfa_coordinator = PlaAlfaCoordinator(hass, entry, session)
    coordinator.pla_alfa = pla_alfa_coordinator
    entry.runtime_data = coordinator

    async def _pla_alfa_first_refresh() -> None:
        await pla_alfa_coordinator.async_refresh()
        if not pla_alfa_coordinator.last_update_success:
            _LOGGER.warning(
                "Pla Alfa fire-risk data unavailable on the first poll (%s); "
                "fire_risk/high_risk stay unavailable until the next successful "
                "poll, in %d h. Wildfire monitoring is unaffected.",
                pla_alfa_coordinator.last_exception,
                PLA_ALFA_SCAN_INTERVAL_HOURS,
            )

    @callback
    def _start_pla_alfa_first_refresh(_hass: HomeAssistant) -> None:
        entry.async_create_background_task(
            hass,
            _pla_alfa_first_refresh(),
            "incendiscat pla alfa first refresh",
        )

    entry.async_on_unload(async_at_started(hass, _start_pla_alfa_first_refresh))
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
