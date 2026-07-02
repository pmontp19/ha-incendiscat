"""Tests for the bomberscat config flow (Task 4, step 1: location + radii)."""

from __future__ import annotations

from custom_components.bomberscat.const import (
    CONF_ALERT_RADIUS,
    CONF_TRACK_RADIUS,
    DEFAULT_ALERT_RADIUS_KM,
    DEFAULT_TRACK_RADIUS_KM,
    DOMAIN,
)
from homeassistant import config_entries
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_RADIUS,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_happy_path_creates_entry(hass: HomeAssistant) -> None:
    """Full flow: init -> form -> valid submit -> entry created with km values."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_LOCATION: {
                CONF_LATITUDE: 41.5,
                CONF_LONGITUDE: 2.1,
                CONF_RADIUS: 50_000,  # meters -> 50 km
            },
            CONF_ALERT_RADIUS: 20,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Bombers de Catalunya"
    assert result["data"] == {
        CONF_LATITUDE: 41.5,
        CONF_LONGITUDE: 2.1,
        CONF_TRACK_RADIUS: 50.0,
        CONF_ALERT_RADIUS: 20.0,
    }


async def test_missing_radius_uses_default(hass: HomeAssistant) -> None:
    """If the location dict has no radius (core#108960), fall back to default."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_LOCATION: {
                CONF_LATITUDE: 41.5,
                CONF_LONGITUDE: 2.1,
                # no CONF_RADIUS key at all
            },
            CONF_ALERT_RADIUS: 10,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TRACK_RADIUS] == float(DEFAULT_TRACK_RADIUS_KM)
    assert result["data"][CONF_ALERT_RADIUS] == 10.0


async def test_alert_radius_greater_than_track_radius_shows_error(
    hass: HomeAssistant,
) -> None:
    """alert_radius > track_radius must produce a recoverable form error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_LOCATION: {
                CONF_LATITUDE: 41.5,
                CONF_LONGITUDE: 2.1,
                CONF_RADIUS: 10_000,  # 10 km track radius
            },
            CONF_ALERT_RADIUS: 30,  # > track radius
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {CONF_ALERT_RADIUS: "alert_gt_track"}

    # The flow must still be recoverable: fix the input and resubmit.
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_LOCATION: {
                CONF_LATITUDE: 41.5,
                CONF_LONGITUDE: 2.1,
                CONF_RADIUS: 10_000,
            },
            CONF_ALERT_RADIUS: 5,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_TRACK_RADIUS] == 10.0
    assert result["data"][CONF_ALERT_RADIUS] == 5.0


async def test_second_config_attempt_aborts(hass: HomeAssistant) -> None:
    """Single-instance integration: a second attempt aborts immediately."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_LOCATION: {
                CONF_LATITUDE: 41.5,
                CONF_LONGITUDE: 2.1,
                CONF_RADIUS: 50_000,
            },
            CONF_ALERT_RADIUS: DEFAULT_ALERT_RADIUS_KM,
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY

    second = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert second["type"] is FlowResultType.ABORT
    assert second["reason"] == "single_instance_allowed"
