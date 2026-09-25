"""TDD RED — Issue #2282 Scheibe S1: Eingangsauswahl Trip UND Ortsvergleich.

SPEC: docs/specs/modules/feat_2282_ortsvergleich_eingangskanaele.md
AC-2, AC-4, AC-5, AC-6, AC-7, AC-14, AC-15 (Auswahl, Rückfrage, Namensadressierung,
Namensgleichheit, Mandantentrennung, 160-Zeichen-Kürzung).

Ist-Stand (gemessen):
- Telegram (`inbound_telegram_reader.py:211-227`) und Premium-SMS
  (`inbound_sms_reader.py:322`) lösen ohne Namen ausschliesslich über
  `pick_active_trip` einen TRIP auf. Ein Ortsvergleich ist nie Kandidat.
- `_find_trip`/`_find_trip_id` suchen nur Trips.
- `services.trip_selection.resolve_active_target` existiert nicht.

Vertrag, auf den diese Tests zeigen (ab dem RED-Commit bindend, Known
Limitations der Spec):
    resolve_active_target(trips, presets: list[dict], now_utc, *, channel) -> Ergebnis
    Ergebnis.kind   -> "route" | "vergleich" | None (None = mehrdeutig/keiner)
    Ergebnis.target -> Trip bzw. Preset-dict | None
    Ergebnis.text   -> None bei eindeutig, sonst fertiger Antworttext

Testpolitik: echte Dateien unter der (per conftest umgeleiteten) Datenwurzel,
echter `TripCommandProcessor`. Gepatcht wird nur der Transport
(`TelegramOutput.send`, `PremiumSmsOutput`) und die Chat-Zuordnung — plus ein
AUFZEICHNENDER Wrapper um `process`, der das Original weiter aufruft.
"""
from __future__ import annotations

import json
import shutil
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from app.config import Settings  # noqa: E402
from app.loader import get_briefings_dir, get_data_dir, load_all_trips, save_trip  # noqa: E402
from app.models import TripReportConfig  # noqa: E402
from app.trip import Stage, Trip, Waypoint  # noqa: E402
from services.trip_command_processor import (  # noqa: E402
    InboundMessage,
    TripCommandProcessor,
)

KEIN_KANDIDAT = "Kein aktiver Trip oder Ortsvergleich gefunden"


# ---------------------------------------------------------------------------
# Fixtures / Helfer
# ---------------------------------------------------------------------------

@pytest.fixture
def user_ids():
    created: list[str] = []

    def _new() -> str:
        uid = f"tdd-2282-{uuid.uuid4().hex[:8]}"
        created.append(uid)
        return uid

    yield _new
    for uid in created:
        shutil.rmtree(get_briefings_dir(uid).parent, ignore_errors=True)


def _trip(user_id: str, name: str, start_offset_days: int, days: int = 3) -> Trip:
    today = date.today()
    stages = [
        Stage(
            id=f"S{i}",
            name=f"Tag {i + 1}",
            date=today + timedelta(days=start_offset_days + i),
            waypoints=[Waypoint(id=f"W{i}", name="A", lat=47.0, lon=11.0, elevation_m=800)],
        )
        for i in range(days)
    ]
    tid = f"trip-{uuid.uuid4().hex[:8]}"
    trip = Trip(id=tid, name=name, stages=stages, report_config=TripReportConfig(trip_id=tid))
    save_trip(trip, user_id)
    return trip


def _preset(user_id: str, name: str, **felder) -> dict:
    pid = f"cmp-{uuid.uuid4().hex[:8]}"
    entry = {
        "id": pid,
        "name": name,
        "kind": "vergleich",
        "user_id": user_id,
        "location_ids": ["loc-a", "loc-b"],
        "schedule": "daily",
        "previous_schedule": "",
        "created_at": "2026-09-01T08:00:00Z",
    }
    entry.update(felder)
    d = get_briefings_dir(user_id)
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{pid}.json").write_text(json.dumps(entry, indent=2), encoding="utf-8")
    return entry


def _nutzer_mit_tier(uid: str, tier: str = "premium") -> None:
    """Nachbesserung #2412 S4a: `send_command_reply_premium_sms` (via
    `_via_premium_sms`) hatte vor dem SMS-Tageslimit-Gate keinen Tier-Check
    -- ohne `user.json` faellt `user_tier._tier()` auf "free" zurueck (Cap
    0). Premium-SMS ist laut #1676 D7 ein Premium-Merkmal, diese Tests
    stehen fuer einen Premium-Nutzer. Muster `test_sms_tageslimit.py::
    _nutzer_anlegen`."""
    d = get_data_dir(uid)
    d.mkdir(parents=True, exist_ok=True)
    (d / "user.json").write_text(json.dumps({"id": uid, "tier": tier}))


def _preset_file(user_id: str, preset_id: str) -> Path:
    return get_briefings_dir(user_id) / f"{preset_id}.json"


def _read(user_id: str, preset_id: str) -> dict:
    return json.loads(_preset_file(user_id, preset_id).read_text(encoding="utf-8"))


def _process_recorder(monkeypatch) -> list[InboundMessage]:
    calls: list[InboundMessage] = []
    original = TripCommandProcessor.process

    def _rec(self, msg):
        calls.append(msg)
        return original(self, msg)

    monkeypatch.setattr(TripCommandProcessor, "process", _rec)
    return calls


def _via_telegram(monkeypatch, user_id: str, text: str):
    sent: list[str] = []
    monkeypatch.setattr(
        "app.loader.lookup_user_by_telegram_chat_id",
        lambda chat_id, data_dir="data": user_id,
    )
    monkeypatch.setattr(
        "services.notification_service.TelegramOutput.send",
        lambda self, subject, body, **kw: sent.append(body) or 1,
    )
    calls = _process_recorder(monkeypatch)
    from services.inbound_telegram_reader import InboundTelegramReader

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
    return sent, calls


class _LernAntwort:
    def __init__(self, user_id: str):
        self._uid = user_id

    def json(self):
        return {"user_id": self._uid}


def _via_premium_sms(monkeypatch, user_id: str, text: str):
    sent: list[str] = []
    from output.channels.premium_sms import PremiumSmsOutput

    monkeypatch.setattr(PremiumSmsOutput, "__init__", lambda self, settings: None)
    monkeypatch.setattr(
        PremiumSmsOutput, "send",
        lambda self, subject, body, **kw: sent.append(body),
    )
    calls = _process_recorder(monkeypatch)
    from services.inbound_sms_reader import InboundSmsReader

    InboundSmsReader()._verarbeite_befehl(
        Settings(), text, "+491701234567", _LernAntwort(user_id),
    )
    return sent, calls


_KANAELE = {"telegram": _via_telegram, "premium_sms": _via_premium_sms}


def _gsm7_len(text: str) -> int:
    ext = set("^{}\\[~]|€\f")
    return sum(2 if ch in ext else 1 for ch in text)


# ---------------------------------------------------------------------------
# resolve_active_target — Entscheidungstabelle (Spec Abschnitt 1)
# ---------------------------------------------------------------------------

def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _trip_obj(name: str, start_offset_days: int) -> Trip:
    today = date.today()
    return Trip(
        id=f"t-{name}",
        name=name,
        stages=[
            Stage(
                id="S1", name="Tag 1", date=today + timedelta(days=start_offset_days),
                waypoints=[Waypoint(id="W1", name="A", lat=47.0, lon=11.0, elevation_m=800)],
            ),
            Stage(
                id="S2", name="Tag 2", date=today + timedelta(days=start_offset_days + 1),
                waypoints=[Waypoint(id="W2", name="B", lat=47.0, lon=11.0, elevation_m=800)],
            ),
        ],
    )


def _preset_dict(name: str, **felder) -> dict:
    d = {"id": f"p-{name}", "name": name, "kind": "vergleich", "schedule": "daily"}
    d.update(felder)
    return d


class TestEntscheidungstabelle:
    def test_nur_trip_ist_eindeutig_trip(self):
        from services.trip_selection import resolve_active_target

        trip = _trip_obj("Korsika", 0)
        erg = resolve_active_target([trip], [], _now(), channel="telegram")
        assert erg.kind == "route" and erg.target is trip and erg.text is None

    def test_ein_vergleich_ohne_trip_ist_eindeutig_vergleich(self):
        """AC-2: 0 Trip + 1 Vergleich -> eindeutig, auch wenn pausiert."""
        from services.trip_selection import resolve_active_target

        p = _preset_dict("Alpenblick", schedule="manual", previous_schedule="daily",
                         paused_at="2026-09-10T08:00:00Z")
        erg = resolve_active_target([_trip_obj("Alt", -20)], [p], _now(), channel="telegram")
        assert erg.kind == "vergleich" and erg.target["id"] == p["id"] and erg.text is None

    def test_trip_plus_ein_vergleich_ist_mehrdeutig(self):
        """AC-4 / Mutation 2: genau 1 Trip + 1 Vergleich darf NICHT den Trip bevorzugen."""
        from services.trip_selection import resolve_active_target

        erg = resolve_active_target(
            [_trip_obj("Korsika", 0)], [_preset_dict("Alpenblick")], _now(), channel="telegram",
        )
        assert erg.kind is None and erg.target is None
        assert "Korsika" in erg.text and "Alpenblick" in erg.text

    def test_zwei_vergleiche_ohne_trip_ist_mehrdeutig(self):
        from services.trip_selection import resolve_active_target

        erg = resolve_active_target(
            [], [_preset_dict("Alpenblick"), _preset_dict("Seenblick")], _now(), channel="telegram",
        )
        assert erg.kind is None
        assert "Alpenblick" in erg.text and "Seenblick" in erg.text

    def test_archiviert_und_abgelaufen_zaehlen_nicht(self):
        """Nur archived_at/end_date machen inaktiv — Vergleich mit Enddatum heute bleibt."""
        from services.trip_selection import resolve_active_target

        heute = date.today().isoformat()
        gestern = (date.today() - timedelta(days=2)).isoformat()
        erg = resolve_active_target(
            [],
            [
                _preset_dict("Archiv", archived_at="2026-09-01T00:00:00Z"),
                _preset_dict("Vorbei", end_date=gestern),
                _preset_dict("Heute", end_date=heute),
            ],
            _now(),
            channel="telegram",
        )
        assert erg.kind == "vergleich" and erg.target["name"] == "Heute"

    def test_keiner_liefert_festen_text(self):
        from services.trip_selection import resolve_active_target

        erg = resolve_active_target([], [], _now(), channel="telegram")
        assert erg.kind is None and erg.target is None
        assert KEIN_KANDIDAT in erg.text


# ---------------------------------------------------------------------------
# AC-15: Premium-SMS-Rückfrage passt in 160 GSM-7-Zeichen, Telegram ungekürzt
# ---------------------------------------------------------------------------

class TestAC15Kuerzung:
    NAMEN = [
        "Hochkönigrunde über den Königssee und zurück",
        "Dolomiten Höhenweg Nummer Eins Nord bis Süd",
        "Stubaier Höhenweg große Runde mit Gipfel",
    ]

    def test_premium_sms_rueckfrage_hoechstens_160_mit_allen_kandidaten(self):
        from services.trip_selection import resolve_active_target

        trip = _trip_obj("Korsika Fernwanderweg GR20 komplett Nord-Süd", 0)
        presets = [_preset_dict(n) for n in self.NAMEN]
        tg = resolve_active_target([trip], presets, _now(), channel="telegram")
        assert _gsm7_len(tg.text) > 160, "Fixture muss ohne Kürzung über 160 liegen"
        for n in self.NAMEN + [trip.name]:
            assert n in tg.text, f"Telegram darf nicht kürzen: {n!r} fehlt"

        sms = resolve_active_target([trip], presets, _now(), channel="premium_sms")
        assert _gsm7_len(sms.text) <= 160, f"{_gsm7_len(sms.text)} Zeichen: {sms.text!r}"
        for n in self.NAMEN + [trip.name]:
            assert n[:4] in sms.text, f"Kandidat {n!r} fehlt in der gekürzten Rückfrage"


# ---------------------------------------------------------------------------
# Adversary Fix-Loop 1, F003 (HIGH): _gsm7_laenge erkannte keine
# UCS-2-erzwingenden Zeichen (Emoji, Kyrillisch, CJK) -- ein einziges davon
# zwingt die GESAMTE SMS in UCS-2 (echtes Limit dann 70 statt 160 Zeichen).
# ---------------------------------------------------------------------------

class TestF003Gsm7UnsichereZeichen:
    NAMEN = [
        "🏔 Gipfelblick Route",
        "Кавказский хребет Trip",
        "Zürich Höhenweg",
    ]

    def test_premium_sms_rueckfrage_bleibt_gsm7_sauber_bei_emoji_und_kyrillisch(self):
        """Adversary F003 (#2282 Fix-Loop 1): Kandidatennamen mit Emoji und
        kyrillischen Zeichen duerfen im Premium-SMS-Text NUR noch GSM-7-
        Zeichen enthalten (Reproduktion vor dem Fix: _gsm7_laenge zaehlte
        das Emoji als gewoehnliches 1-Septet-Zeichen, obwohl es GAR NICHT im
        GSM-7-Alphabet steht und die ganze SMS in UCS-2 zwingen wuerde)."""
        from services.trip_selection import _gsm7_sicher, resolve_active_target
        from tests.tdd._gsm7_charset import assert_gsm7_clean

        trip = _trip_obj("Alpentour", 0)
        presets = [_preset_dict(n) for n in self.NAMEN]

        sms = resolve_active_target([trip], presets, _now(), channel="premium_sms")

        assert_gsm7_clean(sms.text, "F003 Ortsvergleich-Rueckfrage (premium_sms)")
        assert _gsm7_len(sms.text) <= 160, f"{_gsm7_len(sms.text)} Zeichen: {sms.text!r}"
        for n in self.NAMEN:
            kurz = _gsm7_sicher(n)[:4]
            assert kurz in sms.text, (
                f"Kandidat {n!r} (gefaltet {kurz!r}) fehlt in der Rückfrage: {sms.text!r}"
            )

        # Telegram bleibt unveraendert (kein Sanierungsbedarf, kein Limit).
        tg = resolve_active_target([trip], presets, _now(), channel="telegram")
        for n in self.NAMEN:
            assert n in tg.text, f"Telegram darf Namen nicht falten/kürzen: {n!r} fehlt"


# ---------------------------------------------------------------------------
# AC-2: 0 Trip + 1 (pausierter) Vergleich -> `weiter` ohne Namen setzt fort
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kanal", ["telegram", "premium_sms"])
def test_ac2_weiter_ohne_namen_setzt_einzigen_vergleich_fort(monkeypatch, user_ids, kanal):
    uid = user_ids()
    _nutzer_mit_tier(uid)
    _trip(uid, "Alter-Trip", start_offset_days=-20)
    p = _preset(uid, "Alpenblick", schedule="manual", previous_schedule="weekly",
                paused_at="2026-09-10T08:00:00Z")

    sent, calls = _KANAELE[kanal](monkeypatch, uid, "weiter")

    nachher = _read(uid, p["id"])
    assert nachher["schedule"] == "weekly"
    assert not nachher.get("paused_at")
    assert sent and "Mehrdeutig" not in sent[-1] and KEIN_KANDIDAT not in sent[-1]


# ---------------------------------------------------------------------------
# AC-4: Mehrdeutigkeit -> Rückfrage direkt vom Reader, process() NIE aufgerufen
#
# AC-14 (#2417) verengt diese Erwartung: die Zeile testete bislang implizit
# JEDEN Befehl ohne Namen (hier stellvertretend "pause"), weil der Reader
# `resolve_active_target` bisher UNKLASSIFIZIERT fuer jedes Wort aufrief. Nach
# #2417 bleibt das nur noch fuer die `_BEIDE_KINDS`-Befehle (`pause`/`weiter`)
# so — deshalb jetzt ausdruecklich ueber beide parametrisiert, statt nur ueber
# "pause" stellvertretend fuer "jeden Befehl".
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kanal", ["telegram", "premium_sms"])
@pytest.mark.parametrize("lage", ["trip_plus_vergleich", "zwei_vergleiche"])
@pytest.mark.parametrize("befehl", ["pause", "weiter"])
def test_ac4_mehrdeutig_fragt_zurueck_ohne_wirkung(monkeypatch, user_ids, kanal, lage, befehl):
    uid = user_ids()
    _nutzer_mit_tier(uid)
    namen = ["Alpenblick"]
    trip = None
    if lage == "trip_plus_vergleich":
        trip = _trip(uid, "Korsika", start_offset_days=-1)
        namen.append("Korsika")
    else:
        _preset(uid, "Seenblick")
        namen.append("Seenblick")
    p = _preset(uid, "Alpenblick")
    vorher_preset = _preset_file(uid, p["id"]).read_bytes()

    sent, calls = _KANAELE[kanal](monkeypatch, uid, befehl)

    assert calls == [], "Mutation 6: process() darf bei Mehrdeutigkeit nicht laufen"
    assert len(sent) == 1
    for n in namen:
        assert n in sent[0], f"Rückfrage nennt {n!r} nicht: {sent[0]!r}"
    assert _preset_file(uid, p["id"]).read_bytes() == vorher_preset
    if trip is not None:
        geladen = next(t for t in load_all_trips(uid) if t.id == trip.id)
        assert geladen.report_config.paused_until is None


# ---------------------------------------------------------------------------
# AC-14 (#2417): Befehle ausserhalb `_BEIDE_KINDS` (hier stellvertretend
# "status", `_ROUTE_ONLY`) werden bei Trip+Vergleich (L3) NICHT MEHR
# mehrdeutig -- sie erreichen den einzigen aktiven Trip, der Ortsvergleich
# wird ignoriert (Matrix-Zeile `_ROUTE_ONLY`/L3: "Antwort an Trip (NEU)").
# Loest die alte, hier zuvor mitprazierte Erwartung ab, dass JEDER Befehl
# ohne Namen bei Trip+Vergleich in die Rueckfrage laeuft.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kanal", ["telegram", "premium_sms"])
def test_ac14_route_only_befehl_erreicht_bei_trip_plus_vergleich_den_trip(monkeypatch, user_ids, kanal):
    uid = user_ids()
    trip = _trip(uid, "Korsika", start_offset_days=-1)
    _preset(uid, "Alpenblick")

    sent, calls = _KANAELE[kanal](monkeypatch, uid, "status")

    assert calls, "AC-14: 'status' muss den Trip erreichen, nicht mehrdeutig bleiben"
    assert calls[0].trip_name == trip.name, (
        f"AC-14: 'status' muss an den Trip {trip.name!r} adressiert sein, "
        f"erhalten {calls[0].trip_name!r}"
    )
    assert len(sent) == 1
    assert "Mehrdeutig" not in sent[0] and "Alpenblick" not in sent[0], (
        f"AC-14: 'status' darf keine Rueckfrage mehr ausloesen: {sent[0]!r}"
    )
    assert trip.name in sent[0], f"AC-14: Antwort muss den Trip nennen: {sent[0]!r}"


# ---------------------------------------------------------------------------
# AC-5: kein Kandidat -> identischer Text auf beiden Kanälen
# ---------------------------------------------------------------------------

def test_ac5_kein_kandidat_gleicher_text_auf_beiden_kanaelen(monkeypatch, user_ids):
    uid = user_ids()
    _nutzer_mit_tier(uid)
    _trip(uid, "Alter-Trip", start_offset_days=-20)
    _preset(uid, "Archiv", archived_at="2026-09-01T00:00:00Z")

    tg_sent, tg_calls = _via_telegram(monkeypatch, uid, "pause")
    sms_sent, sms_calls = _via_premium_sms(monkeypatch, uid, "pause")

    assert tg_calls == [] and sms_calls == []
    assert len(tg_sent) == 1 and len(sms_sent) == 1
    assert KEIN_KANDIDAT in tg_sent[0]
    assert tg_sent[0] == sms_sent[0]


# ---------------------------------------------------------------------------
# AC-6: vorangestellter Name löst Mehrdeutigkeit auf (Trip ODER Vergleich)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kanal", ["telegram", "premium_sms"])
def test_ac6_name_des_vergleichs_spricht_vergleich_an(monkeypatch, user_ids, kanal):
    uid = user_ids()
    trip = _trip(uid, "Korsika", start_offset_days=-1)
    p = _preset(uid, "Alpenblick")

    sent, calls = _KANAELE[kanal](monkeypatch, uid, "alpenblick pause")

    assert len(calls) == 1, "Name gegeben -> process() muss laufen"
    nachher = _read(uid, p["id"])
    assert nachher["schedule"] == "manual" and nachher.get("paused_at")
    geladen = next(t for t in load_all_trips(uid) if t.id == trip.id)
    assert geladen.report_config.paused_until is None


@pytest.mark.parametrize("kanal", ["telegram", "premium_sms"])
def test_ac6_name_des_trips_spricht_trip_an(monkeypatch, user_ids, kanal):
    uid = user_ids()
    trip = _trip(uid, "Korsika", start_offset_days=-1)
    p = _preset(uid, "Alpenblick")
    vorher_preset = _preset_file(uid, p["id"]).read_bytes()

    # Trip-Pause verlangt eine Dauer (test_issue_882_pause_skip) — "pause" ohne
    # Dauer wird am Trip abgelehnt, das ist Bestand und nicht Gegenstand von AC-6.
    sent, calls = _KANAELE[kanal](monkeypatch, uid, "korsika pause 2d")

    assert len(calls) == 1
    geladen = next(t for t in load_all_trips(uid) if t.id == trip.id)
    assert geladen.report_config.paused_until is not None
    assert _preset_file(uid, p["id"]).read_bytes() == vorher_preset


def test_ac6_email_betreff_findet_vergleich(user_ids):
    uid = user_ids()
    _trip(uid, "Korsika", start_offset_days=-1)
    p = _preset(uid, "Alpenblick")
    from services.inbound_email_reader import InboundEmailReader

    assert InboundEmailReader()._find_trip_id("Alpenblick", uid) == p["id"]


def test_ac6_email_nachricht_mit_vergleichsnamen_pausiert_vergleich(user_ids):
    uid = user_ids()
    p = _preset(uid, "Alpenblick")
    TripCommandProcessor().process(InboundMessage(
        trip_name="Alpenblick", body="pause", sender="a@example.com",
        channel="email", received_at=_now(), user_id=uid,
    ))
    nachher = _read(uid, p["id"])
    assert nachher["schedule"] == "manual" and nachher.get("paused_at")


# ---------------------------------------------------------------------------
# AC-7: Namensgleichheit Trip <-> Vergleich -> Rückfrage statt stiller Trip-Wahl
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kanal", ["telegram", "premium_sms"])
def test_ac7_namensgleichheit_fragt_zurueck(monkeypatch, user_ids, kanal):
    uid = user_ids()
    _nutzer_mit_tier(uid)
    trip = _trip(uid, "Dolomiten", start_offset_days=-1)
    p = _preset(uid, "Dolomiten")
    vorher_preset = _preset_file(uid, p["id"]).read_bytes()

    sent, _calls = _KANAELE[kanal](monkeypatch, uid, "dolomiten pause")

    assert sent, "Nutzer muss eine Antwort bekommen"
    assert "Trip" in sent[-1] and "Vergleich" in sent[-1], sent[-1]
    assert _preset_file(uid, p["id"]).read_bytes() == vorher_preset
    geladen = next(t for t in load_all_trips(uid) if t.id == trip.id)
    assert geladen.report_config.paused_until is None


# ---------------------------------------------------------------------------
# AC-14: Mandantentrennung bei gleichnamigen Vergleichen zweier Nutzer
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kanal", ["telegram", "premium_sms"])
def test_ac14_pause_trifft_nur_den_vergleich_des_absenders(monkeypatch, user_ids, kanal):
    uid_a, uid_b = user_ids(), user_ids()
    pa = _preset(uid_a, "Alpenblick")
    pb = _preset(uid_b, "Alpenblick")
    vorher_b = _preset_file(uid_b, pb["id"]).read_bytes()

    sent, calls = _KANAELE[kanal](monkeypatch, uid_a, "pause")

    assert _read(uid_a, pa["id"])["schedule"] == "manual"
    assert _preset_file(uid_b, pb["id"]).read_bytes() == vorher_b
    assert calls and all(c.user_id == uid_a for c in calls)


# ---------------------------------------------------------------------------
# Adversary Fix-Loop 1, F002 (HIGH): match_leading_name verschluckt den
# Befehl, wenn ein Trip/Vergleich zufaellig wie ein Steuerbefehlswort heisst
# (z. B. "Pause") -- der komplette Text wird dann als Name gelesen, kein
# Rest-Befehl bleibt uebrig.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kanal", ["telegram", "premium_sms"])
def test_f002_trip_name_gleich_befehlswort_pausiert_trotzdem(monkeypatch, user_ids, kanal):
    """Adversary F002 (#2282 Fix-Loop 1): ein Trip heisst "Pause" (einziger
    aktiver Kandidat). Sendet der Nutzer "pause 2d" (PAUSE-Befehl mit Dauer),
    darf match_leading_name NICHT den kompletten Namen "pause" konsumieren
    (Rest waere dann nur "2d", fuer sich kein gueltiger Befehl) -- vor dem
    Fix antwortete das System "Das war kein bekannter Befehl.", der Trip
    blieb unpausiert. Fallback: die normale aktive Auswahl (genau ein
    Kandidat) muss den vollen Text "pause 2d" als Trip-Befehl verarbeiten."""
    uid = user_ids()
    _nutzer_mit_tier(uid)
    trip = _trip(uid, "Pause", start_offset_days=-1)

    sent, calls = _KANAELE[kanal](monkeypatch, uid, "pause 2d")

    assert sent, "Nutzer muss eine Antwort bekommen"
    assert "kein bekannter Befehl" not in sent[-1], (
        f"F002: 'pause 2d' am Trip 'Pause' darf nicht als unbekannter "
        f"Befehl abgelehnt werden: {sent[-1]!r}"
    )
    geladen = next(t for t in load_all_trips(uid) if t.id == trip.id)
    assert geladen.report_config.paused_until is not None, (
        f"F002: Trip 'Pause' haette pausiert werden muessen, Antwort war: {sent!r}"
    )


@pytest.mark.parametrize("kanal", ["telegram", "premium_sms"])
def test_f002_name_gleich_befehlswort_mit_folgebefehl_spricht_trip_an(
    monkeypatch, user_ids, kanal,
):
    """Adversary F002 (#2282 Fix-Loop 1), Gegenprobe: Trip "Pause" UND
    Vergleich "Alpenblick" sind gleichzeitig aktiv (ohne Namen waere das
    mehrdeutig, AC-4). Der Nutzer tippt "pause pause 2d" -- das erste
    "pause" ist der Name, der Rest "pause 2d" der eigentliche Befehl. Die
    Namensadressierung muss trotz identischem Namens-/Befehlswort weiter
    funktionieren, wenn ein echter Folgebefehl uebrigbleibt."""
    uid = user_ids()
    trip = _trip(uid, "Pause", start_offset_days=-1)
    p = _preset(uid, "Alpenblick")
    vorher_preset = _preset_file(uid, p["id"]).read_bytes()

    sent, calls = _KANAELE[kanal](monkeypatch, uid, "pause pause 2d")

    assert len(calls) == 1, "Name gegeben -> process() muss laufen"
    geladen = next(t for t in load_all_trips(uid) if t.id == trip.id)
    assert geladen.report_config.paused_until is not None, (
        f"F002: Trip 'Pause' haette ueber den vorangestellten Namen "
        f"adressiert werden muessen, Antwort war: {sent!r}"
    )
    assert _preset_file(uid, p["id"]).read_bytes() == vorher_preset


# ---------------------------------------------------------------------------
# Adversary Fix-Loop 2, F004 (HIGH): Premium-SMS faltet Namen in der
# Rueckfrage auf GSM-7 (F003) -- antwortet der Nutzer mit GENAU diesem
# angezeigten (gefalteten) Namen, muss das den Original-Vergleich treffen,
# sonst entsteht eine kostenpflichtige Rueckfrage-Endlosschleife.
# ---------------------------------------------------------------------------

def _vergleichsname_aus_rueckfrage(text: str) -> str:
    """Liest den bei '(Vergleich)' angezeigten Namen aus einer Rueckfrage
    aus -- NICHT hartkodiert, da genau die Faltung selbst geprueft wird."""
    vor = text.split("(Vergleich)")[0].strip()
    return vor.rsplit(", ", 1)[-1].strip()


@pytest.mark.parametrize("name_original", ["Zürich-Runde", "Großglockner", "Écrins"])
def test_f004_gefalteter_rueckfragename_findet_den_vergleich(
    monkeypatch, user_ids, name_original,
):
    """Adversary F004: Trip "Korsika" + Vergleich ``name_original`` sind
    beide aktiv -> "pause" ohne Namen liefert eine Rueckfrage mit dem
    GSM-7-gefalteten Namen des Vergleichs. Antwortet der Nutzer mit GENAU
    diesem angezeigten Namen ("<gefaltet> pause"), muss der Original-
    Vergleich pausiert werden, der Trip bleibt unberuehrt."""
    uid = user_ids()
    _nutzer_mit_tier(uid)
    trip = _trip(uid, "Korsika", start_offset_days=-1)
    p = _preset(uid, name_original)

    sent1, calls1 = _via_premium_sms(monkeypatch, uid, "pause")
    assert calls1 == [], "Mehrdeutigkeit darf process() nicht aufrufen"
    assert len(sent1) == 1
    angezeigt = _vergleichsname_aus_rueckfrage(sent1[0])
    assert angezeigt != name_original, (
        f"Testvoraussetzung verletzt: {name_original!r} muesste durch die "
        f"Faltung tatsaechlich veraendert werden, war unveraendert im Text: "
        f"{sent1[0]!r}"
    )

    sent2, calls2 = _via_premium_sms(monkeypatch, uid, f"{angezeigt} pause")

    nachher = _read(uid, p["id"])
    assert nachher["schedule"] == "manual" and nachher.get("paused_at"), (
        f"Vergleich {name_original!r} (angezeigt als {angezeigt!r}) haette "
        f"pausiert werden muessen, Antwort war: {sent2!r}"
    )
    geladen = next(t for t in load_all_trips(uid) if t.id == trip.id)
    assert geladen.report_config.paused_until is None


def test_f004_exakter_treffer_hat_vorrang_vor_gefaltetem(monkeypatch, user_ids):
    """Adversary F004: "Zürich" UND "Zuerich" sind beide aktive Vergleiche
    (ihre gefaltete Form ist identisch: "Zuerich"). Antwortet der Nutzer mit
    "zuerich pause" (== dem UNVERAENDERTEN Rohnamen von Kandidat 2), muss der
    EXAKTE Treffer vor der Faltung gewinnen -- Kandidat 1 ("Zürich") bleibt
    unberuehrt, obwohl seine gefaltete Form ebenfalls "Zuerich" waere."""
    uid = user_ids()
    p1 = _preset(uid, "Zürich")
    p2 = _preset(uid, "Zuerich")

    sent, calls = _via_premium_sms(monkeypatch, uid, "zuerich pause")

    assert len(calls) == 1, "Name gegeben -> process() muss laufen"
    assert _read(uid, p2["id"])["schedule"] == "manual", (
        f"Kandidat 2 ('Zuerich', exakter Treffer) haette pausiert werden "
        f"muessen, Antwort: {sent!r}"
    )
    assert _read(uid, p1["id"])["schedule"] != "manual", (
        "Kandidat 1 ('Zürich') darf trotz gleicher gefalteter Form NICHT "
        "pausiert werden -- der exakte Treffer hat Vorrang"
    )


def test_f004_gefaltete_mehrdeutigkeit_wird_nicht_stillschweigend_aufgeloest(
    monkeypatch, user_ids,
):
    """Adversary F004, Mehrdeutigkeits-Zweig: "Écrins" (Akut) und "Ècrins"
    (Gravis) falten BEIDE auf "Ecrins" (fold_ascii/anyascii unterscheidet
    die Akzente nicht) -- keiner der beiden Rohnamen trifft "ecrins" EXAKT,
    aber beide gefaltet. Der Treffer darf NICHT stillschweigend den ersten
    nehmen: keiner der beiden Vergleiche darf veraendert werden."""
    uid = user_ids()
    p1 = _preset(uid, "Écrins")
    p2 = _preset(uid, "Ècrins")
    vor1 = _preset_file(uid, p1["id"]).read_bytes()
    vor2 = _preset_file(uid, p2["id"]).read_bytes()

    sent, calls = _via_premium_sms(monkeypatch, uid, "ecrins pause")

    assert _preset_file(uid, p1["id"]).read_bytes() == vor1, (
        f"'Écrins' darf durch die mehrdeutige Faltung nicht veraendert "
        f"werden, Antwort: {sent!r}"
    )
    assert _preset_file(uid, p2["id"]).read_bytes() == vor2, (
        f"'Ècrins' darf durch die mehrdeutige Faltung nicht veraendert "
        f"werden, Antwort: {sent!r}"
    )


def test_f005_gefaltete_mehrdeutigkeit_bei_trips_waehlt_keinen(user_ids):
    """Adversary F005: Gegenstueck zum Vergleichs-Fall fuer `_find_trip` im
    Prozessor (E-Mail-/Namenspfad). "Écrins Runde" und "Ècrins Runde" falten
    beide auf "Ecrins Runde"; "ecrins runde" trifft keinen exakt. Keiner der
    beiden Trips darf pausiert werden (kein stiller erster Treffer)."""
    uid = user_ids()
    t1 = _trip(uid, "Écrins Runde", start_offset_days=-1)
    t2 = _trip(uid, "Ècrins Runde", start_offset_days=5)

    TripCommandProcessor().process(InboundMessage(
        trip_name="ecrins runde", body="pause 2d", sender="a@example.com",
        channel="email", received_at=_now(), user_id=uid,
    ))

    for t in (t1, t2):
        geladen = next(x for x in load_all_trips(uid) if x.id == t.id)
        assert geladen.report_config.paused_until is None, t.name
