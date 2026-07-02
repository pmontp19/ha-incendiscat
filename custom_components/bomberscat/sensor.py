"""Sensor platform for bomberscat: aggregated wildfire sensors (Task 6+12).

Implements the 6 aggregated sensors of docs/03-feature-spec.md §3.2-§3.7:
`active_fires`, `nearest_fire_distance`, `nearest_fire_municipi`,
`fires_per_fase`, `fires_per_tipus`, `total_vehicles`. All are
`CoordinatorEntity` subclasses sharing one `DeviceInfo` per
docs/04-architecture.md §7 ("Bombers de Catalunya").

"Active" vs "tracked" (design note, since the spec's wording is ambiguous
about which incidents each sensor should count):

`BomberscatState.incidents` (see coordinator.py) holds two kinds of rows:
incidents whose phase is in the user's configured `active_phases`, *plus*
incidents that just turned `Extingit` and are sitting out their removal
grace period (kept around so `geo_location` entities don't flicker away
instantly). We call the first group "active" and the whole dict "tracked".

- `active_fires`'s state and `nearest_fire_*` only consider the *active*
  group: a grace-period `Extingit` fire is, definitionally, out — counting
  it as "active" or as the "nearest fire" would be misleading. This also
  matches feature-spec §3.2's own definition ("Comptador d'incendis actius
  (definits per `active_phases`)").
- `fires_per_fase`, `fires_per_tipus` and `total_vehicles` count everything
  *tracked* (the full `incidents` dict), since feature-spec §3.7 says "dels
  incidents *en seguiment*" (tracked) for `total_vehicles`, and
  `fires_per_fase`'s whole point is to show the phase breakdown, which is
  only informative if `Extingit` can show a non-zero count during its grace
  window (otherwise the `extingit` attribute would be permanently 0 and the
  sensor would carry no more information than `active_fires` split in two).

Sentinel note (`nearest_fire_distance` = `-1` when there is no active fire):
`-1` under `device_class=DISTANCE` is admittedly an odd choice for a numeric
`float` field over a nice `unit=km` scale (unlike `native_value=None`, which
HA would render as "unknown" and is the idiomatic no-data value for a
measurement). We implement `-1` as feature-spec §3.3 explicitly specifies it
byte-for-byte, but if this sensor's spec is revisited we'd recommend
`None`/unknown instead.
"""

from __future__ import annotations

from collections import Counter
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import UnitOfLength
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceEntryType
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import BomberscatConfigEntry
from .const import DOMAIN
from .coordinator import BomberscatDataUpdateCoordinator, BomberscatState
from .icons import DEFAULT_FASE_ICON, DEFAULT_TIPUS_ICON, FASE_ICONS, TIPUS_ICONS
from .models import Fase, Incident, Tipus

NO_MUNICIPI = "—"
FIRES_UNIT = "incendis"


def _active_incidents(
    state: BomberscatState, active_phases: frozenset[str]
) -> list[Incident]:
    """Tracked incidents whose phase is in the user's `active_phases`.

    See the module docstring for why this excludes grace-period `Extingit`
    incidents even though they are still in `state.incidents`.
    """
    return [inc for inc in state.incidents.values() if inc.fase.value in active_phases]


def _nearest(
    incidents: list[Incident], coordinator: BomberscatDataUpdateCoordinator
) -> Incident | None:
    """The closest incident to home, or `None` if `incidents` is empty."""
    if not incidents:
        return None
    return min(incidents, key=coordinator.distance_km)


class BomberscatEntity(CoordinatorEntity[BomberscatDataUpdateCoordinator]):
    """Base for all bomberscat sensor entities: shared device + naming.

    Mirrors the `BomberscatEntity` sketch in docs/04-architecture.md §7.
    Kept local to this module (rather than a shared `entity.py`) because
    this task may only touch `sensor.py`/`icons.py`/`tests/test_sensor.py`;
    the `binary_sensor`/`geo_location` platforms define their own copy.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: BomberscatDataUpdateCoordinator,
        entry: BomberscatConfigEntry,
        key: str,
    ) -> None:
        super().__init__(coordinator)
        self._attr_unique_id = f"{entry.entry_id}_{key}"
        # No translations/*.json entries exist yet for entity keys (Task 14
        # handles that); until then HA falls back to showing the key itself
        # as the entity name, which is acceptable per this task's brief.
        self._attr_translation_key = key
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="Bombers de Catalunya",
            manufacturer="Generalitat de Catalunya",
            model="Incendis forestals",
            entry_type=DeviceEntryType.SERVICE,
        )


class ActiveFiresSensor(BomberscatEntity, SensorEntity):
    """`sensor.bomberscat_active_fires` (docs/03-feature-spec.md §3.2)."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = FIRES_UNIT

    def __init__(
        self, coordinator: BomberscatDataUpdateCoordinator, entry: BomberscatConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "active_fires")

    @property
    def native_value(self) -> int:
        state: BomberscatState = self.coordinator.data
        return len(_active_incidents(state, self.coordinator.config.active_phases))

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        state: BomberscatState = self.coordinator.data
        cfg = self.coordinator.config
        active = _active_incidents(state, cfg.active_phases)
        in_alert_radius = sum(
            1
            for inc in active
            if self.coordinator.distance_km(inc) <= cfg.alert_radius_km
        )
        last_updated = state.last_success.isoformat() if state.last_success else None
        return {
            "last_updated": last_updated,
            "total_in_track_radius": len(state.incidents),
            "total_in_alert_radius": in_alert_radius,
        }


class NearestFireDistanceSensor(BomberscatEntity, SensorEntity):
    """`sensor.bomberscat_nearest_fire_distance` (feature-spec §3.3).

    See the module docstring for the `-1` sentinel design note.
    """

    _attr_device_class = SensorDeviceClass.DISTANCE
    _attr_native_unit_of_measurement = UnitOfLength.KILOMETERS
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: BomberscatDataUpdateCoordinator, entry: BomberscatConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "nearest_fire_distance")

    @property
    def native_value(self) -> float:
        state: BomberscatState = self.coordinator.data
        active = _active_incidents(state, self.coordinator.config.active_phases)
        nearest = _nearest(active, self.coordinator)
        if nearest is None:
            return -1
        return round(self.coordinator.distance_km(nearest), 1)


class NearestFireMunicipiSensor(BomberscatEntity, SensorEntity):
    """`sensor.bomberscat_nearest_fire_municipi` (feature-spec §3.4)."""

    def __init__(
        self, coordinator: BomberscatDataUpdateCoordinator, entry: BomberscatConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "nearest_fire_municipi")

    @property
    def native_value(self) -> str:
        state: BomberscatState = self.coordinator.data
        active = _active_incidents(state, self.coordinator.config.active_phases)
        nearest = _nearest(active, self.coordinator)
        if nearest is None:
            return NO_MUNICIPI
        return nearest.municipi or NO_MUNICIPI


class FiresPerFaseSensor(BomberscatEntity, SensorEntity):
    """`sensor.bomberscat_fires_per_fase` (feature-spec §3.5).

    Counts *tracked* incidents (see module docstring), including
    grace-period `Extingit` ones, so the `extingit` attribute is
    meaningful.
    """

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = FIRES_UNIT

    def __init__(
        self, coordinator: BomberscatDataUpdateCoordinator, entry: BomberscatConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "fires_per_fase")

    def _counts(self) -> Counter[Fase]:
        state: BomberscatState = self.coordinator.data
        return Counter(inc.fase for inc in state.incidents.values())

    @property
    def native_value(self) -> int:
        return sum(self._counts().values())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        counts = self._counts()
        return {
            "actiu": counts[Fase.ACTIU],
            "estabilitzat": counts[Fase.ESTABILITZAT],
            "controlat": counts[Fase.CONTROLAT],
            "extingit": counts[Fase.EXTINGIT],
        }

    @property
    def icon(self) -> str:
        counts = self._counts()
        present = [fase for fase in Fase if counts[fase]]
        if not present:
            return DEFAULT_FASE_ICON
        # Most severe fase present drives the icon (Fase.severity: Actiu=3
        # .. Extingit=0), e.g. one Actiu + two Extingit shows the fire icon.
        dominant = max(present, key=lambda fase: fase.severity)
        return FASE_ICONS[dominant]


class FiresPerTipusSensor(BomberscatEntity, SensorEntity):
    """`sensor.bomberscat_fires_per_tipus` (feature-spec §3.6). Tracked, not
    just active — see `FiresPerFaseSensor`'s docstring."""

    _attr_state_class = SensorStateClass.MEASUREMENT
    _attr_native_unit_of_measurement = FIRES_UNIT

    def __init__(
        self, coordinator: BomberscatDataUpdateCoordinator, entry: BomberscatConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "fires_per_tipus")

    def _counts(self) -> Counter[Tipus]:
        state: BomberscatState = self.coordinator.data
        return Counter(inc.tipus for inc in state.incidents.values())

    @property
    def native_value(self) -> int:
        return sum(self._counts().values())

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        counts = self._counts()
        return {
            "vf": counts[Tipus.FORESTAL],
            "va": counts[Tipus.AGRICOLA],
            "vu": counts[Tipus.URBANA],
        }

    @property
    def icon(self) -> str:
        counts = self._counts()
        if not any(counts.values()):
            return DEFAULT_TIPUS_ICON
        dominant, _ = counts.most_common(1)[0]
        return TIPUS_ICONS[dominant]


class TotalVehiclesSensor(BomberscatEntity, SensorEntity):
    """`sensor.bomberscat_total_vehicles` (feature-spec §3.7): Σ `ACT_NUM_VEH`
    over *tracked* incidents (see module docstring)."""

    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(
        self, coordinator: BomberscatDataUpdateCoordinator, entry: BomberscatConfigEntry
    ) -> None:
        super().__init__(coordinator, entry, "total_vehicles")

    @property
    def native_value(self) -> int:
        state: BomberscatState = self.coordinator.data
        return sum(inc.vehicles for inc in state.incidents.values())


async def async_setup_entry(
    hass: HomeAssistant,
    entry: BomberscatConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up bomberscat sensors from a config entry."""
    coordinator = entry.runtime_data
    async_add_entities(
        [
            ActiveFiresSensor(coordinator, entry),
            NearestFireDistanceSensor(coordinator, entry),
            NearestFireMunicipiSensor(coordinator, entry),
            FiresPerFaseSensor(coordinator, entry),
            FiresPerTipusSensor(coordinator, entry),
            TotalVehiclesSensor(coordinator, entry),
        ]
    )
