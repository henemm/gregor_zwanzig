"""Fix #1486 — Vorschau == Versand AUCH dann, wenn der Ausblick ENTFAELLT.

Spec: docs/specs/modules/fix_1486_outlook_silent_exit.md (AC-6)
ADR:  docs/adr/0025-eine-gewitter-quelle-fuer-alle-briefing-kanaele.md

Luecke, die diese Datei schliesst (Adversary-Befund F001 zu #1486): die beiden
AC-6-Tests in ``tests/tdd/test_outlook_state_visible_in_channels.py`` belegen die
Zeichengleichheit von Vorschau und Versand ausschliesslich mit einem NICHT
leeren ``multi_day_trend`` (Fixture ``build_thunder_scenario()``). Damit nehmen
alle Renderer strukturell den Bestands-Zweig ``if multi_day_trend:`` und NIE den
mit #1486 eingefuehrten Zweig ``elif outlook_state is not None:``. Folge: streicht
man ``outlook_state``/``outlook_horizon_days`` aus dem ``self._render_email(...)``
-Aufruf in ``src/services/preview_service.py``, bleibt die gesamte benannte Suite
gruen — die Vorschau wuerde bei leerem Trend lautlos vom Versand abweichen
(genau der Rueckfall in das Verhalten VOR #1297).

Geprueft wird deshalb der ECHTE Vorschau-Pfad ``PreviewService._build_report()``
— nicht die Naht ``_render_email()`` direkt. Nur so liegt die Uebergabe der
Ausblick-Parameter INNERHALB des Prueflings; ein Direktaufruf der Naht wuerde
sie selbst mitliefern und die Luecke offenlassen.

DETERMINISMUS (Kern-Schicht, KEIN Netz):
  * ``demo=True`` -> ``FixtureProvider`` fuer das Wetter der berichteten Etappe
    (Vorbild: ``tests/tdd/test_sms_preview_matches_sent.py``).
  * Der Trip hat GENAU EINE Etappe. ``_build_stage_trend()`` steigt dadurch in
    Klasse A (``NO_STAGES``) aus, noch bevor irgendetwas abgerufen wird, und
    ``_collect_future_stage_weather()`` findet keine Folgeetappe — kein
    Live-Fetch, deshalb (anders als bei gefuelltem Trend) hier deterministisch
    pruefbar.

KEINE Mocks. Echte Trip-/Wetter-Objekte, echter Renderpfad.
"""
from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta, timezone

# Klasse-A-Text aus output/renderers/email/outlook_state_hint.py — das ist die
# Zusicherung an den Empfaenger, nicht bloss ein interner Wert.
TEXT_NO_STAGES = "Keine weiteren Etappen — kein Ausblick."

# Einzige zulaessige HTML-Abweichung: das minutengenaue "gesendet"-Label
# (#623 AC-5), das zwei Renderaufrufe naturgemaess verschieden stempeln koennen.
_SENT_LABEL = re.compile(r"gesendet [A-Za-z]{2} · \d{2}:\d{2}")

_TRIP_ID = "tdd-1486-outlook-absent"
_REPORT_TYPE = "evening"
# Morgen liegt sicher im 72h-Fenster des FixtureProviders (Anker: heute 00:00 UTC).
_TARGET = date.today() + timedelta(days=1)
# Nahe Innsbruck — der Standort der Open-Meteo-Fixtures.
_COORDS = [(47.2692, 11.4041), (47.2820, 11.4230), (47.2950, 11.4420)]


def _trip_with_a_single_stage():
    """Trip OHNE Folgeetappe: der Ausblick entfaellt regulaer (Klasse A).

    ``show_night_block=False`` haelt den Vergleich auf die Ausblick-Frage
    fokussiert; ``multi_day_trend_reports=["evening"]`` schaltet den Ausblick
    fuer diesen Report-Typ ueberhaupt erst scharf (sonst greift der
    ``show_outlook``-Riegel in den Renderern).
    """
    from app.models import (
        MetricConfig,
        TripReportConfig,
        UnifiedWeatherDisplayConfig,
    )
    from app.trip import Stage, TimeWindow, Trip, Waypoint

    waypoints = [
        Waypoint(
            id=f"W{i + 1}",
            name="Start" if i == 0 else ("Ziel" if i == len(_COORDS) - 1 else f"Punkt {i + 1}"),
            lat=lat, lon=lon, elevation_m=600,
            time_window=TimeWindow(start=time(9, 0), end=time(9, 0)),
        )
        for i, (lat, lon) in enumerate(_COORDS)
    ]
    stage = Stage(id="S1", name="Letzte Etappe", date=_TARGET,
                  start_time=time(9, 0), waypoints=waypoints)
    display_config = UnifiedWeatherDisplayConfig(
        trip_id=_TRIP_ID,
        metrics=[
            MetricConfig(metric_id="temperature", enabled=True, bucket="primary", order=0),
            MetricConfig(metric_id="thunder", enabled=True, bucket="primary", order=1),
        ],
        updated_at=datetime.now(timezone.utc),
        show_night_block=False,
    )
    report_config = TripReportConfig(
        trip_id=_TRIP_ID, multi_day_trend_reports=[_REPORT_TYPE],
    )
    return Trip(
        id=_TRIP_ID,
        name="TDD 1486 Ausblick entfaellt",
        stages=[stage],
        display_config=display_config,
        report_config=report_config,
    )


def _sent_report(trip, segment_weather, stage_name, trip_tz):
    """Der VERSAND-Render, Schritt fuer Schritt wie ``trip_report_scheduler.py``
    (Z. 865-932): dieselben Scheduler-Methoden, dieselbe Reihenfolge, derselbe
    ``format_email()``-Aufruf. Kein Nachbau eines Rechenwegs.

    Liefert zusaetzlich das ``TrendResult`` zurueck, damit der Test die
    Vorbedingung (leerer Trend + benannter Zustand) belegen kann.
    """
    from output.renderers.trip_report import TripReportFormatter
    from services.report_config_resolver import resolve_report_render_options
    from services.trip_report_scheduler import TripReportSchedulerService

    scheduler = TripReportSchedulerService()
    stage = trip.get_stage_for_date(_TARGET)
    jetzt_utc = datetime.now(timezone.utc)
    trend_result = scheduler._build_stage_trend(
        trip, _TARGET, now_utc=jetzt_utc, tz=trip_tz,
    )
    thunder_forecast = scheduler._build_thunder_forecast_from_trend_or_fetch(
        trip, _TARGET, now_utc=jetzt_utc, tz=trip_tz,
        multi_day_trend=trend_result.rows,
    )
    try:
        from services.weather_pattern import WeatherPatternService
        stability_result = WeatherPatternService().compute_for_trip(
            trip, _TARGET, segment_weather,
        )
    except Exception:
        stability_result = None

    report = TripReportFormatter().format_email(
        segments=segment_weather,
        trip_name=trip.name,
        trip=trip,
        report_type=_REPORT_TYPE,
        display_config=trip.display_config,
        stage_name=stage_name,
        stage_stats=scheduler._compute_stage_stats(stage),
        tz=trip_tz,
        profile=trip.aggregation.profile,
        stability_result=stability_result,
        report_config=trip.report_config,
        render_options=resolve_report_render_options(
            trip.report_config, trip.display_config, _REPORT_TYPE,
        ),
        thunder_forecast=thunder_forecast,
        multi_day_trend=trend_result.rows,
        outlook_state=trend_result.state,
        outlook_horizon_days=trend_result.horizon_days,
        night_weather=None,
    )
    return report, trend_result


def test_preview_matches_sent_when_the_outlook_is_absent():
    """AC-6 bei LEEREM Trend: die Vorschau nennt den Ausblick-Zustand genauso
    wie die versendete Mail — zeichengleich in allen vier Kanaelen.

    Faellt die Uebergabe von ``outlook_state`` im Vorschau-Pfad weg, zeigt die
    Vorschau wieder eine unerklaerte Leerstelle, waehrend der Versand den Grund
    nennt: genau die Divergenz, die #1297/ADR-0025 ausgeschlossen haben.
    """
    from app.models import OutlookState
    from services.preview_service import PreviewService

    trip = _trip_with_a_single_stage()

    # Der ECHTE Vorschau-Pfad — inklusive der Stelle, an der die
    # Ausblick-Parameter an die Render-Naht uebergeben werden.
    preview, segment_weather, stage_name, trip_tz = PreviewService()._build_report(
        trip, _TARGET, _REPORT_TYPE, demo=True,
    )
    sent, trend_result = _sent_report(trip, segment_weather, stage_name, trip_tz)

    # --- Vorbedingungen: genau die Lage, die die AC-6-Bestandstests auslassen.
    assert trend_result.rows is None, (
        "Fixture-Fehler: dieser Test braucht einen LEEREN Trend, sonst nehmen "
        f"die Renderer wieder den `if multi_day_trend:`-Zweig ({trend_result.rows!r})."
    )
    assert trend_result.state is OutlookState.NO_STAGES, (
        f"Fixture-Fehler: erwartet Klasse A (NO_STAGES), war {trend_result.state!r}"
    )
    assert TEXT_NO_STAGES in sent.email_plain, (
        "Fixture-Fehler: die versendete Klartext-Mail muss den Ausblick-Zustand "
        f"benennen, sonst prueft der Vergleich nichts:\n{sent.email_plain}"
    )
    assert TEXT_NO_STAGES in sent.email_html

    # --- AC-6: Vorschau ist zeichengleich zum Versand.
    assert preview.email_plain == sent.email_plain, (
        "Klartext-Mail: Vorschau divergiert vom Versand, wenn der Ausblick "
        f"entfaellt.\nVorschau:\n{preview.email_plain}\n\nVersand:\n{sent.email_plain}"
    )
    assert preview.sms_text == sent.sms_text, (
        f"Kurznachricht: {preview.sms_text!r} != {sent.sms_text!r}"
    )
    assert preview.telegram_bubbles == sent.telegram_bubbles, (
        "Telegram: die Vorschau-Bubbles weichen vom Versand ab."
    )
    assert _SENT_LABEL.sub("", preview.email_html) == _SENT_LABEL.sub("", sent.email_html), (
        "HTML-Mail: Vorschau divergiert vom Versand, wenn der Ausblick entfaellt."
    )

    # --- Und die Vorschau selbst nennt den Grund, statt ihn zu verschweigen.
    assert TEXT_NO_STAGES in preview.email_plain, (
        "Die Vorschau laesst den Ausblick kommentarlos weg, waehrend die "
        "versendete Mail den Grund nennt (#1486 / ADR-0025)."
    )
