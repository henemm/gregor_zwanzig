#!/usr/bin/env python3
"""
Radar-Alert-Mail-Validator -- Issue #830.

Kanonischer Acceptance-Validator fuer Radar-Alert-Mails. Holt die zuletzt
zugestellte Mail aus dem Test-Postfach, erkennt anhand des Marker-Headers
X-GZ-Mail-Type: radar-alert und prueft sie auf Plausibilitaet.

Vorbild: briefing_mail_validator.py (IMAP-Fetch, Exit 0/1/2, YAML-Log).
Stdlib only -- als isoliertes Modul ladbar (keine relativen Importe).

Exit codes:
    0 = alle Checks bestanden (oder Mail ist kein radar-alert -> No-Op)
    1 = Spec-Verletzung mit konkreter Fehlerliste
    2 = technischer Fehler (IMAP nicht erreichbar)
"""
from __future__ import annotations

import email
import imaplib
import os
import re
import sys
from email.header import decode_header
from email.message import Message
from pathlib import Path

# Muster fuer Onset-Zeit (HH:MM, z.B. "14:30")
_TIME_RE = re.compile(r"\b([01]?\d|2[0-3]):[0-5]\d\b")

# Bekannte Intensitaetsstufen aus radar_service.py / format_now_text()
_INTENSITY_LABELS = [
    "Leichter Regen",
    "Maessiger Regen",
    "Mäßiger Regen",
    "Starker Regen",
    "Starker Hagel",
    "Gewitter",
    "Regen",     # Fallback: Teilstring
]

# Segment-Erkennungs-Muster: "Etappe N", "km X-Y", oder generischer Segment-Label
_SEGMENT_RE = re.compile(
    r"(Etappe\s+\d+|km\s+\d+\s*[–\-]\s*\d+|\bseg\b|\bSegment\b)",
    re.IGNORECASE,
)


def _part_text(part: Message) -> str:
    """Dekodierter Payload eines Parts (bytes->str, fail-soft)."""
    payload = part.get_payload(decode=True)
    if payload is None:
        return part.get_payload() or ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, TypeError):
        return payload.decode("utf-8", errors="replace")


def _extract_body(msg: Message) -> str:
    """Extrahiert den plain-text Body aus der Mail (alle Parts)."""
    if msg.is_multipart():
        parts = []
        for part in msg.walk():
            if part.get_content_type() == "text/plain":
                parts.append(_part_text(part))
        return "\n".join(parts)
    return _part_text(msg)


def validate_message(msg: Message) -> tuple[bool, list[str]]:
    """Faellt das Urteil ueber ein geparstes email.message.Message-Objekt.

    Returnt (ok, errors):
    - Falscher Mail-Typ (nicht radar-alert): (True, [Info]) -- sauberes No-Op.
    - Alle Checks bestanden: (True, []).
    - Mind. ein Check schlaegt fehl: (False, [Fehlerliste]).
    """
    mail_type = msg.get("X-GZ-Mail-Type")

    # No-Op fuer fremde Mail-Typen (Exit 2 = sauberes No-Op)
    if mail_type is None or mail_type != "radar-alert":
        info = (
            f"Kein radar-alert-Header (X-GZ-Mail-Type={mail_type!r}) "
            "-- falscher Validator, uebersprungen"
        )
        return True, [info]

    body = _extract_body(msg)
    errors: list[str] = []

    # P-1: Segment-Label vorhanden
    if not _SEGMENT_RE.search(body):
        errors.append(
            "P-1: Kein Segment-Label gefunden (erwartet 'Etappe N', 'km X-Y' o.ae.) "
            f"im Body. Body-Ausschnitt: {body[:120]!r}"
        )

    # P-2: Onset-Zeit im Format HH:MM vorhanden
    times = _TIME_RE.findall(body)
    if not times:
        errors.append(
            "P-2: Keine Onset-Zeit im Format HH:MM gefunden. "
            "Kein 'None' oder UTC-Rohwert erlaubt."
        )

    # P-3: Intensitaetsstufe erkennbar
    body_lower = body.lower()
    found_intensity = any(label.lower() in body_lower for label in _INTENSITY_LABELS)
    if not found_intensity:
        errors.append(
            "P-3: Keine Intensitaetsstufe erkannt. "
            "Erwartet: eines von Leichter/Maessiger/Starker Regen, Starker Hagel, Gewitter."
        )

    # P-4: Cooldown-Hinweis vorhanden
    if "höchstens einmal in" not in body and "hoechstens einmal in" not in body:
        errors.append(
            "P-4: Cooldown-Hinweis ('hoechstens einmal in') fehlt im Body."
        )

    return len(errors) == 0, errors


def _write_validation_log(success: bool, errors: list) -> None:
    """Strukturiertes Validator-Log YAML (fail-soft)."""
    try:
        from datetime import datetime
        import tempfile

        hooks_dir = Path(__file__).resolve().parent
        log_dir = hooks_dir.parent / "workflows" / "_log"
        log_dir.mkdir(parents=True, exist_ok=True)
        workflow_id = os.environ.get("GZ_ACTIVE_WORKFLOW", "unknown")
        date_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        log_path = log_dir / f"{date_str}_{workflow_id}_radar_alert_validation.yaml"

        lines = [
            f"validator: radar_alert_mail_validator",
            f"validated_at: '{datetime.utcnow().isoformat()}'",
            f"workflow_id: '{workflow_id}'",
            f"passed: {str(success).lower()}",
            f"error_count: {len(errors)}",
            "errors:",
        ]
        for err in errors:
            safe = err.replace("'", "''")
            lines.append(f"  - '{safe}'")

        fd, tmp = tempfile.mkstemp(dir=str(log_dir), suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            f.write("\n".join(lines) + "\n")
        os.rename(tmp, str(log_path))
    except Exception:
        pass  # fail-soft


def fetch_latest_message(max_scan: int = 50) -> Message:
    """Holt die neueste radar-alert-Mail aus dem Test-Postfach."""
    src_dir = Path(__file__).resolve().parents[2] / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    from app.config import Settings

    settings = Settings()
    imap_host = settings.imap_host or settings.smtp_host
    # Radar-Alert-Mails werden an gregor-test@henemm.com gesendet (Test-Postfach).
    # Priorisiere GZ_TEST_IMAP_* Credentials, falle auf GZ_IMAP_* zurueck.
    imap_user = settings.test_imap_user or settings.imap_user or settings.smtp_user
    imap_pass = settings.test_imap_pass or settings.imap_pass or settings.smtp_pass
    if not imap_user or not imap_pass:
        raise ValueError("IMAP nicht konfiguriert (GZ_TEST_IMAP_USER/GZ_IMAP_USER)")

    imap = imaplib.IMAP4_SSL(imap_host, settings.imap_port)
    try:
        imap.login(imap_user, imap_pass)
        imap.select("INBOX")
        _, data = imap.search(None, "ALL")
        all_ids = data[0].split()
        if not all_ids:
            raise ValueError("Keine E-Mails gefunden")

        for mid in reversed(all_ids[-max_scan:]):
            _, hdr_data = imap.fetch(mid, "(BODY.PEEK[HEADER])")
            headers = email.message_from_bytes(hdr_data[0][1])
            if headers.get("X-GZ-Mail-Type") == "radar-alert":
                _, msg_data = imap.fetch(mid, "(RFC822)")
                return email.message_from_bytes(msg_data[0][1])

        raise ValueError(
            f"Keine radar-alert-Mail gefunden (scan={max_scan} Mails)"
        )
    finally:
        try:
            imap.close()
            imap.logout()
        except Exception:
            pass


def main() -> None:
    print("=" * 70)
    print("RADAR-ALERT-MAIL-VALIDATOR -- #830")
    print("=" * 70)
    print()

    try:
        msg = fetch_latest_message()
        success, errors = validate_message(msg)
    except Exception as exc:
        print(f"  TECHNISCHER FEHLER: Mail konnte nicht geladen werden: {exc}")
        _write_validation_log(success=False, errors=[str(exc)])
        sys.exit(2)

    _write_validation_log(success=success, errors=errors)

    if success:
        for note in errors:
            print(f"  i {note}")
        print("OK Radar-Alert-Mail-Checks bestanden.")
        sys.exit(0)

    print("SPEC-VERLETZUNGEN GEFUNDEN:")
    print()
    for err in errors:
        print(f"  - {err}", file=sys.stderr)
    print()
    sys.exit(1)


if __name__ == "__main__":
    main()
