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
  `user_id == "default"` (analog `inbound_telegram_reader.py:181`, ADR-0003)
  — VOR dem Aufruf von `_authorize`. `lookup_user_by_email` liefert `None`
  bei Mehrfachtreffer (analog `lookup_user_by_telegram_chat_id`, #2141);
  `_resolve_settings_for_sender`s bestehendes `... or "default"` deckt
  "kein Treffer" UND "mehrdeutig" damit einheitlich ab, ohne dass
  `_resolve_settings_for_sender` selbst geaendert werden muss.
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
"""
from __future__ import annotations

import email
import json
from datetime import date, time
from pathlib import Path

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
    AR_PASS,
    TEST_AUTHSERV_ID,
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


def _msg(from_addr: str, trip_name: str, body: str = "status", auth_header: str | None = AR_PASS) -> email.message.Message:
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
        super().__init__()
        self.replies: list = []

    def send_command_reply_email(self, result, settings):
        self.replies.append(result)


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
    assert result == 0, f"#2143 AC-1: gespoofte Mail wurde verarbeitet (return={result})"
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

    msg = _msg(a_addr, "TripA", body="status", auth_header=AR_PASS)
    result = _run_process_single(reader, settings, msg)

    after_b = _trip_file_bytes("userb", "t-b")
    assert result == 1, f"#2143 AC-2: legitimes Kommando von A wurde nicht verarbeitet (return={result})"
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

    msg = _msg(addr, "UnverifiedTrip", body="status", auth_header=AR_PASS)
    result = _run_process_single(reader, settings, msg)

    assert result == 0, f"#2143 AC-3: unverifizierter Absender wurde verarbeitet (return={result})"
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

    msg = _msg(shared_addr, "FrankTrip", body="status", auth_header=AR_PASS)
    result = _run_process_single(reader, settings, msg)

    assert result == 0, (
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

    msg = _msg(shared_addr, "CarolTrip", body="status", auth_header=AR_PASS)
    result = _run_process_single(reader, settings, msg)

    assert result == 0, f"#2143 AC-4: mehrdeutiger Absender wurde verarbeitet (return={result})"
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

    msg = _msg(addr, "EveTrip", body="status", auth_header=AR_PASS)
    result = _run_process_single(reader, settings, msg)

    assert result == 1, f"#2143 AC-6: gueltiger Absender wurde NICHT verarbeitet (return={result})"
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
