"""Preview-Service für Email + SMS Vorschau (Epic #140, Option C).

Spec: docs/specs/modules/preview_service.md (Sub-Spec)
Master: docs/specs/modules/epic_140_output_vorschau.md

Wiederverwendet TripReportSchedulerService für Trip → Segments → Wetter,
ruft dann format_email() direkt auf — kein Versand, nur Render.
"""
from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from app.config import Settings
from app.loader import get_trips_dir, load_trip

if TYPE_CHECKING:
    from app.trip import Trip

logger = logging.getLogger(__name__)


VALID_REPORT_TYPES = ("morning", "evening")

# Issue #483: Demo-Mode-Fixtures liegen in <repo>/fixtures/openmeteo/.
# parents[2] = src/services/preview_service.py → src/services → src → <repo>.
_FIXTURE_DIR = Path(__file__).resolve().parents[2] / "fixtures" / "openmeteo"


class PreviewService:
    """Erzeugt Email-HTML + SMS-Token-Zeile ohne Versand."""

    def __init__(self, settings: Settings | None = None):
        self.settings = settings or Settings()

    def _load_trip(self, trip_id: str, user_id: str = "default") -> "Trip":
        """Lädt einen Trip aus `data/users/<user>/trips/<id>.json`.

        Raises:
            FileNotFoundError: wenn der Trip nicht existiert.
        """
        trips_dir = get_trips_dir(user_id)
        path = trips_dir / f"{trip_id}.json"
        if not path.exists():
            raise FileNotFoundError(
                f"Trip '{trip_id}' nicht gefunden für user '{user_id}'"
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
        stages = sorted(trip.stages, key=lambda s: s.date) if trip.stages else []
        for stage in stages:
            stage_d = stage.date if isinstance(stage.date, date) else date.fromisoformat(str(stage.date))
            if stage_d >= today:
                return stage_d
        if stages:
            s = stages[0]
            return s.date if isinstance(s.date, date) else date.fromisoformat(str(s.date))
        raise ValueError(f"Trip '{trip.id}' hat keine Stages")

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
            raise LookupError(
                f"Keine Stage am {target.isoformat()} im Trip '{trip.id}'"
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

        if trip.display_config and trip.report_config:
            trip.display_config.show_compact_summary = trip.report_config.show_compact_summary

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
    ):
        """Einzelstelle für den E-Mail-Render-Aufruf in der Vorschau."""
        return scheduler._formatter.format_email(
            segments=segment_weather,
            trip_name=trip.name,
            report_type=report_type,
            display_config=trip.display_config,
            stage_name=stage_name,
            stage_stats=stage_stats,
            tz=trip_tz,
            profile=trip.aggregation.profile,
            stability_result=stability_result,
            report_config=trip.report_config,
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
        report, segment_weather, stage_name, trip_tz = self._build_report(
            trip, target, report_type, demo=demo,
        )

        from src.formatters.sms_trip import SMSTripFormatter, SMS_SYMBOL_BY_METRIC
        # Input-Hygiene: Bei "ID: Beschreibung"-Stage-Namen (z.B. "KHW_10:
        # von Egger Alm...") nur den Teil vor dem ersten ':' nehmen, damit
        # der Prefix-Separator ':' in sms_format.md §3.1 eindeutig bleibt
        # und das nachgelagerte [:10]-Slice (_sanitize_stage_name) nicht
        # bereits gekürzte Beschreibungen produziert. Issue #497.
        clean_stage = (stage_name or "Etappe").split(":", 1)[0].strip()
        # Issue #624 (F001): konfigurierte Schwellwerte aus DisplayConfig übergeben.
        dc = trip.display_config
        _thr = {
            SMS_SYMBOL_BY_METRIC[m.metric_id]: m.sms_threshold
            for m in (dc.metrics if dc else [])
            if m.metric_id in SMS_SYMBOL_BY_METRIC and m.sms_threshold is not None
        }
        # Bug #397 (F001): tz durchreichen, sonst rendern die Stunden-Token UTC
        # statt Ortszeit (z.B. R5.0@8 statt @10 für CEST).
        token_line = SMSTripFormatter().format_sms(
            segment_weather,
            stage_name=clean_stage,
            report_type=report_type,
            tz=trip_tz,
            thresholds=_thr or None,
        )
        return report.email_subject, token_line

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
