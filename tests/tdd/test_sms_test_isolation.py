"""TDD RED — Issue #1336 (Scheibe B von #1337): SMS-Egress-Isolation via
seven.io Sandbox-Key.

SPEC: docs/specs/modules/egress_guard_sms.md

`SMSOutput.send()` feuert heute bedingungslos an `gateway.seven.io`,
`for_testing()` fasst SMS gar nicht an. Diese Tests bauen das Vorbild aus
`telegram.py::_guard_test_mode_chat_id` (Issue #1288) 1:1 auf SMS nach: ein
neues Settings-Feld `seven_sandbox_key` (env `GZ_SEVEN_SANDBOX_KEY`), ein
Channel-Guard `_guard_test_mode_sandbox_key()` als erste Zeile in `send()`,
und die Inventar-Zeile `gateway.seven.io` in `egress_guard.INVENTORY` von
`BLOCKED` auf `TEST_ACCESS`.

Boundary-Sink auf `httpx.post` (Vorbild test_telegram_test_mode_guard.py) —
KEIN Live-seven.io-Call. Der Sentinel raised `AssertedNetworkTouch`, sobald
der Transport tatsaechlich erreicht wird — das beweist positiv (Test 3/5:
Sentinel FEUERT = durchgelassen) wie negativ (Test 1/2: Sentinel bleibt
stumm = der Guard hat VOR dem Transport entschieden), ohne dass ein Mock
die eigene Annahme zurueckspiegelt.

RED-Erwartung (vor Fix):
  - AC-1/AC-2: kein Guard existiert → send() laeuft ungebremst in den
    Sentinel statt in OutputConfigError zu enden → pytest.raises(OutputConfigError)
    schlaegt fehl (der Sentinel wirft stattdessen AssertedNetworkTouch).
  - AC-3: das Feld `seven_sandbox_key` existiert noch nicht auf Settings
    (extra="ignore" verwirft es beim Konstruieren still) → der Zugriff
    `settings.seven_sandbox_key` wirft AttributeError, bevor send() ueberhaupt
    gerufen wird.
  - AC-4: `for_testing()` faengt `seven_api_key` heute gar nicht an → bleibt
    unveraendert der Prod-Key statt auf den Sandbox-Key zu wechseln.
  - AC-5: die Guard-Methode `_guard_test_mode_sandbox_key` existiert noch
    nicht auf `SMSOutput` → `hasattr(...)` schlaegt fehl.
  - AC-6: `INVENTORY["gateway.seven.io"]` ist noch `BLOCKED`, nicht
    `TEST_ACCESS`.
"""
from __future__ import annotations

import httpx
import pytest

from app.config import Settings
from output.channels.base import OutputConfigError
from output.channels.sms import SMSOutput


class AssertedNetworkTouch(Exception):
    """Beweist, dass der HTTP-Transport tatsaechlich erreicht wurde — ob das
    im jeweiligen Test erwuenscht ist (Durchlass) oder ein Fehler waere
    (Guard haette vorher blockieren muessen), entscheidet der Testfall."""


def _make_sentinel(calls: list):
    """Sentinel fuer httpx.post: zeichnet den Aufruf auf und wirft
    AssertedNetworkTouch — niemals ein echter seven.io-Call."""

    def _sentinel_post(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        raise AssertedNetworkTouch(
            "httpx.post wurde erreicht — der Guard hat NICHT vor dem "
            "Transport entschieden"
        )

    return _sentinel_post


def _sms_settings(**overrides) -> Settings:
    """Minimal-Settings fuer SMSOutput — sms_to/seven_api_key/gateway_url
    gesetzt, damit SMSOutput.__init__ (can_send_sms()) nicht vorzeitig
    scheitert. seven_sandbox_key wird nur uebergeben, wenn der Aufrufer es
    explizit als Override mitgibt (existiert als Feld noch nicht — #1336)."""
    defaults = dict(
        sms_gateway_url="https://gateway.seven.io/api/sms",
        sms_to="+49000000000",
        sms_from=None,
        seven_api_key="prod-configured-key",
        is_test_mode=False,
    )
    defaults.update(overrides)
    return Settings(**defaults, _env_file=None)


# ---------------------------------------------------------------------------
# AC-1 — Guard blockt Fehlkonfiguration (abweichender Key) VOR dem Transport
# ---------------------------------------------------------------------------

def test_guard_blocks_mismatched_key_before_transport(monkeypatch):
    """AC-1: Given is_test_mode=True und seven_api_key != seven_sandbox_key /
    When SMSOutput(settings).send() aufgerufen wird / Then wirft der Guard
    OutputConfigError, bevor der HTTP-Sentinel erreicht wird.

    RED: heute existiert kein Guard — send() laeuft ungebremst in den
    Sentinel, der AssertedNetworkTouch statt OutputConfigError wirft."""
    calls: list = []
    monkeypatch.setattr(httpx, "post", _make_sentinel(calls))

    settings = _sms_settings(
        is_test_mode=True,
        seven_api_key="prod-configured-key",
        seven_sandbox_key="sandbox-key-abc",
    )
    output = SMSOutput(settings)

    with pytest.raises(OutputConfigError):
        output.send("Betreff", "Testtext")

    assert calls == [], (
        "AC-1: Im Test-Modus mit abweichendem Key darf der HTTP-Transport "
        f"NICHT erreicht werden, gesehen: {calls!r}"
    )


# ---------------------------------------------------------------------------
# AC-2 — Fail-closed ohne provisionierten Sandbox-Key
# ---------------------------------------------------------------------------

def test_guard_fails_closed_without_sandbox_key(monkeypatch):
    """AC-2: Given is_test_mode=True und seven_sandbox_key=None (nicht
    provisioniert) / When send() aufgerufen wird / Then wirft der Guard
    ebenfalls OutputConfigError statt den unveraenderten Prod-Key
    durchzulassen (schliesst die Fallback-Luecke aus dem Telegram-Vorbild).

    RED: heute existiert kein Guard — send() laeuft ungebremst in den
    Sentinel."""
    calls: list = []
    monkeypatch.setattr(httpx, "post", _make_sentinel(calls))

    settings = _sms_settings(
        is_test_mode=True,
        seven_api_key="prod-configured-key",
        # seven_sandbox_key bewusst NICHT gesetzt — Default None (Feld
        # existiert noch nicht, siehe Modul-Docstring).
    )
    output = SMSOutput(settings)

    with pytest.raises(OutputConfigError):
        output.send("Betreff", "Testtext")

    assert calls == [], (
        "AC-2: Ohne provisionierten Sandbox-Key darf der HTTP-Transport "
        f"NICHT erreicht werden, gesehen: {calls!r}"
    )


# ---------------------------------------------------------------------------
# AC-3 — Sandbox laesst durch (Beweis ohne echten Netzwerk-Touch/Kosten)
# ---------------------------------------------------------------------------

def test_guard_passes_through_matching_sandbox_key(monkeypatch):
    """AC-3: Given is_test_mode=True und der aktive seven_api_key ist
    identisch mit seven_sandbox_key / When send() aufgerufen wird / Then
    wirft der Guard nichts und der Transport-Sentinel wird erreicht (Beweis
    'durchgelassen' ohne echten Netzwerk-Touch/echte Kosten).

    RED: das Feld seven_sandbox_key existiert noch nicht auf Settings —
    extra='ignore' verwirft es beim Konstruieren still, der Zugriff wirft
    AttributeError, bevor send() ueberhaupt gerufen wird."""
    calls: list = []
    monkeypatch.setattr(httpx, "post", _make_sentinel(calls))

    settings = _sms_settings(
        is_test_mode=True,
        seven_api_key="sandbox-key-abc",
        seven_sandbox_key="sandbox-key-abc",
    )

    # Vorbedingung: das Feld muss den Sandbox-Key tatsaechlich tragen —
    # scheitert heute mit AttributeError, weil 'seven_sandbox_key' noch kein
    # deklariertes Settings-Feld ist (#1336).
    assert settings.seven_sandbox_key == "sandbox-key-abc", (
        "Vorbedingung geplatzt: Settings.seven_sandbox_key existiert noch "
        "nicht bzw. traegt nicht den Sandbox-Key"
    )

    output = SMSOutput(settings)

    with pytest.raises(AssertedNetworkTouch):
        output.send("Betreff", "Testtext")

    assert len(calls) == 1, (
        "AC-3: Bei uebereinstimmendem Sandbox-Key MUSS der Transport genau "
        f"einmal erreicht werden (durchgelassen), gesehen: {calls!r}"
    )


# ---------------------------------------------------------------------------
# AC-4 — for_testing() swappt seven_api_key auf seven_sandbox_key (beide Zweige)
# ---------------------------------------------------------------------------

def test_for_testing_swaps_seven_api_key_both_branches():
    """AC-4: Given seven_api_key='prod-configured-key' und
    seven_sandbox_key='sandbox-key-abc' / When settings.for_testing()
    aufgerufen wird / Then ist for_testing().seven_api_key == 'sandbox-key-abc'
    — geprueft in BEIDEN Rueckgabezweigen (mit und ohne test_smtp_user/
    test_smtp_pass gesetzt).

    RED: for_testing() fasst seven_api_key heute gar nicht an — bleibt in
    beiden Zweigen unveraendert der Prod-Key."""
    # Zweig 1: ohne Test-SMTP-Creds (config.py-Zweig ohne test_smtp_user/-pass)
    settings_no_creds = Settings(
        seven_api_key="prod-configured-key",
        seven_sandbox_key="sandbox-key-abc",
        test_smtp_user=None,
        test_smtp_pass=None,
        _env_file=None,
    )
    result_no_creds = settings_no_creds.for_testing()
    assert result_no_creds.seven_api_key == "sandbox-key-abc", (
        "Zweig OHNE Test-SMTP-Creds: erwartet seven_api_key='sandbox-key-abc', "
        f"bekam {result_no_creds.seven_api_key!r}"
    )

    # Zweig 2: mit Test-SMTP-Creds gesetzt
    settings_with_creds = Settings(
        seven_api_key="prod-configured-key",
        seven_sandbox_key="sandbox-key-abc",
        test_smtp_user="tester",
        test_smtp_pass="test-secret",
        _env_file=None,
    )
    result_with_creds = settings_with_creds.for_testing()
    assert result_with_creds.seven_api_key == "sandbox-key-abc", (
        "Zweig MIT Test-SMTP-Creds: erwartet seven_api_key='sandbox-key-abc', "
        f"bekam {result_with_creds.seven_api_key!r}"
    )


# ---------------------------------------------------------------------------
# AC-5 — Prod (is_test_mode=False): Guard ist No-Op
# ---------------------------------------------------------------------------

def test_guard_is_noop_in_production_mode(monkeypatch):
    """AC-5: Given is_test_mode=False (Prod) / When SMSOutput(settings).send()
    mit dem unveraenderten Prod-seven_api_key aufgerufen wird / Then ist der
    Guard ein No-Op — kein OutputConfigError, der Prod-Key bleibt exakt der
    konfigurierte Wert, der Transport-Sentinel wird erreicht.

    RED: die Guard-Methode _guard_test_mode_sandbox_key existiert noch nicht
    auf SMSOutput — hasattr(...) schlaegt fehl, bevor irgendetwas anderes
    geprueft wird."""
    calls: list = []
    monkeypatch.setattr(httpx, "post", _make_sentinel(calls))

    settings = _sms_settings(is_test_mode=False, seven_api_key="prod-configured-key")
    output = SMSOutput(settings)

    assert hasattr(output, "_guard_test_mode_sandbox_key"), (
        "AC-5-Vorbedingung: SMSOutput._guard_test_mode_sandbox_key existiert "
        "noch nicht (#1336)"
    )
    # No-Op direkt geprueft: darf in Prod nichts werfen.
    output._guard_test_mode_sandbox_key()

    with pytest.raises(AssertedNetworkTouch):
        output.send("Betreff", "Testtext")

    assert len(calls) == 1, (
        f"AC-5: Prod-Versand muss den Transport erreichen, gesehen: {calls!r}"
    )
    assert settings.seven_api_key == "prod-configured-key", (
        "AC-5: der Prod-Key darf durch den Guard nicht veraendert werden"
    )


# ---------------------------------------------------------------------------
# AC-6 — Inventar-Flip: gateway.seven.io wird TEST_ACCESS
# ---------------------------------------------------------------------------

def test_inventory_flip_to_test_access():
    """AC-6: Given das aktualisierte egress_guard.INVENTORY / When
    INVENTORY['gateway.seven.io'] gelesen wird / Then ist der Wert
    IsolationKind.TEST_ACCESS (die Go-Zwillingsliste wird separat von
    tests/test_egress_inventory_drift.py auf Deckungsgleichheit geprueft).

    RED: aktuell steht der Wert noch auf BLOCKED (praeventive Stilllegung
    2026-07-21, siehe Spec-Purpose)."""
    from app.egress_guard import INVENTORY, IsolationKind

    assert INVENTORY["gateway.seven.io"] is IsolationKind.TEST_ACCESS, (
        "AC-6: erwartet IsolationKind.TEST_ACCESS fuer 'gateway.seven.io', "
        f"aktuell: {INVENTORY['gateway.seven.io']!r}"
    )
