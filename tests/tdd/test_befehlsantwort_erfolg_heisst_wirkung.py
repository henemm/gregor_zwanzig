"""TDD RED -- Issue #1405 Scheibe S4a: Befehlsantwort "Erfolg heisst Wirkung".

SPEC: docs/specs/modules/feat_1405_s4a_befehlsantwort_erfolg_wirkung.md
CONTEXT: docs/context/feat-1405-s4a-command-result.md

Misst an der ANKOMMENDEN Antwort (nicht am Rueckgabewert von ``process()``
allein): die Befehle laufen durch die ECHTEN Eingaenge -- Mail-Leser
(``_process_single``), SMS-Leser (Premium-SMS-Journal, ``poll_and_process``)
und Telegram (``_process_update``) -- und die Pruefung liest, was der
Recorder an Telegram/seven.io/SMTP wirklich versendet hat. Fundament:
``tests/tdd/_befehl_e2e_fixtures.py`` (#2417), Sperren-Helfer
``tests/tdd/_schreibsperre_helfer.py`` (#2158), Nowcast-Fake
``tests/helpers/strecke_fixtures.py`` (#2051).

Mock-frei: echte Dateisperre eines Fremdprozesses (AC-5/8/9), echte Dateien
(umbenannte Trip-Datei, Verzeichnis statt Befehls-Log, beschaedigter
Snapshot), echte aufzeichnende ``RadarNowcastService``-Unterklasse als
Fake-Quelle. Kein ``Mock()``/``patch()`` der Antwort oder des Prueflings.

Zwei Eingaenge im Spec ("SMS-Leser: ``sms`` UND ``premium_sms``"): es gibt
im Produkt KEINEN Leser, der ``channel="sms"`` erzeugt -- der SMS-Leser
(``inbound_sms_reader.py``) setzt ausschliesslich ``premium_sms``. Der
Kanal ``sms`` wird deshalb nur auf ``process()``-Ebene ueber
``_KURZFORM_KANAELE`` (Sprache/Laenge) mitgemessen, nicht ueber einen Eingang.

Uhrzeit: keine der gemessenen Befehle ist ``heute``/``morgen`` (Briefing-
Sperre #1594 greift dort); das Fundament baut Etappen und Snapshot auf den
Ortstag "jetzt" (#2435) -- kein weiterer Pin noetig.

AC-ZUORDNUNG (Test -> AC):
  AC-1/AC-2/AC-3/AC-4   test_ac1_*, test_ac2_*, test_ac3_*, test_ac4_*
  AC-5                  test_ac5_*   (Charakterisierung: heute schon gruen, bewacht
                                       die Reparatur; success-Teil per process())
  AC-6                  test_ac6_*   (dto.)
  AC-7                  test_ac7_*
  AC-8 / AC-9           test_ac8_*, test_ac9_*
  AC-10 / AC-11         test_ac10_*, test_ac11_*
  AC-12 / AC-13 / AC-14 test_ac12_*, test_ac13_*, test_ac14_*
  AC-15                 test_ac15_*  (Charakterisierung, heute gruen)
  AC-16..AC-19          GREEN-Phase: Ratsche (tests/test_success_status_guard.py)
                        bzw. Adversary-Mutationsgegenprobe -- hier KEIN Test.
  AC-20                 diese Datei (vier Eingaenge, Antwort geht raus)
  AC-21                 bewusste Erwartungsaenderungen in Alt-Tests (siehe
                        Kommentare ``# #1405 S4a AC-21``)

AC-1/AC-4-FEHLERQUELLEN (muessen AUCH NACH der GREEN-Reparatur noch aus dem
Handler herauslaufen -- sonst waere die Mutation "zentralen Fang in
``process()`` entfernen" unbeobachtbar):

  (a) ``snapshot_kaputt``: der gespeicherte Wetter-Snapshot des Trips hat ein
      ``snapshot_at`` ohne Zeitstempel-String (Zahl). ``WeatherSnapshotService.
      load`` faengt nur ``JSONDecodeError/ValueError/KeyError/OSError`` --
      ``datetime.fromisoformat(123)`` wirft ``TypeError`` und laeuft durch
      ``WeatherExtractor.timeline`` und ``_handle_query`` (Befehl ``glance``)
      bis aus ``process()`` heraus. Die Trip-Datei ist heil und wird geladen.
  (b) ``befehlslog_kaputt``: ``command_log.json`` ist gueltiges JSON, aber ein
      Objekt statt einer Liste. ``_is_already_applied`` (Befehl ``ruhetag``)
      iteriert ueber dessen Schluessel und ruft ``.get`` auf einem ``str`` auf
      -> ``AttributeError`` VOR dem Speichern. Der AC-7-Schutz der Spec gilt
      nur fuer das Schreiben NACH dem erfolgreichen Speichern; ``_speichere``
      /``_SpeicherFehler`` fangen nur LockTimeout/LoaderError -- beides sind
      keine lokalen Fange fuer diese Quelle.
  Beide Quellen sind unabhaengig von F2 (Nowcast/Backfill/LoaderError beim
  Speichern), die GREEN lokal faengt.
"""
from __future__ import annotations

import email as email_lib
import json
import logging
import re
import shutil
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.loader import dump_trip_to_dict, get_data_dir, get_snapshots_dir
from services.trip_command_processor import (
    CommandResult,
    InboundMessage,
    TripCommandProcessor,
)
from tests.helpers.strecke_fixtures import (
    future_two_point_trip,
    nass,
    recording_radar_service_type,
    trocken,
)
from tests.tdd._befehl_e2e_fixtures import (
    BefehlNutzer,
    _preset_file,
    _read,
    basis_settings,
    install_transport_fakes,
    lege_lage_an,
    sende_email,
    sende_premium_sms,
    sende_telegram_text,
    user_ids,
)
from tests.tdd._schreibsperre_helfer import (
    briefings_dir,
    frist_verkuerzen,
    fremde_sperre,
    lock_pfad,
    trip_datei,
)

__all__ = ["user_ids"]  # pytest muss die importierte Fixture im Modul finden

KANAELE = ("email", "premium_sms", "telegram")
MAX_SMS = 160
_LADEHINWEIS = ("geladen", "loading")  # Telegram: "Wetter wird geladen..."


# ---------------------------------------------------------------------------
# Treiber: echter Eingang -> tatsaechlich versendete Antwort
# ---------------------------------------------------------------------------

@dataclass
class Gesendet:
    """Alles, was DIESER eine Befehl an den Nutzer versendet hat."""

    betreffe: list = field(default_factory=list)
    texte: list = field(default_factory=list)  # Mail: Body; Telegram/SMS: Nachricht

    def inhaltlich(self) -> list:
        """Texte ohne den Telegram-Ladehinweis (``Wetter wird geladen``)."""
        return [t for t in self.texte if not any(w in t.lower() for w in _LADEHINWEIS)]

    @property
    def letzter(self) -> str:
        inh = self.inhaltlich()
        return inh[-1] if inh else ""

    @property
    def alles(self) -> str:
        return "\n".join(self.betreffe + self.texte)


def _mail_teile(raw: str) -> tuple[str, str]:
    msg = email_lib.message_from_string(raw)
    plain = [
        p.get_payload(decode=True).decode(p.get_content_charset() or "utf-8", errors="replace")
        for p in msg.walk() if p.get_content_type() == "text/plain"
    ]
    betreff = email_lib.header.make_header(email_lib.header.decode_header(msg["Subject"] or ""))
    return str(betreff), "\n".join(plain)


def sende(kanal: str, nutzer: BefehlNutzer, settings, recorder, befehl: str) -> Gesendet:
    """Schickt ``befehl`` durch den echten Eingang ``kanal`` und liefert, was
    dabei versendet wurde.

    Der Telegram-Eingang (``_process_update``) wird wie im Produkt
    (``api/routers/webhook.py:89-92``) von einem aeusseren ``try/except``
    umschlossen -- Mail-Leser und SMS-Leser fangen selbst. Ein Programmfehler
    im Handler bleibt damit als FEHLENDE Antwort sichtbar (Assertion), nicht
    als Testabsturz.
    """
    vor = (len(recorder.emails), len(recorder.premium_sms_out), len(recorder.telegram))
    try:
        if kanal == "email":
            ziel = None if nutzer.trip else (nutzer.presets[0]["name"] if nutzer.presets else None)
            sende_email(settings, nutzer, befehl, trip_name=ziel)
        elif kanal == "premium_sms":
            sende_premium_sms(settings, recorder, nutzer, befehl)
        elif kanal == "telegram":
            sende_telegram_text(settings, nutzer, befehl)
        else:  # pragma: no cover
            raise ValueError(kanal)
    except Exception:  # wie webhook.py: Programmfehler -> Log, keine Antwort
        logging.getLogger(__name__).exception("Eingang %s warf (wie im Webhook gefangen)", kanal)
    recorder.pruefe_keine_unbekannten_aufrufe()  # Fundament-Vertrag (#2417)
    erg = Gesendet()
    for e in recorder.emails[vor[0]:]:
        b, t = _mail_teile(e["raw"])
        erg.betreffe.append(b)
        erg.texte.append(t)
    erg.texte += [e["text"] for e in recorder.premium_sms_out[vor[1]:]]
    erg.texte += [
        e["payload"].get("text", "") for e in recorder.telegram[vor[2]:]
        if e["methode"] in ("sendMessage", "editMessageText")
        and str(e["payload"].get("chat_id")) == str(nutzer.telegram_chat_id)
    ]
    return erg


def _umgebung(monkeypatch, user_ids, lage="L2", *, strecke_km: float | None = None):
    """Recorder, Nutzer, Settings. ``strecke_km``: statt der Fixture-Etappen
    traegt der Nutzer EINEN vermessenen Trip (``future_two_point_trip``,
    Etappe vollstaendig in der Zukunft -> ``strecke`` hat tageszeit-unabhaengig
    eine aktive Vorschau-Etappe mit exakt ``strecke_km`` Reststrecke). Ohne
    Vermessung antwortet ``strecke`` schon VOR jedem Nowcast-Abruf
    "Kilometrierung nicht verfuegbar"."""
    recorder = install_transport_fakes(monkeypatch)
    if strecke_km is None:
        nutzer = lege_lage_an(user_ids, lage)
    else:
        nutzer = lege_lage_an(user_ids, "L1")
        trip = future_two_point_trip(f"gz2417-{uuid.uuid4().hex[:8]}", strecke_km)
        # Direkt als Datei, NICHT ueber ``save_trip``: dessen Compute-on-Save
        # (Naismith) wuerde die konstruierten Ankunftszeiten ueberschreiben, auf
        # denen die Vorschau-Geometrie beruht.
        datei = trip_datei(nutzer.user_id, trip.id)
        datei.parent.mkdir(parents=True, exist_ok=True)
        datei.write_text(json.dumps(dict(dump_trip_to_dict(trip), kind="route")),
                         encoding="utf-8")
        nutzer.trip = trip
    return recorder, nutzer, basis_settings()


def process_direkt(nutzer: BefehlNutzer, befehl: str, *, kanal: str = "telegram",
                   englisch: bool = False, vergleich: bool = False):
    """``process()`` direkt. Wirft ``process()`` heraus, kommt ``(None, exc)``
    zurueck -- der Test scheitert dann an der Assertion auf das Ergebnis
    (RED-Grund "Exception statt Fehlerantwort"), nicht als Absturz."""
    kwargs = {}
    if vergleich:
        preset = nutzer.presets[0]
        name, kwargs = preset["name"], dict(
            resolved_kind="vergleich", resolved_preset_id=preset["id"])
    else:
        name = nutzer.trip.name
    msg = InboundMessage(
        trip_name=name, body=befehl, sender="test", channel=kanal,
        received_at=datetime.now(timezone.utc), user_id=nutzer.user_id,
        englisch=englisch, **kwargs,
    )
    try:
        return TripCommandProcessor().process(msg), None
    except Exception as exc:  # noqa: BLE001
        return None, exc


def _ergebnis(res, exc) -> CommandResult:
    assert exc is None, (
        f"process() wirft {type(exc).__name__}: {exc} statt eine Antwort zu liefern"
    )
    assert res is not None
    return res


def _vol(r: CommandResult) -> str:
    return f"{r.confirmation_subject}\n{r.confirmation_body}"


def _ohne_ladehinweis(g: Gesendet, kanal: str):
    assert g.inhaltlich(), (
        f"Kanal {kanal}: es ging KEINE Antwort raus (Ruecklauf: {g.alles!r})"
    )


# ---------------------------------------------------------------------------
# Fehlerquellen (AC-1/AC-4) -- Begruendung im Moduldocstring
# ---------------------------------------------------------------------------

def _zerstoere_snapshot(nutzer: BefehlNutzer) -> None:
    snap = get_snapshots_dir(nutzer.user_id) / f"{nutzer.trip.id}.json"
    daten = json.loads(snap.read_text(encoding="utf-8"))
    daten["snapshot_at"] = 123  # kein Zeitstempel -> TypeError in fromisoformat
    snap.write_text(json.dumps(daten), encoding="utf-8")


def _zerstoere_befehlslog(nutzer: BefehlNutzer) -> None:
    (get_data_dir(nutzer.user_id) / "command_log.json").write_text(
        json.dumps({"kein": "eine liste"}), encoding="utf-8")


FEHLERQUELLEN = {
    "snapshot_kaputt": ("glance", _zerstoere_snapshot),
    "befehlslog_kaputt": ("ruhetag", _zerstoere_befehlslog),
}


# ---------------------------------------------------------------------------
# AC-1 / AC-2 / AC-3: zentraler Fang -- der Nutzer bekommt IMMER eine Antwort
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("quelle", sorted(FEHLERQUELLEN))
@pytest.mark.parametrize("kanal", KANAELE)
def test_ac1_programmfehler_bringt_fehlerantwort_je_kanal(monkeypatch, user_ids, kanal, quelle):
    """AC-1/AC-2/AC-3 (je Kanal): ein unerwarteter Programmfehler im Handler
    darf nicht zu Schweigen fuehren -- es geht eine Antwort raus, <=160
    Zeichen, die ``STATUS`` nennt und nicht pauschal "erneut senden" rat."""
    recorder, nutzer, settings = _umgebung(monkeypatch, user_ids)
    befehl, zerstoere = FEHLERQUELLEN[quelle]
    zerstoere(nutzer)

    g = sende(kanal, nutzer, settings, recorder, befehl)

    _ohne_ladehinweis(g, kanal)
    text = g.letzter
    assert len(text) <= MAX_SMS, f"AC-2: {len(text)} Zeichen > 160: {text!r}"
    pos = text.find("STATUS")
    assert pos >= 0, f"AC-3: die Fehlerantwort nennt STATUS nicht: {text!r}"
    for m in re.finditer(r"erneut senden|send (it )?again", text, re.IGNORECASE):
        assert m.start() > pos, (
            f"AC-3: 'erneut senden' darf nicht vor/statt STATUS stehen: {text!r}")
    assert not re.search(r"Traceback|TypeError|AttributeError", g.alles), (
        f"AC-4: kein technischer Hergang an den Nutzer: {g.alles!r}")


@pytest.mark.parametrize("quelle", sorted(FEHLERQUELLEN))
def test_ac1_trip_bleibt_bei_programmfehler_unveraendert(monkeypatch, user_ids, quelle):
    """AC-1: der Fang aendert keinen Trip-Bestand (Sicherheitsnetz, kein Schreiben)."""
    recorder, nutzer, settings = _umgebung(monkeypatch, user_ids)
    befehl, zerstoere = FEHLERQUELLEN[quelle]
    zerstoere(nutzer)
    vorher = trip_datei(nutzer.user_id, nutzer.trip.id).read_bytes()

    g = sende("telegram", nutzer, settings, recorder, befehl)

    assert g.inhaltlich(), "es ging keine Antwort raus"
    assert trip_datei(nutzer.user_id, nutzer.trip.id).read_bytes() == vorher


@pytest.mark.parametrize("quelle", sorted(FEHLERQUELLEN))
@pytest.mark.parametrize("kanal,englisch", [
    ("email", False), ("telegram", False), ("telegram", True),
    ("premium_sms", True), ("sms", True),
])
def test_ac1_ac2_ac3_process_success_false_sprache_laenge(
        monkeypatch, user_ids, quelle, kanal, englisch):
    """AC-1 (success=False, suppress_email_reply=False), AC-2 (<=160, DE/EN),
    AC-3 (STATUS). ``sms`` nur hier, siehe Moduldocstring."""
    recorder, nutzer, _ = _umgebung(monkeypatch, user_ids)
    befehl, zerstoere = FEHLERQUELLEN[quelle]
    zerstoere(nutzer)

    res, exc = process_direkt(nutzer, befehl, kanal=kanal, englisch=englisch)

    r = _ergebnis(res, exc)
    assert r.success is False
    assert r.suppress_email_reply is False
    assert len(r.confirmation_body) <= MAX_SMS, r.confirmation_body
    assert "STATUS" in r.confirmation_body, r.confirmation_body
    assert "Traceback" not in _vol(r)
    de_marker = re.search(r"\b(Befehl|bitte|nicht|pr.fen|ausgef.hrt)\b", r.confirmation_body, re.I)
    if englisch or kanal in ("premium_sms", "sms"):
        assert not de_marker, f"AC-2: englische Antwort erwartet: {r.confirmation_body!r}"
    else:
        assert de_marker, f"AC-2: deutsche Antwort erwartet: {r.confirmation_body!r}"


@pytest.mark.parametrize("quelle", sorted(FEHLERQUELLEN))
def test_ac4_traceback_bleibt_im_protokoll(monkeypatch, user_ids, caplog, quelle):
    """AC-4: der Programmfehler steht mit Traceback im Log, nicht in der Antwort."""
    recorder, nutzer, _ = _umgebung(monkeypatch, user_ids)
    befehl, zerstoere = FEHLERQUELLEN[quelle]
    zerstoere(nutzer)

    with caplog.at_level(logging.ERROR):
        res, exc = process_direkt(nutzer, befehl)
    r = _ergebnis(res, exc)

    mit_traceback = [
        rec for rec in caplog.records
        if rec.levelno >= logging.ERROR and rec.exc_info
        and rec.exc_info[0] in (TypeError, AttributeError)
    ]
    assert mit_traceback, (
        f"AC-4: kein Fehler-Log mit Traceback; Records: "
        f"{[(x.levelname, x.getMessage()) for x in caplog.records]}")
    assert "Traceback" not in _vol(r)
    assert "TypeError" not in _vol(r) and "AttributeError" not in _vol(r)


# ---------------------------------------------------------------------------
# AC-5 / AC-6 / AC-7: Klasse A (Speichern)
# ---------------------------------------------------------------------------

#: (Befehl, Woerter, die eine Erfolgsmeldung verraten -- klein geschrieben)
KLASSE_A_BEFEHLE = {
    "pause": ("pause 2d", ("pausiert", "paused until")),
    "skip": ("skip", ("übersprungen", "skipped")),
    "ruhetag": ("ruhetag", ("ruhetag bestätigt", "ruhetag eingetragen", "rest day")),
    "abbruch": ("stop", ("trip beendet", "heimreise", "turned off", "safe trip")),
    "weiter": ("weiter", ("reaktiviert", "restarted", "enjoy the trip")),
}
_ERNEUT = ("erneut", "again")
#: Sperr-spezifischer Wortlaut der LOKALEN Behandlung (``_speichere`` /
#: ``_compare_erneut_senden``). Die zentrale Fehlerantwort (AC-1) enthaelt
#: ebenfalls "erneut", aber nie diesen Satz und stets "STATUS" -- ohne diese
#: Schaerfung bliebe die Mutation "lokale Sperrbehandlung entfernen" unsichtbar,
#: weil der zentrale Fang sie als Fehlerantwort tarnen wuerde.
_SPERRE = ("gerade geaendert", "being changed right now")


def _sperrtext(text: str) -> None:
    kl = text.lower()
    assert any(w in kl for w in _SPERRE), f"kein sperr-spezifischer Wortlaut: {text!r}"
    assert "STATUS" not in text, f"zentrale Fehlerantwort statt lokaler Sperrmeldung: {text!r}"


#: AC-5/AC-8: die Antwort sagt explizit, dass der Befehl NICHT ausgefuehrt
#: wurde -- der Nutzer soll es nicht aus "wird gerade geaendert" erschliessen.
_NICHT_AUSGEFUEHRT = {False: "nicht ausgefuehrt", True: "not executed"}


def _englisch_am_kanal(kanal: str) -> bool:
    """Premium-SMS/SMS antworten stets englisch (siehe AC-2-Tests oben)."""
    return kanal in ("premium_sms", "sms")


def _meldet_nicht_ausgefuehrt(text: str, englisch: bool) -> None:
    erwartet = _NICHT_AUSGEFUEHRT[englisch]
    assert erwartet in text.lower(), (
        f"AC-5/AC-8: {erwartet!r} fehlt in der Antwort: {text!r}")


def _keine_erfolgsbehauptung(text: str, woerter) -> None:
    kl = text.lower()
    for w in woerter:
        assert w not in kl, f"Erfolgsbehauptung {w!r} trotz Nicht-Ausfuehrung: {text!r}"


@pytest.mark.parametrize("name", sorted(KLASSE_A_BEFEHLE))
@pytest.mark.parametrize("kanal", KANAELE)
def test_ac5_gesperrter_trip_meldet_nicht_ausgefuehrt(monkeypatch, user_ids, kanal, name):
    """AC-5: echte Sperre (Fremdprozess haelt flock auf ``<id>.json.lock``) ->
    "bitte erneut senden", keine Erfolgsbehauptung, Trip-Datei unveraendert."""
    befehl, erfolg = KLASSE_A_BEFEHLE[name]
    recorder, nutzer, settings = _umgebung(monkeypatch, user_ids)
    frist_verkuerzen(monkeypatch, 0.3)
    datei = trip_datei(nutzer.user_id, nutzer.trip.id)
    vorher = datei.read_bytes()

    with fremde_sperre(lock_pfad(nutzer.user_id, nutzer.trip.id)):
        g = sende(kanal, nutzer, settings, recorder, befehl)

    _ohne_ladehinweis(g, kanal)
    text = g.alles
    assert any(w in text.lower() for w in _ERNEUT), f"kein Wiederholungshinweis: {text!r}"
    _sperrtext(text)
    _meldet_nicht_ausgefuehrt(text, _englisch_am_kanal(kanal))
    _keine_erfolgsbehauptung(text, erfolg)
    assert datei.read_bytes() == vorher


@pytest.mark.parametrize("englisch", [False, True])
@pytest.mark.parametrize("name", sorted(KLASSE_A_BEFEHLE))
def test_ac5_gesperrter_trip_process_success_false(monkeypatch, user_ids, name, englisch):
    """AC-5: ``success=False`` bei gesperrtem Trip; Text sagt "nicht
    ausgefuehrt" bzw. "not executed"."""
    befehl, _ = KLASSE_A_BEFEHLE[name]
    recorder, nutzer, _ = _umgebung(monkeypatch, user_ids)
    frist_verkuerzen(monkeypatch, 0.3)

    with fremde_sperre(lock_pfad(nutzer.user_id, nutzer.trip.id)):
        res, exc = process_direkt(nutzer, befehl, englisch=englisch)

    r = _ergebnis(res, exc)
    assert r.success is False
    _sperrtext(_vol(r))
    _meldet_nicht_ausgefuehrt(r.confirmation_body, englisch)
    assert len(r.confirmation_body) <= MAX_SMS, r.confirmation_body


def _datei_unter_falschem_namen(nutzer: BefehlNutzer) -> Path:
    """Die Trip-Datei liegt unter anderem Namen als ``<trip.id>.json``: der
    Trip wird geladen (Glob ueber ``briefings/*.json``), ``update_trip`` sucht
    aber ``<id>.json`` -> ``TripNotFound`` (ein ``LoaderError``). Echter
    Dateizustand, root-fest, kein ``patch()``."""
    quelle = trip_datei(nutzer.user_id, nutzer.trip.id)
    ziel = briefings_dir(nutzer.user_id) / "umbenannt.json"
    shutil.move(quelle, ziel)
    return ziel


@pytest.mark.parametrize("name", sorted(KLASSE_A_BEFEHLE))
@pytest.mark.parametrize("kanal", KANAELE)
def test_ac6_loaderfehler_meldet_nicht_gespeichert(monkeypatch, user_ids, kanal, name):
    """AC-6: ``LoaderError`` beim Speichern -> "Nicht gespeichert", keine
    Erfolgsmeldung."""
    befehl, erfolg = KLASSE_A_BEFEHLE[name]
    recorder, nutzer, settings = _umgebung(monkeypatch, user_ids)
    datei = _datei_unter_falschem_namen(nutzer)
    vorher = datei.read_bytes()

    g = sende(kanal, nutzer, settings, recorder, befehl)

    _ohne_ladehinweis(g, kanal)
    text = g.alles
    assert re.search(r"nicht gespeichert|not saved|could not be saved", text, re.IGNORECASE), (
        f"AC-6: 'Nicht gespeichert' fehlt: {text!r}")
    if kanal == "email":
        # F002: auch der BETREFF der tatsaechlich versendeten Mail (der Body
        # traegt "gespeichert werden" ohnehin).
        assert any(re.search(r"nicht gespeichert|not saved", b, re.IGNORECASE)
                   for b in g.betreffe), f"AC-6: Betreff: {g.betreffe!r}"
    _keine_erfolgsbehauptung(text, erfolg)
    assert datei.read_bytes() == vorher
    assert not trip_datei(nutzer.user_id, nutzer.trip.id).exists()


@pytest.mark.parametrize("name", sorted(KLASSE_A_BEFEHLE))
def test_ac6_loaderfehler_process_success_false(monkeypatch, user_ids, name):
    befehl, _ = KLASSE_A_BEFEHLE[name]
    recorder, nutzer, _ = _umgebung(monkeypatch, user_ids)
    _datei_unter_falschem_namen(nutzer)

    res, exc = process_direkt(nutzer, befehl)

    assert _ergebnis(res, exc).success is False


def _befehlslog_als_verzeichnis(nutzer: BefehlNutzer) -> None:
    """Schreiben des Befehls-Logs scheitert NACH dem Speichern: an der Stelle
    von ``command_log.json`` liegt ein Verzeichnis (``open(..., 'w')`` ->
    ``IsADirectoryError``). Wirkt auch unter root; das Lesen faengt
    ``_load_command_log`` (OSError) selbst -> der Fehler entsteht erst beim
    Anhaengen."""
    (get_data_dir(nutzer.user_id) / "command_log.json").mkdir()


def _etappendaten(user_id: str, trip_id: str) -> list:
    return [s["date"] for s in json.loads(
        trip_datei(user_id, trip_id).read_text(encoding="utf-8"))["stages"]]


@pytest.mark.parametrize("kanal", KANAELE)
def test_ac7_nebenschaden_nach_speichern_aendert_antwort_nicht(monkeypatch, user_ids, kanal):
    """AC-7: Ruhetag ist gespeichert, erst das Befehls-Log scheitert -> die
    Antwort meldet den Ruhetag als gesetzt (kein Fehler)."""
    recorder, nutzer, settings = _umgebung(monkeypatch, user_ids)
    _befehlslog_als_verzeichnis(nutzer)
    vorher = _etappendaten(nutzer.user_id, nutzer.trip.id)

    g = sende(kanal, nutzer, settings, recorder, "ruhetag")

    _ohne_ladehinweis(g, kanal)
    assert _etappendaten(nutzer.user_id, nutzer.trip.id) != vorher, "Ruhetag nicht gespeichert"
    assert re.search(r"ruhetag eingetragen|rest day added", g.alles, re.IGNORECASE), (
        f"AC-7: Antwort meldet den Ruhetag nicht als gesetzt: {g.alles!r}")
    assert "STATUS" not in g.alles, f"AC-7: kein Fehlerhinweis erlaubt: {g.alles!r}"


def test_ac7_warnung_im_protokoll(monkeypatch, user_ids, caplog):
    """AC-7: im Protokoll steht eine Warnung ueber den Nebenschaden; success=True."""
    recorder, nutzer, _ = _umgebung(monkeypatch, user_ids)
    _befehlslog_als_verzeichnis(nutzer)

    with caplog.at_level(logging.WARNING):
        res, exc = process_direkt(nutzer, "ruhetag")

    r = _ergebnis(res, exc)
    assert r.success is True
    warn = [x for x in caplog.records
            if x.levelno == logging.WARNING and x.name.endswith("trip_command_processor")]
    assert warn, (
        f"AC-7: keine Warnung des Prozessors; Records: "
        f"{[(x.name, x.levelname, x.getMessage()) for x in caplog.records]}")


# ---------------------------------------------------------------------------
# AC-8 / AC-9: Ortsvergleich pausieren / fortsetzen
# ---------------------------------------------------------------------------

def _preset_pausiert(nutzer: BefehlNutzer) -> None:
    pid = nutzer.presets[0]["id"]
    d = _read(nutzer.user_id, pid)
    d.update(schedule="manual", previous_schedule="daily", paused_at="2026-10-01T08:00:00Z")
    _preset_file(nutzer.user_id, pid).write_text(json.dumps(d), encoding="utf-8")


def _preset_sperre(nutzer: BefehlNutzer):
    return fremde_sperre(lock_pfad(nutzer.user_id, nutzer.presets[0]["id"]))


@pytest.mark.parametrize("kanal", KANAELE)
def test_ac8_gesperrter_vergleich_meldet_nicht_ausgefuehrt(monkeypatch, user_ids, kanal):
    """AC-8: Vergleich gesperrt -> "bitte erneut senden", NICHT "pausiert"."""
    recorder, nutzer, settings = _umgebung(monkeypatch, user_ids, "L4")
    frist_verkuerzen(monkeypatch, 0.3)
    datei = _preset_file(nutzer.user_id, nutzer.presets[0]["id"])
    vorher = datei.read_bytes()

    with _preset_sperre(nutzer):
        g = sende(kanal, nutzer, settings, recorder, "pause")

    _ohne_ladehinweis(g, kanal)
    assert any(w in g.alles.lower() for w in _ERNEUT), g.alles
    _sperrtext(g.alles)
    _meldet_nicht_ausgefuehrt(g.alles, _englisch_am_kanal(kanal))
    _keine_erfolgsbehauptung(g.alles, ("pausiert unbefristet", "paused until", "ortsvergleich pausiert"))
    assert datei.read_bytes() == vorher


@pytest.mark.parametrize("englisch", [False, True])
def test_ac8_gesperrter_vergleich_process_success_false(monkeypatch, user_ids, englisch):
    recorder, nutzer, _ = _umgebung(monkeypatch, user_ids, "L4")
    frist_verkuerzen(monkeypatch, 0.3)

    with _preset_sperre(nutzer):
        res, exc = process_direkt(nutzer, "pause", englisch=englisch, vergleich=True)

    r = _ergebnis(res, exc)
    assert r.success is False
    _sperrtext(_vol(r))
    _meldet_nicht_ausgefuehrt(r.confirmation_body, englisch)
    assert len(r.confirmation_body) <= MAX_SMS, r.confirmation_body


@pytest.mark.parametrize("kanal", KANAELE)
def test_ac9_weiter_auf_nicht_pausiertem_vergleich(monkeypatch, user_ids, kanal):
    """AC-9 (nicht pausiert): "ist nicht pausiert"."""
    recorder, nutzer, settings = _umgebung(monkeypatch, user_ids, "L4")

    g = sende(kanal, nutzer, settings, recorder, "weiter")

    _ohne_ladehinweis(g, kanal)
    assert re.search(r"nicht pausiert|not paused", g.alles, re.IGNORECASE), g.alles


@pytest.mark.parametrize("kanal", KANAELE)
def test_ac9_weiter_auf_pausiertem_vergleich(monkeypatch, user_ids, kanal):
    """AC-9 (pausiert): Bestaetigung "wieder aktiv", Vergleich laeuft wieder."""
    recorder, nutzer, settings = _umgebung(monkeypatch, user_ids, "L4")
    _preset_pausiert(nutzer)

    g = sende(kanal, nutzer, settings, recorder, "weiter")

    _ohne_ladehinweis(g, kanal)
    assert re.search(r"wieder aktiv|active again", g.alles, re.IGNORECASE), g.alles
    assert _read(nutzer.user_id, nutzer.presets[0]["id"])["schedule"] == "daily"


@pytest.mark.parametrize("kanal", KANAELE)
def test_ac9_weiter_auf_gesperrtem_vergleich(monkeypatch, user_ids, kanal):
    """AC-9 (lock_timeout): bisheriger eigener Zweig "bitte erneut senden"."""
    recorder, nutzer, settings = _umgebung(monkeypatch, user_ids, "L4")
    frist_verkuerzen(monkeypatch, 0.3)
    _preset_pausiert(nutzer)

    with _preset_sperre(nutzer):
        g = sende(kanal, nutzer, settings, recorder, "weiter")

    _ohne_ladehinweis(g, kanal)
    assert any(w in g.alles.lower() for w in _ERNEUT), g.alles
    _sperrtext(g.alles)
    assert _read(nutzer.user_id, nutzer.presets[0]["id"])["schedule"] == "manual"


@pytest.mark.parametrize("zustand,erwartet", [
    ("nicht_pausiert", False), ("pausiert", True), ("gesperrt", False)])
def test_ac9_process_success_je_zustand(monkeypatch, user_ids, zustand, erwartet):
    recorder, nutzer, _ = _umgebung(monkeypatch, user_ids, "L4")
    frist_verkuerzen(monkeypatch, 0.3)
    if zustand != "nicht_pausiert":
        _preset_pausiert(nutzer)

    if zustand == "gesperrt":
        with _preset_sperre(nutzer):
            res, exc = process_direkt(nutzer, "weiter", vergleich=True)
    else:
        res, exc = process_direkt(nutzer, "weiter", vergleich=True)

    r = _ergebnis(res, exc)
    assert r.success is erwartet
    if zustand == "gesperrt":
        _sperrtext(_vol(r))


# ---------------------------------------------------------------------------
# AC-10 / AC-11: Klasse B (Wetterabruf) -- Antwort und Status stimmen ueberein
# ---------------------------------------------------------------------------

def _ohne_snapshot_und_abruf(monkeypatch, nutzer: BefehlNutzer) -> None:
    """Kein gespeicherter Snapshot UND der Abruf neuer Daten liefert nichts
    (``_fetch_and_save_snapshot`` ist die fail-soft Netzkante; ohne diesen
    Ersatz haengt das Ergebnis davon ab, ob Open-Meteo erreichbar ist --
    unter ``--disable-socket`` gleich, in der Live-Schicht aber nicht
    deterministisch. Fake-Quelle ohne Daten)."""
    (get_snapshots_dir(nutzer.user_id) / f"{nutzer.trip.id}.json").unlink()
    monkeypatch.setattr(
        "services.trip_command_processor._fetch_and_save_snapshot",
        lambda *a, **kw: None,
    )


_KEIN_SNAPSHOT = re.compile(r"kein wetter-snapshot|no weather data", re.IGNORECASE)
#: Befehl (process()-Eingabe) je ``_handle_query``-Schluessel.
QUERY_BEFEHLE = {
    "glance": "glance", "heute_gewitter": "gewitter",
    "timeline_heute": "### query: timeline_heute",
    "timeline_morgen": "### query: timeline_morgen",
}


@pytest.mark.parametrize("schluessel", sorted(QUERY_BEFEHLE))
def test_ac10_query_ohne_daten_text_unveraendert_success_false(monkeypatch, user_ids, schluessel):
    """AC-10: kein Snapshot + Abruf scheitert -> Text unveraendert, success=False."""
    recorder, nutzer, _ = _umgebung(monkeypatch, user_ids)
    _ohne_snapshot_und_abruf(monkeypatch, nutzer)

    res, exc = process_direkt(nutzer, QUERY_BEFEHLE[schluessel])

    r = _ergebnis(res, exc)
    assert _KEIN_SNAPSHOT.search(r.confirmation_body), r.confirmation_body
    assert r.success is False, "AC-10: Ohne-Daten-Antwort darf nicht 'erfolgreich' heissen"


@pytest.mark.parametrize("schluessel", sorted(QUERY_BEFEHLE))
def test_ac10_query_mit_daten_success_true(monkeypatch, user_ids, schluessel):
    """AC-10 (Gegenprobe): mit Snapshot -> Datentext und success=True."""
    recorder, nutzer, _ = _umgebung(monkeypatch, user_ids)

    res, exc = process_direkt(nutzer, QUERY_BEFEHLE[schluessel])

    r = _ergebnis(res, exc)
    assert not _KEIN_SNAPSHOT.search(r.confirmation_body), r.confirmation_body
    assert r.success is True


@pytest.mark.parametrize("befehl", ["glance", "gewitter"])
@pytest.mark.parametrize("kanal", KANAELE)
def test_ac10_ohne_daten_antwort_kommt_an_je_kanal(monkeypatch, user_ids, kanal, befehl):
    """AC-10/AC-20: die Ohne-Daten-Antwort kommt auf jedem Kanal mit
    unveraendertem Text an."""
    recorder, nutzer, settings = _umgebung(monkeypatch, user_ids)
    _ohne_snapshot_und_abruf(monkeypatch, nutzer)

    g = sende(kanal, nutzer, settings, recorder, befehl)

    _ohne_ladehinweis(g, kanal)
    assert _KEIN_SNAPSHOT.search(g.alles), g.alles


#: Drilldown-Befehle (process()-Eingabe): Stunden-/Werte-Abruf.
DRILLDOWN_BEFEHLE = {
    "drilldown": "### dd_wind_today",
    "hours": "### dd_hours_today",
    "metric": "temp",
}


@pytest.mark.parametrize("name", sorted(DRILLDOWN_BEFEHLE))
def test_ac11_drilldown_ohne_stundendaten_success_false(monkeypatch, user_ids, name):
    """AC-11: keine stuendlichen Daten -> bisheriger Text, success=False."""
    recorder, nutzer, _ = _umgebung(monkeypatch, user_ids)
    _ohne_snapshot_und_abruf(monkeypatch, nutzer)

    res, exc = process_direkt(nutzer, DRILLDOWN_BEFEHLE[name])

    r = _ergebnis(res, exc)
    assert re.search(r"keine st.ndlichen|nicht verf.gbar|no hourly|no data|nicht verf",
                     r.confirmation_body, re.IGNORECASE), r.confirmation_body
    assert r.success is False


@pytest.mark.parametrize("name", sorted(DRILLDOWN_BEFEHLE))
def test_ac11_drilldown_mit_stundendaten_success_true(monkeypatch, user_ids, name):
    recorder, nutzer, _ = _umgebung(monkeypatch, user_ids)

    res, exc = process_direkt(nutzer, DRILLDOWN_BEFEHLE[name])

    r = _ergebnis(res, exc)
    assert r.success is True, r.confirmation_body


@pytest.mark.parametrize("kanal", KANAELE)
def test_ac11_metrik_ohne_daten_antwort_kommt_an_je_kanal(monkeypatch, user_ids, kanal):
    recorder, nutzer, settings = _umgebung(monkeypatch, user_ids)
    _ohne_snapshot_und_abruf(monkeypatch, nutzer)

    g = sende(kanal, nutzer, settings, recorder, "temp")

    _ohne_ladehinweis(g, kanal)


# ---------------------------------------------------------------------------
# AC-12 / AC-13 / AC-14: Nowcast (``jetzt``) und ``strecke``
# ---------------------------------------------------------------------------

_NOWCAST_NICHT_VERFUEGBAR = re.compile(
    r"nowcast[^\n]*(nicht verf.gbar|not available|unavailable)", re.IGNORECASE)


def _radar_faellt_aus(monkeypatch) -> list:
    calls: list = []
    monkeypatch.setattr(
        "services.radar_service.RadarNowcastService",
        recording_radar_service_type(
            calls, script=lambda idx: RuntimeError("Radar-Quelle verweigert")),
    )
    return calls


@pytest.mark.parametrize("kanal", KANAELE)
def test_ac12_nowcast_ausfall_bringt_antwort(monkeypatch, user_ids, kanal):
    """AC-12: Nowcast wirft -> "Nowcast nicht verfuegbar" statt Schweigen."""
    recorder, nutzer, settings = _umgebung(monkeypatch, user_ids)
    calls = _radar_faellt_aus(monkeypatch)

    g = sende(kanal, nutzer, settings, recorder, "jetzt")

    assert calls, "der Nowcast-Fake wurde nie gefragt -- Messaufbau kaputt"
    _ohne_ladehinweis(g, kanal)
    assert _NOWCAST_NICHT_VERFUEGBAR.search(g.alles), g.alles


def test_ac12_nowcast_ausfall_process_success_false(monkeypatch, user_ids):
    recorder, nutzer, _ = _umgebung(monkeypatch, user_ids)
    _radar_faellt_aus(monkeypatch)

    res, exc = process_direkt(nutzer, "jetzt")

    r = _ergebnis(res, exc)
    assert r.success is False
    assert _NOWCAST_NICHT_VERFUEGBAR.search(r.confirmation_body), r.confirmation_body


def test_ac12_nowcast_mit_daten_success_true(monkeypatch, user_ids):
    """AC-12 (Gegenprobe): liefert der Nowcast, bleibt success=True."""
    recorder, nutzer, _ = _umgebung(monkeypatch, user_ids)
    calls: list = []
    monkeypatch.setattr(
        "services.radar_service.RadarNowcastService",
        recording_radar_service_type(calls, script=lambda idx: nass(10, 20)),
    )

    res, exc = process_direkt(nutzer, "jetzt")

    assert _ergebnis(res, exc).success is True


def _nowcast_ohne_daten():
    from services.radar_service import INTENSITY_DRY, NowcastResult

    return NowcastResult(onset_minutes=None, intensity_label=INTENSITY_DRY,
                         source="radar", data_unavailable=True)


@pytest.mark.parametrize("kanal", KANAELE)
def test_ac12_ergaenzung_nowcast_ohne_daten_antwort_kommt_an(monkeypatch, user_ids, kanal):
    """AC-12 Ergaenzung: Nowcast ohne Daten -- die Quelle liefert ein Ergebnis
    mit ``data_unavailable``; die Antwort kommt an und sagt "nicht moeglich"."""
    recorder, nutzer, settings = _umgebung(monkeypatch, user_ids)
    calls: list = []
    monkeypatch.setattr(
        "services.radar_service.RadarNowcastService",
        recording_radar_service_type(calls, script=lambda idx: _nowcast_ohne_daten()),
    )

    g = sende(kanal, nutzer, settings, recorder, "jetzt")

    assert calls, "der Nowcast-Fake wurde nie gefragt -- Messaufbau kaputt"
    _ohne_ladehinweis(g, kanal)
    assert re.search(r"nicht m.glich|not possible", g.alles, re.IGNORECASE), g.alles


def test_ac12_ergaenzung_nowcast_ohne_daten_process_success_false(monkeypatch, user_ids):
    """AC-12 Ergaenzung: Nowcast ohne Daten -> Text unveraendert, success=False."""
    recorder, nutzer, _ = _umgebung(monkeypatch, user_ids)
    calls: list = []
    monkeypatch.setattr(
        "services.radar_service.RadarNowcastService",
        recording_radar_service_type(calls, script=lambda idx: _nowcast_ohne_daten()),
    )

    res, exc = process_direkt(nutzer, "jetzt")

    r = _ergebnis(res, exc)
    assert calls
    assert "nicht möglich" in r.confirmation_body, r.confirmation_body
    assert r.success is False


@pytest.mark.parametrize("kanal", KANAELE)
def test_ac13_strecke_alle_punkte_leer_behauptet_kein_regen(monkeypatch, user_ids, kanal):
    """AC-13: liefert der Nowcast fuer ALLE Punkte nichts, heisst die Antwort
    "Nowcast nicht verfuegbar" -- nie "Kein Regen"."""
    recorder, nutzer, settings = _umgebung(monkeypatch, user_ids, strecke_km=1.5)
    calls = _radar_faellt_aus(monkeypatch)

    g = sende(kanal, nutzer, settings, recorder, "strecke")

    assert calls, "der Nowcast-Fake wurde nie gefragt -- Messaufbau kaputt"
    _ohne_ladehinweis(g, kanal)
    assert _NOWCAST_NICHT_VERFUEGBAR.search(g.alles), g.alles
    assert not re.search(r"kein regen|no rain", g.alles, re.IGNORECASE), g.alles


def test_ac13_strecke_alle_punkte_leer_process_success_false(monkeypatch, user_ids):
    recorder, nutzer, _ = _umgebung(monkeypatch, user_ids, strecke_km=1.5)
    _radar_faellt_aus(monkeypatch)

    res, exc = process_direkt(nutzer, "strecke")

    r = _ergebnis(res, exc)
    assert r.success is False
    assert _NOWCAST_NICHT_VERFUEGBAR.search(r.confirmation_body), r.confirmation_body
    assert "kein regen" not in r.confirmation_body.lower()


@pytest.mark.parametrize("strecke,mehrere", [("lang", True), ("kurz", False)])
def test_ac13_strecke_punktezahl_leer_behauptet_kein_regen(monkeypatch, user_ids, strecke, mehrere):
    """AC-13: alle Punkte leer -- Mehr-Punkt-Fall (22-km-Etappe) UND
    Ein-Punkt-Fall (1,5-km-Etappe: Reststrecke unter dem Punktabstand 2 km
    -> genau ein Abfragepunkt). Nie "Kein Regen", immer
    "Nowcast nicht verfuegbar"."""
    recorder, nutzer, _ = _umgebung(
        monkeypatch, user_ids, strecke_km=22.0 if strecke == "lang" else 1.5)
    calls = _radar_faellt_aus(monkeypatch)

    res, exc = process_direkt(nutzer, "strecke")

    r = _ergebnis(res, exc)
    assert (len(calls) > 1) is mehrere and calls, (
        f"Messaufbau: {len(calls)} Abfragepunkte: {r.confirmation_body!r}")
    assert "kein regen" not in r.confirmation_body.lower(), r.confirmation_body
    assert _NOWCAST_NICHT_VERFUEGBAR.search(r.confirmation_body), r.confirmation_body
    assert r.success is False


def test_ac13_strecke_gegenprobe_trocken_bleibt_kein_regen(monkeypatch, user_ids):
    """AC-13 (Gegenprobe): ein ECHTER 0-mm-Wert -> "Kein Regen" bleibt richtig
    und success=True."""
    recorder, nutzer, _ = _umgebung(monkeypatch, user_ids, strecke_km=1.5)
    calls: list = []
    monkeypatch.setattr(
        "services.radar_service.RadarNowcastService",
        recording_radar_service_type(calls, script=lambda idx: trocken()),
    )

    res, exc = process_direkt(nutzer, "strecke")

    r = _ergebnis(res, exc)
    assert calls, "der Nowcast-Fake wurde nie gefragt -- Messaufbau kaputt"
    assert re.search(r"kein regen|no rain", r.confirmation_body, re.IGNORECASE), r.confirmation_body
    assert r.success is True


def _backfill_wirft(monkeypatch) -> None:
    def _wirft(*a, **kw):
        raise OSError("Streckenlaengen nachtragen fehlgeschlagen")

    monkeypatch.setattr("services.track_resolution.backfill_stage_distances", _wirft)


@pytest.mark.parametrize("kanal", KANAELE)
def test_ac14_backfill_ausfall_bringt_antwort(monkeypatch, user_ids, kanal):
    """AC-14: ``backfill_stage_distances`` wirft -> Antwort statt Schweigen
    ("Nowcast nicht verfuegbar" bzw. gleichwertige Fehlerantwort)."""
    recorder, nutzer, settings = _umgebung(monkeypatch, user_ids, strecke_km=1.5)
    _backfill_wirft(monkeypatch)

    g = sende(kanal, nutzer, settings, recorder, "strecke")

    _ohne_ladehinweis(g, kanal)
    # F001: genau die lokale Nowcast-Fehlerantwort -- NICHT die zentrale
    # STATUS-Antwort aus process() (die wuerde ein werfender except-Zweig liefern).
    assert _NOWCAST_NICHT_VERFUEGBAR.search(g.alles), g.alles
    assert "STATUS" not in g.alles, g.alles


def test_ac14_backfill_ausfall_process_success_false(monkeypatch, user_ids):
    recorder, nutzer, _ = _umgebung(monkeypatch, user_ids, strecke_km=1.5)
    _backfill_wirft(monkeypatch)

    res, exc = process_direkt(nutzer, "strecke")

    assert _ergebnis(res, exc).success is False


# ---------------------------------------------------------------------------
# AC-15: Klasse C -- genehmigte Ausnahmen (Charakterisierung, heute gruen)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("befehl,merkmal", [
    ("hilfe", ("HEUTE", "HILFE", "TODAY", "HELP")),
    ("status", ("Status", "Etappe")),
])
@pytest.mark.parametrize("kanal", KANAELE)
def test_ac15_hilfe_und_status_unveraendert(monkeypatch, user_ids, kanal, befehl, merkmal):
    """AC-15 (Charakterisierung): Text aus der Konfiguration, ohne Abruf."""
    recorder, nutzer, settings = _umgebung(monkeypatch, user_ids)

    g = sende(kanal, nutzer, settings, recorder, befehl)

    _ohne_ladehinweis(g, kanal)
    assert any(m.lower() in g.alles.lower() for m in merkmal), g.alles


@pytest.mark.parametrize("befehl", ["hilfe", "status", "### hilfe"])
def test_ac15_process_success_true(monkeypatch, user_ids, befehl):
    recorder, nutzer, _ = _umgebung(monkeypatch, user_ids)

    res, exc = process_direkt(nutzer, befehl)

    assert _ergebnis(res, exc).success is True


def test_ac15_hilfe_zur_art_vergleich_success_true(monkeypatch, user_ids):
    """AC-15: Hilfe zu einer Art (``_show_help_for_kind``, Vergleich)."""
    recorder, nutzer, _ = _umgebung(monkeypatch, user_ids, "L4")

    res, exc = process_direkt(nutzer, "hilfe", vergleich=True)

    r = _ergebnis(res, exc)
    assert r.success is True
    assert r.confirmation_body.strip()
