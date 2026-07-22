"""TDD RED — Warn-Dienst-Isolation (Issue #1348 Scheibe 2b).

Spec: docs/specs/modules/warn_service_isolation.md ("## Acceptance Criteria",
AC-1 und AC-2).

Ziel: Beweisen, dass die vier amtlichen Warn-Host im Egress-Wächter auf
``BLOCKED`` stehen MÜSSEN — Test/Staging dürfen die echten Warn-APIs nicht mehr
erreichen (Kontingent-Schonung des geteilten Server-IP/Key).

Beweisführung ohne echten Netzwerk-Touch (kein Mock-Theater), exakt nach dem
Muster aus ``test_egress_guard.py``: VOR ``install_egress_guard()`` wird
``httpx.HTTPTransport.handle_request`` durch einen Sentinel ersetzt, der bei
Erreichen ``AssertedNetworkTouch`` wirft. Der Guard wrappt danach diesen
Sentinel als "Original":

- Host ist ``BLOCKED`` (Soll-Zustand) -> ``EgressBlockedError``, der Sentinel
  wird NIE erreicht (kein ``AssertedNetworkTouch``) = "vor dem Transport
  entschieden".
- Host ist ``TEST_ACCESS`` (Ist-Zustand HEUTE) -> Guard reicht durch, der
  Sentinel feuert ``AssertedNetworkTouch`` statt ``EgressBlockedError`` = ROT.

Erwartung in dieser Phase (TDD RED): die vier Warn-Host stehen im INVENTORY
noch auf ``TEST_ACCESS`` -> AC-1 und AC-2 sind ROT.

Zur conftest-autouse-Guard-Fixture (``_egress_guard`` in tests/conftest.py):
Dieses Modul ist NICHT von ihr ausgenommen (nur ``test_egress_guard`` ist es).
Die Fixture installiert den Guard also VOR jedem Test-Body — und zwar um das
WAHRE Original-Transport-Primitiv, nicht um unseren Sentinel. Deshalb setzt
jeder Test zuerst ``uninstall_egress_guard()`` (sauberer Ausgangszustand,
``_installed`` zurück), installiert DANN den Sentinel und ruft ERST DANACH
``install_egress_guard()`` — so umschließt der Guard kontrolliert unseren
Sentinel. Die conftest-Teardown ``uninstall_egress_guard()`` und die lokale
Restore-Fixture stellen anschließend die wahren Originale wieder her.
"""
from __future__ import annotations

import contextlib

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

# Die vier amtlichen Warn-Host, die von Test/Staging isoliert werden sollen.
WARN_HOSTS = [
    "api.meteoalarm.org",
    "warnungen.zamg.at",
    "public-api.meteofrance.fr",
    "www.risque-prevention-incendie.fr",
]

# Wetter-/Radar-Host: bleiben bewusst TEST_ACCESS (dürfen NICHT mitblockiert
# werden — Isolation der Warn-APIs, nicht der Wetter-/Radar-Quellen).
WEATHER_RADAR_HOSTS = [
    "dataset.api.hub.geosphere.at",
    "api.brightsky.dev",
    "radar-api.protezionecivile.it",
]

# Wahre Original-Referenz, VOR jeglicher Manipulation eingefangen.
_TRUE_ORIG_HTTPX_HANDLE_REQUEST = httpx.HTTPTransport.handle_request


class AssertedNetworkTouch(Exception):
    """Wird vom Sentinel geworfen, sobald der httpx-Transport den (simulierten)
    echten Netzwerk-Layer erreicht. Beweist "durchgelassen" ohne einen echten
    Byte-Transport."""


def _install_httpx_sentinel() -> None:
    def _sentinel(self, request):  # noqa: ANN001 - Sentinel-Signatur egal
        raise AssertedNetworkTouch(f"httpx transport reached for {request.url.host}")

    httpx.HTTPTransport.handle_request = _sentinel


@pytest.fixture(autouse=True)
def _restore_transport_after_each_test():
    """Test-Hygiene: nach jedem Test ist das httpx-Transport-Primitiv wieder auf
    die wahre Original-Referenz zurückgesetzt — kein Sentinel/Guard-Leck in
    Folgetests."""
    yield
    with contextlib.suppress(Exception):
        uninstall_egress_guard()
    httpx.HTTPTransport.handle_request = _TRUE_ORIG_HTTPX_HANDLE_REQUEST


def _arm_guard_over_sentinel() -> None:
    """Sauberer Ausgangszustand trotz conftest-Vor-Install, dann Guard über den
    Sentinel legen: uninstall (setzt ``_installed`` zurück) -> Sentinel setzen
    -> install (Guard wrappt den Sentinel als Call-through-Ziel)."""
    uninstall_egress_guard()
    _install_httpx_sentinel()
    install_egress_guard(Settings(is_test_mode=True))


# ---------------------------------------------------------------------------
# AC-1 — mit aktivem Guard wirft ein Request an einen Warn-Host
# EgressBlockedError; der Sentinel-Transport wird NIE erreicht.
# ROT HEUTE: Host ist TEST_ACCESS -> Guard reicht durch -> Sentinel feuert
# AssertedNetworkTouch statt EgressBlockedError.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("host", WARN_HOSTS)
def test_warn_hosts_blocked(host):
    _arm_guard_over_sentinel()

    with pytest.raises(EgressBlockedError):
        httpx.get(f"https://{host}/")


# ---------------------------------------------------------------------------
# AC-2 — INVENTORY: die vier Warn-Host stehen auf BLOCKED; die Wetter-/Radar-
# Host bleiben TEST_ACCESS.
# ROT HEUTE: die vier Warn-Host sind TEST_ACCESS.
# ---------------------------------------------------------------------------


def test_inventory_warn_hosts_blocked():
    for host in WARN_HOSTS:
        assert INVENTORY[host] is IsolationKind.BLOCKED, (
            f"{host} muss BLOCKED sein (Warn-Isolation 2b), ist aber "
            f"{INVENTORY[host]}"
        )

    for host in WEATHER_RADAR_HOSTS:
        assert INVENTORY[host] is IsolationKind.TEST_ACCESS, (
            f"{host} ist Wetter-/Radar-Quelle und muss TEST_ACCESS bleiben, "
            f"ist aber {INVENTORY[host]}"
        )
