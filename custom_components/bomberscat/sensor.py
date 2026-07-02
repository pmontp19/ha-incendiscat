"""Sensor platform for bomberscat (aggregated wildfire sensors)."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BomberscatConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BomberscatConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up bomberscat sensors from a config entry."""
    # Entities are added by T6/T12.
