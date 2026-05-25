"""Preview-Service für Email + SMS Vorschau (Epic #140, Option C).

Spec: docs/specs/modules/preview_service.md (Sub-Spec)
Master: docs/specs/modules/epic_140_output_vorschau.md

Wiederverwendet TripReportSchedulerService für Trip → Segments → Wetter,
ruft dann format_email() direkt auf — kein Versand, nur Render.
"""
from __future__ import annotations

import logging
from datetime import date
from typing import TYPE_CHECKING

from app.config import Settings
from app.loader import get_trips_dir, load_trip

if TYPE_CHECKING:
    from app.trip import Trip

logger = logging.getLogger(__name__)


VALID_REPORT_TYPES = ("morning", "evening")


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

    def _build_report(self, trip: "Trip", target: date, report_type: str):
        """Gemeinsame Pipeline: segments → weather → format_email → TripReport.

        Returns: (report, segment_weather, stage_name) — segment_weather und
        stage_name werden von render_sms_preview wiederverwendet (Issue #188).
        """
        from services.trip_report_scheduler import TripReportSchedulerService
        scheduler = TripReportSchedulerService(self.settings)
        segments = scheduler._convert_trip_to_segments(trip, target)
        if not segments:
            raise LookupError(
                f"Keine Stage am {target.isoformat()} im Trip '{trip.id}'"
            )

        segment_weather = scheduler._fetch_weather(segments)
        if not segment_weather:
            raise RuntimeError(
                f"Wetterdaten nicht verfügbar für Trip '{trip.id}' am {target.isoformat()}"
            )

        from utils.timezone import tz_for_coords
        trip_tz = tz_for_coords(segments[0].start_point.lat, segments[0].start_point.lon)

        stage = trip.get_stage_for_date(target)
        stage_name = stage.name if stage else None
        stage_stats = scheduler._compute_stage_stats(stage) if stage else None

        if trip.display_config and trip.report_config:
            trip.display_config.show_compact_summary = trip.report_config.show_compact_summary

        report = scheduler._formatter.format_email(
            segments=segment_weather,
            trip_name=trip.name,
            report_type=report_type,
            display_config=trip.display_config,
            stage_name=stage_name,
            stage_stats=stage_stats,
            tz=trip_tz,
            profile=trip.aggregation.profile,
        )
        return report, segment_weather, stage_name

    def render_email_preview(
        self,
        trip_id: str,
        *,
        user_id: str = "default",
        report_type: str = "morning",
        target_date: str | None = None,
    ) -> str:
        """Rendert die Email-HTML-Vorschau identisch zur echten Mail."""
        if report_type not in VALID_REPORT_TYPES:
            raise ValueError(f"Ungültiger report_type '{report_type}'")
        trip = self._load_trip(trip_id, user_id)
        target = self._resolve_target_date(trip, target_date)
        report, _segments, _stage_name = self._build_report(trip, target, report_type)
        return report.email_html

    def render_sms_preview(
        self,
        trip_id: str,
        *,
        user_id: str = "default",
        report_type: str = "morning",
        target_date: str | None = None,
    ) -> tuple[str, str]:
        """Rendert die SMS-Vorschau via echter Spec-Token-Pipeline (Issue #188).

        Returns: (email_subject, token_line). token_line ist sms_format.md
        v2.1-konform (≤160 Zeichen, '{StageName}: {Forecast-Tokens...}').
        """
        if report_type not in VALID_REPORT_TYPES:
            raise ValueError(f"Ungültiger report_type '{report_type}'")
        trip = self._load_trip(trip_id, user_id)
        target = self._resolve_target_date(trip, target_date)
        report, segment_weather, stage_name = self._build_report(trip, target, report_type)

        from src.formatters.sms_trip import SMSTripFormatter
        # Input-Hygiene: ':' aus Stage-Namen entfernen, damit der Prefix-
        # Separator ':' in sms_format.md §3.1 eindeutig bleibt.
        clean_stage = (stage_name or "Etappe").replace(":", "").strip()
        token_line = SMSTripFormatter().format_sms(
            segment_weather,
            stage_name=clean_stage,
            report_type=report_type,
        )
        return report.email_subject, token_line

    def render_signal_preview(
        self,
        trip_id: str,
        *,
        user_id: str = "default",
        report_type: str = "morning",
        target_date: str | None = None,
    ) -> tuple[str, str]:
        """Rendert die Signal-Vorschau via #360-Narrow-Renderer (kein Versand).

        Returns: (email_subject, signal_text). signal_text ist der schmale
        Monospace-Body aus render_narrow (≤26 Zeichen pro Zeile).
        """
        if report_type not in VALID_REPORT_TYPES:
            raise ValueError(f"Ungültiger report_type '{report_type}'")
        trip = self._load_trip(trip_id, user_id)
        target = self._resolve_target_date(trip, target_date)
        report, _segments, _stage_name = self._build_report(trip, target, report_type)
        return report.email_subject, (report.signal_text or "")

    def render_telegram_preview(
        self,
        trip_id: str,
        *,
        user_id: str = "default",
        report_type: str = "morning",
        target_date: str | None = None,
    ) -> tuple[str, str]:
        """Rendert die Telegram-Vorschau via #360-Narrow-Renderer (kein Versand).

        Returns: (email_subject, telegram_text).
        """
        if report_type not in VALID_REPORT_TYPES:
            raise ValueError(f"Ungültiger report_type '{report_type}'")
        trip = self._load_trip(trip_id, user_id)
        target = self._resolve_target_date(trip, target_date)
        report, _segments, _stage_name = self._build_report(trip, target, report_type)
        return report.email_subject, (report.telegram_text or "")
