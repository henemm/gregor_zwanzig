#!/usr/bin/env python3
"""Staging-Messtreiber fuer die Befehls-Antwortzeit-Serien (#2439).

Spec: docs/specs/modules/feat_2439_staging_messtreiber.md

Loest auf STAGING seriell die Befehlsserien aus, die
``tests/e2e/test_push_eingang_befehle_staging.py`` aus dem Journal auswertet:
Probelauf (kalt?), E-Mail- und Telegram-Kurzbefehle, kalte HEUTE/MORGEN DE und
Korsika, das HEUTE-dann-HELP-Paar. Der Treiber wertet NICHT aus (keine
Schwellen, kein Urteil); er gibt nur die drei Env-Zeilen fuer den Test aus.

Aufruf:  eval "$(python3 .claude/tools/staging_messlauf.py)"
         python3 .claude/tools/staging_messlauf.py --nur-probelauf   (nur die drei Probelaeufe)
Basis:   Standard https://staging.gregor20.henemm.com (Secure-Cookie). Korsika auf Staging nur
         ueber die Ersatzquelle eu_direct (egress_guard sperrt Meteo-France), offen ausgewiesen.
Exit:    0 = vollstaendig ausgeloest, 1 = Befund (Probelauf warm, Telegram nicht
         verknuepfbar, Antwort/Dauerzeile ausgeblieben, Abbruch, Aufraeumen gescheitert),
         2 = Umgebungsfehler/Sperre.
stdout:  nur bei Exit 0 eines vollen Laufs die drei Zeilen GZ_STAGING_MESSLAUF_SEIT/_TRIP_DE/_TRIP_KORSIKA;
         jeder Fortschritt geht nach stderr.
"""
from __future__ import annotations

import argparse
import importlib.util
import os
import secrets
import smtplib
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

_HIER = Path(__file__).resolve().parent


def _lade_modul(name: str, datei: str):
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, _HIER / datei)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod  # vor exec_module: @dataclass braucht das registrierte Modul
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return mod


pw = _lade_modul("_gz_staging_befehl_pruefen", "staging_befehl_pruefen.py")
ml = _lade_modul("_gz_befehl_messlogik", "befehl_messlogik.py")

STAGING_EINGANG = pw.STAGING_EINGANG
CHAT_ID_PRAEFIX = "gzp-ungueltig-"
GESCHAETZTE_LAUFZEIT = timedelta(hours=2, minutes=15)
PROBE_LAUFZEIT = timedelta(minutes=30)
WIEN = ZoneInfo("Europe/Vienna")
STANDARD_BASIS = "https://staging.gregor20.henemm.com"  # Secure-Cookie kommt nur ueber https (AC-18)
STANDARD_KERN = "http://127.0.0.1:8001"
STAGING_HOST = "staging.gregor20.henemm.com"
PFLICHT = ("GZ_TEST_IMAP_USER", "GZ_TEST_IMAP_PASS", "GZ_CORE_SHARED_SECRET",
           "GZ_AUTH_USER", "GZ_AUTH_PASS", "TELEGRAM_WEBHOOK_SECRET")

# Orte (lat, lon) im DWD-Fenstergebiet (thunder_routing: de_direct), paarweise >= 140 km.
PROBE_ORT = (53.55, 10.00)                       # Hamburg (Probelauf HEUTE, Basis des DE-Trips)
PROBE_MORGEN_ORT = (51.23, 6.78)                 # Duesseldorf (Probelauf MORGEN, nicht in DE_ORTE)
DE_ORTE = ((52.52, 13.40), (48.21, 16.37), (50.08, 14.44), (51.34, 12.37), (49.45, 11.08),
           (47.07, 15.44), (45.44, 12.33), (50.06, 19.94), (54.35, 18.65), (55.68, 12.57))
KORSIKA_ORT = (42.20, 9.05)                      # fr_direct
KORSIKA_ABSTAND = timedelta(seconds=630)         # Meteo-France-Cache-TTL 600 + Reserve
ANTWORT_WARTEN_S = 360
TELEGRAM_TAKT_S = 3
TELEGRAM_VERSUCHE = ANTWORT_WARTEN_S // TELEGRAM_TAKT_S  # Wartegrenze wie Mail, nie die Messschwelle
WEBHOOK_PFAD = "/api/webhooks/telegram/inbound"  # einzige Webhook-Route (#1814), Secret nur im Header


class Befund(Exception):
    """Ehrlicher Befund des Laufs -> Exit 1."""


def _meldung(text: str) -> None:
    print(text, file=sys.stderr, flush=True)


# ---------------------------------------------------------------------------
# Startpruefung (vor jeder Anfrage)
# ---------------------------------------------------------------------------

def _url(url: str):
    try:
        u = urlsplit((url or "").strip())
        return u, u.port
    except ValueError:
        return None, None


def _lokal(url: str, port: int) -> bool:
    u, p = _url(url)
    return bool(u) and u.scheme == "http" and (u.hostname or "").lower() in ("127.0.0.1", "localhost") \
        and p == port and u.path in ("", "/")


def basis_erlaubt(url: str) -> bool:
    """Whitelist: Staging-Go-API lokal 8091 oder die oeffentliche Staging-URL. Nie 8090/Prod."""
    u, p = _url(url)
    oeffentlich = bool(u) and u.scheme == "https" and (u.hostname or "").lower() == STAGING_HOST \
        and p in (None, 443) and u.path in ("", "/")
    return oeffentlich or _lokal(url, 8091)


def kern_erlaubt(url: str) -> bool:
    """Whitelist: Staging-Kern lokal 8001 (8000 waere der Produktions-Kern)."""
    return _lokal(url, 8001)


def zeitfenster_sperre(jetzt: datetime, laufzeit: timedelta) -> str | None:
    lokal = jetzt.astimezone(WIEN)
    minuten = lokal.hour * 60 + lokal.minute
    if minuten >= 23 * 60 + 45 or minuten < 15:
        return "Sperre: Ortszeit Europe/Vienna liegt im Fenster 23:45-00:15 - spaeter starten."
    if (jetzt + laufzeit).astimezone(WIEN).date() != lokal.date():
        return "Sperre: die geschaetzte Laufzeit ueberspannt einen Tageswechsel - frueher starten."
    return None


def lade_umgebung(env: dict | None) -> dict:
    if env is not None:
        return dict(env)
    werte = {}
    try:
        for z in pw.STAGING_ENV.read_text().splitlines():
            if "=" in z and not z.lstrip().startswith("#"):
                k, v = z.split("=", 1)
                werte[k.strip()] = v.strip().strip("'\"")
    except OSError:
        pass
    werte.update({k: v for k, v in os.environ.items()
                  if k.startswith("GZ_") or k == "TELEGRAM_WEBHOOK_SECRET"})
    return werte


def startpruefung(werte: dict, jetzt: datetime, laufzeit: timedelta) -> str | None:
    fehlend = [k for k in PFLICHT if not werte.get(k)]
    if fehlend:
        return f"Umgebung unvollstaendig, es fehlt: {', '.join(fehlend)}"
    basis = werte.get("GZ_STAGING_BASE_URL") or STANDARD_BASIS
    kern = werte.get("GZ_STAGING_CORE_URL") or STANDARD_KERN
    if not basis_erlaubt(basis):
        return "Sperre: GZ_STAGING_BASE_URL ist keine Staging-Adresse (nie Port 8090/Produktion)."
    if not kern_erlaubt(kern):
        return "Sperre: GZ_STAGING_CORE_URL ist nicht der Staging-Kern auf 127.0.0.1:8001."
    return zeitfenster_sperre(jetzt, laufzeit)


# ---------------------------------------------------------------------------
# Staging-Rand
# ---------------------------------------------------------------------------

class MessApi(pw.StagingApi):
    """StagingApi plus Trip-Ladeweg (Read-Modify-Write) und Telegram-Webhook."""

    def pruefe_erreichbar(self) -> None:
        self._rufe("GET", f"{self._basis}/api/health")

    def hole_trip(self, trip_id: str) -> dict:
        return self._rufe("GET", f"{self._basis}/api/trips/{trip_id}")

    def speichere_trip(self, trip: dict) -> None:
        self._rufe("PUT", f"{self._basis}/api/trips/{trip['id']}", trip)

    def telegram_link(self) -> str:
        return self._rufe("GET", f"{self._basis}/api/auth/telegram-link")["link"]

    def telegram_verbunden(self) -> bool:
        return bool(self._rufe("GET", f"{self._basis}/api/auth/telegram-status").get("connected"))

    def telegram_update(self, secret: str, update: dict) -> None:
        self._rufe("POST", f"{self._basis}{WEBHOOK_PFAD}", update,
                   {"X-Telegram-Bot-Api-Secret-Token": secret})


def journal_staging(seit: datetime) -> list:
    """Journal von gregor-python-staging seit ``seit`` (Form wie befehl_messlogik.lese_journal)."""
    erg = subprocess.run(["journalctl", "-u", "gregor-python-staging", "--since", seit.isoformat(),
                          "-o", "short-iso-precise", "--no-pager"],
                         capture_output=True, text=True, timeout=120, check=False)
    if erg.returncode != 0:
        raise OSError(f"journalctl Exit {erg.returncode}")
    return ml.lese_journal(erg.stdout.splitlines())


@dataclass
class Lauf:
    api: MessApi
    tag: str
    webhook_secret: str
    smtp: object
    imap: object
    journal: object
    uhr: object
    schlaf: object
    plus: str = ""
    chat_id: str = ""
    seit: datetime | None = None
    trips: dict = field(default_factory=dict)
    angelegt: list = field(default_factory=list)
    update_id: int = field(default_factory=lambda: 10 ** 12 + secrets.randbelow(10 ** 11))
    letzte_korsika: datetime | None = None
    korsika_ersatz: bool = False   # Staging: egress_guard sperrt Meteo-France -> eu_direct (AC-19)
    nur_probelauf: bool = False


# ---------------------------------------------------------------------------
# Bausteine
# ---------------------------------------------------------------------------

# Befehlsantworten tragen weder In-Reply-To noch einen eigenen Mail-Typ
# (notification_service.send_command_reply_email). Erkannt werden sie am Betreff:
# "Hilfe"/"Help" (trip_command_processor.py:1392/1401), "Kürzel"/"Codes" (:1412),
# "[<Trip>] ..." (Status :2758, Heute/Morgen :1703/1712) - oder am Header
# X-GZ-Mail-Type: trip-briefing (notification_service.py:2310/2318, in pw._eigene_uids).
# Systemmails an dieselbe Plus-Adresse (Verifikation, internal/mail/verify.go:33) zaehlen nicht.
_KURZ_BETREFFE = ("Hilfe", "Help", "Kürzel", "Codes")


def _betreffe(trip: dict) -> tuple:
    return (f"[{trip['name']}]",) + _KURZ_BETREFFE


def _poll(lauf: Lauf) -> None:
    try:
        lauf.api.loese_poll_aus()
    except (pw.StagingFehler, OSError):
        pass  # Cron-Takt verarbeitet die Mail ohnehin


def sende_mail(lauf: Lauf, trip: dict, wort: str) -> None:
    """EIN Befehl per Port 25, Poll, Antwort abwarten (seriell)."""
    seit_uid = pw._mit_imap(lauf.imap, pw.hoechste_uid)
    pw.liefere_ein(pw.baue_befehlsmail(lauf.plus, trip["name"], wort), lauf.smtp)
    _poll(lauf)
    raw = pw._warte_auf_antwort(lauf.imap, lauf.plus, seit_uid, ANTWORT_WARTEN_S, lauf.schlaf,
                                _betreffe(trip))
    if not raw:
        raise Befund(f"E-Mail {wort} [{trip['id']}]: keine Antwort binnen {ANTWORT_WARTEN_S} s "
                     "- Lauf unvollstaendig")
    _meldung(f"  E-Mail {wort} [{trip['id']}]: Antwort erhalten")


def _warte_auf_antworten(lauf: Lauf, seit_uid: int, betreffe, anzahl: int) -> int:
    gewartet, gefunden = 0, 0
    while True:
        gefunden = len(pw._mit_imap(lauf.imap, lambda im: pw._eigene_uids(im, lauf.plus, seit_uid,
                                                                           betreffe)))
        if gefunden >= anzahl or gewartet >= ANTWORT_WARTEN_S:
            return gefunden
        lauf.schlaf(pw.INTERVALL_S)
        gewartet += pw.INTERVALL_S


def sende_paar(lauf: Lauf) -> None:
    """AC-7: HEUTE einliefern, HELP sofort nachschieben (nicht auf HEUTE warten), dann ein Poll."""
    trip = lauf.trips["de"]
    seit_uid = pw._mit_imap(lauf.imap, pw.hoechste_uid)
    pw.liefere_ein(pw.baue_befehlsmail(lauf.plus, trip["name"], "heute"), lauf.smtp)
    pw.liefere_ein(pw.baue_befehlsmail(lauf.plus, trip["name"], "hilfe"), lauf.smtp)
    _poll(lauf)
    n = _warte_auf_antworten(lauf, seit_uid, _betreffe(trip), 2)
    if n < 2:
        raise Befund(f"E-Mail Paar heute+hilfe [{trip['id']}]: nur {n} von 2 Antworten binnen "
                     f"{ANTWORT_WARTEN_S} s - Lauf unvollstaendig")
    _meldung(f"  Paar heute+hilfe [{trip['id']}]: {n} von 2 Antworten erhalten")


def sende_korsika(lauf: Lauf, wort: str) -> None:
    if lauf.letzte_korsika is not None:
        rest = (lauf.letzte_korsika + KORSIKA_ABSTAND - lauf.uhr()).total_seconds()
        if rest > 0:
            _meldung("  warte auf Ablauf des Meteo-France-Caches")
            lauf.schlaf(rest)
    lauf.letzte_korsika = lauf.uhr()
    sende_mail(lauf, lauf.trips["korsika"], wort)


def setze_ort(lauf: Lauf, ort: tuple) -> None:
    """Read-Modify-Write: Trip laden, NUR die Orte der Etappen heute/morgen aendern, speichern."""
    trip = lauf.api.hole_trip(lauf.trips["de"]["id"])
    heute = lauf.uhr().astimezone(WIEN).date()
    tage = {heute.isoformat(), (heute + timedelta(days=1)).isoformat()}
    for etappe in trip.get("stages", []):
        if etappe.get("date") in tage:
            for j, wp in enumerate(etappe.get("waypoints", [])):
                wp["lat"], wp["lon"] = round(ort[0] + 0.01 * j, 4), round(ort[1] + 0.01 * j, 4)
    lauf.api.speichere_trip(trip)


def _telegram_post(lauf: Lauf, text: str) -> None:
    lauf.update_id += 1
    lauf.api.telegram_update(lauf.webhook_secret, {
        "update_id": lauf.update_id,
        "message": {"message_id": lauf.update_id, "date": int(lauf.uhr().timestamp()),
                    "chat": {"id": lauf.chat_id, "type": "private"}, "text": text}})


def _telegram_zeilen(lauf: Lauf) -> int:
    return sum(1 for l in ml.dauerzeilen(lauf.journal(lauf.seit)) if l["kanal"] == "telegram")


def sende_telegram(lauf: Lauf, wort: str) -> None:
    """Simuliertes Webhook-Update; wartet auf die Dauerzeile, bevor der naechste Befehl folgt."""
    vorher = _telegram_zeilen(lauf)
    _telegram_post(lauf, wort)
    for _ in range(TELEGRAM_VERSUCHE):
        if _telegram_zeilen(lauf) > vorher:
            _meldung(f"  Telegram {wort}: verarbeitet")
            return
        lauf.schlaf(TELEGRAM_TAKT_S)
    raise Befund(f"Telegram {wort}: keine Dauerzeile binnen {TELEGRAM_VERSUCHE * TELEGRAM_TAKT_S} s "
                 "im Journal - Lauf unvollstaendig")


def verknuepfe_telegram(lauf: Lauf) -> None:
    """Link-Token holen, ``/start TOKEN`` als Update posten, per telegram-status bestaetigen."""
    try:
        token = lauf.api.telegram_link().rsplit("start=", 1)[1].strip()
        if not token:
            raise ValueError("leeres Token")
        _telegram_post(lauf, f"/start {token}")
        for _ in range(TELEGRAM_VERSUCHE):
            if lauf.api.telegram_verbunden():
                _meldung("Telegram verknuepft (Pruef-chat_id, keine echte Zustellung)")
                return
            lauf.schlaf(TELEGRAM_TAKT_S)
        grund = "telegram-status meldet keine Verbindung"
    except (pw.StagingFehler, OSError, KeyError, IndexError, TypeError, ValueError, AttributeError) as exc:
        grund = f"{type(exc).__name__}: {exc}"
    raise Befund(f"Telegram nicht verknüpfbar ({grund}) - Telegram-Serie nicht ausgeloest, "
                 "Lauf unvollstaendig")


# ---------------------------------------------------------------------------
# Phasen
# ---------------------------------------------------------------------------

def lege_trips_an(lauf: Lauf) -> None:
    """Genau 2 Trips (DE, Korsika) - Kontingent 3 je Nutzer."""
    heute = lauf.uhr().astimezone(WIEN).date()
    for art, ort in (("de", PROBE_ORT), ("korsika", KORSIKA_ORT)):
        trip = pw.baue_trip("A", lauf.tag, heute, ort=ort)
        trip["id"], trip["name"] = f"gzp-{lauf.tag}-{art}", f"GZ-Messlauf {lauf.tag} {art.upper()}"
        lauf.api.lege_trip_an(trip)
        lauf.angelegt.append(trip["id"])
        lauf.trips[art] = trip
        _meldung(f"Trip angelegt: {trip['id']}")


_KORSIKA_ERSATZ = ("Korsika auf Staging: Gewitterquelle eu_direct (Ersatz) - fr_direct ist durch "
                   "egress_guard gesperrt; die Kaltmessung fr_direct ist Prod-Aufgabe")


def _probe(lauf: Lauf, trip: dict, wort: str) -> None:
    """EIN Probelauf, sofort geprueft: warm (kein downloads>0) oder ohne Dauerzeile -> Befund,
    bevor irgendetwas weiter geaendert wird (AC-1)."""
    if trip is lauf.trips["korsika"]:
        sende_korsika(lauf, wort)
    else:
        sende_mail(lauf, trip, wort)
    befehl = wort.upper()
    journal = lauf.journal(lauf.seit)
    laeufe = [l for l in ml.dauerzeilen(journal) if l["trip"] == trip["id"]
              and l["befehl"] == befehl and l["kanal"] == "email"]
    if trip is lauf.trips["korsika"]:
        if lauf.korsika_ersatz:  # AC-19: kein fr_direct-Kaltlauf verlangt, aber eine Dauerzeile
            kalt = bool(laeufe)
        else:
            kalt = bool(laeufe) and ml.kalt_laeufe(laeufe, journal, quellen=("fr_direct_fenster",))
    else:
        kalt = bool(laeufe) and ml.kalt_laeufe(laeufe, journal, quellen=("dwd_fenster",))
    if not kalt:
        raise Befund(f"Probelauf ohne Download-Beleg (warm oder keine Dauerzeile): {befehl} "
                     f"{trip['id']} - keine Serie ausgeloest")


def probelauf(lauf: Lauf) -> None:
    """1x HEUTE Korsika, dann HEUTE/MORGEN DE mit Ortswechsel dazwischen; jeder sofort geprueft."""
    de, ko = lauf.trips["de"], lauf.trips["korsika"]
    _probe(lauf, ko, "heute")
    if lauf.korsika_ersatz:
        _meldung(_KORSIKA_ERSATZ)
    _probe(lauf, de, "heute")
    setze_ort(lauf, PROBE_MORGEN_ORT)  # AC-17: MORGEN sonst aus dem von HEUTE gewaermten Cache
    _probe(lauf, de, "morgen")
    _meldung("Probelauf: DE HEUTE/MORGEN mit Downloads im Journal, Korsika "
             + ("mit Antwort (Ersatzquelle eu_direct)" if lauf.korsika_ersatz else "mit Downloads"))


def serien(lauf: Lauf) -> None:
    de = lauf.trips["de"]
    _meldung("E-Mail-Kurzbefehle")
    for _ in range(5):
        for wort in ("status", "kuerzel", "hilfe"):  # nie HELP direkt nach dem Probelauf-HEUTE
            sende_mail(lauf, de, wort)
    _meldung("Telegram-Kurzbefehle")
    for _ in range(5):
        for wort in ("status", "kuerzel", "hilfe"):
            sende_telegram(lauf, wort)
    _meldung("DE-Serie mit Ortswechsel")
    for i, ort in enumerate(DE_ORTE):
        setze_ort(lauf, ort)
        sende_mail(lauf, de, "heute" if i % 2 == 0 else "morgen")
    _meldung("Korsika-Serie" + (" - " + _KORSIKA_ERSATZ if lauf.korsika_ersatz else ""))
    for i in range(6):
        sende_korsika(lauf, "heute" if i % 2 == 0 else "morgen")
    _meldung("HEUTE-dann-HELP-Paar")
    sende_paar(lauf)


def ablauf(lauf: Lauf) -> list[str]:
    lauf.seit = lauf.uhr().astimezone(timezone.utc).replace(microsecond=0)
    lauf.api.pruefe_erreichbar()
    lauf.plus = pw.baue_plus_adresse(lauf.tag)
    lauf.chat_id = CHAT_ID_PRAEFIX + lauf.tag
    lauf.api.registriere(lauf.plus)
    _meldung(f"Wegwerf-Nutzer registriert: {lauf.api.nutzer_id}")
    lege_trips_an(lauf)
    if lauf.nur_probelauf:
        probelauf(lauf)
        _meldung("Modus nur Probelauf: keine Serien, keine Env-Zeilen")
        return []
    verknuepfe_telegram(lauf)
    probelauf(lauf)
    serien(lauf)
    return [f"GZ_STAGING_MESSLAUF_SEIT={lauf.seit.isoformat().replace('+00:00', 'Z')}",
            f"GZ_STAGING_TRIP_DE={lauf.trips['de']['id']}",
            f"GZ_STAGING_TRIP_KORSIKA={lauf.trips['korsika']['id']}"]


def raeume_auf(lauf: Lauf) -> bool:
    """Beide Trips, Antwortmails, Wegwerf-Nutzer loeschen. True = etwas ist stehen geblieben."""
    nutzer = lauf.api.nutzer_id
    probleme = []
    for tid in lauf.angelegt:
        try:
            lauf.api.loesche_trip(tid)
        except Exception as exc:
            probleme.append(f"Trip {tid} nicht geloescht ({type(exc).__name__})")
    if nutzer is not None:
        try:
            pw._mit_imap(lauf.imap, lambda im: pw.loesche_eigene_antworten(im, lauf.plus))
        except Exception as exc:
            _meldung(f"Hinweis: Antwortmails nicht geloescht ({type(exc).__name__}), Adresse {lauf.plus}")
        try:
            lauf.api.loesche_nutzer()
        except Exception as exc:
            probleme.append(f"Wegwerf-Nutzer nicht geloescht ({type(exc).__name__})")
    for p in probleme:
        _meldung(f"BEFUND Aufraeumen: {p} - Nutzer-Kennung {nutzer}")
    return bool(probleme)


def fuehre_aus(lauf: Lauf) -> int:
    rc, zeilen, rest = 1, None, True
    try:
        try:
            zeilen, rc = ablauf(lauf), 0
        except Befund as exc:
            _meldung(f"BEFUND: {exc}")
        except (pw.StagingFehler, OSError) as exc:
            _meldung(f"Umgebungsfehler: {type(exc).__name__}: {exc}")
            rc = 2
        except KeyboardInterrupt:
            _meldung("Abbruch: unterbrochen")
        except Exception as exc:
            _meldung(f"Abbruch: {type(exc).__name__}: {exc}")
    finally:
        rest = raeume_auf(lauf)
    if rest:
        return max(rc, 1)
    if rc == 0 and zeilen:
        print("\n".join(zeilen), flush=True)
    return rc


def main(argv=None, *, env=None, transport=None, helfer_transport=None, smtp_factory=None,
         imap_factory=None, journal_quelle=None, uhr=None, schlaf=None, laufzeit=None) -> int:
    """Raender injizierbar (Kern-Tests); ohne Angaben echtes HTTP, SMTP, IMAP, journalctl."""
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--nur-probelauf", action="store_true",
                   help="nur die drei Probelaeufe (HEUTE/MORGEN DE, HEUTE Korsika), dann aufraeumen")
    args = p.parse_args(argv)
    werte = lade_umgebung(env)
    uhr = uhr or (lambda: datetime.now(timezone.utc))
    laufzeit = laufzeit or (PROBE_LAUFZEIT if args.nur_probelauf else GESCHAETZTE_LAUFZEIT)
    sperre = startpruefung(werte, uhr(), laufzeit)
    if sperre:
        _meldung(sperre)
        return 2
    basis = werte.get("GZ_STAGING_BASE_URL") or STANDARD_BASIS
    api = MessApi(basis,
                  werte.get("GZ_STAGING_CORE_URL") or STANDARD_KERN,
                  werte["GZ_CORE_SHARED_SECRET"], transport or pw.http_transport(),
                  helfer_transport=helfer_transport or pw.http_transport(),
                  helfer_zugang=(werte["GZ_AUTH_USER"], werte["GZ_AUTH_PASS"]))
    lauf = Lauf(api=api, tag=pw.baue_tag(), webhook_secret=werte["TELEGRAM_WEBHOOK_SECRET"],
                smtp=smtp_factory or smtplib.SMTP, imap=imap_factory or pw._imap_factory(werte),
                journal=journal_quelle or journal_staging, uhr=uhr, schlaf=schlaf or time.sleep,
                korsika_ersatz=(urlsplit(basis).hostname or "").lower() == STAGING_HOST,
                nur_probelauf=args.nur_probelauf)
    return fuehre_aus(lauf)


if __name__ == "__main__":
    sys.exit(main())
