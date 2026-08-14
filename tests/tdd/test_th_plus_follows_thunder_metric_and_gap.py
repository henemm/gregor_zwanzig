"""SMS/Telegram-Kurzform: 'TH+:' verhaelt sich exakt wie 'TH:'.

Issue: #1482 — das Kuerzel fuer das Gewitter der FOLGE-Etappe folgt weder der
Metrik-Auswahl des Trips noch dem konfigurierten Schwellwert, und es kann bei
einer echten Datenluecke keine Unbekannt-Form ('?') zeigen.

PO-Regel (2026-08-03, #1415), einheitlich fuer ALLE Kuerzel:

  * geprueft, nichts ueber der Schwelle -> Null-Form ('TH+:-')
  * Wert nicht abrufbar / Datenluecke   -> 'TH+:?'
  * Metrik **abgewaehlt**               -> Kuerzel entfaellt vollstaendig

Gemessen wird der ECHTE Weg von der Nutzereinstellung bis zum fertigen Text:

  * AC-1/AC-2/AC-6 ueber ``TripReportFormatter.format_email()`` ->
    ``report.sms_text`` — nur dort entsteht die Abhaengigkeit der Token von der
    Trip-Einstellung (``trip_report.py`` leitet ``thresholds`` und
    ``disabled_specs`` aus ``display_config.metrics`` ab).
  * AC-3/AC-4 ueber ``SMSTripFormatter.format_sms()`` (nutzersichtbarer Text)
    und zusaetzlich ueber
    ``TripReportSchedulerService._build_thunder_forecast_from_trend_or_fetch()``,
    wo die Luecke ueberhaupt erst erkannt werden kann.

Keine Mocks, kein Netz, keine Mail — die Datenluecke im Scheduler-Test entsteht
aus einer echten Codepfad-Verzweigung (Folge-Etappe mit nur EINEM Waypoint ->
``convert_trip_to_segments()`` liefert ``[]``, vgl.
``tests/tdd/test_thunder_forecast_fail_soft.py``).
"""
from __future__ import annotations

from datetime import date, timedelta
from typing import Optional

import pytest

from app.models import MetricConfig, ThunderLevel, UnifiedWeatherDisplayConfig
from app.trip import AggregationConfig, Stage, Trip, Waypoint
from output.renderers.sms_trip import SMSTripFormatter
from output.renderers.trip_report import TripReportFormatter
from services.trip_report_scheduler import TripReportSchedulerService

from tests.tdd import _min_temp_felt_fixtures as F

# Gewitter der Folge-Etappe, so wie der Scheduler es liefert (ADR-0025:
# Stufe UND Stunde werden durchgereicht, nie erfunden).
_TOMORROW_HIGH = {
    "+1": {
        "date": "21.07.2026",
        "level": ThunderLevel.HIGH,
        "text": "Starkes Gewitter erwartet ab 15:00",
        "hour": 15,
    }
}
_TOMORROW_LOW = {
    "+1": {
        "date": "21.07.2026",
        "level": ThunderLevel.LOW,
        "text": "Leichtes Gewitter moeglich ab 15:00",
        "hour": 15,
    }
}


def _dc(*metric_ids: str, thunder_sms_threshold: Optional[float] = None):
    """Displaykonfiguration mit genau den genannten Metriken aktiv."""
    return UnifiedWeatherDisplayConfig(
        trip_id="i1482",
        metrics=[
            MetricConfig(
                metric_id=m,
                enabled=True,
                sms_threshold=(thunder_sms_threshold if m == "thunder" else None),
            )
            for m in metric_ids
        ],
    )


def _trip_sms(report_type: str, display_config, thunder_forecast=None) -> str:
    """Echt gerenderte Trip-SMS fuer die gegebene Nutzereinstellung."""
    report = TripReportFormatter().format_email(
        [F.segment()],
        trip_name="Issue1482",
        report_type=report_type,
        night_weather=F.night_weather(),
        display_config=display_config,
        stage_name=F.STAGE_NAME,
        tz=F.TZ,
        thunder_forecast=thunder_forecast,
    )
    return report.sms_text


def _direct_sms(thunder_forecast) -> str:
    """Kurzform direkt aus dem Formatter (ohne Trip-Einstellungen)."""
    return SMSTripFormatter().format_sms(
        [F.segment()],
        report_type="evening",
        tz=F.TZ,
        thunder_forecast=thunder_forecast,
    )


# ---------------------------------------------------------------------------
# AC-1: Metrik "Gewitter" abgewaehlt -> weder TH: noch TH+:
# ---------------------------------------------------------------------------

class TestAC1ThunderDeselectedRemovesBothTokens:
    """Der PO-Fall: 'Gewitter' ist im Trip nicht gewaehlt."""

    def test_th_plus_absent_when_thunder_metric_deselected(self):
        """
        GIVEN: Trip ohne Metrik 'Gewitter', Folge-Etappe MIT Gewitter (HIGH)
        WHEN:  das Briefing gerendert wird (morgens wie abends)
        THEN:  weder 'TH:' noch 'TH+:' erscheinen in der Kurzform
        """
        for report_type in ("morning", "evening"):
            sms = _trip_sms(
                report_type,
                _dc("temperature", "precipitation"),
                thunder_forecast=_TOMORROW_HIGH,
            )

            # Vorbedingung: die Zeile hat ueberhaupt Inhalt und ist nicht
            # gekuerzt — sonst waere ein fehlendes TH+: kein Beweis.
            # Issue #1824 (A): Tiefst- UND Hoechstwert sind gewaehlt, also
            # stehen sie als EIN Bereichs-Token 'D3/20' statt als 'K3 D20'.
            assert "D3/20" in sms, (
                f"[{report_type}] Die gewaehlten Temperaturwerte fehlen — der "
                f"Nachweis ueber TH+: waere nicht aussagekraeftig.\nSMS: {sms}"
            )

            assert "TH:" not in sms, (
                f"[{report_type}] 'TH:' erscheint, obwohl der Nutzer die "
                f"Metrik 'Gewitter' abgewaehlt hat.\nSMS: {sms}"
            )
            assert "TH+:" not in sms, (
                f"[{report_type}] 'TH+:' erscheint, obwohl der Nutzer die "
                f"Metrik 'Gewitter' abgewaehlt hat. Das Kuerzel der "
                f"Folge-Etappe muss derselben Auswahl folgen wie 'TH:'.\n"
                f"SMS: {sms}"
            )


# ---------------------------------------------------------------------------
# AC-2 (Kontrollgruppe): Metrik gewaehlt -> beide Kuerzel erscheinen
# ---------------------------------------------------------------------------

class TestAC2ThunderSelectedKeepsBothTokens:
    """Gegenprobe zu AC-1 — sonst waere AC-1 trivial durch 'TH+: immer weg'
    erfuellbar."""

    def test_both_thunder_tokens_present_when_metric_selected(self):
        """
        GIVEN: Trip MIT Metrik 'Gewitter', Folge-Etappe mit Gewitter (HIGH)
        WHEN:  das Briefing gerendert wird
        THEN:  'TH:' (heute) und 'TH+:H@15' (Folgetag) stehen beide da
        """
        for report_type in ("morning", "evening"):
            sms = _trip_sms(
                report_type,
                _dc("temperature", "precipitation", "thunder"),
                thunder_forecast=_TOMORROW_HIGH,
            )

            assert "TH:" in sms, (
                f"[{report_type}] 'TH:' fehlt bei gewaehlter Metrik "
                f"'Gewitter'.\nSMS: {sms}"
            )
            assert "TH+:H@15" in sms, (
                f"[{report_type}] 'TH+:H@15' fehlt bei gewaehlter Metrik "
                f"'Gewitter' und Gewitter am Folgetag.\nSMS: {sms}"
            )


# ---------------------------------------------------------------------------
# AC-3: echte Datenluecke fuer den Folgetag -> TH+:?
# ---------------------------------------------------------------------------

class TestAC3RealGapShowsUnknown:
    """Folgetag existiert, Daten fehlen — das ist KEINE Entwarnung."""

    def test_gap_marker_renders_th_plus_unknown(self):
        """
        GIVEN: thunder_forecast markiert den Folgetag als echte Datenluecke
               (Ziel-Vertrag: '_gap_offsets' enthaelt '+1')
        WHEN:  die Kurzform gerendert wird
        THEN:  der Text zeigt 'TH+:?' (unbekannt), NICHT 'TH+:-' (Entwarnung)
        """
        sms = _direct_sms({"_gap_offsets": {"+1"}})

        assert "TH+:?" in sms, (
            f"Bei einer echten Datenluecke fuer den Folgetag muss 'TH+:?' "
            f"erscheinen — 'TH+:-' waere eine Fehl-Entwarnung.\nSMS: {sms}"
        )
        assert "TH+:-" not in sms, (
            f"'TH+:-' (Entwarnung) darf bei einer Datenluecke nicht "
            f"erscheinen.\nSMS: {sms}"
        )

    def test_todays_thunder_token_unaffected_by_tomorrow_gap(self):
        """
        GIVEN: nur der FOLGETAG hat eine Datenluecke
        WHEN:  die Kurzform gerendert wird
        THEN:  'TH:' (heute) zeigt weiterhin seinen echten Wert (MED@11) —
               die Luecke des Folgetags faerbt den heutigen Wert nicht ein
        """
        sms = _direct_sms({"_gap_offsets": {"+1"}})

        assert "TH:M@11" in sms, (
            f"Die Luecke des Folgetags darf den heutigen Gewitter-Wert nicht "
            f"ueberschreiben.\nSMS: {sms}"
        )

    def test_scheduler_marks_missing_follow_up_stage_as_gap(self):
        """
        GIVEN: Trip mit echter Folge-Etappe, deren Wetterdaten nicht
               beschaffbar sind (nur EIN Waypoint -> keine Segmente, kein
               Netz), ohne Mehrtages-Trend; UEBERMORGEN gibt es gar keine
               Etappe
        WHEN:  _build_thunder_forecast_from_trend_or_fetch() laeuft
        THEN:  '+1' ist als Luecke markiert, '+2' NICHT (dort ist schlicht
               keine Etappe — das ist kein Datenausfall)
        """
        today = date.today()
        wp_a = Waypoint(id="A", name="Start", lat=42.0, lon=9.0, elevation_m=500)
        wp_b = Waypoint(id="B", name="Ziel", lat=42.1, lon=9.1, elevation_m=600)
        trip = Trip(
            id="i1482gap",
            name="Luecken-Trip",
            stages=[
                Stage(id="heute", name="Heute", date=today,
                      waypoints=[wp_a, wp_b]),
                # Morgige Etappe existiert, liefert aber keine Daten.
                Stage(id="morgen", name="Morgen", date=today + timedelta(days=1),
                      waypoints=[wp_a]),
            ],
            avalanche_regions=[],
            aggregation=AggregationConfig(),
        )

        svc = TripReportSchedulerService()
        forecast = svc._build_thunder_forecast_from_trend_or_fetch(
            trip, today, tz=None, multi_day_trend=None,
        )

        assert forecast is not None, (
            "Bei einer echten Datenluecke fuer die Folge-Etappe darf das "
            "Ergebnis nicht None sein — sonst kann die Kurzform die Luecke "
            "nicht von 'kein Folgetag' unterscheiden."
        )
        gaps = forecast.get("_gap_offsets") or set()
        assert "+1" in gaps, (
            f"Die nicht beschaffbare Folge-Etappe muss als Luecke markiert "
            f"sein (_gap_offsets), bekommen: {forecast!r}"
        )
        assert "+2" not in gaps, (
            f"Uebermorgen gibt es gar keine Etappe — das ist kein "
            f"Datenausfall und darf nicht als Luecke gelten: {forecast!r}"
        )


# ---------------------------------------------------------------------------
# AC-4 (Regressions-Schutz): kein Folgetag -> weiterhin TH+:-
# ---------------------------------------------------------------------------

class TestAC4NoFollowUpDayKeepsNullForm:
    """Gegenprobe zu AC-3, bewusst im selben Modul: 'kein Folgetag' und
    'Folgetag ohne Daten' MUESSEN unterscheidbar bleiben."""

    @pytest.mark.parametrize("thunder_forecast", [None, {}])
    def test_no_follow_up_day_still_shows_dash(self, thunder_forecast):
        """
        GIVEN: kein thunder_forecast (letzte Etappe des Trips, kein Folgetag)
        WHEN:  die Kurzform gerendert wird
        THEN:  'TH+:-' wie bisher — NICHT 'TH+:?'
        """
        sms = _direct_sms(thunder_forecast)

        assert "TH+:-" in sms, (
            f"Ohne Folgetag muss die Null-Form 'TH+:-' stehen bleiben.\n"
            f"SMS: {sms}"
        )
        assert "TH+:?" not in sms, (
            f"'TH+:?' (unbekannt) darf nur bei einer ECHTEN Datenluecke "
            f"erscheinen, nicht wenn es schlicht keinen Folgetag gibt.\n"
            f"SMS: {sms}"
        )

    def test_gap_and_no_follow_up_day_are_distinguishable(self):
        """
        GIVEN: derselbe Datenstand, einmal mit und einmal ohne Luecken-Marker
        WHEN:  beide Kurzformen gerendert werden
        THEN:  sie unterscheiden sich ('TH+:?' vs. 'TH+:-') — sonst ist die
               Regel nur zufaellig erfuellt
        """
        with_gap = _direct_sms({"_gap_offsets": {"+1"}})
        without = _direct_sms({})

        assert "TH+:?" in with_gap and "TH+:-" in without, (
            f"Luecke und 'kein Folgetag' muessen zu verschiedenen Kuerzeln "
            f"fuehren.\nmit Luecke: {with_gap}\nohne: {without}"
        )


# ---------------------------------------------------------------------------
# AC-6: konfigurierter Schwellwert wirkt auch auf TH+:
# ---------------------------------------------------------------------------

class TestAC6ConfiguredThresholdAppliesToThPlus:
    """Der Schwellwert der Metrik 'Gewitter' gilt fuer beide Kuerzel."""

    def test_th_plus_respects_configured_sms_threshold(self):
        """
        GIVEN: Metrik 'Gewitter' gewaehlt mit sms_threshold=2.0, Folge-Etappe
               mit Gewitter der Stufe LOW (Renderwert 1.0 — auf Hoehe des
               hartkodierten Defaults 1.0, aber unter dem konfigurierten 2.0)
        WHEN:  das Briefing gerendert wird
        THEN:  'TH+:-' (kein Ausloesen unter der Schwelle), nicht 'TH+:L@15'
        """
        sms = _trip_sms(
            "morning",
            _dc("temperature", "thunder", thunder_sms_threshold=2.0),
            thunder_forecast=_TOMORROW_LOW,
        )

        assert "TH+:L@15" not in sms, (
            f"'TH+:' loest unterhalb des konfigurierten Schwellwerts (2.0) "
            f"aus — der Schwellwert der Metrik 'Gewitter' wird an das Kuerzel "
            f"der Folge-Etappe nicht weitergereicht.\nSMS: {sms}"
        )
        assert "TH+:-" in sms, (
            f"Unter der konfigurierten Schwelle gehoert die Null-Form "
            f"'TH+:-' in die Zeile.\nSMS: {sms}"
        )

    def test_configured_threshold_still_lets_strong_thunder_through(self):
        """
        GIVEN: derselbe Schwellwert 2.0, Folge-Etappe mit Gewitter HIGH (3.0)
        WHEN:  das Briefing gerendert wird
        THEN:  'TH+:H@15' erscheint — der Schwellwert unterdrueckt nicht
               pauschal, sondern nur unterhalb der Schwelle
        """
        sms = _trip_sms(
            "morning",
            _dc("temperature", "thunder", thunder_sms_threshold=2.0),
            thunder_forecast=_TOMORROW_HIGH,
        )

        assert "TH+:H@15" in sms, (
            f"Starkes Gewitter am Folgetag liegt ueber der konfigurierten "
            f"Schwelle und muss erscheinen.\nSMS: {sms}"
        )


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
