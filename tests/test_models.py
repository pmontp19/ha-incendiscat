"""Tests for models.py: Fase, Tipus, Incident.from_feature()."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest
from custom_components.bomberscat.models import Fase, Incident, Tipus

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


def test_com_fase_unknown_value_maps_to_actiu() -> None:
    feature = {
        "geometry": {"type": "Point", "coordinates": [2.0, 41.0]},
        "properties": {"ACT_NUM_ACTUACIO": "1", "COM_FASE": "Something New"},
    }
    inc = Incident.from_feature(feature)
    assert inc.fase == Fase.ACTIU


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
