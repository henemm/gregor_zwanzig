#!/usr/bin/env python3
"""
Briefing-Mail-Validator (full + compact) — Issue #733.

Kanonischer Acceptance-Validator fuer Trip-Briefing-Mails. Holt die zuletzt
zugestellte Mail aus dem Test-Postfach, erkennt anhand der Marker-Header
X-GZ-Mail-Type / X-GZ-Format deterministisch Typ und Format und prueft sie
format-spezifisch auf Plausibilitaet (nicht bloss String-Presence).

Vorbild: email_spec_validator.py (IMAP-Fetch, Exit 0/1/2, YAML-Log fail-soft).
Stdlib only — als isoliertes Modul ladbar (keine relativen Importe).

Exit codes:
    0 = alle format-spezifischen Checks bestanden (oder Mail ist compare → No-Op)
    1 = Spec-Verletzung mit konkreter Fehlerliste
    2 = technischer Fehler (IMAP nicht erreichbar)
"""
from __future__ import annotations

import argparse
import email
import imaplib
import os
import re
import sys
from email.header import decode_header
from email.message import Message
from pathlib import Path

# Sequenzielle Stundentabellen-Heuristik: mind. 2 distinct HH:00-Treffer.
_HOUR_RE = re.compile(r"\b([01]?\d|2[0-3]):00\b")
# Compact-Plain: echte Tabellenzeile beginnt (ggf. eingerueckt) mit HH:00.
# Pill-Ereigniszeiten ("Wind ab 00:00 … um 23:00", #795/AC-3/AC-10) stehen
# mitten in der Zeile und sind KEINE Stundentabelle.
_HOUR_LINE_RE = re.compile(r"^\s*([01]?\d|2[0-3]):00(\s|$)", re.MULTILINE)
# Temperatur-Range: "12–18°C" / "12-18°C" / "12–18C" (Halbgeviert oder Bindestrich).
_TEMP_RANGE_RE = re.compile(r"(-?\d{1,2})\s*[–-]\s*(-?\d{1,2})\s*°?C")
_MAX_BYTES_DEFAULT = 2048


# --------------------------------------------------------------------------- #
# Hilfsfunktionen
# --------------------------------------------------------------------------- #
def _distinct_hours(text: str) -> list[str]:
    """Distinct HH:00-Treffer in Reihenfolge des ersten Auftretens."""
    seen: list[str] = []
    for m in _HOUR_RE.finditer(text):
        if m.group(0) not in seen:
            seen.append(m.group(0))
    return seen


def _has_hourly_table(text: str) -> bool:
    """Heuristik: >=2 distinct/sequenzielle HH:00 = Stundentabelle.

    HTML (full): jede Zelle, daher der breite \\bHH:00\\b-Treffer.
    """
    return len(_distinct_hours(text)) >= 2


def _has_hourly_table_plain(text: str) -> bool:
    """Compact-Plain-Heuristik: >=2 Zeilen, die mit HH:00 BEGINNEN.

    Schaerfer als _has_hourly_table, damit die ausgeschriebenen Pill-
    Ereigniszeiten (mitten in der Zeile, #795) NICHT faelschlich als
    Stundentabelle gewertet werden.
    """
    hours = {m.group(1) for m in _HOUR_LINE_RE.finditer(text)}
    return len([m for m in _HOUR_LINE_RE.finditer(text)]) >= 2 and len(hours) >= 2


def _part_text(part: Message) -> str:
    """Dekodierter Payload eines Parts (bytes→str, fail-soft)."""
    payload = part.get_payload(decode=True)
    if payload is None:
        return part.get_payload() or ""
    charset = part.get_content_charset() or "utf-8"
    try:
        return payload.decode(charset, errors="replace")
    except (LookupError, TypeError):
        return payload.decode("utf-8", errors="replace")


# --------------------------------------------------------------------------- #
# Format-spezifische Validierung
# --------------------------------------------------------------------------- #
def _validate_full(msg: Message) -> tuple[bool, list[str]]:
    errors: list[str] = []

    if not msg.is_multipart() or msg.get_content_type() != "multipart/alternative":
        errors.append(
            f"FULL: erwartet multipart/alternative, ist '{msg.get_content_type()}'"
        )

    html_parts = [p for p in msg.walk() if p.get_content_type() == "text/html"]
    plain_parts = [p for p in msg.walk() if p.get_content_type() == "text/plain"]
    if not html_parts:
        errors.append("FULL: kein text/html-Part vorhanden (multipart/alternative erwartet)")
    if not plain_parts:
        errors.append("FULL: kein text/plain-Part vorhanden")

    html = _part_text(html_parts[0]) if html_parts else ""

    if html and not _has_hourly_table(html):
        errors.append("FULL: keine sequenzielle Stundentabelle (>=2 HH:00-Zeilen) im HTML-Part")

    errors.extend(_check_plausibility(html))

    if not (msg["Subject"] or "").strip():
        errors.append("FULL: Subject ist leer")

    return len(errors) == 0, errors


def _check_plausibility(html: str) -> list[str]:
    """Selbst-Konsistenz der Werte (weit kalibriert gegen False-Positives)."""
    errors: list[str] = []
    ranges = _TEMP_RANGE_RE.findall(html)
    for lo_s, hi_s in ranges:
        lo, hi = int(lo_s), int(hi_s)
        if lo > hi:
            errors.append(f"FULL: Temperatur-Range unplausibel ({lo}°C > {hi}°C)")

    hours = _distinct_hours(html)
    for hour in hours:
        h = int(hour.split(":")[0])
        if h < 6 or h > 22:
            errors.append(f"FULL: Stunde {hour} ausserhalb Tagesfenster 06–22")

    return errors


def _validate_compact(msg: Message, max_bytes: int) -> tuple[bool, list[str]]:
    errors: list[str] = []

    if msg.is_multipart() or msg.get_content_type() != "text/plain":
        errors.append(
            f"COMPACT: erwartet single text/plain (kein multipart), "
            f"ist '{msg.get_content_type()}' multipart={msg.is_multipart()}"
        )
        # multipart → kein verlaesslicher Plain-Text; frueh raus
        return False, errors

    cte = (msg.get("Content-Transfer-Encoding") or "").strip().lower()
    text = _part_text(msg)

    # Accept quoted-printable when body is ASCII — production MIMEText(us-ascii)
    # emits 7bit; EmailMessage.set_content() may choose quoted-printable for long
    # lines but the decoded content is identical (Issue #733 F002).
    if not text.isascii():
        errors.append("COMPACT: Body ist nicht ASCII (7bit-Verletzung)")
    elif cte and cte not in ("7bit", "quoted-printable"):
        errors.append(f"COMPACT: Content-Transfer-Encoding '{cte}', erwartet 7bit")

    size = len(text.encode("utf-8"))
    if size >= max_bytes:
        errors.append(f"COMPACT: Body {size} Byte >= Limit {max_bytes} Byte (zu gross)")

    if _has_hourly_table_plain(text):
        errors.append("COMPACT: enthaelt sequenzielle Stundentabelle (>=2 HH:00-Zeilen) — verboten")

    errors.extend(_check_compact_blocks(text))

    return len(errors) == 0, errors


def _check_compact_blocks(text: str) -> list[str]:
    """Pflichtbloecke (HART): Kopf, Metriken-Ueberblick, Footer.

    Ausblick (Wetterlage:/Naechste Etappen) ist OPTIONAL — render_compact()
    laesst ihn bei fehlendem stability_result und leerem multi_day_trend
    legitim weg (Issue #733 F001-Fix).
    """
    errors: list[str] = []
    if not (" - " in text and "Report" in text):
        errors.append("COMPACT: Kopf-Zeile (Trip - ... Report) fehlt")
    if "== Metriken-Ueberblick ==" not in text:
        errors.append("COMPACT: Block '== Metriken-Ueberblick ==' fehlt")
    if "----" not in text or "Generated:" not in text:
        errors.append("COMPACT: Footer (Trennlinie + Generated:) fehlt")
    return errors


# --------------------------------------------------------------------------- #
# Oeffentliche API
# --------------------------------------------------------------------------- #
def validate_message(msg: Message, max_bytes: int = _MAX_BYTES_DEFAULT) -> tuple[bool, list[str]]:
    """Faellt das Urteil ueber ein geparstes email.message.Message-Objekt.

    Returnt (ok, errors). ok=True/errors=[] bei bestanden.
    """
    mail_type = msg["X-GZ-Mail-Type"]

    if mail_type is None:
        return False, [
            "Marker-Header X-GZ-Mail-Type fehlt — Mail nicht vom getaggten Renderer"
        ]

    if mail_type in ("compare", "deviation-alert"):
        return True, [
            f"Keine Trip-Briefing-Mail (Typ={mail_type}) — falscher Validator, uebersprungen"
        ]

    if mail_type != "trip-briefing":
        return False, [f"Unbekannter Mail-Typ '{mail_type}' (erwartet trip-briefing/compare/deviation-alert)"]

    mail_format = msg["X-GZ-Format"]
    if mail_format == "full":
        return _validate_full(msg)
    if mail_format == "compact":
        return _validate_compact(msg, max_bytes)

    return False, [f"Unbekanntes Format '{mail_format}' (erwartet full/compact)"]


# --------------------------------------------------------------------------- #
# Mail-Auswahl (Issue #780): gezielt die eigene Mail im geteilten Postfach finden
# --------------------------------------------------------------------------- #
def _decode_subject(raw: str | None) -> str:
    """Dekodiert ein (ggf. RFC-2047-kodiertes) Subject zu lesbarem str.

    Em-Dash/Umlaut-Subjects kommen per IMAP als `=?utf-8?b?...?=` zurueck. Wir
    dekodieren Python-seitig (NICHT IMAP SEARCH SUBJECT — Stalwart matcht nicht
    ueber Bindestriche, Lehre #731).
    """
    if not raw:
        return ""
    parts = []
    for chunk, enc in decode_header(raw):
        if isinstance(chunk, bytes):
            parts.append(chunk.decode(enc or "utf-8", errors="replace"))
        else:
            parts.append(chunk)
    return "".join(parts)


def _message_matches(
    headers: Message,
    mail_type: str | None = None,
    subject_contains: str | None = None,
) -> bool:
    """Praedikat: passt die Mail zu den Filtern? (testbar OHNE IMAP).

    - mail_type gesetzt: X-GZ-Mail-Type muss exakt gleich sein.
    - subject_contains gesetzt: dekodiertes Subject muss den Marker enthalten.
    - beide None: True (rueckwaertskompatibel — neueste Mail).
    """
    if mail_type is not None and headers.get("X-GZ-Mail-Type") != mail_type:
        return False
    if subject_contains is not None:
        subject = _decode_subject(headers.get("Subject"))
        if subject_contains not in subject:
            return False
    return True


# --------------------------------------------------------------------------- #
# CLI / IMAP
# --------------------------------------------------------------------------- #
def fetch_latest_message(
    mail_type: str | None = None,
    subject_contains: str | None = None,
    max_scan: int = 50,
) -> Message:
    """Holt die passende Mail aus dem Test-Postfach als Message-Objekt.

    Ohne Filter (beide None): neueste Mail (rueckwaertskompatibel, AC-8). Mit
    Filter: scannt die Header der bis zu `max_scan` neuesten Mails (newest-first)
    und liefert die erste, die `_message_matches` erfuellt (Issue #780).
    """
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent / "src"))
    from app.config import Settings

    settings = Settings()
    imap_host = settings.imap_host or settings.smtp_host
    imap_user = settings.imap_user or settings.smtp_user
    imap_pass = settings.imap_pass or settings.smtp_pass
    if not imap_user or not imap_pass:
        raise ValueError("IMAP nicht konfiguriert (GZ_IMAP_USER/GZ_IMAP_PASS)")

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
            if _message_matches(headers, mail_type, subject_contains):
                _, msg_data = imap.fetch(mid, "(RFC822)")
                return email.message_from_bytes(msg_data[0][1])

        raise ValueError(
            f"Keine passende Mail gefunden (mail_type={mail_type!r}, "
            f"subject_contains={subject_contains!r}, scan={max_scan})"
        )
    finally:
        try:
            imap.close()
            imap.logout()
        except Exception:
            pass


def run_validation(
    max_bytes: int = _MAX_BYTES_DEFAULT,
    mail_type: str | None = None,
    subject_contains: str | None = None,
    max_scan: int = 50,
) -> tuple[bool, list[str]]:
    """Holt die (optional gefilterte) Mail und validiert sie."""
    msg = fetch_latest_message(
        mail_type=mail_type, subject_contains=subject_contains, max_scan=max_scan
    )
    return validate_message(msg, max_bytes)


def _write_validation_log(success: bool, errors: list) -> None:
    """Strukturiertes Validator-Log YAML (fail-soft, Vorbild email_spec_validator)."""
    try:
        from datetime import datetime
        import tempfile
        import yaml as _yaml

        hooks_dir = Path(__file__).resolve().parent
        log_dir = hooks_dir.parent / "workflows" / "_log"
        log_dir.mkdir(parents=True, exist_ok=True)
        workflow_id = os.environ.get("GZ_ACTIVE_WORKFLOW", "unknown")
        date_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        log_path = log_dir / f"{date_str}_{workflow_id}_briefing_validation.yaml"

        data = {
            "validator": "briefing_mail_validator",
            "validated_at": datetime.utcnow().isoformat(),
            "workflow_id": workflow_id,
            "passed": bool(success),
            "error_count": len(errors),
            "errors": list(errors),
        }
        fd, tmp = tempfile.mkstemp(dir=str(log_dir), suffix=".tmp")
        with os.fdopen(fd, "w") as f:
            _yaml.safe_dump(data, f, allow_unicode=True)
        os.rename(tmp, str(log_path))
    except Exception:
        pass  # fail-soft


def main() -> None:
    parser = argparse.ArgumentParser(description="Briefing-Mail-Validator (#733)")
    parser.add_argument("--max-bytes", type=int, default=_MAX_BYTES_DEFAULT,
                        help="Byte-Limit fuer compact-Mails (default: 2048)")
    parser.add_argument("--mail-type", default=None,
                        help="Nur Mails mit diesem X-GZ-Mail-Type waehlen (#780)")
    parser.add_argument("--subject-contains", default=None,
                        help="Nur Mails waehlen, deren Subject diesen Marker enthaelt (#780)")
    parser.add_argument("--max-scan", type=int, default=50,
                        help="Wie viele neueste Mails maximal scannen (default: 50)")
    args = parser.parse_args()

    print("=" * 70)
    print("BRIEFING-MAIL-VALIDATOR (full + compact) — #733")
    print("=" * 70)
    print()

    try:
        success, errors = run_validation(
            args.max_bytes,
            mail_type=args.mail_type,
            subject_contains=args.subject_contains,
            max_scan=args.max_scan,
        )
    except Exception as e:  # IMAP / technischer Fehler
        print(f"⚠️  TECHNISCHER FEHLER: Mail konnte nicht geladen werden: {e}")
        _write_validation_log(success=False, errors=[str(e)])
        sys.exit(2)

    _write_validation_log(success=success, errors=errors)

    if success:
        for note in errors:
            print(f"  ℹ {note}")
        print("✅ Briefing-Mail-Checks bestanden.")
        sys.exit(0)

    print("❌ SPEC-VERLETZUNGEN GEFUNDEN:")
    print()
    for err in errors:
        print(f"  • {err}")
    print()
    sys.exit(1)


if __name__ == "__main__":
    main()
