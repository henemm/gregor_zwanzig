"""TDD RED — Issue #1009 (Reprocessing-Loop) + Issue #1019 (default-Datenleck).

Zwei Robustheits-/Sicherheitslücken im Inbound-Verarbeitungspfad:

#1019 (RED-Beweis, AC-3): Ein Telegram-Update von einer `chat_id` ohne
registriertes `user.json` fällt auf `user_id="default"` zurück und wird wie ein
regulärer Nutzer verarbeitet — der unbekannte Absender bekommt Trip-/Fehler-
Daten statt eines Registrierungs-Hinweises. Das Autorisierungs-Gate in
`_process_update` fehlt noch → AC-3 ist RED (empirisch belegt: der unbekannte
Absender erhält "Kein aktiver Trip gefunden ..." statt des /start-Hinweises).

#1009 (defensiver Backstop, AC-1): try/except/finally um Verarbeitung +
Antwortversand, `\\Seen` im finally-Zweig. WICHTIG — EMPIRISCHER BEFUND: gegen
das reale Stalwart-IMAP lässt sich die im Ticket beschriebene Reprocessing-
Schleife NICHT reproduzieren, weil `imap.fetch(uid, "(RFC822)")` (Z.101) das
`\\Seen`-Flag serverseitig IMPLIZIT setzt, BEVOR die Exception in `process()`
fliegt. Gemessen: nach einem fehlschlagenden Poll ist die Mail bereits `\\Seen`
und wird beim zweiten Poll NICHT erneut aufgegriffen (nur 1x verarbeitet).
Zudem verschluckt `send_command_reply_email` seine Exceptions bereits selbst.
AC-1 ist daher KEIN RED, sondern ein grüner Backstop-/Regressionstest, der die
vom Fix garantierte Nachbedingung (Mail wird `\\Seen`, kein Reprocessing) absichert.
Die Spec selbst führt #1009 unter Known Limitations als "defensiver Backstop
für einen seltenen Restfall".

AC-2/AC-4 sind Regressions-Sicherungsnetze (Erfolgspfad bzw. registrierter
Nutzer) und sind im aktuellen Stand bereits grün — sie sichern ab, dass der Fix
den Normalfall nicht bricht.

Mock-frei (CLAUDE.md): echter SMTP-Versand ins Stalwart-Test-Postfach
gregor-test@henemm.com, echter IMAP-Roundtrip, echte Telegram-Bot-API. Die
Fehlerinjektion für AC-1 erfolgt über eine ECHTE `TripCommandProcessor`-
Subklasse (kein Mock/patch), die `process()` mit einer echten Exception
überschreibt — exakt der von der Spec vorgesehene "fehlerhafte Processor-Stub
ohne Mock-Ersatz der echten IMAP/SMTP-Kommunikation". Die Telegram-Antwort
wird über eine ECHTE `NotificationService`-Subklasse mitgeschnitten, die den
realen Versand via `super()` weiterhin ausführt (Observability, kein Mock).

Env-Creds werden aus der Hauptrepo-.env geladen (Worktree hat keine eigene).

SPEC: docs/specs/modules/issue_1009_1019_inbound_reader_robustness.md (AC-1..AC-4)
"""
from __future__ import annotations

import email
import imaplib
import json
import os
import shutil
import smtplib
import time as time_mod
import uuid
from datetime import date, datetime, time, timezone
from email.header import decode_header
from email.mime.text import MIMEText
from pathlib import Path

import pytest

from app.config import Settings
from app.loader import save_trip
from app.trip import Stage, TimeWindow, Trip, Waypoint
from services.inbound_email_reader import InboundEmailReader
from services.notification_service import NotificationService
from services.trip_command_processor import TripCommandProcessor

import services.inbound_email_reader as _reader_mod

# Issue #1210 B1: der bekannte 39-%-Hänger -> addopts-wirksamer Marker statt
# nur Credential-Skip (primaere Ausschlussmechanik, nicht Defense-in-Depth).
pytestmark = pytest.mark.email

_REPO_ROOT = Path(__file__).resolve().parents[2]
_MAIN_ENV = Path("/home/hem/gregor_zwanzig/.env")
_DATA_USERS = _REPO_ROOT / "data" / "users"
_TEST_MAILBOX = "gregor-test@henemm.com"
_SYSTEM_FROM = "gregor_zwanzig@henemm.com"


def _load_main_env() -> None:
    """Lädt SMTP-/IMAP-Creds aus der Hauptrepo-.env (Worktree hat keine)."""
    if not _MAIN_ENV.exists():
        return
    for line in _MAIN_ENV.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


_load_main_env()

LAT, LON = 47.2692, 11.4041

_EMAIL_CREDS_PRESENT = bool(
    os.environ.get("GZ_TEST_IMAP_USER")
    and os.environ.get("GZ_TEST_IMAP_PASS")
    and os.environ.get("GZ_TEST_SMTP_PASS")
)
_email_gate = pytest.mark.skipif(
    not _EMAIL_CREDS_PRESENT,
    reason="GZ_TEST_IMAP_*/GZ_TEST_SMTP_PASS nicht gesetzt — echter Mail-Roundtrip nicht möglich",
)


# ---------------------------------------------------------------------------
# Test-User / Trip
# ---------------------------------------------------------------------------

def _make_user(user_id: str, mail_to: str) -> None:
    udir = _DATA_USERS / user_id
    if udir.exists():
        shutil.rmtree(udir)
    udir.mkdir(parents=True)
    (udir / "user.json").write_text(json.dumps({
        "id": user_id,
        "created_at": "2026-07-07T00:00:00Z",
        "mail_to": mail_to,
    }))


def _make_trip(user_id: str, trip_id: str, name: str) -> Trip:
    today = date.today()
    wps = [
        Waypoint(id="G1", name="Start", lat=LAT, lon=LON, elevation_m=600,
                 time_window=TimeWindow(start=time(0, 0), end=time(0, 0)),
                 arrival_override="08:00"),
        Waypoint(id="G2", name="Ziel", lat=47.2950, lon=11.4420, elevation_m=800,
                 time_window=TimeWindow(start=time(23, 59), end=time(23, 59)),
                 arrival_override="18:00"),
    ]
    stage = Stage(id="T1", name=f"{name}-Etappe", date=today,
                  start_time=time(8, 0), waypoints=wps)
    trip = Trip(id=trip_id, name=name, stages=[stage])
    save_trip(trip, user_id=user_id)
    return trip


def _cleanup_user(user_id: str) -> None:
    udir = _DATA_USERS / user_id
    if udir.exists():
        shutil.rmtree(udir)


# ---------------------------------------------------------------------------
# IMAP / SMTP Helper (echter Roundtrip gegen Stalwart-Test-Postfach)
# ---------------------------------------------------------------------------

def _imap() -> imaplib.IMAP4_SSL:
    m = imaplib.IMAP4_SSL(os.environ.get("GZ_IMAP_HOST", "mail.henemm.com"),
                          int(os.environ.get("GZ_IMAP_PORT", "993")), timeout=15)
    m.login(os.environ["GZ_TEST_IMAP_USER"], os.environ["GZ_TEST_IMAP_PASS"])
    m.select("INBOX")
    return m


def _deliver_mail(header_from: str, subject: str, body: str) -> None:
    """Liefert eine echte Mail INS Test-Postfach ein (Stalwart SMTP, STARTTLS).

    Der Envelope-Absender ist IMMER der authentifizierte Test-Account
    (Stalwart erlaubt kein fremdes MAIL FROM). Der `From:`-HEADER trägt dagegen
    die vom Reader geparste Absenderadresse — so kann ein beliebiger
    autorisierter Nutzer-Absender simuliert werden.
    """
    host = os.environ.get("GZ_TEST_SMTP_HOST", "mail.henemm.com")
    port = int(os.environ.get("GZ_TEST_SMTP_PORT", "587"))
    user = os.environ["GZ_TEST_SMTP_USER"]
    password = os.environ["GZ_TEST_SMTP_PASS"]
    envelope_from = f"{user}@henemm.com"
    msg = MIMEText(body, "plain", "utf-8")
    msg["From"] = header_from
    msg["To"] = _TEST_MAILBOX
    msg["Subject"] = subject
    with smtplib.SMTP(host, port, timeout=15) as server:
        server.starttls()
        server.login(user, password)
        server.sendmail(envelope_from, [_TEST_MAILBOX], msg.as_string())


def _subject(msg) -> str:
    raw = decode_header(msg.get("Subject", ""))[0][0]
    return raw.decode(errors="replace") if isinstance(raw, bytes) else str(raw)


def _find_uids_by_token(token: str, timeout_s: int = 120) -> list[bytes]:
    """UIDs aller Mails (egal ob gelesen), deren Subject `token` enthält."""
    deadline = time_mod.time() + timeout_s
    while True:
        m = _imap()
        try:
            _, data = m.uid("search", None, "ALL")
            hits = []
            for uid in (data[0].split() if data and data[0] else []):
                # BODY.PEEK[] statt RFC822 — darf das \Seen-Flag NICHT setzen,
                # sonst würde der UNSEEN-Poll des Readers die Mail verfehlen.
                _, md = m.uid("fetch", uid, "(BODY.PEEK[])")
                if not md or not md[0]:
                    continue
                mail = email.message_from_bytes(md[0][1])
                if token in _subject(mail):
                    hits.append(uid)
            if hits or time_mod.time() > deadline:
                return hits
        finally:
            m.logout()
        time_mod.sleep(8)


def _flags_for_uid(uid: bytes) -> str:
    m = _imap()
    try:
        _, data = m.uid("fetch", uid, "(FLAGS)")
        return data[0].decode() if data and data[0] else ""
    finally:
        m.logout()


def _delete_uids(uids: list[bytes]) -> None:
    if not uids:
        return
    m = _imap()
    try:
        for uid in uids:
            m.uid("store", uid, "+FLAGS", "(\\Deleted)")
        m.expunge()
    finally:
        m.logout()


def _base_email_settings() -> Settings:
    """Settings für poll_and_process: IMAP auf Test-Postfach, SMTP-Reply über Stalwart.

    test_mail_from wird bewusst auf die System-Absenderadresse gezwungen, damit
    der for_testing()-mail_from NIE gleich dem Test-Postfach-Absender ist
    (sonst greift der Loop-Guard in _authorize und die Mail würde abgewiesen).
    """
    return Settings(
        imap_host=os.environ.get("GZ_IMAP_HOST", "mail.henemm.com"),
        imap_port=int(os.environ.get("GZ_IMAP_PORT", "993")),
        imap_user=os.environ["GZ_TEST_IMAP_USER"],
        imap_pass=os.environ["GZ_TEST_IMAP_PASS"],
        # Explizit auf das Test-Postfach zeigen: sonst erbt Settings die
        # produktive GZ_INBOUND_ADDRESS aus der .env → TO-Filter verfehlt die
        # ins Test-Postfach zugestellte Mail.
        inbound_address=_TEST_MAILBOX,
        smtp_user=_TEST_MAILBOX,
        mail_from=_SYSTEM_FROM,
        test_smtp_host=os.environ.get("GZ_TEST_SMTP_HOST", "mail.henemm.com"),
        test_smtp_port=int(os.environ.get("GZ_TEST_SMTP_PORT", "587")),
        test_smtp_user=os.environ["GZ_TEST_SMTP_USER"],
        test_smtp_pass=os.environ["GZ_TEST_SMTP_PASS"],
        test_mail_from=_SYSTEM_FROM,
        test_imap_user=os.environ["GZ_TEST_IMAP_USER"],
        test_imap_pass=os.environ["GZ_TEST_IMAP_PASS"],
    )


class _FailingProcessor(TripCommandProcessor):
    """Echte Subklasse (KEIN Mock): process() wirft eine echte Exception.

    Simuliert den #1009-Restfall (unerwarteter Fehler in der Verarbeitung),
    ohne die echte IMAP/SMTP-Kommunikation zu ersetzen.
    """

    def process(self, inbound):  # noqa: D401 — bewusst überschrieben
        raise RuntimeError("simulierter Verarbeitungsfehler (#1009 RED)")


# ===========================================================================
# AC-1 (#1009) — defensiver Backstop (grün): Mail trotz Exception \Seen
# ===========================================================================

@_email_gate
def test_ac1_exception_marks_mail_seen_no_reprocess():
    """AC-1 (Backstop, grün): trotz Exception in process() ist die Mail \\Seen.

    Gegen das reale Stalwart-IMAP KEIN RED — `imap.fetch(RFC822)` setzt \\Seen
    implizit vor der Exception, daher ist die Mail auch ohne den finally-Fix
    bereits gelesen und wird nicht erneut verarbeitet. Der Test sichert die vom
    Fix garantierte Nachbedingung ab (Anti-Regression gegen eine künftige
    Umstellung auf BODY.PEEK, die die Schleife scharf machen würde).
    """
    user_id = "tdd-1009-usera"
    cmd_addr = "tdd-1009-cmd@henemm.com"
    token = f"GZ1009A-{uuid.uuid4().hex[:8]}"
    trip_name = token
    _make_user(user_id, mail_to=cmd_addr)
    _make_trip(user_id, trip_id="t1009a", name=trip_name)

    settings = _base_email_settings()
    _deliver_mail(header_from=cmd_addr, subject=f"[{trip_name}] status", body="status")

    uids = _find_uids_by_token(token)
    assert uids, "Trigger-Mail wurde nicht im Test-Postfach zugestellt"

    orig = _reader_mod.TripCommandProcessor
    _reader_mod.TripCommandProcessor = _FailingProcessor
    try:
        InboundEmailReader().poll_and_process(settings)
    finally:
        _reader_mod.TripCommandProcessor = orig

    try:
        uids_after = _find_uids_by_token(token, timeout_s=20)
        assert uids_after, "Mail nach Poll nicht mehr auffindbar"
        flags = _flags_for_uid(uids_after[0])
        assert "\\Seen" in flags, (
            f"#1009: Mail blieb UNSEEN nach Exception in process() "
            f"(FLAGS={flags!r}) — kein try/except/finally in _process_single "
            f"→ Endlos-Reprocessing"
        )
    finally:
        _delete_uids(_find_uids_by_token(token, timeout_s=20))
        _cleanup_user(user_id)


# ===========================================================================
# AC-2 (#1009) — Regressionsnetz: Erfolgspfad markiert Mail \Seen, gibt 1
# ===========================================================================

@_email_gate
def test_ac2_success_path_processes_and_marks_seen():
    """AC-2 (Regression, evtl. bereits grün): erfolgreicher status-Befehl.

    Erwartung: poll_and_process gibt >=1 zurück, Mail wird \\Seen. Sichert ab,
    dass der #1009-Fix den Normalfall nicht bricht.
    """
    user_id = "tdd-1009-userb"
    cmd_addr = "tdd-1009-userb@henemm.com"  # eindeutig → Lookup trifft nur diesen User
    token = f"GZ1009B-{uuid.uuid4().hex[:8]}"
    trip_name = token
    _make_user(user_id, mail_to=cmd_addr)
    _make_trip(user_id, trip_id="t1009b", name=trip_name)

    settings = _base_email_settings()
    _deliver_mail(header_from=cmd_addr, subject=f"[{trip_name}] status", body="status")

    uids = _find_uids_by_token(token)
    assert uids, "Trigger-Mail wurde nicht zugestellt"

    try:
        processed = InboundEmailReader().poll_and_process(settings)
        assert processed >= 1, f"Erfolgspfad verarbeitete 0 Befehle (got {processed})"

        uids_after = _find_uids_by_token(token, timeout_s=20)
        flags = _flags_for_uid(uids_after[0]) if uids_after else ""
        assert "\\Seen" in flags, f"Erfolgreiche Mail nicht \\Seen (FLAGS={flags!r})"
    finally:
        _delete_uids(_find_uids_by_token(token, timeout_s=20))
        _cleanup_user(user_id)


# ===========================================================================
# AC-3 + AC-4 (#1019) — echter Telegram-Live-Test (gated GZ_TELEGRAM_LIVE=1)
# ===========================================================================

def _live_gate():
    from tests.tdd._telegram_live_fixture import live_telegram_enabled
    return live_telegram_enabled()


class _RecordingNotificationService(NotificationService):
    """Echte Subklasse (KEIN Mock): schneidet den Body mit, sendet real via super()."""

    def __init__(self) -> None:
        super().__init__()
        self.sent_bodies: list[str] = []

    def send_telegram_message(self, *, chat_id, subject, body, settings, reply_markup=None):
        self.sent_bodies.append(body)
        return super().send_telegram_message(
            chat_id=chat_id, subject=subject, body=body,
            settings=settings, reply_markup=reply_markup,
        )

    def send_command_reply_telegram(self, result, chat_id, settings):
        self.sent_bodies.append(result.confirmation_body)
        return super().send_command_reply_telegram(
            result=result, chat_id=chat_id, settings=settings,
        )

    def edit_telegram_message_text(self, *, chat_id, message_id, text, settings, reply_markup=None):
        self.sent_bodies.append(text)
        return super().edit_telegram_message_text(
            chat_id=chat_id, message_id=message_id, text=text,
            settings=settings, reply_markup=reply_markup,
        )


def _detach_chat_id(chat_id: str, data_dir: str = "data") -> dict:
    """Entfernt telegram_chat_id von allen passenden user.json (read-modify-write).

    Gibt {Path: alter_wert} für die Wiederherstellung zurück.
    """
    originals: dict = {}
    users = Path(data_dir) / "users"
    if not users.exists():
        return originals
    for ud in users.iterdir():
        pf = ud / "user.json"
        if not pf.exists():
            continue
        try:
            prof = json.loads(pf.read_text(encoding="utf-8"))
        except Exception:
            continue
        if str(prof.get("telegram_chat_id", "")) == str(chat_id):
            originals[pf] = prof.get("telegram_chat_id")
            prof.pop("telegram_chat_id", None)
            pf.write_text(json.dumps(prof, ensure_ascii=False, indent=2), encoding="utf-8")
    return originals


def _restore_chat_ids(originals: dict) -> None:
    for pf, val in originals.items():
        try:
            prof = json.loads(pf.read_text(encoding="utf-8"))
        except Exception:
            continue
        prof["telegram_chat_id"] = val
        pf.write_text(json.dumps(prof, ensure_ascii=False, indent=2), encoding="utf-8")


def _make_update(chat_id: str, text: str) -> dict:
    return {
        "update_id": 1,
        "message": {
            "message_id": 1,
            "from": {"id": int(chat_id), "is_bot": False, "first_name": "Test"},
            "chat": {"id": int(chat_id), "type": "private"},
            "date": int(datetime.now(tz=timezone.utc).timestamp()),
            "text": text,
        },
    }


def _make_callback_update(chat_id: str, data: str) -> dict:
    """Update mit callback_query (Button-Klick auf eine bestehende Nachricht)."""
    return {
        "update_id": 1,
        "callback_query": {
            "id": "cbq-test-1",
            "from": {"id": int(chat_id), "is_bot": False, "first_name": "Test"},
            "data": data,
            "message": {
                "message_id": 42,
                "from": {"id": 1, "is_bot": True, "first_name": "Gregor"},
                "chat": {"id": int(chat_id), "type": "private"},
                "date": int(datetime.now(tz=timezone.utc).timestamp()),
                "text": "vorherige Nachricht mit Buttons",
            },
        },
    }


@pytest.mark.skipif(
    not _live_gate(),
    reason="GZ_TELEGRAM_LIVE!=1 oder Staging-Creds fehlen — kein echter Telegram-Live-Test",
)
def test_ac3_unknown_chat_gets_registration_hint():
    """AC-3 RED: unbekannte chat_id (kein user.json-Match) → Registrierungs-Hinweis.

    Aktuell fällt der Reader auf user_id="default" zurück und verschickt
    Trip-/Fehler-Daten OHNE /start-Hinweis (kein Autorisierungs-Gate) → RED.
    """
    from tests.tdd._telegram_live_fixture import staging_live_settings
    from services.inbound_telegram_reader import InboundTelegramReader

    settings = staging_live_settings()
    chat_id = os.environ["GZ_TELEGRAM_TEST_CHAT_ID"]

    # chat_id von allen user.json lösen → lookup liefert garantiert "default"
    originals = _detach_chat_id(chat_id)
    reader = InboundTelegramReader()
    rec = _RecordingNotificationService()
    reader._notification_service = rec
    try:
        reader._process_update(_make_update(chat_id, "status"), settings)
        body = "\n".join(rec.sent_bodies).lower()
        assert "/start" in body, (
            f"#1019: unbekannte chat_id erhielt KEINEN Registrierungs-Hinweis "
            f"(kein Autorisierungs-Gate). Gesendeter Text: {rec.sent_bodies!r}"
        )
    finally:
        _restore_chat_ids(originals)


@pytest.mark.skipif(
    not _live_gate(),
    reason="GZ_TELEGRAM_LIVE!=1 oder Staging-Creds fehlen — kein echter Telegram-Live-Test",
)
def test_ac3b_unknown_chat_callback_gets_registration_hint():
    """AC-3b (#1019 Adversary F001): unbekannte chat_id klickt einen Button.

    Der Callback-Pfad (_process_callback_query) ist über den Webhook fuer JEDEN
    Button-Klick erreichbar. Ohne Gate loest er user_id="default" auf, laedt den
    aktiven Trip und schickt echte Trip-Daten zurueck. Erwartung nach Fix:
    Registrierungs-Hinweis (/start), KEINE Trip-/Wetterdaten.
    """
    from tests.tdd._telegram_live_fixture import staging_live_settings
    from services.inbound_telegram_reader import InboundTelegramReader

    settings = staging_live_settings()
    chat_id = os.environ["GZ_TELEGRAM_TEST_CHAT_ID"]

    originals = _detach_chat_id(chat_id)
    reader = InboundTelegramReader()
    rec = _RecordingNotificationService()
    reader._notification_service = rec
    try:
        # "glance" ist ein realer Inline-Button-Callback (_CALLBACK_QUERY_MAP)
        reader._process_update(_make_callback_update(chat_id, "glance"), settings)
        body = "\n".join(rec.sent_bodies).lower()
        assert "/start" in body, (
            f"#1019 F001: unbekannte chat_id erhielt beim Button-Klick KEINEN "
            f"Registrierungs-Hinweis. Gesendeter Text: {rec.sent_bodies!r}"
        )
        assert "etappe" not in body and "wetter" not in body, (
            f"#1019 F001: Trip-/Wetterdaten im Callback-Pfad geleakt: {rec.sent_bodies!r}"
        )
    finally:
        _restore_chat_ids(originals)


@pytest.mark.skipif(
    not _live_gate(),
    reason="GZ_TELEGRAM_LIVE!=1 oder Staging-Creds fehlen — kein echter Telegram-Live-Test",
)
def test_ac4_registered_chat_gets_trip_response():
    """AC-4 (Regression, evtl. bereits grün): registrierter Nutzer → normale Antwort.

    Sichert ab, dass der #1019-Fix (Block von "default") den registrierten
    Betreiber-/Test-Account NICHT blockiert (kein Registrierungs-Hinweis).
    """
    from tests.tdd._telegram_live_fixture import (
        ensure_test_user_with_active_trip,
        staging_live_settings,
    )
    from services.inbound_telegram_reader import InboundTelegramReader

    settings = staging_live_settings()
    chat_id = os.environ["GZ_TELEGRAM_TEST_CHAT_ID"]
    ensure_test_user_with_active_trip(chat_id=chat_id)

    reader = InboundTelegramReader()
    rec = _RecordingNotificationService()
    reader._notification_service = rec
    reader._process_update(_make_update(chat_id, "status"), settings)

    body = "\n".join(rec.sent_bodies).lower()
    assert rec.sent_bodies, "Registrierter Nutzer erhielt keinerlei Antwort"
    assert "/start" not in body, (
        f"Registrierter Nutzer bekam faelschlich Registrierungs-Hinweis: {rec.sent_bodies!r}"
    )
