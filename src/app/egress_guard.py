"""Zentraler Egress-Waechter (Issue #1337, Scheibe A).

Spec: docs/specs/modules/egress_guard.md

Patcht in Test/Staging die drei Transport-Primitive (`httpx.HTTPTransport.
handle_request`, `smtplib.SMTP.connect`, `imaplib.IMAP4.open`), damit jeder
ausgehende Ruf an einen Host laeuft, der explizit als `TEST_ACCESS` oder
`BLOCKED` deklariert ist. Undeklarierte Hosts sind ein Tripwire
(`EgressBlockedError`). In Prod ist der Guard ein reiner No-Op.
"""
from __future__ import annotations

import imaplib
import smtplib
from enum import Enum
from typing import Any

import httpx


class IsolationKind(Enum):
    """Deklarierte Isolationsart je Host."""

    TEST_ACCESS = "test_access"
    BLOCKED = "blocked"


class EgressBlockedError(Exception):
    """Wird geworfen, wenn ein Host nicht als TEST_ACCESS deklariert ist."""


INVENTORY: dict[str, IsolationKind] = {
    "api.open-meteo.com": IsolationKind.TEST_ACCESS,
    "air-quality-api.open-meteo.com": IsolationKind.TEST_ACCESS,
    "dataset.api.hub.geosphere.at": IsolationKind.TEST_ACCESS,
    "warnungen.zamg.at": IsolationKind.TEST_ACCESS,
    "api.brightsky.dev": IsolationKind.TEST_ACCESS,
    "radar-api.protezionecivile.it": IsolationKind.TEST_ACCESS,
    "api.meteoalarm.org": IsolationKind.TEST_ACCESS,
    "public-api.meteofrance.fr": IsolationKind.TEST_ACCESS,
    "www.risque-prevention-incendie.fr": IsolationKind.TEST_ACCESS,
    "gateway.seven.io": IsolationKind.BLOCKED,
    "api.telegram.org": IsolationKind.BLOCKED,
    "mail.henemm.com": IsolationKind.TEST_ACCESS,
}

_LOCALHOST_HOSTS = {"localhost", "127.0.0.1"}

# Wahre Original-Referenzen, einmalig beim Modul-Import eingefangen. Dient als
# Restore-Ziel fuer uninstall() -- unabhaengig davon, was zwischenzeitlich
# (z.B. durch Test-Sentinels) auf den Klassenattributen sitzt.
_TRUE_ORIG_HTTPX_HANDLE_REQUEST: Any = httpx.HTTPTransport.handle_request
_TRUE_ORIG_SMTP_CONNECT: Any = smtplib.SMTP.connect
_TRUE_ORIG_IMAP_OPEN: Any = imaplib.IMAP4.open

_installed = False
_dynamic_test_hosts: set[str] = set()

# Call-through-Ziele: die Funktion, die direkt UNTER dem Guard-Patch sass, im
# Moment des install()-Aufrufs (kann ein Test-Sentinel sein).
_orig_httpx_handle_request: Any = None
_orig_smtp_connect: Any = None
_orig_imap_open: Any = None


def _is_allowed(host: str | None) -> bool:
    if not host:
        return False
    if host in _LOCALHOST_HOSTS:
        return True
    if host in _dynamic_test_hosts:
        return True
    return INVENTORY.get(host) is IsolationKind.TEST_ACCESS


def _guarded_httpx_handle_request(self, request):  # noqa: ANN001
    host = request.url.host
    if _is_allowed(host):
        return _orig_httpx_handle_request(self, request)
    raise EgressBlockedError(f"httpx egress blocked for host: {host}")


def _guarded_smtp_connect(self, host="localhost", port=0, source_address=None):
    if _is_allowed(host):
        return _orig_smtp_connect(self, host, port, source_address)
    raise EgressBlockedError(f"smtplib egress blocked for host: {host}")


def _guarded_imap_open(self, host="", port=143, timeout=None):
    if _is_allowed(host):
        return _orig_imap_open(self, host, port, timeout)
    raise EgressBlockedError(f"imaplib egress blocked for host: {host}")


def install_egress_guard(settings) -> None:
    """Patcht die drei Transport-Primitive, wenn Test/Staging aktiv ist.

    No-Op in Prod (kein `is_test_mode` und `env != "staging"`) sowie bei
    wiederholtem Aufruf (Idempotenz).
    """
    global _installed, _orig_httpx_handle_request, _orig_smtp_connect
    global _orig_imap_open

    if not (settings.is_test_mode or settings.env == "staging"):
        return
    if _installed:
        return

    for host in (getattr(settings, "test_smtp_host", None), getattr(settings, "imap_host", None)):
        if host:
            _dynamic_test_hosts.add(host)

    _orig_httpx_handle_request = httpx.HTTPTransport.handle_request
    _orig_smtp_connect = smtplib.SMTP.connect
    _orig_imap_open = imaplib.IMAP4.open

    httpx.HTTPTransport.handle_request = _guarded_httpx_handle_request
    smtplib.SMTP.connect = _guarded_smtp_connect
    imaplib.IMAP4.open = _guarded_imap_open

    _installed = True


def uninstall_egress_guard() -> None:
    """Stellt die wahren Original-Referenzen wieder her (Restore-Kette)."""
    global _installed

    httpx.HTTPTransport.handle_request = _TRUE_ORIG_HTTPX_HANDLE_REQUEST
    smtplib.SMTP.connect = _TRUE_ORIG_SMTP_CONNECT
    imaplib.IMAP4.open = _TRUE_ORIG_IMAP_OPEN

    _installed = False
    _dynamic_test_hosts.clear()
