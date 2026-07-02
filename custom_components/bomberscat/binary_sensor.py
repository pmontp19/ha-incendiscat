"""Binary sensor platform for bomberscat (Task 8: `fire_nearby`).

Implements `binary_sensor.bomberscat_fire_nearby` (docs/03-feature-spec.md
§3.9): `on` when any incident that passes the tracking filters is within the
**alert** radius (`coordinator.config.alert_radius_km`) — deliberately not
the (larger) track radius, which only gates `geo_location` entities and the
aggregate counters. `binary_sensor.high_risk` (§3.10, Pla Alfa) is Task 10's
responsibility and is intentionally not implemented here.

Device class (`SAFETY` vs `PROBLEM`): both HA binary sensor device classes
share the exact `on`/`off` semantics we need (`on` = bad). We picked
`SAFETY` because its documented meaning is "the device/state is unsafe"
(https://developers.home-assistant.io/docs/core/entity/binary-sensor/),
which matches "a wildfire is close enough to be a safety concern" more
directly than `PROBLEM`'s generic "something is wrong" — and `SAFETY` is the
device class HA's own smoke/gas/CO binary sensors use, which is the closest
existing precedent for a fire-adjacent condition. It also nudges dashboards
towards the shield-style icon instead of the generic alert-triangle one.

Grace-period interaction (docs/04-architecture.md §5, Task 5): the
coordinator keeps a just-`Extingit` incident in `state.incidents` for
`resolved_grace_minutes` after it stops being active, purely so the
`geo_location` entity (Task 7) doesn't flicker away instantly. That grace
period is a UI/lifecycle nicety for the per-incident entity, not a signal
that the fire is still a threat. `fire_nearby` therefore filters
`coordinator.data.incidents` down to phases in `coordinator.config
.active_phases` before applying the alert-radius check — an
Extingit-in-grace incident inside the alert radius does **not** keep
`fire_nearby` on, even though it is still present in `coordinator.data
.incidents` and still has a `geo_location` entity. Rationale: `Extingit` is
by definition not in the user-configured `active_phases` (default `[Actiu,
Estabilitzat]`, and `Extingit` cannot be added to that set as an "active"
phase per docs/03-feature-spec.md §2), so alerting on it once it is out
would contradict the whole point of the active-phases filter — the fire
being tracked for a few more minutes for map-flicker reasons should not
re-trigger (or hold on) a safety alert.
"""

from __future__ import annotations

from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BomberscatConfigEntry
from .const import DOMAIN
from .coordinator import BomberscatDataUpdateCoordinator, BomberscatState
from .models import Incident


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BomberscatConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up bomberscat binary sensors from a config entry."""
    async_add_entities([BomberscatFireNearbyBinarySensor(entry)])


class BomberscatFireNearbyBinarySensor(
    CoordinatorEntity[BomberscatState], BinarySensorEntity
):
    """`on` iff an actively-tracked incident is within the alert radius."""

    _attr_has_entity_name = True
    _attr_translation_key = "fire_nearby"
    _attr_device_class = BinarySensorDeviceClass.SAFETY

    def __init__(self, entry: BomberscatConfigEntry) -> None:
        coordinator: BomberscatDataUpdateCoordinator = entry.runtime_data
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_fire_nearby"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Bombers de Catalunya",
            manufacturer="Generalitat de Catalunya",
            model="Incendis forestals",
            entry_type=DeviceEntryType.SERVICE,
        )

    def _alerting_incidents(self) -> list[Incident]:
        """Tracked incidents that are both actively-phased and in alert range.

        See the module docstring for why `Extingit`-in-grace-period
        incidents (present in `coordinator.data.incidents` but not in
        `active_phases`) are excluded here.
        """
        coordinator = self.coordinator
        cfg = coordinator.config
        return [
            inc
            for inc in coordinator.data.incidents.values()
            if inc.fase.value in cfg.active_phases
            and coordinator.distance_km(inc) <= cfg.alert_radius_km
        ]

    def _nearest(self) -> Incident | None:
        candidates = self._alerting_incidents()
        if not candidates:
            return None
        return min(candidates, key=self.coordinator.distance_km)

    @property
    def is_on(self) -> bool:
        return self._nearest() is not None

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """`nearest_*` attributes when `on`; `None` (no attributes) when `off`."""
        nearest = self._nearest()
        if nearest is None:
            return None
        return {
            "nearest_act_num": nearest.act_num,
            "nearest_distance_km": round(self.coordinator.distance_km(nearest), 1),
            "nearest_municipi": nearest.municipi,
            "nearest_fase": nearest.fase.value,
        }
