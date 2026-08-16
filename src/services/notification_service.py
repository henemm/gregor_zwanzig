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
from types import SimpleNamespace
from typing import TYPE_CHECKING, Optional
from zoneinfo import ZoneInfo

from app.config import Settings
from output.renderers.trip_report import TripReportFormatter
from output.renderers.alert.model import AlertMessage, OnsetEvent
from output.renderers.alert.project import to_alert_message, to_multi_point_alert_message
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
from output.channels.base import OutputConfigError
from output.channels.email import EmailOutput
from output.channels.premium_sms import PremiumSmsOutput
from output.channels.sms import SMSOutput
from output.channels.telegram import TelegramOutput
from services.trip_command_processor import CommandResult
from utils.timezone import local_dt, local_fmt

if TYPE_CHECKING:
    from app.models import (
        DayComparison,
        NormalizedTimeseries,
        OutlookState,
        SegmentWeatherData,
        StabilityResult,
        TripReportConfig,
        UnifiedWeatherDisplayConfig,
        WeatherChange,
    )
    from app.profile import ActivityProfile
    from app.trip import Trip
    from services.radar_service import NowcastResult
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
    # Fix #1486: benennt, WARUM der Ausblick entfaellt (None = Altbestand-
    # Aufrufer, dann bleibt der Block wie bisher kommentarlos weg).
    outlook_state: Optional["OutlookState"] = None
    outlook_horizon_days: Optional[int] = None
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
    # Issue #1676 S2a (ADR-0049): vierter Kanal, unabhaengig von send_sms.
    send_premium_sms: bool = False
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
    # Issue #1439: Starkregen-Kurzfristhinweis (planmaessiger Pfad) — Rohdaten
    # (intensity_label, onset_minutes) vom Scheduler ermittelt (kein Renderer-
    # Import dort, Architektur-Grenze). None = kein Treffer/Guard aktiv.
    # Die Textformatierung passiert hier im NotificationService.
    starkregen_nowcast: tuple[str, int] | None = None


@dataclass
class NotificationResult:
    """Rückgabe eines Versandlaufs."""
    sent: bool
    sent_channels: list[str] = field(default_factory=list)
    telegram_fully_sent: bool = True
    no_channel_configured: bool = False
    error: str | None = None
    # Issue #1459: `sent_channels` bedeutet "Kanal wurde betreten" (Best-Effort,
    # Anti-Pattern #656) -- ein gescheiterter Transport bleibt darin stehen.
    # `failed_channels` haelt zusaetzlich fest, welche davon technisch NICHT
    # angekommen sind, ohne diese bewusste Semantik zu veraendern.
    failed_channels: list[str] = field(default_factory=list)
    # Issue #1676 S2a (Spec D4): Kanal -> Grund, warum NICHTS hinausging.
    # `failed_channels` haelt gescheiterte Transporte fest; hier steht der
    # Fall davor — der Kanal wurde bewusst nicht betreten (z.B. keine oder
    # veraltete gelernte Rueckadresse). Ein Ergebnisfeld statt einer
    # Logzeile, weil eine Logzeile kein Nachweis ist.
    blocked_channels: dict[str, str] = field(default_factory=dict)
    # Issue #1676 S2a (Spec D10), Adversary-Fund F002: derselbe Sperrfall
    # zusaetzlich als maschinenlesbare Kennung (`ChannelBlockedError.
    # reason_code`). Der Prosatext oben ist fuer Menschen; wer Faelle
    # unterscheiden oder buchen will, vergleicht die Kennung. Ein FEHLENDER
    # Eintrag heisst: das war keine bewusste Sperre, sondern ein Transport-
    # oder Programmfehler. Genau diese Unterscheidung ist am Prosatext allein
    # nicht moeglich — ein Absturztext sieht dort aus wie eine Sperrmeldung.
    blocked_reason_codes: dict[str, str] = field(default_factory=dict)

    @property
    def delivered_channels(self) -> list[str]:
        """Kanaele, die den Versand ohne Fehler abgeschlossen haben."""
        return [c for c in self.sent_channels if c not in self.failed_channels]


def _record_block_reason_code(
    codes: dict[str, str], channel: str, exc: BaseException,
) -> None:
    """Traegt die Kennung einer BEWUSSTEN Sperre ein — sonst nichts.

    Issue #1676 S2a (Spec D10). Bewusst per ``getattr``: der umgebende
    ``except`` faengt jede Ausnahme (Kanalunabhaengigkeit, #1662), also auch
    Transport- und Programmfehler. Die tragen keinen ``reason_code`` und
    bekommen hier auch keinen erfunden — ihr Fehlen IST die Aussage
    „das war keine Sperre". Ein Ersatzwert wuerde genau die Unterscheidung
    zerstoeren, um die es geht.
    """
    code = getattr(exc, "reason_code", None)
    if isinstance(code, str) and code.strip():
        codes[channel] = code


@dataclass
class RadarAlertRequest:
    """DTO für Radar-Onset-Alerts vom TripAlertService an den NotificationService.

    Issue #1402: `tz` ist PFLICHTFELD — der einzige Konstrukteur
    (`TripAlertService.check_radar_alerts`) loest ihn immer ueber
    `tz_for_coords()` auf (nie `None`).
    """
    onset_minutes: int
    onset_time: str
    km_from: float
    km_to: float
    is_convective: bool
    intensity_label: str
    source_label: str
    tz: ZoneInfo
    briefing_context: str | None = None
    # Issue #1744 A1: Kennung der betroffenen Etappe ("1".."N"/"Ziel"), additiv
    # und optional. Ohne sie nennt der Nowcast den Ort weiter als km-Spanne
    # (AC-7) — genau das taten bis 2026-08-12 ALLE Nowcast-Mails, waehrend die
    # amtliche Warnung zum selben Ort "🏁 Ziel" sagte.
    segment_id: str | None = None


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
    """Anzeigename(n) der amtlichen Quelle(n) (Issue #1216 AC-7, erweitert um
    #1251): abgeleitet aus ALLEN beteiligten Warnungen statt nur der
    führenden (höchststufigen) — ein Bündel aus zwei Behörden (z.B. GeoSphere
    Austria + Météo-France) nennt beide, statt die zweite Quelle zu verlieren.
    Reihenfolge: höchste Stufe zuerst (Vorbild `_sort_notices`), dedupliziert
    bei mehreren Warnungen derselben Quelle."""
    from output.renderers.alert.official_alerts import official_alert_source_label

    if not dto_notices:
        return "Amtliche Quelle"
    ordered = sorted(dto_notices, key=lambda n: -n.alert.level)
    labels = [official_alert_source_label(n.alert.source) for n in ordered]
    return ", ".join(dict.fromkeys(labels))


def compute_has_gap(
    segments: list["SegmentWeatherData"],
    night_weather: Optional["NormalizedTimeseries"],
    tz: ZoneInfo,
    start_hour: Optional[int] = None,
    end_hour: Optional[int] = None,
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

    _start = DAY_WINDOW_START_HOUR if start_hour is None else start_hour
    _end = DAY_WINDOW_END_HOUR if end_hour is None else end_hour
    rendered = {
        local_hour(dp.ts, tz)
        for dp in build_day_window_points(
            segments, night_weather, tz, start_hour=_start, end_hour=_end,
        )
    }
    expected = set(range(_start, _end + 1))
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
        from output.renderers.day_window import resolve_configured_window
        _rc = request.report_config
        _dw_start, _dw_end = resolve_configured_window(
            getattr(_rc, "day_window_start_hour", None) if _rc else None,
            getattr(_rc, "day_window_end_hour", None) if _rc else None,
        )
        has_gap = compute_has_gap(
            request.segment_weather, request.night_weather, request.trip_tz,
            start_hour=_dw_start, end_hour=_dw_end,
        )

        # Issue #1461 S3b-1: was seit dem letzten Briefing dieses Trips einen
        # Kanal nicht erreicht hat. Echte `user_id` (Mandantentrennung, nie
        # "default") und die Protokoll-Kennung `trip.id`.
        from services.alert_briefing_anchor import undelivered_since_last_briefing

        undelivered = undelivered_since_last_briefing(
            user_id=self._user_id, entity_id=request.trip.id, entity_type="trip",
        )

        # Issue #1439: Starkregen-Kurzfristhinweis — der Scheduler liefert nur
        # Rohdaten (Architektur-Grenze), die Textformatierung (Renderer-Aufruf)
        # passiert hier.
        starkregen_hint_text = None
        if request.starkregen_nowcast is not None:
            from output.renderers.email.starkregen_hint import format_starkregen_hint

            _intensity_label, _onset_minutes = request.starkregen_nowcast
            starkregen_hint_text = format_starkregen_hint(
                _intensity_label, _onset_minutes, tz=request.trip_tz,
            )

        report = self._formatter.format_email(
            segments=request.segment_weather,
            trip_name=request.trip.name,
            trip=request.trip,
            undelivered=undelivered,
            report_type=request.report_type,
            display_config=request.display_config,
            night_weather=request.night_weather,
            thunder_forecast=request.thunder_forecast,
            multi_day_trend=request.multi_day_trend,
            outlook_state=request.outlook_state,
            outlook_horizon_days=request.outlook_horizon_days,
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
            starkregen_hint_text=starkregen_hint_text,
        )

        self._apply_prefixes(report, request)

        no_channel_configured = (
            not request.send_email
            and not request.send_sms
            and not request.send_telegram
            # Issue #1676 S2a: ein Trip, der NUR Premium-SMS bekommt, ist
            # konfiguriert — sonst gaelte der Lauf als "kein Kanal".
            and not request.send_premium_sms
        )

        sent_channels: list[str] = []
        blocked_channels: dict[str, str] = {}
        blocked_reason_codes: dict[str, str] = {}

        # E-Mail — Issue #1662 (Punkt 8): Zustellbilanz statt Kanalreihenfolge.
        # Bisher war E-Mail der einzige Kanal ohne `try`; ein SMTP-/Guard-Fehler
        # verliess die Funktion sofort und riss SMS und Telegram mit, obwohl die
        # funktioniert haetten. Der Fehler wird jetzt festgehalten und erst am
        # Funktionsende ausgewertet (siehe dort) — verschluckt wird er nie.
        email_error: Optional[BaseException] = None
        if request.send_email:
            try:
                self._send_email(report)
                sent_channels.append("email")
            except Exception as e:  # noqa: BLE001 — Zustellbilanz, s. Funktionsende
                email_error = e
                logger.error(f"E-Mail send failed for {request.trip.name}: {e}")

        # SMS
        #
        # Issue #1680 S2 (nur Hinweis, keine Logikaenderung): der Rueckfall
        # `sms_text or email_plain` ist der EINZIGE Weg, auf dem die
        # Gewitter-Herkunft ("… · CAPE", Teil der Kurzzusammenfassung in
        # `email_plain`) doch noch in SMS/Premium-SMS landen koennte — beide
        # Kanaele tragen sie laut PO-Entscheidung ausdruecklich NICHT.
        # `sms_text` wird seit #868 immer erzeugt (`trip_report.py:441`), der
        # Zweig ist also praktisch tot; "praktisch tot" ist aber keine
        # Unmoeglichkeit. Bewacht wird er am erzeugten Text (Spec AC-8:
        # `sms_text` nicht-leer UND ohne jede Zutat-Bezeichnung), nicht durch
        # die Annahme, er sei unerreichbar.
        # Issue #1680 S3 (Nachtrag, weiterhin keine Logikaenderung): seit
        # dieser Scheibe tragen AUCH die Gewitter-Pille des Metriken-
        # Ueberblicks und die GLANCE-Tageszeile eine Herkunft, die in
        # `email_plain` landet -- der Rueckfall unten ist damit derselbe
        # Weg fuer mehr Inhalt, nicht fuer einen neuen.
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

        # Premium-SMS (Garmin inReach, Issue #1676 S2a, ADR-0049).
        # Bewusst OHNE vorgeschaltete `can_send_*`-Bedingung: ob eine gelernte
        # Rueckadresse vorliegt und frisch genug ist, entscheidet der Kanal
        # selbst (Spec D3) und liefert den Grund als Ausnahme zurueck. Eine
        # Bedingung davor wuerde dieselbe Pruefung doppeln und den Grund
        # verschlucken — genau das, was `blocked_channels` verhindert.
        # Zum Rueckfall `sms_text or email_plain` s. den Hinweis beim
        # SMS-Block oben (Issue #1680 S2, Herkunft gehoert hier nicht hin).
        if request.send_premium_sms:
            try:
                PremiumSmsOutput(self._settings).send(
                    subject=report.email_subject,
                    body=report.sms_text or report.email_plain,
                )
                sent_channels.append("premium_sms")
            except Exception as e:  # noqa: BLE001 — Grund wird Ergebnisfeld
                blocked_channels["premium_sms"] = str(e)
                _record_block_reason_code(blocked_reason_codes, "premium_sms", e)
                logger.error(
                    f"Premium-SMS nicht versendet für {request.trip.name}: {e}"
                )

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
                except Exception as e:  # noqa: BLE001 — #1662 AC-9, s. unten
                    logger.error(
                        f"Telegram kurzform send failed for {request.trip.name}: {e}"
                    )
                    telegram_fully_sent = False
            else:
                bubbles = report.telegram_bubbles or [report.email_plain]
                # Issue #1370: KEIN Abbruch der Serie mehr. Ein endgueltig
                # gescheiterter Teil darf die restlichen Teile nicht mehr
                # verschlucken — der Nutzer bekam sonst ein halbes Briefing
                # ohne jede Meldung.
                failed_bubbles = 0
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
                    except Exception as e:  # noqa: BLE001 — #1662 AC-9
                        # Auch eine unerwartete Stoerung (nicht nur OutputError)
                        # zaehlt wie jeder andere Kanalfehler in die
                        # Zustellbilanz, statt den ganzen Lauf abzubrechen.
                        logger.error(
                            f"Telegram bubble {i + 1}/{len(bubbles)} send failed for {request.trip.name}: {e}"
                        )
                        telegram_fully_sent = False
                        failed_bubbles += 1
                if failed_bubbles:
                    self._send_telegram_incomplete_hint(report, failed_bubbles)
                if telegram_fully_sent:
                    # Nur bei vollstaendiger Zustellung — das Briefing-Log darf
                    # nicht behaupten, Telegram sei komplett zugestellt worden.
                    sent_channels.append("telegram")

        # WEATHER-04: Service-E-Mail bei SMS-only + Fehler
        if request.failed_segments:
            self._send_service_error_email(request)

        # Issue #1662 (Punkt 8) — tragende Invariante: nach oben durchgereicht
        # wird ein Versandfehler genau dann, wenn NICHTS zugestellt wurde. Dann
        # greift der Fehlerpfad in `trip_report_scheduler` unveraendert
        # (Diagnose-Zeile, Anker (#1629) und neu der Nachliefer-Vermerk).
        # Hat mindestens ein Kanal zugestellt, waere eine Nachlieferung eine
        # Dopplung des funktionierenden Kanals — der Ausfall bleibt trotzdem
        # sichtbar: ueber die Diagnose-Spur und ueber sein Fehlen in
        # `sent_channels`.
        if email_error is not None:
            if not sent_channels:
                raise email_error
            from services.alert_briefing_anchor import record_briefing_dispatch_failure

            record_briefing_dispatch_failure(
                user_id=self._user_id, kind="route",
                entity_id=request.trip.id, error=email_error,
            )

        return NotificationResult(
            sent=bool(sent_channels),
            sent_channels=sent_channels,
            telegram_fully_sent=telegram_fully_sent,
            no_channel_configured=no_channel_configured,
            blocked_channels=blocked_channels,
            blocked_reason_codes=blocked_reason_codes,
        )

    def _send_telegram_incomplete_hint(self, report, missing_count: int) -> None:
        """Sichtbarer „Briefing unvollstaendig"-Hinweis (Issue #1370).

        fail-soft: scheitert auch dieser Hinweis, wird das nur protokolliert —
        er darf den Versandlauf nie mit einer Ausnahme abbrechen.
        """
        from output.renderers.narrow import render_telegram_incomplete_hint

        try:
            TelegramOutput(self._settings).send(
                subject=report.email_subject,
                body=render_telegram_incomplete_hint(missing_count),
                parse_mode="HTML",
                suppress_subject_line=True,
            )
        except Exception as e:  # noqa: BLE001 — fail-soft, siehe Docstring
            logger.error(f"Telegram incomplete-briefing hint failed: {e}")

    def send_no_data_hint(
        self,
        trip: "Trip",
        report_type: str,
        *,
        send_email: bool = True,
        send_sms: bool = False,
        send_telegram: bool = False,
        send_premium_sms: bool = False,
    ) -> NotificationResult:
        """Kurzer Hinweis bei komplettem Wetterdaten-Ausfall (Issue #1012).

        Issue #1676 S2a: `send_premium_sms` ist hier kein Beiwerk — der
        Scheduler entscheidet den Kanal an derselben Stelle wie fuer das
        Briefing. Ein Flag, das ankommt und nichts tut, waere ein stilles
        Loch: der Nutzer haette den Kanal gewaehlt und nie erfahren, dass er
        die Ausfallmeldung nicht bekommt.
        """
        subject = f"[{trip.name}] Wetterdaten nicht verfügbar"
        text = (
            "Wetterdienst aktuell nicht erreichbar — wir versuchen es weiter "
            "und liefern das Briefing nach, sobald Daten verfügbar sind."
        )
        sent_channels: list[str] = []
        blocked_channels: dict[str, str] = {}
        blocked_reason_codes: dict[str, str] = {}

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

        if send_premium_sms:
            try:
                PremiumSmsOutput(self._settings).send(subject=subject, body=text)
                sent_channels.append("premium_sms")
            except Exception as e:  # noqa: BLE001 — Grund wird Ergebnisfeld
                blocked_channels["premium_sms"] = str(e)
                _record_block_reason_code(blocked_reason_codes, "premium_sms", e)
                logger.error(f"No-data hint Premium-SMS blockiert für {trip.name}: {e}")

        if send_telegram and self._settings.can_send_telegram():
            try:
                TelegramOutput(self._settings).send(subject=subject, body=text)
                sent_channels.append("telegram")
            except Exception as e:
                logger.error(f"No-data hint Telegram failed for {trip.name}: {e}")

        return NotificationResult(
            sent=bool(sent_channels),
            sent_channels=sent_channels,
            blocked_channels=blocked_channels,
            blocked_reason_codes=blocked_reason_codes,
        )

    def send_deviation_alert(
        self,
        trip: "Trip",
        weather: list["SegmentWeatherData"],
        changes: list["WeatherChange"],
        effective_channels: set[str],
        official_notices: Optional[list] = None,
        mail_sink: Optional[object] = None,
        telegram_style: str = "rich",
        corridor_hits: Optional[list] = None,
    ) -> NotificationResult:
        """Wetter-Änderungs-Alert: rendern und über konfigurierte Kanäle versenden.

        Issue #1023: Der AlertService kennt keine Renderer-/Transport-Details mehr.
        Issue #1088: optionale amtliche Warnungen werden in dieselbe Nachricht
        gebündelt (kein zweiter Versand). Issue #1444 S1: `corridor_hits`
        (Schwellen-Treffer) buendeln sich genauso in dieselbe Nachricht.
        """
        from utils.timezone import tz_for_coords

        alert_tz = tz_for_coords(
            weather[0].segment.start_point.lat,
            weather[0].segment.start_point.lon,
        )
        stand_at = local_fmt(datetime.now(timezone.utc), alert_tz)
        alert_msg = to_alert_message(
            changes, weather, trip.name, tz=alert_tz, stand_at=stand_at,
            corridor_hits=corridor_hits,
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
        location_positions: Optional[dict[str, int]] = None,
        telegram_style: str = "rich",
    ) -> NotificationResult:
        """Gebündelter Deviation-Alert-Versand für MEHRERE gleichzeitig
        betroffene Orte EINES Compare-Presets (Issue #1170, Adversary F001).

        Baut über `to_multi_point_alert_message()` EINE `AlertMessage` für
        alle übergebenen Orte (statt eines Einzel-Versands je Ort) und
        delegiert unverändert an `_dispatch_alert_message()` (ADR-0021:
        Rendering/Versand bleiben geteilt).

        `entities`: `list[(location_name, points, changes)]`.

        Issue #1467 S2 AG3b: `location_positions` (Ortsname → 1-basierte
        Position in `preset["location_ids"]`) ist NEU und defaultiert — nur
        der Ortsvergleich-Änderungspfad (`compare_alert.py`) setzt ihn und
        bekommt dadurch die Orts-Zahlenkodierung in der Kurznachricht.

        Issue #1467 S2, Korrektur K-5: `telegram_style` ist ebenfalls NEU und
        defaultiert auf `"rich"` — der Ortsvergleich-Änderungspfad reicht
        damit den Kurzstil-Schalter (#1260) durch, der auf diesem Weg bisher
        wirkungslos war. Aufrufer, die ihn nicht setzen, bleiben rich.
        """
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
        # Issue #1467 S2 AG3a: NUR dieser Aufrufer (Ortsvergleich-
        # Aenderungsalarm) reicht `telegram_groups` durch -- damit faechert
        # `_dispatch_alert_message()` Telegram je Ort auf (PO E2, „eine
        # Sprechblase je Ort"). Die drei anderen Aufrufer (Trip-Delta,
        # Trip-Radar, Compare-Radar) uebergeben den Parameter nicht und
        # bleiben unveraendert bei EINER gebuendelten Telegram-Nachricht.
        return self._dispatch_alert_message(
            alert_msg=alert_msg,
            effective_channels=effective_channels,
            mail_type="deviation-alert",
            mail_sink=mail_sink,
            target_name=target_name,
            radar_mode=False,
            alert_tz=alert_tz,
            telegram_style=telegram_style,
            telegram_groups=groups,
            sms_location_positions=location_positions,
        )

    def send_multi_location_radar_alert(
        self,
        entities: list[tuple[str, object, "NowcastResult"]],
        effective_channels: set[str],
        *,
        tz: Optional[ZoneInfo] = None,
        stand_at: Optional[str] = None,
        mail_sink: Optional[object] = None,
        cooldown_display: Optional[str] = None,
        telegram_style: str = "rich",
    ) -> NotificationResult:
        """Gebündelter Onset-Alert-Versand für MEHRERE gleichzeitig auslösende
        Vergleichs-Orte EINES Compare-Presets (Issue #1041 Slice 1a).

        Baut über `to_multi_location_onset_alert_message()` EINE `AlertMessage`
        für alle übergebenen Orte und delegiert unverändert an
        `_dispatch_alert_message()` (ADR-0021: Rendering/Versand bleiben
        geteilt). `entities`: `list[(location_name, location, NowcastResult)]`
        — das Orts-Objekt (`.lat`/`.lon`) trägt die Zeitzone bei.
        `cooldown_display`: optionaler, bereits formatierter Cooldown-Hinweis
        (Pflicht-Fix, analog `send_radar_alert()`s gleichnamigem Parameter).

        Issue #1383: Die Zeitzone wird — wie in der Schwestermethode
        `send_multi_location_deviation_alert()` — aus dem ersten Ort
        abgeleitet. Der frühere stille `ZoneInfo("UTC")`-Default ließ jeden
        Aufrufer ohne `tz` alle Uhrzeiten in UTC rendern (echte Prod-Mail:
        „Regen in 15 Min ab 20:00" für Orte in Europe/Paris = 2 h daneben).
        `tz` bleibt als expliziter Override erhalten; UTC ist nur noch
        letzter Notnagel bei nicht aufloesbarem Ort (Guard analog
        `send_multi_location_official_alert()`).

        Issue #1402 (entdoppelt): die Herleitung nutzt jetzt den EINEN
        Aufloeser `resolve_location_tz()` (respektiert ein gesetztes
        `SavedLocation.timezone`-Feld VOR den Koordinaten) statt einer
        eigenen `tz_for_coords()`-Direktkopie.
        """
        from output.renderers.alert.project import to_multi_location_onset_alert_message
        from utils.timezone import resolve_location_tz

        # Befund F002 (#1385): der frühere `if entities else None`-Zweig war tot
        # — der einzige Aufrufer schliesst leere Bündel aus, und der Renderer
        # quittiert sie ohnehin mit `ValueError`. Hier derselbe Fehlertyp,
        # nur früher und mit klarer Ursache statt eines IndexError.
        if not entities:
            raise ValueError(
                "send_multi_location_radar_alert benötigt mindestens einen Ort"
            )
        first_loc = entities[0][1]
        alert_tz = tz or resolve_location_tz(first_loc) or ZoneInfo("UTC")
        resolved_stand_at = stand_at or local_fmt(datetime.now(timezone.utc), alert_tz)
        # Issue #1385: Die Orts-Objekte werden MITGEREICHT — der Renderer
        # formatiert die Onset-Zeit je Ort in dessen eigener Zeitzone. Vorher
        # wurde `_loc` hier weggeworfen, wodurch alle Orte die Ortszeit des
        # ERSTEN Ortes trugen (Zermatt + Auckland → beide „ab 23:18").
        alert_msg = to_multi_location_onset_alert_message(
            list(entities), tz=alert_tz, stand_at=resolved_stand_at,
            cooldown_display=cooldown_display,
        )
        target_name = ", ".join(name for name, _loc, _nc in entities)
        return self._dispatch_alert_message(
            alert_msg=alert_msg,
            effective_channels=effective_channels,
            mail_type="radar-alert",
            mail_sink=mail_sink,
            target_name=target_name,
            radar_mode=True,
            alert_tz=alert_tz,
            telegram_style=telegram_style,
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
            build_official_alert_notices, render_official_alert_mail_plain,
            render_official_alert_sms, render_official_alert_subject,
            render_official_alert_telegram, render_warn_block,
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
        # Issue #1744 A2 (AC-13): eigens gebauter Klartext-Teil aus denselben
        # Datenzeilen wie das HTML -- ohne ihn strippt `build_mime_message` die
        # Tags aus dem HTML und der Klartext-Leser bekommt Zeilensalat.
        plain = render_official_alert_mail_plain(
            dto_notices, source_label=source_label, stand_at=stand_at,
            tz=alert_tz, context_label=trip.name,
        )
        telegram_text = render_official_alert_telegram(
            dto_notices, prefix=trip.name, source_label=source_label, tz=alert_tz,
        )

        sent_channels: list[str] = []
        failed_channels: list[str] = []  # Issue #1459: Alarm-Protokoll
        # Issue #1701 (S2b, D5): analog `_dispatch_alert_message`.
        blocked_channels: dict[str, str] = {}
        blocked_reason_codes: dict[str, str] = {}

        if "email" in effective_channels and self._settings.can_send_email():
            sent_channels.append("email")
            try:
                if mail_sink is not None:
                    mail_sink(subject=subject, body=html)
                else:
                    EmailOutput(self._settings).send(
                        subject=subject, body=html, html=True,
                        plain_text_body=plain, mail_type="official-alert",
                    )
            except Exception as e:
                failed_channels.append("email")
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
                failed_channels.append("telegram")
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
                failed_channels.append("sms")
                logger.error(f"Official alert sms failed for {trip.name}: {e}")

        # Premium-SMS (Garmin inReach, Issue #1701 S2b) — bewusst OHNE
        # can_send_*()-Bereitschaftsfrage (D2), Sperrgrund geht nach
        # `blocked_channels`/`blocked_reason_codes` statt `failed_channels`
        # (kein Transportfehler, s. `_dispatch_alert_message`).
        if "premium_sms" in effective_channels:
            sent_channels.append("premium_sms")
            try:
                sms_prefix = trip.name.replace(" ", "")
                premium_text = render_official_alert_sms(
                    dto_notices, sms_prefix=sms_prefix, tz=alert_tz,
                )
                PremiumSmsOutput(self._settings).send(subject="", body=premium_text)
            except Exception as e:  # noqa: BLE001 — Grund wird Ergebnisfeld
                blocked_channels["premium_sms"] = str(e)
                _record_block_reason_code(blocked_reason_codes, "premium_sms", e)
                failed_channels.append("premium_sms")
                logger.error(f"Official alert premium-sms failed for {trip.name}: {e}")

        return NotificationResult(
            sent=bool(sent_channels), sent_channels=sent_channels,
            failed_channels=failed_channels,
            blocked_channels=blocked_channels,
            blocked_reason_codes=blocked_reason_codes,
        )

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
        unveraendert — wie der bisherige Compare-Versand
        (`EmailOutput(settings).send(...)` in `scheduler_dispatch_service`),
        damit ein SMTP-Ausfall weiterhin als Fehler des Preset-Versands
        sichtbar bleibt. `send_trip_report` entscheidet das seit #1662 NICHT
        mehr ueber die Kanalreihenfolge, sondern ueber die Zustellbilanz; der
        Ortsvergleich hat bis heute keinen Nachhol-Mechanismus und bleibt
        deshalb bewusst beim Bestandsverhalten.

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

        Issue #1402 (entdoppelt): `locations` sind `SavedLocation`-Objekte
        (Ortsvergleich) — die Herleitung nutzt jetzt `resolve_location_tz()`
        (respektiert ein gesetztes `.timezone`-Feld VOR den Koordinaten)
        statt einer eigenen `tz_for_coords()`-Direktkopie.
        """
        from output.renderers.alert.official_alerts import (
            build_compare_official_alert_notices, render_official_alert_mail_plain,
            render_official_alert_subject, render_warn_block,
        )
        from utils.timezone import resolve_location_tz

        all_location_ids = [loc.id for loc in locations]
        id_to_name = {loc.id: loc.name for loc in locations}
        dto_notices = build_compare_official_alert_notices(
            all_location_ids, id_to_name, tagged_alerts,
        )
        if not dto_notices:
            return NotificationResult(sent=False, sent_channels=[])

        first_loc = locations[0] if locations else None
        alert_tz = (
            (resolve_location_tz(first_loc) or ZoneInfo("UTC"))
            if first_loc is not None
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
        # Issue #1744 A2 (AC-13): derselbe Mailtyp, derselbe Klartext-Bau wie im
        # Trip-Pfad -- sonst haetten die zwei Flaechen desselben Mailtyps
        # wieder zwei verschiedene Klartexte.
        plain = render_official_alert_mail_plain(
            dto_notices, source_label=source_label, stand_at=stand_at,
            tz=alert_tz, context_label="Ortsvergleich",
        )

        sent_channels: list[str] = []
        failed_channels: list[str] = []  # Issue #1459: Alarm-Protokoll
        # Issue #1701 (S2b, D5): analog `_dispatch_alert_message`.
        blocked_channels: dict[str, str] = {}
        blocked_reason_codes: dict[str, str] = {}
        if "email" in effective_channels and self._settings.can_send_email():
            if not self._dispatch_compare_official_email(
                preset_name, subject, html, mail_sink, plain=plain,
            ):
                failed_channels.append("email")
            sent_channels.append("email")
        if "telegram" in effective_channels and self._settings.can_send_telegram():
            if not self._dispatch_compare_official_telegram(
                preset_name, subject, dto_notices, source_label, alert_tz, telegram_sink,
                telegram_style=telegram_style,
            ):
                failed_channels.append("telegram")
            sent_channels.append("telegram")
        if "sms" in effective_channels and self._settings.can_send_sms():
            if not self._dispatch_compare_official_sms(
                preset_name, dto_notices, alert_tz, sms_sink
            ):
                failed_channels.append("sms")
            sent_channels.append("sms")
        # Premium-SMS (Garmin inReach, Issue #1701 S2b) — bewusst OHNE
        # can_send_*()-Bereitschaftsfrage (D2), Sperrgrund geht nach
        # `blocked_channels`/`blocked_reason_codes` statt `failed_channels`.
        # Append NACH dem Helfer-Aufruf (wie bei email/telegram/sms in dieser
        # Funktion) — der Erfolgsmarker steht erst, nachdem die Tat versucht
        # wurde, nicht davor (Klasse 1c, s. `test_success_status_guard.py`).
        if "premium_sms" in effective_channels:
            if not self._dispatch_compare_official_premium_sms(
                preset_name, dto_notices, alert_tz, blocked_channels, blocked_reason_codes,
            ):
                failed_channels.append("premium_sms")
            sent_channels.append("premium_sms")

        return NotificationResult(
            sent=bool(sent_channels), sent_channels=sent_channels,
            failed_channels=failed_channels,
            blocked_channels=blocked_channels,
            blocked_reason_codes=blocked_reason_codes,
        )

    def _dispatch_compare_official_email(
        self, preset_name: str, subject: str, html: str, mail_sink: Optional[object],
        *, plain: str | None = None,
    ) -> bool:
        """Issue #1459: `True`, wenn der Transport ohne Fehler durchlief."""
        try:
            if mail_sink is not None:
                mail_sink(subject=subject, body=html)
            else:
                EmailOutput(self._settings).send(
                    subject=subject, body=html, html=True,
                    plain_text_body=plain, mail_type="official-alert",
                )
        except Exception as e:
            logger.error(f"Compare official alert email failed for {preset_name}: {e}")
            return False
        return True

    def _dispatch_compare_official_telegram(
        self, preset_name: str, subject: str, dto_notices: list, source_label: str,
        alert_tz: ZoneInfo, telegram_sink: Optional[object],
        telegram_style: str = "rich",
    ) -> bool:
        """Issue #1459: `True`, wenn der Transport ohne Fehler durchlief."""
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
                return True
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
            return False
        return True

    def _dispatch_compare_official_sms(
        self, preset_name: str, dto_notices: list, alert_tz: ZoneInfo,
        sms_sink: Optional[object],
    ) -> bool:
        """Issue #1459: `True`, wenn der Transport ohne Fehler durchlief."""
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
            return False
        return True

    def _dispatch_compare_official_premium_sms(
        self, preset_name: str, dto_notices: list, alert_tz: ZoneInfo,
        blocked_channels: dict[str, str], blocked_reason_codes: dict[str, str],
    ) -> bool:
        """Issue #1701 (S2b, Vorbild `_dispatch_compare_official_sms`):
        `True`, wenn der Transport ohne Fehler durchlief. Eine bewusste
        Sperre (keine/veraltete Rueckadresse) landet zusaetzlich in
        `blocked_channels`/`blocked_reason_codes` (D5) — kein
        Transportfehler."""
        from output.renderers.alert.official_alerts import render_official_alert_sms

        try:
            sms_prefix = preset_name.replace(" ", "")
            premium_text = render_official_alert_sms(
                dto_notices, sms_prefix=sms_prefix, tz=alert_tz,
            )
            PremiumSmsOutput(self._settings).send(subject="", body=premium_text)
        except Exception as e:  # noqa: BLE001 — Grund wird Ergebnisfeld
            blocked_channels["premium_sms"] = str(e)
            _record_block_reason_code(blocked_reason_codes, "premium_sms", e)
            logger.error(f"Compare official alert premium-sms failed for {preset_name}: {e}")
            return False
        return True

    def send_radar_alert(
        self,
        trip: "Trip",
        *,
        request: RadarAlertRequest,
        source: str,
        cooldown_display: str,
        effective_channels: set[str],
        mail_sink: Optional[object] = None,
        telegram_style: str = "rich",
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
            segment_id=request.segment_id,  # Issue #1744 A1
        )
        # Issue #1402: kein stiller Rueckfall mehr -- `request.tz` ist seit
        # `RadarAlertRequest` ein Pflichtfeld.
        alert_tz = request.tz
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
            telegram_style=telegram_style,
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
        alert_tz: ZoneInfo,
        telegram_style: str = "rich",
        telegram_groups: Optional[list[tuple[str, list, object]]] = None,
        sms_location_positions: Optional[dict[str, int]] = None,
    ) -> NotificationResult:
        """Versendet eine kanonische AlertMessage über die konfigurierten Kanäle.

        Issue #1402: `alert_tz` ist PFLICHTPARAMETER — alle vier produktiven
        Aufrufer loesen ihn bereits vorher ueber `tz_for_coords()`/das
        `RadarAlertRequest`-Pflichtfeld auf.

        Issue #1260 S3: ist `telegram_style="kurzform"`, sendet der Telegram-
        Zweig den bereits gerenderten `sms_body` (Plaintext, `parse_mode=None`,
        keine Inline-Knöpfe) statt der reichen HTML-Bubble. Default `"rich"` —
        wer nichts übergibt, bleibt rich; keine implizite Kopplung an ein
        Trip-Feld.

        Issue #1467 S2, Korrektur K-6: der Kurzstil-Zweig steht VOR dem
        `telegram_groups`-Fan-out. Der Ortsvergleich-Änderungsalarm setzt seit
        AG3a immer `telegram_groups`; in der umgekehrten Reihenfolge käme sein
        Kurzstil-Schalter nie zum Zug. Kurzform heißt genau EINE gemeinsame
        Nachricht (PO-Entscheidung 2026-08-04) — die Ortsnummern ergeben nur
        im gemeinsamen Text Sinn.

        Issue #1088: liegen `official_notices` vor, wird ein Text-Block an
        html/plain/telegram_body angehängt — SMS bewusst OHNE Zusatz
        (Nicht-Parität, analog Slice-3-AC-6).

        Issue #1467 S2 AG3a: `telegram_groups` (`list[(location_name,
        changes, point)]`) ist ein NEUER, defaultierter Parameter —
        ausschließlich `send_multi_location_deviation_alert()` setzt ihn.
        Ist er gesetzt, faechert der Telegram-Zweig in EINE Sprechblase je
        Ort auf (PO E2), statt der einen gebuendelten Nachricht. Alle
        anderen Aufrufer (Trip-Δ, Trip-Radar, Compare-Radar) lassen den
        Parameter auf `None` — ihr Verhalten bleibt unveraendert (AC-26).

        Issue #1467 S2 AG3b: `sms_location_positions` ist die gleiche Mechanik
        fuer die Kurznachricht — ebenfalls defaultiert, ebenfalls nur von
        `send_multi_location_deviation_alert()` gesetzt. Ohne ihn bleibt der
        SMS-Text der drei anderen Alarmwege byte-identisch.
        """
        subject = render_alert_subject(alert_msg)
        html, plain = render_alert_email(alert_msg)
        telegram_body = render_alert_telegram(alert_msg)
        sms_body = render_alert_sms(
            alert_msg, location_positions=sms_location_positions,
        )

        if official_notices:
            from output.renderers.alert.official_alerts import (
                build_official_alert_notices, render_official_alert_notice_plain,
                render_warn_block,
            )

            # Befund 4b (#1338 Format, AC-6): der eingebettete amtliche
            # Zusatzblock nutzt den geteilten `render_warn_block(variant=
            # "embedded")` -- dieselbe Bannerform (.wb, Farb-Tokens, Chips,
            # Quelle-Zeile) wie `send_official_alert` -- statt HTML-escaped
            # Plaintext in ein rohes `<p>`. `official_notices` ist hier eine
            # Liste roher `(OfficialAlert, segment_ids)`-Tupel (kein `trip`
            # verfuegbar) -- `build_official_alert_notices(None, ...)` baut
            # daraus die DTOs (ohne Trip faellt die Segment-Gesamtzahl leer
            # aus, "gesamte Route"-Verdichtung entfaellt ersatzlos, s.
            # `_trip_total_segment_ids`-Docstring).
            embed_notices = build_official_alert_notices(None, official_notices)
            embed_source = _official_source_label_for(embed_notices)
            embedded_html = render_warn_block(
                embed_notices, variant="embedded", source_label=embed_source,
                tz=alert_tz,
            )
            html = html.replace(
                "</body></html>", embedded_html + "</body></html>",
            )
            # Plain/Telegram bleiben beim bestehenden Notice-Text (AC-6 betrifft
            # nur das HTML-Format, das aus dem Rahmen brach).
            extra_lines = render_official_alert_notice_plain(
                official_notices, tz=alert_tz,
            )
            extra_text = "\n".join(extra_lines)
            plain += "\n\n" + extra_text
            telegram_body += "\n\n" + extra_text

        sent_channels: list[str] = []
        failed_channels: list[str] = []
        # Issue #1701 (S2b, D5): Kanal -> Grund, warum Premium-SMS NICHT
        # zugestellt wurde (bewusste Sperre, nicht Transportfehler) — an den
        # Aufrufer durchgereicht, der es an `alert_log.append_entry()`
        # weiterreicht (D5).
        blocked_channels: dict[str, str] = {}
        blocked_reason_codes: dict[str, str] = {}
        # Issue #1467 S2 AG3a: bleibt True fuer alle Aufrufer ohne
        # `telegram_groups` (unveraendertes Verhalten). Nur der Fan-out-Zweig
        # unten setzt ihn bei einer Teilzustellung auf False (AC-25c).
        telegram_fully_sent = True

        def _log_error(channel: str, e: Exception) -> None:
            failed_channels.append(channel)  # Issue #1459: Alarm-Protokoll
            # D4-Fund (#1701): harter Dict-Zugriff ohne Rueckfall stuerzte
            # bei einem gescheiterten Premium-SMS-Versand INNERHALB der
            # Fehlerbehandlung selbst ab (KeyError) und riss alle NACH
            # Premium-SMS liegenden Kanaele mit -- aus einem Teilausfall
            # wurde ein Totalausfall. `.get()` mit Fallback haertet die
            # Stelle zusaetzlich gegen jeden kuenftigen fuenften Kanal.
            label = {
                "email": "Email", "telegram": "Telegram", "sms": "SMS",
                "premium_sms": "Premium-SMS",
            }.get(channel, channel)
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
                    # Issue #1467 S2, Korrektur K-6 (PO-Entscheidung
                    # 2026-08-04): der Kurzstil hat VORRANG vor dem Fan-out je
                    # Ort. Der Ortsvergleich-Aenderungsalarm setzt seit AG3a
                    # immer `telegram_groups` — stuende dieser Zweig weiterhin
                    # hinter dem Fan-out, kaeme der Kurzstil auf diesem Weg
                    # nie dran. Es geht EINE gemeinsame Nachricht raus: die
                    # Kurznachricht fuehrt alle Orte als Zahl in EINEM Text,
                    # je Ort aufgeteilt waeren die Ortsnummern sinnlos. Die
                    # beiden anderen Kurzstil-Pfade (Trip-Alarm, amtlicher
                    # Ortsvergleich-Alarm) senden ebenfalls genau eine.
                    TelegramOutput(self._settings).send(
                        subject=subject,
                        body=sms_body,
                        parse_mode=None,
                        suppress_subject_line=True,
                    )
                elif telegram_groups:
                    # Issue #1467 S2 AG3a: EINE Sprechblase je Ort statt
                    # einer gebuendelten Nachricht (PO E2). `to_multi_point_
                    # alert_message()` mit GENAU einer Gruppe liefert
                    # byte-identisch die bereits erprobte Einzel-Ort-Form
                    # (project.py:193-195). Kein Abbruch der Serie bei einem
                    # Teilfehler (#1370-Muster) -- jeder Ort bekommt seinen
                    # eigenen try/except.
                    #
                    # Issue #1467 S2 AG3 Haertung (Adversary F002): der
                    # try/except umschliesst AUCH das Aufbereiten
                    # (`to_multi_point_alert_message()`/`render_alert_
                    # telegram()`), nicht nur `.send()`. Diese Fehlerklasse
                    # -- eine Ausnahme in einer Schleife reisst alle
                    # UEBRIGEN Einheiten mit -- hat in dieser Scheibe bereits
                    # zweimal zugeschlagen (#1467 S2 AG2, F001 und F003: ein
                    # kaputter Ruhezeit-Wert brachte den kompletten
                    # Alarm-Lauf zum Absturz und schaltete alle weiteren
                    # Ortsvergleiche still). Ohne dieses Haertung wuerde ein
                    # Rendering-Fehler bei EINEM Ort die gesamte Serie
                    # abbrechen: 0 statt N-1 Nachrichten kommen an, kein
                    # Hinweis geht raus, und `telegram_fully_sent` bleibt
                    # faelschlich True trotz `failed_channels=['telegram']`.
                    failed_count = 0
                    for group in telegram_groups:
                        try:
                            single_msg = to_multi_point_alert_message(
                                [group], tz=alert_tz, stand_at=alert_msg.stand_at,
                            )
                            single_body = render_alert_telegram(single_msg)
                            TelegramOutput(self._settings).send(
                                subject=subject,
                                body=single_body,
                                parse_mode="HTML",
                                suppress_subject_line=True,
                            )
                        except Exception as e:
                            logger.error(
                                f"Telegram alert (Ort {group[0]!r}) failed "
                                f"for {target_name}: {e}"
                            )
                            telegram_fully_sent = False
                            failed_count += 1
                    if failed_count:
                        failed_channels.append("telegram")
                        # #1370-Muster: Teilzustellung wird gemeldet statt
                        # still verschluckt.
                        self._send_telegram_incomplete_hint(
                            SimpleNamespace(email_subject=subject), failed_count,
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

        # Premium-SMS (Garmin inReach, Issue #1701 S2b) — bewusst OHNE
        # vorgeschaltete can_send_*()-Bereitschaftsfrage (D2): die
        # Sendebereitschaft entscheidet ausschliesslich
        # `PremiumSmsOutput._resolve_recipient()` zur Sendezeit; eine
        # bewusste Sperre (keine/veraltete Rueckadresse) landet in
        # `blocked_channels`/`blocked_reason_codes` statt in
        # `failed_channels` — sie ist kein Transportfehler.
        if "premium_sms" in effective_channels:
            sent_channels.append("premium_sms")
            try:
                PremiumSmsOutput(self._settings).send(subject=subject, body=sms_body)
            except Exception as e:  # noqa: BLE001 — Grund wird Ergebnisfeld
                blocked_channels["premium_sms"] = str(e)
                _record_block_reason_code(blocked_reason_codes, "premium_sms", e)
                _log_error("premium_sms", e)

        return NotificationResult(
            sent=bool(sent_channels), sent_channels=sent_channels,
            failed_channels=failed_channels,
            telegram_fully_sent=telegram_fully_sent,
            blocked_channels=blocked_channels,
            blocked_reason_codes=blocked_reason_codes,
        )

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
        """Versucht, das Zieldatum aus den Segmenten zu ermitteln.

        Issue #1727 S5b (ADR-0044): der Rueckfall (Report ohne verwertbare
        Segmente) folgt der ZONE DER TOUR, die am DTO bereits als
        `request.trip_tz` aufgeloest vorliegt — kein zweiter Aufloeser, kein
        zusaetzlicher Parameter. Vorher stand hier `date.today()`: im
        Mismatch-Fenster las der Nutzer im Mail-/SMS-/Telegram-Praefix ein
        Datum, das einen Tag neben dem Tag lag, fuer den das Briefing gilt.
        """
        if report.segments and report.segments[0].segment:
            return report.segments[0].segment.start_time.date()
        return local_dt(datetime.now(timezone.utc), request.trip_tz).date()

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
