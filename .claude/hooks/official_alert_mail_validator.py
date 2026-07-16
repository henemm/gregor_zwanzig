#!/usr/bin/env python3
"""
Official-Alert-Mail-Validator -- Issue #1197 (Luecke im Renderer-Mail-Gate).

Kanonischer Acceptance-Validator fuer die Standalone-Amtliche-Warnung-Mail
(Trip- und Compare-Pfad, gerendert von
`src/output/renderers/alert/official_alerts.py::render_official_alert_html`
via `render_warn_block(variant="standalone", ...)`). Holt die zuletzt
zugestellte Mail aus dem Test-Postfach, erkennt anhand des Marker-Headers
X-GZ-Mail-Type: official-alert und prueft sie auf Plausibilitaet.

Bislang deckte KEIN Validator diesen sicherheitskritischen Mail-Typ ab --
`radar_alert_mail_validator.py` prueft ausschliesslich X-GZ-Mail-Type:
radar-alert und behandelt official-alert-Mails als No-Op. Dieses Modul
schliesst die Luecke.

Vorbild: radar_alert_mail_validator.py (IMAP-Fetch, Exit 0/1/2, YAML-Log).
Stdlib only -- als isoliertes Modul ladbar (keine relativen Importe).

Struktur-Pruefung: der HTML-Body wird mit `html.parser.HTMLParser` (stdlib)
geparst, um die tatsaechlich vom Renderer emittierten CSS-Klassen-Tokens zu
sammeln (kein Substring-Fund auf den Rohtext -- eine Klasse zaehlt nur, wenn
sie als `class="..."`-Attributwert auftaucht). Zusaetzlich wird der
extrahierte Text auf die deterministischen Textbausteine der SOLL-Vorlage
(#1233 Slice B) geprueft: Verdict-Anzahl (Ziffer > 0), Warnstufe, Gueltig-
Zeitangabe, Quelle-Zeile, Stand-Footer.

Exit codes:
    0 = alle Checks bestanden (oder Mail ist kein official-alert -> No-Op)
    1 = Spec-Verletzung mit konkreter Fehlerliste
    2 = technischer Fehler (IMAP nicht erreichbar)
"""
from __future__ import annotations

import email
import imaplib
import os
import re
import sys
from email.message import Message
from html.parser import HTMLParser
from pathlib import Path

# Issue #1282 AC-4: shared-repo _log-Aufloesung (git-common-dir) -- gleiches
# Muster wie renderer_mail_gate.py fuer hook_utils (sys.path-Erweiterung fuer
# standalone-Aufruf, kein relativer Import noetig).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _e2e_paths  # noqa: E402

# Verdict-Zeile: "{N} amtliche Warnung" / "{N} amtliche Warnungen".
_VERDICT_RE = re.compile(r"(\d+)\s+amtliche Warnung(?:en)?")

# Warnstufen-Woerter (Leiter bei uniformer Stufe, Meter/Headline bei gemischten).
# Bewusst OHNE \b-Wortgrenzen: die Tag-Strip-Ableitung des Plain-Text-Parts
# (build_mime_message) fuegt zwischen benachbarten Inline-Elementen KEIN
# Leerzeichen ein (z.B. "GELBORANGEROT" in der Warnstufen-Leiter) -- ein
# Boundary-Check wuerde dort systematisch fehlschlagen, obwohl die
# Warnstufe strukturell vorhanden ist (zusaetzlich ueber S-2 abgesichert).
_LEVEL_WORD_RE = re.compile(r"(GELB|ORANGE|ROT)")

# Gueltigkeits-Zeile (P-3, Issue #1240): jedes Vorkommen mitsamt seinem Wert bis
# zum Zeilen- bzw. Element-Ende. Der Plain-Text-Part ist tag-gestrippt, der
# HTML-Part nicht -- deshalb endet der Wert am Umbruch ODER am naechsten Tag.
_VALIDITY_RE = re.compile(r"Gültig:\s*([^\n<]*)")
# Plausibler Zeitraum: DE-Wochentag + Datum, so wie `_format_validity` emittiert
# ("Sa 12.07. - ganztaegig" bzw. "Sa 12.07. - 15:00-21:00"). Alles andere --
# insbesondere "unbekannt" oder ein leerer Wert -- ist KEINE Zeitangabe.
_VALIDITY_VALUE_RE = re.compile(r"\b(Mo|Di|Mi|Do|Fr|Sa|So)\s+\d{2}\.\d{2}\.")

# CSS-Klassen, die die SOLL-Vorlage (#1233 Slice B) fuer die Standalone-
# Amtliche-Warnung-Mail zwingend emittiert.
_REQUIRED_CLASSES = {"verdict", "warn", "src", "body-foot"}
# Warnstufen-Traeger: Leiter (uniform) ODER Eskalations-Meter (gemischt).
_LADDER_CLASSES = {"stufe-line"}
_MIXED_METER_CLASSES = {"stacked", "meter"}


class _ClassCollector(HTMLParser):
    """Sammelt alle `class="..."`-Attributwert-Tokens der HTML-Struktur.

    Bewusst OHNE Baum-/Nesting-Tracking (robust gegen unbalancierte Void-Tags
    wie `<br>` in der generierten Mail-HTML) -- ein Token zaehlt nur, wenn es
    tatsaechlich als Klassen-Attributwert auftaucht, nicht wenn das Wort
    irgendwo im Fliesstext vorkommt. Das unterscheidet die Pruefung von einer
    naiven Substring-Suche im Rohtext."""

    def __init__(self) -> None:
        super().__init__()
        self.classes: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if name == "class" and value:
                self.classes.update(value.split())


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


def _extract_parts(msg: Message) -> tuple[str, str]:
    """Extrahiert (plain_text, html) aus der Mail (alle Parts)."""
    plain_parts: list[str] = []
    html_parts: list[str] = []
    if msg.is_multipart():
        for part in msg.walk():
            ctype = part.get_content_type()
            if ctype == "text/plain":
                plain_parts.append(_part_text(part))
            elif ctype == "text/html":
                html_parts.append(_part_text(part))
    else:
        body = _part_text(msg)
        if msg.get_content_type() == "text/html":
            html_parts.append(body)
        else:
            plain_parts.append(body)
    return "\n".join(plain_parts), "\n".join(html_parts)


def validate_message(msg: Message) -> tuple[bool, list[str]]:
    """Faellt das Urteil ueber ein geparstes email.message.Message-Objekt.

    Returnt (ok, errors):
    - Falscher Mail-Typ (nicht official-alert): (True, [Info]) -- sauberes No-Op.
    - Alle Checks bestanden: (True, []).
    - Mind. ein Check schlaegt fehl: (False, [Fehlerliste]).
    """
    mail_type = msg.get("X-GZ-Mail-Type")

    if mail_type is None or mail_type != "official-alert":
        info = (
            f"Kein official-alert-Header (X-GZ-Mail-Type={mail_type!r}) "
            "-- falscher Validator, uebersprungen"
        )
        return True, [info]

    plain, html = _extract_parts(msg)
    # Faellt der HTML-Part aus (z.B. non-multipart-Mail), auf den Plain-Text
    # zurueckfallen -- der enthaelt (per build_mime_message) den taggeloeschten
    # HTML-Body und traegt daher noch die Textbausteine, nur keine Klassen.
    text = plain or html
    errors: list[str] = []

    collector = _ClassCollector()
    try:
        collector.feed(html)
    except Exception as exc:  # fail-closed: kaputtes HTML ist ein echter Befund
        errors.append(f"S-0: HTML-Body nicht parsbar: {exc}")

    missing_classes = _REQUIRED_CLASSES - collector.classes
    if missing_classes:
        errors.append(
            "S-1: Erwartete CSS-Struktur-Klassen fehlen im HTML-Body: "
            f"{sorted(missing_classes)}. Gefundene Klassen: {sorted(collector.classes)}"
        )

    has_ladder = bool(_LADDER_CLASSES & collector.classes)
    has_mixed_meter = _MIXED_METER_CLASSES <= collector.classes
    if not (has_ladder or has_mixed_meter):
        errors.append(
            "S-2: Weder Warnstufen-Leiter ('stufe-line', uniform) noch "
            "Eskalations-Meter ('warn stacked'/'meter', gemischt) im HTML-Body "
            f"gefunden. Gefundene Klassen: {sorted(collector.classes)}"
        )

    verdict_match = _VERDICT_RE.search(text)
    if not verdict_match or int(verdict_match.group(1)) < 1:
        errors.append(
            "P-1: Keine plausible Verdict-Zeile '{N} amtliche Warnung(en)' mit "
            f"N>=1 gefunden. Text-Ausschnitt: {text[:160]!r}"
        )

    if not _LEVEL_WORD_RE.search(text):
        errors.append(
            "P-2: Keine Warnstufe (GELB/ORANGE/ROT) im Text erkennbar."
        )

    # P-3 (Issue #1240): Die ANWESENHEIT der Gueltigkeits-Zeile ist kein taugliches
    # Kriterium -- Praefektur-Zugangssperren und Waldbrand-Tagesstufen liefern keine
    # valid_from/valid_to, ihre Warnungen tragen zu Recht keine Zeile (PO-Entscheidung
    # #1238). Geprueft wird stattdessen der INHALT: steht eine Zeile da, MUSS sie
    # einen echten Zeitraum tragen. Damit faellt "Gueltig: unbekannt" -- der von
    # #1238 beanstandete Zustand -- kuenftig durch, statt durchgewinkt zu werden.
    for raw_value in _VALIDITY_RE.findall(text):
        value = raw_value.strip()
        if not _VALIDITY_VALUE_RE.search(value):
            errors.append(
                "P-3: 'Gültig:'-Zeile ohne plausible Zeitangabe "
                f"(Wochentag + Datum erwartet, gefunden: {value!r}). Warnungen ohne "
                "bekannten Zeitraum tragen gar keine Gültig-Zeile."
            )

    if "Quelle:" not in text or "abgerufen bei" not in text:
        errors.append(
            "P-4: Quelle nicht sichtbar -- 'Quelle:' und/oder 'abgerufen bei' "
            "fehlt im Body."
        )

    if "Stand: heute" not in text:
        errors.append("P-5: 'Stand: heute'-Footer fehlt im Body.")

    return len(errors) == 0, errors


def _write_validation_log(success: bool, errors: list) -> None:
    """Strukturiertes Validator-Log YAML (fail-soft).

    Issue #1282 AC-4: log_dir liegt im shared-repo (git-common-dir via
    _e2e_paths.shared_repo_dir), Fail-soft-Fallback auf die alte __file__-
    relative Berechnung (z.B. ausserhalb eines Git-Repos).
    """
    try:
        from datetime import datetime
        import tempfile

        hooks_dir = Path(__file__).resolve().parent
        fallback_log_dir = hooks_dir.parent / "workflows" / "_log"
        try:
            shared = _e2e_paths.shared_repo_dir(cwd=hooks_dir)
        except Exception:
            shared = None
        log_dir = (shared / ".claude" / "workflows" / "_log") if shared else fallback_log_dir
        log_dir.mkdir(parents=True, exist_ok=True)
        workflow_id = os.environ.get("OPENSPEC_ACTIVE_WORKFLOW", "unknown")
        date_str = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        log_path = log_dir / f"{date_str}_{workflow_id}_official_alert_validation.yaml"

        lines = [
            f"validator: official_alert_mail_validator",
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
    """Holt die neueste official-alert-Mail aus dem Test-Postfach."""
    src_dir = Path(__file__).resolve().parents[2] / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    from app.config import Settings

    settings = Settings()
    imap_host = settings.imap_host or settings.smtp_host
    # Standalone-Amtliche-Warnung-Mails werden an gregor-test@henemm.com
    # gesendet (Test-Postfach). Priorisiere GZ_TEST_IMAP_*, falle auf
    # GZ_IMAP_* zurueck.
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
            if headers.get("X-GZ-Mail-Type") == "official-alert":
                _, msg_data = imap.fetch(mid, "(RFC822)")
                return email.message_from_bytes(msg_data[0][1])

        raise ValueError(
            f"Keine official-alert-Mail gefunden (scan={max_scan} Mails)"
        )
    finally:
        try:
            imap.close()
            imap.logout()
        except Exception:
            pass


def main() -> None:
    print("=" * 70)
    print("OFFICIAL-ALERT-MAIL-VALIDATOR -- #1197")
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
        print("OK Official-Alert-Mail-Checks bestanden.")
        sys.exit(0)

    print("SPEC-VERLETZUNGEN GEFUNDEN:")
    print()
    for err in errors:
        print(f"  - {err}", file=sys.stderr)
    print()
    sys.exit(1)


if __name__ == "__main__":
    main()
