"""Regressionsschutz — Issue #1614 Teil 3: Kanal-Schwellen-Verdrahtung.

SPEC: docs/specs/modules/fix_1614_briefing_warnfenster.md (AC-10 .. AC-13)

Kritischer Befund der Spec-Phase: Teil 3 ist BEREITS vollstaendig
implementiert (#1461 S3b-2a Trip, S3b-2b Compare) -- diese Tests sind reiner
Regressionsschutz und laufen schon HEUTE gruen, kein TDD im engeren Sinn.
Kein Produktivcode wird durch diese Datei ausgeloest.

Testpolitik: kein Mock-Theater, echte Renderer-Aufrufe (Kern-Schicht, kein
Netz). Geprueft wird die erzeugte Ausgabe (SMS-/Telegram-Text), nicht interne
Funktionsaufrufe.

Pfadregel #1409: reine Modul-Importe, kein fester Hauptrepo-Pfad noetig.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.trip import Stage, Trip, Waypoint
from services.official_alerts import OfficialAlert
from tests.unit.test_renderers_email import _make_segment_weather

LAT, LON = 42.20, 9.05


def _gelb_alert() -> OfficialAlert:
    # Hazard "flood" (Kuerzel "FL") statt "thunderstorm" ("TH"): das
    # Trip-SMS-Format traegt bereits ein IMMER vorhandenes Gewitter-
    # Vorhersage-Token mit demselben Symbol "TH:" (SMS_MULTI_SYMBOLS_BY_METRIC
    # "thunder" -> ("TH:", "TH+:")) -- ein Substring-Check auf "TH:" waere
    # unabhaengig vom amtlichen Warnblock immer wahr und bewiese nichts.
    now = datetime.now(timezone.utc)
    return OfficialAlert(
        source="tdd-1614-t10", hazard="flood", level=2,
        label="Hochwasserwarnung Stufe 2 (#1614)", region_label="Region",
        valid_from=now - timedelta(hours=1), valid_to=now + timedelta(hours=8),
    )


def _segment_with_alert(alert: OfficialAlert):
    sw = _make_segment_weather()
    sw.official_alerts = [alert]
    return sw


def _trip(threshold: dict | None) -> Trip:
    stage = Stage(
        id="T1", name="Tag 1", date=date.today(),
        waypoints=[
            Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0),
            Waypoint(id="G2", name="Ziel", lat=LAT + 0.05, lon=LON + 0.05, elevation_m=1200.0),
        ],
    )
    return Trip(
        id="trip-1614-schwelle", name="Schwellen-Trip", stages=[stage],
        alert_channel_thresholds=threshold,
    )


def test_trip_sms_zeigt_gelbe_warnung_bei_startwert_schwelle():
    """Test 10 / AC-10.

    GIVEN ein Trip hat fuer den SMS-Kanal keine eigene Schwelle gesetzt
          (Startwert "gering")
    WHEN  die Trip-SMS fuer eine amtliche Warnung Stufe 2 (GELB) erzeugt wird
    THEN  enthaelt der SMS-Text die Warnung.
    """
    from output.renderers.trip_report import TripReportFormatter

    trip = _trip(None)
    seg = _segment_with_alert(_gelb_alert())

    report = TripReportFormatter().format_email(
        segments=[seg], trip_name=trip.name, report_type="evening",
        trip=trip, tz=ZoneInfo("UTC"),
    )
    assert "FL:" in report.sms_text, (
        f"Die GELB-Warnung muss bei Startwert-Schwelle im SMS-Text erscheinen: "
        f"{report.sms_text!r}"
    )


def test_trip_sms_verbirgt_gelbe_warnung_bei_hochgesetzter_schwelle():
    """Test 11 / AC-11 (Gegenprobe zu AC-10).

    GIVEN derselbe Trip hat die SMS-Kanal-Schwelle explizit auf "hoch"
          gesetzt
    WHEN  dieselbe GELB-Warnung gerendert wird
    THEN  fehlt sie im SMS-Text.
    """
    from output.renderers.trip_report import TripReportFormatter

    trip = _trip({"sms": "HIGH"})
    seg = _segment_with_alert(_gelb_alert())

    report = TripReportFormatter().format_email(
        segments=[seg], trip_name=trip.name, report_type="evening",
        trip=trip, tz=ZoneInfo("UTC"),
    )
    assert "FL:" not in report.sms_text, (
        f"Die GELB-Warnung darf bei hochgesetzter SMS-Schwelle nicht erscheinen: "
        f"{report.sms_text!r}"
    )


def test_trip_telegram_bubble_folgt_derselben_kanal_schwelle():
    """Test 12 / AC-12 (analog Test 10/11 fuer Telegram).

    GIVEN ein Trip hat fuer den Telegram-Kanal keine eigene Schwelle bzw.
          eine hochgesetzte Schwelle
    WHEN  die Telegram-Bubble fuer dieselbe GELB-Warnung gerendert wird
    THEN  erscheint sie im ersten Fall und fehlt im zweiten.
    """
    from output.renderers.narrow import _official_alert_bubble

    seg = _segment_with_alert(_gelb_alert())

    bubble_low = _official_alert_bubble([seg], ZoneInfo("UTC"), trip=_trip(None))
    assert bubble_low is not None and "Amtliche Warnung" in bubble_low.text, (
        f"Bei Startwert-Schwelle muss die GELB-Warnung in der Telegram-Bubble "
        f"erscheinen: {bubble_low!r}"
    )

    bubble_high = _official_alert_bubble(
        [seg], ZoneInfo("UTC"), trip=_trip({"telegram": "HIGH"}),
    )
    assert bubble_high is None, (
        f"Bei hochgesetzter Telegram-Schwelle darf keine Bubble entstehen: {bubble_high!r}"
    )


def test_compare_bericht_zeigt_gelbe_warnung_unabhaengig_von_der_alarm_schwelle():
    """Test 13 / AC-13 (Regressionsschutz Compare-Bericht, "Zwei Wirkungsorte").

    GIVEN ein Ortsvergleich-Ort traegt eine amtliche Warnung Stufe 2 (GELB) --
          `render_compare_sms`/`render_compare_telegram` kennen strukturell
          KEINEN Alarm-Kanal-Schwellenparameter (#1461 S3b-2b, PO-dokumentiert)
    WHEN  der reguläre Kurznachrichten-Bericht (SMS und Telegram) erzeugt wird
    THEN  erscheint die Warnung trotzdem -- der Bericht bleibt bewusst
          unabhaengig von einer je Kanal eingestellten Alarm-Schwelle.
    """
    from app.user import ComparisonResult, LocationResult, SavedLocation
    from output.renderers.comparison import render_compare_sms, render_compare_telegram

    location = SavedLocation(id="loc-1614", name="Testort", lat=LAT, lon=LON, elevation_m=1000)
    loc_result = LocationResult(location=location, official_alerts=[_gelb_alert()])
    result = ComparisonResult(
        locations=[loc_result], time_window=(0, 23), target_date=date.today(),
    )

    sms = render_compare_sms(result)
    telegram = render_compare_telegram(result)

    assert "!FL" in sms, (
        "Der Compare-SMS-Bericht muss eine GELB-Warnung unabhaengig von einer "
        f"Alarm-Kanal-Schwelle zeigen (Zwei Wirkungsorte, #1461 S3b-2b): {sms!r}"
    )
    # Compare-Telegram traegt keinen "Amtliche Warnung"-Praefix (der Praefix
    # ist dort der Ortsname, s. comparison.py:748) -- "Warnstufe" ist der
    # zuverlaessige Marker, dass ueberhaupt eine amtliche Warnung im Block
    # gerendert wurde (render_official_alert_telegram()).
    assert "Warnstufe" in telegram, (
        "Der Compare-Telegram-Bericht muss eine GELB-Warnung unabhaengig von "
        f"einer Alarm-Kanal-Schwelle zeigen: {telegram!r}"
    )
