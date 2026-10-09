#!/usr/bin/env python3
"""Staging-Pruefweg fuer Befehle ueber den ECHTEN E-Mail-Eingang (#2542).

Spec: docs/specs/modules/fix_2542_staging_befehl_pruefweg.md

Schickt Befehle (status, heute, Ruhetag, Startdatum) ueber die anonyme
Port-25-Zustellung an den Staging-Eingang und wertet die Antwortmail aus.
Aendert keinen Produktcode und umgeht die Absenderpruefung nicht: der eigene
Server ist fuer henemm.com sendeberechtigt (SPF/DMARC bestehen legitim).

Aufruf:  python3 .claude/tools/staging_befehl_pruefen.py --szenario status|heute|verschiebung|alle
Exit:    0 = alles bestanden, 1 = Antwort ausgeblieben/Inhalt falsch,
         2 = Aufruf-/Umgebungsfehler (Relay-Sperre, Zugangsdaten, Registrierung ...)
"""
from __future__ import annotations

import argparse
import html as html_mod
import http.cookiejar
import imaplib
import json
import os
import re
import secrets
import smtplib
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from email import message_from_bytes
from email.header import decode_header, make_header
from email.message import EmailMessage
from email.utils import getaddresses, make_msgid
from pathlib import Path

STAGING_EINGANG = "gregor-staging@henemm.com"
BASIS_POSTFACH = "gregor-test"
MAIL_HOST = "mail.henemm.com"
STAGING_ENV = Path("/home/hem/gregor_zwanzig_staging/.env")
INTERVALL_S = 10

OBST = "02: Obstansersee-Hütte nach Porzehütte"
B_NAMEN = ["02: X", "02 – X", "2 Seen Runde", "1.5 km Runde", "1. Pass", "2. X", "03:"]
_PLAN = {
    "A": [(-3, "Aufstieg Nord"), (-2, "Grat Ost"), (-1, "Kar Mitte"), (0, OBST), (1, "Abstieg Tal")],
    "B": list(enumerate(B_NAMEN)),
    "C": [(2, "4: Alpha"), (0, "2: Beta"), (3, "1: Gamma"), (1, "3: Delta")],
    "D": [(5 + i, n) for i, n in enumerate(B_NAMEN)],
    "D2": [(7 + i, n) for i, n in enumerate(B_NAMEN)],
}
_GRUPPEN = {"status": ["B"], "heute": ["A"], "verschiebung": ["D", "D2"],
            "alle": ["A", "B", "C", "D", "D2"]}
# Kopie von app.trip._STAGE_PREFIX_RE (Werkzeug laeuft ohne src-Import)
_PRAEFIX = re.compile(
    r"^\s*(?:(?:Etappe|Tag|Stage)\s*\d+\b\s*[:.\-–—]?|\d{1,2}\s*[:\-–—](?:\s+|$))\s*(?P<rest>.*)$",
    re.IGNORECASE,
)
_ADRESSE = re.compile(r"[A-Za-z0-9._%+\-]+@henemm\.com")


class StagingFehler(RuntimeError):
    """HTTP-Fehler der Staging-Schnittstelle (ohne Antwortkoerper, ohne Geheimnisse)."""


@dataclass
class Ergebnis:
    ok: bool
    meldung: str


# ---------------------------------------------------------------------------
# Reine Funktionen
# ---------------------------------------------------------------------------

def baue_tag() -> str:
    return time.strftime("%d%H%M") + "-" + secrets.token_hex(4)


def baue_plus_adresse(tag: str) -> str:
    return f"{BASIS_POSTFACH}+{tag}@henemm.com"


def pruefe_empfaenger(adresse: str) -> str:
    """Relay-Sperre: nur genau eine Adresse auf @henemm.com, sonst Exit 2."""
    if not isinstance(adresse, str) or not _ADRESSE.fullmatch(adresse):
        print("Relay-Sperre: Empfaenger nicht auf @henemm.com - Abbruch.", file=sys.stderr)
        raise SystemExit(2)
    return adresse


def baue_befehlsmail(plus_adresse: str, trip_name: str, befehl: str, wort: str | None = None) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = plus_adresse
    msg["To"] = STAGING_EINGANG
    msg["Subject"] = f"[{trip_name}] {wort or befehl}"
    msg["Date"] = datetime.now().astimezone().strftime("%a, %d %b %Y %H:%M:%S %z")
    msg["Message-ID"] = make_msgid(domain="henemm.com")
    msg.set_content(befehl + "\n")
    return msg


def _etappe(i: int, name: str, datum: date) -> dict:
    wp = [{"id": f"G{j + 1}", "name": ort, "lat": 47.10 + 0.01 * i + 0.01 * j,
           "lon": 11.00 + 0.01 * i + 0.01 * j, "elevation_m": 1500 + 100 * j}
          for j, ort in enumerate(("Start", "Ziel"))]
    return {"id": f"T{i + 1}", "name": name, "date": datum.isoformat(), "waypoints": wp}


def baue_trip(szenario: str, tag: str, heute: date) -> dict:
    stages = [_etappe(i, name, heute + timedelta(days=off))
              for i, (off, name) in enumerate(_PLAN[szenario])]
    return {"id": f"gzp-{tag}-{szenario.lower()}", "name": f"GZ-Pruefung {tag} {szenario}",
            "stages": stages}


def antworttext(raw: bytes) -> str:
    msg = message_from_bytes(raw)
    teil = None
    for art in ("plain", "html"):
        for p in msg.walk():
            if p.get_content_type() == f"text/{art}" and teil is None:
                teil = (art, p)
        if teil:
            break
    if teil is None:
        return ""
    art, p = teil
    text = (p.get_payload(decode=True) or b"").decode(p.get_content_charset() or "utf-8", "replace")
    if art == "plain":
        return text
    text = re.sub(r"(?is)<(style|script)\b.*?</\1>", " ", text)
    text = re.sub(r"(?i)<(br|/div|/p|/tr|/li|/h\d|/table)[^>]*>", "\n", text)
    text = html_mod.unescape(re.sub(r"<[^>]+>", " ", text))
    return "\n".join(re.sub(r"[ \t\xa0]+", " ", z).strip() for z in text.splitlines() if z.strip())


def exit_code(antwort, count) -> int:
    """0 genau dann, wenn eine Antwortmail da ist; count ist nur Diagnose."""
    return 0 if antwort is not None else 1


# ---------------------------------------------------------------------------
# Auswertung
# ---------------------------------------------------------------------------

def _bezeichnung(etappen: list, e: dict) -> str:
    geordnet = sorted(etappen, key=lambda s: s["date"])
    n = next(i for i, s in enumerate(geordnet) if s is e) + 1
    name = (e["name"] or "").strip()
    m = _PRAEFIX.match(name)
    rest = m.group("rest").strip() if m else name
    return f"Etappe {n}: {rest}" if rest else f"Etappe {n}"


def _d(e: dict) -> date:
    return date.fromisoformat(e["date"])


def _fmt(d: date) -> str:
    return f"{d:%d.%m.%Y}"


def _zeile(text: str, muster: str) -> bool:
    return re.search(muster, text, re.M) is not None


def _pruefe_status(text: str, etappen: list, heute: date) -> list[str]:
    fehler = []
    for e in etappen:
        if _d(e) < heute:
            continue
        label = _bezeichnung(etappen, e)
        if not _zeile(text, rf"^\s*{_fmt(_d(e))}\s+[–-]\s+{re.escape(label)}\s*$"):
            fehler.append(f"status: erwartet '{_fmt(_d(e))} - {label}'")
    return fehler


def _pruefe_heute(text: str, etappen: list, heute: date) -> list[str]:
    ziel = next((e for e in etappen if _d(e) == heute), None)
    if ziel is None:
        return ["heute: Szenario ohne heutige Etappe"]
    label = _bezeichnung(etappen, ziel)
    n = int(re.match(r"Etappe (\d+)", label).group(1))
    rest = label.split(": ", 1)[1] if ": " in label else ""
    m = re.search(r"\bEtappe\s+(\d+)\b", text) or re.search(r"\bE(\d+)\b", text)
    if m is None or int(m.group(1)) != n:
        return [f"heute: erwartet Etappe {n}, gefunden {m.group(0) if m else 'keine Nummer'}"]
    if rest[:8] and rest[:8] not in re.sub(r"\s+", " ", text):
        return [f"heute: Etappenname '{rest[:8]}...' fehlt"]
    return []


def _pruefe_verschiebung(text: str, etappen: list, heute: date, delta: int | None,
                         neu_start: date | None) -> list[str]:
    fehler = []
    if neu_start is not None:
        alt = min(_d(e) for e in etappen)
        kopf = f"Startdatum verschoben: {_fmt(alt)} -> {_fmt(neu_start)}"
        if kopf not in text:
            fehler.append(f"erwartet '{kopf}'")
        delta = (neu_start - alt).days
    for e in etappen:
        if neu_start is None and _d(e) <= heute:
            continue
        label, alt_d = _bezeichnung(etappen, e), _d(e)
        neu_d = alt_d + timedelta(days=delta)
        zusatz = rf"{_fmt(alt_d)} -> {_fmt(neu_d)}" if neu_start is None else _fmt(neu_d)
        if not _zeile(text, rf"^\s*{re.escape(label)}: {zusatz}\s*$"):
            fehler.append(f"erwartet '{label}: {zusatz.replace(chr(92), '')}'")
    return fehler


_ERWARTET = {"A": ("status", "heute"), "B": ("status",), "C": ("status",),
             "D": ("ruhetag",), "D2": ("startdatum",)}


def werte_aus(szenario, etappen, antworten, heute, *, neues_startdatum=None) -> Ergebnis:
    fehler = []
    for key in _ERWARTET[szenario]:
        text = antworten.get(key)
        if text is None:
            return Ergebnis(False, f"Keine Antwort auf '{key}' - Mail vermutlich verworfen "
                                   "(Absenderpruefung?)")
        if key == "status":
            fehler += _pruefe_status(text, etappen, heute)
        elif key == "heute":
            fehler += _pruefe_heute(text, etappen, heute)
        elif key == "ruhetag":
            fehler += _pruefe_verschiebung(text, etappen, heute, 1, None)
        else:
            fehler += _pruefe_verschiebung(text, etappen, heute, None, neues_startdatum)
    if fehler:
        return Ergebnis(False, "; ".join(fehler))
    return Ergebnis(True, "Antworten entsprechen der Erwartung")


# ---------------------------------------------------------------------------
# Netzrand: SMTP, IMAP, Staging-API
# ---------------------------------------------------------------------------

def liefere_ein(msg: EmailMessage, smtp_factory=smtplib.SMTP) -> None:
    """Anonyme Zustellung Port 25; JEDER Empfaenger wird VOR dem Verbindungsaufbau geprueft."""
    felder = [v for k in ("To", "Cc", "Bcc") for v in msg.get_all(k, [])]
    roh = [str(v) for v in felder]
    if any(getattr(v, "defects", None) for v in felder) or any(c in z for z in roh for c in "\r\n"):
        pruefe_empfaenger("\n")  # Zeilenumbruch im Empfaengerfeld: Exit 2
    teile = [t for z in roh for t in z.split(",")]
    empfaenger = [a for _, a in getaddresses(teile)]
    if len(empfaenger) != len(teile) or any(a not in t for a, t in zip(empfaenger, teile)):
        pruefe_empfaenger("\n")  # Empfaengerfeld nicht eindeutig lesbar: Exit 2
    if not empfaenger:
        pruefe_empfaenger("")  # kein Empfaenger: Exit 2
    for a in empfaenger:
        pruefe_empfaenger(a)
    absender = getaddresses([str(msg["From"])])[0][1]
    with smtp_factory(MAIL_HOST, 25, timeout=30) as server:
        server.ehlo()
        server.sendmail(absender, empfaenger, msg.as_bytes())


def _alle_uids(imap) -> list[int]:
    _, daten = imap.uid("SEARCH", None, "ALL")
    return [int(u) for u in (daten[0] or b"").split()]


def hoechste_uid(imap) -> int:
    return max(_alle_uids(imap), default=0)


def _betreff(kopf) -> str:
    roh = kopf.get("Subject", "")
    try:
        return str(make_header(decode_header(roh)))
    except Exception:
        return str(roh)


def _eigene_uids(imap, plus_adresse: str, seit_uid: int, betreffe=None) -> list[int]:
    """UIDs > seit_uid, deren To-Header EXAKT die Plus-Adresse ist (IMAP-TO sucht Teilstring).

    ``betreffe``: erlaubte Betreff-Anfaenge (z.B. ``"[<Trip>]"``); Systemmails wie die
    Verifikationsmail bei der Registrierung gehen an dieselbe Adresse, sind aber keine Antwort.
    """
    _, daten = imap.uid("SEARCH", None, "TO", f'"{plus_adresse}"')
    treffer = []
    for uid in sorted(int(u) for u in (daten[0] or b"").split()):
        if uid <= seit_uid:
            continue
        _, d = imap.uid("FETCH", str(uid), "(BODY.PEEK[HEADER.FIELDS (TO SUBJECT)])")
        kopf = message_from_bytes(next((t[1] for t in d if isinstance(t, tuple)), b""))
        adressen = [a.lower() for _, a in getaddresses(kopf.get_all("To", []))]
        if adressen != [plus_adresse.lower()]:
            continue
        if betreffe and not _betreff(kopf).startswith(tuple(betreffe)):
            continue
        treffer.append(uid)
    return treffer


def finde_antwort(imap, plus_adresse: str, seit_uid: int, betreffe=None):
    for uid in _eigene_uids(imap, plus_adresse, seit_uid, betreffe):
        _, d = imap.uid("FETCH", str(uid), "(BODY.PEEK[])")
        roh = next((t[1] for t in d if isinstance(t, tuple)), None)
        if roh:
            return roh
    return None


def loesche_eigene_antworten(imap, plus_adresse: str) -> None:
    uids = _eigene_uids(imap, plus_adresse, 0)
    for uid in uids:
        imap.uid("STORE", str(uid), "+FLAGS", "(\\Deleted)")
    if uids:
        imap.expunge()


class StagingApi:
    """Wegwerf-Nutzer, Trips und Poll-Ausloesung auf Staging; transport ist der HTTP-Rand."""

    def __init__(self, basis_url, kern_url, kern_secret, transport):
        self._basis, self._kern = basis_url.rstrip("/"), kern_url.rstrip("/")
        self._secret, self._transport = kern_secret, transport
        self._username = None
        self._passwort = None

    def __repr__(self) -> str:
        return f"StagingApi(basis={self._basis!r}, nutzer={self._username!r})"

    @property
    def nutzer_id(self):
        return self._username

    def _rufe(self, methode, url, body=None, headers=None) -> dict:
        status, antwort = self._transport(methode, url, headers or {}, body)
        if not 200 <= status < 300:
            pfad = url.split("//", 1)[-1].split("/", 1)[-1]
            raise StagingFehler(f"{methode} /{pfad} -> HTTP {status}")
        return antwort

    def registriere(self, email_adresse: str) -> str:
        tag = email_adresse.split("+", 1)[-1].split("@", 1)[0]
        name, passwort = f"gzp-{tag}", secrets.token_urlsafe(18)
        b = self._basis
        self._rufe("POST", f"{b}/api/auth/register", {
            "username": name, "password": passwort, "email": email_adresse})
        self._username, self._passwort = name, passwort  # erst jetzt existiert der Nutzer
        self._rufe("POST", f"{b}/api/auth/login",
                   {"username": self._username, "password": self._passwort})
        tok = self._rufe("POST", f"{b}/api/auth/verify-email/staging-token",
                         {"username": self._username})["token"]
        self._rufe("POST", f"{b}/api/auth/verify-email", {"user": self._username, "token": tok})
        return self._username

    def lege_trip_an(self, trip: dict) -> None:
        self._rufe("POST", f"{self._basis}/api/trips", trip)

    def loese_poll_aus(self):
        antwort = self._rufe("POST", f"{self._kern}/api/scheduler/inbound-commands", None,
                             {"X-GZ-Core-Auth": self._secret})
        return antwort.get("count")

    def loesche_nutzer(self) -> None:
        if self._username is None:
            return
        self._rufe("POST", f"{self._basis}/api/auth/account/delete", {"password": self._passwort})


def http_transport():
    """Echter HTTP-Rand mit Cookie-Sitzung (Anmeldung per Cookie)."""
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))

    def transport(methode, url, headers, body):
        daten = json.dumps(body).encode() if body is not None else (b"{}" if methode == "POST" else None)
        req = urllib.request.Request(url, data=daten, method=methode,
                                     headers={"Content-Type": "application/json", **headers})
        try:
            with opener.open(req, timeout=60) as r:
                status, roh = r.status, r.read()
        except urllib.error.HTTPError as exc:
            status, roh = exc.code, exc.read()
        try:
            return status, json.loads(roh or b"{}")
        except ValueError:
            return status, {}

    return transport


# ---------------------------------------------------------------------------
# Lauf
# ---------------------------------------------------------------------------

def _befehle(szenario: str, etappen: list) -> list[tuple[str, str, str | None]]:
    if szenario == "A":
        return [("status", "status", None), ("heute", "heute", None)]
    if szenario == "D":
        return [("ruhetag", "### ruhetag: 1", "ruhetag")]
    if szenario == "D2":
        neu = min(_d(e) for e in etappen) + timedelta(days=3)
        return [("startdatum", f"### startdatum: {neu.isoformat()}", "startdatum")]
    return [("status", "status", None)]


def _mit_imap(imap_factory, funktion):
    """Eine IMAP-Verbindung je Aufruf, immer sauber mit logout geschlossen."""
    imap = imap_factory()
    try:
        return funktion(imap)
    finally:
        try:
            imap.logout()
        except Exception:
            pass


def _warte_auf_antwort(imap_factory, plus, seit_uid, timeout, schlaf, betreffe=None):
    gewartet = 0
    while True:
        raw = _mit_imap(imap_factory, lambda im: finde_antwort(im, plus, seit_uid, betreffe))
        if raw is not None or gewartet >= timeout:
            return raw
        schlaf(INTERVALL_S)
        gewartet += INTERVALL_S


def _fahre_befehl(befehl, trip, api, plus, smtp_factory, imap_factory, timeout, schlaf):
    key, text, wort = befehl
    seit = _mit_imap(imap_factory, hoechste_uid)
    liefere_ein(baue_befehlsmail(plus, trip["name"], text, wort), smtp_factory)
    try:
        count = api.loese_poll_aus()
    except (RuntimeError, OSError):
        count = None  # Cron-Takt abwarten
    betreffe = (f"[{trip['name']}]", "[GZ#")  # Trip-Name oder Shortcode-Kopf des Briefings
    raw = _warte_auf_antwort(imap_factory, plus, seit, timeout, schlaf, betreffe)
    print(f"  [{key}] Antwort: {'ja' if raw is not None else 'NEIN'} (Poll count={count})")
    return key, (antworttext(raw) if raw is not None else None), exit_code(raw, count)


def _fahre_szenario(s, api, plus, smtp_factory, imap_factory, heute, tag, timeout, schlaf) -> int:
    trip = baue_trip(s, tag, heute)
    api.lege_trip_an(trip)
    antworten, rc = {}, 0
    for befehl in _befehle(s, trip["stages"]):
        key, text, code = _fahre_befehl(befehl, trip, api, plus, smtp_factory, imap_factory,
                                        timeout, schlaf)
        antworten[key], rc = text, max(rc, code)
    neu = min(_d(e) for e in trip["stages"]) + timedelta(days=3) if s == "D2" else None
    erg = werte_aus(s, trip["stages"], antworten, heute, neues_startdatum=neu)
    print(f"{'PASS' if erg.ok else 'FAIL'} {s}: {erg.meldung}")
    return max(rc, 0 if erg.ok else 1)


def fuehre_lauf(szenarien, *, api, smtp_factory, imap_factory, heute, tag,
                timeout=360, schlaf=time.sleep, aufraeumen=True) -> int:
    plus = baue_plus_adresse(tag)
    nutzer = None
    try:
        nutzer = api.registriere(plus)
        rc = 0
        for s in szenarien:
            rc = max(rc, _fahre_szenario(s, api, plus, smtp_factory, imap_factory, heute, tag,
                                         timeout, schlaf))
        return rc
    finally:
        _raeume_auf(api, nutzer, imap_factory, plus, aufraeumen)


def fuehre_lauf_exit(*args, **kwargs) -> int:
    """Wie fuehre_lauf, aber Umgebungs-/HTTP-Fehler werden zu Exit 2 mit klarer Meldung."""
    try:
        return fuehre_lauf(*args, **kwargs)
    except (RuntimeError, OSError) as exc:
        print(f"Abbruch: {exc}", file=sys.stderr)
        return 2


def _raeume_auf(api, nutzer, imap_factory, plus, aufraeumen=True) -> None:
    if not aufraeumen:
        kennung = nutzer or getattr(api, "nutzer_id", None) or "unbekannt"
        print(f"--ohne-cleanup: nichts geloescht. Nutzer-Kennung: {kennung}, Adresse: {plus}")
        return
    try:
        _mit_imap(imap_factory, lambda im: loesche_eigene_antworten(im, plus))
    except Exception as exc:  # Aufraeumen darf den Befund nicht verdecken
        print(f"Hinweis: Antwortmails nicht geloescht ({type(exc).__name__}); Adresse {plus}")
    try:
        api.loesche_nutzer()
    except Exception as exc:
        kennung = nutzer or getattr(api, "nutzer_id", None) or "unbekannt"
        print(f"WARNUNG: Wegwerf-Nutzer nicht geloescht ({type(exc).__name__}) - "
              f"uebrig geblieben: {kennung}")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def _lade_env() -> dict:
    werte = {}
    try:
        for z in STAGING_ENV.read_text().splitlines():
            if "=" in z and not z.lstrip().startswith("#"):
                k, v = z.split("=", 1)
                werte[k.strip()] = v.strip().strip("'\"")
    except OSError:
        pass
    werte.update({k: v for k, v in os.environ.items() if k.startswith("GZ_")})
    return werte


def _imap_factory(env: dict):
    def fabrik():
        imap = imaplib.IMAP4_SSL(env.get("GZ_IMAP_HOST", MAIL_HOST), int(env.get("GZ_IMAP_PORT", "993")))
        imap.login(env["GZ_TEST_IMAP_USER"], env["GZ_TEST_IMAP_PASS"])
        imap.select("INBOX")
        return imap
    return fabrik


def _ortszeit_sperre(jetzt: datetime) -> bool:
    minuten = jetzt.hour * 60 + jetzt.minute
    return minuten >= 23 * 60 + 45 or minuten < 15


def main(argv=None, *, transport=None, smtp_factory=None, imap_factory=None, jetzt=None) -> int:
    """Netzrand injizierbar (Tests); ohne Angaben gelten echtes HTTP, SMTP und IMAP."""
    p = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    p.add_argument("--szenario", default="alle")
    p.add_argument("--timeout", type=int, default=360)
    p.add_argument("--ohne-cleanup", action="store_true", help="nur Fehlersuche: nichts loeschen")
    args = p.parse_args(argv)
    szenarien = _GRUPPEN.get(args.szenario) or ([args.szenario] if args.szenario in _PLAN else None)
    if szenarien is None:
        print(f"Unbekanntes Szenario: {args.szenario}", file=sys.stderr)
        return 2
    env = _lade_env()
    fehlend = [k for k in ("GZ_TEST_IMAP_USER", "GZ_TEST_IMAP_PASS", "GZ_CORE_SHARED_SECRET") if not env.get(k)]
    if fehlend:
        print(f"Zugangsdaten fehlen: {', '.join(fehlend)}", file=sys.stderr)
        return 2
    from zoneinfo import ZoneInfo
    jetzt = jetzt or datetime.now(ZoneInfo("Europe/Vienna"))
    if _ortszeit_sperre(jetzt):
        print("Abbruch: Lauf faellt ins Zeitfenster um Mitternacht Ortszeit - spaeter erneut starten.",
              file=sys.stderr)
        return 2
    api = StagingApi(env.get("GZ_STAGING_BASE_URL", "https://staging.gregor20.henemm.com"),
                     env.get("GZ_STAGING_CORE_URL", "http://127.0.0.1:8001"),
                     env["GZ_CORE_SHARED_SECRET"], transport or http_transport())
    return fuehre_lauf_exit(szenarien, api=api, smtp_factory=smtp_factory or smtplib.SMTP,
                            imap_factory=imap_factory or _imap_factory(env), heute=jetzt.date(), tag=baue_tag(),
                            timeout=args.timeout, aufraeumen=not args.ohne_cleanup)


if __name__ == "__main__":
    sys.exit(main())
