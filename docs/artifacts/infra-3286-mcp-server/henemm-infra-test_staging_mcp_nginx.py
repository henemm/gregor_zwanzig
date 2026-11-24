"""Textvertrag der MCP-Pfade in der Staging-nginx-Datei (gregor_zwanzig#3286).

Nur Regressionsschutz, kein Verhaltensnachweis: das Verhalten belegt die Außen-Probe
``.claude/tools/staging_mcp_pruefen.py`` im Repo gregor_zwanzig.

Ausführen: python3 -m pytest tests/test_staging_mcp_nginx.py -v
"""

import re
from pathlib import Path

import pytest

CONF = Path(__file__).resolve().parent.parent / "nginx" / "staging.gregor20.henemm.com.conf"

BLOECKE = {
    "= /api/mcp": "8091",
    "^~ /api/mcp/oauth/": "8091",
    "^~ /.well-known/oauth-": "3001",
}
KOPFZEILEN = [
    "proxy_set_header Host $host;",
    "proxy_set_header X-Real-IP $remote_addr;",
    "proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;",
    "proxy_set_header X-Forwarded-Proto $scheme;",
]


def _conf():
    """Conf ohne Kommentare, damit ein Kommentar keine Zusicherung erfüllt."""
    return re.sub(r"(?m)#.*$", "", CONF.read_text(encoding="utf-8"))


def _block(name):
    treffer = re.findall(r"location\s+" + re.escape(name) + r"\s*\{([^{}]*)\}", _conf())
    assert len(treffer) == 1, f"location {name}: {len(treffer)} Blöcke, erwartet genau 1"
    return treffer[0]


@pytest.mark.parametrize("name", BLOECKE)
def test_schranke_ist_aus(name):
    assert "auth_basic off;" in _block(name)


@pytest.mark.parametrize("name,port", BLOECKE.items())
def test_ziel(name, port):
    assert f"proxy_pass http://127.0.0.1:{port};" in _block(name)


@pytest.mark.parametrize("zeile", KOPFZEILEN)
@pytest.mark.parametrize("name", BLOECKE)
def test_kopfzeilen(name, zeile):
    """X-Real-IP trägt die Registrierungsbremse in Go (AC-8)."""
    assert zeile in _block(name)


@pytest.mark.parametrize("verboten", ["satisfy", "allow", "deny", "limit_req", "proxy_buffering"])
@pytest.mark.parametrize("name", BLOECKE)
def test_keine_sperren_aus_den_nachbarbloecken(name, verboten):
    """satisfy any + deny all sperrt mit auth_basic off alle; limit_req: henemm-infra#397."""
    assert not re.search(rf"(?m)^\s*{verboten}\b", _block(name))


def test_mcp_wartet_laenger_als_der_laengste_aufruf():
    """10 s Ortssuche + 5 s Kontingent + 60 s Core = 75 s; nginx-Standard 60 s (AC-7)."""
    assert "proxy_read_timeout 120s;" in _block("= /api/mcp")


def test_nur_die_bekannten_bloecke_sind_offen():
    """Keine Öffnung nebenbei, auch nicht von /login."""
    offen = {n.strip() for n, b in re.findall(r"location\s+([^{]+)\{([^{}]*)\}", _conf()) if "auth_basic off" in b}
    assert offen == {"= /api/health", "/api/webhooks/telegram/", "/api/webhooks/sms/",
                     "/api/webhooks/mail/", *BLOECKE}


SERVER_IP = ["satisfy any;", "allow 178.104.143.19;", "allow 2a01:4f8:1c18:3591::1;", "deny all;"]
ZUGRIFF = {
    "/api/webhooks/telegram/": ["allow 149.154.160.0/20;", "allow 91.108.4.0/22;", "deny all;"],
    "/api/webhooks/sms/": ["allow 195.201.160.143;", "allow 2a01:4f8:13a:8e7::2;", "deny all;"],
    "/api/internal/": ["deny all;"],
    "/api/": SERVER_IP,
    "/": SERVER_IP,
}


def test_schranke_auf_server_ebene():
    """Alles ohne eigenen Block erbt die Schranke; auf Server-Ebene steht nur sie."""
    ausserhalb = re.sub(r"location\s+[^{]+\{[^{}]*\}", "", _conf())
    assert re.findall(r"\b(?:auth_basic|auth_basic_user_file|satisfy|allow|deny)\s[^;]*;", ausserhalb) == [
        'auth_basic "Staging";', "auth_basic_user_file /etc/nginx/htpasswd-staging;"]


def test_zugriffslisten_wie_bestand():
    """Reihenfolge zählt (nginx wertet die erste passende Zeile); kein Block darüber hinaus."""
    gefunden = {n.strip(): re.findall(r"\b(?:satisfy|allow|deny)\s[^;]*;", b)
                for n, b in re.findall(r"location\s+([^{]+)\{([^{}]*)\}", _conf())}
    assert {n: z for n, z in gefunden.items() if z} == ZUGRIFF
