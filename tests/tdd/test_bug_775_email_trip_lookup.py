"""TDD RED — Bug #775: E-Mail-Interaktion „Trip nicht gefunden".

Root cause (empirisch verifiziert, siehe docs/context/bug-775-email-trip-lookup.md):
Der Briefing-Betreff enthält einen Em-Dash `—`. Beim Versand RFC-2047-Q-kodiert
Python den ganzen Betreff; im Q-Encoding wird **Leerzeichen = `_`**. Antwortet die
Nutzerin, scheitert (A) die Extraktion still (Klammern als `=5B/=5D` kodiert) bzw.
(C) der exakte Namensvergleich `Hermannsweg_mit_Astrid_2026` ≠
`Hermannsweg mit Astrid 2026`.

KEINE Mocks — echte MIME-Serialisierung, echtes File-I/O, echter Reader/Processor.

SPEC: docs/specs/modules/trip_shortcode_routing.md v1.0
"""
from __future__ import annotations

import email
import shutil
from datetime import date, datetime, timezone

import pytest

from email.mime.text import MIMEText

from app.loader import get_data_dir, load_trip, save_trip
from app.trip import Stage, Trip, Waypoint
from services.inbound_email_reader import InboundEmailReader
from services.trip_command_processor import InboundMessage, TripCommandProcessor

_REAL_NAME = "Hermannsweg mit Astrid 2026"   # gespeichert MIT Leerzeichen
_MANGLED = "Hermannsweg_mit_Astrid_2026"     # so kommt es aus der Reply (Underscores)
_USER_A = "bug775_user_a"
_USER_B = "bug775_user_b"


# ---------------------------------------------------------------------------
# Helpers — reale Trips auf der Platte, kein Mock
# ---------------------------------------------------------------------------

def _make_trip(trip_id: str, name: str, *, with_today_stage: bool = False, **extra) -> Trip:
    stages = []
    if with_today_stage:
        stages = [Stage(
            id="S1", name="Etappe 1", date=date.today(),
            waypoints=[
                Waypoint(id="G1", name="Start", lat=52.276, lon=7.721, elevation_m=76),
                Waypoint(id="G2", name="Ziel", lat=52.220, lon=7.801, elevation_m=172),
            ],
        )]
    return Trip(id=trip_id, name=name, stages=stages, **extra)


def _cleanup_user(user_id: str) -> None:
    d = get_data_dir(user_id)
    if d.exists():
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture(autouse=True)
def _clean():
    for u in (_USER_A, _USER_B):
        _cleanup_user(u)
    yield
    for u in (_USER_A, _USER_B):
        _cleanup_user(u)


def _encoded_reply_subject(visible_subject: str) -> str:
    """Erzeuge den ECHTEN Wire-Betreff einer Reply: setze einen Betreff mit Em-Dash,
    serialisiere ihn (Python Q-encodet), und lies ihn wie der Inbound-Reader via
    msg.get('Subject') aus (RFC-2047-kodiert, Leerzeichen→Underscore)."""
    out = MIMEText("body", "plain", "utf-8")
    out["Subject"] = "Re: " + visible_subject
    received = email.message_from_bytes(out.as_bytes())
    return received.get("Subject", "")


# ---------------------------------------------------------------------------
# AC-1 — Inbound-Betreff RFC-2047 dekodieren (Szenario A: still ignoriert)
# ---------------------------------------------------------------------------

class TestAC1DecodeSubject:
    def test_encoded_subject_is_decoded_before_extraction(self):
        """GIVEN Reply mit RFC-2047-Q-kodiertem Betreff (Em-Dash im Original)
        WHEN der Reader den Trip-Bezeichner extrahiert
        THEN dekodiert er zuerst → Klammern + Name (mit Leerzeichen) sichtbar."""
        reader = InboundEmailReader()
        enc = _encoded_reply_subject(f"[{_REAL_NAME}] Etappe 1 — Morgen — Gewitter")
        # Beweis: der Betreff IST kodiert (sonst testen wir nichts Echtes)
        assert "=?" in enc and "?q?" in enc.lower()
        extracted = reader._extract_trip_name(enc)
        assert extracted is not None, (
            "Szenario A: kodierter Betreff wird heute still ignoriert (kein '[')"
        )
        assert extracted == _REAL_NAME


# ---------------------------------------------------------------------------
# AC-2 — Toleranter Trip-Lookup (Leerzeichen ↔ Underscore) in BEIDEN Stellen
# ---------------------------------------------------------------------------

class TestAC2TolerantLookup:
    def test_reader_find_trip_id_tolerates_underscores(self):
        trip = _make_trip("ta_reader", _REAL_NAME)
        save_trip(trip, _USER_A)
        reader = InboundEmailReader()
        found = reader._find_trip_id(_MANGLED, _USER_A)
        assert found == "ta_reader", "Underscore-Variante muss den Trip finden"

    def test_processor_find_trip_tolerates_underscores(self):
        trip = _make_trip("ta_proc", _REAL_NAME)
        save_trip(trip, _USER_A)
        proc = TripCommandProcessor()
        found = proc._find_trip(_MANGLED, _USER_A)
        assert found is not None and found.id == "ta_proc"

    def test_command_with_mangled_name_no_longer_trip_not_found(self):
        """Der gemeldete Bug: 'jetzt' auf den Trip mit Underscore-Namen."""
        trip = _make_trip("ta_cmd", _REAL_NAME, with_today_stage=True)
        save_trip(trip, _USER_A)
        proc = TripCommandProcessor()
        msg = InboundMessage(
            trip_name=_MANGLED, body="jetzt", sender="x@example.com",
            channel="email", received_at=datetime.now(tz=timezone.utc),
            user_id=_USER_A,
        )
        result = proc.process(msg)
        assert result.command != "trip_not_found"
        assert "Kein Trip mit Name" not in result.confirmation_body


# ---------------------------------------------------------------------------
# AC-3 — Eindeutiger GZ#-Shortcode pro Nutzer + Persistenz (kein Datenverlust)
# ---------------------------------------------------------------------------

class TestAC3Shortcode:
    def test_shortcode_derived_from_name(self):
        from app.shortcode import generate_shortcode
        code = generate_shortcode(_REAL_NAME, _USER_A)
        assert code == "GZ#HERM"

    def test_shortcode_unique_per_user(self):
        from app.shortcode import generate_shortcode
        t1 = _make_trip("t1", _REAL_NAME, shortcode="GZ#HERM")
        save_trip(t1, _USER_A)
        code2 = generate_shortcode("Hermannsweg Nord", _USER_A)
        assert code2 == "GZ#HERM2", "Kollision pro Nutzer → numerisches Suffix"

    def test_same_shortcode_allowed_across_users(self):
        from app.shortcode import generate_shortcode
        t1 = _make_trip("t1", _REAL_NAME, shortcode="GZ#HERM")
        save_trip(t1, _USER_A)
        # anderer Nutzer → darf wieder GZ#HERM bekommen (mandantengetrennt)
        assert generate_shortcode(_REAL_NAME, _USER_B) == "GZ#HERM"

    def test_shortcode_persisted_roundtrip(self):
        """Datenverlust-Schutz: shortcode übersteht save → load."""
        trip = _make_trip("tp", "Persist Test", shortcode="GZ#PERS")
        path = save_trip(trip, _USER_A)
        loaded = load_trip(path)
        assert loaded.shortcode == "GZ#PERS"


# ---------------------------------------------------------------------------
# AC-4 — Shortcode im Betreff + primäres Inbound-Routing über Shortcode
# ---------------------------------------------------------------------------

class TestAC4ShortcodeRouting:
    def test_subject_carries_shortcode(self):
        from src.output.tokens.dto import TokenLine
        from src.output.subject import build_email_subject
        line = TokenLine(
            stage_name="Etappe 1", report_type="morning",
            trip_name=_REAL_NAME, shortcode="GZ#HERM",
        )
        subject = build_email_subject(line)
        assert "GZ#HERM" in subject

    def test_reader_routes_by_shortcode_even_when_name_mangled(self):
        """Shortcode ist ASCII ohne Leerzeichen → immun gegen Q-Encoding.
        Selbst wenn der Name-Teil Underscores trägt, routet der Code korrekt."""
        trip = _make_trip("ts", _REAL_NAME, shortcode="GZ#HERM")
        save_trip(trip, _USER_A)
        reader = InboundEmailReader()
        bracket_content = f"GZ#HERM {_MANGLED}"
        assert reader._find_trip_id(bracket_content, _USER_A) == "ts"


# ---------------------------------------------------------------------------
# AC-5 — Mock-freier Roundtrip: Betreff → MIME → Reply → dekodieren → Trip → jetzt
# ---------------------------------------------------------------------------

class TestAC5RealRoundtrip:
    def test_full_roundtrip_jetzt_resolves_trip(self):
        from src.output.tokens.dto import TokenLine
        from src.output.subject import build_email_subject
        from output.channels.email import build_mime_message

        trip = _make_trip("tr", _REAL_NAME, with_today_stage=True, shortcode="GZ#HERM")
        save_trip(trip, _USER_A)

        # 1. Realer Versand-Betreff (mit Em-Dash + Shortcode)
        line = TokenLine(
            stage_name="Etappe 1", report_type="morning",
            trip_name=_REAL_NAME, main_risk="Thunder", shortcode="GZ#HERM",
        )
        subject = build_email_subject(line)

        # 2. MIME-Serialisierung wie der echte Versand
        msg = build_mime_message(
            subject=subject, body="<p>x</p>", from_addr="gregor@henemm.com",
            to_header="steffi@example.com", reply_to=None, html=True,
            plain_text_body="x", mail_type="trip-briefing", mail_format="full",
        )
        wire = msg.as_bytes()

        # 3. Reply empfangen (Re: + erneut serialisiert/geparst wie über IMAP)
        received = email.message_from_bytes(wire)
        received.replace_header("Subject", "Re: " + received.get("Subject", ""))
        reparsed = email.message_from_bytes(received.as_bytes())
        recv_subject = reparsed.get("Subject", "")

        # 4. Reader: dekodieren + extrahieren + Trip finden
        reader = InboundEmailReader()
        extracted = reader._extract_trip_name(recv_subject)
        assert extracted is not None
        trip_id = reader._find_trip_id(extracted, _USER_A)
        assert trip_id == "tr"

        # 5. Processor führt 'jetzt' aus — NICHT mehr 'Trip nicht gefunden'
        inbound = InboundMessage(
            trip_name=extracted, body="jetzt", sender="steffi@example.com",
            channel="email", received_at=datetime.now(tz=timezone.utc),
            user_id=_USER_A,
        )
        result = TripCommandProcessor().process(inbound)
        assert result.command == "now"
        assert "Kein Trip mit Name" not in result.confirmation_body
