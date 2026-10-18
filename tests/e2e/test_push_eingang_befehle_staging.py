"""Live-Schicht (nur ``/e2e-verify``): Push-Eingang fuer Befehle gegen STAGING.

Issue #2439 Scheibe (a). Spec: docs/specs/modules/feat_2439_befehle_push_eingang.md

Marker ``live`` + ``staging``: laeuft NICHT im Kern-Testlauf und NICHT lokal
(Opt-in ``GZ_STAGING_E2E=1``).

AC-Zuordnung:
  AC-11  HTTP-Smoke von aussen: ungueltiges Secret auf den Webhook-Pfaden ->
         403 (nicht 401/404/Basic-Auth-Challenge); ein uebriger Staging-Pfad
         -> 401 (Basic-Auth bleibt dort aktiv).
  AC-1   SMS: ``push.last_received`` von ``premium_sms_poll`` und ``last_run``
         des Jobs liegen Sekunden auseinander, nicht Minuten.
  AC-2   Mail: dasselbe fuer ``inbound_command_poll``.
  AC-8   ``push.last_received`` existiert im Status (Sichtbarkeit eines
         Ausfalls des Sofort-Wegs).

Voraussetzung fuer AC-1/AC-2: der /e2e-verify-Treiber hat VOR diesem Test eine
echte Befehls-SMS (zweite seven.io-Nummer) bzw. -Mail (``gregor-test+...@``)
auf Staging ausgeloest. Der Test misst nur den Zeitabstand im Status-Endpoint
(``X-GZ-Status-Token`` aus ``GZ_STAGING_STATUS_TOKEN``); Basic-Auth fuer
Staging optional aus ``GZ_STAGING_BASIC_AUTH`` (``user:pass``, nie im Klartext
ins Repo).
"""
from __future__ import annotations

import os
from datetime import datetime

import httpx
import pytest

STAGING = "https://staging.gregor20.henemm.com"
GRENZE_SEKUNDEN = 60  # "Sekunden, nicht Minuten" -- weit unter dem 5-min-Raster

pytestmark = [
    pytest.mark.live,
    pytest.mark.staging,
    pytest.mark.skipif(
        os.environ.get("GZ_STAGING_E2E") != "1",
        reason="Staging-Live-Test: nur /e2e-verify (GZ_STAGING_E2E=1)",
    ),
]


def _basic_auth() -> tuple[str, str] | None:
    roh = os.environ.get("GZ_STAGING_BASIC_AUTH", "")
    if ":" not in roh:
        return None
    user, _, pw = roh.partition(":")
    return user, pw


# ---------------------------------------------------------------------------
# AC-11: HTTP-Smoke von aussen
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("kanal", ["sms", "mail"])
def test_ac11_webhook_pfad_ungueltiges_secret_ist_403_ohne_basic_auth(kanal):
    antwort = httpx.post(
        f"{STAGING}/api/webhooks/{kanal}/ungueltiges-secret-ac11",
        content=b"{}", headers={"Content-Type": "application/json"}, timeout=15,
    )  # bewusst OHNE Basic-Auth: die Ausnahme fuer diese Pfade ist die Pruefung
    assert antwort.status_code == 403, (
        f"/api/webhooks/{kanal}/ auf Staging: erwartet 403 (Go-API erreicht, kein "
        f"Basic-Auth-Hindernis), bekam {antwort.status_code} "
        f"(WWW-Authenticate={antwort.headers.get('www-authenticate')!r})"
    )
    assert "www-authenticate" not in {k.lower() for k in antwort.headers}


def test_ac11_uebriger_staging_pfad_bleibt_geschuetzt():
    antwort = httpx.get(f"{STAGING}/api/scheduler/status", timeout=15)  # ohne Basic-Auth
    assert antwort.status_code == 401, (
        f"uebrige Staging-Pfade muessen hinter Basic-Auth bleiben, bekam {antwort.status_code}"
    )


# ---------------------------------------------------------------------------
# AC-1 / AC-2 / AC-8: Zeitabstand last_received -> last_run im Status
# ---------------------------------------------------------------------------

def _job_status(job_id: str) -> dict:
    token = os.environ.get("GZ_STAGING_STATUS_TOKEN")
    assert token, "GZ_STAGING_STATUS_TOKEN fehlt (Befund der Testumgebung, kein Flake)"
    antwort = httpx.get(
        f"{STAGING}/api/scheduler/status",
        headers={"X-GZ-Status-Token": token}, auth=_basic_auth(), timeout=15,
    )
    assert antwort.status_code == 200, antwort.text[:200]
    for job in antwort.json()["jobs"]:
        if job.get("id") == job_id:
            return job
    raise AssertionError(f"Job {job_id!r} nicht im Staging-Status")


def _pruefe_sofortweg(job_id: str):
    job = _job_status(job_id)
    push = job.get("push")
    assert isinstance(push, dict) and "last_received" in push, (
        f"{job_id}: Status-Feld push.last_received fehlt: {push!r}"  # AC-8
    )
    assert push["last_received"], (
        f"{job_id}: kein Webhook eingegangen (push.last_received leer) -- Treiber hat "
        f"keinen Befehl ausgeloest oder der Sofort-Weg ist ausgefallen: {push!r}"
    )
    assert push.get("received_total", 0) >= 1
    empfangen = datetime.fromisoformat(push["last_received"])
    assert job.get("last_run"), f"{job_id}: kein last_run"
    assert job["last_run"].get("status") == "ok", (
        f"{job_id}: last_run.status ist {job['last_run'].get('status')!r} statt 'ok' -- "
        f"Poll-Lauf nach Webhook gescheitert (z.B. EOF auf wiederverwendeter "
        f"Core-Verbindung): {job['last_run']!r}"
    )
    gelaufen = datetime.fromisoformat(job["last_run"]["time"])
    abstand = (gelaufen - empfangen).total_seconds()
    assert 0 <= abstand <= GRENZE_SEKUNDEN, (
        f"{job_id}: last_run {abstand:.0f} s nach last_received (erwartet Sekunden, "
        f"nicht Minuten): {push!r} / {job['last_run']!r}"
    )


def test_ac1_sms_last_run_sekunden_nach_webhook():
    _pruefe_sofortweg("premium_sms_poll")


def test_ac2_mail_last_run_sekunden_nach_webhook():
    _pruefe_sofortweg("inbound_command_poll")


# ===========================================================================
# #2439 Scheibe (b): Antwortzeit der Befehle -- AC-3, AC-4, AC-5, AC-12, AC-14
# Spec: docs/specs/modules/feat_2439_befehle_antwortzeit.md
# ===========================================================================
#
# Messweise: Diese Tests LOESEN KEINE Befehle aus (wie AC-1/AC-2 oben: der /e2e-verify-Treiber
# schickt sie ueber die ECHTEN Eingaenge -- E-Mail gregor-test+...@, Telegram, zweite
# seven.io-Nummer). Sie WERTEN das Staging-Journal aus (Quelle der Wahrheit: die
# Dauer-Zeile aus AC-1, NICHT der Gesamtlauf des Treibers):
#     befehl=<NAME> kanal=<email|telegram|sms|premium_sms> trip=<id> dauer_ms=<n>
# Umgebung (vom Treiber gesetzt):
#   GZ_STAGING_MESSLAUF_SEIT   ISO-Zeitpunkt (UTC), VOR dem ersten ausgeloesten Befehl
#   GZ_STAGING_TRIP_DE         (optional) Trip-ID der DE/Alpen-Route; filtert AC-4
#   GZ_STAGING_TRIP_KORSIKA    Trip-ID des Korsika-Trips (`fr_direct`), Pflicht fuer AC-5
# Das Journal von `gregor-python-staging` ist fuer `hem` lesbar (journalctl); ohne Lesezugriff
# FAILt der Test mit klarer Meldung (Befund der Testumgebung, kein Flake).
# Kalt (AC-4): der Treiber startet `gregor-python-staging` vor jedem Lauf neu oder nimmt ein
# noch nie abgerufenes Datum; der Test BELEGT es aus dem Journal -- nur Laeufe, in deren
# Zeitspanne eine DWD-Fensterzeile `downloads>0` steht, zaehlen als kalt.

import re
import statistics
import subprocess
from datetime import timedelta, timezone

_ZEILE_DAUER = re.compile(r"befehl=(\S+) kanal=(\S+) trip=(\S+) dauer_ms=(\d+)")
_ZEILE_DWD = re.compile(r"fenster_s=[\d.]+ downloads=(\d+) cache_treffer=\d+")
_KANAL_GRUPPEN = {
    "email": {"email"},
    "telegram": {"telegram"},
    "premium_sms": {"premium_sms", "sms"},  # der SMS-Eingang laeuft ueber den Rueckkanal
}
GRENZE_OHNE_WETTER_MS = 30_000
GRENZE_MIT_WETTER_MS = 60_000
GRENZE_MEDIAN_MS = 45_000
MIN_LAEUFE_OHNE_WETTER = 5
MIN_LAEUFE_WETTER = 5
MIN_LAEUFE_KORSIKA = 3
HELP_NACH_HEUTE_MS = 30_000
HELP_GESAMT_MS = 90_000


def _messlauf_seit() -> str:
    seit = os.environ.get("GZ_STAGING_MESSLAUF_SEIT", "")
    assert seit, (
        "GZ_STAGING_MESSLAUF_SEIT fehlt (Befund der Testumgebung): der Treiber muss den "
        "Startzeitpunkt der ausgeloesten Befehle exportieren"
    )
    return seit


def _journal(unit: str, seit: str) -> list[tuple[datetime, str]]:
    erg = subprocess.run(
        ["journalctl", "-u", unit, "--since", seit, "--no-pager", "-o", "short-iso-precise"],
        capture_output=True, text=True, timeout=60,
    )
    assert erg.returncode == 0, (
        f"journalctl -u {unit} nicht lesbar (Befund der Testumgebung): {erg.stderr[:200]}"
    )
    zeilen = []
    for roh in erg.stdout.splitlines():
        kopf, _, rest = roh.partition(" ")
        try:
            zeit = datetime.strptime(kopf, "%Y-%m-%dT%H:%M:%S.%f%z")
        except ValueError:
            continue
        zeilen.append((zeit.astimezone(timezone.utc), rest))
    return zeilen


def _dauerzeilen(seit: str, *, trip: str | None = None) -> list[dict]:
    treffer = []
    for zeit, text in _journal("gregor-python-staging", seit):
        m = _ZEILE_DAUER.search(text)
        if m and (trip is None or m.group(3) == trip):
            treffer.append({"ts": zeit, "befehl": m.group(1), "kanal": m.group(2),
                            "trip": m.group(3), "ms": int(m.group(4))})
    return treffer


def _kalt(lauf: dict, dwd_zeilen: list[tuple[datetime, int]]) -> bool:
    """Kalt = im Zeitfenster des Befehls hat ein DWD-Fenster tatsaechlich heruntergeladen."""
    anfang = lauf["ts"] - timedelta(milliseconds=lauf["ms"])
    return any(anfang <= zeit <= lauf["ts"] and downloads > 0 for zeit, downloads in dwd_zeilen)


def _dwd_downloads(seit: str) -> list[tuple[datetime, int]]:
    return [(zeit, int(m.group(1))) for zeit, text in _journal("gregor-python-staging", seit)
            if (m := _ZEILE_DWD.search(text))]


def _auswahl(laeufe: list[dict], befehl: str, eingang: str | None = None) -> list[dict]:
    kanaele = _KANAL_GRUPPEN[eingang] if eingang else None
    return [l for l in laeufe if l["befehl"] == befehl and (kanaele is None or l["kanal"] in kanaele)]


@pytest.mark.parametrize("befehl", ["HELP", "CODES", "STATUS"])
@pytest.mark.parametrize("eingang", ["email", "telegram", "premium_sms"])
def test_ac3_befehle_ohne_wetterabruf_unter_30_sekunden_auf_jedem_eingang(eingang, befehl):
    """AC-3: jeder Lauf (>= 5 je Befehl und Eingang) liegt in der Dauer-Zeile unter 30 s."""
    laeufe = _auswahl(_dauerzeilen(_messlauf_seit()), befehl, eingang)
    werte = [l["ms"] for l in laeufe]
    assert len(werte) >= MIN_LAEUFE_OHNE_WETTER, (
        f"AC-3: nur {len(werte)} {befehl}-Laeufe ueber {eingang} im Journal (erwartet >= "
        f"{MIN_LAEUFE_OHNE_WETTER}); der Treiber hat zu wenige ausgeloest oder die Dauer-Zeile "
        f"(AC-1) fehlt"
    )
    assert max(werte) < GRENZE_OHNE_WETTER_MS, (
        f"AC-3: {befehl} ueber {eingang}: Einzelwerte {werte} ms, Maximum {max(werte)} ms "
        f">= {GRENZE_OHNE_WETTER_MS} ms"
    )


@pytest.mark.parametrize("befehl", ["HEUTE", "MORGEN"])
def test_ac4_wetterbefehle_kalt_auf_de_route_max_unter_60s_und_median_unter_45s(befehl):
    """AC-4: >= 5 KALTE Laeufe je Befehl (E-Mail, Telegram, Premium-SMS je mindestens einmal
    darunter): jeder < 60 s UND Median < 45 s; alle Einzelwerte werden ausgegeben."""
    seit = _messlauf_seit()
    laeufe = _auswahl(_dauerzeilen(seit, trip=os.environ.get("GZ_STAGING_TRIP_DE")), befehl)
    dwd_zeilen = _dwd_downloads(seit)
    kalte = [l for l in laeufe if _kalt(l, dwd_zeilen)]
    werte = [l["ms"] for l in kalte]
    print(f"AC-4 {befehl}: kalte Einzelwerte (ms) = {werte}; alle Laeufe = "
          f"{[(l['kanal'], l['ms']) for l in laeufe]}")
    assert len(kalte) >= MIN_LAEUFE_WETTER, (
        f"AC-4: nur {len(kalte)} KALTE {befehl}-Laeufe belegt (DWD-Fensterzeile mit "
        f"downloads>0 im Befehlsfenster), erwartet >= {MIN_LAEUFE_WETTER}; alle Laeufe: "
        f"{[(l['kanal'], l['ms']) for l in laeufe]}"
    )
    fehlende = [e for e, kanaele in _KANAL_GRUPPEN.items()
                if not any(l["kanal"] in kanaele for l in kalte)]
    assert not fehlende, f"AC-4: unter den kalten {befehl}-Laeufen fehlt der Eingang {fehlende}"
    assert max(werte) < GRENZE_MIT_WETTER_MS, (
        f"AC-4: {befehl} kalt, Einzelwerte {werte} ms: Maximum {max(werte)} ms >= "
        f"{GRENZE_MIT_WETTER_MS} ms (Ausgangswert vor der Aenderung 57800 ms)"
    )
    assert statistics.median(werte) < GRENZE_MEDIAN_MS, (
        f"AC-4: {befehl} kalt, Einzelwerte {werte} ms: Median {statistics.median(werte)} ms "
        f">= {GRENZE_MEDIAN_MS} ms"
    )


@pytest.mark.parametrize("befehl", ["HEUTE", "MORGEN"])
def test_ac5_wetterbefehle_kalt_auf_korsika_route_jeder_lauf_unter_60s(befehl):
    """AC-5: Korsika-Trip (`fr_direct`), >= 3 kalte Laeufe je Befehl, jeder < 60 s."""
    trip = os.environ.get("GZ_STAGING_TRIP_KORSIKA", "")
    assert trip, "GZ_STAGING_TRIP_KORSIKA fehlt (Befund der Testumgebung): Korsika-Trip-ID"
    seit = _messlauf_seit()
    laeufe = _auswahl(_dauerzeilen(seit, trip=trip), befehl)
    werte = [l["ms"] for l in laeufe]
    print(f"AC-5 {befehl} Korsika: Einzelwerte (ms) = {werte}")
    assert len(werte) >= MIN_LAEUFE_KORSIKA, (
        f"AC-5: nur {len(werte)} {befehl}-Laeufe fuer den Korsika-Trip, erwartet >= "
        f"{MIN_LAEUFE_KORSIKA}"
    )
    assert max(werte) < GRENZE_MIT_WETTER_MS, (
        f"AC-5: {befehl} Korsika, Einzelwerte {werte} ms: Maximum {max(werte)} ms >= "
        f"{GRENZE_MIT_WETTER_MS} ms -- Befund in diesem Ticket (Abrufpfad fr_direct "
        f"beschleunigen), keine Ausnahme"
    )


@pytest.mark.parametrize("eingang", ["email", "premium_sms"])
def test_ac12_help_waehrend_heute_wird_spaetestens_30s_nach_dessen_ende_beantwortet(eingang):
    """AC-12: Der Treiber sendet `HEUTE` und direkt danach `HELP` ueber denselben Eingang.
    Gemessen aus den Journalzeitpunkten der beiden Dauer-Zeilen (Uebergabe der Antwort):
    HELP <= 30 s nach HEUTE-Ende; HELP-Gesamtzeit (ab HEUTE-Start, obere Schranke) < 90 s."""
    laeufe = sorted(_dauerzeilen(_messlauf_seit()), key=lambda l: l["ts"])
    kanaele = _KANAL_GRUPPEN[eingang]
    paare = []
    for i, heute in enumerate(laeufe):
        if heute["befehl"] != "HEUTE" or heute["kanal"] not in kanaele:
            continue
        for help_ in laeufe[i + 1:]:
            if help_["befehl"] == "HELP" and help_["kanal"] in kanaele:
                paare.append((heute, help_))
                break
    assert paare, (
        f"AC-12: kein HEUTE->HELP-Paar ueber {eingang} im Journal -- der Treiber hat den "
        f"HELP nicht direkt nach dem HEUTE gesendet"
    )
    for heute, help_ in paare:
        nach_ende_s = (help_["ts"] - heute["ts"]).total_seconds()
        start_heute = heute["ts"] - timedelta(milliseconds=heute["ms"])
        gesamt_ms = (help_["ts"] - start_heute).total_seconds() * 1000
        assert nach_ende_s <= HELP_NACH_HEUTE_MS / 1000, (
            f"AC-12 ({eingang}): HELP wurde {nach_ende_s:.1f} s nach Ende des HEUTE "
            f"beantwortet (> 30 s)"
        )
        assert gesamt_ms < HELP_GESAMT_MS, (
            f"AC-12 ({eingang}): HELP-Gesamtzeit {gesamt_ms:.0f} ms >= {HELP_GESAMT_MS} ms"
        )


def test_ac14_sms_nachversuch_kein_eof_im_staging_log():
    """AC-14 (Ergaenzung zu test_ac1_sms_last_run_sekunden_nach_webhook, das `last_run.status ==
    ok` bereits prueft): im Staging-Journal von Go-API UND Python-Kern steht seit dem Messlauf
    kein EOF-Fehler (wiederverwendete Core-Verbindung)."""
    seit = _messlauf_seit()
    eof = []
    for unit in ("gregor-api-staging", "gregor-python-staging"):
        eof += [f"{unit}: {text[:160]}" for _zeit, text in _journal(unit, seit)
                if re.search(r"\bEOF\b", text)]
    assert not eof, f"AC-14: EOF-Fehler im Staging-Log seit {seit}: {eof[:5]}"
