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
"""
from __future__ import annotations

import email
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


def _mail_bytes(to: str, betreff: str, text: str, msgid: str) -> bytes:
    m = EmailMessage()
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
                if "HEADER" in teil:
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

    heute_lang = f"Morgen-Briefing\nEtappe {n}: {OBST_REST}\n08:00 12°C"
    heute_kurz = f"E{n} {OBST_REST[:10]} T12"
    assert w.werte_aus("A", etappen, {"status": status, "heute": heute_lang}, HEUTE).ok
    assert w.werte_aus("A", etappen, {"status": status, "heute": heute_kurz}, HEUTE).ok

    # heute nennt die Zahl aus dem Namen (2) statt der Position
    falsch_heute = f"Morgen-Briefing\nEtappe 2: {OBST_REST}\n"
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
    m.set_content("<html><body><h2>Etappe 4: <b>Obstansersee-Hütte</b> nach Porzehütte</h2></body></html>",
                  subtype="html")
    text = w.antworttext(m.as_bytes())
    assert "Etappe 4:" in text
    assert "<h2>" not in text and "<b>" not in text


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


class _ErsatzTransport:
    """HTTP-Rand der StagingApi: antwortet generisch und hält Anfragen fest."""

    TOKEN = "TOKEN-GEHEIM-c0ffee-9912"

    def __init__(self, fehler_pfad: str | None = None):
        self.anfragen: list[tuple] = []
        self.fehler_pfad = fehler_pfad

    def __call__(self, method, url, headers=None, body=None):
        self.anfragen.append((method, url, dict(headers or {}), body))
        if self.fehler_pfad and self.fehler_pfad in url:
            return 500, {"error": "internal"}
        return 200, {"id": "nutzer-fake-1", "user_id": "nutzer-fake-1", "token": self.TOKEN,
                     "count": 0, "ok": True}

    def gesendete_passwoerter(self) -> set[str]:
        werte = set()
        for _, _, _, body in self.anfragen:
            if isinstance(body, dict):
                for k, v in body.items():
                    if "pass" in k.lower() and isinstance(v, str) and v:
                        werte.add(v)
        return werte


@pytest.mark.parametrize("fehler_pfad", [None, "/api/trips"])
def test_ausgaben_enthalten_keine_geheimnisse(capsys, fehler_pfad):
    """AC-9: weder Passwort noch Token noch Core-Secret in irgendeiner Ausgabe."""
    w = _werkzeug()
    secret = "KERN-SECRET-PLATZHALTER-5b7d"
    transport = _ErsatzTransport(fehler_pfad)
    api = w.StagingApi("https://staging.example.invalid", "http://127.0.0.1:8001", secret, transport)
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
    if fehler_pfad is None:
        assert any(secret in h.values() for _, u, h, _ in transport.anfragen
                   if "/api/scheduler/inbound-commands" in u), \
            "Poll-Auslösung ohne X-GZ-Core-Auth — Test wäre vakuum"
    for geheim in passwoerter | {secret, _ErsatzTransport.TOKEN}:
        assert geheim not in gesamt, "Geheimnis in der Ausgabe"


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
