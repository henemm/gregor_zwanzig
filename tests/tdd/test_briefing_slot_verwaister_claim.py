"""TDD RED — #1897: verwaister Briefing-Slot nach hartem Prozessende.

SPEC: docs/specs/modules/fix_1897_verwaister_briefing_slot.md (AC-1, AC-3,
AC-4, AC-5, AC-7, AC-8). AC-2/AC-6/AC-9 stehen in
``test_briefing_slot_faelligkeit_und_alarmsperre.py``.

Ausgangslage (real eingetreten, Trip KHW ``5f534011``, 14.08. abends und
16.08. morgens): ein Versandprozess wird mitten im Lauf hart beendet. Zurueck
bleibt in ``briefing_slots.json`` ein Vermerk mit ``outcome: null``, den
``is_recorded()`` heute als „erledigt" zaehlt — das Briefing bleibt fuer den
Rest des Ortstags aus.

────────────────────────────────────────────────────────────────────────────
Schnittstellen-Entscheidungen (die GREEN-Phase richtet sich danach)
────────────────────────────────────────────────────────────────────────────
1. ``services.briefing_slots.CLAIM_TTL = 900`` — MODUL-Attribut, zur Laufzeit
   gelesen (Muster ``LOCK_TIMEOUT_SECONDS``). Kein Test schreibt die Zahl 900.
2. ``BriefingSlotStore.reserve(trip_id, slot, local_day, zone=None, *, moment:
   datetime) -> bool`` — ``moment`` ist PFLICHT und keyword-only (ADR-0051
   Regel 3, kein ``datetime.now()``-Rueckfall).
3. ``BriefingSlotStore.is_recorded_or_claimed(trip_id, slot, local_day,
   zone=None, *, moment: datetime) -> bool`` — das zweite, eigenstaendige
   Praedikat („abgeschlossen ODER lebendig in Arbeit") fuer
   ``_collect_due_trips``. ``is_recorded()`` bedeutet ab jetzt ausschliesslich
   „abgeschlossen" (``outcome`` gesetzt) plus Rueckwaerts-Ableitung.
4. ``TripReportSchedulerService._dispatch_due_item(trip, report_type,
   local_day, *, now_utc: datetime)`` — reicht denselben Lauf-Zeitpunkt an
   ``reserve()`` durch.

────────────────────────────────────────────────────────────────────────────
RED-Charakter je Test
────────────────────────────────────────────────────────────────────────────
Der verwaiste Vermerk wird NICHT ueber die neue Schnittstelle aufgebaut,
sondern als roher Datei-Zustand geschrieben — genau so, wie ihn ein hart
beendeter Prozess hinterlaesst. Dadurch scheitern AC-1 und AC-5 heute am
gemeldeten FEHLVERHALTEN (kein Versand), nicht bloss an einer fehlenden
Signatur. AC-3/AC-4/AC-7/AC-8 nageln zusaetzlich die neue Schnittstelle fest
und sind heute rot, weil ``reserve(..., moment=...)`` sie nicht kennt.

Kein Mock-Theater: Speicher, Sperre, Schluesselbildung, Faelligkeitsfenster
und Sammellauf laufen ECHT. Ersetzt ist an genau einer Stelle die Naht zum
Netz — ``_send_trip_report_outcome`` — durch eine echte Unterklasse, die einen
der dokumentierten Ausgaenge zurueckgibt und ihre Aufrufe mitschreibt.

Zeit ist durchgehend PARAMETER (feste UTC-Zeitpunkte); die Ortszone des Trips
ist ``Atlantic/Reykjavik`` (ganzjaehrig UTC+0), Ortsstunde = UTC-Stunde.
Pfadregel #1409: alles relativ zu DIESER Datei bzw. ueber ``app.loader``.
"""
from __future__ import annotations

import json
import sys
import threading
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.loader import get_briefings_dir, get_data_dir, load_all_trips  # noqa: E402
from services import briefing_slots  # noqa: E402
from services.briefing_slots import BriefingSlotStore  # noqa: E402

REYKJAVIK = (64.13, -21.90)  # Atlantic/Reykjavik, ganzjaehrig UTC+0
TRIP = "khw-1897"
TAG = date(2026, 8, 20)
SLOT_STUNDE = 7
ABEND_STUNDE = 18

# Die vier Ausgaenge, die einen Slot abschliessen (`trip_report_scheduler.py:94`).
VERMERK_AUSGAENGE = ("sent", "no_stage", "no_weather", "no_channels")


def _ttl() -> int:
    """``CLAIM_TTL`` zur LAUFZEIT — nie als getippte Zahl im Test."""
    return briefing_slots.CLAIM_TTL


def _uhr(stunde: int, minute: int = 0) -> datetime:
    return datetime(TAG.year, TAG.month, TAG.day, stunde, minute, tzinfo=timezone.utc)


def _schreibe_trip(user_id: str) -> None:
    """Echter Trip in ``briefings/`` (Cutover-Lesepfad #1250)."""
    lat, lon = REYKJAVIK
    stages = [
        {
            "id": f"{TRIP}-s{i}", "name": f"Etappe {i}",
            "date": (TAG + timedelta(days=i - 1)).isoformat(),
            "waypoints": [
                {"id": f"{TRIP}-wp{i}a", "name": "Start",
                 "lat": lat, "lon": lon, "elevation_m": 300},
                {"id": f"{TRIP}-wp{i}b", "name": "Ziel",
                 "lat": lat + 0.05, "lon": lon + 0.05, "elevation_m": 700},
            ],
        }
        for i in range(3)
    ]
    ordner = get_briefings_dir(user_id)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / f"{TRIP}.json").write_text(json.dumps({
        "id": TRIP, "name": "Karnischer Hoehenweg", "kind": "route",
        "stages": stages,
        "report_config": {
            "trip_id": TRIP, "enabled": True,
            "morning_time": f"{SLOT_STUNDE:02d}:00:00",
            "evening_time": f"{ABEND_STUNDE:02d}:00:00",
            "send_email": True,
        },
    }), encoding="utf-8")


def _trip_obj(user_id: str):
    for trip in load_all_trips(user_id=user_id):
        if trip.id == TRIP:
            return trip
    raise AssertionError(f"Trip {TRIP!r} nicht ladbar fuer {user_id!r}")


def _vermerk_datei(user_id: str) -> Path:
    return get_data_dir(user_id) / "briefing_slots.json"


def _offener_vermerk(user_id: str, recorded_at: datetime, slot: str = "morning") -> Path:
    """Genau der Zustand, den ein HART BEENDETER Versandprozess hinterlaesst:
    ein Eintrag im Bestandsschema (`_eintrag()`, `briefing_slots.py:136-144`)
    mit ``outcome: null``.

    Bewusst roh geschrieben statt ueber die neue ``reserve(..., moment=...)``:
    so misst der Test das gemeldete FEHLVERHALTEN und nicht bloss eine
    fehlende Signatur.
    """
    pfad = _vermerk_datei(user_id)
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({"entries": [{
        "trip_id": TRIP, "slot": slot, "local_day": TAG.isoformat(),
        "recorded_at": recorded_at.isoformat(), "outcome": None,
    }]}, indent=2), encoding="utf-8")
    return pfad


def _briefing_log(user_id: str, sent_at: datetime, slot: str = "morning") -> None:
    """Ein regulaerer Protokoll-Eintrag — der Nachweis, dass die Mail trotz
    verwaistem Vermerk bereits draussen ist (`_log_bezeugt_versand`)."""
    pfad = get_data_dir(user_id) / "briefing_log.json"
    pfad.parent.mkdir(parents=True, exist_ok=True)
    pfad.write_text(json.dumps({"entries": [{
        "trip_id": TRIP, "kind": slot, "sent_at": sent_at.isoformat(),
        "channels": ["email"],
    }]}), encoding="utf-8")


def _zaehlende_klasse():
    """Echter ``TripReportSchedulerService``, bei dem AUSSCHLIESSLICH die Naht
    zum Netz ersetzt ist (Muster aus ``test_briefing_slot_idempotenz.py``)."""
    from services.trip_report_scheduler import TripReportSchedulerService

    class _MitProtokoll(TripReportSchedulerService):
        versandversuche: list = []

        def _send_trip_report_outcome(self, trip, report_type, **kwargs):
            type(self).versandversuche.append((trip.id, report_type))
            return "sent"

    _MitProtokoll.versandversuche = []
    return _MitProtokoll


def _scheduler(user_id: str):
    return _zaehlende_klasse()(user_id=user_id)


def _voller_lauf(user_id: str, now_utc: datetime, monkeypatch) -> list:
    """Der ECHTE Versandlauf ueber den geteilten Orchestrator — dieselbe Kette,
    die der stuendliche Cron-Tick faehrt (``run_briefing_dispatch`` →
    ``collect_due`` → ``pre_pass`` → ``dispatch_one``).

    Bewusst NICHT ``_collect_due_trips`` + ``_dispatch_due_item`` von Hand: der
    Lauf-Zeitpunkt muss laut Spec vom Orchestrator bis in ``reserve()``
    durchgereicht werden; ein handgebauter Lauf saehe eine gerissene
    Durchreichung nicht.
    """
    from services import trip_report_scheduler as trs
    from services.dispatch_orchestrator import run_briefing_dispatch

    from tests.helpers.briefing_imminent_fixtures import settings_email_only

    klasse = _zaehlende_klasse()
    monkeypatch.setattr(trs, "TripReportSchedulerService", klasse)
    run_briefing_dispatch("route", user_id, now_utc, settings=settings_email_only())
    return list(klasse.versandversuche)


# ---------------------------------------------------------------------------
# AC-1 — der abgebrochene Slot wird beim naechsten stuendlichen Lauf nachgeholt
# ---------------------------------------------------------------------------

def test_ac1_verwaister_vermerk_wird_beim_naechsten_lauf_nachgeholt(monkeypatch):
    """AC-1.

    GIVEN das Morgen-Briefing wurde um 07:00 Ortszeit begonnen und der Prozess
    endete hart, sodass ein Vermerk ohne Ausgang zurueckbleibt
    WHEN der naechste stuendliche Lauf um 08:00 Ortszeit laeuft
    THEN wird das Briefing verschickt und der Vermerk traegt danach den
    Ausgang ``sent``.

    Gemessen am beobachtbaren Versandaufruf, nicht per Dateiinhalt-Grep. Dass
    der Ausgang wirklich gesetzt wurde, zeigt der dritte Lauf: waere er es
    nicht, ginge das Briefing um 09:00 ein zweites Mal raus.

    RED-Charakter: Fehlernachweis — heute zaehlt jeder gefundene Eintrag als
    „erledigt" (`briefing_slots.py:78`), der 08:00-Lauf sendet nichts.
    """
    user = "u1897-ac1"
    _schreibe_trip(user)
    _offener_vermerk(user, _uhr(SLOT_STUNDE))

    versuche = _voller_lauf(user, _uhr(SLOT_STUNDE + 1), monkeypatch)

    assert versuche == [(TRIP, "morning")], (
        "Der 07:00-Versand ist hart abgebrochen — der 08:00-Lauf muss das "
        f"Briefing nachholen, protokolliert wurde {versuche}."
    )
    assert BriefingSlotStore(user).is_recorded(TRIP, "morning", TAG) is True, (
        "Nach dem nachgeholten Versand muss der Vermerk einen Ausgang tragen "
        "(`sent`) — sonst ist der Slot weiterhin offen."
    )
    assert _voller_lauf(user, _uhr(SLOT_STUNDE + 2), monkeypatch) == [], (
        "Der 09:00-Lauf liegt noch im Nachhol-Fenster: mit gesetztem Ausgang "
        "darf das Briefing kein zweites Mal rausgehen."
    )


# ---------------------------------------------------------------------------
# AC-3 — ein junger Vermerk blockiert weiter (kein Doppelversand)
# ---------------------------------------------------------------------------

def test_ac3_junger_vermerk_verweigert_die_reservierung(monkeypatch):
    """AC-3.

    GIVEN ein Vermerk ohne Ausgang ist juenger als ``CLAIM_TTL``, der Versand
    laeuft also noch
    WHEN ein zweiter Lauf denselben Slot reservieren will
    THEN verweigert die Reservierung und es findet kein zweiter Versand statt.

    Fail-closed wie heute: ``False``, keine Ausnahme.

    RED-Charakter: Mutations-Waechter — heute gruen (jeder Eintrag blockiert),
    rot wegen der fehlenden Pflicht-Zeit in ``reserve``. NACH der Umsetzung
    bewacht er die teuerste Verfaelschung: eine Uebernahme-Regel ohne
    Altersgrenze wuerde hier doppelt an echte Empfaenger senden.
    """
    user = "u1897-ac3"
    _schreibe_trip(user)
    jetzt = _uhr(SLOT_STUNDE, 2)
    _offener_vermerk(user, jetzt - timedelta(seconds=_ttl() // 9))

    scheduler = _scheduler(user)
    assert BriefingSlotStore(user).reserve(
        TRIP, "morning", TAG, moment=jetzt,
    ) is False, (
        "Ein Vermerk ohne Ausgang, der juenger als CLAIM_TTL ist, gehoert zu "
        "einem laufenden Versand — die Reservierung muss verweigert werden."
    )
    assert scheduler._dispatch_due_item(
        _trip_obj(user), "morning", TAG, now_utc=jetzt,
    ) is None, "Ohne Reservierung darf kein Versandversuch stattfinden."
    assert scheduler.versandversuche == [], (
        f"Kein zweiter Versandaufruf erlaubt, protokolliert: "
        f"{scheduler.versandversuche}"
    )


# ---------------------------------------------------------------------------
# AC-4 — Uebernahme des verwaisten Vermerks samt frischem Zeitstempel
# ---------------------------------------------------------------------------

def test_ac4_verwaister_vermerk_wird_mit_neuem_zeitstempel_uebernommen():
    """AC-4.

    GIVEN ein Vermerk ohne Ausgang ist aelter als ``CLAIM_TTL``
    WHEN ein Lauf denselben Slot reservieren will
    THEN wird der Vermerk uebernommen, sein Zeitstempel auf den neuen
    Zeitpunkt gesetzt, und der Versand findet statt.

    Der erneuerte Zeitstempel wird VERHALTENSSEITIG nachgewiesen, nicht per
    Dateiinhalt: unmittelbar nach der Uebernahme ist der Vermerk wieder „jung"
    — eine Reservierung knapp VOR Ablauf der neuen Frist muss scheitern.
    Bliebe ``recorded_at`` stehen, waere der Vermerk dort laengst wieder
    verwaist und ein dritter Lauf uebernaehme ihn (Doppelversand).

    RED-Charakter: Fehlernachweis fuer die Uebernahme (heute blockiert der
    alte Vermerk dauerhaft) — rot heute mangels ``moment``-Parameter.
    """
    user = "u1897-ac4"
    _schreibe_trip(user)
    jetzt = _uhr(SLOT_STUNDE + 1)
    _offener_vermerk(user, jetzt - timedelta(seconds=_ttl() * 2))
    store = BriefingSlotStore(user)

    assert store.reserve(TRIP, "morning", TAG, moment=jetzt) is True, (
        "Ein Vermerk ohne Ausgang, der aelter als CLAIM_TTL ist, stammt aus "
        "einem hart beendeten Prozess und muss uebernommen werden."
    )
    assert store.reserve(
        TRIP, "morning", TAG, moment=jetzt + timedelta(seconds=_ttl() - 1),
    ) is False, (
        "Nach der Uebernahme muss `recorded_at` auf den neuen Zeitpunkt "
        "stehen — knapp vor Ablauf der Frist ist der Vermerk noch jung. "
        "Bleibt der alte Zeitstempel stehen, uebernimmt ihn der naechste Lauf "
        "sofort erneut."
    )

    zweiter = "u1897-ac4b"
    _schreibe_trip(zweiter)
    _offener_vermerk(zweiter, jetzt - timedelta(seconds=_ttl() * 2))
    scheduler = _scheduler(zweiter)
    assert scheduler._dispatch_due_item(
        _trip_obj(zweiter), "morning", TAG, now_utc=jetzt,
    ) == "sent", "Nach der Uebernahme muss der Versand tatsaechlich laufen."
    assert scheduler.versandversuche == [(TRIP, "morning")]


# ---------------------------------------------------------------------------
# AC-5 — zugestellt, aber nicht vermerkt: kein zweiter Versand
# ---------------------------------------------------------------------------

def test_ac5_bereits_zugestelltes_briefing_wird_nicht_erneut_versendet():
    """AC-5.

    GIVEN ein Vermerk ohne Ausgang ist aelter als ``CLAIM_TTL``, aber das
    Briefing-Protokoll weist fuer denselben Trip, dieselbe Slot-Art und
    denselben Ortstag einen regulaeren Versand aus
    WHEN ein Lauf den Slot reservieren will
    THEN findet kein erneuter Versand statt.

    Der Prozess starb zwischen erfolgreichem Versand und ``record_outcome()``
    — die Mail ist draussen, der Vermerk sieht verwaist aus. Der Claim wird
    stattdessen direkt abgeschlossen; ``is_recorded()`` beweist das, denn die
    Rueckwaerts-Ableitung schweigt hier (``briefing_slots.json`` existiert
    bereits, `briefing_slots.py:199`).

    RED-Charakter: Fehlernachweis fuer die Folge-Gefahr der Uebernahme — eine
    Uebernahme-Regel ohne diesen Protokoll-Blick sendet das Briefing ein
    zweites Mal an echte Empfaenger inklusive kostenpflichtiger Premium-SMS.
    """
    user = "u1897-ac5"
    _schreibe_trip(user)
    jetzt = _uhr(SLOT_STUNDE + 1)
    _briefing_log(user, _uhr(SLOT_STUNDE, 4))
    _offener_vermerk(user, _uhr(SLOT_STUNDE))
    store = BriefingSlotStore(user)

    assert store.reserve(TRIP, "morning", TAG, moment=jetzt) is False, (
        "Das Protokoll bezeugt den Versand dieses Ortstags — der verwaiste "
        "Vermerk darf NICHT uebernommen werden."
    )
    assert store.is_recorded(TRIP, "morning", TAG) is True, (
        "Der Vermerk muss stattdessen direkt als `sent` abgeschlossen werden; "
        "bliebe er offen, versuchte es jeder folgende Lauf erneut."
    )
    scheduler = _scheduler(user)
    assert scheduler._dispatch_due_item(
        _trip_obj(user), "morning", TAG, now_utc=jetzt,
    ) is None
    assert scheduler.versandversuche == [], (
        f"Kein zweiter Versand, protokolliert: {scheduler.versandversuche}"
    )


# ---------------------------------------------------------------------------
# AC-7 — zwei gleichzeitige Laeufe, genau eine Uebernahme
# ---------------------------------------------------------------------------

def test_ac7_gleichzeitige_uebernahme_gelingt_genau_einmal(monkeypatch):
    """AC-7.

    GIVEN zwei Laeufe versuchen im selben Augenblick, denselben verwaisten
    Vermerk zu uebernehmen
    WHEN beide reservieren wollen
    THEN uebernimmt genau einer, der andere sendet nicht.

    Gleichzeitigkeit ausschliesslich ueber ``threading.Barrier`` — keine
    Wartezeit, keine Systemuhr.

    🔴 Die Schranke liegt am GEFAHRENPUNKT: unmittelbar vor dem Erwerb der
    Sidecar-Sperre in ``_update()`` (Adversary F003). Vor
    ``_dispatch_due_item`` gesetzt taugte sie nicht — der Test-Versand kehrt
    sofort zurueck, der gewinnende Thread lief deshalb meist komplett durch
    (reserve → Versand → ``record_outcome``), bevor der zweite ueberhaupt bis
    zu seinem Sperren-Erwerb kam. Der Test war damit gruen aus
    Scheduling-Zufall, nicht weil der Code absichert: eine Fassung, die
    Alterspruefung und Uebernahme trennt, kam ungestraft durch.

    Ersetzt ist NICHT die Sperre — die echte ``acquire_exclusive`` laeuft
    danach unveraendert, ebenso Speicher, Schluesselbildung und Versandkette.
    Synchronisiert wird allein der EINSPRUNG-Zeitpunkt, und nur beim ersten
    Sperren-Erwerb je Thread: der Gewinner nimmt die Sperre fuer
    ``record_outcome`` gleich noch einmal und liefe sonst gegen eine Schranke,
    an der niemand mehr wartet.

    🔴 Zweite Haelfte derselben Luecke: der Test-Versand kehrte bisher SOFORT
    zurueck, der Gewinner setzte den Ausgang also noch bevor der Verlierer
    seine Reservierung ueberhaupt versuchte — dann rettete ihn die
    Ausgangs-Pruefung statt der Alters-Pruefung, und die eigentliche Zusicherung
    blieb ungeprueft. Ein echter Versand dauert Sekunden bis Minuten (die
    ``CLAIM_TTL``-Begruendung nennt 319 s als laengsten gemessenen Einzellauf).
    Der Versand haelt hier deshalb an, bis der andere Lauf mit seiner
    Reservierung durch ist — laufen BEIDE in den Versand, wartet keiner mehr auf
    den anderen und die Wartezeit laeuft ab; genau dann meldet der Test die zwei
    Versandaufrufe.

    🔴 Ausnahmen aus Threads meldet pytest nur als WARNUNG. Sie werden deshalb
    eingesammelt und ausdruecklich assertiert — ohne das waere der Test blind.

    RED-Charakter: Mutations-Waechter — rot, sobald Alterspruefung und
    Uebernahme in ZWEI Schritte zerfallen (erst lesen, dann schreiben): dann
    beanspruchen beide Laeufe denselben Vermerk und das Briefing geht doppelt
    raus.
    """
    user = "u1897-ac7"
    _schreibe_trip(user)
    jetzt = _uhr(SLOT_STUNDE + 1)
    _offener_vermerk(user, jetzt - timedelta(seconds=_ttl() * 2))

    from services.trip_day import trip_tz

    schranke = threading.Barrier(2)
    anderer_fertig = threading.Event()
    ergebnisse: list = []
    fehler: list = []

    class _MitLaufendemVersand(_zaehlende_klasse()):
        def _send_trip_report_outcome(self, trip, report_type, **kwargs):
            ausgang = super()._send_trip_report_outcome(trip, report_type, **kwargs)
            anderer_fertig.wait(timeout=5)
            return ausgang

    scheduler = _MitLaufendemVersand(user_id=user)
    trip = _trip_obj(user)
    trip_tz(trip)  # Zonen-Aufloesung vorwaermen — nicht Teil des Rennens

    echte_sperre = briefing_slots.acquire_exclusive
    eigener_stand = threading.local()

    def _sperre_nach_schranke(fd, timeout):
        if not getattr(eigener_stand, "sync", False):
            eigener_stand.sync = True
            schranke.wait(timeout=15)
        return echte_sperre(fd, timeout)

    monkeypatch.setattr(briefing_slots, "acquire_exclusive", _sperre_nach_schranke)

    def _versuch() -> None:
        try:
            ergebnisse.append(
                scheduler._dispatch_due_item(trip, "morning", TAG, now_utc=jetzt)
            )
        except BaseException as exc:  # noqa: BLE001 - bewusst alles einsammeln
            fehler.append(exc)
        finally:
            anderer_fertig.set()

    threads = [threading.Thread(target=_versuch) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=30)

    assert fehler == [], f"Ausnahme in einem der beiden Laeufe: {fehler!r}"
    assert ergebnisse.count("sent") == 1 and ergebnisse.count(None) == 1, (
        f"Genau ein Lauf darf den verwaisten Vermerk uebernehmen, "
        f"Ergebnisse: {ergebnisse!r}"
    )
    assert scheduler.versandversuche == [(TRIP, "morning")], (
        f"Genau ein Versandaufruf erlaubt, protokolliert: "
        f"{scheduler.versandversuche}"
    )


# ---------------------------------------------------------------------------
# Frist-Mechanik — die drei Zusicherungen der Spec an ihrem Wirkort
# (Adversary F002 Laufzeit-Lesen, F001 Grenzfall, F005 Zeitstempel)
# ---------------------------------------------------------------------------


def test_claim_ttl_wird_zur_laufzeit_gelesen(monkeypatch):
    """``CLAIM_TTL`` ist ein MODUL-Attribut und wird bei jeder Pruefung neu
    gelesen — eine beim Import gebundene lokale Konstante machte jede
    Test-Verkuerzung der Frist still wirkungslos (Adversary F002).

    Gemessen am Verhalten: DERSELBE Vermerk, DERSELBE Zeitpunkt, nur die Frist
    wird gesenkt — und aus „laufender Versand" wird „verwaist". Bindet der Code
    die Frist beim Import, bleibt die zweite Antwort ``False``.
    """
    user = "u1897-ttl-laufzeit"
    _schreibe_trip(user)
    jetzt = _uhr(SLOT_STUNDE + 1)
    alter = _ttl() // 3
    _offener_vermerk(user, jetzt - timedelta(seconds=alter))
    store = BriefingSlotStore(user)

    assert store.reserve(TRIP, "morning", TAG, moment=jetzt) is False, (
        "Testaufbau prueft nichts: der Vermerk muss unter der REGULAEREN Frist "
        "noch als lebendig gelten."
    )
    monkeypatch.setattr(briefing_slots, "CLAIM_TTL", alter // 2)
    assert store.reserve(TRIP, "morning", TAG, moment=jetzt) is True, (
        "Mit gesenkter Frist ist derselbe Vermerk verwaist — wird CLAIM_TTL "
        "nicht zur Laufzeit gelesen, bleibt die Frist unerreichbar und jeder "
        "TTL-Test misst nur noch den Vorgabewert."
    )


@pytest.mark.parametrize("versatz, uebernommen", [(0, False), (1, True)])
def test_grenzfall_exakt_ttl_gilt_noch_nicht_als_verwaist(versatz, uebernommen):
    """Grenzfall der Frist (Adversary F001): „exakt ``CLAIM_TTL`` alt" ist NOCH
    NICHT verwaist, erst eine Sekunde darueber.

    Fail-closed wie ueberall in diesem Speicher — auf der Kippe lieber ein
    ausgelassener Slot als ein Doppelversand. Ohne diese Zusicherung waere der
    Wechsel von ``>`` auf ``>=`` ein unbemerkter Schritt in die teure Richtung.
    """
    user = f"u1897-ttl-grenze-{versatz}"
    _schreibe_trip(user)
    jetzt = _uhr(SLOT_STUNDE + 1)
    _offener_vermerk(user, jetzt - timedelta(seconds=_ttl() + versatz))

    assert BriefingSlotStore(user).reserve(
        TRIP, "morning", TAG, moment=jetzt,
    ) is uebernommen, (
        f"Ein Vermerk, der exakt CLAIM_TTL plus {versatz} s alt ist, muss "
        f"{'uebernommen werden' if uebernommen else 'blockieren'}."
    )


def test_neuer_vermerk_traegt_den_lauf_zeitpunkt():
    """Ein FRISCH angelegter Vermerk bekommt sein ``recorded_at`` vom
    uebergebenen Lauf-Zeitpunkt, nicht von der Systemuhr (Adversary F005).

    Sonst maesse die Verwaisungs-Frist gegen einen anderen Zeitstrahl als den
    des Aufrufers — der Vermerk waere je nach Abstand der beiden Uhren sofort
    verwaist (Doppelversand) oder nie (dauerhafter Ausfall).

    Verhaltensseitig gemessen, nicht per Dateiinhalt: die Frist wird von BEIDEN
    Seiten angefahren. Ein Rueckfall auf die Systemuhr verschiebt den
    Kipppunkt und laesst eine der beiden Zusicherungen scheitern, egal in
    welche Richtung die Uhren auseinanderliegen.
    """
    user = "u1897-neuer-vermerk"
    _schreibe_trip(user)
    jetzt = _uhr(SLOT_STUNDE)
    store = BriefingSlotStore(user)

    assert store.reserve(TRIP, "morning", TAG, moment=jetzt) is True, (
        "Ohne Vermerk und ohne Protokoll muss die erste Reservierung gelingen."
    )
    assert store.reserve(
        TRIP, "morning", TAG, moment=jetzt + timedelta(seconds=_ttl()),
    ) is False, (
        "Gemessen vom uebergebenen Lauf-Zeitpunkt aus ist der Vermerk nach "
        "genau CLAIM_TTL noch lebendig — traegt er stattdessen die Systemuhr, "
        "liegt der Kipppunkt woanders."
    )
    assert store.reserve(
        TRIP, "morning", TAG, moment=jetzt + timedelta(seconds=_ttl() + 1),
    ) is True, (
        "Eine Sekunde spaeter ist derselbe Vermerk verwaist — bleibt er "
        "blockiert, misst die Frist gegen einen fremden Zeitstrahl."
    )


# ---------------------------------------------------------------------------
# AC-8 — Bestandsvermerke bleiben abgeschlossen, ohne Migration
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ausgang", VERMERK_AUSGAENGE)
def test_ac8_bestandsvermerke_bleiben_abgeschlossen(ausgang: str):
    """AC-8.

    GIVEN Bestandseintraege, die vor dieser Aenderung geschrieben wurden
    WHEN sie gelesen werden
    THEN verhalten sich abgeschlossene Vermerke unveraendert und es ist keine
    Datenmigration noetig.

    Der Zeitstempel liegt bewusst ZEHN TAGE zurueck: eine Verwaisungs-Regel,
    die nur aufs Alter schaut und ``outcome`` uebersieht, uebernaehme diese
    Eintraege und sendete jedes abgeschlossene Briefing erneut. Genau das
    faengt die dritte Zusicherung.

    „Keine Migration" wird als Byte-Gleichheit der Speicherdatei vor/nach dem
    Lesen gemessen — es geht um einen ausgebliebenen SCHREIBVORGANG, nicht um
    einen Textbeleg fuer Verhalten.

    RED-Charakter: Mutations-Waechter — heute strukturell erfuellt, rot wegen
    der beiden neuen Signaturen; danach bewacht er die Alters-Dimension gegen
    den teuersten Fehlgriff.
    """
    user = f"u1897-ac8-{ausgang}"
    _schreibe_trip(user)
    jetzt = _uhr(SLOT_STUNDE + 1)
    pfad = _offener_vermerk(user, jetzt - timedelta(days=10))
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    daten["entries"][0]["outcome"] = ausgang
    pfad.write_text(json.dumps(daten, indent=2), encoding="utf-8")
    vorher = pfad.read_bytes()

    store = BriefingSlotStore(user)
    assert store.is_recorded(TRIP, "morning", TAG) is True, (
        f"Ausgang '{ausgang}' schliesst den Slot ab — `is_recorded` muss ihn "
        "unveraendert als erledigt melden."
    )
    assert store.is_recorded_or_claimed(
        TRIP, "morning", TAG, moment=jetzt,
    ) is True, (
        f"Auch das Faelligkeits-Praedikat muss den abgeschlossenen Ausgang "
        f"'{ausgang}' kennen — sonst sammelt der Scheduler den Slot erneut ein."
    )
    assert store.reserve(TRIP, "morning", TAG, moment=jetzt) is False, (
        f"Ein zehn Tage alter, mit '{ausgang}' abgeschlossener Vermerk ist "
        "NICHT verwaist — wer nur aufs Alter sieht, sendet ihn erneut."
    )
    assert pfad.read_bytes() == vorher, (
        "Bestandsdaten duerfen beim Lesen nicht umgeschrieben werden — es gibt "
        "keine Migration."
    )


def test_ac8_unbekannter_ausgang_schliesst_den_slot_ebenfalls_ab():
    """AC-8, Ergaenzung: „abgeschlossen" heisst ``outcome`` GESETZT, nicht
    ``outcome`` aus einer bekannten Menge.

    GIVEN ein Vermerk traegt einen Ausgang, den dieser Speicher nicht kennt —
    einen kuenftigen fuenften Wert des Schedulers
    WHEN die beiden Praedikate ihn lesen
    THEN gilt der Slot als abgeschlossen und wird nicht uebernommen.

    Die Spec begruendet das ausdruecklich („Implementation Details", Zustand 1):
    pruefte der Speicher die Zugehoerigkeit zu ``VERMERK_AUSGAENGE``, entschiede
    er ueber die Ausgangs-Auswahl des Schedulers mit — und ein neuer fuenfter
    Ausgang fiele still auf „nicht erledigt" zurueck, also GENAU in den Fehler,
    den Issue #1897 behebt: ein zugestelltes Briefing ginge erneut raus.

    ``test_ac8_bestandsvermerke_bleiben_abgeschlossen`` kann das nicht sehen —
    es ist ueber ``VERMERK_AUSGAENGE`` parametrisiert und faehrt damit nur die
    vier Werte, fuer die beide Lesarten dasselbe Ergebnis liefern. Dieser Fall
    fuehrt deshalb einen ERFUNDENEN Ausgang ein; dass er wirklich unbekannt
    ist, wird gegen die echte Menge des Schedulers gemessen, nicht angenommen.

    Der Zeitstempel liegt weit jenseits von ``CLAIM_TTL``: so zeigt jede der
    drei Zusicherungen, dass der AUSGANG entscheidet und nicht das Alter.
    """
    from services.trip_report_scheduler import VERMERK_AUSGAENGE as ECHTE_MENGE

    fremder = "onboard_error"
    assert fremder not in ECHTE_MENGE, (
        f"Testaufbau prueft nichts: '{fremder}' ist inzwischen ein bekannter "
        f"Ausgang ({sorted(ECHTE_MENGE)}) — es braucht einen anderen."
    )

    user = "u1897-ac8-fremder-ausgang"
    _schreibe_trip(user)
    jetzt = _uhr(SLOT_STUNDE + 1)
    pfad = _offener_vermerk(user, jetzt - timedelta(seconds=_ttl() * 10))
    daten = json.loads(pfad.read_text(encoding="utf-8"))
    daten["entries"][0]["outcome"] = fremder
    pfad.write_text(json.dumps(daten, indent=2), encoding="utf-8")

    store = BriefingSlotStore(user)
    assert store.is_recorded(TRIP, "morning", TAG) is True, (
        f"Ein gesetzter Ausgang schliesst den Slot ab, auch wenn dieser "
        f"Speicher ihn nicht kennt ('{fremder}') — sonst haelt die Alarm-Sperre "
        "fuer einen bereits erledigten Slot weiter."
    )
    assert store.is_recorded_or_claimed(
        TRIP, "morning", TAG, moment=jetzt,
    ) is True, (
        f"Auch das Faelligkeits-Praedikat muss '{fremder}' als Abschluss "
        "lesen — sonst sammelt der Scheduler den Slot erneut ein."
    )
    assert store.reserve(TRIP, "morning", TAG, moment=jetzt) is False, (
        f"Ein mit '{fremder}' abgeschlossener Vermerk ist NICHT verwaist, egal "
        "wie alt er ist — wer nur bekannte Ausgaenge gelten laesst, sendet das "
        "Briefing ein zweites Mal an echte Empfaenger."
    )
