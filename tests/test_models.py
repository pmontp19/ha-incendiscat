"""Tests for models.py: Fase, Tipus, Incident.from_feature()."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from custom_components.incendiscat.models import Fase, Incident, Tipus, incident_key

FIXTURES_DIR = Path(__file__).parent / "fixtures"


def _load(name: str) -> dict:
    return json.loads((FIXTURES_DIR / name).read_text())


# ---------------------------------------------------------------------------
# Fase
# ---------------------------------------------------------------------------


def test_fase_severity_ordering() -> None:
    assert Fase.ACTIU.severity == 3
    assert Fase.ESTABILITZAT.severity == 2
    assert Fase.CONTROLAT.severity == 1
    assert Fase.EXTINGIT.severity == 0


def test_fase_has_no_sense_fase_member() -> None:
    assert "SENSE_FASE" not in Fase.__members__


# ---------------------------------------------------------------------------
# Incident.from_feature — real sample fixture
# ---------------------------------------------------------------------------


def test_from_feature_parses_real_sample_fixture() -> None:
    data = _load("featureserver_sample.json")
    incidents = [Incident.from_feature(f) for f in data["features"]]
    assert len(incidents) == len(data["features"])
    for inc in incidents:
        assert inc.act_num
        assert isinstance(inc.lat, float)
        assert isinstance(inc.lon, float)
        assert isinstance(inc.fase, Fase)
        assert isinstance(inc.tipus, Tipus)


def test_from_feature_known_values() -> None:
    data = _load("featureserver_sample.json")
    feature = data["features"][0]
    inc = Incident.from_feature(feature)

    assert inc.act_num == "262311630"
    assert inc.lon == pytest.approx(2.16657666649)
    assert inc.lat == pytest.approx(41.7238869198289)
    assert inc.fase == Fase.ESTABILITZAT
    assert inc.tipus == Tipus.FORESTAL
    assert inc.tipus_desc == "Incendi vegetació forestal"
    assert inc.municipi == "Sant Quirze Safaja"
    assert inc.vehicles == 0
    assert inc.situacio == "I"
    assert inc.fi is None
    # 1782300143000 ms since epoch UTC.
    assert inc.inici == datetime.fromtimestamp(1782300143000 / 1000, tz=UTC)
    assert inc.inici.tzinfo is UTC
    assert inc.data_act == datetime.fromtimestamp(1782974073000 / 1000, tz=UTC)


# ---------------------------------------------------------------------------
# Null / missing field tolerance
# ---------------------------------------------------------------------------


def test_com_fase_null_maps_to_actiu() -> None:
    feature = {
        "geometry": {"type": "Point", "coordinates": [2.0, 41.0]},
        "properties": {"ACT_NUM_ACTUACIO": "1", "COM_FASE": None},
    }
    inc = Incident.from_feature(feature)
    assert inc.fase == Fase.ACTIU


def test_com_fase_missing_key_maps_to_actiu() -> None:
    feature = {
        "geometry": {"type": "Point", "coordinates": [2.0, 41.0]},
        "properties": {"ACT_NUM_ACTUACIO": "1"},
    }
    inc = Incident.from_feature(feature)
    assert inc.fase == Fase.ACTIU


def test_com_fase_padded_value_is_stripped_before_matching() -> None:
    """A trailing/leading space (observed on the live FeatureServer) must not
    misclassify a real phase value as unknown -> Actiu, which would silently
    suppress incendiscat_phase_change events."""
    feature = {
        "geometry": {"type": "Point", "coordinates": [2.0, 41.0]},
        "properties": {"ACT_NUM_ACTUACIO": "1", "COM_FASE": "Estabilitzat "},
    }
    inc = Incident.from_feature(feature)
    assert inc.fase == Fase.ESTABILITZAT


def test_com_fase_lowercase_value_falls_back_to_actiu_with_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Only whitespace-stripping is required; casing mismatches keep the
    existing unknown-value fallback behavior (Actiu + a warning)."""
    feature = {
        "geometry": {"type": "Point", "coordinates": [2.0, 41.0]},
        "properties": {"ACT_NUM_ACTUACIO": "1", "COM_FASE": "estabilitzat"},
    }
    with caplog.at_level("WARNING"):
        inc = Incident.from_feature(feature)
    assert inc.fase == Fase.ACTIU
    assert any("COM_FASE" in record.message for record in caplog.records)


def test_com_fase_unknown_value_maps_to_actiu() -> None:
    feature = {
        "geometry": {"type": "Point", "coordinates": [2.0, 41.0]},
        "properties": {"ACT_NUM_ACTUACIO": "1", "COM_FASE": "Something New"},
    }
    inc = Incident.from_feature(feature)
    assert inc.fase == Fase.ACTIU


def test_tal_cod_alarma2_padded_value_is_stripped_before_matching() -> None:
    feature = {
        "geometry": {"type": "Point", "coordinates": [2.0, 41.0]},
        "properties": {"ACT_NUM_ACTUACIO": "1", "TAL_COD_ALARMA2": " VU"},
    }
    inc = Incident.from_feature(feature)
    assert inc.tipus == Tipus.URBANA


def test_tal_cod_alarma2_null_maps_to_vf() -> None:
    feature = {
        "geometry": {"type": "Point", "coordinates": [2.0, 41.0]},
        "properties": {"ACT_NUM_ACTUACIO": "1", "TAL_COD_ALARMA2": None},
    }
    inc = Incident.from_feature(feature)
    assert inc.tipus == Tipus.FORESTAL


def test_tal_cod_alarma2_missing_key_maps_to_vf() -> None:
    feature = {
        "geometry": {"type": "Point", "coordinates": [2.0, 41.0]},
        "properties": {"ACT_NUM_ACTUACIO": "1"},
    }
    inc = Incident.from_feature(feature)
    assert inc.tipus == Tipus.FORESTAL


def test_missing_properties_and_geometry_does_not_raise() -> None:
    inc = Incident.from_feature({})
    assert inc.act_num == ""
    assert inc.lat == 0.0
    assert inc.lon == 0.0
    assert inc.fase == Fase.ACTIU
    assert inc.tipus == Tipus.FORESTAL
    assert inc.municipi is None
    assert inc.inici is None
    assert inc.fi is None
    assert inc.edit_date is None
    assert inc.creation_date is None
    assert inc.data_act is None


def test_from_feature_with_none_input_does_not_raise() -> None:
    inc = Incident.from_feature(None)  # type: ignore[arg-type]
    assert inc.act_num == ""


def test_from_feature_with_partial_coordinates_does_not_raise() -> None:
    feature = {"geometry": {"coordinates": [2.0]}, "properties": {}}
    inc = Incident.from_feature(feature)
    assert inc.lon == 2.0
    assert inc.lat == 0.0


def test_missing_coordinates_logs_warning(caplog: pytest.LogCaptureFixture) -> None:
    feature = {
        "geometry": {"coordinates": []},
        "properties": {"ACT_NUM_ACTUACIO": "1"},
    }
    with caplog.at_level("WARNING"):
        inc = Incident.from_feature(feature)
    assert inc.lat == 0.0
    assert inc.lon == 0.0
    assert any("coordinate" in record.message.lower() for record in caplog.records)


def test_present_coordinates_do_not_log_warning(
    caplog: pytest.LogCaptureFixture,
) -> None:
    feature = {
        "geometry": {"coordinates": [2.0, 41.0]},
        "properties": {"ACT_NUM_ACTUACIO": "1"},
    }
    with caplog.at_level("WARNING"):
        Incident.from_feature(feature)
    assert not any("coordinate" in record.message.lower() for record in caplog.records)


def test_from_feature_with_garbage_timestamp_does_not_raise() -> None:
    feature = {
        "geometry": {"coordinates": [2.0, 41.0]},
        "properties": {"ACT_NUM_ACTUACIO": "1", "ACT_DAT_INICI": "not-a-timestamp"},
    }
    inc = Incident.from_feature(feature)
    assert inc.inici is None


def test_municipi_falls_back_to_dpx_when_sig_missing() -> None:
    feature = {
        "geometry": {"coordinates": [2.0, 41.0]},
        "properties": {"ACT_NUM_ACTUACIO": "1", "MUNICIPI_DPX": "Girona"},
    }
    inc = Incident.from_feature(feature)
    assert inc.municipi == "Girona"


def test_vehicles_defaults_to_zero_when_missing() -> None:
    feature = {"geometry": {"coordinates": [2.0, 41.0]}, "properties": {}}
    inc = Incident.from_feature(feature)
    assert inc.vehicles == 0


# ---------------------------------------------------------------------------
# Duplicates fixture (used mainly by test_arcgis.py, sanity-checked here)
# ---------------------------------------------------------------------------


def test_duplicates_fixture_both_rows_parse() -> None:
    data = _load("featureserver_duplicates.json")
    incidents = [Incident.from_feature(f) for f in data["features"]]
    assert len(incidents) == 2
    assert {i.act_num for i in incidents} == {"999000001"}
    # One row has COM_FASE=null (-> Actiu), the other has COM_FASE="Actiu".
    assert {i.fase for i in incidents} == {Fase.ACTIU}


# ---------------------------------------------------------------------------
# incident_key — fallback when ACT_NUM_ACTUACIO is missing from the schema
# (verified live 2026-08-09, docs/01-data-sources.md §2)
# ---------------------------------------------------------------------------


def test_incident_key_prefers_act_num_actuacio() -> None:
    props = {
        "ACT_NUM_ACTUACIO": "262311630",
        "MUNICIPI_SIG": "Sant Quirze Safaja",
        "ACT_DAT_INICI": 1782300143000,
        "OBJECTID": 1063216,
    }
    assert incident_key(props) == "262311630"


def test_incident_key_falls_back_to_municipi_and_inici() -> None:
    props = {
        "MUNICIPI_SIG": "Beuda",
        "ACT_DAT_INICI": 1786169257000,
        "OBJECTID": 1098362,
    }
    assert incident_key(props) == "Beuda|1786169257000"


def test_incident_key_fallback_uses_municipi_dpx_when_sig_missing() -> None:
    props = {"MUNICIPI_DPX": "Girona", "ACT_DAT_INICI": 123}
    assert incident_key(props) == "Girona|123"


def test_incident_key_falls_back_to_objectid_when_municipi_missing() -> None:
    props = {"ACT_DAT_INICI": 123, "OBJECTID": 1098362}
    assert incident_key(props) == "1098362"


def test_incident_key_falls_back_to_global_id_when_objectid_missing() -> None:
    props = {"GlobalID": "27a255d0-c5d2-41b2-9a8b-0bb9fe90d1f5"}
    assert incident_key(props) == "27a255d0-c5d2-41b2-9a8b-0bb9fe90d1f5"


def test_incident_key_empty_when_nothing_identifying_is_present() -> None:
    assert incident_key({}) == ""


def test_incident_key_stable_across_repeated_snapshot_rows() -> None:
    """Two snapshot rows for the same incident (differing only in the fields
    an edit changes) must still collapse to one dedup key."""
    first = {"MUNICIPI_SIG": "Beuda", "ACT_DAT_INICI": 1786169257000, "ACT_NUM_VEH": 0}
    second = {"MUNICIPI_SIG": "Beuda", "ACT_DAT_INICI": 1786169257000, "ACT_NUM_VEH": 3}
    assert incident_key(first) == incident_key(second)


def test_from_feature_uses_fallback_key_when_act_num_actuacio_missing() -> None:
    """End-to-end: a feature from a FeatureServer that no longer exposes
    ACT_NUM_ACTUACIO must still get a non-empty, usable act_num instead of
    being silently unidentifiable (see arcgis.py's _dedupe_features)."""
    feature = {
        "geometry": {"coordinates": [2.94417396346624, 42.2670258516484]},
        "properties": {
            "MUNICIPI_SIG": "Mont-ral",
            "ACT_DAT_INICI": 1785844601000,
            "COM_FASE": "Controlat",
            "OBJECTID": 1095455,
        },
    }
    inc = Incident.from_feature(feature)
    assert inc.act_num == "Mont-ral|1785844601000"
    assert inc.municipi == "Mont-ral"
