"""TDD RED — Kanal-/Slot-Schalter der Auslieferungskette (Issue #2422 S3, Bein (a)).

SPEC: docs/specs/modules/fix_2422_s3_kanal_an_aus_kette.md (AC-1..AC-4, AC-6..AC-15,
AC-17). AC-5 (Alarm-Vorlauf) und AC-16 (Mail-Pillen) stehen in eigenen Dateien.

Zielverhalten: Es geht genau das hinaus, was das gespeicherte Trip-JSON aussagt.
Ein abgeschalteter Slot liefert nichts (``morning_enabled``/``evening_enabled``),
ein abgeschalteter Kanal wird nicht bedient, ein Tier ohne Berechtigung bekommt
weder SMS noch Premium-SMS, ``email_format`` und die Erwaehnungsschwelle kommen
so an, wie sie eingestellt sind.

Einstieg wie im echten Betrieb: der Trip liegt im PERSISTENZFORMAT DES EDITORS
auf der Platte (``briefings/<id>.json``, Golden D als Vorlage), wird vom ECHTEN
``load_all_trips`` -> ``load_trip`` gelesen und vom ECHTEN
``TripReportSchedulerService.send_due_reports(now_utc)`` verschickt. So wirkt
das Lesen der Per-Slot-Schalter im Loader (Mutation M3) am Einstieg -- ein
Test, der ein ``TripReportConfig`` im Speicher baute, umginge genau diese
Stelle.

Messpunkt: die vier Kanal-Ausgaenge des ``NotificationService``, ersetzt durch
den geteilten Aufzeichner (``tests/helpers/transport_mitschrift.py``). Der
Aufzeichner ersetzt NUR die Naht zum Netz, nie die Entscheidung, wer bedient
wird -- die faellt im Produktivcode. Kein ``Mock()``/``patch()``.

Erwartungen kommen aus dem gespeicherten JSON (``erreichbare_kanaele``,
``erwartete_kaskade``) bzw. aus der geteilten Fallzeilen-Tabelle
``tests/fixtures/report_config_slot_faelle.json`` -- nie aus einer
Produktfunktion.

Bezugszeit FEST: Ortstag am Ort der Etappen + feste Ortsstunde
(``tests/helpers/ortstag.py``), nie die Systemuhr als Stunde. Nutzerkennungen
tragen bewusst kein "test"/"tdd" (Herkunftssperre #2406).

RED heute: ``send_due_reports`` kennt nur den Gesamtschalter ``enabled``; die
Per-Slot-Schalter werden nicht gelesen (AC-1, AC-2, AC-4, AC-6 und die
AC-3-Faelle mit Per-Slot-Schluesseln). Alles uebrige ist Charakterisierung
und startet GRUEN (AC-3-Altdaten, AC-7..AC-15, AC-17).
"""
from __future__ import annotations

import copy
import json
import logging
import re
import sys
from datetime import datetime, time, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
for _p in (str(ROOT), str(ROOT / "src")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

from app.loader import get_briefings_dir, get_data_dir, load_all_trips  # noqa: E402
from services.briefing_slots import _STATE_FILENAME  # noqa: E402
from services.trip_report_scheduler import TripReportSchedulerService  # noqa: E402
from tests.helpers.einstellung_auslieferung_orakel import (  # noqa: E402
    _COL_LABEL_TO_ID,
    AUSNAHMEN,
    erreichbare_kanaele,
    erwartete_kaskade,
    parse_kanal,
    roh_wert_der_metrik,
)
from tests.helpers.ortstag import ortstag  # noqa: E402
from tests.helpers.transport_mitschrift import (  # noqa: E402
    ALLE_KANAELE,
    Kanalmitschrift,
    aufzeichner_installieren,
)
from tests.tdd._einstellung_auslieferung_fixtures import (  # noqa: E402
    TRANSPORT_ENV,
    frisches_profil,
    golden_dict,
)
from utils.timezone import tz_for_coords  # noqa: E402

#: Exakter Standort aus ``providers/fixture.py::_FIXTURE_LOCATIONS`` (= die
#: Koordinaten der Etappen in Golden D) -- der Ortstag wird hier gemessen.
INNSBRUCK = (47.2692, 11.4041)

TABELLE = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures"
     / "report_config_slot_faelle.json").read_text()
)["faelle"]

#: Nur E-Mail eingeschaltet -- haelt Tests klein, die nicht den Kanal pruefen.
_NUR_EMAIL = {
    "send_email": True, "send_telegram": False,
    "send_sms": False, "send_premium_sms": False,
}

_FEHLT = object()  # Sentinel: Schluessel aus dem JSON ENTFERNEN


# ---------------------------------------------------------------------------
# Aufbau-Helfer (echte Dateien auf der isolierten Datenwurzel)
# ---------------------------------------------------------------------------


@pytest.fixture
def mit(monkeypatch) -> Kanalmitschrift:
    """Aufzeichner an den vier Kanal-Ausgaengen; Transportfelder unbrauchbar
    aber vollstaendig belegt (#1477: nichts geht je hinaus)."""
    for name, wert in TRANSPORT_ENV.items():
        monkeypatch.setenv(name, wert)
    return aufzeichner_installieren(monkeypatch)


def _rc(**ueberschreiben) -> dict:
    """``report_config`` von Golden D OHNE die Per-Slot-Schalter (die setzt
    jeder Test selbst); ``_FEHLT`` entfernt einen Schluessel."""
    rc = copy.deepcopy(golden_dict("golden_d")["report_config"])
    rc.pop("morning_enabled", None)
    rc.pop("evening_enabled", None)
    for schluessel, wert in ueberschreiben.items():
        if wert is _FEHLT:
            rc.pop(schluessel, None)
        else:
            rc[schluessel] = wert
    return rc


def _trip_schreiben(uid: str, report_config, *, basis: dict | None = None) -> str:
    """Trip im Persistenzformat des Editors auf die Platte (``briefings/<id>.json``).

    ``basis`` ist ein Golden-D-Dict (Default: unveraendertes Golden D); dessen
    ``report_config`` wird durch ``report_config`` ersetzt, ``None`` entfernt
    den ganzen Block. Gibt die Trip-Kennung zurueck.
    """
    d = copy.deepcopy(basis if basis is not None else golden_dict("golden_d"))
    trip_id = f"kette-{uid.rsplit('-', 1)[-1]}"
    d["id"] = trip_id
    d["kind"] = "route"
    if report_config is None:
        d.pop("report_config", None)
    else:
        d["report_config"] = copy.deepcopy(report_config)
    ordner = get_briefings_dir(uid)
    ordner.mkdir(parents=True, exist_ok=True)
    (ordner / f"{trip_id}.json").write_text(json.dumps(d), encoding="utf-8")
    return trip_id


def _datei(uid: str, trip_id: str) -> dict:
    """Die Trip-Datei so, wie sie JETZT auf der Platte steht."""
    return json.loads((get_briefings_dir(uid) / f"{trip_id}.json").read_text())


def _jetzt(stunde: int, minute: int = 0, *, tage: int = 0) -> datetime:
    """UTC-Zeitpunkt der ORTSzeit ``stunde:minute`` am Ortstag (+``tage``) der
    Etappen. Feste Stunde -- der Ausgang haengt nicht von der Tageszeit des
    Testlaufs ab; die Zone ist NICHT UTC (Innsbruck: +1/+2)."""
    tag = ortstag(*INNSBRUCK) + timedelta(days=tage)
    zone = tz_for_coords(*INNSBRUCK)
    return datetime.combine(tag, time(stunde, minute), tzinfo=zone).astimezone(
        timezone.utc
    )


def _lauf(uid: str, jetzt: datetime) -> tuple[int, int]:
    """Der regulaere Sammellauf des Schedulers zur Bezugszeit ``jetzt``."""
    return TripReportSchedulerService(user_id=uid).send_due_reports(jetzt)


def _slot_der_sendung(sendung: dict) -> str:
    """``morning``/``evening`` aus dem Betreff (``... — Morgen``/``... — Abend``)."""
    if sendung["subject"].rstrip().endswith("Morgen"):
        return "morning"
    if sendung["subject"].rstrip().endswith("Abend"):
        return "evening"
    raise AssertionError(f"Betreff ohne Morgen/Abend-Kennung: {sendung['subject']!r}")


def _slots(mit: Kanalmitschrift, kanal: str = "email") -> list[str]:
    return [_slot_der_sendung(s) for s in mit.sendungen(kanal)]


def _kurz(mit: Kanalmitschrift) -> dict[str, list[str]]:
    """Lesbare Kurzform der Mitschrift fuer Fehlermeldungen: je Kanal die
    Betreffs (``Kanalmitschrift.__repr__`` traegt die kompletten Koerper)."""
    return {k: [s["subject"] for s in mit.sendungen(k)] for k in ALLE_KANAELE
            if mit.sendungen(k)}


def _transportnamen(orakel_namen) -> set[str]:
    """Orakel-Namen (``email_html``/``telegram_kurzform``/...) auf die vier
    Transport-Kanaele der Mitschrift abbilden."""
    aus = set()
    for name in orakel_namen:
        aus.add("email" if name.startswith("email")
                else "telegram" if name.startswith("telegram") else name)
    return aus


def _golden_beide_an(*, email_format: str | None = None) -> dict:
    """Golden D mit BEIDEN Slots an (die Datei selbst traegt "Abend aus")."""
    d = golden_dict("golden_d")
    d["report_config"]["morning_enabled"] = True
    d["report_config"]["evening_enabled"] = True
    if email_format is not None:
        d["report_config"]["email_format"] = email_format
    return d


# ═══════════════════════════ AC-1 ════════════════════════════════════════════


def test_abend_aus_liefert_nur_morgen(mit):
    """AC-1: Editor-Stand "Morgen an / Abend aus" ⇒ nur das Morgen-Briefing.

    GIVEN ``enabled=true``, ``morning_enabled=true``, ``evening_enabled=false``,
          beide Zeiten in derselben Stunde, Etappen heute und morgen.
    WHEN  ``send_due_reports`` zu dieser Stunde laeuft.
    THEN  geht auf jedem eingeschalteten Kanal genau EIN Briefing hinaus (Morgen)
          und kein Abend-Briefing.

    RED heute: der Scheduler liest ``evening_enabled`` nicht -- das Abend-
    Briefing geht zusaetzlich hinaus (sent=2).
    """
    uid = frisches_profil()
    _trip_schreiben(uid, _rc(
        morning_enabled=True, evening_enabled=False,
        morning_time="09:00:00", evening_time="09:00:00",
    ))

    gesendet, fehlgeschlagen = _lauf(uid, _jetzt(9))

    for kanal in ALLE_KANAELE:
        assert len(mit.sendungen(kanal)) == 1, (
            f"AC-1: auf Kanal {kanal!r} muss genau EIN Briefing (Morgen) "
            f"ankommen, aufgezeichnet: {_kurz(mit)}"
        )
    assert _slots(mit) == ["morning"], (
        f"AC-1: die eine E-Mail muss das Morgen-Briefing sein, Betreffs: "
        f"{[s['subject'] for s in mit.sendungen('email')]}"
    )
    assert (gesendet, fehlgeschlagen) == (1, 0), (
        f"AC-1: der Lauf meldet genau EIN versendetes Briefing, erhalten "
        f"sent={gesendet}, failed={fehlgeschlagen}"
    )


# ═══════════════════════════ AC-2 ════════════════════════════════════════════


def test_morgen_aus_liefert_nur_abend(mit):
    """AC-2: Umkehrung von AC-1 -- "Morgen aus / Abend an" ⇒ nur das Abend-Briefing.

    RED heute: das Morgen-Briefing geht trotz ``morning_enabled=false`` hinaus.
    """
    uid = frisches_profil()
    _trip_schreiben(uid, _rc(
        morning_enabled=False, evening_enabled=True,
        morning_time="09:00:00", evening_time="09:00:00",
    ))

    gesendet, fehlgeschlagen = _lauf(uid, _jetzt(9))

    for kanal in ALLE_KANAELE:
        assert len(mit.sendungen(kanal)) == 1, (
            f"AC-2: auf Kanal {kanal!r} muss genau EIN Briefing (Abend) "
            f"ankommen, aufgezeichnet: {_kurz(mit)}"
        )
    assert _slots(mit) == ["evening"], (
        f"AC-2: die eine E-Mail muss das Abend-Briefing sein, Betreffs: "
        f"{[s['subject'] for s in mit.sendungen('email')]}"
    )
    assert (gesendet, fehlgeschlagen) == (1, 0), (
        f"AC-2: erwartet sent=1, failed=0, erhalten sent={gesendet}, "
        f"failed={fehlgeschlagen}"
    )


# ═══════════════════════════ AC-3 ════════════════════════════════════════════


def test_geteilte_fallzeilen_tabelle_ist_vollstaendig():
    """Adversary F004: eine leere oder gekuerzte Tabelle darf die
    parametrisierten Faelle nicht still SKIPPEN (Exit 0) -- derselbe
    Laengenwaechter wie im Go- und TS-Bein (>= 12 Zeilen)."""
    assert len(TABELLE) >= 12, (
        f"report_config_slot_faelle.json hat {len(TABELLE)} Faelle, erwartet >= 12 "
        f"(Datei gekuerzt?)"
    )


@pytest.mark.parametrize("fall", TABELLE, ids=[f["name"] for f in TABELLE])
def test_altdaten_und_gesamtschalter_folgen_der_regel(mit, fall):
    """AC-3: jede Zeile der GETEILTEN Fallzeilen-Tabelle (Python-Bein).

    GIVEN ein Trip mit der ``report_config`` der Zeile (``null`` = Block fehlt)
          und den Morgen-/Abend-Zeiten in getrennten Stunden.
    WHEN  der Sammellauf zur Morgen-Stunde und danach zur Abend-Stunde laeuft.
    THEN  kommt je Slot genau dann ein Briefing an, wenn ``slot_morning`` bzw.
          ``slot_evening`` der Zeile wahr ist (Gesamtschalter = Master, ein
          Per-Slot-``false`` schaltet NUR seinen Slot ab, Altdaten unveraendert).

    RED heute: die Zeilen MIT Per-Slot-Schluesseln (``abend_aus``, ``morgen_aus``,
    ``beide_aus_enabled_true``, ``nur_morgen_gesetzt_aus``). Die Altdaten-/
    Master-Zeilen sind Regressionswaechter und starten gruen.
    """
    roh = fall["report_config"]
    if roh is None:
        rc, stunde_morgen, stunde_abend = None, 7, 18  # Standardzeiten ohne Block
    else:
        rc = copy.deepcopy(roh)
        rc.setdefault("morning_time", "06:00:00")
        rc.setdefault("evening_time", "20:00:00")
        rc.setdefault("send_email", True)
        stunde_morgen, stunde_abend = 6, 20
    uid = frisches_profil()
    _trip_schreiben(uid, rc)

    _lauf(uid, _jetzt(stunde_morgen))
    morgens = _slots(mit)
    mit.leeren()
    _lauf(uid, _jetzt(stunde_abend))
    abends = _slots(mit)

    assert morgens == (["morning"] if fall["slot_morning"] else []), (
        f"AC-3 [{fall['name']}]: Morgen-Slot soll "
        f"{'senden' if fall['slot_morning'] else 'schweigen'} "
        f"(report_config={roh!r}), gesendet wurde {morgens}"
    )
    assert abends == (["evening"] if fall["slot_evening"] else []), (
        f"AC-3 [{fall['name']}]: Abend-Slot soll "
        f"{'senden' if fall['slot_evening'] else 'schweigen'} "
        f"(report_config={roh!r}), gesendet wurde {abends}"
    )


# ═══════════════════════════ AC-4 ════════════════════════════════════════════


@pytest.mark.parametrize("enabled", [True, False], ids=["enabled_true", "enabled_false"])
def test_beide_slots_aus_liefert_nichts_in_beiden_schreibweisen(mit, enabled):
    """AC-4: beide Per-Slot-Schalter aus ⇒ NICHTS geht hinaus -- egal ob der
    Gesamtschalter (so schreibt es der Editor) ``false`` oder (von Hand) ``true`` ist.

    Positivkontrolle im selben Test: derselbe Aufbau mit BEIDEN Slots an
    liefert zu beiden Stunden je ein Briefing -- "nichts" heisst also nicht
    "Aufbau kaputt".

    RED heute (``enabled_true``): der Gesamtschalter ist an, die Per-Slot-
    Schalter bleiben ungelesen -- beide Briefings gehen hinaus.
    """
    kontrolle = frisches_profil()
    _trip_schreiben(kontrolle, _rc(enabled=True, morning_enabled=True, evening_enabled=True))
    _lauf(kontrolle, _jetzt(6))
    _lauf(kontrolle, _jetzt(20))
    assert _slots(mit) == ["morning", "evening"], (
        f"Positivkontrolle: bei beiden Slots an muss je EIN Briefing kommen, "
        f"aufgezeichnet: {_kurz(mit)}"
    )
    mit.leeren()

    uid = frisches_profil()
    _trip_schreiben(uid, _rc(enabled=enabled, morning_enabled=False, evening_enabled=False))
    _lauf(uid, _jetzt(6))
    _lauf(uid, _jetzt(20))

    assert mit.kanaele == [], (
        f"AC-4: bei beiden Slots aus (enabled={enabled}) darf NICHTS hinausgehen, "
        f"aufgezeichnet: {_kurz(mit)}"
    )


# ═══════════════════════════ AC-6 ════════════════════════════════════════════


def test_skip_next_bleibt_bei_abgeschaltetem_slot_und_datei_bleibt_vollstaendig(mit):
    """AC-6: ein abgeschalteter Slot verbraucht ``skip_next`` NICHT.

    GIVEN ``skip_next=true``, "Abend aktiv" aus, "Morgen aktiv" an (Morgen-Zeit
          21:00, damit sie im selben Ortstag NACH dem Abend-Lauf faellig wird),
          dazu ein dem Frontend unbekannter Schluessel und Kanal-/Zeit-
          Einstellungen. Zunaechst existiert NUR die Etappe von morgen.
    WHEN  der Sammellauf zur Abend-Stunde laeuft (20:00); dann wird die
          Etappe von heute nachgetragen und der Lauf zur Morgen-Stunde
          (21:00) faellig; danach weitere Laeufe im selben Fenster und am
          Folgetag (21:00, Positivkontrolle).
    THEN  steht ``skip_next`` nach dem Abend-Lauf WEITERHIN auf der Platte;
          der Morgen-Lauf uebergeht das Briefing (kein Versand, Vermerk
          ``skipped``) und verbraucht den Wunsch; im restlichen Fenster kommt
          es nicht nach; am Folgetag wird wieder gesendet. In jedem Zustand
          sind ALLE Schluessel des urspruenglichen ``report_config`` (Per-Slot-
          Schalter, Kanaele, Zeiten, unbekannter Schluessel) mit ihrem Wert
          erhalten -- geprueft an der Datei NACH dem echten Schreiber
          (``save_trip`` aus dem ``skip_next``-Read-Modify-Write).

    Aufbau-Begruendung (Befund an der Spec): ``_get_active_trips`` wird vom
    Sammellauf je Durchgang (Morgen, Abend) und UNABHAENGIG von der Faelligkeit
    gerufen und verbraucht ``skip_next`` fuer jeden Trip mit Etappe am
    Zieltag. Mit Etappen heute UND morgen verbraeuchte schon der Morgen-
    Durchgang den Wunsch beim Abend-Lauf -- dann waere nicht der ABGESCHALTETE
    SLOT der Verbraucher, und AC-6 waere auch mit korrekter Slot-Pruefung
    nicht erfuellbar. Nur so kann allein der Abend-Durchgang verbrauchen.

    RED heute: der Abend-Durchgang verbraucht ``skip_next`` (die Slot-Pruefung
    fehlt vor dem Verbrauch).
    """
    basis = golden_dict("golden_d")
    stage_heute, *nur_morgen = basis["stages"]
    basis["stages"] = nur_morgen
    uid = frisches_profil()
    trip_id = _trip_schreiben(uid, _rc(
        morning_enabled=True, evening_enabled=False, skip_next=True,
        morning_time="21:00:00", evening_time="20:00:00",
        editor_unbekannter_schluessel={"bleibt": [1, 2, 3]},
    ), basis=basis)
    original = _datei(uid, trip_id)["report_config"]
    assert original["skip_next"] is True and original["evening_enabled"] is False

    def _erhalten(nach: dict, *, ausser: tuple[str, ...] = ()) -> list[str]:
        return [k for k, v in original.items()
                if k not in ausser and nach.get(k, _FEHLT) != v]

    def _vermerk_morgen() -> list[dict]:
        pfad = get_data_dir(uid) / _STATE_FILENAME
        eintraege = json.loads(pfad.read_text())["entries"] if pfad.exists() else []
        return [e for e in eintraege if e.get("slot") == "morning"]

    # 1. Abend-Lauf: Slot aus -- nichts geht hinaus, der Wunsch bleibt stehen.
    _lauf(uid, _jetzt(20))
    nach_abend = _datei(uid, trip_id)["report_config"]
    assert mit.kanaele == [], f"AC-6: Abend aus -- es darf nichts hinausgehen: {_kurz(mit)}"
    assert nach_abend.get("skip_next") is True, (
        f"AC-6: ein abgeschalteter Slot darf skip_next nicht verbrauchen, "
        f"in der Datei steht skip_next={nach_abend.get('skip_next')!r}"
    )
    assert _erhalten(nach_abend) == [], (
        f"AC-6: nach dem Abend-Lauf muessen alle Schluessel der Datei erhalten "
        f"sein, veraendert/verloren: {_erhalten(nach_abend)}"
    )

    # 2. Die Etappe von heute kommt hinzu; der Morgen-Slot wird faellig.
    datei = _datei(uid, trip_id)
    datei["stages"].insert(0, stage_heute)
    (get_briefings_dir(uid) / f"{trip_id}.json").write_text(json.dumps(datei), encoding="utf-8")
    _lauf(uid, _jetzt(21))
    nach_morgen = _datei(uid, trip_id)["report_config"]
    assert mit.kanaele == [], (
        f"AC-6: skip_next gesetzt -- das naechste AKTIVE Briefing (Morgen) muss "
        f"uebersprungen werden: {_kurz(mit)}"
    )
    assert [e.get("outcome") for e in _vermerk_morgen()] == ["skipped"], (
        f"AC-6: das uebersprungene Briefing erreicht den Versand nicht, der Slot "
        f"ist aber als 'skipped' abgeschlossen, Vermerke: {_vermerk_morgen()}"
    )
    assert nach_morgen.get("skip_next") is False, (
        f"AC-6: das uebersprungene Briefing verbraucht den Wunsch, in der Datei "
        f"steht skip_next={nach_morgen.get('skip_next')!r}"
    )
    assert _erhalten(nach_morgen, ausser=("skip_next",)) == [], (
        f"AC-6: nach dem Verbrauch muessen alle uebrigen Schluessel erhalten "
        f"sein, veraendert/verloren: {_erhalten(nach_morgen, ausser=('skip_next',))}"
    )

    # 3. Das uebersprungene Briefing kommt auch spaeter im Nachhol-Fenster
    #    (21:00-24:00) NICHT nach -- Ueberspringen heisst auslassen, nicht
    #    um einen Stundentakt verschieben.
    for stunde, minute in ((21, 30), (22, 0), (23, 0)):
        _lauf(uid, _jetzt(stunde, minute))
        assert mit.kanaele == [], (
            f"AC-6: das uebersprungene Morgen-Briefing darf um {stunde:02d}:{minute:02d} "
            f"nicht nachkommen: {_kurz(mit)}"
        )

    # 4. Positivkontrolle: am Folgetag geht das Morgen-Briefing wieder hinaus.
    _lauf(uid, _jetzt(21, tage=1))
    assert _slots(mit) == ["morning"], (
        f"AC-6 Positivkontrolle: nach dem Verbrauch muss das naechste Morgen-"
        f"Briefing ankommen, aufgezeichnet: {_kurz(mit)}"
    )


def test_skip_next_wird_erst_vom_faelligen_briefing_verbraucht(mit):
    """AC-6 (Normalfall mitten im Trip): ein Lauf zu einer NICHT faelligen
    Stunde verbraucht ``skip_next`` nicht.

    GIVEN Etappen heute UND morgen, beide Slots aktiv (Morgen 06:00, Abend
          20:00), ``skip_next=true``.
    WHEN  der stuendliche Sammellauf um 12:00 laeuft (kein Slot faellig), dann
          zur Abend-Stunde (20:00), im Fenster (21:00) und am Folgetag zur
          Morgen-Stunde (06:00).
    THEN  steht ``skip_next`` nach dem 12-Uhr-Lauf weiter in der Datei; der
          20-Uhr-Lauf uebergeht das Abend-Briefing und verbraucht den Wunsch;
          um 21:00 kommt es nicht nach; der Morgen-Lauf des Folgetags liefert
          wieder (Positivkontrolle).

    Bis #2422 S3 verbrauchte ``_get_active_trips`` den Wunsch in JEDEM
    Stundenlauf mit Etappe am Zieltag -- das naechste Briefing kam trotzdem.
    """
    uid = frisches_profil()
    trip_id = _trip_schreiben(uid, _rc(
        **_NUR_EMAIL, morning_enabled=True, evening_enabled=True, skip_next=True,
        morning_time="06:00:00", evening_time="20:00:00",
    ))

    _lauf(uid, _jetzt(12))
    assert mit.kanaele == [], f"AC-6: um 12:00 ist nichts faellig: {_kurz(mit)}"
    assert _datei(uid, trip_id)["report_config"].get("skip_next") is True, (
        "AC-6: ein Lauf ohne faelliges Briefing darf skip_next nicht verbrauchen"
    )

    _lauf(uid, _jetzt(20))
    assert mit.kanaele == [], (
        f"AC-6: das naechste faellige Briefing (Abend) muss entfallen: {_kurz(mit)}"
    )
    assert _datei(uid, trip_id)["report_config"].get("skip_next") is False, (
        "AC-6: das uebersprungene faellige Briefing verbraucht den Wunsch"
    )

    _lauf(uid, _jetzt(21))
    assert mit.kanaele == [], (
        f"AC-6: das uebersprungene Abend-Briefing kommt im Fenster nicht nach: {_kurz(mit)}"
    )

    _lauf(uid, _jetzt(6, tage=1))
    assert _slots(mit) == ["morning"], (
        f"AC-6 Positivkontrolle: nach dem Verbrauch kommt das naechste Briefing: {_kurz(mit)}"
    )


# ═══════════════════════════ AC-7 ════════════════════════════════════════════


@pytest.mark.parametrize(
    "pause,erwartet",
    [("paused_until_zukunft", 0), ("paused_until_abgelaufen", 1), ("paused_at", 0)],
)
def test_pause_und_trip_pause_unterdruecken_den_versand(mit, pause, erwartet):
    """AC-7: ``paused_until`` in der Zukunft und Trip-Pause (``paused_at``)
    unterdruecken den Versand; ein abgelaufenes ``paused_until`` nicht.

    Regressionswaechter (heute GRUEN): Pausen-Wirkung bleibt beim Umbau der
    Slot-Pruefung bestehen. Die abgelaufene Pause ist zugleich die
    Positivkontrolle -- gleicher Aufbau, dort MUSS gesendet werden.
    """
    jetzt = _jetzt(6)
    if pause == "paused_at":
        rc = _rc(**_NUR_EMAIL)
    else:
        delta = timedelta(days=2) if pause == "paused_until_zukunft" else -timedelta(days=2)
        rc = _rc(**_NUR_EMAIL, paused_until=(jetzt + delta).isoformat())
    basis = golden_dict("golden_d")
    if pause == "paused_at":
        basis["paused_at"] = (jetzt - timedelta(days=1)).isoformat()
    uid = frisches_profil()
    _trip_schreiben(uid, rc, basis=basis)

    _lauf(uid, jetzt)

    assert len(mit.sendungen("email")) == erwartet, (
        f"AC-7 [{pause}]: erwartet {erwartet} Morgen-Mail(s), aufgezeichnet: {_kurz(mit)}"
    )


# ═══════════════════════════ AC-8 ════════════════════════════════════════════

_KANAL_SCHALTER = {
    "email": "send_email", "telegram": "send_telegram",
    "sms": "send_sms", "premium_sms": "send_premium_sms",
}
_MATRIX = (
    [(f"nur_{k}", {s: (k2 == k) for k2, s in _KANAL_SCHALTER.items()})
     for k in _KANAL_SCHALTER]
    + [(f"alle_ausser_{k}", {s: (k2 != k) for k2, s in _KANAL_SCHALTER.items()})
       for k in _KANAL_SCHALTER]
)


@pytest.mark.parametrize("schalter", [m[1] for m in _MATRIX], ids=[m[0] for m in _MATRIX])
def test_kanalmatrix_bedient_genau_die_eingeschalteten_kanaele(mit, schalter):
    """AC-8: acht Kombinationen (jeder der vier Kanaele allein und jeder als
    einziger AUS) -- bedient wird EXAKT die eingeschaltete Menge, jeder Kanal
    mit demselben Massstab (E-Mail ist nicht privilegiert).

    Erwartung NUR aus ``erreichbare_kanaele`` (rohes JSON, Tier premium).
    Charakterisierung, heute GRUEN.
    """
    rc = _rc(**schalter)
    uid = frisches_profil(tier="premium")
    _trip_schreiben(uid, rc)

    _lauf(uid, _jetzt(6))

    erwartet = _transportnamen(erreichbare_kanaele(rc, tier="premium"))
    bedient = set(mit.kanaele)
    assert bedient == erwartet, (
        f"AC-8: eingeschaltet {sorted(k for k, s in _KANAL_SCHALTER.items() if schalter[s])}, "
        f"erwartet bedient {sorted(erwartet)}, tatsaechlich bedient {sorted(bedient)} "
        f"({_kurz(mit)})"
    )
    for kanal in erwartet:
        assert len(mit.sendungen(kanal)) == 1, (
            f"AC-8: Kanal {kanal!r} genau EINMAL bedienen, aufgezeichnet: {_kurz(mit)}"
        )


# ═══════════════════════════ AC-9 ════════════════════════════════════════════


def test_alle_kanaele_aus_liefert_nichts_und_vermerkt_no_channels(mit):
    """AC-9: alle vier Kanaele aus ⇒ nichts geht hinaus, ehrlich verbucht.

    GIVEN ein Trip mit allen vier Kanaelen aus (Slot faellig).
    WHEN  der Sammellauf laeuft.
    THEN  geht nichts hinaus, der Lauf meldet keinen Versandfehler, der Slot ist
          mit dem Ausgang ``no_channels`` vermerkt (Platte, ``briefing_slots.json``),
          ein zweiter Lauf in derselben Stunde sendet ebenfalls nichts und der
          Einzel-Slot-Versand liefert ``no_channels``.
    """
    rc = _rc(send_email=False, send_telegram=False, send_sms=False, send_premium_sms=False)
    uid = frisches_profil()
    trip_id = _trip_schreiben(uid, rc)
    assert erreichbare_kanaele(rc, tier="premium") == ()  # Aufbau: wirklich alles aus...
    jetzt = _jetzt(6)

    _gesendet, fehlgeschlagen = _lauf(uid, jetzt)

    def _vermerke() -> list[dict]:
        pfad = get_data_dir(uid) / _STATE_FILENAME
        eintraege = json.loads(pfad.read_text())["entries"] if pfad.exists() else []
        return [e for e in eintraege if e.get("trip_id") == trip_id]

    assert mit.kanaele == [], f"AC-9: nichts darf hinausgehen: {_kurz(mit)}"
    assert fehlgeschlagen == 0, f"AC-9: kein Versandfehler, erhalten failed={fehlgeschlagen}"
    vermerke = _vermerke()
    assert [(e["slot"], e["outcome"]) for e in vermerke] == [("morning", "no_channels")], (
        f"AC-9: der Slot muss als 'no_channels' vermerkt sein (kein Fehler, kein "
        f"Nachhol-Versuch), Vermerke: {vermerke}"
    )

    _lauf(uid, jetzt + timedelta(minutes=30))  # zweiter Lauf, gleiche Stunde
    assert mit.kanaele == [], f"AC-9: der zweite Lauf darf nichts senden: {_kurz(mit)}"
    assert _vermerke() == vermerke, "AC-9: der zweite Lauf darf den Vermerk nicht veraendern"

    trip = next(t for t in load_all_trips(uid) if t.id == trip_id)
    ausgang = TripReportSchedulerService(user_id=uid).send_test_report_outcome(trip, "morning")
    assert ausgang == "no_channels", f"AC-9: Einzel-Slot-Versand liefert {ausgang!r}"
    assert mit.kanaele == [], f"AC-9: auch der Einzel-Slot-Versand sendet nichts: {_kurz(mit)}"


# ═══════════════════════════ AC-10 ═══════════════════════════════════════════

_DEFAULT_FAELLE = {
    "a_send_email_fehlt": (
        _rc(send_email=_FEHLT, send_telegram=True, send_sms=False, send_premium_sms=False), 6),
    "b_send_telegram_sms_premium_fehlen": (
        _rc(send_email=True, send_telegram=_FEHLT, send_sms=_FEHLT, send_premium_sms=_FEHLT), 6),
    "c_ganz_ohne_report_config": (None, 7),
}


@pytest.mark.parametrize("fall", list(_DEFAULT_FAELLE))
def test_fehlende_kanal_schluessel_folgen_den_editor_defaults(mit, fall):
    """AC-10: fehlende Kanal-Schluessel folgen den Standardwerten des Editors.

    (a) ``send_email`` fehlt -> E-Mail an; (b) ``send_telegram``/``send_sms``/
    ``send_premium_sms`` fehlen -> aus; (c) ganz ohne ``report_config`` -> nur E-Mail.
    Erwartung aus ``erreichbare_kanaele`` (rohes JSON). Heute GRUEN.
    """
    rc, stunde = _DEFAULT_FAELLE[fall]
    uid = frisches_profil(tier="premium")
    _trip_schreiben(uid, rc)

    _lauf(uid, _jetzt(stunde))

    erwartet = _transportnamen(erreichbare_kanaele(rc, tier="premium"))
    assert set(mit.kanaele) == erwartet, (
        f"AC-10 [{fall}]: erwartet bedient {sorted(erwartet)}, tatsaechlich bedient "
        f"{sorted(mit.kanaele)} ({_kurz(mit)})"
    )
    assert "email" in erwartet, "Aufbau: E-Mail ist in jedem Default-Fall an"
    assert len(mit.sendungen("email")) == 1, f"AC-10 [{fall}]: E-Mail fehlt: {_kurz(mit)}"
    if fall != "a_send_email_fehlt":
        assert erwartet == {"email"}, f"Aufbau: {fall} soll NUR E-Mail erwarten"


# ═══════════════════════════ AC-11 ═══════════════════════════════════════════


@pytest.mark.parametrize("tier", ["free", "standard"])
def test_tier_gate_begrenzt_sms_und_premium_sms(mit, tier):
    """AC-11: Berechtigung != Einstellung.

    Alle vier Schalter an: bei ``free`` weder SMS noch Premium-SMS, bei
    ``standard`` SMS aber NICHT Premium-SMS (eigenes Gate, ADR-0049); E-Mail und
    Telegram sind unberuehrt. Erwartung aus ``erreichbare_kanaele(..., tier=...)``.
    Charakterisierung, heute GRUEN.
    """
    rc = _rc()  # Golden D: alle vier send_* = true
    assert all(rc[s] is True for s in _KANAL_SCHALTER.values())
    uid = frisches_profil(tier=tier)
    _trip_schreiben(uid, rc)

    _lauf(uid, _jetzt(6))

    erwartet = _transportnamen(erreichbare_kanaele(rc, tier=tier))
    assert set(mit.kanaele) == erwartet, (
        f"AC-11 [{tier}]: erwartet bedient {sorted(erwartet)}, tatsaechlich bedient "
        f"{sorted(mit.kanaele)} ({_kurz(mit)})"
    )
    assert {"email", "telegram"} <= set(mit.kanaele), (
        f"AC-11 [{tier}]: E-Mail und Telegram sind vom Tier unberuehrt: {_kurz(mit)}"
    )
    assert ("premium_sms" in mit.kanaele) is (tier == "premium"), f"AC-11 [{tier}]: {_kurz(mit)}"


def test_premium_sms_ohne_berechtigung_gilt_als_kein_kanal(mit):
    """AC-11 (Tier-Gate der Premium-SMS an der Stelle, an der es WIRKT).

    GIVEN Tier ``standard`` (SMS erlaubt, Premium-SMS nicht) und ein Trip, bei
          dem NUR Premium-SMS eingeschaltet ist.
    WHEN  der Slot faellig ist und der Sammellauf laeuft.
    THEN  geht nichts hinaus und der Slot ist ehrlich als ``no_channels``
          vermerkt -- kein Versandfehler, keine Nachlieferung.

    Warum eigener Fall: am Transport ist ein Tier-Gate, das Premium-SMS an
    ``sms_allowed`` statt ``premium_sms_allowed`` bindet (Mutation M7), nicht zu
    sehen -- das Premium-SMS-Tageslimit (0 bei ``standard``) sperrt dahinter
    ein zweites Mal. Sichtbar wird der Fehler am Ausgang: der Trip gaelte als
    „Kanal konfiguriert, aber gesperrt" und liefe in Fehlschlag/Nachlieferung.
    """
    rc = _rc(send_email=False, send_telegram=False, send_sms=False, send_premium_sms=True)
    uid = frisches_profil(tier="standard")
    trip_id = _trip_schreiben(uid, rc)
    assert erreichbare_kanaele(rc, tier="standard") == ()  # Aufbau: nichts erreichbar

    _gesendet, fehlgeschlagen = _lauf(uid, _jetzt(6))

    pfad = get_data_dir(uid) / _STATE_FILENAME
    eintraege = json.loads(pfad.read_text())["entries"] if pfad.exists() else []
    vermerke = [(e["slot"], e["outcome"]) for e in eintraege if e.get("trip_id") == trip_id]
    assert mit.kanaele == [], f"AC-11: nichts darf hinausgehen: {_kurz(mit)}"
    assert fehlgeschlagen == 0, f"AC-11: kein Versandfehler, erhalten failed={fehlgeschlagen}"
    assert vermerke == [("morning", "no_channels")], (
        f"AC-11: Premium-SMS ohne Berechtigung ist 'kein Kanal', nicht 'gesperrt' "
        f"-- Vermerke: {vermerke}"
    )


# ═══════════════════════════ AC-12 ═══════════════════════════════════════════


@pytest.mark.parametrize("fmt", ["compact", "full"])
def test_email_format_compact_und_full_kommen_wie_eingestellt_an(mit, fmt):
    """AC-12: ``email_format`` kommt so an, wie er gespeichert ist.

    ``compact`` -> Marker ``mail_format="compact"`` und kompakter Klartext-Aufbau
    (Textkoerper, KEIN HTML-Stundentabellen-Koerper); ``full`` -> Marker
    ``mail_format="full"`` und HTML-Koerper mit Stundentabelle. Beide tragen
    ``mail_type="trip-briefing"``. Heute GRUEN.
    """
    rc = _rc(**_NUR_EMAIL, email_format=fmt)
    uid = frisches_profil()
    _trip_schreiben(uid, rc)

    _lauf(uid, _jetzt(6))

    mails = mit.sendungen("email")
    assert len(mails) == 1, f"AC-12 [{fmt}]: genau EINE Mail erwartet: {_kurz(mit)}"
    mail = mails[0]
    assert mail["mail_type"] == "trip-briefing", f"AC-12 [{fmt}]: mail_type={mail['mail_type']!r}"
    assert mail["mail_format"] == fmt, (
        f"AC-12: email_format={fmt!r} gespeichert, die Mail traegt "
        f"mail_format={mail['mail_format']!r}"
    )
    body = mail["body"] or ""
    # ``<thead>`` = Stundentabelle; ``<table`` traefe auch den Mastkopf jeder HTML-Mail.
    hat_tabelle = "<thead" in body.lower()
    if fmt == "compact":
        assert not hat_tabelle, (
            "AC-12: die kompakte Mail darf keinen HTML-Stundentabellen-Koerper tragen"
        )
        assert body.lstrip().startswith("WETTER-BRIEFING"), (
            f"AC-12: kompakter Klartext-Aufbau erwartet, Anfang: {body[:80]!r}"
        )
    else:
        assert hat_tabelle, (
            f"AC-12: die volle Mail traegt eine HTML-Stundentabelle, Anfang: {body[:80]!r}"
        )
        assert (mail["plain_text_body"] or "").strip(), (
            "AC-12: die volle Mail traegt zusaetzlich den Klartext-Teil"
        )


# ═══════════════════════════ AC-13 ═══════════════════════════════════════════


@pytest.mark.parametrize(
    "slot,stunde,minute,erwartet",
    [
        ("morning", 5, 59, 0), ("morning", 6, 0, 1), ("morning", 8, 59, 1),
        ("morning", 9, 0, 0),
        ("evening", 19, 59, 0), ("evening", 20, 0, 1), ("evening", 22, 59, 1),
        ("evening", 23, 0, 0),
    ],
)
def test_versandzeit_fenster_und_kein_doppelversand(mit, caplog, slot, stunde, minute, erwartet):
    """AC-13: Versandzeiten im Editor-Format (``"06:00:00"``/``"20:00:00"``) und
    Nachhol-Fenster ``[Stunde, Stunde+3)`` in ORTSzeit (nicht UTC), nie doppelt.

    GIVEN Morgen 06:00:00 / Abend 20:00:00 in Innsbrucker Ortszeit.
    WHEN  der Lauf zur Ortszeit ``stunde:minute`` laeuft -- und danach ein
          zweites Mal im selben Fenster.
    THEN  liefert nur die Ortszeit im Fenster GENAU EIN Briefing des Slots;
          der Vermerk des ersten Versands beendet das Fenster -- schon beim
          SAMMELN (kein "Slot nicht reservierbar"-Warnlog): die Reservierung
          im Versand haelt Doppelmails zwar auch dann noch ab, aber ein zu
          langer Sammelbestand legt den Nachliefer-Mechanismus still (#1897).
    Charakterisierung, heute GRUEN.
    """
    caplog.set_level(logging.WARNING, logger="trip_report_scheduler")
    uid = frisches_profil()
    _trip_schreiben(uid, _rc(**_NUR_EMAIL, morning_time="06:00:00", evening_time="20:00:00"))
    jetzt = _jetzt(stunde, minute)
    assert jetzt.utcoffset() == timedelta(0) and jetzt.hour != stunde, (
        "Aufbau: die Bezugszeit ist UTC, die Stunde muss sich von der Ortsstunde unterscheiden"
    )

    _lauf(uid, jetzt)
    nach_erstem_lauf = _slots(mit)
    _lauf(uid, jetzt)                              # zweiter Lauf, gleiche Minute
    fensterende = (8 if slot == "morning" else 22) if erwartet else stunde
    _lauf(uid, _jetzt(fensterende, 59))            # letzte Minute des Fensters
    nach_allen = _slots(mit)

    assert nach_erstem_lauf == ([slot] * erwartet), (
        f"AC-13: Ortszeit {stunde:02d}:{minute:02d} ({slot}) soll {erwartet} Briefing(s) "
        f"liefern, geliefert: {nach_erstem_lauf}"
    )
    assert nach_allen == nach_erstem_lauf, (
        f"AC-13: kein Doppelversand -- nach weiteren Laeufen im selben Fenster "
        f"steht {nach_allen} statt {nach_erstem_lauf}"
    )
    assert "nicht reservierbar" not in caplog.text, (
        f"AC-13: der Vermerk muss den Slot schon beim Sammeln aus der Faelligkeit "
        f"nehmen, der Versand versuchte ihn erneut: {caplog.text.strip()[:300]}"
    )


# ═══════════════════════════ AC-14 ═══════════════════════════════════════════


def test_zeitfeld_mit_minuten_loest_zur_stunde_aus(mit):
    """AC-14: ein Zeitfeld mit Minuten (``morning_time="07:30:00"``, Altbestand
    oder direkter API-Weg) loest zur STUNDE aus: der Lauf um 07:00 Ortszeit
    liefert das Morgen-Briefing (nicht erst "um halb acht", nicht gar nicht);
    um 06:59 (Stunde davor) kommt noch nichts. Heute GRUEN.
    """
    rc = _rc(**_NUR_EMAIL, morning_time="07:30:00", evening_time="20:00:00")
    frueh, puenktlich = frisches_profil(), frisches_profil()
    _trip_schreiben(frueh, rc)
    _trip_schreiben(puenktlich, rc)

    _lauf(frueh, _jetzt(6, 59))
    assert mit.kanaele == [], f"AC-14: um 06:59 ist noch nichts faellig: {_kurz(mit)}"

    _lauf(puenktlich, _jetzt(7, 0))
    assert _slots(mit) == ["morning"], (
        f"AC-14: um 07:00 Ortszeit muss das Morgen-Briefing ankommen "
        f"(Zeitfeld mit Minuten), aufgezeichnet: {_kurz(mit)}"
    )


# ═══════════════════════════ AC-15 ═══════════════════════════════════════════

#: Stundenwert Niederschlag: ueber der Golden-D-Schwelle (0,1), unter dem
#: Standard (0,2) -- nur so kann der Test "Schwelle wirkt" von "Standard" trennen.
_STUNDENWERT_MM = 0.15
#: Standard-Erwaehnungsschwelle Regen ohne Nutzerwert (``metric_catalog`` DEFAULTS).
_STANDARD_SCHWELLE_MM = 0.2


@pytest.fixture
def stundenwert_015(monkeypatch, tmp_path):
    """Die echte Offline-Stundenreihe (Innsbruck-Fixture), nur mit kontrolliertem
    Niederschlags-Stundenwert 0,15 mm -- Renderer und Schwellenlogik laufen echt."""
    quelle = ROOT / "fixtures" / "openmeteo"
    for datei in quelle.glob("*.json"):
        roh = json.loads(datei.read_text())
        for punkt in roh["data"]:
            punkt["precip_1h_mm"] = _STUNDENWERT_MM
        (tmp_path / datei.name).write_text(json.dumps(roh))
    monkeypatch.setenv("GZ_TEST_FIXTURE_DIR", str(tmp_path))
    return _STUNDENWERT_MM


def _regen_metrik(d: dict) -> dict:
    return next(m for m in d["display_config"]["metrics"] if m["metric_id"] == "precipitation")


def _regen_im_layout(d: dict, kanal: str = "sms") -> dict:
    return next(m for m in d["display_config"]["channel_layouts"][kanal]
                if m["metric_id"] == "precipitation")


def _regen_wert_je_kanal(mit: Kanalmitschrift) -> dict[str, str | None]:
    """Roher Wert des Regen-Tokens (``R``) im SMS-, Kurzform- und Premium-SMS-
    Text, geparst (nicht per Substring). Ein Regen-Token OHNE Erwaehnung steht
    als ``-`` im Text -- "erwaehnt" heisst also: Wert ist eine Zahl."""
    return {
        kanal: roh_wert_der_metrik(mit, kanal, "precipitation")
        for kanal in ("sms", "telegram_kurzform", "premium_sms")
    }


def _erwaehnt(wert: str | None) -> bool:
    return wert not in (None, "-", "?")


def test_globale_sms_schwelle_wirkt_in_allen_drei_sms_texten(mit, stundenwert_015):
    """AC-15: die GLOBALE ``sms_threshold`` wirkt in SMS, Telegram-Kurzform und
    Premium-SMS -- und nur die globale.

    Stundenwert 0,15 mm (aus der echten Stundenreihe). Fuenf Faelle aus Golden D:
      A) global 0,1 (Golden D)              -> Regen-Token in ALLEN drei Texten,
      B) globale Schwelle entfernt (0,2)    -> Regen-Token in KEINEM,
      C) global 0,1 + Layout-Schwelle 5,0   -> Token bleibt (Layout aendert nichts),
      D) global entfernt + Layout-Schwelle 0,1 -> Token bleibt weg,
      E) global 0,12 -> Token da. E belegt, dass der Stundenwert 0,15 wirklich
         ankommt: die unveraenderte Fixture-Reihe (0,1 mm) liesse bei 0,12 den
         Token weg -- A..D allein trennten "0,15" nicht von "0,1".
    Die Erwartung folgt aus dem gespeicherten JSON (Schwelle <= Stundenwert).
    Charakterisierung, heute GRUEN.
    """
    def _fall(aendern) -> tuple[dict, dict[str, str | None]]:
        d = _golden_beide_an()
        aendern(d)
        _trip_schreiben(profil := frisches_profil(), d["report_config"], basis=d)
        mit.leeren()
        _lauf(profil, _jetzt(6))
        return d, _regen_wert_je_kanal(mit)

    def _erwartet(d: dict) -> bool:
        schwelle = _regen_metrik(d).get("sms_threshold")
        return _STUNDENWERT_MM >= (_STANDARD_SCHWELLE_MM if schwelle is None else schwelle)

    def _global_weg(d): _regen_metrik(d).pop("sms_threshold", None)

    def _layout_5(d): _regen_im_layout(d)["sms_threshold"] = 5.0

    def _global_weg_layout_01(d):
        _global_weg(d)
        _regen_im_layout(d)["sms_threshold"] = 0.1

    def _global_012(d): _regen_metrik(d)["sms_threshold"] = 0.12

    def _email_layout_ohne_regen(d):
        # Adversary F002 (M10c): die Mail waehlt Regen ab, die SMS behaelt ihn.
        # Die SMS-Schwelle muss aus der GLOBALEN Liste kommen -- in der auf das
        # E-Mail-Layout kollabierten Liste fehlt der Regen-Eintrag ganz.
        dc = d["display_config"]
        layouts = [dc["channel_layouts"]] + list(dc["channel_layouts_per_report"].values())
        for layout in layouts:
            if "email" in layout:
                layout["email"] = [m for m in layout["email"]
                                   if m["metric_id"] != "precipitation"]

    faelle = {
        "A_global_0_1": lambda d: None,
        "B_global_entfernt": _global_weg,
        "C_global_0_1_layout_5_0": _layout_5,
        "D_global_entfernt_layout_0_1": _global_weg_layout_01,
        "E_global_0_12": _global_012,
        "F_global_0_1_email_layout_ohne_regen": _email_layout_ohne_regen,
    }
    for name, aendern in faelle.items():
        d, werte = _fall(aendern)
        erwartet = _erwartet(d)
        token = {kanal: _erwaehnt(w) for kanal, w in werte.items()}
        assert token == {"sms": erwartet, "telegram_kurzform": erwartet, "premium_sms": erwartet}, (
            f"AC-15 [{name}]: Stundenwert {_STUNDENWERT_MM} mm, globale Schwelle "
            f"{_regen_metrik(d).get('sms_threshold')!r} -> Regen-Token erwartet: {erwartet}; "
            f"tatsaechlich je Kanal (Rohwert): {werte} ({_kurz(mit)})"
        )
    # Gegenprobe: A und B muessen sich unterscheiden, sonst trennt der Aufbau nichts.
    assert _erwartet(_golden_beide_an()) is True
    d_b = _golden_beide_an()
    _global_weg(d_b)
    assert _erwartet(d_b) is False


_TAG_RE = re.compile(r"<[^>]+>")


def _ids_je_kanal(mit: Kanalmitschrift) -> dict[str, list[str]]:
    """metric_ids in TEXT-Reihenfolge je Kanal, aus dem tatsaechlich gesendeten
    Text. Der HTML-Teil wird hier robust gelesen (erste ``<thead>`` der Mail):
    ``parse_email_html`` des Orakels nimmt starr die zweite ``<table>`` an --
    das passt zum Golden-Render, nicht zum Layout der Scheduler-Mail."""
    ids = {k: parse_kanal(mit, k)[0]
           for k in ("email_plain", "sms", "premium_sms", "telegram_kurzform")}
    html = mit.sendungen("email")[0]["body"]
    kopf = re.search(r"<thead>(.*?)</thead>", html, re.DOTALL)
    assert kopf, "Vorbedingung: die volle Mail traegt eine Stundentabelle mit <thead>"
    labels = [_TAG_RE.sub("", t).strip()
              for t in re.findall(r"<th[^>]*>(.*?)</th>", kopf.group(1), re.DOTALL)]
    ids["email_html"] = [_COL_LABEL_TO_ID[l] for l in labels if l in _COL_LABEL_TO_ID]
    return ids


def _kaskaden_abweichungen(golden: dict, mit: Kanalmitschrift, slot: str) -> set:
    """(metric_id, kanal, dimension) je Abweichung zwischen gesendetem Text und
    ``erwartete_kaskade`` (rohes JSON) -- abzueglich der im Register
    ``AUSNAHMEN`` bekannten, dokumentierten Produktabweichungen (S1)."""
    ist = _ids_je_kanal(mit)
    rot = set()
    for kanal, ist_ids in ist.items():
        soll_ids = [m for m, _ in erwartete_kaskade(golden, kanal, slot)]
        zellen = {(m, kanal, "erscheint") for m in set(soll_ids) ^ set(ist_ids)}
        gemeinsam_soll = [m for m in soll_ids if m in ist_ids]
        gemeinsam_ist = [m for m in ist_ids if m in soll_ids]
        zellen |= {(m, kanal, "reihenfolge") for m in gemeinsam_soll
                   if gemeinsam_soll.index(m) != gemeinsam_ist.index(m)}
        rot |= {
            (m, k, dim) for m, k, dim in zellen
            if not any(e.kanal == k and e.dimension == dim and e.metrik in (m, "*")
                       for e in AUSNAHMEN)
        }
    return rot



# ═══════════════════════════ AC-17 ═══════════════════════════════════════════


def test_per_report_layout_gewinnt_am_abend_morgen_folgt_per_channel(mit):
    """AC-17: ``channel_layouts_per_report`` gewinnt bis in den Text.

    Golden D (beide Slots an): Abend hat ein ``per_report``-Layout fuer E-Mail und
    SMS mit anderer Auswahl/Reihenfolge als ``channel_layouts``, der Morgen hat
    keins. Abend-Briefing: E-Mail, SMS, Premium-SMS und Kurzform zeigen die
    ``per_report``-Auswahl und -Reihenfolge; Morgen-Briefing: ``per_channel``.
    ``per_report`` darf das globale Maximum nicht erweitern (Schnitt) -- Fall 2:
    ``gust`` global abgewaehlt, im Abend-``per_report``-SMS aber gewaehlt.
    Erwartung aus ``erwartete_kaskade`` (rohes JSON). Heute GRUEN.
    """
    def _laufen(d: dict, slot: str, stunde: int):
        uid = frisches_profil()
        _trip_schreiben(uid, d["report_config"], basis=d)
        mit.leeren()
        _lauf(uid, _jetzt(stunde))
        assert _slots(mit) == [slot], f"Vorbedingung: nur der {slot}-Slot laeuft: {_kurz(mit)}"

    golden = _golden_beide_an(email_format="full")
    # Aufbau-Kontrolle: die beiden Kaskaden-Quellen unterscheiden sich wirklich.
    for kanal in ("sms", "email_plain"):
        assert erwartete_kaskade(golden, kanal, "evening") != erwartete_kaskade(golden, kanal, "morning"), (
            f"Aufbau: per_report (Abend) und per_channel (Morgen) muessen sich fuer "
            f"{kanal} unterscheiden"
        )

    for slot, stunde in (("evening", 20), ("morning", 6)):
        _laufen(golden, slot, stunde)
        rot = _kaskaden_abweichungen(golden, mit, slot)
        assert not rot, (
            f"AC-17 [{slot}]: Auswahl/Reihenfolge weichen von der Kaskade "
            f"per_report > per_channel > global ab (metrik, kanal, dimension): "
            f"{sorted(rot)}"
        )
        soll_sms = [m for m, _ in erwartete_kaskade(golden, "sms", slot)]
        ist_sms = parse_kanal(mit, "sms")[0]
        assert ist_sms == soll_sms, (
            f"AC-17 [{slot}]: SMS zeigt {ist_sms}, erwartet {soll_sms}"
        )

    # Schnitt gegen das globale Maximum: gust global aus, per_report-SMS will gust.
    schnitt = _golden_beide_an(email_format="full")
    next(m for m in schnitt["display_config"]["metrics"] if m["metric_id"] == "gust")["enabled"] = False
    per_report_sms = schnitt["display_config"]["channel_layouts_per_report"]["evening"]["sms"]
    assert any(m["metric_id"] == "gust" and m["enabled"] for m in per_report_sms), (
        "Aufbau: das Abend-per_report-SMS-Layout waehlt gust"
    )
    _laufen(schnitt, "evening", 20)
    ist_sms = parse_kanal(mit, "sms")[0]
    assert "gust" not in ist_sms, (
        f"AC-17 Schnitt: gust ist global abgewaehlt, per_report darf das Maximum "
        f"nicht erweitern, die SMS zeigt {ist_sms}"
    )
    assert set(ist_sms) == {m for m, _ in erwartete_kaskade(schnitt, "sms", "evening")}, (
        f"AC-17 Schnitt: SMS zeigt {ist_sms}, erwartet "
        f"{[m for m, _ in erwartete_kaskade(schnitt, 'sms', 'evening')]}"
    )
