"""#1135 Symptom 1 — Plausibilitaets-Gate fuer amtliche Hitzewarnungen.

SPEC: docs/specs/modules/issue_1135_heat_warning_plausibility.md (AC-3..AC-7)
KONTEXT: docs/context/fix-1135-heat-warning.md

PO-Entscheidung (2026-07-15): eine amtliche `extreme_heat`-Vigilance-Warnung
wird im Trip-Briefing fuer eine Etappe AUSGEBLENDET, wenn die dort modellierte
gefuehlte Hoechsttemperatur (`wind_chill_max_c`) klar unter der Hitzeschwelle
(25 C) liegt. Fehlen die Daten (None), wird NICHT unterdrueckt (Fail-safe).
Nicht-Hitze-Warnungen (Wind/Gewitter) bleiben unberuehrt.

RED-Grund (heute rot):
- `SegmentWeatherSummary` kennt das Feld `wind_chill_max_c` noch nicht
  -> TypeError schon beim Segment-Aufbau (AC-7 + alle Gate-Tests).
- Selbst mit Feld: es gibt noch kein Plausibilitaets-Gate im Briefing-Pfad
  -> AC-3 wuerde die Hitzewarnung weiter zeigen.

Kern-Schicht (deterministisch): echte DTOs, echter `render_html`, Auswertung
am gerenderten HTML per BeautifulSoup. Kein Netz, kein Mock, keine IMAP.
"""
from __future__ import annotations

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from bs4 import BeautifulSoup

TZ = ZoneInfo("Europe/Paris")
UTC = timezone.utc
HEAT_FROM = datetime(2026, 7, 15, 6, 0, tzinfo=UTC)
HEAT_TO = datetime(2026, 7, 15, 20, 0, tzinfo=UTC)


def _heat_alert(region: str = "06", level: int = 3):
    from services.official_alerts.models import OfficialAlert
    return OfficialAlert(
        source="meteofrance_vigilance", hazard="extreme_heat", level=level,
        label="Extreme Hitze", valid_from=HEAT_FROM, valid_to=HEAT_TO,
        region_label=region,
    )


def _thunder_alert(region: str = "06", level: int = 3):
    from services.official_alerts.models import OfficialAlert
    return OfficialAlert(
        source="meteofrance_vigilance", hazard="thunderstorm", level=level,
        label="Gewitter", valid_from=HEAT_FROM, valid_to=HEAT_TO,
        region_label=region,
    )


def _segment(seg_id: int, *, felt_max, alerts):
    """Ein Trip-Segment mit gesetzter gefuehlter Hoechsttemperatur
    (`wind_chill_max_c`) und amtlichen Warnungen."""
    from app.models import (
        ForecastDataPoint, ForecastMeta, GPXPoint, NormalizedTimeseries,
        Provider, SegmentWeatherData, SegmentWeatherSummary, ThunderLevel,
        TripSegment,
    )

    seg = TripSegment(
        segment_id=seg_id,
        start_point=GPXPoint(lat=44.0 + seg_id * 0.1, lon=6.0 + seg_id * 0.1, elevation_m=1800.0),
        end_point=GPXPoint(lat=44.05 + seg_id * 0.1, lon=6.05 + seg_id * 0.1, elevation_m=2000.0),
        start_time=datetime(2026, 7, 15, 8, 0, tzinfo=UTC),
        end_time=datetime(2026, 7, 15, 14, 0, tzinfo=UTC),
        duration_hours=6.0, distance_km=6.0, ascent_m=300.0, descent_m=100.0,
    )
    rows = [
        ForecastDataPoint(
            ts=datetime(2026, 7, 15, h, 0), t2m_c=17.0, wind10m_kmh=12.0,
            precip_1h_mm=0.0, thunder_level=ThunderLevel.NONE,
        )
        for h in range(8, 15)
    ]
    summary = SegmentWeatherSummary(
        temp_max_c=19.0, temp_min_c=12.0, wind_max_kmh=12.0,
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
    "time": "08:00", "temp": 17.0, "_wind_dir_deg": None, "_is_day": True,
    "_dni_wm2": None, "_sunny_hours": 0.0, "_wmo_code": None,
}]


def _render(segs) -> BeautifulSoup:
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.html import render_html
    html = render_html(
        segments=segs, seg_tables=[_SIMPLE_ROWS] * len(segs),
        trip_name="TDD-1135", report_type="morning",
        dc=build_default_display_config(), night_rows=[],
        thunder_forecast=None, changes=None, stage_name=None, stage_stats=None,
        multi_day_trend=None, compact_summary=None, tz=TZ, friendly_keys=set(),
    )
    return BeautifulSoup(html, "html.parser")


def _heat_items(soup: BeautifulSoup) -> list:
    """Alle amtlichen Warn-Karten (`.wb-item`) im embedded WarnBlock, deren
    Text auf eine Hitzewarnung zeigt."""
    return [it for it in soup.select(".wb-item") if "Hitze" in it.get_text(" ", strip=True)]


def _warn_items(soup: BeautifulSoup) -> list:
    return soup.select(".wb-item")


# ---------------------------------------------------------------------------
# AC-7 — neues Segment-Feld: gefuehlte Hoechsttemperatur (MAX)
# ---------------------------------------------------------------------------

def test_ac7_segment_summary_exposes_felt_max():
    """AC-7: Given eine Segment-Zeitreihe mit `wind_chill_c`-Werten
    [10, 22, 31, 27] / When die erweiterte Segment-Zusammenfassung berechnet
    wird / Then ist `wind_chill_max_c == 31` (das Maximum), analog zum
    bestehenden `wind_chill_min_c`."""
    from app.models import (
        ForecastDataPoint, ForecastMeta, NormalizedTimeseries, Provider,
        SegmentWeatherSummary, ThunderLevel,
    )
    from services.weather_metrics import WeatherMetricsService

    values = [10.0, 22.0, 31.0, 27.0]
    rows = [
        ForecastDataPoint(
            ts=datetime(2026, 7, 15, 8 + i, 0), t2m_c=v + 2, wind_chill_c=v,
            thunder_level=ThunderLevel.NONE,
        )
        for i, v in enumerate(values)
    ]
    ts = NormalizedTimeseries(
        meta=ForecastMeta(provider=Provider.OPENMETEO, model="best_match", grid_res_km=2.0),
        data=rows,
    )
    basis = SegmentWeatherSummary(
        temp_max_c=33.0, temp_min_c=12.0, wind_max_kmh=10.0,
        thunder_level_max=ThunderLevel.NONE, precip_sum_mm=0.0,
    )
    result = WeatherMetricsService().compute_extended_metrics(ts, basis)
    assert result.wind_chill_max_c == 31.0, (
        f"gefuehlte Hoechsttemperatur (wind_chill_max_c) falsch/fehlt: "
        f"{getattr(result, 'wind_chill_max_c', 'FEHLT')!r} (erwartet 31.0)"
    )
    # Non-Regression: das bestehende MIN bleibt unveraendert korrekt.
    assert result.wind_chill_min_c == 10.0


# ---------------------------------------------------------------------------
# AC-3 — Hitzewarnung wird bei klarem Widerspruch ausgeblendet
# ---------------------------------------------------------------------------

def test_ac3_heat_warning_suppressed_when_felt_max_below_threshold():
    """AC-3: Given eine Etappe mit einer amtlichen `extreme_heat`-Warnung, aber
    die dort modellierte gefuehlte Hoechsttemperatur betraegt 18 C (< 25 C) /
    When das Trip-Briefing gerendert wird / Then erscheint fuer diese Etappe
    KEINE Hitzewarnung."""
    soup = _render([_segment(1, felt_max=18.0, alerts=[_heat_alert()])])
    assert _heat_items(soup) == [], (
        "Hitzewarnung trotz gefuehlt max 18 C (< 25 C) noch sichtbar — "
        "Plausibilitaets-Gate greift nicht."
    )


def test_ac3_boundary_just_below_threshold_suppressed():
    """AC-3 (Grenzfall knapp darunter): 24.9 C < 25 C -> unterdrueckt."""
    soup = _render([_segment(1, felt_max=24.9, alerts=[_heat_alert()])])
    assert _heat_items(soup) == [], (
        "Hitzewarnung bei gefuehlt max 24.9 C (< 25 C) muss unterdrueckt werden."
    )


# ---------------------------------------------------------------------------
# AC-4 — Hitzewarnung bleibt bei plausibler Hitze sichtbar
# ---------------------------------------------------------------------------

def test_ac4_heat_warning_shown_when_felt_max_at_or_above_threshold():
    """AC-4: Given eine Etappe mit `extreme_heat`-Warnung und gefuehlter
    Hoechsttemperatur 31 C (>= 25 C) / When das Briefing gerendert wird / Then
    wird die Hitzewarnung ANGEZEIGT."""
    soup = _render([_segment(1, felt_max=31.0, alerts=[_heat_alert()])])
    assert len(_heat_items(soup)) == 1, (
        "Hitzewarnung bei plausibler Hitze (gefuehlt max 31 C) fehlt — "
        "Gate unterdrueckt faelschlich."
    )


def test_ac4_boundary_exactly_threshold_shown():
    """AC-4 (Grenzfall genau auf der Schwelle): 25.0 C ist NICHT < 25 C
    -> Warnung bleibt sichtbar."""
    soup = _render([_segment(1, felt_max=25.0, alerts=[_heat_alert()])])
    assert len(_heat_items(soup)) == 1, (
        "Hitzewarnung bei gefuehlt max genau 25.0 C muss sichtbar bleiben "
        "(Schwelle ist strikt '<', 25 wird gezeigt)."
    )


# ---------------------------------------------------------------------------
# AC-5 — Fail-safe: fehlende Temperaturdaten -> nie unterdruecken
# ---------------------------------------------------------------------------

def test_ac5_heat_warning_shown_when_felt_max_unavailable():
    """AC-5 (Fail-safe): Given eine Etappe mit `extreme_heat`-Warnung, aber es
    liegt KEINE gefuehlte Temperatur vor (`wind_chill_max_c` ist None) / When
    das Briefing gerendert wird / Then wird die Warnung ANGEZEIGT — eine
    amtliche Warnung wird bei fehlenden Daten niemals unterdrueckt."""
    soup = _render([_segment(1, felt_max=None, alerts=[_heat_alert()])])
    assert len(_heat_items(soup)) == 1, (
        "Bei fehlender gefuehlter Temperatur (None) darf die amtliche "
        "Hitzewarnung NICHT unterdrueckt werden (Fail-safe verletzt)."
    )


# ---------------------------------------------------------------------------
# AC-6 — Gate greift ausschliesslich auf Hitze
# ---------------------------------------------------------------------------

def test_ac6_non_heat_warning_unaffected_by_gate():
    """AC-6: Given eine Etappe mit gefuehlt max 15 C, die eine Gewitter-Warnung
    (Nicht-Hitze) traegt / When das Briefing gerendert wird / Then bleibt diese
    Warnung unveraendert sichtbar — das Plausibilitaets-Gate wirkt nur auf
    `extreme_heat`, nicht auf Wind/Gewitter."""
    soup = _render([_segment(1, felt_max=15.0, alerts=[_thunder_alert()])])
    items = _warn_items(soup)
    assert len(items) == 1, (
        "Gewitter-Warnung bei niedriger gefuehlter Temperatur wurde faelschlich "
        "vom Hitze-Gate mitgefiltert."
    )
    assert "Gewitter" in items[0].get_text(" ", strip=True), (
        f"Erwartete Gewitter-Warnung fehlt: {items[0].get_text(' ', strip=True)!r}"
    )
