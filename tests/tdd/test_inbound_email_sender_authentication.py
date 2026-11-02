"""TDD RED — Inbound-Mail: gefaelschter Absender genuegt fuer Trip-Kommandos (#2143).

Deckt AC-1..AC-4 und AC-6 der Spec
``docs/specs/modules/inbound_command_channels.md`` v1.5, §5 (AC-5 — zweiter
gefaelschter Authentication-Results-Header — ist separat in
``test_authentication_results_parsing.py``, weil sie an der noch nicht
existierenden Funktion ``parse_authentication_results`` haengt).

Root Cause (bestaetigt in der Analyse-Phase): `_authorize()`
(`inbound_email_reader.py:188-202`) prueft den Absender nur gegen `mail_to`
desselben, aus dem `From:`-Header aufgeloesten Nutzerprofils — tautologisch.
Weder SPF/DKIM (`Authentication-Results`) noch `email_verified_at` noch ein
`user_id == "default"`-Gate (ADR-0003) existieren.

Implementierungsvertrag fuer /50-implement (in dieser RED-Phase festgelegt,
WEICHT bewusst vom illustrativen Code-Block in der Spec §5 ab — siehe
Begruendung unten; die ACs selbst sind identisch erfuellt):

* `_process_single` gated NACH `_resolve_settings_for_sender` explizit auf
  eine fehlende Zuordnung — VOR dem Aufruf von `_authorize`.
  `lookup_user_by_email` liefert `None` bei Mehrfachtreffer (analog
  `lookup_user_by_telegram_chat_id`, #2141). Stand #2147 Scheibe B2
  (``docs/specs/modules/adresswechsel_nach_bestaetigung.md`` §8, AC-14):
  `_resolve_settings_for_sender` liefert dann `None` als Kennung (kein
  Rueckfall mehr auf `"default"`), das Gate prueft `user_id is None`; "kein
  Treffer", "mehrdeutig" und "nicht bestaetigt" sind damit einheitlich
  abgedeckt. (Urspruenglich: `... or "default"` + Gate `== "default"`.)
* `_authorize(self, sender, settings, msg)` bekommt WEITERHIN die bereits
  user-scoped `settings` (wie heute), NICHT die Basis-Settings — anders als
  die Spec-Pseudocode-Skizze, die `_authorize` einen eigenen
  `lookup_user_by_email`-Aufruf zuschreibt. Grund: die Identitaets-
  Aufloesung (wer ist der Absender?) und die Autorisierungs-Pruefung (darf
  DIESER bereits identifizierte Absender das?) sind zwei verschiedene
  Zustaendigkeiten — das deckt sich mit dem Telegram-Vorbild, wo der
  `user_id == "default"`-Gate ebenfalls IM Reader steht, nicht im
  Autorisierungs-Helper. `_authorize` bleibt fuer: bestehender
  mail_from/mail_to/inbound_address-Abgleich (Loop-Guard, unveraendert) +
  NEU `email_verified_at`-Pflicht + NEU SPF/DKIM-Pass (`_spf_dkim_pass`).

Nachweisform (CLAUDE.md, Mock-Verbot): echtes Dateisystem (`tmp_path` via
``monkeypatch.setattr(loader, "_DATA_ROOT", ...)``), echte `user.json`- und
Trip-Profile (``save_trip``), eine faelschungssichere Fake-IMAP NUR an der
Transportgrenze (`imap.fetch`/`imap.store` — legitimes Transport-Double,
analog dem Telegram-Pendants `httpx.post`-Fake), eine echte
`TripCommandProcessor`-Subklasse, die `super().process()` WIRKLICH aufruft
(kein Mock) und nur die Aufrufe mitzaehlt, sowie eine echte
`NotificationService`-Subklasse, die Reply-Versuche aufzeichnet OHNE echten
SMTP-Versand auszufuehren (Kern-Schicht: deterministisch, kein Netz).

SPEC: docs/specs/modules/inbound_command_channels.md v1.5, §5, AC-1..AC-4, AC-6.

#2252 (SECURITY-FIX, Spec v1.7, §5/§5a, AC-7, AC-12..AC-15) — TESTVERTRAG:

* `_authorize(sender, settings, msg)` bleibt in der Signatur unveraendert;
  intern ruft es `_single_from_address(msg) -> bool` (AC-14: genau ein
  `From:`-Header mit genau einer Adresse) und
  `_spf_dkim_pass(msg, settings.mail_server_hostname, from_domain)` mit
  `from_domain = sender.rpartition("@")[2]` (Spec 5a, Domain-Ausrichtung).
* Pass-Header in Annahmetests sind auf die `From:`-Domain ausgerichtet
  (`ar_pass_for(<From-Adresse>)`), damit Ablehnungen nur am jeweils
  geprueften Waechter entstehen. Echte Prod-Header H1–H4 laufen mit
  `mail_server_hostname="mail.henemm.com"` (explizit gesetzt).
* AC-15 Zwei-Nutzer-Test: Nutzer A (@henemm.com) und B (@opfer.example)
  mit VERSCHIEDENEN Domains ueber den echten `_process_single`-Pfad.
"""
from __future__ import annotations

import email
import json
import logging
from datetime import date, time
from pathlib import Path

import pytest

from app import loader
from app.config import Settings
from app.loader import get_briefings_dir, lookup_user_by_email, save_trip
from app.trip import Stage, TimeWindow, Trip, Waypoint
from app.models import TripReportConfig
from services.inbound_email_reader import InboundEmailReader
from services.notification_service import NotificationService
from services.trip_command_processor import TripCommandProcessor

import services.inbound_email_reader as _reader_mod

from tests.fixtures.authentication_results_fixtures import (
    AR_FOREIGN_DOMAIN_ALIGNED,
    AR_H1_NORMAL,
    AR_H2_INJECTION,
    AR_H2B_ALIGNED_INJECTION,
    AR_H3_ESCAPED_QUOTE,
    AR_H4_RESEND,
    PROD_AUTHSERV_ID,
    TEST_AUTHSERV_ID,
    ar_pass_for,
)

LAT, LON = 47.2692, 11.4041


# ---------------------------------------------------------------------------
# Fixtures / Helpers
# ---------------------------------------------------------------------------

def _write_user(
    data_root: Path, user_id: str, mail_to: str, email_verified_at: str | None = None,
) -> None:
    user_dir = data_root / "users" / user_id
    user_dir.mkdir(parents=True, exist_ok=True)
    profile = {"id": user_id, "mail_to": mail_to}
    if email_verified_at is not None:
        profile["email_verified_at"] = email_verified_at
    (user_dir / "user.json").write_text(json.dumps(profile), encoding="utf-8")


def _make_trip(user_id: str, trip_id: str, name: str, with_report_config: bool = False) -> Trip:
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
    report_config = TripReportConfig(trip_id=trip_id, enabled=True) if with_report_config else None
    trip = Trip(id=trip_id, name=name, stages=[stage], report_config=report_config)
    save_trip(trip, user_id=user_id)
    return trip


def _trip_file_bytes(user_id: str, trip_id: str) -> bytes:
    return (get_briefings_dir(user_id) / f"{trip_id}.json").read_bytes()


def _base_settings(mail_to: str, mail_server_hostname: str = TEST_AUTHSERV_ID) -> Settings:
    # smtp_host/-user/-pass explizit setzen, damit can_send_email() unabhaengig
    # von einer lokalen .env deterministisch True liefert (Kern-Schicht-Regel).
    return Settings(
        mail_to=mail_to,
        mail_server_hostname=mail_server_hostname,
        smtp_host="smtp.example.com",
        smtp_user="test-user",
        smtp_pass="test-pass",
    )


_ALIGNED = object()  # Sentinel: auf die From-Domain ausgerichteter Pass-Header (#2252)


def _msg(from_addr: str, trip_name: str, body: str = "status", auth_header=_ALIGNED) -> email.message.Message:
    if auth_header is _ALIGNED:
        auth_header = ar_pass_for(from_addr)
    lines = [f"From: {from_addr}", "To: cmd@example.com", f"Subject: [{trip_name}] Befehl"]
    if auth_header is not None:
        lines.append(f"Authentication-Results: {auth_header}")
    lines.append("")
    lines.append(body)
    raw = "\r\n".join(lines).encode("utf-8")
    return email.message_from_bytes(raw)


class _FakeImap:
    """Fake NUR an der Transportgrenze — liefert die vorgefertigte Message zurueck."""

    def __init__(self, raw_bytes: bytes) -> None:
        self._raw = raw_bytes
        self.stored: list[tuple] = []

    def fetch(self, uid, spec):
        return "OK", [(b"1 (RFC822 {n})", self._raw)]

    def store(self, uid, flags, value):
        self.stored.append((uid, flags, value))


def _fake_imap_for(msg) -> _FakeImap:
    return _FakeImap(msg.as_bytes())


class _RecordingProcessor(TripCommandProcessor):
    """Echte Subklasse: zaehlt Aufrufe mit, fuehrt process() ECHT via super() aus."""

    calls: list = []

    def process(self, inbound):
        _RecordingProcessor.calls.append(inbound)
        return super().process(inbound)


class _RecordingNotificationService(NotificationService):
    """Echte Subklasse: zeichnet Reply-Versuche auf OHNE echten SMTP-Versand
    (Kern-Schicht — deterministisch, kein Netz, CLAUDE.md Testschicht-Regel)."""

    def __init__(self) -> None:
        super().__init__(user_id="default")
        self.replies: list = []

    def send_command_reply_email(self, result, settings, lang="de"):
        self.replies.append(result)
        return True  # #1405 S4b AC-23: Vertrag "-> bool" (zugestellt)


def _run_process_single(reader: InboundEmailReader, settings: Settings, msg) -> int:
    imap = _fake_imap_for(msg)
    _RecordingProcessor.calls = []
    orig = _reader_mod.TripCommandProcessor
    _reader_mod.TripCommandProcessor = _RecordingProcessor
    try:
        return reader._process_single(imap, b"1", settings)
    finally:
        _reader_mod.TripCommandProcessor = orig


# ---------------------------------------------------------------------------
# AC-1: gefaelschter From-Header ohne gueltigen Authentication-Results-Header
# ---------------------------------------------------------------------------

def test_ac1_spoofed_sender_without_spf_dkim_pass_is_rejected(tmp_path, monkeypatch):
    """AC-1: GIVEN eine Email mit gefaelschtem `From:` auf die `mail_to`-Adresse
    eines echten, verifizierten Nutzers, aber OHNE Authentication-Results:
    spf=pass;dkim=pass vom eigenen Mailserver
    WHEN die Email verarbeitet wird
    THEN wird das Kommando NICHT verarbeitet, kein Trip wird geaendert, kein
    Reply wird gesendet.

    Heute (RED): `_authorize()` prueft nur `sender == mail_to` desselben
    Profils -- der fehlende/fehlgeschlagene SPF/DKIM-Check wird gar nicht
    ausgewertet, die gespoofte Mail wird verarbeitet."""
    monkeypatch.setattr(loader, "_DATA_ROOT", str(tmp_path))
    victim = "victim"
    victim_addr = "victim@example.com"
    _write_user(tmp_path, victim, mail_to=victim_addr, email_verified_at="2026-01-01T00:00:00Z")
    trip = _make_trip(victim, "t-victim", "VictimTrip", with_report_config=True)
    before = _trip_file_bytes(victim, "t-victim")

    settings = _base_settings(mail_to=victim_addr)
    reader = InboundEmailReader()
    reader._notification_service = _RecordingNotificationService()

    # Kein Authentication-Results-Header ueberhaupt (auth_header=None) --
    # simuliert eine gespoofte Mail, die NICHT durch die anonyme Stalwart-
    # Inbound-Pipeline lief und daher keinen echten Header traegt.
    msg = _msg(victim_addr, "VictimTrip", body="abbruch", auth_header=None)
    result = _run_process_single(reader, settings, msg)

    after = _trip_file_bytes(victim, "t-victim")
    assert result == (0, 0), f"#2143 AC-1: gespoofte Mail wurde verarbeitet (return={result})"  # #1405 S4b AC-23
    assert after == before, "#2143 AC-1: Trip von 'victim' wurde durch gespoofte Mail veraendert"
    assert not _RecordingProcessor.calls, "#2143 AC-1: TripCommandProcessor wurde trotz Spoof aufgerufen"
    assert not reader._notification_service.replies, "#2143 AC-1: Reply wurde trotz Spoof gesendet"


# ---------------------------------------------------------------------------
# AC-2: Zwei-Nutzer-Isolation
# ---------------------------------------------------------------------------

def test_ac2_command_from_user_a_never_touches_user_b_trip(tmp_path, monkeypatch):
    """AC-2: GIVEN zwei verschiedene, jeweils eindeutig verifizierte Nutzer A
    und B mit eigenen Trips
    WHEN ein Kommando per Email von Nutzer A eingeht
    THEN wird niemals ein Trip von Nutzer B veraendert (Zwei-Nutzer-Pflicht,
    CLAUDE.md)."""
    monkeypatch.setattr(loader, "_DATA_ROOT", str(tmp_path))
    a_addr, b_addr = "usera@example.com", "userb@example.com"
    _write_user(tmp_path, "usera", mail_to=a_addr, email_verified_at="2026-01-01T00:00:00Z")
    _write_user(tmp_path, "userb", mail_to=b_addr, email_verified_at="2026-01-01T00:00:00Z")
    _make_trip("usera", "t-a", "TripA")
    _make_trip("userb", "t-b", "TripB")
    before_b = _trip_file_bytes("userb", "t-b")

    settings = _base_settings(mail_to=a_addr)
    reader = InboundEmailReader()
    reader._notification_service = _RecordingNotificationService()

    msg = _msg(a_addr, "TripA", body="status", auth_header=ar_pass_for(a_addr))
    result = _run_process_single(reader, settings, msg)

    after_b = _trip_file_bytes("userb", "t-b")
    assert result == (1, 0), f"#2143 AC-2: legitimes Kommando von A wurde nicht verarbeitet (return={result})"  # #1405 S4b AC-23
    assert after_b == before_b, "#2143 AC-2: Trip von Nutzer B wurde durch Kommando von A veraendert"
    assert len(_RecordingProcessor.calls) == 1
    assert _RecordingProcessor.calls[0].user_id == "usera", (
        f"#2143 AC-2: Kommando wurde nicht auf usera gescoped: {_RecordingProcessor.calls[0].user_id!r}"
    )


# ---------------------------------------------------------------------------
# AC-3: email_verified_at fehlt
# ---------------------------------------------------------------------------

def test_ac3_unverified_profile_is_rejected_despite_valid_spf_dkim(tmp_path, monkeypatch):
    """AC-3: GIVEN ein Nutzerprofil OHNE gesetztes `email_verified_at`
    WHEN eine Email mit korrektem SPF/DKIM-Pass und passendem `mail_to` von
    diesem Absender eingeht
    THEN wird kein Kommando ausgeloest und kein Reply gesendet.

    Heute (RED): `_authorize()` prueft `email_verified_at` gar nicht -- die
    Mail wird trotz fehlender Verifizierung verarbeitet."""
    monkeypatch.setattr(loader, "_DATA_ROOT", str(tmp_path))
    addr = "unverified@example.com"
    _write_user(tmp_path, "unverified", mail_to=addr, email_verified_at=None)
    _make_trip("unverified", "t-u", "UnverifiedTrip")

    settings = _base_settings(mail_to=addr)
    reader = InboundEmailReader()
    reader._notification_service = _RecordingNotificationService()

    msg = _msg(addr, "UnverifiedTrip", body="status", auth_header=ar_pass_for(addr))
    result = _run_process_single(reader, settings, msg)

    assert result == (0, 0), f"#2143 AC-3: unverifizierter Absender wurde verarbeitet (return={result})"  # #1405 S4b AC-23
    assert not _RecordingProcessor.calls, "#2143 AC-3: Processor wurde trotz fehlender Verifizierung aufgerufen"
    assert not reader._notification_service.replies, "#2143 AC-3: Reply trotz fehlender Verifizierung gesendet"


# ---------------------------------------------------------------------------
# AC-4: lookup_user_by_email liefert None bei Mehrfachtreffer
# ---------------------------------------------------------------------------

def test_ac4_lookup_returns_none_for_ambiguous_mail_to(tmp_path):
    """AC-4: GIVEN zwei Nutzerprofile mit identischer `mail_to`-Adresse
    (Mehrfachtreffer)
    WHEN `lookup_user_by_email()` fuer diese Adresse aufgerufen wird
    THEN liefert der Lookup `None` statt eines der beiden Profile.

    Heute (RED): `lookup_user_by_email` nimmt den ersten Treffer (Iterations-
    reihenfolge von `list_all_user_ids`), statt bei Kollision `None` zu
    liefern."""
    shared_addr = "shared@example.com"
    _write_user(tmp_path, "alice", mail_to=shared_addr, email_verified_at="2026-01-01T00:00:00Z")
    _write_user(tmp_path, "bob", mail_to=shared_addr, email_verified_at="2026-01-01T00:00:00Z")

    result = lookup_user_by_email(shared_addr, data_dir=str(tmp_path))

    assert result is None, (
        f"#2143 AC-4: mehrdeutige mail_to-Adresse {shared_addr!r} wurde dem "
        f"Konto {result!r} zugeordnet (erwartet: None) -- ein Angreifer mit "
        f"passender user_id koennte fremde Kommandos uebernehmen"
    )


def test_ac4_default_gate_is_the_sole_blocker_when_base_settings_are_otherwise_valid(
    tmp_path, monkeypatch,
):
    """F001 (Adversary #2143): der `user_id == "default"`-Gate muss auch dann
    blocken, wenn die Basis-``Settings`` (wie sie ``poll_and_process``
    produktiv uebergibt) fuer sich genommen bereits VOLLSTAENDIG
    autorisierungsfaehig waeren (eigenes ``mail_to``, ``email_verified_at``,
    gueltiger SPF/DKIM-Header) -- damit ist der Gate der EINZIGE Blocker,
    nicht ein nachgelagerter Check zufaellig aus einem anderen Grund
    (Mutations-Gegenprobe C des Adversary: 0/33 Tests rot bei komplett
    entferntem Gate, weil die bisherigen AC-4-Tests OHNE eigenes
    email_verified_at in den Basis-Settings konstruiert waren)."""
    monkeypatch.setattr(loader, "_DATA_ROOT", str(tmp_path))
    shared_addr = "shared3@example.com"
    _write_user(tmp_path, "frank", mail_to=shared_addr, email_verified_at="2026-01-01T00:00:00Z")
    _write_user(tmp_path, "grace", mail_to=shared_addr, email_verified_at="2026-01-01T00:00:00Z")
    _make_trip("frank", "t-f", "FrankTrip")

    # Bewusst SELBST vollstaendig gueltig: mail_to == shared_addr,
    # email_verified_at gesetzt, mail_server_hostname passend zum Header.
    settings = Settings(
        mail_to=shared_addr,
        email_verified_at="2026-01-01T00:00:00Z",
        mail_server_hostname=TEST_AUTHSERV_ID,
    )
    reader = InboundEmailReader()
    reader._notification_service = _RecordingNotificationService()

    msg = _msg(shared_addr, "FrankTrip", body="status", auth_header=ar_pass_for(shared_addr))
    result = _run_process_single(reader, settings, msg)

    assert result == (0, 0), (  # #1405 S4b AC-23: (processed, failed)
        f"#2143 F001: bei mehrdeutigem mail_to muss der 'default'-Gate blocken, "
        f"selbst wenn die Basis-Settings fuer sich genommen bereits gueltig "
        f"waeren (return={result})"
    )
    assert not _RecordingProcessor.calls
    assert not reader._notification_service.replies, (
        "#2143 F001: Reply trotz mehrdeutigem Absender gesendet -- Adress-Leak"
    )


def test_ac4_ambiguous_sender_rejected_end_to_end(tmp_path, monkeypatch):
    """AC-4 (Ende-zu-Ende): eine Mail von der mehrdeutigen Adresse darf ueber
    `_process_single` weder verarbeitet werden noch einen Reply ausloesen --
    ADR-0003-Gate (`user_id == "default"`), analog Telegram."""
    monkeypatch.setattr(loader, "_DATA_ROOT", str(tmp_path))
    shared_addr = "shared2@example.com"
    _write_user(tmp_path, "carol", mail_to=shared_addr, email_verified_at="2026-01-01T00:00:00Z")
    _write_user(tmp_path, "dave", mail_to=shared_addr, email_verified_at="2026-01-01T00:00:00Z")
    _make_trip("carol", "t-c", "CarolTrip")

    settings = _base_settings(mail_to=shared_addr)
    reader = InboundEmailReader()
    reader._notification_service = _RecordingNotificationService()

    msg = _msg(shared_addr, "CarolTrip", body="status", auth_header=ar_pass_for(shared_addr))
    result = _run_process_single(reader, settings, msg)

    assert result == (0, 0), f"#2143 AC-4: mehrdeutiger Absender wurde verarbeitet (return={result})"  # #1405 S4b AC-23
    assert not _RecordingProcessor.calls
    assert not reader._notification_service.replies, (
        "#2143 AC-4: Reply an mehrdeutigen Absender gesendet -- Adress-Leak"
    )


# ---------------------------------------------------------------------------
# AC-6: Regression -- gueltiger Fall bleibt funktionsfaehig
# ---------------------------------------------------------------------------

def test_ac6_valid_verified_sender_with_spf_dkim_pass_is_processed(tmp_path, monkeypatch):
    """AC-6 (Regression): GIVEN korrektes SPF/DKIM-Pass, gesetztes
    `email_verified_at`, eindeutiger Lookup
    WHEN die Email verarbeitet wird
    THEN wird das Kommando wie zuvor verarbeitet und die Bestaetigung
    gesendet -- bestehendes Verhalten bleibt erhalten."""
    monkeypatch.setattr(loader, "_DATA_ROOT", str(tmp_path))
    addr = "eve@example.com"
    _write_user(tmp_path, "eve", mail_to=addr, email_verified_at="2026-01-01T00:00:00Z")
    _make_trip("eve", "t-e", "EveTrip")

    settings = _base_settings(mail_to=addr)
    reader = InboundEmailReader()
    reader._notification_service = _RecordingNotificationService()

    msg = _msg(addr, "EveTrip", body="status", auth_header=ar_pass_for(addr))
    result = _run_process_single(reader, settings, msg)

    assert result == (1, 0), f"#2143 AC-6: gueltiger Absender wurde NICHT verarbeitet (return={result})"  # #1405 S4b AC-23
    assert len(_RecordingProcessor.calls) == 1
    assert len(reader._notification_service.replies) == 1
    assert reader._notification_service.replies[0].trip_name == "EveTrip"


# ---------------------------------------------------------------------------
# AC-3-Unterstuetzung: email_verified_at darf nicht durch extra="ignore"
# stillschweigend verworfen werden (config.py:117, Silent-Drop-Falle)
# ---------------------------------------------------------------------------

def test_email_verified_at_survives_with_user_profile(tmp_path, monkeypatch):
    """RED: `email_verified_at` muss als `Settings`-Feld deklariert sein --
    sonst verwirft `extra="ignore"` (config.py:117) den Profilwert
    stillschweigend, der `_authorize`-Check waere wirkungslos obwohl er im
    Code steht (analog `premium_sms_reply_to`-Praezedenzfall)."""
    monkeypatch.setattr(loader, "_DATA_ROOT", str(tmp_path))
    _write_user(tmp_path, "verified-user", mail_to="v@example.com",
                email_verified_at="2026-01-01T00:00:00Z")

    settings = Settings(mail_to="fallback@example.com")
    user_settings = settings.with_user_profile("verified-user")

    assert user_settings.email_verified_at == "2026-01-01T00:00:00Z", (
        "#2143: email_verified_at wurde beim Laden des Nutzerprofils "
        "verworfen (Settings-Feld fehlt, extra='ignore' schluckt es still)"
    )


def test_settings_has_mail_server_hostname_field():
    """RED: `mail_server_hostname` muss als `Settings`-Feld existieren --
    Vergleichsbasis fuer `authserv-id` in `_spf_dkim_pass`."""
    settings = Settings(mail_server_hostname=TEST_AUTHSERV_ID)
    assert settings.mail_server_hostname == TEST_AUTHSERV_ID


# ===========================================================================
# #2252 — Integration ueber _authorize / _process_single (AC-7, AC-12..AC-15)
# ===========================================================================

_VERIFIED = "2026-01-01T00:00:00Z"
_SYSTEM_FROM = "system@example.invalid"  # explizit, unabhaengig von GZ_MAIL_FROM in .env


def _raw_lines_msg(lines: list[str]) -> email.message.Message:
    """Raw-Bytes wie IMAP sie liefert (Header inkl. woertlicher Faltungen)."""
    return email.message_from_bytes("\r\n".join(lines + ["", "status"]).encode("utf-8"))


def _authz_settings(mail_to: str, authserv: str) -> Settings:
    return Settings(
        mail_to=mail_to,
        mail_from=_SYSTEM_FROM,
        email_verified_at=_VERIFIED,
        mail_server_hostname=authserv,
        smtp_host="smtp.example.com",
        smtp_user="test-user",
        smtp_pass="test-pass",
    )


def _authorize_with(sender: str, from_lines: list[str], header: str, authserv: str) -> bool:
    msg = _raw_lines_msg(from_lines + [
        "To: cmd@henemm.com", "Subject: [Trip] Befehl", f"Authentication-Results: {header}",
    ])
    return InboundEmailReader()._authorize(sender, _authz_settings(sender, authserv), msg)


class TestAuthorize2252:
    """`_authorize` mit echten Prod-Headern (authserv mail.henemm.com) und Luecke 2."""

    def test_ac7_h2_injection_is_rejected(self):
        sender = "nutzer@henemm.com"
        assert _authorize_with(sender, [f"From: {sender}"], AR_H2_INJECTION, PROD_AUTHSERV_ID) is False, (
            "#2252 AC-7: Injektion ueber quoted Local-Part (H2) wurde autorisiert"
        )

    def test_f001_aligned_injection_is_rejected(self):
        sender = "nutzer@henemm.com"
        assert _authorize_with(sender, [f"From: {sender}"], AR_H2B_ALIGNED_INJECTION, PROD_AUTHSERV_ID) is False, (
            "F001: ausgerichtete Injektion ueber quoted Local-Part (H2b) wurde autorisiert"
        )

    def test_ac7_h3_escaped_quote_injection_is_rejected(self):
        sender = "nutzer@henemm.com"
        assert _authorize_with(sender, [f"From: {sender}"], AR_H3_ESCAPED_QUOTE, PROD_AUTHSERV_ID) is False, (
            "#2252 AC-7: Injektion mit \\\"-Escape (H3) wurde autorisiert"
        )

    def test_ac12_foreign_domain_aligned_luecke2_is_rejected(self):
        sender = "opfer@opfer.example"
        assert _authorize_with(sender, [f"From: {sender}"], AR_FOREIGN_DOMAIN_ALIGNED, TEST_AUTHSERV_ID) is False, (
            "#2252 AC-12: SPF/DKIM der Angreifer-Domain wurde fuer From @opfer.example akzeptiert"
        )

    def test_ac14_two_from_headers_are_rejected(self):
        sender = "nutzer@henemm.com"
        lines = [f"From: {sender}", "From: angreifer@evil.example"]
        assert _authorize_with(sender, lines, AR_H1_NORMAL, PROD_AUTHSERV_ID) is False, (
            "#2252 AC-14: zwei From:-Header wurden akzeptiert"
        )

    def test_ac14_two_addresses_in_one_from_are_rejected(self):
        sender = "nutzer@henemm.com"
        lines = [f"From: {sender}, angreifer@evil.example"]
        assert _authorize_with(sender, lines, AR_H1_NORMAL, PROD_AUTHSERV_ID) is False, (
            "#2252 AC-14: From: mit zwei Adressen wurde akzeptiert"
        )

    def test_ac13_h1_is_accepted(self):
        sender = "nutzer@henemm.com"
        assert _authorize_with(sender, [f"From: {sender}"], AR_H1_NORMAL, PROD_AUTHSERV_ID) is True

    def test_ac13_h4_resend_is_accepted(self):
        sender = "gregor_zwanzig@henemm.com"  # != _SYSTEM_FROM (Loop-Guard)
        assert _authorize_with(sender, [f"From: {sender}"], AR_H4_RESEND, PROD_AUTHSERV_ID) is True


class TestSingleFromAddress:
    """AC-14: `_single_from_address(msg)` — genau ein From:-Header, genau eine Adresse."""

    def _check(self, from_lines: list[str]) -> bool:
        msg = _raw_lines_msg(from_lines + ["To: cmd@henemm.com", "Subject: x"])
        return InboundEmailReader()._single_from_address(msg)

    def test_single_address_is_true(self):
        assert self._check(["From: Nutzer <nutzer@henemm.com>"]) is True

    def test_display_name_with_comma_is_one_address(self):
        """Outlook-Stil: Komma im quoted Anzeigenamen ist KEINE zweite Adresse
        (sonst bricht AC-6 fuer echte Nutzer)."""
        assert self._check(['From: "Emmrich, Henning" <nutzer@henemm.com>']) is True

    def test_two_headers_is_false(self):
        assert self._check(["From: nutzer@henemm.com", "From: angreifer@evil.example"]) is False

    def test_two_addresses_is_false(self):
        assert self._check(["From: nutzer@henemm.com, angreifer@evil.example"]) is False

    def test_missing_from_is_false(self):
        assert self._check([]) is False


# ---------------------------------------------------------------------------
# AC-7 / AC-14 Ende-zu-Ende ueber _process_single
# ---------------------------------------------------------------------------

def _seen_marked(imap: _FakeImap) -> bool:
    return any(value == "\\Seen" for _uid, _flags, value in imap.stored)


def _run_raw(reader: InboundEmailReader, settings: Settings, msg) -> tuple[object, _FakeImap]:
    imap = _fake_imap_for(msg)
    _RecordingProcessor.calls = []
    orig = _reader_mod.TripCommandProcessor
    _reader_mod.TripCommandProcessor = _RecordingProcessor
    try:
        return reader._process_single(imap, b"1", settings), imap
    finally:
        _reader_mod.TripCommandProcessor = orig


def _cmd_msg(from_lines: list[str], trip_name: str, header: str, body: str) -> email.message.Message:
    lines = from_lines + [
        "To: cmd@henemm.com", f"Subject: [{trip_name}] Befehl", f"Authentication-Results: {header}", "",
        body,
    ]
    return email.message_from_bytes("\r\n".join(lines).encode("utf-8"))


def _reader() -> InboundEmailReader:
    reader = InboundEmailReader()
    reader._notification_service = _RecordingNotificationService()
    return reader


def _reader_warnings(caplog) -> list:
    return [r for r in caplog.records
            if r.name == "services.inbound_email_reader" and r.levelno == logging.WARNING]


def test_ac7_h2_injection_end_to_end_is_rejected(tmp_path, monkeypatch, caplog):
    """AC-7: H2 mit From = verifizierte mail_to ⇒ SEEN, kein Reply, WARNING-Log,
    Trip unveraendert."""
    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(loader, "_DATA_ROOT", str(tmp_path))
    addr = "nutzer-h2@henemm.com"
    _write_user(tmp_path, "nutzerh2", mail_to=addr, email_verified_at=_VERIFIED)
    _make_trip("nutzerh2", "t-h2", "H2Trip", with_report_config=True)
    before = _trip_file_bytes("nutzerh2", "t-h2")

    reader = _reader()
    result, imap = _run_raw(reader, _authz_settings(addr, PROD_AUTHSERV_ID),
                            _cmd_msg([f"From: {addr}"], "H2Trip", AR_H2_INJECTION, "stop"))

    assert result == (0, 0), f"#2252 AC-7: H2-Injektion wurde verarbeitet (return={result})"
    assert _trip_file_bytes("nutzerh2", "t-h2") == before
    assert not _RecordingProcessor.calls
    assert not reader._notification_service.replies
    assert _seen_marked(imap), "#2252 AC-7: abgelehnte Mail nicht SEEN markiert"
    assert _reader_warnings(caplog), "#2252 AC-7: kein WARNING-Log bei Ablehnung"


def test_f001_aligned_injection_end_to_end_is_rejected(tmp_path, monkeypatch, caplog):
    """F001 (Adversary #2252): H2-Muster mit AUSGERICHTETER Nutzlast
    (``dkim=pass header.d=henemm.com`` im quoted Local-Part) — ohne Quote-Schutz
    waere das ein akzeptiertes dkim-Segment. ⇒ SEEN, kein Reply, WARNING, Trip
    unveraendert."""
    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(loader, "_DATA_ROOT", str(tmp_path))
    addr = "nutzer-h2b@henemm.com"
    _write_user(tmp_path, "nutzerh2b", mail_to=addr, email_verified_at=_VERIFIED)
    _make_trip("nutzerh2b", "t-h2b", "H2bTrip", with_report_config=True)
    before = _trip_file_bytes("nutzerh2b", "t-h2b")

    reader = _reader()
    result, imap = _run_raw(reader, _authz_settings(addr, PROD_AUTHSERV_ID),
                            _cmd_msg([f"From: {addr}"], "H2bTrip", AR_H2B_ALIGNED_INJECTION, "stop"))

    assert result == (0, 0), f"F001: ausgerichtete Injektion wurde verarbeitet (return={result})"
    assert _trip_file_bytes("nutzerh2b", "t-h2b") == before
    assert not _RecordingProcessor.calls
    assert not reader._notification_service.replies
    assert _seen_marked(imap), "F001: abgelehnte Mail nicht SEEN markiert"
    assert _reader_warnings(caplog), "F001: kein WARNING-Log bei Ablehnung"


def test_ac14_double_from_end_to_end_is_rejected(tmp_path, monkeypatch, caplog):
    """AC-14: erster From:-Header = verifizierte mail_to, Header sonst gueltig
    (H1) ⇒ trotzdem fail-closed (SEEN, kein Reply, WARNING-Log, Trip unveraendert)."""
    caplog.set_level(logging.DEBUG)
    monkeypatch.setattr(loader, "_DATA_ROOT", str(tmp_path))
    addr = "nutzer-df@henemm.com"
    _write_user(tmp_path, "nutzerdf", mail_to=addr, email_verified_at=_VERIFIED)
    _make_trip("nutzerdf", "t-df", "DfTrip", with_report_config=True)
    before = _trip_file_bytes("nutzerdf", "t-df")

    reader = _reader()
    msg = _cmd_msg([f"From: {addr}", "From: angreifer@evil.example"], "DfTrip", AR_H1_NORMAL, "stop")
    result, imap = _run_raw(reader, _authz_settings(addr, PROD_AUTHSERV_ID), msg)

    assert result == (0, 0), f"#2252 AC-14: Doppel-From wurde verarbeitet (return={result})"
    assert _trip_file_bytes("nutzerdf", "t-df") == before
    assert not reader._notification_service.replies
    assert _seen_marked(imap)
    assert _reader_warnings(caplog), "#2252 AC-14: kein WARNING-Log bei Ablehnung"


# ---------------------------------------------------------------------------
# AC-15: zwei Nutzer mit VERSCHIEDENEN Domains
# ---------------------------------------------------------------------------

_A_ID, _A_ADDR, _A_TRIP, _A_TID = "nutzera", "nutzer-a@henemm.com", "AlphaTrip", "t-alpha"
_B_ID, _B_ADDR, _B_TRIP, _B_TID = "nutzerb", "nutzer-b@opfer.example", "BetaTrip", "t-beta"


def _two_users(tmp_path, monkeypatch) -> None:
    monkeypatch.setattr(loader, "_DATA_ROOT", str(tmp_path))
    _write_user(tmp_path, _A_ID, mail_to=_A_ADDR, email_verified_at=_VERIFIED)
    _write_user(tmp_path, _B_ID, mail_to=_B_ADDR, email_verified_at=_VERIFIED)
    _make_trip(_A_ID, _A_TID, _A_TRIP, with_report_config=True)
    _make_trip(_B_ID, _B_TID, _B_TRIP, with_report_config=True)


def _send(reader, from_addr: str, trip: str, header: str, authserv: str, body: str = "stop"):
    # Basis-Settings bewusst NEUTRAL (nicht die Adresse eines der Nutzer):
    # die Nutzerzuordnung muss ueber den echten Lookup erfolgen.
    settings = _authz_settings("basis@example.invalid", authserv)
    return _run_raw(reader, settings, _cmd_msg([f"From: {from_addr}"], trip, header, body))


def test_ac15_mail_from_b_aligned_to_a_domain_never_changes_b_trip(tmp_path, monkeypatch):
    """AC-15 entscheidender Fall: From = Adresse von B (@opfer.example), der
    Header ist aber auf A's Domain (henemm.com) ausgerichtet ⇒ abgelehnt,
    B's Trip unveraendert (und A's auch)."""
    _two_users(tmp_path, monkeypatch)
    before_a, before_b = _trip_file_bytes(_A_ID, _A_TID), _trip_file_bytes(_B_ID, _B_TID)
    reader = _reader()

    result, imap = _send(reader, _B_ADDR, _B_TRIP, ar_pass_for(_A_ADDR), TEST_AUTHSERV_ID)

    assert result == (0, 0), (
        f"#2252 AC-15: Mail mit From=B, aber auf A's Domain ausgerichtet, wurde verarbeitet (return={result})"
    )
    assert _trip_file_bytes(_B_ID, _B_TID) == before_b, "#2252 AC-15: Trip von B wurde veraendert"
    assert _trip_file_bytes(_A_ID, _A_TID) == before_a
    assert not reader._notification_service.replies
    assert _seen_marked(imap)


@pytest.mark.parametrize("from_who,header,authserv", [
    pytest.param("a", AR_H2_INJECTION, PROD_AUTHSERV_ID, id="H2-an-A"),
    pytest.param("a", AR_H3_ESCAPED_QUOTE, PROD_AUTHSERV_ID, id="H3-an-A"),
    pytest.param("b", AR_FOREIGN_DOMAIN_ALIGNED, TEST_AUTHSERV_ID, id="Luecke2-an-B"),
])
def test_ac15_attacks_are_rejected_for_both_users(tmp_path, monkeypatch, from_who, header, authserv):
    _two_users(tmp_path, monkeypatch)
    before_a, before_b = _trip_file_bytes(_A_ID, _A_TID), _trip_file_bytes(_B_ID, _B_TID)
    addr, trip = (_A_ADDR, _A_TRIP) if from_who == "a" else (_B_ADDR, _B_TRIP)
    reader = _reader()

    result, _imap = _send(reader, addr, trip, header, authserv)

    assert result == (0, 0), f"#2252 AC-15: Angriff gegen Nutzer {from_who} wurde verarbeitet (return={result})"
    assert _trip_file_bytes(_A_ID, _A_TID) == before_a
    assert _trip_file_bytes(_B_ID, _B_TID) == before_b
    assert not reader._notification_service.replies


def test_ac15_aligned_mails_are_accepted_per_user_and_touch_only_own_trip(tmp_path, monkeypatch):
    """Positivkontrolle (heute und nach dem Fix gruen): H1/H4 fuer A
    (@henemm.com) und ein auf opfer.example ausgerichteter Header fuer B werden
    akzeptiert; jede Mail aendert nur den eigenen Trip — und `stop` aendert
    die Trip-Datei tatsaechlich (sonst waere "unveraendert" oben wertlos)."""
    _two_users(tmp_path, monkeypatch)
    before_a, before_b = _trip_file_bytes(_A_ID, _A_TID), _trip_file_bytes(_B_ID, _B_TID)
    reader = _reader()

    result, _ = _send(reader, _A_ADDR, _A_TRIP, AR_H1_NORMAL, PROD_AUTHSERV_ID, body="stop")
    assert result == (1, 0), f"H1 fuer A abgelehnt (return={result})"
    assert _RecordingProcessor.calls[0].user_id == _A_ID
    after_a = _trip_file_bytes(_A_ID, _A_TID)
    assert after_a != before_a, "Vorbedingung: STOP muss A's Trip-Datei aendern"
    assert _trip_file_bytes(_B_ID, _B_TID) == before_b, "Mail von A hat B's Trip veraendert"

    result, _ = _send(reader, _A_ADDR, _A_TRIP, AR_H4_RESEND, PROD_AUTHSERV_ID, body="status")
    assert result == (1, 0), f"H4 fuer A abgelehnt (return={result})"
    assert _RecordingProcessor.calls[0].user_id == _A_ID
    assert _trip_file_bytes(_B_ID, _B_TID) == before_b

    result, _ = _send(reader, _B_ADDR, _B_TRIP, ar_pass_for(_B_ADDR), TEST_AUTHSERV_ID, body="stop")
    assert result == (1, 0), f"ausgerichtete Mail fuer B abgelehnt (return={result})"
    assert _RecordingProcessor.calls[0].user_id == _B_ID
    assert _trip_file_bytes(_B_ID, _B_TID) != before_b, "Vorbedingung: STOP muss B's Trip-Datei aendern"
    assert _trip_file_bytes(_A_ID, _A_TID) == after_a, "Mail von B hat A's Trip veraendert"
