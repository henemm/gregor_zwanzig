"""Preview-Service für Email + SMS Vorschau (Epic #140, Option C).

Spec: docs/specs/modules/preview_service.md (Sub-Spec)
Master: docs/specs/modules/epic_140_output_vorschau.md

Wiederverwendet TripReportSchedulerService für Trip → Segments → Wetter,
ruft dann format_email() direkt auf — kein Versand, nur Render.
"""
from __future__ import annotations

import json
import logging
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from app.config import Settings
from app.loader import get_briefings_dir, load_trip

if TYPE_CHECKING:
    from app.trip import Trip

logger = logging.getLogger(__name__)


VALID_REPORT_TYPES = ("morning", "evening")

# Issue #990: Waypoint-Mindestschwelle für eine renderbare Etappe. SSoT ist
# der Vergleichsausdruck in src/services/trip_segments.py:120
# (`len(stage.waypoints) < 2` → []). Hier nur referenziert, nicht neu
# kodifiziert — bleibt konsistent mit dem geteilten Alert-/Briefing-Pfad.
_MIN_WAYPOINTS_FOR_RENDER = 2


def _stage_is_renderable(stage) -> bool:
    """True, wenn die Etappe genug Wegpunkte für eine Vorschau hat.

    Spiegelt die Schwelle aus trip_segments.convert_trip_to_segments
    (`len(stage.waypoints) < 2` → leere Segments).
    """
    return len(stage.waypoints) >= _MIN_WAYPOINTS_FOR_RENDER

# Issue #483: Demo-Mode-Fixtures liegen in <repo>/fixtures/openmeteo/.
# parents[2] = src/services/preview_service.py → src/services → src → <repo>.
_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "openmeteo"


class PreviewService:
    """Erzeugt Email-HTML + SMS-Token-Zeile ohne Versand."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()

    def _load_trip(self, trip_id: str, user_id: str = "default") -> "Trip":
        """Lädt einen Trip aus `data/users/<user>/briefings/<id>.json`
        (Issue #1250 Scheibe 7a Cutover, ADR-0023 -- war `trips/<id>.json`).

        Issue #1250 Scheibe 7b (AC-37): briefings/ haelt nach dem
        vergleich-Cutover BEIDE kinds. Ein `kind=="vergleich"`-Eintrag ist ein
        ComparePreset, kein Trip -- der Preview-Pfad weigert sich, ihn still
        als (kaputten, stufenlosen) Trip zu bauen.

        Raises:
            FileNotFoundError: wenn der Trip nicht existiert.
            ValueError: wenn der Eintrag ein Vergleich (kind=vergleich) ist.
        """
        trips_dir = get_briefings_dir(user_id)
        path = trips_dir / f"{trip_id}.json"
        if not path.exists():
            raise FileNotFoundError(
                f"Trip '{trip_id}' nicht gefunden für user '{user_id}'"
            )
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            raw = None
        if isinstance(raw, dict) and raw.get("kind") == "vergleich":
            raise ValueError(
                f"'{trip_id}' ist ein Vergleich (kind=vergleich), kein Trip — "
                "der Preview-Pfad lädt nur Trips (Issue #1250 AC-37)"
            )
        return load_trip(path)

    def _resolve_target_date(self, trip: "Trip", given_date: str | None) -> date:
        """Liefert das Ziel-Datum: gegebenes oder nächstes Stage-Datum.

        Falls kein Stage in der Zukunft, nimm das erste Stage-Datum überhaupt.
        """
        if given_date:
            try:
                return date.fromisoformat(given_date)
            except ValueError as e:
                raise ValueError(f"Ungültiges Datum '{given_date}', ISO erwartet") from e
        today = date.today()
        # Issue #990 / Adversary F001: Trip komplett ohne Etappen ist ein
        # anderer Fall als "Etappen ohne genug Wegpunkte". Ein wegpunktloser
        # Trip hat keine im Wegpunkt-Editor bearbeitbare Etappe — daher hier
        # ValueError (→ HTTP 422, generisch), NICHT den waypoint-LookupError
        # (→ 404), der das Frontend fälschlich zum Wegpunkt-Editor schickt.
        if not trip.stages:
            raise ValueError(f"Trip '{trip.id}' hat keine Stages")
        stages = sorted(trip.stages, key=lambda s: s.date)

        def _stage_d(s) -> date:
            return s.date if isinstance(s.date, date) else date.fromisoformat(str(s.date))

        # Issue #990: Auto-Resolve überspringt nicht-renderbare Etappen (< 2
        # Wegpunkte), damit die Vorschau nicht an einer wegpunktlosen Etappe
        # scheitert, obwohl eine spätere renderbar ist.
        for stage in stages:
            if _stage_is_renderable(stage) and _stage_d(stage) >= today:
                return _stage_d(stage)
        for stage in stages:  # Fallback: erste renderbare Etappe überhaupt
            if _stage_is_renderable(stage):
                return _stage_d(stage)
        raise LookupError(
            f"Trip '{trip.id}' hat keine Etappe mit genug waypoints für eine Vorschau"
        )

    def _build_report(
        self,
        trip: "Trip",
        target: date,
        report_type: str,
        demo: bool = False,
    ):
        """Gemeinsame Pipeline: segments → weather → format_email → TripReport.

        Args:
            trip: Trip-Modell
            target: Ziel-Datum
            report_type: 'morning' | 'evening'
            demo: Wenn True (Issue #483), wird der FixtureProvider statt der
                Live-OpenMeteo-API genutzt. Damit ist die Vorschau immer
                verfügbar — unabhängig von API-Limit oder Datum.

        Returns: (report, segment_weather, stage_name, trip_tz) — segment_weather,
        stage_name und trip_tz werden von render_sms_preview wiederverwendet
        (Issue #188 / Bug #397: tz muss in die SMS-Token durchgereicht werden).
        """
        from services.trip_report_scheduler import TripReportSchedulerService
        scheduler = TripReportSchedulerService(self.settings)
        segments = scheduler._convert_trip_to_segments(trip, target)
        if not segments:
            # Issue #990: Zwei Ursachen unterscheiden, damit die Frontend-
            # Erkennung aus #421 (matcht "waypoint" case-insensitive) nur beim
            # echten Wegpunkt-Fall greift, nicht beim "Datum falsch"-Fall.
            stage = trip.get_stage_for_date(target)
            if stage is None:
                raise LookupError(
                    f"Keine Stage am {target.isoformat()} im Trip '{trip.id}'"
                )
            raise LookupError(
                f"Stage am {target.isoformat()} im Trip '{trip.id}' hat zu wenige "
                "waypoints für eine Vorschau"
            )

        if demo:
            from providers.fixture import FixtureProvider
            provider = FixtureProvider(str(_FIXTURE_DIR))
        else:
            provider = None
        segment_weather = scheduler._fetch_weather(segments, provider=provider)
        if not segment_weather:
            raise RuntimeError(
                f"Wetterdaten nicht verfügbar für Trip '{trip.id}' am {target.isoformat()}"
            )

        from utils.timezone import tz_for_coords
        trip_tz = tz_for_coords(segments[0].start_point.lat, segments[0].start_point.lon)

        stage = trip.get_stage_for_date(target)
        stage_name = trip.numbered_stage_label(stage) if stage else None
        stage_stats = scheduler._compute_stage_stats(stage) if stage else None

        # Issue #1209 (Scheibe B): EINZIGER Ableitungspfad report_config ->
        # render-wirksame Optionen, ersetzt den Patch-Hack (F002), der
        # trip.display_config mutiert hat.
        from services.report_config_resolver import resolve_report_render_options
        render_options = resolve_report_render_options(
            trip.report_config, trip.display_config, report_type,
        )

        # Fix #1297: Vorschau-Pfad war nicht Teil von ADR-0025. multi_day_trend
        # und thunder_forecast werden hier ueber DIESELBEN Scheduler-Methoden
        # bezogen, die auch der Versandweg nutzt (trip_report_scheduler.py:836-848)
        # — keine lokale Nachbau-Berechnung, sonst divergiert die Vorschau
        # strukturell (SMS immer `TH+:-`). Gate auf show_multi_day_trend identisch
        # zum Versand.
        multi_day_trend = None
        if segment_weather and render_options.show_multi_day_trend:
            multi_day_trend = scheduler._build_stage_trend(trip, target, tz=trip_tz)
        thunder_forecast = scheduler._build_thunder_forecast_from_trend_or_fetch(
            trip, target, tz=trip_tz, multi_day_trend=multi_day_trend,
        )

        # Issue #1315: Nacht-Wetter fuer BEIDE report_types (#1313-Semantik),
        # ueber dieselbe geteilte Funktion wie der Versand (kein Duplikat).
        # Nur beschaffen, wenn der Trip die Sektion ueberhaupt zeigen wuerde
        # -- has_gap bleibt bewusst False (#1331, kein Versand-Kontext hier).
        # Adversary-Fix (F001, Issue #483): im Demo-Modus denselben
        # FixtureProvider durchreichen wie an _fetch_weather (Z.158-163) --
        # sonst loest die Demo-Vorschau einen echten Live-open-meteo-Call
        # fuer das Nacht-Segment aus und verletzt den Demo-Vertrag.
        night_weather = None
        if segment_weather and trip.display_config.show_night_block:
            from services.segment_weather import fetch_night_weather
            night_weather = fetch_night_weather(segment_weather[-1], provider=provider)

        # Issue #474: F12 Wetterlage-Label vor format_email berechnen.
        try:
            from services.weather_pattern import WeatherPatternService
            stability_result = WeatherPatternService().compute_for_trip(
                trip, target, segment_weather
            )
        except Exception:
            stability_result = None

        report = self._render_email(
            scheduler=scheduler,
            segment_weather=segment_weather,
            trip=trip,
            report_type=report_type,
            stage_name=stage_name,
            stage_stats=stage_stats,
            trip_tz=trip_tz,
            stability_result=stability_result,
            render_options=render_options,
            thunder_forecast=thunder_forecast,
            multi_day_trend=multi_day_trend,
            night_weather=night_weather,
        )
        return report, segment_weather, stage_name, trip_tz

    def _render_email(
        self,
        scheduler,
        segment_weather,
        trip: "Trip",
        report_type: str,
        stage_name: str | None,
        stage_stats,
        trip_tz,
        stability_result,
        render_options=None,
        thunder_forecast=None,
        multi_day_trend=None,
        night_weather=None,
    ):
        """Einzelstelle für den E-Mail-Render-Aufruf in der Vorschau.

        Fix #1297: thunder_forecast/multi_day_trend werden jetzt durchgereicht,
        damit die Vorschau denselben Gewitter-Wert wie der Versand zeigt (ADR-0025).
        Fix #1315: night_weather ebenso -- sonst zeigt die Vorschau nie die
        Sektion "Nacht am Ziel" (has_gap bleibt bewusst False, #1331).
        """
        from output.renderers.trip_report import TripReportFormatter
        return TripReportFormatter().format_email(
            segments=segment_weather,
            trip_name=trip.name,
            trip=trip,
            report_type=report_type,
            display_config=trip.display_config,
            stage_name=stage_name,
            stage_stats=stage_stats,
            tz=trip_tz,
            profile=trip.aggregation.profile,
            stability_result=stability_result,
            report_config=trip.report_config,
            render_options=render_options,
            thunder_forecast=thunder_forecast,
            multi_day_trend=multi_day_trend,
            night_weather=night_weather,
        )

    def render_email_preview(
        self,
        trip_id: str,
        *,
        user_id: str = "default",
        report_type: str = "morning",
        target_date: str | None = None,
        demo: bool = False,
    ) -> str:
        """Rendert die Email-HTML-Vorschau identisch zur echten Mail."""
        if report_type not in VALID_REPORT_TYPES:
            raise ValueError(f"Ungültiger report_type '{report_type}'")
        trip = self._load_trip(trip_id, user_id)
        target = self._resolve_target_date(trip, target_date)
        report, _segments, _stage_name, _trip_tz = self._build_report(
            trip, target, report_type, demo=demo,
        )
        # Issue #722: compact format — wrap plain text in <pre> for browser preview
        if not report.email_html and report.email_plain:
            import html as _html
            return f"<pre style='font-family:monospace;white-space:pre-wrap;font-size:13px'>{_html.escape(report.email_plain)}</pre>"
        return report.email_html

    def render_sms_preview(
        self,
        trip_id: str,
        *,
        user_id: str = "default",
        report_type: str = "morning",
        target_date: str | None = None,
        demo: bool = False,
    ) -> tuple[str, str]:
        """Rendert die SMS-Vorschau via echter Spec-Token-Pipeline (Issue #188).

        Returns: (email_subject, token_line). token_line ist sms_format.md
        v2.1-konform (≤160 Zeichen, '{StageName}: {Forecast-Tokens...}').
        """
        if report_type not in VALID_REPORT_TYPES:
            raise ValueError(f"Ungültiger report_type '{report_type}'")
        trip = self._load_trip(trip_id, user_id)
        target = self._resolve_target_date(trip, target_date)
        report, _segment_weather, _stage_name, _trip_tz = self._build_report(
            trip, target, report_type, demo=demo,
        )
        # Issue #954: kein eigener Renderpfad mehr — report.sms_text ist bereits
        # der #944-korrekte Versandtext (inkl. disabled_specs-Filterung).
        return report.email_subject, report.sms_text

    def render_telegram_preview(
        self,
        trip_id: str,
        *,
        user_id: str = "default",
        report_type: str = "morning",
        target_date: str | None = None,
        demo: bool = False,
    ) -> tuple[str, str, list[str]]:
        """Rendert die Telegram-Vorschau via #1001-Multi-Bubble-Renderer (kein Versand).

        Returns: (email_subject, body, bubbles). ``body`` ist die mit einem
        Trennzeichen verbundene Kette aller Bubbles (Rueckwaertskompatibilitaet
        fuer bestehende Konsumenten des einzelnen Body-Strings, AC-7).
        """
        if report_type not in VALID_REPORT_TYPES:
            raise ValueError(f"Ungültiger report_type '{report_type}'")
        trip = self._load_trip(trip_id, user_id)
        target = self._resolve_target_date(trip, target_date)
        report, _segments, _stage_name, _trip_tz = self._build_report(
            trip, target, report_type, demo=demo,
        )
        bubbles = report.telegram_bubbles or []
        body = "\n\n---\n\n".join(bubbles)
        return report.email_subject, body, bubbles
