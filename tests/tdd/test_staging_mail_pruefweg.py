"""Staging-Mailweg für die Mail-Verifikation in /e2e-verify (#2774).

Spec: docs/specs/modules/fix_2774_staging_mailweg.md

Prüfling: ``.claude/tools/staging_mail_pruefen.py`` — aufgelöst RELATIV zu dieser
Testdatei, per ``importlib`` geladen. Fehlt das Werkzeug, schlägt jeder Test
einzeln fehl (kein Sammel-ERROR).

Schnittstellen-Vertrag, den diese Tests festschreiben
------------------------------------------------------
Reine Funktionen (kein Netz):
    baue_mail_tag() -> str                  eindeutig je Aufruf, nur [a-z0-9-]
    baue_plus_adresse(tag)                  "gregor-test+<tag>@henemm.com"
    baue_trip_name(tag) -> str              enthält den Tag
    baue_orte(tag) -> list[dict]            genau 3 Orte {"id","name","lat","lon"}, Namen mit Tag
    baue_preset(tag, location_ids) -> dict  Mindestfelder: name (mit Tag), schedule="manual",
                                            profil, forecast_hours in {24,48,72},
                                            hour_from/hour_to (0..23, to >= from), location_ids
    waehle_validator(pfad) -> (dateiname, mail_type)
                                            "trip"    -> ("briefing_mail_validator.py", "trip-briefing")
                                            "compare" -> ("email_spec_validator.py", "compare")
    baue_validator_aufruf(pfad, betreff) -> list[str]   argv-Liste mit Skript, --mail-type,
                                            --subject-contains <betreff>
    bestimme_exit(ausgaenge) -> int         ausgaenge = Liste von (art, wert):
                                            ("validator", exitcode) | ("versand_abgelehnt", None)
                                            | ("core_401", None) | ("zugangsdaten_fehlen", None)
                                            | ("registrierung_abgelehnt", None)
                                            0 nur bei lauter ("validator", 0); Mail-/Versand-/
                                            Validatorbefund = 1; Umgebungsfehler = 2;
                                            bei Mischung gewinnt der höhere Code.
    EINZELVERSAND_TIMEOUT_S >= 300

Netzrand (injizierbar, echte lokale Ersatzimplementierungen, kein Mock/patch):
    MailApi(basis_url, kern_url, kern_secret, transport, *, helfer_transport, helfer_zugang)
        erbt StagingApi aus staging_befehl_pruefen.py (registriere, lege_trip_an, loesche_trip,
        loesche_nutzer) und ergänzt: lege_ort_an(ort), lege_preset_an(preset) -> preset_id,
        loesche_ort(id), loesche_preset(id), sende_einzelversand(pfad, objekt_id, report_type)
        -> dict. Einzelversand geht an den KERN mit Header X-GZ-Core-Auth und Query user_id.
    fuehre_lauf(pfade, *, api, validator_runner, tag, report_type="morning") -> int
        pfade ⊂ {"trip","compare"}; validator_runner(argv) -> Exit-Code. Aufräumen im finally
        in der Reihenfolge Preset, Orte, Trip, Nutzer; scheitert es, wird die Kennung ausgegeben
        und der Exit ist != 0. HTTP 401 vom Kern und Registrierungsfehler -> 2,
        sonstiger Versandfehler -> 1.
    main(argv, *, transport=None, helfer_transport=None, validator_runner=None) -> int

Erweiterung #2830 (englischer Pfad, ``--lang en``)
--------------------------------------------------
    baue_validator_aufruf(pfad, betreff, lang="de")   lang="en" haengt ``--lang en --to-contains +en@``
                                            an; Default ohne beides (de-Aufruf unveraendert).
    EnMailApi(MailApi)                      ohne Helfer-Konto konstruierbar;
        melde_an(user, passwort)            Login (POST /api/auth/login), keine Registrierung;
                                            setzt ``nutzer_id`` = Anmeldename (die echte Kennung)
        loesche_nutzer()                    strukturell No-op: nie ein Transportaufruf
    fuehre_lauf(..., lang="de", en_zugang=None)
        lang="en": ``en_zugang=(user, passwort)`` -> ``api.melde_an`` statt ``registriere``;
        nur eigene (Tag-)Objekte loeschen, den Nutzer nie. (``en_zugang`` ist die einzige
        Signatur-Ergaenzung ueber die Spec hinaus: fuehre_lauf muss die Zugangsdaten kennen.)
    main(["--typ", ..., "--lang", "de"|"en"]) Default de; en liest GZ_E2E_EN_USER/GZ_E2E_EN_PASS,
        fehlt eines: Exit 2 ohne Netzzugriff; Helfer-Konto (GZ_AUTH_*) wird nicht verlangt.
"""
from __future__ import annotations

import importlib.util
import json
import re
import secrets
import sys
import threading
import time
from email.message import EmailMessage
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WERKZEUG = REPO_ROOT / ".claude" / "tools" / "staging_mail_pruefen.py"
E2E_VERIFY = REPO_ROOT / ".claude" / "commands" / "e2e-verify.md"
MAIL_VALIDATORS = REPO_ROOT / "docs" / "reference" / "mail_validators.md"
PLAYBOOK = REPO_ROOT / "docs" / "reference" / "operations_playbook.md"
STAGING_ENV = Path("/home/hem/gregor_zwanzig_staging/.env")

CORE_SECRET = "KERN-GEHEIMNIS-xq7731"
HELFER_USER, HELFER_PASS = "helfer-konto", "HELFER-PASS-zz4410"
EN_UID, EN_PASS = "u-en0e2830", "EN-PASS-vv9981"   # fester Staging-Nutzer ``en`` (#2830)
RUNBOOK_EN = REPO_ROOT / "docs" / "runbooks" / "staging_e2e_nutzer_en.md"


def _werkzeug():
    if not WERKZEUG.exists():
        pytest.fail(f"Prüfwerkzeug fehlt: {WERKZEUG.relative_to(REPO_ROOT)}")
    name = "staging_mail_pruefen_unter_test"
    if name in sys.modules:
        return sys.modules[name]
    spec = importlib.util.spec_from_file_location(name, WERKZEUG)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


# ---------------------------------------------------------------------------
# Ersatz-Staging: kleiner HTTP-Server auf Loopback (Go-API und Kern in einem)
# ---------------------------------------------------------------------------

class _Staging:
    def __init__(self, ablehnen: dict | None = None, kern_antwort=None):
        self.ablehnen = ablehnen or {}          # Pfad-Teil -> HTTP-Status
        self.kern_antwort = kern_antwort        # (status, body) für Einzelversand
        self.users: dict[str, dict] = {}
        self.log: list[tuple] = []              # (user, methode, pfad)
        self.kern: list[dict] = []              # aufgezeichnete Kern-Aufrufe
        self.bodies: list[tuple] = []           # (methode, pfad, body) aller Go-API-Aufrufe
        self.feste_id: str | None = None        # Register vergibt diese id statt u-<hex>
        self.preset_ohne_id = False             # Preset-POST-Antwort ohne "id"
        self.kern_verzoegerung_s = 0.0          # Kern antwortet erst nach dieser Zeit
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _antwort(self, status, body, cookie=None):
                roh = json.dumps(body).encode()
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(roh)))
                if cookie:
                    self.send_header("Set-Cookie", f"sid={cookie}; Path=/")
                self.end_headers()
                self.wfile.write(roh)

            def _handle(self, methode):
                teile = urlsplit(self.path)
                pfad, query = teile.path, parse_qs(teile.query)
                laenge = int(self.headers.get("Content-Length") or 0)
                body = json.loads(self.rfile.read(laenge) or b"{}") if laenge else {}
                sid = ""
                for c in (self.headers.get("Cookie") or "").split(";"):
                    if c.strip().startswith("sid="):
                        sid = c.strip()[4:]
                outer.log.append((sid, methode, pfad))
                outer.bodies.append((methode, pfad, body))
                for teil, status in outer.ablehnen.items():
                    if teil in pfad:
                        return self._antwort(status, {"error": "abgelehnt"})
                if pfad.startswith("/api/scheduler/"):
                    return self._kern(methode, pfad, query)
                u = outer.users
                if pfad == "/api/auth/login":
                    if body.get("username") == HELFER_USER:
                        return self._antwort(200, {}, cookie="helfer") if body.get("password") == HELFER_PASS \
                            else self._antwort(401, {"error": "bad"})
                    n = u.get(body.get("username"))
                    if not n or n["pw"] != body.get("password"):
                        return self._antwort(401, {"error": "bad"})
                    if not n["verified"]:
                        return self._antwort(403, {"error": "email_not_verified"})
                    return self._antwort(200, {}, cookie=body["username"])
                if pfad == "/api/auth/register":
                    uid = outer.feste_id or "u-" + secrets.token_hex(4)
                    u[uid] = {"pw": body["password"], "email": body["email"], "verified": False,
                              "trips": {}, "locations": {}, "presets": {}, "token": secrets.token_hex(4)}
                    return self._antwort(201, {"id": uid})
                if pfad == "/api/auth/verify-email/staging-token":
                    if sid != "helfer":
                        return self._antwort(403, {"error": "forbidden"})
                    return self._antwort(200, {"token": u[body["username"]]["token"]})
                if pfad == "/api/auth/verify-email":
                    n = u.get(body.get("user"))
                    if not n or n["token"] != body.get("token"):
                        return self._antwort(400, {"error": "bad_token"})
                    n["verified"] = True
                    return self._antwort(200, {})
                n = u.get(sid)
                if n is None:
                    return self._antwort(401, {"error": "unauthorized"})
                if pfad == "/api/auth/account/delete":
                    del u[sid]
                    return self._antwort(200, {})
                for sammlung, praefix in (("trips", "/api/trips"), ("locations", "/api/locations"),
                                          ("presets", "/api/compare/presets")):
                    if methode == "POST" and pfad == praefix:
                        oid = body.get("id") or "p-" + secrets.token_hex(3)
                        n[sammlung][oid] = body
                        if sammlung == "presets" and outer.preset_ohne_id:
                            return self._antwort(201, {k: v for k, v in body.items() if k != "id"})
                        return self._antwort(201, {**body, "id": oid})
                    if methode == "DELETE" and pfad.startswith(praefix + "/"):
                        n[sammlung].pop(pfad.rsplit("/", 1)[1], None)
                        return self._antwort(204 if False else 200, {})
                return self._antwort(404, {"error": "not_found"})

            def _kern(self, methode, pfad, query):
                uid = (query.get("user_id") or [""])[0]
                eintrag = {"pfad": pfad, "user_id": uid, "query": query,
                           "auth": self.headers.get("X-GZ-Core-Auth")}
                outer.kern.append(eintrag)
                if outer.kern_verzoegerung_s:
                    time.sleep(outer.kern_verzoegerung_s)  # echter Versand dauert Minuten
                if eintrag["auth"] != CORE_SECRET:
                    return self._antwort(401, {"error": "unauthorized"})
                if outer.kern_antwort:
                    s, b = outer.kern_antwort
                    return self._antwort(s, b)
                n = outer.users.get(uid)
                oid = pfad.split("/")[-2]
                if n is None or (oid not in n["trips"] and oid not in n["presets"]):
                    return self._antwort(404, {"error": "not_found"})
                return self._antwort(200, {"status": "ok", "sent": True, "id": oid})

            do_GET = lambda s: s._handle("GET")       # noqa: E731
            do_POST = lambda s: s._handle("POST")     # noqa: E731
            do_DELETE = lambda s: s._handle("DELETE")  # noqa: E731

        self._srv = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self._srv.server_address[1]}"
        threading.Thread(target=self._srv.serve_forever, daemon=True).start()

    def schliessen(self):
        self._srv.shutdown()
        self._srv.server_close()

    def api(self, w, secret=CORE_SECRET, **kw):
        return w.MailApi(self.url, self.url, secret, w.pw.http_transport(),
                         helfer_transport=w.pw.http_transport(), helfer_zugang=(HELFER_USER, HELFER_PASS),
                         **kw)

    def seed_en(self, uid=EN_UID, passwort=EN_PASS) -> str:
        """Der feste, bestaetigte Nutzer ``en`` existiert schon (scripts/staging_e2e_user_en.py)."""
        self.users[uid] = {"pw": passwort, "email": "gregor-test+en@henemm.com", "verified": True,
                           "trips": {}, "locations": {}, "presets": {}, "token": "x"}
        return uid

    def en_api(self, w, secret=CORE_SECRET, **kw):
        return w.EnMailApi(self.url, self.url, secret, w.pw.http_transport(), **kw)

    def konto_loeschungen(self) -> list[tuple]:
        return [e for e in self.log if e[2].endswith("/account/delete")]

    def trip_bodies(self) -> list[dict]:
        return [b for m, p, b in self.bodies if m == "POST" and p == "/api/trips"]


@pytest.fixture
def staging():
    s = _Staging()
    yield s
    s.schliessen()


class _Runner:
    """Ersatz für den Validator-Unterprozess: zeichnet argv auf, liefert vorgegebene Exit-Codes."""

    def __init__(self, exits=None):
        self.aufrufe: list[list[str]] = []
        self.exits = exits or {}

    def __call__(self, argv):
        self.aufrufe.append(list(argv))
        for name, code in self.exits.items():
            if any(name in a for a in argv):
                return code
        return 0


# ---------------------------------------------------------------------------
# AC-3: reine Funktionen
# ---------------------------------------------------------------------------

def test_betreff_tag_und_plus_adresse_werden_gebaut():
    w = _werkzeug()
    tag = w.baue_mail_tag()
    assert re.fullmatch(r"[a-z0-9-]+", tag)
    assert w.baue_plus_adresse(tag) == f"gregor-test+{tag}@henemm.com"
    assert tag in w.baue_trip_name(tag)
    orte = w.baue_orte(tag)
    assert len(orte) == 3 and all(tag in o["name"] for o in orte)
    assert len({o["id"] for o in orte}) == 3


def test_tags_sind_je_lauf_eindeutig():
    w = _werkzeug()
    assert len({w.baue_mail_tag() for _ in range(200)}) == 200


def test_validator_wahl_und_argumente_je_pfad():
    w = _werkzeug()
    assert w.waehle_validator("trip") == ("briefing_mail_validator.py", "trip-briefing")
    assert w.waehle_validator("compare") == ("email_spec_validator.py", "compare")
    for pfad, skript, typ in (("trip", "briefing_mail_validator.py", "trip-briefing"),
                              ("compare", "email_spec_validator.py", "compare")):
        argv = w.baue_validator_aufruf(pfad, "GZ-Mailpruefung 04-abc")
        assert any(a.endswith(skript) for a in argv)
        assert argv[argv.index("--mail-type") + 1] == typ
        assert argv[argv.index("--subject-contains") + 1] == "GZ-Mailpruefung 04-abc"
    with pytest.raises((ValueError, KeyError)):
        w.waehle_validator("radar")


# ---------------------------------------------------------------------------
# AC-5: Preset
# ---------------------------------------------------------------------------

def test_preset_enthaelt_mindestfelder_und_tag():
    w = _werkzeug()
    tag = w.baue_mail_tag()
    ids = [o["id"] for o in w.baue_orte(tag)]
    p = w.baue_preset(tag, ids)
    assert p["name"] and tag in p["name"]
    assert p["schedule"] == "manual"
    assert p["profil"]
    assert p["forecast_hours"] in (24, 48, 72)
    assert 0 <= p["hour_from"] <= p["hour_to"] <= 23
    assert p["location_ids"] == ids and len(p["location_ids"]) >= 3


# ---------------------------------------------------------------------------
# AC-7: Exit-Code-Ableitung
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ausgaenge,erwartet", [
    ([("validator", 0)], 0),
    ([("validator", 0), ("validator", 0)], 0),
    ([("validator", 1)], 1),
    ([("validator", 0), ("validator", 1)], 1),
    ([("versand_abgelehnt", None)], 1),
    ([("versand_abgelehnt", None), ("validator", 0)], 1),
    ([("core_401", None)], 2),
    ([("zugangsdaten_fehlen", None)], 2),
    ([("registrierung_abgelehnt", None)], 2),
    ([("validator", 1), ("core_401", None)], 2),
    ([("validator", 2)], 2),
    ([("validator", 0), ("validator", 2)], 2),
    ([("aufraeumen_fehlgeschlagen", None), ("validator", 0)], 2),
    ([], 2),  # kein einziger Pfad gelaufen: nie 0 ohne bestandenen Validator
])
def test_exit_code_ableitung(ausgaenge, erwartet):
    assert _werkzeug().bestimme_exit(ausgaenge) == erwartet


def test_lauf_exit_je_ausgang_gegen_ersatz_staging(staging):
    w = _werkzeug()
    assert w.fuehre_lauf(["trip"], api=staging.api(w), validator_runner=_Runner(), tag="t1-aaaa") == 0
    assert w.fuehre_lauf(["trip"], api=staging.api(w), validator_runner=_Runner({"briefing": 1}),
                         tag="t2-aaaa") == 1
    staging.kern_antwort = (500, {"error": "send_failed"})
    r = _Runner()
    assert w.fuehre_lauf(["trip"], api=staging.api(w), validator_runner=r, tag="t3-aaaa") == 1
    assert r.aufrufe == [], "abgelehnter Versand darf keinen Validator auf eine ältere Mail loslassen"
    staging.kern_antwort = None
    assert w.fuehre_lauf(["trip"], api=staging.api(w, secret="falsch"), validator_runner=_Runner(),
                         tag="t4-aaaa") == 2
    staging.ablehnen = {"/api/auth/register": 429}
    assert w.fuehre_lauf(["trip"], api=staging.api(w), validator_runner=_Runner(), tag="t5-aaaa") == 2


# ---------------------------------------------------------------------------
# AC-4: Einzelversand mit Core-Auth und echter user_id
# ---------------------------------------------------------------------------

def test_einzelversand_sendet_core_auth_und_echte_user_id(staging):
    w = _werkzeug()
    assert w.EINZELVERSAND_TIMEOUT_S >= 300
    rc = w.fuehre_lauf(["trip", "compare"], api=staging.api(w), validator_runner=_Runner(),
                       tag="t6-bbbb", report_type="evening")
    assert rc == 0
    assert len(staging.kern) == 2
    trip_call, cmp_call = staging.kern
    assert re.fullmatch(r"/api/scheduler/trips/[^/]+/send", trip_call["pfad"])
    assert trip_call["query"]["report_type"] == ["evening"]
    assert re.fullmatch(r"/api/scheduler/compare-presets/[^/]+/send", cmp_call["pfad"])
    for c in staging.kern:
        assert c["auth"] == CORE_SECRET
        assert re.fullmatch(r"u-[0-9a-f]{8}", c["user_id"]) and c["user_id"] != "default"


def test_ausgaben_enthalten_keine_geheimnisse(staging, capsys):
    w = _werkzeug()
    w.fuehre_lauf(["trip"], api=staging.api(w), validator_runner=_Runner(), tag="t7-cccc")
    staging.ablehnen = {"/api/scheduler/": 500}
    w.fuehre_lauf(["trip"], api=staging.api(w), validator_runner=_Runner(), tag="t8-cccc")
    aus = capsys.readouterr()
    for geheim in (CORE_SECRET, HELFER_PASS):
        assert geheim not in aus.out and geheim not in aus.err
    assert CORE_SECRET not in repr(staging.api(w))


# ---------------------------------------------------------------------------
# AC-1/AC-2 (Kern-Anteil): Ablauf und Wegwerf-Nutzer gegen Ersatz-Staging
# ---------------------------------------------------------------------------

def test_lauf_legt_bestaetigten_nutzer_mit_plus_adresse_an_und_ruft_pfadrichtigen_validator(staging):
    w = _werkzeug()
    tag = "t9-dddd"
    r = _Runner()
    seen = {}
    api = staging.api(w)
    orig = api.sende_einzelversand

    def beobachte(*a, **k):  # echte Methode, nur Zustand der Welt beim Versand festhalten
        seen["users"] = {k2: dict(v) for k2, v in staging.users.items()}
        return orig(*a, **k)

    api.sende_einzelversand = beobachte
    assert w.fuehre_lauf(["trip", "compare"], api=api, validator_runner=r, tag=tag) == 0
    (n,) = seen["users"].values()
    assert n["email"] == f"gregor-test+{tag}@henemm.com" and n["verified"] is True
    trip_argv, cmp_argv = r.aufrufe
    assert any(a.endswith("briefing_mail_validator.py") for a in trip_argv)
    assert trip_argv[trip_argv.index("--subject-contains") + 1] == w.baue_trip_name(tag)
    assert any(a.endswith("email_spec_validator.py") for a in cmp_argv)
    assert tag in cmp_argv[cmp_argv.index("--subject-contains") + 1]


# ---------------------------------------------------------------------------
# AC-6: Aufräumen
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("stelle", ["/api/trips", "/api/scheduler/", "validator"])
def test_cleanup_laeuft_auch_bei_fehler(staging, stelle):
    w = _werkzeug()
    runner = _Runner({"validator": 1}) if stelle == "validator" else _Runner()
    if stelle != "validator":
        staging.ablehnen = {stelle: 500}
    rc = w.fuehre_lauf(["trip", "compare"], api=staging.api(w), validator_runner=runner, tag="t10-eeee")
    assert rc != 0
    assert staging.users == {}, "Nutzer samt Trip, Orten und Preset muss weg sein"


def test_cleanup_reihenfolge_und_befund_bei_fehlschlag(staging):
    w = _werkzeug()
    assert w.fuehre_lauf(["trip", "compare"], api=staging.api(w), validator_runner=_Runner(),
                         tag="t11-ffff") == 0
    loeschungen = [p for _, m, p in staging.log if m == "DELETE" or p.endswith("/account/delete")]
    arten = [("preset" if "/compare/presets/" in p else "ort" if "/locations/" in p
              else "trip" if "/trips/" in p else "nutzer") for p in loeschungen]
    assert arten == ["preset", "ort", "ort", "ort", "trip", "nutzer"]


def test_uebrig_gebliebener_nutzer_wird_mit_kennung_gemeldet(staging, capsys):
    w = _werkzeug()
    staging.ablehnen = {"/api/auth/account/delete": 500}
    rc = w.fuehre_lauf(["trip"], api=staging.api(w), validator_runner=_Runner(), tag="t13-gggg")
    aus = capsys.readouterr()
    (uebrig,) = staging.users
    assert rc != 0 and uebrig in aus.out + aus.err


# ---------------------------------------------------------------------------
# AC-11: Mehr-Nutzer-Isolation
# ---------------------------------------------------------------------------

def test_zwei_laeufe_nutzen_getrennte_nutzer_und_loeschen_nur_eigenes(staging):
    w = _werkzeug()
    fremd = staging.api(w)
    fremd_id = fremd.registriere(w.baue_plus_adresse("fremd-0001"))
    fremd.lege_trip_an({"id": "fremd-trip", "name": "Fremder Trip", "stages": []})
    assert w.fuehre_lauf(["trip"], api=staging.api(w), validator_runner=_Runner(), tag="a1-aaaa") == 0
    assert w.fuehre_lauf(["trip"], api=staging.api(w), validator_runner=_Runner(), tag="a2-bbbb") == 0
    assert list(staging.users) == [fremd_id]
    assert "fremd-trip" in staging.users[fremd_id]["trips"]
    kern_ids = {c["user_id"] for c in staging.kern}
    assert len(kern_ids) == 2 and fremd_id not in kern_ids and "default" not in kern_ids
    for sid, methode, pfad in staging.log:
        if methode == "DELETE":
            assert sid != fremd_id and "fremd-trip" not in pfad


# ---------------------------------------------------------------------------
# main(): Umgebung
# ---------------------------------------------------------------------------

def _env(monkeypatch, tmp_path, w, *, mit_zugang=True):
    monkeypatch.setattr(w.pw, "STAGING_ENV", tmp_path / "keine.env")
    for k in ("GZ_CORE_SHARED_SECRET", "GZ_AUTH_USER", "GZ_AUTH_PASS"):
        monkeypatch.delenv(k, raising=False)
    if mit_zugang:
        monkeypatch.setenv("GZ_CORE_SHARED_SECRET", CORE_SECRET)
        monkeypatch.setenv("GZ_AUTH_USER", HELFER_USER)
        monkeypatch.setenv("GZ_AUTH_PASS", HELFER_PASS)


def test_main_ohne_zugangsdaten_ist_exit_2_ohne_netz(monkeypatch, tmp_path, capsys, staging):
    w = _werkzeug()
    _env(monkeypatch, tmp_path, w, mit_zugang=False)
    monkeypatch.setenv("GZ_STAGING_BASE_URL", staging.url)
    assert w.main(["--typ", "trip"], validator_runner=_Runner()) == 2
    assert staging.log == []
    assert "GZ_CORE_SHARED_SECRET" in capsys.readouterr().err


def test_main_trip_gegen_ersatz_staging_ist_exit_0_und_raeumt_auf(monkeypatch, tmp_path, staging):
    w = _werkzeug()
    _env(monkeypatch, tmp_path, w)
    monkeypatch.setenv("GZ_STAGING_BASE_URL", staging.url)
    monkeypatch.setenv("GZ_STAGING_CORE_URL", staging.url)
    assert w.main(["--typ", "trip"], validator_runner=_Runner()) == 0
    assert staging.users == {}


def _main_env(monkeypatch, tmp_path, w, staging):
    _env(monkeypatch, tmp_path, w)
    monkeypatch.setenv("GZ_STAGING_BASE_URL", staging.url)
    monkeypatch.setenv("GZ_STAGING_CORE_URL", staging.url)


def test_main_beide_faehrt_trip_und_compare(monkeypatch, tmp_path, staging):
    w = _werkzeug()
    _main_env(monkeypatch, tmp_path, w, staging)
    r = _Runner()
    assert w.main(["--typ", "beide"], validator_runner=r) == 0
    assert [c["pfad"].split("/")[3] for c in staging.kern] == ["trips", "compare-presets"]
    assert len(r.aufrufe) == 2
    assert any(a.endswith("briefing_mail_validator.py") for a in r.aufrufe[0])
    assert any(a.endswith("email_spec_validator.py") for a in r.aufrufe[1])
    assert staging.users == {}


# ---------------------------------------------------------------------------
# F001: Kern meldet 200, aber nichts versendet -> kein Validator auf alte Mail
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("pfad", ["trip", "compare"])
@pytest.mark.parametrize("antwort", [{"status": "skipped", "sent": False}, {"status": "ok"}])
def test_kern_200_ohne_versand_ist_exit_1_ohne_validator(staging, pfad, antwort):
    w = _werkzeug()
    staging.kern_antwort = (200, antwort)
    r = _Runner()
    assert w.fuehre_lauf([pfad], api=staging.api(w), validator_runner=r, tag="f1-aaaa") == 1
    assert r.aufrufe == [], "nicht versendete Mail darf keinen Validator auf eine ältere Mail loslassen"
    assert len(staging.kern) == 1
    assert staging.users == {}


# ---------------------------------------------------------------------------
# F002: 401-Pfad verrät kein Geheimnis
# ---------------------------------------------------------------------------

def test_401_pfad_verraet_weder_echtes_noch_falsches_secret(staging, capsys):
    w = _werkzeug()
    falsch = "FALSCH-GEHEIM-k93x"
    for pfad in ("trip", "compare"):
        assert w.fuehre_lauf([pfad], api=staging.api(w, secret=falsch), validator_runner=_Runner(),
                             tag=f"f2-{pfad}") == 2
    assert [c["auth"] for c in staging.kern] == [falsch, falsch]
    aus = capsys.readouterr()
    assert "401" in aus.err
    for geheim in (CORE_SECRET, falsch, HELFER_PASS):
        assert geheim not in aus.out and geheim not in aus.err


# ---------------------------------------------------------------------------
# F003: echter Validator-Rand wartet auf die Mail im Postfach
# ---------------------------------------------------------------------------

class _Postfach:
    """imaplib-artiges Postfach: UID SEARCH ALL und UID FETCH der Kopffelder (PEEK)."""

    def __init__(self):
        self.mails: dict[int, bytes] = {}
        self.verbindungen = 0
        self.abgemeldet = 0

    def lege_ab(self, betreff: str, mail_type: str | None):
        m = EmailMessage()
        m["From"], m["To"] = "gregor_zwanzig@henemm.com", "gregor-test+x@henemm.com"
        m["Subject"] = betreff
        if mail_type:
            m["X-GZ-Mail-Type"] = mail_type
        m.set_content("Inhalt")
        self.mails[max(self.mails, default=0) + 1] = m.as_bytes()

    def fabrik(self):
        self.verbindungen += 1
        return self

    def logout(self):
        self.abgemeldet += 1
        return ("BYE", [b""])

    def uid(self, befehl, *args):
        befehl = befehl.upper()
        if befehl == "SEARCH":
            return ("OK", [" ".join(str(u) for u in sorted(self.mails)).encode()])
        if befehl == "FETCH":
            uid = int(args[0])
            assert "PEEK" in args[1], "Wartepunkt darf Mails nicht als gelesen markieren"
            felder = re.search(r"FIELDS \(([^)]*)\)", args[1]).group(1).lower().split()
            kopf = self.mails[uid].split(b"\n\n", 1)[0].split(b"\n")
            auswahl = b"\r\n".join(z for z in kopf if z.split(b":", 1)[0].decode().lower() in felder)
            return ("OK", [(f"{uid} (BODY[HEADER.FIELDS] {{{len(auswahl)}}}".encode(), auswahl + b"\r\n\r\n"),
                           b")"])
        raise AssertionError(f"unerwarteter IMAP-Befehl {befehl}")


def _validator_attrappe(marker: Path, betreff: str, mail_type: str) -> list[str]:
    """Echter Unterprozess statt Validator: hinterlässt eine Spur und endet mit Exit 3."""
    code = "import pathlib, sys; pathlib.Path(sys.argv[1]).write_text('lief'); sys.exit(3)"
    return [sys.executable, "-c", code, str(marker), "--mail-type", mail_type, "--subject-contains", betreff]


def test_validator_startet_erst_wenn_passende_mail_im_postfach_liegt(tmp_path):
    w = _werkzeug()
    box = _Postfach()
    box.lege_ab("[GZM t-imap] Morgen", "compare")           # richtiger Tag, falscher Mail-Typ
    box.lege_ab("[GZM t-anders] Morgen", "trip-briefing")   # richtiger Typ, fremder Tag
    box.lege_ab("[GZM t-imap] Morgen", None)                # ohne Marker-Header
    schlaefe = []

    def schlaf(s):
        assert not (tmp_path / "spur").exists(), "Validator lief, bevor die Mail da war"
        schlaefe.append(s)
        if len(schlaefe) == 2:
            box.lege_ab("Gregor [GZM t-imap] Morgen-Briefing", "trip-briefing")

    runner = w.echter_validator_runner({}, timeout=600, schlaf=schlaf, imap_factory=box.fabrik)
    rc = runner(_validator_attrappe(tmp_path / "spur", "GZM t-imap", "trip-briefing"))
    assert rc == 3, "Exit des Validators wird unverändert durchgereicht"
    assert (tmp_path / "spur").read_text() == "lief"
    assert len(schlaefe) == 2 and box.verbindungen == 3 == box.abgemeldet


def test_validator_startet_nicht_wenn_mail_bis_timeout_ausbleibt(tmp_path, capsys):
    w = _werkzeug()
    box = _Postfach()
    box.lege_ab("[GZM t-imap] Morgen", "compare")
    schlaefe = []
    runner = w.echter_validator_runner({}, timeout=30, schlaf=schlaefe.append, imap_factory=box.fabrik)
    rc = runner(_validator_attrappe(tmp_path / "spur", "GZM t-imap", "trip-briefing"))
    assert rc != 0
    assert not (tmp_path / "spur").exists(), "ohne zugestellte Mail darf kein Validator laufen"
    assert sum(schlaefe) == 30, "Gesamtwartezeit entspricht genau dem Timeout, nicht laenger"
    assert box.verbindungen == len(schlaefe) + 1
    assert "GZM t-imap" in capsys.readouterr().err


def _postfach_mit_zielmail_und_nachfolgern(anzahl_danach: int) -> _Postfach:
    box = _Postfach()
    box.lege_ab("Gregor [GZM t-fenster] Morgen-Briefing", "trip-briefing")
    for i in range(anzahl_danach):
        box.lege_ab(f"[GZM fremd-{i}] Abend", "compare")
    return box


def test_zielmail_innerhalb_der_letzten_40_wird_gefunden(tmp_path):
    w = _werkzeug()
    box = _postfach_mit_zielmail_und_nachfolgern(39)   # Zielmail ist die 40.-juengste
    schlaefe = []
    runner = w.echter_validator_runner({}, timeout=0, schlaf=schlaefe.append, imap_factory=box.fabrik)
    rc = runner(_validator_attrappe(tmp_path / "spur", "GZM t-fenster", "trip-briefing"))
    assert rc == 3 and (tmp_path / "spur").read_text() == "lief"
    assert schlaefe == []


def test_zielmail_ausserhalb_der_letzten_40_wird_nicht_gefunden(tmp_path):
    w = _werkzeug()
    box = _postfach_mit_zielmail_und_nachfolgern(40)   # Zielmail ist die 41.-juengste
    runner = w.echter_validator_runner({}, timeout=0, schlaf=lambda s: None, imap_factory=box.fabrik)
    rc = runner(_validator_attrappe(tmp_path / "spur", "GZM t-fenster", "trip-briefing"))
    assert rc == 1
    assert not (tmp_path / "spur").exists(), "nur das Fenster der letzten 40 Mails zaehlt"


# ---------------------------------------------------------------------------
# F004: Randfälle Exit, Aufräumen, Isolation, Preset, Zeitlimit
# ---------------------------------------------------------------------------

def test_validator_exit_2_wird_als_2_durchgereicht(staging):
    w = _werkzeug()
    assert w.fuehre_lauf(["trip"], api=staging.api(w), validator_runner=_Runner({"briefing": 2}),
                         tag="f4-aaaa") == 2
    assert w.fuehre_lauf(["trip", "compare"], api=staging.api(w),
                         validator_runner=_Runner({"email_spec": 2}), tag="f4-bbbb") == 2


def test_uebrig_gebliebener_nutzer_steht_in_der_warnung(staging, capsys):
    w = _werkzeug()
    staging.ablehnen = {"/api/auth/account/delete": 500}
    assert w.fuehre_lauf(["trip"], api=staging.api(w), validator_runner=_Runner(), tag="f4-cccc") != 0
    (uebrig,) = staging.users
    warnungen = [z for z in capsys.readouterr().err.splitlines() if "nicht geloescht" in z]
    assert warnungen and all(uebrig in z for z in warnungen)


def test_reste_beim_geloeschten_nutzer_sind_ein_befund(staging, capsys):
    w = _werkzeug()
    staging.ablehnen = {"/api/trips/": 500, "/api/compare/presets/": 500}  # nur DELETE, POST bleibt heil
    rc = w.fuehre_lauf(["trip", "compare"], api=staging.api(w), validator_runner=_Runner(), tag="f4-dddd")
    assert rc == 2, "nicht gelöschte Objekte sind ein Aufräum-Fehlschlag"
    assert staging.users == {}, "der Nutzer wird trotzdem gelöscht"
    nutzer = {c["user_id"] for c in staging.kern}
    (kennung,) = nutzer
    err = capsys.readouterr().err
    assert any("Reste" in z and kennung in z for z in err.splitlines())


def test_einzelversand_an_nutzer_default_wird_verweigert(staging):
    w = _werkzeug()
    staging.feste_id = "default"
    r = _Runner()
    rc = w.fuehre_lauf(["trip", "compare"], api=staging.api(w), validator_runner=r, tag="f4-eeee")
    assert rc != 0
    assert staging.kern == [], "kein Kern-Aufruf mit user_id=default"
    assert r.aufrufe == []


def test_preset_antwort_ohne_id_ist_umgebungsfehler(staging):
    w = _werkzeug()
    staging.preset_ohne_id = True
    r = _Runner()
    assert w.fuehre_lauf(["compare"], api=staging.api(w), validator_runner=r, tag="f4-ffff") == 2
    assert staging.kern == [] and r.aufrufe == []


def test_kern_zeitlimit_hat_untergrenze_300_s_am_echten_aufruf(staging):
    w = _werkzeug()
    staging.kern_verzoegerung_s = 1.5
    api = staging.api(w, kern_timeout=1)  # zu kleines Limit muss auf >= 300 s angehoben werden
    assert w.fuehre_lauf(["trip"], api=api, validator_runner=_Runner(), tag="f4-gggg") == 0
    assert len(staging.kern) == 1


# ---------------------------------------------------------------------------
# F005: --format compact (nur lokal gegen Ersatz-Staging belegt, live nicht)
# ---------------------------------------------------------------------------

def _email_format(trip: dict) -> str:
    return (trip.get("report_config") or {}).get("email_format", "full")


def test_trip_format_full_standard_und_compact_auf_wunsch(staging):
    w = _werkzeug()
    assert w.fuehre_lauf(["trip"], api=staging.api(w), validator_runner=_Runner(), tag="f5-aaaa") == 0
    assert w.fuehre_lauf(["trip"], api=staging.api(w), validator_runner=_Runner(), tag="f5-bbbb",
                         email_format="compact") == 0
    assert [_email_format(t) for t in staging.trip_bodies()] == ["full", "compact"]


def test_main_reicht_format_compact_an_den_trip_durch(monkeypatch, tmp_path, staging):
    w = _werkzeug()
    _main_env(monkeypatch, tmp_path, w, staging)
    assert w.main(["--typ", "trip"], validator_runner=_Runner()) == 0
    assert w.main(["--typ", "trip", "--format", "compact"], validator_runner=_Runner()) == 0
    assert [_email_format(t) for t in staging.trip_bodies()] == ["full", "compact"]


# ---------------------------------------------------------------------------
# AC-9 / AC-10: Rezept und Grenze (doc-compliance-test)
# ---------------------------------------------------------------------------

def test_rezept_in_e2e_verify_und_referenz():
    # doc-compliance-test
    e2e = E2E_VERIFY.read_text(encoding="utf-8")
    ref = MAIL_VALIDATORS.read_text(encoding="utf-8")
    spiel = PLAYBOOK.read_text(encoding="utf-8")
    for stichwort in ("staging_mail_pruefen.py", "email_taken", "X-GZ-Core-Auth",
                      "gregor-test+", "--subject-contains", "briefing_mail_validator.py",
                      "email_spec_validator.py"):
        assert stichwort in e2e, f"Stichwort fehlt in e2e-verify.md: {stichwort!r}"
    assert re.search(r"Exit[- ]?(Code)?\s*2", e2e)
    assert "--subject-contains" in ref and "staging_mail_pruefen.py" in ref
    assert "staging_mail_pruefen.py" in spiel
    assert "Der Trip bekommt als einzigen Empfaenger die Test-Adresse `gregor-test@henemm.com`" not in e2e


def test_rezept_nennt_grenze_ohne_winddaten():
    # doc-compliance-test
    for pfad in (E2E_VERIFY, MAIL_VALIDATORS):
        text = pfad.read_text(encoding="utf-8")
        for stichwort in ("Winddaten", "lokal", "#1670"):
            assert stichwort in text, f"{stichwort!r} fehlt in {pfad.name}"


# ---------------------------------------------------------------------------
# #2830: englischer Pfad (--lang en) gegen das Ersatz-Staging
# ---------------------------------------------------------------------------

def _lauf_en(w, staging, pfade=("trip",), *, runner=None, tag="e1-aaaa", passwort=EN_PASS, secret=CORE_SECRET):
    return w.fuehre_lauf(list(pfade), api=staging.en_api(w, secret=secret), validator_runner=runner or _Runner(),
                         tag=tag, lang="en", en_zugang=(EN_UID, passwort))


def _eigene_loeschungen(staging):
    return [(s, p) for s, m, p in staging.log if m == "DELETE"]


# AC-12 -----------------------------------------------------------------------

def test_en_lauf_meldet_an_statt_zu_registrieren_und_legt_objekte_unter_nutzer_en_an(staging):
    w = _werkzeug()
    staging.seed_en()
    assert _lauf_en(w, staging, ("trip", "compare")) == 0
    pfade = [p for _, _, p in staging.log]
    assert "/api/auth/login" in pfade
    assert not any(p in ("/api/auth/register", "/api/auth/verify-email",
                         "/api/auth/verify-email/staging-token") for p in pfade), \
        "der feste Nutzer en wird angemeldet, nie registriert oder ueber das Helfer-Konto bestaetigt"
    anlegen = [s for s, m, p in staging.log if m == "POST" and p in
               ("/api/trips", "/api/locations", "/api/compare/presets")]
    assert len(anlegen) == 1 + 3 + 1 and set(anlegen) == {EN_UID}
    assert [c["user_id"] for c in staging.kern] == [EN_UID, EN_UID]
    assert all(c["auth"] == CORE_SECRET for c in staging.kern)


# AC-13 -----------------------------------------------------------------------

def test_validator_aufruf_traegt_lang_en_und_to_contains_nur_bei_en():
    w = _werkzeug()
    for pfad in ("trip", "compare"):
        de = w.baue_validator_aufruf(pfad, "GZM x-1")
        assert "--lang" not in de and "--to-contains" not in de
        assert w.baue_validator_aufruf(pfad, "GZM x-1", lang="de") == de
        en = w.baue_validator_aufruf(pfad, "GZM x-1", lang="en")
        assert en[en.index("--lang") + 1] == "en"
        assert en[en.index("--to-contains") + 1] == "+en@"
        assert en[:len(de)] == de, "Skript, --mail-type und --subject-contains bleiben unveraendert"
        assert en[en.index("--subject-contains") + 1] == "GZM x-1"
        assert len(en) == len(de) + 4


def test_en_lauf_reicht_lang_en_an_den_validator_durch(staging):
    w = _werkzeug()
    staging.seed_en()
    r = _Runner()
    assert _lauf_en(w, staging, ("trip", "compare"), runner=r, tag="e2-aaaa") == 0
    assert len(r.aufrufe) == 2
    for argv in r.aufrufe:
        assert argv[argv.index("--lang") + 1] == "en"
        assert argv[argv.index("--to-contains") + 1] == "+en@"
        assert "e2-aaaa" in argv[argv.index("--subject-contains") + 1]


# AC-14 -----------------------------------------------------------------------

@pytest.mark.parametrize("ausgang", ["erfolg", "versand_abgelehnt", "validator_befund", "aufraeumen_scheitert"])
def test_en_nutzer_wird_nie_geloescht_auch_nicht_bei_fehler(staging, ausgang):
    w = _werkzeug()
    staging.seed_en()
    runner = _Runner({"briefing": 1}) if ausgang == "validator_befund" else _Runner()
    if ausgang == "versand_abgelehnt":
        staging.ablehnen = {"/api/scheduler/": 500}
    if ausgang == "aufraeumen_scheitert":
        staging.ablehnen = {"/api/trips/": 500}
    rc = _lauf_en(w, staging, runner=runner, tag="e3-aaaa")
    assert (rc == 0) == (ausgang == "erfolg")
    assert staging.konto_loeschungen() == [], "account/delete darf im en-Pfad nie aufgerufen werden"
    assert EN_UID in staging.users


def test_en_lauf_loescht_nur_eigene_objekte_fremde_bleiben(staging):
    w = _werkzeug()
    staging.seed_en()
    n = staging.users[EN_UID]
    n["trips"]["fremd-trip"], n["locations"]["fremd-ort"], n["presets"]["fremd-preset"] = {}, {}, {}
    assert _lauf_en(w, staging, ("trip", "compare"), tag="e4-aaaa") == 0
    assert set(n["trips"]) == {"fremd-trip"} and set(n["locations"]) == {"fremd-ort"}
    assert set(n["presets"]) == {"fremd-preset"}
    loeschungen = _eigene_loeschungen(staging)
    assert loeschungen and not any("fremd" in p for _, p in loeschungen)
    assert {s for s, _ in loeschungen} == {EN_UID}


def test_en_aufraeumfehler_meldet_kennungen_und_exit_ungleich_0(staging, capsys):
    w = _werkzeug()
    staging.seed_en()
    staging.ablehnen = {"/api/trips/": 500, "/api/locations/": 500, "/api/compare/presets/": 500}
    assert _lauf_en(w, staging, ("trip", "compare"), tag="e5-aaaa") != 0
    n = staging.users[EN_UID]
    uebrig = list(n["trips"]) + list(n["locations"]) + list(n["presets"])
    assert len(uebrig) == 1 + 3 + 1
    aus = capsys.readouterr()
    for kennung in uebrig:
        assert kennung in aus.out + aus.err, f"uebrig gebliebene Kennung {kennung} nicht gemeldet"


def test_en_mail_api_loesche_nutzer_ist_strukturell_noop(staging):
    w = _werkzeug()
    staging.seed_en()
    api = staging.en_api(w)
    api.loesche_nutzer()                       # noch nicht angemeldet
    api.melde_an(EN_UID, EN_PASS)
    assert api.nutzer_id == EN_UID
    vorher = len(staging.log)
    api.loesche_nutzer()                       # angemeldet, Passwort bekannt - trotzdem nichts
    assert len(staging.log) == vorher and staging.konto_loeschungen() == []
    assert EN_UID in staging.users


# AC-15 -----------------------------------------------------------------------

def _env_en(monkeypatch, tmp_path, w, staging, *, user=True, passwort=True, wert=EN_PASS):
    monkeypatch.setattr(w.pw, "STAGING_ENV", tmp_path / "keine.env")
    for k in ("GZ_CORE_SHARED_SECRET", "GZ_AUTH_USER", "GZ_AUTH_PASS", "GZ_E2E_EN_USER", "GZ_E2E_EN_PASS"):
        monkeypatch.delenv(k, raising=False)       # Helfer-Konto bewusst NICHT gesetzt
    monkeypatch.setenv("GZ_CORE_SHARED_SECRET", CORE_SECRET)
    monkeypatch.setenv("GZ_STAGING_BASE_URL", staging.url)
    monkeypatch.setenv("GZ_STAGING_CORE_URL", staging.url)
    if user:
        monkeypatch.setenv("GZ_E2E_EN_USER", EN_UID)
    if passwort:
        monkeypatch.setenv("GZ_E2E_EN_PASS", wert)


@pytest.mark.parametrize("user,passwort", [(False, False), (True, False), (False, True)])
def test_main_en_ohne_zugangsdaten_ist_exit_2_ohne_netz(monkeypatch, tmp_path, capsys, staging, user, passwort):
    w = _werkzeug()
    staging.seed_en()
    _env_en(monkeypatch, tmp_path, w, staging, user=user, passwort=passwort)
    assert w.main(["--typ", "trip", "--lang", "en"], validator_runner=_Runner()) == 2
    assert staging.log == [], "vor jeder Aenderung und ohne Netzzugriff"
    err = capsys.readouterr().err
    assert ("GZ_E2E_EN_USER" in err) == (not user) and ("GZ_E2E_EN_PASS" in err) == (not passwort)
    assert EN_PASS not in err and EN_UID not in err


def test_main_en_login_abgelehnt_ist_exit_2_ohne_anlegen(monkeypatch, tmp_path, capsys, staging):
    w = _werkzeug()
    staging.seed_en()
    falsch = "FALSCHES-EN-PASS-k4471"
    _env_en(monkeypatch, tmp_path, w, staging, wert=falsch)
    r = _Runner()
    assert w.main(["--typ", "beide", "--lang", "en"], validator_runner=r) == 2
    assert r.aufrufe == [] and staging.kern == []
    assert [(m, p) for _, m, p in staging.log] == [("POST", "/api/auth/login")], \
        "genau ein abgelehnter Login-Versuch, sonst keine Anfrage (Abbruch ohne Anlegen)"
    assert not any(m == "POST" and p in ("/api/trips", "/api/locations", "/api/compare/presets",
                                         "/api/auth/register") for _, m, p in staging.log)
    assert staging.konto_loeschungen() == [] and EN_UID in staging.users
    aus = capsys.readouterr()
    assert falsch not in aus.out + aus.err and EN_PASS not in aus.out + aus.err


def test_main_lang_de_ist_default_und_de_en_wird_abgelehnt(monkeypatch, tmp_path, staging):
    w = _werkzeug()
    _env(monkeypatch, tmp_path, w)
    monkeypatch.setenv("GZ_STAGING_BASE_URL", staging.url)
    monkeypatch.setenv("GZ_STAGING_CORE_URL", staging.url)
    assert w.main(["--typ", "trip", "--lang", "de,en"], validator_runner=_Runner()) == 2
    assert staging.log == []
    r = _Runner()
    assert w.main(["--typ", "trip", "--lang", "de"], validator_runner=r) == 0
    assert "--lang" not in r.aufrufe[0] and staging.users == {}


def test_main_en_gegen_ersatz_staging_ist_exit_0_ohne_helfer_konto(monkeypatch, tmp_path, staging):
    w = _werkzeug()
    staging.seed_en()
    _env_en(monkeypatch, tmp_path, w, staging)
    r = _Runner()
    assert w.main(["--typ", "beide", "--lang", "en"], validator_runner=r) == 0
    assert len(r.aufrufe) == 2 and all("--lang" in a and "+en@" in a for a in r.aufrufe)
    assert staging.users[EN_UID]["trips"] == {} and staging.users[EN_UID]["presets"] == {}
    assert staging.konto_loeschungen() == []


# AC-16 -----------------------------------------------------------------------

def test_en_ausgaben_enthalten_keine_geheimnisse(monkeypatch, tmp_path, staging, capsys):
    w = _werkzeug()
    staging.seed_en()
    _lauf_en(w, staging, tag="e6-aaaa")                                   # Erfolg
    staging.ablehnen = {"/api/scheduler/": 500}
    _lauf_en(w, staging, tag="e6-bbbb")                                   # Versand abgelehnt
    staging.ablehnen = {"/api/trips/": 500}
    _lauf_en(w, staging, tag="e6-cccc")                                   # Aufraeumfehler
    staging.ablehnen = {}
    _lauf_en(w, staging, tag="e6-dddd", secret="FALSCH-GEHEIM-k93x")      # Core 401
    _lauf_en(w, staging, tag="e6-eeee", passwort="FALSCH-EN-zz81")        # Login abgelehnt
    aus = capsys.readouterr()
    for geheim in (EN_PASS, CORE_SECRET, HELFER_PASS, "FALSCH-GEHEIM-k93x", "FALSCH-EN-zz81"):
        assert geheim not in aus.out and geheim not in aus.err
    assert EN_PASS not in repr(staging.en_api(w))


# AC-17 -----------------------------------------------------------------------

@pytest.mark.parametrize("zusatz", [{}, {"lang": "de"}])
def test_de_lauf_ohne_lang_verhaelt_sich_wie_vorher(staging, capsys, zusatz):
    w = _werkzeug()
    r = _Runner()
    assert w.fuehre_lauf(["trip"], api=staging.api(w), validator_runner=r, tag="d1-aaaa", **zusatz) == 0
    assert "--lang" not in r.aufrufe[0] and "--to-contains" not in r.aufrufe[0]
    assert staging.users == {}, "Wegwerf-Nutzer wird geloescht"
    assert len(staging.konto_loeschungen()) == 1
    assert "/api/auth/register" in [p for _, _, p in staging.log]
    assert "Wegwerf-Nutzer geloescht" in capsys.readouterr().out


# AC-18 -----------------------------------------------------------------------

def test_en_lauf_exit_je_ausgang_gegen_ersatz_staging(staging):
    w = _werkzeug()
    staging.seed_en()
    assert _lauf_en(w, staging, tag="x1-aaaa") == 0
    assert _lauf_en(w, staging, runner=_Runner({"briefing": 1}), tag="x2-aaaa") == 1
    assert _lauf_en(w, staging, runner=_Runner({"briefing": 2}), tag="x2-bbbb") == 2
    staging.kern_antwort = (500, {"error": "send_failed"})
    r = _Runner()
    assert _lauf_en(w, staging, runner=r, tag="x3-aaaa") == 1
    assert r.aufrufe == [], "abgelehnter Versand darf keinen Validator auf eine aeltere Mail loslassen"
    staging.kern_antwort = (200, {"status": "skipped", "sent": False})
    assert _lauf_en(w, staging, runner=r, tag="x3-bbbb") == 1 and r.aufrufe == []
    staging.kern_antwort = None
    assert _lauf_en(w, staging, tag="x4-aaaa", secret="falsch") == 2
    assert _lauf_en(w, staging, tag="x5-aaaa", passwort="falsch") == 2
    assert staging.users[EN_UID]["trips"] == {}


# AC-21 -----------------------------------------------------------------------

def test_en_und_de_lauf_nutzen_getrennte_kennungen_und_beruehren_keine_fremden_daten(staging):
    w = _werkzeug()
    staging.seed_en()
    assert _lauf_en(w, staging, ("trip", "compare"), tag="m1-aaaa") == 0
    assert w.fuehre_lauf(["trip"], api=staging.api(w), validator_runner=_Runner(), tag="m2-bbbb") == 0
    en_kern, de_kern = staging.kern[:2], staging.kern[2:]
    assert {c["user_id"] for c in en_kern} == {EN_UID}
    (de_uid,) = {c["user_id"] for c in de_kern}
    assert re.fullmatch(r"u-[0-9a-f]{8}", de_uid) and de_uid != EN_UID
    assert "default" not in {c["user_id"] for c in staging.kern}
    assert list(staging.users) == [EN_UID], "der de-Wegwerf-Nutzer ist weg, der Nutzer en besteht"
    for sid, methode, pfad in staging.log:
        if methode == "DELETE" or pfad.endswith("/account/delete"):
            assert sid in (EN_UID, de_uid)
            if sid == de_uid:
                assert "m1-aaaa" not in pfad
            if sid == EN_UID:
                assert "m2-bbbb" not in pfad and not pfad.endswith("/account/delete")


# AC-20 (doc-compliance-test) -------------------------------------------------

def test_rezept_nennt_lang_en_aufruf_in_runbook_und_e2e_verify():
    # doc-compliance-test
    for pfad in (RUNBOOK_EN, E2E_VERIFY):
        text = pfad.read_text(encoding="utf-8")
        assert re.search(r"staging_mail_pruefen\.py[^\n]*--lang en", text), \
            f"Aufruf 'staging_mail_pruefen.py ... --lang en' fehlt in {pfad.name}"
        assert "--langs de,en" in text and "staging_gate.py" in text, f"Gate-Hinweis fehlt in {pfad.name}"
        assert re.search(r"Nutzer `?en`?[^\n]*(nie|nicht)[^\n]*gel(oe|ö)scht|nie[^\n]*gel(oe|ö)scht[^\n]*`?en`?",
                         text), f"Hinweis 'Nutzer en wird nie geloescht' fehlt in {pfad.name}"


# ---------------------------------------------------------------------------
# AC-1 / AC-2: Live gegen Staging (nur /e2e-verify)
# ---------------------------------------------------------------------------

def _staging_bereit():
    try:
        return STAGING_ENV.is_file() and STAGING_ENV.read_text()
    except OSError:
        return False


def _staging_en_bereit():
    text = _staging_bereit()
    return bool(text) and "GZ_E2E_EN_USER" in text and "GZ_E2E_EN_PASS" in text


@pytest.mark.live
@pytest.mark.staging
@pytest.mark.skipif(not _staging_bereit(), reason="Staging-Zugangsdaten nicht lesbar")
def test_gesamtlauf_trip_auf_staging():
    assert _werkzeug().main(["--typ", "trip"]) == 0


@pytest.mark.live
@pytest.mark.staging
@pytest.mark.skipif(not _staging_bereit(), reason="Staging-Zugangsdaten nicht lesbar")
def test_gesamtlauf_compare_auf_staging():
    assert _werkzeug().main(["--typ", "compare"]) == 0


# AC-19: englischer Pfad live (nur /e2e-verify)

@pytest.mark.live
@pytest.mark.staging
@pytest.mark.skipif(not _staging_en_bereit(), reason="Staging-Zugangsdaten des Nutzers en nicht lesbar")
def test_gesamtlauf_trip_en_auf_staging():
    assert _werkzeug().main(["--typ", "trip", "--lang", "en"]) == 0


@pytest.mark.live
@pytest.mark.staging
@pytest.mark.skipif(not _staging_en_bereit(), reason="Staging-Zugangsdaten des Nutzers en nicht lesbar")
def test_gesamtlauf_compare_en_auf_staging():
    assert _werkzeug().main(["--typ", "compare", "--lang", "en"]) == 0
