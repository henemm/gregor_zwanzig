"""
TDD RED — Issues #130, #93, #107 UI-Polish.

Spec: docs/specs/modules/issue_130_93_107_ui_polish.md

AC-1: Alert-Mail-Betreff enthält Etappennamen (stage_name), nicht Rohdatum
AC-2: Fallback auf Datumsformat wenn keine Stage zum Alert-Datum existiert
AC-3: Keine ASCII-Umlaut-Ersetzungen (ae/oe/ue) in user-sichtbaren Svelte-Strings
AC-4: TripForm.svelte ist aus dem Repository entfernt
"""
from __future__ import annotations

import re
from datetime import date as date_type, datetime, time, timedelta, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Helpers (kopiert / analog test_trip_alert.py)
# ---------------------------------------------------------------------------

from app.models import (
    ChangeSeverity,
    ForecastDataPoint,
    ForecastMeta,
    NormalizedTimeseries,
    Provider,
    GPXPoint,
    SegmentWeatherData,
    SegmentWeatherSummary,
    TripSegment,
    WeatherChange,
)
from app.trip import Stage, TimeWindow, Trip, Waypoint


def _make_trip_with_stage(stage_name: str, stage_date: date_type) -> Trip:
    """Trip mit einer Stage, die am stage_date liegt."""
    wp = Waypoint(
        id="W1", name="Start", lat=47.0, lon=11.0, elevation_m=1000.0,
        time_window=TimeWindow(start=time(8, 0), end=time(10, 0)),
    )
    stage = Stage(id="S1", name=stage_name, date=stage_date, waypoints=[wp])
    return Trip(id="test-trip", name="GR20", stages=[stage])


def _make_segment_weather(start_date: date_type) -> SegmentWeatherData:
    """SegmentWeatherData dessen start_time.date() == start_date."""
    start_dt = datetime.combine(start_date, time(8, 0), tzinfo=timezone.utc)
    segment = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=47.0, lon=11.0, elevation_m=1000.0),
        end_point=GPXPoint(lat=47.1, lon=11.1, elevation_m=1200.0),
        start_time=start_dt,
        end_time=start_dt + timedelta(hours=8),
        duration_hours=8.0,
        distance_km=15.0,
        ascent_m=500.0,
        descent_m=200.0,
    )
    meta = ForecastMeta(
        provider=Provider.OPENMETEO, model="test", run=start_dt,
        grid_res_km=1.0, interp="point_grid",
    )
    ts = NormalizedTimeseries(
        meta=meta,
        data=[ForecastDataPoint(ts=start_dt, t2m_c=20.0, wind10m_kmh=15.0)],
    )
    summary = SegmentWeatherSummary(
        temp_min_c=15.0, temp_max_c=20.0, temp_avg_c=17.5,
        wind_max_kmh=25.0, precip_sum_mm=0.0,
    )
    return SegmentWeatherData(
        segment=segment, timeseries=ts, aggregated=summary,
        fetched_at=start_dt, provider="openmeteo",
    )


def _make_change() -> WeatherChange:
    return WeatherChange(
        metric="wind_max_kmh", old_value=15.0, new_value=45.0,
        delta=30.0, threshold=10.0,
        severity=ChangeSeverity.MAJOR, direction="increase",
    )


# ---------------------------------------------------------------------------
# AC-1: Alert-Mail-Betreff enthält Etappennamen
# ---------------------------------------------------------------------------

class TestAC1SubjectContainsStageName:
    """
    AC-1: Given Trip mit passender Stage / When format_email ohne stage_name
    aufgerufen wird (aktueller Bug) / Then FEHLT der Etappenname im Betreff.
    Test demonstriert den Bug: Betreff zeigt Datum, nicht den Etappennamen.
    Nach dem Fix: _send_alert() übergibt stage_name → Test liefert Stage-Namen.
    """

    def test_ac1_subject_contains_stage_name(self) -> None:
        """
        GREEN: _send_alert() leitet stage_name aus Trip.get_stage_for_date() ab
        und übergibt ihn an format_email(). Test simuliert diesen Pfad:
        Trip mit passender Stage → stage_name extrahiert → Betreff enthält ihn.
        """
        from formatters.trip_report import TripReportFormatter

        today = date_type.today()
        stage_name = "Tag 3: Vizzavona → Capanelle"
        trip = _make_trip_with_stage(stage_name, today)
        weather = [_make_segment_weather(today)]
        changes = [_make_change()]

        # Reproduziert exakt das _send_alert()-Verhalten nach dem Fix:
        # stage_name aus Trip.get_stage_for_date() ableiten und übergeben.
        alert_date = weather[0].segment.start_time.date()
        matched_stage = trip.get_stage_for_date(alert_date)
        derived_stage_name = matched_stage.name if matched_stage else None

        formatter = TripReportFormatter()
        report = formatter.format_email(
            segments=weather,
            trip_name="GR20",
            # Issue #921: alert-Pfad ist tot (kanonischer Renderer); subject.py
            # kennt kein 'alert' → 'update' ist der lebende Report-Typ.
            report_type="update",
            changes=changes,
            stage_name=derived_stage_name,
        )

        assert stage_name in report.email_subject, (
            f"Betreff '{report.email_subject}' enthält nicht den Etappennamen "
            f"'{stage_name}'. Bug: _send_alert() übergibt kein stage_name."
        )


# ---------------------------------------------------------------------------
# AC-2: Fallback auf Datumsformat ohne passende Stage
# ---------------------------------------------------------------------------

class TestAC2FallbackToDate:
    """
    AC-2: Wenn keine Stage zum Alert-Datum existiert, nutzt der Betreff
    das Datumsformat als Fallback (kein Crash).
    """

    def test_ac2_fallback_to_date_when_no_stage(self) -> None:
        """
        Given Trip OHNE Stage zum Alert-Datum
        When format_email mit stage_name=None aufgerufen wird
        Then enthält der Betreff ein Datumsformat, kein 'None'.
        """
        from formatters.trip_report import TripReportFormatter

        today = date_type.today()
        weather = [_make_segment_weather(today)]

        formatter = TripReportFormatter()
        report = formatter.format_email(
            segments=weather,
            trip_name="GR20",
            # Issue #921: alert-Pfad tot; 'update' ist der lebende Report-Typ.
            report_type="update",
            stage_name=None,  # Kein Match → Fallback
        )

        subject = report.email_subject
        # Kein "None" im Betreff (Fallback soll Datum zeigen)
        assert "None" not in subject, (
            f"Betreff '{subject}' enthält 'None' — Fallback broken."
        )
        # Datumsformat DD.MM.YYYY oder YYYY-MM-DD muss vorhanden sein
        date_pattern = re.compile(r'\d{2}\.\d{2}\.\d{4}|\d{4}-\d{2}-\d{2}')
        assert date_pattern.search(subject), (
            f"Betreff '{subject}' enthält kein Datumsformat — Fallback broken."
        )


# ---------------------------------------------------------------------------
# AC-3: Keine ASCII-Umlaut-Ersetzungen in user-sichtbaren Svelte-Strings
# ---------------------------------------------------------------------------

# ASCII-Umlaut-Pattern die in user-sichtbaren Strings verboten sind
_FORBIDDEN_PATTERNS = [
    (r'\bwaehlen\b', "waehlen → wählen"),
    (r'\bausgewaehlt\b', "ausgewaehlt → ausgewählt"),
    (r'\bAuswaehlen\b', "Auswaehlen → Auswählen"),
    (r'\bauswaehlen\b', "auswaehlen → auswählen"),
    (r'\beinfuegen\b', "einfuegen → einfügen"),
    (r'\bZurueck\b', "Zurueck → Zurück"),
    (r'\bAktivitaet\b', "Aktivitaet → Aktivität"),
    (r'\bVorschlaege\b', "Vorschlaege → Vorschläge"),
    (r'\bbestaetigen\b', "bestaetigen → bestätigen"),
    (r'\bBestaetigen\b', "Bestaetigen → Bestätigen"),
    (r'\bbestaetigt\b', "bestaetigt → bestätigt"),
    (r'\bBestaetigt\b', "Bestaetigt → Bestätigt"),
    (r'\bunbestaetigt\b', "unbestaetigt → unbestätigt"),
    (r'\bKanaele\b', "Kanaele → Kanäle"),
    (r'\bdemnaechst\b', "demnaechst → demnächst"),
    (r'\bverfuegbar\b', "verfuegbar → verfügbar"),
    (r'\bloeschen\b', "loeschen → löschen"),
    (r'\bLoeschen\b', "Loeschen → Löschen"),
]

_SVELTE_FILES = [
    "frontend/src/lib/components/trip-wizard/TripWizardShell.svelte",
    "frontend/src/lib/components/trip-wizard/steps/Step1Profile.svelte",
    "frontend/src/lib/components/trip-wizard/steps/Step2Stages.svelte",
    "frontend/src/lib/components/trip-wizard/steps/Step4Briefings.svelte",
    "frontend/src/lib/components/trip-wizard/steps/WaypointRow.svelte",
    "frontend/src/lib/components/edit/EditRouteSection.svelte",
    "frontend/src/lib/components/trip-detail/FullProfile.svelte",
    "frontend/src/lib/components/trip-detail/waypoints/WaypointCard.svelte",
]


class TestAC3NoAsciiUmlauts:
    """
    AC-3: 8 Svelte-Dateien dürfen keine ASCII-Umlaut-Ersetzungen in
    user-sichtbaren Strings enthalten.
    """

    def test_ac3_no_ascii_umlauts_in_svelte_files(self) -> None:
        """
        RED: Svelte-Dateien enthalten noch ASCII-Ersetzungen.
        Test sammelt alle Verstöße und schlägt mit vollständiger Liste fehl.
        """
        repo_root = Path(__file__).parent.parent.parent
        violations: list[str] = []

        for rel_path in _SVELTE_FILES:
            file_path = repo_root / rel_path
            assert file_path.exists(), f"Datei nicht gefunden: {rel_path}"
            content = file_path.read_text(encoding="utf-8")

            # Nur user-sichtbare Teile prüfen:
            # - Reine Kommentarzeilen überspringen (// … und <!-- … -->)
            # - Inline-Kommentare am Zeilenende abschneiden (// …)
            for line_no, line in enumerate(content.splitlines(), 1):
                stripped = line.lstrip()
                # Reine Zeilen-Kommentare überspringen
                if (stripped.startswith("//") or stripped.startswith("*")
                        or stripped.startswith("<!--")):
                    continue
                # Inline-JS-Kommentar abschneiden (// …), HTML-Kommentar abschneiden
                check_part = re.split(r'\s*//', line)[0]
                check_part = re.sub(r'<!--.*?-->', '', check_part)
                for pattern, hint in _FORBIDDEN_PATTERNS:
                    if re.search(pattern, check_part):
                        violations.append(
                            f"{rel_path}:{line_no} — {hint} — Zeile: {line.strip()!r}"
                        )

        assert not violations, (
            f"{len(violations)} ASCII-Umlaut-Verstoß/Verstöße gefunden:\n"
            + "\n".join(violations)
        )


# ---------------------------------------------------------------------------
# AC-4: TripForm.svelte ist gelöscht
# ---------------------------------------------------------------------------

class TestAC4TripFormDeleted:
    """
    AC-4: TripForm.svelte darf nicht mehr im Repository existieren.
    """

    def test_ac4_tripform_deleted(self) -> None:
        """
        RED: TripForm.svelte existiert noch — Datei wurde noch nicht gelöscht.
        Nach dem Fix (git rm): Datei weg, Test grün.
        """
        repo_root = Path(__file__).parent.parent.parent
        tripform = repo_root / "frontend/src/lib/components/TripForm.svelte"

        assert not tripform.exists(), (
            f"TripForm.svelte existiert noch unter {tripform}. "
            "Datei ist toter Code und soll via 'git rm' entfernt werden (Issue #107)."
        )
