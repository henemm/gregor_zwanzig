"""#1135 Symptom 2 — Mehrfach-Anzeige derselben Hitzewarnung im Trip-Briefing.

SPEC: docs/specs/modules/issue_1135_heat_warning_plausibility.md (AC-1, AC-2)
KONTEXT: docs/context/fix-1135-heat-warning.md

Root-Cause (bewiesen): der Briefing-HTML-Pfad (`html.py`) verdichtet amtliche
Warnungen nur ueber `dedupe_official_alerts` (Stufe 1, Schluessel enthaelt das
`region_label` = Departement-Code) und NICHT ueber die regionsuebergreifende
Buendelung `_bundle_by_hazard_level` (Stufe 2), die Alarm- und Compare-Pfad
bereits nutzen. Ein Trip durch drei Departements unter derselben nationalen
Hitzewelle erzeugt dadurch drei optisch identische Karten. #1254
(Point-in-Polygon) hat das real verschaerft.

RED-Grund (heute rot):
- AC-1: drei Hitzewarnungen (drei Departements, gleiche Stufe + Gueltigkeit)
  ergeben aktuell DREI `.wb-item`-Karten statt einer gebuendelten.
- Alle Tests konstruieren `SegmentWeatherSummary(wind_chill_max_c=...)`, das
  Feld existiert noch nicht -> TypeError beim Aufbau (bis Symptom 1 den Feld
  einfuehrt; beide Symptome teilen denselben Fix-Workflow).

Kern-Schicht (deterministisch): echte DTOs, echter `render_html`, Auswertung
am HTML per BeautifulSoup. Kein Netz, kein Mock.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

TZ = ZoneInfo("Europe/Paris")
UTC = timezone.utc
HEAT_FROM = datetime(2026, 7, 15, 6, 0, tzinfo=UTC)
HEAT_TO = datetime(2026, 7, 15, 20, 0, tzinfo=UTC)


def _heat_alert(region: str, level: int = 3, vf=HEAT_FROM, vt=HEAT_TO):
    from services.official_alerts.models import OfficialAlert
    return OfficialAlert(
        source="meteofrance_vigilance", hazard="extreme_heat", level=level,
        label="Extreme Hitze", valid_from=vf, valid_to=vt, region_label=region,
    )


def _segment(seg_id: int, *, alerts, felt_max=32.0):
    """Trip-Segment mit plausibel hoher gefuehlter Temperatur (>= 25 C, damit
    das Symptom-1-Gate die Warnung NICHT ausblendet) und amtlichen Warnungen."""
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
        TripSegment,
    )

    seg = TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=43.0 + seg_id * 0.3, lon=5.0 + seg_id * 0.3, elevation_m=200.0),
        end_point=GPXPoint(lat=43.1 + seg_id * 0.3, lon=5.1 + seg_id * 0.3, elevation_m=300.0),
        start_time=datetime(2026, 7, 15, 8, 0, tzinfo=UTC),
        end_time=datetime(2026, 7, 15, 14, 0, tzinfo=UTC),
        duration_hours=6.0, distance_km=6.0, ascent_m=100.0, descent_m=100.0,
    )
    rows = [
        ForecastDataPoint(
            ts=datetime(2026, 7, 15, h, 0), t2m_c=33.0, wind10m_kmh=8.0,
            precip_1h_mm=0.0, thunder_level=ThunderLevel.NONE,
        )
        for h in range(8, 15)
    ]
    summary = SegmentWeatherSummary(
        temp_max_c=34.0, temp_min_c=22.0, wind_max_kmh=8.0,
        thunder_level_max=ThunderLevel.NONE, precip_sum_mm=0.0,
        wind_chill_max_c=felt_max,
    )
    return SegmentWeatherData(
        segment=seg,
        timeseries=NormalizedTimeseries(
            meta=ForecastMeta(provider=Provider.OPENMETEO, model="best_match", grid_res_km=2.0),
            data=rows,
        ),
        aggregated=summary,
        fetched_at=datetime(2026, 7, 14, tzinfo=UTC),
        provider="openmeteo",
        official_alerts=alerts,
    )


_SIMPLE_ROWS = [{
    "time": "08:00", "temp": 33.0, "_wind_dir_deg": None, "_is_day": True,
    "_dni_wm2": None, "_sunny_hours": 0.0, "_wmo_code": None,
}]


def _render(segs) -> BeautifulSoup:
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.html import render_html
    html = render_html(
        segments=segs, seg_tables=[_SIMPLE_ROWS] * len(segs),
        trip_name="TDD-1135-bundle", report_type="morning",
        dc=build_default_display_config(), night_rows=[],
        thunder_forecast=None, changes=None, stage_name=None, stage_stats=None,
        multi_day_trend=None, compact_summary=None, tz=TZ, friendly_keys=set(),
    )
    return BeautifulSoup(html, "html.parser")


def _heat_items(soup: BeautifulSoup) -> list:
    return [it for it in soup.select(".wb-item") if "Hitze" in it.get_text(" ", strip=True)]


# ---------------------------------------------------------------------------
# AC-1 — drei Departements, dieselbe Hitzewarnung -> EINE gebuendelte Karte
# ---------------------------------------------------------------------------

def test_ac1_same_heat_across_departments_bundled_into_one_card():
    """AC-1: Given ein Trip kreuzt drei Departements (Segmente 1, 3, 5), die
    alle unter derselben `extreme_heat`-Vigilance gleicher Stufe und gleichem
    Gueltigkeitsfenster stehen (jede Etappe plausibel heiss) / When das
    Trip-Briefing gerendert wird / Then erscheint GENAU EINE Hitze-Warnkarte,
    deren Streckenbezug ALLE drei betroffenen Segmente nennt — nicht drei
    separate, optisch identische Karten."""
    segs = [
        _segment(1, alerts=[_heat_alert("83")]),
        _segment(3, alerts=[_heat_alert("13")]),
        _segment(5, alerts=[_heat_alert("06")]),
    ]
    soup = _render(segs)
    heat = _heat_items(soup)
    assert len(heat) == 1, (
        f"Dieselbe Hitzewarnung ueber drei Departements erscheint {len(heat)}x "
        "statt gebuendelt als eine Karte (Symptom 2 'warum 3x')."
    )
    # Nicht bloss eine ueberlebende Einzel-Karte: die gebuendelte Karte muss den
    # gesamten betroffenen Streckenbezug tragen (Segmente 1, 3, 5) -- schuetzt
    # gegen einen verlustbehafteten Kurzschluss, der zwei Departements einfach
    # verwirft.
    route = heat[0].get_text(" ", strip=True)
    for seg_no in ("1", "3", "5"):
        assert seg_no in route, (
            f"Gebuendelte Karte nennt Segment {seg_no} nicht "
            f"(Streckenbezug ging verloren): {route!r}"
        )
    # F001 (Adversary, HIGH): die gebuendelte Karte muss zusaetzlich die NAMEN
    # aller drei betroffenen Departements nennen (nicht nur die Codes, nicht
    # nur des Buendel-Repraesentanten) -- sonst weiss niemand, welche
    # Departements tatsaechlich betroffen sind.
    for dep_name in ("Var", "Bouches-du-Rhône", "Alpes-Maritimes"):
        assert dep_name in route, (
            f"Gebuendelte Karte nennt Departement-Namen {dep_name!r} nicht "
            f"(nur Codes statt Namen?): {route!r}"
        )


# ---------------------------------------------------------------------------
# AC-2 — verschiedene Stufen bleiben getrennt (Guard gegen Ueberbuendelung)
# ---------------------------------------------------------------------------

def test_ac2_different_levels_stay_separate():
    """AC-2: Given zwei Hitzewarnungen UNTERSCHIEDLICHER Stufe (Segment 1
    orange/Level 3, Segment 2 gelb/Level 2), beide Etappen plausibel heiss /
    When das Briefing gerendert wird / Then bleiben beide als getrennte
    Warnungen sichtbar — verschiedene Stufe ist fachlich eine verschiedene
    Warnung und darf nicht zu einer Karte kollabieren."""
    segs = [
        _segment(1, alerts=[_heat_alert("04", level=3)]),
        _segment(2, alerts=[_heat_alert("05", level=2)]),
    ]
    soup = _render(segs)
    heat = _heat_items(soup)
    assert len(heat) == 2, (
        f"Hitzewarnungen unterschiedlicher Stufe wurden zu {len(heat)} Karte(n) "
        "ueberbuendelt — verschiedene Stufen muessen getrennt bleiben."
    )
