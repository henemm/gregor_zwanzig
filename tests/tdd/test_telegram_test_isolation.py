"""TDD RED — Issue #1363 (Scheibe C von #1337): Telegram-Egress-Isolation ueber
ALLE schreibenden Bot-API-Methoden.

SPEC: docs/specs/modules/egress_guard_telegram.md

`TelegramOutput` hat bereits einen Chat-ID-Guard (`_guard_test_mode_chat_id`,
Issue #1288), aber der prueft nur `settings.telegram_chat_id` in `send()` --
drei weitere schreibende Methoden (`_send_fallback_without_parse_mode`,
`delete_message`, `edit_message_text`) nehmen ihre `chat_id` als Argument
entgegen und werden vom bestehenden Guard nicht erfasst. Ausserdem gibt es noch
KEINEN Token-Guard: ein Staging-Prozess ohne provisionierten Test-Bot-Token
wuerde klaglos ueber den Prod-Bot senden. Diese Tests bauen -- analog zu
`test_sms_test_isolation.py` (#1336) -- das Vorbild aus `telegram.py::
_guard_test_mode_chat_id` (#1288) auf einen Token-Guard sowie einen
argument-basierten Chat-Guard aus, und heben `api.telegram.org` im zentralen
Egress-Waechter von `BLOCKED` auf `TEST_ACCESS`.

Boundary-Sink auf `httpx.post` (Vorbild test_sms_test_isolation.py /
test_telegram_test_mode_guard.py) -- KEIN Live-Telegram-Call. Der Sentinel
zeichnet jeden Aufruf auf und wirft `AssertedNetworkTouch`, sobald der
Transport tatsaechlich erreicht wird -- das beweist positiv (Sentinel FEUERT =
durchgelassen) wie negativ (Sentinel bleibt stumm = der Guard hat VOR dem
Transport entschieden), ohne dass ein Mock die eigene Annahme zurueckspiegelt.

RED-Erwartung (vor Fix):
  - AC-1/AC-2/AC-3: kein Token-/Chat-Argument-Guard existiert -> die jeweilige
    Methode laeuft ungebremst in den Sentinel, der `AssertedNetworkTouch`
    statt `OutputConfigError` wirft -- `pytest.raises(OutputConfigError)`
    schlaegt fehl (die falsche Exception propagiert aus dem Block).
  - AC-4/AC-7: die Vorbedingung `settings.telegram_test_bot_token == ...`
    schlaegt mit `AttributeError` fehl -- das Feld existiert vor #1363 noch
    nicht auf `Settings` (`extra="ignore"` verwirft es beim Konstruieren
    still).
  - AC-5: `for_testing()` fasst `telegram_bot_token` heute gar nicht an --
    bleibt in beiden Zweigen unveraendert der Prod-Token statt auf den
    Test-Bot-Token zu wechseln.
  - AC-6: die Guard-Methoden `_guard_test_mode_bot_token` /
    `_guard_test_mode_target_chat` existieren noch nicht auf `TelegramOutput`
    -- der direkte No-Op-Beweis-Aufruf wirft `AttributeError`.
  - AC-8: `INVENTORY["api.telegram.org"]` ist noch `BLOCKED`, nicht
    `TEST_ACCESS`.
"""
from __future__ import annotations

import httpx
import pytest

from app.config import Settings
from output.channels.base import OutputConfigError
from output.channels.telegram import TelegramOutput

PROD_BOT_TOKEN = "prod-bot-token-abc123"
TEST_BOT_TOKEN = "staging-bot-token-xyz789"
PROD_CHAT_ID = "777000111"
TEST_CHAT_ID = "424242"

# Die 5 schreibenden Methoden (AC-1/AC-2), davon 3 argument-basiert (AC-3).
ALL_FIVE_METHODS = [
    "send",
    "_send_fallback_without_parse_mode",
    "delete_message",
    "edit_message_text",
    "set_my_commands",
]
ARGUMENT_BASED_METHODS = [
    "_send_fallback_without_parse_mode",
    "delete_message",
    "edit_message_text",
]


class AssertedNetworkTouch(Exception):
    """Beweist, dass der HTTP-Transport tatsaechlich erreicht wurde -- ob das
    im jeweiligen Test erwuenscht ist (Durchlass) oder ein Fehler waere (Guard
    haette vorher blockieren muessen), entscheidet der Testfall."""


def _make_sentinel(calls: list):
    """Sentinel fuer httpx.post: zeichnet den Aufruf auf und wirft
    AssertedNetworkTouch -- niemals ein echter Bot-API-Call."""

    def _sentinel_post(*args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        raise AssertedNetworkTouch(
            "httpx.post wurde erreicht -- der Guard hat NICHT vor dem "
            "Transport entschieden"
        )

    return _sentinel_post


def _telegram_settings(**overrides) -> Settings:
    """Minimal-Settings fuer TelegramOutput. `telegram_test_bot_token` wird
    nur uebergeben, wenn der Aufrufer es explizit als Override mitgibt --
    existiert als Feld noch nicht (#1363), extra="ignore" verwirft es beim
    Konstruieren still."""
    defaults = dict(
        telegram_bot_token=PROD_BOT_TOKEN,
        telegram_chat_id=PROD_CHAT_ID,
        telegram_test_chat_id="",
        is_test_mode=False,
    )
    defaults.update(overrides)
    return Settings(**defaults, _env_file=None)


def _invoke(output: TelegramOutput, method_name: str, chat_id: str):
    """Ruft die benannte schreibende Methode mit plausiblen Minimal-Argumenten
    auf -- die konkreten Payload-Inhalte sind fuer die Guard-Tests irrelevant,
    nur ob der Sentinel (httpx.post) erreicht wird."""
    if method_name == "send":
        return output.send("Betreff", "Testtext")
    if method_name == "_send_fallback_without_parse_mode":
        return output._send_fallback_without_parse_mode(chat_id, "Testtext", None, "Betreff")
    if method_name == "delete_message":
        return output.delete_message(chat_id, 123)
    if method_name == "edit_message_text":
        return output.edit_message_text(chat_id, 123, "Neuer Text")
    if method_name == "set_my_commands":
        return output.set_my_commands()
    raise ValueError(f"Unbekannte Methode: {method_name!r}")


# ---------------------------------------------------------------------------
# AC-1 -- Token-Guard blockt Fehlkonfiguration VOR dem Transport (5 Methoden)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method_name", ALL_FIVE_METHODS)
def test_token_guard_blocks_mismatched_bot_token_before_transport(method_name, monkeypatch):
    """AC-1: Given is_test_mode=True und der aktive telegram_bot_token ist
    ungleich telegram_test_bot_token / When eine der 5 schreibenden Methoden
    aufgerufen wird / Then wirft die jeweilige Methode OutputConfigError,
    bevor der HTTP-Sentinel erreicht wird.

    Chat-Konfiguration ist bewusst durchgehend PASSEND (telegram_chat_id ==
    telegram_test_chat_id == TEST_CHAT_ID) -- das isoliert die Aussage "es
    ist wirklich der Token-Guard, der hier blockiert", nicht ein kuenftiger
    Chat-Guard.

    RED: heute existiert kein Token-Guard -- die Methode laeuft ungebremst
    in den Sentinel, der AssertedNetworkTouch statt OutputConfigError wirft."""
    calls: list = []
    monkeypatch.setattr(httpx, "post", _make_sentinel(calls))

    settings = _telegram_settings(
        is_test_mode=True,
        telegram_bot_token=PROD_BOT_TOKEN,
        telegram_test_bot_token=TEST_BOT_TOKEN,
        telegram_chat_id=TEST_CHAT_ID,
        telegram_test_chat_id=TEST_CHAT_ID,
    )
    output = TelegramOutput(settings)

    with pytest.raises(OutputConfigError):
        _invoke(output, method_name, TEST_CHAT_ID)

    assert calls == [], (
        f"AC-1 ({method_name}): Im Test-Modus mit abweichendem Bot-Token darf "
        f"der HTTP-Transport NICHT erreicht werden, gesehen: {calls!r}"
    )


# ---------------------------------------------------------------------------
# AC-2 -- Fail-closed ohne provisionierten Test-Bot-Token (5 Methoden)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method_name", ALL_FIVE_METHODS)
def test_token_guard_fails_closed_without_test_bot_token(method_name, monkeypatch):
    """AC-2: Given is_test_mode=True und telegram_test_bot_token="" (nicht
    provisioniert) / When eine der 5 Methoden aufgerufen wird / Then wirft
    der Token-Guard ebenfalls OutputConfigError statt stillschweigend den
    unveraenderten Prod-Token durchzulassen (Fail-closed gegen die
    Fallback-Luecke aus for_testing()).

    RED: heute existiert kein Token-Guard -- die Methode laeuft ungebremst
    in den Sentinel."""
    calls: list = []
    monkeypatch.setattr(httpx, "post", _make_sentinel(calls))

    settings = _telegram_settings(
        is_test_mode=True,
        telegram_bot_token=PROD_BOT_TOKEN,
        # telegram_test_bot_token bewusst NICHT gesetzt -- Default (Feld
        # existiert noch nicht, siehe Modul-Docstring).
        telegram_chat_id=TEST_CHAT_ID,
        telegram_test_chat_id=TEST_CHAT_ID,
    )
    output = TelegramOutput(settings)

    with pytest.raises(OutputConfigError):
        _invoke(output, method_name, TEST_CHAT_ID)

    assert calls == [], (
        f"AC-2 ({method_name}): Ohne provisionierten Test-Bot-Token darf der "
        f"HTTP-Transport NICHT erreicht werden, gesehen: {calls!r}"
    )


# ---------------------------------------------------------------------------
# AC-3 -- Chat-Argument-Guard blockt (3 argument-basierte Methoden)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method_name", ARGUMENT_BASED_METHODS)
def test_chat_argument_guard_blocks_wrong_target_chat(method_name, monkeypatch):
    """AC-3: Given is_test_mode=True, korrekter telegram_test_bot_token aktiv,
    aber die uebergebene chat_id ist ungleich telegram_test_chat_id / When
    _send_fallback_without_parse_mode, delete_message oder edit_message_text
    mit dieser chat_id aufgerufen wird / Then wirft
    _guard_test_mode_target_chat() OutputConfigError vor dem Sentinel.

    Token-Konfiguration ist bewusst PASSEND (telegram_bot_token ==
    telegram_test_bot_token) -- isoliert die Aussage "es ist wirklich der
    Chat-Argument-Guard", nicht der Token-Guard.

    RED: heute existiert kein Chat-Argument-Guard fuer diese 3 Methoden --
    sie lesen `chat_id` nur als Payload-Wert und laufen ungebremst in den
    Sentinel."""
    calls: list = []
    monkeypatch.setattr(httpx, "post", _make_sentinel(calls))

    settings = _telegram_settings(
        is_test_mode=True,
        telegram_bot_token=TEST_BOT_TOKEN,
        telegram_test_bot_token=TEST_BOT_TOKEN,
        telegram_chat_id=TEST_CHAT_ID,
        telegram_test_chat_id=TEST_CHAT_ID,
    )
    output = TelegramOutput(settings)
    wrong_chat_id = PROD_CHAT_ID  # weicht von telegram_test_chat_id ab

    with pytest.raises(OutputConfigError):
        _invoke(output, method_name, wrong_chat_id)

    assert calls == [], (
        f"AC-3 ({method_name}): Bei abweichender chat_id darf der HTTP-"
        f"Transport NICHT erreicht werden, gesehen: {calls!r}"
    )


# ---------------------------------------------------------------------------
# AC-4 -- Durchlass bei korrekter Konfiguration (5 Methoden)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method_name", ALL_FIVE_METHODS)
def test_guards_pass_through_matching_test_config(method_name, monkeypatch):
    """AC-4: Given is_test_mode=True, aktiver Token == telegram_test_bot_token
    UND (bei den 3 argument-basierten Methoden) chat_id ==
    telegram_test_chat_id / When eine der 5 Methoden aufgerufen wird / Then
    wirft kein Guard und der Transport-Sentinel wird erreicht (Beweis
    "durchgelassen" ohne echten Netzwerk-Touch).

    RED-Grund: die Vorbedingung `settings.telegram_test_bot_token == ...`
    schlaegt mit AttributeError fehl -- das Feld existiert vor #1363 noch
    nicht auf Settings (Vorbild test_sms_test_isolation.py, Test 3)."""
    calls: list = []
    monkeypatch.setattr(httpx, "post", _make_sentinel(calls))

    settings = _telegram_settings(
        is_test_mode=True,
        telegram_bot_token=TEST_BOT_TOKEN,
        telegram_test_bot_token=TEST_BOT_TOKEN,
        telegram_chat_id=TEST_CHAT_ID,
        telegram_test_chat_id=TEST_CHAT_ID,
    )

    # Vorbedingung: das Feld muss den Test-Bot-Token tatsaechlich tragen --
    # scheitert heute mit AttributeError, weil 'telegram_test_bot_token' noch
    # kein deklariertes Settings-Feld ist (#1363).
    assert settings.telegram_test_bot_token == TEST_BOT_TOKEN, (
        "Vorbedingung geplatzt: Settings.telegram_test_bot_token existiert "
        "noch nicht bzw. traegt nicht den Test-Bot-Token"
    )

    output = TelegramOutput(settings)

    with pytest.raises(AssertedNetworkTouch):
        _invoke(output, method_name, TEST_CHAT_ID)

    assert len(calls) == 1, (
        f"AC-4 ({method_name}): Bei uebereinstimmender Test-Konfiguration "
        f"MUSS der Transport genau einmal erreicht werden (durchgelassen), "
        f"gesehen: {calls!r}"
    )


# ---------------------------------------------------------------------------
# AC-5 -- for_testing() swappt telegram_bot_token (beide Zweige)
# ---------------------------------------------------------------------------

def test_for_testing_swaps_telegram_bot_token_both_branches():
    """AC-5: Given telegram_bot_token='prod-token' und
    telegram_test_bot_token='staging-token' / When settings.for_testing()
    aufgerufen wird / Then ist for_testing().telegram_bot_token ==
    'staging-token' in BEIDEN Rueckgabezweigen (mit und ohne gesetzte
    Test-SMTP-Creds).

    RED: for_testing() fasst telegram_bot_token heute gar nicht an -- bleibt
    in beiden Zweigen unveraendert der Prod-Token."""
    # Zweig 1: ohne Test-SMTP-Creds (config.py-Zweig ohne test_smtp_user/-pass)
    settings_no_creds = Settings(
        telegram_bot_token="prod-token",
        telegram_test_bot_token="staging-token",
        test_smtp_user=None,
        test_smtp_pass=None,
        _env_file=None,
    )
    result_no_creds = settings_no_creds.for_testing()
    assert result_no_creds.telegram_bot_token == "staging-token", (
        "Zweig OHNE Test-SMTP-Creds: erwartet telegram_bot_token="
        f"'staging-token', bekam {result_no_creds.telegram_bot_token!r}"
    )

    # Zweig 2: mit Test-SMTP-Creds gesetzt
    settings_with_creds = Settings(
        telegram_bot_token="prod-token",
        telegram_test_bot_token="staging-token",
        test_smtp_user="tester",
        test_smtp_pass="test-secret",
        _env_file=None,
    )
    result_with_creds = settings_with_creds.for_testing()
    assert result_with_creds.telegram_bot_token == "staging-token", (
        "Zweig MIT Test-SMTP-Creds: erwartet telegram_bot_token="
        f"'staging-token', bekam {result_with_creds.telegram_bot_token!r}"
    )


# ---------------------------------------------------------------------------
# AC-6 -- Prod (is_test_mode=False): beide Guards sind No-Op (5 Methoden)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("method_name", ALL_FIVE_METHODS)
def test_guards_are_noop_in_production_mode(method_name, monkeypatch):
    """AC-6: Given is_test_mode=False (Prod) / When TelegramOutput(settings)
    eine der 5 Methoden mit unverändertem Prod-telegram_bot_token aufruft /
    Then werfen weder Token- noch Chat-Argument-Guard, Prod-Token/-Chat
    bleiben exakt die konfigurierten Werte, der Transport-Sentinel wird
    erreicht.

    RED: die Guard-Methoden _guard_test_mode_bot_token und
    _guard_test_mode_target_chat existieren noch nicht auf TelegramOutput --
    der direkte No-Op-Beweis-Aufruf wirft AttributeError, bevor irgendetwas
    anderes geprueft wird."""
    calls: list = []
    monkeypatch.setattr(httpx, "post", _make_sentinel(calls))

    settings = _telegram_settings(
        is_test_mode=False,
        telegram_bot_token=PROD_BOT_TOKEN,
        telegram_chat_id=PROD_CHAT_ID,
    )
    output = TelegramOutput(settings)

    # Direkter No-Op-Beweis -- schlaegt heute mit AttributeError fehl, weil
    # diese Guard-Methoden vor #1363 noch nicht existieren.
    output._guard_test_mode_bot_token()
    output._guard_test_mode_target_chat(PROD_CHAT_ID)

    with pytest.raises(AssertedNetworkTouch):
        _invoke(output, method_name, PROD_CHAT_ID)

    assert len(calls) == 1, (
        f"AC-6 ({method_name}): Prod-Versand muss den Transport erreichen, "
        f"gesehen: {calls!r}"
    )
    assert settings.telegram_bot_token == PROD_BOT_TOKEN, (
        "AC-6: der Prod-Token darf durch den Guard nicht veraendert werden"
    )
    assert settings.telegram_chat_id == PROD_CHAT_ID, (
        "AC-6: die Prod-Chat-ID darf durch den Guard nicht veraendert werden"
    )


# ---------------------------------------------------------------------------
# AC-7 -- Regressionsschutz: bestehender #1288-Chat-Guard bleibt unveraendert
# ---------------------------------------------------------------------------

def test_existing_1288_chat_guard_unchanged(monkeypatch):
    """AC-7: Given dieselbe Chat-ID-Fehlkonfiguration wie vor #1363 (Mismatch
    ueber settings.telegram_chat_id in send()) / When send() aufgerufen wird
    / Then ist Fehlertext und Verhalten von _guard_test_mode_chat_id()
    identisch zum Stand vor dieser Spec -- kein Regress von #1288.

    Token-Konfiguration ist bewusst PASSEND (telegram_bot_token ==
    telegram_test_bot_token) -- isoliert die Aussage "es ist wirklich der
    alte Chat-Guard (ueber settings.telegram_chat_id), der hier greift",
    nicht ein kuenftiger Token-Guard.

    RED-Grund: die Vorbedingung `settings.telegram_test_bot_token == ...`
    schlaegt mit AttributeError fehl -- das Feld existiert vor #1363 noch
    nicht auf Settings. Der eigentliche Fehlertext ist bereits heute stabil
    (der #1288-Guard existiert unveraendert) -- diese Vorbedingung stellt nur
    sicher, dass der Test nach der Implementierung wirklich den ALTEN
    Chat-Guard prueft und nicht versehentlich vom neuen Token-Guard maskiert
    wird."""
    calls: list = []
    monkeypatch.setattr(httpx, "post", _make_sentinel(calls))

    settings = _telegram_settings(
        is_test_mode=True,
        telegram_bot_token=TEST_BOT_TOKEN,
        telegram_test_bot_token=TEST_BOT_TOKEN,
        telegram_chat_id=PROD_CHAT_ID,
        telegram_test_chat_id=TEST_CHAT_ID,
    )

    assert settings.telegram_test_bot_token == TEST_BOT_TOKEN, (
        "Vorbedingung geplatzt: Settings.telegram_test_bot_token existiert "
        "noch nicht bzw. traegt nicht den Test-Bot-Token"
    )

    output = TelegramOutput(settings)

    with pytest.raises(OutputConfigError) as exc_info:
        output.send("Betreff", "Testnachricht")

    assert str(exc_info.value) == (
        f"[telegram] Test-Modus aktiv, aber chat_id={PROD_CHAT_ID!r} ist "
        "nicht die konfigurierte Test-Chat-ID (GZ_TELEGRAM_TEST_CHAT_ID) — "
        "Versand blockiert (Issue #1288)."
    ), f"Fehlertext des #1288-Guards hat sich veraendert: {exc_info.value!r}"

    assert calls == [], (
        f"AC-7: Der bestehende #1288-Guard muss weiterhin VOR jedem POST "
        f"greifen, gesehen: {calls!r}"
    )


# ---------------------------------------------------------------------------
# AC-8 -- Inventar-Flip: api.telegram.org wird TEST_ACCESS
# ---------------------------------------------------------------------------

def test_inventory_flip_to_test_access():
    """AC-8: Given das aktualisierte egress_guard.INVENTORY / When
    INVENTORY['api.telegram.org'] gelesen wird / Then ist der Wert
    IsolationKind.TEST_ACCESS (die Go-Zwillingsliste wird separat von
    tests/test_egress_inventory_drift.py auf Deckungsgleichheit geprueft).

    RED: aktuell steht der Wert noch auf BLOCKED (praeventive Stilllegung,
    siehe Spec-Purpose)."""
    from app.egress_guard import INVENTORY, IsolationKind

    assert INVENTORY["api.telegram.org"] is IsolationKind.TEST_ACCESS, (
        "AC-8: erwartet IsolationKind.TEST_ACCESS fuer 'api.telegram.org', "
        f"aktuell: {INVENTORY['api.telegram.org']!r}"
    )
