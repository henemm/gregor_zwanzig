"""Amtliche Warnungen in Mails dürfen nicht doppelt erscheinen (#1217/#1218).

Konsolidierung aller Dedup-Pfade auf `dedupe_official_alerts`
((region_label, hazard), höchste Stufe, Segment-Union) + Segment-Bezug im
Trip-Briefing. Verhaltenstests, KEINE Mocks: echte OfficialAlert-Datenklassen
durch die echten Renderpfade (render_compare_html / _render_overview_row /
render_html).

RED-Stand (vor Fix):
- Compare-Übersichts-Chips (_render_warn_cell) bekommen rohen, undeduplizierten
  Input (compare_html.py:244) -> Chip doppelt (#1218).
- Übersichts-Chip und Pro-Ort-Streifen nutzen verschiedene Dedup-Strategien
  (roh vs. _dedup_alerts) -> Anzahlen divergieren.
- Trip-Briefing nutzt collect_trip_alert_entries (Gruppe region_label, Objekt-
  Gleichheit) -> Fast-Duplikate (gleiche region_label+hazard, andere Stufe)
  rutschen durch (#1217); Segment-Bezug fehlt komplett.
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from zoneinfo import ZoneInfo

from app.models import ForecastDataPoint
from app.profile import ActivityProfile
from app.user import ComparisonResult, LocationResult, SavedLocation
from output.renderers.email.compare_html import _render_overview_row, render_compare_html
from output.renderers.email.html import render_html
from services.official_alerts.models import OfficialAlert

# Distinktive Zähl-Signaturen der zwei Render-Boundaries:
CHIP_SIG = "font-size:9.5px;font-weight:700"      # _render_warn_cell Übersichts-Chip
BADGE_SIG = "padding:8px 16px;margin:8px 20px"    # render_official_alerts_html Pro-Ort-Streifen-Badge
WARN_METRIC = {"key": "warn", "label": "Amtliche Warnungen"}


def _heat(level: int = 3, *, region: str = "Haute-Corse", label: str | None = None,
          hazard: str = "extreme_heat") -> OfficialAlert:
    return OfficialAlert(
        source="test-dedup", hazard=hazard, level=level,
        label=label or f"Hitzewarnung {region}", region_label=region,
    )


def _loc_with_alerts(loc_id: str, name: str, alerts: list[OfficialAlert]) -> LocationResult:
    loc = SavedLocation(id=loc_id, name=name, lat=42.15, lon=9.05, elevation_m=800)
    dp = ForecastDataPoint(ts=datetime(2026, 7, 9, 9, 0), t2m_c=34.0)
    return LocationResult(location=loc, score=70, official_alerts=alerts, hourly_data=[dp])


def _seg_with_alerts(segment_id: int, alerts: list[OfficialAlert]):
    from app.models import (
        ForecastMeta, GPXPoint, NormalizedTimeseries, Provider,
        SegmentWeatherData, SegmentWeatherSummary, ThunderLevel, TripSegment,
    )
    seg = TripSegment(
        segment_id=segment_id,
        start_point=GPXPoint(lat=42.13, lon=9.13, elevation_m=900.0),
        end_point=GPXPoint(lat=42.10, lon=9.18, elevation_m=1450.0),
        start_time=datetime(2026, 7, 11, 8, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 11, 12, 0, tzinfo=timezone.utc),
        duration_hours=4.0, distance_km=14.5, ascent_m=820.0, descent_m=440.0,
    )
    meta = ForecastMeta(provider=Provider.OPENMETEO, model="demo", grid_res_km=1.3)
    data = [
        ForecastDataPoint(
            ts=datetime(2026, 7, 11, h, 0, tzinfo=timezone.utc),
            t2m_c=20.0, wind10m_kmh=15.0, precip_1h_mm=0.0,
            thunder_level=ThunderLevel.NONE,
        )
        for h in range(8, 13)
    ]
    ts = NormalizedTimeseries(meta=meta, data=data)
    agg = SegmentWeatherSummary(
        temp_min_c=14.0, temp_max_c=22.0, wind_max_kmh=22.0,
        precip_sum_mm=0.0, thunder_level_max=ThunderLevel.NONE,
    )
    return SegmentWeatherData(
        segment=seg, timeseries=ts, aggregated=agg,
        fetched_at=datetime.now(timezone.utc), provider="demo",
        official_alerts=alerts,
    )


def _render_trip_html(segments) -> str:
    from app.metric_catalog import build_default_display_config
    return render_html(
        segments=segments, seg_tables=[[] for _ in segments],
        trip_name="Test GR20", report_type="morning",
        dc=build_default_display_config(), night_rows=[],
        thunder_forecast=None, changes=None, stage_name="Etappe",
        stage_stats=None, multi_day_trend=None, compact_summary="ok",
        tz=ZoneInfo("Europe/Berlin"), friendly_keys=set(),
    )


# ---------------------------------------------------------------------------
# AC-1 (#1218): Übersichts-Chip erscheint genau einmal je (region_label, hazard)
# ---------------------------------------------------------------------------

def test_ac1_overview_chip_dedups_same_region_hazard():
    """Zwei Hitze-Warnungen gleicher (region_label, hazard), verschiedene Stufe
    -> Übersichts-Chip genau EINMAL (höchste Stufe). RED: heute 2 Chips (roher
    Input in compare_html.py:244)."""
    loc = _loc_with_alerts("l1", "Ospedale", [_heat(2), _heat(4)])
    row = _render_overview_row(WARN_METRIC, [loc])
    assert row.count(CHIP_SIG) == 1, (
        f"Übersichts-Chip muss genau 1x erscheinen (Dedup fehlt), "
        f"gefunden {row.count(CHIP_SIG)}x"
    )


# ---------------------------------------------------------------------------
# AC-2 (#1218): Übersichts-Chip und Pro-Ort-Streifen deduplizieren identisch
# ---------------------------------------------------------------------------

def test_ac2_overview_and_strip_use_same_dedup():
    """Identische Warnung doppelt -> Chip-Anzahl == Streifen-Badge-Anzahl == 1.
    RED: heute Chips=2 (roh), Badges=1 (_dedup_alerts) -> divergent."""
    a = _heat(3, label="Hitze identisch")
    b = _heat(3, label="Hitze identisch")
    loc = _loc_with_alerts("l2", "Ospedale", [a, b])
    result = ComparisonResult(locations=[loc], time_window=(9, 16), target_date=date.today())
    html = render_compare_html(result, profile=ActivityProfile.ALLGEMEIN)
    chips = html.count(CHIP_SIG)
    badges = html.count(BADGE_SIG)
    assert chips == badges, (
        f"Übersichts-Chip ({chips}) und Pro-Ort-Streifen ({badges}) müssen "
        f"dieselbe entdoppelte Menge zeigen (eine gemeinsame Dedup-Quelle)"
    )
    assert chips == 1, f"Identische Warnung muss auf 1 Chip kollabieren, war {chips}"


# ---------------------------------------------------------------------------
# AC-3 (#1217): Trip-Briefing zeigt dieselbe Warnung genau einmal
# ---------------------------------------------------------------------------

def test_ac3_trip_briefing_dedups_same_region_hazard():
    """Dieselbe Warnung über zwei Etappen (gleiche region_label+hazard+label,
    verschiedene Stufe) -> im Briefing genau EINMAL. RED: heute 2x, weil
    collect_trip_alert_entries nur nach Objekt-Gleichheit entdoppelt und die
    verschieden-stufigen Alerts beide durchlässt."""
    label = "Hitzewarnung Haute-Corse"
    seg1 = _seg_with_alerts(1, [_heat(2, label=label)])
    seg2 = _seg_with_alerts(2, [_heat(4, label=label)])
    html = _render_trip_html([seg1, seg2])
    assert html.count(label) == 1, (
        f"Warnung darf im Briefing nur 1x erscheinen, gefunden {html.count(label)}x"
    )


# ---------------------------------------------------------------------------
# AC-4 (#1217): Trip-Briefing nennt den Segment-Bezug (format_segment_reference)
# ---------------------------------------------------------------------------

def test_ac4_trip_briefing_shows_segment_reference():
    """Warnung betrifft Segmente 1 und 2 -> Briefing nennt 'Segment 1–2'
    (zusammenhängend, wie Warn-Mail #1200). RED: heute fehlt jeder Segment-
    Bezug (collect_trip_alert_entries verwirft die Segment-IDs)."""
    label = "Hitzewarnung Haute-Corse"
    seg1 = _seg_with_alerts(1, [_heat(3, label=label)])
    seg2 = _seg_with_alerts(2, [_heat(3, label=label)])
    html = _render_trip_html([seg1, seg2])
    assert "Segment 1–2" in html, (
        "Trip-Briefing muss den Segment-Bezug 'Segment 1–2' der betroffenen "
        "Etappen nennen (fehlt heute komplett)"
    )


# ---------------------------------------------------------------------------
# AC-5: Kein Over-Dedup (Nicht-Regressions-Wächter, heute grün)
# ---------------------------------------------------------------------------

def test_ac5_different_hazards_not_collapsed():
    """Verschiedene hazards an einem Ort -> zwei Chips (nicht kollabieren)."""
    loc = _loc_with_alerts("l5a", "O", [
        _heat(3, region="Haute-Corse"),
        _heat(3, region="Haute-Corse", hazard="thunderstorm", label="Gewitter HC"),
    ])
    row = _render_overview_row(WARN_METRIC, [loc])
    assert row.count(CHIP_SIG) == 2, (
        f"Verschiedene hazards dürfen nicht kollabieren, gefunden {row.count(CHIP_SIG)}"
    )


def test_ac5_same_hazard_different_region_not_collapsed():
    """Gleicher hazard, verschiedene Region -> zwei Chips (nicht kollabieren)."""
    loc = _loc_with_alerts("l5b", "O", [
        _heat(3, region="Haute-Corse"),
        _heat(3, region="Corse-du-Sud", label="Hitze CDS"),
    ])
    row = _render_overview_row(WARN_METRIC, [loc])
    assert row.count(CHIP_SIG) == 2, (
        f"Gleicher hazard verschiedene Region darf nicht kollabieren, "
        f"gefunden {row.count(CHIP_SIG)}"
    )


# ---------------------------------------------------------------------------
# AC-7 (F001): Eskalierende Massiv-Sperre desselben Massivs = EINE Warnung
# ---------------------------------------------------------------------------

def _massif_alert(level: int) -> OfficialAlert:
    """Wie massif_closure._niveau_to_alert nach dem #1217/#1218-Fix erzeugt:
    region_label=None, Stufe im Label-Text codiert, ABER stabile
    stufen-unabhaengige dedup_id (= massif_id) gesetzt."""
    wording = {3: "Zugang eingeschränkt", 4: "Zugang gesperrt"}[level]
    return OfficialAlert(
        source="massif_closure", hazard="access_ban", level=level,
        label=f"{wording} — Massif de l'Esterel", region_label=None,
        dedup_id="ESTEREL-MASSIF-ID",
    )


def test_ac7_escalating_massif_closure_dedups_in_briefing():
    """Dasselbe Massiv, Niveau 3 auf Segment 1, Niveau 4 auf Segment 2 ->
    im Trip-Briefing GENAU EIN Badge (höchste Stufe 4, 'gesperrt'). RED: heute
    zwei Badges, weil der level-behaftete Label-Text als Dedup-Key dient."""
    seg1 = _seg_with_alerts(1, [_massif_alert(3)])
    seg2 = _seg_with_alerts(2, [_massif_alert(4)])
    html = _render_trip_html([seg1, seg2])
    # HTML-Renderer escaped Apostrophe als &#x27; -> "Esterel" ist die eindeutige
    # Zähl-Signatur des Massivnamens (kein Konflikt mit Escaping).
    count = html.count("Esterel")
    assert count == 1, (
        f"Eskalierende Massiv-Sperre muss zu EINEM Badge kollabieren, gefunden {count}x"
    )
    assert "Zugang gesperrt" in html and "Esterel" in html, (
        "Der verbleibende Badge muss die HÖCHSTE Stufe (Niveau 4, 'gesperrt') zeigen"
    )
    assert "Zugang eingeschränkt" not in html, (
        "Die niedrigere Stufe (Niveau 3) darf nach dem Dedup nicht mehr erscheinen"
    )


def test_ac7_escalating_massif_closure_dedups_in_compare_overview():
    """Gleiches Szenario im Compare-Übersichts-Chip: EIN Chip statt zwei."""
    loc = _loc_with_alerts("l7", "Esterel", [_massif_alert(3), _massif_alert(4)])
    row = _render_overview_row(WARN_METRIC, [loc])
    assert row.count(CHIP_SIG) == 1, (
        f"Eskalierende Massiv-Sperre muss im Übersichts-Chip zu 1 kollabieren, "
        f"gefunden {row.count(CHIP_SIG)}"
    )


# ---------------------------------------------------------------------------
# AC-8 (F002): Fallback-Key-Kollision region_label==label darf nicht kollabieren
# ---------------------------------------------------------------------------

def _render_trip_plain(segments) -> str:
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.plain import render_plain
    return render_plain(
        segments=segments, seg_tables=[[] for _ in segments],
        trip_name="Test GR20", report_type="morning",
        dc=build_default_display_config(), night_rows=[],
        thunder_forecast=None, changes=None, stage_name="Etappe",
        stage_stats=None, multi_day_trend=None, compact_summary="ok",
        tz=ZoneInfo("Europe/Berlin"), friendly_keys=set(),
    )


def _render_trip_compact(segments) -> str:
    from app.metric_catalog import build_default_display_config
    from output.renderers.email.compact import render_compact
    return render_compact(
        segments=segments, dc=build_default_display_config(),
        multi_day_trend=None, stability_result=None,
        tz=ZoneInfo("Europe/Berlin"), report_type="morning",
        trip_name="Test GR20", stage_name="Etappe", stage_stats=None,
    )


def test_ac3_plain_dedups_same_region_hazard():
    """#1217 im Plain-Textteil (multipart 'full'): identische Warnung ueber
    zwei Etappen erscheint genau einmal."""
    label = "Hitzewarnung Haute-Corse"
    seg1 = _seg_with_alerts(1, [_heat(2, label=label)])
    seg2 = _seg_with_alerts(2, [_heat(4, label=label)])
    out = _render_trip_plain([seg1, seg2])
    assert out.count(label) == 1, f"Plain-Body zeigt Warnung {out.count(label)}x statt 1x"


def test_ac3_compact_dedups_same_region_hazard():
    """#1217 im Compact-Body (gesamter Mail-Inhalt bei email_format=compact)."""
    label = "Hitzewarnung Haute-Corse"
    seg1 = _seg_with_alerts(1, [_heat(2, label=label)])
    seg2 = _seg_with_alerts(2, [_heat(4, label=label)])
    out = _render_trip_compact([seg1, seg2])
    assert out.count(label) == 1, f"Compact-Body zeigt Warnung {out.count(label)}x statt 1x"


def test_ac7_plain_escalating_massif_dedups():
    """F001 im Plain-Textteil: eskalierende Massiv-Sperre genau einmal, hoechste Stufe."""
    seg1 = _seg_with_alerts(1, [_massif_alert(3)])
    seg2 = _seg_with_alerts(2, [_massif_alert(4)])
    out = _render_trip_plain([seg1, seg2])
    assert out.count("Esterel") == 1, f"Plain-Body zeigt Massiv-Sperre {out.count('Esterel')}x statt 1x"
    assert "Zugang gesperrt" in out and "Zugang eingeschränkt" not in out, (
        "Plain-Body muss die hoechste Stufe (gesperrt) zeigen, nicht die niedrigere"
    )


def test_ac7_compact_escalating_massif_dedups():
    """F001 im Compact-Body."""
    seg1 = _seg_with_alerts(1, [_massif_alert(3)])
    seg2 = _seg_with_alerts(2, [_massif_alert(4)])
    out = _render_trip_compact([seg1, seg2])
    assert out.count("Esterel") == 1, f"Compact-Body zeigt Massiv-Sperre {out.count('Esterel')}x statt 1x"
    assert "gesperrt" in out, "Compact-Body muss die hoechste Stufe (gesperrt) zeigen"


def test_ac8_region_label_equal_to_other_label_not_collapsed():
    """Alert A: region_label=None, label='Massiv X gesperrt'. Alert B:
    region_label='Massiv X gesperrt' (zufällig == A.label), eigenes label.
    Gleicher hazard. Sie sind GENUIN verschieden und dürfen NICHT kollabieren.
    RED: heute kollabiert der nicht-namespaced Fallback 'region_label or label'
    beide auf denselben Key."""
    from output.renderers.alert.official_alerts import dedupe_official_alerts

    a = OfficialAlert(source="s-a", hazard="access_ban", level=3,
                      label="Massiv X gesperrt", region_label=None)
    b = OfficialAlert(source="s-b", hazard="access_ban", level=2,
                      label="Zugang Massiv X eingeschränkt", region_label="Massiv X gesperrt")
    result = dedupe_official_alerts([(a, ["1"]), (b, ["2"])])
    assert len(result) == 2, (
        f"Zufällige region_label==label-Kollision darf zwei verschiedene "
        f"Warnungen NICHT kollabieren, bekommen {len(result)} statt 2"
    )
