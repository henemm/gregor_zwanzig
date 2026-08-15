"""Regressionsschutz — Issue #1614 Teil 4: "!"-Kennzeichnung amtlicher Warnungen.

SPEC: docs/specs/modules/fix_1614_briefing_warnfenster.md (AC-14, AC-15, AC-16)

Kritischer Befund der Spec-Phase: Teil 4 ist BEREITS vollstaendig
implementiert (Trip-SMS Issue #1318 `output/tokens/render.py::_fuse`,
Compare-SMS Issue #1332 `comparison.py::_official_alert_sms_marker`) --
diese Tests sind reiner Regressionsschutz und laufen schon HEUTE gruen, kein
TDD im engeren Sinn. Kein Produktivcode wird durch diese Datei ausgeloest.

Testpolitik: kein Mock-Theater, echte Renderer-Aufrufe (Kern-Schicht, kein
Netz). Geprueft wird die erzeugte Ausgabe (SMS-/Telegram-Text).
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.trip import Stage, Trip, Waypoint
from app.user import ComparisonResult, LocationResult, SavedLocation
from services.official_alerts import OfficialAlert
from tests.unit.test_renderers_email import _make_segment_weather

LAT, LON = 42.20, 9.05


def _two_official_alerts() -> tuple[OfficialAlert, OfficialAlert]:
    """Zwei verschiedene Gefahren, beide Stufe 3 (orange, ueber jeder
    Kanal-Schwelle) -- fuer den Nachweis "genau EIN fuehrendes '!' vor dem
    GESAMTEN Block, nicht vor jedem einzelnen Token"."""
    now = datetime.now(timezone.utc)
    thunder = OfficialAlert(
        source="tdd-1614-t14", hazard="thunderstorm", level=3,
        label="Gewitterwarnung (#1614)", region_label="Region",
        valid_from=now - timedelta(hours=1), valid_to=now + timedelta(hours=8),
    )
    flood = OfficialAlert(
        source="tdd-1614-t14", hazard="flood", level=3,
        label="Hochwasserwarnung (#1614)", region_label="Region",
        valid_from=now - timedelta(hours=1), valid_to=now + timedelta(hours=8),
    )
    return thunder, flood


def _segment_with_alerts(alerts: list[OfficialAlert]):
    sw = _make_segment_weather()
    sw.official_alerts = list(alerts)
    return sw


def _trip() -> Trip:
    # #1709: feste Ankunftszeiten statt Naismith-Self-Heal
    # (trip_segments.py:125-127) — die Zeiten selbst tragen keine
    # Pruefaussage dieser Datei, sie muessen nur ueberhaupt gesetzt sein.
    stage = Stage(
        id="T1", name="Tag 1", date=date.today(),
        waypoints=[
            Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=1000.0,
                     arrival_calculated="08:00"),
            Waypoint(id="G2", name="Ziel", lat=LAT + 0.05, lon=LON + 0.05, elevation_m=1200.0,
                     arrival_calculated="12:00"),
        ],
    )
    return Trip(id="trip-1614-marker", name="Marker-Trip", stages=[stage])


def test_trip_sms_traegt_genau_ein_fuehrendes_ausrufezeichen_vor_dem_warnblock():
    """Test 14 / AC-14 (Trip-SMS).

    GIVEN eine amtliche Warnung erreicht den SMS-Kanal (Stufe 3, orange)
    WHEN  die Trip-SMS-Kurzform erzeugt wird
    THEN  steht genau ein fuehrendes "!" unmittelbar vor dem ersten Token des
          amtlichen Warnblocks, kein weiteres "!" vor folgenden Tokens
          desselben Blocks (Issue #1318).
    """
    from output.renderers.trip_report import TripReportFormatter

    thunder, flood = _two_official_alerts()
    seg = _segment_with_alerts([thunder, flood])
    trip = _trip()

    report = TripReportFormatter().format_email(
        segments=[seg], trip_name=trip.name, report_type="evening",
        trip=trip, tz=ZoneInfo("UTC"),
    )
    sms = report.sms_text
    assert sms.count("!") == 1, (
        f"Erwartet genau EIN '!' im gesamten SMS-Text, gefunden {sms.count('!')}: {sms!r}"
    )
    assert "!TH:" in sms, f"Das '!' muss unmittelbar vor dem ersten Warnblock-Token stehen: {sms!r}"
    assert "FL:" in sms and "!FL:" not in sms, (
        f"Das zweite Token desselben Blocks darf KEIN eigenes '!' tragen: {sms!r}"
    )


def test_compare_sms_traegt_denselben_ausrufezeichen_marker():
    """Test 15 / AC-14 (Compare-SMS, Regressionsschutz #1332).

    GIVEN dieselbe Ausgangslage fuer einen Ortsvergleichs-Ort
    WHEN  die Compare-SMS-Kurzform erzeugt wird
    THEN  traegt der Ortsblock denselben "!"-Marker (genau einmal, vor dem
          ersten Token).
    """
    from output.renderers.comparison import render_compare_sms

    thunder, flood = _two_official_alerts()
    location = SavedLocation(id="loc-1614", name="Testort", lat=LAT, lon=LON, elevation_m=1000)
    loc_result = LocationResult(location=location, official_alerts=[thunder, flood])
    result = ComparisonResult(
        locations=[loc_result], time_window=(0, 23), target_date=date.today(),
    )

    sms = render_compare_sms(result)
    assert sms.count("!") == 1, (
        f"Erwartet genau EIN '!' im gesamten Compare-SMS-Text, gefunden "
        f"{sms.count('!')}: {sms!r}"
    )
    assert "!TH:" in sms, f"Das '!' muss unmittelbar vor dem ersten Warnblock-Token stehen: {sms!r}"
    assert "FL:" in sms and "!FL:" not in sms, (
        f"Das zweite Token desselben Blocks darf KEIN eigenes '!' tragen: {sms!r}"
    )


def test_telegram_zeigt_amtliche_warnung_ohne_ausrufezeichen_praefix():
    """Test 16 / AC-15 (Nicht-Ziel-Nachweis Telegram, Trip UND Compare).

    GIVEN dieselbe amtliche Warnung erreicht Trip-Telegram bzw.
          Compare-Telegram
    WHEN  die jeweilige Bubble/Nachricht gerendert wird
    THEN  enthaelt der Text KEIN "!"-Praefix -- Telegram nutzt stattdessen
          ausschliesslich die bestehende Emoji-Kennzeichnung (Trip UND
          Compare bewusst kein Marker, PO-Korrektur 2026-07-23,
          `comparison.py:723-725`).
    """
    from output.renderers.comparison import render_compare_telegram
    from output.renderers.narrow import _official_alert_bubble

    thunder, flood = _two_official_alerts()

    trip_seg = _segment_with_alerts([thunder, flood])
    trip_bubble = _official_alert_bubble([trip_seg], ZoneInfo("UTC"), trip=_trip())
    assert trip_bubble is not None, "Vorbedingung: die Trip-Telegram-Bubble muss entstehen"
    assert "!" not in trip_bubble.text, (
        f"Trip-Telegram darf keinen '!'-Marker zeigen (Emoji-Kennzeichnung "
        f"stattdessen): {trip_bubble.text!r}"
    )

    location = SavedLocation(id="loc-1614b", name="Testort", lat=LAT, lon=LON, elevation_m=1000)
    loc_result = LocationResult(location=location, official_alerts=[thunder, flood])
    result = ComparisonResult(
        locations=[loc_result], time_window=(0, 23), target_date=date.today(),
    )
    compare_telegram = render_compare_telegram(result)
    assert "!" not in compare_telegram, (
        f"Compare-Telegram darf keinen '!'-Marker zeigen (Emoji-Kennzeichnung "
        f"stattdessen): {compare_telegram!r}"
    )
