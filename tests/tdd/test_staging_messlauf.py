"""Staging-Messtreiber fuer die Befehls-Antwortzeit-Serien (#2439).

Spec: docs/specs/modules/feat_2439_staging_messtreiber.md (AC-1 .. AC-20)

Pruefling: ``.claude/tools/staging_messlauf.py`` -- aufgeloest RELATIV zu dieser
Testdatei, geladen per ``importlib`` in JEDEM Test (fehlt das Werkzeug, scheitert
jeder Test einzeln, kein Sammel-ERROR). Daneben ``staging_befehl_pruefen.py``
(``baue_trip`` mit Ortsparameter, Rueckwaertskompatibilitaet).

Alle Tests laufen ohne Netz gegen eine Ersatz-Staging-Welt (``_Welt``): Go-API,
Kern-Poll, Telegram-Webhook, Stalwart (SMTP Port 25 + IMAP) und Journal. Keine
Mock()/patch()/MagicMock, kein Lesen des Werkzeug-Quelltexts. Die Uhr ist eine
Ersatz-Uhr; ``schlaf`` schreibt sie fort, es wird nie real gewartet.

Fakten aus dem echten Code (Grundlage der Ersatzwelt)
-----------------------------------------------------
F1 Kalt-Marker (Journalzeilen, Logger-Format ``%s``):
   ``dwd_fenster fenster_s=%.2f downloads=%d cache_treffer=%d``        src/providers/dwd.py:893-896
   ``fr_direct_fenster fenster_s=%.2f downloads=%d cache_treffer=%d``  src/providers/meteofrance.py:702-706
   Auswerteregel des Konsumenten: ``.claude/tools/befehl_messlogik.py`` (``_ZEILE_FENSTER``,
   ``kalt_laeufe``: Fensterzeile mit downloads>0 im Fenster [ts-dauer, ts] der Dauerzeile).
   DWD-Fenstergebiet: NICHT in dwd.py, sondern ``src/providers/thunder_routing.py:73-76``
   (first-match): FR 41.3-51.1N/-5.2-9.7E -> ``fr_direct``; DE_ALPEN 43.17-58.09N/-3.95-20.35E
   -> ``de_direct``. DWD-Gebiet = DE_ALPEN-Rechteck OHNE FR-Rechteck (z. B. Freiburg 48.0/7.85
   laeuft ueber fr_direct!). Die Tests laden ``thunder_routing.py`` per Dateipfad und
   verlangen ``thunder_provider_for(lat, lon) == "de_direct"`` (DE) bzw. ``"fr_direct"`` (Korsika).
F2 Dauerzeile ``befehl=%s kanal=%s trip=%s dauer_ms=%d`` (src/services/trip_command_processor.py:
   1050-1054); hinter ``trip=`` steht die Trip-ID (``msg.resolved_preset_id`` bzw.
   ``_find_trip(...).id``, Z. 1108-1111), NICHT der Name.
F3 Telegram-Webhook: ``POST /api/webhooks/telegram/inbound`` (internal/router/router.go; Alt-Route {secret} seit #1814 S2 entfernt);
   das Pfadsegment wird NICHT geprueft, nur der Header ``X-Telegram-Bot-Api-Secret-Token``
   gegen ``TELEGRAM_WEBHOOK_SECRET`` (internal/handler/telegram_webhook.go); Go antwortet
   IMMER 200 nach Weiterleitung an den Kern ``/api/internal/telegram-webhook``
   (api/routers/webhook.py:52-95): Dedup per ``update_id`` (Seen-Set), Update-Form
   ``{"update_id": int, "message": {"chat": {"id": ...}, "text": "..."}}``,
   chat_id wird per ``str(...)`` gelesen (src/services/inbound_telegram_reader.py:174).
   Verknuepfung: ``GET /api/auth/telegram-link`` (Sitzung) -> ``{"link":
   "https://t.me/<bot>?start=<TOKEN>", ...}`` (internal/handler/telegram_connect.go:187-231);
   dann ENTWEDER ``POST /api/internal/telegram-connect {"token","chat_id"}`` mit
   ``X-GZ-Core-Auth`` -- NUR direkt auf 127.0.0.1 und NICHT ueber einen Proxy
   (internal/handler/localhost_guard.go:38-46, ueber die oeffentliche Staging-URL also 403) --
   ODER ein Webhook-Update mit Text ``/start <TOKEN>`` (inbound_telegram_reader.py:189-192, 605ff).
   Bestaetigung nur ueber ``GET /api/auth/telegram-status`` -> ``{"connected": bool}``.
F4 Trip-Ladeweg: ``GET /api/trips/{id}`` + ``PUT /api/trips/{id}`` (router.go:243/245). PUT
   ersetzt ``stages`` KOMPLETT (internal/handler/trip.go ~361), unbekannte JSON-Felder entfallen,
   fehlende Trip-Felder bleiben erhalten. Zusatzfelder der Ersatzwelt sind daher ECHTE
   Modellfelder (internal/model/trip.go): Trip ``shortcode``/``display_config``/``report_config``/
   ``corridors``, Etappe ``start_time``, Wegpunkt ``time_window``/``confirmed``/``origin``.
F5 Konsument tests/e2e/test_push_eingang_befehle_staging.py:191-215: ``journalctl -u
   gregor-python-staging --since <GZ_STAGING_MESSLAUF_SEIT> -o short-iso-precise``; die
   Startzeit muss also von journalctl verstanden werden (``...Z`` und ``+00:00`` gehen,
   geprueft). ``GZ_STAGING_TRIP_DE``/``GZ_STAGING_TRIP_KORSIKA`` filtern ``l["trip"] == <id>``.
F6 Poll-Ausloeser ``POST <kern>/api/scheduler/inbound-commands`` laeuft SYNCHRON unter
   Lock und antwortet ``{"status": "busy"}``, solange ein Lauf haelt (api/routers/scheduler.py:
   197-215). Die Ersatzwelt bildet das ab: der Aufruf kehrt erst nach der Verarbeitung aller
   offenen Mails zurueck (Uhr laeuft weiter). Fuer das AC-7-Paar muss HELP also eingeliefert
   werden, BEVOR der Poll fuer das HEUTE blockiert. Antwortmails brauchen danach noch einige
   Sekunden Transit bis ins Postfach (Resend -> Stalwart).

Schnittstellen-Vertrag ``.claude/tools/staging_messlauf.py``
-----------------------------------------------------------
Konstanten:
    STAGING_EINGANG = "gregor-staging@henemm.com"   (Port-25-Weg, wie staging_befehl_pruefen)
    CHAT_ID_PRAEFIX = "gzp-ungueltig-"
    GESCHAETZTE_LAUFZEIT: timedelta   (2 h .. 2 h 30)

main(argv=None, *, env=None, transport=None, helfer_transport=None, smtp_factory=None,
     imap_factory=None, journal_quelle=None, uhr=None, schlaf=None, laufzeit=None) -> int
    env             dict; wenn angegeben, ERSETZT es vollstaendig .env-Datei und os.environ.
                    Pflicht: GZ_TEST_IMAP_USER, GZ_TEST_IMAP_PASS, GZ_CORE_SHARED_SECRET,
                    GZ_AUTH_USER, GZ_AUTH_PASS, TELEGRAM_WEBHOOK_SECRET. Optional:
                    GZ_STAGING_BASE_URL (Go-API), GZ_STAGING_CORE_URL (Kern, Staging = 8001).
    transport       transport(method, url, headers, body) -> (status, dict) -- Sitzung des
                    Wegwerf-Nutzers; traegt Go-API, Kern-Poll UND Webhook-Posts.
    helfer_transport  eigene Sitzung des Helfer-Kontos (wie StagingApi, nur staging-token).
    smtp_factory    smtplib.SMTP-artig (Port-25-Einlieferung, ``liefere_ein``).
    imap_factory    () -> imaplib-artiges Objekt; nur ``uid(...)``-Befehle (SEARCH/FETCH mit
                    BODY.PEEK/STORE) plus expunge/logout (wie ``finde_antwort``).
    journal_quelle  (seit: datetime aware) -> list[(datetime UTC aware, text)] -- Form wie
                    ``befehl_messlogik.lese_journal``; Standard: journalctl gregor-python-staging.
    uhr             () -> datetime (aware). EINZIGE Zeitquelle fuer Ablauf und Startzeit.
    schlaf          (sekunden) -> None. Einziges Warten (kein time.sleep im Ablauf).
    laufzeit        timedelta; geschaetzte Laufzeit fuer die Zeitfenster-Pruefung
                    (Standard GESCHAETZTE_LAUFZEIT).
    Exit: 0 vollstaendig ausgeloest, 1 Befund, 2 Umgebungsfehler/Sperre.
    stdout: bei Exit 0 GENAU drei Zeilen ``GZ_STAGING_MESSLAUF_SEIT=<ISO-8601 UTC>``,
    ``GZ_STAGING_TRIP_DE=<id>``, ``GZ_STAGING_TRIP_KORSIKA=<id>`` (in dieser Reihenfolge);
    JEDER Fortschritt/Befund geht nach stderr. KONFLIKT mit dem wiederverwendeten Bestand:
    ``_fahre_befehl``/``_fahre_szenario``/``_raeume_auf`` drucken nach stdout (inkl. PASS/FAIL)
    -- diese duerfen so nicht durchgereicht werden (AC-9, AC-16).

Ablauf (Spec "Implementation Details" Schritte 2-10; die Reihenfolge der Phasen 3-8 wird
hier ALS VERTRAG festgeschrieben, abgeleitet aus der Nummerierung der Spec):
    Startpruefung (URL-Sperre AC-13, Zeitfenster AC-11) VOR jeder Anfrage -> Registrierung ->
    genau 2 Trips (DE, Korsika) -> Telegram-Verknuepfung (bestaetigt per telegram-status) ->
    Probelauf [DE HEUTE, DE MORGEN, Korsika HEUTE] + Journalpruefung ->
    E-Mail HELP/CODES/STATUS je 5x -> Telegram help/codes/status je 5x ->
    DE-Serie 5x HEUTE + 5x MORGEN (vor JEDEM Lauf GET->PUT auf einen neuen Ort) ->
    Korsika-Serie 3x HEUTE + 3x MORGEN (Einlieferungen > 600 s auseinander, auch zum
    Korsika-Probelauf) -> AC-7-Paar: HEUTE (DE-Trip, ohne Ortswechsel) + sofort HELP per E-Mail
    -> stdout-Zeilen -> finally: beide Trips loeschen, dann Nutzer.
    ABGELEITETE Regel (nicht Spec-Text): ausser dem AC-7-Paar darf auf ein E-Mail-HEUTE NIE als
    naechster E-Mail-Befehl ein HELP folgen (z. B. Kurzserie nicht mit HELP beginnen, weil der
    Probelauf mit HEUTE endet). Grund: ``befehl_messlogik.paare_heute_help`` paart JEDES HEUTE mit
    dem naechsten HELP desselben Eingangs (ohne Trip-Filter) und der unveraenderte Live-Test
    wertet jedes Paar gegen die 30-s-/90-s-Grenze.
Abgeleitete Zusatzbedingungen (Begruendung):
    * Der DE-Trip hat ausser heute/morgen weitere Etappen ("andere Etappen identisch" pruefbar).
    * Jeder der 10 DE-Serien-Orte liegt >= 120 km von allen anderen UND vom Probelauf-Ort
      ("auf einen NEUEN Ort", AC-2) und im DWD-Gebiet (F1).
    * chat_id: ``str``, beginnt mit CHAT_ID_PRAEFIX, enthaelt den Lauf-Tag (Teil von
      ``gzp-<tag>``), ist NICHT rein numerisch und beginnt nicht mit ``@``. Begruendung:
      negative Zahlen sind in Telegram echte Gruppen-/Supergruppen-IDs (-100...), ein negativer
      Sentinel ist daher nicht "erkennbar ungueltig"; ein nicht-numerischer String ohne ``@``
      adressiert nie einen Chat. Der Kern liest chat_id als String (F3), ``mask_number`` und
      die Konto-Aufloesung arbeiten auf Strings.
    * Das Webhook-Pfadsegment ist NICHT das Secret (Secret nie in einer URL/einem Log).

``staging_befehl_pruefen.baue_trip(szenario, tag, heute, *, ort=None)``:
    ort = (lat, lon) oder None. Ohne ort unveraendert (Basis 47.10/11.00); mit ort beginnt
    der erste Wegpunkt der ersten Etappe exakt bei (lat, lon), das Raster (+0.01 je Etappe/
    Wegpunkt) bleibt.
"""
from __future__ import annotations

import copy
import importlib.util
import math
import re
import sys
import time
from datetime import date, datetime, timedelta, timezone
from email import message_from_bytes
from email.message import EmailMessage
from email.utils import getaddresses
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WERKZEUG = REPO_ROOT / ".claude" / "tools" / "staging_messlauf.py"
PRUEFWEG = REPO_ROOT / ".claude" / "tools" / "staging_befehl_pruefen.py"
MESSLOGIK = REPO_ROOT / ".claude" / "tools" / "befehl_messlogik.py"
ROUTING = REPO_ROOT / "src" / "providers" / "thunder_routing.py"

WIEN = ZoneInfo("Europe/Vienna")
START = datetime(2027, 7, 14, 14, 0, tzinfo=WIEN)
BASIS = "http://127.0.0.1:8091"
KERN = "http://127.0.0.1:8001"
WEBHOOK_SECRET = "tg-geheim-7f3a9c"
KERN_SECRET = "kern-geheim-41b2"
HELFER = ("helfer-konto", "helfer-pw-9x8y")
MAILHOST = "mail.henemm.com"
STAGING_EINGANG = "gregor-staging@henemm.com"
FREMD_TRIPS = ("fremd-trip-1", "fremd-trip-2")


def _lade(pfad: Path, name: str):
    if not pfad.exists():
        pytest.fail(f"Datei fehlt: {pfad.relative_to(REPO_ROOT)}")
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, pfad)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    try:
        spec.loader.exec_module(mod)
    except BaseException:
        sys.modules.pop(name, None)
        raise
    return mod


def _werkzeug():
    return _lade(WERKZEUG, "staging_messlauf_unter_test")


def _pruefweg():
    return _lade(PRUEFWEG, "staging_befehl_pruefen_fuer_messlauf")


def _messlogik():
    return _lade(MESSLOGIK, "befehl_messlogik_fuer_messlauf")


def _routing():
    return _lade(ROUTING, "thunder_routing_fuer_messlauf")


def _km(a, b) -> float:
    (la1, lo1), (la2, lo2) = a, b
    p1, p2 = math.radians(la1), math.radians(la2)
    dp, dl = p2 - p1, math.radians(lo2 - lo1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0 * math.asin(math.sqrt(h))


_WORTE = {"help": "HELP", "hilfe": "HELP", "codes": "CODES", "kuerzel": "CODES",
          "kürzel": "CODES", "status": "STATUS", "heute": "HEUTE", "morgen": "MORGEN"}


def _befehl_aus(text: str) -> str:
    wort = (text or "").strip().split()
    return _WORTE.get(wort[0].lower(), "UNKNOWN") if wort else "UNKNOWN"


# ---------------------------------------------------------------------------
# Ersatz-Staging-Welt
# ---------------------------------------------------------------------------

class _Uhr:
    def __init__(self, start: datetime):
        self.t = start.astimezone(timezone.utc)
        self.schlaf_aufrufe = 0

    def jetzt(self) -> datetime:
        return self.t

    def schlaf(self, s) -> None:
        assert s >= 0, f"negativer Schlaf {s}"
        self.schlaf_aufrufe += 1
        self.t = self.t + timedelta(seconds=float(s))


class _Abbruch:
    """Stoerung: wirft ``exc`` beim n-ten Ereignis der Art ``art``."""

    def __init__(self, art: str, n: int, exc: BaseException):
        self.art, self.n, self.exc, self.zaehler = art, n, exc, 0

    def pruefe(self, art: str) -> None:
        if art == self.art:
            self.zaehler += 1
            if self.zaehler == self.n:
                raise self.exc


class _Welt:
    """Ersatz fuer Staging: Go-API, Kern, Webhook, Stalwart, Journal (siehe F1-F6)."""

    DAUER_S = {"de": 25.0, "korsika": 30.0, "kurz": 2.0, "telegram": 1.5}
    TRANSIT_S = 4.0
    CRON_S = 60.0

    def __init__(self, *, start=START, basis=BASIS, kern=KERN, warm=(), link_kaputt=None,
                 loeschen_scheitert=(), abbruch: _Abbruch | None = None, keine_antwort=(),
                 ohne_dauerzeile=(), telegram_still=(), telegram_verzoegerung_s=0.0,
                 ohne_cron=False, verifikationsmail_s=None, antwort_verzoegerung=None,
                 email_zeile_bei_telegram=None, verknuepfung_verzoegerung_s=0.0):
        self.uhr = _Uhr(start)
        self.verknuepfung_verzoegerung_s = verknuepfung_verzoegerung_s  # telegram-status erst danach
        self.verknuepft_ab: datetime | None = None
        self.antwort_verzoegerung = dict(antwort_verzoegerung or {})  # {("STATUS", 1): 300.0}
        self.email_zeile_bei_telegram = email_zeile_bei_telegram  # n: spaete kanal=email-Zeile
        self.keine_antwort = set(keine_antwort)      # {("STATUS", 2)}: n-te Mail dieses Befehls
        self.ohne_dauerzeile = set(ohne_dauerzeile)  # {("de", 0)}: Wetterlauf ohne Dauerzeile
        self.telegram_still = set(telegram_still)    # {3}: n-tes Telegram-Kommando ohne Dauerzeile
        self.telegram_verzoegerung_s = telegram_verzoegerung_s
        self.verifikationsmail_s = verifikationsmail_s  # Verifikationsmail n s nach 1. Einlieferung
        if ohne_cron:
            self.CRON_S = 10.0 ** 9                  # Mails nur ueber den Poll-Ausloeser
        self.befehl_nr: dict[str, int] = {}
        self.telegram_nr = 0
        self.basis, self.kern = basis.rstrip("/"), kern.rstrip("/")
        self.warm = set(warm)                 # {("de", 0), ("korsika", 0), ...}
        self.link_kaputt = link_kaputt        # None | "link500" | "token"
        self.loeschen_scheitert = set(loeschen_scheitert)  # {"trip", "nutzer"}
        self.abbruch = abbruch
        self.seq = 0
        self.ereignisse: list[dict] = []
        self.anfragen: list[dict] = []
        self.journal: list[tuple[datetime, str]] = []
        self.postfach: list[dict] = []        # {uid, an, roh, sichtbar_ab, cmd}
        self.offen: list[dict] = []           # eingelieferte, unverarbeitete Mails
        self.verarbeitet_bis = self.uhr.t
        self.nutzer: dict[str, dict] = {}
        self.geloeschte_nutzer: list[str] = []
        self.trips: dict[str, dict] = {}
        self.besitzer: dict[str, str] = {}
        self.angelegt: list[dict] = []
        self.geloeschte_trips: list[str] = []
        self.put_historie: list[dict] = []
        self.tokens: dict[str, str] = {}
        self.gesehene_updates: set = set()
        self.zaehler = {"transport": 0, "helfer": 0, "smtp": 0, "imap": 0, "journal": 0}
        self.aktiv = 0
        self.max_aktiv = 0
        self.wetterlauf_nr = {"de": 0, "korsika": 0}
        self.kalt_orte: set = set()
        self.korsika_letzter_abruf: datetime | None = None
        self.uid = 100
        for i, tid in enumerate(FREMD_TRIPS):
            self.trips[tid] = {"id": tid, "name": f"Fremder Trip {i}", "stages": [
                {"id": "S1", "name": "X", "date": "2027-07-14", "waypoints": [
                    {"id": "W1", "name": "A", "lat": 46.5, "lon": 11.3, "elevation_m": 900}]}]}
            self.besitzer[tid] = "fremder-nutzer"
        self.fremd_vorher = copy.deepcopy({t: self.trips[t] for t in FREMD_TRIPS})

    # -- Werkzeug-Raender -------------------------------------------------

    def env(self, **extra) -> dict:
        werte = {"GZ_TEST_IMAP_USER": "gregor-test", "GZ_TEST_IMAP_PASS": "imap-pw-123",
                 "GZ_CORE_SHARED_SECRET": KERN_SECRET, "GZ_AUTH_USER": HELFER[0],
                 "GZ_AUTH_PASS": HELFER[1], "TELEGRAM_WEBHOOK_SECRET": WEBHOOK_SECRET,
                 "GZ_STAGING_BASE_URL": self.basis, "GZ_STAGING_CORE_URL": self.kern}
        werte.update(extra)
        return {k: v for k, v in werte.items() if v is not None}

    def transport_fuer(self, rolle: str):
        welt, sitzung = self, {"user": None}

        def transport(method, url, headers, body):
            welt.zaehler["transport" if rolle == "nutzer" else "helfer"] += 1
            welt.aktiv += 1
            welt.max_aktiv = max(welt.max_aktiv, welt.aktiv)
            try:
                return welt._http(rolle, sitzung, method, url, dict(headers or {}),
                                  copy.deepcopy(body))
            finally:
                welt.aktiv -= 1
        return transport

    def smtp_factory(self):
        welt = self

        class _Smtp:
            def __init__(self, host="", port=0, *a, **k):
                welt.zaehler["smtp"] += 1
                self.host, self.port = host, port

            def __enter__(self):
                return self

            def __exit__(self, *exc):
                return False

            def ehlo(self, *a, **k):
                return (250, b"ok")

            helo = ehlo

            def sendmail(self, von, an, roh, *a, **k):
                if isinstance(an, str):
                    an = [an]
                if isinstance(roh, str):
                    roh = roh.encode()
                welt._mail_ein(self.host, self.port, von, list(an), roh)
                return {}

            def send_message(self, msg, from_addr=None, to_addrs=None, *a, **k):
                von = from_addr or getaddresses([msg["From"]])[0][1]
                an = to_addrs or [x for _, x in getaddresses(msg.get_all("To", []))]
                return self.sendmail(von, an, msg.as_bytes())

            def quit(self):
                return (221, b"bye")

            close = quit
        return _Smtp

    def imap_factory(self):
        def fabrik():
            self.zaehler["imap"] += 1
            return _Imap(self)
        return fabrik

    def journal_quelle(self, seit):
        self.zaehler["journal"] += 1
        self._fortschreiben()
        if isinstance(seit, str):
            seit = datetime.fromisoformat(seit.replace("Z", "+00:00"))
        if seit.tzinfo is None:
            seit = seit.replace(tzinfo=timezone.utc)
        return [(t, z) for t, z in self.journal if seit <= t <= self.uhr.t]

    def lauf(self, mod, **kw):
        """EIN Aufruf von main() mit ALLEN Raendern injiziert (nie ein Standardrand)."""
        argumente = dict(env=self.env(), transport=self.transport_fuer("nutzer"),
                         helfer_transport=self.transport_fuer("helfer"),
                         smtp_factory=self.smtp_factory(), imap_factory=self.imap_factory(),
                         journal_quelle=self.journal_quelle, uhr=self.uhr.jetzt,
                         schlaf=self.uhr.schlaf, laufzeit=None)
        argumente.update(kw)
        return mod.main([], **argumente)

    # -- interne Mechanik ---------------------------------------------------

    def _ereignis(self, art: str, **daten) -> dict:
        self.seq += 1
        e = {"seq": self.seq, "art": art, "t": self.uhr.t, **daten}
        self.ereignisse.append(e)
        return e

    def _log(self, t: datetime, text: str) -> None:
        self.journal.append((t, f"gregor20 python3[4711]: [INFO] {text}"))
        self.journal.sort(key=lambda z: z[0])

    def _user_by_mail(self, adresse: str):
        for name, u in self.nutzer.items():
            if u["email"].lower() == adresse.lower():
                return name
        return None

    def _trip_by_name(self, user: str, name: str):
        for tid, t in self.trips.items():
            if self.besitzer.get(tid) == user and t.get("name") == name:
                return t
        return None

    def _trip_art(self, trip: dict) -> str:
        wp = trip["stages"][0]["waypoints"][0]
        return "korsika" if _routing().thunder_provider_for(wp["lat"], wp["lon"]) == "fr_direct" else "de"

    def staging_egress_gesperrt(self) -> bool:
        return self.basis.startswith("https://staging.gregor20.henemm.com")

    def _heute(self, t: datetime) -> date:
        return t.astimezone(WIEN).date()

    def _etappe_fuer(self, trip: dict, befehl: str, t: datetime):
        ziel = self._heute(t) + timedelta(days=1 if befehl == "MORGEN" else 0)
        return next((s for s in trip["stages"] if s.get("date") == ziel.isoformat()), None)

    def _mail_ein(self, host, port, von, an, roh):
        if self.abbruch:
            self.abbruch.pruefe("smtp")
        msg = message_from_bytes(roh)
        betreff = str(msg.get("Subject", ""))
        m = re.match(r"\s*\[(?P<trip>[^\]]+)\]\s*(?P<rest>.*)", betreff)
        teil = next((p for p in msg.walk() if p.get_content_type() == "text/plain"), None)
        text = (teil.get_payload(decode=True) or b"").decode("utf-8", "replace") if teil else ""
        zeile = next((z for z in text.splitlines() if z.strip()), "") or (m.group("rest") if m else "")
        befehl = _befehl_aus(zeile)
        user = self._user_by_mail(von)
        trip = self._trip_by_name(user, m.group("trip")) if (m and user) else None
        stufen = copy.deepcopy(trip["stages"]) if trip else None
        cmd = self._ereignis("smtp", host=host, port=port, von=von, an=an, betreff=betreff,
                             befehl=befehl, trip_id=trip["id"] if trip else None,
                             trip_art=self._trip_art(trip) if trip else None, stufen=stufen,
                             antwort_uid=None, abgeholt_seq=None, bereit=None)
        self.offen.append(cmd)
        if self.verifikationsmail_s is not None and user and len(self.mails()) == 1:
            self._verifikationsmail(von)

    def _verifikationsmail(self, an: str) -> None:
        """Go-Systemmail an die Plus-Adresse (internal/mail/verify.go:33), keine Befehlsantwort."""
        m = EmailMessage()
        m["From"], m["To"] = "gregor_zwanzig@henemm.com", an
        m["Subject"] = "Bestätige deine E-Mail-Adresse für Gregor 20"
        m.set_content("Bitte bestaetigen\n")
        self.uid += 1
        self.postfach.append({"uid": self.uid, "an": an, "roh": m.as_bytes(), "cmd": None,
                              "sichtbar_ab": self.uhr.t + timedelta(seconds=self.verifikationsmail_s)})

    def _verarbeite(self, cmd: dict, beginn: datetime) -> datetime:
        befehl, art = cmd["befehl"], cmd["trip_art"]
        self.befehl_nr[befehl] = self.befehl_nr.get(befehl, 0) + 1
        stumm = (befehl, self.befehl_nr[befehl]) in self.keine_antwort
        wetter = befehl in ("HEUTE", "MORGEN") and art is not None
        nr = None
        dauer = self.DAUER_S[art] if wetter else self.DAUER_S["kurz"]
        ende = beginn + timedelta(seconds=dauer)
        if wetter:
            nr = self.wetterlauf_nr[art]
            self.wetterlauf_nr[art] += 1
            if art == "de":
                etappe = self._etappe_fuer({"stages": cmd["stufen"]}, befehl, cmd["t"])
                wp = etappe["waypoints"][0] if etappe else {"lat": 0, "lon": 0}
                # Echter Cache haengt am ORT, nicht am Befehl: MORGEN am Ort von HEUTE ist warm.
                schluessel = (round(wp["lat"], 1), round(wp["lon"], 1))
                kalt = schluessel not in self.kalt_orte
                self.kalt_orte.add(schluessel)
                marker = "dwd_fenster"
            else:
                letzte = self.korsika_letzter_abruf
                kalt = letzte is None or (beginn - letzte).total_seconds() > 600
                self.korsika_letzter_abruf = beginn
                marker = "fr_direct_fenster"
            if (art, nr) in self.warm:
                kalt = False
            downloads = 415 if (kalt and art == "de") else (96 if kalt else 0)
            if art == "korsika" and self.staging_egress_gesperrt():
                pass   # egress_guard sperrt Meteo-France auf Staging: nie fr_direct_fenster (AC-19)
            else:
                self._log(beginn + timedelta(seconds=1),
                          f"providers.x: {marker} fenster_s=4.20 downloads={downloads} "
                          f"cache_treffer={0 if downloads else 415}")
        if (art, nr) not in self.ohne_dauerzeile:
            self._log(ende, f"services.trip_command_processor: befehl={befehl} kanal=email "
                            f"trip={cmd['trip_id'] or '-'} dauer_ms={int(dauer * 1000)}")
        self.verarbeitet_bis = ende
        if stumm:
            return ende
        antwort = EmailMessage()
        antwort["From"] = "gregor_zwanzig@henemm.com"
        antwort["To"] = cmd["von"]
        name = cmd["betreff"].split("]", 1)[0].lstrip(" [") if "]" in cmd["betreff"] else "?"
        # Betreffe wie trip_command_processor.py: "Hilfe" (:1401), "Kürzel" (:1412), "[Trip] Status"
        antwort["Subject"] = {"HELP": "Hilfe", "CODES": "Kürzel"}.get(
            befehl, f"[{name}] {befehl.capitalize()}")
        if wetter:
            antwort["X-GZ-Mail-Type"] = "trip-briefing"
        antwort.set_content(f"Antwort auf {befehl}\n")
        self.uid += 1
        extra = self.antwort_verzoegerung.get((befehl, self.befehl_nr[befehl]), 0.0)
        bereit = ende + timedelta(seconds=self.TRANSIT_S + extra)
        self.postfach.append({"uid": self.uid, "an": cmd["von"], "roh": antwort.as_bytes(),
                              "sichtbar_ab": bereit, "cmd": cmd})
        cmd["antwort_uid"], cmd["bereit"] = self.uid, bereit
        self.verarbeitet_bis = ende
        return ende

    def _fortschreiben(self) -> None:
        """Cron-Takt: Mails, die >= 60 s liegen, werden ohne Poll-Ausloeser verarbeitet."""
        while self.offen and self.offen[0]["t"] + timedelta(seconds=self.CRON_S) <= self.uhr.t:
            cmd = self.offen.pop(0)
            beginn = max(cmd["t"] + timedelta(seconds=self.CRON_S), self.verarbeitet_bis)
            self._verarbeite(cmd, beginn)

    def _poll(self) -> tuple[int, dict]:
        self._fortschreiben()
        if self.verarbeitet_bis > self.uhr.t:
            return 200, {"status": "busy"}
        e = self._ereignis("poll_start")
        n = 0
        while self.offen:
            cmd = self.offen.pop(0)
            beginn = max(self.uhr.t, self.verarbeitet_bis)
            ende = self._verarbeite(cmd, beginn)
            self.uhr.t = max(self.uhr.t, ende)   # synchroner Lauf (F6)
            n += 1
        self._ereignis("poll_ende", start_seq=e["seq"])
        # #1405 S4b AC-23: der Python-Core meldet den Fehlerzaehler des Laufs mit.
        return 200, {"status": "ok", "count": n, "processed": n, "failed": 0}

    def _webhook(self, headers, body) -> tuple[int, dict]:
        kopf = {k.lower(): v for k, v in headers.items()}
        if kopf.get("x-telegram-bot-api-secret-token") != WEBHOOK_SECRET:
            return 403, {"error": "forbidden"}
        upd = body or {}
        msg = upd.get("message") or {}
        text = str(msg.get("text", ""))
        chat = str((msg.get("chat") or {}).get("id", ""))
        uid = upd.get("update_id")
        dup = isinstance(uid, int) and uid in self.gesehene_updates
        self._ereignis("webhook", update_id=uid, chat_id=(msg.get("chat") or {}).get("id"),
                       text=text, duplikat=dup)
        if dup:
            return 200, {"status": "duplicate"}
        if isinstance(uid, int):
            self.gesehene_updates.add(uid)
        if text.startswith("/start "):
            tok = text.split(" ", 1)[1].strip()
            if self.link_kaputt != "token" and tok in self.tokens:
                self.nutzer[self.tokens.pop(tok)]["chat_id"] = chat
                self.verknuepft_ab = self.uhr.t + timedelta(seconds=self.verknuepfung_verzoegerung_s)
            return 200, {"status": "ok"}
        user = next((n for n, u in self.nutzer.items() if u.get("chat_id") == chat and chat), None)
        if user is None:
            return 200, {"status": "ok"}
        befehl = _befehl_aus(text)
        beginn = max(self.uhr.t, self.verarbeitet_bis)
        ende = beginn + timedelta(seconds=self.DAUER_S["telegram"])
        eigene = [t for t, b in self.besitzer.items() if b == user]
        self.telegram_nr += 1
        if self.telegram_nr == self.email_zeile_bei_telegram:   # spaete Mail-Dauerzeile, 3 s danach
            self._log(beginn + timedelta(seconds=3),
                      f"services.trip_command_processor: befehl=STATUS kanal=email "
                      f"trip={eigene[0] if eigene else '-'} dauer_ms=2000")
        if self.telegram_nr not in self.telegram_still:   # Journal-Zeile erst nach Verzoegerung
            self._log(ende + timedelta(seconds=self.telegram_verzoegerung_s),
                      f"services.trip_command_processor: befehl={befehl} kanal=telegram "
                      f"trip={eigene[0] if eigene else '-'} dauer_ms=1500")
        self.uhr.t = max(self.uhr.t, ende)
        self.verarbeitet_bis = ende
        return 200, {"status": "ok"}

    def _http(self, rolle, sitzung, method, url, headers, body):
        self._fortschreiben()
        self._ereignis("http", rolle=rolle, method=method, url=url, headers=headers,
                       body=copy.deepcopy(body))
        self.anfragen.append({"rolle": rolle, "method": method, "url": url,
                              "headers": headers, "body": body, "seq": self.seq})
        if url.startswith(self.kern + "/"):
            pfad = url[len(self.kern):]
            if method == "POST" and pfad == "/api/scheduler/inbound-commands":
                if headers.get("X-GZ-Core-Auth") != KERN_SECRET:
                    return 401, {"error": "unauthorized"}
                return self._poll()
            return 404, {"error": "not_found"}
        if not url.startswith(self.basis + "/"):
            return 404, {"error": "fremder_host"}
        pfad = url[len(self.basis):].split("?", 1)[0]
        user = sitzung["user"]
        body = body or {}
        if method == "GET" and pfad == "/api/health":
            return 200, {"status": "ok"}
        if method == "POST" and pfad == "/api/auth/login":
            if (body.get("username"), body.get("password")) == HELFER and rolle == "helfer":
                sitzung["user"] = HELFER[0]
                return 200, {}
            u = self.nutzer.get(body.get("username"))
            if u and u["pw"] == body.get("password"):
                if not u["verifiziert"]:
                    return 403, {"error": "email_not_verified"}
                sitzung["user"] = body["username"]
                return 200, {}
            return 401, {"error": "invalid_credentials"}
        if method == "POST" and pfad == "/api/auth/register":
            name = body.get("username")
            if not name or name in self.nutzer:
                return 409, {"error": "exists"}
            self.nutzer[name] = {"pw": body.get("password"), "email": body.get("email"),
                                 "verifiziert": False, "chat_id": ""}
            self._ereignis("registriert", name=name)
            return 201, {}
        if method == "POST" and pfad == "/api/auth/verify-email/staging-token":
            if user != HELFER[0] or body.get("username") not in self.nutzer:
                return 403, {"error": "forbidden"}
            return 200, {"token": "vt-" + body["username"]}
        if method == "POST" and pfad == "/api/auth/verify-email":
            name = body.get("user")
            if name in self.nutzer and body.get("token") == "vt-" + name:
                self.nutzer[name]["verifiziert"] = True
                return 200, {}
            return 400, {"error": "bad_token"}
        if user is None or user == HELFER[0]:
            return 401, {"error": "unauthorized"}
        if method == "POST" and pfad == "/api/auth/account/delete":
            if "nutzer" in self.loeschen_scheitert:
                return 500, {"error": "internal"}
            self.nutzer.pop(user, None)
            self.geloeschte_nutzer.append(user)
            sitzung["user"] = None
            return 200, {}
        if method == "GET" and pfad == "/api/auth/telegram-link":
            if self.link_kaputt == "link500":
                return 500, {"error": "token_store_unavailable"}
            tok = f"tok{len(self.tokens) + 1}x{self.seq}"
            self.tokens[tok] = user
            return 200, {"link": f"https://t.me/gregor_staging_bot?start={tok}",
                         "connected": bool(self.nutzer[user]["chat_id"]), "chat_id_suffix": ""}
        if method == "GET" and pfad == "/api/auth/telegram-status":
            cid = self.nutzer[user]["chat_id"]
            if cid and self.verknuepft_ab is not None and self.uhr.t < self.verknuepft_ab:
                cid = None                           # Verknuepfung noch nicht sichtbar
            return 200, {"connected": bool(cid), "chat_id_suffix": ("..." + cid[-3:]) if cid else ""}
        if method == "POST" and pfad == "/api/internal/telegram-connect":
            if not self.basis.startswith("http://127.0.0.1"):
                return 403, {"error": "forbidden"}      # localhost_guard: proxied (F3)
            if headers.get("X-GZ-Core-Auth") != KERN_SECRET:
                return 401, {"error": "unauthorized"}
            tok = body.get("token")
            if self.link_kaputt == "token" or tok not in self.tokens:
                return 422, {"error": "token_invalid"}
            self.nutzer[self.tokens.pop(tok)]["chat_id"] = str(body.get("chat_id"))
            self.verknuepft_ab = self.uhr.t + timedelta(seconds=self.verknuepfung_verzoegerung_s)
            return 200, {"status": "connected"}
        if method == "GET" and pfad == "/api/trips":
            return 200, {"trips": [copy.deepcopy(t) for i, t in self.trips.items()
                                   if self.besitzer.get(i) == user]}
        if method == "POST" and pfad == "/api/trips":
            if self.abbruch:
                self.abbruch.pruefe("trip_post")
            eigene = [i for i, b in self.besitzer.items() if b == user]
            if len(eigene) >= 3:
                return 403, {"error": "trip_limit"}
            tid = body.get("id")
            if not tid or tid in self.trips:
                return 400, {"error": "validation_error"}
            trip = copy.deepcopy(body)
            trip.update({"shortcode": "GZ7X", "display_config": {"theme": "kontrast"},
                         "report_config": {"morning_time": "06:30"},
                         "corridors": [{"id": "K1", "width_m": 250}]})
            for s in trip.get("stages", []):
                s["start_time"] = "07:15"
                for w in s.get("waypoints", []):
                    w.update({"time_window": "08:00-10:00", "confirmed": True, "origin": "manual"})
            self.trips[tid] = trip
            self.besitzer[tid] = user
            self.angelegt.append(copy.deepcopy(body))
            return 201, copy.deepcopy(trip)
        m = re.fullmatch(r"/api/trips/([^/]+)", pfad)
        if m:
            tid = m.group(1)
            if self.besitzer.get(tid) != user:
                return 404, {"error": "not_found"}
            if method == "GET":
                return 200, copy.deepcopy(self.trips[tid])
            if method == "PUT":
                if self.abbruch:
                    self.abbruch.pruefe("put")
                vorher = copy.deepcopy(self.trips[tid])
                neu = copy.deepcopy(vorher)
                if "name" in body:
                    neu["name"] = body["name"]
                if "stages" in body:   # komplett ersetzt, unbekannte Felder entfallen (F4)
                    erlaubt_s = {"id", "name", "date", "waypoints", "start_time"}
                    erlaubt_w = {"id", "name", "lat", "lon", "elevation_m", "time_window",
                                 "confirmed", "origin", "arrival_override"}
                    neu["stages"] = [
                        {**{k: v for k, v in s.items() if k in erlaubt_s},
                         "waypoints": [{k: v for k, v in w.items() if k in erlaubt_w}
                                       for w in s.get("waypoints", [])]}
                        for s in body["stages"]]
                for k in ("display_config", "report_config"):
                    if isinstance(body.get(k), dict):
                        neu[k] = {**vorher.get(k, {}), **body[k]}
                self.trips[tid] = neu
                self.put_historie.append({"trip": tid, "vorher": vorher,
                                          "nachher": copy.deepcopy(neu), "body": body,
                                          "seq": self.seq, "t": self.uhr.t})
                return 200, copy.deepcopy(neu)
            if method == "DELETE":
                if "trip" in self.loeschen_scheitert:
                    return 500, {"error": "internal"}
                self.trips.pop(tid)
                self.besitzer.pop(tid)
                self.geloeschte_trips.append(tid)
                return 204, {}
        m = re.fullmatch(r"/api/webhooks/telegram/inbound", pfad)  # #1814 S2: Alt-Route {secret} entfernt
        if m and method == "POST":
            return self._webhook(headers, body)
        return 404, {"error": "not_found"}

    # -- Auswertehilfen fuer die Tests -------------------------------------

    def mails(self) -> list[dict]:
        return [e for e in self.ereignisse if e["art"] == "smtp"]

    def wetter(self, art: str) -> list[dict]:
        return [e for e in self.mails() if e["trip_art"] == art and e["befehl"] in ("HEUTE", "MORGEN")]

    def kommando_posts(self) -> list[dict]:
        return [e for e in self.ereignisse
                if e["art"] == "webhook" and not str(e["text"]).startswith("/start")]

    def registrierter_nutzer(self):
        e = next((e for e in self.ereignisse if e["art"] == "registriert"), None)
        return e["name"] if e else None

    def ids(self, art: str) -> list[str]:
        return [t["id"] for t in self.angelegt if self._trip_art(t) == art]

    def eigene_reste(self) -> list[str]:
        name = self.registrierter_nutzer()
        return [t for t, b in self.besitzer.items() if b == name]


class _Imap:
    """imaplib-artig ueber dem Welt-Postfach; nur sichtbare Mails (Transit), TO = Teilstring."""

    def __init__(self, welt: _Welt):
        self.w = welt

    def _sichtbar(self):
        self.w._fortschreiben()
        return [m for m in self.w.postfach if m["sichtbar_ab"] <= self.w.uhr.t]

    def select(self, *a, **k):
        return ("OK", [str(len(self._sichtbar())).encode()])

    def login(self, *a, **k):
        return ("OK", [b""])

    def logout(self):
        return ("BYE", [b""])

    def close(self):
        return ("OK", [b""])

    def expunge(self):
        return ("OK", [b""])

    def noop(self):
        return ("OK", [b""])

    def uid(self, befehl, *args):
        befehl = befehl.upper()
        if befehl == "SEARCH":
            krit = [a for a in args if a is not None]
            treffer = self._sichtbar()
            if len(krit) >= 2 and str(krit[0]).upper() == "TO":
                nadel = str(krit[1]).strip('"').lower()
                treffer = [m for m in treffer if nadel in m["an"].lower()]
            return ("OK", [" ".join(str(m["uid"]) for m in treffer).encode()])
        if befehl == "FETCH":
            uid = int(str(args[0]).split(":")[0])
            m = next((m for m in self._sichtbar() if m["uid"] == uid), None)
            if m is None:
                return ("OK", [None])
            cmd = m["cmd"]
            if cmd is not None and cmd["abgeholt_seq"] is None:
                cmd["abgeholt_seq"] = self.w._ereignis("abgeholt", uid=uid)["seq"]
            teil = str(args[1]).upper() if len(args) > 1 else ""
            roh = m["roh"]
            if "HEADER" in teil:
                roh = roh.split(b"\n\n", 1)[0] + b"\r\n\r\n"
            return ("OK", [(f"{uid} (UID {uid} BODY[] {{{len(roh)}}}".encode(), roh), b")"])
        if befehl == "STORE":
            return ("OK", [b""])
        return ("NO", [b"unbekannt"])


def _ausgabe(capsys):
    erg = capsys.readouterr()
    return erg.out, erg.err


def _erfolgslauf(capsys, **welt_kw):
    mod = _werkzeug()
    welt = _Welt(**welt_kw)
    rc = welt.lauf(mod)
    out, err = _ausgabe(capsys)
    return welt, rc, out, err


def _env_zeilen(out: str) -> dict:
    return dict(z.split("=", 1) for z in out.splitlines() if "=" in z)


# Je Probelauf-Befund der EXAKTE Umfang bis zum Abbruch (Reihenfolge: Korsika HEUTE, DE HEUTE,
# Ortswechsel, DE MORGEN). Schluessel = (art, n-ter Wetterlauf dieser Art) des Befunds.
_PROBE_ABBRUCH = {("korsika", 0): {"de": 0, "put": 0},   # Korsika zuerst: noch nichts an DE
                  ("de", 0): {"de": 1, "put": 0},        # HEUTE-Befund: sofort, KEIN Ortswechsel
                  ("de", 1): {"de": 2, "put": 1}}        # MORGEN-Befund: nach dem einen Wechsel


def _nur_probelauf_ortswechsel(welt, fall) -> None:
    """AC-1/AC-17: nach einem Probelauf-Befund exakt der Umfang bis zum Befund -- nach HEUTE-DE
    weder Ortswechsel noch MORGEN (Adversary F001), nach MORGEN-DE genau der EINE Wechsel."""
    soll = _PROBE_ABBRUCH[fall]
    puts, de_laeufe = welt.put_historie, welt.wetter("de")
    assert len(de_laeufe) == soll["de"], (
        f"Befund {fall}: {len(de_laeufe)} DE-Wetterlaeufe, erwartet genau {soll['de']}")
    assert len(puts) == soll["put"], (
        f"Befund {fall}: {len(puts)} Ortswechsel (PUT), erwartet genau {soll['put']}")
    assert len(welt.wetter("korsika")) == 1, "Korsika-Probelauf nicht genau einmal"
    if puts:
        assert puts[0]["trip"] == welt.ids("de")[0], "Probelauf-Wechsel nicht am DE-Trip"
        assert de_laeufe[0]["seq"] < puts[0]["seq"] < de_laeufe[1]["seq"], (
            "Ortswechsel liegt nicht zwischen Probelauf-HEUTE und -MORGEN")


# ---------------------------------------------------------------------------
# AC-1 Probelauf
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("warm", [("de", 0), ("de", 1), ("korsika", 0)],
                         ids=["de-heute-warm", "de-morgen-warm", "korsika-warm"])
def test_warmer_probelauf_bricht_mit_befund_ab_ohne_serie_und_raeumt_auf(capsys, warm):
    welt, rc, out, err = _erfolgslauf(capsys, warm={warm})
    assert rc == 1, f"warmer Probelauf {warm}: Exit {rc}, erwartet 1 (Befund)"
    kurz = [m for m in welt.mails() if m["befehl"] in ("HELP", "CODES", "STATUS")]
    assert not kurz, f"nach warmem Probelauf trotzdem Kurzbefehle eingeliefert: {len(kurz)}"
    assert not welt.kommando_posts(), "nach warmem Probelauf trotzdem Telegram-Serie gepostet"
    assert len(welt.wetter("de")) <= 2 and len(welt.wetter("korsika")) <= 1, (
        "nach warmem Probelauf weitere Wetterlaeufe (Serie) ausgeloest")
    _nur_probelauf_ortswechsel(welt, warm)
    assert welt.angelegt and not welt.eigene_reste(), f"Trips nicht aufgeraeumt: {welt.eigene_reste()}"
    assert welt.registrierter_nutzer() in welt.geloeschte_nutzer, "Wegwerf-Nutzer nicht geloescht"
    assert "GZ_STAGING_MESSLAUF_SEIT" not in out, "Befund-Lauf meldet Env-Zeilen wie ein voller Lauf"


def test_kalter_probelauf_fuehrt_zur_serie(capsys):
    welt, rc, out, err = _erfolgslauf(capsys)
    assert rc == 0, f"voller Ersatz-Lauf: Exit {rc}; stderr: {err[-800:]}"
    assert len(welt.wetter("de")) == 13 and len(welt.wetter("korsika")) == 7, (
        f"Wetterlaeufe DE {len(welt.wetter('de'))} (erwartet 2 Probe + 10 Serie + 1 Paar), "
        f"Korsika {len(welt.wetter('korsika'))} (erwartet 1 Probe + 6 Serie)")
    probe_de = {m["befehl"] for m in welt.wetter("de")[:2]}
    assert probe_de == {"HEUTE", "MORGEN"}, f"DE-Probelauf: {probe_de}"
    assert welt.wetter("korsika")[0]["befehl"] == "HEUTE"
    erste_kurz = next(m["seq"] for m in welt.mails() if m["befehl"] in ("HELP", "CODES", "STATUS"))
    probe = welt.wetter("de")[:2] + welt.wetter("korsika")[:1]
    assert all(p["seq"] < erste_kurz for p in probe), "Probelauf liegt nicht VOR der Serie"
    assert welt.zaehler["journal"] >= 1, "Journal nie gelesen -- Probelauf ungeprueft"


# ---------------------------------------------------------------------------
# AC-2 Kaelte DE per Ortswechsel (Read-Modify-Write)
# ---------------------------------------------------------------------------

def _ort(lauf: dict, welt: _Welt):
    etappe = welt._etappe_fuer({"stages": lauf["stufen"]}, lauf["befehl"], lauf["t"])
    assert etappe is not None, f"DE-Trip ohne Etappe fuer {lauf['befehl']} am Lauftag"
    return etappe


def test_de_serie_wechselt_ort_per_read_modify_write_ohne_feldverlust(capsys):
    welt, rc, out, err = _erfolgslauf(capsys)
    assert rc == 0, f"Exit {rc}; stderr: {err[-800:]}"
    de_id = welt.ids("de")[0]
    puts = [p for p in welt.put_historie if p["trip"] == de_id]
    assert len(puts) >= 10, f"nur {len(puts)} Ortswechsel (PUT) am DE-Trip, erwartet >= 10"
    heute = welt._heute(START)
    tage = {heute.isoformat(), (heute + timedelta(days=1)).isoformat()}
    for p in puts:
        vor, nach, body = p["vorher"], p["nachher"], p["body"]
        assert {k: v for k, v in vor.items() if k != "stages"} == \
               {k: v for k, v in nach.items() if k != "stages"}, "Trip-Felder ausserhalb der Etappen geaendert/verloren"
        assert [s["id"] for s in vor["stages"]] == [s["id"] for s in nach["stages"]]
        andere = [s for s in vor["stages"] if s["date"] not in tage]
        assert andere, "DE-Trip ohne weitere Etappen -- 'andere Etappen identisch' nicht pruefbar"
        for sv, sn in zip(vor["stages"], nach["stages"]):
            if sv["date"] not in tage:
                assert sv == sn, f"Etappe {sv['id']} (nicht heute/morgen) veraendert"
                continue
            assert {k: v for k, v in sv.items() if k != "waypoints"} == \
                   {k: v for k, v in sn.items() if k != "waypoints"}, f"Etappe {sv['id']}: Felder ausser Orten geaendert"
            assert [w["id"] for w in sv["waypoints"]] == [w["id"] for w in sn["waypoints"]]
            for wv, wn in zip(sv["waypoints"], sn["waypoints"]):
                for k in ("time_window", "confirmed", "origin"):
                    assert wn.get(k) == wv.get(k), f"Wegpunkt-Zusatzfeld {k} verloren"
        for s in body["stages"]:
            assert s.get("start_time") == "07:15", "PUT-Body ohne Etappen-Zusatzfeld start_time"
            for w in s["waypoints"]:
                assert w.get("time_window") == "08:00-10:00" and w.get("confirmed") is True, (
                    "PUT-Body ohne Wegpunkt-Zusatzfelder (Replace statt Read-Modify-Write)")
        gets = [a for a in welt.anfragen if a["method"] == "GET"
                and a["url"].endswith(f"/api/trips/{de_id}") and a["seq"] < p["seq"]]
        frueher = [q for q in welt.put_historie if q["trip"] == de_id and q["seq"] < p["seq"]]
        assert gets and (not frueher or gets[-1]["seq"] > frueher[-1]["seq"]), (
            "PUT ohne vorheriges GET desselben Trips (kein Read-Modify-Write)")


def test_de_serie_nutzt_zehn_neue_orte_mit_120_km_abstand_im_dwd_gebiet(capsys):
    welt, rc, out, err = _erfolgslauf(capsys)
    assert rc == 0, f"Exit {rc}; stderr: {err[-800:]}"
    laeufe = welt.wetter("de")
    serie, probe = laeufe[2:12], laeufe[:2]
    assert sorted(l["befehl"] for l in serie) == ["HEUTE"] * 5 + ["MORGEN"] * 5
    routing = _routing()
    orte = []
    for l in serie:
        etappe = _ort(l, welt)
        for w in etappe["waypoints"]:
            assert routing.thunder_provider_for(w["lat"], w["lon"]) == "de_direct", (
                f"Ort {w['lat']}/{w['lon']} liegt nicht im DWD-Fenstergebiet (thunder_routing)")
        orte.append((etappe["waypoints"][0]["lat"], etappe["waypoints"][0]["lon"]))
    for i in range(len(orte)):
        for j in range(i + 1, len(orte)):
            assert _km(orte[i], orte[j]) >= 120, f"Orte {orte[i]} und {orte[j]}: {_km(orte[i], orte[j]):.0f} km"
    probe_orte = [(_ort(l, welt)["waypoints"][0]["lat"], _ort(l, welt)["waypoints"][0]["lon"]) for l in probe]
    for o in orte:
        for p in probe_orte:
            assert _km(o, p) >= 120, f"Serien-Ort {o} nicht neu gegenueber Probelauf-Ort {p}"
    for k in range(1, len(serie)):
        zwischen = [p for p in welt.put_historie
                    if serie[k - 1]["seq"] < p["seq"] < serie[k]["seq"]]
        assert zwischen, f"vor DE-Serienlauf {k + 1} kein Ortswechsel"


# ---------------------------------------------------------------------------
# AC-3 Korsika-Abstand
# ---------------------------------------------------------------------------

def test_korsika_laeufe_liegen_mehr_als_600_sekunden_auseinander(capsys):
    welt, rc, out, err = _erfolgslauf(capsys)
    assert rc == 0, f"Exit {rc}; stderr: {err[-800:]}"
    laeufe = welt.wetter("korsika")
    serie = laeufe[1:]
    assert sorted(l["befehl"] for l in serie) == ["HEUTE"] * 3 + ["MORGEN"] * 3, (
        f"Korsika-Serie: {[l['befehl'] for l in serie]}")
    for a, b in zip(laeufe, laeufe[1:]):
        abstand = (b["t"] - a["t"]).total_seconds()
        assert abstand > 600, f"Korsika-Einlieferungen nur {abstand:.0f} s auseinander (> 600 s noetig)"
    ml = _messlogik()
    kid = welt.ids("korsika")[0]
    dauer = [l for l in ml.dauerzeilen(welt.journal) if l["trip"] == kid]
    kalt = ml.kalt_laeufe(dauer, welt.journal, quellen=("fr_direct_fenster",))
    assert len(kalt) == 7, f"nur {len(kalt)} von 7 Korsika-Laeufen kalt im Ersatz-Journal"
    assert welt.uhr.schlaf_aufrufe > 0, "Wartezeit nicht ueber die injizierte Uhr/schlaf"


# ---------------------------------------------------------------------------
# AC-4 / AC-7 / AC-8 E-Mail-Serie, Paar, seriell
# ---------------------------------------------------------------------------

def _paar_help(welt: _Welt) -> dict:
    letzte_de = welt.wetter("de")[-1]
    naechste = [m for m in welt.mails() if m["seq"] > letzte_de["seq"]]
    assert letzte_de["befehl"] == "HEUTE" and naechste and naechste[0]["befehl"] == "HELP", (
        "AC-7-Paar fehlt: letzter DE-Wetterlauf ist kein HEUTE mit direkt folgendem HELP")
    return naechste[0]


def test_email_kurzbefehle_je_fuenfmal_ueber_port_25_jeweils_nach_der_antwort(capsys):
    welt, rc, out, err = _erfolgslauf(capsys)
    assert rc == 0, f"Exit {rc}; stderr: {err[-800:]}"
    paar = _paar_help(welt)
    kurz = [m for m in welt.mails() if m["befehl"] in ("HELP", "CODES", "STATUS") and m is not paar]
    for b in ("HELP", "CODES", "STATUS"):
        n = sum(1 for m in kurz if m["befehl"] == b)
        assert n == 5, f"{b} per E-Mail {n}x eingeliefert, erwartet genau 5"
    for m in welt.mails():
        assert (m["host"], m["port"]) == (MAILHOST, 25), f"nicht ueber Port 25: {m['host']}:{m['port']}"
        assert [a.lower() for a in m["an"]] == [STAGING_EINGANG], f"falscher Empfaenger {m['an']}"
    mails = welt.mails()
    for vor, nach in zip(mails, mails[1:]):
        if nach is paar:
            continue
        assert vor["abgeholt_seq"] is not None and vor["abgeholt_seq"] < nach["seq"], (
            f"{nach['befehl']} eingeliefert, bevor die Antwort auf {vor['befehl']} abgeholt war")


def test_help_des_paars_wird_vor_der_heute_antwort_eingeliefert(capsys):
    welt, rc, out, err = _erfolgslauf(capsys)
    assert rc == 0, f"Exit {rc}; stderr: {err[-800:]}"
    heute = welt.wetter("de")[-1]
    hilfe = _paar_help(welt)
    assert heute["bereit"] is not None, "HEUTE des Paars nie verarbeitet"
    assert hilfe["t"] < heute["bereit"], "HELP erst eingeliefert, als die HEUTE-Antwort schon vorlag"
    assert heute["abgeholt_seq"] is None or hilfe["seq"] < heute["abgeholt_seq"], (
        "HELP erst nach Abholen der HEUTE-Antwort eingeliefert")
    ml = _messlogik()
    paare = ml.paare_heute_help(ml.dauerzeilen(welt.journal), {"email"}, 300)
    assert len(paare) == 1, (
        f"Konsument (paare_heute_help) findet {len(paare)} E-Mail-Paare, erwartet genau 1 -- ein "
        f"ungewolltes HEUTE->HELP (z. B. Probelauf-HEUTE direkt vor der HELP-Serie) wuerde im "
        f"Live-Test als AC-12-Befund gewertet: {[(h['trip'], x['befehl']) for h, x in paare]}")
    assert paare[0][0]["trip"] == welt.ids("de")[0], "einziges Paar liegt nicht auf dem DE-Trip"


def test_hoechstens_ein_befehl_gleichzeitig_ausser_dem_paar(capsys):
    welt, rc, out, err = _erfolgslauf(capsys)
    assert rc == 0, f"Exit {rc}; stderr: {err[-800:]}"
    paar = _paar_help(welt)
    mails = welt.mails()
    ueberlappend = []
    for m in mails:
        offen = [v for v in mails if v["seq"] < m["seq"]
                 and (v["abgeholt_seq"] is None or v["abgeholt_seq"] > m["seq"])]
        if offen:
            ueberlappend.append((m["befehl"], [v["befehl"] for v in offen]))
    assert ueberlappend == [("HELP", ["HEUTE"])], f"ueberlappende Befehle: {ueberlappend}"
    assert paar["befehl"] == "HELP"
    for p in welt.kommando_posts():
        offen = [v for v in mails if v["seq"] < p["seq"]
                 and (v["abgeholt_seq"] is None or v["abgeholt_seq"] > p["seq"])]
        assert not offen, f"Telegram-Befehl waehrend offener E-Mail {[v['befehl'] for v in offen]}"
    assert welt.max_aktiv == 1, f"{welt.max_aktiv} HTTP-Anfragen (Poll) gleichzeitig"
    starts = [e for e in welt.ereignisse if e["art"] in ("poll_start", "poll_ende")]
    for a, b in zip(starts, starts[1:]):
        assert a["art"] != b["art"], "Poll-Ausloeser ueberlappend gestartet"


# ---------------------------------------------------------------------------
# AC-5 / AC-6 Telegram
# ---------------------------------------------------------------------------

def test_telegram_serie_fuenfzehn_updates_mit_secret_und_eindeutigen_update_ids(capsys):
    welt, rc, out, err = _erfolgslauf(capsys)
    assert rc == 0, f"Exit {rc}; stderr: {err[-800:]}"
    mod = _werkzeug()
    posts = welt.kommando_posts()
    assert len(posts) == 15, f"{len(posts)} Telegram-Befehls-Updates, erwartet 15"
    for b in ("HELP", "CODES", "STATUS"):
        n = sum(1 for p in posts if _befehl_aus(p["text"]) == b)
        assert n == 5, f"Telegram {b}: {n}x, erwartet 5"
    alle = [e for e in welt.ereignisse if e["art"] == "webhook"]
    ids = [e["update_id"] for e in alle]
    assert all(isinstance(i, int) for i in ids), f"update_id nicht ganzzahlig: {ids}"
    assert len(set(ids)) == len(ids), "update_id wiederholt (Dedup-Treffer)"
    assert not any(e["duplikat"] for e in alle)
    hooks = [a for a in welt.anfragen if "/api/webhooks/telegram/" in a["url"]]
    assert hooks, "kein Telegram-Webhook-Aufruf gesehen"
    for a in hooks:
        assert a["url"].endswith("/api/webhooks/telegram/inbound"), f"Alt-Pfad benutzt: {a['url']}"
        kopf = {k.lower(): v for k, v in a["headers"].items()}
        assert kopf.get("x-telegram-bot-api-secret-token") == WEBHOOK_SECRET
        assert WEBHOOK_SECRET not in a["url"], "Secret steht in der Webhook-URL"
    tag = welt.registrierter_nutzer().split("gzp-", 1)[-1]
    chats = {p["chat_id"] for p in posts}
    assert len(chats) == 1, f"mehrere chat_ids: {chats}"
    cid = chats.pop()
    assert isinstance(cid, str) and cid.startswith(mod.CHAT_ID_PRAEFIX), f"chat_id {cid!r}"
    assert not re.fullmatch(r"-?\d+", cid) and not cid.startswith("@"), f"chat_id {cid!r} koennte echt sein"
    assert tag in cid, "chat_id nicht eindeutig je Lauf (Tag fehlt)"
    telegram_dauer = [l for l in _messlogik().dauerzeilen(welt.journal) if l["kanal"] == "telegram"]
    assert len(telegram_dauer) == 15, f"nur {len(telegram_dauer)} Telegram-Befehle verarbeitet (Verknuepfung?)"


def test_chat_id_ist_je_lauf_verschieden(capsys):
    w1, rc1, _, _ = _erfolgslauf(capsys)
    w2, rc2, _, _ = _erfolgslauf(capsys)
    assert rc1 == rc2 == 0
    c1 = {p["chat_id"] for p in w1.kommando_posts()}
    c2 = {p["chat_id"] for p in w2.kommando_posts()}
    assert c1 and c2 and not (c1 & c2), f"chat_id in zwei Laeufen gleich: {c1 & c2}"


@pytest.mark.parametrize("kaputt", ["link500", "token"])
def test_scheiternde_telegram_verknuepfung_ist_ehrlicher_befund(capsys, kaputt):
    welt, rc, out, err = _erfolgslauf(capsys, link_kaputt=kaputt)
    assert rc == 1, f"Verknuepfung kaputt ({kaputt}): Exit {rc}, erwartet 1"
    assert "Telegram nicht verknüpfbar" in out + err, "Befund 'Telegram nicht verknüpfbar' fehlt"
    assert "GZ_STAGING_MESSLAUF_SEIT" not in out and "GZ_STAGING_TRIP_DE" not in out, (
        "Lauf trotz fehlender Telegram-Serie als vollstaendig gemeldet")
    assert not welt.eigene_reste() and welt.registrierter_nutzer() in welt.geloeschte_nutzer
    # F-A2-01 (AC-6): nach gescheiterter Verknuepfung geht KEIN Telegram-Kommando mehr ab
    start = [e["seq"] for e in welt.ereignisse
             if e["art"] == "webhook" and str(e["text"]).startswith("/start")]
    ab = start[-1] if start else 0
    danach = [e for e in welt.ereignisse if e["art"] == "webhook" and e["seq"] > ab
              and _befehl_aus(e["text"]) in ("HELP", "CODES", "STATUS")]
    assert not danach, (f"Verknuepfung gescheitert ({kaputt}), trotzdem {len(danach)} "
                        "Telegram-Kommandos gepostet")


def test_oeffentliche_staging_url_verknuepft_ueber_start_token(capsys):
    """telegram-connect ist ueber den Proxy 403 (F3) -- es bleibt nur /start TOKEN."""
    welt, rc, out, err = _erfolgslauf(capsys, basis="https://staging.gregor20.henemm.com")
    assert rc == 0, f"oeffentliche Staging-URL: Exit {rc}; stderr: {err[-800:]}"
    assert len(welt.kommando_posts()) == 15


# ---------------------------------------------------------------------------
# AC-9 Env-Ausgabe
# ---------------------------------------------------------------------------

def test_stdout_enthaelt_genau_die_drei_env_zeilen(capsys):
    welt, rc, out, err = _erfolgslauf(capsys)
    assert rc == 0, f"Exit {rc}; stderr: {err[-800:]}"
    zeilen = out.splitlines()
    assert len(zeilen) == 3, f"stdout hat {len(zeilen)} Zeilen (Fortschritt gehoert nach stderr): {zeilen[:5]}"
    namen = [z.split("=", 1)[0] for z in zeilen]
    assert namen == ["GZ_STAGING_MESSLAUF_SEIT", "GZ_STAGING_TRIP_DE", "GZ_STAGING_TRIP_KORSIKA"]
    werte = _env_zeilen(out)
    roh = werte["GZ_STAGING_MESSLAUF_SEIT"]
    seit = datetime.fromisoformat(roh.replace("Z", "+00:00"))
    assert seit.tzinfo is not None and seit.utcoffset() == timedelta(0), f"Startzeit nicht UTC: {roh}"
    assert roh.endswith("Z") or roh.endswith("+00:00"), f"Startzeit-Form {roh}"
    erste = min([m["t"] for m in welt.mails()] + [p["t"] for p in welt.kommando_posts()])
    assert seit <= erste, f"Startzeit {seit} liegt NACH dem ersten Befehl {erste}"
    assert werte["GZ_STAGING_TRIP_DE"] == welt.ids("de")[0]
    assert werte["GZ_STAGING_TRIP_KORSIKA"] == welt.ids("korsika")[0]
    ml = _messlogik()
    laeufe = [l for l in ml.dauerzeilen(welt.journal) if l["ts"] >= seit]
    for key, art in (("GZ_STAGING_TRIP_DE", "de"), ("GZ_STAGING_TRIP_KORSIKA", "korsika")):
        befehle = {l["befehl"] for l in laeufe if l["trip"] == werte[key]}
        assert {"HEUTE", "MORGEN"} <= befehle, f"{key}={werte[key]} trifft keine Dauerzeile trip= (F2)"
    assert all(l["ts"] >= seit for l in ml.dauerzeilen(welt.journal)), "Dauerzeilen vor der Startzeit"


# ---------------------------------------------------------------------------
# AC-10 Aufraeumen im finally
# ---------------------------------------------------------------------------

_ABBRUCHPUNKTE = {
    "nach-registrierung": ("trip_post", 1),
    "nach-trip-de": ("trip_post", 2),
    "nach-beiden-trips": ("smtp", 1),
    "mitten-in-serie": ("smtp", 6),
}


@pytest.mark.parametrize("ausnahme", [RuntimeError, KeyboardInterrupt], ids=["fehler", "unterbrechung"])
@pytest.mark.parametrize("punkt", list(_ABBRUCHPUNKTE))
def test_abbruch_an_jeder_stufe_loescht_trips_und_nutzer(capsys, punkt, ausnahme):
    mod = _werkzeug()
    art, n = _ABBRUCHPUNKTE[punkt]
    welt = _Welt(abbruch=_Abbruch(art, n, ausnahme(f"Stoerung {punkt}")))
    try:
        rc = welt.lauf(mod)
    except KeyboardInterrupt:
        rc = None
    out, err = _ausgabe(capsys)
    assert welt.abbruch.zaehler >= n, f"Stoerpunkt {punkt} nie erreicht"
    assert welt.registrierter_nutzer() is not None
    assert not welt.eigene_reste(), f"{punkt}: Trips stehen geblieben: {welt.eigene_reste()}"
    assert welt.registrierter_nutzer() in welt.geloeschte_nutzer, f"{punkt}: Nutzer nicht geloescht"
    assert rc != 0, f"{punkt}: Abbruch mit Exit 0"
    assert "GZ_STAGING_MESSLAUF_SEIT" not in out


@pytest.mark.parametrize("was", ["trip", "nutzer"])
def test_scheiterndes_loeschen_nennt_kennung_und_exit_ungleich_null(capsys, was):
    welt, rc, out, err = _erfolgslauf(capsys, loeschen_scheitert={was})
    assert rc != 0, f"Loeschen von {was} gescheitert, trotzdem Exit 0"
    assert welt.registrierter_nutzer() in out + err, "Befund ohne Nutzer-Kennung"
    if was == "trip":
        loesch_versuche = [a for a in welt.anfragen if a["url"].endswith("/api/auth/account/delete")]
        assert loesch_versuche, "nach gescheitertem Trip-Loeschen kein Versuch, den Nutzer zu loeschen"


# ---------------------------------------------------------------------------
# AC-11 / AC-12 / AC-13 Startpruefung und Exit-Codes
# ---------------------------------------------------------------------------

def _keine_anfrage(welt: _Welt) -> None:
    assert welt.zaehler == {"transport": 0, "helfer": 0, "smtp": 0, "imap": 0, "journal": 0}, (
        f"Anfragen trotz Sperre: {welt.zaehler}")


@pytest.mark.parametrize("uhrzeit", [(23, 50), (0, 10), (22, 30)], ids=["23:50", "00:10", "22:30"])
def test_zeitfenster_sperrt_vor_jeder_anfrage(capsys, uhrzeit):
    """23:50/00:10 liegen im Sperrfenster. 22:30 ist ABWEICHEND vom Testplan-Beispiel der Spec
    gesperrt: bei geschaetzten 2-2,5 h Laufzeit endet der Lauf nach Mitternacht -- der AC-11-Text
    ("geschaetzte Laufzeit ueberspannt einen Tageswechsel") hat Vorrang vor dem Beispiel."""
    mod = _werkzeug()
    welt = _Welt(start=datetime(2027, 7, 14, *uhrzeit, tzinfo=WIEN))
    rc = welt.lauf(mod)
    out, err = _ausgabe(capsys)
    assert rc == 2, f"Start {uhrzeit}: Exit {rc}, erwartet 2"
    assert err.strip(), "Sperre ohne klare Meldung"
    _keine_anfrage(welt)


def test_zeitfenster_erlaubt_nachmittag_und_kurze_laufzeit_am_abend(capsys):
    mod = _werkzeug()
    welt = _Welt(start=datetime(2027, 7, 14, 14, 0, tzinfo=WIEN))
    assert welt.lauf(mod) == 0
    _ausgabe(capsys)
    welt2 = _Welt(start=datetime(2027, 7, 14, 22, 30, tzinfo=WIEN))
    welt2.lauf(mod, laufzeit=timedelta(minutes=30))
    _ausgabe(capsys)
    assert welt2.zaehler["transport"] + welt2.zaehler["helfer"] > 0, (
        "22:30 mit injizierter Laufzeit 30 min muss starten (Laufzeit-Schaetzung injizierbar)")


@pytest.mark.parametrize("fehlt", ["GZ_TEST_IMAP_USER", "GZ_TEST_IMAP_PASS", "GZ_CORE_SHARED_SECRET",
                                   "GZ_AUTH_USER", "GZ_AUTH_PASS", "TELEGRAM_WEBHOOK_SECRET"])
def test_fehlende_umgebung_ist_exit_2_ohne_anfrage(capsys, fehlt):
    mod = _werkzeug()
    welt = _Welt()
    rc = welt.lauf(mod, env=welt.env(**{fehlt: None}))
    out, err = _ausgabe(capsys)
    assert rc == 2, f"ohne {fehlt}: Exit {rc}"
    _keine_anfrage(welt)


def test_staging_nicht_erreichbar_ist_exit_2(capsys):
    mod = _werkzeug()
    welt = _Welt()

    def tot(method, url, headers, body):
        raise ConnectionRefusedError("Verbindung abgelehnt")
    rc = welt.lauf(mod, transport=tot, helfer_transport=tot)
    _ausgabe(capsys)
    assert rc == 2, f"Staging nicht erreichbar: Exit {rc}"
    assert welt.zaehler["smtp"] == 0


def test_exit_codes_erfolg_befund_umgebung(capsys):
    assert _erfolgslauf(capsys)[1] == 0
    assert _erfolgslauf(capsys, warm={("de", 0)})[1] == 1
    mod = _werkzeug()
    welt = _Welt()
    assert welt.lauf(mod, env=welt.env(GZ_CORE_SHARED_SECRET=None)) == 2
    _ausgabe(capsys)


@pytest.mark.parametrize("basis,kern", [
    ("http://127.0.0.1:8090", KERN),
    ("http://localhost:8090/", KERN),
    ("https://gregor20.henemm.com", KERN),
    ("https://gregor20.henemm.com/", KERN),
    ("https://GREGOR20.henemm.com", KERN),
    ("http://gregor20.henemm.com:8091", KERN),
    (BASIS, "http://127.0.0.1:8000"),
    (BASIS, "http://127.0.0.1:8090"),
])
def test_produktions_adressen_werden_vor_jeder_anfrage_abgelehnt(capsys, basis, kern):
    mod = _werkzeug()
    welt = _Welt(basis=basis.rstrip("/"), kern=kern)
    rc = welt.lauf(mod, env=welt.env(GZ_STAGING_BASE_URL=basis, GZ_STAGING_CORE_URL=kern))
    _ausgabe(capsys)
    assert rc == 2, f"{basis} / {kern}: Exit {rc}, erwartet 2"
    _keine_anfrage(welt)


@pytest.mark.parametrize("basis", ["http://127.0.0.1:8091", "https://staging.gregor20.henemm.com"])
def test_staging_adressen_sind_erlaubt(capsys, basis):
    welt, rc, out, err = _erfolgslauf(capsys, basis=basis)
    assert rc == 0, f"{basis}: Exit {rc}; stderr: {err[-800:]}"


@pytest.mark.parametrize("basis", ["http://staging.gregor20.henemm.com",
                                   "http://staging.gregor20.henemm.com/"])
def test_staging_host_ohne_https_wird_vor_jeder_anfrage_abgelehnt(capsys, basis):
    """Adversary F002 / AC-18: das Sitzungs-Cookie ist Secure -- ueber http kaeme es nie zurueck.
    Der oeffentliche Staging-Host ist NUR per https erlaubt (lokal nur http://127.0.0.1:8091)."""
    mod = _werkzeug()
    welt = _Welt(basis=basis.rstrip("/"))
    rc = welt.lauf(mod, env=welt.env(GZ_STAGING_BASE_URL=basis))
    out, err = _ausgabe(capsys)
    assert rc == 2, f"{basis}: Exit {rc}, erwartet 2 (http auf dem Staging-Host)"
    assert err.strip() and not out, "Sperre ohne Meldung oder mit stdout-Ausgabe"
    _keine_anfrage(welt)


# ---------------------------------------------------------------------------
# AC-14 / AC-15 Kontingent, nur eigene Trips
# ---------------------------------------------------------------------------

def test_genau_zwei_trip_anlagen(capsys):
    welt, rc, out, err = _erfolgslauf(capsys)
    assert rc == 0
    anlagen = [a for a in welt.anfragen if a["method"] == "POST" and a["url"].endswith("/api/trips")]
    assert len(anlagen) == 2, f"{len(anlagen)} Trip-Anlagen, erwartet genau 2"
    assert sorted(welt._trip_art(t) for t in welt.angelegt) == ["de", "korsika"]


_ERLAUBT = [
    ("GET", r"/api/health"),
    ("POST", r"/api/auth/(login|register|verify-email|verify-email/staging-token|account/delete)"),
    ("GET", r"/api/auth/telegram-(link|status)"),
    ("POST", r"/api/internal/telegram-connect"),
    ("GET", r"/api/trips"), ("POST", r"/api/trips"),
    ("GET", r"/api/trips/(?P<id>[^/]+)"), ("PUT", r"/api/trips/(?P<id>[^/]+)"),
    ("DELETE", r"/api/trips/(?P<id>[^/]+)"),
    ("POST", r"/api/webhooks/telegram/inbound"),
]


def test_nur_erlaubte_endpunkte_und_nur_eigene_trips(capsys):
    welt, rc, out, err = _erfolgslauf(capsys)
    assert rc == 0
    eigene = {t["id"] for t in welt.angelegt}
    for a in welt.anfragen:
        url = a["url"]
        assert not any(f in url for f in FREMD_TRIPS), f"Zugriff auf fremden Trip: {url}"
        if url.startswith(KERN + "/"):
            assert (a["method"], url[len(KERN):]) == ("POST", "/api/scheduler/inbound-commands"), (
                f"nicht erlaubter Kern-Aufruf (Sammellauf/Briefing?): {a['method']} {url}")
            continue
        assert url.startswith(BASIS + "/"), f"fremder Host: {url}"
        pfad = url[len(BASIS):].split("?", 1)[0]
        treffer = [re.fullmatch(p, pfad) for m, p in _ERLAUBT if m == a["method"]]
        treffer = [t for t in treffer if t]
        assert treffer, f"nicht erlaubter Endpunkt: {a['method']} {pfad}"
        tid = treffer[0].groupdict().get("id")
        if tid is not None:
            assert tid in eigene, f"Trip-Zugriff auf fremde ID {tid}"
    assert {t: welt.trips[t] for t in FREMD_TRIPS} == welt.fremd_vorher, "fremde Trips veraendert"
    fremd_namen = {welt.trips[t]["name"] for t in FREMD_TRIPS}
    assert not any(n in m["betreff"] for m in welt.mails() for n in fremd_namen)
    assert all(m["trip_id"] in eigene for m in welt.mails()), "Befehl ohne eigenen Trip-Bezug"


# ---------------------------------------------------------------------------
# AC-16 Treiber wertet nicht aus
# ---------------------------------------------------------------------------

def test_ausgabe_enthaelt_keine_schwellen_kein_urteil_und_keine_geheimnisse(capsys):
    t0 = time.monotonic()
    welt, rc, out, err = _erfolgslauf(capsys)
    dauer = time.monotonic() - t0
    assert rc == 0
    gesamt = out + err
    assert not re.search(r"(?<![\d.,])(30|45|60)\s?s\b", gesamt), "Schwellenwert (30/45/60 s) in der Ausgabe"
    assert not re.search(r"\b(PASS|FAIL|PASSED|FAILED)\b", gesamt), "Pass/Fail-Urteil in der Ausgabe"
    assert not re.search(r"(?i)(zu langsam|schnell genug|schwelle|grenzwert)", gesamt)
    for geheim in (WEBHOOK_SECRET, KERN_SECRET, HELFER[1], "imap-pw-123"):
        assert geheim not in gesamt, "Geheimnis im Klartext ausgegeben"
    # Ersatz-Uhr: es wird nie real gewartet (Grenze grosszuegig gegen langsame CI-Rechner)
    assert dauer < 5.0, f"voller Ersatz-Lauf dauerte {dauer:.1f} s real -- echtes Warten im Ablauf?"


# ---------------------------------------------------------------------------
# baue_trip: Ortsparameter + Rueckwaertskompatibilitaet
# ---------------------------------------------------------------------------

HEUTE = date(2027, 7, 14)


def test_baue_trip_ohne_ort_bleibt_bei_47_10_und_11_00():
    trip = _pruefweg().baue_trip("A", "t1", HEUTE)
    for i, s in enumerate(trip["stages"]):
        for j, w in enumerate(s["waypoints"]):
            assert w["lat"] == pytest.approx(47.10 + 0.01 * i + 0.01 * j)
            assert w["lon"] == pytest.approx(11.00 + 0.01 * i + 0.01 * j)
    assert trip["id"] == "gzp-t1-a" and trip["name"] == "GZ-Pruefung t1 A"


def test_baue_trip_nimmt_einen_ort_an():
    pw = _pruefweg()
    trip = pw.baue_trip("A", "t1", HEUTE, ort=(42.2, 9.05))
    erste = trip["stages"][0]["waypoints"][0]
    assert (erste["lat"], erste["lon"]) == (pytest.approx(42.2), pytest.approx(9.05))
    for i, s in enumerate(trip["stages"]):
        for j, w in enumerate(s["waypoints"]):
            assert w["lat"] == pytest.approx(42.2 + 0.01 * i + 0.01 * j)
            assert w["lon"] == pytest.approx(9.05 + 0.01 * i + 0.01 * j)
    ohne = pw.baue_trip("A", "t1", HEUTE)
    assert [s["date"] for s in trip["stages"]] == [s["date"] for s in ohne["stages"]]
    assert pw.baue_trip("A", "t1", HEUTE, ort=None) == ohne


# ---------------------------------------------------------------------------
# Fix-Loop 1 (Adversary F001-F006): Sicherungen dort pruefen, wo sie wirken
# ---------------------------------------------------------------------------

def _befund_ohne_env(welt: _Welt, rc, out: str) -> None:
    assert rc == 1, f"Exit {rc}, erwartet 1 (Befund)"
    assert "GZ_STAGING_MESSLAUF_SEIT" not in out and "GZ_STAGING_TRIP_DE" not in out, (
        "unvollstaendiger Lauf meldet Env-Zeilen wie ein voller Lauf")
    assert not welt.eigene_reste(), f"Trips nicht aufgeraeumt: {welt.eigene_reste()}"
    assert welt.registrierter_nutzer() in welt.geloeschte_nutzer, "Wegwerf-Nutzer nicht geloescht"


def _befund_zeilen(err: str) -> list[str]:
    return [z for z in err.splitlines() if z.startswith("BEFUND:")]


def test_chat_id_jedes_updates_ist_nicht_numerisch_und_traegt_den_vertragspraefix(capsys):
    """F001: geprueft gegen das Vertrags-Literal, nicht gegen die Konstante des Prueflings."""
    welt, rc, out, err = _erfolgslauf(capsys)
    assert rc == 0, f"Exit {rc}; stderr: {err[-800:]}"
    alle = [e for e in welt.ereignisse if e["art"] == "webhook"]
    assert len(alle) == 16, f"{len(alle)} Webhook-Updates, erwartet /start + 15 Befehle"
    for e in alle:
        cid = e["chat_id"]
        assert isinstance(cid, str) and cid.startswith("gzp-ungueltig-"), f"chat_id {cid!r}"
        with pytest.raises(ValueError):
            int(cid)
        assert re.search(r"[a-z]", cid) and not cid.startswith("@"), f"chat_id {cid!r} koennte echt sein"


def test_zweiter_lauf_gegen_denselben_dedup_speicher_trifft_kein_duplikat(capsys):
    """F002: der Kern haelt gesehene update_ids im Prozessspeicher (api/routers/webhook.py:40-48)
    -- ueber Laeufe hinweg. Ein fester Startwert liefe im zweiten Lauf komplett ins Dedup."""
    mod = _werkzeug()
    w1 = _Welt()
    assert w1.lauf(mod) == 0
    w2 = _Welt()
    w2.gesehene_updates = w1.gesehene_updates
    rc2 = w2.lauf(mod)
    out, err = _ausgabe(capsys)
    assert rc2 == 0, f"zweiter Lauf: Exit {rc2}; stderr: {err[-800:]}"
    assert not any(e["duplikat"] for e in w2.ereignisse if e["art"] == "webhook"), "Dedup-Treffer"
    telegram = [l for l in _messlogik().dauerzeilen(w2.journal) if l["kanal"] == "telegram"]
    assert len(telegram) == 15, f"zweiter Lauf: nur {len(telegram)} Telegram-Befehle verarbeitet"


@pytest.mark.parametrize("lauf", [("de", 0), ("de", 1), ("korsika", 0)],
                         ids=["de-heute", "de-morgen", "korsika-heute"])
def test_probelauf_ohne_dauerzeile_ist_befund(capsys, lauf):
    """F003: Fensterzeile mit downloads>0 liegt vor, nur die Dauerzeile fehlt -> kein Kaelte-Beleg."""
    welt, rc, out, err = _erfolgslauf(capsys, ohne_dauerzeile={lauf})
    _befund_ohne_env(welt, rc, out)
    assert not [m for m in welt.mails() if m["befehl"] in ("HELP", "CODES", "STATUS")], (
        "Probelauf ohne Dauerzeile, trotzdem Kurzbefehle eingeliefert")
    assert not welt.kommando_posts(), "Serie trotz fehlender Dauerzeile"
    _nur_probelauf_ortswechsel(welt, lauf)


@pytest.mark.parametrize("befehl,n,wort", [("HEUTE", 1, "heute"), ("STATUS", 3, "status"),
                                           ("CODES", 5, "kuerzel"), ("HELP", 6, "hilfe")],
                         ids=["probelauf-heute", "status-3", "kuerzel-5", "paar-hilfe"])
def test_ausbleibende_mail_antwort_ist_befund(capsys, befehl, n, wort):
    """F004 (E-Mail): Exit 0 heisst 'vollstaendig ausgeloest' (AC-12) -- ohne Antwort ist er es nicht."""
    welt, rc, out, err = _erfolgslauf(capsys, keine_antwort={(befehl, n)})
    _befund_ohne_env(welt, rc, out)
    befund = _befund_zeilen(err)
    assert any("E-Mail" in z and wort in z and "Antwort" in z for z in befund), (
        f"Befund nennt Kanal E-Mail und Befehl {wort} nicht: {befund or err[-600:]}")


def test_ausbleibende_telegram_dauerzeile_ist_befund(capsys):
    """F004 (Telegram): das 4. Kommando (status, 2. Runde) erzeugt keine Dauerzeile."""
    welt, rc, out, err = _erfolgslauf(capsys, telegram_still={4})
    _befund_ohne_env(welt, rc, out)
    befund = _befund_zeilen(err)
    assert any("Telegram status" in z and "Dauerzeile" in z for z in befund), (
        f"Befund nennt Kanal Telegram und Befehl status nicht: {befund or err[-600:]}")


def test_telegram_wartet_auf_verspaetete_dauerzeile(capsys):
    """F004: die Dauerzeile erscheint erst 10 s nach der Verarbeitung -- warten, nicht aufgeben."""
    welt, rc, out, err = _erfolgslauf(capsys, telegram_verzoegerung_s=10.0)
    assert rc == 0, f"verspaetete Dauerzeile: Exit {rc}; stderr: {err[-800:]}"
    posts = welt.kommando_posts()
    assert len(posts) == 15
    zeilen = sorted(l["ts"] for l in _messlogik().dauerzeilen(welt.journal) if l["kanal"] == "telegram")
    for p, z in zip(posts[1:], zeilen):
        assert z <= p["t"], "naechstes Telegram-Kommando vor der Dauerzeile des vorigen gepostet"


def test_telegram_wartet_ueber_die_messschwelle_hinaus(capsys):
    """AC-16: eine Telegram-Dauerzeile, die erst ~100 s nach dem Update im Journal steht, liegt
    jenseits der 60-s-Messschwelle -- der Treiber darf den langsamen Fall nicht selbst wegfiltern,
    sondern muss warten und den Lauf vollstaendig (Exit 0, drei Env-Zeilen) abschliessen."""
    welt, rc, out, err = _erfolgslauf(capsys, telegram_verzoegerung_s=100.0)
    assert rc == 0, f"Dauerzeile nach ~100 s: Exit {rc}; stderr: {err[-800:]}"
    assert len(_env_zeilen(out)) == 3, f"stdout ohne die drei Env-Zeilen: {out!r}"
    posts = welt.kommando_posts()
    zeilen = sorted(l["ts"] for l in _messlogik().dauerzeilen(welt.journal) if l["kanal"] == "telegram")
    assert len(posts) == 15 and len(zeilen) == 15, f"{len(posts)} Updates, {len(zeilen)} Dauerzeilen"
    abstand = [(z - p["t"]).total_seconds() for p, z in zip(posts, zeilen)]
    assert all(90 <= a <= 120 for a in abstand), f"Dauerzeile nicht 90-120 s nach dem Update: {abstand}"


def test_mail_antwort_kommt_nur_ueber_den_poll_ausloeser(capsys):
    """F004: ohne Cron-Takt verarbeitet nur der Poll-Ausloeser -- faellt er weg, keine Antwort."""
    welt, rc, out, err = _erfolgslauf(capsys, ohne_cron=True)
    assert rc == 0, f"ohne Cron: Exit {rc}; stderr: {err[-800:]}"
    assert all(m["abgeholt_seq"] is not None for m in welt.mails()), "Antwort nie abgeholt"


def test_startzeit_hat_die_z_form_fuer_journalctl_since(capsys):
    """F005: der Konsument (tests/e2e/test_push_eingang_befehle_staging.py:191-205) parst den Wert
    NICHT selbst, sondern reicht ihn roh an ``journalctl --since`` -- vereinbarte Form:
    sekundengenaues UTC mit ``Z`` (wie es auch die Ersatzwelt-journal_quelle liest)."""
    welt, rc, out, err = _erfolgslauf(capsys)
    assert rc == 0
    roh = _env_zeilen(out)["GZ_STAGING_MESSLAUF_SEIT"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", roh), f"Startzeit-Form {roh!r}"
    assert datetime.strptime(roh, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc) == (
        START.astimezone(timezone.utc)), "Startzeit ist nicht der Laufbeginn in UTC"


def test_verifikationsmail_nach_dem_schnappschuss_zaehlt_nicht_als_antwort(capsys):
    """F006: Systemmail an die Plus-Adresse trifft 10 s nach der ersten Einlieferung ein."""
    welt, rc, out, err = _erfolgslauf(capsys, verifikationsmail_s=10.0)
    assert rc == 0, f"Exit {rc}; stderr: {err[-800:]}"
    assert any(m["cmd"] is None for m in welt.postfach), "Verifikationsmail nie eingestellt"
    mails = welt.mails()
    paar = _paar_help(welt)
    for vor, nach in zip(mails, mails[1:]):
        if nach is paar:
            continue
        assert vor["abgeholt_seq"] is not None and vor["abgeholt_seq"] < nach["seq"], (
            f"{nach['befehl']} eingeliefert, bevor die echte Antwort auf {vor['befehl']} abgeholt war "
            "(Verifikationsmail als Antwort gezaehlt?)")


# ---------------------------------------------------------------------------
# Fix-Loop 2 (Adversary F-A2-02, F-A2-04)
# ---------------------------------------------------------------------------

def _telegram_zeilen_der_welt(welt: _Welt) -> list:
    return sorted(l["ts"] for l in _messlogik().dauerzeilen(welt.journal) if l["kanal"] == "telegram")


def test_telegram_warten_zaehlt_keine_verspaetete_mail_dauerzeile(capsys):
    """F-A2-02 (AC-5/AC-8): waehrend des Wartens auf die (verzoegerte) Telegram-Dauerzeile des
    4. Kommandos erscheint eine spaete kanal=email-Zeile -- sie beendet das Warten nicht."""
    welt, rc, out, err = _erfolgslauf(capsys, telegram_verzoegerung_s=10.0, email_zeile_bei_telegram=4)
    assert rc == 0, f"Exit {rc}; stderr: {err[-800:]}"
    spaet = [l for l in _messlogik().dauerzeilen(welt.journal)
             if l["kanal"] == "email" and l["befehl"] == "STATUS"]
    assert len(spaet) == 6, f"eingeworfene Mail-Dauerzeile nicht geparst ({len(spaet)} STATUS-Zeilen)"
    posts = welt.kommando_posts()
    zeilen = _telegram_zeilen_der_welt(welt)
    assert len(posts) == 15 and len(zeilen) == 15
    for i, (p, z) in enumerate(zip(posts[1:], zeilen), start=2):
        assert z <= p["t"], (f"Telegram-Kommando {i} gepostet, bevor die Telegram-Dauerzeile des "
                             "vorigen da war (Mail-Dauerzeile mitgezaehlt?)")


def test_ausbleibende_telegram_dauerzeile_wird_nicht_durch_mail_zeile_ersetzt(capsys):
    """F-A2-02: Telegram-Kommando 4 bleibt ohne Dauerzeile, dafuer kommt eine spaete Mail-Zeile."""
    welt, rc, out, err = _erfolgslauf(capsys, telegram_still={4}, email_zeile_bei_telegram=4)
    _befund_ohne_env(welt, rc, out)
    befund = _befund_zeilen(err)
    assert any("Telegram status" in z and "Dauerzeile" in z for z in befund), (
        f"Befund nennt Kanal Telegram und Befehl status nicht: {befund or err[-600:]}")
    assert len(welt.kommando_posts()) == 4, "nach der ausgebliebenen Dauerzeile weiter gepostet"


def test_mail_antwort_nach_300_sekunden_wird_noch_angenommen(capsys):
    """F-A2-04: die Antwort-Wartezeit ist 360 s -- eine Antwort nach ~300 s zaehlt noch."""
    welt, rc, out, err = _erfolgslauf(capsys, antwort_verzoegerung={("STATUS", 1): 300.0})
    assert rc == 0, f"Antwort nach 300 s: Exit {rc}; stderr: {err[-800:]}"
    status = next(m for m in welt.mails() if m["befehl"] == "STATUS")
    assert status["abgeholt_seq"] is not None, "verspaetete Antwort nie abgeholt"
    assert (status["bereit"] - status["t"]).total_seconds() >= 300


def test_mail_antwort_nach_mehr_als_360_sekunden_ist_befund(capsys):
    """F-A2-04: kommt die Antwort erst nach > 360 s, ist der Lauf unvollstaendig."""
    welt, rc, out, err = _erfolgslauf(capsys, antwort_verzoegerung={("STATUS", 1): 400.0})
    _befund_ohne_env(welt, rc, out)
    befund = _befund_zeilen(err)
    assert any("E-Mail status" in z and "Antwort" in z for z in befund), (
        f"Befund nennt E-Mail status nicht: {befund or err[-600:]}")


# ---------------------------------------------------------------------------
# Fix-Loop 3 (Adversary F001 Paar-Frist, F002 Wartegrenze der Telegram-Verknuepfung)
# ---------------------------------------------------------------------------

def test_paar_antworten_nach_100_sekunden_werden_noch_angenommen(capsys):
    """F001 (AC-7): beide Antworten des HEUTE-dann-HELP-Paars liegen erst ~100 s nach der
    Verarbeitung im Postfach -- jenseits der 90-s-Paar-Messgrenze. Der Treiber wertet nicht aus,
    er wartet bis zur Antwort-Wartegrenze und schliesst vollstaendig ab (Exit 0, drei Env-Zeilen).
    Paar-HEUTE ist das 11. HEUTE (1 Probe-DE, 1 Probe-Korsika, 5 DE-Serie, 3 Korsika-Serie),
    Paar-HELP das 6. HELP (5 Kurzbefehl-Serie)."""
    welt, rc, out, err = _erfolgslauf(capsys, antwort_verzoegerung={("HEUTE", 11): 100.0,
                                                                     ("HELP", 6): 100.0})
    assert rc == 0, f"Paar-Antworten nach ~100 s: Exit {rc}; stderr: {err[-800:]}"
    assert len(_env_zeilen(out)) == 3, f"stdout ohne die drei Env-Zeilen: {out!r}"
    heute, hilfe = welt.wetter("de")[-1], _paar_help(welt)
    for m in (heute, hilfe):
        assert m["bereit"] is not None, f"{m['befehl']} des Paars nie verarbeitet"
        assert (m["bereit"] - m["t"]).total_seconds() >= 100, (
            f"Verzoegerung greift nicht am Paar ({m['befehl']}): Ersatzwelt-Nummerierung veraltet?")
        assert m["abgeholt_seq"] is not None, f"Antwort auf {m['befehl']} des Paars nie abgeholt"


def test_telegram_verknuepfung_nach_100_sekunden_wird_noch_abgewartet(capsys):
    """F002: telegram-status meldet die Verbindung erst ~100 s nach ``/start TOKEN`` -- der
    Treiber wartet bis zu seiner Wartegrenze (wie Mail, 360 s) und schliesst vollstaendig ab."""
    welt, rc, out, err = _erfolgslauf(capsys, verknuepfung_verzoegerung_s=100.0)
    assert rc == 0, f"Verknuepfung nach ~100 s: Exit {rc}; stderr: {err[-800:]}"
    assert len(_env_zeilen(out)) == 3, f"stdout ohne die drei Env-Zeilen: {out!r}"
    assert welt.verknuepft_ab is not None and (welt.verknuepft_ab - START).total_seconds() >= 100
    assert len(welt.kommando_posts()) == 15, "Telegram-Serie nicht vollstaendig ausgeloest"


# ---------------------------------------------------------------------------
# AC-17 Probelauf misst kalt: Ortswechsel zwischen HEUTE und MORGEN (v1.1)
# ---------------------------------------------------------------------------

def _ort_von(lauf: dict, welt: _Welt) -> tuple:
    w = _ort(lauf, welt)["waypoints"][0]
    return (w["lat"], w["lon"])


def test_probelauf_wechselt_den_ort_zwischen_heute_und_morgen_per_read_modify_write(capsys):
    welt, rc, out, err = _erfolgslauf(capsys)
    assert rc == 0, f"Exit {rc}; stderr: {err[-800:]}"
    heute, morgen = welt.wetter("de")[:2]
    assert (heute["befehl"], morgen["befehl"]) == ("HEUTE", "MORGEN")
    de_id = welt.ids("de")[0]
    zwischen = [p for p in welt.put_historie
                if p["trip"] == de_id and heute["seq"] < p["seq"] < morgen["seq"]]
    assert zwischen, "kein Ortswechsel (PUT) zwischen Probelauf-HEUTE und Probelauf-MORGEN"
    gets = [a for a in welt.anfragen if a["method"] == "GET" and a["url"].endswith(f"/api/trips/{de_id}")
            and heute["seq"] < a["seq"] < zwischen[0]["seq"]]
    assert gets, "Probelauf-Ortswechsel ohne vorheriges GET (kein Read-Modify-Write)"
    o_heute, o_morgen = _ort_von(heute, welt), _ort_von(morgen, welt)
    assert _km(o_heute, o_morgen) >= 120, (
        f"Probelauf-Orte {o_heute} und {o_morgen}: {_km(o_heute, o_morgen):.0f} km -- MORGEN "
        "liest sonst den von HEUTE gewaermten Cache")
    assert _routing().thunder_provider_for(*o_morgen) == "de_direct", "MORGEN-Ort ausserhalb des DWD-Gebiets"


def test_probelauf_morgen_ort_wird_von_der_serie_nicht_wiederverwendet(capsys):
    welt, rc, out, err = _erfolgslauf(capsys)
    assert rc == 0, f"Exit {rc}; stderr: {err[-800:]}"
    laeufe = welt.wetter("de")
    o_morgen = _ort_von(laeufe[1], welt)
    for l in laeufe[2:12]:
        assert _km(o_morgen, _ort_von(l, welt)) >= 120, (
            f"Serienlauf nutzt den Probelauf-MORGEN-Ort {o_morgen} erneut -- waere warm")


# ---------------------------------------------------------------------------
# AC-18 Standard-Basis ist die oeffentliche https-Staging-URL
# ---------------------------------------------------------------------------

def test_ohne_basis_env_laeuft_der_treiber_gegen_die_https_staging_url(capsys):
    mod = _werkzeug()
    welt = _Welt(basis="https://staging.gregor20.henemm.com")
    rc = welt.lauf(mod, env=welt.env(GZ_STAGING_BASE_URL=None))
    out, err = _ausgabe(capsys)
    assert rc == 0, f"Exit {rc}; stderr: {err[-800:]}"
    urls = [a["url"] for a in welt.anfragen if not a["url"].startswith(welt.kern)]
    assert urls, "keine Go-API-Anfrage"
    assert all(u.startswith("https://staging.gregor20.henemm.com/") for u in urls), (
        f"Standardbasis nicht https-Staging: {sorted({u.split('/api')[0] for u in urls})}")


# ---------------------------------------------------------------------------
# AC-19 Korsika auf Staging: Ersatzquelle eu_direct, offen ausgewiesen
# ---------------------------------------------------------------------------

STAGING_URL = "https://staging.gregor20.henemm.com"


def test_korsika_auf_staging_verlangt_keinen_fr_direct_kaltlauf_und_loest_die_serie_aus(capsys):
    welt, rc, out, err = _erfolgslauf(capsys, basis=STAGING_URL)
    assert rc == 0, f"Exit {rc}; stderr: {err[-800:]}"
    assert not any("fr_direct_fenster" in t for _, t in welt.journal), "Ersatzwelt-Fehler: fr_direct auf Staging"
    assert len(welt.wetter("korsika")) == 7, f"Korsika-Serie nicht ausgeloest: {len(welt.wetter('korsika'))}"
    assert "eu_direct" in err and "rsatz" in err, (
        "Ersatzquelle eu_direct nicht offen als Ersatz ausgewiesen (stderr)")
    assert "GZ_STAGING_MESSLAUF_SEIT" in out


def test_korsika_ohne_antwort_auf_staging_ist_trotzdem_befund(capsys):
    welt, rc, out, err = _erfolgslauf(capsys, basis=STAGING_URL, ohne_dauerzeile={("korsika", 0)})
    assert rc == 1, f"Exit {rc}, erwartet 1 (Korsika ohne Antwort)"
    assert not [m for m in welt.mails() if m["befehl"] in ("HELP", "CODES", "STATUS")], "Serie trotz Befund"
    assert welt.angelegt and not welt.eigene_reste(), f"nicht aufgeraeumt: {welt.eigene_reste()}"


def test_warmer_de_probelauf_ist_auf_staging_weiter_befund(capsys):
    welt, rc, out, err = _erfolgslauf(capsys, basis=STAGING_URL, warm={("de", 1)})
    assert rc == 1, f"Exit {rc}, erwartet 1 (DE MORGEN warm)"
    assert not welt.kommando_posts()


def test_korsika_auf_lokaler_basis_verlangt_weiter_fr_direct(capsys):
    welt, rc, out, err = _erfolgslauf(capsys, warm={("korsika", 0)})
    assert rc == 1, f"Exit {rc}: lokal ist fr_direct nicht gesperrt, warmes Korsika bleibt Befund"


# ---------------------------------------------------------------------------
# AC-20 Modus "nur Probelauf" (Kern-Vertrag; der echte Lauf steht in tests/e2e)
# ---------------------------------------------------------------------------

def test_nur_probelauf_loest_nur_die_drei_probelaeufe_aus_und_raeumt_auf(capsys):
    mod = _werkzeug()
    welt = _Welt(basis=STAGING_URL)
    rc = mod.main(
        ["--nur-probelauf"], env=welt.env(), transport=welt.transport_fuer("nutzer"),
        helfer_transport=welt.transport_fuer("helfer"), smtp_factory=welt.smtp_factory(),
        imap_factory=welt.imap_factory(), journal_quelle=welt.journal_quelle,
        uhr=welt.uhr.jetzt, schlaf=welt.uhr.schlaf)
    out, err = _ausgabe(capsys)
    assert rc == 0, f"Exit {rc}; stderr: {err[-800:]}"
    assert len(welt.wetter("de")) == 2 and len(welt.wetter("korsika")) == 1, (
        f"Probelauf-Umfang: DE {len(welt.wetter('de'))}, Korsika {len(welt.wetter('korsika'))}")
    assert not [m for m in welt.mails() if m["befehl"] in ("HELP", "CODES", "STATUS")], "Kurzbefehle im Probemodus"
    assert not welt.kommando_posts(), "Telegram-Serie im Probemodus"
    assert welt.angelegt and not welt.eigene_reste(), f"Trips nicht aufgeraeumt: {welt.eigene_reste()}"
    assert welt.registrierter_nutzer() in welt.geloeschte_nutzer, "Wegwerf-Nutzer nicht geloescht"


def _nur_probelauf(welt: _Welt, **kw):
    """--nur-probelauf mit allen Raendern injiziert; ``laufzeit`` NICHT injiziert (Default greift)."""
    mod = _werkzeug()
    argumente = dict(env=welt.env(), transport=welt.transport_fuer("nutzer"),
                     helfer_transport=welt.transport_fuer("helfer"), smtp_factory=welt.smtp_factory(),
                     imap_factory=welt.imap_factory(), journal_quelle=welt.journal_quelle,
                     uhr=welt.uhr.jetzt, schlaf=welt.uhr.schlaf)
    argumente.update(kw)
    return mod.main(["--nur-probelauf"], **argumente)


@pytest.mark.parametrize("basis", [STAGING_URL, BASIS], ids=["staging", "lokal"])
def test_nur_probelauf_verknuepft_kein_telegram_und_liefert_nur_drei_mails_ein(capsys, basis):
    """Adversary F003 (k): im Probemodus weder Telegram-Link noch /start noch Webhook; genau die
    drei Probe-Mails, nur der EINE Probelauf-Ortswechsel."""
    welt = _Welt(basis=basis)
    rc = _nur_probelauf(welt)
    out, err = _ausgabe(capsys)
    assert rc == 0, f"Exit {rc}; stderr: {err[-800:]}"
    telegram = [a["url"] for a in welt.anfragen if "telegram" in a["url"]]
    assert not telegram, f"Telegram-Anfragen im Probemodus: {telegram}"
    assert not [e for e in welt.ereignisse if e["art"] == "webhook"], "Webhook-Update im Probemodus"
    befehle = [(m["trip_art"], m["befehl"]) for m in welt.mails()]
    assert befehle == [("korsika", "HEUTE"), ("de", "HEUTE"), ("de", "MORGEN")], (
        f"Probemodus lieferte nicht genau die drei Probe-Mails ein: {befehle}")
    assert len(welt.put_historie) == 1, f"{len(welt.put_historie)} PUT, erwartet nur den Probe-Wechsel"


def test_nur_probelauf_schreibt_nichts_nach_stdout(capsys):
    """Adversary F003 (h): stdout bleibt im Probemodus VOLLSTAENDIG leer -- auch keine Leerzeile;
    ``eval "$(...)"`` darf nach einem Probelauf keine Env-Zeilen setzen."""
    welt = _Welt(basis=STAGING_URL)
    rc = _nur_probelauf(welt)
    out, err = _ausgabe(capsys)
    assert rc == 0, f"Exit {rc}; stderr: {err[-800:]}"
    assert out == "", f"stdout im Probemodus nicht leer: {out!r}"
    assert "Probelauf" in err, "Probemodus ohne Fortschrittsmeldung auf stderr"


def test_nur_probelauf_nutzt_die_kurze_laufzeit_fuer_die_zeitfenster_sperre(capsys):
    """Adversary F003 (i): 23:20 Wien -- Probelauf (30 min) endet 23:50 am selben Tag und darf
    starten; der volle Lauf (2 h 15 min) ueberspannt Mitternacht und ist gesperrt (Exit 2)."""
    start = datetime(2027, 7, 14, 23, 20, tzinfo=WIEN)
    welt = _Welt(start=start, basis=STAGING_URL)
    rc = _nur_probelauf(welt)
    out, err = _ausgabe(capsys)
    assert rc == 0, f"Probelauf 23:20: Exit {rc}, erwartet 0; stderr: {err[-800:]}"
    assert len(welt.mails()) == 3, "Probelauf 23:20 hat nicht die drei Probe-Mails eingeliefert"
    voll = _Welt(start=start, basis=STAGING_URL)
    rc_voll = voll.lauf(_werkzeug())
    out, err = _ausgabe(capsys)
    assert rc_voll == 2, f"voller Lauf 23:20: Exit {rc_voll}, erwartet 2 (Tageswechsel)"
    _keine_anfrage(voll)
