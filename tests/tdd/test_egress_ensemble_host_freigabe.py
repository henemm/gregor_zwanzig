"""TDD RED — Ensemble-Host im Egress-Inventar (Issue #3348).

Spec: docs/specs/modules/fix_3348_ensemble_egress.md (AC-1 bis AC-4).

Symptom aus Nutzersicht: Auf Staging fehlt die Großwetterlage in jeder
Trip-Mail, weil der Egress-Wächter den Ensemble-Abruf an
``ensemble-api.open-meteo.com`` sperrt (Staging-Log: ``Ensemble fetch failed:
httpx egress blocked for host: ensemble-api.open-meteo.com``). Ohne
Ensemble-Werte bleibt ``confidence_pct`` leer und ``stability_result`` None.

Beweisführung ohne Netz und ohne Mock-Theater: Das echte Transport-Primitiv
``httpx.HTTPTransport.handle_request`` wird VOR ``install_egress_guard()`` durch
einen Netzersatz ersetzt, der eine echte, aufgezeichnete Ensemble-Antwort
(Fixture) zurückgibt. Der Guard wrappt danach genau diesen Ersatz. Der
Provider läuft über seinen echten ``httpx.Client`` (echter HTTPTransport) —
also exakt über den Weg, den der Wächter auf Staging bewacht. Sperrt der
Wächter, wirft er ``EgressBlockedError``, der Provider schluckt ihn
(best-effort) und liefert ``{}`` — genau das Staging-Symptom.
"""
from __future__ import annotations

import contextlib
import json
from pathlib import Path
from typing import List

import httpx
import pytest

from app.config import Location, Settings
from app.egress_guard import (
    INVENTORY,
    EgressBlockedError,
    IsolationKind,
    install_egress_guard,
    uninstall_egress_guard,
)

_TRUE_ORIG_HTTPX_HANDLE_REQUEST = httpx.HTTPTransport.handle_request

ENSEMBLE_HOST = "ensemble-api.open-meteo.com"

_FIXTURE_PATH = (
    Path(__file__).resolve().parents[1]
    / "fixtures"
    / "openmeteo_ensemble"
    / "wolayersee_2026-09-19_weather_code.json"
)

_WOLAYERSEE = Location(latitude=46.61, longitude=12.87, name="Wolayersee", elevation_m=1950)


class AssertedNetworkTouch(Exception):
    """Netzersatz wurde erreicht, obwohl der Guard hätte sperren müssen."""


@pytest.fixture(autouse=True)
def _restore_transport():
    yield
    with contextlib.suppress(Exception):
        uninstall_egress_guard()
    httpx.HTTPTransport.handle_request = _TRUE_ORIG_HTTPX_HANDLE_REQUEST


def _frischer_guard_zustand() -> None:
    """Der globale conftest-Guard ist bereits installiert (idempotent). Damit
    der Guard unseren Netzersatz als "Original" wrappt, wird er hier zuerst
    abgebaut und nach dem Setzen des Ersatzes neu installiert."""
    uninstall_egress_guard()


def _install_replay_transport(seen: List[httpx.Request]) -> None:
    """Netzersatz: liefert die echte aufgezeichnete Ensemble-Antwort."""
    _frischer_guard_zustand()
    payload = json.loads(_FIXTURE_PATH.read_text())

    def _replay(self, request):  # noqa: ANN001
        seen.append(request)
        return httpx.Response(200, json=payload, request=request)

    httpx.HTTPTransport.handle_request = _replay


def _install_touch_sentinel() -> None:
    _frischer_guard_zustand()
    def _sentinel(self, request):  # noqa: ANN001
        raise AssertedNetworkTouch(f"transport reached for {request.url.host}")

    httpx.HTTPTransport.handle_request = _sentinel


def test_ac1_ensemble_abruf_kommt_durch_den_staging_waechter(monkeypatch, tmp_path):
    """GIVEN der Egress-Wächter ist im Test-/Staging-Modus installiert
    WHEN der Open-Meteo-Provider seinen Ensemble-Abruf über den echten Client ausführt
    THEN erreicht die Anfrage an ensemble-api.open-meteo.com den Transport und
    der Provider liefert Ensemble-Statistiken (Grundlage für confidence_pct und
    damit die Großwetterlage) statt eines leeren Ergebnisses.

    RED heute: Host fehlt im Inventar -> EgressBlockedError -> Provider liefert {}.
    """
    from providers.openmeteo import OpenMeteoProvider

    monkeypatch.setattr(
        "providers.openmeteo.DIAGNOSTICS_PATH", tmp_path / "openmeteo_calls.jsonl"
    )
    seen: List[httpx.Request] = []
    _install_replay_transport(seen)
    install_egress_guard(Settings(is_test_mode=True))

    provider = OpenMeteoProvider()
    result = provider._fetch_ensemble_spread(_WOLAYERSEE)

    assert seen and seen[0].url.host == ENSEMBLE_HOST, (
        "Der Ensemble-Abruf hat den Transport nie erreicht — der Egress-Wächter "
        f"sperrt {ENSEMBLE_HOST} (Staging-Symptom #3348)."
    )
    assert result, "Provider lieferte keine Ensemble-Statistik (leeres Ergebnis)."
    assert any(
        s.spread_t2m_k is not None for s in result.values()
    ), "Keine Stunde mit Temperatur-Streuung — confidence_pct bliebe leer."


def test_ac1_ensemble_host_ist_test_access_wie_der_haupt_host():
    """GIVEN das Python-Inventar
    THEN steht der Ensemble-Host mit derselben Isolationsart wie api.open-meteo.com.
    """
    assert INVENTORY.get(ENSEMBLE_HOST) is IsolationKind.TEST_ACCESS
    assert INVENTORY[ENSEMBLE_HOST] is INVENTORY["api.open-meteo.com"]


@pytest.mark.parametrize(
    "host",
    [
        "seasonal-api.open-meteo.com",  # undeklarierter Nachbar desselben Anbieters
        "feeds.meteoalarm.org",  # Warn-Host, BLOCKED
    ],
)
def test_ac2_undeklarierte_und_warn_hosts_bleiben_gesperrt(host):
    """GIVEN der Wächter ist installiert
    WHEN ein undeklarierter Nachbar-Host oder ein Warn-Host gerufen wird
    THEN EgressBlockedError und der Transport wird nie erreicht.
    """
    _install_touch_sentinel()
    install_egress_guard(Settings(is_test_mode=True))

    with pytest.raises(EgressBlockedError):
        httpx.get(f"https://{host}/v1/x")


def test_ac4_prod_bleibt_unveraendert_kein_patch():
    """GIVEN Produktions-Einstellungen (kein Test-Modus, env != staging)
    WHEN install_egress_guard läuft
    THEN bleibt das Transport-Primitiv unangetastet (No-Op).
    """
    _frischer_guard_zustand()
    before = httpx.HTTPTransport.handle_request
    install_egress_guard(Settings(is_test_mode=False, env="production"))
    assert httpx.HTTPTransport.handle_request is before
