"""Kern: Auswertung des Prod-Lese-Werkzeugs `befehl_antwortzeit.py` (#2439, AC-8).

Spec: docs/specs/modules/feat_2439_push_eingang_prod_scharf.md

Fixtures (``tests/fixtures/befehl_antwortzeit/``):
  - ``seven_journal_2026-09-27_bis_10-15.json``: ECHTER Mitschnitt der seven.io-Journale
    inbound/outbound (GET /api/journal/*), Rufnummern durch Rollen ersetzt
    (+49000SERVICE = Servicenummer, +49000ABSENDER = Garmin-/Test-Absender). Enthaelt die
    beiden Echtdaten-Fallen:
      * seven.io-Zeitstempel sind OHNE Zone und in Ortszeit Europe/Berlin -- belegt am
        15.10.: Journal 06:25:01, Webhook bei Staging 04:25:06 UTC.
      * outbound 15.10. 06:25:00,846 "CODES" ist der AUSLOESER von der zweiten Nummer (an
        die Servicenummer), keine Antwort -- er darf nie als Antwort zugeordnet werden.
      * 27.09. 08:51 und 09:14 blieben unbeantwortet; die Antwort 09:50 gehoert zum
        Eingang 09:46, nicht zu einem frueheren.
  - ``prod_dauerzeilen_2026-09.log``: Dauer-Zeilen im echten Journalformat
    (``journalctl -o short-iso-precise``, UTC). Die Zeile gab es im September noch nicht;
    sie ist zu den echten seven.io-Zeitpunkten passend gesetzt, mit einer Telegram- und
    einer Phasen-Zeile als Stoerer.

Vertrag an ``.claude/tools/befehl_antwortzeit.py`` (nur lesend):
  auswerten(inbound, outbound, dauerzeilen, push=None) -> {
      "befehle": [{"befehl", "kanal", "eingang", "antwort", "antwortzeit_s", "dauer_ms",
                   "push_zugeordnet"}, ...]   # je Eingang, aufsteigend nach Eingang
      "statistik": {befehl: {"anzahl", "max_s", "median_s"}}  # nur beantwortete
  }
  * Bruecke ist die Dauer-Zeile (kanal premium_sms/sms): Dauer-Zeilen nach Startzeit
    (ts - dauer_ms) aufsteigend; jede gehoert zum FRUEHESTEN noch freien Eingang mit
    Eingang <= Start und Eingang >= Start - 600 s. Ihr `befehl` gilt.
    Antwort = noch freier outbound VON der Servicenummer AN den Absender, zeitlich am
    naechsten an der Dauer-Zeile (|Abstand| <= 30 s). So bekommt bei ueberlappenden
    Befehlen (HEUTE, 5 s spaeter HELP, HELP-Antwort zuerst) jeder seine eigene Antwort.
  * Ohne Dauer-Zeile (aeltere Daten): Antwort = erster freier outbound an den Absender
    nach dem Eingang und vor dem naechsten Eingang desselben Absenders; Befehl aus dem
    SMS-Text (Gross, ohne XX-Code-Praefix).
  * Jede Antwort wird hoechstens einem Eingang zugeordnet.
  * seven.io-Zeit wird als Europe/Berlin gelesen (Sommer- UND Winterzeit), nie fester Versatz.
  * push_zugeordnet = `push.last_received` liegt in [Eingang - 5 s, Eingang + 60 s].
Die Dauer-Zeilen liest ``befehl_messlogik.dauerzeilen(lese_journal(...))``.
"""
from __future__ import annotations

import importlib.util
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

_REPO = Path(__file__).resolve().parents[1]
_FIX = _REPO / "tests" / "fixtures" / "befehl_antwortzeit"


def _lade(name: str):
    pfad = _REPO / ".claude" / "tools" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(name, pfad)
    assert spec and pfad.is_file(), f"{pfad} fehlt"
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _utc(text: str) -> datetime:
    return datetime.fromisoformat(f"{text}+00:00").astimezone(timezone.utc)


def _auswertung(push=None) -> dict:
    ml = _lade("befehl_messlogik")
    werkzeug = _lade("befehl_antwortzeit")
    journal = json.loads((_FIX / "seven_journal_2026-09-27_bis_10-15.json").read_text("utf-8"))
    dauer = ml.dauerzeilen(ml.lese_journal(
        (_FIX / "prod_dauerzeilen_2026-09.log").read_text("utf-8").splitlines()))
    return werkzeug.auswerten(journal["inbound"], journal["outbound"], dauer, push=push)


def _eintrag(erg: dict, eingang_utc: str) -> dict:
    ziel = _utc(eingang_utc)
    treffer = [b for b in erg["befehle"] if b["eingang"] == ziel]
    assert len(treffer) == 1, (
        f"Eingang {eingang_utc} UTC nicht genau einmal gefunden; vorhanden: "
        f"{[b['eingang'].isoformat() for b in erg['befehle']]} -- seven.io-Zeit ist Europe/Berlin"
    )
    return treffer[0]


def test_ac8_jeder_eingang_erscheint_einmal_in_zeitfolge():
    erg = _auswertung()
    eingaenge = [b["eingang"] for b in erg["befehle"]]
    assert len(eingaenge) == 10
    assert eingaenge == sorted(eingaenge)
    assert all(e.tzinfo is not None for e in eingaenge), "Eingang ohne Zeitzone"


@pytest.mark.parametrize("eingang_utc, antwort_utc, sekunden, befehl, dauer_ms", [
    ("2026-09-27T07:46:16", "2026-09-27T07:50:00.367", 224.367, "HELP", 140),
    ("2026-09-27T07:52:47", "2026-09-27T07:55:00.270", 133.270, "STATUS", None),
    ("2026-09-28T14:44:00", "2026-09-28T14:45:00.414", 60.414, "HELP", 95),
    ("2026-09-28T14:45:32", "2026-09-28T14:50:00.283", 268.283, "CODES", 88),
    ("2026-09-28T14:50:50", "2026-09-28T14:58:36.413", 466.413, "MORGEN", 31250),
])
def test_ac8_eingang_antwort_und_dauer(eingang_utc, antwort_utc, sekunden, befehl, dauer_ms):
    b = _eintrag(_auswertung(), eingang_utc)
    assert b["antwort"] == _utc(antwort_utc)
    assert b["antwortzeit_s"] == pytest.approx(sekunden, abs=0.001)
    assert b["befehl"] == befehl
    assert b["dauer_ms"] == dauer_ms, "Dauer aus falscher Zeile (Telegram/Phase) oder fehlend"


@pytest.mark.parametrize("eingang_utc", [
    "2026-09-27T06:51:01",  # Status, unbeantwortet
    "2026-09-27T07:14:08",  # hilfe, unbeantwortet -- die 09:50-Antwort gehoert zu 09:46
    "2026-10-15T04:25:01",  # CODES; das outbound-Echo 06:25:00,846 ist der Ausloeser
])
def test_ac8_unbeantworteter_eingang_bekommt_keine_fremde_antwort(eingang_utc):
    b = _eintrag(_auswertung(), eingang_utc)
    assert b["antwort"] is None and b["antwortzeit_s"] is None, b


def test_ac8_eine_antwort_wird_hoechstens_einem_eingang_zugeordnet():
    antworten = [b["antwort"] for b in _auswertung()["befehle"] if b["antwort"]]
    assert len(antworten) == len(set(antworten)) == 7


def test_ac8_maximum_und_median_je_befehl():
    stat = _auswertung()["statistik"]
    assert stat["HELP"]["anzahl"] == 2
    assert stat["HELP"]["max_s"] == pytest.approx(224.367, abs=0.001)
    assert stat["HELP"]["median_s"] == pytest.approx(142.3905, abs=0.001)
    # unbeantwortetes Status 27.09. 08:51 zaehlt nicht mit
    assert stat["STATUS"] == {"anzahl": 1, "max_s": pytest.approx(133.27, abs=0.001),
                              "median_s": pytest.approx(133.27, abs=0.001)}


def test_ac8_push_zuordnung_nur_beim_zeitlich_passenden_eingang():
    push = {"received_total": 1, "rejected_total": 0, "missed_total": 0,
            "last_received": "2026-09-28T16:50:52+02:00", "last_missed": None}
    erg = _auswertung(push=push)
    zugeordnet = [b["eingang"] for b in erg["befehle"] if b["push_zugeordnet"]]
    assert zugeordnet == [_utc("2026-09-28T14:50:50")]


def test_ac8_ohne_push_status_ist_nichts_zugeordnet():
    assert not any(b["push_zugeordnet"] for b in _auswertung()["befehle"])


# ---------------------------------------------------------------------------
# Ueberlappung und Winterzeit -- im echten Format, Werte gesetzt (nach dem 25.10. gibt es
# noch keinen Mitschnitt; genau dort liegt aber die offene Prod-Messung AC-6/AC-9/AC-10).
# ---------------------------------------------------------------------------

_SERVICE, _ABS = "+49000SERVICE", "+49000ABSENDER"


def _ein(ts: str, text: str) -> dict:
    return {"id": "1", "from": _ABS, "to": _SERVICE, "text": text, "timestamp": ts,
            "reply_to_message_id": None, "price": 0.01}


def _aus(ts: str, text: str) -> dict:
    return {"id": "x", "to": _ABS, "from": _SERVICE, "text": text, "timestamp": ts,
            "price": "0.1500", "dlr": "DELIVERED", "type": "direct", "channel": "SMS"}


def _dauer(ts_utc: str, befehl: str, ms: int) -> str:
    return (f"{ts_utc}+00:00 Rennwienix uv[1]: x INFO befehl_dauer: befehl={befehl} "
            f"kanal=premium_sms trip=khw-403 dauer_ms={ms}")


def _werte(inbound, outbound, dauer_zeilen):
    ml = _lade("befehl_messlogik")
    werkzeug = _lade("befehl_antwortzeit")
    dauer = ml.dauerzeilen(ml.lese_journal(dauer_zeilen))
    return werkzeug.auswerten(inbound, outbound, dauer)


def test_ac8_ueberlappende_befehle_bekommen_jeweils_ihre_eigene_antwort():
    """HEUTE 09:00:00, HELP 09:00:05 (Winterzeit, +01:00); die HELP-Antwort geht VOR der
    HEUTE-Antwort raus. Die reine Eingangsreihenfolge wuerde HEUTE die HELP-Antwort geben."""
    erg = _werte(
        [_ein("2026-10-27 09:00:00", "heute"), _ein("2026-10-27 09:00:05", "help")],
        [_aus("2026-10-27 09:00:06.200", "Commands: ..."),
         _aus("2026-10-27 09:00:41.300", "E4: W- WD:NW ...")],
        [_dauer("2026-10-27T08:00:06.400000", "HELP", 300),
         _dauer("2026-10-27T08:00:41.500000", "HEUTE", 39000)],
    )
    heute = _eintrag(erg, "2026-10-27T08:00:00")
    help_ = _eintrag(erg, "2026-10-27T08:00:05")
    assert (heute["befehl"], help_["befehl"]) == ("HEUTE", "HELP")
    assert heute["antwort"] == _utc("2026-10-27T08:00:41.300")
    assert heute["antwortzeit_s"] == pytest.approx(41.3, abs=0.001)
    assert heute["dauer_ms"] == 39000
    assert help_["antwort"] == _utc("2026-10-27T08:00:06.200")
    assert help_["antwortzeit_s"] == pytest.approx(1.2, abs=0.001)
    assert help_["dauer_ms"] == 300


def test_ac8_winterzeit_wird_als_europe_berlin_gelesen():
    """Nach dem 25.10. gilt +01:00 -- ein fest verdrahteter Versatz von 2 h faellt hier auf."""
    erg = _werte([_ein("2026-10-27 08:00:00", "Status")],
                 [_aus("2026-10-27 08:00:45.100", "Status: KHW 403")], [])
    b = _eintrag(erg, "2026-10-27T07:00:00")
    assert b["antwort"] == _utc("2026-10-27T07:00:45.100")
    assert b["antwortzeit_s"] == pytest.approx(45.1, abs=0.001)
    assert b["befehl"] == "STATUS"
