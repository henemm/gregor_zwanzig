"""Außen-Probe des MCP-Konnektors auf Staging (#3286).

Spec: docs/specs/modules/infra_3286_mcp_server_einrichtung.md (AC-1 bis AC-6, AC-9, AC-10)

Prüfling ``.claude/tools/staging_mcp_pruefen.py``, gegen einen echten lokalen HTTP-Server (keine Mocks).
Schnittstelle:
    main(argv=None, *, env=None, basis=BASIS, server_merkmal=SERVER_MERKMAL) -> int
        env   Zuordnung der Zugangsdaten (None = os.environ); basis = zu prüfende Adresse (zugleich
              erwarteter Issuer und Origin); existiert der Pfad server_merkmal, läuft die Probe auf
              dem Server: Exit 2 ohne Netzzugriff.
        argv  [] = Regelprüfung; ["--vor-freigabe"] = fail-closed-Lauf (AC-6): auch das Konto
              GZ_AUTH_* muss 403 erhalten. Unbekanntes Argument: Exit 2.
    Exit 0 bestanden, 1 Soll verfehlt, 2 Aufruf-/Umgebungsfehler (auch: Server nicht erreichbar,
    Anmeldung abgelehnt). Basic-Zugangsdaten gehen NUR an POST /api/auth/login.
    Je Befund eine Zeile, die den Pfad nennt ("<pfad> ..." oder "<pfad>: ...").
"""
from __future__ import annotations

import base64
import hashlib
import importlib.util
import json
import os
import socket
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
WERKZEUG = REPO_ROOT / ".claude" / "tools" / "staging_mcp_pruefen.py"

META_SERVER = "/.well-known/oauth-authorization-server"
META_RESSOURCE = "/.well-known/oauth-protected-resource"
META = [META_SERVER, META_RESSOURCE, META_RESSOURCE + "/api/mcp"]
OAUTH = ["/api/mcp/oauth/register", "/api/mcp/oauth/authorize", "/api/mcp/oauth/token"]
SOLL = [*META, "/api/mcp", *OAUTH]
VERBOTEN = ["/", "/login", "/api/trips", "/api/mcpx", "/api/_internal/mcp/wetter",
            "/.well-known/openid-configuration"]
INTERN = "/api/internal/"
CSP = ("default-src 'none'; style-src 'unsafe-inline'; form-action 'self' http://localhost:* "
       "http://127.0.0.1:*; frame-ancestors 'none'; base-uri 'none'")
ENV = {"GZ_VALIDATOR_USER": "schranke-nutzer", "GZ_VALIDATOR_PASS": "SCHRANKE-GEHEIM-a1",
       "GZ_AUTH_USER": "default", "GZ_AUTH_PASS": "APP-GEHEIM-b2",
       "GZ_STAGING_ADMIN_USER": "gz-staging-admin", "GZ_STAGING_ADMIN_PASS": "ADMIN-GEHEIM-c3"}
BASIC = base64.b64encode(f"{ENV['GZ_VALIDATOR_USER']}:{ENV['GZ_VALIDATOR_PASS']}".encode()).decode()
GO_FEHLER = [("Content-Security-Policy", "default-src 'none'")]
FREMD = "https://gregor20.henemm.com"
CODE, TOKEN, ERNEUERN, SITZUNG = "CODE-GEHEIM-d4", "TOKEN-GEHEIM-e5", "REFRESH-GEHEIM-f6", "SITZUNG-GEHEIM-g7"
GEHEIM = [ENV["GZ_VALIDATOR_PASS"], ENV["GZ_AUTH_PASS"], ENV["GZ_STAGING_ADMIN_PASS"], BASIC,
          CODE, TOKEN, ERNEUERN, SITZUNG]


class _Staging:
    """nginx-Schranke und Go-Konnektor (Verhalten wie internal/mcp) auf Loopback."""

    def __init__(self):
        self.blockiert: set[str] = set()       # Soll-Pfade, die noch hinter der Schranke liegen
        self.offen: dict[str, int] = {}        # sonst gesperrter Pfad -> Antwortstatus ohne Basic
        self.frei = {"default"}                # GZ_MCP_USER_IDS
        self.leck: str | None = None           # "GET": Zweitkonto sieht Zustimmung; "POST": nur Code
        self.csp = [CSP]
        self.www = 'Bearer resource_metadata="{b}' + META_RESSOURCE + '/api/mcp"'
        self.meta_basis: str | None = None     # abweichender Issuer bzw. Resource
        self.meta: dict[str, dict] = {}        # je Metadatenpfad abweichende Felder
        self.register_status = 201
        self.ablehnung = (403, GO_FEHLER)      # Antwort an nicht gelistete Konten
        self.ablehnung_bei = ""                # Methode, für die self.ablehnung gilt ("" = beide)
        self.umleitung: dict[str, str] = {}    # abweichende Felder bzw. Ziel der Code-Weiterleitung
        self.ziel: str | None = None
        self.token, self.token_status = TOKEN, 200
        self.haengt_s = 0.0
        self.meta_html = False                 # Metadaten 200, aber HTML
        self.code_status = 303
        self.ohne_code = False
        self.werkzeuge = ["ort_suchen", "wetter"]
        self.wetter: dict | str = {"ort": {"name": "Innsbruck"}, "stunden": [{"zeit": "x", "t2m_c": 1.0}]}
        self.wetter_fehler = False
        self.log: list[tuple[str, str]] = []
        self.basic_pfade: set[str] = set()
        self.challenge = ""
        self.redirect = ""
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def _raus(self, status, body=b"", kopf=(), typ="application/json"):
                roh = body if isinstance(body, bytes) else json.dumps(body).encode()
                self.send_response(status)
                for k, v in [("Content-Type", typ), ("Content-Length", str(len(roh))), *kopf]:
                    self.send_header(k, v)
                self.end_headers()
                self.wfile.write(roh)

            def _handle(self, methode):
                teile = urlsplit(self.path)
                pfad, q = teile.path, {k: v[0] for k, v in parse_qs(teile.query).items()}
                roh = self.rfile.read(int(self.headers.get("Content-Length") or 0))
                auth = self.headers.get("Authorization") or ""
                outer.log.append((methode, pfad))
                if auth.startswith("Basic "):
                    outer.basic_pfade.add(pfad)
                if pfad.startswith(INTERN):
                    return self._raus(outer.offen.get(pfad, 403))
                if (pfad not in SOLL or pfad in outer.blockiert) and auth != f"Basic {BASIC}":
                    if pfad in outer.offen:
                        ziel = [("Location", "/login")] if outer.offen[pfad] == 302 else []
                        return self._raus(outer.offen[pfad], {}, ziel)
                    return self._raus(401, b"", [("WWW-Authenticate", 'Basic realm="Staging"')], "text/html")
                time.sleep(outer.haengt_s)
                if pfad in META:
                    return self._meta(pfad)
                if pfad == "/api/auth/login":
                    return self._anmelden(json.loads(roh or b"{}"))
                if pfad == "/api/mcp":
                    return self._mcp(auth, roh)
                if pfad == OAUTH[0] and methode == "POST":
                    if outer.register_status != 201:
                        return self._raus(outer.register_status, {"error": "rate_limit_exceeded"})
                    uris = json.loads(roh or b"{}").get("redirect_uris") or []
                    if not uris or not all(u.startswith("http://127.0.0.1:") for u in uris):
                        return self._raus(400, {"error": "invalid_redirect_uri"})
                    outer.redirect = uris[0]
                    return self._raus(201, {"client_id": "c_1", "redirect_uris": uris})
                if pfad == OAUTH[1]:
                    if methode == "POST":
                        q = {k: v[0] for k, v in parse_qs(roh.decode()).items()}
                    return self._autorisieren(methode, q)
                if pfad == OAUTH[2] and methode == "POST":
                    return self._token({k: v[0] for k, v in parse_qs(roh.decode()).items()})
                return self._raus(404, {"error": "not_found"})

            def _meta(self, pfad):
                if outer.meta_html:
                    return self._raus(200, b"<html></html>", typ="text/html")
                b = outer.meta_basis or outer.basis
                soll = {"issuer": b} if pfad == META_SERVER \
                    else {"resource": b + "/api/mcp", "authorization_servers": [b]}
                return self._raus(200, {**soll, **outer.meta.get(pfad, {})})

            def _anmelden(self, b):
                if (b.get("username"), b.get("password")) not in (
                        (ENV["GZ_AUTH_USER"], ENV["GZ_AUTH_PASS"]),
                        (ENV["GZ_STAGING_ADMIN_USER"], ENV["GZ_STAGING_ADMIN_PASS"])):
                    return self._raus(401, {"error": "bad"})
                cookie = f"gz_session={SITZUNG}.{b['username']}; Path=/; HttpOnly"
                return self._raus(200, {"id": b["username"]}, [("Set-Cookie", cookie)])

            def _autorisieren(self, methode, q):
                if methode == "POST" and self.headers.get("Origin") != outer.basis:
                    return self._raus(403, {"error": "origin"})
                if q.get("client_id") != "c_1" or q.get("redirect_uri") != outer.redirect \
                        or q.get("response_type") != "code" or q.get("code_challenge_method") != "S256" \
                        or not q.get("code_challenge"):
                    return self._raus(400, b"<html></html>", [("Content-Security-Policy", CSP)], "text/html")
                nutzer = ""
                for teil in (self.headers.get("Cookie") or "").split(";"):
                    if teil.strip().startswith(f"gz_session={SITZUNG}."):
                        nutzer = teil.strip().rsplit(".", 1)[1]
                if not nutzer:
                    return self._raus(302, b"", [("Location", "/login?redirect=x")])
                if nutzer not in outer.frei and outer.leck != methode:
                    gilt = outer.ablehnung_bei in ("", methode)
                    status, kopf = outer.ablehnung if gilt else (403, GO_FEHLER)
                    return self._raus(status, b"<html>nicht freigegeben</html>", kopf, "text/html")
                kopf = [("Content-Security-Policy", c) for c in outer.csp]
                if methode == "GET":
                    return self._raus(200, b"<html><form></form></html>", kopf, "text/html")
                if q.get("aktion") != "erlauben":
                    return self._raus(303, b"", [("Location", outer.redirect + "?error=access_denied")])
                outer.challenge = q["code_challenge"]
                daten = {"state": q.get("state", ""), "iss": outer.basis}
                if not outer.ohne_code:
                    daten["code"] = CODE
                ziel = (outer.ziel or outer.redirect) + "?" + urlencode({**daten, **outer.umleitung})
                return self._raus(outer.code_status, b"", [("Location", ziel), *kopf])

            def _token(self, f):
                probe = hashlib.sha256(f.get("code_verifier", "").encode()).digest()
                ok = f.get("grant_type") == "authorization_code" and f.get("code") == CODE \
                    and f.get("client_id") == "c_1" and f.get("redirect_uri") == outer.redirect \
                    and base64.urlsafe_b64encode(probe).rstrip(b"=").decode() == outer.challenge
                if not ok:
                    return self._raus(400, {"error": "invalid_grant"})
                return self._raus(outer.token_status, {"access_token": outer.token, "refresh_token": ERNEUERN,
                                                       "token_type": "Bearer"})

            def _mcp(self, auth, roh):
                if auth != f"Bearer {TOKEN}":
                    return self._raus(401, {"error": "unauthorized"},
                                      [("WWW-Authenticate", outer.www.replace("{b}", outer.basis))])
                m = json.loads(roh)
                if m["method"] == "tools/list":
                    erg = {"tools": [{"name": n} for n in outer.werkzeuge]}
                elif m["method"] == "tools/call" and m["params"]["name"] == "wetter":
                    text = outer.wetter if isinstance(outer.wetter, str) else json.dumps(outer.wetter)
                    erg = {"content": [{"type": "text", "text": text}], "isError": outer.wetter_fehler}
                else:
                    erg = {"protocolVersion": "2025-11-25", "capabilities": {}}
                return self._raus(200, {"jsonrpc": "2.0", "id": m.get("id"), "result": erg})

            def do_GET(self):
                self._handle("GET")

            def do_POST(self):
                self._handle("POST")

        self.httpd = ThreadingHTTPServer(("127.0.0.1", 0), H)
        self.basis = f"http://127.0.0.1:{self.httpd.server_address[1]}"
        threading.Thread(target=self.httpd.serve_forever, args=(0.02,), daemon=True).start()


@pytest.fixture
def staging():
    s = _Staging()
    yield s
    s.httpd.shutdown()
    s.httpd.server_close()


def _werkzeug():
    if not WERKZEUG.exists():
        pytest.fail(f"Prüfwerkzeug fehlt: {WERKZEUG.relative_to(REPO_ROOT)}")
    spec = importlib.util.spec_from_file_location("staging_mcp_pruefen_unter_test", WERKZEUG)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def lauf(capsys, tmp_path):
    """Führt die Probe aus; JEDER Lauf prüft, dass kein Geheimnis in der Ausgabe steht (AC-10)."""
    def _lauf(basis, argv=(), env=ENV, merkmal=None, zeitgrenze=None):
        mod = _werkzeug()
        mod.TIMEOUT_S = zeitgrenze or mod.TIMEOUT_S
        rc = mod.main(list(argv), env=env, basis=basis, server_merkmal=merkmal or tmp_path / "kein-server")
        aus = capsys.readouterr()
        text = aus.out + aus.err
        assert not [g for g in GEHEIM if g in text], "Geheimnis in der Ausgabe"
        return rc, text
    return _lauf


def _genannt(pfad, text):
    return any(pfad in z.split() or f"{pfad}:" in z.split() for z in text.splitlines())


def test_vollstaendiges_soll_besteht(staging, lauf):
    """Test 3 (AC-1 bis AC-5, AC-9): alles wie gefordert -> Exit 0, alle Pfade wirklich abgefragt."""
    rc, text = lauf(staging.basis)
    assert rc == 0, text
    assert {p for _, p in staging.log} >= {*SOLL, *VERBOTEN, INTERN}
    assert ("POST", OAUTH[2]) in staging.log and ("POST", "/api/mcp") in staging.log


def test_basic_zugangsdaten_nur_an_die_anmeldung(staging, lauf):
    """Sonst bewiese die Probe nichts: mit Basic ist jeder Pfad offen."""
    lauf(staging.basis)
    assert staging.basic_pfade == {"/api/auth/login"}


@pytest.mark.parametrize("pfad", SOLL)
def test_einzelner_blockierter_soll_pfad(staging, lauf, pfad):
    """Test 1 (AC-1, AC-2, AC-10)."""
    staging.blockiert = {pfad}
    rc, text = lauf(staging.basis)
    assert rc == 1
    assert _genannt(pfad, text), text


def test_alle_soll_pfade_blockiert_wie_vor_der_aenderung(staging, lauf):
    """Test 1 / AC-13: Ist-Stand bzw. Rollback -> Exit 1 (nicht 2), alle Pfade genannt."""
    staging.blockiert = set(SOLL)
    rc, text = lauf(staging.basis)
    assert rc == 1
    assert [p for p in SOLL if not _genannt(p, text)] == []


@pytest.mark.parametrize("status", [200, 302, 401, 404])
@pytest.mark.parametrize("pfad", VERBOTEN)
def test_offener_verbotspfad(staging, lauf, pfad, status):
    """Test 2 (AC-3): nur 401 MIT Basic gilt; 401 der App, Weiterleitung und 404 sind offen."""
    staging.offen = {pfad: status}
    rc, text = lauf(staging.basis)
    assert rc == 1
    assert _genannt(pfad, text), text


@pytest.mark.parametrize("status", [200, 401, 404])
def test_interner_pfad_muss_403_bleiben(staging, lauf, status):
    """AC-3."""
    staging.offen = {INTERN: status}
    rc, text = lauf(staging.basis)
    assert rc == 1
    assert _genannt(INTERN, text), text


@pytest.mark.parametrize("abweichung", [
    {"meta_basis": "https://gregor20.henemm.com"}, {"meta_html": True},
    {"www": "Bearer"}, {"www": 'Basic realm="Staging"'},
    {"www": 'Bearer resource_metadata="https://gregor20.henemm.com/.well-known/oauth-protected-resource/api/mcp"'},
])
def test_metadaten_und_bearer_hinweis_falsch(staging, lauf, abweichung):
    """AC-1, AC-2: falscher Issuer, HTML statt JSON, falscher WWW-Authenticate."""
    vars(staging).update(abweichung)
    assert lauf(staging.basis)[0] == 1


@pytest.mark.parametrize("abweichung", [
    {"frei": set()}, {"code_status": 200}, {"ohne_code": True}, {"werkzeuge": ["ort_suchen"]},
    {"wetter": {"ort": {"name": "Innsbruck"}, "stunden": []}}, {"wetter": {"ort": {}, "stunden": [{"t2m_c": 1}]}},
    {"wetter": "Der Wetterdienst antwortet nicht."}, {"wetter_fehler": True},
])
def test_oauth_ablauf_unvollstaendig(staging, lauf, abweichung):
    """AC-4: jeder einzelne Schritt zählt."""
    vars(staging).update(abweichung)
    assert lauf(staging.basis)[0] == 1


@pytest.mark.parametrize("pfad,feld,wert", [
    (META_SERVER, "issuer", FREMD), *[(p, f, w) for p in META[1:] for f, w in (
        ("resource", FREMD + "/api/mcp"), ("authorization_servers", [FREMD]))]])
def test_einzelnes_metadatenfeld_falsch(staging, lauf, pfad, feld, wert):
    """F003 (AC-1): jedes Feld jedes Dokuments zählt für sich."""
    staging.meta = {pfad: {feld: wert}}
    rc, text = lauf(staging.basis)
    assert rc == 1
    assert _genannt(pfad, text), text


_STUNDE = {"zeit": "x", "t2m_c": 1.0}


@pytest.mark.parametrize("abweichung", [
    {"wetter": {"ort": {}, "stunden": [_STUNDE]}},
    *[{"wetter": {"ort": {"name": "Innsbruck"}, "stunden": st}} for st in (
        [{"t2m_c": 1.0}], [{"zeit": "x"}], [_STUNDE, {"t2m_c": 1.0}], [_STUNDE, {"zeit": "x"}])],
    {"werkzeuge": ["wetter"]}, {"token_status": 400}, {"token_status": 201},
    {"code_status": 302}, {"umleitung": {"iss": FREMD}}, {"umleitung": {"state": "falsch"}},
    {"ziel": "http://127.0.0.1:1/fremd"},
])
def test_oauth_ablauf_einzelmerkmal_falsch(staging, lauf, abweichung):
    """F003, F006 (AC-4): je Fall genau ein Merkmal falsch."""
    vars(staging).update(abweichung)
    assert lauf(staging.basis)[0] == 1


@pytest.mark.parametrize("argv", [[], ["--vor-freigabe"]])
@pytest.mark.parametrize("methode", ["GET", "POST"])
@pytest.mark.parametrize("antwort", [
    (302, [*GO_FEHLER, ("Location", "/login?redirect=x")]), (500, GO_FEHLER), (403, []),
    (403, [*GO_FEHLER, ("Location", "http://127.0.0.1:1/?code=x")])], ids=["302", "500", "403-fremd", "403-location"])
def test_ablehnung_muss_403_von_go_ohne_weiterleitung_sein(staging, lauf, antwort, methode, argv):
    """F004 (AC-5, AC-6): eine andere Absage ist kein Beleg, dass Go das Konto ablehnt."""
    staging.ablehnung, staging.ablehnung_bei = antwort, methode
    staging.frei = set() if argv else {"default"}
    rc, text = lauf(staging.basis, argv)
    assert rc == 1
    assert _genannt(OAUTH[1], text), text


def test_ausnahmetext_mit_geheimnis_bleibt_stumm(staging, lauf):
    """F005 (AC-10): http.client nennt einen ungültigen Headerwert im Ausnahmetext."""
    staging.token = TOKEN + "\nX"
    rc, text = lauf(staging.basis)
    assert rc == 2
    assert "ValueError" in text


def test_haengender_server_ist_umgebungsfehler(staging, lauf):
    """F007: die Zeitgrenze erreicht die Verbindung; die Antwort käme erst nach 1,5 s."""
    staging.haengt_s = 1.5
    start = time.monotonic()
    assert lauf(staging.basis, zeitgrenze=0.2)[0] == 2
    assert time.monotonic() - start < 1.4


def test_zeitgrenze_passt_zur_spec():
    """F007 (AC-7): länger als der längste Aufruf (10+5+60 s), nicht länger als nginx wartet (120 s)."""
    assert 10 + 5 + 60 < _werkzeug().TIMEOUT_S <= 120


def test_registrierungsbremse_ist_umgebungsfehler(staging, lauf):
    """F008: 429 heißt Kontingent erschöpft, nicht Schranke zu; übrige Befunde werden weiter genannt."""
    staging.register_status, staging.offen = 429, {"/login": 200}
    rc, text = lauf(staging.basis)
    assert rc == 2
    zeilen = [z for z in text.splitlines() if OAUTH[0] in z]
    assert len(zeilen) == 1 and "429" in zeilen[0] and "Soll" not in zeilen[0], text
    assert _genannt("/login", text), text


def test_registrierungsbremse_allein_ist_nie_bestanden(staging, lauf):
    """F008."""
    staging.register_status = 429
    rc, text = lauf(staging.basis)
    assert rc == 2 and "BESTANDEN" not in text


@pytest.mark.parametrize("methode", ["GET", "POST"])
def test_zweites_konto_erhaelt_zustimmung_oder_code(staging, lauf, methode):
    """Test 4 (AC-5): Mandantentrennung, auch wenn erst der POST leckt."""
    staging.leck = methode
    assert lauf(staging.basis)[0] == 1


@pytest.mark.parametrize("csp", [[CSP, CSP], [CSP, "default-src 'self'"], ["default-src 'self'"], []])
def test_csp_nicht_genau_die_der_api(staging, lauf, csp):
    """Test 5 (AC-9)."""
    staging.csp = csp
    assert lauf(staging.basis)[0] == 1


def test_vor_freigabe_ist_fail_closed(staging, lauf):
    """AC-6: ohne GZ_MCP_USER_IDS erhält auch default 403; nie wird ein Code ausgestellt."""
    staging.frei = set()
    rc, text = lauf(staging.basis, ["--vor-freigabe"])
    assert rc == 0, text
    assert staging.challenge == ""


def test_vor_freigabe_schlaegt_an_wenn_schon_freigegeben(staging, lauf):
    """AC-6: default erhält bereits einen Code -> Exit 1."""
    assert lauf(staging.basis, ["--vor-freigabe"])[0] == 1


@pytest.mark.parametrize("fehlt", sorted(ENV))
@pytest.mark.parametrize("leer", [True, False])
def test_fehlende_zugangsdaten(staging, lauf, fehlt, leer):
    """Test 6 (AC-10): Exit 2 ohne Netzzugriff, Name der Variable genannt."""
    env = {**ENV, fehlt: ""} if leer else {k: v for k, v in ENV.items() if k != fehlt}
    rc, text = lauf(staging.basis, env=env)
    assert rc == 2
    assert fehlt in text
    assert staging.log == []


def test_start_auf_dem_server(staging, lauf, tmp_path):
    """Test 6 (AC-10): die Server-IP umgeht die Schranke -> Exit 2 ohne Netzzugriff."""
    assert lauf(staging.basis, merkmal=tmp_path)[0] == 2
    assert staging.log == []


def test_server_merkmal_ist_der_staging_klon():
    assert str(_werkzeug().SERVER_MERKMAL) == "/home/hem/gregor_zwanzig_staging"


def test_unbekanntes_argument(staging, lauf):
    assert lauf(staging.basis, ["--vor-freigab"])[0] == 2
    assert staging.log == []


def test_anmeldung_abgelehnt_ist_umgebungsfehler(staging, lauf):
    assert lauf(staging.basis, env={**ENV, "GZ_AUTH_PASS": "falsch"})[0] == 2


def test_server_nicht_erreichbar_ist_umgebungsfehler(lauf):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    assert lauf(f"http://127.0.0.1:{port}")[0] == 2


def test_aufruf_als_programm_ohne_umgebung():
    """Test 6: der echte Programmaufruf endet mit Exit 2 (auf dem Server wie anderswo)."""
    _werkzeug()
    umgebung = {k: v for k, v in os.environ.items() if not k.startswith("GZ_")}
    p = subprocess.run([sys.executable, str(WERKZEUG)], env=umgebung, capture_output=True, text=True, timeout=20)
    assert p.returncode == 2, p.stdout + p.stderr
    assert "Traceback" not in p.stderr
