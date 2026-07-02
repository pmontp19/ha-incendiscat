"""The Bombers de Catalunya (bomberscat) integration.

Monitors real-time wildfire activity in Catalonia via the Catalan Fire
Department (Bombers) public ArcGIS FeatureServer, plus wildfire-risk data
from the Pla Alfa service.
"""

from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant

from .const import DOMAIN

__all__ = ["DOMAIN"]


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up bomberscat from a config entry.

    TODO(T5): build the BomberscatDataUpdateCoordinator, store it on
    entry.runtime_data (typed alias, not hass.data — see docs/04-architecture
    §5), call async_config_entry_first_refresh(), and forward to platforms
    (sensor/binary_sensor/geo_location). For now this only makes the entry
    setup succeed so the config flow (Task 4) is testable end to end; there
    is nothing to poll or unload yet.
    """
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a bomberscat config entry.

    TODO(T5): unload forwarded platforms once they exist
    (await hass.config_entries.async_unload_platforms(entry, PLATFORMS)).
    """
    return True
