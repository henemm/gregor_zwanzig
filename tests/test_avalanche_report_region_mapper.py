"""Generischer Punkt-in-Region-Mapper und Grenzpunkt-Politik (AC-9, AC-10).

SPEC: docs/specs/modules/avalanche_report_bulletin.md -- AC-9, AC-10
VERTRAG: docs/artifacts/feat-1441-s1-lawinenlagebericht/red-contract.md Abschnitt 3

Geometrie = die aufgezeichneten EAWS-Regionen (CC0). Der Grenzpunkt ist ein echter Eckpunkt der
gemeinsamen Kante von AT-07-04-02 und AT-07-16 (README.md der Fixtures); die Voraussetzung "liegt in
beiden Polygonen" wird unabhaengig vom Mapper mit `geo_ray_cast._point_in_ring` selbst bewiesen.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from tests.helpers.avalanche_report_support import (
    P_BORDER, P_TIROL_AT_07_28, REGIONS, FakeClock, FixtureTransport, Reply, fixture_table,
    make_source, raw,
)

UTC = timezone.utc
AT_07 = REGIONS / "AT-07_micro-regions.geojson.json"
_REPO = Path(__file__).resolve().parents[1]


def _polygone(region_id: str):
    for feature in json.loads(AT_07.read_text(encoding="utf-8"))["features"]:
        if feature["properties"]["id"] == region_id:
            return feature["geometry"]["coordinates"]
    raise KeyError(region_id)


def _liegt_in(region_id: str, lat: float, lon: float) -> bool:
    from services.official_alerts.geo_ray_cast import _point_in_ring

    return any(
        _point_in_ring(lat, lon, [tuple(p) for p in poly[0]])
        and not any(_point_in_ring(lat, lon, [tuple(p) for p in hole]) for hole in poly[1:])
        for poly in _polygone(region_id)
    )


# ---------------------------------------------------------------- Voraussetzung des Grenzpunkts
def test_ac9_voraussetzung_grenzpunkt_liegt_nach_dem_bestands_raycast_in_beiden_polygonen():
    assert _liegt_in("AT-07-04-02", *P_BORDER)
    assert _liegt_in("AT-07-16", *P_BORDER)


# ---------------------------------------------------------------- RegionMapper
def test_ac9_mapper_liefert_beide_regionen_am_grenzpunkt_und_bei_jedem_lauf_gleich():
    from services.official_alerts.region_mapper import RegionMapper

    ergebnisse = [RegionMapper(AT_07).regions_at(*P_BORDER) for _ in range(5)]
    mapper = RegionMapper(AT_07)
    ergebnisse += [mapper.regions_at(*P_BORDER) for _ in range(5)]

    assert all(e == ["AT-07-04-02", "AT-07-16"] for e in ergebnisse), ergebnisse


def test_ac9_innerer_punkt_trifft_genau_eine_region_und_ein_punkt_ausserhalb_keine():
    from services.official_alerts.region_mapper import RegionMapper

    mapper = RegionMapper(AT_07)

    assert mapper.regions_at(*P_TIROL_AT_07_28) == ["AT-07-28"]
    assert mapper.regions_at(48.1371, 11.5754) == []          # Muenchen


def test_ac9_mapper_bounding_box_umschliesst_alle_features():
    from services.official_alerts.region_mapper import RegionMapper

    min_lon, min_lat, max_lon, max_lat = RegionMapper(AT_07).bbox()

    assert (round(min_lon, 3), round(min_lat, 3), round(max_lon, 3), round(max_lat, 3)) == (
        10.098, 46.651, 12.963, 47.743)


def test_ac9_mapper_beachtet_loecher(tmp_path):
    """Ein Punkt im Loch eines Polygons gehoert nicht zur Region (synthetische Geometrie)."""
    from services.official_alerts.region_mapper import RegionMapper

    aussen = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
    loch = [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]
    pfad = tmp_path / "donut.geojson.json"
    pfad.write_text(json.dumps({"type": "FeatureCollection", "features": [{
        "type": "Feature", "properties": {"id": "XX-01"},
        "geometry": {"type": "MultiPolygon", "coordinates": [[aussen, loch]]},
    }]}), encoding="utf-8")

    mapper = RegionMapper(pfad)

    assert mapper.regions_at(5.0, 5.0) == []           # lat 5, lon 5: im Loch
    assert mapper.regions_at(1.0, 1.0) == ["XX-01"]


@pytest.mark.parametrize("inhalt", [None, "{kaputt", '{"type": "FeatureCollection"}', "[]"],
                         ids=["fehlt", "kein-json", "ohne-features", "falscher-typ"])
def test_ac9_mapper_ist_fail_soft_bei_fehlender_oder_kaputter_datei(tmp_path, inhalt):
    from services.official_alerts.region_mapper import RegionMapper

    pfad = tmp_path / "x.geojson.json"
    if inhalt is not None:
        pfad.write_text(inhalt, encoding="utf-8")

    mapper = RegionMapper(pfad)

    assert mapper.regions_at(47.0, 11.0) == []
    assert mapper.bbox() is None


# ---------------------------------------------------------------- Grenzpunkt-Politik der Quelle
def _quelle(datei: str):
    transport = FixtureTransport({"AT-07": Reply(200, raw(datei))})
    clock = FakeClock(datetime(2026, 2, 20, 8, 0, tzinfo=UTC))
    return transport, make_source(transport, clock, table=fixture_table(keys=("AT-07",)))


@pytest.mark.parametrize("datei, stufen", [
    ("2026-02-20_AT-07_de_CAAMLv6.json", (3, 4)),                                       # echt
    ("derived/2026-02-20_AT-07_de_CAAMLv6_DERIVED_border_2_4.json", (2, 4)),            # abgeleitet (README)
], ids=["echt-3-4", "abgeleitet-2-4"])
def test_ac9_grenzpunkt_meldet_die_hoechste_stufe_mit_der_url_der_tragenden_region(datei, stufen):
    for _ in range(3):                                                  # "bei jedem Lauf gleich"
        transport, source = _quelle(datei)
        alerts = source.fetch(*P_BORDER)

        assert len(alerts) == 1, alerts
        assert alerts[0].native_level == max(stufen)
        assert alerts[0].url == "https://avalanche.report/bulletin/2026-02-20?region=AT-07-16"
        assert alerts[0].dedup_id == "avalanche_bulletin:AT-07-16"
        assert transport.served("AT-07") == 1


def test_ac9_bei_gleichstand_gewinnt_die_kleinste_regions_id():
    datei = "derived/2026-02-20_AT-07_de_CAAMLv6_DERIVED_border_4_4.json"
    urls = set()
    for _ in range(5):
        _transport, source = _quelle(datei)
        (alert,) = source.fetch(*P_BORDER)
        urls.add(alert.url)
        assert alert.native_level == 4

    assert urls == {"https://avalanche.report/bulletin/2026-02-20?region=AT-07-04-02"}


# ---------------------------------------------------------------- AC-10: MeteoAlarm nutzt den Mapper
def test_ac10_meteoalarm_nutzt_den_gemeinsamen_mapper_und_keine_eigene_kopie():
    """Seit #2266 (Rueckbau der EDR-Klasse) braucht ``meteoalarm.py`` keine
    Punkt-in-Flaeche-Pruefung mehr: es darf weder einen Alias noch eine eigene
    Kopie der Geometrie-Logik tragen -- die Trefferlogik lebt allein im Mapper."""
    from services.official_alerts import meteoalarm, region_mapper

    assert not hasattr(meteoalarm, "_point_in_geometry")
    assert not hasattr(meteoalarm, "_point_in_ring")
    assert Path(region_mapper.__file__).resolve().is_relative_to(_REPO)


_QUADRAT = [[0, 0], [10, 0], [10, 10], [0, 10], [0, 0]]
_LOCH = [[4, 4], [6, 4], [6, 6], [4, 6], [4, 4]]
_GEOMETRIEN = [
    ("polygon-innen", {"type": "Polygon", "coordinates": [_QUADRAT]}, (5.0, 2.0), True),
    ("polygon-aussen", {"type": "Polygon", "coordinates": [_QUADRAT]}, (20.0, 2.0), False),
    ("polygon-loch", {"type": "Polygon", "coordinates": [_QUADRAT, _LOCH]}, (5.0, 5.0), False),
    ("multipolygon-zweites", {"type": "MultiPolygon", "coordinates": [
        [_QUADRAT], [[[20, 20], [30, 20], [30, 30], [20, 30], [20, 20]]]]}, (25.0, 25.0), True),
    ("multipolygon-keiner", {"type": "MultiPolygon", "coordinates": [[_QUADRAT]]}, (25.0, 25.0), False),
    ("punkt-typ", {"type": "Point", "coordinates": [1, 1]}, (1.0, 1.0), False),
    ("leer", {"type": "Polygon", "coordinates": []}, (1.0, 1.0), False),
    ("ohne-koordinaten", {"type": "MultiPolygon"}, (1.0, 1.0), False),
]


# Die fruehere Regressionswache ueber den Alias ``meteoalarm._point_in_geometry``
# entfiel mit #2266; dieselben Bestandsfaelle prueft der folgende Test direkt am
# Ursprungsmodul ``region_mapper.point_in_geometry``.
@pytest.mark.parametrize("name, geometrie, punkt, erwartet", _GEOMETRIEN, ids=[g[0] for g in _GEOMETRIEN])
def test_ac10_mapper_liefert_fuer_dieselben_faelle_dieselben_treffer(name, geometrie, punkt, erwartet):
    from services.official_alerts.region_mapper import point_in_geometry

    lat, lon = punkt
    assert point_in_geometry(lat, lon, geometrie) is erwartet
