"""N (Nacht-Tiefsttemperatur) nur im Abendbriefing, aus night_weather.

Spec: docs/specs/modules/night_temp_evening_only.md
Issue: #1319 (Epic), Scheibe D

PO-Entscheidung DEC-1 (2026-07-23): N erscheint (a) NUR NOCH im
Abendbriefing (morgens komplett weggelassen, kein Platzhalter) und zeigt
(b) dort die ECHTE Nacht-Tiefsttemperatur am Schlafplatz aus
``night_weather`` (Ankunft -> 06:00 Folgetag am Etappenziel), NICHT mehr das
Tagessegment-Minimum (kaelteste Wanderstunde).

TDD RED. Nachweis ueber den EINEN Einstiegspunkt
``TripReportFormatter.format_email()`` (genau wie
tests/tdd/test_sms_daywindow_aggregation.py) -- erzeugt SMS, E-Mail
(Kurzzusammenfassung + grosse Nachttabelle) UND Telegram-Bubbles aus
DENSELBEN ``segments``/``night_weather``. Kein Aufruf einer Helferfunktion
mit vorgefertigten Daten (ADR-0025, Entscheidung 5).

Fixture-Design: die Segment-Tageszeitreihe traegt eine KALTE Stunde
(``_COLD_C`` = 3.0, "kaelteste Wanderstunde") UND eine WARME Stunde
(``_WARM_MAX_C`` = 20.0, Tagesmaximum); ``night_weather`` traegt durchgehend
eine MILDE Nachttemperatur (``_MILD_NIGHT_C`` = 11.0). Vor dem Fix zeigen
alle drei Kurzformen abends noch 3 (Tagessegment-Min) statt 11
(Nacht-Tiefstwert) -- genau die zwei divergierenden Werte, die AC-2 prueft.

Keine Mocks, keine Dateiinhalt-Checks. Reale Fixtures, reale Aufrufe.
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from app.metric_catalog import build_default_display_config
from app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    MetricConfig,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
    UnifiedWeatherDisplayConfig,
)
from output.renderers.compact_summary import CompactSummaryFormatter
from output.renderers.narrow import render_telegram_bubbles
from output.renderers.sms_trip import SMSTripFormatter
from output.renderers.trip_report import TripReportFormatter

_YEAR, _MONTH = 2026, 7
_TZ = ZoneInfo("Europe/Paris")  # GR20/Korsika-typisch, CEST=UTC+2 im Juli

_WALK_START_H = 8
_ARRIVAL_H = 12  # Etappenende == Ankunft am Ziel
_WARM_HOUR = 11  # innerhalb der Wanderzeit 8-12

_COLD_C = 3.0        # kaelteste Wanderstunde (Tagessegment-Minimum, ALTE Quelle)
_WARM_MAX_C = 20.0   # Tagesmaximum (D-Token, unveraendert in beiden Report-Typen)
_MILD_NIGHT_C = 11.0  # echte Nacht-Tiefsttemperatur am Ziel (NEUE Quelle fuer N abends)


def _meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO,
        model="test",
        run=datetime(_YEAR, _MONTH, 15, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0,
        interp="point_grid",
    )


def _local_to_utc(day: int, hour: int) -> datetime:
    """Ortszeit-Wanduhr (Europe/Paris) `day`/`hour`:00 -> echter UTC-Instant
    (analog test_sms_daywindow_aggregation.py::_local_to_utc)."""
    local_dt = datetime(_YEAR, _MONTH, day, hour, 0, tzinfo=_TZ)
    return local_dt.astimezone(timezone.utc)


def _dp(day: int, hour: int, *, temp: float = 15.0) -> ForecastDataPoint:
    return ForecastDataPoint(
        ts=_local_to_utc(day, hour),
        t2m_c=temp,
        wind10m_kmh=5.0,
        gust_kmh=5.0,
        precip_1h_mm=0.0,
        pop_pct=0,
        cloud_total_pct=50,
        thunder_level=ThunderLevel.NONE,
        humidity_pct=55,
    )


def _segment(
    day: int = 20,
    start_h: int = _WALK_START_H,
    end_h: int = _ARRIVAL_H,
    *,
    cold_hour: int = _WALK_START_H,
    warm_hour: int = _WARM_HOUR,
) -> SegmentWeatherData:
    """Wander-Segment mit VOLLER 24h-Zeitreihe: kalte Stunde (_COLD_C) am
    ``cold_hour`` (Segment-Tagesminimum), warme Stunde (_WARM_MAX_C) am
    ``warm_hour`` (Segment-Tagesmaximum), Baseline 15.0 sonst. Das Aggregat
    (``SegmentWeatherSummary.temp_min_c``/``temp_max_c``) spiegelt dieselben
    Extremwerte -- die heutige (Bug-)Quelle fuer N/D in SMS und
    Kurzzusammenfassung (``sms_trip.py::_segments_to_normalized_forecast``,
    ``compact_summary.py::_format_temperature``)."""
    seg = TripSegment(
        segment_id=1,
        start_point=GPXPoint(lat=42.0, lon=9.0, elevation_m=500.0),
        end_point=GPXPoint(lat=42.1, lon=9.1, elevation_m=600.0),
        start_time=_local_to_utc(day, start_h),
        end_time=_local_to_utc(day, end_h),
        duration_hours=float(end_h - start_h),
        distance_km=12.0,
        ascent_m=300.0,
        descent_m=0.0,
    )
    data = []
    for h in range(0, 24):
        if h == cold_hour:
            t = _COLD_C
        elif h == warm_hour:
            t = _WARM_MAX_C
        else:
            t = 15.0
        data.append(_dp(day, h, temp=t))
    ts = NormalizedTimeseries(meta=_meta(), data=data)
    return SegmentWeatherData(
        segment=seg,
        timeseries=ts,
        aggregated=SegmentWeatherSummary(
            temp_min_c=_COLD_C,
            temp_max_c=_WARM_MAX_C,
            wind_max_kmh=15.0,
            gust_max_kmh=25.0,
            precip_sum_mm=0.0,
            thunder_level_max=ThunderLevel.NONE,
        ),
        fetched_at=datetime(_YEAR, _MONTH, day, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


def _night_weather(day: int = 20, arrival_h: int = _ARRIVAL_H) -> NormalizedTimeseries:
    """Nacht-Zeitreihe Ankunft (day, arrival_h) -> 06:00 Folgetag, DURCHGEHEND
    milde Temperatur (_MILD_NIGHT_C) -- die vom Fix zu nutzende echte Quelle
    fuer N abends (analog test_sms_daywindow_aggregation.py::_night_weather,
    #1313-Zeitraum Ankunft->06:00 Folgetag)."""
    points: list[ForecastDataPoint] = []
    for h in range(arrival_h, 24):
        points.append(_dp(day, h, temp=_MILD_NIGHT_C))
    next_day = day + 1
    for h in range(0, 7):
        points.append(_dp(next_day, h, temp=_MILD_NIGHT_C))
    return NormalizedTimeseries(meta=_meta(), data=points)


def _dc_temp_only() -> UnifiedWeatherDisplayConfig:
    """Displaykonfiguration mit AUSSCHLIESSLICH 'temperature' aktiv -- isoliert
    die Kurzzusammenfassungs-/Telegram-Kurzuebersichts-Assertions von anderen
    Metriken (Regen/Wind/Gewitter wuerden sonst z.B. eigene '-'-Zeichen in
    Zeitfenster-Mustern einstreuen und die Temperatur-Zeile verschleiern)."""
    return UnifiedWeatherDisplayConfig(
        trip_id="e7", metrics=[MetricConfig(metric_id="temperature", enabled=True)],
    )


def _report(segments, night_weather, *, report_type: str, dc=None):
    """Der EINE Einstiegspunkt (wie test_sms_daywindow_aggregation.py::_report):
    erzeugt SMS + E-Mail (inkl. Kurzzusammenfassung + Nachttabelle) +
    Telegram-Bubbles aus DENSELBEN Rohdaten."""
    return TripReportFormatter().format_email(
        segments,
        trip_name="E7",
        report_type=report_type,
        night_weather=night_weather,
        display_config=dc or _dc_temp_only(),
        stage_name="E7",
        tz=_TZ,
    )


def _compact_temp_phrase(email_plain: str) -> str:
    """Die Kurzzusammenfassungs-Zeile (email/plain.py) minus Titel-Praefix
    -- bei ``_dc_temp_only()`` besteht der Satz NUR aus der Temperatur-Phrase."""
    for line in email_plain.splitlines():
        if line.startswith("E7:"):
            if ": " in line:
                return line.split(": ", 1)[1]
            return ""
    return ""


def _sms_n_value(sms: str) -> str | None:
    """Extrahiert den N-Token-Wert aus der SMS (z.B. 'N11' -> '11'), oder
    None wenn kein N-Token vorkommt. Lookbehind schliesst Symbole wie 'SN'/
    'SN24+' aus (kein Buchstabe direkt vor dem 'N')."""
    m = re.search(r"(?<![A-Za-z])N(-?\d+)", sms)
    return m.group(1) if m else None


def _telegram_temp_line(report) -> str:
    """Die 'T ...'-Zeile aus der Telegram-Kurzuebersicht-Bubble."""
    for bubble in report.telegram_bubbles:
        if "Kurzübersicht" in bubble:
            for line in bubble.splitlines():
                if line.startswith("T "):
                    return line
    return ""


# ---------------------------------------------------------------------------
# AC-1: Morgenbriefing -- N fehlt in allen drei Kurzformen komplett (DEC-2)
# ---------------------------------------------------------------------------

class TestAC1NAbsentInAllThreeShortFormsMorning:
    """AC-1: Given ein Morgenbriefing mit vorhandenen Segment- UND
    Nachtdaten / When SMS, Kurzzusammenfassung und Telegram-Kurzuebersicht
    gerendert werden / Then enthaelt KEINE der drei Kurzformen ein
    N-Token/eine Nacht-Min-Angabe."""

    def test_n_absent_in_all_three_short_forms_morning(self):
        segments = [_segment()]
        night = _night_weather()
        report = _report(segments, night, report_type="morning")

        n_val = _sms_n_value(report.sms_text)
        assert n_val is None, (
            f"SMS zeigt morgens einen N-Wert (N{n_val}), obwohl N laut "
            f"DEC-2 morgens komplett entfaellt (kein Platzhalter).\n"
            f"SMS: {report.sms_text}"
        )

        temp_phrase = _compact_temp_phrase(report.email_plain)
        assert temp_phrase == f"{int(_WARM_MAX_C)}°C", (
            f"Kurzzusammenfassung zeigt morgens einen Bereich/Min-Wert "
            f"statt ausschliesslich des Tagesmaximums ({int(_WARM_MAX_C)}°C).\n"
            f"Phrase: {temp_phrase!r}\nPlain:\n{report.email_plain}"
        )

        tg_line = _telegram_temp_line(report)
        assert "3.0" not in tg_line, (
            f"Telegram-Kurzuebersicht zeigt morgens noch das "
            f"Tagessegment-Minimum (3.0) statt es wegzulassen.\n"
            f"Zeile: {tg_line!r}"
        )
        assert not re.search(r"\d+\.\d+-\d+\.\d+", tg_line), (
            f"Telegram-Kurzuebersicht zeigt morgens noch einen "
            f"Min-Max-Bereich statt nur des Maximums.\nZeile: {tg_line!r}"
        )


# ---------------------------------------------------------------------------
# AC-2: Abendbriefing -- N-Wert aus night_weather, NICHT Tagessegment-Minimum
# ---------------------------------------------------------------------------

class TestAC2NFromNightWeatherNotDaySegmentMinEvening:
    """AC-2: Given ein Abendbriefing mit night_weather-Daten am Ziel / When
    alle drei Kurzformen gerendert werden / Then zeigen alle drei einen
    N-Wert von 11 (Nacht-Tiefstwert), NICHT 3 (Tagessegment-Minimum)."""

    def test_n_from_night_weather_not_day_segment_min_evening(self):
        segments = [_segment()]
        night = _night_weather()
        report = _report(segments, night, report_type="evening")

        n_val = _sms_n_value(report.sms_text)
        assert n_val == "11", (
            f"SMS zeigt abends N{n_val} statt N11 -- der Wert muss aus "
            f"night_weather (milde Nacht 11°C) stammen, nicht aus dem "
            f"Tagessegment-Minimum (3°C, kaelteste Wanderstunde).\n"
            f"SMS: {report.sms_text}"
        )

        temp_phrase = _compact_temp_phrase(report.email_plain)
        assert temp_phrase == "11–20°C", (
            f"Kurzzusammenfassung zeigt abends nicht die echte "
            f"Nacht-Tiefsttemperatur (11°C) am Schlafplatz.\n"
            f"Phrase: {temp_phrase!r}\nPlain:\n{report.email_plain}"
        )

        tg_line = _telegram_temp_line(report)
        assert "11.0" in tg_line, (
            f"Telegram-Kurzuebersicht zeigt abends nicht die echte "
            f"Nacht-Tiefsttemperatur (11.0).\nZeile: {tg_line!r}"
        )
        assert "3.0" not in tg_line, (
            f"Telegram-Kurzuebersicht zeigt abends noch das "
            f"Tagessegment-Minimum (3.0) statt der Nacht-Tiefsttemperatur.\n"
            f"Zeile: {tg_line!r}"
        )


# ---------------------------------------------------------------------------
# AC-3: Konsistenz -- alle drei Kurzformen einig (Sichtbarkeit + Wert)
# ---------------------------------------------------------------------------

class TestAC3ShortFormsConsistentNightMinAndVisibility:
    """AC-3: Given identische Trip-/Wetterdaten / When SMS,
    Kurzzusammenfassung und Telegram in Morgen UND Abend gerendert werden /
    Then verhalten sich alle drei konsistent (gleiches Sichtbarkeits-Muster,
    gleicher numerischer Nacht-Min-Wert)."""

    def test_short_forms_consistent_night_min_and_visibility(self):
        segments = [_segment()]
        night = _night_weather()

        morning = _report(segments, night, report_type="morning")
        evening = _report(segments, night, report_type="evening")

        # Morgen: alle drei zeigen KEINE Nacht-Min-Angabe.
        assert _sms_n_value(morning.sms_text) is None, (
            f"SMS zeigt morgens einen N-Wert.\nSMS: {morning.sms_text}"
        )
        morning_compact = _compact_temp_phrase(morning.email_plain)
        assert "–" not in morning_compact, (
            f"Kurzzusammenfassung zeigt morgens einen Bereich (Min-Max) "
            f"statt nur des Maximums.\nPhrase: {morning_compact!r}"
        )
        morning_tg = _telegram_temp_line(morning)
        assert "3.0" not in morning_tg, (
            f"Telegram zeigt morgens noch das Tagessegment-Minimum.\n"
            f"Zeile: {morning_tg!r}"
        )

        # Abend: alle drei zeigen DENSELBEN Nacht-Min-Wert (11).
        sms_n = _sms_n_value(evening.sms_text)
        evening_compact = _compact_temp_phrase(evening.email_plain)
        evening_tg = _telegram_temp_line(evening)

        assert sms_n == "11", f"SMS: {evening.sms_text}"
        assert "11" in evening_compact, f"Kompakt: {evening_compact!r}"
        assert "11.0" in evening_tg, f"Telegram: {evening_tg!r}"
        assert "3.0" not in evening_tg, (
            f"Telegram zeigt abends noch das Tagessegment-Minimum statt "
            f"ausschliesslich des Nacht-Tiefstwerts.\nZeile: {evening_tg!r}"
        )


# ---------------------------------------------------------------------------
# AC-4: grosse E-Mail-Nachttabelle bleibt unveraendert (DEC-3, Abgrenzung)
# ---------------------------------------------------------------------------

class TestAC4LargeEmailNightTableUnchanged:
    """AC-4 (Charakterisierung/Negativ-AC, DEC-3): die grosse E-Mail-Tabelle
    'Nacht am Ziel' bleibt unabhaengig vom N-Sichtbarkeits-Gate der
    Kurzformen in BEIDEN Report-Typen unveraendert vorhanden. Dieser Test
    darf bereits heute gruen sein (Abgrenzung, kein Verhaltenswechsel durch
    diese Spec) -- muss es nach dem Fix auch BLEIBEN."""

    def test_large_email_night_table_unchanged(self):
        segments = [_segment()]
        night = _night_weather()
        dc = build_default_display_config()

        morning = TripReportFormatter().format_email(
            segments, trip_name="E7", report_type="morning",
            night_weather=night, display_config=dc, stage_name="E7", tz=_TZ,
        )
        evening = TripReportFormatter().format_email(
            segments, trip_name="E7", report_type="evening",
            night_weather=night, display_config=dc, stage_name="E7", tz=_TZ,
        )

        for label, report in (("morning", morning), ("evening", evening)):
            assert "Nacht am Ziel" in report.email_plain, (
                f"'Nacht am Ziel'-Block fehlt im {label}-Briefing -- DEC-3 "
                f"verlangt, dass die grosse Tabelle unabhaengig vom "
                f"N-Kurzform-Gate in beiden Report-Typen erscheint.\n"
                f"Plain:\n{report.email_plain}"
            )
            night_idx = report.email_plain.find("Nacht am Ziel")
            night_block = report.email_plain[night_idx:]
            assert "11.0" in night_block or "11" in night_block, (
                f"Nachttabelle zeigt nicht die echte Nacht-Tiefsttemperatur "
                f"(11°C) im {label}-Briefing.\nBlock:\n{night_block}"
            )


# ---------------------------------------------------------------------------
# AC-5: Bestandstrip ohne Migration rendert fehlerfrei (Charakterisierung)
# ---------------------------------------------------------------------------

class TestAC5LegacyTripRendersWithoutMigration:
    """AC-5: Given ein Bestandstrip ohne jegliche Datenmigration (aelterer
    Aufrufstil, kein night_weather/has_gap-Parameter gesetzt) / When die
    drei Kurzformen gerendert werden / Then laeuft das Rendering fehlerfrei
    durch (kein Schema-/Persistenzfehler, DEC-4: reine Render-Logik)."""

    def test_legacy_trip_renders_without_migration(self):
        segments = [_segment()]

        sms = SMSTripFormatter().format_sms(segments, stage_name="E7", tz=_TZ)
        assert sms, "SMS-Rendering eines Bestandstrips liefert leeren Text"

        compact = CompactSummaryFormatter().format_stage_summary(
            segments, "E7", _dc_temp_only(), tz=_TZ,
        )
        assert compact, "Kurzzusammenfassung eines Bestandstrips liefert leeren Text"

        bubbles = render_telegram_bubbles(
            segments=segments,
            seg_tables=[[]],
            dc=_dc_temp_only(),
            report_type="evening",
            tz=_TZ,
            trip_name="E7",
        )
        assert bubbles, "Telegram-Bubbles eines Bestandstrips sind leer"


# ---------------------------------------------------------------------------
# AC-6: night_weather=None im Abendbriefing -- fail-soft auf Tagessegment-Min
# ---------------------------------------------------------------------------

class TestAC6NightMinFailsSoftToDayMinWithoutNightWeather:
    """AC-6: Given night_weather=None (Provider-Fehler/Fetch-Ausfall) im
    Abendbriefing / When die drei Kurzformen gerendert werden / Then
    stuerzt kein Renderer ab, und die Nacht-Min-Anzeige faellt fail-soft
    auf das bisherige Tagessegment-Minimum (3) zurueck."""

    def test_night_min_fails_soft_to_day_min_without_night_weather(self):
        segments = [_segment()]
        report = _report(segments, None, report_type="evening")

        assert report.sms_text, "SMS-Text fehlt komplett (Absturz/Leerlauf?)"
        assert report.email_plain, "email_plain fehlt komplett (Absturz/Leerlauf?)"
        assert report.telegram_bubbles, "Telegram-Bubbles fehlen komplett (Absturz/Leerlauf?)"

        n_val = _sms_n_value(report.sms_text)
        assert n_val is not None, (
            f"Ohne night_weather muss die SMS abends trotzdem einen N-Wert "
            f"zeigen (Fail-soft-Fallback auf das Tagessegment-Minimum).\n"
            f"SMS: {report.sms_text}"
        )
        assert n_val == "3", (
            f"Fail-soft-Fallback muss auf das bisherige Tagessegment-"
            f"Minimum (3) zurueckfallen, nicht auf einen anderen Wert.\n"
            f"SMS: {report.sms_text}"
        )
