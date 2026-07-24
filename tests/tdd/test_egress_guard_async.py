"""TDD RED — Egress Guard, Async-Transport (Issue #1337, Scheibe Go-Prozess).

Spec: docs/specs/modules/egress_guard_go.md ("## Test Plan" Test 8/9;
"## Acceptance Criteria" AC-8, AC-9).

Beweisfuehrung identisch zu Scheibe A (``test_egress_guard.py``), nur auf dem
asynchronen Transport-Primitiv ``httpx.AsyncHTTPTransport.handle_async_request``:
VOR ``install_egress_guard()`` wird das Original durch einen Sentinel ersetzt,
der bei Erreichen ``AssertedNetworkTouch`` wirft. Damit ist ohne ein einziges
gesendetes Byte beweisbar:

- Guard blockt (undeklarierter Host) -> ``EgressBlockedError``, Sentinel NIE
  erreicht.
- Guard laesst durch (TEST_ACCESS-Host) -> Sentinel feuert = "durchgelassen".
- Prod -> ``handle_async_request`` bleibt referenz-identisch (kein Patch).

Kein Mock-Theater: reale Klassenmethoden-Ersetzung, realer ``httpx.AsyncClient``
als Aufrufweg aus Nutzersicht.

Erwartung in dieser Phase (TDD RED): ``install_egress_guard`` patcht den
Async-Transport noch nicht -> der Sentinel wird auch bei undeklariertem Host
erreicht (``AssertedNetworkTouch`` statt ``EgressBlockedError``) -> ROT.
"""
from __future__ import annotations

import asyncio

import httpx
import pytest

from app.config import Settings
from app.egress_guard import (
    EgressBlockedError,
    install_egress_guard,
    uninstall_egress_guard,
)

_TRUE_ORIG_ASYNC_HANDLE = httpx.AsyncHTTPTransport.handle_async_request

UNDECLARED_URL = "https://egress-tripwire.invalid/probe"
DECLARED_URL = "https://api.open-meteo.com/v1/forecast"


class AssertedNetworkTouch(Exception):
    """Sentinel-Signal: der (simulierte) echte Netzwerk-Layer wurde erreicht."""


def _install_async_sentinel() -> None:
    async def _sentinel(self, request):  # noqa: ANN001 - Sentinel-Signatur egal
        raise AssertedNetworkTouch(f"async transport reached for {request.url.host}")

    httpx.AsyncHTTPTransport.handle_async_request = _sentinel


def _restore_async_transport() -> None:
    httpx.AsyncHTTPTransport.handle_async_request = _TRUE_ORIG_ASYNC_HANDLE


@pytest.fixture
def async_guard():
    """Sentinel setzen, Guard darueber installieren, danach alles zuruecksetzen."""
    _install_async_sentinel()
    install_egress_guard(Settings(is_test_mode=True))
    try:
        yield
    finally:
        uninstall_egress_guard()
        _restore_async_transport()


def _async_get(url: str):
    async def _run():
        async with httpx.AsyncClient(timeout=1.0) as client:
            return await client.get(url)

    return asyncio.run(_run())


def test_async_undeclared_host_blocked(async_guard):
    """GIVEN Test-Modus und ein Host ohne Inventar-Deklaration
    WHEN ein Request ueber httpx.AsyncClient rausgeht
    THEN wirft der Guard EgressBlockedError und der Transport wird nie erreicht.
    """
    with pytest.raises(EgressBlockedError):
        _async_get(UNDECLARED_URL)


def test_async_declared_host_passes(async_guard):
    """GIVEN Test-Modus und ein als TEST_ACCESS deklarierter Host
    WHEN ein Request ueber httpx.AsyncClient rausgeht
    THEN laesst der Guard durch und der Sentinel-Transport feuert.
    """
    with pytest.raises(AssertedNetworkTouch):
        _async_get(DECLARED_URL)


def test_mixed_case_host_normalized():
    """GIVEN ein als TEST_ACCESS deklarierter Host in gemischter Schreibweise
    (F001: smtplib/imaplib bekommen den Host als rohes Argument, httpx-Redirects
    fremder Server liefern beliebiges Casing im Location-Header)
    WHEN die Entscheidungsregel _is_allowed geprueft wird
    THEN normalisiert sie den Host und laesst den deklarierten Host durch,
    waehrend ein BLOCKED-Host in gemischter Schreibweise geblockt bleibt.
    """
    from app.egress_guard import _is_allowed

    assert _is_allowed("Api.Open-Meteo.com") is True
    assert _is_allowed("Uptime.BetterStack.com") is False
    assert _is_allowed("LOCALHOST") is True


def test_async_prod_no_patch():
    """GIVEN Prod-Einstellungen (kein Test-Modus, env=production)
    WHEN install_egress_guard laeuft
    THEN bleibt handle_async_request referenz-identisch zum Original.
    """
    try:
        install_egress_guard(Settings(is_test_mode=False, env="production"))
        assert httpx.AsyncHTTPTransport.handle_async_request is _TRUE_ORIG_ASYNC_HANDLE
    finally:
        uninstall_egress_guard()
        _restore_async_transport()
