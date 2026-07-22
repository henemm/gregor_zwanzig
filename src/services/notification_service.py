"""
NotificationService — zentrale Verteilerschicht für Briefings und Hinweise.

Issue #1022: Services liefern DTOs; dieser Service wählt den Renderer und
ruft die Transport-Kanäle (E-Mail, SMS, Telegram) auf. Damit entkoppelt sich
der Scheduler (und später Alert-/Inbound-Pfade) von formatters/output/outputs.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Optional
from zoneinfo import ZoneInfo

from app.config import Settings
from output.renderers.trip_report import TripReportFormatter
from output.renderers.alert.model import AlertMessage, OnsetEvent
from output.renderers.alert.project import to_alert_message
from output.renderers.alert.render import (
    render_email as render_alert_email,
    render_sms as render_alert_sms,
    render_subject as render_alert_subject,
    render_telegram as render_alert_telegram,
)
from output.renderers.email.compact import _ascii as _ascii_hint
from output.renderers.email.design_tokens import (
    FONT_UI, G_ACCENT, G_DANGER, G_INK, G_PAPER, G_SURFACE_1, WEB_FONT_LINK,
)
from output.channels.base import OutputConfigError, OutputError
from output.channels.email import EmailOutput
from output.channels.sms import SMSOutput
from output.channels.telegram import TelegramOutput
from services.trip_command_processor import CommandResult
from utils.timezone import local_fmt

if TYPE_CHECKING:
    from app.models import (
        DayComparison,
        NormalizedTimeseries,
        SegmentWeatherData,
        StabilityResult,
        TripReportConfig,
        UnifiedWeatherDisplayConfig,
        WeatherChange,
    )
    from app.profile import ActivityProfile
    from app.trip import Trip
    from services.report_config_resolver import ReportRenderOptions

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
    # Issue #1113: Hinweis auf Abschnitte ohne Wetterdaten (0 % < Fehlerquote <= 75 %)
    partial_outage_hint: str | None = None
    # Service-Fehler-Hinweis für SMS-only + Teilausfall
    failed_segments: list["SegmentWeatherData"] = field(default_factory=list)
    # On-Demand unterdrückt Marker/Snapshot-Seiteneffekte (wird vom Scheduler gesteuert)
    on_demand: bool = False
    # Issue #1208: aufgeloeste render-wirksame Optionen (einziger Ableitungsweg
    # von report_config zu format_email); None → interner Resolver-Fallback.
    render_options: Optional["ReportRenderOptions"] = None


@dataclass
class NotificationResult:
    """Rückgabe eines Versandlaufs."""
    sent: bool
    sent_channels: list[str] = field(default_factory=list)
    telegram_fully_sent: bool = True
    no_channel_configured: bool = False
    error: str | None = None


@dataclass
class RadarAlertRequest:
    """DTO für Radar-Onset-Alerts vom TripAlertService an den NotificationService."""
    onset_minutes: int
    onset_time: str
    km_from: float
    km_to: float
    is_convective: bool
    intensity_label: str
    source_label: str
    briefing_context: str | None = None
    tz: ZoneInfo | None = None


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


def _official_source_label_for(dto_notices: list) -> str:
    """Anzeigename der amtlichen Quelle (Issue #1216 AC-7): abgeleitet aus der
    führenden (höchststufigen) Warnung statt des früher hartkodierten
    „GeoSphere Austria" für ALLE Quellen. Bei mehreren Quellen unter denselben
    Notices gewinnt die Quelle der höchststufigen Warnung."""
    from output.renderers.alert.official_alerts import official_alert_source_label

    if not dto_notices:
        return "Amtliche Quelle"
    leading = max(dto_notices, key=lambda n: n.alert.level)
    return official_alert_source_label(leading.alert.source)


def compute_has_gap(
    segments: list["SegmentWeatherData"],
    night_weather: Optional["NormalizedTimeseries"],
    tz: ZoneInfo,
) -> bool:
    """Issue #1331/#1334 Fix-Loop 4 (Option C): EINZIGER Berechnungspunkt fuer
    die Ziel-Datenluecke — der echte Versandpfad (``send_trip_report``, unten)
    ruft GENAU diese Funktion unmittelbar vor ``format_email()`` auf, weil
    ``night_weather`` hier real vorliegt (Scheduler holt es unbedingt, #1313).

    Statt die Luecke NACHZURECHNEN (Fix-Loop 3, separate Gap-Heuristik,
    wiederholt an Kanten abgewichen: F004-F007), wird sie DIREKT aus dem echten
    Renderer-Ergebnis abgeleitet — Erkennung == Anzeige per Konstruktion,
    keine Divergenz mehr moeglich. Subsumiert Segment-Luecken UND
    Nacht-Luecken in EINER Pruefung."""
    if not segments:
        return False
    from output.renderers.day_window import (
        DAY_WINDOW_END_HOUR, DAY_WINDOW_START_HOUR, build_day_window_points,
    )
    from utils.timezone import local_hour

    rendered = {
        local_hour(dp.ts, tz)
        for dp in build_day_window_points(segments, night_weather, tz)
    }
    expected = set(range(DAY_WINDOW_START_HOUR, DAY_WINDOW_END_HOUR + 1))
    return not expected.issubset(rendered)


def _official_source_url_for(dto_notices: list) -> str | None:
    """Quelle-Link der führenden (höchststufigen) Warnung (Issue #1216 F002).
    Für variant="standalone" derzeit ungenutzt (der Thin-Wrapper reicht 1:1 an
    render_official_alert_html durch), aber spec-konform mitgereicht."""
    if not dto_notices:
        return None
    leading = max(dto_notices, key=lambda n: n.alert.level)
    return getattr(leading.alert, "url", None)


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

        # Issue #1331/#1334 Fix-Loop 3 (F003): siehe compute_has_gap()
        # Docstring — Vorschau/Golden-Tests, die format_email() ohne
        # night_weather aufrufen, bekommen bewusst KEINE Luecke unterstellt.
        has_gap = compute_has_gap(
            request.segment_weather, request.night_weather, request.trip_tz,
        )

        report = self._formatter.format_email(
            segments=request.segment_weather,
            trip_name=request.trip.name,
            trip=request.trip,
            report_type=request.report_type,
            display_config=request.display_config,
            night_weather=request.night_weather,
            thunder_forecast=request.thunder_forecast,
            multi_day_trend=request.multi_day_trend,
            stage_name=request.stage_name,
            stage_stats=request.stage_stats,
            exposed_sections=request.exposed_sections,
            tz=request.trip_tz,
            profile=request.profile,
            stability_result=request.stability_result,
            report_config=request.report_config,
            day_comparison=request.day_comparison,
            shortcode=request.shortcode,
            stage_total=request.stage_total,
            trip_url=request.trip_url,
            render_options=request.render_options,
            has_gap=has_gap,
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
                SMSOutput(self._settings).send(
                    subject=report.email_subject,
                    body=report.sms_text or report.email_plain,
                )
                sent_channels.append("sms")
            except Exception as e:
                logger.error(f"SMS send failed for {request.trip.name}: {e}")

        # Telegram
        if request.send_telegram and self._settings.can_send_telegram():
            telegram_style = getattr(request.report_config, "telegram_style", "rich")

            if telegram_style == "kurzform":
                # Issue #1260: Kurzstil — EINE Nachricht mit dem SMS-Text,
                # ohne Bubbles/Inline-Knöpfe, parse_mode=None (Text ist nicht
                # HTML-escaped).
                try:
                    TelegramOutput(self._settings).send(
                        subject=report.email_subject,
                        body=report.sms_text or report.email_plain,
                        parse_mode=None,
                        suppress_subject_line=True,
                    )
                    sent_channels.append("telegram")
                except OutputError as e:
                    logger.error(
                        f"Telegram kurzform send failed for {request.trip.name}: {e}"
                    )
                    telegram_fully_sent = False
            else:
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
                SMSOutput(self._settings).send(subject=subject, body=text)
                sent_channels.append("sms")
            except Exception as e:
                logger.error(f"No-data hint SMS failed for {trip.name}: {e}")

        if send_telegram and self._settings.can_send_telegram():
            try:
                TelegramOutput(self._settings).send(subject=subject, body=text)
                sent_channels.append("telegram")
            except Exception as e:
                logger.error(f"No-data hint Telegram failed for {trip.name}: {e}")

        return NotificationResult(sent=bool(sent_channels), sent_channels=sent_channels)

    def send_deviation_alert(
        self,
        trip: "Trip",
        weather: list["SegmentWeatherData"],
        changes: list["WeatherChange"],
        effective_channels: set[str],
        official_notices: Optional[list] = None,
        mail_sink: Optional[object] = None,
        telegram_style: str = "rich",
    ) -> NotificationResult:
        """Wetter-Änderungs-Alert: rendern und über konfigurierte Kanäle versenden.

        Issue #1023: Der AlertService kennt keine Renderer-/Transport-Details mehr.
        Issue #1088: optionale amtliche Warnungen werden in dieselbe Nachricht
        gebündelt (kein zweiter Versand).
        """
        from utils.timezone import tz_for_coords

        alert_tz = tz_for_coords(
            weather[0].segment.start_point.lat,
            weather[0].segment.start_point.lon,
        )
        stand_at = local_fmt(datetime.now(timezone.utc), alert_tz)
        alert_msg = to_alert_message(
            changes, weather, trip.name, tz=alert_tz, stand_at=stand_at,
        )
        return self._dispatch_alert_message(
            alert_msg=alert_msg,
            effective_channels=effective_channels,
            mail_type="deviation-alert",
            mail_sink=mail_sink,
            target_name=trip.name,
            radar_mode=False,
            official_notices=official_notices,
            alert_tz=alert_tz,
            telegram_style=telegram_style,
        )

    def send_location_deviation_alert(
        self,
        entity_name: str,
        points: list,
        changes: list["WeatherChange"],
        effective_channels: set[str],
        mail_sink: Optional[object] = None,
    ) -> NotificationResult:
        """Trip-freier Deviation-Alert-Versand für EINEN generischen Ort
        (Compare, Issue #1169).

        Issue #1170: Ein-Ort-Sonderfall von
        `send_multi_location_deviation_alert()` — Delegation statt
        Duplikation garantiert Byte-Identität zur bisherigen Ausgabe
        (Regressions-Invariante, AC-7).
        """
        return self.send_multi_location_deviation_alert(
            entities=[(entity_name, points, changes)],
            effective_channels=effective_channels,
            mail_sink=mail_sink,
        )

    def send_multi_location_deviation_alert(
        self,
        entities: list[tuple[str, list, list["WeatherChange"]]],
        effective_channels: set[str],
        mail_sink: Optional[object] = None,
    ) -> NotificationResult:
        """Gebündelter Deviation-Alert-Versand für MEHRERE gleichzeitig
        betroffene Orte EINES Compare-Presets (Issue #1170, Adversary F001).

        Baut über `to_multi_point_alert_message()` EINE `AlertMessage` für
        alle übergebenen Orte (statt eines Einzel-Versands je Ort) und
        delegiert unverändert an `_dispatch_alert_message()` (ADR-0021:
        Rendering/Versand bleiben geteilt).

        `entities`: `list[(location_name, points, changes)]`.
        """
        from output.renderers.alert.project import to_multi_point_alert_message
        from utils.timezone import tz_for_coords

        first_points = entities[0][1]
        alert_tz = tz_for_coords(first_points[0].lat, first_points[0].lon)
        stand_at = local_fmt(datetime.now(timezone.utc), alert_tz)
        groups = [
            (name, changes, points[0] if points else None)
            for name, points, changes in entities
        ]
        alert_msg = to_multi_point_alert_message(groups, tz=alert_tz, stand_at=stand_at)
        target_name = ", ".join(name for name, _points, _changes in entities)
        return self._dispatch_alert_message(
            alert_msg=alert_msg,
            effective_channels=effective_channels,
            mail_type="deviation-alert",
            mail_sink=mail_sink,
            target_name=target_name,
            radar_mode=False,
            alert_tz=alert_tz,
        )

    def send_multi_location_radar_alert(
        self,
        entities: list[tuple[str, "NowcastResult"]],
        effective_channels: set[str],
        *,
        tz: Optional[ZoneInfo] = None,
        stand_at: Optional[str] = None,
        mail_sink: Optional[object] = None,
        cooldown_display: Optional[str] = None,
    ) -> NotificationResult:
        """Gebündelter Onset-Alert-Versand für MEHRERE gleichzeitig auslösende
        Vergleichs-Orte EINES Compare-Presets (Issue #1041 Slice 1a).

        Baut über `to_multi_location_onset_alert_message()` EINE `AlertMessage`
        für alle übergebenen Orte und delegiert unverändert an
        `_dispatch_alert_message()` (ADR-0021: Rendering/Versand bleiben
        geteilt). `entities`: `list[(location_name, NowcastResult)]`.
        `cooldown_display`: optionaler, bereits formatierter Cooldown-Hinweis
        (Pflicht-Fix, analog `send_radar_alert()`s gleichnamigem Parameter).
        """
        from output.renderers.alert.project import to_multi_location_onset_alert_message

        alert_tz = tz or ZoneInfo("UTC")
        resolved_stand_at = stand_at or local_fmt(datetime.now(timezone.utc), alert_tz)
        alert_msg = to_multi_location_onset_alert_message(
            entities, tz=alert_tz, stand_at=resolved_stand_at,
            cooldown_display=cooldown_display,
        )
        target_name = ", ".join(name for name, _nc in entities)
        return self._dispatch_alert_message(
            alert_msg=alert_msg,
            effective_channels=effective_channels,
            mail_type="radar-alert",
            mail_sink=mail_sink,
            target_name=target_name,
            radar_mode=True,
            alert_tz=alert_tz,
        )

    def send_official_alert(
        self,
        trip: "Trip",
        notices: list,
        effective_channels: set[str],
        mail_sink: Optional[object] = None,
        sms_sink: Optional[object] = None,
        telegram_style: str = "rich",
    ) -> NotificationResult:
        """Standalone amtlicher Alert ohne Wetter-Delta (Issue #1088; Format-
        Fidelity zur Design-Vorlage in Issue #1216).

        Baut aus den rohen `(OfficialAlert, segment_ids)`-Paaren die
        kontext-agnostischen `OfficialAlertNotice`-DTOs und rendert Betreff,
        HTML-Body, Telegram- und SMS-Text ueber die vier Vorlagen-Renderer.
        """
        from output.renderers.alert.official_alerts import (
            build_official_alert_notices, render_official_alert_sms,
            render_official_alert_subject, render_official_alert_telegram,
            render_warn_block,
        )
        from utils.timezone import tz_for_coords

        first_wp = next(iter(trip.all_waypoints), None)
        alert_tz = (
            tz_for_coords(first_wp.lat, first_wp.lon)
            if first_wp is not None
            else ZoneInfo("UTC")
        )
        dto_notices = build_official_alert_notices(trip, notices)
        source_label = _official_source_label_for(dto_notices)
        source_url = _official_source_url_for(dto_notices)
        # #1233 Nebenbefund AC-12: Betreff und Body MUESSEN dieselbe tz-aware
        # Quelle nutzen (sonst Wochentags-Divergenz Betreff vs. Body).
        subject = render_official_alert_subject(dto_notices, prefix=trip.name, tz=alert_tz)
        stand_at = local_fmt(datetime.now(timezone.utc), alert_tz)
        # Issue #1216 F002: geteilter Baustein statt Direktaufruf. variant=
        # "standalone" reicht 1:1 an render_official_alert_html durch (byte-
        # identischer Output, Fidelity-Bestandsschutz #952/#957).
        html = render_warn_block(
            dto_notices, variant="standalone", source_label=source_label,
            source_url=source_url, stand_at=stand_at, tz=alert_tz,
            context_label=trip.name,
        )
        telegram_text = render_official_alert_telegram(
            dto_notices, prefix=trip.name, source_label=source_label, tz=alert_tz,
        )

        sent_channels: list[str] = []

        if "email" in effective_channels and self._settings.can_send_email():
            sent_channels.append("email")
            try:
                if mail_sink is not None:
                    mail_sink(subject=subject, body=html)
                else:
                    EmailOutput(self._settings).send(
                        subject=subject, body=html, html=True, mail_type="official-alert",
                    )
            except Exception as e:
                logger.error(f"Official alert email failed for {trip.name}: {e}")

        if "telegram" in effective_channels and self._settings.can_send_telegram():
            sent_channels.append("telegram")
            try:
                # Issue #1260 S3: Kurzstil sendet den SMS-Text (Plaintext,
                # parse_mode=None) statt der reichen Telegram-Warnvorlage.
                if telegram_style == "kurzform":
                    kurz_body = render_official_alert_sms(
                        dto_notices, sms_prefix=trip.name.replace(" ", ""),
                        tz=alert_tz,
                    )
                    TelegramOutput(self._settings).send(
                        subject=subject, body=kurz_body,
                        parse_mode=None, suppress_subject_line=True,
                    )
                else:
                    TelegramOutput(self._settings).send(
                        subject=subject, body=telegram_text,
                        parse_mode="HTML", suppress_subject_line=True,
                    )
            except Exception as e:
                logger.error(f"Official alert telegram failed for {trip.name}: {e}")

        if "sms" in effective_channels and self._settings.can_send_sms():
            sent_channels.append("sms")
            try:
                sms_prefix = trip.name.replace(" ", "")
                sms_text = render_official_alert_sms(
                    dto_notices, sms_prefix=sms_prefix, tz=alert_tz,
                )
                if sms_sink is not None:
                    sms_sink(sms_text)
                else:
                    SMSOutput(self._settings).send(subject="", body=sms_text)
            except Exception as e:
                logger.error(f"Official alert sms failed for {trip.name}: {e}")

        return NotificationResult(sent=bool(sent_channels), sent_channels=sent_channels)

    # TODO(#1207): wird durch den Versand-Orchestrator generalisiert
    def send_compare_report(
        self,
        *,
        subject: str,
        html_body: str,
        text_body: str,
        telegram_text: str,
        sms_text: str,
        recipients: list[str],
        effective_channels: set[str],
        compare_hourly_enabled: bool = True,
        mail_sink: Optional[object] = None,
        sms_sink: Optional[object] = None,
        telegram_sink: Optional[object] = None,
    ) -> NotificationResult:
        """Versendet ein Vergleichs-Briefing ueber die aufgeloesten Kanaele
        (Issue #1270, Scheibe S5).

        Content-Type-spezifische Methode auf der geteilten Klasse — dasselbe
        Muster wie `send_multi_location_official_alert` (Compare-Alarm) neben
        `send_trip_report` (Trip-Briefing). Die Kanal-Aufloesung
        (`effective_channels`) passiert beim Aufrufer analog
        `compare_official_alert._effective_channels` (Opt-in UND `can_send_*()`
        UND `sms_allowed()`); hier wird die globale Sendefaehigkeit als
        Belt-and-Suspenders nochmals geprueft.

        Fail-soft je Kanal (AC-5): Telegram-/SMS-Fehler werden geloggt, reissen
        aber die anderen Kanaele nicht mit. Der E-Mail-Pfad propagiert Fehler
        unveraendert — identisch zum Bestandsverhalten von `send_trip_report`
        (`self._send_email(report)` ohne try/except) und zum bisherigen
        Compare-Versand (`EmailOutput(settings).send(...)` in
        `scheduler_dispatch_service`), damit ein SMTP-Ausfall weiterhin als
        Fehler des Preset-Versands sichtbar bleibt.

        `mail_sink`/`sms_sink`/`telegram_sink`: deterministische Transport-Naht
        (Vorbild `send_multi_location_official_alert`) — kein Netz, kein SMTP.
        """
        sent_channels: list[str] = []

        if "email" in effective_channels:
            if mail_sink is not None:
                mail_sink(subject=subject, body=html_body)
            else:
                # Laufzeit-Aufloesung (kein Modul-Level-Alias): der
                # Compare-Versandpfad wird ueber `output.channels.email`
                # instrumentiert (#1124-Marker-Nachweis).
                from output.channels.email import EmailOutput as _EmailOutput

                _EmailOutput(self._settings).send(
                    subject,
                    html_body,
                    plain_text_body=text_body,
                    to=recipients,
                    compare_hourly_enabled=compare_hourly_enabled,
                    mail_type="compare",  # Issue #1124: X-GZ-Mail-Type
                )
            sent_channels.append("email")

        if "telegram" in effective_channels and self._settings.can_send_telegram():
            try:
                if telegram_sink is not None:
                    telegram_sink(telegram_text)
                else:
                    TelegramOutput(self._settings).send(
                        subject=subject,
                        body=telegram_text,
                        parse_mode=None,
                        suppress_subject_line=True,
                    )
                sent_channels.append("telegram")
            except OutputConfigError:
                raise  # NEU — permanente Fehlkonfiguration darf NICHT im
                       # Fail-Soft-Netz verschwinden (Issue #1288/#1290 Interlock)
            except Exception as e:
                logger.error(f"Compare report telegram failed for {subject!r}: {e}")

        if "sms" in effective_channels and self._settings.can_send_sms():
            try:
                if sms_sink is not None:
                    sms_sink(sms_text)
                else:
                    SMSOutput(self._settings).send(subject="", body=sms_text)
                sent_channels.append("sms")
            except Exception as e:
                logger.error(f"Compare report sms failed for {subject!r}: {e}")

        return NotificationResult(sent=bool(sent_channels), sent_channels=sent_channels)

    def send_multi_location_official_alert(
        self,
        preset_name: str,
        locations: list,
        tagged_alerts: list,
        effective_channels: set[str],
        telegram_style: str = "rich",
        *,
        mail_sink: Optional[object] = None,
        sms_sink: Optional[object] = None,
        telegram_sink: Optional[object] = None,
    ) -> NotificationResult:
        """Gebündelter Standalone-Alarm für amtliche Warnungen im Ortsvergleich
        (Issue #1216 Slice 2a) — Orts-Scope-Pendant zu `send_official_alert()`
        (Trip, Segment-Scope). Nutzt dieselben vier Vorlagen-Renderer, EIN
        Versand je Kanal fuer ALLE betroffenen Orte gebuendelt.

        `locations`: Orts-Objekte (`.id`/`.name`/`.lat`/`.lon`) — die Zeitzone
        der Gueltigkeits-Zeiten (F001) wird vom ersten Ort abgeleitet, analog
        zu `send_official_alert()`.
        `tagged_alerts`: rohe `(OfficialAlert, betroffene_orts_ids)`-Paare
        (bereits vorgefiltert auf neu/eskaliert durch den Aufrufer, IDs statt
        Namen -- F006: gleichnamige Orte duerfen nicht kollabieren; Namen
        werden hier NUR zur Anzeige aufgeloest).
        """
        from output.renderers.alert.official_alerts import (
            build_compare_official_alert_notices, render_official_alert_subject,
            render_warn_block,
        )
        from utils.timezone import tz_for_coords

        all_location_ids = [loc.id for loc in locations]
        id_to_name = {loc.id: loc.name for loc in locations}
        dto_notices = build_compare_official_alert_notices(
            all_location_ids, id_to_name, tagged_alerts,
        )
        if not dto_notices:
            return NotificationResult(sent=False, sent_channels=[])

        first_loc = locations[0] if locations else None
        alert_tz = (
            tz_for_coords(first_loc.lat, first_loc.lon)
            if first_loc is not None and first_loc.lat is not None and first_loc.lon is not None
            else ZoneInfo("UTC")
        )
        source_label = _official_source_label_for(dto_notices)
        source_url = _official_source_url_for(dto_notices)
        # #1233 Nebenbefund AC-12: Betreff und Body MUESSEN dieselbe tz-aware
        # Quelle nutzen (sonst Wochentags-Divergenz Betreff vs. Body).
        subject = render_official_alert_subject(dto_notices, prefix=preset_name, tz=alert_tz)
        stand_at = local_fmt(datetime.now(timezone.utc), alert_tz)
        # Issue #1216 F002: geteilter Baustein (variant="standalone") statt
        # Direktaufruf; Thin-Wrapper -> byte-identischer HTML-Output.
        html = render_warn_block(
            dto_notices, variant="standalone", source_label=source_label,
            source_url=source_url, stand_at=stand_at, tz=alert_tz,
            context_label="Ortsvergleich",
        )

        sent_channels: list[str] = []
        if "email" in effective_channels and self._settings.can_send_email():
            self._dispatch_compare_official_email(preset_name, subject, html, mail_sink)
            sent_channels.append("email")
        if "telegram" in effective_channels and self._settings.can_send_telegram():
            self._dispatch_compare_official_telegram(
                preset_name, subject, dto_notices, source_label, alert_tz, telegram_sink,
                telegram_style=telegram_style,
            )
            sent_channels.append("telegram")
        if "sms" in effective_channels and self._settings.can_send_sms():
            self._dispatch_compare_official_sms(preset_name, dto_notices, alert_tz, sms_sink)
            sent_channels.append("sms")

        return NotificationResult(sent=bool(sent_channels), sent_channels=sent_channels)

    def _dispatch_compare_official_email(
        self, preset_name: str, subject: str, html: str, mail_sink: Optional[object],
    ) -> None:
        try:
            if mail_sink is not None:
                mail_sink(subject=subject, body=html)
            else:
                EmailOutput(self._settings).send(
                    subject=subject, body=html, html=True, mail_type="official-alert",
                )
        except Exception as e:
            logger.error(f"Compare official alert email failed for {preset_name}: {e}")

    def _dispatch_compare_official_telegram(
        self, preset_name: str, subject: str, dto_notices: list, source_label: str,
        alert_tz: ZoneInfo, telegram_sink: Optional[object],
        telegram_style: str = "rich",
    ) -> None:
        from output.renderers.alert.official_alerts import (
            render_official_alert_sms, render_official_alert_telegram,
        )

        try:
            # Issue #1260 S4: Kurzstil sendet den amtlichen SMS-Text (Plaintext,
            # parse_mode=None, keine Inline-Knöpfe) statt der reichen Compare-
            # Warnvorlage. Default "rich" bleibt unverändert.
            if telegram_style == "kurzform":
                kurz_body = render_official_alert_sms(
                    dto_notices, sms_prefix=preset_name.replace(" ", ""), tz=alert_tz,
                )
                if telegram_sink is not None:
                    telegram_sink(kurz_body)
                else:
                    TelegramOutput(self._settings).send(
                        subject=subject, body=kurz_body,
                        parse_mode=None, suppress_subject_line=True,
                    )
                return
            telegram_text = render_official_alert_telegram(
                dto_notices, prefix=preset_name, source_label=source_label, tz=alert_tz,
            )
            if telegram_sink is not None:
                telegram_sink(telegram_text)
            else:
                TelegramOutput(self._settings).send(
                    subject=subject, body=telegram_text,
                    parse_mode="HTML", suppress_subject_line=True,
                )
        except Exception as e:
            logger.error(f"Compare official alert telegram failed for {preset_name}: {e}")

    def _dispatch_compare_official_sms(
        self, preset_name: str, dto_notices: list, alert_tz: ZoneInfo,
        sms_sink: Optional[object],
    ) -> None:
        from output.renderers.alert.official_alerts import render_official_alert_sms

        try:
            sms_prefix = preset_name.replace(" ", "")
            sms_text = render_official_alert_sms(dto_notices, sms_prefix=sms_prefix, tz=alert_tz)
            if sms_sink is not None:
                sms_sink(sms_text)
            else:
                SMSOutput(self._settings).send(subject="", body=sms_text)
        except Exception as e:
            logger.error(f"Compare official alert sms failed for {preset_name}: {e}")

    def send_radar_alert(
        self,
        trip: "Trip",
        *,
        request: RadarAlertRequest,
        source: str,
        cooldown_display: str,
        effective_channels: set[str],
        mail_sink: Optional[object] = None,
    ) -> NotificationResult:
        """Radar-Onset-Alert: rendern und über konfigurierte Kanäle versenden."""
        onset_event = OnsetEvent(
            onset_minutes=request.onset_minutes,
            onset_time=request.onset_time,
            km_from=request.km_from,
            km_to=request.km_to,
            is_convective=request.is_convective,
            intensity_label=request.intensity_label,
            source_label=request.source_label,
            briefing_context=request.briefing_context,
        )
        alert_tz = request.tz or ZoneInfo("UTC")
        alert_msg = AlertMessage(
            trip_short=trip.name,
            stand_at=local_fmt(datetime.now(timezone.utc), alert_tz),
            events=(onset_event,),
            source=source,
            cooldown_display=cooldown_display,
        )
        return self._dispatch_alert_message(
            alert_msg=alert_msg,
            effective_channels=effective_channels,
            mail_type="radar-alert",
            mail_sink=mail_sink,
            target_name=trip.id,
            radar_mode=True,
            alert_tz=alert_tz,
        )

    def _dispatch_alert_message(
        self,
        alert_msg: AlertMessage,
        effective_channels: set[str],
        *,
        mail_type: str = "deviation-alert",
        mail_sink: Optional[object] = None,
        target_name: str = "",
        radar_mode: bool = False,
        official_notices: Optional[list] = None,
        alert_tz: Optional[ZoneInfo] = None,
        telegram_style: str = "rich",
    ) -> NotificationResult:
        """Versendet eine kanonische AlertMessage über die konfigurierten Kanäle.

        Issue #1260 S3: ist `telegram_style="kurzform"`, sendet der Telegram-
        Zweig den bereits gerenderten `sms_body` (Plaintext, `parse_mode=None`,
        keine Inline-Knöpfe) statt der reichen HTML-Bubble. Default `"rich"` —
        Compare-Aufrufer (nicht im Scope) übergeben nichts und bleiben rich;
        keine implizite Kopplung an ein Trip-Feld.

        Issue #1088: liegen `official_notices` vor, wird ein Text-Block an
        html/plain/telegram_body angehängt — SMS bewusst OHNE Zusatz
        (Nicht-Parität, analog Slice-3-AC-6).
        """
        subject = render_alert_subject(alert_msg)
        html, plain = render_alert_email(alert_msg)
        telegram_body = render_alert_telegram(alert_msg)
        sms_body = render_alert_sms(alert_msg)

        if official_notices:
            import html as _html_mod

            from output.renderers.alert.official_alerts import (
                render_official_alert_notice_plain,
            )

            extra_lines = render_official_alert_notice_plain(
                official_notices, tz=alert_tz,
            )
            extra_text = "\n".join(extra_lines)
            plain += "\n\n" + extra_text
            html = html.replace(
                "</body></html>", f"<p>{_html_mod.escape(extra_text)}</p></body></html>",
            )
            telegram_body += "\n\n" + extra_text

        sent_channels: list[str] = []

        def _log_error(channel: str, e: Exception) -> None:
            label = {"email": "Email", "telegram": "Telegram", "sms": "SMS"}[channel]
            if radar_mode:
                logger.error(f"Radar alert {channel} failed for {target_name}: {e}")
            else:
                logger.error(f"{label} alert failed for {target_name}: {e}")

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
                _log_error("email", e)

        # Telegram
        if "telegram" in effective_channels and self._settings.can_send_telegram():
            sent_channels.append("telegram")
            try:
                if telegram_style == "kurzform":
                    TelegramOutput(self._settings).send(
                        subject=subject,
                        body=sms_body,
                        parse_mode=None,
                        suppress_subject_line=True,
                    )
                else:
                    TelegramOutput(self._settings).send(
                        subject=subject,
                        body=telegram_body,
                        parse_mode="HTML",
                        suppress_subject_line=True,
                    )
            except Exception as e:
                _log_error("telegram", e)

        # SMS
        if "sms" in effective_channels and self._settings.can_send_sms():
            sent_channels.append("sms")
            try:
                SMSOutput(self._settings).send(subject=subject, body=sms_body)
            except Exception as e:
                _log_error("sms", e)

        return NotificationResult(sent=bool(sent_channels), sent_channels=sent_channels)

    # ------------------------------------------------------------------
    # Inbound command replies (Issue #1024)
    # ------------------------------------------------------------------

    def send_command_reply_email(
        self, result: CommandResult, settings: Settings,
    ) -> None:
        """Sendet eine Command-Bestätigung per E-Mail."""
        try:
            EmailOutput(settings).send(
                subject=result.confirmation_subject,
                body=result.confirmation_body,
                html=False,
            )
            logger.info(f"Confirmation sent: {result.confirmation_subject}")
        except Exception as e:
            logger.error(f"Failed to send confirmation: {e}")

    def send_command_reply_telegram(
        self,
        result: CommandResult,
        chat_id: str,
        settings: Settings,
    ) -> int | None:
        """Sendet eine Command-Bestätigung als Telegram-Nachricht."""
        try:
            kwargs = {
                "subject": result.confirmation_subject,
                "body": result.confirmation_body,
            }
            if result.reply_markup is not None:
                kwargs["reply_markup"] = result.reply_markup
            return TelegramOutput(settings).send(**kwargs)
        except Exception as e:
            logger.error(f"Telegram command reply failed for {chat_id}: {e}")
            return None

    def send_telegram_message(
        self,
        *,
        chat_id: str,
        subject: str,
        body: str,
        settings: Settings,
        reply_markup: dict | None = None,
    ) -> int | None:
        """Sendet eine einfache Telegram-Nachricht (z.B. Fehlerhinweis)."""
        try:
            kwargs = {"subject": subject, "body": body}
            if reply_markup is not None:
                kwargs["reply_markup"] = reply_markup
            return TelegramOutput(settings).send(**kwargs)
        except Exception as e:
            logger.error(f"Telegram message failed for {chat_id}: {e}")
            return None

    def edit_telegram_message_text(
        self,
        *,
        chat_id: str,
        message_id: int,
        text: str,
        settings: Settings,
        reply_markup: dict | None = None,
    ) -> bool:
        """Editiert eine vorhandene Telegram-Nachricht in-place."""
        from output.channels.telegram import TelegramOutput
        try:
            TelegramOutput(settings).edit_message_text(
                chat_id,
                message_id,
                text,
                reply_markup=reply_markup,
            )
            return True
        except Exception as e:
            logger.error(f"Telegram edit_message_text failed for {chat_id}/{message_id}: {e}")
            return False

    def delete_telegram_message(
        self,
        *,
        chat_id: str,
        message_id: int,
        settings: Settings,
    ) -> bool:
        """Löscht eine Telegram-Nachricht."""
        from output.channels.telegram import TelegramOutput
        try:
            TelegramOutput(settings).delete_message(chat_id, message_id)
            return True
        except Exception as e:
            logger.error(f"Telegram delete_message failed for {chat_id}/{message_id}: {e}")
            return False

    def answer_telegram_callback_query(
        self,
        *,
        callback_query_id: str,
        settings: Settings,
    ) -> bool:
        """Beantwortet eine Telegram Callback Query (Spinner beenden)."""
        from output.channels.telegram import TelegramOutput
        try:
            TelegramOutput(settings).answer_callback_query(callback_query_id)
            return True
        except Exception as e:
            logger.error(f"Telegram answer_callback_query failed for {callback_query_id}: {e}")
            return False

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _apply_prefixes(self, report, request: TripReportRequest) -> None:
        """Test-/On-Demand-/Catchup-/Teilausfall-Präfixe auf Betreff und Body anwenden."""
        stage_name = request.stage_name or "Etappe"
        target_date = self._target_date_from_report(report, request)
        human_date = target_date.strftime("%d.%m.%Y")

        if request.test_prefix:
            hint = f"Test-Vorschau für {stage_name} am {human_date}"
            report.email_subject = f"[TEST] {report.email_subject}"
            self._prepend_hint(report, hint)
        elif request.on_demand_prefix:
            hint = f"Briefing auf Anfrage für {stage_name} am {human_date}"
            self._prepend_hint(report, hint)
        else:
            # Issue #1113: catchup_prefix (Nachlieferung) und
            # partial_outage_hint (Rest-Teilausfall) dürfen gleichzeitig
            # gesetzt sein und verdrängen sich nicht — catchup zuerst.
            hints = [h for h in (request.catchup_prefix, request.partial_outage_hint) if h]
            if hints:
                self._prepend_hint(report, "\n\n".join(hints))

    def _prepend_hint(self, report, hint: str) -> None:
        if report.email_plain:
            # Issue #1208-Folgebefund: Compact-Mails (kein HTML-Teil) sind per
            # Vertrag reines ASCII (7bit) — der Plain-Hinweis wird NUR dann
            # transliteriert, wenn der Report compact ist. Full-Mails (HTML
            # gesetzt) behalten den Umlaut unveraendert.
            plain_hint = hint if report.email_html else _ascii_hint(hint)
            report.email_plain = f"{plain_hint}\n\n{report.email_plain}"
        if report.email_html:
            report.email_html = self._inject_html_hint(report.email_html, hint)
        if report.telegram_bubbles:
            report.telegram_bubbles[0] = f"{hint}\n\n{report.telegram_bubbles[0]}"

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
