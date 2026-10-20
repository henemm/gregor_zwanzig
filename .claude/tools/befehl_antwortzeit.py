#!/usr/bin/env python3
"""Prod-Lese-Werkzeug: Antwortzeit der Befehle je Kanal (#2439, Spec §7). Nur lesend.

Liest (1) das seven.io-Journal inbound/outbound, (2) die Dauer-Zeilen
`befehl=… kanal=… trip=… dauer_ms=…` aus dem Prod-Journal `gregor-python`, (3) den
Push-Status von Prod (`/api/scheduler/status`). Versendet nichts, schreibt nichts.
Schluessel und Token kommen aus der Konfiguration und werden nie ausgegeben; Rufnummern
erscheinen nicht in der Ausgabe.

Aufruf:
    uv run python3 .claude/tools/befehl_antwortzeit.py --since 2026-10-20 [--kanal premium_sms|telegram|email]
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

BERLIN = ZoneInfo("Europe/Berlin")
BRUECKE_FENSTER_S = 600
ANTWORT_NAHE_S = 30
PUSH_VOR_S, PUSH_NACH_S = 5, 60
STATUS_URL = "http://127.0.0.1:8090/api/scheduler/status"
JOB_JE_KANAL = {"premium_sms": "premium_sms_poll", "email": "inbound_command_poll"}


def _seven_zeit(text: str) -> datetime:
    """seven.io-Zeitstempel sind zonenlos und in Ortszeit Europe/Berlin."""
    return datetime.fromisoformat(text.replace(" ", "T")).replace(tzinfo=BERLIN).astimezone(
        timezone.utc)


def _befehl_aus_text(text: str) -> str:
    woerter = (text or "").strip().split()
    if woerter and woerter[0].upper().startswith("XX") and len(woerter) > 1:
        woerter = woerter[1:]
    return woerter[0].upper() if woerter else ""


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
          "antwort": None, "dauer_ms": None} for m in inbound),
        key=lambda e: e["eingang"])
    frei = [{"ts": _seven_zeit(m["timestamp"]), "von": m.get("from"), "an": m.get("to")}
            for m in outbound]

    sms = [d for d in dauerzeilen if d["kanal"] in ("premium_sms", "sms")]
    for dz in sorted(sms, key=lambda d: d["ts"] - timedelta(milliseconds=d["ms"])):
        start = dz["ts"] - timedelta(milliseconds=dz["ms"])
        ziel = next((e for e in eingaenge if e["befehl"] is None and e["eingang"] <= start
                     and e["eingang"] >= start - timedelta(seconds=BRUECKE_FENSTER_S)), None)
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
        e["befehl"] = _befehl_aus_text(e["text"])
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


def _prod_journal(since: str) -> list[dict]:
    erg = subprocess.run(["journalctl", "-u", "gregor-python", "--since", since, "--no-pager",
                          "-o", "short-iso-precise"], capture_output=True, text=True, timeout=60)
    if erg.returncode != 0:
        sys.exit(f"journalctl gregor-python nicht lesbar: {erg.stderr[:200]}")
    return ml.dauerzeilen(ml.lese_journal(erg.stdout.splitlines()))


def _push_status(job_id: str) -> dict | None:
    import httpx
    antwort = httpx.get(STATUS_URL, headers={"X-GZ-Status-Token": _konfig("GZ_STATUS_TOKEN")},
                        timeout=15)
    for job in antwort.json().get("jobs", []):
        if job.get("id") == job_id:
            return job.get("push")
    return None


def _ausgabe_dauer_kanal(dauer: list[dict], kanal: str) -> None:
    je_befehl: dict[str, list[int]] = {}
    for d in dauer:
        if d["kanal"] == kanal:
            print(f"{d['ts'].isoformat()} {d['befehl']} {kanal} trip={d['trip']} {d['ms']} ms")
            je_befehl.setdefault(d["befehl"], []).append(d["ms"])
    for name, werte in sorted(je_befehl.items()):
        print(f"{name}: n={len(werte)} max={max(werte)} ms median={statistics.median(werte)} ms")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--since", required=True, help="JJJJ-MM-TT")
    parser.add_argument("--kanal", choices=["premium_sms", "telegram", "email"])
    args = parser.parse_args()
    dauer = _prod_journal(args.since)
    for kanal in ([args.kanal] if args.kanal else ["premium_sms", "telegram", "email"]):
        print(f"== {kanal} ==")
        if kanal != "premium_sms":
            _ausgabe_dauer_kanal(dauer, kanal)
            continue
        push = _push_status(JOB_JE_KANAL[kanal])
        erg = auswerten(_seven_journal("inbound", args.since),
                        _seven_journal("outbound", args.since), dauer, push=push)
        for b in erg["befehle"]:
            print(f"{b['eingang'].isoformat()} {b['befehl']} antwort={b['antwort'] and b['antwort'].isoformat()} "
                  f"antwortzeit_s={b['antwortzeit_s']} dauer_ms={b['dauer_ms']} push={b['push_zugeordnet']}")
        for name, s in sorted(erg["statistik"].items()):
            print(f"{name}: n={s['anzahl']} max={s['max_s']:.1f} s median={s['median_s']:.1f} s")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
