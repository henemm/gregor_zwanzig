"""TDD RED — Egress Guard (Issue #1337 Scheibe A).

Spec: docs/specs/modules/egress_guard.md ("## Test Plan", Test 1-8; "##
Acceptance Criteria", AC-1..AC-6).

Beweisfuehrung ohne echten Netzwerk-Touch (kein Mock-Theater): VOR
``install_egress_guard()`` wird das jeweilige Original-Transport-Primitiv
(``httpx.HTTPTransport.handle_request`` / ``smtplib.SMTP.connect`` /
``imaplib.IMAP4.open``) durch einen Sentinel ersetzt, der bei Erreichen eine
``AssertedNetworkTouch``-Exception wirft. Erst danach patcht der Guard die
Klassenmethode -- er wrappt damit unseren Sentinel als das "Original", auf das
er bei TEST_ACCESS/localhost durchreicht. So beweisen wir ohne ein einziges
gesendetes Byte:

- Guard blockt (undeklariert/BLOCKED) -> ``EgressBlockedError``, der Sentinel
  wird NIE erreicht (kein ``AssertedNetworkTouch``).
- Guard laesst durch (TEST_ACCESS/localhost) -> der Sentinel feuert
  ``AssertedNetworkTouch`` = Beweis "durchgelassen" ohne echte Verbindung.

KEINE Mocks/patch/MagicMock -- reale Klassenmethoden-Ersetzung plus reale aus
Nutzersicht aequivalente Aufrufe (``httpx.get``/``httpx.Client()``,
``smtplib.SMTP(...)``, ``imaplib.IMAP4(...)``) gegen den (nach Guard-Install)
gepatchten Entry-Point.

Erwartung in dieser Phase (TDD RED): ``src/app/egress_guard.py`` existiert
noch nicht -> ModuleNotFoundError bei Sammlung, alle Tests ROT.
"""
from __future__ import annotations

import contextlib
import imaplib
import smtplib

import httpx
import pytest

from app.config import Settings
from app.egress_guard import (
    INVENTORY,
    EgressBlockedError,
    IsolationKind,
    install_egress_guard,
    uninstall_egress_guard,
)

# Wahre Original-Referenzen, eingefangen VOR jeglicher Manipulation in diesem
# Modul -- Grundlage fuer Identitaetsvergleiche (AC-3) und die finale
# Restore-Pruefung (Test-Hygiene, s.u.).
_TRUE_ORIG_HTTPX_HANDLE_REQUEST = httpx.HTTPTransport.handle_request
_TRUE_ORIG_SMTP_CONNECT = smtplib.SMTP.connect
_TRUE_ORIG_IMAP_OPEN = imaplib.IMAP4.open


class AssertedNetworkTouch(Exception):
    """Wird vom Sentinel geworfen, sobald ein Transport-Primitiv den
    (simulierten) echten Netzwerk-Layer erreicht. Beweist "durchgelassen"
    ohne einen einzigen echten Byte-Transport."""


def _install_httpx_sentinel() -> None:
    def _sentinel(self, request):  # noqa: ANN001 - Sentinel-Signatur egal
        raise AssertedNetworkTouch(f"httpx transport reached for {request.url.host}")

    httpx.HTTPTransport.handle_request = _sentinel


def _install_smtp_sentinel() -> None:
    def _sentinel(self, host="localhost", port=0, source_address=None):
        raise AssertedNetworkTouch(f"smtplib connect reached for {host}")

    smtplib.SMTP.connect = _sentinel


def _install_imap_sentinel() -> None:
    def _sentinel(self, host="", port=143, timeout=None):
        raise AssertedNetworkTouch(f"imaplib open reached for {host}")

    imaplib.IMAP4.open = _sentinel


@pytest.fixture(autouse=True)
def _restore_transports_after_each_test():
    """Test-Hygiene PFLICHT (kein Bezug auf conftest.py, die Restore-Fixture
    ist Implementierungs-Scope und existiert noch nicht): egal was ein Test
    tut, danach sind alle drei Transport-Primitive wieder auf die wahren
    Original-Referenzen zurueckgesetzt -- kein Leck in andere Tests."""
    yield
    with contextlib.suppress(Exception):
        uninstall_egress_guard()
    httpx.HTTPTransport.handle_request = _TRUE_ORIG_HTTPX_HANDLE_REQUEST
    smtplib.SMTP.connect = _TRUE_ORIG_SMTP_CONNECT
    imaplib.IMAP4.open = _TRUE_ORIG_IMAP_OPEN


# ---------------------------------------------------------------------------
# Test 1 / AC-1 — Tripwire greift bei undeklariertem Host (httpx.get)
# ---------------------------------------------------------------------------


def test_undeclared_host_blocked_before_transport():
    _install_httpx_sentinel()
    settings = Settings(is_test_mode=True)
    install_egress_guard(settings)

    with pytest.raises(EgressBlockedError):
        httpx.get("http://undeclared-host.example.invalid/")


# ---------------------------------------------------------------------------
# Test 2 / AC-1 — gilt auch fuer einen selbstgebauten httpx.Client()
# ---------------------------------------------------------------------------


def test_undeclared_host_blocked_custom_client():
    _install_httpx_sentinel()
    settings = Settings(is_test_mode=True)
    install_egress_guard(settings)

    client = httpx.Client(transport=httpx.HTTPTransport())
    try:
        with pytest.raises(EgressBlockedError):
            client.get("http://another-undeclared.example.invalid/")
    finally:
        client.close()


# ---------------------------------------------------------------------------
# Test 3 / AC-2 — deklarierter TEST_ACCESS-Host laesst durch (smtplib)
# ---------------------------------------------------------------------------


def test_declared_test_access_host_passes_through():
    assert INVENTORY["mail.henemm.com"] is IsolationKind.TEST_ACCESS

    _install_smtp_sentinel()
    settings = Settings(is_test_mode=True)
    install_egress_guard(settings)

    with pytest.raises(AssertedNetworkTouch):
        smtplib.SMTP(host="mail.henemm.com", port=587)


# ---------------------------------------------------------------------------
# Test 4 / AC-3 — Prod-No-Op: kein Patch gesetzt
# ---------------------------------------------------------------------------


def test_prod_mode_installs_no_patch():
    original = httpx.HTTPTransport.handle_request

    settings = Settings(env="production", is_test_mode=False)
    install_egress_guard(settings)

    assert httpx.HTTPTransport.handle_request is original
    assert httpx.HTTPTransport.handle_request is _TRUE_ORIG_HTTPX_HANDLE_REQUEST
    assert smtplib.SMTP.connect is _TRUE_ORIG_SMTP_CONNECT
    assert imaplib.IMAP4.open is _TRUE_ORIG_IMAP_OPEN


# ---------------------------------------------------------------------------
# Test 5 / AC-4 — alle drei Primitive einzeln abgedeckt, kein Kurzschluss
# ---------------------------------------------------------------------------


def test_all_three_transports_covered():
    _install_httpx_sentinel()
    _install_smtp_sentinel()
    _install_imap_sentinel()

    settings = Settings(is_test_mode=True)
    install_egress_guard(settings)

    # httpx: undeklarierter Host (Tripwire-Pfad) -> EgressBlockedError, kein
    # Touch. Bewusst KEIN konkreter Inventar-Eintrag als Beispiel: jede
    # kuenftige Scheibe (D: Warn-Dienste, E: Resend) hebt weitere Hosts von
    # BLOCKED auf TEST_ACCESS -- der Tripwire-Pfad fuer undeklarierte Hosts
    # bleibt dagegen dauerhaft stabil (s. api.telegram.org-Flip, Issue #1363).
    with pytest.raises(EgressBlockedError):
        httpx.get("https://nicht-im-inventar.invalid/bot123/sendMessage")

    # smtplib: undeklarierter Host -> EgressBlockedError, kein Touch.
    with pytest.raises(EgressBlockedError):
        smtplib.SMTP(host="undeclared-smtp.example.invalid", port=25)

    # imaplib: deklarierter TEST_ACCESS-Host -> durchgelassen, Sentinel feuert.
    with pytest.raises(AssertedNetworkTouch):
        imaplib.IMAP4(host="mail.henemm.com", port=993)


# ---------------------------------------------------------------------------
# Test 6 / AC-5 — Idempotenz: zweiter install()-Aufruf patcht nicht doppelt
# ---------------------------------------------------------------------------


def test_double_install_is_idempotent():
    _install_httpx_sentinel()
    _install_smtp_sentinel()
    _install_imap_sentinel()

    settings = Settings(is_test_mode=True)
    install_egress_guard(settings)

    patched_http = httpx.HTTPTransport.handle_request
    patched_smtp = smtplib.SMTP.connect
    patched_imap = imaplib.IMAP4.open

    install_egress_guard(settings)

    assert httpx.HTTPTransport.handle_request is patched_http
    assert smtplib.SMTP.connect is patched_smtp
    assert imaplib.IMAP4.open is patched_imap

    # Die einzige Restore-Kette stellt trotz Doppel-Install die wahren
    # Originale vollstaendig wieder her.
    uninstall_egress_guard()
    assert httpx.HTTPTransport.handle_request is _TRUE_ORIG_HTTPX_HANDLE_REQUEST
    assert smtplib.SMTP.connect is _TRUE_ORIG_SMTP_CONNECT
    assert imaplib.IMAP4.open is _TRUE_ORIG_IMAP_OPEN


# ---------------------------------------------------------------------------
# Test 7 / AC-6 — localhost/127.0.0.1 ohne Deklaration durchgelassen
# ---------------------------------------------------------------------------


def test_localhost_passes_through_without_declaration():
    assert "localhost" not in INVENTORY
    assert "127.0.0.1" not in INVENTORY

    _install_httpx_sentinel()
    settings = Settings(is_test_mode=True)
    install_egress_guard(settings)

    with pytest.raises(AssertedNetworkTouch):
        httpx.get("http://127.0.0.1:8001/health")

    with pytest.raises(AssertedNetworkTouch):
        httpx.get("http://localhost:8001/health")


# ---------------------------------------------------------------------------
# Test 8 / Restore-Fixture-Verhalten — Original-Referenzen nach uninstall()
# ---------------------------------------------------------------------------


def test_uninstall_restores_originals():
    settings = Settings(is_test_mode=True)
    install_egress_guard(settings)

    assert httpx.HTTPTransport.handle_request is not _TRUE_ORIG_HTTPX_HANDLE_REQUEST
    assert smtplib.SMTP.connect is not _TRUE_ORIG_SMTP_CONNECT
    assert imaplib.IMAP4.open is not _TRUE_ORIG_IMAP_OPEN

    uninstall_egress_guard()

    assert httpx.HTTPTransport.handle_request is _TRUE_ORIG_HTTPX_HANDLE_REQUEST
    assert smtplib.SMTP.connect is _TRUE_ORIG_SMTP_CONNECT
    assert imaplib.IMAP4.open is _TRUE_ORIG_IMAP_OPEN


# ---------------------------------------------------------------------------
# Test 9 / Fix F001 (Adversary BROKEN) — der ECHTE Laufzeitprozess arm't den
# Guard. Der Waechter darf nicht nur in der Legacy-Debug-CLI (`src/app/cli.py`)
# haengen, sondern MUSS im produktiven Prozess `uvicorn api.main:app`
# (systemd `gregor-python-staging`) scharf sein. Beweis ohne Mock: die
# FastAPI-App im Staging-Modus per TestClient starten -> der lifespan-Startpfad
# ruft `install_egress_guard()`. Danach ist (a) das httpx-Transport-Primitiv
# real durch den Guard ersetzt und (b) ein Abruf an einen undeklarierten Host
# wirft `EgressBlockedError`. Bricht diese Verdrahtung weg, wird der Test rot.
# ---------------------------------------------------------------------------


def test_api_main_startup_arms_egress_guard_in_staging(monkeypatch):
    from app.egress_guard import _guarded_httpx_handle_request

    # Saubere Ausgangslage: der App-Start (nicht ein Test-Prolog) muss
    # installieren. Dieses Modul ist von der conftest-Guard-Fixture bewusst
    # ausgenommen, es gibt also keinen konkurrierenden Vor-Install.
    uninstall_egress_guard()
    assert httpx.HTTPTransport.handle_request is _TRUE_ORIG_HTTPX_HANDLE_REQUEST

    # Aktivierungsbedingung des Guards fuer den echten Prozess: GZ_ENV=staging.
    monkeypatch.setenv("GZ_ENV", "staging")

    from fastapi.testclient import TestClient

    from api.main import app

    with TestClient(app):
        # lifespan-Startup ist gelaufen -> der api.main-Bootstrap hat den Guard
        # scharf geschaltet. Identitaets- UND Verhaltensbeweis:
        assert httpx.HTTPTransport.handle_request is _guarded_httpx_handle_request
        with pytest.raises(EgressBlockedError):
            httpx.get("http://undeclared-host.example.invalid/")
