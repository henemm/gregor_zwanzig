"""Reine Auswertelogik fuer die Befehls-Antwortzeit-Messung (#2439, Spec §6).

Kein Netz, kein Journal-Zugriff: nur Funktionen auf bereits gelesenen Zeilen. Wird vom
Live-Test ``tests/e2e/test_push_eingang_befehle_staging.py`` UND vom Prod-Lese-Werkzeug
``befehl_antwortzeit.py`` gemeinsam genutzt.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

_ZEILE_DAUER = re.compile(r"befehl=(\S+) kanal=(\S+) trip=(\S+) dauer_ms=(\d+)")
_ZEILE_FENSTER = re.compile(r"\b(\w+_fenster) fenster_s=[\d.]+ downloads=(\d+) cache_treffer=\d+")
STANDARD_QUELLEN = ("dwd_fenster", "fr_direct_fenster")


def _zeit(text: str) -> datetime | None:
    """ISO-Zeit aus `journalctl -o short-iso-precise` (`+00:00` oder `+0000`) -> UTC."""
    try:
        zeit = datetime.fromisoformat(text)
    except ValueError:
        try:
            zeit = datetime.strptime(text, "%Y-%m-%dT%H:%M:%S.%f%z")
        except ValueError:
            return None
    if zeit.tzinfo is None:
        return None
    return zeit.astimezone(timezone.utc)


def lese_journal(zeilen) -> list[tuple[datetime, str]]:
    """Journalzeilen -> [(Zeit UTC, Rest der Zeile)]; Zeilen ohne Zeitstempel entfallen."""
    erg = []
    for roh in zeilen:
        kopf, _, rest = roh.partition(" ")
        zeit = _zeit(kopf)
        if zeit is not None:
            erg.append((zeit, rest))
    return erg


def dauerzeilen(journal) -> list[dict]:
    """Dauer-Zeilen `befehl=… kanal=… trip=… dauer_ms=…` (Phasen-Zeilen zaehlen nicht)."""
    treffer = []
    for zeit, text in journal:
        m = _ZEILE_DAUER.search(text)
        if m:
            treffer.append({"ts": zeit, "befehl": m.group(1), "kanal": m.group(2),
                            "trip": m.group(3), "ms": int(m.group(4))})
    return treffer


def paare_heute_help(laeufe, kanaele, max_abstand_s):
    """Paart ein HEUTE mit dem unmittelbar folgenden HELP desselben Eingangs.

    Bedingungen: der HELP liegt hoechstens `max_abstand_s` nach dem HEUTE-START und es
    liegt kein anderer Befehl desselben Eingangs dazwischen. HEUTE ohne Partner entfallen.
    """
    eingang = sorted((l for l in laeufe if l["kanal"] in kanaele), key=lambda l: l["ts"])
    paare = []
    for heute, naechster in zip(eingang, eingang[1:]):
        if heute["befehl"] != "HEUTE" or naechster["befehl"] != "HELP":
            continue
        start = heute["ts"] - timedelta(milliseconds=heute["ms"])
        if (naechster["ts"] - start).total_seconds() <= max_abstand_s:
            paare.append((heute, naechster))
    return paare


def kalt_laeufe(laeufe, fenster_zeilen, quellen=STANDARD_QUELLEN):
    """Laeufe, in deren Befehlsfenster eine Fensterzeile mit `downloads>0` steht.

    Massgeblich ist der Praefix der Zeile (`dwd_fenster`, `fr_direct_fenster`): eine
    Korsika-Zeile zaehlt nicht als DWD-Download und umgekehrt.
    """
    downloads = []
    for zeit, text in fenster_zeilen:
        m = _ZEILE_FENSTER.search(text)
        if m and m.group(1) in quellen and int(m.group(2)) > 0:
            downloads.append(zeit)
    kalt = []
    for lauf in laeufe:
        anfang = lauf["ts"] - timedelta(milliseconds=lauf["ms"])
        if any(anfang <= zeit <= lauf["ts"] for zeit in downloads):
            kalt.append(lauf)
    return kalt


def antwortzeit_aus_journalen(eingang_ts: datetime, ausgang_ts: datetime) -> float:
    """Sekunden vom Eingang bis zur Antwort."""
    return (ausgang_ts - eingang_ts).total_seconds()


def messung_ueberholt(job: dict, grenze_s: float = 60, takt_s: float = 300) -> bool:
    """True, wenn `last_run` nicht mehr den Poll-Lauf NACH dem Webhook zeigt.

    Ueberholt = Abstand `last_received` -> `last_run` ueberschreitet `grenze_s` UND zwischen
    beiden liegt ein `takt_s`-Tick (ein spaeterer Cron-Lauf hat `last_run` ueberschrieben).
    Fehlende Werte oder ein `last_run` vor dem Webhook sind NICHT ueberholt (Aufrufer prueft
    und wird rot).
    """
    empfangen = (job.get("push") or {}).get("last_received")
    gelaufen = (job.get("last_run") or {}).get("time")
    if not empfangen or not gelaufen:
        return False
    t_emp = datetime.fromisoformat(empfangen).timestamp()
    t_lauf = datetime.fromisoformat(gelaufen).timestamp()
    if t_lauf - t_emp <= grenze_s:
        return False
    naechster_tick = (t_emp // takt_s + 1) * takt_s
    return naechster_tick <= t_lauf
