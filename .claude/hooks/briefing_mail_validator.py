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

_WIND_TOL = 3       # km/h (AC-3)
_SONNE_TOL_MIN = 5  # min (AC-4)


class RenderUnavailable(Exception):
    """Playwright/Browser fehlt → Exit 2, nicht Exit 1 (technischer Fehler, AC-1)."""


# --------------------------------------------------------------------------- #
# Hilfsfunktionen
# --------------------------------------------------------------------------- #
def _distinct_hours(text: str, html: bool = False) -> list[str]:
    """Distinct HH:00-Treffer in Reihenfolge des ersten Auftretens.

    Fuer HTML (html=True) werden Pill-Zeiten (mitten im Text) ignoriert, indem
    nur Treffer in <td> oder am Zeilenanfang (mobile <pre>) gewertet werden (#836).
    """
    seen: list[str] = []
    if html:
        # Erfasst:
        # 1. <td data-label="Time">HH:00</td>
        # 2. <td>HH:00</td>
        # 3. \n  HH:00   (mobile compact <pre>)
        # 4. >HH:00 (Start einer Zelle ohne data-label, fail-soft)
        pattern = re.compile(r'(?:data-label="Time">|<td>|>|(?:\n|^)\s*)([01]?\d|2[0-3]):00(?:\s|</td>|&nbsp;|<)')
        for m in pattern.finditer(text):
            h = f"{m.group(1)}:00"
            if h not in seen:
                seen.append(h)
    else:
        for m in _HOUR_RE.finditer(text):
            if m.group(0) not in seen:
                seen.append(m.group(0))
    return seen


def _has_hourly_table(text: str) -> bool:
    """Heuristik: >=2 distinct/sequenzielle HH:00 = Stundentabelle.

    HTML (full): jede Zelle, daher der breite \\bHH:00\\b-Treffer.
    """
    return len(_distinct_hours(text, html=True)) >= 2


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


# Issue #833 — Parser-Helfer (HTML-Struktur statt String-Presence)
_TH_RE = re.compile(r"<th[^>]*>(.*?)</th>", re.IGNORECASE | re.DOTALL)
_ROW_RE = re.compile(r"<tr[^>]*>(.*?)</tr>", re.IGNORECASE | re.DOTALL)
_TD_RE = re.compile(r"<td[^>]*>(.*?)</td>", re.IGNORECASE | re.DOTALL)
# Issue #863 — nur tbody-Inhalt scannen (Trend-Tabelle hat kein tbody)
_TBODY_RE = re.compile(r"<tbody[^>]*>(.*?)</tbody>", re.IGNORECASE | re.DOTALL)
_SPAN_RE = re.compile(r"<span[^>]*>(.*?)</span>", re.IGNORECASE | re.DOTALL)
_MOBILE_PRE_RE = re.compile(
    r'class="[^"]*mobile-compact[^"]*".*?<pre[^>]*>(.*?)</pre>',
    re.IGNORECASE | re.DOTALL,
)
_TAG_RE = re.compile(r"<[^>]+>")


def _strip_tags(s: str) -> str:
    return _TAG_RE.sub("", s).strip()


def _th_tokens(html: str) -> list[str]:
    """Alle <th>-Inhalte (Tags gestrippt)."""
    return [_strip_tags(m) for m in _TH_RE.findall(html)]


def _mobile_header_tokens(html: str) -> list[str]:
    """Erste nicht-leere Zeile im .mobile-compact-<pre>, per Whitespace gesplittet."""
    m = _MOBILE_PRE_RE.search(html)
    if not m:
        return []
    for line in _strip_tags(m.group(1)).splitlines():
        if line.strip():
            return line.split()
    return []


def _column_values(html: str, header_de: str) -> list[float]:
    """Numerische Zellwerte der Spalte mit th-Text == header_de (über th-INDEX).

    Mappt NICHT über data-label (kann englisch sein), nur über die Header-Reihe.
    Scannt ausschließlich <tbody>-Inhalte — Trend-/Stats-Tabellen ohne tbody
    werden damit ignoriert (Issue #863).
    """
    headers = _th_tokens(html)
    try:
        idx = headers.index(header_de)
    except ValueError:
        return []
    tbody_content = " ".join(m.group(1) for m in _TBODY_RE.finditer(html))
    values: list[float] = []
    for row_html in _ROW_RE.findall(tbody_content):
        cells = _TD_RE.findall(row_html)
        if idx >= len(cells):
            continue
        num = re.search(r"-?\d+(?:\.\d+)?", _strip_tags(cells[idx]))
        if num:
            values.append(float(num.group(0)))
    return values


def _column_hours_sum(html: str, *header_names: str) -> float | None:
    """Summe der ‚X.Y h'-Zellen der Spalte (Sonne). None, wenn keine ‚h'-Zahl."""
    headers = _th_tokens(html)
    idx = next((headers.index(h) for h in header_names if h in headers), None)
    if idx is None:
        return None
    total = 0.0
    found = False
    for row_html in _ROW_RE.findall(html):
        cells = _TD_RE.findall(row_html)
        if idx >= len(cells):
            continue
        m = re.search(r"(\d+(?:\.\d+)?)\s*h\b", _strip_tags(cells[idx]))
        if m:
            total += float(m.group(1))
            found = True
    return total if found else None


def _column_num_sum(html: str, *header_names: str) -> float | None:
    """Summe numerischer Zellen der Spalte. None, wenn Spalte fehlt."""
    headers = _th_tokens(html)
    idx = next((headers.index(h) for h in header_names if h in headers), None)
    if idx is None:
        return None
    return sum(_column_values(html, headers[idx]))


def _pills(html: str) -> list[str]:
    """Pill-Texte aus dem Metriken-Überblick (alle <span>-Inhalte)."""
    return [_strip_tags(s) for s in _SPAN_RE.findall(html)]


def _check_layer_consistency(html: str) -> list[str]:
    """AC-3: Pill-Spitzenwert vs. Tabellen-Spalten-Max (Toleranz _WIND_TOL)."""
    errors: list[str] = []
    pill_re = re.compile(
        r"([A-Za-zÄÖÜäöüß]+)\s+ab\s+\d{1,2}:\d{2}.*?(\d+)\s*km/h"
    )
    for pill in _pills(html):
        m = pill_re.search(pill)
        if not m:
            continue
        label, value = m.group(1), float(m.group(2))
        col = _column_values(html, label)
        if not col:
            continue
        col_max = max(col)
        if abs(value - col_max) > _WIND_TOL:
            errors.append(
                f"FULL: Ebenen-Widerspruch '{label}' — Pill {value:g} vs. "
                f"Tabellen-Max {col_max:g} (km/h, > {_WIND_TOL})"
            )
    return errors


def _check_metric_plausibility(html: str) -> list[str]:
    """AC-4: Sonne-Pill vs. Σ Sonnenstunden; ‚kein Regen' vs. Regen-Summe."""
    errors: list[str] = []
    for pill in _pills(html):
        m = re.search(r"Sonne\s+(\d+)\s*min", pill)
        if not m:
            continue
        pill_min = int(m.group(1))
        sun_h = _column_hours_sum(html, "Sonne", "Sun")
        if sun_h is None:
            continue  # Einfach-Modus (Emoji, keine Zahl) → überspringen
        if abs(pill_min - sun_h * 60) > _SONNE_TOL_MIN:
            errors.append(
                f"FULL: Sonne-Widerspruch — Pill {pill_min} min vs. Tabelle "
                f"{sun_h * 60:.0f} min (> {_SONNE_TOL_MIN})"
            )

    overview = " ".join(_pills(html))
    if "kein Regen" in overview:
        rain = _column_num_sum(html, "Regen", "Rain")
        if rain is not None and rain >= 0.1:
            errors.append(
                f"FULL: ‚kein Regen' widerspricht Tabellen-Summe {rain:g} mm"
            )
    return errors


def _data_visible(page) -> bool:
    """True, wenn bei diesem Viewport eine Wetterdaten-Tabelle sichtbar ist.

    Sichtbar = irgendeine `table.resp` ODER `.mobile-compact` mit offsetHeight>0
    und display!='none'. Eine flache (nicht responsiv gewrappte) Tabelle ist bei
    jeder Breite sichtbar; nur ein per @media versteckter Block ohne Gegenstueck
    macht den Viewport leer (AC-1, #831-Klasse).
    """
    return page.evaluate(
        "()=>{const els=document.querySelectorAll('table.resp,.mobile-compact');"
        "for(const el of els){const s=getComputedStyle(el);"
        "if(el.offsetHeight>0 && s.display!=='none') return true;} return false;}"
    )


def _selector_present_and_visible(page, selector: str) -> tuple[bool, bool]:
    """(existiert, sichtbar) fuer einen Selektor im aktuellen Viewport."""
    res = page.evaluate(
        "(sel)=>{const el=document.querySelector(sel);"
        "if(!el) return [false,false];const s=getComputedStyle(el);"
        "return [true, el.offsetHeight>0 && s.display!=='none'];}",
        selector,
    )
    return bool(res[0]), bool(res[1])


def _check_rendered(html: str) -> list[str]:
    """AC-1: headless Render bei 390px und 1000px; Daten muessen sichtbar bleiben.

    Fehlt Playwright/Browser → RenderUnavailable (Exit 2), NICHT Exit 1.
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RenderUnavailable(f"Playwright nicht installiert: {e}")
    import tempfile

    errors: list[str] = []
    tmp = tempfile.NamedTemporaryFile(suffix=".html", delete=False, mode="w")
    try:
        tmp.write(html)
        tmp.close()
        url = f"file://{tmp.name}"
        try:
            ctx = sync_playwright().start()
            browser = ctx.chromium.launch(headless=True)
        except Exception as e:
            raise RenderUnavailable(f"Browser-Launch fehlgeschlagen: {e}")
        try:
            wrong = {390: ".desktop-only", 1000: ".mobile-compact"}
            for w, lbl in ((390, "390px (mobil)"), (1000, "1000px (Desktop)")):
                page = browser.new_page(viewport={"width": w, "height": 844})
                page.goto(url, timeout=10000)
                page.wait_for_load_state("networkidle")
                if not _data_visible(page):
                    errors.append(
                        f"FULL: bei {lbl} ist keine Wetterdaten-Tabelle sichtbar "
                        f"(Viewport leer — responsiver Block ohne Gegenstueck?)"
                    )
                exists, visible = _selector_present_and_visible(page, wrong[w])
                if exists and visible:
                    errors.append(
                        f"FULL: bei {lbl} ist '{wrong[w]}' sichtbar — muss bei "
                        f"dieser Breite versteckt sein (Dual-Render, #794)"
                    )
        finally:
            browser.close()
            ctx.stop()
    finally:
        try:
            os.unlink(tmp.name)
        except OSError:
            pass
    return errors


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

    if html:
        errors.extend(_check_rendered(html))            # AC-1 (kann RenderUnavailable werfen)
        errors.extend(_check_layer_consistency(html))   # AC-3
        errors.extend(_check_metric_plausibility(html))  # AC-4

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

    hours = _distinct_hours(html, html=True)
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
        workflow_id = os.environ.get("OPENSPEC_ACTIVE_WORKFLOW", "unknown")
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
