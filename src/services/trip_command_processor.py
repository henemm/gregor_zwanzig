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

logger = logging.getLogger(__name__)

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


# ---------------------------------------------------------------------------
# Command Parsing
# ---------------------------------------------------------------------------

_COMMAND_PATTERN = re.compile(r"^###\s+(\S+?)(?:[:\s]\s*(.+))?$")

_VALID_COMMANDS = {"ruhetag", "report", "startdatum", "abbruch", "status", "hilfe", "now"}

_QUERY_KEYS = {"glance", "heute", "morgen", "heute_gewitter",
               "timeline_heute", "timeline_morgen"}

_GLANCE_BUTTONS = {
    "inline_keyboard": [[
        {"text": "📋 Timeline heute", "callback_data": "tl_today"},
        {"text": "📋 Timeline morgen", "callback_data": "tl_tomorrow"},
    ]]
}

_THUNDER_LABEL = {
    "NONE": "kein",
    "MED": "mäßig",
    "HIGH": "hoch",
}


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
        command_date = msg.received_at.date()
        if key == "ruhetag":
            return self._apply_ruhetag(trip, value, command_date)
        elif key == "report":
            return self._trigger_report(trip, value, msg.user_id)
        elif key == "startdatum":
            return self._shift_start(trip, value)
        elif key == "abbruch":
            return self._cancel_trip(trip)
        elif key == "status":
            return self._show_status(trip)
        elif key == "now":
            return self._show_now(trip)

        # Should not reach here due to whitelist check above
        return CommandResult(
            success=False, command=key,
            confirmation_subject="Fehler",
            confirmation_body="Interner Fehler.",
        )

    def _parse_command(self, body: str) -> tuple[Optional[str], Optional[str]]:
        """Parse first non-blank line for ### key: value format."""
        first_line = next(
            (line.strip() for line in body.splitlines() if line.strip()),
            "",
        )
        match = _COMMAND_PATTERN.match(first_line)
        if not match:
            return None, None
        return match.group(1).lower(), (match.group(2) or "").strip() or None

    def _find_trip(self, trip_name: str, user_id: str = "default") -> Optional[Trip]:
        """Case-insensitive trip name lookup, user-scoped."""
        for trip in load_all_trips(user_id):
            if trip.name.lower() == trip_name.lower():
                return trip
        logger.warning(f"No trip found for name: {trip_name!r} (user: {user_id!r})")
        return None

    # -----------------------------------------------------------------------
    # Query (read-only) — no save_trip, no _append_command_log, no _delete_snapshot
    # -----------------------------------------------------------------------

    def _handle_query(
        self, trip: Trip, query_key: str, received_at: datetime, user_id: str,
    ) -> CommandResult:
        """Dispatch read-only query. Never mutates trip state."""
        from services.weather_extractor import WeatherExtractor
        extractor = WeatherExtractor(user_id=user_id)
        timeline = extractor.timeline(trip.id)

        today = received_at.date()
        tomorrow = today + timedelta(days=1)

        if query_key == "glance":
            body = self._fmt_glance(timeline, today, tomorrow)
            return CommandResult(
                success=True, command="glance",
                confirmation_subject=f"[{trip.name}] Glance",
                confirmation_body=body,
                trip_name=trip.name,
                reply_markup=_GLANCE_BUTTONS,
            )
        elif query_key == "heute":
            body = self._fmt_day(timeline, today, "Heute")
            return CommandResult(
                success=True, command="heute",
                confirmation_subject=f"[{trip.name}] Heute",
                confirmation_body=body,
                trip_name=trip.name,
            )
        elif query_key == "morgen":
            body = self._fmt_day(timeline, tomorrow, "Morgen")
            return CommandResult(
                success=True, command="morgen",
                confirmation_subject=f"[{trip.name}] Morgen",
                confirmation_body=body,
                trip_name=trip.name,
            )
        elif query_key == "heute_gewitter":
            body = self._fmt_gewitter(timeline, today)
            return CommandResult(
                success=True, command="heute_gewitter",
                confirmation_subject=f"[{trip.name}] Gewitter heute",
                confirmation_body=body,
                trip_name=trip.name,
            )
        elif query_key == "timeline_heute":
            body = self._fmt_timeline(timeline, today, "Heute", "today")
            return CommandResult(
                success=True, command="timeline_heute",
                confirmation_subject=f"[{trip.name}] Timeline heute",
                confirmation_body=body,
                trip_name=trip.name,
                reply_markup=self._timeline_buttons(timeline, today, "today"),
            )
        elif query_key == "timeline_morgen":
            body = self._fmt_timeline(timeline, tomorrow, "Morgen", "tomorrow")
            return CommandResult(
                success=True, command="timeline_morgen",
                confirmation_subject=f"[{trip.name}] Timeline morgen",
                confirmation_body=body,
                trip_name=trip.name,
                reply_markup=self._timeline_buttons(timeline, tomorrow, "tomorrow"),
            )
        # Fallback (should not reach)
        return CommandResult(
            success=False, command=query_key,
            confirmation_subject="Fehler",
            confirmation_body="Unbekannter Query-Key.",
            trip_name=trip.name,
        )

    def _aggregate_day(self, timeline, target_date) -> Optional[dict]:
        """Aggregiere Timeline-Punkte für target_date. None wenn keine Punkte."""
        from app.models import ThunderLevel as TL
        points = [p for p in timeline.points if p.arrival_time.date() == target_date]
        if not points:
            return None
        temp_max = max((p.metrics.temp_max_c for p in points if p.metrics.temp_max_c is not None), default=None)
        temp_min = min((p.metrics.temp_min_c for p in points if p.metrics.temp_min_c is not None), default=None)
        wind_max = max((p.metrics.wind_max_kmh for p in points if p.metrics.wind_max_kmh is not None), default=None)
        thunder_order = [TL.NONE, TL.MED, TL.HIGH]
        thunder_vals = [p.metrics.thunder_level_max for p in points if p.metrics.thunder_level_max is not None]
        thunder = max(thunder_vals, key=lambda t: thunder_order.index(t)) if thunder_vals else TL.NONE
        precip = sum(p.metrics.precip_sum_mm for p in points if p.metrics.precip_sum_mm is not None)
        pop = max((p.metrics.pop_max_pct for p in points if p.metrics.pop_max_pct is not None), default=None)
        return {"temp_max": temp_max, "temp_min": temp_min, "wind_max": wind_max,
                "thunder": thunder, "precip": precip, "pop": pop}

    def _fmt_day_agg(self, agg: dict, label: str) -> str:
        """Formatiert Tages-Aggregat als kompakte Zeile."""
        t_max = f"{agg['temp_max']:.0f}" if agg['temp_max'] is not None else "?"
        t_min = f"{agg['temp_min']:.0f}" if agg['temp_min'] is not None else "?"
        wind = f"{agg['wind_max']:.0f}" if agg['wind_max'] is not None else "?"
        thunder_label = _THUNDER_LABEL.get(agg['thunder'].value if agg['thunder'] else "NONE", "?")
        precip = f"{agg['precip']:.1f}" if agg.get('precip') else "0.0"
        return (
            f"{label}: 🌡 {t_min}–{t_max}°C  💨 {wind} km/h  "
            f"🌧 {precip}mm  ⛈ Gewitter: {thunder_label}"
        )

    def _fmt_glance(self, timeline, today, tomorrow) -> str:
        if not timeline.available:
            return (
                "Kein Wetter-Snapshot verfügbar. "
                "Bitte einen Report anfordern um aktuelle Daten zu laden."
            )
        agg_heute = self._aggregate_day(timeline, today)
        agg_morgen = self._aggregate_day(timeline, tomorrow)
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

    def _fmt_day(self, timeline, target_date, label: str) -> str:
        if not timeline.available:
            return (
                "Kein Wetter-Snapshot verfügbar. "
                "Bitte einen Report anfordern um aktuelle Daten zu laden."
            )
        agg = self._aggregate_day(timeline, target_date)
        if not agg:
            return f"{label} ({target_date:%d.%m}): Keine Etappe geplant"
        return self._fmt_day_agg(agg, f"{label} ({target_date:%d.%m})")

    def _fmt_gewitter(self, timeline, today) -> str:
        if not timeline.available:
            return (
                "Kein Wetter-Snapshot verfügbar. "
                "Bitte einen Report anfordern um aktuelle Daten zu laden."
            )
        agg = self._aggregate_day(timeline, today)
        if not agg:
            return f"Heute ({today:%d.%m}): Keine Etappe geplant — kein Gewitter-Status."
        thunder = agg["thunder"]
        label = _THUNDER_LABEL.get(thunder.value if thunder else "NONE", "?")
        return f"⛈ Gewitter heute ({today:%d.%m}): {label}"

    def _fmt_timeline(self, timeline, target_date, label: str, day_token: str) -> str:
        """Vertikale Timeline: pro Wegpunkt zwei Zeilen (Zeit/Höhe + Metriken)."""
        if not timeline.available:
            return (
                "Kein Wetter-Snapshot verfügbar. "
                "Bitte einen Report anfordern um aktuelle Wetterdaten zu laden."
            )
        pts = sorted(
            [p for p in timeline.points if p.arrival_time.date() == target_date],
            key=lambda p: p.arrival_time,
        )
        if not pts:
            return f"{label} ({target_date:%d.%m}): Keine Etappe geplant"

        lines = [f"📋 Timeline · {label} ({target_date:%d.%m})", ""]
        for p in pts:
            if p.elevation_m is not None:
                lines.append(f"🕐 {p.arrival_time:%H:%M} · {int(p.elevation_m)} m")
            else:
                lines.append(f"🕐 {p.arrival_time:%H:%M}")
            m = p.metrics
            t_min = f"{m.temp_min_c:.0f}" if m.temp_min_c is not None else "?"
            t_max = f"{m.temp_max_c:.0f}" if m.temp_max_c is not None else "?"
            wind = f"{m.wind_max_kmh:.0f}" if m.wind_max_kmh is not None else "?"
            precip = f"{m.precip_sum_mm:.1f}" if m.precip_sum_mm is not None else "0.0"
            thunder = m.thunder_level_max
            t_label = _THUNDER_LABEL.get(thunder.value if thunder else "NONE", "?")
            lines.append(
                f"   🌡 {t_min}–{t_max} °C  💨 {wind} km/h  "
                f"🌧 {precip} mm  ⛈ {t_label}"
            )
        return "\n".join(lines)

    def _timeline_buttons(self, timeline, target_date, day_token: str) -> dict:
        """Drilldown-Buttons je kritischer Metrik + immer Zurück."""
        from app.models import ThunderLevel
        back = {"text": "⬅️ Zurück", "callback_data": "glance"}
        agg = self._aggregate_day(timeline, target_date) if timeline.available else None
        if not agg:
            return {"inline_keyboard": [[back]]}

        drilldown: list[dict] = []
        thunder_order = [ThunderLevel.NONE, ThunderLevel.MED, ThunderLevel.HIGH]
        thunder = agg["thunder"]
        if thunder is not None and thunder_order.index(thunder) >= thunder_order.index(ThunderLevel.MED):
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
    ) -> CommandResult:
        """Shift all stages after command_date by +N days (default: 1)."""
        shift_days = int(value) if value and value.isdigit() else 1

        # Idempotency check
        if self._is_already_applied(trip.id, "ruhetag", command_date):
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
        save_trip(new_trip)
        self._delete_snapshot(trip.id)
        self._append_command_log(trip.id, "ruhetag", command_date)

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

    def _shift_start(self, trip: Trip, value: Optional[str]) -> CommandResult:
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
        save_trip(new_trip)
        self._delete_snapshot(trip.id)

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

    def _show_status(self, trip: Trip) -> CommandResult:
        """Listet alle Etappen mit Datum."""
        lines = [f"Status: {trip.name}", ""]
        for stage in trip.stages:
            lines.append(f"  {stage.date:%d.%m.%Y} – {stage.name}")
        return CommandResult(
            success=True, command="status",
            confirmation_subject=f"[{trip.name}] Status",
            confirmation_body="\n".join(lines),
            trip_name=trip.name,
        )

    def _show_help(self) -> CommandResult:
        """Listet alle verfügbaren Befehle mit Syntax."""
        body = (
            "Verfügbare Befehle:\n\n"
            "  ruhetag [N]           – Etappen um N Tage verschieben (Standard: 1)\n"
            "  startdatum YYYY-MM-DD – Neues Startdatum setzen\n"
            "  report morning|evening – Sofortigen Bericht anfordern\n"
            "  status                – Aktuelle Etappenübersicht\n"
            "  abbruch               – Scheduling deaktivieren\n"
            "  hilfe                 – Diese Hilfe anzeigen"
        )
        return CommandResult(
            success=True, command="hilfe",
            confirmation_subject="Hilfe",
            confirmation_body=body,
        )

    def _show_now(self, trip: Trip) -> CommandResult:
        """Fetch radar nowcast for today's stage position."""
        from services.radar_service import RadarNowcastService
        today = date.today()
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
        result = svc.get_nowcast(wp.lat, wp.lon)
        body = svc.format_now_text(result)
        return CommandResult(
            success=True, command="now",
            confirmation_subject=f"[{trip.name}] Nowcast",
            confirmation_body=body,
            trip_name=trip.name,
        )

    def _cancel_trip(self, trip: Trip) -> CommandResult:
        """Disable report scheduling for the trip."""
        if trip.report_config:
            new_config = dataclasses.replace(trip.report_config, enabled=False)
            new_trip = dataclasses.replace(trip, report_config=new_config)
            save_trip(new_trip)

        return CommandResult(
            success=True, command="abbruch",
            confirmation_subject=f"[{trip.name}] Trip beendet",
            confirmation_body=f"Reports fuer '{trip.name}' deaktiviert. Gute Heimreise!",
            trip_name=trip.name,
        )

    # -----------------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------------

    def _delete_snapshot(self, trip_id: str) -> None:
        """Delete cached weather snapshot after date changes."""
        snapshot_path = get_snapshots_dir() / f"{trip_id}.json"
        try:
            if snapshot_path.exists():
                snapshot_path.unlink()
                logger.info(f"Snapshot deleted: {snapshot_path}")
        except OSError as e:
            logger.error(f"Failed to delete snapshot {snapshot_path}: {e}")

    def _get_command_log_path(self) -> Path:
        """Get path to command_log.json."""
        return get_data_dir() / "command_log.json"

    def _load_command_log(self) -> list[dict]:
        """Load command log entries."""
        path = self._get_command_log_path()
        if not path.exists():
            return []
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, OSError):
            return []

    def _append_command_log(
        self, trip_id: str, command: str, command_date: date,
    ) -> None:
        """Append entry to command log for idempotency tracking."""
        entries = self._load_command_log()
        entries.append({
            "trip_id": trip_id,
            "command": command,
            "date": command_date.isoformat(),
            "applied_at": datetime.now(tz=timezone.utc).isoformat(),
        })
        path = self._get_command_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)

    def _is_already_applied(
        self, trip_id: str, command: str, command_date: date,
    ) -> bool:
        """Check if command was already applied today (idempotency)."""
        for entry in self._load_command_log():
            if (
                entry.get("trip_id") == trip_id
                and entry.get("command") == command
                and entry.get("date") == command_date.isoformat()
            ):
                return True
        return False
