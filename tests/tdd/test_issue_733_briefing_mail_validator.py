"""TDD RED — Issue #733: Kanonischer Validator für Trip-Briefing-Mails.

Beweist Verhalten (kein Mock, keine Dateiinhalt-Checks):
- Layer A: build_mime_message() setzt die Marker-Header X-GZ-Mail-Type / X-GZ-Format
  (echte MIME-Objekt-Inspektion, Muster wie test_issue_722_email_compact.py).
- Layer B: briefing_mail_validator.validate_message() fällt sein Urteil über
  echt konstruierte MIME-Nachrichten (serialisiert + reparst → Wire-Format).

Die End-to-End-Zustellung (Header in echt zugestellter Mail via IMAP) wird in
der Acceptance-Stage gegen Staging geprüft; hier wird die reine MIME-/Validator-
Logik mit realen email.message-Objekten bewiesen.
"""
from __future__ import annotations

import email
import importlib.util
from email.message import EmailMessage
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR_PATH = REPO_ROOT / ".claude" / "hooks" / "briefing_mail_validator.py"


def _load_validator():
    """Lade den Validator als isoliertes Modul (vermeidet sys.modules-Kontamination)."""
    spec = importlib.util.spec_from_file_location("bmv733", str(VALIDATOR_PATH))
    if spec is None or spec.loader is None:
        raise ImportError(f"Validator nicht ladbar: {VALIDATOR_PATH}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


# --------------------------------------------------------------------------- #
# MIME-Builder (echte Nachrichten, kein Mock)
# --------------------------------------------------------------------------- #
_VALID_FULL_HTML = (
    '<div>Tag 3 - GR20</div>'
    '<table data-table="resp" style="width:100%;border-collapse:collapse;"><thead><tr><th>Time</th><th>Temp</th></tr></thead><tbody>'
    '<tr><td data-label="Time">08:00</td><td>12°C</td></tr>'
    '<tr><td data-label="Time">09:00</td><td>14°C</td></tr>'
    '<tr><td data-label="Time">10:00</td><td>15°C</td></tr>'
    '</tbody></table>'
    '<div>05 · Ausblick</div><div>Nächste Etappen</div>'
    '<table><tr><td>Mi · Etappe 4</td></tr>'
    '<tr><td>12–18°C</td><td>2mm</td><td>15 km/h</td></tr></table>'
)

_VALID_COMPACT_TEXT = (
    "WANDERWETTER\n"
    "GR20 - Evening Report\n"
    "Etappe 3\n"
    "11.06.2026\n"
    "\n"
    "== Metriken-Ueberblick ==\n"
    "  [OK] Wind max 25 km/h\n"
    "  [WARN] Regen 4mm\n"
    "\n"
    "Wetterlage: WECHSELHAFT - Die Lage ist im Uebergang. "
    "Prognosen ab Tag 3 mit Vorsicht behandeln.\n"
    "\n"
    "Naechste Etappen\n"
    "Mi  Etappe 4                   12-18C   2mm   15\n"
    "\n"
    "----------------------------------------\n"
    "Generated: 2026-06-11 08:00 UTC\n"
    "Data: open-meteo (icon)\n"
)


def _wire(msg: EmailMessage) -> email.message.Message:
    """Serialisiere und reparse — exakt das, was IMAP zurückliefert."""
    return email.message_from_bytes(msg.as_bytes())


def _build_full(html: str = _VALID_FULL_HTML, plain: str = "GR20 Evening Report\nTag 3",
                subject: str = "GR20 - Evening Report",
                with_html_part: bool = True) -> email.message.Message:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = "gregor_zwanzig@henemm.com"
    msg["To"] = "gregor-test@henemm.com"
    msg["X-GZ-Mail-Type"] = "trip-briefing"
    msg["X-GZ-Format"] = "full"
    msg.set_content(plain)
    if with_html_part:
        msg.add_alternative(html, subtype="html")
    return _wire(msg)


def _build_compact(text: str = _VALID_COMPACT_TEXT,
                   multipart: bool = False) -> email.message.Message:
    msg = EmailMessage()
    msg["Subject"] = "GR20 - Evening Report"
    msg["From"] = "gregor_zwanzig@henemm.com"
    msg["To"] = "gregor-test@henemm.com"
    msg["X-GZ-Mail-Type"] = "trip-briefing"
    msg["X-GZ-Format"] = "compact"
    msg.set_content(text)
    if multipart:
        msg.add_alternative("<p>" + text + "</p>", subtype="html")
    return _wire(msg)


def _build_compare() -> email.message.Message:
    msg = EmailMessage()
    msg["Subject"] = "Wetter-Vergleich: GR20 (11.06.2026)"
    msg["From"] = "gregor_zwanzig@henemm.com"
    msg["To"] = "gregor-test@henemm.com"
    msg["X-GZ-Mail-Type"] = "compare"
    msg["X-GZ-Format"] = "full"
    msg.set_content("Vergleich plain")
    msg.add_alternative("<table>Vergleich</table>", subtype="html")
    return _wire(msg)


# --------------------------------------------------------------------------- #
# Layer A — Marker-Header in build_mime_message (AC-1, AC-2, AC-3)
# --------------------------------------------------------------------------- #
class TestMarkerHeaders:
    def test_ac1_full_briefing_carries_trip_briefing_full_markers(self):
        """AC-1: full-Briefing-Mail trägt X-GZ-Mail-Type:trip-briefing + X-GZ-Format:full."""
        from outputs.email import build_mime_message
        msg = build_mime_message(
            subject="GR20 - Evening Report", body="<h1>Wetter</h1>",
            from_addr="gregor_zwanzig@henemm.com", to_header="gregor-test@henemm.com",
            reply_to=None, html=True, plain_text_body="Wetter",
            mail_type="trip-briefing", mail_format="full",
        )
        assert msg["X-GZ-Mail-Type"] == "trip-briefing"
        assert msg["X-GZ-Format"] == "full"

    def test_ac2_compact_briefing_carries_compact_markers_and_is_text_plain(self):
        """AC-2: compact-Briefing trägt trip-briefing/compact und ist single text/plain."""
        from outputs.email import build_mime_message
        msg = build_mime_message(
            subject="GR20 - Evening Report", body="GR20 plain compact",
            from_addr="gregor_zwanzig@henemm.com", to_header="gregor-test@henemm.com",
            reply_to=None, html=False, plain_text_body=None,
            mail_type="trip-briefing", mail_format="compact",
        )
        assert msg["X-GZ-Mail-Type"] == "trip-briefing"
        assert msg["X-GZ-Format"] == "compact"
        assert msg.get_content_type() == "text/plain"
        assert not msg.is_multipart()

    def test_ac3_compare_mail_carries_compare_marker(self):
        """AC-3: Orts-Vergleich-Mail trägt X-GZ-Mail-Type:compare (kein Briefing-Tag)."""
        from outputs.email import build_mime_message
        msg = build_mime_message(
            subject="Wetter-Vergleich: GR20", body="<table>x</table>",
            from_addr="gregor_zwanzig@henemm.com", to_header="gregor-test@henemm.com",
            reply_to=None, html=True, plain_text_body="x",
            mail_type="compare", mail_format="full",
        )
        assert msg["X-GZ-Mail-Type"] == "compare"

    def test_marker_optional_backward_compat(self):
        """Ohne mail_type/mail_format bleibt die Mail unverändert (Service-Error-Mail etc.)."""
        from outputs.email import build_mime_message
        msg = build_mime_message(
            subject="x", body="x", from_addr="a@b.c", to_header="d@e.f",
            reply_to=None, html=False, plain_text_body=None,
        )
        assert msg["X-GZ-Mail-Type"] is None
        assert msg["X-GZ-Format"] is None


# --------------------------------------------------------------------------- #
# Layer B — Validator-Urteil full (AC-4, AC-5)
# --------------------------------------------------------------------------- #
class TestValidatorFull:
    def test_ac4_plausible_full_passes(self):
        """AC-4: plausible full-Mail (multipart, HTML+Plain, Stundentabelle, Werte ok) → Exit 0."""
        bmv = _load_validator()
        ok, errors = bmv.validate_message(_build_full())
        assert ok, f"plausible full-Mail muss bestehen, errors={errors}"
        assert errors == []

    def test_ac5_inverted_temperature_fails(self):
        """AC-5: temp_lo > temp_hi (18–12°C) → Exit 1 mit konkreter Temperatur-Meldung."""
        bmv = _load_validator()
        bad_html = _VALID_FULL_HTML.replace("12–18°C", "18–12°C")
        ok, errors = bmv.validate_message(_build_full(html=bad_html))
        assert not ok
        assert any("temp" in e.lower() for e in errors), errors

    def test_ac5_missing_html_part_fails(self):
        """AC-5: als full getaggt, aber kein HTML-Part (single text/plain) → Exit 1."""
        bmv = _load_validator()
        ok, errors = bmv.validate_message(_build_full(with_html_part=False))
        assert not ok
        assert any("html" in e.lower() or "multipart" in e.lower() for e in errors), errors

    def test_ac5_empty_hourly_table_fails(self):
        """AC-5: full ohne sequenzielle Stundentabelle → Exit 1."""
        bmv = _load_validator()
        no_hours = (
            '<div>Tag 3 - GR20</div><div>Nächste Etappen</div>'
            '<table><tr><td>12–18°C</td></tr></table>'
        )
        ok, errors = bmv.validate_message(_build_full(html=no_hours))
        assert not ok
        assert any("stunde" in e.lower() or "table" in e.lower() or "tabelle" in e.lower()
                   for e in errors), errors


# --------------------------------------------------------------------------- #
# Layer B — Validator-Urteil compact (AC-6)
# --------------------------------------------------------------------------- #
class TestValidatorCompact:
    def test_ac6_plausible_compact_passes(self):
        """AC-6: gültige compact-Mail (text/plain, 7bit, ascii, klein, alle Blöcke) → Exit 0."""
        bmv = _load_validator()
        ok, errors = bmv.validate_message(_build_compact())
        assert ok, f"plausible compact-Mail muss bestehen, errors={errors}"
        assert errors == []

    def test_ac6_multipart_compact_fails(self):
        """AC-6: compact die multipart ist → Exit 1."""
        bmv = _load_validator()
        ok, errors = bmv.validate_message(_build_compact(multipart=True))
        assert not ok
        assert any("multipart" in e.lower() or "text/plain" in e.lower() for e in errors), errors

    def test_ac6_compact_with_hourly_table_fails(self):
        """AC-6: compact die eine Stundentabelle enthält → Exit 1."""
        bmv = _load_validator()
        with_hours = _VALID_COMPACT_TEXT + (
            "\n08:00  12C  0mm  10\n09:00  13C  0mm  12\n10:00  14C  1mm  15\n"
        )
        ok, errors = bmv.validate_message(_build_compact(text=with_hours))
        assert not ok
        assert any("stunde" in e.lower() or "tabelle" in e.lower() for e in errors), errors

    def test_ac6_compact_too_large_fails(self):
        """AC-6: compact > 2 KB → Exit 1."""
        bmv = _load_validator()
        big = _VALID_COMPACT_TEXT + ("X" * 2200)
        ok, errors = bmv.validate_message(_build_compact(text=big))
        assert not ok
        assert any("kb" in e.lower() or "byte" in e.lower() or "gross" in e.lower()
                   or "groß" in e.lower() or "2" in e for e in errors), errors

    def test_ac6_compact_without_outlook_passes(self):
        """F001-Fix: gültige compact-Mail OHNE Ausblick-Block muss bestehen.

        render_compact() lässt Wetterlage:/Naechste-Etappen weg, wenn
        stability_result=None und multi_day_trend leer/None ist (Morgen-Report).
        Der Validator darf das NICHT als Fehler werten — gate-erosion-Schutz.
        """
        no_outlook = (
            "WANDERWETTER\n"
            "GR20 - Morning Report\n"
            "Etappe 3\n"
            "11.06.2026\n"
            "\n"
            "== Metriken-Ueberblick ==\n"
            "  [OK] Wind max 20 km/h\n"
            "  [OK] Regen 1mm\n"
            "\n"
            "----------------------------------------\n"
            "Generated: 2026-06-11 05:30 UTC\n"
            "Data: open-meteo (icon)\n"
        )
        bmv = _load_validator()
        ok, errors = bmv.validate_message(_build_compact(text=no_outlook))
        assert ok, f"compact-Mail ohne Ausblick muss bestehen (F001), errors={errors}"
        assert errors == []


# --------------------------------------------------------------------------- #
# Layer B — Dispatch / No-Op bei compare (AC-7)
# --------------------------------------------------------------------------- #
class TestValidatorDispatch:
    def test_ac7_compare_tagged_is_clean_noop(self):
        """AC-7: compare-getaggte Mail → kein struktureller Fehlalarm, Exit 0 (No-Op)."""
        bmv = _load_validator()
        ok, errors = bmv.validate_message(_build_compare())
        assert ok, f"compare-Mail darf nicht als kaputtes Briefing durchfallen, errors={errors}"
        # No-Op-Meldung statt struktureller Fehler
        assert any("compare" in e.lower() or "vergleich" in e.lower() or "briefing" in e.lower()
                   for e in errors) or errors == []

    def test_missing_marker_header_fails(self):
        """Mail ohne Marker-Header (nicht vom getaggten Renderer) → Exit 1 mit klarer Meldung."""
        bmv = _load_validator()
        msg = EmailMessage()
        msg["Subject"] = "Random"
        msg["From"] = "a@b.c"
        msg["To"] = "d@e.f"
        msg.set_content("kein marker")
        ok, errors = bmv.validate_message(_wire(msg))
        assert not ok
        assert any("marker" in e.lower() or "x-gz" in e.lower() for e in errors), errors
