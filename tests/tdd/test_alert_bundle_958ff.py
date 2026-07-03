"""
TDD-RED: Fix Alert Bundle — #958/#959/#933/#921/#980/#981/#982/#986

Spec: docs/specs/modules/fix_alert_bundle_958ff.md (15 ACs, AC-5/6/7 sind Frontend
und liegen in frontend/e2e/alert-bundle-958ff.spec.ts).

Ein Test pro Backend-AC. Jeder Docstring zitiert Given/When/Then aus der Spec.
KEINE Mocks — echte Renderer-/Modell-/Loader-/Service-Aufrufe.

Erwarteter Test-Bruch in Bestandstests (siehe Spec §"Erwartete Test-Brüche"):
test_957_alert_mail_literal_structure.py, test_issue_917_alert_renderer.py und
test_978_deviation_line_readability.py brechen NACH der #958-Δ-Umstellung, weil
ihre Fixtures mit `threshold` als Absolutwert konstruiert wurden. Das ist
erwartetes Kollateral der GREEN-Phase, nicht dieser RED-Datei.
"""
from __future__ import annotations

import json
import shutil
from datetime import datetime, timezone
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MIG_USER = "tdd-958-mig"


# ---------------------------------------------------------------------------
# Fixtures / Helfer
# ---------------------------------------------------------------------------

def _make_segment_data(freezing_level_m: float, segment_id: str = "1",
                        km_from: float = 0.0, km_to: float = 10.0):
    """Echtes SegmentWeatherData mit gesetztem freezing_level_m (AC-4)."""
    from app.models import GPXPoint, SegmentWeatherData, SegmentWeatherSummary, TripSegment

    start = GPXPoint(lat=46.5, lon=10.5, elevation_m=1800.0, distance_from_start_km=km_from)
    end = GPXPoint(lat=46.5, lon=10.6, elevation_m=2000.0, distance_from_start_km=km_to)
    seg = TripSegment(
        segment_id=segment_id,
        start_point=start,
        end_point=end,
        start_time=datetime(2026, 7, 2, 6, 0, tzinfo=timezone.utc),
        end_time=datetime(2026, 7, 2, 8, 0, tzinfo=timezone.utc),
        duration_hours=2.0,
        distance_km=km_to - km_from,
        ascent_m=200.0,
        descent_m=50.0,
    )
    summary = SegmentWeatherSummary(freezing_level_m=freezing_level_m)
    return SegmentWeatherData(
        segment=seg,
        timeseries=None,
        aggregated=summary,
        fetched_at=datetime.now(timezone.utc),
        provider="openmeteo",
    )


def _bundle_multi_msg():
    """2 über-Schwelle-Events (gust, thunder) + 1 unter-Schwelle-Event
    (rain_probability) — gemeinsame Fixture für AC-10/AC-11/AC-14.

    Δ-Werte sind bewusst so gewählt, dass die Klassifikation über/unter
    sowohl unter der ALTEN (Absolutwert-) als auch der NEUEN (Δ-)Semantik
    identisch ausfällt — die Fixture testet gezielt #980/#981, nicht #958.
    """
    from output.renderers.alert.model import AlertEvent, AlertMessage

    e_gust = AlertEvent(metric_id="gust", value_from=30.0, value_to=80.0, threshold=40.0,
                         cmp="über", occurred_at="10:00", km_from=0.0, km_to=5.0)
    e_thunder = AlertEvent(metric_id="thunder", value_from=30.0, value_to=90.0, threshold=40.0,
                            cmp="über", occurred_at="11:00", km_from=1.0, km_to=5.0)
    e_rain = AlertEvent(metric_id="rain_probability", value_from=70.0, value_to=90.0,
                         threshold=95.0, cmp="über", occurred_at=None, km_from=0.0, km_to=4.0)
    return AlertMessage(trip_short="TEST", stand_at="14:30",
                         events=(e_gust, e_thunder, e_rain), source=None)


def _all_under_threshold_msg():
    """2 Events, beide unter Schwelle (Δ < threshold) — Fixture für AC-12."""
    from output.renderers.alert.model import AlertEvent, AlertMessage

    e1 = AlertEvent(metric_id="rain_probability", value_from=70.0, value_to=90.0,
                     threshold=95.0, cmp="über", occurred_at=None, km_from=0.0, km_to=3.0)
    e2 = AlertEvent(metric_id="cape", value_from=500.0, value_to=550.0, threshold=100.0,
                     cmp="über", occurred_at="12:00", km_from=1.0, km_to=4.0)
    return AlertMessage(trip_short="TEST", stand_at="15:00", events=(e1, e2), source=None)


# ---------------------------------------------------------------------------
# AC-1 (#958): over_thr() — Δ-Semantik statt Absolutwert-Vergleich
# ---------------------------------------------------------------------------

def test_ac1_over_thr_uses_delta_not_absolute():
    """AC-1: Given ein AlertEvent mit value_from=2855, value_to=3285,
    threshold=400, cmp='unter' (Bug-Report-Fall) / When over_thr(e) / Then
    True, weil abs(3285-2855)=430 >= 400 — unabhängig von cmp und davon, ob
    value_to größer/kleiner als threshold ist. Gegenprobe: fallende Richtung
    (value_from=3285, value_to=2855), gleicher Betrag -> ebenfalls True."""
    from output.renderers.alert.model import AlertEvent, over_thr

    rising = AlertEvent(
        metric_id="freezing_level", value_from=2855.0, value_to=3285.0,
        threshold=400.0, cmp="unter", occurred_at=None, km_from=0.0, km_to=1.0,
    )
    assert over_thr(rising) is True, (
        f"abs(3285-2855)=430 >= 400 -> over_thr() muss True liefern (Δ-Semantik), "
        f"bekommen: {over_thr(rising)!r}"
    )

    falling = AlertEvent(
        metric_id="freezing_level", value_from=3285.0, value_to=2855.0,
        threshold=400.0, cmp="unter", occurred_at=None, km_from=0.0, km_to=1.0,
    )
    assert over_thr(falling) is True, (
        f"Gegenprobe (fallende Richtung, gleicher Betrag) muss ebenfalls True "
        f"liefern, bekommen: {over_thr(falling)!r}"
    )


# ---------------------------------------------------------------------------
# AC-2 (#958): render_email() Verdikt + Datenblock — "Änderung {über/unter}"
# ---------------------------------------------------------------------------

def test_ac2_render_email_change_wording_and_datablock():
    """AC-2: Given dasselbe Event (Bug-Report-Werte) / When render_email() die
    Single-Metrik-Verdict-Pill und den Datenblock rendert / Then enthält der
    Verdict-Text 'Änderung über deiner Alarm-Schwelle (400 m)' (nicht mehr
    'jetzt über Schwelle 400 m') und der Datenblock zeigt 'Änderung über ✗'
    in der Alarm-Schwelle-Zeile — in html UND plain."""
    from output.renderers.alert.model import AlertEvent, AlertMessage
    from output.renderers.alert.render import render_email

    event = AlertEvent(
        metric_id="freezing_level", value_from=2855.0, value_to=3285.0,
        threshold=400.0, cmp="unter", occurred_at="09:00", km_from=0.0, km_to=5.0,
    )
    msg = AlertMessage(trip_short="TEST", stand_at="09:30", events=(event,), source=None)
    html, plain = render_email(msg)

    for content in (html, plain):
        assert "Änderung über deiner Alarm-Schwelle (400 m)" in content, (
            f"Verdikt-Text fehlt oder ist noch die alte Formulierung "
            f"('jetzt über Schwelle ...'): {content!r}"
        )
        assert "Änderung über ✗" in content, (
            f"Datenblock-Zeile 'Alarm-Schwelle' zeigt nicht 'Änderung über ✗': {content!r}"
        )


# ---------------------------------------------------------------------------
# AC-3 (#959): Migration snow_line -> freezing_level beim Laden (Read-Modify-Write)
# ---------------------------------------------------------------------------

def test_ac3_snow_line_migrates_to_freezing_level_on_load():
    """AC-3: Given ein Bestandstrip mit
    metric_alert_levels={'snow_line': 'standard'} (kein freezing_level-Key) /
    When der Trip geladen wird / Then enthält metric_alert_levels danach
    freezing_level='standard' statt snow_line, alle anderen Trip-Felder sind
    unverändert (Read-Modify-Write, kein Datenverlust — BUG-DATALOSS-GR221-Lehre)."""
    trips_dir = _REPO_ROOT / "data" / "users" / _MIG_USER / "trips"
    trips_dir.mkdir(parents=True, exist_ok=True)
    trip_id = "mig-1"
    trip_path = trips_dir / f"{trip_id}.json"
    trip_json = {
        "id": trip_id,
        "name": "Migrations-Testtrip",
        "stages": [],
        "avalanche_regions": ["AT-7"],
        "shortcode": "GZ9001",
        "activity": "wandern",
        "region": "GR20",
        "display_config": {
            "metric_alert_levels": {"snow_line": "standard"},
        },
    }
    trip_path.write_text(json.dumps(trip_json), encoding="utf-8")

    try:
        from app.loader import load_trip

        loaded = load_trip(trip_id, data_dir=str(_REPO_ROOT / "data"), user_id=_MIG_USER)
        assert loaded is not None, "Trip wurde nicht geladen"

        levels = loaded.display_config.metric_alert_levels if loaded.display_config else None
        assert levels is not None, "metric_alert_levels fehlt nach dem Laden"
        assert levels.get("freezing_level") == "standard", (
            f"Erwartet freezing_level='standard' nach Migration, bekommen: {levels!r}"
        )
        assert "snow_line" not in levels, (
            f"snow_line-Key hätte nach der Migration entfernt sein müssen: {levels!r}"
        )

        # Read-Modify-Write: alle anderen Felder bleiben unverändert.
        assert loaded.avalanche_regions == ["AT-7"], (
            f"avalanche_regions verändert: {loaded.avalanche_regions!r}"
        )
        assert loaded.shortcode == "GZ9001", f"shortcode verändert: {loaded.shortcode!r}"
        assert loaded.activity == "wandern", f"activity verändert: {loaded.activity!r}"
        assert loaded.region == "GR20", f"region verändert: {loaded.region!r}"
    finally:
        shutil.rmtree(_REPO_ROOT / "data" / "users" / _MIG_USER, ignore_errors=True)


# ---------------------------------------------------------------------------
# AC-4 (#959): FREEZING_LEVEL-Regel erzeugt WeatherChange (statt still verworfen)
# ---------------------------------------------------------------------------

def test_ac4_freezing_level_delta_rule_produces_weatherchange():
    """AC-4: Given weather_change_detection.py nach der Änderung / When ein
    Nutzer 'Nullgradgrenze' (freezing_level) auswählt und ein Δ von 430 m auf
    einem Segment auftritt / Then erzeugt der Change-Detector einen
    WeatherChange-Eintrag für freezing_level_m (aktuell: Regel wird still
    verworfen -> logger.warning(...); continue durch fehlenden Dict-Eintrag
    in _ALERT_METRIC_TO_SUMMARY_FIELD)."""
    from app.models import AlertMetric, AlertRule, AlertRuleKind, AlertSeverity
    from services.weather_change_detection import WeatherChangeDetectionService

    rule = AlertRule(
        id="fl-delta-1", kind=AlertRuleKind.DELTA, metric=AlertMetric.FREEZING_LEVEL,
        threshold=400.0, severity=AlertSeverity.WARNING, enabled=True,
    )
    service = WeatherChangeDetectionService.from_alert_rules([rule])

    old_data = _make_segment_data(freezing_level_m=2855.0, segment_id="1", km_from=0.0, km_to=12.0)
    new_data = _make_segment_data(freezing_level_m=3285.0, segment_id="1", km_from=0.0, km_to=12.0)

    changes = service.detect_changes(old_data, new_data)

    matching = [c for c in changes if c.metric == "freezing_level_m"]
    assert matching, (
        f"Erwartet einen WeatherChange für 'freezing_level_m' (Δ=430 >= "
        f"Schwelle 400), aber die Regel wird still verworfen. changes={changes!r}"
    )


# ---------------------------------------------------------------------------
# AC-10 (#980): Unter-Schwelle-Zeile im Multi-Datenblock
# ---------------------------------------------------------------------------

def test_ac10_multi_datablock_under_threshold_row_format():
    """AC-10: Given eine Multi-Metrik-Nachricht mit einem unter-Schwelle-Event
    (rain_probability, value_from=70, value_to=90, threshold=95, Δ=20<95) /
    When der E-Mail-Datenblock gerendert wird / Then zeigt die Zeile links
    'Regen% · unter Schwelle' (OHNE Schwellen-Zahl) und rechts '70 → 90 %'
    (neutraler Pfeil, KEIN über/unter-Wort am Ende) — exakt wie Design-Vorlage
    Zeile 231-234."""
    from output.renderers.alert.render import render_email

    html, plain = render_email(_bundle_multi_msg())

    for content in (html, plain):
        assert "Regen% · unter Schwelle" in content, (
            f"Label 'Regen% · unter Schwelle' (ohne Schwellen-Zahl) fehlt: {content!r}"
        )
        assert "70 → 90 %" in content, (
            f"Neutraler-Pfeil-Wert '70 → 90 %' fehlt: {content!r}"
        )
        assert "Regen% · Schwelle" not in content, (
            f"Alte Zeile mit Schwellen-Zahl ('Regen% · Schwelle ...') noch "
            f"vorhanden: {content!r}"
        )


# ---------------------------------------------------------------------------
# AC-11 (#981): Betreff/Verdict/Telegram-Zähler auf über-Schwelle filtern
# ---------------------------------------------------------------------------

def test_ac11_counters_filter_to_over_threshold_only():
    """AC-11: Given eine Multi-Metrik-Nachricht mit 2 über- und 1
    unter-Schwelle-Event / When Betreff, E-Mail-Verdict-Pill und
    Telegram-Kopfzeile gerendert werden / Then zeigen alle drei '2 über
    Schwelle' (nicht 3), und das Top-3 im Betreff enthält NUR die 2
    über-Schwelle-Events (nicht 'Regen%')."""
    from output.renderers.alert.render import render_email, render_subject, render_telegram

    msg = _bundle_multi_msg()

    subj = render_subject(msg)
    assert "2 über Schwelle" in subj, f"Betreff zeigt nicht '2 über Schwelle': {subj!r}"
    assert "Regen%" not in subj, (
        f"Top-3 im Betreff enthält das unter-Schwelle-Event 'Regen%': {subj!r}"
    )

    html, _ = render_email(msg)
    assert "2 über Schwelle" in html, (
        f"E-Mail-Verdict-Pill zeigt nicht '2 über Schwelle': {html!r}"
    )

    tg = render_telegram(msg)
    assert "2 über Schwelle" in tg, f"Telegram-Kopfzeile zeigt nicht '2 über Schwelle': {tg!r}"


# ---------------------------------------------------------------------------
# AC-12 (#981, Randfall): 0 über-Schwelle-Events -> "N Änderungen seit dem Briefing"
# ---------------------------------------------------------------------------

def test_ac12_all_under_threshold_shows_aenderungen_fallback():
    """AC-12: Given eine Multi-Metrik-Nachricht, in der ALLE Events unter
    Schwelle liegen (0 über-Schwelle-Events) / When Betreff, E-Mail-Verdict
    und Telegram-Kopf gerendert werden / Then lautet die Formulierung
    'N Änderungen seit dem Briefing' (N=Gesamtzahl) statt '0 über Schwelle'
    in allen drei Kanälen."""
    from output.renderers.alert.render import render_email, render_subject, render_telegram

    msg = _all_under_threshold_msg()

    subj = render_subject(msg)
    assert "2 Änderungen seit dem Briefing" in subj, (
        f"Betreff zeigt nicht den Randfall-Text '2 Änderungen seit dem "
        f"Briefing': {subj!r}"
    )

    html, _ = render_email(msg)
    assert "2 Änderungen seit dem Briefing" in html, (
        f"E-Mail-Verdict zeigt nicht den Randfall-Text: {html!r}"
    )

    tg = render_telegram(msg)
    assert "2 Änderungen seit dem Briefing" in tg, (
        f"Telegram-Kopf zeigt nicht den Randfall-Text: {tg!r}"
    )


# ---------------------------------------------------------------------------
# AC-13 (#982): Intra-Gruppen-Sortierung nach abs(severity)
# ---------------------------------------------------------------------------

def test_ac13_under_threshold_group_sorted_by_abs_severity():
    """AC-13: Given zwei unter-Schwelle-Events mit unterschiedlicher Distanz
    zur Schwelle (severity=-0.3 und severity=-0.8) in derselben Nachricht /
    When _sorted() die gedämpfte Gruppe ordnet / Then erscheint das Event mit
    severity=-0.8 (gust/Böen) VOR dem mit severity=-0.3 (cape/CAPE) im
    gerenderten Output — Betrag statt Vorzeichen bestimmt die
    Intra-Gruppen-Reihenfolge."""
    from output.renderers.alert.model import AlertEvent, AlertMessage, over_thr, severity
    from output.renderers.alert.render import render_email

    e_cape = AlertEvent(metric_id="cape", value_from=95.0, value_to=70.0, threshold=100.0,
                         cmp="über", occurred_at="09:00", km_from=0.0, km_to=2.0)
    e_gust = AlertEvent(metric_id="gust", value_from=25.0, value_to=20.0, threshold=100.0,
                         cmp="über", occurred_at="10:00", km_from=2.0, km_to=4.0)

    # Vorbedingungen der Fixture absichern (kein Test-Artefakt, echte Formel).
    assert severity(e_cape) == pytest.approx(-0.3), f"severity(cape)={severity(e_cape)!r}"
    assert severity(e_gust) == pytest.approx(-0.8), f"severity(gust)={severity(e_gust)!r}"
    assert over_thr(e_cape) is False and over_thr(e_gust) is False, (
        "beide Events müssen in der unter-Schwelle-Gruppe liegen (Vorbedingung)"
    )

    msg = AlertMessage(trip_short="TEST", stand_at="16:00", events=(e_cape, e_gust), source=None)
    html, _ = render_email(msg)

    idx_gust = html.find("Böen")
    idx_cape = html.find("CAPE")
    assert idx_gust != -1 and idx_cape != -1, (
        f"Beide Labels ('Böen', 'CAPE') müssen im Output vorkommen: {html!r}"
    )
    assert idx_gust < idx_cape, (
        f"severity=-0.8 (Böen) muss VOR severity=-0.3 (CAPE) erscheinen (Betrag "
        f"statt Vorzeichen sortiert); Böen@{idx_gust}, CAPE@{idx_cape}: {html!r}"
    )


# ---------------------------------------------------------------------------
# AC-14 (#986): Outlook-kompatible 2-Spalten-Tabellen-Rows (Deviation)
# ---------------------------------------------------------------------------

def test_ac14_email_datablock_uses_two_column_table_rows():
    """AC-14: Given ein Single- oder Multi-Metrik-Deviation-Datenblock / When
    das E-Mail-HTML gerendert wird / Then ist jede Datenblock-Zeile eine
    <table>-Row mit 2 <td>-Zellen (Label links, Wert rechtsbündig) statt
    zweier <span>s im selben <div>."""
    from output.renderers.alert.model import AlertEvent, AlertMessage
    from output.renderers.alert.render import render_email

    single_event = AlertEvent(
        metric_id="cape", value_from=1230.0, value_to=620.0, threshold=800.0,
        cmp="über", occurred_at="09:00", km_from=0.0, km_to=1.8,
    )
    single_msg = AlertMessage(trip_short="TEST", stand_at="09:30", events=(single_event,), source=None)
    html_single, _ = render_email(single_msg)

    assert "<span" not in html_single, (
        f"Single-Datenblock nutzt noch <span>-Markup statt <table>-Rows: {html_single!r}"
    )
    assert html_single.count("<tr") == 3, (
        f"Erwartet 3 Tabellen-Zeilen (Wert-Vergleich/Schwellwert-Status/Wo & "
        f"wann), gefunden: {html_single.count('<tr')}: {html_single!r}"
    )
    assert html_single.count('align="right"') == 3, (
        f"Erwartet 3x align=\"right\" (Wert-Spalte je Zeile): {html_single!r}"
    )

    multi_msg = _bundle_multi_msg()
    html_multi, _ = render_email(multi_msg)
    assert "<span" not in html_multi, (
        f"Multi-Datenblock nutzt noch <span>-Markup statt <table>-Rows: {html_multi!r}"
    )
    assert html_multi.count("<tr") == 3, (
        f"Erwartet 3 Tabellen-Zeilen (3 Events), gefunden: "
        f"{html_multi.count('<tr')}: {html_multi!r}"
    )


# ---------------------------------------------------------------------------
# AC-15 (#986): Onset-Datenblock — dieselbe 2-Spalten-Tabellen-Row-Struktur
# ---------------------------------------------------------------------------

def test_ac15_onset_datablock_uses_two_column_table_rows():
    """AC-15: Given den Onset-Datenblock (_render_email_onset(), msg.source
    != None) / When das HTML gerendert wird / Then folgt er derselben
    2-Spalten-Tabellen-Row-Struktur wie AC-14 (konsistente
    Outlook-Kompatibilität über Deviation- UND Onset-Alerts)."""
    from output.renderers.alert.model import AlertMessage, OnsetEvent
    from output.renderers.alert.render import render_email

    onset_event = OnsetEvent(
        onset_minutes=25, onset_time="16:10", km_from=3.0, km_to=5.0,
        is_convective=True, intensity_label="stark", source_label="Radar DWD",
        briefing_context=None,
    )
    msg = AlertMessage(
        trip_short="TEST", stand_at="15:45", events=(onset_event,),
        source="radar_nowcast", cooldown_display=None,
    )
    html, _ = render_email(msg)

    assert "<span" not in html, (
        f"Onset-Datenblock nutzt noch <span>-Markup statt <table>-Rows: {html!r}"
    )
    assert html.count("<tr") == 3, (
        f"Erwartet 3 Tabellen-Zeilen (Wo & wann/Intensität/Quelle), gefunden: "
        f"{html.count('<tr')}: {html!r}"
    )
    assert html.count('align="right"') == 3, (
        f"Erwartet 3x align=\"right\": {html!r}"
    )
