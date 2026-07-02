"""The Bombers de Catalunya (bomberscat) integration.

Monitors real-time wildfire activity in Catalonia via the Catalan Fire
Department (Bombers) public ArcGIS FeatureServer, plus wildfire-risk data
from the Pla Alfa service.
"""

from __future__ import annotations

import logging

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import DOMAIN
from .coordinator import BomberscatDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# entry.runtime_data alias (docs/04-architecture.md §5, "runtime-data" rule):
# the coordinator lives on the config entry itself, not hass.data[DOMAIN].
type BomberscatConfigEntry = ConfigEntry[BomberscatDataUpdateCoordinator]

PLATFORMS: tuple[Platform, ...] = (
    Platform.BINARY_SENSOR,
    Platform.GEO_LOCATION,
    Platform.SENSOR,
)

__all__ = ["DOMAIN", "BomberscatConfigEntry"]


async def async_setup_entry(hass: HomeAssistant, entry: BomberscatConfigEntry) -> bool:
    """Set up bomberscat from a config entry.

    `async_config_entry_first_refresh()` runs the first poll synchronously
    and raises `ConfigEntryNotReady` on failure (network error, FeatureServer
    down, ...), which is exactly the "fail setup cleanly, let HA retry
    later" behavior Task 5 asks for — we do not need to catch anything here.
    """
    session = async_get_clientsession(hass)
    coordinator = BomberscatDataUpdateCoordinator(hass, entry, session)
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = coordinator
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def _async_update_listener(
    hass: HomeAssistant, entry: BomberscatConfigEntry
) -> None:
    """Reload the entry when options change (options flow lands in T11)."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_unload_entry(hass: HomeAssistant, entry: BomberscatConfigEntry) -> bool:
    """Unload a bomberscat config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
