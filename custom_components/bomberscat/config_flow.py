"""Config flow for the Bombers de Catalunya (bomberscat) integration.

Step 1 (this file, Task 4): location + the two tracking radii (§2 of
docs/03-feature-spec.md). Step 2 (subtipus/fases/polling/min_vehicles) and
the options flow / ``async_step_reconfigure`` are added in Task 11 — do not
add them here.

Single instance: this integration models "my home + the fires around it",
so a single config entry per Home Assistant installation is enough for v1.
There is no natural per-account unique id to key on (unlike cloud
integrations with an API key), and letting the user create N entries for N
different locations would need per-entry device/entity naming we don't have
yet. We therefore abort on a second `user` step via
``self._async_current_entries()`` (the same pattern used by
``raspberry_pi`` and other single-instance core integrations) rather than
``async_set_unique_id`` + ``_abort_if_unique_id_configured``. Moving the
tracked location will be handled by ``async_step_reconfigure`` in Task 11,
not by creating a second entry.
"""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, ConfigFlowResult
from homeassistant.const import (
    CONF_LATITUDE,
    CONF_LOCATION,
    CONF_LONGITUDE,
    CONF_RADIUS,
    UnitOfLength,
)
from homeassistant.helpers import selector
from homeassistant.util.unit_conversion import DistanceConverter

from .const import (
    CONF_ALERT_RADIUS,
    CONF_TRACK_RADIUS,
    DEFAULT_ALERT_RADIUS_KM,
    DEFAULT_TRACK_RADIUS_KM,
    DOMAIN,
    MAX_TRACK_RADIUS_KM,
    MIN_TRACK_RADIUS_KM,
)

ERROR_ALERT_GT_TRACK = "alert_gt_track"


def _build_schema() -> vol.Schema:
    """Build the step-1 schema: map location (with radius) + alert radius."""
    return vol.Schema(
        {
            vol.Required(CONF_LOCATION): selector.LocationSelector(
                selector.LocationSelectorConfig(radius=True)
            ),
            vol.Optional(
                CONF_ALERT_RADIUS, default=DEFAULT_ALERT_RADIUS_KM
            ): selector.NumberSelector(
                selector.NumberSelectorConfig(
                    min=1,
                    max=MAX_TRACK_RADIUS_KM,
                    step=1,
                    unit_of_measurement="km",
                    mode=selector.NumberSelectorMode.BOX,
                )
            ),
        }
    )


class BomberscatConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Bombers de Catalunya."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        """Handle the (only, for now) setup step: location + radii."""
        if self._async_current_entries():
            return self.async_abort(reason="single_instance_allowed")

        errors: dict[str, str] = {}

        if user_input is not None:
            location: dict[str, float] = user_input[CONF_LOCATION]
            latitude = location[CONF_LATITUDE]
            longitude = location[CONF_LONGITUDE]

            # The LocationSelector's own vol.Optional("radius") means the
            # frontend can submit the form without a radius even though we
            # asked for one (home-assistant/core#108960) — default instead
            # of KeyError.
            radius_m = location.get(CONF_RADIUS)
            if radius_m is None:
                track_radius_km = float(DEFAULT_TRACK_RADIUS_KM)
            else:
                track_radius_km = DistanceConverter.convert(
                    radius_m, UnitOfLength.METERS, UnitOfLength.KILOMETERS
                )
            # Defensive clamp: the map's radius handle has no hard min/max,
            # so keep it inside the documented tracking range (5-200 km).
            track_radius_km = min(
                max(track_radius_km, MIN_TRACK_RADIUS_KM), MAX_TRACK_RADIUS_KM
            )

            alert_radius_km = float(
                user_input.get(CONF_ALERT_RADIUS, DEFAULT_ALERT_RADIUS_KM)
            )

            if alert_radius_km > track_radius_km:
                errors[CONF_ALERT_RADIUS] = ERROR_ALERT_GT_TRACK
            else:
                return self.async_create_entry(
                    title="Bombers de Catalunya",
                    data={
                        CONF_LATITUDE: latitude,
                        CONF_LONGITUDE: longitude,
                        CONF_TRACK_RADIUS: track_radius_km,
                        CONF_ALERT_RADIUS: alert_radius_km,
                    },
                )

        # Re-show the form: on first display, pre-fill from hass.config +
        # defaults; on a validation error, keep whatever the user submitted
        # so the flow is recoverable without retyping everything.
        suggested_values: dict[str, Any] = user_input or {
            CONF_LOCATION: {
                CONF_LATITUDE: self.hass.config.latitude,
                CONF_LONGITUDE: self.hass.config.longitude,
                CONF_RADIUS: DEFAULT_TRACK_RADIUS_KM * 1000,
            },
            CONF_ALERT_RADIUS: DEFAULT_ALERT_RADIUS_KM,
        }
        data_schema = self.add_suggested_values_to_schema(
            _build_schema(), suggested_values
        )
        return self.async_show_form(
            step_id="user", data_schema=data_schema, errors=errors
        )
