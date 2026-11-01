"""
NotificationService — zentrale Verteilerschicht für Briefings und Hinweise.

Issue #1022: Services liefern DTOs; dieser Service wählt den Renderer und
ruft die Transport-Kanäle (E-Mail, SMS, Telegram) auf. Damit entkoppelt sich
der Scheduler (und später Alert-/Inbound-Pfade) von formatters/output/outputs.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from types import SimpleNamespace
from typing import TYPE_CHECKING, Optional
from zoneinfo import ZoneInfo

from app.config import Settings
from i18n import Lang, resolve_user_lang, t
from i18n.format import fmt_date_numeric
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
from output.channels.base import ChannelBlockedError, OutputConfigError
from output.channels.email import EmailOutput
from output.channels.premium_sms import PremiumSmsOutput
from output.channels.seven_io_base import mask_number
from output.channels.sms import SMSOutput
from output.channels.recipient import PremiumSmsRecipient, SmsRecipient, TelegramRecipient
from output.channels.telegram import TelegramOutput
from services import sms_daily_limit
from services.trip_command_processor import CommandResult
from services.trip_day import trip_local_today
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

#: Issue #2422 S4 (Fix #1088): kurzer SMS-Hinweistext, wenn eine gebündelte
#: Abweichungs-/Radar-Alarm-Mail einen eingebetteten amtlichen Zusatzblock
#: trägt — die SMS bekommt statt des kompletten Zusatzblocks nur diesen
#: knappen Hinweis (Zeichen-Budget SMS). Vertrag geteilt mit
#: `tests/tdd/test_alarm_sms_paritaet_amtlicher_zusatz.py::_AMTL_HINWEIS_TOKEN`.
_AMTL_HINWEIS_SMS_TOKEN = "+ amtl. Warnung s. E-Mail/Telegram"
_AMTL_HINWEIS_SMS_SUFFIX = " " + _AMTL_HINWEIS_SMS_TOKEN


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
    # Issue #2051 S1: die Datenform traegt zusaetzlich Ende und R4-Waechter
    # (`event_end_minutes`, `event_ongoing_beyond_horizon`) — das alte
    # Zwei-Tupel konnte das Ende gar nicht transportieren.
    # Issue #2050 S2b: fuenftes Glied `already_running`, und `onset_minutes`
    # wird optional — ein laufendes Ereignis, das in der laufenden
    # Viertelstunde endet, hat keinen kuenftigen Beginn.
    # Issue #2051 S3: sechstes Glied `source_reach_minutes` -- additiv, wie
    # die vorherigen Erweiterungen dieses Tupels. Ohne es kaeme die
    # Reichweite an DIESEM Pfad (dem einzigen ohne Vorlauf-Deckel, aus dem
    # der Ticket-Realfall stammt) nie beim Formatierer an.
    starkregen_nowcast: (
        tuple[str, int | None, int | None, bool, bool, int | None] | None
    ) = None


@dataclass
class NotificationResult:
    """Rückgabe eines Versandlaufs."""
    sent: bool
    sent_channels: list[str] = field(default_factory=list)
    telegram_fully_sent: bool = True
    no_channel_configured: bool = False
    error: str | None = None
    # Issue #1405 S1 (ADR-0086, loest #684 AC-3 ab): `sent_channels` heisst
    # in allen Pfaden "zugestellt"; "betreten" steht in `attempted_channels`.
    # `failed_channels` haelt fest, welche Kanaele technisch scheiterten.
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
    # Issue #1405 S1 (ADR-0086): Kanaele, die BETRETEN wurden (Gate bestanden,
    # Versand versucht) -- unabhaengig vom Ausgang. Speist im Alarmpfad
    # `reachable_channels` (Cockpit-Zahl, #1459 AC-11); `sent_channels`
    # heisst seither in allen Pfaden "zugestellt".
    attempted_channels: list[str] = field(default_factory=list)
    # Issue #1441 S2: Kanaele, deren Nachricht die Entwarnung TATSAECHLICH
    # enthielt (SMS-Kuerzung kann sie verdraengen, AC-12).
    allclear_channels: list[str] = field(default_factory=list)
    # Issue #1405 S4b (B21): gescheiterte Begleit-Hinweise bei ZUGESTELLTEM
    # Versand ("telegram_incomplete_hint", "service_error_email"). Bewusst
    # getrennt von `failed_channels` (ADR-0086: Backoff/Throttle/
    # `delivery_outcome` bleiben unberuehrt); die Laeufe zaehlen es als
    # `notice_failed` und melden status "partial".
    notice_failures: list[str] = field(default_factory=list)

    @property
    def delivered_channels(self) -> list[str]:
        """Kanaele, die den Versand ohne Fehler abgeschlossen haben."""
        return [c for c in self.sent_channels if c not in self.failed_channels]

    @property
    def delivery_outcome(self) -> str:
        """Issue #1405 S1 (ADR-0086): abgeleiteter Ausgang, nie gesetzt.

        Sperre = Key in `blocked_reason_codes`; Transportfehler = Key in
        `failed_channels` OHNE Sperr-Code (Premium-SMS-Transportfehler steht
        zusaetzlich in `blocked_channels`, aber ohne Code)."""
        if self.delivered_channels:
            return "delivered"
        if any(c not in self.blocked_reason_codes for c in self.failed_channels):
            return "transport_failed"
        if self.blocked_reason_codes:
            return "blocked_only"
        return "no_channel"


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
    # Issue #2050 S2b: `None`, wenn das Ereignis bereits laeuft und in der
    # laufenden Viertelstunde endet -- dann ist kein kuenftiger Beginn
    # bestimmbar (`already_running` traegt die Aussage).
    onset_minutes: int | None
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
    # Issue #2009: Tagesbezug des Onset-Zeitpunkts (0 = heute, 1 = morgen).
    # `onset_time` ist reines "HH:MM" — seit der Schwelle 55 rutscht der
    # Zeitpunkt regelmaessig ueber Mitternacht und waere ohne den Offset
    # mehrdeutig. Berechnet wird er dort, wo `onset_time` entsteht
    # (`trip_alert.check_radar_alerts`), damit beide dieselbe Zone benutzen.
    onset_day_offset: int = 0
    # Issue #2054: Wochentagskuerzel des Onset-Zeitpunkts -- reiner
    # Passthrough bis in den Renderer, gebildet dort, wo auch der Versatz
    # entsteht (`trip_alert.check_radar_alerts`), damit beide dieselbe Zone
    # benutzen. `None` bei Versatz 0; ohne das Feld bliebe der Tagesbezug in
    # der Kurzform ohne Darstellung.
    onset_weekday: str | None = None
    # Issue #2018: additiv, optional (Muster `briefing_context`). Traegt die
    # ausformulierte Bezugszeile, wenn das Ereignis-Identitaets-Gate diese
    # Meldung als NACHTRAG zu einer bereits zugestellten amtlichen Warnung
    # eingestuft hat. `send_radar_alert()` reicht sie unveraendert auf die
    # `AlertMessage` durch; ohne sie bleibt der Versand byte-identisch.
    addendum_reference: str | None = None
    # Issue #2046: additiv, optional. Erwartete Niederschlagsmenge (mm) der
    # Stunde AB DEM BEGINN (`NowcastResult.onset_precip_mm`) -- die Zahl, die
    # die Onset-Kurznachricht nennt. Ohne sie bleibt der Versand
    # byte-identisch (zahlenlose Alt-Form).
    onset_precip_mm: float | None = None
    # Issue #2051 S1: additiv, optional (Muster `onset_precip_mm` o.). Ende
    # desselben Ereignisses als reines "HH:MM" und sein EIGENER Tagesbezug --
    # gebildet dort, wo auch `onset_time`/`onset_day_offset` entstehen
    # (`trip_alert.check_radar_alerts`), damit beide dieselbe Zone benutzen.
    # `None` heisst "kein Ende ableitbar"; ohne die Felder bleibt der Versand
    # byte-identisch.
    event_end_time: str | None = None
    event_end_day_offset: int = 0
    # Issue #2054: Wochentagskuerzel des ENDE-Zeitpunkts (Muster
    # `onset_weekday` o.) -- eigenstaendig, weil Beginn und Ende an
    # verschiedenen Kalendertagen liegen koennen.
    event_end_weekday: str | None = None
    # Issue #2051 S1 (Spec v1.1): der R4-Waechter reist MIT der Uhrzeit bis in
    # den Renderer, weil er dort ueber die Textform entscheidet (Untergrenze
    # vs. bekanntes Ende, AC-20). Ohne ihn kaeme im Waechterfall die
    # Normalform an und behauptete ein Ende, das die Daten nicht hergeben.
    event_ongoing_beyond_horizon: bool = False
    # Issue #2050 S2b: das Ereignis laeuft zum Meldezeitpunkt bereits. Additiv,
    # Default aus. Reist bis in den Renderer, weil dort die BEGINN-Angabe
    # durch den Zustand ersetzt wird; das Ende kommt weiter aus den
    # `event_end_*`-Feldern.
    already_running: bool = False
    # Issue #2051 S3: additiv, optional (Muster `event_end_time`/
    # `event_end_day_offset` o.). Reichweite der Quelle als reines "HH:MM",
    # gebildet in `trip_alert.check_radar_alerts` ueber die geteilte
    # Fassung `project.source_reach_display` -- derselbe Baustein, den auch
    # der Ortsvergleich-Pfad benutzt (ADR-0021). `None` heisst "keine
    # Reichweite bekannt ODER durch E5 unterdrueckt".
    source_reach_time: str | None = None
    source_reach_day_offset: int = 0
    # Issue #2051 S3: additiv, optional. Grenzzeit der Ortsschaerfe, gebildet
    # ueber `project.location_sharpness_display`. `None` heisst "weder
    # Beginn noch Ende liegen jenseits der Grenze".
    location_sharpness_limit_time: str | None = None
    location_sharpness_limit_day_offset: int = 0
    # Issue #2036/#2051 S2a: stammen `km_from`/`km_to` aus echter GPX-
    # Wegstrecke (`TripSegment.distance_measured`)? Der Trip-Onset-Pfad hat
    # das Flag bis S2a NIE gesetzt -- ohne es bliebe die Ausdehnung auf JEDER
    # Etappe stumm, auch auf den vermessenen.
    km_measured: bool = False
    # Issue #2051 S2a: die Nass-Zonen der Reststrecke, gebildet aus der
    # Mehrpunkt-Abfrage (`rain_extent.derive_rain_zones`). Additiv, Default
    # leer -> ohne sie bleibt der Versand byte-identisch.
    rain_zones: tuple = ()
    # Issue #2050 S4b-2: hat die Gewitterpruefung stattgefunden
    # (`NowcastResult.convective_checked`)? Reist bis in den Renderer, weil
    # dort der Text entsteht, der "geprueft, kein Gewitter" von "nicht
    # geprueft" unterscheidet. Default `True` -- ein `False`-Default
    # beschriftete jede Bestandslage faelschlich als ungeprueft.
    convective_checked: bool = True
    # Issue #2050 S4b-2: km-Lage der ausgefallenen Messpunkte der
    # Ausdehnungs-Messung (`_messluecken_felder`, dieselbe Buchfuehrung wie im
    # Alarmprotokoll seit S4b). Additiv, Default leer -> ohne sie bleibt der
    # Versand byte-identisch.
    gap_km: tuple = ()
    # Issue #2122: additiv, optional. Das Datum, dem das gemeldete Segment
    # ENTSTAMMT (`_resolve_alert_segment()` in `trip_alert.py`) -- NICHT
    # zwingend `today` (Nachtsegment kann der Vortag sein, AC-6). Der
    # Trip-Radar-Pfad setzt es immer; der Ortsvergleich-Radar-Pfad baut kein
    # `RadarAlertRequest` und laesst es damit implizit `None`.
    segment_date: date | None = None


def abschnitt_id(segment_data, lang: Lang) -> str:
    """Kennung eines Abschnitts in Nutzertexten (Teilausfall-Hinweis,
    Service-Fehler-Mail); das Ziel-Segment (``"Ziel"``) heisst in ``lang`` wie
    im Alarm (Issue #2672)."""
    seg_id = str(segment_data.segment.segment_id)
    return t("alarm.segment.ziel", lang) if seg_id == "Ziel" else seg_id


def build_service_error_email_html(
    trip_name: str, report_type: str, error_lines: str, *, lang: Lang = "de",
) -> str:
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
        f'<h2 class="heading">{t("versand.servicefehler.titel", lang)}</h2>'
        '<div class="meta">'
        f'<strong>Trip:</strong> {trip_name}<br>'
        f'<strong>Report:</strong> {report_type.title()}<br>'
        f'<strong>Problem:</strong> {t("versand.servicefehler.problem", lang)}'
        '</div>'
        f'<p><strong>{t("versand.servicefehler.segmente", lang)}</strong></p>'
        f'<div class="error-block">{error_lines}</div>'
        '<p style="font-size:13px; color:#5c5a52;">'
        f'{t("versand.servicefehler.grund", lang)}'
        '</p>'
        '</div>'
        f'<div class="footer" style="background:{G_INK}; color:#ffffff;">'
        f'Gregor Zwanzig &mdash; {t("versand.servicefehler.fusszeile", lang)}'
        '</div>'
        '</body>'
        '</html>'
    )


def _official_source_label_for(dto_notices: list, *, lang: Lang = "de") -> str:
    """Anzeigename(n) der amtlichen Quelle(n) (Issue #1216 AC-7, erweitert um
    #1251): abgeleitet aus ALLEN beteiligten Warnungen statt nur der
    führenden (höchststufigen) — ein Bündel aus zwei Behörden (z.B. GeoSphere
    Austria + Météo-France) nennt beide, statt die zweite Quelle zu verlieren.
    Reihenfolge: höchste Stufe zuerst (Vorbild `_sort_notices`), dedupliziert
    bei mehreren Warnungen derselben Quelle."""
    from output.renderers.alert.official_alerts import official_alert_source_label

    if not dto_notices:
        return t("warnung.quelle.amtlich", lang)
    ordered = sorted(dto_notices, key=lambda n: -n.alert.level)
    labels = [official_alert_source_label(n.alert.source, lang=lang) for n in ordered]
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


def _stage_number_for_date(trip: "Trip", d: "date | None") -> int | None:
    """Issue #2122: 1-basierte chronologische Etappen-Position DIESES Datums
    -- dieselbe Zahl, die `Trip.numbered_stage_label()` im Briefing zeigt
    (Position in `sorted(trip.stages, key=lambda s: s.date)`, aufgeloest ueber
    `Trip.get_stage_for_date()`). `None` ohne auflösbares Datum/Etappe (AC-8/
    AC-9) -- der Renderer laesst das Praefix dann ersatzlos weg."""
    if d is None:
        return None
    stage = trip.get_stage_for_date(d)
    if stage is None:
        return None
    ordered = sorted(trip.stages, key=lambda s: s.date)
    try:
        return ordered.index(stage) + 1
    except ValueError:
        return None


def _measured_event_km(alert_msg) -> dict:
    """Gemessene km-Spanne je Segment-Kennung aus den bereits projizierten
    Alarm-Ereignissen (Issue #2036). Quelle fuer den EINGEBETTETEN amtlichen
    Warnblock, damit beide Haelften derselben Mail dieselbe Ortssprache
    sprechen (#1744 AC-6). Ungemessene Ereignisse liefern keinen Eintrag --
    die Warnung bleibt dort bei "Segment N"."""
    result: dict = {}
    for e in list(alert_msg.events) + list(alert_msg.onset_shift_events):
        if not getattr(e, "km_measured", False):
            continue
        seg = getattr(e, "segment_id", None)
        if seg:
            result[str(seg)] = (e.km_from, e.km_to)
    return result


def _official_allclear_source_label(dto_notices: list, ac_notices: list, *,
                                    lang: Lang = "de") -> str:
    """Issue #1441 S2: Quelle einer reinen Entwarnung aus dem Gedaechtnis."""
    from output.renderers.alert.official_alerts import official_alert_source_label

    if dto_notices or not ac_notices:
        return _official_source_label_for(dto_notices, lang=lang)
    return ", ".join(dict.fromkeys(
        official_alert_source_label(n.source, lang=lang) for n in ac_notices))


def _official_subject(dto_notices: list, ac_notices: list, *, prefix: str, tz,
                      lang: Lang = "de") -> str:
    """Issue #1441 S2: Warnung zuerst, dann "+ Entwarnung …"."""
    from output.renderers.alert.official_alerts import (
        render_official_alert_subject, render_official_allclear_subject_part,
    )

    if not ac_notices:
        return render_official_alert_subject(dto_notices, prefix=prefix, tz=tz, lang=lang)
    part = render_official_allclear_subject_part(ac_notices, lang=lang)
    if dto_notices:
        warnung = render_official_alert_subject(dto_notices, prefix=prefix, tz=tz, lang=lang)
        return f"{warnung} + {part}"
    scopes = {n.scope_label for n in ac_notices}
    scope = next(iter(scopes)) if len(scopes) == 1 else t("warnung.umfang.mehrere_orte", lang)
    return f"[{prefix}] {scope} · {part}"


def _official_mail_bodies(
    dto_notices: list, ac_notices: list, *, source_label: str, source_url, stand_at: str,
    tz, context_label: str, lang: Lang = "de",
) -> tuple[str, str]:
    """Issue #1441 S2: (HTML, Klartext) -- Entwarnungs-Abschnitt nach den Warnungen."""
    from output.renderers.alert import official_alerts as oa

    if not dto_notices:
        kw = dict(stand_at=stand_at, source_label=source_label, context_label=context_label,
                  lang=lang)
        return (oa.render_official_allclear_mail_html(ac_notices, **kw),
                oa.render_official_allclear_mail_plain(ac_notices, **kw))
    html = oa.render_warn_block(
        dto_notices, variant="standalone", source_label=source_label,
        source_url=source_url, stand_at=stand_at, tz=tz, context_label=context_label,
        allclear_html=oa.render_official_allclear_html(ac_notices, lang=lang), lang=lang,
    )
    plain = oa.render_official_alert_mail_plain(
        dto_notices, source_label=source_label, stand_at=stand_at,
        tz=tz, context_label=context_label, source_url=source_url,
        allclear_lines=oa.render_official_allclear_plain(ac_notices, lang=lang), lang=lang,
    )
    return html, plain


def _official_telegram_rich(dto_notices: list, ac_notices: list, *, prefix: str,
                            source_label: str, tz, lang: Lang = "de") -> str:
    from output.renderers.alert.official_alerts import (
        render_official_alert_telegram, render_official_allclear_telegram,
    )

    if not dto_notices:
        return render_official_allclear_telegram(ac_notices, prefix=prefix, lang=lang)
    text = render_official_alert_telegram(
        dto_notices, prefix=prefix, source_label=source_label, tz=tz, lang=lang)
    if not ac_notices:
        return text
    return f"{text}\n\n{render_official_allclear_telegram(ac_notices, lang=lang)}"


def _compare_allclear_channels(ac_notices: list, dto_notices: list, telegram_style: str,
                               alert_tz) -> list[str]:
    """Issue #1441 S2: Kanaele, deren Ortsvergleich-Nachricht die Entwarnung traegt."""
    from output.renderers.alert.official_alerts import render_official_alert_sms_with_allclears

    if not ac_notices:
        return []
    _text, in_sms = render_official_alert_sms_with_allclears(dto_notices, ac_notices, tz=alert_tz)
    channels = ["email"]
    if telegram_style != "kurzform" or in_sms:
        channels.append("telegram")
    return channels + (["sms", "premium_sms"] if in_sms else [])


def _official_source_url_for(dto_notices: list) -> str | None:
    """Quelle-Link der führenden (höchststufigen) Warnung (Issue #1216 F002).
    Issue #1441 (CC BY 4.0): auch die eigenstaendige Warn-Mail zeigt ihn
    (HTML-Fusszeile + Klartext)."""
    if not dto_notices:
        return None
    leading = max(dto_notices, key=lambda n: n.alert.level)
    return getattr(leading.alert, "url", None)


def _alert_format_modes(display_config) -> dict[str, dict[str, str]]:
    """Issue #1737: Kanal -> {col_key: Anzeigemodus} aus der Anzeige-
    Konfiguration DES jeweiligen Trips bzw. Vergleichs (Kanal-Kaskade
    `get_metrics_for_channel`, ADR-0050) -- dieselbe Aufloesung wie das
    Briefing. Ohne Konfiguration leer (= ROH). Nie aus einem anderen Nutzer."""
    if display_config is None:
        return {}
    from app.metric_catalog import get_metric
    from output.renderers.email.helpers import _effective_format_mode

    out: dict[str, dict[str, str]] = {}
    unknown: list[str] = []
    for channel in ("email", "telegram"):
        modes: dict[str, str] = {}
        for report_type in ("morning", "evening"):
            for mc in display_config.get_metrics_for_channel(channel, report_type):
                try:
                    col = get_metric(mc.metric_id).col_key
                except KeyError:
                    unknown.append(mc.metric_id)
                    continue
                modes.setdefault(col, _effective_format_mode(mc))
        out[channel] = modes
    if unknown:
        logger.warning(
            "_alert_format_modes: Metriken %s ohne Katalog-Eintrag -- ihre "
            "Stundenzeilen erscheinen ROH statt im Anzeigemodus (vgl. #1737)",
            sorted(set(unknown)),
        )
    return out


def _alert_indicator_keys(display_config) -> dict[str, frozenset[str]]:
    """Issue #1737: Kanal -> col_keys mit Ampel-Punkt im HTML -- wie
    `build_html_indicator_keys` des Briefings, aber ueber die Kanal-Kaskade
    DES jeweiligen Trips ("Einfach" ist dort `use_friendly_format`)."""
    if display_config is None:
        return {}
    from app.metric_catalog import get_metric
    from output.renderers.email.helpers import _AMPEL_CAPABLE_METRIC_IDS

    out: dict[str, frozenset[str]] = {}
    for channel in ("email", "telegram"):
        keys: set[str] = set()
        for report_type in ("morning", "evening"):
            for mc in display_config.get_metrics_for_channel(channel, report_type):
                if mc.metric_id in _AMPEL_CAPABLE_METRIC_IDS and getattr(
                    mc, "use_friendly_format", True,
                ):
                    keys.add(get_metric(mc.metric_id).col_key)
        out[channel] = frozenset(keys)
    return out


class NotificationService:
    """Wählt Renderer und Transporte für Trip-Briefings und Service-Hinweise."""

    def __init__(
        self, settings: Optional[Settings] = None, user_id: Optional[str] = None,
        *, lang: Optional[Lang] = None,
    ) -> None:
        # #2151 Scheibe C (ADR-0003): kein stiller Rueckfall auf das Konto
        # "default". Ohne settings UND ohne user_id gibt es kein Profil, das
        # geladen werden duerfte; mit settings allein ist der Dienst fuer die
        # Versandwege nutzbar, jede Operation mit Nutzerbezug scheitert aber
        # in _require_user() (Vorbild Go `requireUser`, Scheibe B).
        if settings is None and not user_id:
            raise ValueError(
                "NotificationService: weder settings noch user_id angegeben (#2151)"
            )
        self._settings = settings if settings else Settings().with_user_profile(user_id)
        self._formatter = TripReportFormatter()
        self._user_id = user_id
        # Issue #2671 (ADR-0104): Sprache am Dienstobjekt, einmal je Nutzer
        # gelesen (nie Modul-/Klassenzustand); P9b reicht sie direkt herein.
        self._lang: Lang = lang or (resolve_user_lang(user_id) if user_id else "de")

    def _require_user(self) -> str:
        """Nutzerkennung fuer nutzerbezogene Datenzugriffe -- fail-closed."""
        if not self._user_id:
            raise ValueError(
                "NotificationService: Operation braucht user_id, der Dienst "
                "wurde ohne Nutzerkennung konstruiert (#2151)"
            )
        return self._user_id

    def _telegram_output(self) -> TelegramOutput:
        """Issue #1412 S4a: Telegram-Ausgang an den Profil-Chat des Nutzers
        (frisch aus ``user.json``), nie an ``settings.telegram_chat_id``."""
        recipient = TelegramRecipient.for_user(self._require_user(), self._settings)
        return TelegramOutput(self._settings, recipient=recipient)

    @staticmethod
    def _telegram_reply(settings: Settings, chat_id) -> TelegramOutput:
        """Issue #1412 S4a (R7): Antwort geht an die uebergebene ``chat_id``
        -- nur zulaessig als Absender des laufenden Webhook-Updates."""
        return TelegramOutput(settings, recipient=TelegramRecipient.inbound_reply(chat_id))

    def _sms_output(self) -> SMSOutput:
        """Issue #1412 S4b: SMS an die bestaetigte Profilnummer (frisch aus
        ``user.json``), nie an ``settings.sms_to``. Aufruf IM ``try`` nach der
        Tageslimit-Reservierung -- ein Block gibt sie dort wieder frei."""
        recipient = SmsRecipient.for_user(self._require_user(), self._settings)
        return SMSOutput(self._settings, recipient=recipient)

    def _premium_sms_output(self, settings: Optional[Settings] = None) -> PremiumSmsOutput:
        """Issue #1412 S4b: Premium-SMS an die gelernte Rueckadresse aus
        ``user.json`` (auch fuer Befehlsantworten), nie aus den Settings."""
        settings = settings if settings is not None else self._settings
        recipient = PremiumSmsRecipient.for_user(self._require_user(), settings)
        return PremiumSmsOutput(settings, recipient=recipient)

    def _sms_gate_reserve(
        self, kind: str, purpose: str, now: datetime,
        blocked_channels: dict[str, str], blocked_reason_codes: dict[str, str],
    ) -> bool:
        """Issue #2412 S4a: Tageslimit-Gate vor jedem SMS-/Premium-SMS-Versand.

        Duenner Wrapper -- die 12 Sendestellen bleiben unkonsolidiert (Spec),
        nur die Gate-Pruefung selbst ist geteilt. `True` = reserviert, der
        Aufrufer darf senden. `False` = Sperre, `blocked_channels`/
        `blocked_reason_codes` wurden befuellt -- kein Versand, kein
        `sent_channels.append`.
        """
        try:
            sms_daily_limit.check_and_reserve(self._require_user(), kind, purpose, now)
        except ChannelBlockedError as e:
            blocked_channels[kind] = str(e)
            _record_block_reason_code(blocked_reason_codes, kind, e)
            return False
        return True

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
            user_id=self._require_user(), entity_id=request.trip.id, entity_type="trip",
        )

        # Issue #1439: Starkregen-Kurzfristhinweis — der Scheduler liefert nur
        # Rohdaten (Architektur-Grenze), die Textformatierung (Renderer-Aufruf)
        # passiert hier.
        starkregen_hint_text = None
        if request.starkregen_nowcast is not None:
            from output.renderers.email.starkregen_hint import format_starkregen_hint

            (
                _intensity_label, _onset_minutes,
                _event_end_minutes, _event_ongoing, _already_running,
                _source_reach_minutes,
            ) = request.starkregen_nowcast
            starkregen_hint_text = format_starkregen_hint(
                _intensity_label, _onset_minutes, tz=request.trip_tz,
                # Issue #2051 S1: Ende und Waechter aus DEMSELBEN
                # Nowcast-Ergebnis, das schon Label und Beginn liefert.
                event_end_minutes=_event_end_minutes,
                event_ongoing_beyond_horizon=_event_ongoing,
                # Issue #2050 S2b: der Laufend-Zustand ebenfalls aus demselben
                # Ergebnis -- er entscheidet ueber die BEGINN-Angabe der Zeile.
                already_running=_already_running,
                # Issue #2051 S3: die Reichweite ebenfalls aus demselben
                # Ergebnis -- Adversary-Fund F002, der Pfad ohne Vorlauf-
                # Deckel liess sie sonst nie beim Formatierer ankommen.
                source_reach_minutes=_source_reach_minutes,
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
            lang=self._lang,
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
        # Issue #1405 S4b (B21): gescheiterte Begleit-Hinweise, getrennt von
        # der Zustellbilanz (ADR-0086).
        notice_failures: list[str] = []

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
            now_sms = datetime.now(timezone.utc)
            if self._sms_gate_reserve(
                "sms", "briefing", now_sms, blocked_channels, blocked_reason_codes,
            ):
                try:
                    self._sms_output().send(
                        subject=report.email_subject,
                        body=report.sms_text or report.email_plain,
                    )
                    sent_channels.append("sms")
                except Exception as e:
                    sms_daily_limit.release_reservation(self._require_user(), "sms", now_sms)
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
            now_premium = datetime.now(timezone.utc)
            if self._sms_gate_reserve(
                "premium_sms", "briefing", now_premium, blocked_channels, blocked_reason_codes,
            ):
                try:
                    self._premium_sms_output().send(
                        subject=report.email_subject,
                        body=report.sms_text or report.email_plain,
                    )
                    sent_channels.append("premium_sms")
                except Exception as e:  # noqa: BLE001 — Grund wird Ergebnisfeld
                    sms_daily_limit.release_reservation(
                        self._require_user(), "premium_sms", now_premium,
                    )
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
                    self._telegram_output().send(
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
                        self._telegram_output().send(
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
                if failed_bubbles and not self._send_telegram_incomplete_hint(
                        report, failed_bubbles):
                    notice_failures.append("telegram_incomplete_hint")
                if telegram_fully_sent:
                    # Nur bei vollstaendiger Zustellung — das Briefing-Log darf
                    # nicht behaupten, Telegram sei komplett zugestellt worden.
                    sent_channels.append("telegram")

        # WEATHER-04: Service-E-Mail bei SMS-only + Fehler
        if request.failed_segments and not self._send_service_error_email(request):
            notice_failures.append("service_error_email")

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
                user_id=self._require_user(), kind="route",
                entity_id=request.trip.id, error=email_error,
            )

        return NotificationResult(
            sent=bool(sent_channels),
            sent_channels=sent_channels,
            telegram_fully_sent=telegram_fully_sent,
            no_channel_configured=no_channel_configured,
            blocked_channels=blocked_channels,
            blocked_reason_codes=blocked_reason_codes,
            notice_failures=notice_failures,
        )

    def _send_telegram_incomplete_hint(self, report, missing_count: int) -> bool:
        """Sichtbarer „Briefing unvollstaendig"-Hinweis (Issue #1370).

        fail-soft: scheitert auch dieser Hinweis, bricht er den Versandlauf nie
        mit einer Ausnahme ab. Issue #1405 S4b: liefert ``True`` bei
        Zustellung, ``False`` bei gescheitertem Versuch — der Aufrufer traegt
        das in ``NotificationResult.notice_failures`` ein.
        """
        from output.renderers.narrow import render_telegram_incomplete_hint

        try:
            self._telegram_output().send(
                subject=report.email_subject,
                body=render_telegram_incomplete_hint(missing_count, lang=self._lang),
                parse_mode="HTML",
                suppress_subject_line=True,
            )
        except Exception as e:  # noqa: BLE001 — fail-soft, siehe Docstring
            logger.error(f"Telegram incomplete-briefing hint failed: {e}")
            return False
        return True

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
        subject = t("versand.betreff.wetterdaten_fehlen", self._lang, trip=trip.name)
        text = t("versand.hinweis.wetterdienst_ausfall", self._lang)
        # PO-Korrektur 2026-10-31 (ADR-0104): SMS/Premium-SMS in jeder Sprache wie bisher.
        sms_text = t("versand.hinweis.wetterdienst_ausfall", "de")
        sent_channels: list[str] = []
        blocked_channels: dict[str, str] = {}
        blocked_reason_codes: dict[str, str] = {}

        if send_email:
            try:
                EmailOutput(self._settings).send(
                    subject=subject, body=text, html=False, lang=self._lang,
                )
                sent_channels.append("email")
            except Exception as e:
                logger.error(f"No-data hint email failed for {trip.name}: {e}")

        if send_sms and self._settings.can_send_sms():
            now_sms = datetime.now(timezone.utc)
            if self._sms_gate_reserve(
                "sms", "briefing", now_sms, blocked_channels, blocked_reason_codes,
            ):
                try:
                    self._sms_output().send(subject=subject, body=sms_text)
                    sent_channels.append("sms")
                except Exception as e:
                    sms_daily_limit.release_reservation(self._require_user(), "sms", now_sms)
                    logger.error(f"No-data hint SMS failed for {trip.name}: {e}")

        if send_premium_sms:
            now_premium = datetime.now(timezone.utc)
            if self._sms_gate_reserve(
                "premium_sms", "briefing", now_premium, blocked_channels, blocked_reason_codes,
            ):
                try:
                    self._premium_sms_output().send(subject=subject, body=sms_text)
                    sent_channels.append("premium_sms")
                except Exception as e:  # noqa: BLE001 — Grund wird Ergebnisfeld
                    sms_daily_limit.release_reservation(
                        self._require_user(), "premium_sms", now_premium,
                    )
                    blocked_channels["premium_sms"] = str(e)
                    _record_block_reason_code(blocked_reason_codes, "premium_sms", e)
                    logger.error(f"No-data hint Premium-SMS blockiert für {trip.name}: {e}")

        if send_telegram and self._settings.can_send_telegram():
            try:
                self._telegram_output().send(subject=subject, body=text)
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
        reference_at: Optional[str] = None,
        anchor_weather: Optional[list["SegmentWeatherData"]] = None,
    ) -> NotificationResult:
        """Wetter-Änderungs-Alert: rendern und über konfigurierte Kanäle versenden.

        Issue #1737: `anchor_weather` ist die ALTE Reihe (Anker, Quelle des
        Vergleichs) -- aus ihr und `weather` entstehen die Stundenzeilen; der
        Anzeigemodus je Kanal kommt aus `trip.display_config`.

        Issue #1023: Der AlertService kennt keine Renderer-/Transport-Details mehr.
        Issue #1088: optionale amtliche Warnungen werden in dieselbe Nachricht
        gebündelt (kein zweiter Versand).
        Issue #1916: `reference_at` ist der bereits formatierte Referenz-
        Zeitpunkt der tatsaechlich verglichenen Vergleichsbasis (Aufrufer:
        `TripAlertService`) -- additiv, `None` laesst den Footer unveraendert.
        """
        from utils.timezone import tz_for_coords

        alert_tz = tz_for_coords(
            weather[0].segment.start_point.lat,
            weather[0].segment.start_point.lon,
        )
        # Issue #2020 Scheibe 2: EINE Referenzzeit fuer Stand-Zeile UND
        # Blickrichtung -- sonst koennte die Fusszeile eine andere Stunde
        # nennen als die Restmengen-Rechnung.
        now_utc = datetime.now(timezone.utc)
        stand_at = local_fmt(now_utc, alert_tz)
        # Issue #2122 (AC-1): der Abweichungs-Alarm ist STRIKT "heute" (der
        # einzige Anker-Kandidat, `trip_alert._kanal_anker_kandidat` verwirft
        # jeden mit abweichendem `target_date`) -- kein Rueckgriff auf
        # `_resolve_alert_segment` noetig. "Heute" ist der ORTSTAG der Tour
        # (Adversary F001, ADR-0044) -- NICHT die Server-/Weltzeit-Wanduhr:
        # `date.today()` waere um Mitternacht ein `ambient_clock`-Rueckfall
        # (Issue #1402) und koennte bei einer Tour ausserhalb der Serverzone
        # die falsche Etappe treffen.
        stage_number = _stage_number_for_date(trip, trip_local_today(trip, now_utc))
        alert_msg = to_alert_message(
            changes, weather, trip.name, tz=alert_tz, stand_at=stand_at,
            reference_at=reference_at,
            now_utc=now_utc, stage_number=stage_number,
            anchor_segments=anchor_weather,
            format_modes=_alert_format_modes(trip.display_config),
            indicator_keys=_alert_indicator_keys(trip.display_config),
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
        reference_at: Optional[str] = None,
        anchor_points: Optional[dict] = None,
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

        Issue #1916: `reference_at` ist additiv, analog `send_deviation_alert()`
        — kein bestehender Aufrufer setzt ihn, Verhalten bleibt unveraendert.

        Issue #1737: `anchor_points` (`{Ortsname: PointWeatherData}`, ALTE Reihe
        je Ort) speist die Stundenzeilen (additiv). Die Stundenwerte sind
        IMMER roh wie die Stundentabelle der Vergleichs-Mail (PO 2026-10-21,
        AC-5) -- der Ortsvergleich kennt keine Roh/Einfach-Wahl dafuer.
        """
        from utils.timezone import tz_for_coords

        first_points = entities[0][1]
        alert_tz = tz_for_coords(first_points[0].lat, first_points[0].lon)
        stand_at = local_fmt(datetime.now(timezone.utc), alert_tz)
        groups = [
            (name, changes, points[0] if points else None)
            for name, points, changes in entities
        ]
        alert_msg = to_multi_point_alert_message(
            groups, tz=alert_tz, stand_at=stand_at, reference_at=reference_at,
            anchor_points=anchor_points,
        )
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
            anchor_points=anchor_points,
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
        segment_km: Optional[dict] = None,
        allclears: Optional[list] = None,
    ) -> NotificationResult:
        """Standalone amtlicher Alert ohne Wetter-Delta (Issue #1088; Format-
        Fidelity zur Design-Vorlage in Issue #1216).

        Issue #1441 S2: `allclears` (Entwarnungen) stehen in DERSELBEN Nachricht
        nach den Warnungen; `allclear_channels` meldet, wo sie enthalten waren.

        Baut aus den rohen `(OfficialAlert, segment_ids)`-Paaren die
        kontext-agnostischen `OfficialAlertNotice`-DTOs und rendert Betreff,
        HTML-Body, Telegram- und SMS-Text ueber die vier Vorlagen-Renderer.
        """
        from output.renderers.alert.official_alerts import (
            build_official_alert_notices, build_official_allclear_notices,
            render_official_alert_sms_with_allclears,
        )
        from utils.timezone import tz_for_coords

        first_wp = next(iter(trip.all_waypoints), None)
        alert_tz = (
            tz_for_coords(first_wp.lat, first_wp.lon)
            if first_wp is not None
            else ZoneInfo("UTC")
        )
        # Issue #2122 (AC-5, Adversary F001/F002): das Datum des TATSAECHLICH
        # verwendeten rollierenden Ankers -- dieselbe Kanal-Reihenfolge
        # (`sorted`) wie der lenient Anker-Rueckfall in
        # `trip_alert._resolve_current_weather` (erster Treffer gewinnt,
        # keine Alterspruefung dort -- der reicht dort NUR die Routen-
        # Geometrie weiter, die altersunabhaengig gueltig bleibt). Die
        # Etappen-NUMMER haengt dagegen sehr wohl vom Tag ab: ein mehrere
        # Tage alter, fuer die Geometrie noch brauchbarer Anker wuerde sonst
        # eine FALSCHE Etappe behaupten (F002, reproduziert: S1 statt S3).
        # Deshalb zaehlt der Anker hier NUR, wenn sein Datum mit dem
        # ORTSTAG der Tour (F001, ADR-0044 -- NICHT `date.today()`)
        # uebereinstimmt; sonst `stage_number=None` (kein Praefix) statt
        # eine geratene Zahl -- dieselbe Linie wie AC-8.
        from services.weather_snapshot import WeatherSnapshotService

        now_utc = datetime.now(timezone.utc)
        local_today = trip_local_today(trip, now_utc)
        snap_svc = WeatherSnapshotService(user_id=self._require_user())
        anchor_date = None
        for channel in sorted(effective_channels):
            anchor_date = snap_svc.alarm_anchor_target_date(trip.id, channel)
            if anchor_date is not None:
                break
        stage_number = (
            _stage_number_for_date(trip, local_today)
            if anchor_date == local_today else None
        )
        # Issue #2036: gemessene km-Spannen mitgeben -- ohne sie bleibt die
        # amtliche Warnung byte-identisch bei der Segment-Sprache.
        lang = self._lang
        dto_notices = build_official_alert_notices(
            trip, notices, segment_km=segment_km, stage_number=stage_number, lang=lang,
        )
        ac_notices = build_official_allclear_notices(allclears or [], lang=lang)
        source_label = _official_allclear_source_label(dto_notices, ac_notices, lang=lang)
        source_url = _official_source_url_for(dto_notices)
        # #1233 Nebenbefund AC-12: Betreff und Body MUESSEN dieselbe tz-aware
        # Quelle nutzen (sonst Wochentags-Divergenz Betreff vs. Body).
        subject = _official_subject(
            dto_notices, ac_notices, prefix=trip.name, tz=alert_tz, lang=lang)
        stand_at = local_fmt(datetime.now(timezone.utc), alert_tz)
        # Issue #1216 F002 / #1744 A2 (AC-13): geteilter Baustein (variant=
        # "standalone") plus eigens gebauter Klartext aus denselben Datenzeilen.
        html, plain = _official_mail_bodies(
            dto_notices, ac_notices, source_label=source_label, source_url=source_url,
            stand_at=stand_at, tz=alert_tz, context_label=trip.name, lang=lang,
        )
        telegram_text = _official_telegram_rich(
            dto_notices, ac_notices, prefix=trip.name, source_label=source_label, tz=alert_tz,
            lang=lang,
        )
        sms_body, sms_has_allclear = render_official_alert_sms_with_allclears(
            dto_notices, ac_notices, tz=alert_tz,
        )
        allclear_channels: list[str] = []
        if ac_notices:
            allclear_channels.append("email")
            if telegram_style != "kurzform" or sms_has_allclear:
                allclear_channels.append("telegram")
            if sms_has_allclear:
                allclear_channels.extend(["sms", "premium_sms"])

        # Issue #1405 S1 (ADR-0086): `sent_channels` = zugestellt (append IM
        # try NACH dem Send), `attempted_channels` = betreten (NACH dem try).
        sent_channels: list[str] = []
        attempted_channels: list[str] = []
        failed_channels: list[str] = []  # Issue #1459: Alarm-Protokoll
        # Issue #1701 (S2b, D5): analog `_dispatch_alert_message`.
        blocked_channels: dict[str, str] = {}
        blocked_reason_codes: dict[str, str] = {}

        if "email" in effective_channels and self._settings.can_send_email():
            try:
                if mail_sink is not None:
                    mail_sink(subject=subject, body=html)
                else:
                    EmailOutput(self._settings).send(
                        subject=subject, body=html, html=True,
                        plain_text_body=plain, mail_type="official-alert", lang=self._lang,
                    )
                sent_channels.append("email")
            except Exception as e:
                failed_channels.append("email")
                logger.error(f"Official alert email failed for {trip.name}: {e}")
            attempted_channels.append("email")

        if "telegram" in effective_channels and self._settings.can_send_telegram():
            try:
                # Issue #1260 S3: Kurzstil sendet den SMS-Text (Plaintext,
                # parse_mode=None) statt der reichen Telegram-Warnvorlage.
                if telegram_style == "kurzform":
                    self._telegram_output().send(
                        subject=subject, body=sms_body,
                        parse_mode=None, suppress_subject_line=True,
                    )
                else:
                    self._telegram_output().send(
                        subject=subject, body=telegram_text,
                        parse_mode="HTML", suppress_subject_line=True,
                    )
                sent_channels.append("telegram")
            except Exception as e:
                failed_channels.append("telegram")
                logger.error(f"Official alert telegram failed for {trip.name}: {e}")
            attempted_channels.append("telegram")

        if "sms" in effective_channels and self._settings.can_send_sms():
            now_sms = datetime.now(timezone.utc)
            if self._sms_gate_reserve(
                "sms", "alert", now_sms, blocked_channels, blocked_reason_codes,
            ):
                try:
                    if sms_sink is not None:
                        sms_sink(sms_body)
                    else:
                        self._sms_output().send(subject="", body=sms_body)
                    sent_channels.append("sms")
                except Exception as e:
                    sms_daily_limit.release_reservation(self._require_user(), "sms", now_sms)
                    failed_channels.append("sms")
                    logger.error(f"Official alert sms failed for {trip.name}: {e}")
                attempted_channels.append("sms")

        # Premium-SMS (Garmin inReach, Issue #1701 S2b) — bewusst OHNE
        # can_send_*()-Bereitschaftsfrage (D2), Sperrgrund geht nach
        # `blocked_channels`/`blocked_reason_codes` statt `failed_channels`
        # (kein Transportfehler, s. `_dispatch_alert_message`).
        if "premium_sms" in effective_channels:
            now_premium = datetime.now(timezone.utc)
            if self._sms_gate_reserve(
                "premium_sms", "alert", now_premium, blocked_channels, blocked_reason_codes,
            ):
                try:
                    self._premium_sms_output().send(subject="", body=sms_body)
                    sent_channels.append("premium_sms")
                except Exception as e:  # noqa: BLE001 — Grund wird Ergebnisfeld
                    sms_daily_limit.release_reservation(
                        self._require_user(), "premium_sms", now_premium,
                    )
                    blocked_channels["premium_sms"] = str(e)
                    _record_block_reason_code(blocked_reason_codes, "premium_sms", e)
                    failed_channels.append("premium_sms")
                    logger.error(f"Official alert premium-sms failed for {trip.name}: {e}")
                attempted_channels.append("premium_sms")

        return NotificationResult(
            sent=bool(sent_channels), sent_channels=sent_channels,
            attempted_channels=attempted_channels,
            failed_channels=failed_channels,
            blocked_channels=blocked_channels,
            blocked_reason_codes=blocked_reason_codes,
            allclear_channels=allclear_channels,
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
        premium_sms_sink: Optional[object] = None,
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
        # Issue #2412 S4a: existierten vorher nicht in dieser Methode (Spec:
        # "send_compare_report (neue Ergebnisfelder)").
        blocked_channels: dict[str, str] = {}
        blocked_reason_codes: dict[str, str] = {}
        failed_channels: list[str] = []  # Issue #2275

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
                    # X-GZ-Lang = Sprache des INHALTS: seit #2672 rendert
                    # scheduler_dispatch_service den Ortsvergleich in derselben
                    # Sprache, mit der dieser Dienst gebaut wurde.
                    lang=self._lang,
                )
            sent_channels.append("email")

        if "telegram" in effective_channels and self._settings.can_send_telegram():
            try:
                if telegram_sink is not None:
                    telegram_sink(telegram_text)
                else:
                    self._telegram_output().send(
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
            now_sms = datetime.now(timezone.utc)
            if self._sms_gate_reserve(
                "sms", "briefing", now_sms, blocked_channels, blocked_reason_codes,
            ):
                try:
                    if sms_sink is not None:
                        sms_sink(sms_text)
                    else:
                        self._sms_output().send(subject="", body=sms_text)
                    sent_channels.append("sms")
                except Exception as e:
                    sms_daily_limit.release_reservation(self._require_user(), "sms", now_sms)
                    logger.error(f"Compare report sms failed for {subject!r}: {e}")

        # Premium-SMS (Issue #2275, ADR-0049): kein `can_send_*` davor — die
        # Freigabe steckt im Aufloeser, Rueckadresse/Frist prueft der Kanal.
        # Fail-soft: Fehler wird gebucht, E-Mail-Erfolg bleibt gueltig.
        if "premium_sms" in effective_channels:
            now_premium = datetime.now(timezone.utc)
            if self._sms_gate_reserve(
                "premium_sms", "briefing", now_premium, blocked_channels, blocked_reason_codes,
            ):
                try:
                    if premium_sms_sink is not None:
                        premium_sms_sink(sms_text)
                    else:
                        self._premium_sms_output().send(subject="", body=sms_text)
                    sent_channels.append("premium_sms")
                except Exception as e:  # noqa: BLE001 — Grund wird Ergebnisfeld
                    sms_daily_limit.release_reservation(
                        self._require_user(), "premium_sms", now_premium,
                    )
                    blocked_channels["premium_sms"] = str(e)
                    _record_block_reason_code(blocked_reason_codes, "premium_sms", e)
                    # AC-2: auch ein Transportfehler traegt einen Code (der
                    # Ortsvergleich hat keinen Nachhol-Weg, der Fehlschlag muss
                    # maschinenlesbar sein); Sperrgruende behalten ihren Code.
                    blocked_reason_codes.setdefault("premium_sms", "premium_sms_send_failed")
                    failed_channels.append("premium_sms")
                    logger.error(f"Compare report premium_sms failed for {subject!r}: {e}")

        return NotificationResult(
            sent=bool(sent_channels), sent_channels=sent_channels,
            # Issue #2280: Paritaet zum Trip — kein wirksamer Kanal.
            no_channel_configured=not effective_channels,
            failed_channels=failed_channels,
            blocked_channels=blocked_channels, blocked_reason_codes=blocked_reason_codes,
        )

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
        allclears: Optional[list] = None,
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
            build_compare_official_alert_notices, build_official_allclear_notices,
        )
        from utils.timezone import resolve_location_tz

        all_location_ids = [loc.id for loc in locations]
        id_to_name = {loc.id: loc.name for loc in locations}
        lang = self._lang
        dto_notices = build_compare_official_alert_notices(
            all_location_ids, id_to_name, tagged_alerts, lang=lang,
        )
        # Issue #1441 S2: Entwarnungen (Orts-IDs -> Namen) in derselben Nachricht.
        ac_notices = build_official_allclear_notices(allclears or [], id_to_name, lang=lang)
        if not dto_notices and not ac_notices:
            return NotificationResult(sent=False, sent_channels=[])

        first_loc = locations[0] if locations else None
        alert_tz = (
            (resolve_location_tz(first_loc) or ZoneInfo("UTC"))
            if first_loc is not None
            else ZoneInfo("UTC")
        )
        source_label = _official_allclear_source_label(dto_notices, ac_notices, lang=lang)
        source_url = _official_source_url_for(dto_notices)
        # #1233 Nebenbefund AC-12: Betreff und Body MUESSEN dieselbe tz-aware
        # Quelle nutzen (sonst Wochentags-Divergenz Betreff vs. Body).
        subject = _official_subject(
            dto_notices, ac_notices, prefix=preset_name, tz=alert_tz, lang=lang)
        stand_at = local_fmt(datetime.now(timezone.utc), alert_tz)
        # Issue #1216 F002 / #1744 A2 (AC-13): derselbe Baustein und derselbe
        # Klartext-Bau wie im Trip-Pfad.
        html, plain = _official_mail_bodies(
            dto_notices, ac_notices, source_label=source_label, source_url=source_url,
            stand_at=stand_at, tz=alert_tz,
            context_label=t("versand.kontext.ortsvergleich", lang), lang=lang,
        )

        # Issue #1701 (S2b, D5): analog `_dispatch_alert_message`.
        blocked_channels: dict[str, str] = {}
        blocked_reason_codes: dict[str, str] = {}
        # Issue #1405 S1 (ADR-0086): Helfer liefern `True` = zugestellt. Ein
        # `False` MIT Sperr-Code ist eine bewusste Sperre, kein Transport-
        # fehler. `attempted_channels` fuehrt -- wie frueher `sent_channels`
        # -- jeden betretenen Kanal, auch den gesperrten (Cockpit-Zahl).
        versuche: list[tuple[str, bool]] = []
        if "email" in effective_channels and self._settings.can_send_email():
            versuche.append(("email", self._dispatch_compare_official_email(
                preset_name, subject, html, mail_sink, plain=plain,
            )))
        if "telegram" in effective_channels and self._settings.can_send_telegram():
            versuche.append(("telegram", self._dispatch_compare_official_telegram(
                preset_name, subject, dto_notices, source_label, alert_tz, telegram_sink,
                telegram_style=telegram_style, ac_notices=ac_notices,
            )))
        if "sms" in effective_channels and self._settings.can_send_sms():
            versuche.append(("sms", self._dispatch_compare_official_sms(
                preset_name, dto_notices, alert_tz, sms_sink,
                blocked_channels, blocked_reason_codes, ac_notices=ac_notices,
            )))
        # Premium-SMS (Garmin inReach, Issue #1701 S2b) — bewusst OHNE
        # can_send_*()-Bereitschaftsfrage (D2), Sperrgrund geht nach
        # `blocked_channels`/`blocked_reason_codes` statt `failed_channels`.
        if "premium_sms" in effective_channels:
            versuche.append(("premium_sms", self._dispatch_compare_official_premium_sms(
                preset_name, dto_notices, alert_tz, blocked_channels, blocked_reason_codes,
                ac_notices=ac_notices,
            )))

        sent_channels = [c for c, ok in versuche if ok]
        failed_channels = [  # Issue #1459: Alarm-Protokoll
            c for c, ok in versuche if not ok and c not in blocked_reason_codes
        ]
        return NotificationResult(
            sent=bool(sent_channels), sent_channels=sent_channels,
            attempted_channels=[c for c, _ok in versuche],
            failed_channels=failed_channels,
            blocked_channels=blocked_channels,
            blocked_reason_codes=blocked_reason_codes,
            allclear_channels=_compare_allclear_channels(
                ac_notices, dto_notices, telegram_style, alert_tz,
            ),
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
                    plain_text_body=plain, mail_type="official-alert", lang=self._lang,
                )
        except Exception as e:
            logger.error(f"Compare official alert email failed for {preset_name}: {e}")
            return False
        return True

    def _dispatch_compare_official_telegram(
        self, preset_name: str, subject: str, dto_notices: list, source_label: str,
        alert_tz: ZoneInfo, telegram_sink: Optional[object],
        telegram_style: str = "rich", ac_notices: Optional[list] = None,
    ) -> bool:
        """Issue #1459: `True`, wenn der Transport ohne Fehler durchlief."""
        from output.renderers.alert.official_alerts import (
            render_official_alert_sms_with_allclears,
        )

        try:
            # Issue #1260 S4: Kurzstil sendet den amtlichen SMS-Text (Plaintext,
            # parse_mode=None, keine Inline-Knöpfe) statt der reichen Compare-
            # Warnvorlage. Default "rich" bleibt unverändert.
            if telegram_style == "kurzform":
                kurz_body, _ = render_official_alert_sms_with_allclears(
                    dto_notices, ac_notices or [], tz=alert_tz,
                )
                if telegram_sink is not None:
                    telegram_sink(kurz_body)
                else:
                    self._telegram_output().send(
                        subject=subject, body=kurz_body,
                        parse_mode=None, suppress_subject_line=True,
                    )
                return True
            telegram_text = _official_telegram_rich(
                dto_notices, ac_notices or [], prefix=preset_name,
                source_label=source_label, tz=alert_tz, lang=self._lang,
            )
            if telegram_sink is not None:
                telegram_sink(telegram_text)
            else:
                self._telegram_output().send(
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
        blocked_channels: Optional[dict[str, str]] = None,
        blocked_reason_codes: Optional[dict[str, str]] = None,
        ac_notices: Optional[list] = None,
    ) -> bool:
        """Issue #1459: `True`, wenn der Transport ohne Fehler durchlief.

        Issue #2412 S4a: `False` auch bei Tageslimit-Sperre (kein
        Transportversuch) — `blocked_channels`/`blocked_reason_codes` werden
        dann befuellt (analog `_dispatch_compare_official_premium_sms`)."""
        from output.renderers.alert.official_alerts import (
            render_official_alert_sms_with_allclears,
        )

        _blocked = blocked_channels if blocked_channels is not None else {}
        _codes = blocked_reason_codes if blocked_reason_codes is not None else {}
        now = datetime.now(timezone.utc)
        if not self._sms_gate_reserve("sms", "alert", now, _blocked, _codes):
            return False
        try:
            sms_text, _ = render_official_alert_sms_with_allclears(
                dto_notices, ac_notices or [], tz=alert_tz,
            )
            if sms_sink is not None:
                sms_sink(sms_text)
            else:
                self._sms_output().send(subject="", body=sms_text)
        except Exception as e:
            sms_daily_limit.release_reservation(self._require_user(), "sms", now)
            logger.error(f"Compare official alert sms failed for {preset_name}: {e}")
            return False
        return True

    def _dispatch_compare_official_premium_sms(
        self, preset_name: str, dto_notices: list, alert_tz: ZoneInfo,
        blocked_channels: dict[str, str], blocked_reason_codes: dict[str, str],
        ac_notices: Optional[list] = None,
    ) -> bool:
        """Issue #1701 (S2b, Vorbild `_dispatch_compare_official_sms`):
        `True`, wenn der Transport ohne Fehler durchlief. Eine bewusste
        Sperre (keine/veraltete Rueckadresse ODER Issue #2412 S4a
        Tageslimit) landet zusaetzlich in `blocked_channels`/
        `blocked_reason_codes` (D5) — kein Transportfehler."""
        from output.renderers.alert.official_alerts import (
            render_official_alert_sms_with_allclears,
        )

        now = datetime.now(timezone.utc)
        if not self._sms_gate_reserve(
            "premium_sms", "alert", now, blocked_channels, blocked_reason_codes,
        ):
            return False
        try:
            premium_text, _ = render_official_alert_sms_with_allclears(
                dto_notices, ac_notices or [], tz=alert_tz,
            )
            self._premium_sms_output().send(subject="", body=premium_text)
        except Exception as e:  # noqa: BLE001 — Grund wird Ergebnisfeld
            sms_daily_limit.release_reservation(self._require_user(), "premium_sms", now)
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
        # Issue #2122 (AC-2/AC-6): das Datum, dem das gemeldete Segment
        # ENTSTAMMT (`request.segment_date`) -- NICHT `today`, ein
        # Nachtsegment kann der Vortag sein. Ortsvergleich-Radar baut kein
        # `RadarAlertRequest` -> `segment_date` bleibt `None` -> keine Etappe.
        stage_number = _stage_number_for_date(trip, request.segment_date)
        onset_event = OnsetEvent(
            # Issue #2050 S2b: ohne kuenftigen Beginn traegt `onset_minutes`
            # `None` -- der Renderer-Vertrag verlangt eine Zahl, liest sie im
            # Laufend-Fall aber nirgends (jede Textform verzweigt vorher).
            onset_minutes=request.onset_minutes or 0,
            already_running=request.already_running,  # Issue #2050 S2b
            onset_time=request.onset_time,
            km_from=request.km_from,
            km_to=request.km_to,
            is_convective=request.is_convective,
            intensity_label=request.intensity_label,
            source_label=request.source_label,
            briefing_context=request.briefing_context,
            segment_id=request.segment_id,  # Issue #1744 A1
            onset_day_offset=request.onset_day_offset,  # Issue #2009
            onset_weekday=request.onset_weekday,  # Issue #2054
            onset_precip_mm=request.onset_precip_mm,  # Issue #2046
            event_end_time=request.event_end_time,  # Issue #2051 S1
            event_end_day_offset=request.event_end_day_offset,  # Issue #2051 S1
            event_end_weekday=request.event_end_weekday,  # Issue #2054
            # Issue #2051 S1 (Spec v1.1): waehlt die Ende-Textform im Renderer.
            event_ongoing_beyond_horizon=request.event_ongoing_beyond_horizon,
            # Issue #2051 S3: additiv durchgereicht.
            source_reach_time=request.source_reach_time,
            source_reach_day_offset=request.source_reach_day_offset,
            location_sharpness_limit_time=request.location_sharpness_limit_time,
            location_sharpness_limit_day_offset=request.location_sharpness_limit_day_offset,
            # Issue #2051 S2a: Ausdehnung und die Echtheitspruefung der
            # km-Zahlen reisen GEMEINSAM -- die Zonen ohne `km_measured`
            # blieben im Text stumm, das Flag ohne Zonen wirkungslos.
            km_measured=request.km_measured,
            rain_zones=tuple(request.rain_zones),
            # Issue #2050 S4b-2: die ausgefallene Gewitterpruefung und die
            # Messluecken der Ausdehnung -- beide rein beschreibend, sie
            # aendern nur den Text (Kennzeichnung), nicht die Entscheidung.
            convective_checked=request.convective_checked,
            gap_km=tuple(request.gap_km),
            stage_number=stage_number,  # Issue #2122
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
            addendum_reference=request.addendum_reference,  # Issue #2018
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
        anchor_points: Optional[dict] = None,
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

        Issue #1088 / #2422 S4 (Fix): liegen `official_notices` vor, wird ein
        Text-Block an html/plain/telegram_body angehängt UND `sms_body` bekommt
        mindestens den kurzen Hinweistext `_AMTL_HINWEIS_SMS_TOKEN` angehängt
        (Epic #2133: „jeder Kanal muss jede Frage beantworten können" — ein
        sang- und klangloses Weglassen ist keine akzeptable Abweichung mehr).
        Das Limit wird VOR dem Rendern um die Hinweislänge reduziert (gleiches
        Muster wie der `addendum`-Zweig in `render_sms()`), damit das
        140-Zeichen-Alarm-SMS-Limit auch mit Hinweis nie überschritten wird.
        `sms_body` wird auch für Telegram-Kurzform und Premium-SMS
        wiederverwendet — beide bekommen den Hinweis dann ebenfalls (im
        Sinne der Kanal-Parität kein Fehlverhalten).

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
        lang = self._lang
        subject = render_alert_subject(alert_msg, lang=lang)
        html, plain = render_alert_email(alert_msg, lang=lang)
        telegram_body = render_alert_telegram(alert_msg, lang=lang)
        # Issue #2422 S4 (Fix #1088): liegt ein amtlicher Zusatzblock vor,
        # wird das SMS-Limit VOR dem Rendern um die Hinweislänge reduziert,
        # damit der angehängte Hinweistext das 140-Zeichen-Limit nicht
        # sprengt (gleiches Muster wie der `addendum`-Zweig in `render_sms`).
        sms_limit = 140
        if official_notices:
            sms_limit -= len(_AMTL_HINWEIS_SMS_SUFFIX)
        sms_body = render_alert_sms(
            alert_msg, limit=sms_limit, location_positions=sms_location_positions,
        )
        if official_notices:
            sms_body += _AMTL_HINWEIS_SMS_SUFFIX

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
            # Issue #2036: dieselbe Ortssprache wie der Aenderungs-Teil
            # DERSELBEN Mail -- die km-Spannen stammen aus den bereits
            # projizierten Ereignissen, nicht aus einer zweiten Quelle.
            embed_notices = build_official_alert_notices(
                None, official_notices,
                segment_km=_measured_event_km(alert_msg), lang=lang,
            )
            embed_source = _official_source_label_for(embed_notices, lang=lang)
            embedded_html = render_warn_block(
                embed_notices, variant="embedded", source_label=embed_source,
                tz=alert_tz, lang=lang,
            )
            html = html.replace(
                "</body></html>", embedded_html + "</body></html>",
            )
            # Plain/Telegram bleiben beim bestehenden Notice-Text (AC-6 betrifft
            # nur das HTML-Format, das aus dem Rahmen brach).
            extra_lines = render_official_alert_notice_plain(
                official_notices, tz=alert_tz, lang=lang,
            )
            extra_text = "\n".join(extra_lines)
            plain += "\n\n" + extra_text
            telegram_body += "\n\n" + extra_text

        # Issue #1405 S1 (ADR-0086): `sent_channels` = zugestellt (append IM
        # try NACH dem Send), `attempted_channels` = betreten (NACH dem try).
        sent_channels: list[str] = []
        attempted_channels: list[str] = []
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
        # Issue #1405 S4b (B21): gescheiterter Teilzustellungs-Hinweis, NICHT
        # in `failed_channels` (ADR-0086: Backoff/Throttle unberuehrt).
        notice_failures: list[str] = []

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

        # E-Mail: zugestellt erst nach fehlerfreiem Send (ADR-0086 loest
        # #684 AC-3 ab); betreten ist der Kanal in jedem Fall.
        if "email" in effective_channels and self._settings.can_send_email():
            try:
                if mail_sink is not None:
                    mail_sink(subject=subject, body=plain)
                else:
                    EmailOutput(self._settings).send(
                        subject=subject,
                        body=html,
                        plain_text_body=plain,
                        mail_type=mail_type,
                        lang=lang,
                    )
                sent_channels.append("email")
            except Exception as e:
                _log_error("email", e)
            attempted_channels.append("email")

        # Telegram
        if "telegram" in effective_channels and self._settings.can_send_telegram():
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
                    self._telegram_output().send(
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
                                # Issue #1737: der Anker reist je Ort mit.
                                anchor_points=anchor_points,
                                format_modes=alert_msg.format_modes,
                                indicator_keys=alert_msg.indicator_keys,
                            )
                            single_body = render_alert_telegram(single_msg, lang=lang)
                            self._telegram_output().send(
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
                    if failed_count and not self._send_telegram_incomplete_hint(
                            SimpleNamespace(email_subject=subject), failed_count):
                        # #1370-Muster: Teilzustellung wird gemeldet statt
                        # still verschluckt; scheitert der Hinweis selbst,
                        # steht das im Ergebnis (#1405 S4b).
                        notice_failures.append("telegram_incomplete_hint")
                    # Issue #1405 S1 (AC-6): mindestens eine Blase angekommen
                    # = Kanal zugestellt (keine Wiederholung, keine Dubletten);
                    # die Teilzustellung zeigt `telegram_fully_sent`. Scheitern
                    # ALLE Blasen, ist das ein Transportfehler.
                    if failed_count == len(telegram_groups):
                        raise RuntimeError(
                            f"alle {failed_count} Telegram-Sprechblasen gescheitert"
                        )
                else:
                    self._telegram_output().send(
                        subject=subject,
                        body=telegram_body,
                        parse_mode="HTML",
                        suppress_subject_line=True,
                    )
                sent_channels.append("telegram")
            except Exception as e:
                _log_error("telegram", e)
            attempted_channels.append("telegram")

        # SMS
        if "sms" in effective_channels and self._settings.can_send_sms():
            now_sms = datetime.now(timezone.utc)
            if self._sms_gate_reserve(
                "sms", "alert", now_sms, blocked_channels, blocked_reason_codes,
            ):
                try:
                    self._sms_output().send(subject=subject, body=sms_body)
                    sent_channels.append("sms")
                except Exception as e:
                    sms_daily_limit.release_reservation(self._require_user(), "sms", now_sms)
                    _log_error("sms", e)
                attempted_channels.append("sms")

        # Premium-SMS (Garmin inReach, Issue #1701 S2b) — bewusst OHNE
        # vorgeschaltete can_send_*()-Bereitschaftsfrage (D2): die
        # Sendebereitschaft entscheidet ausschliesslich
        # `PremiumSmsRecipient.for_user()` zur Sendezeit (#1412 S4b); eine
        # bewusste Sperre (keine/veraltete Rueckadresse) landet in
        # `blocked_channels`/`blocked_reason_codes` statt in
        # `failed_channels` — sie ist kein Transportfehler.
        if "premium_sms" in effective_channels:
            now_premium = datetime.now(timezone.utc)
            if self._sms_gate_reserve(
                "premium_sms", "alert", now_premium, blocked_channels, blocked_reason_codes,
            ):
                try:
                    self._premium_sms_output().send(subject=subject, body=sms_body)
                    sent_channels.append("premium_sms")
                except Exception as e:  # noqa: BLE001 — Grund wird Ergebnisfeld
                    sms_daily_limit.release_reservation(
                        self._require_user(), "premium_sms", now_premium,
                    )
                    blocked_channels["premium_sms"] = str(e)
                    _record_block_reason_code(blocked_reason_codes, "premium_sms", e)
                    _log_error("premium_sms", e)
                attempted_channels.append("premium_sms")

        return NotificationResult(
            sent=bool(sent_channels), sent_channels=sent_channels,
            attempted_channels=attempted_channels,
            failed_channels=failed_channels,
            telegram_fully_sent=telegram_fully_sent,
            blocked_channels=blocked_channels,
            blocked_reason_codes=blocked_reason_codes,
            notice_failures=notice_failures,
        )

    # ------------------------------------------------------------------
    # Inbound command replies (Issue #1024)
    # ------------------------------------------------------------------

    def send_command_reply_email(
        self, result: CommandResult, settings: Settings, *, lang: str = "de",
    ) -> bool:
        """Sendet eine Command-Bestätigung per E-Mail.

        Issue #1405 S4b: ``True`` = zugestellt, ``False`` = Versand gescheitert
        (der Posteingang-Lauf zaehlt das als Fehler). ``lang`` (#2673): Sprache
        des Inhalts fuer den Kopf ``X-GZ-Lang``.
        """
        try:
            EmailOutput(settings).send(
                subject=result.confirmation_subject,
                body=result.confirmation_body,
                html=False,
                lang=lang,
            )
            logger.info(f"Confirmation sent: {result.confirmation_subject}")
        except Exception as e:
            logger.error(f"Failed to send confirmation: {e}")
            return False
        return True

    def send_command_reply_premium_sms(
        self, result: CommandResult, settings: Settings,
    ) -> None:
        """Sendet eine Command-Bestätigung per Premium-SMS (Issue #2184).

        Issue #2412 S4a: `purpose="reply"` -- Garmin-Antworten duerfen die
        Reply-Reserve ueber dem Premium-SMS-Grundlimit ausschoepfen. Kein
        `NotificationResult` an dieser Stelle (`-> None`); eine Sperre bleibt
        nur ueber die Aufzeichner-/Transport-Beobachtung sichtbar (Spec).
        """
        now = datetime.now(timezone.utc)
        if not self._sms_gate_reserve("premium_sms", "reply", now, {}, {}):
            logger.error("Premium-SMS confirmation blocked: SMS-Tageslimit erreicht")
            return
        try:
            self._premium_sms_output(settings).send(
                subject=result.confirmation_subject,
                body=result.confirmation_body,
            )
            logger.info(f"Premium-SMS confirmation sent: {result.confirmation_subject}")
        except Exception as e:
            sms_daily_limit.release_reservation(self._require_user(), "premium_sms", now)
            logger.error(f"Failed to send premium-sms confirmation: {e}")

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
            return self._telegram_reply(settings, chat_id).send(**kwargs)
        except Exception as e:
            logger.error(f"Telegram command reply failed for {mask_number(chat_id)}: {e}")
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
            return self._telegram_reply(settings, chat_id).send(**kwargs)
        except Exception as e:
            logger.error(f"Telegram message failed for {mask_number(chat_id)}: {e}")
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
        try:
            self._telegram_reply(settings, chat_id).edit_message_text(
                chat_id,
                message_id,
                text,
                reply_markup=reply_markup,
            )
            return True
        except Exception as e:
            logger.error(f"Telegram edit_message_text failed for {mask_number(chat_id)}/{message_id}: {e}")
            return False

    def delete_telegram_message(
        self,
        *,
        chat_id: str,
        message_id: int,
        settings: Settings,
    ) -> bool:
        """Löscht eine Telegram-Nachricht."""
        try:
            self._telegram_reply(settings, chat_id).delete_message(chat_id, message_id)
            return True
        except Exception as e:
            logger.error(f"Telegram delete_message failed for {mask_number(chat_id)}/{message_id}: {e}")
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
            logger.error(f"Telegram answer_callback_query failed for {mask_number(callback_query_id)}: {e}")
            return False

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _apply_prefixes(self, report, request: TripReportRequest) -> None:
        """Test-/On-Demand-/Catchup-/Teilausfall-Präfixe auf Betreff und Body anwenden."""
        stage_name = request.stage_name or t("versand.etappe.rueckfall", self._lang)
        target_date = self._target_date_from_report(report, request)
        human_date = fmt_date_numeric(target_date, self._lang)

        if request.test_prefix:
            hint = t("versand.hinweis.test_vorschau", self._lang,
                     etappe=stage_name, datum=human_date)
            report.email_subject = f"[TEST] {report.email_subject}"
            self._prepend_hint(report, hint)
        elif request.on_demand_prefix:
            hint = t("versand.hinweis.auf_anfrage", self._lang,
                     etappe=stage_name, datum=human_date)
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
                lang=self._lang,
            )
        else:
            email_output.send(
                subject=report.email_subject,
                body=report.email_plain,
                html=False,
                mail_type="trip-briefing",
                mail_format="compact",
                lang=self._lang,
            )

    def _send_service_error_email(self, request: TripReportRequest) -> bool:
        """Service-E-Mail bei Provider-Fehler für SMS-only Trips.

        Issue #1405 S4b: ``True`` = zugestellt oder nicht erforderlich (kein
        SMS-only-Trip bzw. kein Mailversand eingerichtet -- kein Versuch, wie
        bei der Befehlsantwort), ``False`` = Versand gescheitert.
        """
        config = request.report_config
        is_sms_only = config and config.send_sms and not config.send_email
        if not is_sms_only or not self._settings.can_send_email():
            return True
        error_lines = "\n".join(
            "  - " + t("versand.scheduler.abschnitt", self._lang, id=abschnitt_id(e, self._lang))
            + f": {e.error_message}"
            for e in request.failed_segments
            if e.segment is not None
        )
        # Issue #2672: Rumpf, Betreff und X-GZ-Lang in derselben Sprache.
        subject = t("versand.betreff.wetterdaten_fehlen_ascii", self._lang, trip=request.trip.name)
        body = build_service_error_email_html(
            trip_name=request.trip.name,
            report_type=request.report_type,
            error_lines=error_lines,
            lang=self._lang,
        )
        try:
            EmailOutput(self._settings).send(subject=subject, body=body, html=True,
                                             lang=self._lang)
            logger.info(f"Service error email sent for {request.trip.name}")
        except Exception as e:
            logger.error(f"Failed to send service error email: {e}")
            return False
        return True
