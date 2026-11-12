"""Mail-Validatoren akzeptieren nur Mails des Dienst-Absenders (#2961).

Spec: docs/specs/modules/security_haertung_2026_11_repo_ci.md (AC-5, AC-6)

Das Test-Postfach ist geteilt; eine fremde, juengere Mail mit passenden
Marker-Koepfen darf nie die Pruefung einer echten Mail ersetzen. Die Mails
hier sind echte RFC-822-Texte, das Postfach ist das kleine IMAP-Double der
bestehenden Auswahl-Tests (Test-Seam ``imap=``). Der Render-Test laeuft in
echtem Headless-Chromium gegen einen lokalen HTTP-Empfaenger und prueft, dass
weder JavaScript laeuft noch eine Netzanfrage das Haus verlaesst.
"""
from __future__ import annotations

import http.server
import importlib.util
import sys
import threading
from email import message_from_string
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOKS = ROOT / ".claude" / "hooks"
sys.path.insert(0, str(HOOKS))

import _mail_trust  # noqa: E402
from tests.fixtures.authentication_results_fixtures import (  # noqa: E402
    AR_DKIM_PASS_NO_D,
    AR_FAIL,
    AR_FOREIGN_AUTHSERV,
    AR_H1_NORMAL,
    AR_H1_SPF_SWAPPED,
    AR_H2_INJECTION,
    AR_H3_ESCAPED_QUOTE,
    AR_H4_RESEND,
    AR_MAILFROM_FAIL_HELO_PASS,
    AR_SPF_PASS_NO_SCOPE,
    PROD_AUTHSERV_ID,
    TEST_AUTHSERV_ID,
)

DIENST = "gregor-test@henemm.com"
SERVER = "mail.henemm.com"
VERTRAUEN = _mail_trust.Vertrauen(frozenset({DIENST}), SERVER)
TYPEN = {
    "briefing_mail_validator": "trip-briefing",
    "email_spec_validator": "compare",
    "official_alert_mail_validator": "official-alert",
    "radar_alert_mail_validator": "radar-alert",
}


def _validator(name: str):
    spec = importlib.util.spec_from_file_location(f"{name}_vertrauen", HOOKS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _roh(von: str, typ: str, betreff: str, auth: str | None = None) -> str:
    koepfe = []
    if auth is not None:
        koepfe.append(f"Authentication-Results: {auth}")
    koepfe += [
        f"From: Gregor <{von}>",
        "To: gregor-test+lauf@henemm.com",
        f"Subject: {betreff}",
        f"X-GZ-Mail-Type: {typ}",
        "X-GZ-Format: full",
        "X-GZ-Lang: de",
        "Content-Type: text/plain; charset=utf-8",
    ]
    return "\n".join(koepfe) + "\n\nInhalt\n"


class _Postfach:
    """Minimales IMAP-Double: Mails (roh) in Eingangsreihenfolge, id = 1..n."""

    def __init__(self, rohmails: list[str]):
        self._roh = [r.encode() for r in rohmails]

    def select(self, _box):
        return "OK", [b""]

    def search(self, _charset, _kriterium):
        return "OK", [b" ".join(str(i + 1).encode() for i in range(len(self._roh)))]

    def fetch(self, mid, teil):
        roh = self._roh[int(mid) - 1]
        if "HEADER" in teil:
            return "OK", [(b"", roh.split(b"\n\n", 1)[0] + b"\n\n")]
        return "OK", [(b"", roh)]

    def close(self):
        pass

    def logout(self):
        pass


def _hole(name: str, box: _Postfach):
    mod = _validator(name)
    if name == "email_spec_validator":
        return mod._fetch_latest_message(
            imap=box, ignore_mail_age_reason="Test ohne Server-Zeit", vertrauen=VERTRAUEN)
    return mod.fetch_latest_message(imap=box, vertrauen=VERTRAUEN)


@pytest.mark.parametrize("name", list(TYPEN))
def test_juengere_fremde_mail_verdraengt_die_echte_nicht(name):
    """AC-5: Given echte Mail und danach eine fremde mit gleichen Markern /
    When der Validator waehlt / Then nimmt er die echte."""
    typ = TYPEN[name]
    box = _Postfach([_roh(DIENST, typ, "echt"), _roh("angreifer@example.org", typ, "fremd")])
    assert _hole(name, box)["Subject"] == "echt"


@pytest.mark.parametrize("name", list(TYPEN))
def test_nur_fremde_mail_ist_kein_treffer(name):
    """AC-5: nur eine fremde Mail im Postfach -> Fehler mit Absender-Grund."""
    box = _Postfach([_roh("angreifer@example.org", TYPEN[name], "fremd")])
    with pytest.raises(ValueError, match="ABSENDER"):
        _hole(name, box)


@pytest.mark.parametrize("name", list(TYPEN))
def test_gefaelschter_absender_scheitert_an_dkim_spf_des_eigenen_servers(name):
    """AC-5: From stimmt, aber der eigene Server meldet DKIM/SPF fail -> verworfen."""
    auth = f"{SERVER}; dkim=fail header.d=henemm.com; spf=fail smtp.mailfrom=henemm.com"
    box = _Postfach([_roh(DIENST, TYPEN[name], "gefaelscht", auth)])
    with pytest.raises(ValueError, match="AUTHENTISIERUNG"):
        _hole(name, box)


@pytest.mark.parametrize("name", list(TYPEN))
def test_echte_mail_mit_dkim_pass_wird_gewaehlt(name):
    auth = f"{SERVER}; dkim=pass header.d=henemm.com; spf=pass smtp.mailfrom=henemm.com"
    box = _Postfach([_roh(DIENST, TYPEN[name], "echt", auth)])
    assert _hole(name, box)["Subject"] == "echt"


def _kopf(roh: str):
    return message_from_string(roh)


def _mit(auth: str | None, von: str = DIENST, server: str = SERVER):
    """(Grund, Warnung) fuer eine Mail mit diesem Authentication-Results-Kopf;
    IMAP-Faltung ``\\r\\n\\t`` wird zur RFC-822-Folgezeile."""
    kopf = None if auth is None else auth.replace("\r\n", "\n")
    v = _mail_trust.Vertrauen(frozenset({DIENST}), server)
    return _mail_trust.pruefen(_kopf(_roh(von, "compare", "x", kopf)), v)


def test_absender_regeln():
    ok = _roh(DIENST, "compare", "x")
    assert _mail_trust.pruefen(_kopf(ok), VERTRAUEN) == (None, None)
    # Gross-/Kleinschreibung der Adresse ist egal
    assert _mit(None, von=DIENST.upper()) == (None, None)
    # zwei From-Koepfe
    grund, _ = _mail_trust.pruefen(_kopf("From: <a@example.org>\n" + ok), VERTRAUEN)
    assert "genau ein From" in grund
    # fremde Domain: Ablehnung
    grund, _ = _mit(None, von="angreifer@example.org")
    assert grund.startswith("ABSENDER")
    # eigene Domain, nicht gelistet: Warnung, keine Ablehnung
    grund, warnung = _mit(None, von="gregor_zwanzig@henemm.com")
    assert grund is None and "nicht als Dienst-Absender gelistet" in warnung
    # kein Absender ermittelbar: Warnung statt Ablehnung (fail-soft)
    leer = _mail_trust.Vertrauen(frozenset(), SERVER)
    grund, warnung = _mail_trust.pruefen(_kopf(ok), leer)
    assert grund is None and "kein Dienst-Absender ermittelbar" in warnung


@pytest.mark.parametrize("auth", [AR_H1_NORMAL, AR_H1_SPF_SWAPPED])
def test_helo_permerror_neben_mailfrom_pass_wird_akzeptiert(auth):
    """Echter Staging-/Prod-Kopf: spf=permerror im HELO-Scope + spf=pass mailfrom."""
    assert _mit(auth, server=PROD_AUTHSERV_ID) == (None, None)


def test_resend_dkim_pass_wird_akzeptiert():
    """Echte Resend-Zustellung (dkim=pass header.d=henemm.com header.s=resend)."""
    assert _mit(AR_H4_RESEND, von="gregor_zwanzig@henemm.com", server=PROD_AUTHSERV_ID)[0] is None


def test_ohne_kopf_entfaellt_die_teilpruefung():
    """Port 587 traegt strukturell keinen Kopf."""
    assert _mit(None) == (None, None)


def test_kopf_eines_fremden_servers_zaehlt_nicht():
    assert _mit(AR_FOREIGN_AUTHSERV, server=TEST_AUTHSERV_ID.replace("test", "x"))[0] is None


@pytest.mark.parametrize("auth", [AR_FAIL, AR_MAILFROM_FAIL_HELO_PASS, AR_SPF_PASS_NO_SCOPE,
                                  AR_DKIM_PASS_NO_D])
def test_nicht_bestaetigte_domain_wird_verworfen(auth):
    """mailfrom-fail, nur HELO-pass, scope-lose bzw. nicht ausgerichtete Ergebnisse."""
    grund, _ = _mit(auth, server=TEST_AUTHSERV_ID)
    assert grund and grund.startswith("AUTHENTISIERUNG")


def test_fremde_header_d_ohne_ausrichtung_wird_verworfen():
    auth = (f"{TEST_AUTHSERV_ID}; spf=pass smtp.mailfrom=a@attacker.example; "
            "dkim=pass header.d=attacker.example; dmarc=fail header.from=henemm.com")
    grund, _ = _mit(auth, server=TEST_AUTHSERV_ID)
    assert grund and grund.startswith("AUTHENTISIERUNG")


@pytest.mark.parametrize("auth", [AR_H2_INJECTION, AR_H3_ESCAPED_QUOTE])
def test_injektion_ueber_quotes_wird_verworfen(auth):
    grund, _ = _mit(auth, server=PROD_AUTHSERV_ID)
    assert grund and "unlesbar" in grund


def test_absender_kommt_aus_der_versandkonfiguration(monkeypatch):
    """AC-5: der erwartete Absender ist der, den der Versand selbst setzt; auf
    Staging ist das das Konto des Test-Postfachs (fix-2542, Staging-.env)."""
    from app.config import Settings

    monkeypatch.delenv(_mail_trust.ENV_ABSENDER, raising=False)
    s = Settings(_env_file=None, test_smtp_user="gregor-test", test_smtp_pass="platzhalter",
                 mail_server_hostname=SERVER)
    v = _mail_trust.aus_settings(s)
    assert DIENST in v.absender and v.authserv_id == SERVER
    # nur der Postfach-Zugang, den der Validator ohnehin braucht, genuegt
    nur_imap = Settings(_env_file=None, test_imap_user="gregor-test")
    assert DIENST in _mail_trust.aus_settings(nur_imap).absender
    monkeypatch.setenv(_mail_trust.ENV_ABSENDER, "Dienst@Example.org, zweiter@example.org")
    v = _mail_trust.aus_settings(s)
    assert v.absender == {"dienst@example.org", "zweiter@example.org"}


# --- Render ohne JavaScript und ohne Netz ---------------------------------------


class _Zaehler(http.server.BaseHTTPRequestHandler):
    anfragen: list = []

    def do_GET(self):  # noqa: N802
        _Zaehler.anfragen.append(self.path)
        self.send_response(200)
        self.send_header("Content-Type", "image/png")
        self.end_headers()

    def log_message(self, *_args):
        pass


def test_render_laeuft_ohne_javascript_und_ohne_netz():
    """AC-6: Given Mail-HTML mit Skript und externem Bild / When der Briefing-
    Validator rendert / Then laeuft das Skript nicht und keine Anfrage verlaesst
    den Browser."""
    mod = _validator("briefing_mail_validator")
    server = http.server.HTTPServer(("127.0.0.1", 0), _Zaehler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    _Zaehler.anfragen = []
    port = server.server_address[1]
    html = (
        "<html><body>"
        f'<img src="http://127.0.0.1:{port}/pixel.png">'
        '<table data-table="resp"><tr><td>08:00</td><td>12</td></tr></table>'
        "<script>document.querySelector('table').remove();"
        f"fetch('http://127.0.0.1:{port}/js');</script>"
        "</body></html>"
    )
    try:
        fehler = mod._check_rendered(html)
    except mod.RenderUnavailable as exc:
        pytest.skip(f"kein Headless-Chromium: {exc}")
    finally:
        server.shutdown()
    assert _Zaehler.anfragen == [], f"Netzanfragen aus dem Render: {_Zaehler.anfragen}"
    assert not any("keine Wetterdaten-Tabelle" in f for f in fehler), (
        f"Skript lief (Tabelle entfernt): {fehler}"
    )
