"""
NotificationService — zentrale Verteilerschicht für Briefings und Hinweise.

Issue #1022: Services liefern DTOs; dieser Service wählt den Renderer und
ruft die Transport-Kanäle (E-Mail, SMS, Telegram) auf. Damit entkoppelt sich
der Scheduler (und später Alert-/Inbound-Pfade) von formatters/output/outputs.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Optional
from zoneinfo import ZoneInfo

from app.config import Settings
from formatters.trip_report import TripReportFormatter
from output.renderers.alert.model import AlertMessage
from output.renderers.alert.render import (
    render_email as render_alert_email,
    render_sms as render_alert_sms,
    render_subject as render_alert_subject,
    render_telegram as render_alert_telegram,
)
from output.renderers.email.design_tokens import (
    FONT_UI, G_ACCENT, G_DANGER, G_INK, G_PAPER, G_SURFACE_1, WEB_FONT_LINK,
)
from outputs.email import EmailOutput

if TYPE_CHECKING:
    from app.models import (
        DayComparison,
        NormalizedTimeseries,
        SegmentWeatherData,
        StabilityResult,
        TripReportConfig,
        UnifiedWeatherDisplayConfig,
    )
    from app.profile import ActivityProfile
    from app.trip import Trip
    from services.daylight_service import DaylightWindow

logger = logging.getLogger(__name__)


@dataclass
class TripReportRequest:
    """DTO vom Scheduler an den NotificationService.

    Enthält alle Daten, die für Rendering und Versand eines Trip-Briefings
    benötigt werden, aber keine Renderer-/Transport-Objekte.
    """
    trip: "Trip"
    report_type: str
    segment_weather: list["SegmentWeatherData"]
    trip_tz: ZoneInfo
    stage_name: str | None = None
    stage_stats: dict | None = None
    night_weather: Optional["NormalizedTimeseries"] = None
    thunder_forecast: Optional[dict] = None
    multi_day_trend: Optional[list[dict]] = None
    stability_result: Optional["StabilityResult"] = None
    daylight_window: Optional["DaylightWindow"] = None
    day_comparison: Optional["DayComparison"] = None
    exposed_sections: list = field(default_factory=list)
    report_config: Optional["TripReportConfig"] = None
    display_config: Optional["UnifiedWeatherDisplayConfig"] = None
    profile: Optional["ActivityProfile"] = None
    shortcode: str | None = None
    stage_total: int | None = None
    trip_url: str | None = None
    # Versand-Steuerung
    send_email: bool = True
    send_sms: bool = False
    send_telegram: bool = False
    # Hinweise / Präfixe
    test_prefix: bool = False
    on_demand_prefix: bool = False
    catchup_prefix: str | None = None
    # Service-Fehler-Hinweis für SMS-only + Teilausfall
    failed_segments: list["SegmentWeatherData"] = field(default_factory=list)
    # On-Demand unterdrückt Marker/Snapshot-Seiteneffekte (wird vom Scheduler gesteuert)
    on_demand: bool = False


@dataclass
class NotificationResult:
    """Rückgabe eines Versandlaufs."""
    sent: bool
    sent_channels: list[str] = field(default_factory=list)
    telegram_fully_sent: bool = True
    no_channel_configured: bool = False
    error: str | None = None


def build_service_error_email_html(trip_name: str, report_type: str, error_lines: str) -> str:
    """Service-Error E-Mail-Body mit Design-System tokens.

    Aus trip_report_scheduler.py hierher verschoben (Issue #1022), weil die
    Erzeugung des HTML-Bodys zum Renderer/Output-Bereich gehört.
    """
    return (
        '<!DOCTYPE html>'
        '<html>'
        '<head>'
        '<meta charset="utf-8">'
        f'{WEB_FONT_LINK}'
        '<style>'
        f'body {{ margin:0; padding:0; background:{G_PAPER}; '
        f'font-family:{FONT_UI}; color:{G_INK}; }}'
        '.container { max-width:640px; margin:0 auto; padding:24px; }'
        f'.heading {{ border-bottom:2px solid {G_ACCENT}; color:{G_ACCENT}; '
        'padding-bottom:8px; margin:0 0 16px 0; font-size:20px; }'
        f'.meta {{ background:{G_SURFACE_1}; padding:12px 16px; '
        'border-radius:6px; margin-bottom:16px; font-size:14px; }'
        f'.error-block {{ border-left:4px solid {G_DANGER}; '
        f'background:{G_SURFACE_1}; padding:12px 16px; margin:16px 0; '
        'font-family: ui-monospace, SFMono-Regular, Menlo, monospace; '
        'font-size:13px; white-space:pre-wrap; }'
        f'.footer {{ background:{G_INK}; color:#ffffff; padding:16px 24px; '
        'text-align:center; font-size:12px; }'
        '.footer a { color:#ffffff; text-decoration:underline; }'
        '</style>'
        '</head>'
        '<body>'
        '<div class="container">'
        '<h2 class="heading">Service-Benachrichtigung</h2>'
        '<div class="meta">'
        f'<strong>Trip:</strong> {trip_name}<br>'
        f'<strong>Report:</strong> {report_type.title()}<br>'
        '<strong>Problem:</strong> Wetterdaten konnten nicht abgerufen werden.'
        '</div>'
        '<p><strong>Betroffene Segmente:</strong></p>'
        f'<div class="error-block">{error_lines}</div>'
        '<p style="font-size:13px; color:#5c5a52;">'
        'Diese E-Mail wurde automatisch gesendet, weil Ihr Trip nur SMS aktiviert '
        'hat und Anbieter-Fehler aufgetreten sind.'
        '</p>'
        '</div>'
        f'<div class="footer" style="background:{G_INK}; color:#ffffff;">'
        'Gregor Zwanzig &mdash; automatischer Wetter-Service'
        '</div>'
        '</body>'
        '</html>'
    )


class NotificationService:
    """Wählt Renderer und Transporte für Trip-Briefings und Service-Hinweise."""

    def __init__(self, settings: Optional[Settings] = None, user_id: str = "default") -> None:
        self._settings = settings if settings else Settings().with_user_profile(user_id)
        self._formatter = TripReportFormatter()
        self._user_id = user_id

    # ------------------------------------------------------------------
    # Öffentliche API
    # ------------------------------------------------------------------

    def send_trip_report(self, request: TripReportRequest) -> NotificationResult:
        """Render ein Briefing und versende es über die konfigurierten Kanäle."""
        if not request.segment_weather:
            return NotificationResult(sent=False, error="no segments")

        report = self._formatter.format_email(
            segments=request.segment_weather,
            trip_name=request.trip.name,
            report_type=request.report_type,
            display_config=request.display_config,
            night_weather=request.night_weather,
            thunder_forecast=request.thunder_forecast,
            multi_day_trend=request.multi_day_trend,
            stage_name=request.stage_name,
            stage_stats=request.stage_stats,
            exposed_sections=request.exposed_sections,
            daylight=request.daylight_window,
            tz=request.trip_tz,
            profile=request.profile,
            stability_result=request.stability_result,
            report_config=request.report_config,
            day_comparison=request.day_comparison,
            shortcode=request.shortcode,
            stage_total=request.stage_total,
            trip_url=request.trip_url,
        )

        self._apply_prefixes(report, request)

        no_channel_configured = (
            not request.send_email
            and not request.send_sms
            and not request.send_telegram
        )

        sent_channels: list[str] = []

        # E-Mail
        if request.send_email:
            self._send_email(report)
            sent_channels.append("email")

        # SMS
        telegram_fully_sent = True
        if request.send_sms and self._settings.can_send_sms():
            try:
                from outputs.sms import SMSOutput
                SMSOutput(self._settings).send(
                    subject=report.email_subject,
                    body=report.sms_text or report.email_plain,
                )
                sent_channels.append("sms")
            except Exception as e:
                logger.error(f"SMS send failed for {request.trip.name}: {e}")

        # Telegram
        if request.send_telegram and self._settings.can_send_telegram():
            from outputs.base import OutputError
            from outputs.telegram import TelegramOutput

            bubbles = report.telegram_bubbles or [report.email_plain]
            for i, bubble_text in enumerate(bubbles):
                markup = report.telegram_actions_markup if i == len(bubbles) - 1 else None
                try:
                    TelegramOutput(self._settings).send(
                        subject=report.email_subject,
                        body=bubble_text,
                        reply_markup=markup,
                        parse_mode="HTML",
                        suppress_subject_line=True,
                    )
                except OutputError as e:
                    logger.error(
                        f"Telegram bubble {i + 1}/{len(bubbles)} send failed for {request.trip.name}: {e}"
                    )
                    telegram_fully_sent = False
                    break
            if telegram_fully_sent:
                sent_channels.append("telegram")

        # WEATHER-04: Service-E-Mail bei SMS-only + Fehler
        if request.failed_segments:
            self._send_service_error_email(request)

        return NotificationResult(
            sent=bool(sent_channels),
            sent_channels=sent_channels,
            telegram_fully_sent=telegram_fully_sent,
            no_channel_configured=no_channel_configured,
        )

    def send_no_data_hint(
        self,
        trip: "Trip",
        report_type: str,
        *,
        send_email: bool = True,
        send_sms: bool = False,
        send_telegram: bool = False,
    ) -> NotificationResult:
        """Kurzer Hinweis bei komplettem Wetterdaten-Ausfall (Issue #1012)."""
        subject = f"[{trip.name}] Wetterdaten nicht verfügbar"
        text = (
            "Wetterdienst aktuell nicht erreichbar — wir versuchen es weiter "
            "und liefern das Briefing nach, sobald Daten verfügbar sind."
        )
        sent_channels: list[str] = []

        if send_email:
            try:
                EmailOutput(self._settings).send(subject=subject, body=text, html=False)
                sent_channels.append("email")
            except Exception as e:
                logger.error(f"No-data hint email failed for {trip.name}: {e}")

        if send_sms and self._settings.can_send_sms():
            try:
                from outputs.sms import SMSOutput
                SMSOutput(self._settings).send(subject=subject, body=text)
                sent_channels.append("sms")
            except Exception as e:
                logger.error(f"No-data hint SMS failed for {trip.name}: {e}")

        if send_telegram and self._settings.can_send_telegram():
            try:
                from outputs.telegram import TelegramOutput
                TelegramOutput(self._settings).send(subject=subject, body=text)
                sent_channels.append("telegram")
            except Exception as e:
                logger.error(f"No-data hint Telegram failed for {trip.name}: {e}")

        return NotificationResult(sent=bool(sent_channels), sent_channels=sent_channels)

    def send_alert_message(
        self,
        alert_msg: AlertMessage,
        effective_channels: set[str],
        *,
        mail_type: str = "deviation-alert",
        mail_sink: Optional[object] = None,
    ) -> NotificationResult:
        """Versendet eine kanonische AlertMessage über die konfigurierten Kanäle.

        Issue #1023: TripAlertService kennt keine Transport-Implementierungen mehr.
        Renderer-Auswahl (E-Mail, Telegram, SMS) und Versand liegen hier.
        """
        subject = render_alert_subject(alert_msg)
        html, plain = render_alert_email(alert_msg)
        telegram_body = render_alert_telegram(alert_msg)
        sms_body = render_alert_sms(alert_msg)

        sent_channels: list[str] = []

        # E-Mail: Kanal gilt als betreten, wenn er konfiguriert ist — auch wenn
        # der Best-Effort-Versand fehlschlägt (Issue #684 AC-3, Anti-Pattern #656).
        if "email" in effective_channels and self._settings.can_send_email():
            sent_channels.append("email")
            try:
                if mail_sink is not None:
                    mail_sink(subject=subject, body=plain)
                else:
                    EmailOutput(self._settings).send(
                        subject=subject,
                        body=html,
                        plain_text_body=plain,
                        mail_type=mail_type,
                    )
            except Exception as e:
                logger.error(f"Alert email failed: {e}")

        # Telegram
        if "telegram" in effective_channels and self._settings.can_send_telegram():
            sent_channels.append("telegram")
            try:
                from outputs.telegram import TelegramOutput
                TelegramOutput(self._settings).send(
                    subject=subject,
                    body=telegram_body,
                    parse_mode="HTML",
                    suppress_subject_line=True,
                )
            except Exception as e:
                logger.error(f"Alert telegram failed: {e}")

        # SMS
        if "sms" in effective_channels and self._settings.can_send_sms():
            sent_channels.append("sms")
            try:
                from outputs.sms import SMSOutput
                SMSOutput(self._settings).send(subject=subject, body=sms_body)
            except Exception as e:
                logger.error(f"Alert SMS failed: {e}")

        return NotificationResult(sent=bool(sent_channels), sent_channels=sent_channels)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _apply_prefixes(self, report, request: TripReportRequest) -> None:
        """Test-/On-Demand-/Catchup-Präfixe auf Betreff und Body anwenden."""
        stage_name = request.stage_name or "Etappe"
        target_date = self._target_date_from_report(report, request)
        human_date = target_date.strftime("%d.%m.%Y")

        if request.test_prefix:
            hint = f"Test-Vorschau für {stage_name} am {human_date}"
            report.email_subject = f"[TEST] {report.email_subject}"
            if report.email_plain:
                report.email_plain = f"{hint}\n\n{report.email_plain}"
            if report.email_html:
                report.email_html = self._inject_html_hint(report.email_html, hint)
            if report.telegram_bubbles:
                report.telegram_bubbles[0] = f"{hint}\n\n{report.telegram_bubbles[0]}"
        elif request.on_demand_prefix:
            hint = f"Briefing auf Anfrage für {stage_name} am {human_date}"
            if report.email_plain:
                report.email_plain = f"{hint}\n\n{report.email_plain}"
            if report.email_html:
                report.email_html = self._inject_html_hint(report.email_html, hint)
            if report.telegram_bubbles:
                report.telegram_bubbles[0] = f"{hint}\n\n{report.telegram_bubbles[0]}"
        elif request.catchup_prefix:
            if report.email_plain:
                report.email_plain = f"{request.catchup_prefix}\n\n{report.email_plain}"
            if report.email_html:
                report.email_html = self._inject_html_hint(report.email_html, request.catchup_prefix)
            if report.telegram_bubbles:
                report.telegram_bubbles[0] = (
                    f"{request.catchup_prefix}\n\n{report.telegram_bubbles[0]}"
                )

    @staticmethod
    def _inject_html_hint(html: str, hint: str) -> str:
        if "<body>" in html:
            return html.replace("<body>", f"<body><p>{hint}</p>", 1)
        return f"<p>{hint}</p>{html}"

    @staticmethod
    def _target_date_from_report(report, request: TripReportRequest):
        """Versucht, das Zieldatum aus den Segmenten zu ermitteln."""
        if report.segments and report.segments[0].segment:
            return report.segments[0].segment.start_time.date()
        from datetime import date as _date
        return _date.today()

    def _send_email(self, report) -> None:
        """Versendet das Briefing per E-Mail (full oder compact)."""
        email_output = EmailOutput(self._settings)
        if report.email_html:
            email_output.send(
                subject=report.email_subject,
                body=report.email_html,
                plain_text_body=report.email_plain,
                mail_type="trip-briefing",
                mail_format="full",
            )
        else:
            email_output.send(
                subject=report.email_subject,
                body=report.email_plain,
                html=False,
                mail_type="trip-briefing",
                mail_format="compact",
            )

    def _send_service_error_email(self, request: TripReportRequest) -> None:
        """Service-E-Mail bei Provider-Fehler für SMS-only Trips."""
        config = request.report_config
        is_sms_only = config and config.send_sms and not config.send_email
        if not is_sms_only:
            return
        error_lines = "\n".join(
            f"  - Segment {e.segment.segment_id}: {e.error_message}"
            for e in request.failed_segments
            if e.segment is not None
        )
        subject = f"[{request.trip.name}] Wetterdaten nicht verfuegbar"
        body = build_service_error_email_html(
            trip_name=request.trip.name,
            report_type=request.report_type,
            error_lines=error_lines,
        )
        try:
            EmailOutput(self._settings).send(subject=subject, body=body, html=True)
            logger.info(f"Service error email sent for {request.trip.name}")
        except Exception as e:
            logger.error(f"Failed to send service error email: {e}")
