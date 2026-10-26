#!/usr/bin/env python3
"""Prod-Lese-Werkzeug: Antwortzeit der Befehle je Kanal (#2439, Spec §7). Nur lesend.

Liest (1) das seven.io-Journal inbound/outbound, (2) die Dauer-Zeilen
`befehl=… kanal=… trip=… dauer_ms=…` aus dem Prod-Journal `gregor-python`, (3) den
Push-Status von Prod (`/api/scheduler/status`). Versendet nichts, schreibt nichts.
Schluessel und Token kommen aus der Konfiguration und werden nie ausgegeben; Rufnummern
erscheinen nicht in der Ausgabe.

Aufruf NUR mit `uv run` (braucht die Projekt-venv: die Befehlserkennung kommt aus
`src/services/trip_command_processor.py`; ohne venv ModuleNotFoundError):
    uv run python3 .claude/tools/befehl_antwortzeit.py --since 2026-10-20 [--kanal premium_sms|telegram|email]
        [--trip <id>] [--ziel]
Je Lauf wird die Quelle/Kaltheit (`fr_direct`|`dwd`|`warm`) aus den Fensterzeilen abgeleitet.
`--ziel` prueft die Zielgroessen (kalte HEUTE/MORGEN-Laeufe) und liefert Exit-Code
0 (bestanden) / 1 (verfehlt) / 2 (nicht belegt); ohne `--ziel` immer 0.
"""
from __future__ import annotations

import argparse
import os
import statistics
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parent))
import befehl_messlogik as ml  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
# Eine Quelle fuer Texterkennung und Journalnamen: dieselben Funktionen wie Reader/Prozessor.
from services.trip_command_processor import (  # noqa: E402
    TripCommandProcessor, _befehlsname, _erstes_wort, _metric_id_for_word,
)
from services.inbound_sms_reader import split_link_code  # noqa: E402

_PARSER = TripCommandProcessor()  # nur `_parse_command`, wie `_ParseNurProcessor` im Reader

BERLIN = ZoneInfo("Europe/Berlin")
BRUECKE_FENSTER_S = 600
ANTWORT_NAHE_S = 30
PUSH_VOR_S, PUSH_NACH_S = 5, 60
STATUS_URL = "http://127.0.0.1:8090/api/scheduler/status"
JOB_JE_KANAL = {"premium_sms": "premium_sms_poll", "email": "inbound_command_poll"}
KANAL_GRUPPEN = {"premium_sms": {"premium_sms", "sms"}, "telegram": {"telegram"},
                 "email": {"email"}}  # SMS-Eingang laeuft ueber den Rueckkanal (wie Staging-Test)

# Zielgroessen (Haupt-Spec feat_2439_befehle_antwortzeit AC-4/AC-5; gleichlautend mit
# tests/e2e/test_push_eingang_befehle_staging.py) -- nicht lockern.
GRENZE_MIT_WETTER_MS = 60_000
GRENZE_MEDIAN_MS = 45_000
MIN_LAEUFE_KORSIKA = 3
MIN_LAEUFE_WETTER = 5
ZIEL_BEFEHLE = ("HEUTE", "MORGEN")
MINDESTZAHL_JE_QUELLE = {"fr_direct": MIN_LAEUFE_KORSIKA, "dwd": MIN_LAEUFE_WETTER}


def _seven_zeit(text: str) -> datetime:
    """seven.io-Zeitstempel sind zonenlos und in Ortszeit Europe/Berlin."""
    return datetime.fromisoformat(text.replace(" ", "T")).replace(tzinfo=BERLIN).astimezone(
        timezone.utc)


def _befehl_aus_text(text: str) -> str:
    """Journalname des Befehls wie in der Dauer-Zeile: `split_link_code` (Reader), dann
    `_parse_command` + METRIK/`_befehlsname` wie `TripCommandProcessor._logge_dauer`.
    Was so nicht deutbar ist (z. B. Trip-Name vor dem Befehl), wird UNKNOWN."""
    _, befehl = split_link_code(text or "")
    key, value = _PARSER._parse_command(befehl)
    if key is None and _metric_id_for_word(_erstes_wort(befehl)):
        return "METRIK"
    return _befehlsname(key, value)


def _ziel_fuer_dauerzeile(frei_im_fenster: list[dict], befehl: str) -> dict | None:
    """V001/F007: Vorrang der frueheste Eingang mit EXAKT diesem Befehl; Rueckfall der
    frueheste UNKNOWN-Eingang; ein Eingang mit ANDEREM bekanntem Befehl nie."""
    for gesucht in (befehl, "UNKNOWN"):
        ziel = next((e for e in frei_im_fenster if e["erkannt"] == gesucht), None)
        if ziel is not None:
            return ziel
    return None


def _push_passt(push, eingang: datetime) -> bool:
    empfangen = (push or {}).get("last_received")
    if not empfangen:
        return False
    abstand = (datetime.fromisoformat(empfangen) - eingang).total_seconds()
    return -PUSH_VOR_S <= abstand <= PUSH_NACH_S


def _statistik(befehle: list[dict]) -> dict:
    je_befehl: dict[str, list[float]] = {}
    for b in befehle:
        if b["antwortzeit_s"] is not None:
            je_befehl.setdefault(b["befehl"], []).append(b["antwortzeit_s"])
    return {name: {"anzahl": len(w), "max_s": max(w), "median_s": statistics.median(w)}
            for name, w in je_befehl.items()}


def _antwort_waehlen(eingang: dict, frei: list[dict], ziel: datetime | None,
                     bis: datetime | None) -> dict | None:
    """Freier outbound von der Servicenummer an den Absender.

    Mit `ziel`: der zeitlich naechste (|Abstand| <= 30 s). Ohne: der erste nach dem Eingang
    und vor `bis` (naechster Eingang desselben Absenders).
    """
    kandidaten = [a for a in frei if a["von"] == eingang["service"] and a["an"] == eingang["absender"]]
    if ziel is not None:
        kandidaten = [a for a in kandidaten
                      if abs((a["ts"] - ziel).total_seconds()) <= ANTWORT_NAHE_S]
        return min(kandidaten, key=lambda a: abs((a["ts"] - ziel).total_seconds()), default=None)
    kandidaten = [a for a in kandidaten
                  if a["ts"] >= eingang["eingang"] and (bis is None or a["ts"] < bis)]
    return min(kandidaten, key=lambda a: a["ts"], default=None)


def auswerten(inbound, outbound, dauerzeilen, push=None) -> dict:
    """Ordnet jedem Eingang Befehl, Antwort, Dauer und Push-Zuordnung zu (siehe Tests)."""
    eingaenge = sorted(
        ({"eingang": _seven_zeit(m["timestamp"]), "absender": m.get("from"),
          "service": m.get("to"), "text": m.get("text", ""), "befehl": None,
          "erkannt": _befehl_aus_text(m.get("text", "")),
          "antwort": None, "dauer_ms": None} for m in inbound),
        key=lambda e: e["eingang"])
    frei = [{"ts": _seven_zeit(m["timestamp"]), "von": m.get("from"), "an": m.get("to")}
            for m in outbound]

    sms = [d for d in dauerzeilen if d["kanal"] in ("premium_sms", "sms")]
    for dz in sorted(sms, key=lambda d: d["ts"] - timedelta(milliseconds=d["ms"])):
        start = dz["ts"] - timedelta(milliseconds=dz["ms"])
        ziel = _ziel_fuer_dauerzeile(
            [e for e in eingaenge if e["befehl"] is None and e["eingang"] <= start
             and e["eingang"] >= start - timedelta(seconds=BRUECKE_FENSTER_S)], dz["befehl"])
        if ziel is None:
            continue
        ziel["befehl"], ziel["dauer_ms"] = dz["befehl"], dz["ms"]
        antwort = _antwort_waehlen(ziel, frei, dz["ts"], None)
        if antwort:
            ziel["antwort"] = antwort["ts"]
            frei.remove(antwort)

    for i, e in enumerate(eingaenge):
        if e["befehl"] is not None:
            continue
        e["befehl"] = e["erkannt"]
        spaeter = [x["eingang"] for x in eingaenge[i + 1:] if x["absender"] == e["absender"]]
        antwort = _antwort_waehlen(e, frei, None, spaeter[0] if spaeter else None)
        if antwort:
            e["antwort"] = antwort["ts"]
            frei.remove(antwort)

    befehle = [{
        "befehl": e["befehl"], "kanal": "premium_sms", "eingang": e["eingang"],
        "antwort": e["antwort"],
        "antwortzeit_s": ml.antwortzeit_aus_journalen(e["eingang"], e["antwort"])
        if e["antwort"] else None,
        "dauer_ms": e["dauer_ms"], "push_zugeordnet": _push_passt(push, e["eingang"]),
    } for e in eingaenge]
    return {"befehle": befehle, "statistik": _statistik(befehle)}


def kaltheit_je_lauf(dauerzeilen: list[dict], journal, trip: str | None = None) -> list[dict]:
    """Je Lauf (optional nur Trip `trip`) die Quelle: "fr_direct", wenn im Befehlsfenster ein
    `fr_direct_fenster` mit downloads>0 steht, sonst "dwd" bei `dwd_fenster`, sonst "warm".
    Abgeleitet ueber `ml.kalt_laeufe` -- kein Quellenfeld in der Dauerzeile."""
    laeufe = [d for d in dauerzeilen if trip is None or d["trip"] == trip]
    fr = {id(lauf) for lauf in ml.kalt_laeufe(laeufe, journal, quellen=("fr_direct_fenster",))}
    dwd = {id(lauf) for lauf in ml.kalt_laeufe(laeufe, journal, quellen=("dwd_fenster",))}
    return [{**lauf, "quelle": "fr_direct" if id(lauf) in fr
             else "dwd" if id(lauf) in dwd else "warm"} for lauf in laeufe]


def _status(werte: list[int], mindestzahl: int) -> str:
    """Ein Einzellauf >= Grenze verfehlt immer; der Median ist erst ab der Mindestzahl
    aussagekraeftig (darunter: nicht belegt)."""
    if werte and max(werte) >= GRENZE_MIT_WETTER_MS:
        return "verfehlt"
    if len(werte) < mindestzahl:
        return "nicht belegt"
    return "verfehlt" if statistics.median(werte) >= GRENZE_MEDIAN_MS else "bestanden"


def pruefe_ziel(laeufe: list[dict]) -> list[dict]:
    """Zielgroessen je (Befehl, Quelle), nur HEUTE/MORGEN und nur kalte Laeufe: jeder Lauf
    < 60 000 ms und Median < 45 000 ms; Mindestzahl fr_direct 3 (AC-5), dwd 5 (AC-4).
    "verfehlt" hat Vorrang vor "nicht belegt"."""
    gruppen: dict[tuple[str, str], list[int]] = {}
    for lauf in laeufe:
        if lauf["befehl"] in ZIEL_BEFEHLE and lauf["quelle"] in MINDESTZAHL_JE_QUELLE:
            gruppen.setdefault((lauf["befehl"], lauf["quelle"]), []).append(lauf["ms"])
    for quelle in {q for _, q in gruppen}:  # fehlender Befehl je Quelle: nicht belegt
        for befehl in ZIEL_BEFEHLE:
            gruppen.setdefault((befehl, quelle), [])
    return [{"befehl": befehl, "quelle": quelle, "anzahl": len(werte), "werte_ms": werte,
             "median_ms": statistics.median(werte) if werte else None,
             "status": _status(werte, MINDESTZAHL_JE_QUELLE[quelle])}
            for (befehl, quelle), werte in sorted(gruppen.items())]


def ziel_exitcode(ergebnisse: list[dict]) -> int:
    """0 nur wenn alle Gruppen bestanden; 1 bei einer verfehlten; sonst 2 (auch: nichts
    geprueft -- das ist nie "bestanden")."""
    status = {e["status"] for e in ergebnisse}
    if "verfehlt" in status:
        return 1
    return 0 if status == {"bestanden"} else 2


# ---------------------------------------------------------------------------
# Lesende Anbindung (nur CLI; nicht Teil der Kern-Tests)
# ---------------------------------------------------------------------------

def _konfig(name: str) -> str:
    wert = os.environ.get(name)
    if not wert:
        from dotenv import dotenv_values
        for pfad in (Path.cwd() / ".env", Path("/home/hem/gregor_zwanzig/.env")):
            if pfad.is_file() and not wert:
                wert = dotenv_values(pfad).get(name)
    if not wert:
        sys.exit(f"{name} nicht gefunden (Umgebung oder .env).")
    return wert


def _seven_journal(kind: str, since: str) -> list[dict]:
    import httpx
    antwort = httpx.get(f"https://gateway.seven.io/api/journal/{kind}",
                        headers={"X-Api-Key": _konfig("GZ_SEVEN_API_KEY")},
                        params={"limit": 100, "date_from": since}, timeout=20)
    daten = antwort.json() if antwort.status_code == 200 else None
    if not isinstance(daten, list):
        sys.exit(f"seven.io-Journal {kind}: HTTP {antwort.status_code}")
    return daten


def _prod_journal(since: str) -> list[tuple[datetime, str]]:
    """Rohe Journalzeilen (Dauer- UND Fensterzeilen), damit die Kaltheit ableitbar ist."""
    erg = subprocess.run(["journalctl", "-u", "gregor-python", "--since", since, "--no-pager",
                          "-o", "short-iso-precise"], capture_output=True, text=True, timeout=60)
    if erg.returncode != 0:
        sys.exit(f"journalctl gregor-python nicht lesbar: {erg.stderr[:200]}")
    return ml.lese_journal(erg.stdout.splitlines())


def _push_status(job_id: str) -> dict | None:
    import httpx
    antwort = httpx.get(STATUS_URL, headers={"X-GZ-Status-Token": _konfig("GZ_STATUS_TOKEN")},
                        timeout=15)
    for job in antwort.json().get("jobs", []):
        if job.get("id") == job_id:
            return job.get("push")
    return None


def _ausgabe_dauer_kanal(laeufe: list[dict], kanal: str) -> None:
    """Je Lauf: Zeit, Befehl, Kanal, Trip, Dauer, Quelle/Kaltheit (SMS-Eingang zaehlt zu
    premium_sms, er laeuft ueber denselben Rueckkanal)."""
    je_befehl: dict[str, list[int]] = {}
    for d in laeufe:
        if d["kanal"] in KANAL_GRUPPEN[kanal]:
            print(f"{d['ts'].isoformat()} {d['befehl']} {d['kanal']} trip={d['trip']} "
                  f"{d['ms']} ms quelle={d['quelle']}")
            je_befehl.setdefault(d["befehl"], []).append(d["ms"])
    for name, werte in sorted(je_befehl.items()):
        print(f"{name}: n={len(werte)} max={max(werte)} ms median={statistics.median(werte)} ms")


def _ausgabe_premium_sms(since: str, laeufe: list[dict]) -> None:
    push = _push_status(JOB_JE_KANAL["premium_sms"])
    erg = auswerten(_seven_journal("inbound", since),
                    _seven_journal("outbound", since), laeufe, push=push)
    for b in erg["befehle"]:
        print(f"{b['eingang'].isoformat()} {b['befehl']} antwort={b['antwort'] and b['antwort'].isoformat()} "
              f"antwortzeit_s={b['antwortzeit_s']} dauer_ms={b['dauer_ms']} push={b['push_zugeordnet']}")
    for name, s in sorted(erg["statistik"].items()):
        print(f"{name}: n={s['anzahl']} max={s['max_s']:.1f} s median={s['median_s']:.1f} s")


def _ausgabe_ziel(ergebnisse: list[dict], laeufe: list[dict]) -> None:
    print("== Zielgroessen-Pruefung (kalte HEUTE/MORGEN-Laeufe) ==")
    for e in ergebnisse:
        kanaele: dict[str, int] = {}
        for lauf in laeufe:
            if lauf["befehl"] == e["befehl"] and lauf["quelle"] == e["quelle"]:
                kanaele[lauf["kanal"]] = kanaele.get(lauf["kanal"], 0) + 1
        zusatz = " (Median-Grenze fuer Korsika zusaetzlich, strenger als Haupt-Spec AC-5)" \
            if e["quelle"] == "fr_direct" else ""
        print(f"{e['befehl']} quelle={e['quelle']}: {e['status']} n={e['anzahl']} "
              f"werte_ms={e['werte_ms']} median_ms={e['median_ms']} kanaele={kanaele}{zusatz}")
    if not ergebnisse:
        print("keine kalten HEUTE/MORGEN-Laeufe -- nicht belegt")


def _argumente(argv: list[str] | None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--since", required=True, help="JJJJ-MM-TT")
    parser.add_argument("--kanal", choices=["premium_sms", "telegram", "email"])
    parser.add_argument("--trip", help="nur Laeufe dieser Trip-ID")
    parser.add_argument("--ziel", action="store_true",
                        help="Zielgroessen pruefen (Exit 0 bestanden, 1 verfehlt, 2 nicht belegt)")
    parser.add_argument("--journal-datei", help="Offline: Journal aus Datei statt journalctl; "
                        "ohne seven.io/Push-Zugriff")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _argumente(argv)
    offline = bool(args.journal_datei)
    journal = (ml.lese_journal(Path(args.journal_datei).read_text("utf-8").splitlines())
               if offline else _prod_journal(args.since))
    laeufe = kaltheit_je_lauf(ml.dauerzeilen(journal), journal, trip=args.trip)
    for kanal in ([args.kanal] if args.kanal else ["premium_sms", "telegram", "email"]):
        print(f"== {kanal} ==")
        _ausgabe_dauer_kanal(laeufe, kanal)
        if kanal == "premium_sms" and not offline:
            _ausgabe_premium_sms(args.since, laeufe)
    if not args.ziel:
        return 0
    if args.kanal:  # Pruefung "je Kanal": nur Laeufe dieser Kanalgruppe
        laeufe = [lauf for lauf in laeufe if lauf["kanal"] in KANAL_GRUPPEN[args.kanal]]
    ergebnisse = pruefe_ziel(laeufe)
    _ausgabe_ziel(ergebnisse, laeufe)
    return ziel_exitcode(ergebnisse)


if __name__ == "__main__":
    raise SystemExit(main())
