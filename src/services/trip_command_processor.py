"""
Channel-agnostic Trip Command Processor.

Processes remote trip commands via `### key: value` syntax from any inbound
channel (Email, SMS). Returns CommandResult with confirmation text for the
caller to send back on the same channel.

SPEC: docs/specs/modules/trip_command_processor.md v2.1
"""
from __future__ import annotations

import dataclasses
import json
import logging
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from app.loader import get_data_dir, get_snapshots_dir, load_all_trips, save_trip
from app.trip import Stage, Trip
from services.trip_day import anchor_tz, display_tz, trip_local_now, trip_local_today
from utils.timezone import UTC, local_dt, local_fmt, local_hour

logger = logging.getLogger(__name__)


def _norm(s: str) -> str:
    """Normalisiert Trip-Namen: Leerzeichen↔Unterstrich, Mehrfach-WS, lowercase."""
    return re.sub(r"\s+", " ", s.replace("_", " ")).strip().lower()


# ---------------------------------------------------------------------------
# DTOs
# ---------------------------------------------------------------------------

@dataclass
class InboundMessage:
    """Channel-agnostic inbound command DTO."""
    trip_name: str
    body: str
    sender: str
    channel: str            # "email" or "sms"
    received_at: datetime
    user_id: str = "default"


@dataclass
class StageShift:
    """Single stage date shift for confirmation display."""
    stage_name: str
    old_date: date
    new_date: date


@dataclass
class CommandResult:
    """Result of command processing with confirmation text."""
    success: bool
    command: str
    confirmation_subject: str
    confirmation_body: str
    trip_name: Optional[str] = None
    shifts: Optional[list[StageShift]] = None
    reply_markup: Optional[dict] = None
    # Issue #1007: True bei erfolgreichem heute/morgen-On-Demand-Briefing —
    # das Briefing selbst IST die Antwort, keine zusätzliche Bestätigung senden.
    suppress_email_reply: bool = False


# ---------------------------------------------------------------------------
# Command Parsing
# ---------------------------------------------------------------------------

_COMMAND_PATTERN = re.compile(r"^###\s+(\S+?)(?:[:\s]\s*(.+))?$")

_VALID_COMMANDS = {"ruhetag", "report", "startdatum", "abbruch", "status", "hilfe", "now", "weiter", "pause", "skip"}

# Bare-keyword mapping (case-insensitive): keyword → internal key
# Kanalübergreifender Grundbefehlssatz (Issue #731): HEUTE/MORGEN/JETZT/GEWITTER/RUHETAG/STATUS/STOP/WEITER/HILFE/PAUSE/SKIP
_BARE_KEYWORD_MAP = {
    "heute":    "heute",
    "morgen":   "morgen",
    "jetzt":    "now",
    "now":      "now",
    "gewitter": "heute_gewitter",
    "ruhetag":  "ruhetag",
    "status":   "status",
    "stop":     "abbruch",
    "weiter":   "weiter",
    "hilfe":    "hilfe",
    "help":     "hilfe",
    "glance":   "glance",
    "pause":    "pause",
    "skip":     "skip",
}

_PAUSE_DURATION_RE = re.compile(r"^(\d+)\s*([dh]?)$")

_QUERY_KEYS = {"glance", "heute", "morgen", "heute_gewitter",
               "timeline_heute", "timeline_morgen"}

_GLANCE_BUTTONS = {
    "inline_keyboard": [[
        {"text": "📋 Timeline heute", "callback_data": "tl_today"},
        {"text": "📋 Timeline morgen", "callback_data": "tl_tomorrow"},
    ]]
}

_HEUTE_BUTTONS = {
    "inline_keyboard": [
        [
            {"text": "⏱ Stunden", "callback_data": "dd_hours_today"},
            {"text": "⛈ Gewitter", "callback_data": "dd_thunder_today"},
            {"text": "💨 Wind", "callback_data": "dd_wind_today"},
            {"text": "🌧 Regen", "callback_data": "dd_precip_today"},
        ],
        [{"text": "🕐 Timeline", "callback_data": "tl_today"}],
    ]
}

_MORGEN_BUTTONS = {
    "inline_keyboard": [
        [
            {"text": "⏱ Stunden", "callback_data": "dd_hours_tomorrow"},
            {"text": "⛈ Gewitter", "callback_data": "dd_thunder_tomorrow"},
            {"text": "💨 Wind", "callback_data": "dd_wind_tomorrow"},
            {"text": "🌧 Regen", "callback_data": "dd_precip_tomorrow"},
        ],
        [{"text": "🕐 Timeline", "callback_data": "tl_tomorrow"}],
    ]
}

_THUNDER_LABEL = {
    "NONE": "kein",
    # Issue #1474 Adversary-Folgeaudit: LOW fehlte -- fiel auf den
    # Unbekannt-Fallback "?" zurueck, obwohl LOW ein bekannter Wert ist.
    "LOW": "leicht",
    "MED": "mäßig",
    "HIGH": "hoch",
}

# Issue #1001: Aktionen-Bubble-Keyboard (Multi-Bubble-Telegram-Redesign).
# Eigenes Praefix `act_` verhindert Kollision mit den `dd_*`/`tl_*`-Drilldown-
# Callbacks oben. Dispatch der einzelnen Buttons: siehe
# inbound_telegram_reader._CALLBACK_QUERY_MAP.
ACTIONS_BUBBLE_BUTTONS = {
    "inline_keyboard": [
        [
            {"text": "📋 Übersicht", "callback_data": "act_overview"},
            {"text": "⏸ Pause", "callback_data": "act_pause"},
        ],
        [
            {"text": "⏭ Überspringen", "callback_data": "act_skip"},
            {"text": "📊 Spalten", "callback_data": "act_columns"},
        ],
        [{"text": "❓ Hilfe", "callback_data": "act_help"}],
    ]
}

_DRILLDOWN_PATTERN = re.compile(r"^dd_(thunder|wind|precip)_(today|tomorrow)$")
_HOURS_PATTERN = re.compile(r"^dd_hours_(today|tomorrow)$")


def _thunder_fmt(value, *, with_emoji: bool = True) -> str:
    """Formatiert ThunderLevel (Enum oder String nach Roundtrip) als deutsches Label.

    Issue #1222 AC-6: E-Mail/SMS bekommen KEIN Kreis-Emoji (nur das Wort),
    Telegram bleibt byte-identisch mit Emoji.
    """
    # Issue #1474 Adversary-Folgeaudit: LOW fehlte in beiden Karten -- fiel
    # auf "· keine Daten" zurueck, obwohl LOW ein bekannter Wert ist.
    _MAP_EMOJI = {
        "NONE": "⚪ keins", "LOW": "🟢 leicht", "MED": "🟡 mäßig", "HIGH": "🔴 hoch",
    }
    _MAP_PLAIN = {"NONE": "keins", "LOW": "leicht", "MED": "mäßig", "HIGH": "hoch"}
    if value is None:
        return "· keine Daten"
    key = value.value if hasattr(value, "value") else str(value)
    _map = _MAP_EMOJI if with_emoji else _MAP_PLAIN
    return _map.get(key, "· keine Daten")


def _local_midnight(day: date, tz) -> datetime:
    """Mitternacht des Ortstages ``day`` in der Zone ``tz``."""
    return datetime(day.year, day.month, day.day, 0, 0, tzinfo=tz)


def _hours_between(start: datetime, end: datetime) -> float:
    """Echte Stunden zwischen zwei Ortszeitpunkten — Differenz UEBER UTC.

    Issue #1470 Adversary-Fund F002: ein Ortstag hat NICHT immer 24 Stunden.
    Am Sommerzeit-Ende (Europe/Paris 2026-10-25) sind es 25, am Anfang
    (2026-03-29) nur 23. Ein festes ``hours=24`` liess deshalb die Stunde 23
    aus der Tabelle fallen bzw. eine Zeile des Folgetages hereinbluten.

    Die Umrechnung nach UTC ist PFLICHT und kein Zierrat: haben beide
    Zeitpunkte DASSELBE ``tzinfo``-Objekt, ignoriert Python die Zone und
    rechnet auf den naiven Werten — dann kommt an JEDEM Tag 24.0 heraus, auch
    an den Wechseltagen. Gemessen: naive Subtraktion 24.0/24.0/24.0, ueber UTC
    23.0/25.0/24.0 fuer den 29.03./25.10./21.08.2026.

    Rueckgabe bewusst ``float``: Zonen mit halbstuendigem Wechsel (z.B.
    Lord Howe Island, 30 Minuten) ergeben 23.5 — ein ``int`` wuerde das
    stillschweigend abschneiden.

    Die Umrechnung laeuft ueber ``local_dt`` (den EINEN Naiv-Guard aus
    ``utils.timezone``), nicht ueber ein rohes ``.astimezone`` — so wie es der
    Zeitzonen-Waechter fuer diese Datei verlangt.
    """
    return (
        local_dt(end, UTC) - local_dt(start, UTC)
    ).total_seconds() / 3600


def _num_fmt(unit: str):
    """Gibt einen Formatter zurück der numerische Werte mit Einheit formatiert."""
    def _fmt(value, *, with_emoji: bool = True) -> str:
        if value is None:
            return "· keine Daten"
        if unit == "km/h":
            return f"{round(float(value))} km/h"
        return f"{float(value):.1f} {unit}"
    return _fmt


_DRILLDOWN_METRICS: dict[str, tuple] = {
    "thunder": ("thunder_level", "⛈️ Gewitter", _thunder_fmt),
    "wind":    ("wind10m_kmh",   "💨 Wind",      _num_fmt("km/h")),
    "precip":  ("precip_1h_mm",  "🌧 Niederschlag", _num_fmt("mm")),
}


# ---------------------------------------------------------------------------
# Issue #1007 Adversary-Fix F002: reine Mapping-Funktion Outcome → Antworttext
# (mock-frei testbar, keine Seiteneffekte).
# ---------------------------------------------------------------------------

def _on_demand_failure_body(outcome: str, label: str, target_date: date) -> str:
    """Formatiert den Antworttext für einen nicht-erfolgreichen On-Demand-Versand.

    outcome: "no_stage" | "no_weather" | "no_channels" | "channels_unreachable"
    (alles außer "sent").
    """
    human_date = f"{target_date:%d.%m.%Y}"
    if outcome == "no_weather":
        return (
            f"{label} ({human_date}): Wetterdaten aktuell nicht verfügbar — "
            "bitte später erneut versuchen."
        )
    if outcome == "no_channels":
        return (
            "Keine Versandkanäle für diesen Trip aktiv — Briefing nicht "
            "gesendet. Kanäle im Trip-Editor aktivieren."
        )
    # Issue #1403 AC-4: Versandweg konfiguriert, aber technisch nicht
    # erreichbar (z.B. Telegram ohne gültige Bot-Verbindung) — eigene
    # Meldung, damit sie sich nicht mit "no_channels" (Konfiguration)
    # verwechseln lässt.
    if outcome == "channels_unreachable":
        return (
            "Versandweg für diesen Trip konfiguriert, aber nicht erreichbar "
            "— Briefing nicht gesendet. Verbindung prüfen."
        )
    # "no_stage" (Default/Fallback)
    return f"{label} ({human_date}): Keine Etappe geplant"


# ---------------------------------------------------------------------------
# On-demand Fetch Helper (AC-5: cache-check before fetch)
# ---------------------------------------------------------------------------

def _fetch_and_save_snapshot(trip, user_id: str, today, tomorrow) -> None:
    """Fetcht Wetterdaten on-demand und speichert als Snapshot. Fail-soft.

    Cache-Check: existiert bereits ein Snapshot mit target_date == heute,
    wird kein neuer Fetch ausgelöst. Verhindert redundante API-Calls.
    """
    from app.loader import get_snapshots_dir
    from services.weather_snapshot import WeatherSnapshotService
    from services.trip_report_scheduler import TripReportSchedulerService

    # Cache-Check: rohe JSON-Datei prüfen (load() gibt keine target_date zurück)
    snap_path = get_snapshots_dir(user_id) / f"{trip.id}.json"
    if snap_path.exists():
        try:
            import json as _json
            raw = _json.loads(snap_path.read_text(encoding="utf-8"))
            if raw.get("target_date") == today.isoformat():
                return  # Frischer Snapshot vorhanden — kein Re-Fetch
        except Exception:
            pass  # Im Zweifel: Fetch trotzdem versuchen

    try:
        scheduler = TripReportSchedulerService(user_id=user_id)
        segments = scheduler._convert_trip_to_segments(trip, today)
        segments_tomorrow = scheduler._convert_trip_to_segments(trip, tomorrow)
        all_segments = segments + segments_tomorrow
        if not all_segments:
            return
        segment_weather = scheduler._fetch_weather(all_segments)
        if segment_weather:
            WeatherSnapshotService(user_id).save(trip.id, segment_weather, today)
    except Exception as exc:
        logger.warning("on-demand fetch fehlgeschlagen für trip %s: %s", trip.id, exc)


# ---------------------------------------------------------------------------
# Processor
# ---------------------------------------------------------------------------

class TripCommandProcessor:
    """Processes trip commands from any inbound channel."""

    def process(self, msg: InboundMessage) -> CommandResult:
        """Parse, validate, and execute a trip command."""
        # 1. Parse command
        key, value = self._parse_command(msg.body)

        if key is None:
            return CommandResult(
                success=False, command="unknown",
                confirmation_subject="Unbekannter Befehl",
                confirmation_body=(
                    "Befehlsformat: ### key: value\n"
                    "Verfuegbar: ruhetag, report, startdatum, abbruch, status, hilfe"
                ),
                trip_name=msg.trip_name,
            )

        # Hours-Drilldown: dd_hours_<day> — direkt ODER via key
        actual_hours_token = None
        if _HOURS_PATTERN.match(key):
            actual_hours_token = key
        elif key == "query" and value and _HOURS_PATTERN.match(value.lower()):
            actual_hours_token = value.lower()

        if actual_hours_token is not None:
            hm = _HOURS_PATTERN.match(actual_hours_token)
            day_token = hm.group(1)
            trip = self._find_trip(msg.trip_name, msg.user_id)
            if not trip:
                return CommandResult(
                    success=False, command=actual_hours_token,
                    confirmation_subject=f"[{msg.trip_name}] Trip nicht gefunden",
                    confirmation_body=f"Kein Trip mit Name '{msg.trip_name}' gefunden.",
                    trip_name=msg.trip_name,
                )
            return self._handle_hours_drilldown(
                trip, day_token, msg.received_at, msg.user_id, msg.channel
            )

        # Drilldown-Tokens: dd_<metric>_<day> — via "### query: dd_..." ODER direkt
        actual_drilldown_token = None
        if key == "query" and value and _DRILLDOWN_PATTERN.match(value.lower()):
            actual_drilldown_token = value.lower()
        elif _DRILLDOWN_PATTERN.match(key):
            actual_drilldown_token = key

        if actual_drilldown_token is not None:
            m = _DRILLDOWN_PATTERN.match(actual_drilldown_token)
            metric, day_token = m.group(1), m.group(2)
            trip = self._find_trip(msg.trip_name, msg.user_id)
            if not trip:
                return CommandResult(
                    success=False, command=actual_drilldown_token,
                    confirmation_subject=f"[{msg.trip_name}] Trip nicht gefunden",
                    confirmation_body=f"Kein Trip mit Name '{msg.trip_name}' gefunden.",
                    trip_name=msg.trip_name,
                )
            return self._handle_drilldown(
                trip, metric, day_token, msg.received_at, msg.user_id, msg.channel
            )

        # Query-Keys: key=="query" mit value als Query-Key ODER direkter Query-Key
        actual_query_key = None
        if key == "query" and value and value.lower() in _QUERY_KEYS:
            actual_query_key = value.lower()
        elif key in _QUERY_KEYS:
            actual_query_key = key

        if actual_query_key is not None:
            trip = self._find_trip(msg.trip_name, msg.user_id)
            if not trip:
                return CommandResult(
                    success=False, command=actual_query_key,
                    confirmation_subject=f"[{msg.trip_name}] Trip nicht gefunden",
                    confirmation_body=f"Kein Trip mit Name '{msg.trip_name}' gefunden.",
                    trip_name=msg.trip_name,
                    reply_markup=_GLANCE_BUTTONS,
                )
            return self._handle_query(trip, actual_query_key, msg.received_at, msg.user_id)

        # hilfe braucht keinen Trip-Lookup
        if key == "hilfe":
            return self._show_help()

        # Issue #1001 Adversary-Finding F002: "columns" (Aktionen-Bubble-Button
        # "📊 Spalten") braucht ebenfalls keinen Trip-Lookup — Spalten-Konfiguration
        # ist ausschliesslich ein Frontend-Trip-Editor-Flow (siehe Spec Known
        # Limitations), aber statt eines stillen Nichts-Tuns bekommt der Nutzer
        # jetzt einen informativen Hinweis.
        if key == "columns":
            return self._show_columns_info()

        if key not in _VALID_COMMANDS:
            return CommandResult(
                success=False, command=key,
                confirmation_subject=f"[{msg.trip_name}] Unbekannter Befehl",
                confirmation_body=(
                    f"'{key}' ist kein gueltiger Befehl.\n"
                    "Verfuegbar: ruhetag, report, startdatum, abbruch, status, hilfe"
                ),
                trip_name=msg.trip_name,
            )

        # 2. Lookup trip
        trip = self._find_trip(msg.trip_name, msg.user_id)
        if not trip:
            return CommandResult(
                success=False, command=key,
                confirmation_subject=f"[{msg.trip_name}] Trip nicht gefunden",
                confirmation_body=f"Kein Trip mit Name '{msg.trip_name}' gefunden.",
                trip_name=msg.trip_name,
            )

        # 3. Dispatch
        # Issue #1727 S5a (ADR-0044): "heute" ist der ORTStag DIESER Tour, nicht
        # der Weltzeit-Tag der Nachricht. Im Mismatch-Fenster (00:30 Ortszeit auf
        # Korsika = 22:30 UTC des Vortages) trug `command_date` sonst den Vortag
        # -- `### ruhetag` verschob dann die heutige Etappe mit.
        command_date = trip_local_today(trip, msg.received_at)
        if key == "ruhetag":
            return self._apply_ruhetag(trip, value, command_date, msg.user_id)
        elif key == "report":
            return self._trigger_report(trip, value, msg.user_id)
        elif key == "startdatum":
            return self._shift_start(trip, value, msg.user_id)
        elif key == "abbruch":
            return self._cancel_trip(trip, msg.user_id)
        elif key == "status":
            return self._show_status(trip, msg.received_at)
        elif key == "now":
            return self._show_now(trip, msg.received_at)
        elif key == "weiter":
            return self._resume_trip(trip, msg.user_id)
        elif key == "pause":
            return self._apply_pause(trip, value, msg.user_id)
        elif key == "skip":
            return self._apply_skip(trip, msg.user_id)

        # Should not reach here due to whitelist check above
        return CommandResult(
            success=False, command=key,
            confirmation_subject="Fehler",
            confirmation_body="Interner Fehler.",
        )

    def _parse_command(self, body: str) -> tuple[Optional[str], Optional[str]]:
        """Parse first non-blank line for ### key: value OR bare KEYWORD format."""
        first_line = next(
            (line.strip() for line in body.splitlines() if line.strip()),
            "",
        )
        # ###-Pfad hat Vorrang
        match = _COMMAND_PATTERN.match(first_line)
        if match:
            return match.group(1).lower(), (match.group(2) or "").strip() or None
        # Bare-keyword: erstes Token (case-insensitiv), Rest = value
        parts = first_line.split(None, 1)
        if parts:
            keyword = parts[0].lower()
            internal = _BARE_KEYWORD_MAP.get(keyword)
            if internal is not None:
                rest = parts[1].strip() if len(parts) > 1 else None
                return internal, rest or None
        return None, None

    def _find_trip(self, trip_name: str, user_id: str = "default") -> Optional[Trip]:
        """Trip-Lookup: primär über GZ#-Shortcode, Fallback toleranter Namensvergleich."""
        trips = load_all_trips(user_id)
        first_token = trip_name.split()[0].upper() if trip_name.strip() else ""
        if first_token.startswith("GZ#"):
            for trip in trips:
                if trip.shortcode.upper() == first_token:
                    return trip
        query = _norm(trip_name)
        for trip in trips:
            if _norm(trip.name) == query:
                return trip
        logger.warning(f"No trip found for name: {trip_name!r} (user: {user_id!r})")
        return None

    # -----------------------------------------------------------------------
    # Query (read-only) — no save_trip, no _append_command_log, no _delete_snapshot
    # -----------------------------------------------------------------------

    def _handle_query(
        self, trip: Trip, query_key: str, received_at: datetime, user_id: str,
    ) -> CommandResult:
        """Dispatch read-only query. Never mutates trip state.

        Fix #1795 (ADR-0044): "heute"/"morgen" folgen dem ORTStag der Tour,
        nicht dem UTC-Tag von ``received_at`` — EINE Auflösung
        (``trip_local_now``), aus der Tag UND (via ``display_tz``, je Tag
        seine eigene Zone, AC-4) die Anzeige-Zonen hervorgehen. Alle
        Formatierer bekommen ``tz`` als Pflichtparameter durchgereicht
        (Docstring-Begründung: siehe ``_format_drilldown``) — ein Default
        würde die Ortszeit wieder still gegen die Prozess-Zeitzone tauschen.
        """
        local_now = trip_local_now(trip, received_at)
        today = local_now.date()
        tomorrow = today + timedelta(days=1)
        tz_heute = display_tz(trip, today)
        tz_morgen = display_tz(trip, tomorrow)

        # Issue #1007: heute/morgen lösen das volle Tages-Briefing aus (kein
        # Einzeiler-Aggregat mehr) — eigener Zweig VOR dem Timeline-Setup, da
        # der Scheduler die Wetterdaten selbst holt (keine WeatherExtractor-
        # Timeline nötig).
        if query_key == "heute":
            return self._trigger_on_demand(trip, "morning", "Heute", user_id)
        elif query_key == "morgen":
            return self._trigger_on_demand(trip, "evening", "Morgen", user_id)

        from services.weather_extractor import WeatherExtractor
        extractor = WeatherExtractor(user_id=user_id)
        timeline = extractor.timeline(trip.id)

        if not timeline.available:
            _fetch_and_save_snapshot(trip=trip, user_id=user_id, today=today, tomorrow=tomorrow)
            timeline = extractor.timeline(trip.id)

        if query_key == "glance":
            body = self._fmt_glance(timeline, today, tomorrow, tz_heute, tz_morgen)
            return CommandResult(
                success=True, command="glance",
                confirmation_subject=f"[{trip.name}] Glance",
                confirmation_body=body,
                trip_name=trip.name,
                reply_markup=_GLANCE_BUTTONS,
            )
        elif query_key == "heute_gewitter":
            body = self._fmt_gewitter(timeline, today, tz_heute)
            return CommandResult(
                success=True, command="heute_gewitter",
                confirmation_subject=f"[{trip.name}] Gewitter heute",
                confirmation_body=body,
                trip_name=trip.name,
            )
        elif query_key == "timeline_heute":
            body = self._fmt_timeline(timeline, today, "Heute", "today", tz_heute)
            return CommandResult(
                success=True, command="timeline_heute",
                confirmation_subject=f"[{trip.name}] Timeline heute",
                confirmation_body=body,
                trip_name=trip.name,
                reply_markup=self._timeline_buttons(timeline, today, "today", tz_heute),
            )
        elif query_key == "timeline_morgen":
            body = self._fmt_timeline(timeline, tomorrow, "Morgen", "tomorrow", tz_morgen)
            return CommandResult(
                success=True, command="timeline_morgen",
                confirmation_subject=f"[{trip.name}] Timeline morgen",
                confirmation_body=body,
                trip_name=trip.name,
                reply_markup=self._timeline_buttons(timeline, tomorrow, "tomorrow", tz_morgen),
            )
        # Fallback (should not reach)
        return CommandResult(
            success=False, command=query_key,
            confirmation_subject="Fehler",
            confirmation_body="Unbekannter Query-Key.",
            trip_name=trip.name,
        )

    def _trigger_on_demand(
        self, trip: Trip, report_type: str, label: str, user_id: str,
    ) -> CommandResult:
        """Issue #1007: heute/morgen lösen das volle Tages-Briefing aus statt
        des bisherigen Einzeiler-Aggregats. Wiederverwendung des On-Demand-
        Versandpfads (#768-Test-Pfad-Semantik, aber ohne Etappen-Fallback und
        ohne [TEST]-Präfix). Adversary-Fix F001/F002: `send_on_demand_report`
        liefert ein Outcome ("sent"/"no_stage"/"no_weather"/"no_channels")
        statt eines bloßen bool — nur "sent" unterdrückt die Bestätigung.

        Fix #1795 AC-7: der Fehlertext nennt den TATSAECHLICH von
        `send_on_demand_report` benutzten Zieltag (`OnDemandErgebnis.zieltag`)
        — kein eigener, im Aufrufer aus `received_at` geratener `target_date`
        mehr (Nebengewinn: der Parameter entfaellt hier ersatzlos).
        """
        from services.trip_report_scheduler import TripReportSchedulerService
        query_key = "heute" if report_type == "morning" else "morgen"
        buttons = _HEUTE_BUTTONS if report_type == "morning" else _MORGEN_BUTTONS
        service = TripReportSchedulerService(user_id=user_id)
        ergebnis = service.send_on_demand_report(trip, report_type)
        if ergebnis.outcome != "sent":
            return CommandResult(
                success=True, command=query_key,
                confirmation_subject=f"[{trip.name}] {label}",
                confirmation_body=_on_demand_failure_body(
                    ergebnis.outcome, label, ergebnis.zieltag,
                ),
                trip_name=trip.name,
                reply_markup=buttons,
            )
        return CommandResult(
            success=True, command=query_key,
            confirmation_subject=f"[{trip.name}] {label}",
            confirmation_body=f"{label}-Briefing wird gesendet.",
            trip_name=trip.name,
            reply_markup=buttons,
            suppress_email_reply=True,
        )

    # -----------------------------------------------------------------------
    # Drilldown (read-only) — stündliche Einzelmetrik-Liste
    # -----------------------------------------------------------------------

    def _handle_drilldown(
        self,
        trip: Trip,
        metric: str,
        day_token: str,
        received_at: datetime,
        user_id: str,
        channel: str = "telegram",
    ) -> CommandResult:
        """Stündliche Drilldown-Liste für eine Metrik (thunder/wind/precip).

        Issue #1222 AC-6: `channel` steuert Emoji-Darstellung — Telegram
        behält Kreis-Emojis, E-Mail/SMS bekommen nur das Wort.
        """
        with_emoji = channel == "telegram"
        from services.weather_extractor import WeatherExtractor
        field, header, fmt = _DRILLDOWN_METRICS[metric]

        from_time, hours, day_date, tz = self._day_window(trip, day_token, received_at)

        extractor = WeatherExtractor(user_id)
        res = extractor.drilldown(
            trip.id, field, from_time=from_time, hours=hours
        )
        # Issue #1475 Nachbesserung (Punkt 6/AC-9): fuer den Gewitter-Drilldown
        # wird DIESELBE, unveraenderte (bereits metrik-generische) Methode ein
        # zweites Mal gerufen — mit `hail_flag`. Der Merge geschieht ueber den
        # Zeitstempel, weil beide Abrufe denselben Trip und dasselbe Zeitfenster
        # betreffen. Die Gewitterstufe selbst wird davon nie veraendert (AC-10).
        hail_by_ts: dict = {}
        if field == "thunder_level":
            hail_res = extractor.drilldown(
                trip.id, "hail_flag", from_time=from_time, hours=hours,
            )
            if hail_res.available:
                hail_by_ts = {pt.ts: pt.value for pt in hail_res.points}
        if not res.available:
            return CommandResult(
                success=False,
                command=f"dd_{metric}_{day_token}",
                confirmation_subject=f"[{trip.name}] Keine stündlichen Daten",
                confirmation_body=(
                    "Keine stündlichen Daten verfügbar. "
                    "Bitte einen Report anfordern um aktuelle Daten zu laden."
                ),
                trip_name=trip.name,
            )

        body = self._format_drilldown(
            res, header, fmt, tz, with_emoji=with_emoji, hail_by_ts=hail_by_ts,
        )
        back = "tl_today" if day_token == "today" else "tl_tomorrow"
        markup = {"inline_keyboard": [[{"text": "⬅️ Zurück", "callback_data": back}]]}
        return CommandResult(
            success=True,
            command=f"dd_{metric}_{day_token}",
            confirmation_subject=f"[{trip.name}] {header} stündlich",
            confirmation_body=body,
            reply_markup=markup,
            trip_name=trip.name,
        )

    def _handle_hours_drilldown(
        self,
        trip: Trip,
        day_token: str,
        received_at: datetime,
        user_id: str,
        channel: str = "telegram",
    ) -> CommandResult:
        """Stündliche Kompakttabelle: Zeit | Temp | Wind | Regen | Gewitter.

        Issue #1222 AC-6: `channel` steuert die Gewitter-Symbol-Spalte —
        Telegram behält Kreis-Emojis, E-Mail/SMS bekommen nur das Wort.
        """
        with_emoji = channel == "telegram"
        from services.weather_extractor import WeatherExtractor

        from_time, hours, today_date, tz = self._day_window(trip, day_token, received_at)
        if day_token == "today":
            back_btn, back_cb, label = "⬅️ /heute", "heute", "Heute"
        else:
            back_btn, back_cb, label = "⬅️ /morgen", "morgen", "Morgen"

        ex = WeatherExtractor(user_id)
        r_temp  = ex.drilldown(trip.id, "t2m_c",        from_time=from_time, hours=hours)
        r_wind  = ex.drilldown(trip.id, "wind10m_kmh",  from_time=from_time, hours=hours)
        r_rain  = ex.drilldown(trip.id, "precip_1h_mm", from_time=from_time, hours=hours)
        r_thund = ex.drilldown(trip.id, "thunder_level", from_time=from_time, hours=hours)

        if not r_temp.available:
            return CommandResult(
                success=False,
                command=f"dd_hours_{day_token}",
                confirmation_subject=f"[{trip.name}] Keine stündlichen Daten",
                confirmation_body=(
                    "Keine stündlichen Daten verfügbar. "
                    "Bitte einen Report anfordern um aktuelle Daten zu laden."
                ),
                trip_name=trip.name,
            )

        wind_map  = {p.ts: p.value for p in r_wind.points}  if r_wind.available  else {}
        rain_map  = {p.ts: p.value for p in r_rain.points}  if r_rain.available  else {}
        thund_map = {p.ts: p.value for p in r_thund.points} if r_thund.available else {}

        lines = [f"📅 Stunden · {label} ({today_date:%d.%m})", ""]
        for pt in r_temp.points:
            h = f"{local_hour(pt.ts, tz):02d}"
            temp = f"{pt.value:.0f}°C" if pt.value is not None else "?°C"
            wind_val = wind_map.get(pt.ts)
            wind = f"{wind_val:.0f}km/h" if wind_val is not None else "?"
            rain_val = rain_map.get(pt.ts)
            rain = f"{rain_val:.1f}mm" if rain_val is not None else "?"
            thund_val = thund_map.get(pt.ts)
            if thund_val is None or str(thund_val) in ("NONE", "ThunderLevel.NONE"):
                t_sym = "—"
            # Issue #1474 Adversary-Folgeaudit: LOW fiel bisher mangels
            # eigenem Zweig in den ELSE-Fall und wurde faelschlich als
            # starkes Gewitter (🔴/hoch) angezeigt.
            elif str(thund_val) in ("LOW", "ThunderLevel.LOW"):
                t_sym = "🟢" if with_emoji else "leicht"
            elif str(thund_val) in ("MED", "ThunderLevel.MED"):
                t_sym = "🟡" if with_emoji else "mäßig"
            else:
                t_sym = "🔴" if with_emoji else "hoch"
            lines.append(f"{h}  {temp:<7} {wind:<8} {rain:<6} {t_sym}")

        markup = {"inline_keyboard": [[{"text": back_btn, "callback_data": back_cb}]]}
        return CommandResult(
            success=True,
            command=f"dd_hours_{day_token}",
            confirmation_subject=f"[{trip.name}] Stunden {label}",
            confirmation_body="\n".join(lines),
            reply_markup=markup,
            trip_name=trip.name,
        )

    def _day_window(self, trip: Trip, day_token: str, received_at: datetime):
        """Tagesfenster fuer "heute"/"morgen" — in der ORTSzeit der Tour.

        Issue #1470 (PO-Entscheidung "Ja, Ortszeit."): vorher hingen BEIDE
        Zweige an der Weltzeit. ``received_at`` traegt immer UTC (beide
        Inbound-Reader setzen ``datetime.now(tz=timezone.utc)``) — auf Korsika
        begann "morgen" dadurch um 02:00 Ortszeit, und zwischen Orts- und
        Weltzeit-Mitternacht trug "heute" das Datum von GESTERN.

        Das Morgen-Fenster reicht von Ortsmitternacht bis zur NAECHSTEN
        Ortsmitternacht — nicht feste 24 Stunden (Adversary-Fund F002, s.
        ``_hours_between``). "Heute" bleibt bewusst bei 12 Stunden: das ist
        eine DAUER ab jetzt ("die naechsten 12 Stunden") und keine
        Kalendertags-Grenze; eine Dauer ist sommerzeit-immun, wenn sie in UTC
        addiert wird. Sie an der Ortsmitternacht zu kappen wuerde die Vorschau
        kurz vor Mitternacht still auf Minuten zusammenschrumpfen — eine
        Produktaenderung, die niemand bestellt hat.

        Reihenfolge-Falle: ``display_tz(trip, day_date)`` braucht den Tag,
        aber welcher Tag "heute" ist, entscheidet erst die Zone. Aufgeloest in
        zwei Schritten (``services.trip_day``, #1697 — verschoben aus #1470,
        Verhalten bit-identisch) — die Zone des WELTZEIT-Tages (``anchor_tz``)
        bestimmt den Kalendertag, die etappengenaue Zone genau dieses Tages
        danach Fensterbeginn UND Beschriftung. ``tz`` wird ZURUECKGEGEBEN und
        vom Aufrufer durchgereicht, nicht dort ein zweites Mal geholt: so
        koennen Fenstergrenze und Uhrzeitspalte konstruktiv nicht
        auseinanderlaufen (AC-4).

        Rueckgabe: ``(from_time, hours, day_date, tz)``.
        """
        local_now = local_dt(received_at, anchor_tz(trip, received_at))
        if day_token == "today":
            day_date = local_now.date()
            return received_at, 12, day_date, display_tz(trip, day_date)
        day_date = (local_now + timedelta(days=1)).date()
        next_date = day_date + timedelta(days=1)
        tz = display_tz(trip, day_date)
        from_time = _local_midnight(day_date, tz)
        hours = _hours_between(from_time, _local_midnight(next_date, tz))
        return from_time, hours, day_date, tz

    def _format_drilldown(
        self, res, header: str, fmt, tz, with_emoji: bool = True,
        hail_by_ts: Optional[dict] = None,
    ) -> str:
        """Formatiert DrilldownResult als stündliche Liste.

        ``tz`` ist Pflicht (Issue #1402): ein Default wuerde die Ortszeit
        wieder still gegen die Prozess-Zeitzone tauschen.

        Issue #1475 Nachbesserung (Punkt 6): ``hail_by_ts`` ordnet je Zeitpunkt
        das Hagel-Kennzeichen zu. Nur bei bestaetigtem Hagel (``True``) haengt
        der deskriptive Zusatz an — Stunden mit ``None``/``False`` bleiben
        zeichengleich (kein unbedingtes Anhaengen, ADR-0007 kein Rat).
        """
        from output.metric_format import format_hail_note

        hail_by_ts = hail_by_ts or {}
        lines = [f"{header} — stündlich"]
        for pt in res.points:
            time_str = local_fmt(pt.ts, tz)
            line = f"{time_str}  {fmt(pt.value, with_emoji=with_emoji)}"
            note = format_hail_note(hail_by_ts.get(pt.ts))
            if note:
                line = f"{line} · {note}"
            lines.append(line)
        return "\n".join(lines)

    def _aggregate_day(self, timeline, target_date, tz) -> Optional[dict]:
        """Aggregiere Timeline-Punkte für target_date. None wenn keine Punkte.

        Fix #1795: der Filter vergleicht den ORTStag des Wegpunkts
        (``local_dt(p.arrival_time, tz).date()``), nicht mehr den rohen
        UTC-Tag von ``arrival_time`` — ``tz`` ist Pflichtparameter, s.
        ``_handle_query``.
        """
        from app.models import ThunderLevel as TL
        from output.metric_format import thunder_ordinal
        points = [p for p in timeline.points if local_dt(p.arrival_time, tz).date() == target_date]
        if not points:
            return None
        temp_max = max((p.metrics.temp_max_c for p in points if p.metrics.temp_max_c is not None), default=None)
        temp_min = min((p.metrics.temp_min_c for p in points if p.metrics.temp_min_c is not None), default=None)
        wind_max = max((p.metrics.wind_max_kmh for p in points if p.metrics.wind_max_kmh is not None), default=None)
        # Issue #1474 Adversary-Folgeaudit: die vormals lokale
        # {NONE,MED,HIGH}-Liste kannte LOW nicht -- .index() warf ValueError.
        # thunder_ordinal() ist die geteilte Sortier-Skala.
        thunder_vals = [p.metrics.thunder_level_max for p in points if p.metrics.thunder_level_max is not None]
        thunder = max(thunder_vals, key=thunder_ordinal) if thunder_vals else TL.NONE
        precip = sum(p.metrics.precip_sum_mm for p in points if p.metrics.precip_sum_mm is not None)
        pop = max((p.metrics.pop_max_pct for p in points if p.metrics.pop_max_pct is not None), default=None)
        # Issue #1475 S5a: Hagel-Kennzeichen ueber dieselbe Prioritaetsregel
        # (ja > unbekannt > nein) wie die Tages-/Etappen-Aggregation -- die
        # ROHEN Werte inkl. `None` ("unbekannt"), kein Vorfiltern.
        from output.metric_format import hail_priority
        hail_flag = hail_priority(
            [getattr(p.metrics, "hail_flag", None) for p in points]
        )
        # Issue #1680 S2: die Zutaten, die die oben gebildete Tagesstufe
        # tragen -- ueber DIESELBE, nach `target_date` gefilterte Wegpunkt-
        # liste (Stufe und Herkunft aus EINER Rechnung, Spec D6). Der geteilte
        # Helfer statt einer dritten Eigenimplementierung derselben Regel
        # (#1480). Issue #1680 S3: `_fmt_day_agg()`/GLANCE liest den Schluessel
        # jetzt EBENFALLS (Spec D3) -- der Scheibe-2-Entscheid "GLANCE bleibt
        # bewusst zeichengleich" (dortige D3, Known Limitation 4) ist mit
        # PO-Entscheid vom 2026-08-13 abgeloest. Verbraucher sind damit
        # `_fmt_gewitter()` UND `_fmt_day_agg()`.
        from output.metric_format import union_of_max_carriers
        thunder_signals = union_of_max_carriers(
            [(p.metrics.thunder_level_max,
              getattr(p.metrics, "thunder_level_max_signals", None))
             for p in points]
        )
        return {"temp_max": temp_max, "temp_min": temp_min, "wind_max": wind_max,
                "thunder": thunder, "precip": precip, "pop": pop,
                "hail_flag": hail_flag, "thunder_signals": thunder_signals}

    def _fmt_day_agg(self, agg: dict, label: str) -> str:
        """Formatiert Tages-Aggregat als kompakte Zeile."""
        t_max = f"{agg['temp_max']:.0f}" if agg['temp_max'] is not None else "?"
        t_min = f"{agg['temp_min']:.0f}" if agg['temp_min'] is not None else "?"
        wind = f"{agg['wind_max']:.0f}" if agg['wind_max'] is not None else "?"
        thunder_label = _THUNDER_LABEL.get(agg['thunder'].value if agg['thunder'] else "NONE", "?")
        # Issue #1680 S3 (Spec D3, abgeloeste Entscheidung): die tragende(n)
        # Zutat(en) der oben gezeigten Tagesstufe -- aus DEMSELBEN Aggregat,
        # das auch `agg['thunder']` traegt (`_aggregate_day()`, EINE Rechnung
        # ueber die nach `target_date` gefilterte Wegpunktliste, AC-11). Ohne
        # Traeger (kein Gewitter, Alt-Schnappschuss ohne das Feld) bleibt die
        # Zeile zeichengleich zu bisher (AC-16). Denselben Schluessel und
        # denselben Textbaustein nutzt `_fmt_gewitter()` -- keine zweite
        # Formulierung. KANAL: GLANCE erreicht ausschliesslich E-Mail und
        # Telegram (`InboundMessage` hat genau diese zwei Erzeuger); einen
        # SMS-/Premium-SMS-Kommandopfad gibt es nicht, die PO-Abwahl "SMS ohne
        # Herkunft" greift hier strukturell.
        from output.metric_format import thunder_signal_label
        _traeger = agg.get("thunder_signals")
        _herkunft = ", ".join(thunder_signal_label(n) for n in _traeger or [])
        if _herkunft:
            thunder_label = f"{thunder_label} · {_herkunft}"
        precip = f"{agg['precip']:.1f}" if agg.get('precip') else "0.0"
        return (
            f"{label}: 🌡 {t_min}–{t_max}°C  💨 {wind} km/h  "
            f"🌧 {precip}mm  ⛈ Gewitter: {thunder_label}"
        )

    def _fmt_glance(self, timeline, today, tomorrow, tz_heute, tz_morgen) -> str:
        """Fix #1795 AC-4: je Tag die Zone SEINER EIGENEN Etappe — ``tz_heute``
        für ``today``, ``tz_morgen`` für ``tomorrow`` (nicht eine gemeinsame
        Zone für beide Tage)."""
        if not timeline.available:
            return (
                "Kein Wetter-Snapshot verfügbar. "
                "Bitte einen Report anfordern um aktuelle Daten zu laden."
            )
        agg_heute = self._aggregate_day(timeline, today, tz_heute)
        agg_morgen = self._aggregate_day(timeline, tomorrow, tz_morgen)
        lines = ["🗓 Glance — heute & morgen", ""]
        if agg_heute:
            lines.append(self._fmt_day_agg(agg_heute, f"heute ({today:%d.%m})"))
        else:
            lines.append(f"heute ({today:%d.%m}): Keine Etappe geplant")
        if agg_morgen:
            lines.append(self._fmt_day_agg(agg_morgen, f"morgen ({tomorrow:%d.%m})"))
        else:
            lines.append(f"morgen ({tomorrow:%d.%m}): Keine Etappe geplant")
        return "\n".join(lines)

    def _fmt_gewitter(self, timeline, today, tz) -> str:
        if not timeline.available:
            return (
                "Kein Wetter-Snapshot verfügbar. "
                "Bitte einen Report anfordern um aktuelle Daten zu laden."
            )
        agg = self._aggregate_day(timeline, today, tz)
        if not agg:
            return f"Heute ({today:%d.%m}): Keine Etappe geplant — kein Gewitter-Status."
        thunder = agg["thunder"]
        label = _THUNDER_LABEL.get(thunder.value if thunder else "NONE", "?")
        # Issue #1475 S5a: derselbe geteilte Textbaustein wie in den Mail-
        # Renderern (#1481 DRY, call-time Import) -- rein deskriptiv NEBEN der
        # Gewitterstufe, ohne Handlungsempfehlung (ADR-0007, Spec AC-8). Bei
        # "unbekannt"/"nein" bleibt die Antwort zeichengleich zu bisher.
        from output.metric_format import format_hail_note, thunder_signal_label
        hail_note = format_hail_note(agg.get("hail_flag"))
        suffix = f" · {hail_note}" if hail_note else ""
        # Issue #1680 S2: die tragende(n) Zutat(en) der oben gezeigten Stufe --
        # additiv VOR dem Hagel-Suffix, rein deskriptiv ohne Bewertung
        # (ADR-0007). Ohne Traeger (kein Gewitter, Alt-Schnappschuss ohne das
        # Feld) bleibt die Zeile zeichengleich zu bisher.
        # KANAL: das GEWITTER-Kommando erreicht ausschliesslich E-Mail und
        # Telegram -- `InboundMessage` hat genau diese zwei Erzeuger
        # (inbound_email_reader.py, inbound_telegram_reader.py). Es gibt keinen
        # SMS-/Premium-SMS-Kommandopfad, die PO-Abwahl "SMS ohne Herkunft"
        # greift hier also strukturell, ohne Kanal-Unterscheidung.
        traeger = agg.get("thunder_signals")
        herkunft = ", ".join(thunder_signal_label(n) for n in traeger or [])
        if herkunft:
            suffix = f" · {herkunft}{suffix}"
        return f"⛈ Gewitter heute ({today:%d.%m}): {label}{suffix}"

    def _fmt_timeline(self, timeline, target_date, label: str, day_token: str, tz) -> str:
        """Vertikale Timeline: pro Wegpunkt zwei Zeilen (Zeit/Höhe + Metriken).

        Fix #1795: sowohl der Tagesfilter (``local_dt(...).date()``, AC-3) als
        auch die 🕐-Uhrzeit (``local_fmt``, AC-1/AC-5) laufen über die
        durchgereichte Ortszone — kein rohes ``arrival_time.date()``/
        ``:%H:%M`` auf dem UTC-Zeitstempel mehr.
        """
        if not timeline.available:
            return (
                "Kein Wetter-Snapshot verfügbar. "
                "Bitte einen Report anfordern um aktuelle Wetterdaten zu laden."
            )
        pts = sorted(
            [p for p in timeline.points if local_dt(p.arrival_time, tz).date() == target_date],
            key=lambda p: p.arrival_time,
        )
        if not pts:
            return f"{label} ({target_date:%d.%m}): Keine Etappe geplant"

        lines = [f"📋 Timeline · {label} ({target_date:%d.%m})", ""]
        for p in pts:
            if p.elevation_m is not None:
                lines.append(f"🕐 {local_fmt(p.arrival_time, tz)} · {int(p.elevation_m)} m")
            else:
                lines.append(f"🕐 {local_fmt(p.arrival_time, tz)}")
            m = p.metrics
            t_min = f"{m.temp_min_c:.0f}" if m.temp_min_c is not None else "?"
            t_max = f"{m.temp_max_c:.0f}" if m.temp_max_c is not None else "?"
            wind = f"{m.wind_max_kmh:.0f}" if m.wind_max_kmh is not None else "?"
            precip = f"{m.precip_sum_mm:.1f}" if m.precip_sum_mm is not None else "0.0"
            thunder = m.thunder_level_max
            t_label = _THUNDER_LABEL.get(thunder.value if thunder else "NONE", "?")
            # Issue #1680 S3 (Spec D2): die tragende(n) Zutat(en) DIESES
            # Wegpunkts -- `thunder_level_max` UND `thunder_level_max_signals`
            # stammen aus DEMSELBEN `m` (`SegmentWeatherSummary`, von
            # `compute_basis_metrics()` fuer genau dieses eine Segment
            # gerechnet). Die Liste wird PRO Wegpunkt in der Schleife gelesen,
            # nie einmal ausserhalb -- sonst zeigte jede Zeile dieselbe,
            # globale Herkunft (AC-10). `getattr`, weil ein Alt-Schnappschuss
            # vor Scheibe 1/2 das Feld nicht kennt (AC-15): dann bleibt die
            # Zeile zeichengleich, ohne "unbekannt" und ohne leeren Trenner.
            # KANAL: die Timeline erreicht nur E-Mail und Telegram (s. Hinweis
            # in `_fmt_day_agg()`), SMS/Premium-SMS haben keinen Kommandopfad.
            from output.metric_format import thunder_signal_label
            _traeger = getattr(m, "thunder_level_max_signals", None)
            _herkunft = ", ".join(thunder_signal_label(n) for n in _traeger or [])
            if _herkunft:
                t_label = f"{t_label} · {_herkunft}"
            lines.append(
                f"   🌡 {t_min}–{t_max} °C  💨 {wind} km/h  "
                f"🌧 {precip} mm  ⛈ {t_label}"
            )
        return "\n".join(lines)

    def _timeline_buttons(self, timeline, target_date, day_token: str, tz) -> dict:
        """Drilldown-Buttons je kritischer Metrik + immer Zurück."""
        from app.models import ThunderLevel
        from output.metric_format import thunder_ordinal
        back = {"text": "⬅️ Zurück", "callback_data": "glance"}
        agg = self._aggregate_day(timeline, target_date, tz) if timeline.available else None
        if not agg:
            return {"inline_keyboard": [[back]]}

        drilldown: list[dict] = []
        # Issue #1474 Adversary-Folgeaudit: zweite lokale Kopie derselben
        # {NONE,MED,HIGH}-Liste wie _aggregate_day() -- kannte LOW ebenfalls
        # nicht. thunder_ordinal() statt eigener Liste.
        thunder = agg["thunder"]
        if thunder is not None and thunder_ordinal(thunder) >= thunder_ordinal(ThunderLevel.MED):
            drilldown.append({"text": "🔍 Gewitter", "callback_data": f"dd_thunder_{day_token}"})
        if agg["wind_max"] is not None and agg["wind_max"] >= 40:
            drilldown.append({"text": "🔍 Wind", "callback_data": f"dd_wind_{day_token}"})
        if (agg["pop"] or 0) >= 30 or (agg["precip"] or 0) >= 1.0:
            drilldown.append({"text": "🔍 Niederschlag", "callback_data": f"dd_precip_{day_token}"})

        rows = []
        if drilldown:
            rows.append(drilldown)
        rows.append([back])
        return {"inline_keyboard": rows}

    # -----------------------------------------------------------------------
    # Commands
    # -----------------------------------------------------------------------

    def _apply_ruhetag(
        self, trip: Trip, value: Optional[str], command_date: date,
        user_id: str = "default",
    ) -> CommandResult:
        """Shift all stages after command_date by +N days (default: 1)."""
        shift_days = int(value) if value and value.isdigit() else 1

        # Idempotency check
        if self._is_already_applied(trip.id, "ruhetag", command_date, user_id):
            return CommandResult(
                success=False, command="ruhetag",
                confirmation_subject=f"[{trip.name}] Ruhetag bereits eingetragen",
                confirmation_body="Ruhetag wurde heute bereits eingetragen.",
                trip_name=trip.name,
            )

        shifts: list[StageShift] = []
        new_stages: list[Stage] = []

        for stage in trip.stages:
            if stage.date > command_date:
                new_date = stage.date + timedelta(days=shift_days)
                new_stages.append(dataclasses.replace(stage, date=new_date))
                shifts.append(StageShift(stage.name, stage.date, new_date))
            else:
                new_stages.append(stage)

        if not shifts:
            return CommandResult(
                success=False, command="ruhetag",
                confirmation_subject=f"[{trip.name}] Keine Etappen",
                confirmation_body="Keine zukuenftigen Etappen zum Verschieben.",
                trip_name=trip.name,
            )

        new_trip = dataclasses.replace(trip, stages=new_stages)
        save_trip(new_trip, user_id)
        self._delete_snapshot(trip.id, user_id)
        self._append_command_log(trip.id, "ruhetag", command_date, user_id)

        tage_wort = "Tag" if shift_days == 1 else "Tage"
        lines = [f"Ruhetag eingetragen: +{shift_days} {tage_wort}.", ""]
        lines.append("Verschobene Etappen:")
        for s in shifts:
            lines.append(
                f"  {s.stage_name}: {s.old_date:%d.%m.%Y} -> {s.new_date:%d.%m.%Y}"
            )
        lines.append("")
        lines.append("Naechster Report kommt planmaessig.")

        return CommandResult(
            success=True, command="ruhetag",
            confirmation_subject=f"[{trip.name}] Ruhetag bestaetigt",
            confirmation_body="\n".join(lines),
            trip_name=trip.name, shifts=shifts,
        )

    def _trigger_report(
        self, trip: Trip, value: Optional[str], user_id: str = "default",
    ) -> CommandResult:
        """Trigger an immediate morning/evening report."""
        report_type = (value or "morning").lower()
        if report_type not in ("morning", "evening"):
            return CommandResult(
                success=False, command="report",
                confirmation_subject=f"[{trip.name}] Ungueltiger Report-Typ",
                confirmation_body=f"Report-Typ '{report_type}' unbekannt. Erlaubt: morning, evening",
                trip_name=trip.name,
            )

        from services.trip_report_scheduler import TripReportSchedulerService
        service = TripReportSchedulerService(user_id=user_id)
        service.send_test_report(trip, report_type)

        return CommandResult(
            success=True, command="report",
            confirmation_subject=f"[{trip.name}] Report gesendet",
            confirmation_body=f"{report_type.title()} Report wird jetzt gesendet.",
            trip_name=trip.name,
        )

    def _shift_start(
        self, trip: Trip, value: Optional[str], user_id: str = "default",
    ) -> CommandResult:
        """Shift all stages relative to a new start date."""
        if not value:
            return CommandResult(
                success=False, command="startdatum",
                confirmation_subject=f"[{trip.name}] Fehlendes Datum",
                confirmation_body="Bitte Datum angeben: ### startdatum: YYYY-MM-DD",
                trip_name=trip.name,
            )
        try:
            new_start = date.fromisoformat(value)
        except ValueError:
            return CommandResult(
                success=False, command="startdatum",
                confirmation_subject=f"[{trip.name}] Ungueltiges Datum",
                confirmation_body=f"'{value}' ist kein gueltiges Datum. Format: YYYY-MM-DD",
                trip_name=trip.name,
            )

        old_start = trip.stages[0].date
        delta = new_start - old_start
        shifts = []
        new_stages = []
        for stage in trip.stages:
            new_date = stage.date + delta
            new_stages.append(dataclasses.replace(stage, date=new_date))
            shifts.append(StageShift(stage.name, stage.date, new_date))

        new_trip = dataclasses.replace(trip, stages=new_stages)
        save_trip(new_trip, user_id)
        self._delete_snapshot(trip.id, user_id)

        lines = [f"Startdatum verschoben: {old_start:%d.%m.%Y} -> {new_start:%d.%m.%Y}", ""]
        lines.append("Neue Etappen-Daten:")
        for s in shifts:
            lines.append(f"  {s.stage_name}: {s.new_date:%d.%m.%Y}")

        return CommandResult(
            success=True, command="startdatum",
            confirmation_subject=f"[{trip.name}] Startdatum geaendert",
            confirmation_body="\n".join(lines),
            trip_name=trip.name, shifts=shifts,
        )

    def _show_status(self, trip: Trip, now_utc: datetime) -> CommandResult:
        """Listet heute und kommende Etappen (vergangene werden gefiltert).

        Issue #1727 S5a (ADR-0044): "heute" ist der ORTStag DIESER Tour. Vorher
        stand hier `date.today()` -- das Datum der Prozess-Zeitzone, auf dem
        Server `Etc/UTC`. In Neuseeland blieb die lokal abgeschlossene Etappe
        dadurch bis zu zwoelf Stunden am Tag stehen, an der US-Westkueste fiel
        die heutige bis zu sieben Stunden am Tag durch den Filter.

        Args:
            trip: die Tour, deren Etappen gelistet werden.
            now_utc: Zeitpunkt der Abfrage (`msg.received_at`). Pflichtparameter
                -- ein Default auf die Systemuhr wuerde genau die Umgebungsuhr
                wieder einfuehren, die ADR-0051 Regel 3 verbietet.
        """
        today = trip_local_today(trip, now_utc)
        lines = [f"Status: {trip.name}", ""]
        for stage in trip.stages:
            if stage.date >= today:
                lines.append(f"  {stage.date:%d.%m.%Y} – {stage.name}")
        return CommandResult(
            success=True, command="status",
            confirmation_subject=f"[{trip.name}] Status",
            confirmation_body="\n".join(lines),
            trip_name=trip.name,
        )

    def _show_help(self) -> CommandResult:
        """Listet alle verfügbaren Befehle mit Syntax (Issue #731: abruf-zentriert)."""
        body = (
            "Verfügbare Befehle:\n\n"
            "  HEUTE                 – Wetter der heutigen Etappe\n"
            "  MORGEN                – Wetter der morgigen Etappe\n"
            "  JETZT                 – Nowcast Regen/Gewitter nächste ~2h\n"
            "  GEWITTER              – Gewittergefahr heutige Etappe\n"
            "  RUHETAG [N]           – Etappen um N Tage verschieben (Standard: 1)\n"
            "  STATUS                – Heute und kommende Etappen\n"
            "  PAUSE [2d / 12h]      – Briefings für Dauer unterbrechen\n"
            "  SKIP                  – Nächstes Briefing überspringen\n"
            "  STOP                  – Briefings dauerhaft deaktivieren\n"
            "  WEITER                – Briefings reaktivieren\n"
            "  HILFE                 – Diese Hilfe anzeigen"
        )
        return CommandResult(
            success=True, command="hilfe",
            confirmation_subject="Hilfe",
            confirmation_body=body,
        )

    def _show_columns_info(self) -> CommandResult:
        """Antwort auf den Aktionen-Bubble-Button "📊 Spalten" (Issue #1001 F002).

        Spalten-Konfiguration hat keinen Inline-Telegram-Bearbeitungsflow
        (Spec Known Limitations) — ein informativer Hinweis statt eines
        stillen, unsichtbaren Nichts-Tuns.
        """
        return CommandResult(
            success=True, command="columns",
            confirmation_subject="Spalten",
            confirmation_body=(
                "Spalten-Konfiguration ist nur im Trip-Editor möglich:\n"
                "https://gregor20.henemm.com"
            ),
        )

    def _apply_pause(
        self, trip: Trip, value: Optional[str], user_id: str,
    ) -> CommandResult:
        """Pause reports until paused_until (via RMW)."""
        if not value:
            return CommandResult(
                success=False, command="pause",
                confirmation_subject=f"[{trip.name}] PAUSE: Dauer fehlt",
                confirmation_body=(
                    "Bitte Dauer angeben, z.B. PAUSE 2d oder PAUSE 12h.\n"
                    "Format: N d (Tage) oder N h (Stunden)."
                ),
                trip_name=trip.name,
            )
        if not trip.report_config:
            return CommandResult(
                success=False, command="pause",
                confirmation_subject=f"[{trip.name}] Kein report_config",
                confirmation_body="Für diesen Trip ist kein Berichts-Zeitplan konfiguriert.",
                trip_name=trip.name,
            )
        m = _PAUSE_DURATION_RE.match(value.strip())
        if not m:
            return CommandResult(
                success=False, command="pause",
                confirmation_subject=f"[{trip.name}] PAUSE: Ungültige Dauer",
                confirmation_body=(
                    f"'{value}' ist keine gültige Dauer.\n"
                    "Beispiele: PAUSE 2d (2 Tage) oder PAUSE 12h (12 Stunden)."
                ),
                trip_name=trip.name,
            )
        n = int(m.group(1))
        if n <= 0:
            return CommandResult(
                success=False, command="pause",
                confirmation_subject=f"[{trip.name}] PAUSE: Dauer muss > 0 sein",
                confirmation_body=(
                    "Die Pause-Dauer muss größer als 0 sein.\n"
                    "Beispiele: PAUSE 2d (2 Tage) oder PAUSE 12h (12 Stunden)."
                ),
                trip_name=trip.name,
            )
        unit = m.group(2) or "d"
        if unit == "h":
            delta = timedelta(hours=n)
        else:
            delta = timedelta(days=n)
        paused_until = datetime.now(timezone.utc) + delta
        new_rc = dataclasses.replace(trip.report_config, paused_until=paused_until)
        new_trip = dataclasses.replace(trip, report_config=new_rc)
        save_trip(new_trip, user_id)
        return CommandResult(
            success=True, command="pause",
            confirmation_subject=f"[{trip.name}] Briefings pausiert",
            confirmation_body=(
                f"Briefings für '{trip.name}' pausiert bis "
                f"{paused_until.strftime('%d.%m.%Y %H:%M')} UTC.\n"
                "Zum Fortsetzen: STOP (dauerhaft) oder warte bis die Pause abläuft."
            ),
            trip_name=trip.name,
        )

    def _apply_skip(self, trip: Trip, user_id: str) -> CommandResult:
        """Skip the next scheduled send (one-shot, idempotent)."""
        if not trip.report_config:
            return CommandResult(
                success=False, command="skip",
                confirmation_subject=f"[{trip.name}] Kein report_config",
                confirmation_body="Für diesen Trip ist kein Berichts-Zeitplan konfiguriert.",
                trip_name=trip.name,
            )
        new_rc = dataclasses.replace(trip.report_config, skip_next=True)
        new_trip = dataclasses.replace(trip, report_config=new_rc)
        save_trip(new_trip, user_id)
        return CommandResult(
            success=True, command="skip",
            confirmation_subject=f"[{trip.name}] Nächster Versand übersprungen",
            confirmation_body=(
                f"Das nächste Briefing für '{trip.name}' wird übersprungen.\n"
                "Danach läuft der Zeitplan wieder normal."
            ),
            trip_name=trip.name,
        )

    def _show_config(self, trip: Trip) -> CommandResult:
        """Return a link to trip settings — read-only, no save_trip."""
        url = f"https://gregor20.henemm.com/trips/{trip.id}"
        return CommandResult(
            success=True, command="config",
            confirmation_subject=f"[{trip.name}] Trip-Einstellungen",
            confirmation_body=(
                f"Einstellungen für '{trip.name}':\n{url}\n\n"
                "Dort kannst du Zeitplan, Kanäle und Alarm-Schwellen anpassen."
            ),
            trip_name=trip.name,
        )

    def _show_now(self, trip: Trip, now_utc: datetime) -> CommandResult:
        """Fetch radar nowcast for today's stage position.

        Issue #1727 S5a (ADR-0044): der Standort haengt am ORTStag der Tour.
        #1402 hatte hier nur die Uhrzeit des Onset-Textes ortsrichtig gemacht --
        die Etappen-, und damit die Standortwahl, blieb am Servertag haengen.

        Args:
            trip: die Tour, deren heutiger Wegpunkt den Nowcast bestimmt.
            now_utc: Zeitpunkt der Abfrage (`msg.received_at`). Pflichtparameter
                aus demselben Grund wie in :meth:`_show_status`.
        """
        from services.radar_service import RadarNowcastService
        today = trip_local_today(trip, now_utc)
        stage = trip.get_stage_for_date(today)
        if not stage or not stage.waypoints:
            return CommandResult(
                success=False, command="now",
                confirmation_subject=f"[{trip.name}] Kein heutiger Standort",
                confirmation_body=(
                    "Keine heutige Etappe gefunden. "
                    "Aktueller Position/Standort unbekannt — "
                    "bitte Etappenplan prüfen."
                ),
                trip_name=trip.name,
            )
        wp = stage.waypoints[0]
        svc = RadarNowcastService()
        # Issue #1329 C2: /jetzt ist eine Nutzeraktion -- explizit
        # user_briefing (Default, nie gedrosselt), zur Dokumentation der Absicht.
        result = svc.get_nowcast(wp.lat, wp.lon, priority="user_briefing")
        # Issue #1402: ohne tz faellt format_now_text() auf das argumentlose
        # .astimezone() zurueck -- deutet die Onset-Zeit in der PROZESS-
        # Zeitzone des Servers statt der Ortszeit des Wegpunkts.
        from utils.timezone import tz_for_coords

        body = svc.format_now_text(result, tz=tz_for_coords(wp.lat, wp.lon))
        return CommandResult(
            success=True, command="now",
            confirmation_subject=f"[{trip.name}] Nowcast",
            confirmation_body=body,
            trip_name=trip.name,
            reply_markup={"inline_keyboard": [[{"text": "🔄 Aktualisieren", "callback_data": "now"}]]},
        )

    def _cancel_trip(self, trip: Trip, user_id: str = "default") -> CommandResult:
        """Disable report scheduling for the trip."""
        if trip.report_config:
            new_config = dataclasses.replace(trip.report_config, enabled=False)
            new_trip = dataclasses.replace(trip, report_config=new_config)
            save_trip(new_trip, user_id)

        return CommandResult(
            success=True, command="abbruch",
            confirmation_subject=f"[{trip.name}] Trip beendet",
            confirmation_body=f"Reports fuer '{trip.name}' deaktiviert. Gute Heimreise!",
            trip_name=trip.name,
        )

    def _resume_trip(self, trip: Trip, user_id: str = "default") -> CommandResult:
        """Reaktiviert den Report-Versand für den Trip (enabled=True via RMW)."""
        if trip.report_config:
            new_config = dataclasses.replace(trip.report_config, enabled=True)
            new_trip = dataclasses.replace(trip, report_config=new_config)
            save_trip(new_trip, user_id)

        return CommandResult(
            success=True, command="weiter",
            confirmation_subject=f"[{trip.name}] Briefings reaktiviert",
            confirmation_body=f"Reports fuer '{trip.name}' wieder aktiviert. Viel Erfolg auf der Tour!",
            trip_name=trip.name,
        )

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _delete_snapshot(self, trip_id: str, user_id: str = "default") -> None:
        """Delete cached weather snapshot after date changes."""
        snapshot_path = get_snapshots_dir(user_id) / f"{trip_id}.json"
        try:
            if snapshot_path.exists():
                snapshot_path.unlink()
                logger.info(f"Snapshot deleted: {snapshot_path}")
        except OSError as e:
            logger.error(f"Failed to delete snapshot {snapshot_path}: {e}")

    def _get_command_log_path(self, user_id: str = "default") -> Path:
        """Get path to command_log.json."""
        return get_data_dir(user_id) / "command_log.json"

    def _load_command_log(self, user_id: str = "default") -> list[dict]:
        """Load command log entries."""
        path = self._get_command_log_path(user_id)
        if not path.exists():
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []

    def _append_command_log(
        self, trip_id: str, command: str, command_date: date,
        user_id: str = "default",
    ) -> None:
        """Append entry to command log for idempotency tracking."""
        entries = self._load_command_log(user_id)
        entries.append({
            "trip_id": trip_id,
            "command": command,
            "date": command_date.isoformat(),
            "applied_at": datetime.now(tz=timezone.utc).isoformat(),
        })
        path = self._get_command_log_path(user_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)

    def _is_already_applied(
        self, trip_id: str, command: str, command_date: date,
        user_id: str = "default",
    ) -> bool:
        """Check if command was already applied today (idempotency)."""
        for entry in self._load_command_log(user_id):
            if (
                entry.get("trip_id") == trip_id
                and entry.get("command") == command
                and entry.get("date") == command_date.isoformat()
            ):
                return True
        return False
