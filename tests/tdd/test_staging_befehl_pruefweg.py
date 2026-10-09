"""Staging-Prüfweg für Befehle über den echten E-Mail-Eingang (#2542).

Spec: docs/specs/modules/fix_2542_staging_befehl_pruefweg.md

Prüfling: ``.claude/tools/staging_befehl_pruefen.py`` — aufgelöst RELATIV zu
dieser Testdatei (nie über den festen Hauptrepo-Pfad), geladen per
``importlib`` in jedem Test. Fehlt das Werkzeug, schlägt jeder Test einzeln
fehl (kein Sammel-ERROR beim Einsammeln).

Schnittstellen-Vertrag, den diese Tests festschreiben
------------------------------------------------------
Konstanten:
    STAGING_EINGANG = "gregor-staging@henemm.com"

Reine Funktionen:
    baue_tag() -> str
        eindeutig je Aufruf, nur ``[a-z0-9-]`` (gültig im Local-Part).
    baue_plus_adresse(tag) -> "gregor-test+<tag>@henemm.com"
    pruefe_empfaenger(adresse) -> str
        gibt die Adresse zurück, wenn sie GENAU auf ``@henemm.com`` endet
        (eine einzelne Adresse, keine Subdomain, keine Zeilenumbrüche);
        sonst ``SystemExit`` mit Code 2.
    baue_befehlsmail(plus_adresse, trip_name, befehl) -> EmailMessage
        From = plus_adresse, To = STAGING_EINGANG,
        Subject = "[<trip_name>] <befehl>", erste Textzeile = befehl.
    baue_trip(szenario, tag, heute) -> dict
        szenario in {"A", "B", "C", "D", "D2"}; Ergebnis im Format der
        Staging-API: {"id", "name", "stages": [{"id", "name",
        "date": "YYYY-MM-DD", "waypoints": [{"id", "name", "lat", "lon",
        "elevation_m"}, ...]}, ...]} in der Listenreihenfolge, in der der
        Trip angelegt wird.
    antworttext(raw: bytes) -> str
        Text einer Antwortmail (text/plain-Teil, sonst HTML ohne Tags).
    werte_aus(szenario, etappen, antworten, heute, *, neues_startdatum=None)
        -> Ergebnis mit ``.ok: bool`` und ``.meldung: str``.
        ``antworten`` bildet Befehl -> Antworttext (oder None, wenn keine
        Antwort kam) ab: A {"status", "heute"}, B/C {"status"},
        D {"ruhetag"}, D2 {"startdatum"}.
    exit_code(antwort, count) -> int
        0 genau dann, wenn eine Antwort da ist — ``count`` (Zähler des
        Poll-Aufrufs) ist nur Diagnose.

Netzrand (injizierbar, in den Tests durch kleine Ersatzklassen belegt —
kein Mock/patch):
    liefere_ein(msg, smtp_factory=smtplib.SMTP) -> None
        prüft JEDEN Empfänger mit pruefe_empfaenger, BEVOR smtp_factory
        aufgerufen wird; Einlieferung an mail.henemm.com Port 25, Umschlag-
        Absender = From-Adresse.
    finde_antwort(imap, plus_adresse, seit_uid) -> bytes | None
        ``imap`` ist ein imaplib-artiges Objekt (ausgewähltes Postfach), es
        wird ausschließlich ``imap.uid(...)`` benutzt; Abruf von Inhalten nur
        per ``BODY.PEEK[...]``. Treffer = UID > seit_uid UND To-Adresse exakt
        gleich plus_adresse.
    StagingApi(basis_url, kern_url, kern_secret, transport)
        transport(method, url, headers: dict, body: dict | None)
            -> (status: int, antwort: dict)
        Methoden: registriere(email) -> nutzer_id, lege_trip_an(trip),
        loese_poll_aus() -> int | None, loesche_nutzer().
    fuehre_lauf(szenarien, *, api, smtp_factory, imap_factory, heute, tag,
                timeout=360, schlaf=time.sleep) -> int
        legt EINEN Wegwerf-Nutzer an, räumt im finally auf (loesche_nutzer);
        scheitert das Aufräumen, wird die Nutzer-Kennung ausgegeben.
        Liest die Uhr NICHT selbst (``heute`` kommt von außen); die Sperre
        für das Zeitfenster um Mitternacht Ortszeit gehört in ``main()``.
        Je Befehl wird ``seit_uid`` neu bestimmt, damit eine Antwort nie
        einem früheren Befehl desselben Laufs zugeordnet wird.
        Rückgabe 0 nur, wenn alle gewählten Szenarien bestehen.

Fehler der StagingApi (HTTP ≠ 2xx) erben von ``RuntimeError``. Der Header
``X-GZ-Core-Auth`` trägt den rohen Secret-Wert (``api/main.py``,
``CORE_AUTH_HEADER``, Vergleich per ``compare_digest``).
"""
from __future__ import annotations

import email
import email.header
import email.policy
import importlib.util
import re
import sys
from datetime import date, timedelta
from email.message import EmailMessage
from email.utils import getaddresses
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WERKZEUG = REPO_ROOT / ".claude" / "tools" / "staging_befehl_pruefen.py"
E2E_VERIFY = REPO_ROOT / ".claude" / "commands" / "e2e-verify.md"
STAGING_ENV = Path("/home/hem/gregor_zwanzig_staging/.env")

HEUTE = date(2027, 7, 14)


def _werkzeug():
    if not WERKZEUG.exists():
        pytest.fail(f"Prüfwerkzeug fehlt: {WERKZEUG.relative_to(REPO_ROOT)}")
    name = "staging_befehl_pruefen_unter_test"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, WERKZEUG)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Ersatzklassen am Netzrand
# ---------------------------------------------------------------------------

class _ErsatzSmtp:
    """smtplib.SMTP-artig; zählt Verbindungen und hält den Umschlag fest."""

    verbindungen: list = []
    umschlaege: list = []
    fehler: BaseException | None = None

    def __init__(self, host="", port=0, *args, **kwargs):
        type(self).verbindungen.append((host, port))

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def ehlo(self, *a, **k):
        return (250, b"ok")

    helo = ehlo

    def sendmail(self, from_addr, to_addrs, msg, *a, **k):
        if type(self).fehler is not None:
            raise type(self).fehler
        if isinstance(to_addrs, str):
            to_addrs = [to_addrs]
        type(self).umschlaege.append((from_addr, list(to_addrs), msg))
        return {}

    def send_message(self, msg, from_addr=None, to_addrs=None, *a, **k):
        if from_addr is None:
            from_addr = getaddresses([msg["From"]])[0][1]
        if to_addrs is None:
            to_addrs = [a for _, a in getaddresses(msg.get_all("To", []))]
        return self.sendmail(from_addr, to_addrs, msg.as_bytes())

    def quit(self):
        return (221, b"bye")

    close = quit


def _smtp_klasse(fehler: BaseException | None = None):
    return type("Smtp", (_ErsatzSmtp,), {"verbindungen": [], "umschlaege": [], "fehler": fehler})


def _mail_bytes(to: str, betreff: str, text: str, msgid: str, mail_typ: str | None = None) -> bytes:
    m = EmailMessage()
    if mail_typ:
        m["X-GZ-Mail-Type"] = mail_typ
    m["From"] = "gregor-test@henemm.com"
    m["To"] = to
    m["Subject"] = betreff
    m["Message-ID"] = msgid
    m.set_content(text)
    return m.as_bytes()


class _ErsatzImap:
    """imaplib-artiges Postfach mit echter IMAP-Semantik für die genutzten Befehle.

    - SEARCH-Kriterien TO/HEADER werden wie echte Server als TEILSTRING
      ausgewertet (deshalb muss das Werkzeug den To-Header selbst exakt
      vergleichen).
    - ``UID n:*`` liefert wie echte Server mindestens die höchste UID.
    - FETCH ohne ``PEEK`` (BODY[...] / RFC822) setzt \\Seen.
    """

    def __init__(self, mails: dict[int, bytes]):
        self.mails = dict(mails)
        self.gesehen: set[int] = set()
        self.befehle: list[tuple] = []
        self.geloescht: set[int] = set()

    def select(self, *a, **k):
        return ("OK", [str(len(self.mails)).encode()])

    def login(self, *a, **k):
        return ("OK", [b""])

    def logout(self):
        return ("BYE", [b""])

    def close(self):
        return ("OK", [b""])

    def expunge(self):
        for uid in list(self.geloescht):
            self.mails.pop(uid, None)
        return ("OK", [b""])

    @staticmethod
    def _text(x):
        return x.decode() if isinstance(x, bytes) else str(x)

    def _uids(self, satz: str) -> list[int]:
        alle = sorted(self.mails)
        ergebnis: list[int] = []
        for teil in satz.split(","):
            if ":" in teil:
                lo, hi = teil.split(":")
                lo_i = int(lo)
                hi_i = max(alle) if hi == "*" else int(hi)
                treffer = [u for u in alle if lo_i <= u <= hi_i]
                if hi == "*" and not treffer and alle:
                    treffer = [max(alle)]
                ergebnis += treffer
            elif teil.strip():
                u = int(teil)
                if u in self.mails:
                    ergebnis.append(u)
        return ergebnis

    def uid(self, befehl, *args):
        befehl = self._text(befehl).upper()
        self.befehle.append((befehl,) + tuple(self._text(a) if a is not None else None for a in args))
        if befehl == "SEARCH":
            kriterien = " ".join(self._text(a) for a in args if a is not None)
            treffer = sorted(self.mails)
            m = re.search(r"UID\s+(\S+)", kriterien, re.I)
            if m:
                erlaubt = set(self._uids(m.group(1)))
                treffer = [u for u in treffer if u in erlaubt]
            for feld, wert in re.findall(r'(?:HEADER\s+)?\b(TO)\s+"?([^"\s)]+)"?', kriterien, re.I):
                treffer = [
                    u for u in treffer
                    if wert.lower() in (email.message_from_bytes(self.mails[u])["To"] or "").lower()
                ]
            return ("OK", [" ".join(str(u) for u in treffer).encode()])
        if befehl == "FETCH":
            satz, teil = self._text(args[0]), self._text(args[1]).upper()
            daten: list = []
            for u in self._uids(satz):
                raw = self.mails[u]
                if "HEADER.FIELDS" in teil:
                    felder = re.search(r"HEADER\.FIELDS\s*\(([^)]*)\)", teil).group(1).split()
                    kopf = email.message_from_bytes(raw, policy=email.policy.compat32)
                    nutz = b"".join(f"{n}: {v}\n".encode() for n in felder
                                    for k, v in kopf.items() if k.upper() == n) + b"\n"
                elif "HEADER" in teil:
                    nutz = raw.split(b"\n\n", 1)[0] + b"\n\n"
                else:
                    nutz = raw
                if "PEEK" not in teil and ("BODY[" in teil or re.search(r"RFC822(?![.](HEADER|SIZE))", teil)):
                    self.gesehen.add(u)
                daten.append((f"{u} (UID {u} BODY[] {{{len(nutz)}}}".encode(), nutz))
                daten.append(b")")
            return ("OK", daten)
        if befehl == "STORE":
            satz, op, flags = self._text(args[0]), self._text(args[1]), self._text(args[2])
            for u in self._uids(satz):
                if "\\SEEN" in flags.upper() and op.startswith("+"):
                    self.gesehen.add(u)
                if "\\DELETED" in flags.upper() and op.startswith("+"):
                    self.geloescht.add(u)
            return ("OK", [b""])
        if befehl == "EXPUNGE":
            return self.expunge()
        return ("OK", [b""])


class _ErsatzApi:
    """Staging-Schnittstelle am Netzrand; protokolliert die Schrittfolge."""

    def __init__(self, fehler_bei: str | None = None, fehler: BaseException | None = None,
                 loeschen_scheitert: bool = False):
        self.schritte: list[str] = []
        self.fehler_bei = fehler_bei
        self.fehler = fehler
        self.loeschen_scheitert = loeschen_scheitert
        self.nutzer_id = "nutzer-wegwerf-7f3a91"

    def _ggf(self, schritt):
        self.schritte.append(schritt)
        if self.fehler_bei == schritt:
            raise self.fehler

    def registriere(self, email_adresse):
        self._ggf("registriere")
        return self.nutzer_id

    def lege_trip_an(self, trip):
        self._ggf("lege_trip_an")

    def loese_poll_aus(self):
        self._ggf("loese_poll_aus")
        return 0

    def loesche_trip(self, trip_id):
        self.schritte.append("loesche_trip")

    def loesche_nutzer(self):
        self.schritte.append("loesche_nutzer")
        if self.loeschen_scheitert:
            raise RuntimeError("delete failed")


def _kein_schlaf(_s):
    return None


# ---------------------------------------------------------------------------
# Hilfen: Antworttexte im Format des Systems
# ---------------------------------------------------------------------------

def _datum(e) -> date:
    return date.fromisoformat(e["date"])


def _echter_trip(trip_dict):
    """Baut aus der Werkzeug-Ausgabe einen echten ``app.trip.Trip``."""
    from app.trip import Stage, Trip, Waypoint

    stages = []
    for i, e in enumerate(trip_dict["stages"]):
        wps = [
            Waypoint(id=w.get("id", f"G{j+1}"), name=w.get("name", ""), lat=float(w["lat"]),
                     lon=float(w["lon"]), elevation_m=int(w.get("elevation_m", 0)))
            for j, w in enumerate(e.get("waypoints") or [{"lat": 47.0, "lon": 11.0}])
        ]
        stages.append(Stage(id=e.get("id", f"T{i+1}"), name=e["name"], date=_datum(e), waypoints=wps))
    return Trip(id=trip_dict.get("id", "t"), name=trip_dict["name"], stages=stages)


def _status_text(trip_dict, heute: date) -> str:
    """Format von ``TripCommandProcessor._show_status`` (E-Mail-Langform, Strich „–")."""
    trip = _echter_trip(trip_dict)
    zeilen = [f"Status: {trip.name}", ""]
    for s in trip.stages:
        if s.date >= heute:
            zeilen.append(f"  {s.date:%d.%m.%Y} – {trip.numbered_stage_label(s)}")
    return "\n".join(zeilen)


def _ruhetag_text(trip_dict, heute: date) -> str:
    """Format von ``_apply_ruhetag`` (verschiebt Etappen NACH heute um +1 Tag)."""
    trip = _echter_trip(trip_dict)
    zeilen = ["Ruhetag eingetragen: +1 Tag.", "", "Verschobene Etappen:"]
    for s in trip.stages:
        if s.date > heute:
            zeilen.append(f"  {trip.numbered_stage_label(s)}: {s.date:%d.%m.%Y} -> {s.date + timedelta(days=1):%d.%m.%Y}")
    zeilen += ["", "Naechster Report kommt planmaessig."]
    return "\n".join(zeilen)


def _startdatum_text(trip_dict, neues_start: date) -> str:
    """Format von ``_shift_start``."""
    trip = _echter_trip(trip_dict)
    alt = min(s.date for s in trip.stages)
    delta = neues_start - alt
    zeilen = [f"Startdatum verschoben: {alt:%d.%m.%Y} -> {neues_start:%d.%m.%Y}", "", "Neue Etappen-Daten:"]
    for s in trip.stages:
        zeilen.append(f"  {trip.numbered_stage_label(s)}: {s.date + delta:%d.%m.%Y}")
    return "\n".join(zeilen)


def _chrono_nummer(etappen, name: str) -> int:
    geordnet = sorted(etappen, key=_datum)
    return [e["name"] for e in geordnet].index(name) + 1


OBST = "02: Obstansersee-Hütte nach Porzehütte"
OBST_REST = "Obstansersee-Hütte nach Porzehütte"
B_NAMEN = ["02: X", "02 – X", "2 Seen Runde", "1.5 km Runde", "1. Pass", "2. X", "03:"]


# ---------------------------------------------------------------------------
# AC-2: Adressen, Header, Tags
# ---------------------------------------------------------------------------

def test_adressen_und_header_werden_exakt_gebaut():
    """AC-2: Plus-Adresse, From = Umschlag-Absender, To = Staging-Eingang, Betreff."""
    w = _werkzeug()
    tag = w.baue_tag()
    plus = w.baue_plus_adresse(tag)
    assert plus == f"gregor-test+{tag}@henemm.com"
    assert w.STAGING_EINGANG == "gregor-staging@henemm.com"

    msg = w.baue_befehlsmail(plus, f"GZ-Pruefung {tag} A", "status")
    assert getaddresses([msg["From"]])[0][1] == plus
    assert [a for _, a in getaddresses(msg.get_all("To", []))] == ["gregor-staging@henemm.com"]
    assert msg["Subject"] == f"[GZ-Pruefung {tag} A] status"
    text = msg.get_body(preferencelist=("plain",)).get_content()
    assert text.strip().splitlines()[0].strip() == "status"

    smtp = _smtp_klasse()
    w.liefere_ein(msg, smtp_factory=smtp)
    assert len(smtp.verbindungen) == 1
    host, port = smtp.verbindungen[0]
    assert host in ("mail.henemm.com", "178.104.143.19")
    assert port == 25
    assert len(smtp.umschlaege) == 1
    umschlag_von, umschlag_an, _ = smtp.umschlaege[0]
    assert umschlag_von == plus, "Umschlag-Absender muss exakt die From-Adresse sein"
    assert umschlag_an == ["gregor-staging@henemm.com"]


def test_tags_sind_je_lauf_eindeutig():
    """AC-2: zwei Läufe erzeugen nie denselben Tag — auch nicht in derselben Sekunde."""
    w = _werkzeug()
    tags = [w.baue_tag() for _ in range(1000)]
    assert len(set(tags)) == 1000
    for t in tags:
        assert re.fullmatch(r"[a-z0-9-]{4,40}", t), t


# ---------------------------------------------------------------------------
# AC-3: Relay-Sperre
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("adresse", [
    "gregor-staging@henemm.com",
    "gregor-test@henemm.com",
    "gregor-test+abc123@henemm.com",
])
def test_relay_sperre_laesst_henemm_adressen_zu(adresse):
    """AC-3 (Positivseite): genau @henemm.com wird akzeptiert."""
    w = _werkzeug()
    assert w.pruefe_empfaenger(adresse) == adresse


@pytest.mark.parametrize("adresse", [
    "x@henemm.com.evil.de",
    "henemm.com@evil.de",
    "x@evil.de",
    "x@sub.henemm.com",
    "x@henemm.comx",
    "x@henemm.com, y@evil.de",
    "x@henemm.com\r\nRCPT TO:<y@evil.de>",
    "",
])
def test_relay_sperre_lehnt_fremde_domains_ab(adresse):
    """AC-3: fremde/getarnte Domains ⇒ Exit 2, und zwar VOR jedem Verbindungsaufbau."""
    w = _werkzeug()
    with pytest.raises(SystemExit) as exc:
        w.pruefe_empfaenger(adresse)
    assert exc.value.code == 2

    msg = EmailMessage()
    msg["From"] = "gregor-test+abc@henemm.com"
    msg["To"] = adresse.replace("\r\n", " ") or "nobody@evil.de"
    msg["Subject"] = "[T] status"
    msg.set_content("status")
    smtp = _smtp_klasse()
    with pytest.raises(SystemExit) as exc2:
        w.liefere_ein(msg, smtp_factory=smtp)
    assert exc2.value.code == 2
    assert smtp.verbindungen == [], "Bei gesperrtem Empfänger darf keine Verbindung aufgebaut werden"


# ---------------------------------------------------------------------------
# AC-4: Exit-Code — Antwortmail ist das Erfolgssignal, nicht count
# ---------------------------------------------------------------------------

def test_ausbleibende_antwort_ist_exit_ungleich_null():
    """AC-4: keine Antwort ⇒ Exit ≠ 0, Meldung nennt das Verwerfen — egal was count sagt."""
    w = _werkzeug()
    assert w.exit_code(None, count=1) != 0
    assert w.exit_code(None, count=0) != 0
    assert w.exit_code(None, count=None) != 0

    trip = w.baue_trip("B", "tagx", HEUTE)
    erg = w.werte_aus("B", trip["stages"], {"status": None}, HEUTE)
    assert erg.ok is False
    assert "verworfen" in erg.meldung.lower()


def test_antwort_da_trotz_count_null_ist_erfolg():
    """AC-4: Antwort da, Poll meldet count=0 (Cron war schneller) ⇒ Erfolg."""
    w = _werkzeug()
    raw = _mail_bytes("gregor-test+t@henemm.com", "[T] Status", "Status: T", "<a@x>")
    assert w.exit_code(raw, count=0) == 0
    assert w.exit_code(raw, count=None) == 0


# ---------------------------------------------------------------------------
# AC-5: Antwortsuche im geteilten Postfach
# ---------------------------------------------------------------------------

def _postfach(plus: str):
    lokal, domain = plus.split("@")
    return _ErsatzImap({
        3: _mail_bytes(plus, "[T] Status", "alte eigene Mail", "<alt@x>"),
        7: _mail_bytes("gregor-test@henemm.com", "fremd", "fremde Mail", "<fremd@x>"),
        8: _mail_bytes(f"{lokal}x@{domain}", "[T] Status", "anderer Lauf (Tag-Verlängerung)", "<verl@x>"),
        9: _mail_bytes("gregor-test+anderertag@henemm.com", "[T] Status", "anderer Lauf", "<anders@x>"),
        10: _mail_bytes(f'"Gregor Test" <{plus}>', "[T] Status", "Status: richtig", "<richtig@x>"),
        11: _mail_bytes(f"x{plus}", "[T] Status", "Präfix-Verlängerung", "<praefix@x>"),
    })


def test_antwortsuche_nimmt_nur_die_eigene_mail():
    """AC-5: genau die Mail mit To == eigene Plus-Adresse UND UID > Laufbeginn."""
    w = _werkzeug()
    plus = "gregor-test+lauf42@henemm.com"
    imap = _postfach(plus)
    raw = w.finde_antwort(imap, plus, seit_uid=5)
    assert raw is not None, "die eigene neue Antwort (UID 10) wurde nicht gefunden"
    assert email.message_from_bytes(raw)["Message-ID"] == "<richtig@x>"

    leer = _ErsatzImap({k: v for k, v in _postfach(plus).mails.items() if k != 10})
    assert w.finde_antwort(leer, plus, seit_uid=5) is None, \
        "ohne eigene neue Mail darf nichts gefunden werden (alte UID 3 und Fremde zählen nicht)"


def test_antwortsuche_markiert_fremde_mails_nicht():
    """AC-5: Abruf nur per BODY.PEEK, kein STORE/Seen auf fremde Mails."""
    w = _werkzeug()
    plus = "gregor-test+lauf42@henemm.com"
    imap = _postfach(plus)
    w.finde_antwort(imap, plus, seit_uid=5)

    assert imap.gesehen == set(), f"Gelesen-Markierung gesetzt auf UIDs {sorted(imap.gesehen)}"
    for befehl in imap.befehle:
        assert befehl[0] in ("SEARCH", "FETCH"), f"unerwarteter IMAP-Befehl {befehl}"
        if befehl[0] == "FETCH":
            teil = (befehl[2] or "").upper()
            assert "PEEK" in teil or "HEADER" in teil and "RFC822" in teil, f"Abruf ohne PEEK: {befehl}"


# ---------------------------------------------------------------------------
# AC-6: Szenarien
# ---------------------------------------------------------------------------

def test_szenarien_bauen_die_vorgesehenen_etappen():
    """AC-6: Namen, Positionen, Daten und Lauf-Tag der gebauten Trips."""
    w = _werkzeug()
    tag = "lauf7q"
    trips = {s: w.baue_trip(s, tag, HEUTE) for s in ("A", "B", "C", "D", "D2")}

    for s, t in trips.items():
        assert tag in t["name"], f"Szenario {s}: Trip-Name ohne Lauf-Tag"
        assert t["stages"], f"Szenario {s}: keine Etappen"
        for e in t["stages"]:
            assert e["waypoints"], f"Szenario {s}: Etappe {e['name']!r} ohne Wegpunkte"
            for wp in e["waypoints"]:
                assert -90 <= float(wp["lat"]) <= 90 and -180 <= float(wp["lon"]) <= 180
    assert len({t["name"] for t in trips.values()}) == 5
    assert len({t["id"] for t in trips.values()}) == 5

    a = trips["A"]["stages"]
    assert len(a) == 5
    assert a[3]["name"] == OBST
    assert _datum(a[3]) == HEUTE
    assert all(_datum(e) < HEUTE for e in a[:3])
    assert _datum(a[4]) > HEUTE

    b = trips["B"]["stages"]
    assert sorted(e["name"] for e in b) == sorted(B_NAMEN)
    assert all(_datum(e) >= HEUTE for e in b)

    c = trips["C"]["stages"]
    assert len(c) == 4
    daten = [_datum(e) for e in c]
    assert daten != sorted(daten), "Szenario C muss in vertauschter Listenreihenfolge angelegt werden"
    assert all(d >= HEUTE for d in daten)
    abweichend = 0
    for e in c:
        m = re.search(r"\d+", e["name"])
        assert m, f"Szenario C: Name {e['name']!r} ohne Zahl"
        if int(m.group()) != _chrono_nummer(c, e["name"]):
            abweichend += 1
    assert abweichend >= 2, "Namenszahlen in C müssen von der Datumsfolge abweichen"

    for s in ("D", "D2"):
        d = trips[s]["stages"]
        assert min(_datum(e) for e in d) > HEUTE, f"{s}: Startdatum muss in der Zukunft liegen"
        assert any(re.match(r"^\d{1,2}\s*[:–-]", e["name"]) for e in d), f"{s}: keine Zahlenpräfix-Namen"


# ---------------------------------------------------------------------------
# AC-7: Auswertung status / heute
# ---------------------------------------------------------------------------

def test_auswertung_status_heute_zahl():
    """AC-7: status und heute nennen für die heutige Etappe dieselbe (chronologische) Zahl."""
    w = _werkzeug()
    trip = w.baue_trip("A", "tagA", HEUTE)
    etappen = trip["stages"]
    n = _chrono_nummer(etappen, OBST)
    status = _status_text(trip, HEUTE)
    assert f"Etappe {n}: {OBST_REST}" in status  # Fixture-Selbstkontrolle

    # Text-Fassung des Briefings (plain.py: stage_name-Zeile = numbered_stage_label)
    heute_lang = f"Morgen-Briefing\nEtappe {n}: {OBST_REST}\n08:00 12°C"
    # HTML-Fassung nach Tag-Entfernung (html.py: eigenes Element „Etappe N / Gesamt", Titel getrennt)
    heute_html = f"MORGEN\nEtappe {n} / {len(etappen)}\n{OBST_REST}\nDo · 14.07.2027 · 06:00 MESZ"
    heute_kurz = f"E{n} {OBST_REST[:10]} T12"
    assert w.werte_aus("A", etappen, {"status": status, "heute": heute_lang}, HEUTE).ok
    assert w.werte_aus("A", etappen, {"status": status, "heute": heute_html}, HEUTE).ok
    assert w.werte_aus("A", etappen, {"status": status, "heute": heute_kurz}, HEUTE).ok

    # heute nennt die Zahl aus dem Namen (2) statt der Position
    falsch_heute = f"Morgen-Briefing\nEtappe 2: {OBST_REST}\n"
    assert not w.werte_aus("A", etappen, {"status": status, "heute": falsch_heute}, HEUTE).ok
    falsch_heute = f"MORGEN\nEtappe 2 / {len(etappen)}\n{OBST_REST}\n"
    assert not w.werte_aus("A", etappen, {"status": status, "heute": falsch_heute}, HEUTE).ok
    # heute nennt eine andere Zahl als status
    assert not w.werte_aus("A", etappen, {"status": status, "heute": f"E{n + 1} Obstansers"}, HEUTE).ok
    # status mit doppelter Nummer
    doppelt = status.replace(f"Etappe {n}: {OBST_REST}", f"Etappe {n}: {OBST}")
    assert not w.werte_aus("A", etappen, {"status": doppelt, "heute": heute_lang}, HEUTE).ok
    # status mit Namenszahl statt Position
    namenszahl = status.replace(f"Etappe {n}: {OBST_REST}", f"Etappe 2: {OBST_REST}")
    assert not w.werte_aus("A", etappen, {"status": namenszahl, "heute": heute_lang}, HEUTE).ok
    # Antwort fehlt
    assert not w.werte_aus("A", etappen, {"status": status, "heute": None}, HEUTE).ok


def test_auswertung_praefix_und_randfaelle():
    """AC-7: „02: X" → „Etappe N: X", „03:" → „Etappe N", Punkt ist kein Trenner."""
    w = _werkzeug()
    trip = w.baue_trip("B", "tagB", HEUTE)
    etappen = trip["stages"]
    status = _status_text(trip, HEUTE)

    erwartet_rest = {
        "02: X": "X", "02 – X": "X", "2 Seen Runde": "2 Seen Runde",
        "1.5 km Runde": "1.5 km Runde", "1. Pass": "1. Pass", "2. X": "2. X", "03:": None,
    }
    for name, rest in erwartet_rest.items():  # Fixture-Selbstkontrolle gegen #2441 AC-2/3
        n = _chrono_nummer(etappen, name)
        if rest is None:
            assert re.search(rf"– Etappe {n}$", status, re.M)
        else:
            assert f"– Etappe {n}: {rest}" in status

    assert w.werte_aus("B", etappen, {"status": status}, HEUTE).ok

    n02 = _chrono_nummer(etappen, "02: X")
    zeilen = status.splitlines()
    idx = next(i for i, z in enumerate(zeilen) if z.endswith(f"Etappe {n02}: X"))
    kaputt = list(zeilen)
    kaputt[idx] = kaputt[idx].replace(f"Etappe {n02}: X", f"Etappe {n02}: 02: X")
    assert not w.werte_aus("B", etappen, {"status": "\n".join(kaputt)}, HEUTE).ok

    n03 = _chrono_nummer(etappen, "03:")
    kaputt = [z + ":" if z.endswith(f"Etappe {n03}") else z for z in zeilen]
    assert not w.werte_aus("B", etappen, {"status": "\n".join(kaputt)}, HEUTE).ok

    n1p = _chrono_nummer(etappen, "1. Pass")
    kaputt = [z.replace(f"Etappe {n1p}: 1. Pass", f"Etappe {n1p}: Pass") for z in zeilen]
    assert not w.werte_aus("B", etappen, {"status": "\n".join(kaputt)}, HEUTE).ok

    ohne_zeile = "\n".join(z for z in zeilen if "2 Seen Runde" not in z)
    assert not w.werte_aus("B", etappen, {"status": ohne_zeile}, HEUTE).ok


def test_auswertung_chronologische_zaehlung():
    """AC-7 (#2441 AC-9): Nummer = Position nach Datum, nicht Listenposition/Namenszahl."""
    w = _werkzeug()
    trip = w.baue_trip("C", "tagC", HEUTE)
    etappen = trip["stages"]
    status = _status_text(trip, HEUTE)
    assert w.werte_aus("C", etappen, {"status": status}, HEUTE).ok

    # Nummern nach Listenposition statt nach Datum
    falsch = []
    zeilen = status.splitlines()
    for i, e in enumerate(etappen):
        n_chrono = _chrono_nummer(etappen, e["name"])
        if n_chrono != i + 1:
            falsch.append((n_chrono, i + 1))
    assert falsch, "Fixture: Listenreihenfolge muss von der Datumsfolge abweichen"
    nach_liste = []
    for z in zeilen:
        m = re.search(r"Etappe (\d+)", z)
        if m:
            datum = re.search(r"\d{2}\.\d{2}\.\d{4}", z).group()
            pos = next(i for i, e in enumerate(etappen) if f"{_datum(e):%d.%m.%Y}" == datum) + 1
            z = z.replace(f"Etappe {m.group(1)}", f"Etappe {pos}")
        nach_liste.append(z)
    assert "\n".join(nach_liste) != status
    assert not w.werte_aus("C", etappen, {"status": "\n".join(nach_liste)}, HEUTE).ok


# ---------------------------------------------------------------------------
# AC-8: Auswertung Ruhetag / Startdatum
# ---------------------------------------------------------------------------

def test_auswertung_ruhetag_bestaetigung():
    """AC-8: Ruhetag-Bestätigung „  Etappe N: Rest: alt -> alt+1" mit status-Nummern."""
    w = _werkzeug()
    trip = w.baue_trip("D", "tagD", HEUTE)
    etappen = trip["stages"]
    text = _ruhetag_text(trip, HEUTE)
    assert text.count("->") == len(etappen)  # Fixture-Selbstkontrolle: alle in der Zukunft
    assert w.werte_aus("D", etappen, {"ruhetag": text}, HEUTE).ok

    m = re.search(r"Etappe (\d+)", text)
    n = int(m.group(1))
    andere = n + 1 if n < len(etappen) else n - 1
    vertauscht = text.replace(f"Etappe {n}:", "Etappe §:", 1).replace(f"Etappe {andere}:", f"Etappe {n}:", 1) \
        .replace("Etappe §:", f"Etappe {andere}:", 1)
    assert not w.werte_aus("D", etappen, {"ruhetag": vertauscht}, HEUTE).ok

    ohne_datum = re.sub(r" -> \d{2}\.\d{2}\.\d{4}", " -> ", text, count=1)
    assert not w.werte_aus("D", etappen, {"ruhetag": ohne_datum}, HEUTE).ok

    zwei_tage = _ruhetag_text(trip, HEUTE)
    erstes = re.search(r"-> (\d{2}\.\d{2}\.\d{4})", zwei_tage).group(1)
    t, mo, j = (int(x) for x in erstes.split("."))
    zwei_tage = zwei_tage.replace(f"-> {erstes}", f"-> {date(j, mo, t) + timedelta(days=1):%d.%m.%Y}", 1)
    assert not w.werte_aus("D", etappen, {"ruhetag": zwei_tage}, HEUTE).ok

    praefix = re.sub(r"(Etappe \d+): X", r"\1: 02: X", text, count=1)
    if praefix != text:
        assert not w.werte_aus("D", etappen, {"ruhetag": praefix}, HEUTE).ok


def test_auswertung_startdatum_bestaetigung():
    """AC-8: Startdatum-Bestätigung „  Etappe N: Rest: neues Datum" mit status-Nummern."""
    w = _werkzeug()
    trip = w.baue_trip("D2", "tagD2", HEUTE)
    etappen = trip["stages"]
    neu = min(_datum(e) for e in etappen) + timedelta(days=3)
    text = _startdatum_text(trip, neu)
    assert w.werte_aus("D2", etappen, {"startdatum": text}, HEUTE, neues_startdatum=neu).ok

    # Datumsteil falsch verschoben (Delta 2 statt 3)
    falsch = _startdatum_text(trip, neu - timedelta(days=1))
    assert not w.werte_aus("D2", etappen, {"startdatum": falsch}, HEUTE, neues_startdatum=neu).ok

    # abweichende Nummer
    m = re.search(r"Etappe (\d+):", text)
    n = int(m.group(1))
    falsche_nr = text.replace(f"Etappe {n}:", f"Etappe {n + len(etappen)}:", 1)
    assert not w.werte_aus("D2", etappen, {"startdatum": falsche_nr}, HEUTE, neues_startdatum=neu).ok

    # fehlendes Datum
    ohne = re.sub(r": \d{2}\.\d{2}\.\d{4}$", ":", text, count=1, flags=re.M)
    assert not w.werte_aus("D2", etappen, {"startdatum": ohne}, HEUTE, neues_startdatum=neu).ok

    assert not w.werte_aus("D2", etappen, {"startdatum": None}, HEUTE, neues_startdatum=neu).ok


def test_antworttext_liest_html_briefing():
    """AC-7: das heute-Briefing kommt als HTML-Mail; der Text muss auswertbar sein."""
    w = _werkzeug()
    m = EmailMessage()
    m["From"] = "gregor-test@henemm.com"
    m["To"] = "gregor-test+t@henemm.com"
    m["Subject"] = "[T] Morgen"
    # Struktur wie src/output/renderers/email/html.py (Issue #890): Nummer und Titel in
    # getrennten Elementen ohne Leerraum dazwischen.
    m.set_content(
        '<html><body><table><tr><td><div class="eyebrow">MORGEN</div>'
        '<div style="font-size:11px;">Etappe 4 / 5</div>'
        '<div style="font-size:20px;"><b>Obstansersee-Hütte</b> nach Porzehütte</div>'
        '</td></tr></table></body></html>',
        subtype="html")
    text = w.antworttext(m.as_bytes())
    assert re.search(r"\bEtappe 4 / 5\b", text)
    assert "5Obstansersee" not in text, "Tag-Entfernung muss Element-Grenzen als Leerraum erhalten"
    assert "Obstansersee-Hütte nach Porzehütte" in text
    assert "<div" not in text and "<b>" not in text


# ---------------------------------------------------------------------------
# AC-9: Aufräumen und Geheimnisse
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("stelle,fehler", [
    ("lege_trip_an", RuntimeError("trip kaputt")),
    ("lege_trip_an", KeyboardInterrupt()),
    ("smtp", RuntimeError("smtp kaputt")),
    ("smtp", KeyboardInterrupt()),
])
def test_cleanup_laeuft_auch_bei_fehler(stelle, fehler):
    """AC-9: bei Fehler UND Abbruch (KeyboardInterrupt) wird der Wegwerf-Nutzer gelöscht."""
    w = _werkzeug()
    api = _ErsatzApi(fehler_bei=stelle if stelle != "smtp" else None, fehler=fehler)
    smtp = _smtp_klasse(fehler if stelle == "smtp" else None)
    imap = _ErsatzImap({})
    try:
        rc = w.fuehre_lauf(["A"], api=api, smtp_factory=smtp, imap_factory=lambda: imap,
                           heute=HEUTE, tag="tagcl", timeout=0, schlaf=_kein_schlaf)
    except (RuntimeError, KeyboardInterrupt):
        rc = None
    assert rc != 0
    assert "registriere" in api.schritte
    assert api.schritte[-1] == "loesche_nutzer", f"Schrittfolge: {api.schritte}"
    assert api.schritte.count("registriere") == 1, "genau EIN Wegwerf-Nutzer pro Lauf (Registrier-Limit)"


class _ErsatzSystem:
    """Spielt den Staging-Eingang nach: jede eingelieferte Befehlsmail erzeugt eine
    Antwort an die Absender-Plus-Adresse im gemeinsamen Postfach. Die heute-Antwort
    erscheint erst nach dem nächsten Warteschritt (wie das echte Briefing später)."""

    def __init__(self, api: "_ErsatzApi", heute_zahl_versatz: int = 0,
                 vorab: bool = False, heute_betreff: str | None = None,
                 heute_echtes_briefing: bool = False):
        self.api = api
        self.vorab = vorab
        self.heute_betreff = heute_betreff
        self.heute_echtes_briefing = heute_echtes_briefing
        self.imap = _ErsatzImap({1: _mail_bytes("gregor-test@henemm.com", "alt", "alt", "<alt@x>")})
        self.versatz = heute_zahl_versatz
        self.ausstehend: list[bytes] = []
        system = self

        class _Smtp(_ErsatzSmtp):
            verbindungen: list = []
            umschlaege: list = []
            fehler = None

            def sendmail(self, from_addr, to_addrs, msg, *a, **k):
                super().sendmail(from_addr, to_addrs, msg, *a, **k)
                system._antworte(from_addr, msg)
                return {}

        self.smtp = _Smtp

    def _ablegen(self, raw: bytes):
        self.imap.mails[max(self.imap.mails) + 1] = raw

    def _antworte(self, plus, msg):
        raw = msg if isinstance(msg, bytes) else (msg.encode() if isinstance(msg, str) else msg.as_bytes())
        betreff = email.message_from_bytes(raw)["Subject"] or ""
        trip = next(t for t in self.api.trips if betreff.startswith(f"[{t['name']}]"))
        etappen = trip["stages"]
        if self.vorab:
            self._vorlauf(plus, trip["name"])
        if betreff.rstrip().endswith("status"):
            self._ablegen(_mail_bytes(plus, f"[{trip['name']}] Status", _status_text(trip, HEUTE), "<s@x>"))
        elif betreff.rstrip().endswith("heute"):
            n = _chrono_nummer(etappen, OBST) + self.versatz
            text = f"Morgen-Briefing\nEtappe {n}: {OBST_REST}\n"
            betreff_h = self.heute_betreff or f"[{trip['name']}] Morgen"
            typ = None
            if self.heute_echtes_briefing:
                # Echtes Briefing: Betreff OHNE Trip-Praefix, Marker-Header gesetzt (siehe
                # test_echter_briefing_betreff_*, Quelle src/output/subject.py:175-183 + :96-116)
                betreff_h = f"Etappe {n}: {OBST_REST} {chr(8212)} Morgen"
                typ = "trip-briefing"
            raw_h = _mail_bytes(plus, betreff_h, text, "<h@x>", typ)
            if self.heute_betreff:  # GANZER Betreff in EINEM kodierten Wort (wie Go/mime.QEncoding)
                kodiert = email.header.Header(betreff_h, "utf-8").encode().replace("\n", "").encode()
                raw_h = re.sub(rb"Subject: [^\n]*(\n[ \t][^\n]*)*", b"Subject: " + kodiert, raw_h, count=1)
            self.ausstehend.append(raw_h)

    def _vorlauf(self, plus, trip_name):
        """Mails an dieselbe Adresse, die KEINE Antwort sind und VOR der echten Antwort liegen."""
        verif = (f"From: Gregor 20 <noreply@henemm.com>\nTo: {plus}\n"
                 "Subject: =?UTF-8?q?Best=C3=A4tige_deine_E-Mail-Adresse_f=C3=BCr_Gregor_20?=\n"
                 "Message-ID: <verif@x>\n\nBitte bestaetigen.\n").encode()
        self._ablegen(verif)
        self._ablegen(_mail_bytes(plus, "[Anderer-Trip] Status", "FALSCH anderer Trip", "<a1@x>"))
        self._ablegen(_mail_bytes(plus, f"Re: [{trip_name}] Status", "FALSCH nur enthalten", "<a2@x>"))

    def schlaf(self, _s):
        while self.ausstehend:
            self._ablegen(self.ausstehend.pop(0))


class _ErsatzApiMitTrips(_ErsatzApi):
    def __init__(self, **kw):
        super().__init__(**kw)
        self.trips: list[dict] = []

    def lege_trip_an(self, trip):
        super().lege_trip_an(trip)
        self.trips.append(trip)


@pytest.mark.parametrize("versatz,erwartet", [(0, 0), (1, 1)])
def test_lauf_szenario_a_bis_zur_auswertung(versatz, erwartet):
    """AC-4/AC-7 im Zusammenspiel: Antwort da (count=0) ⇒ Exit 0; falsche heute-Zahl ⇒ Exit 1.

    Die heute-Antwort erscheint erst NACH der status-Antwort. Ein Werkzeug, das die
    Lauf-UID nicht je Befehl neu bestimmt, wertet die status-Mail als heute-Antwort
    und meldet im Fall „falsche Zahl" fälschlich Exit 0.
    """
    w = _werkzeug()
    api = _ErsatzApiMitTrips()
    system = _ErsatzSystem(api, heute_zahl_versatz=versatz)
    rc = w.fuehre_lauf(["A"], api=api, smtp_factory=system.smtp, imap_factory=lambda: system.imap,
                       heute=HEUTE, tag="tagok", timeout=5, schlaf=system.schlaf)
    assert rc == erwartet
    assert len(system.smtp.umschlaege) == 2, "A braucht genau zwei Befehlsmails (status, heute)"
    assert api.schritte[-1] == "loesche_nutzer"
    assert 1 in system.imap.mails and 1 not in system.imap.gesehen | system.imap.geloescht, \
        "fremde Mail im geteilten Postfach angefasst"


def test_cleanup_ohne_antwort_und_gescheitertes_loeschen_wird_gemeldet(capsys):
    """AC-4 + AC-9: Lauf ohne Antwort ⇒ Exit ≠ 0; scheitert das Löschen ⇒ Nutzer-Kennung in der Ausgabe."""
    w = _werkzeug()
    api = _ErsatzApi(loeschen_scheitert=True)
    smtp = _smtp_klasse()
    rc = w.fuehre_lauf(["B"], api=api, smtp_factory=smtp, imap_factory=lambda: _ErsatzImap({}),
                       heute=HEUTE, tag="tagdel", timeout=0, schlaf=_kein_schlaf)
    assert rc != 0
    assert api.schritte[-1] == "loesche_nutzer"
    assert smtp.umschlaege, "die Befehlsmail wurde gar nicht eingeliefert"
    aus = capsys.readouterr()
    assert api.nutzer_id in aus.out + aus.err


HELFER_USER = "helfer-bestaetigt"
HELFER_PASS = "HELFER-PASSWORT-GEHEIM-31ab"


class _VertragsStaging:
    """Staging-Server mit dem ECHTEN Vertrag (kein Spiegel der eigenen Annahme).

    - register legt ein UNBESTAETIGTES Konto an und stellt keine Sitzung aus
    - login eines unbestaetigten Kontos -> 403 {"error":"email_not_verified"} (#2271)
    - staging-token verlangt eine Sitzung eines BESTAETIGTEN Kontos, sonst 401
    - verify-email ist oeffentlich und loest das Token ein
    - Trip-Anlage und Konto-Loeschung wirken auf die Sitzung, in der sie laufen
    Jede ``sitzung()`` ist ein eigener Cookie-Speicher; ``akteure`` haelt je Anfrage fest,
    unter welchem angemeldeten Nutzer sie lief.
    """

    TOKEN = "TOKEN-GEHEIM-c0ffee-9912"

    def __init__(self, status_je_pfad=None):
        self.anfragen: list[tuple] = []
        self.akteure: list[str | None] = []
        self.status_je_pfad = status_je_pfad or {}
        self.konten = {HELFER_USER: {"pw": HELFER_PASS, "verifiziert": True}}
        self.trips: list[tuple[str, str]] = []
        self.geloescht: list[str] = []

    def sitzung(self):
        cookie = {"nutzer": None}

        def transport(method, url, headers=None, body=None):
            pfad = url.split("//", 1)[1].split("/", 1)[1]
            self.anfragen.append((method, pfad, dict(headers or {}), body))
            self.akteure.append(cookie["nutzer"])
            for teil, status in self.status_je_pfad.items():
                if teil in url:
                    return status, {"error": "x"}
            return self._antwort(cookie, pfad, headers or {}, body or {}, method)

        return transport

    TRIP_KONTINGENT = 3  # Tarif "free": internal/model/tier.go:55, Zaehlregel internal/handler/quota.go:130ff

    def _antwort(self, cookie, pfad, headers, body, method="POST"):
        nutzer = cookie["nutzer"]
        if pfad == "api/auth/register":
            self.konten[body["username"]] = {"pw": body["password"], "verifiziert": False}
            return 201, {"id": "nutzer-fake-1"}
        if pfad == "api/auth/login":
            k = self.konten.get(body.get("username"))
            if k is None or k["pw"] != body.get("password"):
                return 401, {"error": "invalid_credentials"}
            if not k["verifiziert"]:
                return 403, {"error": "email_not_verified"}
            cookie["nutzer"] = body["username"]
            return 200, {"ok": True}
        if pfad == "api/auth/verify-email/staging-token":
            if nutzer is None or not self.konten[nutzer]["verifiziert"]:
                return 401, {"error": "unauthorized"}
            return 200, {"token": self.TOKEN}
        if pfad == "api/auth/verify-email":
            k = self.konten.get(body.get("user"))
            if k is None or body.get("token") != self.TOKEN:
                return 400, {"error": "invalid_token"}
            k["verifiziert"] = True
            return 200, {"ok": True}
        if pfad == "api/scheduler/inbound-commands":
            return 200, {"count": 0}
        if nutzer is None:
            return 401, {"error": "unauthorized"}
        if pfad == "api/trips" and method == "POST":
            if sum(1 for n, _ in self.trips if n == nutzer) >= self.TRIP_KONTINGENT:
                return 409, {"error": "quota_exceeded"}
            self.trips.append((nutzer, body.get("id")))
            return 201, {"id": body.get("id")}
        if pfad.startswith("api/trips/") and method == "DELETE":  # internal/router/router.go:242
            eintrag = (nutzer, pfad.rsplit("/", 1)[1])
            if eintrag not in self.trips:
                return 404, {"error": "not_found"}
            self.trips.remove(eintrag)
            return 204, {}
        if pfad == "api/auth/account/delete":
            if body.get("password") != self.konten[nutzer]["pw"]:
                return 403, {"error": "wrong_password"}
            self.geloescht.append(nutzer)
            del self.konten[nutzer]
            cookie["nutzer"] = None
            return 200, {"ok": True}
        return 200, {"ok": True}

    def gesendete_passwoerter(self) -> set[str]:
        werte = set()
        for _, _, _, body in self.anfragen:
            if isinstance(body, dict):
                for k, v in body.items():
                    if "pass" in k.lower() and isinstance(v, str) and v:
                        werte.add(v)
        return werte


def _api(tr, secret="geheim-x"):
    """StagingApi mit getrennten Sitzungen: Wegwerf-Nutzer und Helfer-Konto."""
    w = _werkzeug()
    return w.StagingApi("https://s.example.invalid", "http://127.0.0.1:8001", secret,
                        tr.sitzung(), helfer_transport=tr.sitzung(),
                        helfer_zugang=(HELFER_USER, HELFER_PASS))


@pytest.mark.parametrize("fehler_pfad", [None, "/api/trips"])
def test_ausgaben_enthalten_keine_geheimnisse(capsys, fehler_pfad):
    """AC-9: weder Passwort noch Token noch Core-Secret in irgendeiner Ausgabe."""
    w = _werkzeug()
    secret = "KERN-SECRET-PLATZHALTER-5b7d"
    transport = _VertragsStaging({fehler_pfad: 500} if fehler_pfad else None)
    api = _api(transport, secret)
    try:
        w.fuehre_lauf(["B"], api=api, smtp_factory=_smtp_klasse(),
                      imap_factory=lambda: _ErsatzImap({}), heute=HEUTE, tag="tagsec",
                      timeout=0, schlaf=_kein_schlaf)
    except RuntimeError as exc:
        print(f"Abbruch: {exc}")
    aus = capsys.readouterr()
    gesamt = aus.out + aus.err + repr(api)

    passwoerter = transport.gesendete_passwoerter()
    assert passwoerter, "Registrierung hat kein Passwort gesendet — Test wäre vakuum"
    assert HELFER_PASS in passwoerter, "Helfer-Login hat kein Passwort gesendet — Test wäre vakuum"
    if fehler_pfad is None:
        assert any(secret in h.values() for _, u, h, _ in transport.anfragen
                   if "api/scheduler/inbound-commands" in u), \
            "Poll-Auslösung ohne X-GZ-Core-Auth — Test wäre vakuum"
    for geheim in passwoerter | {secret, _VertragsStaging.TOKEN}:
        assert geheim not in gesamt, "Geheimnis in der Ausgabe"


# ---------------------------------------------------------------------------
# Fix-Runde nach Adversary (F008, F002, F003, F004, F006)
# ---------------------------------------------------------------------------

def test_antwortsuche_ueberspringt_systemmail_an_dieselbe_adresse():
    """F008: die Verifikationsmail der Registrierung geht an dieselbe Plus-Adresse und liegt VOR der Antwort."""
    w = _werkzeug()
    plus = "gregor-test+lauf43@henemm.com"
    imap = _ErsatzImap({
        6: _mail_bytes(plus, "Bestätige deine E-Mail-Adresse für Gregor 20", "Link", "<verif@x>"),
        7: _mail_bytes(plus, "[GZ-Pruefung lauf43 B] Status", "Status: richtig", "<antwort@x>"),
    })
    raw = w.finde_antwort(imap, plus, seit_uid=0, betreffe=("[GZ-Pruefung lauf43 B]", "[GZ#"))
    assert raw is not None
    assert email.message_from_bytes(raw)["Message-ID"] == "<antwort@x>"
    nur_system = _ErsatzImap({6: imap.mails[6]})
    assert w.finde_antwort(nur_system, plus, seit_uid=0, betreffe=("[GZ-Pruefung lauf43 B]",)) is None


def test_registrierkette_reihenfolge_und_inhalt():
    """F002/#2542: Helfer-Login -> register -> staging-token -> verify-email -> login -> trips -> poll -> delete."""
    w = _werkzeug()
    tr = _VertragsStaging()
    api = _api(tr)
    plus = "gregor-test+kette1@henemm.com"
    nutzer = api.registriere(plus)
    trip = w.baue_trip("B", "kette1", HEUTE)
    api.lege_trip_an(trip)
    api.loese_poll_aus()
    api.loesche_nutzer()
    pfade = [(m, p) for m, p, _, _ in tr.anfragen]
    assert pfade == [
        ("POST", "api/auth/login"),  # Helfer
        ("POST", "api/auth/register"), ("POST", "api/auth/verify-email/staging-token"),
        ("POST", "api/auth/verify-email"), ("POST", "api/auth/login"),
        ("POST", "api/trips"), ("POST", "api/scheduler/inbound-commands"),
        ("POST", "api/auth/account/delete"),
    ]
    helfer_login, reg, tokreq, ver, login, trips, poll, loesch = (a[3] for a in tr.anfragen)
    assert helfer_login == {"username": HELFER_USER, "password": HELFER_PASS}
    assert reg["email"] == plus and reg["username"] == nutzer and len(reg["password"]) >= 8
    assert reg["username"] != HELFER_USER
    assert login == {"username": nutzer, "password": reg["password"]}
    assert tokreq == {"username": nutzer}
    assert ver == {"user": nutzer, "token": _VertragsStaging.TOKEN}
    assert trips["id"] == trip["id"] and trips["name"] == trip["name"]
    assert loesch == {"password": reg["password"]}
    assert tr.anfragen[6][2].get("X-GZ-Core-Auth") == "geheim-x"


def test_wegwerf_nutzer_wird_nach_bestaetigung_angemeldet_und_helfer_bleibt_unberuehrt():
    """#2542: Login des neuen Nutzers erst NACH verify-email (sonst 403 email_not_verified);
    staging-token laeuft unter der Helfer-Sitzung; Trip und Loeschung unter dem Wegwerf-Nutzer."""
    w = _werkzeug()
    tr = _VertragsStaging()
    api = _api(tr)
    nutzer = api.registriere("gregor-test+sess1@henemm.com")
    api.lege_trip_an(w.baue_trip("B", "sess1", HEUTE))
    api.loesche_nutzer()
    nach_pfad = {}
    for (_, pfad, _, _), akteur in zip(tr.anfragen, tr.akteure):
        nach_pfad.setdefault(pfad, []).append(akteur)
    assert nach_pfad["api/auth/verify-email/staging-token"] == [HELFER_USER]
    assert tr.trips == [(nutzer, "gzp-sess1-b")]
    assert tr.geloescht == [nutzer]
    assert HELFER_USER in tr.konten, "Helfer-Konto darf nie geloescht werden"
    assert nutzer not in tr.konten


def test_fehlender_helfer_login_stoppt_vor_der_registrierung(capsys):
    """#2542: scheitert der Helfer-Login, wird NICHT registriert (kein verbrauchter Versuch, keine Konto-Leiche)."""
    w = _werkzeug()
    tr = _VertragsStaging({"/api/auth/login": 401})
    api = _api(tr)
    rc = w.fuehre_lauf_exit(["B"], api=api, smtp_factory=_smtp_klasse(),
                            imap_factory=lambda: _ErsatzImap({}), heute=HEUTE, tag="taghelf",
                            timeout=0, schlaf=_kein_schlaf)
    assert rc == 2
    pfade = [p for _, p, _, _ in tr.anfragen]
    assert "api/auth/register" not in pfade and "api/auth/account/delete" not in pfade
    assert HELFER_PASS not in capsys.readouterr().err


def test_http_fehler_nennt_das_error_feld_ohne_geheimnisse():
    """#2542: Meldung enthaelt das error-Feld der Antwort (z. B. email_not_verified), nie Passwoerter."""
    w = _werkzeug()

    def transport(methode, url, headers, body):
        return 403, {"error": "email_not_verified", "password": "NICHT-AUSGEBEN"}

    api = w.StagingApi("https://s.example.invalid", "http://127.0.0.1:8001", "geheim-x", transport)
    with pytest.raises(w.StagingFehler) as exc:
        api._rufe("POST", "https://s.example.invalid/api/auth/login", {"password": "x"})
    text = str(exc.value)
    assert "HTTP 403 (email_not_verified)" in text and "NICHT-AUSGEBEN" not in text


def test_http_fehler_bei_registrierung_ist_exit_2_ohne_wiederholung(capsys):
    """F002: 429 bei register -> klare Meldung, Exit 2, genau EIN Versuch, kein Loeschversuch."""
    w = _werkzeug()
    tr = _VertragsStaging({"/api/auth/register": 429})
    api = _api(tr)
    rc = w.fuehre_lauf_exit(["B"], api=api, smtp_factory=_smtp_klasse(),
                            imap_factory=lambda: _ErsatzImap({}), heute=HEUTE, tag="tag429",
                            timeout=0, schlaf=_kein_schlaf)
    assert rc == 2
    assert [p for _, p, _, _ in tr.anfragen].count("api/auth/register") == 1
    assert not any("account/delete" in p for _, p, _, _ in tr.anfragen)
    err = capsys.readouterr().err
    assert "429" in err and "register" in err and "geheim-x" not in err


def test_cleanup_loescht_nur_eigene_antworten():
    """F003: nur Mails mit To == Plus-Adresse werden geloescht, fremde und Namensverlaengerungen nicht."""
    w = _werkzeug()
    plus = "gregor-test+lauf44@henemm.com"
    imap = _postfach(plus)
    imap.mails[12] = _mail_bytes(plus, "[T] Status", "zweite eigene", "<e2@x>")
    w.loesche_eigene_antworten(imap, plus)
    assert 10 not in imap.mails and 12 not in imap.mails
    for fremd in (7, 8, 9, 11):
        assert fremd in imap.mails, f"fremde Mail {fremd} geloescht"


def test_imap_verbindungen_werden_geschlossen():
    """F004: jede je Poll geoeffnete IMAP-Verbindung wird mit logout beendet."""
    w = _werkzeug()
    geoeffnet = []

    class _Imap(_ErsatzImap):
        def __init__(self):
            super().__init__({})
            self.zu = False
            geoeffnet.append(self)

        def logout(self):
            self.zu = True
            return ("BYE", [b""])

    rc = w.fuehre_lauf(["B"], api=_ErsatzApi(), smtp_factory=_smtp_klasse(), imap_factory=_Imap,
                       heute=HEUTE, tag="tagimap", timeout=0, schlaf=_kein_schlaf)
    assert rc != 0 and geoeffnet
    assert all(i.zu for i in geoeffnet), "IMAP-Verbindung ohne logout liegen gelassen"


def test_ohne_cleanup_loescht_nichts_und_nennt_die_kennung(capsys):
    """F006: --ohne-cleanup (aufraeumen=False) ueberspringt das Loeschen und gibt die Kennung aus."""
    w = _werkzeug()
    api = _ErsatzApi()
    imap = _ErsatzImap({})
    w.fuehre_lauf(["B"], api=api, smtp_factory=_smtp_klasse(), imap_factory=lambda: imap,
                  heute=HEUTE, tag="tagoc", timeout=0, schlaf=_kein_schlaf, aufraeumen=False)
    assert "loesche_nutzer" not in api.schritte
    assert api.nutzer_id in capsys.readouterr().out


@pytest.mark.parametrize("heute_betreff", [None, "[GZ#ABCD] Morgen – Briefing"])
def test_lauf_nimmt_nur_echte_antworten_trotz_vorlauf_mails(heute_betreff):
    """F009: Verifikationsmail (RFC 2047), fremder Trip und 'enthaelt nur' liegen VOR der Antwort;
    die heute-Antwort mit Shortcode-Betreff (kodiert) zaehlt trotzdem. Im LAUF bewacht."""
    w = _werkzeug()
    api = _ErsatzApiMitTrips()
    system = _ErsatzSystem(api, vorab=True, heute_betreff=heute_betreff)
    rc = w.fuehre_lauf(["A"], api=api, smtp_factory=system.smtp, imap_factory=lambda: system.imap,
                       heute=HEUTE, tag="tagvor", timeout=5, schlaf=system.schlaf)
    assert rc == 0
    if heute_betreff:  # Fixture-Selbstkontrolle: der Betreff liegt wirklich RFC-2047-kodiert vor
        kodiert = email.header.Header(heute_betreff, "utf-8").encode()
        assert kodiert.startswith("=?") and "[GZ#" not in kodiert


def test_lauf_ohne_echte_antwort_nur_vorlauf_mails_ist_fehlschlag():
    """F009: liegen nur Systemmails/fremde Mails an der Adresse, ist das KEINE Antwort (Exit 1)."""
    w = _werkzeug()
    api = _ErsatzApiMitTrips()
    system = _ErsatzSystem(api, vorab=True)
    def nur_vorlauf(plus, msg):
        raw = msg if isinstance(msg, bytes) else msg.as_bytes()
        trip = next(t for t in api.trips if (email.message_from_bytes(raw)["Subject"] or "").startswith(f"[{t['name']}]"))
        system._vorlauf(plus, trip["name"])

    system._antworte = nur_vorlauf
    rc = w.fuehre_lauf(["B"], api=api, smtp_factory=system.smtp, imap_factory=lambda: system.imap,
                       heute=HEUTE, tag="tagnur", timeout=0, schlaf=system.schlaf)
    assert rc == 1


def test_lauf_raeumt_eigene_antworten_im_cleanup_weg():
    """F003b: der LAUF ruft das Antwort-Aufraeumen auf; fremde Mail im Postfach bleibt."""
    w = _werkzeug()
    api = _ErsatzApiMitTrips()
    system = _ErsatzSystem(api, vorab=True)
    plus = w.baue_plus_adresse("tagcln")
    rc = w.fuehre_lauf(["B"], api=api, smtp_factory=system.smtp, imap_factory=lambda: system.imap,
                       heute=HEUTE, tag="tagcln", timeout=5, schlaf=system.schlaf)
    assert rc == 0
    uebrig = [u for u, m in system.imap.mails.items()
              if plus in (email.message_from_bytes(m)["To"] or "")]
    assert uebrig == [], f"eigene Mails nicht aufgeraeumt: {uebrig}"
    assert 1 in system.imap.mails


@pytest.mark.parametrize("to_feld", [
    "gregor-test+lauf45@henemm.com, fremd@henemm.com",
    "fremd@henemm.com, gregor-test+lauf45@henemm.com",
])
def test_antwortsuche_lehnt_mehrfach_empfaenger_ab(to_feld):
    """F012: genau EIN Empfaenger gleich der Plus-Adresse; Mehrfach-To zaehlt nicht."""
    w = _werkzeug()
    plus = "gregor-test+lauf45@henemm.com"
    imap = _ErsatzImap({5: _mail_bytes(to_feld, "[T] Status", "Mehrfach", "<m@x>")})
    assert w.finde_antwort(imap, plus, seit_uid=0) is None


def _main_umgebung(monkeypatch, tmp_path, *, mit_zugang=True):
    w = _werkzeug()
    monkeypatch.setattr(w, "STAGING_ENV", tmp_path / "keine.env")
    for k in ("GZ_TEST_IMAP_USER", "GZ_TEST_IMAP_PASS", "GZ_CORE_SHARED_SECRET",
              "GZ_AUTH_USER", "GZ_AUTH_PASS"):
        if mit_zugang:
            monkeypatch.setenv(k, "platzhalter-" + k.lower())
        else:
            monkeypatch.delenv(k, raising=False)
    if mit_zugang:
        monkeypatch.setenv("GZ_AUTH_USER", HELFER_USER)
        monkeypatch.setenv("GZ_AUTH_PASS", HELFER_PASS)
    from datetime import datetime
    from zoneinfo import ZoneInfo
    return w, datetime(2027, 7, 14, 12, 0, tzinfo=ZoneInfo("Europe/Vienna"))


def test_main_fehlende_zugangsdaten_ist_exit_2_ohne_netz(monkeypatch, tmp_path, capsys):
    """F010: ohne Zugangsdaten Exit 2, nennt die Namen, kontaktiert nichts."""
    w, jetzt = _main_umgebung(monkeypatch, tmp_path, mit_zugang=False)
    tr = _VertragsStaging()
    smtp = _smtp_klasse()
    rc = w.main(["--szenario", "status"], transport=tr.sitzung(), helfer_transport=tr.sitzung(),
                smtp_factory=smtp, imap_factory=lambda: _ErsatzImap({}), jetzt=jetzt)
    assert rc == 2
    assert tr.anfragen == [] and smtp.verbindungen == []
    assert "GZ_TEST_IMAP_USER" in capsys.readouterr().err


@pytest.mark.parametrize("fehlt", ["GZ_AUTH_USER", "GZ_AUTH_PASS"])
def test_main_ohne_helfer_zugangsdaten_ist_exit_2_ohne_registrierung(monkeypatch, tmp_path, capsys, fehlt):
    """#2542: ohne GZ_AUTH_USER/PASS Exit 2 VOR jeder Registrierung (kein register-Aufruf, kein Netz)."""
    w, jetzt = _main_umgebung(monkeypatch, tmp_path)
    monkeypatch.delenv(fehlt)
    tr = _VertragsStaging()
    smtp = _smtp_klasse()
    rc = w.main(["--szenario", "status"], transport=tr.sitzung(), helfer_transport=tr.sitzung(),
                smtp_factory=smtp, imap_factory=lambda: _ErsatzImap({}), jetzt=jetzt)
    assert rc == 2
    assert tr.anfragen == [] and smtp.verbindungen == []
    err = capsys.readouterr().err
    assert fehlt in err and HELFER_PASS not in err


def test_main_reicht_ohne_cleanup_durch_und_wandelt_fehler_in_exit_2(monkeypatch, tmp_path, capsys):
    """F010: --ohne-cleanup erreicht den Lauf; HTTP-Fehler laufen ueber fuehre_lauf_exit (Exit 2)."""
    w, jetzt = _main_umgebung(monkeypatch, tmp_path)
    tr = _VertragsStaging()
    rc = w.main(["--szenario", "B", "--timeout", "0", "--ohne-cleanup"], transport=tr.sitzung(),
                helfer_transport=tr.sitzung(),
                smtp_factory=_smtp_klasse(), imap_factory=lambda: _ErsatzImap({}), jetzt=jetzt)
    assert rc == 1  # keine Antwort
    assert not any("account/delete" in p for _, p, _, _ in tr.anfragen)
    assert "--ohne-cleanup" in capsys.readouterr().out

    tr2 = _VertragsStaging({"/api/auth/register": 429})
    rc2 = w.main(["--szenario", "B", "--timeout", "0"], transport=tr2.sitzung(),
                 helfer_transport=tr2.sitzung(), smtp_factory=_smtp_klasse(), imap_factory=lambda: _ErsatzImap({}), jetzt=jetzt)
    assert rc2 == 2

    tr3 = _VertragsStaging()
    w.main(["--szenario", "B", "--timeout", "0"], transport=tr3.sitzung(),
           helfer_transport=tr3.sitzung(), smtp_factory=_smtp_klasse(), imap_factory=lambda: _ErsatzImap({}), jetzt=jetzt)
    assert any("account/delete" in p for _, p, _, _ in tr3.anfragen), "ohne Schalter muss geloescht werden"



# ---------------------------------------------------------------------------
# AC-10: Rezept in /e2e-verify
# ---------------------------------------------------------------------------

def test_rezept_in_e2e_verify_vorhanden():
    # doc-compliance-test
    """AC-10: Rezept „Befehl per echtem Mail-Eingang auf Staging" mit Pflicht-Stichworten."""
    text = E2E_VERIFY.read_text(encoding="utf-8")
    for stichwort in (
        "Befehl per echtem Mail-Eingang auf Staging",
        "staging_befehl_pruefen.py",
        "--szenario",
        "count",
        "Antwortmail",
        "Premium-SMS",
        "Telegram",
        "Handy-Nachtest",
    ):
        assert stichwort in text, f"Rezept-Stichwort fehlt in e2e-verify.md: {stichwort!r}"
    assert re.search(r"Exit[- ]?(Code)?\s*2", text), "Exit-Code-Bedeutung (2) fehlt"


# ---------------------------------------------------------------------------
# Live/Staging (nur /e2e-verify)
# ---------------------------------------------------------------------------

def _staging_bereit():
    try:
        return STAGING_ENV.is_file() and STAGING_ENV.read_text()
    except OSError:
        return False


@pytest.mark.live
@pytest.mark.staging
@pytest.mark.skipif(not _staging_bereit(), reason="Staging-Zugangsdaten nicht lesbar")
def test_gesamtlauf_status_auf_staging():
    """AC-1: status über Port 25 an den Staging-Eingang ⇒ Antwortmail an die Plus-Adresse."""
    w = _werkzeug()
    assert w.main(["--szenario", "status"]) == 0


@pytest.mark.live
@pytest.mark.staging
@pytest.mark.skipif(not _staging_bereit(), reason="Staging-Zugangsdaten nicht lesbar")
def test_gesamtlauf_alle_szenarien_auf_staging():
    """AC-8 (live) + AC-11: alle Szenarien gegen Staging ⇒ Exit 0."""
    w = _werkzeug()
    assert w.main(["--szenario", "alle"]) == 0


# ---------------------------------------------------------------------------
# Fix-Runde 2 (zweiter echter Lauf): Trip-Kontingent + echter Briefing-Betreff
# ---------------------------------------------------------------------------

def test_alle_szenarien_ueberschreiten_das_trip_kontingent_nicht():
    """Befund 1: Tarif free = max. 3 Trips. A,B,C,D,D2 duerfen nie gleichzeitig existieren.

    Rot gegen den Stand ohne Trip-Loeschen: 4. Trip -> 409 quota_exceeded -> StagingFehler.
    """
    w = _werkzeug()
    tr = _VertragsStaging()
    api = _api(tr)
    rc = w.fuehre_lauf(["A", "B", "C", "D", "D2"], api=api, smtp_factory=_smtp_klasse(),
                       imap_factory=lambda: _ErsatzImap({}), heute=HEUTE, tag="tagquota",
                       timeout=0, schlaf=_kein_schlaf)
    assert rc != 0  # keine Antworten -> Befund, aber KEIN Abbruch durch 409
    angelegt = [p for m, p, _, _ in tr.anfragen if p == "api/trips"]
    assert len(angelegt) == 5, "alle fuenf Szenarien muessen ihren Trip anlegen koennen"
    assert not [t for t in tr.trips if t[0].startswith("gzp-")], "Trips muessen nach Lauf weg sein"


def test_trip_wird_unter_der_sitzung_des_wegwerf_nutzers_geloescht():
    """Befund 1: DELETE /api/trips/{id} laeuft als Wegwerf-Nutzer (nicht Helfer), fremde Trips bleiben."""
    w = _werkzeug()
    tr = _VertragsStaging()
    tr.trips.append(("anderer-nutzer", "fremd"))
    api = _api(tr)
    w.fuehre_lauf(["B"], api=api, smtp_factory=_smtp_klasse(), imap_factory=lambda: _ErsatzImap({}),
                  heute=HEUTE, tag="tagdel2", timeout=0, schlaf=_kein_schlaf)
    loeschungen = [(a, p) for (m, p, _, _), a in zip(tr.anfragen, tr.akteure)
                   if m == "DELETE" and p.startswith("api/trips/")]
    assert len(loeschungen) == 1
    assert loeschungen[0][0].startswith("gzp-") and loeschungen[0][1].endswith("-b")
    assert ("anderer-nutzer", "fremd") in tr.trips


def test_echter_briefing_betreff_traegt_keinen_trip_praefix():
    """Befund 2: Quelle des Betreffs. Das Briefing nennt die Etappe als 'Etappe N: <Name>'
    (src/app/trip.py:311, aufgerufen trip_report_scheduler.py:1554). Mit Trip-Praefix waere der
    Betreff 78+ Zeichen; build_email_subject verwirft den Trip-Praefix dann
    (src/output/subject.py:175-183) -> Betreff beginnt NICHT mit '[<Trip>]'."""
    import sys
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
    from output.subject import build_email_subject
    from output.tokens.dto import TokenLine
    zeile = TokenLine(stage_name="Etappe 4: Obstansersee-Hütte nach Porzehütte", report_type="morning",
                      tokens=(), trip_name="GZ-Pruefung 090724-bd5f7394 A", shortcode=None)
    betreff = build_email_subject(zeile)
    assert betreff == "Etappe 4: Obstansersee-Hütte nach Porzehütte \u2014 Morgen"
    assert not betreff.startswith("[")


def test_antwortsuche_erkennt_briefing_ohne_trip_praefix_ueber_marker_header():
    """Befund 2: ECHTER Betreff (s.o.) + Header X-GZ-Mail-Type: trip-briefing (src/output/channels/email.py:344,
    notification_service.py:2166). Systemmail ohne Marker und Alarmmail mit anderem Typ zaehlen NICHT."""
    w = _werkzeug()
    plus = "gregor-test+lauf44@henemm.com"
    betreffe = ("[GZ-Pruefung lauf44 A]", "[GZ#")
    echt = "Etappe 4: Obstansersee-Hütte nach Porzehütte \u2014 Morgen"
    verif = _mail_bytes(plus, "Bestätige deine E-Mail-Adresse für Gregor 20", "Link", "<verif@x>")
    alarm = _mail_bytes(plus, "Etappe 4: Obstansersee-Hütte nach Porzehütte \u2014 Alarm", "x", "<al@x>", "deviation-alert")
    briefing = _mail_bytes(plus, echt, "Morgen-Briefing", "<b@x>", "trip-briefing")
    imap = _ErsatzImap({6: verif, 7: alarm, 8: briefing})
    raw = w.finde_antwort(imap, plus, seit_uid=0, betreffe=betreffe)
    assert raw is not None and email.message_from_bytes(raw)["Message-ID"] == "<b@x>"
    ohne = _ErsatzImap({6: verif, 7: alarm, 9: _mail_bytes(plus, echt, "t", "<c@x>")})
    assert w.finde_antwort(ohne, plus, seit_uid=0, betreffe=betreffe) is None


def test_lauf_erkennt_echte_heute_briefing_mail():
    """Befund 2 im LAUF (A: status + heute): die heute-Antwort ist ein echtes Briefing ohne Trip-Praefix."""
    w = _werkzeug()
    api = _ErsatzApiMitTrips()
    system = _ErsatzSystem(api, vorab=True, heute_echtes_briefing=True)
    rc = w.fuehre_lauf(["A"], api=api, smtp_factory=system.smtp, imap_factory=lambda: system.imap,
                       heute=HEUTE, tag="tagbrief", timeout=5, schlaf=system.schlaf)
    assert rc == 0
