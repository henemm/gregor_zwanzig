#!/usr/bin/env python3
"""Außen-Probe des MCP-Konnektors auf Staging: Pfade, OAuth-Ablauf mit zwei Konten, CSP (#3286).

Spec: docs/specs/modules/infra_3286_mcp_server_einrichtung.md. Zugangsdaten nur aus der Umgebung;
ausgegeben werden nur feste Texte und Statuszahlen, nie Werte aus Umgebung oder Antworten.
Aufruf:  python3 .claude/tools/staging_mcp_pruefen.py [--vor-freigabe]   (auch GZ_AUTH_* muss 403 erhalten)
Exit:    0 = bestanden, 1 = Soll verfehlt, 2 = Aufruf-/Umgebungsfehler
"""
import base64
import hashlib
import http.client
import json
import os
import secrets
import sys
from collections import namedtuple
from contextlib import closing
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

BASIS = "https://staging.gregor20.henemm.com"
SERVER_MERKMAL = Path("/home/hem/gregor_zwanzig_staging")
VARIABLEN = [f"GZ_{k}_{t}" for k in ("VALIDATOR", "AUTH", "STAGING_ADMIN") for t in ("USER", "PASS")]
META_SERVER, META_RESSOURCE = "/.well-known/oauth-authorization-server", "/.well-known/oauth-protected-resource"
MCP, LOGIN, INTERN = "/api/mcp", "/api/auth/login", "/api/internal/"
REGISTER, AUTHORIZE, TOKEN = (f"/api/mcp/oauth/{n}" for n in ("register", "authorize", "token"))
GESPERRT = ["/", "/login", "/api/trips", "/api/mcpx", "/api/_internal/mcp/wetter", "/.well-known/openid-configuration"]
RUECKSPRUNG = "http://127.0.0.1:8765/callback"
CSP = ("default-src 'none'; style-src 'unsafe-inline'; form-action 'self' http://localhost:* "
       "http://127.0.0.1:*; frame-ancestors 'none'; base-uri 'none'")  # internal/mcp cspFuer (Loopback)
TIMEOUT_S = 100  # ein Wetteraufruf dauert bis zu 75 s
Antwort = namedtuple("Antwort", "status kopf objekt csp www")


class Umgebungsfehler(Exception):
    """Trägt nur feste Texte."""


def objekt(roh) -> dict:
    try:
        wert = json.loads(roh)
    except (TypeError, ValueError):
        return {}
    return wert if isinstance(wert, dict) else {}


def rufe(basis, methode, pfad, rumpf=None, **kopf) -> Antwort:
    """Eine Anfrage, Rumpf dict = JSON, str = Formular; http.client folgt Weiterleitungen nie."""
    if rumpf:
        kopf["Content-Type"] = "application/json" if isinstance(rumpf, dict) else "application/x-www-form-urlencoded"
        rumpf = (json.dumps(rumpf) if isinstance(rumpf, dict) else rumpf).encode()
    ziel = urlsplit(basis)
    art = http.client.HTTPSConnection if ziel.scheme == "https" else http.client.HTTPConnection
    with closing(art(ziel.netloc, timeout=TIMEOUT_S)) as verbindung:
        verbindung.request(methode, pfad, rumpf, kopf)
        a = verbindung.getresponse()
        csp, www = (a.headers.get_all(n, []) for n in ("Content-Security-Policy", "WWW-Authenticate"))
        return Antwort(a.status, a.headers, objekt(a.read()), csp, www)


def von_go(a, status) -> bool:
    """Fehlerseite der Go-API: erkennbar an deren CSP, nginx setzt keine solche."""
    return a.status == status and "default-src 'none'" in "".join(a.csp) and not a.kopf.get("Location")


def code_aus(a, state, basis) -> str:
    ziel = a.kopf.get("Location") or ""
    q = parse_qs(urlsplit(ziel).query)
    echt = ziel.startswith(RUECKSPRUNG + "?") and q.get("state") == [state] and q.get("iss") == [basis]
    return q.get("code", [""])[0] if a.status == 303 and echt else ""


def wetter_ok(a) -> bool:
    erg = a.objekt.get("result") or {}
    daten = objekt((erg.get("content") or [{}])[0].get("text"))
    stunden = daten.get("stunden") or []
    voll = stunden and all(s.get("zeit") and any(type(w) in (int, float) for w in s.values()) for s in stunden)
    return erg.get("isError") is False and bool(voll and (daten.get("ort") or {}).get("name"))


def pfadregeln(basis) -> list:
    """(Methode, Pfad, Rumpf, Regel); genau eine Registrierung je Lauf (Kontingent 20/h)."""
    hinweis = [f'Bearer resource_metadata="{basis}{META_RESSOURCE}{MCP}"']
    ressource = (200, basis + MCP, [basis])
    return [
        ("GET", META_SERVER, None, lambda a: a.status == 200 and a.objekt.get("issuer") == basis),
        *[("GET", pfad, None, lambda a: ressource == (
            a.status, a.objekt.get("resource"), a.objekt.get("authorization_servers")))
          for pfad in (META_RESSOURCE, META_RESSOURCE + MCP)],
        ("POST", MCP, {"jsonrpc": "2.0", "id": 1, "method": "ping"}, lambda a: a.status == 401 and a.www == hinweis),
        ("POST", REGISTER, {"client_name": "Staging-Probe", "redirect_uris": [RUECKSPRUNG]},
         lambda a: a.status == 201 and a.objekt.get("client_id")),
        ("GET", AUTHORIZE, None, lambda a: von_go(a, 400)),
        ("POST", TOKEN, "grant_type=authorization_code",
         lambda a: a.status in (400, 401) and a.objekt.get("error") in ("invalid_client", "invalid_grant")),
        *[("GET", pfad, None, lambda a: a.status == 401 and any(w.startswith("Basic ") for w in a.www))
          for pfad in GESPERRT],
        ("GET", INTERN, None, lambda a: a.status == 403)]


def anmelden(basis, env, konto) -> str:
    basic = base64.b64encode(f"{env['GZ_VALIDATOR_USER']}:{env['GZ_VALIDATOR_PASS']}".encode()).decode()
    daten = {"username": env[f"GZ_{konto}_USER"], "password": env[f"GZ_{konto}_PASS"]}
    a = rufe(basis, "POST", LOGIN, daten, Authorization=f"Basic {basic}")
    kekse = [c.split(";")[0] for c in a.kopf.get_all("Set-Cookie", []) if c.startswith("gz_session=")]
    if a.status != 200 or not kekse:
        raise Umgebungsfehler(f"{LOGIN}: Anmeldung GZ_{konto}_* abgelehnt (HTTP {a.status})")
    return kekse[0]


def pruefe_konto(basis, env, konto, client, frei, melde) -> None:
    pruefer, state = secrets.token_urlsafe(48), secrets.token_urlsafe(12)
    probe = base64.urlsafe_b64encode(hashlib.sha256(pruefer.encode()).digest()).rstrip(b"=").decode()
    felder = {"response_type": "code", "client_id": client, "redirect_uri": RUECKSPRUNG, "scope": "wetter",
              "code_challenge": probe, "code_challenge_method": "S256", "state": state, "resource": basis + MCP}
    kopf = {"Cookie": anmelden(basis, env, konto), "Origin": basis}
    a = rufe(basis, "GET", f"{AUTHORIZE}?{urlencode(felder)}", **kopf)
    if not melde(a.status == 200 if frei else von_go(a, 403), AUTHORIZE, f"GZ_{konto}_* GET (HTTP {a.status})"):
        return
    melde(not frei or a.csp == [CSP], AUTHORIZE, f"nicht genau die CSP der Go-API ({len(a.csp)} Header)")
    a = rufe(basis, "POST", AUTHORIZE, urlencode({**felder, "aktion": "erlauben"}), **kopf)
    code = code_aus(a, state, basis)
    if not melde(code if frei else von_go(a, 403), AUTHORIZE, f"GZ_{konto}_* POST (HTTP {a.status})") or not frei:
        return
    a = rufe(basis, "POST", TOKEN, urlencode({"grant_type": "authorization_code", "code": code, "client_id": client,
                                              "redirect_uri": RUECKSPRUNG, "code_verifier": pruefer}))
    token = a.objekt.get("access_token")
    if not melde(a.status == 200 and token, TOKEN, f"kein Token (HTTP {a.status})"):
        return
    kopf = {"Authorization": f"Bearer {token}", "Accept": "application/json, text/event-stream"}
    a = rufe(basis, "POST", MCP, {"jsonrpc": "2.0", "id": 1, "method": "tools/list"}, **kopf)
    namen = {w.get("name") for w in (a.objekt.get("result") or {}).get("tools") or []}
    melde({"ort_suchen", "wetter"} <= namen, MCP, f"Werkzeugliste unvollständig (HTTP {a.status})")
    # Ort in der Ortssuche eindeutig, siehe internal/resolver/testdata
    aufruf = {"name": "wetter", "arguments": {"ort": "Frankfurt am Main"}}
    a = rufe(basis, "POST", MCP, {"jsonrpc": "2.0", "id": 2, "method": "tools/call", "params": aufruf}, **kopf)
    melde(wetter_ok(a), MCP, f"Wetterantwort ohne Ortsname oder Stundenwerte (HTTP {a.status})")


def main(argv=None, *, env=None, basis=BASIS, server_merkmal=SERVER_MERKMAL) -> int:
    argv, env, befunde = sys.argv[1:] if argv is None else argv, os.environ if env is None else env, []

    def melde(ok, pfad, text) -> bool:
        if not ok:
            befunde.append(pfad)
            print(f"{pfad}: {text}")
        return bool(ok)

    try:
        fehlt = [v for v in VARIABLEN if not env.get(v)]
        if argv not in ([], ["--vor-freigabe"]):
            raise Umgebungsfehler("Unbekanntes Argument, erlaubt ist nur --vor-freigabe")
        if Path(server_merkmal).exists():
            raise Umgebungsfehler("Start auf dem Server: dessen IP umgeht die Schranke, Ergebnis ohne Aussage")
        if fehlt:
            raise Umgebungsfehler("Umgebung unvollständig: " + " ".join(fehlt))
        client, gebremst = "", False
        for methode, pfad, rumpf, regel in pfadregeln(basis):
            a = rufe(basis, methode, pfad, rumpf)
            if pfad == REGISTER:
                client, gebremst = a.objekt.get("client_id", ""), a.status == 429
            erfuellt = regel(a) or (pfad == REGISTER and gebremst)
            melde(erfuellt, pfad, f"Soll ohne Zugangsdaten verfehlt (HTTP {a.status})")
        if gebremst:
            raise Umgebungsfehler(f"{REGISTER}: Registrierungskontingent erschöpft (HTTP 429), später wiederholen")
        for konto in ("AUTH", "STAGING_ADMIN") if client else ():
            pruefe_konto(basis, env, konto, client, konto == "AUTH" and not argv, melde)
    except Exception as e:  # noqa: BLE001 - fremde Ausnahmetexte können Geheimnisse tragen (Headerwerte)
        print(e if isinstance(e, Umgebungsfehler) else f"Abbruch ({type(e).__name__})", file=sys.stderr)
        return 2
    print(f"NICHT BESTANDEN: {len(befunde)} Befund(e)" if befunde else "BESTANDEN")
    return 1 if befunde else 0


if __name__ == "__main__":
    sys.exit(main())
