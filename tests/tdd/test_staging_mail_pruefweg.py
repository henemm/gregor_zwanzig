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
"""
from __future__ import annotations

import importlib.util
import json
import re
import secrets
import sys
import threading
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
                    uid = "u-" + secrets.token_hex(4)
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

    def api(self, w, secret=CORE_SECRET):
        return w.MailApi(self.url, self.url, secret, w.pw.http_transport(),
                         helfer_transport=w.pw.http_transport(), helfer_zugang=(HELFER_USER, HELFER_PASS))


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
# AC-1 / AC-2: Live gegen Staging (nur /e2e-verify)
# ---------------------------------------------------------------------------

def _staging_bereit():
    try:
        return STAGING_ENV.is_file() and STAGING_ENV.read_text()
    except OSError:
        return False


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
