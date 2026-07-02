"""Binary sensor platform for bomberscat (fire_nearby, high_risk)."""

from __future__ import annotations

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import BomberscatConfigEntry


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BomberscatConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up bomberscat binary sensors from a config entry."""
    # Entities are added by T8 (fire_nearby) and T10 (high_risk).
