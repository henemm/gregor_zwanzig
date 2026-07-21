"""Festes Tagesfenster 04:00-19:00 fuer die vier Kurzformen (Epic #1319, Scheibe A).

Spec: docs/specs/modules/sms_daywindow_aggregation.md
ADR:  docs/adr/0025-eine-gewitter-quelle-fuer-alle-briefing-kanaele.md (Novellierung)
Bug:  #1317 — Gewitter nach Ankunft (14:00) fehlt in SMS/Kurzzusammenfassung/
      Kopf-Pille/Telegram-Fusszeile, obwohl die Detailtabelle "Nacht am Ziel"
      es zeigt.

TDD RED. Der Nachweis laeuft ausschliesslich durch den gemeinsamen
Einstiegspunkt ``TripReportFormatter.format_email()`` (empfohlener Weg laut
Spec-Quellenliste fuer AC-1/AC-2/AC-4) — genau der Aufruf, der SMS,
Kurzzusammenfassung, Kopf-Pillen (via render_email/render_plain), Telegram-
Fusszeile UND die Detailtabelle "Nacht am Ziel" aus DEMSELBEN ``segments``/
``night_weather`` erzeugt. Kein Aufruf einer Helferfunktion mit vorgefertigten
Daten (ADR-0025, Entscheidung 5) — genau diese Abkuerzung liess den #1275-Bug
drei Anlaeufe lang ueberleben.

Fixture-Muster uebernommen aus tests/tdd/test_sms_thunder_from_hourly_timeseries.py
(#1275) und tests/tdd/test_briefing_parity_night_thunder.py (#1313, night_weather-
Zeitraum Ankunft->06:00 Folgetag).

Manche ACs (obere/untere Fenstergrenze-AUSSCHLUSS, Regressionsschutz,
fail-soft) sind bereits HEUTE gruen — nicht weil das Fenster schon korrekt
ist, sondern weil night_weather/Fruehstunden heute GAR NICHT einfliessen.
Sie sind als GUARD markiert und muessen nach dem Fix gruen BLEIBEN.

Keine Mocks, keine Dateiinhalt-Checks. Reale Fixtures, reale Aufrufe.
"""
from __future__ import annotations

import dataclasses
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from src.app.metric_catalog import build_default_display_config
from src.app.models import (
    ForecastDataPoint,
    ForecastMeta,
    GPXPoint,
    NormalizedTimeseries,
    Provider,
    SegmentWeatherData,
    SegmentWeatherSummary,
    ThunderLevel,
    TripSegment,
)
from src.output.renderers.day_window import DAY_WINDOW_END_HOUR, DAY_WINDOW_START_HOUR
from src.output.renderers.trip_report import TripReportFormatter

_YEAR, _MONTH = 2026, 7
_TZ = ZoneInfo("Europe/Paris")  # GR20/Korsika-typisch, CEST=UTC+2 im Juli

_WALK_START_H = 8
_ARRIVAL_H = 12  # Etappenende == Ankunft am Ziel


def _meta() -> ForecastMeta:
    return ForecastMeta(
        provider=Provider.OPENMETEO,
        model="test",
        run=datetime(_YEAR, _MONTH, 15, 0, 0, tzinfo=timezone.utc),
        grid_res_km=1.0,
        interp="point_grid",
    )


def _local_to_utc(day: int, hour: int) -> datetime:
    """Ortszeit-Wanduhr (Europe/Paris) `day`/`hour`:00 -> echter UTC-Instant.

    Realitaetsnah: ``ForecastDataPoint.ts`` ist in Produktion IMMER UTC
    (app/models.py:327 "start_time # UTC!"). Fixtures spezifizieren
    Ereignisse in Ortszeit — wie ein GR20-Wanderer sie erlebt und wie sie
    in den Erwartungswerten (`TH:H@14`, `14:00`, ...) auftauchen — und
    konvertieren hier EINMAL nach UTC, exakt wie ein Provider das fuer
    einen Ort mit UTC+2 (CEST) liefern wuerde. Deckt F001 auf: Code, der
    faelschlich roh `.hour` auf einem UTC-Instant liest, sieht eine andere
    Stunde als die hier gemeinte Ortszeit.
    """
    local_dt = datetime(_YEAR, _MONTH, day, hour, 0, tzinfo=_TZ)
    return local_dt.astimezone(timezone.utc)


def _dp(
    day: int, hour: int, *,
    thunder: ThunderLevel = ThunderLevel.NONE,
    precip: float = 0.0,
    pop: int = 0,
    gust: float = 5.0,
    wind: float = 5.0,
) -> ForecastDataPoint:
    """Ein Stunden-Datenpunkt zur Ortszeit-Stunde `hour` (Europe/Paris),
    intern als UTC-Instant gespeichert (s. `_local_to_utc`). Baseline-Werte
    liegen bewusst UNTER den SMS-Erwaehnungsschwellen (R>0.2, PR>20, G>20 —
    sms_format.md/DEFAULTS), damit nur explizit gesetzte Ereignis-Stunden
    Token/Pillen ausloesen."""
    return ForecastDataPoint(
        ts=_local_to_utc(day, hour),
        t2m_c=15.0,
        wind10m_kmh=wind,
        gust_kmh=gust,
        precip_1h_mm=precip,
        pop_pct=pop,
        cloud_total_pct=50,
        thunder_level=thunder,
        humidity_pct=55,
    )


def _segment(
    day: int = 20,
    start_h: int = _WALK_START_H,
    end_h: int = _ARRIVAL_H,
    early_event: tuple[int, ThunderLevel] | None = None,
    agg_precip_sum_mm: float | None = None,
) -> SegmentWeatherData:
    """Segment mit VOLLER 24h-Zeitreihe (0..23 Uhr) — wie in der Produktion
    (segment_weather.py:164-166: 'OpenMeteo returns full-day data'). Die
    heutigen Kurzform-Renderer filtern das bereits vorhandene Array auf die
    Wanderzeit [start_h, end_h] herunter; genau diese Fensterung ist der
    Test-Gegenstand.

    `early_event`: (hour, thunder_level) fuer eine Stunde VOR Aufbruch
    (Fixture fuer AC-7, untere Fenstergrenze).
    """
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
    early_h, early_lvl = early_event if early_event else (None, ThunderLevel.NONE)
    data = [
        _dp(day, h, thunder=(early_lvl if h == early_h else ThunderLevel.NONE))
        for h in range(0, 24)
    ]
    ts = NormalizedTimeseries(meta=_meta(), data=data)
    return SegmentWeatherData(
        segment=seg,
        timeseries=ts,
        aggregated=SegmentWeatherSummary(
            temp_min_c=10.0,
            temp_max_c=20.0,
            wind_max_kmh=15.0,
            gust_max_kmh=25.0,
            precip_sum_mm=agg_precip_sum_mm,
            thunder_level_max=ThunderLevel.NONE,
        ),
        fetched_at=datetime(_YEAR, _MONTH, day, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


def _segment_with_hour_overrides(
    day: int,
    start_h: int,
    end_h: int,
    overrides: dict[int, dict],
) -> SegmentWeatherData:
    """Wie ``_segment``, aber mit expliziten Ueberschreibungen je
    Ortszeit-Stunde (Regen/Wind/Boe/Gewitter) — ``early_event`` deckt nur
    Gewitter ab; Rand-/Volllast-Tests (Adversary-Zusatztests) brauchen mehr
    Kontrolle je Stunde."""
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
    data = [_dp(day, h, **overrides.get(h, {})) for h in range(0, 24)]
    ts = NormalizedTimeseries(meta=_meta(), data=data)
    precip_sum = sum(o.get("precip", 0.0) for o in overrides.values())
    return SegmentWeatherData(
        segment=seg,
        timeseries=ts,
        aggregated=SegmentWeatherSummary(
            temp_min_c=10.0,
            temp_max_c=20.0,
            wind_max_kmh=max([o.get("wind", 5.0) for o in overrides.values()] or [15.0]),
            gust_max_kmh=max([o.get("gust", 5.0) for o in overrides.values()] or [25.0]),
            precip_sum_mm=precip_sum,
            thunder_level_max=ThunderLevel.NONE,
        ),
        fetched_at=datetime(_YEAR, _MONTH, day, 6, 0, tzinfo=timezone.utc),
        provider="openmeteo",
    )


def _night_weather(
    day: int = 20,
    arrival_h: int = _ARRIVAL_H,
    event_hour: int | None = 14,
    event_day_offset: int = 0,
    thunder: ThunderLevel = ThunderLevel.HIGH,
    precip: float = 0.0,
    pop: int = 0,
    gust: float = 5.0,
) -> NormalizedTimeseries:
    """Nacht-Zeitreihe Ankunft (day, arrival_h) -> 06:00 Folgetag — wie
    trip_report_scheduler._fetch_night_weather() / #1313
    test_briefing_parity_night_thunder._night_weather(). `event_hour` (+
    `event_day_offset` 0=Ankunftstag, 1=Folgetag) setzt EIN Ereignis; alle
    anderen Stunden bleiben Baseline (kein Gewitter, keine Schwellwerte)."""
    points: list[ForecastDataPoint] = []
    for h in range(arrival_h, 24):
        is_ev = event_hour is not None and event_hour == h and event_day_offset == 0
        points.append(_dp(
            day, h,
            thunder=thunder if is_ev else ThunderLevel.NONE,
            precip=precip if is_ev else 0.0,
            pop=pop if is_ev else 0,
            gust=gust if is_ev else 5.0,
        ))
    next_day = day + 1
    for h in range(0, 7):
        is_ev = event_hour is not None and event_hour == h and event_day_offset == 1
        points.append(_dp(
            next_day, h,
            thunder=thunder if is_ev else ThunderLevel.NONE,
            precip=precip if is_ev else 0.0,
            pop=pop if is_ev else 0,
            gust=gust if is_ev else 5.0,
        ))
    return NormalizedTimeseries(meta=_meta(), data=points)


def _dc(*, rain_probability: bool = False):
    """UnifiedWeatherDisplayConfig — Default-Metriken (temperature/wind/gust/
    precipitation/thunder aktiv), optional rain_probability zusaetzlich (fuer
    AC-3, per Default deaktiviert)."""
    dc = build_default_display_config()
    if rain_probability:
        metrics = [
            dataclasses.replace(mc, enabled=True) if mc.metric_id == "rain_probability" else mc
            for mc in dc.metrics
        ]
        dc = dataclasses.replace(dc, metrics=metrics)
    return dc


def _report(segments, night_weather, *, report_type: str = "morning", dc=None):
    """Der EINE Einstiegspunkt: erzeugt SMS + E-Mail (HTML/Plain, inkl.
    Kopf-Pillen + Detailtabelle) + Telegram-Bubbles aus DENSELBEN Rohdaten."""
    return TripReportFormatter().format_email(
        segments,
        trip_name="E7",
        report_type=report_type,
        night_weather=night_weather,
        display_config=dc or _dc(),
        stage_name="E7",
        tz=_TZ,
    )


def _compact_line(email_plain: str) -> str:
    """Die Kompakt-Summary-Zeile (email/plain.py) — beginnt mit 'E7:'."""
    for line in email_plain.splitlines():
        if line.startswith("E7:"):
            return line
    return ""


def _telegram_text(report) -> str:
    return "\n".join(report.telegram_bubbles)


# ---------------------------------------------------------------------------
# AC-1: gemeldeter Fall #1317, Morgen-Report — Gewitter 14:00 nach Ankunft 12:00
# ---------------------------------------------------------------------------

class TestAC1MorningReportShowsArrivalThunder:
    """AC-1: Gewitter um 14:00 in night_weather (Ankunft 12:00) muss in SMS,
    Kurzzusammenfassung, Kopf-Pille UND Telegram-Fusszeile erscheinen.

    RED-Erwartung: schlaegt fehl, weil night_weather heute in KEINEM der vier
    Kurzform-Pfade ankommt (sms_trip.py/_segments_to_normalized_forecast,
    compact_summary.py/_collect_hourly_data, email/helpers.py/
    build_metrics_summary_pills, narrow.py/_windowed_thunder_severity lesen
    ausschliesslich `segments`, nie `night_weather`)."""

    def test_sms_shows_arrival_thunder(self):
        segments = [_segment(day=20)]
        night = _night_weather(day=20, event_hour=14, thunder=ThunderLevel.HIGH)
        report = _report(segments, night, report_type="morning")

        assert "TH:-" not in report.sms_text, (
            f"SMS meldet KEIN Gewitter, obwohl night_weather um 14:00 (nach "
            f"Ankunft 12:00) ein HIGH-Gewitter enthaelt — der gemeldete Fall "
            f"#1317.\nSMS: {report.sms_text}"
        )
        assert "TH:H@14" in report.sms_text, f"Erwartet `TH:H@14`.\nSMS: {report.sms_text}"

    def test_compact_summary_shows_arrival_thunder(self):
        segments = [_segment(day=20)]
        night = _night_weather(day=20, event_hour=14, thunder=ThunderLevel.HIGH)
        report = _report(segments, night, report_type="morning")
        compact = _compact_line(report.email_plain)

        assert "⚡" in compact and "14:00" in compact, (
            f"Kurzzusammenfassung nennt kein Gewitter um 14:00, obwohl die "
            f"Detailtabelle 'Nacht am Ziel' es korrekt zeigt.\nKompakt: {compact!r}"
        )

    def test_head_pill_shows_arrival_thunder(self):
        segments = [_segment(day=20)]
        night = _night_weather(day=20, event_hour=14, thunder=ThunderLevel.HIGH)
        report = _report(segments, night, report_type="morning")

        assert "Gewitter ab 14:00 · stärkste 14:00" in report.email_plain, (
            f"Metriken-Ueberblick-Pille zeigt kein Gewitter um 14:00.\n"
            f"Plain:\n{report.email_plain}"
        )

    def test_telegram_footer_shows_arrival_thunder(self):
        segments = [_segment(day=20)]
        night = _night_weather(day=20, event_hour=14, thunder=ThunderLevel.HIGH)
        report = _report(segments, night, report_type="morning")
        telegram = _telegram_text(report)

        assert "⚡ HIGH" in telegram, (
            f"Telegram-Fusszeile meldet kein Gewitter um 14:00.\n"
            f"Telegram:\n{telegram}"
        )


# ---------------------------------------------------------------------------
# AC-2: gleicher Fall, Abend-Report (berichteter Tag = morgen)
# ---------------------------------------------------------------------------

class TestAC2EveningReportShowsArrivalThunder:
    """AC-2: derselbe Fall wie AC-1, aber Etappe/Nacht liegen auf dem
    Folgetag (Abend-Report berichtet 'morgen'). Der Bezugstag-Mechanismus
    bleibt unveraendert korrekt — die Aggregation muss trotzdem greifen."""

    def test_all_four_channels_show_thunder_for_evening_report(self):
        segments = [_segment(day=21)]
        night = _night_weather(day=21, event_hour=14, thunder=ThunderLevel.HIGH)
        report = _report(segments, night, report_type="evening")
        compact = _compact_line(report.email_plain)
        telegram = _telegram_text(report)

        assert "TH:H@14" in report.sms_text, f"SMS: {report.sms_text}"
        assert "⚡" in compact and "14:00" in compact, f"Kompakt: {compact!r}"
        assert "Gewitter ab 14:00 · stärkste 14:00" in report.email_plain
        assert "⚡ HIGH" in telegram, f"Telegram:\n{telegram}"


# ---------------------------------------------------------------------------
# AC-3: Begleitwerte (Regen/Regenwahrscheinlichkeit/Boeen) derselben Stunde
# ---------------------------------------------------------------------------

class TestAC3CompanionValuesAtSameHour:
    """AC-3: 14:00 traegt zusaetzlich Regen (0.5mm>0.2), PR (30%>20%) und
    Boeen (25km/h>20km/h) — SMS `R`/`PR`/`G`, Kurzzusammenfassung und die
    Regen-/Boeen-Pillen muessen dieselbe Stunde zeigen (kein 'Gewitter ohne
    Regen')."""

    def test_sms_shows_rain_pr_gust_at_same_hour(self):
        segments = [_segment(day=20, agg_precip_sum_mm=0.5)]
        night = _night_weather(
            day=20, event_hour=14, thunder=ThunderLevel.HIGH,
            precip=0.5, pop=30, gust=25.0,
        )
        report = _report(segments, night, dc=_dc(rain_probability=True))
        sms = report.sms_text

        assert "TH:H@14" in sms, f"SMS: {sms}"
        assert "R0.5@14" in sms, f"Erwartet Regen-Token R0.5@14.\nSMS: {sms}"
        assert "PR30%@14" in sms, f"Erwartet Regenwahrsch.-Token PR30%@14.\nSMS: {sms}"
        assert "G25@14" in sms, f"Erwartet Boeen-Token G25@14.\nSMS: {sms}"

    def test_compact_summary_names_rain_start_hour(self):
        segments = [_segment(day=20, agg_precip_sum_mm=0.5)]
        night = _night_weather(
            day=20, event_hour=14, thunder=ThunderLevel.HIGH,
            precip=0.5, pop=30, gust=25.0,
        )
        report = _report(segments, night, dc=_dc(rain_probability=True))
        compact = _compact_line(report.email_plain)

        assert "Regen" in compact and "14:00" in compact, (
            f"Kurzzusammenfassung nennt kein Regen um 14:00 — die "
            f"Regenstunde aus night_weather fehlt in der Musterermittlung "
            f"(_find_rain_pattern liest nur segment-gefensterte Stunden).\n"
            f"Kompakt: {compact!r}"
        )

    def test_pills_show_rain_pr_gust_at_same_hour(self):
        segments = [_segment(day=20, agg_precip_sum_mm=0.5)]
        night = _night_weather(
            day=20, event_hour=14, thunder=ThunderLevel.HIGH,
            precip=0.5, pop=30, gust=25.0,
        )
        report = _report(segments, night, dc=_dc(rain_probability=True))
        plain = report.email_plain

        assert "Gewitter ab 14:00 · stärkste 14:00" in plain, f"Plain:\n{plain}"
        assert "Regen ab 14:00 · 0.5 mm" in plain, f"Regen-Pille fehlt.\nPlain:\n{plain}"
        assert "Regen-W. >20% ab 14:00 · max 30% (14:00)" in plain, (
            f"Regenwahrsch.-Pille fehlt.\nPlain:\n{plain}"
        )
        assert "Böen >20 km/h ab 14:00 · max 25 (14:00)" in plain, (
            f"Boeen-Pille fehlt.\nPlain:\n{plain}"
        )

    def test_compact_summary_shows_night_only_rain_ac1(self):
        """Fix #1330 AC-1: Regen ausschliesslich NACH Ankunft (Segment-
        Aggregat `summary.precip_sum_mm` explizit 0.0/trocken) muss in der
        Kurzzusammenfassung als Regen erscheinen, nicht als 'trocken' — die
        Ja/Nein-Weiche in `_format_precipitation()` liest heute noch das
        leere Segment-Aggregat statt der Tagesfenster-Summe aus `hourly`."""
        segments = [_segment(day=20, agg_precip_sum_mm=0.0)]
        night = _night_weather(
            day=20, event_hour=14, thunder=ThunderLevel.NONE, precip=0.5,
        )
        report = _report(segments, night)
        compact = _compact_line(report.email_plain)

        assert "trocken" not in compact, (
            f"Kurzzusammenfassung meldet 'trocken', obwohl im Tagesfenster "
            f"um 14:00 (nach Ankunft) 0.5mm Regen liegen — die Ja/Nein-"
            f"Weiche liest noch summary.precip_sum_mm=0.0 statt der "
            f"Tagesfenster-Summe aus `hourly`.\nKompakt: {compact!r}"
        )
        assert "Regen" in compact and "14:00" in compact, (
            f"Kurzzusammenfassung nennt keinen Regen um 14:00.\n"
            f"Kompakt: {compact!r}"
        )

    def test_compact_summary_shows_daywindow_gust_peak_ac2(self):
        """Fix #1330 AC-2: der Böen-Anteil der Kurzzusammenfassung muss die
        Tagesfenster-Spitze aus `hourly` zeigen (hier 45 km/h über
        night_weather um 14:00), nicht das hartkodierte, veraltete
        Segment-Aggregat `summary.gust_max_kmh=25.0` aus `_segment()`."""
        segments = [_segment(day=20)]
        night = _night_weather(
            day=20, event_hour=14, thunder=ThunderLevel.NONE, gust=45.0,
        )
        report = _report(segments, night)
        compact = _compact_line(report.email_plain)

        assert "25 km/h" not in compact, (
            f"Kurzzusammenfassung zeigt noch den veralteten Segment-"
            f"Böenwert 25 km/h statt der Tagesfenster-Spitze — "
            f"_format_wind() liest noch summary.gust_max_kmh statt max() "
            f"über `hourly`.\nKompakt: {compact!r}"
        )
        assert "45 km/h" in compact, (
            f"Kurzzusammenfassung nennt nicht die Tagesfenster-Böenspitze "
            f"45 km/h.\nKompakt: {compact!r}"
        )


# ---------------------------------------------------------------------------
# AC-4: Konsistenz-Invariante — alle vier Kurzformen + Detailtabelle einig
# ---------------------------------------------------------------------------

class TestAC4AllFiveOutputsAgree:
    """AC-4: ein einziger format_email()-Aufruf; SMS, Kurzzusammenfassung,
    Pille, Telegram-Fusszeile UND die Detailtabelle 'Nacht am Ziel' melden
    uebereinstimmend ein Gewitter um 14:00 (Fortfuehrung ADR-0025 auf das
    erweiterte Fenster)."""

    def test_single_call_all_outputs_consistent(self):
        segments = [_segment(day=20)]
        night = _night_weather(day=20, event_hour=14, thunder=ThunderLevel.HIGH)
        report = _report(segments, night, report_type="morning")
        compact = _compact_line(report.email_plain)
        telegram = _telegram_text(report)

        # Referenz (darf nicht regressieren): die Detailtabelle zeigt den
        # Nacht-Block bereits heute korrekt.
        assert "Nacht am Ziel" in report.email_plain, (
            "Referenzverhalten kaputt: Detailtabelle 'Nacht am Ziel' fehlt "
            "bereits im Ausgangszustand — Test-Fixture pruefen."
        )

        assert "TH:H@14" in report.sms_text, f"SMS widerspricht der Tabelle.\nSMS: {report.sms_text}"
        assert "⚡" in compact and "14:00" in compact, (
            f"Kurzzusammenfassung widerspricht der Tabelle.\nKompakt: {compact!r}"
        )
        assert "Gewitter ab 14:00 · stärkste 14:00" in report.email_plain, (
            "Kopf-Pille widerspricht der Tabelle."
        )
        assert "⚡ HIGH" in telegram, f"Telegram widerspricht der Tabelle.\nTelegram:\n{telegram}"


# ---------------------------------------------------------------------------
# AC-5/AC-6: obere Fenstergrenze (19:00) — Ausschluss/Einschluss
# ---------------------------------------------------------------------------

class TestAC5UpperBoundExclusion:
    """AC-5: Ereignis um 20:00 (ausserhalb 04-19, aber innerhalb Ankunft->
    06:00) darf KEIN Token/keine Pille ausloesen.

    GUARD, kein RED: heute schon gruen — aber aus dem falschen Grund
    (night_weather fliesst ueberhaupt nicht ein). Muss nach dem Fix gruen
    BLEIBEN (Beweis, dass die obere Grenze korrekt bei 19:00 gezogen wird,
    nicht einfach 'Ankunft->06:00' komplett uebernommen wird)."""

    def test_20_00_thunder_not_shown_in_any_channel(self):
        segments = [_segment(day=20)]
        night = _night_weather(day=20, event_hour=20, thunder=ThunderLevel.HIGH)
        report = _report(segments, night, report_type="morning")
        compact = _compact_line(report.email_plain)
        telegram = _telegram_text(report)

        assert "TH:-" in report.sms_text, f"SMS: {report.sms_text}"
        assert "TH:H@20" not in report.sms_text, f"SMS: {report.sms_text}"
        assert "⚡" not in compact, f"Kompakt: {compact!r}"
        assert "Gewitter ab 20:00" not in report.email_plain
        assert "kein Gewitter" in report.email_plain
        assert "⚡ kein" in telegram, f"Telegram:\n{telegram}"
        assert "⚡ HIGH" not in telegram, f"Telegram:\n{telegram}"


class TestAC6UpperBoundInclusion:
    """AC-6: Ereignis um 18:00 (innerhalb 04-19) MUSS in allen vier Kanaelen
    erscheinen. Echtes RED (wie AC-1), diesmal an der oberen Grenze."""

    def test_18_00_thunder_shown_in_all_four_channels(self):
        segments = [_segment(day=20)]
        night = _night_weather(day=20, event_hour=18, thunder=ThunderLevel.HIGH)
        report = _report(segments, night, report_type="morning")
        compact = _compact_line(report.email_plain)
        telegram = _telegram_text(report)

        assert "TH:H@18" in report.sms_text, f"SMS: {report.sms_text}"
        assert "⚡" in compact and "18:00" in compact, f"Kompakt: {compact!r}"
        assert "Gewitter ab 18:00 · stärkste 18:00" in report.email_plain
        assert "⚡ HIGH" in telegram, f"Telegram:\n{telegram}"


# ---------------------------------------------------------------------------
# AC-7: untere Fenstergrenze (04:00) — vor Aufbruch
# ---------------------------------------------------------------------------

class TestAC7LowerBoundBeforeDeparture:
    """AC-7: Aufbruch 08:00. Ereignis um 05:00 (vor Aufbruch, innerhalb
    04-19) muss gezeigt werden — echtes RED (die Wanderzeit-Fensterung
    schneidet heute an start_h=8 ab). Ereignis um 03:00 (ausserhalb 04-19)
    bleibt GUARD (heute wie zukuenftig ausgeschlossen)."""

    def test_05_00_thunder_before_departure_is_shown(self):
        segments = [_segment(day=20, early_event=(5, ThunderLevel.HIGH))]
        report = _report(segments, None, report_type="morning")
        compact = _compact_line(report.email_plain)
        telegram = _telegram_text(report)

        assert "TH:H@5" in report.sms_text, (
            f"SMS zeigt kein Gewitter um 05:00 (vor Aufbruch 08:00, aber "
            f"innerhalb 04-19) — die erste-Segment-Fensteruntergrenze wurde "
            f"nicht auf 4 abgesenkt.\nSMS: {report.sms_text}"
        )
        assert "⚡" in compact and "5:00" in compact, f"Kompakt: {compact!r}"
        assert "Gewitter ab 05:00 · stärkste 05:00" in report.email_plain
        assert "⚡ HIGH" in telegram, f"Telegram:\n{telegram}"

    def test_03_00_thunder_before_departure_stays_excluded(self):
        """GUARD: 03:00 liegt ausserhalb 04-19 — heute schon (zufaellig)
        ausgeschlossen, muss es auch nach der Fensteraufweitung bleiben."""
        segments = [_segment(day=20, early_event=(3, ThunderLevel.HIGH))]
        report = _report(segments, None, report_type="morning")

        assert "TH:-" in report.sms_text, (
            f"03:00 liegt ausserhalb des Tagesfensters 04-19 und darf kein "
            f"Token ausloesen.\nSMS: {report.sms_text}"
        )
        assert "TH:H@3" not in report.sms_text, f"SMS: {report.sms_text}"


# ---------------------------------------------------------------------------
# AC-8: Regressionsschutz — reine Wanderzeit-Ereignisse unveraendert
# ---------------------------------------------------------------------------

class TestAC8WalkingWindowRegressionGuard:
    """AC-8 GUARD: ein Ereignis vollstaendig INNERHALB der bisherigen
    Wanderzeit (08-12) — muss vor UND nach dem Fix identisch (bit-gleich)
    gemeldet werden. Bereits heute gruen (unveraendert korrekt seit #1275)."""

    def test_thunder_within_walking_window_unaffected(self):
        segments = [_segment(day=20, early_event=(9, ThunderLevel.HIGH))]
        night = _night_weather(day=20, event_hour=None)
        report = _report(segments, night, report_type="morning")
        compact = _compact_line(report.email_plain)
        telegram = _telegram_text(report)

        assert "TH:H@9" in report.sms_text, f"SMS: {report.sms_text}"
        assert "⚡" in compact and "9:00" in compact, f"Kompakt: {compact!r}"
        assert "Gewitter ab 09:00 · stärkste 09:00" in report.email_plain
        assert "⚡ HIGH" in telegram, f"Telegram:\n{telegram}"


# ---------------------------------------------------------------------------
# AC-9: night_weather=None -> fail-soft (kein Absturz, reine Segment-Fensterung)
# ---------------------------------------------------------------------------

class TestAC9NightWeatherNoneFailSoft:
    """AC-9 GUARD: night_weather=None (z.B. dc.show_night_block=False, kein
    Zielsegment) darf keinen der vier Kanaele zum Absturz bringen; das
    Ergebnis ist reine Segment-Fensterung im 04-19-Fenster."""

    def test_no_night_weather_does_not_crash_and_stays_plausible(self):
        segments = [_segment(day=20)]
        report = _report(segments, None, report_type="morning")

        assert report.sms_text, "SMS-Text fehlt komplett (Absturz/Leerlauf?)"
        assert "TH:-" in report.sms_text, (
            f"Ohne night_weather und ohne Gewitter in der Etappe muss `TH:-` "
            f"stehen (fail-soft, kein erfundenes Signal).\nSMS: {report.sms_text}"
        )
        assert report.email_plain, "email_plain fehlt komplett (Absturz/Leerlauf?)"
        assert report.telegram_bubbles, "Telegram-Bubbles fehlen komplett (Absturz/Leerlauf?)"


# ---------------------------------------------------------------------------
# Adversary-Zusatztest 1: isolierter Schauer exakt am Fensterrand (F001-Fix)
# ---------------------------------------------------------------------------

class TestAdversaryRainAtWindowEdge:
    """Adversary-Abdeckungsluecke (Bug #1317-Nachtrag, F001): ein Schauer,
    der GENAU am Fensterrand (Ortszeit 04:00 bzw. 19:00) liegt, darf keine
    irrefuehrende Musteraussage erzeugen — weder ein erfundenes "Regen ab
    X:00" (als haette der Schauer FRISCH im Fenster begonnen, obwohl vor
    04:00 unbeobachtet) noch ein erfundenes "trocken ab X:00" ueber die
    obere Fenstergrenze 19:00 hinaus (unbeobachtet danach). Ortszeit
    Europe/Paris (UTC+2 im Juli) — deckt exakt den F001-Zeitzonenfehler ab,
    der ohne den Fix Ereignisse am unteren Rand (04/05 Uhr) verschluckte."""

    def test_shower_starting_exactly_at_lower_window_edge_04_00(self):
        """Regen 04:00-05:00 (Ortszeit, Fensteranfang), danach trocken bis
        Ankunft 12:00. `_find_rain_pattern` darf NICHT 'starts_later'
        (Regen ab X) melden, weil 04:00 der erste sichtbare Fensterwert ist
        — vor 04:00 ist unbeobachtet, ein 'ab 04:00' waere die Behauptung
        eines echten Neubeginns, den wir nicht kennen."""
        segments = [_segment_with_hour_overrides(
            day=20, start_h=_WALK_START_H, end_h=_ARRIVAL_H,
            overrides={4: {"precip": 0.4}, 5: {"precip": 0.4}},
        )]
        report = _report(segments, None, report_type="morning")
        compact = _compact_line(report.email_plain)

        assert "trocken, Regen ab 04:00" not in compact, (
            f"Irrefuehrend: 04:00 ist der erste sichtbare Fensterwert, kein "
            f"beobachteter Neubeginn.\nKompakt: {compact!r}"
        )
        assert "leichter Regen bis 5:00, trocken ab 6:00" in compact, (
            f"Erwartete exakte Musteraussage fehlt (deckt F001 auf: ohne "
            f"Ortszeit-Fix wird die 04/05-Uhr-Regenstunde am Fensteranfang "
            f"verschluckt statt korrekt als 'bis 5:00' erkannt).\n"
            f"Kompakt: {compact!r}"
        )

    def test_shower_ending_exactly_at_upper_window_edge_19_00(self):
        """Regen 18:00-19:00 (Ortszeit, Fensterende), davor trocken ab
        Aufbruch. `_find_rain_pattern` darf NICHT 'bis 19:00, trocken ab
        20:00' melden — 19:00 ist der letzte sichtbare Fensterwert, ob es
        danach weiterregnet ist unbeobachtet."""
        segments = [_segment_with_hour_overrides(
            day=20, start_h=_WALK_START_H, end_h=DAY_WINDOW_END_HOUR,
            overrides={18: {"precip": 0.4}, 19: {"precip": 0.4}},
        )]
        report = _report(segments, None, report_type="morning")
        compact = _compact_line(report.email_plain)

        assert "trocken ab 20:00" not in compact, (
            f"Irrefuehrend: 19:00 ist der letzte sichtbare Fensterwert, ein "
            f"beobachtetes Ende danach ist nicht bekannt.\nKompakt: {compact!r}"
        )
        assert "bis 19:00" not in compact, (
            f"Irrefuehrend: kein beobachtetes Ende bei 19:00.\nKompakt: {compact!r}"
        )
        assert "Regen" in compact, f"Regen fehlt komplett.\nKompakt: {compact!r}"


# ---------------------------------------------------------------------------
# Adversary-Zusatztest 2: SMS 160-Zeichen-Limit bei voll besetztem Fenster
# ---------------------------------------------------------------------------

class TestAdversarySmsLengthUnderFullWindow:
    """Adversary-Abdeckungsluecke: mit dem breiteren 04-19-Fenster (F001-Fix)
    koennen R/PR/W/G/TH gleichzeitig mit Onset+Peak (zwei verschiedenen
    Stunden je Metrik, `{first}@{h1}({peak}@{h2})`) auftreten — der
    Extremfall fuer die SMS-160-Zeichen-Regel. Muss weiterhin einhalten UND
    `TH:` darf nicht durch Truncation verschwinden (Prioritaet 10, hoechste
    Prio — sms_format.md §6)."""

    def test_full_window_all_metrics_onset_and_peak_stays_under_160(self):
        segments = [_segment_with_hour_overrides(
            day=20, start_h=DAY_WINDOW_START_HOUR, end_h=DAY_WINDOW_END_HOUR,
            overrides={
                6: {"precip": 0.3, "pop": 25, "wind": 12.0, "gust": 25.0,
                    "thunder": ThunderLevel.MED},
                14: {"precip": 5.0, "pop": 80, "wind": 45.0, "gust": 70.0,
                     "thunder": ThunderLevel.HIGH},
            },
        )]
        report = _report(segments, None, report_type="morning", dc=_dc(rain_probability=True))
        sms = report.sms_text

        assert len(sms) <= 160, (
            f"SMS ueberschreitet 160 Zeichen bei voll besetztem Fenster "
            f"({len(sms)} Zeichen).\nSMS: {sms}"
        )
        assert "TH:" in sms, f"TH: fehlt (durch Truncation verschluckt?).\nSMS: {sms}"
        assert "TH:-" not in sms, f"Gewitter-Ereignis wurde nicht erkannt.\nSMS: {sms}"
