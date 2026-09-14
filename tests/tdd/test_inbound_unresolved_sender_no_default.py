"""TDD RED — Issue #2147 Scheibe B2: Inbound-Mail von einem nicht zuordenbaren
Absender loest nie ein Kommando aus, und es gibt keinen Rueckfall auf ein
Konto ``"default"``.

Spec: docs/specs/modules/adresswechsel_nach_bestaetigung.md §8, AC-14.

Zwei Teile:

1. Verhalten (Regressionswaechter, heute bereits GRUEN): unbekannter,
   unbestaetigter bzw. nur im Nebenfeld ``email`` stehender Absender ->
   ``TripCommandProcessor.process`` wird NICHT aufgerufen, keine Antwortmail,
   die Mail wird ``\\Seen`` markiert, Rueckgabe 0. Heute erfuellt, weil
   ``_process_single`` den Rueckfall ``"default"`` verwirft.
2. Rueckgabevertrag (heute ROT): ``_resolve_settings_for_sender`` liefert
   fuer eine nicht zuordenbare Adresse ``None`` als Kennung — nicht die
   Zeichenkette ``"default"`` (Gate und Rueckgabetyp werden gemeinsam
   umgestellt, Entscheidung 7).

Nachweisform (CLAUDE.md, kein Mock-Theater): echtes Dateisystem
(``loader._DATA_ROOT`` -> ``tmp_path``), echte ``user.json`` und Trips,
Test-Doubles NUR an der IMAP-Transportgrenze (``fetch``/``store``, Aufrufe
werden ausgewertet), eine echte ``TripCommandProcessor``-Subklasse, die
Aufrufe zaehlt und ``super().process()`` ausfuehrt, und eine echte
``NotificationService``-Subklasse, die Antwortversuche aufzeichnet statt per
SMTP zu senden. Zwei-Nutzer-Pflicht: zwei echte Konten mit Trips.
"""
from __future__ import annotations

import email
import json
import sys
from datetime import date, time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

from app import loader  # noqa: E402
from app.config import Settings  # noqa: E402
from app.loader import save_trip  # noqa: E402
from app.trip import Stage, TimeWindow, Trip, Waypoint  # noqa: E402
import services.inbound_email_reader as _reader_mod  # noqa: E402
from services.inbound_email_reader import InboundEmailReader  # noqa: E402
from services.notification_service import NotificationService  # noqa: E402
from services.trip_command_processor import TripCommandProcessor  # noqa: E402
from tests.fixtures.authentication_results_fixtures import AR_PASS, TEST_AUTHSERV_ID  # noqa: E402

VERIFIED = "2026-01-01T00:00:00Z"
LAT, LON = 47.2692, 11.4041


def _write_profile(data_root: Path, user_id: str, **fields) -> None:
    user_dir = data_root / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    (user_dir / "user.json").write_text(json.dumps({"id": user_id, **fields}), encoding="utf-8")


def _make_trip(user_id: str, trip_id: str, name: str) -> None:
    today = date.today()
    wps = [
        Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=600,
                 time_window=TimeWindow(start=time(0, 0), end=time(0, 0)),
                 arrival_override="08:00"),
        Waypoint(id="G2", name="Ziel", lat=47.2950, lon=11.4420, elevation_m=800,
                 time_window=TimeWindow(start=time(23, 59), end=time(23, 59)),
                 arrival_override="18:00"),
    ]
    stage = Stage(id="T1", name=f"{name}-Etappe", date=today, start_time=time(8, 0), waypoints=wps)
    save_trip(Trip(id=trip_id, name=name, stages=[stage]), user_id=user_id)


def _valid_base_settings(sender: str) -> Settings:
    """Basis-Settings, die FUER SICH bereits autorisierungsfaehig waeren
    (mail_to == Absender, bestaetigt, passender authserv-id) — damit ist die
    fehlende Zuordnung der EINZIGE Blocker, nicht zufaellig ein
    nachgelagerter Check (Muster aus #2143 F001)."""
    return Settings(
        mail_to=sender,
        email_verified_at=VERIFIED,
        mail_server_hostname=TEST_AUTHSERV_ID,
        smtp_host="smtp.example.com",
        smtp_user="relay-user",
        smtp_pass="relay-pass",
    )


def _msg(from_addr: str, trip_name: str) -> email.message.Message:
    raw = "\r\n".join([
        f"From: {from_addr}",
        "To: cmd@example.com",
        f"Subject: [{trip_name}] Befehl",
        f"Authentication-Results: {AR_PASS}",
        "",
        "status",
    ]).encode("utf-8")
    return email.message_from_bytes(raw)


class _FakeImap:
    """Double NUR an der IMAP-Transportgrenze."""

    def __init__(self, raw: bytes) -> None:
        self._raw = raw
        self.stored: list[tuple] = []

    def fetch(self, uid, spec):
        return "OK", [(b"1 (RFC822 {n})", self._raw)]

    def store(self, uid, flags, value):
        self.stored.append((uid, flags, value))


class _CountingProcessor(TripCommandProcessor):
    calls: list = []

    def process(self, inbound):
        _CountingProcessor.calls.append(inbound)
        return super().process(inbound)


class _RecordingNotificationService(NotificationService):
    def __init__(self) -> None:
        super().__init__()
        self.replies: list = []

    def send_command_reply_email(self, result, settings):
        self.replies.append(result)


@pytest.fixture
def two_accounts(tmp_path, monkeypatch):
    """Zwei echte, bestaetigte Konten mit je einem Trip."""
    monkeypatch.setattr(loader, "_DATA_ROOT", str(tmp_path))
    _write_profile(tmp_path, "wanderer-a", mail_to="wanderer-a-kontakt@gmail.com",
                   email="wanderer-a-login@gmail.com", email_verified_at=VERIFIED)
    _write_profile(tmp_path, "wanderer-b", mail_to="wanderer-b-kontakt@gmail.com",
                   email_verified_at=VERIFIED)
    _make_trip("wanderer-a", "t-a", "TourA")
    _make_trip("wanderer-b", "t-b", "TourB")
    return tmp_path


def _run(sender: str, trip_name: str):
    reader = InboundEmailReader()
    reader._notification_service = _RecordingNotificationService()
    imap = _FakeImap(_msg(sender, trip_name).as_bytes())
    _CountingProcessor.calls = []
    orig = _reader_mod.TripCommandProcessor
    _reader_mod.TripCommandProcessor = _CountingProcessor
    try:
        result = reader._process_single(imap, b"1", _valid_base_settings(sender))
    finally:
        _reader_mod.TripCommandProcessor = orig
    return result, imap, reader._notification_service


def _assert_dropped_silently(label: str, result, imap, notifications) -> None:
    assert result == 0, f"AC-14 ({label}): Mail wurde verarbeitet (return={result})"
    assert not _CountingProcessor.calls, (
        f"AC-14 ({label}): TripCommandProcessor.process wurde aufgerufen: "
        f"{[c.user_id for c in _CountingProcessor.calls]}"
    )
    assert not notifications.replies, f"AC-14 ({label}): Antwortmail wurde ausgeloest"
    assert (b"1", "+FLAGS", "\\Seen") in imap.stored, (
        f"AC-14 ({label}): Mail wurde nicht als gelesen markiert, store-Aufrufe: {imap.stored}"
    )


# ---------------------------------------------------------------------------
# Teil 1 — Verhalten (Regressionswaechter, heute gruen)
# ---------------------------------------------------------------------------

def test_ac14_unknown_sender_runs_no_command_sends_no_reply_marks_seen(two_accounts):
    """AC-14: unbekannte Absenderadresse (in keinem Profil)."""
    result, imap, notifications = _run("unbekannt-absender@gmail.com", "TourA")
    _assert_dropped_silently("unbekannt", result, imap, notifications)


def test_ac14_unverified_sender_runs_no_command_sends_no_reply_marks_seen(two_accounts):
    """AC-14: Absender ist ``mail_to`` eines UNBESTAETIGTEN Kontos (mit Trip)."""
    _write_profile(two_accounts, "wanderer-u", mail_to="wanderer-u-kontakt@gmail.com")
    _make_trip("wanderer-u", "t-u", "TourU")
    result, imap, notifications = _run("wanderer-u-kontakt@gmail.com", "TourU")
    _assert_dropped_silently("unbestaetigt", result, imap, notifications)


def test_ac14_sender_only_in_email_side_field_runs_no_command(two_accounts):
    """AC-14: Absender steht nur im Nebenfeld ``email`` von wanderer-a
    (``mail_to`` abweichend) -> nicht zuordenbar."""
    result, imap, notifications = _run("wanderer-a-login@gmail.com", "TourA")
    _assert_dropped_silently("nur Nebenfeld", result, imap, notifications)


def test_ac14_ambiguous_sender_runs_no_command(two_accounts):
    """AC-14: zwei echte bestaetigte Konten mit derselben wirksamen Adresse."""
    _write_profile(two_accounts, "wanderer-doppel", mail_to="wanderer-b-kontakt@gmail.com",
                   email_verified_at=VERIFIED)
    result, imap, notifications = _run("wanderer-b-kontakt@gmail.com", "TourB")
    _assert_dropped_silently("mehrdeutig", result, imap, notifications)


# ---------------------------------------------------------------------------
# Teil 2 — Rueckgabevertrag ohne "default" (heute ROT)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "label, sender, extra_profile",
    [
        ("unbekannt", "unbekannt-absender@gmail.com", None),
        ("unbestaetigt", "wanderer-u-kontakt@gmail.com",
         ("wanderer-u", {"mail_to": "wanderer-u-kontakt@gmail.com"})),
        ("nur-nebenfeld-email", "wanderer-a-login@gmail.com", None),
        ("mehrdeutig", "wanderer-b-kontakt@gmail.com",
         ("wanderer-doppel", {"mail_to": "wanderer-b-kontakt@gmail.com", "email_verified_at": VERIFIED})),
    ],
)
def test_ac14_resolve_settings_for_unresolvable_sender_returns_none_not_default(
    two_accounts, label, sender, extra_profile,
):
    """AC-14 / §8: fuer eine nicht zuordenbare Adresse ist die Kennung ``None``
    — nie ``"default"`` und nie ein fremdes/unbestaetigtes Konto."""
    if extra_profile is not None:
        uid, fields = extra_profile
        _write_profile(two_accounts, uid, **fields)

    resolved = InboundEmailReader()._resolve_settings_for_sender(
        sender, _valid_base_settings(sender), data_dir=str(two_accounts),
    )
    user_id = resolved[0]

    assert user_id is None, (
        f"AC-14 ({label}): _resolve_settings_for_sender lieferte Kennung {user_id!r} "
        "statt None — kein Rueckfall auf 'default', keine Zuordnung ohne "
        "bestaetigte wirksame Adresse"
    )


def test_ac14_resolve_settings_for_verified_effective_sender_returns_account(two_accounts):
    """Gegenprobe: bestaetigte wirksame Adresse liefert weiterhin das Konto
    (faengt "immer None"). Heute gruen."""
    resolved = InboundEmailReader()._resolve_settings_for_sender(
        "wanderer-a-kontakt@gmail.com", _valid_base_settings("wanderer-a-kontakt@gmail.com"),
        data_dir=str(two_accounts),
    )
    assert resolved[0] == "wanderer-a"
