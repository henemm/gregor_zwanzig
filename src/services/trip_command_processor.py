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


# ---------------------------------------------------------------------------
# Command Parsing
# ---------------------------------------------------------------------------

_COMMAND_PATTERN = re.compile(r"^###\s+(\S+?)(?:[:\s]\s*(.+))?$")

_VALID_COMMANDS = {"ruhetag", "report", "startdatum", "abbruch"}


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
                    "Verfuegbar: ruhetag, report, startdatum, abbruch"
                ),
                trip_name=msg.trip_name,
            )

        if key not in _VALID_COMMANDS:
            return CommandResult(
                success=False, command=key,
                confirmation_subject=f"[{msg.trip_name}] Unbekannter Befehl",
                confirmation_body=(
                    f"'{key}' ist kein gueltiger Befehl.\n"
                    "Verfuegbar: ruhetag, report, startdatum, abbruch"
                ),
                trip_name=msg.trip_name,
            )

        # 2. Lookup trip
        trip = self._find_trip(msg.trip_name)
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
            return self._trigger_report(trip, value)
        elif key == "startdatum":
            return self._shift_start(trip, value)
        elif key == "abbruch":
            return self._cancel_trip(trip)

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

    def _find_trip(self, trip_name: str) -> Optional[Trip]:
        """Case-insensitive trip name lookup."""
        for trip in load_all_trips():
            if trip.name.lower() == trip_name.lower():
                return trip
        logger.warning(f"No trip found for name: {trip_name!r}")
        return None

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

    def _trigger_report(self, trip: Trip, value: Optional[str]) -> CommandResult:
        """Trigger an immediate morning/evening report."""
        report_type = value or "morning"
        if report_type not in ("morning", "evening"):
            return CommandResult(
                success=False, command="report",
                confirmation_subject=f"[{trip.name}] Ungueltiger Report-Typ",
                confirmation_body=f"Report-Typ '{report_type}' unbekannt. Erlaubt: morning, evening",
                trip_name=trip.name,
            )

        from services.trip_report_scheduler import TripReportSchedulerService
        service = TripReportSchedulerService()
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
