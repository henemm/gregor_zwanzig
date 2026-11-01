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
    Eingang <= Start und Eingang >= Start - 600 s, dessen Text-Befehl (Alias-normalisiert
    wie im Prozessor, z. B. "Tomorrow" -> MORGEN) zum `befehl` der Dauer-Zeile passt.
    Ihr `befehl` gilt.
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


# ---------------------------------------------------------------------------
# Fix-Loop 1 (Adversary F002/F003): Median, Absender, 30-s-Naehe, Einmal-Zuordnung
# ---------------------------------------------------------------------------

_ABS_B = "+49000ANDERER"


def _von(absender: str, ts: str, text: str) -> dict:
    return {**_ein(ts, text), "from": absender}


def _an(absender: str, ts: str, text: str) -> dict:
    return {**_aus(ts, text), "to": absender}


def test_f002_median_ist_nicht_der_mittelwert():
    """Drei beantwortete HELP nach 10, 12 und 100 s: Median 12 s (Mittelwert waere 40,67 s)."""
    erg = _werte(
        [_ein("2026-10-27 09:00:00", "help"), _ein("2026-10-27 09:10:00", "help"),
         _ein("2026-10-27 09:20:00", "help")],
        [_aus("2026-10-27 09:00:10", "Commands"), _aus("2026-10-27 09:10:12", "Commands"),
         _aus("2026-10-27 09:21:40", "Commands")], [])
    stat = erg["statistik"]["HELP"]
    assert stat["anzahl"] == 3
    assert stat["max_s"] == pytest.approx(100.0)
    assert stat["median_s"] == pytest.approx(12.0)


def test_f003_antwort_geht_an_den_absender_des_eingangs():
    """Zwei Absender, zwei Eingaenge im selben Fenster. Die Antwort an B liegt der Dauer-Zeile
    von A zeitlich naeher als die eigene -- sie darf A trotzdem nicht zugeordnet werden."""
    erg = _werte(
        [_von(_ABS, "2026-10-27 09:00:00", "help"), _von(_ABS_B, "2026-10-27 09:00:02", "codes")],
        [_aus("2026-10-27 09:00:05.900", "Commands (A)"),
         _an(_ABS_B, "2026-10-27 09:00:04.900", "Codes (B)")],
        [_dauer("2026-10-27T08:00:05.000000", "HELP", 100),
         _dauer("2026-10-27T08:00:06.000000", "CODES", 100)],
    )
    a = _eintrag(erg, "2026-10-27T08:00:00")
    b = _eintrag(erg, "2026-10-27T08:00:02")
    assert (a["befehl"], b["befehl"]) == ("HELP", "CODES")
    assert a["antwort"] == _utc("2026-10-27T08:00:05.900")
    assert b["antwort"] == _utc("2026-10-27T08:00:04.900")


def test_f003_nachricht_einer_fremden_nummer_an_den_absender_ist_keine_antwort():
    """Eine Nachricht VON einer anderen Nummer AN den Absender liegt der Dauer-Zeile naeher
    als die echte Antwort der Servicenummer -- sie darf nicht als Antwort gelten."""
    fremd = {**_aus("2026-10-27 09:00:05.000", "Werbung"), "from": "+49000FREMD"}
    erg = _werte([_ein("2026-10-27 09:00:00", "help")],
                 [fremd, _aus("2026-10-27 09:00:05.900", "Commands")],
                 [_dauer("2026-10-27T08:00:05.000000", "HELP", 100)])
    assert _eintrag(erg, "2026-10-27T08:00:00")["antwort"] == _utc("2026-10-27T08:00:05.900")


def test_f003_antwort_jenseits_von_30_sekunden_zur_dauer_zeile_gilt_nicht():
    erg = _werte([_ein("2026-10-27 09:00:00", "help")],
                 [_aus("2026-10-27 09:00:46", "spaeter, fremd")],
                 [_dauer("2026-10-27T08:00:01.000000", "HELP", 100)])
    b = _eintrag(erg, "2026-10-27T08:00:00")
    assert b["befehl"] == "HELP" and b["dauer_ms"] == 100
    assert b["antwort"] is None and b["antwortzeit_s"] is None


def test_f003_eine_antwort_gehoert_nur_einem_eingang_mit_dauer_zeile():
    """Zwei Eingaenge, zwei Dauer-Zeilen, aber nur EINE Antwort im Journal."""
    erg = _werte([_ein("2026-10-27 09:00:00", "heute"), _ein("2026-10-27 09:00:05", "help")],
                 [_aus("2026-10-27 09:00:11", "E4: ...")],
                 [_dauer("2026-10-27T08:00:10.000000", "HEUTE", 100),
                  _dauer("2026-10-27T08:00:12.000000", "HELP", 100)])
    antworten = [b["antwort"] for b in erg["befehle"] if b["antwort"]]
    assert antworten == [_utc("2026-10-27T08:00:11")]


def test_f003_von_der_dauer_zeile_vergebene_antwort_geht_nicht_nochmal_an_spaeteren_eingang():
    """E1 (mit Dauer-Zeile) nimmt die Antwort 09:00:40; E2 (ohne Dauer-Zeile, spaeter, selber
    Absender) darf sie nicht ein zweites Mal bekommen."""
    erg = _werte([_ein("2026-10-27 09:00:00", "heute"), _ein("2026-10-27 09:00:10", "codes")],
                 [_aus("2026-10-27 09:00:40", "E4: ...")],
                 [_dauer("2026-10-27T08:00:40.000000", "HEUTE", 39000)])
    e1 = _eintrag(erg, "2026-10-27T08:00:00")
    e2 = _eintrag(erg, "2026-10-27T08:00:10")
    assert e1["antwort"] == _utc("2026-10-27T08:00:40")
    assert e2["antwort"] is None


# ---------------------------------------------------------------------------
# Fix-Loop 2 (Validierung V001): ein Eingang ohne eigene Dauer-Zeile ("hallo") darf die
# Dauer-Zeile des echten Befehls nicht stehlen -- der Befehl der Dauer-Zeile muss zum
# Text-Befehl des Eingangs passen.
# ---------------------------------------------------------------------------

def test_v001_eingang_ohne_dauer_zeile_stiehlt_nicht_die_dauer_des_folgebefehls():
    erg = _werte([_ein("2026-10-27 09:00:00", "hallo"), _ein("2026-10-27 09:00:05", "heute")],
                 [_aus("2026-10-27 09:00:41.300", "E4: W- WD:NW ...")],
                 [_dauer("2026-10-27T08:00:41.500000", "HEUTE", 36000)])
    heute = _eintrag(erg, "2026-10-27T08:00:05")
    hallo = _eintrag(erg, "2026-10-27T08:00:00")
    assert heute["befehl"] == "HEUTE" and heute["dauer_ms"] == 36000
    assert heute["antwort"] == _utc("2026-10-27T08:00:41.300")
    assert heute["antwortzeit_s"] == pytest.approx(36.3, abs=0.001)
    assert hallo["dauer_ms"] is None
    assert hallo["antwort"] is None and hallo["antwortzeit_s"] is None
    assert erg["statistik"]["HEUTE"]["max_s"] == pytest.approx(36.3, abs=0.001)
    assert erg["statistik"]["HEUTE"]["median_s"] == pytest.approx(36.3, abs=0.001)


def test_v001_gespiegelt_spaeterer_eingang_ohne_dauer_zeile_bekommt_sie_auch_nicht():
    """Schuetzt vor der Schein-Loesung 'spaetester Eingang vor dem Start'."""
    erg = _werte([_ein("2026-10-27 09:00:00", "heute"), _ein("2026-10-27 09:00:05", "hallo")],
                 [_aus("2026-10-27 09:00:41.300", "E4: W- WD:NW ...")],
                 [_dauer("2026-10-27T08:00:41.500000", "HEUTE", 36000)])
    heute = _eintrag(erg, "2026-10-27T08:00:00")
    hallo = _eintrag(erg, "2026-10-27T08:00:05")
    assert heute["befehl"] == "HEUTE" and heute["dauer_ms"] == 36000
    assert heute["antwort"] == _utc("2026-10-27T08:00:41.300")
    assert heute["antwortzeit_s"] == pytest.approx(41.3, abs=0.001)
    assert hallo["dauer_ms"] is None
    assert hallo["antwort"] is None and hallo["antwortzeit_s"] is None


# ---------------------------------------------------------------------------
# Fix-Loop 1 zu V001 (Adversary F001/F002): Texterkennung wie im Prozessor
# (erste Zeile, Zitat/Slash, ###, Satzzeichen), Einmalzuordnung je Eingang.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text, befehl", [
    ("Heute!", "HEUTE"),
    ("Heute.", "HEUTE"),
    ("/heute", "HEUTE"),
    ("> heute", "HEUTE"),
    ("### heute", "HEUTE"),
    ("XXCJD224 Heute!", "HEUTE"),
    ("Hilfe?", "HELP"),
])
def test_f001_eingang_mit_satzzeichen_oder_praefix_bekommt_seine_dauer_zeile(text, befehl):
    erg = _werte([_ein("2026-10-27 09:00:00", text)],
                 [_aus("2026-10-27 09:00:10", "...")],
                 [_dauer("2026-10-27T08:00:10.200000", befehl, 9000)])
    b = _eintrag(erg, "2026-10-27T08:00:00")
    assert (b["befehl"], b["dauer_ms"]) == (befehl, 9000)
    assert b["antwort"] == _utc("2026-10-27T08:00:10")


@pytest.mark.parametrize("text", ["Heute!", "/heute", "> heute", "XXCJD224 Heute!"])
def test_f001_befehl_ohne_dauer_zeile_ist_normalisiert(text):
    """Aeltere Daten ohne Dauer-Zeile: kein eigener Statistik-Schluessel 'HEUTE!'."""
    erg = _werte([_ein("2026-10-27 09:00:00", text)], [_aus("2026-10-27 09:00:10", "...")], [])
    assert _eintrag(erg, "2026-10-27T08:00:00")["befehl"] == "HEUTE"
    assert set(erg["statistik"]) == {"HEUTE"}


def test_f002_zwei_gleiche_befehle_bekommen_je_ihre_eigene_dauer_zeile():
    erg = _werte([_ein("2026-10-27 09:00:00", "heute"), _ein("2026-10-27 09:00:20", "heute")],
                 [],
                 [_dauer("2026-10-27T08:00:30.000000", "HEUTE", 5000),
                  _dauer("2026-10-27T08:00:45.000000", "HEUTE", 10000)])
    assert _eintrag(erg, "2026-10-27T08:00:00")["dauer_ms"] == 5000
    assert _eintrag(erg, "2026-10-27T08:00:20")["dauer_ms"] == 10000


@pytest.mark.parametrize("dauer_zeile", [
    # passender Befehl, aber Start 700 s nach dem Eingang (ausserhalb 600 s)
    _dauer("2026-10-27T08:11:41.000000", "HEUTE", 1000),
    # im Fenster, aber anderer Befehl
    _dauer("2026-10-27T08:00:10.000000", "HELP", 100),
])
def test_f002_dauer_zeile_ohne_passenden_eingang_wird_niemandem_zugeordnet(dauer_zeile):
    erg = _werte([_ein("2026-10-27 09:00:00", "heute")], [], [dauer_zeile])
    b = _eintrag(erg, "2026-10-27T08:00:00")
    assert b["dauer_ms"] is None and b["befehl"] == "HEUTE"


# ---------------------------------------------------------------------------
# Fix-Loop 2 zu V001 (Adversary F004-F006): Code-Abtrennung wie der Reader
# (`split_link_code` auf dem GANZEN Text), erste Zeile, reiner Code, Aliase ohne Dauer-Zeile.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", ["XXCJD224\nheute", "### heute\nViele Gruesse\nHenning"])
def test_f004_f005_befehl_in_erster_zeile_bzw_nach_code_zeile_bekommt_dauer(text):
    erg = _werte([_ein("2026-10-27 09:00:00", text)], [],
                 [_dauer("2026-10-27T08:00:10.200000", "HEUTE", 9000)])
    b = _eintrag(erg, "2026-10-27T08:00:00")
    assert (b["befehl"], b["dauer_ms"]) == ("HEUTE", 9000)


@pytest.mark.parametrize("text", ["xx heute", "XX1 > heute"])
def test_f004_kein_code_in_code_gestalt_ist_kein_befehl(text):
    """Der Prozessor erkennt hier keinen Befehl (UNKNOWN). Fix-Loop 3: ein UNKNOWN-Eingang
    ist nur noch RUECKFALL -- steht ein echtes "heute" im Fenster, gewinnt dieses."""
    erg = _werte([_ein("2026-10-27 09:00:00", text)], [], [])
    assert _eintrag(erg, "2026-10-27T08:00:00")["befehl"] == "UNKNOWN"
    erg = _werte([_ein("2026-10-27 09:00:00", text), _ein("2026-10-27 09:00:05", "heute")], [],
                 [_dauer("2026-10-27T08:00:15.200000", "HEUTE", 9000)])
    b = _eintrag(erg, "2026-10-27T08:00:00")
    assert b["dauer_ms"] is None and b["befehl"] == "UNKNOWN"
    assert _eintrag(erg, "2026-10-27T08:00:05")["dauer_ms"] == 9000


def test_f005_reiner_code_ohne_befehl_bricht_nicht_ab():
    erg = _werte([_ein("2026-10-27 09:00:00", "XXCJD224")], [], [])
    b = _eintrag(erg, "2026-10-27T08:00:00")
    assert b["befehl"] == "UNKNOWN" and b["dauer_ms"] is None


@pytest.mark.parametrize("text, befehl", [("hilfe", "HELP"), ("Tomorrow", "MORGEN"),
                                          ("XXCJD224 kuerzel", "CODES")])
def test_f006_befehl_ohne_dauer_zeile_traegt_den_journalnamen(text, befehl):
    erg = _werte([_ein("2026-10-27 09:00:00", text)], [_aus("2026-10-27 09:00:10", "...")], [])
    assert _eintrag(erg, "2026-10-27T08:00:00")["befehl"] == befehl
    assert set(erg["statistik"]) == {befehl}


# ---------------------------------------------------------------------------
# Fix-Loop 3 zu V001 (Adversary F007/F008): Zuordnungsregel
#   1. Vorrang: exakter Befehl,  2. Rueckfall: UNKNOWN-Eingang,  3. nie ein ANDERER Befehl.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("text", ["GR20 heute", "XXAAA234 GR20 heute"])
def test_f007_trip_name_vor_dem_befehl_bekommt_die_dauer_zeile_im_rueckfall(text):
    erg = _werte([_ein("2026-10-27 09:00:00", text)], [_aus("2026-10-27 09:00:10", "...")],
                 [_dauer("2026-10-27T08:00:10.200000", "HEUTE", 9000)])
    b = _eintrag(erg, "2026-10-27T08:00:00")
    assert (b["befehl"], b["dauer_ms"]) == ("HEUTE", 9000)
    assert b["antwort"] == _utc("2026-10-27T08:00:10")
    assert set(erg["statistik"]) == {"HEUTE"}


@pytest.mark.parametrize("text", ["wind", "Temp"])
def test_f007_metrik_wort_passt_exakt_zur_metrik_dauer_zeile(text):
    erg = _werte([_ein("2026-10-27 09:00:00", text)], [],
                 [_dauer("2026-10-27T08:00:10.200000", "METRIK", 900)])
    b = _eintrag(erg, "2026-10-27T08:00:00")
    assert (b["befehl"], b["dauer_ms"]) == ("METRIK", 900)


def test_f007_metrik_wort_ohne_dauer_zeile_heisst_metrik():
    erg = _werte([_ein("2026-10-27 09:00:00", "wind")], [], [])
    assert _eintrag(erg, "2026-10-27T08:00:00")["befehl"] == "METRIK"


def test_f007_exakter_treffer_hat_vorrang_vor_unknown_eingaengen():
    erg = _werte([_ein("2026-10-27 09:00:00", "hallo"), _ein("2026-10-27 09:00:03", "GR20 heute"),
                  _ein("2026-10-27 09:00:05", "heute")], [],
                 [_dauer("2026-10-27T08:00:41.500000", "HEUTE", 36000)])
    assert _eintrag(erg, "2026-10-27T08:00:05")["dauer_ms"] == 36000
    assert _eintrag(erg, "2026-10-27T08:00:00")["dauer_ms"] is None
    assert _eintrag(erg, "2026-10-27T08:00:03")["dauer_ms"] is None


def test_f007_anderer_bekannter_befehl_bekommt_die_dauer_zeile_nie():
    erg = _werte([_ein("2026-10-27 09:00:00", "hilfe")], [],
                 [_dauer("2026-10-27T08:00:10.200000", "HEUTE", 9000)])
    b = _eintrag(erg, "2026-10-27T08:00:00")
    assert (b["befehl"], b["dauer_ms"]) == ("HELP", None)


@pytest.mark.parametrize("text, befehl", [("ABBRUCH", "ABBRUCH"), ("CANCEL", "ABBRUCH"),
                                          ("Abbrechen", "UNKNOWN"),
                                          ("### abbruch", "ABBRUCH"), ("stop", "ABBRUCH")])
def test_f008_nacktes_abbruch_ist_wie_im_prozessor(text, befehl):
    """Bare-Pfad nur ueber `_BARE_KEYWORD_MAP` (seit #2673 kennt sie ABBRUCH/CANCEL
    als Alias von STOP); der `###`-Pfad nimmt wie `_parse_command` jedes Wort als
    Schluessel; ein Fremdwort bleibt UNKNOWN."""
    erg = _werte([_ein("2026-10-27 09:00:00", text)], [], [])
    assert _eintrag(erg, "2026-10-27T08:00:00")["befehl"] == befehl


# ---------------------------------------------------------------------------
# Loop 4 (Adversary F009/F011): Kanalfilter, Fenstergrenze, Startzeit = ts - dauer_ms
# ---------------------------------------------------------------------------

def test_f009_telegram_dauer_zeile_gehoert_nie_zu_einem_sms_eingang():
    telegram = ("2026-10-27T08:00:10.000000+00:00 Rennwienix uv[1]: x INFO befehl_dauer: "
                "befehl=HEUTE kanal=telegram trip=khw-403 dauer_ms=100")
    erg = _werte([_ein("2026-10-27 09:00:00", "heute")], [], [telegram])
    b = _eintrag(erg, "2026-10-27T08:00:00")
    assert b["befehl"] == "HEUTE" and b["dauer_ms"] is None


def test_f011_eingang_nach_dem_start_der_dauer_zeile_bekommt_sie_nicht():
    """Start = 08:00:30 - 20 s = 08:00:10; der Eingang 08:00:20 kam erst danach."""
    erg = _werte([_ein("2026-10-27 09:00:20", "heute")], [],
                 [_dauer("2026-10-27T08:00:30.000000", "HEUTE", 20000)])
    assert _eintrag(erg, "2026-10-27T08:00:20")["dauer_ms"] is None


def test_f011_lange_dauer_bringt_den_eingang_erst_ueber_ts_minus_ms_ins_fenster():
    """Ende 08:10:30, 330 s Dauer => Start 08:05:00; der Eingang 08:00:00 liegt im Fenster
    [Start - 600 s, Start], aber NICHT in [Ende - 600 s, Ende]."""
    erg = _werte([_ein("2026-10-27 09:00:00", "heute")], [],
                 [_dauer("2026-10-27T08:10:30.000000", "HEUTE", 330000)])
    assert _eintrag(erg, "2026-10-27T08:00:00")["dauer_ms"] == 330000


def test_f011_ueberlappende_gleiche_befehle_werden_nach_start_nicht_nach_ende_zugeordnet():
    """X: Start 08:00:05, Ende 08:01:00 (nur A davor). Y: Start 08:00:15, Ende 08:00:20.
    Nach Ende sortiert kaeme Y zuerst und naehme A -- X faende dann keinen Eingang mehr."""
    erg = _werte([_ein("2026-10-27 09:00:00", "heute"), _ein("2026-10-27 09:00:10", "heute")], [],
                 [_dauer("2026-10-27T08:01:00.000000", "HEUTE", 55000),
                  _dauer("2026-10-27T08:00:20.000000", "HEUTE", 5000)])
    assert _eintrag(erg, "2026-10-27T08:00:00")["dauer_ms"] == 55000
    assert _eintrag(erg, "2026-10-27T08:00:10")["dauer_ms"] == 5000
