"""TDD RED — Issue #2282 Scheibe S1: Befehle, die es am Ortsvergleich (noch) nicht gibt.

SPEC: docs/specs/modules/feat_2282_ortsvergleich_eingangskanaele.md — AC-11, AC-12.

Ist-Stand (gemessen): ein Vergleichsname wird vom Prozessor nicht gefunden, jede
Antwort lautet „Kein Trip mit Name … gefunden" bzw. die volle Trip-Hilfe.

Mutation 4 (kind-Filter nur in der Hilfe, nicht in der Ablehnung) wird gefangen,
weil hier der EXAKTE Ablehnungstext verlangt wird. „Kein Versand" wird an allen
drei Transporten gemessen (Telegram, Premium-SMS, E-Mail) — jeder Aufruf zählt.
"""
from __future__ import annotations

import json
import shutil
import sys
import uuid
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from app.loader import get_briefings_dir, save_trip  # noqa: E402
from app.models import TripReportConfig  # noqa: E402
from app.trip import Stage, Trip, Waypoint  # noqa: E402
from services.trip_command_processor import (  # noqa: E402
    InboundMessage,
    TripCommandProcessor,
)

NICHT_VERFUEGBAR = "für Ortsvergleiche per Nachricht noch nicht verfügbar"


@pytest.fixture
def uid():
    u = f"tdd-2282-ab-{uuid.uuid4().hex[:8]}"
    yield u
    shutil.rmtree(get_briefings_dir(u).parent, ignore_errors=True)


@pytest.fixture
def versand(monkeypatch):
    """Zählt jeden Transport-Aufruf; ein echter Versand darf nie passieren."""
    aufrufe: list[str] = []
    from output.channels.premium_sms import PremiumSmsOutput
    from output.channels.telegram import TelegramOutput

    monkeypatch.setattr(TelegramOutput, "send", lambda self, *a, **kw: aufrufe.append("telegram"))
    monkeypatch.setattr(PremiumSmsOutput, "__init__", lambda self, settings: None)
    monkeypatch.setattr(PremiumSmsOutput, "send", lambda self, *a, **kw: aufrufe.append("premium_sms"))
    from output.channels.email import EmailOutput
    from services.notification_service import NotificationService
    from services.trip_report_scheduler import TripReportSchedulerService

    monkeypatch.setattr(EmailOutput, "send", lambda self, *a, **kw: aufrufe.append("email"))
    # Harte Namen, kein hasattr-Guard: fehlt eine Methode, soll das Patchen
    # laut scheitern statt den Wächter still leer zu lassen.
    for cls, name in (
        (NotificationService, "send_compare_report"),
        (NotificationService, "send_trip_report"),
        (TripReportSchedulerService, "send_on_demand_report"),
        (TripReportSchedulerService, "send_test_report"),
    ):
        monkeypatch.setattr(cls, name, lambda self, *a, _n=name, **kw: aufrufe.append(_n))
    return aufrufe


def _preset(user_id: str, name: str = "Alpenblick") -> dict:
    pid = f"cmp-{uuid.uuid4().hex[:8]}"
    entry = {
        "id": pid, "name": name, "kind": "vergleich", "user_id": user_id,
        "location_ids": ["loc-a", "loc-b"], "schedule": "daily",
        "previous_schedule": "", "created_at": "2026-09-01T08:00:00Z",
    }
    d = get_briefings_dir(user_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{pid}.json").write_text(json.dumps(entry, indent=2), encoding="utf-8")
    return entry


def _send(user_id: str, body: str, name: str = "Alpenblick"):
    return TripCommandProcessor().process(InboundMessage(
        trip_name=name, body=body, sender="12345", channel="telegram",
        received_at=datetime.now(tz=timezone.utc), user_id=user_id,
    ))


def _dateien(user_id: str) -> dict[str, bytes]:
    return {p.name: p.read_bytes() for p in sorted(get_briefings_dir(user_id).glob("*.json"))}


# ---------------------------------------------------------------------------
# AC-11: Trip-only-Befehle -> „gibt es beim Ortsvergleich nicht"
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("befehl, woerter", [
    ("skip", ("skip",)),
    ("ruhetag 2", ("ruhetag",)),
    ("strecke", ("strecke",)),
    ("### startdatum: 2026-10-01", ("startdatum",)),
    ("status", ("status",)),
    ("jetzt", ("jetzt", "now")),
    ("gewitter", ("gewitter",)),
    ("glance", ("glance",)),
    # STOP ist das Nutzerwort, `abbruch` der interne Schlüssel
    ("stop", ("stop", "abbruch")),
])
def test_ac11_trip_befehl_am_vergleich_wird_abgelehnt(uid, versand, befehl, woerter):
    _preset(uid)
    vorher = _dateien(uid)
    res = _send(uid, befehl)
    assert "gibt es beim Ortsvergleich nicht" in res.confirmation_body, res.confirmation_body
    assert any(w in res.confirmation_body.lower() for w in woerter), res.confirmation_body
    assert res.success is False
    assert _dateien(uid) == vorher
    assert versand == []


def test_ac11_metrikwort_am_vergleich_wird_abgelehnt(uid, versand):
    _preset(uid)
    vorher = _dateien(uid)
    res = _send(uid, "wind")
    assert "gibt es beim Ortsvergleich nicht" in res.confirmation_body, res.confirmation_body
    assert _dateien(uid) == vorher
    assert versand == []


def test_ac11_drilldown_am_vergleich_wird_abgelehnt(uid, versand):
    _preset(uid)
    vorher = _dateien(uid)
    res = _send(uid, "### query: dd_hours_today")
    assert "gibt es beim Ortsvergleich nicht" in res.confirmation_body, res.confirmation_body
    assert _dateien(uid) == vorher
    assert versand == []


@pytest.mark.parametrize("befehl", ["report", "heute", "morgen"])
def test_ac11_report_heute_morgen_uebergangsantwort_ohne_versand(uid, versand, befehl):
    _preset(uid)
    vorher = _dateien(uid)
    res = _send(uid, befehl)
    assert NICHT_VERFUEGBAR in res.confirmation_body, res.confirmation_body
    assert "Web-App" in res.confirmation_body
    assert _dateien(uid) == vorher
    assert versand == [], f"es darf kein Briefing versendet werden: {versand}"


# ---------------------------------------------------------------------------
# AC-12: hilfe am Vergleich = echte Teilmenge der Trip-Hilfe
# ---------------------------------------------------------------------------

def _befehlszeilen(text: str) -> set[str]:
    """Zeilen des Steuerbefehl-Blocks (vor dem Wetter-Größen-Block)."""
    block = text.split("Wetter-Größen", 1)[0]
    return {z.strip().split()[0] for z in block.splitlines() if z.startswith("  ") and z.strip()}


def test_ac12_hilfe_am_vergleich_nur_pause_weiter_hilfe(uid):
    _preset(uid)
    today = date.today()
    trip = Trip(
        id="t-korsika", name="Korsika",
        stages=[Stage(id="S1", name="Tag 1", date=today,
                      waypoints=[Waypoint(id="W1", name="A", lat=47.0, lon=11.0, elevation_m=800)])],
        report_config=TripReportConfig(trip_id="t-korsika"),
    )
    save_trip(trip, uid)

    vergleich = _befehlszeilen(_send(uid, "hilfe").confirmation_body)
    trip_hilfe = _befehlszeilen(_send(uid, "hilfe", name="Korsika").confirmation_body)

    assert vergleich == {"PAUSE", "WEITER", "HILFE"}, vergleich
    assert vergleich < trip_hilfe
    assert {"RUHETAG", "SKIP", "STRECKE"} <= trip_hilfe


# ---------------------------------------------------------------------------
# Adversary Fix-Loop 1, F001 (CRITICAL): Telegram kodiert Query-Keys
# (heute/glance/gewitter/...) unbedingt als "### query: <key>"
# (inbound_telegram_reader.py::_command_body) -- unabhaengig vom Ziel-kind.
# Der Prozessor-Isolationstest oben (_send) baut InboundMessage DIREKT und
# umgeht diese Kodierung komplett -- er kann den Fehler strukturell nicht
# sehen. Reproduktion deshalb ueber den ECHTEN Telegram-Draht.
# ---------------------------------------------------------------------------

def _via_telegram(monkeypatch, user_id: str, text: str) -> list[str]:
    """Echter Telegram-Draht (Muster
    test_eingangsauswahl_trip_und_vergleich.py::_via_telegram) — nur so
    durchlaeuft eine Nachricht `_command_body`s Query-Key-Kodierung."""
    from app.config import Settings
    from services.inbound_telegram_reader import InboundTelegramReader

    sent: list[str] = []
    monkeypatch.setattr(
        "app.loader.lookup_user_by_telegram_chat_id",
        lambda chat_id, data_dir="data": user_id,
    )
    monkeypatch.setattr(
        "services.notification_service.TelegramOutput.send",
        lambda self, subject, body, **kw: sent.append(body) or 1,
    )
    settings = Settings(telegram_bot_token="fake:token", telegram_chat_id="12345")
    update = {
        "update_id": 1,
        "message": {
            "chat": {"id": 12345},
            "text": text,
            "date": int(datetime.now(tz=timezone.utc).timestamp()),
        },
    }
    InboundTelegramReader()._process_update(update, settings)
    return sent


@pytest.mark.parametrize("befehl", ["heute", "glance", "gewitter"])
def test_f001_telegram_query_key_gegen_vergleich_zeigt_ac11_text_ohne_ladehinweis(
    monkeypatch, uid, befehl,
):
    """Adversary F001 (#2282 Fix-Loop 1): Nutzer mit GENAU EINEM aktiven
    Vergleich und KEINEM Trip sendet per Telegram "heute"/"glance"/"gewitter"
    -- alle drei sind Query-Keys, die der Reader als "### query: <key>"
    kodiert. Erwartet: genau eine Antwort, der korrekte AC-11-Text (nicht
    "'query' gibt es beim Ortsvergleich nicht."), KEINE vorherige
    "⏳ Wetter wird geladen..."-Nachricht, Preset-Datei unveraendert."""
    _preset(uid)
    vorher = _dateien(uid)

    sent = _via_telegram(monkeypatch, uid, befehl)

    assert len(sent) == 1, f"genau eine Antwort erwartet, gesehen: {sent!r}"
    assert "⏳" not in sent[0], f"keine Lade-Nachricht am Vergleich erwartet: {sent[0]!r}"
    assert "query" not in sent[0].lower(), (
        f"das falsche Wort 'query' darf nicht mehr erscheinen: {sent[0]!r}"
    )
    if befehl == "heute":
        assert NICHT_VERFUEGBAR in sent[0], sent[0]
        assert "Web-App" in sent[0]
    else:
        assert "gibt es beim Ortsvergleich nicht" in sent[0], sent[0]
    assert _dateien(uid) == vorher


# ---------------------------------------------------------------------------
# Adversary F001-Nachtrag (#2282 Fix-Loop 2): dieselbe Ladehinweis-Luecke
# auch beim vorangestellten NAMEN (nicht nur bei der aktiven Auswahl ohne
# Namen) -- match_leading_name kennt das Kind des Treffers, der Reader
# muss es VOR der Lade-Entscheidung nutzen, ohne eine zweite Suche.
# ---------------------------------------------------------------------------

def test_f001_namenspraefix_vergleich_unterdrueckt_ladehinweis(monkeypatch, uid):
    """Adversary F001-Nachtrag: Trip "Korsika" UND Vergleich "Alpenblick"
    sind beide aktiv. "alpenblick heute" adressiert per Namen eindeutig den
    Vergleich -- die Antwort muss die AC-11-Uebergangsantwort sein, OHNE
    vorherige "⏳ Wetter wird geladen..."-Nachricht (der Vergleich bekommt
    ohnehin nur die synchrone Ablehnung, nie einen Wetterabruf)."""
    today = date.today()
    trip = Trip(
        id="t-korsika-f001b", name="Korsika",
        stages=[Stage(id="S1", name="Tag 1", date=today,
                      waypoints=[Waypoint(id="W1", name="A", lat=47.0, lon=11.0, elevation_m=800)])],
        report_config=TripReportConfig(trip_id="t-korsika-f001b"),
    )
    save_trip(trip, uid)
    _preset(uid, "Alpenblick")

    sent = _via_telegram(monkeypatch, uid, "alpenblick heute")

    assert len(sent) == 1, f"genau eine Antwort erwartet, gesehen: {sent!r}"
    assert "⏳" not in sent[0], f"keine Lade-Nachricht am Vergleich erwartet: {sent[0]!r}"
    assert NICHT_VERFUEGBAR in sent[0], sent[0]
    assert "Web-App" in sent[0]


def test_f001_namenspraefix_trip_zeigt_ladehinweis_weiterhin(monkeypatch, uid):
    """Gegenprobe: "korsika heute" adressiert per Namen eindeutig den TRIP --
    der Trip-Pfad bleibt unveraendert, die Lade-Nachricht muss weiterhin
    erscheinen. `TripCommandProcessor.process()` wird gemockt (Muster
    test_inbound_telegram_reader.py::test_inbound_message_channel_is_telegram)
    -- geprueft wird die Lade-Nachrichten-ENTSCHEIDUNG des Readers, nicht die
    tatsaechliche Wetterverarbeitung (kein Netz)."""
    from services.trip_command_processor import CommandResult

    today = date.today()
    trip = Trip(
        id="t-korsika-f001c", name="Korsika",
        stages=[Stage(id="S1", name="Tag 1", date=today,
                      waypoints=[Waypoint(id="W1", name="A", lat=47.0, lon=11.0, elevation_m=800)])],
        report_config=TripReportConfig(trip_id="t-korsika-f001c"),
    )
    save_trip(trip, uid)

    sent: list[str] = []
    monkeypatch.setattr(
        "app.loader.lookup_user_by_telegram_chat_id",
        lambda chat_id, data_dir="data": uid,
    )
    monkeypatch.setattr(
        "services.notification_service.TelegramOutput.send",
        lambda self, subject, body, **kw: sent.append(body) or 1,
    )
    monkeypatch.setattr(
        "services.notification_service.TelegramOutput.edit_message_text",
        lambda self, chat_id, message_id, text, **kw: None,
    )
    monkeypatch.setattr(
        "services.trip_command_processor.TripCommandProcessor.process",
        lambda self, msg: CommandResult(
            success=True, command="heute", confirmation_subject="Heute",
            confirmation_body="OK", trip_name=msg.trip_name,
        ),
    )
    from app.config import Settings
    from services.inbound_telegram_reader import InboundTelegramReader

    settings = Settings(telegram_bot_token="fake:token", telegram_chat_id="12345")
    update = {
        "update_id": 1,
        "message": {
            "chat": {"id": 12345}, "text": "korsika heute",
            "date": int(datetime.now(tz=timezone.utc).timestamp()),
        },
    }
    InboundTelegramReader()._process_update(update, settings)

    assert any("⏳" in s for s in sent), (
        f"Gegenprobe: Namenspraefix auf einen TRIP muss die Lade-Nachricht "
        f"weiterhin zeigen, gesehen: {sent!r}"
    )
