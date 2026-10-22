"""TDD RED — Issue #2282 Scheibe S2: report/heute/morgen am Ortsvergleich
liefern ein echtes Vergleichs-Briefing.

SPEC: docs/specs/modules/feat_2282_s2_ortsvergleich_befehle_versand.md
(AC-1 bis AC-12, AC-14, AC-15 im Kern; AC-13 und AC-16 sind reine
Staging-Schicht und haben hier bewusst KEINEN Ersatztest).

Aufbau (kein Mock-Theater):

* Preset als ROHES Fixture-JSON (``tests/fixtures/compare_kette/basis.json``)
  im Nutzerverzeichnis, gelesen vom ECHTEN Loader.
* Wetter: ``_compare_kette_fixtures.engine_naht`` -- echte Subklasse von
  ``ComparisonEngine`` mit aufgezeichneten Tageswerten je Ort, kein Netz.
* Transport: geteilter Aufzeichner ``tests/helpers/transport_mitschrift.py``
  -- ersetzt NUR die vier Ausgangsklassen, die Kanal-Entscheidung faellt im
  Produktivcode. Gezaehlt wird je Kanal.
* Befehle laufen durch den echten Eingang: ``TripCommandProcessor.process``
  je Kanal (``channel=...``), bzw. ``InboundTelegramReader._process_update``
  und ``InboundSmsReader._verarbeite_befehl`` fuer die Adressierung.

Neue Symbole (``resolve_restricted_channel_flags``, ``preset_ortstag``,
``send_compare_preset(restrict_to_channel=...)``) werden ausschliesslich in
den Testfunktionen ueber ``getattr`` geholt -- die Datei bleibt sammelbar und
jeder Test wird aus einem Verhaltensgrund rot.
"""
from __future__ import annotations

import json
import re
import sys
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(REPO_ROOT / "src"))

from app.loader import get_data_dir, save_trip  # noqa: E402
from app.models import TripReportConfig  # noqa: E402
from app.trip import Stage, Trip, Waypoint  # noqa: E402
from services.trip_command_processor import (  # noqa: E402
    InboundMessage,
    TripCommandProcessor,
)
from tests.helpers.transport_mitschrift import aufzeichner_installieren  # noqa: E402
from tests.tdd import _compare_kette_fixtures as kette  # noqa: E402

#: Chat, aus dem die Telegram-Befehle kommen -- bewusst NICHT der Profil-Chat
#: (``chat-<uid>``), damit Befehlsantwort und Briefing am Ziel trennbar sind.
EINGANG_CHAT = "777000111"
PREMIUM_ABSENDER = "+490000000008"
LADEHINWEIS = "⏳"
UEBERGANGSANTWORT = "noch nicht verfügbar"


# ---------------------------------------------------------------------------
# Aufbau
# ---------------------------------------------------------------------------


@pytest.fixture
def mit(monkeypatch):
    """Transport-Env unbrauchbar (#1477), aufgezeichnetes Wetter, Aufzeichner
    an den vier Ausgaengen. Telegram bekommt zusaetzlich ``edit_message_text``/
    ``delete_message`` (der Reader ersetzt damit den Ladehinweis), beides wird
    mitgeschrieben."""
    kette.transport_einrichten(monkeypatch)
    kette.engine_naht(monkeypatch)
    mitschrift = aufzeichner_installieren(monkeypatch)

    from services import notification_service as ns

    basis = ns.TelegramOutput

    class _TelegramMitBearbeiten(basis):
        def edit_message_text(self, chat_id, message_id, text, **kw):
            mitschrift.je_kanal["telegram"].append({
                "empfaenger": str(chat_id), "subject": "edit", "body": text,
                "plain_text_body": None, "parse_mode": None, "mail_type": None,
                "mail_format": None, "compare_hourly_enabled": None,
            })
            return True

        def delete_message(self, chat_id, message_id):
            return True

    monkeypatch.setattr(ns, "TelegramOutput", _TelegramMitBearbeiten)
    return mitschrift


@pytest.fixture
def anker(monkeypatch, mit):
    """Zaehlt Δ-Anker-Schreibvorgaenge. ``engine_naht`` setzt den Schreiber auf
    einen stummen No-op -- dann waere „Anker unveraendert" vakuum-wahr. Hier
    wird jeder Aufruf mitgezaehlt (kein Netz, kein Rueckgabewert noetig)."""
    import services.scheduler_dispatch_service as sds

    aufrufe: list[tuple] = []
    monkeypatch.setattr(sds, "_write_compare_alert_snapshots",
                        lambda *a, **k: aufrufe.append(a))
    return aufrufe


def _nutzer(tier: str = "premium", **profil_aenderung) -> str:
    """Frisches Profil (eigene Empfaenger) + die beiden Fixture-Orte."""
    uid = kette.nutzer_anlegen(tier)
    if profil_aenderung:
        pfad = get_data_dir(uid) / "user.json"
        daten = json.loads(pfad.read_text())
        for feld, wert in profil_aenderung.items():
            if wert is None:
                daten.pop(feld, None)
            else:
                daten[feld] = wert
        pfad.write_text(json.dumps(daten))
    kette.orte_anlegen(uid)
    return uid


def _vergleich(uid: str, name: str = "Alpenblick", **felder) -> dict:
    preset = kette.fixture_dict("basis")
    preset["id"] = f"cmp-{uuid.uuid4().hex[:8]}"
    preset["name"] = name
    preset.update(felder)
    kette.preset_ablegen(uid, preset)
    return preset


def _trip(uid: str, name: str = "Korsika") -> Trip:
    heute = date.today()
    tid = f"trip-{uuid.uuid4().hex[:8]}"
    stages = [
        Stage(id=f"S{i}", name=f"Tag {i + 1}", date=heute + timedelta(days=i - 1),
              waypoints=[Waypoint(id=f"W{i}", name="A", lat=47.0, lon=11.0,
                                  elevation_m=800)])
        for i in range(3)
    ]
    trip = Trip(id=tid, name=name, stages=stages,
                report_config=TripReportConfig(trip_id=tid))
    save_trip(trip, uid)
    return trip


def _befehl(uid: str, body: str, *, name: str = "Alpenblick", kanal: str = "telegram",
            received_at: datetime | None = None):
    """Der echte Prozessor-Eingang mit dem Kanal, ueber den der Befehl kam."""
    sender = {"premium_sms": PREMIUM_ABSENDER, "sms": "+490000000009",
              "email": f"{uid}@example.invalid"}.get(kanal, EINGANG_CHAT)
    return TripCommandProcessor().process(InboundMessage(
        trip_name=name, body=body, sender=sender, channel=kanal,
        received_at=received_at or datetime.now(tz=timezone.utc), user_id=uid,
    ))


def _telegram_eingang(monkeypatch, uid: str, text: str) -> None:
    """Getippter Telegram-Text durch den ECHTEN Webhook-Pfad."""
    from app.config import Settings
    from services.inbound_telegram_reader import InboundTelegramReader

    monkeypatch.setattr("app.loader.lookup_user_by_telegram_chat_id",
                        lambda chat_id, data_dir="data": uid)
    update = {"update_id": 1, "message": {
        "chat": {"id": int(EINGANG_CHAT)}, "text": text,
        "date": int(datetime.now(tz=timezone.utc).timestamp()),
    }}
    InboundTelegramReader()._process_update(update, Settings())


class _LernAntwort:
    def __init__(self, user_id: str):
        self._uid = user_id

    def json(self):
        return {"user_id": self._uid}


def _premium_sms_eingang(uid: str, text: str) -> None:
    """Satelliten-Text durch den ECHTEN Premium-SMS-Befehlspfad."""
    from app.config import Settings
    from services.inbound_sms_reader import InboundSmsReader

    InboundSmsReader()._verarbeite_befehl(Settings(), text, PREMIUM_ABSENDER,
                                          _LernAntwort(uid))


def _an_eingang(mit) -> list[dict]:
    """Telegram-Sendungen an den fragenden Chat (Befehlsantworten, Ladehinweis)."""
    return [s for s in mit.sendungen("telegram") if str(s["empfaenger"]) == EINGANG_CHAT]


def _briefing_telegram(mit, uid: str) -> list[dict]:
    """Telegram-Sendungen an den Profil-Chat des Nutzers (= Briefing)."""
    return [s for s in mit.sendungen("telegram") if str(s["empfaenger"]) == f"chat-{uid}"]


def _log(uid: str) -> list[dict]:
    pfad = get_data_dir(uid) / "briefing_log.json"
    if not pfad.exists():
        return []
    return json.loads(pfad.read_text(encoding="utf-8")).get("entries", [])


def _antworttext(res) -> str:
    return f"{res.confirmation_subject}\n{res.confirmation_body}"


def _stand(uid: str) -> dict[str, bytes]:
    """Byte-Stand ALLER Dateien des Nutzers (Status, briefing_log, Presets)."""
    wurzel = get_data_dir(uid)
    return {str(p.relative_to(wurzel)): p.read_bytes()
            for p in sorted(wurzel.rglob("*")) if p.is_file()}


def _user_tier_funktion():
    import services.user_tier as user_tier

    fn = getattr(user_tier, "resolve_restricted_channel_flags", None)
    assert fn is not None, (
        "services.user_tier hat keine Funktion `resolve_restricted_channel_flags"
        "(restrict, user_id)` -- die Kanal-Aufloesung fuer den Anfragekanal steht "
        "nur im Trip (`TripReportSchedulerService._resolve_channel_flags`) und "
        "ist fuer den Ortsvergleich nicht teilbar (Spec Impl. 4, AC-7)."
    )
    return fn


# ═══════════════════════════ AC-1 ════════════════════════════════════════════


def test_ac1_report_per_telegram_liefert_auf_allen_aktivierten_kanaelen(monkeypatch, mit):
    """AC-1: report durch den Telegram-Eingang -> Vergleichs-Briefing je
    aktiviertem Kanal genau einmal + Bestaetigung im Trip-Wortlaut."""
    uid = _nutzer("premium")
    _vergleich(uid, send_telegram=True, send_sms=True, send_premium_sms=True,
               alert_channels=[])

    _telegram_eingang(monkeypatch, uid, "report")

    mails = mit.sendungen("email")
    assert len(mails) == 1 and mails[0]["mail_type"] == "compare", (
        f"AC-1: genau eine Vergleichs-Mail erwartet: {mit!r}"
    )
    assert len(mit.sendungen("sms")) == 1, mit
    assert len(mit.sendungen("premium_sms")) == 1, mit
    assert len(_briefing_telegram(mit, uid)) == 1, mit
    antworten = "\n".join(s["body"] or "" for s in _an_eingang(mit))
    assert "Report wird jetzt gesendet" in antworten, (
        f"AC-1: Bestaetigung im Wortlaut des Trip-report erwartet: {antworten!r}"
    )
    assert UEBERGANGSANTWORT not in antworten


# ═══════════════════════════ AC-2 ════════════════════════════════════════════


def test_ac2_heute_per_telegram_nur_auf_telegram(mit):
    uid = _nutzer("premium")
    _vergleich(uid, send_telegram=True, send_sms=True, send_premium_sms=True,
               alert_channels=[])

    res = _befehl(uid, "heute", kanal="telegram")

    assert mit.kanaele == ["telegram"], (
        f"AC-2: heute kam ueber Telegram -- NUR Telegram darf bedient werden: {mit!r}"
    )
    assert len(_briefing_telegram(mit, uid)) == 1, mit
    assert res.suppress_email_reply is True, "das Briefing IST die Antwort"
    eintraege = [e for e in _log(uid) if e.get("entity_type") == "compare"]
    assert eintraege and eintraege[-1]["channels"] == ["telegram"], eintraege
    assert eintraege[-1]["kind"] == "morning" and eintraege[-1]["on_demand"] is True


# ═══════════════════════════ AC-3 ════════════════════════════════════════════


def test_ac3_morgen_zieltag_ist_ortstag_plus_eins_und_abendslot(mit):
    """AC-3: 22:30 UTC am 06.07. ist in Innsbruck (CEST) schon der 07.07.
    ``morgen`` betrifft deshalb den 08.07. -- ein Server-/UTC-Tag-basierter
    Zieltag laege auf dem 07.07. Zeitquelle ist ``received_at`` (ADR-0051)."""
    import services.compare_slot_scheduler as css
    from services.scheduler_dispatch_service import build_compare_preset_subject

    uid = _nutzer("premium")
    preset = _vergleich(uid, send_telegram=True)
    eingang = datetime(2026, 7, 6, 22, 30, tzinfo=timezone.utc)

    res = _befehl(uid, "morgen", kanal="telegram", received_at=eingang)

    preset_ortstag = getattr(css, "preset_ortstag", None)
    assert preset_ortstag is not None, (
        "services.compare_slot_scheduler hat keine Funktion `preset_ortstag("
        "preset, all_locations, now_utc)` -- die Ortstag-Rechnung steckt inline "
        "in `presets_due_for_hour` und ist fuer den Befehl nicht nutzbar."
    )
    orte = {o.id: o for o in kette.alle_orte(uid)}
    ortstag = preset_ortstag(kette.preset_laden(uid, preset["id"]), orte, eingang)
    assert ortstag == date(2026, 7, 7), ortstag
    briefing = _briefing_telegram(mit, uid)
    assert len(briefing) == 1, f"AC-3: genau ein Briefing auf Telegram: {mit!r} / {res!r}"
    erwartet = build_compare_preset_subject(preset["name"], ortstag + timedelta(days=1))
    assert erwartet == build_compare_preset_subject(preset["name"], date(2026, 7, 8))
    assert briefing[0]["subject"] == erwartet, (
        f"AC-3: Zieltag muss Ortstag+1 (08.07.) sein: {briefing[0]['subject']!r}"
    )
    eintraege = [e for e in _log(uid) if e.get("entity_type") == "compare"]
    assert eintraege and eintraege[-1]["kind"] == "evening", eintraege


# ═══════════════════════════ AC-4 ════════════════════════════════════════════


def test_ac4_heute_per_email_eine_vergleichsmail_ohne_antwortmail(mit):
    uid = _nutzer("premium")
    _vergleich(uid, send_telegram=True, send_sms=True)

    res = _befehl(uid, "heute", kanal="email")

    assert mit.kanaele == ["email"], mit
    mails = mit.sendungen("email")
    assert len(mails) == 1 and mails[0]["mail_type"] == "compare", mails
    assert res.suppress_email_reply is True, (
        "AC-4: keine zusaetzliche Text-Antwortmail neben dem Briefing"
    )


# ═══════════════════════════ AC-5 ════════════════════════════════════════════


def test_ac5_heute_per_sms_kompakt_nur_sms(mit):
    """SMS ist kein eigener Eingangsleser (nur Premium-SMS) -- deshalb ueber den
    Prozessor-Eingang mit ``channel="sms"``."""
    uid = _nutzer("standard")
    _vergleich(uid, send_sms=True, send_telegram=True)

    res = _befehl(uid, "heute", kanal="sms")

    assert mit.kanaele == ["sms"], mit
    sms = mit.sendungen("sms")
    assert len(sms) == 1 and 0 < len(sms[0]["body"]) <= 160, sms
    assert res.suppress_email_reply is True


def test_ac5_heute_per_sms_bei_ausgeschoepftem_tageslimit_absage(mit):
    uid = _nutzer("standard")
    _vergleich(uid, send_sms=True)
    kette.sms_tageslimit_erschoepfen(uid)

    res = _befehl(uid, "heute", kanal="sms")

    assert mit.kanaele == [], f"AC-5: Tageslimit erreicht -- kein Versand: {mit!r}"
    assert res.success is False
    text = _antworttext(res)
    assert "Ortsvergleich" in text and UEBERGANGSANTWORT not in text, text


# ═══════════════════════════ AC-6 ════════════════════════════════════════════


def test_ac6_premium_sms_anfragekanal_mit_tarif_trotz_fehlendem_opt_in(mit):
    uid = _nutzer("premium")
    preset = _vergleich(uid, send_premium_sms=False)
    assert "alert_channels" not in preset

    res = _befehl(uid, "heute", kanal="premium_sms")

    assert mit.kanaele == ["premium_sms"], (
        f"AC-6: Anfragekanal Premium-SMS ist nur an den Tarif gebunden: {mit!r}"
    )
    assert res.suppress_email_reply is True


def test_ac6_premium_sms_ohne_tarif_kanal_nicht_erreichbar(mit):
    uid = _nutzer("standard")
    _vergleich(uid, send_premium_sms=False)

    res = _befehl(uid, "heute", kanal="premium_sms")

    assert mit.kanaele == [], mit
    assert res.success is False
    text = _antworttext(res).lower()
    assert "reachable" in text or "erreichbar" in text, (
        f"AC-6: ohne Premium-Tarif kommt der channels_unreachable-Text: {text!r}"
    )
    assert "no channels" not in text and "keine versandkan" not in text, (
        f"AC-6: das ist der no_channels-Text, verlangt ist channels_unreachable: {text!r}"
    )


# ═══════════════════════════ AC-7 ════════════════════════════════════════════

_INDEX = {"email": 0, "sms": 1, "premium_sms": 2, "telegram": 3}

#: (Anfragekanal, Tarif) -> (email, sms, premium_sms, telegram). Am
#: 2026-10-22 VOR der Auslagerung aus dem damals noch eigenstaendigen
#: ``TripReportSchedulerService._resolve_channel_flags(restrict_to_channel=k)``
#: abgelesen und hier eingefroren. Bewusst ein Literal: nach /50 delegiert der
#: Trip an die geteilte Funktion -- ein Vergleich "Trip-Weg == geteilte
#: Funktion" waere dann selbstbezueglich und finge z.B. ein entferntes
#: ``premium_sms_allowed``-Gate nicht mehr.
ERWARTET_FLAGS = {
    ("email", "free"): (True, False, False, False),
    ("email", "standard"): (True, False, False, False),
    ("email", "premium"): (True, False, False, False),
    ("telegram", "free"): (False, False, False, True),
    ("telegram", "standard"): (False, False, False, True),
    ("telegram", "premium"): (False, False, False, True),
    ("sms", "free"): (False, False, False, False),
    ("sms", "standard"): (False, True, False, False),
    ("sms", "premium"): (False, True, False, False),
    ("premium_sms", "free"): (False, False, False, False),
    ("premium_sms", "standard"): (False, False, False, False),
    ("premium_sms", "premium"): (False, False, True, False),
}


@pytest.mark.parametrize("tier", ["free", "standard", "premium"])
@pytest.mark.parametrize("kanal", ["email", "telegram", "sms", "premium_sms"])
def test_ac7_geteilte_aufloesung_liefert_dieselben_flags_wie_der_trip(monkeypatch, kanal, tier):
    """Gleiche Eingaben -> gleiche Flags fuer den Trip-Weg und die geteilte
    Funktion, beide gegen die eingefrorene Vorher-Tabelle (Trip-Verhalten
    unveraendert). Kein Stub der Tarif-Gates: echte ``user.json``."""
    from services.trip_report_scheduler import TripReportSchedulerService

    kette.transport_einrichten(monkeypatch)
    fn = _user_tier_funktion()
    uid = _nutzer(tier)
    aus = TripReportConfig(trip_id="t-ac7", send_email=False, send_sms=False,
                           send_premium_sms=False, send_telegram=False)
    trip_flags = TripReportSchedulerService._resolve_channel_flags(
        TripReportSchedulerService(user_id=uid), aus, uid, restrict_to_channel=kanal,
    )
    erwartet = ERWARTET_FLAGS[(kanal, tier)]
    assert tuple(trip_flags) == erwartet, ("Trip-Verhalten veraendert", kanal, tier, trip_flags)
    assert tuple(fn(kanal, uid)) == erwartet, (kanal, tier, fn(kanal, uid))


@pytest.mark.parametrize("opt_in", [False, True])
@pytest.mark.parametrize("tier", ["free", "standard", "premium"])
@pytest.mark.parametrize("kanal", ["email", "telegram", "sms", "premium_sms"])
def test_ac7_vergleich_bedient_genau_die_flags_der_geteilten_aufloesung(mit, kanal, tier, opt_in):
    """Paritaetsmatrix Kanal x Tarif x Opt-in: der eingeschraenkte
    Vergleichsversand bedient genau den Anfragekanal, wenn die geteilte
    Aufloesung ihn freigibt -- unabhaengig vom Preset-Opt-in."""
    from services.scheduler_dispatch_service import send_compare_preset

    _user_tier_funktion()  # RED-Grund: geteilte Aufloesung fehlt
    uid = _nutzer(tier)
    preset = _vergleich(uid, send_telegram=opt_in, send_sms=opt_in,
                        send_premium_sms=opt_in,
                        **({"alert_channels": []} if opt_in else {}))
    flags = ERWARTET_FLAGS[(kanal, tier)]

    send_compare_preset(uid, preset["id"], restrict_to_channel=kanal)

    erwartet = [kanal] if flags[_INDEX[kanal]] else []
    assert mit.kanaele == erwartet, (kanal, tier, opt_in, flags, mit)


# ═══════════════════════════ AC-8 ════════════════════════════════════════════


def _szenario(code: str, monkeypatch, mit) -> tuple[str, dict]:
    """Baut je Fehlercode einen echten Ausloeser (kein Stub des Ergebnisses)."""
    if code == "no_channels":
        uid = _nutzer("premium", mail_to=None)
        return uid, _vergleich(uid)
    if code == "channels_unreachable":
        from services import notification_service as ns

        class _TelegramGestoert(ns.TelegramOutput):
            def send(self, *a, **kw):
                raise RuntimeError("Telegram-Gateway gestoert")

        monkeypatch.setattr(ns, "TelegramOutput", _TelegramGestoert)
        uid = _nutzer("premium", mail_to=None)
        return uid, _vergleich(uid, send_telegram=True)
    if code == "no_weather":
        import services.comparison_engine as ce_mod

        class _OhneWetter(ce_mod.ComparisonEngine):
            @staticmethod
            def run(*a, **kw):
                raise RuntimeError("Provider-Stoerung")

        monkeypatch.setattr(ce_mod, "ComparisonEngine", _OhneWetter)
        uid = _nutzer("premium")
        return uid, _vergleich(uid, send_telegram=True)
    if code == "invalid_preset":
        uid = _nutzer("premium")
        return uid, _vergleich(uid, send_telegram=True, location_ids=["loc-geloescht"])
    if code == "already_in_progress":
        uid = _nutzer("premium")
        return uid, _vergleich(uid, send_telegram=True)
    raise AssertionError(code)


def _mit_lock(code: str, uid: str, preset: dict, fn):
    from services.send_lock import release_send_lock, try_acquire_send_lock

    if code != "already_in_progress":
        return fn()
    assert try_acquire_send_lock("compare", uid, preset["id"])
    try:
        return fn()
    finally:
        release_send_lock("compare", uid, preset["id"])


_CODES = ["already_in_progress", "no_weather", "no_channels",
          "channels_unreachable", "invalid_preset"]


@pytest.mark.parametrize("code", _CODES)
def test_ac8_report_fehlercode_eigener_text_mit_label_ortsvergleich(monkeypatch, mit, code):
    uid, preset = _szenario(code, monkeypatch, mit)

    res = _mit_lock(code, uid, preset, lambda: _befehl(uid, "report"))

    text = _antworttext(res)
    assert res.success is False, text
    assert mit.kanaele == [], mit
    assert "Ortsvergleich" in text, f"AC-8 {code}: Label 'Ortsvergleich' fehlt: {text!r}"
    assert not re.search(r"\bTrip\b", text), f"AC-8 {code}: Trip-Label im Text: {text!r}"
    assert UEBERGANGSANTWORT not in text and "Web-App" not in text, text


@pytest.mark.parametrize("befehl", ["heute", "morgen"])
@pytest.mark.parametrize("code", ["already_in_progress", "no_weather", "invalid_preset"])
def test_ac8_heute_morgen_fehlercode_mit_label_ortsvergleich(monkeypatch, mit, code, befehl):
    uid, preset = _szenario(code, monkeypatch, mit)

    res = _mit_lock(code, uid, preset, lambda: _befehl(uid, befehl))

    text = _antworttext(res)
    assert res.success is False, text
    assert mit.kanaele == [], mit
    assert "Ortsvergleich" in text, f"AC-8 {befehl}/{code}: Label fehlt: {text!r}"
    assert not re.search(r"\bTrip\b", text), text
    assert UEBERGANGSANTWORT not in text, text


def test_ac8_jeder_fehlercode_hat_einen_eigenen_text(monkeypatch, mit):
    texte: dict[str, str] = {}
    for code in _CODES:
        with monkeypatch.context() as mp:
            uid, preset = _szenario(code, mp, mit)
            res = _mit_lock(code, uid, preset, lambda: _befehl(uid, "report"))
        texte[code] = res.confirmation_body
    assert len(set(texte.values())) == len(_CODES), (
        f"AC-8: Codes muessen unterscheidbar sein: {json.dumps(texte, ensure_ascii=False)}"
    )


def test_ac8_teilausfall_wetter_nennt_die_ortsnamen(monkeypatch, mit):
    """AC-8: kein Fehler, aber fuer EINEN Ort keine Wetterdaten -> Zustellung
    mit den uebrigen Orten, die Antwort nennt den Ort beim NAMEN. Heute meldet
    ``send_compare_preset`` solche Wetter-Teilausfaelle gar nicht zurueck
    (nur nicht aufloesbare Orts-IDs)."""
    import services.comparison_engine as ce_mod

    mit_werten = ce_mod.ComparisonEngine  # die Aufzeichnungs-Subklasse

    class _BozenOhneWetter(mit_werten):
        @staticmethod
        def run(*a, **kw):
            ergebnis = mit_werten.run(*a, **kw)
            for lr in ergebnis.locations:
                if lr.location.id == "loc-bz":
                    lr.error = "Provider-Stoerung"
            return ergebnis

    monkeypatch.setattr(ce_mod, "ComparisonEngine", _BozenOhneWetter)
    uid = _nutzer("premium")
    _vergleich(uid, send_telegram=True)

    res = _befehl(uid, "report")

    text = _antworttext(res)
    assert res.success is True, text
    assert mit.sendungen("email"), mit
    assert "Bozen" in text, f"AC-8: Teilausfall muss den Ort beim Namen nennen: {text!r}"


def test_ac8_teilausfall_geloeschter_ort_wird_genannt(mit):
    """Sekundaerfall: ein nicht mehr aufloesbarer (geloeschter) Ort. Fuer ihn
    gibt es keinen Namen mehr -- ``fehlende_orte`` traegt seine Kennung."""
    uid = _nutzer("premium")
    _vergleich(uid, send_telegram=True,
               location_ids=["loc-ibk", "loc-bz", "loc-geloescht"])

    res = _befehl(uid, "report")

    assert res.success is True, _antworttext(res)
    assert mit.sendungen("email"), mit
    assert "loc-geloescht" in _antworttext(res), (
        f"AC-8: Teilausfall muss die fehlenden Orte nennen: {_antworttext(res)!r}"
    )


# ═══════════════════════════ AC-9 ════════════════════════════════════════════


def test_ac9_gehaltener_lock_kein_zweites_briefing_danach_wieder_frei(mit):
    from services.send_lock import release_send_lock, try_acquire_send_lock

    uid = _nutzer("premium")
    preset = _vergleich(uid, send_telegram=True)

    assert try_acquire_send_lock("compare", uid, preset["id"])
    try:
        res = _befehl(uid, "report")
    finally:
        release_send_lock("compare", uid, preset["id"])

    assert mit.kanaele == [], f"AC-9: kein zweites Briefing bei laufendem Versand: {mit!r}"
    assert res.success is False and UEBERGANGSANTWORT not in res.confirmation_body

    danach = _befehl(uid, "report")
    assert danach.success is True, _antworttext(danach)
    assert len(mit.sendungen("email")) == 1, mit


# ═══════════════════════════ AC-10 ═══════════════════════════════════════════


@pytest.mark.parametrize("befehl", ["report", "heute", "morgen"])
def test_ac10_premium_sms_ohne_namen_rueckfrage_hoechstens_160_ohne_versand(mit, befehl):
    uid = _nutzer("premium")
    _trip(uid, "Korsika")
    _vergleich(uid, send_premium_sms=True, send_telegram=True, alert_channels=[])

    _premium_sms_eingang(uid, befehl)

    antworten = mit.sendungen("premium_sms")
    assert len(antworten) == 1, f"AC-10: genau EINE Rueckfrage, kein Briefing: {mit!r}"
    text = antworten[0]["body"]
    assert len(text) <= 160, f"AC-10: Rueckfrage >160 Zeichen: {text!r}"
    assert "Kors" in text and "Alpe" in text, f"AC-10: Rueckfrage ohne Kandidaten: {text!r}"
    assert mit.sendungen("email") == [] and mit.sendungen("telegram") == [], mit


@pytest.mark.parametrize("befehl", ["report", "heute", "morgen"])
def test_ac10_telegram_ohne_namen_rueckfrage_ohne_versand(monkeypatch, mit, befehl):
    uid = _nutzer("premium")
    _trip(uid, "Korsika")
    preset = _vergleich(uid, send_telegram=True)
    vorher = kette.preset_laden(uid, preset["id"])

    _telegram_eingang(monkeypatch, uid, befehl)

    antworten = _an_eingang(mit)
    assert len(antworten) == 1, f"AC-10: genau EINE Rueckfrage: {mit!r}"
    assert "Korsika" in antworten[0]["body"] and "Alpenblick" in antworten[0]["body"], antworten
    assert _briefing_telegram(mit, uid) == [] and mit.sendungen("email") == [], mit
    assert kette.preset_laden(uid, preset["id"]) == vorher


def test_ac10_telegram_mit_vergleichsnamen_bedient_genau_den_vergleich(monkeypatch, mit):
    uid = _nutzer("premium")
    _trip(uid, "Korsika")
    _vergleich(uid, send_telegram=True)

    _telegram_eingang(monkeypatch, uid, "alpenblick heute")

    assert len(_briefing_telegram(mit, uid)) == 1, mit
    assert mit.sendungen("email") == [], "heute ist kanaltreu"
    alle = "\n".join(s["body"] or "" for s in _an_eingang(mit))
    assert "Korsika" not in alle and UEBERGANGSANTWORT not in alle, alle


def test_ac10_telegram_mit_tripnamen_bedient_nicht_den_vergleich(monkeypatch, mit):
    """Gegenprobe: der benannte Trip wird angesprochen, der Vergleich bleibt
    unberuehrt (keine Rueckfrage, kein Vergleichs-Briefing)."""
    uid = _nutzer("premium")
    _trip(uid, "Korsika")
    _vergleich(uid, send_telegram=True)

    _telegram_eingang(monkeypatch, uid, "korsika report")

    assert not [m for m in mit.sendungen("email") if m["mail_type"] == "compare"], mit
    alle = "\n".join(s["body"] or "" for s in _an_eingang(mit))
    assert "Alpenblick" not in alle, f"keine Rueckfrage bei benanntem Trip: {alle!r}"


# ═══════════════════════════ AC-11 ═══════════════════════════════════════════


@pytest.mark.parametrize("befehl", ["heute", "morgen", "report"])
def test_ac11_nur_ein_vergleich_ohne_namen_wird_bedient(monkeypatch, mit, befehl):
    from services.trip_selection import KEIN_AKTIVES_ZIEL_TEXT

    uid = _nutzer("premium")
    _vergleich(uid, send_telegram=True)

    _telegram_eingang(monkeypatch, uid, befehl)

    alle = "\n".join(s["body"] or "" for s in _an_eingang(mit))
    assert KEIN_AKTIVES_ZIEL_TEXT not in alle and "Kein aktiver Trip" not in alle, alle
    assert len(_briefing_telegram(mit, uid)) == 1, (
        f"AC-11: der einzige Vergleich muss bedient werden: {mit!r}"
    )


def test_ac11_nur_ein_vergleich_premium_sms_heute_wird_bedient(mit):
    from services.trip_selection import KEIN_AKTIVES_ZIEL_TEXT_EN

    uid = _nutzer("premium")
    _vergleich(uid)

    _premium_sms_eingang(uid, "heute")

    sms = mit.sendungen("premium_sms")
    assert len(sms) == 1, f"AC-11: Briefing (keine zweite Bestaetigung): {mit!r}"
    assert KEIN_AKTIVES_ZIEL_TEXT_EN not in sms[0]["body"], sms


@pytest.mark.parametrize("befehl", ["heute", "report"])
def test_ac11_mehrere_vergleiche_ohne_namen_rueckfrage(monkeypatch, mit, befehl):
    uid = _nutzer("premium")
    _vergleich(uid, "Alpenblick", send_telegram=True)
    _vergleich(uid, "Seenblick", send_telegram=True)

    _telegram_eingang(monkeypatch, uid, befehl)

    antworten = _an_eingang(mit)
    assert len(antworten) == 1, mit
    text = antworten[0]["body"]
    assert "Alpenblick" in text and "Seenblick" in text, text
    assert "Kein aktiver Trip" not in text, text
    assert mit.sendungen("email") == [] and _briefing_telegram(mit, uid) == [], mit


@pytest.mark.parametrize("befehl", ["report", "heute", "morgen"])
@pytest.mark.parametrize("kanal", ["telegram", "premium_sms"])
def test_ac11_nur_trip_bleibt_unveraendert_beim_trip(befehl, kanal):
    """Regressionswaechter (gruen erwartet): ohne Vergleich adressiert der
    Befehl ohne Namen weiterhin den aktiven Trip."""
    from services.trip_selection import resolve_command_target

    uid = kette.nutzer_anlegen("premium")
    trip = _trip(uid, "Korsika")
    erg = resolve_command_target(befehl, [trip], [], datetime.now(tz=timezone.utc),
                                 channel=kanal)
    assert erg.kind == "route" and erg.target.id == trip.id, erg


@pytest.mark.parametrize("befehl", ["glance", "gewitter"])
def test_ac11_query_befehle_bleiben_trip_only(monkeypatch, mit, befehl):
    """Regressionswaechter (gruen erwartet): glance/gewitter am einzigen
    Vergleich bleiben beim 'kein aktiver Trip'-Hinweis, kein Versand."""
    from services.trip_selection import KEIN_AKTIVES_ZIEL_TEXT

    uid = _nutzer("premium")
    _vergleich(uid, send_telegram=True)

    _telegram_eingang(monkeypatch, uid, befehl)

    antworten = _an_eingang(mit)
    assert len(antworten) == 1 and antworten[0]["body"] == KEIN_AKTIVES_ZIEL_TEXT, antworten
    assert mit.sendungen("email") == [] and _briefing_telegram(mit, uid) == [], mit


def test_ac11_hilfe_am_vergleich_nennt_report_heute_morgen(mit):
    uid = _nutzer("premium")
    _vergleich(uid)

    deutsch = _befehl(uid, "hilfe", kanal="telegram").confirmation_body
    englisch = _befehl(uid, "hilfe", kanal="premium_sms").confirmation_body

    for wort in ("REPORT", "HEUTE", "MORGEN"):
        assert wort in deutsch, f"AC-11: Vergleichs-Hilfe ohne {wort}: {deutsch!r}"
    for wort in ("REPORT", "TODAY", "TOMORROW"):
        assert wort in englisch, f"AC-11: Vergleichs-Kurzhilfe ohne {wort}: {englisch!r}"


# ═══════════════════════════ AC-12 ═══════════════════════════════════════════


def test_ac12_zwei_nutzer_b_bleibt_unberuehrt(mit):
    a = _nutzer("premium")
    b = _nutzer("premium")
    _vergleich(a, "Alpenblick", send_telegram=True)
    _vergleich(b, "Bergsicht", send_telegram=True)
    vorher_b = _stand(b)

    res_eigen = _befehl(a, "report", name="Alpenblick")
    _befehl(a, "heute", name="Alpenblick")
    _befehl(a, "report", name="Bergsicht")
    _befehl(a, "heute", name="Bergsicht")

    assert res_eigen.success is True, _antworttext(res_eigen)
    empfaenger = {str(s["empfaenger"]) for k in mit.kanaele for s in mit.sendungen(k)}
    assert empfaenger, f"AC-12: A muss sein Briefing bekommen: {mit!r}"
    assert empfaenger <= {f"{a}@example.invalid", f"chat-{a}"}, (
        f"AC-12: Zustellung ausserhalb von A: {empfaenger}"
    )
    assert _stand(b) == vorher_b, "AC-12: Bs Versand/Status/briefing_log veraendert"


# ═══════════════════════════ AC-14 ═══════════════════════════════════════════


@pytest.mark.parametrize("befehl", ["report", "heute", "morgen"])
def test_ac14_telegram_ladehinweis_vor_dem_vergleichs_briefing(monkeypatch, mit, befehl):
    uid = _nutzer("premium")
    _vergleich(uid, send_telegram=True)

    _telegram_eingang(monkeypatch, uid, befehl)

    reihenfolge = mit.sendungen("telegram")
    lade = [i for i, s in enumerate(reihenfolge)
            if str(s["empfaenger"]) == EINGANG_CHAT and LADEHINWEIS in (s["body"] or "")]
    briefing = [i for i, s in enumerate(reihenfolge) if str(s["empfaenger"]) == f"chat-{uid}"]
    assert lade, f"AC-14: kein Ladehinweis am Vergleich: {reihenfolge!r}"
    assert briefing and lade[0] < briefing[0], (
        f"AC-14: Ladehinweis muss VOR dem Briefing kommen: {reihenfolge!r}"
    )


# ═══════════════════════════ AC-15 ═══════════════════════════════════════════


def test_ac15_anfrage_nimmt_das_regulaere_briefing_nicht_weg(mit, anker):
    from services.compare_slot_scheduler import presets_due_for_hour

    uid = _nutzer("premium")
    preset = _vergleich(uid, send_telegram=True)

    res = _befehl(uid, "report")

    assert res.success is True, _antworttext(res)
    eintraege = [e for e in _log(uid) if e.get("entity_type") == "compare"]
    assert len(eintraege) == 1 and eintraege[0]["on_demand"] is True, (
        f"AC-15: das PRODUKT muss einen on_demand-Eintrag schreiben: {eintraege}"
    )
    assert anker == [], f"AC-15: Δ-Anker angefasst: {anker}"
    assert not (get_data_dir(uid) / "first_briefing.json").exists(), (
        "AC-15: Erst-Briefing-Markierung durch eine Anfrage gesetzt"
    )
    wien = ZoneInfo("Europe/Vienna")
    morgens = datetime.now(wien).replace(hour=7, minute=5, second=0, microsecond=0)
    faellig = presets_due_for_hour(
        [kette.preset_laden(uid, preset["id"])],
        {o.id: o for o in kette.alle_orte(uid)},
        morgens.astimezone(timezone.utc),
    )
    assert [d.preset["id"] for d in faellig] == [preset["id"]], (
        f"AC-15: das regulaere Morgen-Briefing muss weiter faellig sein: {faellig}"
    )
