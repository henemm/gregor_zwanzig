"""Gemeinsamer Berichtsaufbau des Trip-Briefings (Issue #3128).

SPEC: docs/specs/modules/trip_briefing_aufbau.md

gz-eigenstaendig: Trip-Briefing setzt Etappen-Segmente, Nacht, Trend und Gewitter zusammen; der Ortsvergleich (compare_briefing_aufbau) hat andere Fachdaten und eigenen Ablauf, beide folgen nur demselben Bausteinmuster.

EINZIGE Stelle, die Segmente, Wetterabruf, Anreicherung (Wetterlage, Etappe,
Nacht, Trend, Gewitter) und den Render-Aufruf eines Trip-Briefings
zusammensetzt. Versand (``TripReportSchedulerService._briefing_bauen_und_senden``
plus ``NotificationService.send_trip_report``) = Baustein + Nebenwirkungen +
Senden; Vorschau (``PreviewService._build_report``) = Baustein.

Fuenf kleine Funktionen statt eines Rundum-Aufrufs, weil der Versand zwischen
Wetterabruf und Rendern Kontingent (#2961) und ``no_weather`` (#1113) prueft,
die Phasenuhr misst und den Anker im try-Block setzt (#1629). Ohne
Nebenwirkungen: kein Versand, kein Kontingent, kein Anker, keine Marker, keine
Persistenz. Phasenwechsel meldet der Baustein nur ueber den vom Aufrufer
uebergebenen Rueckruf ``phase``; die Uhr selbst bleibt im Scheduler.

Importiert weder ``trip_report_scheduler`` noch ``preview_service`` (kein
Zirkelimport): der Scheduler wird als Objekt uebergeben, seine Methoden werden
zur Laufzeit aufgeloest. Aufrufer loesen die Funktionen zur Laufzeit ueber das
Modul auf, damit eine Aenderung hier in Vorschau UND Versand wirkt.

Multi-User (ADR-0003): ``user_id`` kommt immer vom Aufrufer, nie ``"default"``.
"""
from __future__ import annotations

import contextvars
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

#: Marke "vom Baustein selbst beschaffen" (Versand) statt "vom Aufrufer
#: bereits geliefert" (Vorschau, Trend nebenlaeufig #1839).
_LADEN: Any = object()


def _ohne_phase(_name: str) -> None:
    """Kein Phasen-Rueckruf (Vorschau misst keine Phasen)."""


@dataclass
class TripAnreicherung:
    """Ergebnis von :func:`trip_anreicherung_bauen` (alles, was der Render
    neben den Segmenten braucht)."""

    stability_result: Any
    stage_name: Optional[str]
    stage_stats: Optional[dict]
    night_weather: Any
    multi_day_trend: Optional[list]
    outlook_state: Any
    outlook_horizon_days: Optional[int]
    thunder_forecast: Optional[dict]


def trip_segmente_bauen(scheduler, trip, target, persist: Optional[bool] = None) -> list:
    """Segmente der Etappe am Zieltag. ``persist=False`` = Vorschau (kein
    Backfill-Schreiben, #2036); ``None`` = Scheduler-Attribut entscheidet
    (Versand). Test-Fallback (#768), Klemmen (#1325, #2417) und der
    ``_last_converted_trip``-Tausch bleiben beim Aufrufer."""
    if persist is None:
        return scheduler._convert_trip_to_segments(trip, target)
    return scheduler._convert_trip_to_segments(trip, target, persist=persist)


def trip_wetter_laden(scheduler, segments: list, provider=None) -> list:
    """Hauptabruf des Wetters je Segment (Nutzer = ``scheduler._user_id``).
    ``provider`` nur fuer den Demo-Modus der Vorschau (#483)."""
    if provider is None:
        return scheduler._fetch_weather(segments)
    return scheduler._fetch_weather(segments, provider=provider)


def trip_anreicherung_bauen(
    scheduler,
    trip,
    target,
    segment_weather: list,
    *,
    report_type: str,
    now_utc,
    trip_tz,
    render_options,
    night_weather: Any = _LADEN,
    trend_result: Any = _LADEN,
    phase: Callable[[str], None] = _ohne_phase,
) -> TripAnreicherung:
    """Wetterlage, Etappe/Name/Stats, Nachtwetter, Trend und Gewitter.

    ``night_weather``/``trend_result`` weggelassen: der Baustein beschafft sie
    seriell wie der Versand (Nacht immer, #1313; Trend nach Resolver, #1208).
    Uebergeben: die Vorschau hat sie bereits nebenlaeufig beschafft (#1839).
    """
    # F12 / Issue #122 (#479): Stabilitaets-Label aus den vorhandenen
    # ``confidence_pct_min``-Werten der Folge-Segmente.
    stability_result = None
    try:
        from services.weather_pattern import WeatherPatternService
        stability_result = WeatherPatternService().compute_for_trip(
            trip, target, segment_weather
        )
    except Exception as e:
        logger.warning(f"WeatherPatternService failed for {trip.id}: {e}")

    stage = trip.get_stage_for_date(target)
    stage_name = trip.numbered_stage_label(stage) if stage else None
    stage_stats = scheduler._compute_stage_stats(stage) if stage else None

    # Nachtwetter (beide report_types, #1313).
    if night_weather is _LADEN:
        night_weather = None
        phase("nacht")
        if segment_weather:
            night_weather = scheduler._fetch_night_weather(segment_weather[-1])
        phase("rest")

    # Mehrtages-Trend VOR der Gewitter-Vorschau (#1275); Fix #1486: `.rows`
    # plus `.state`/`.horizon_days`.
    if trend_result is _LADEN:
        trend_result = None
        if segment_weather and render_options.show_multi_day_trend:
            phase("ausblick")
            trend_result = scheduler._build_stage_trend(
                trip, target, now_utc=now_utc, tz=trip_tz,
                report_type=report_type,
            )
    multi_day_trend = None
    outlook_state = None
    outlook_horizon_days = None
    if trend_result is not None:
        multi_day_trend = trend_result.rows
        outlook_state = trend_result.state
        outlook_horizon_days = trend_result.horizon_days

    # Gewitter-Vorschau (+1/+2, #1275) aus derselben Quelle wie der Ausblick;
    # #1651: Nachtreihe durchgereicht.
    phase("gewitter_vorschau")
    thunder_forecast = scheduler._build_thunder_forecast_from_trend_or_fetch(
        trip, target, now_utc=now_utc, tz=trip_tz,
        multi_day_trend=multi_day_trend, night_weather=night_weather,
    )
    phase("rest")

    return TripAnreicherung(
        stability_result=stability_result,
        stage_name=stage_name,
        stage_stats=stage_stats,
        night_weather=night_weather,
        multi_day_trend=multi_day_trend,
        outlook_state=outlook_state,
        outlook_horizon_days=outlook_horizon_days,
        thunder_forecast=thunder_forecast,
    )


def trip_report_rendern(
    *,
    segment_weather: list,
    trip,
    report_type: str,
    display_config,
    profile,
    report_config,
    render_options,
    tz,
    stage_name: Optional[str] = None,
    stage_stats: Optional[dict] = None,
    stability_result=None,
    night_weather=None,
    thunder_forecast: Optional[dict] = None,
    multi_day_trend: Optional[list] = None,
    outlook_state=None,
    outlook_horizon_days: Optional[int] = None,
    exposed_sections: Optional[list] = None,
    shortcode: Optional[str] = None,
    stage_total: Optional[int] = None,
    trip_url: Optional[str] = None,
    has_gap: bool = False,
    lang="de",
    undelivered: Optional[list] = None,
    vortag=None,
    starkregen: Optional[str] = None,
    formatter=None,
):
    """Der EINE Render-Weg (``TripReportFormatter.format_email``) fuer E-Mail,
    SMS und Telegram. Defaults = Defaults des Formatters (Vorschau: keine
    Luecke #1331, keine Sprache, keine Zusatzbloecke)."""
    if formatter is None:
        from output.renderers.trip_report import TripReportFormatter
        formatter = TripReportFormatter()
    return formatter.format_email(
        segments=segment_weather,
        trip_name=trip.name,
        trip=trip,
        undelivered=undelivered,
        report_type=report_type,
        display_config=display_config,
        night_weather=night_weather,
        thunder_forecast=thunder_forecast,
        multi_day_trend=multi_day_trend,
        outlook_state=outlook_state,
        outlook_horizon_days=outlook_horizon_days,
        stage_name=stage_name,
        stage_stats=stage_stats,
        exposed_sections=exposed_sections,
        tz=tz,
        profile=profile,
        stability_result=stability_result,
        report_config=report_config,
        day_comparison=vortag,
        shortcode=shortcode,
        stage_total=stage_total,
        trip_url=trip_url,
        render_options=render_options,
        has_gap=has_gap,
        starkregen_hint_text=starkregen,
        lang=lang,
    )


def _vorschau_haupt_und_nacht(scheduler, segments, trip, target, provider, user_id):
    """Hauptabruf plus Nachtwetter der Vorschau (#1839: Hauptzweig neben dem
    Trend). Nachtwetter nur bei ``night_weather_needed`` (heutiger Stand,
    Angleichung an den Versand in #3144)."""
    from services.fehler_code import fehler_mit_code

    segment_weather = trip_wetter_laden(scheduler, segments, provider=provider)
    if not segment_weather:
        raise fehler_mit_code(RuntimeError, "vorschau_wetter_fehlt",
                              trip_id=trip.id, datum=target.isoformat())
    from services.segment_weather import fetch_night_weather, night_weather_needed
    night_weather = None
    if night_weather_needed(trip.display_config):
        night_weather = fetch_night_weather(
            segment_weather[-1], provider=provider, user_id=user_id,
        )
    return segment_weather, night_weather


def trip_briefing_bauen(scheduler, trip, target, report_type: str, *, now_utc,
                        provider=None, user_id: Optional[str] = None):
    """Gesamtaufruf (Segmente -> Wetter -> Anreicherung -> Render) fuer die
    Vorschau. Rueckgabe ``(report, segment_weather, stage_name, trip_tz)``.

    Der Aufrufer schaltet ``scheduler.persist_backfill = False`` (#2036).
    Wirft ``LookupError`` ``vorschau_etappe_fehlt`` bzw.
    ``vorschau_zu_wenige_wegpunkte`` (#990) und ``RuntimeError``
    ``vorschau_wetter_fehlt``.
    """
    from services.fehler_code import fehler_mit_code
    from services.report_config_resolver import resolve_report_render_options
    from utils.timezone import tz_for_coords

    segments = trip_segmente_bauen(scheduler, trip, target, persist=False)
    if not segments:
        # #990: die Frontend-Erkennung (#421) unterscheidet beide Ursachen.
        if trip.get_stage_for_date(target) is None:
            raise fehler_mit_code(LookupError, "vorschau_etappe_fehlt",
                                  datum=target.isoformat(), trip_id=trip.id)
        raise fehler_mit_code(LookupError, "vorschau_zu_wenige_wegpunkte",
                              datum=target.isoformat(), trip_id=trip.id)

    trip_tz = tz_for_coords(segments[0].start_point.lat, segments[0].start_point.lon)
    render_options = resolve_report_render_options(
        trip.report_config, trip.display_config, report_type,
    )

    # #1839: Trend in EIGENEM Thread gleichzeitig zu Hauptabruf + Nacht;
    # copy_context() traegt ContextVar-Werte in den Zweig, der `with`-Block
    # wartet immer auf den Trend-Thread (kein verwaister Thread).
    with ThreadPoolExecutor(max_workers=1, thread_name_prefix="preview-trend") as pool:
        trend_future = None
        if render_options.show_multi_day_trend:
            trend_future = pool.submit(
                contextvars.copy_context().run,
                scheduler._build_stage_trend,
                trip, target, now_utc=now_utc, tz=trip_tz,
                report_type=report_type,
            )
        try:
            segment_weather, night_weather = _vorschau_haupt_und_nacht(
                scheduler, segments, trip, target, provider, user_id,
            )
        except BaseException:
            if trend_future is not None:
                trend_exc = trend_future.exception()
                if trend_exc is not None:
                    logger.warning(
                        "Vorschau-Trend verworfen, Hauptabruf gescheitert: %r",  # i18n-log
                        trend_exc,
                    )
            raise
        trend_result = trend_future.result() if trend_future is not None else None

    anr = trip_anreicherung_bauen(
        scheduler, trip, target, segment_weather,
        report_type=report_type, now_utc=now_utc, trip_tz=trip_tz,
        render_options=render_options,
        night_weather=night_weather, trend_result=trend_result,
    )
    report = trip_report_rendern(
        segment_weather=segment_weather,
        trip=trip,
        report_type=report_type,
        display_config=trip.display_config,
        profile=trip.aggregation.profile,
        report_config=trip.report_config,
        render_options=render_options,
        tz=trip_tz,
        stage_name=anr.stage_name,
        stage_stats=anr.stage_stats,
        stability_result=anr.stability_result,
        night_weather=anr.night_weather,
        thunder_forecast=anr.thunder_forecast,
        multi_day_trend=anr.multi_day_trend,
        outlook_state=anr.outlook_state,
        outlook_horizon_days=anr.outlook_horizon_days,
    )
    return report, segment_weather, anr.stage_name, trip_tz
